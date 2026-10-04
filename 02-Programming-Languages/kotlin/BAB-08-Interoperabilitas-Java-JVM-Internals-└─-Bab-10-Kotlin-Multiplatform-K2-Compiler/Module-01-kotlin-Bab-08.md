# SEKSI 01 — IDENTITAS MODUL

* **Kode Modul:** KOT-MOD-08-01
* **Nama Modul:** Interoperabilitas Java, JVM Internals, Kotlin Multiplatform (KMP), dan K2 Compiler Architecture
* **Kategori:** 02-Programming-Languages
* **Track:** Kotlin Core to Systems Architecture
* **Tingkat Kesulitan:** Advanced / L4-L5
* **Prasyarat:** Pemahaman mendalam tentang JVM Memory Model (Heap, Stack, Metaspace), Java Bytecode Fundamentals (`javap`), Object-Oriented System Design, Kotlin Type System, Coroutines Execution Context.

---

# SEKSI 02 — LEARNING OBJECTIVES

Pada akhir modul ini, software engineer diharapkan mampu:

1. **Menganalisis Mekanisme Bytecode Interop:** Membedah transformasi sintaksis Kotlin ke dalam Java Virtual Machine (JVM) bytecode, mencakup resolusi *platform types*, konvensi pemanggilan *synthetic accessors*, *mangled names*, dan *static bridge generation*.
2. **Mengevaluasi Pipeline K2 Compiler:** Menjelaskan secara presisi evolusi arsitektur compiler Kotlin dari frontend K1 (PSI-based) ke K2 berbasis *Frontend Intermediate Representation* (FIR) dan *unified Backend IR* (IR Lowering).
3. **Mendesain Arsitektur Kotlin Multiplatform (KMP):** Mengimplementasikan kode multi-target lintas JVM, Native, dan JS/Wasm menggunakan mekanisme `expect`/`actual`, hirarki source-set modern, serta memahami link-time boundary antar runtime platform.
4. **Mengoptimalkan Performa & Binary Compatibility:** Menerapkan anotasi JVM (`@JvmStatic`, `@JvmOverloads`, `@JvmName`, `@Throws`, `@JvmField`, `@JvmInline`) secara tepat guna mengeliminasi runtime overhead dan menjaga *Application Binary Interface* (ABI) compatibility dalam lingkungan *mixed-language enterprise*.
5. **Melakukan Debugging & Observasi Tingkat Rendah:** Melakukan reverse engineering terhadap artefak `.class` hasil kompilasi, mendiagnosis *memory leak* pada perbatasan interop, dan menganalisis tahapan resolusi tipe K2 melalui FIR dumps.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Dualitas Abstraksi Kotlin dan Realitas JVM
JVM tidak mengenal *extension functions*, *named parameters*, *coroutines*, *inline value classes*, maupun *null safety* bawaan di tingkat instruction set. JVM hanya memahami class, interface, field, method descriptors, dan instruction set seperti `invokevirtual`, `invokestatic`, `invokeinterface`, `invokespecial`, serta `invokedynamic`. 

Mental model Anda harus melihat Kotlin sebagai **kompiler transformatif tingkat tinggi** yang memetakan konstruksi modern ke dalam batasan kaku Java Class File Format specification (JSR-924). Kode Kotlin yang tampak sederhana sering kali diubah menjadi *synthetic classes*, *bridges*, dan *hidden check assertions* (`Intrinsics.checkNotNullParameter`).

### Paradigma K2: Dari AST Lambat ke Fast Semantic FIR
Pada compiler K1 generasi lama, abstraksi *Program Structure Interface* (PSI) mengikat semantic analysis langsung ke representasi AST dari IDE IntelliJ. Konsekuensinya adalah pemborosan alokasi heap dan resolusi tipe lambat (*cyclic resolution passes*).

Mental model K2 mengadopsi struktur compiler modern:
* **Single-Pass Parsing & Light Desugaring:** Mengubah source code langsung menjadi struktur data datar dan efisien bernama **Frontend Intermediate Representation (FIR)**.
* **Unified Semantic Model:** Resolusi nama, *type inference*, dan *control flow analysis* dieksekusi secara terpadu tanpa re-resolusi berulang.
* **Shared Backend IR:** Mengonversi FIR menjadi Backend Intermediate Representation (IR), di mana seluruh platform (JVM, JS, Native, Wasm) menerima representasi seragam sebelum dilakukan *lowering* ke target bytecode atau mesin instruksi target (LLVM/Machine Code).

```
[Mental Model: Pipeline Abstraksi]
Kotlin Source -> FIR (Semantic/Type Check) -> Kotlin IR -> Lowering -> Target Bytecode / LLVM IR
```

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah perbandingan arsitektural kompilasi antara K1 (arsitektur legasi) dan K2 (arsitektur modern terpadu), serta jalur kompilasi Kotlin Multiplatform:

```
+-----------------------------------------------------------------------------------+
|                        ARSITEKTUR KOMPILASI KOTLIN (K1 vs K2)                    |
+-----------------------------------------------------------------------------------+

     [K1 ARCHITECTURE] (Legacy)
     +-------------+      +-------------------+      +----------------------------+
     | Kotlin Src  | ---> | Lexer / Parser    | ---> | PSI Tree                   |
     +-------------+      +-------------------+      +-------------+--------------+
                                                                   |
                                                                   v
                                                     +----------------------------+
                                                     | Type Checker & Resolution  |
                                                     | (ResolveSession, BindingCtx)|
                                                     +-------------+--------------+
                                                                   |  (Lambat, Memakan
                                                                   v   Banyak Heap)
                                                     +----------------------------+
                                                     | Old JVM Backend / IR Gen   |
                                                     +-------------+--------------+
                                                                   |
                                                                   v
                                                     [ JVM Bytecode / JS / Native ]

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 

     [K2 ARCHITECTURE] (Modern, High-Performance)
     +-------------+      +-------------------+      +----------------------------+
     | Kotlin Src  | ---> | Light Tree /      | ---> | FIR (Frontend IR)          |
     | (JVM/Native)|      | Raw FIR Builder   |      | Tree Construction          |
     +-------------+      +-------------------+      +-------------+--------------+
                                                                   |
                                                                   v
                                                     +----------------------------+
                                                     | FIR Resolvers              |
                                                     | - Contracts & Inference    |
                                                     | - Status, Imports, SuperQ  |
                                                     +-------------+--------------+
                                                                   |
                                                                   v
                                                     +----------------------------+
                                                     | Backend IR (Common IR)     |
                                                     +-------------+--------------+
                                                                   |
                      +--------------------------------------------+--------------------------------------------+
                      |                                            |                                            |
                      v                                            v                                            v
        +----------------------------+               +----------------------------+               +----------------------------+
        | JVM Backend IR Lowerings   |               | Native Backend (LLVM IR)   |               | JS / Wasm Backend Lowering |
        +--------------+-------------+               +--------------+-------------+               +--------------+-------------+
                       |                                            |                                            |
                       v                                            v                                            v
               [ .class Files ]                              [ Mach-O / ELF ]                             [ .wasm / .js ]
```

### Alur Eksekusi Kotlin Multiplatform & SourceSet Compilation

```
                +---------------------------------+
                |        commonMain (FIR)         |  <-- Platform Agnostic Models,
                |   expect fun getDeviceId(): Id  |      Business Logic, Protocols
                +----------------+----------------+
                                 |
                 +---------------+---------------+
                 |                               |
                 v                               v
  +------------------------------+ +------------------------------+
  |        jvmMain (FIR)         | |      nativeMain (FIR)        |
  |  actual fun getDeviceId()    | |  actual fun getDeviceId()    |
  |  [Menggunakan java.util.UUID]| |  [Menggunakan POSIX UUID]    |
  +--------------+---------------+ +--------------+---------------+
                 |                                |
                 v (JVM IR Lowering)              v (Konan LLVM Lowering)
  +------------------------------+ +------------------------------+
  |    Bytecode (.class / JAR)   | |  Native Binary (Framework)   |
  +------------------------------+ +------------------------------+
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. FIR (Frontend Intermediate Representation)
FIR menyatukan representasi sintaksis dan semantik ke dalam satu pohon objek yang tidak dapat diubah (immutable-by-phase). Tidak seperti K1 yang mengandalkan `BindingContext` (berupa hash map besar berisi node AST ke metadata resolusi), FIR menyimpan informasi tipe langsung di dalam node FIR itu sendiri:
* `FirElement`: Basis seluruh struktur sintaksis.
* `FirDeclaration`: Representasi fungsi, kelas, atau properti.
* `FirResolvedTypeRef`: Node yang secara eksplisit menyimpan hasil inferensi tipe setelah *type resolution phase*.

### 2. IR Lowering
Backend Kotlin bekerja berdasarkan konsep **Lowering**. Lowering adalah transformasi modular dari Backend IR ke Backend IR yang lebih sederhana, mendekati instruksi bahasa mesin target. 
* *InnerClassLowering*: Mengekstrak *inner class* menjadi kelas level paket dengan referensi `this$0`.
* *CoroutinesLowering*: Membedah fungsi `suspend` menjadi *State Machine* berbasis `ContinuationImpl`, membuat method turunan dengan parameter `Continuation<? super Unit>`.
* *JvmInlineClassLowering*: Menghapus pembungkus objek (*unboxing*) dari `value class` dan mengganti tanda tangan method pemanggil dengan tipe primitif dasarnya.

### 3. Java Interoperability Internals: Mangling & Bridge Methods
Untuk mempertahankan enkapsulasi dan integrasi mulus dengan Java, kompiler Kotlin melakukan modifikasi nama (*name mangling*):
* **Internal Visibility:** Fungsi dengan visibilitas `internal` di-compile ke JVM dengan nama:  
  `namaFungsi$module_name_buildType()`  
  Hal ini mencegah pemanggilan sembarangan dari Java, karena karakter `$` tidak valid secara konvensional pada sintaks identifier Java (meski valid secara bytecode).
* **Inline Classes (Value Classes):** Fungsi yang menerima `value class` dimodifikasi namanya menggunakan hash struktural tipe:  
  `fun process(id: UserId)` di-compile menjadi `process-5Xy4z0k(String id)`.
* **Platform Types (`T!`):** Di Kotlin, tipe data yang berasal dari Java tanpa anotasi nullability dinyatakan sebagai tipe fleksibel (*flexible type*) `T..T?`. Kotlin tidak melakukan pemeriksaan null saat penugasan, melainkan menyisipkan bytecode `checkNotNull` secara otomatis sesaat sebelum nilai tersebut dide-reference atau dimasukkan ke konteks non-null Kotlin.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Memory Mapping & JVM Bytecode Mechanics

Kotlin menyediakan serangkaian instruksi khusus ke JVM untuk menghasilkan bytecode spesifik yang optimal. Memahami instruksi tingkat rendah ini penting untuk mencegah *overhead* alokasi objek runtime.

#### A. Anotasi Interoperabilitas Tingkat Lanjut

1. **`@JvmStatic`**
   * *Tanpa `@JvmStatic`:* JVM menghasilkan singleton `Companion` object instance. Pemanggilan dari Java mengharuskan akses instance: `MyClass.Companion.doSomething();`. Bytecode yang dipanggil adalah `GETSTATIC MyClass.Companion : LMyClass$Companion;` diikuti `INVOKEVIRTUAL MyClass$Companion.doSomething ()V`.
   * *Dengan `@JvmStatic`:* Kompiler membuat *static bridge method* langsung pada level kelas terluar `MyClass.class`. Java dapat memanggil langsung `MyClass.doSomething();`. Bytecode yang dihasilkan: `INVOKESTATIC MyClass.doSomething ()V`, yang kemudian mendelegasikan panggilan ke singleton companion tanpa alokasi overhead.

2. **`@JvmField`**
   * Secara default, `val x: Int = 10` di-compile menjadi private field `private final int x = 10;` lengkap dengan getter `public final int getX()`.
   * `@JvmField` menginstruksikan backend compiler untuk **menghilangkan getter/setter** dan mengekspos field tersebut sebagai `public final int x = 10;` murni. Hal ini krusial saat bekerja dengan Java Reflection, Serialization libraries, atau performa ekstrim yang menghindari invoke overhead.

3. **`@JvmOverloads`**
   * Kotlin mendukung argumen default: `fun connect(host: String, port: Int = 8080)`.
   * Secara internal, kompiler menghasilkan sebuah *synthetic method*:  
     `public static synthetic void connect$default(String, int, int, Object)`.
   * Java tidak dapat melihat argumen default. Menggunakan `@JvmOverloads` memaksa kompiler menghasilkan *overloaded methods*:
     * `public void connect(String host, int port)`
     * `public void connect(String host)` -> mendelegasikan ke method pertama dengan port 8080.

4. **`@Throws`**
   * Kotlin tidak memiliki *Checked Exceptions*. Semua exception bersifat *unchecked*.
   * Jika method Kotlin melempar `IOException`, Java yang memanggil method tersebut tidak dapat menangkapnya dalam blok `try { ... } catch (IOException e)` jika compiler Java tidak melihat deklarasi `throws IOException` pada signature bytecode method.
   * `@Throws(IOException::class)` menambahkan atribut `Exceptions` pada table metadata Java classfile method.

#### B. Mekanisme `expect` / `actual` di K2 Compiler

Pada K2, resolusi `expect`/`actual` dilakukan di level Frontend Intermediate Representation (FIR) dan Backend IR:
1. **Weak Expect/Actual (Typealiasing):** Kotlin memungkinkan `expect class PlatformAtomicRef<T>` diselesaikan dengan `actual typealias PlatformAtomicRef<T> = java.util.concurrent.atomic.AtomicReference<T>` di JVM. K2 memvalidasi bahwa seluruh *shape* kelas (fungsi, field, parameter tipe, variansi) pada class target Java memenuhi kontrak `expect`.
2. **Strong Expect/Actual:** Jika `actual` diimplementasikan sebagai kelas baru, IR lowering memverifikasi kompatibilitas binary dan memastikan penyesuaian symbol linkage antar compilation unit.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL (Step-by-step)

Implementasi berikut menunjukkan bagaimana Kotlin berinteraksi dengan ekosistem Java pada tingkat bytecode, penggunaan metadata kompilasi, serta implementasi KMP `expect`/`actual`.

### Struktur File
```
├── commonMain/
│   └── kotlin/com/architect/kmp/PlatformCrypto.kt
├── jvmMain/
│   ├── kotlin/com/architect/kmp/PlatformCrypto.jvm.kt
│   └── kotlin/com/architect/kmp/JavaInteropBridge.kt
└── javaMain/
    └── java/com/architect/kmp/EnterpriseLegacyConsumer.java
```

#### 1. Definisi KMP Abstraksi (`commonMain/kotlin/.../PlatformCrypto.kt`)
```kotlin
package com.architect.kmp

// Definisi expect untuk modul kriptografi multiplatform
expect class PlatformCrypto() {
    val platformName: String
    fun hashSha256(input: ByteArray): ByteArray
}

// Inline value class untuk performa tanpa alokasi heap di target platform
@JvmInline
value class SecureToken(val raw: String) {
    init {
        require(raw.isNotEmpty()) { "Token tidak boleh kosong" }
    }
}
```

#### 2. Implementasi Platform JVM (`jvmMain/kotlin/.../PlatformCrypto.jvm.kt`)
```kotlin
package com.architect.kmp

import java.security.MessageDigest

actual class PlatformCrypto {
    actual val platformName: String = "JVM: ${System.getProperty("java.version")}"

    actual fun hashSha256(input: ByteArray): ByteArray {
        val digest = MessageDigest.getInstance("SHA-256")
        return digest.digest(input)
    }
}
```

#### 3. Implementasi Interop JVM Komprehensif (`jvmMain/kotlin/.../JavaInteropBridge.kt`)
```kotlin
@file:JvmName("CryptoBridgeUtils") // Mengubah nama static class hasil kompilasi file

package com.architect.kmp

import java.io.IOException

class CryptoSecurityService private constructor(
    @JvmField val engineName: String // Diekspos sebagai public field tanpa getter
) {
    companion object {
        private const val DEFAULT_BUFFER_SIZE = 4096

        @JvmField
        val INSTANCE: CryptoSecurityService = CryptoSecurityService("DefaultEngine")

        @JvmStatic
        fun getSingletonEngine(): CryptoSecurityService {
            return INSTANCE
        }
    }

    @JvmOverloads
    @Throws(IOException::class)
    fun processData(data: ByteArray, bufferSize: Int = DEFAULT_BUFFER_SIZE, dryRun: Boolean = false): Int {
        if (data.isEmpty()) {
            throw IOException("Data payload buffer kosong, operasi dibatalkan.")
        }
        if (dryRun) return 0
        
        return data.size + bufferSize
    }

    // Nama fungsi di-mangle untuk Java demi menghindari collision atau memodifikasi konvensi
    @JvmName("executeCustomComputation")
    fun execute(token: SecureToken): String {
        return "Processed-${token.raw}"
    }
}
```

#### 4. Konsumen Java Legacy (`javaMain/java/.../EnterpriseLegacyConsumer.java`)
```java
package com.architect.kmp;

import java.io.IOException;

public class EnterpriseLegacyConsumer {

    public static void main(String[] args) {
        // 1. Memanggil static method yang di-generate via @JvmStatic
        CryptoSecurityService service = CryptoSecurityService.getSingletonEngine();

        // 2. Mengakses field langsung via @JvmField (zero overhead getter)
        System.out.println("Engine: " + service.engineName);

        // 3. Menguji @JvmOverloads
        try {
            byte[] dummyData = new byte[]{1, 2, 3};
            // Java dapat memanggil overloaded method yang di-generate secara sintesis
            int processedBytes = service.processData(dummyData);
            System.out.println("Processed: " + processedBytes);

            // Memanggil overloaded versi penuh
            int detailedBytes = service.processData(dummyData, 1024, false);
            System.out.println("Detailed Processed: " + detailedBytes);

            // Menangkap Checked Exception yang diekspos via @Throws
            service.processData(new byte[0]);
        } catch (IOException e) {
            System.err.println("Berhasil menangkap checked exception dari Kotlin: " + e.getMessage());
        }

        // 4. Memanggil method dengan @JvmName dan inline class (unboxed parameter)
        // Di Java, SecureToken di-unwrap menjadi String primitif
        String result = service.executeCustomComputation("SECURE_SECRET_TOKEN_XYZ");
        System.out.println("Hasil: " + result);

        // 5. Mengakses method tingkat file dengan @file:JvmName
        // Defaultnya JavaInteropBridgeKt, diubah menjadi CryptoBridgeUtils
        // (Jika ada fungsi top-level di file tersebut)
    }
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis Bytecode: `CryptoSecurityService.class`
Menggunakan utilitas `javap -c -v com.architect.kmp.CryptoSecurityService`:

```
public final class com.architect.kmp.CryptoSecurityService
  minor version: 0
  major version: 52 // Java 8 compatibility bytecode target
  flags: ACC_PUBLIC, ACC_FINAL, ACC_SUPER
```

1. **Anotasi `@JvmField val engineName: String`**
   ```
   public final java.lang.String engineName;
     descriptor: Ljava/lang/String;
     flags: ACC_PUBLIC, ACC_FINAL
   ```
   *Analisis:* Kompiler Kotlin tidak membuat method `public final java.lang.String getEngineName()`. Sebaliknya, field dideklarasikan dengan flag `ACC_PUBLIC`. Ini menghemat slot *constant pool* untuk method descriptor dan instruksi call stack `invokevirtual` dari Java.

2. **Anotasi `@JvmStatic fun getSingletonEngine()`**
   ```
   public static final com.architect.kmp.CryptoSecurityService getSingletonEngine();
     descriptor: ()Lcom/architect/kmp/CryptoSecurityService;
     flags: ACC_PUBLIC, ACC_STATIC, ACC_FINAL
     Code:
       stack=1, locals=0, args_size=0
          0: getstatic     #12 // Field Companion:Lcom/architect/kmp/CryptoSecurityService$Companion;
          3: invokevirtual #15 // Method com/architect/kmp/CryptoSecurityService$Companion.getSingletonEngine:()Lcom/architect/kmp/CryptoSecurityService;
          6: areturn
   ```
   *Analisis:* Kompiler menambahkan static method pada kelas induk (`ACC_STATIC`). Di dalamnya, instruksi `getstatic` memuat instance singleton Companion, kemudian memanggil method `getSingletonEngine` miliknya secara delegatif via `invokevirtual`.

3. **Anotasi `@Throws(IOException::class)` & `@JvmOverloads` pada `processData`**
   ```
   public final int processData(byte[], int) throws java.io.IOException;
     descriptor: ([BI)I
     flags: ACC_PUBLIC, ACC_FINAL
     Exceptions:
       throws java.io.IOException

   public final int processData(byte[]) throws java.io.IOException;
     descriptor: ([B)I
     flags: ACC_PUBLIC, ACC_FINAL
     Exceptions:
       throws java.io.IOException
   ```
   *Analisis:* `@JvmOverloads` menciptakan 3 variasi method secara otomatis di class file. Tanpa anotasi ini, hanya signature method lengkap `processData(byte[], int, boolean)` yang dapat diakses Java. Atribut `Exceptions: throws java.io.IOException` dicatat dalam classfile, memungkinkan javac melakukan *compile-time checked exception validation*.

4. **Anotasi `@JvmName("executeCustomComputation")` pada Value Class Parameter**
   ```
   public final java.lang.String executeCustomComputation(java.lang.String);
     descriptor: (Ljava/lang/String;)Ljava/lang/String;
     flags: ACC_PUBLIC, ACC_FINAL
   ```
   *Analisis:* `SecureToken` mengalami *unboxing* karena proses IR lowering (`JvmInlineClassLowering`). Di level bytecode, tipe datanya direduksi langsung menjadi `java.lang.String`. Karena kita menyematkan `@JvmName`, Java dapat memanggil fungsi ini tanpa terkena algoritma mangling standar Kotlin (yang biasanya menghasilkan nama seperti `execute-xK1Y(String token)`).

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario: Arsitektur Multi-Platform Core Banking Cryptographic SDK
Sebuah bank multinasional memiliki aplikasi Mobile Android (Kotlin), iOS (Swift via Kotlin Multiplatform), dan Sistem Kliring Enterprise (Java 11/17 Spring Boot Backend). Mereka membutuhkan shared library kriptografi untuk melakukan penandatanganan payload transaksi finansial.

#### Kendala Arsitektur:
1. **Performa Ekstrim Backend Java:** Service Spring Boot menangani 45.000 Request per Second (RPS). Tidak boleh ada alokasi objek Kotlin wrapper yang berlebihan (memicu Garbage Collection pause).
2. **Checked Exception Compatibility:** Java client mewajibkan *checked exception* (`DigitalSignatureException`) agar memenuhi arsitektur kontrol transaksi Spring.
3. **Zero Platform Leakage di KMP:** Logic hash dan signature engine harus menggunakan implementasi hardware-accelerated pada target JVM (Java Cryptography Architecture / JCA) dan CommonCrypto pada iOS target.
4. **Migrasi Kompilasi K2:** SDK harus memanfaatkan compiler Kotlin 2.0 (K2) untuk memangkas waktu *clean build* pipeline CI/CD yang sebelumnya memakan waktu 40 menit di K1.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Di bawah ini adalah implementasi end-to-end multiplatform cryptographic module dengan optimasi backend dan K2 compiler pipeline.

### Konfigurasi Multiplatform Gradle (`build.gradle.kts`)
```kotlin
plugins {
    alias(libs.plugins.kotlinMultiplatform) // Kotlin 2.0.0+
}

kotlin {
    // Explicitly configure K2 Compiler
    jvmToolchain(17)

    jvm {
        compilations.all {
            compileTaskProvider.configure {
                compilerOptions {
                    freeCompilerArgs.addAll(
                        "-Xjvm-default=all",          // Generate default methods in interfaces
                        "-Xbackend-threads=4",        // K2 parallel IR backend generation
                        "-Xjsr305=strict"             // Strict null-safety for Java Interop
                    )
                }
            }
        }
    }

    listOf(
        iosX64(),
        iosArm64(),
        iosSimulatorArm64()
    ).forEach { iosTarget ->
        iosTarget.binaries.framework {
            baseName = "BankCoreSecurity"
            isStatic = true
        }
    }

    sourceSets {
        commonMain.dependencies {
            // No external dependencies to keep it pure and lightweight
        }
        jvmMain.dependencies {
            // Enterprise JVM cryptographic provider
            implementation("org.bouncycastle:bcprov-jdk18on:1.77")
        }
    }
}
```

### 1. `commonMain/kotlin/com/bank/core/CryptoEngine.kt`
```kotlin
package com.bank.core

// Exception standar domain enterprise
open class BankSecurityException(message: String, cause: Throwable? = null) : Exception(message, cause)

class InvalidPayloadException(message: String) : BankSecurityException(message)

// Inline Value Class untuk mencegah alokasi String berulang di heap
@JvmInline
value class TransactionSignature(val signatureHex: String)

expect class NativeCryptoEngine() {
    fun signPayload(payload: ByteArray, privateKeyDer: ByteArray): TransactionSignature
}

interface SignatureVerifier {
    fun verify(payload: ByteArray, signature: TransactionSignature, publicKeyDer: ByteArray): Boolean
}
```

### 2. `jvmMain/kotlin/com/bank/core/NativeCryptoEngine.jvm.kt`
```kotlin
package com.bank.core

import java.io.IOException
import java.security.KeyFactory
import java.security.Signature
import java.security.spec.PKCS8EncodedKeySpec

actual class NativeCryptoEngine {

    @Throws(BankSecurityException::class, IOException::class)
    @JvmName("signTransactionPayload")
    actual fun signPayload(payload: ByteArray, privateKeyDer: ByteArray): TransactionSignature {
        if (payload.isEmpty()) {
            throw InvalidPayloadException("Payload transaksi kosong.")
        }

        try {
            val keySpec = PKCS8EncodedKeySpec(privateKeyDer)
            val kf = KeyFactory.getInstance("RSA")
            val privateKey = kf.generatePrivate(keySpec)

            val sig = Signature.getInstance("SHA256withRSA")
            sig.initSign(privateKey)
            sig.update(payload)
            val signatureBytes = sig.sign()

            // Mengonversi byte array ke Hex string secara efisien
            val hexString = signatureBytes.joinToString("") { "%02x".format(it) }
            return TransactionSignature(hexString)
        } catch (e: Exception) {
            throw BankSecurityException("Gagal menandatangani payload: ${e.message}", e)
        }
    }
}
```

### 3. Java Spring Boot Service Consumer (`EnterpriseSignService.java`)
```java
package com.bank.enterprise;

import com.bank.core.BankSecurityException;
import com.bank.core.InvalidPayloadException;
import com.bank.core.NativeCryptoEngine;

import java.io.IOException;
import java.nio.charset.StandardCharsets;

public class EnterpriseSignService {

    private final NativeCryptoEngine cryptoEngine;

    public EnterpriseSignService() {
        // Instansiasi engine Kotlin yang bersih di Java
        this.cryptoEngine = new NativeCryptoEngine();
    }

    public String processPaymentSigning(String rawTransactionPayload, byte[] rsaKeyDer) {
        byte[] payloadBytes = rawTransactionPayload.getBytes(StandardCharsets.UTF_8);

        try {
            // Value class TransactionSignature direduksi menjadi method yang mengembalikan String murni!
            // Function name tetap stabil via @JvmName
            String hexSignature = cryptoEngine.signTransactionPayload(payloadBytes, rsaKeyDer);
            
            return hexSignature;
        } catch (InvalidPayloadException e) {
            // Checked exception dari Kotlin berhasil ditangkap tanpa runtime crash
            System.err.println("Validation Error: " + e.getMessage());
            throw new IllegalArgumentException(e);
        } catch (BankSecurityException | IOException e) {
            System.err.println("Fatal Cryptographic Error: " + e.getMessage());
            throw new RuntimeException("Transaction signing aborted", e);
        }
    }
}
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### Matrix Perbandingan Arsitektur: K1 vs K2

| Parameter | Arsitektur K1 (Legacy) | Arsitektur K2 (Modern FIR) | Implikasi Arsitektural |
| :--- | :--- | :--- | :--- |
| **Representasi Data** | PSI (AST) + BindingContext (Map-based) | FIR (Flat, Semantic, Self-contained) | K2 memangkas konsumsi heap compiler hingga 40-50%. |
| **Compiler Phases** | Multi-pass parsing, re-resolving symbols | Single-pass type inference & semantic check | Waktu build compile CI/CD turun 2x lipat pada K2. |
| **Backend Architecture**| Terpisah per target (JVM, Native, JS) | Shared Backend IR (Unified Lowering) | Penulisan compiler plugin (seperti Compose/KSP) seragam. |
| **Resolusi Error** | Tersebar, sering inkonsisten pada Edge Case | Sentralisasi via Control Flow Analysis FIR | Pesan error kompilasi K2 jauh lebih deterministik. |

### Pendekatan Interop & Eksekusi: Alternatif Desain

```
+-----------------------------------------------------------------------------------------+
|                  TRADE-OFF: EXPECT/ACTUAL VS INTERFACE-BASED ABSTRACTION               |
+-----------------------------------------------------------------------------------------+

Kriteria                  | expect/actual Mechanism         | Pure Interface + DI Pattern
--------------------------+---------------------------------+------------------------------
Runtime Overhead          | ZERO (Static Resolution / Link) | Virtual Call Overhead (vtable)
Binary Coupling           | Sangat Ketat (Compile-time bind)| Longgar (Decoupled via DI)
Kebutuhan Test Mocking    | Sulit di-mock tanpa source sets | Sangat mudah di-mock (Unit testing)
Dukungan Constructor Plat.| Ya, actual dapat akses platform | Tidak langsung, butuh Factory
Kesesuaian                | High-Performance Native Core    | Arsitektur Bisnis / UI Apps
```

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. The "Platform Type Null Leak" (`String!`)
* **Mekanisme Pitfall:** Ketika Java method mengembalikan null:
  ```java
  public class LegacyUserRepository {
      public static String findEmail() { return null; } // Implicitly String!
  }
  ```
* Jika Kotlin menerima type ini ke dalam variabel tanpa tipe eksplisit:
  ```kotlin
  val email = LegacyUserRepository.findEmail() // Type is inferred as String!
  println(email.length) // Throws NullPointerException saat runtime
  ```
* **Kompiler K2:** K2 mempertahankan pemeriksaan tipe ketat, namun tipe platform tetap menjadi lubang celah *soundness* type system.
* **Solusi Defensif:** Selalu buat kontrak tipe eksplisit saat menerima tipe platform:
  ```kotlin
  val email: String? = LegacyUserRepository.findEmail() // Aman, compiler memaksa null handling
  ```

### 2. Generics Wildcard Incompatibility (Covariance & Contravariance)
* Java wildcard: `List<? extends Number>`.
* Kotlin generic: `List<out Number>`.
* Jika method Java didefinisikan sebagai:
  ```java
  public void processItems(List<Number> items) { ... }
  ```
  Kotlin tidak dapat mengirim `List<Int>` ke method tersebut meskipun `Int` turunan dari `Number`, karena `java.util.List` di Java bersifat *invariant*.
* **Solusi Bytecode:** Gunakan `@JvmWildcard` atau `@JvmSuppressWildcards`:
  ```kotlin
  fun sendData(list: List<@JvmWildcard Number>) 
  // Menghasilkan signature Java: void sendData(List<? extends Number> list)
  ```

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Mistake 1: Tidak mendefinisikan `@Throws` pada fungsi I/O Kotlin yang dikonsumsi Java
* **Dampak:** Java memanggil fungsi Kotlin yang gagal dan melempar `IOException`. Java tidak membungkus fungsi tersebut dengan try-catch karena Kotlin menyembunyikannya dari signature `.class`. Akibatnya, exception menembus unchecked boundary dan mematikan thread JVM secara tidak terduga.
* **Solusi:**
  ```kotlin
  // SALAH:
  fun readFile(path: String): String = File(path).readText()

  // BENAR:
  @Throws(IOException::class)
  fun readFile(path: String): String = File(path).readText()
  ```

### Mistake 2: Membengkakkan Instansiasi Companion Object pada Hot-Paths
* **Dampak:** Mengakses property konstan companion tanpa `@JvmField` atau `const` dari Java:
  ```kotlin
  class SecurityConstants {
      companion object {
          val TIMEOUT = 5000 // Menghasilkan Companion instance call
      }
  }
  ```
  Java memanggil `SecurityConstants.Companion.getTIMEOUT()`. Pada perulangan jutaan iterasi, alokasi register untuk instance dan *method dispatch* companion menurunkan efisiensi caching CPU.
* **Solusi:**
  ```kotlin
  class SecurityConstants {
      companion object {
          const val TIMEOUT = 5000 // Inlined primitive literal ke constant pool
          @JvmField val INSTANCE_ID = UUID.randomUUID().toString() // Field akses langsung
      }
  }
  ```

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Jadikan ABI Stabil Menggunakan Binary Compatibility Validator (BCV):**  
   Gunakan plugin JetBrains `binary-compatibility-validator` di pipeline CI untuk mendeteksi perubahan *signature* public method yang dapat merusak kompatibilitas pustaka Java/Kotlin yang didistribusikan.
2. **K2 Compiler Flag Standardization:**
   Gunakan flag `-Xjvm-default=all` dalam `compileKotlin` configuration untuk memanfaatkan JVM 8 default methods pada interface Java daripada membuat kelas `$DefaultImpls` tambahan.
3. **Desain Datar untuk Kotlin Multiplatform SourceSets:**
   Hindari struktur dependensi modular yang terlalu dalam pada level platform target. Gunakan hirarki source-set default KMP modern:
   ```
   commonMain -> jvmMain, nativeMain, jsMain
   ```
4. **Isolasi Logika Java Interop:**
   Buat module atau package facade khusus (misal: `com.company.sdk.interop`) yang dihiasi anotasi JVM (`@JvmStatic`, `@JvmOverloads`), menjaga source code domain core murni dan idiomatis Kotlin.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Benchmarking Synthetic Accessors
Jika inner class mengakses private field dari outer class:
```kotlin
class OuterNode {
    private var internalState: Int = 0

    inner class InnerWorker {
        fun mutate() {
            internalState += 1 // Menghasilkan synthetic accessor
        }
    }
}
```
Kompiler Kotlin terpaksa membuat *synthetic bridge method*:
```java
// Hasil decompile classfile:
static int access$getInternalState$p(OuterNode obj) { return obj.internalState; }
static void access$setInternalState$p(OuterNode obj, int val) { obj.internalState = val; }
```
Panggilan bridge ini menambahkan beban pada pipeline JVM inline-cache. 

* **Optimasi:** Ubah visibilitas `internalState` menjadi `internal` (dalam internal module scope) atau restrukturisasi kelas menjadi decoupled top-level object jika berada di lintasan komputasi kritis (*hot loop*).

### Value Class vs Heap Allocation
Gunakan `@JvmInline value class` untuk identifier domain (User ID, Currency Code, Milliseconds).
* **Alokasi Heap:** `0 bytes` (dikonversi ke tipe primitif di JVM stack frame via IR Lowering).
* **Penghematan:** Menghindari *pointer indirection* 64-bit dan *object header overhead* (12 atau 16 byte per objek di JVM heap).

---

# SEKSI 16 — KEAMANAN & HARDENING

### Reflection Attack Vectors pada Internal Declarations
Modifier `internal` di Kotlin bukanlah mekanisme keamanan, melainkan fitur visibilitas compile-time. Di level bytecode JVM, member `internal` diubah menjadi `public` dengan *mangled name*:
```kotlin
class KeyStoreVault {
    internal fun decryptMasterKey(): ByteArray = byteArrayOf(0x01)
}
```
Bytecode:
```
public final byte[] decryptMasterKey$module_name_release();
```
Penyerang yang menyusupkan pustaka pihak ketiga di JVM classpath yang sama dapat mengeksekusi method tersebut menggunakan Java reflection biasa tanpa memerlukan flag `setAccessible(true)`:
```java
Method m = KeyStoreVault.class.getMethod("decryptMasterKey$module_name_release");
byte[] leaked = (byte[]) m.invoke(vault);
```

### Panduan Hardening:
1. Terapkan tools pengabur kode (*ProGuard / R8*) untuk melakukan *re-obfuscation* dan *shrinking* pada seluruh *internal mangled signatures*.
2. Gunakan **Java Platform Module System (JPMS)** (`module-info.java`) untuk membatasi `exports` paket secara runtime, sehingga class tidak dapat diakses bahkan via *reflective invocation* dari luar modul JDK.

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### Diagnostic K2 Compiler Melalui Compiler Argument Flags
Tambahkan flags berikut pada blok `compilerOptions` di Gradle untuk menganalisis keputusan IR lowering dan FIR phase:

```kotlin
tasks.withType<org.jetbrains.kotlin.gradle.tasks.KotlinCompile>().configureEach {
    compilerOptions {
        freeCompilerArgs.addAll(
            "-Xdump-fir=true",             // Dumps Frontend Intermediate Representation
            "-Xvalidate-ir=true",          // Validates Backend IR graph before bytecode emission
            "-Xprofile-phases=true"        // Profiling latency per K2 compilation phase
        )
    }
}
```

### Memeriksa Null Safety Bytecode via Terminal
Untuk memvalidasi apakah runtime bytecode menyisipkan pengecekan null yang tidak perlu di hot loop:
```bash
javap -c build/classes/kotlin/main/com/bank/core/NativeCryptoEngine.class
```
Periksa keberadaan instruksi:
```
INVOKESTATIC kotlin/jvm/internal/Intrinsics.checkNotNullParameter (Ljava/lang/Object;Ljava/lang/String;)V
```
Jika method tersebut dipanggil dalam *high-frequency loops* dan argumen sudah dijamin aman oleh arsitektur internal, hilangkan overhead ini menggunakan compiler flag `-Xno-param-assertions` dan `-Xno-call-assertions`.

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

```
+--------------------------------------------------------------------------------------------------+
|                              KOTLIN INTEROP & K2 COMPILER CHEAT SHEET                            |
+--------------------------+-------------------------------------+---------------------------------+
| Anotasi / Konstruksi     | Efek Transformasi Bytecode          | Kasus Penggunaan Utama          |
+--------------------------+-------------------------------------+---------------------------------+
| @JvmStatic               | Membuat static bridge di root class | Interop Java static invocations |
| @JvmField                | Hapus getter/setter, jadikan public | Java Serialization, Reflection  |
| @JvmOverloads            | Generate n-overload methods Java    | Parameter default di Java       |
| @JvmName("xyz")          | Mengubah symbol name di classfile   | Menghindari mangling / collision|
| @Throws(MyEx::class)     | Menulis attribute Exceptions di JVM | Checked exceptions di Java      |
| @JvmInline value class   | Unboxing tipe ke level primitif/obj | Zero-allocation type safety     |
| expect / actual          | Linkage antarmuka multiplatform     | Native/JVM KMP abstraction      |
| -Xjvm-default=all        | Interface default method JVM 8+     | Modern binary compatibility     |
+--------------------------+-------------------------------------+---------------------------------+

Tahapan Kompilasi K2:
  Kotlin Code ---> Raw FIR Builder ---> FIR Semantic Passes ---> Kotlin IR ---> IR Lowerings ---> JVM Bytecode
```

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

#### Kategori A: Pemahaman Konseptual (Basic)
1. **Mengapa method `internal` pada Kotlin dimodifikasi namanya (*mangled*) menjadi `method$module_name()` di level JVM bytecode?**
   * *Jawaban:* Karena JVM tidak memiliki konsep visibilitas `internal`. Untuk mencegah compiler Java memanggil method ini secara langsung (tanpa melanggar visibility contract module), compiler memodifikasi namanya dengan memasukkan karakter illegal Java `$`.
2. **Apa yang terjadi secara internal jika tipe Java tanpa anotasi nullability dibaca oleh Kotlin?**
   * *Jawaban:* Tipe tersebut dianggap sebagai *Platform Type* (`T!`). Kotlin memperlakukannya secara fleksibel (bisa nullable atau non-null), tetapi meniadakan compile-time safety check dan membebankan risiko `NullPointerException` di runtime.
3. **Sebutkan perbedaan mendasar struktur frontend compiler K1 dan K2!**
   * *Jawaban:* K1 menggunakan representasi PSI/AST yang digabungkan dengan `BindingContext` eksternal (Map-based memory model) yang lambat dan boros memori. K2 menggunakan FIR (Frontend IR) terintegrasi berbasis single-pass resolution yang bersifat *immutable* dan hemat alokasi heap.
4. **Apa fungsi dari anotasi `@file:JvmName("Utils")`?**
   * *Jawaban:* Mengubah nama class file artifak `.class` yang dihasilkan dari top-level functions/properties dari defaultnya `FilenameKt.class` menjadi `Utils.class`.
5. **Mengapa `value class` yang menggunakan satu parameter primitif tidak dialokasikan di Heap JVM saat dioperasikan secara lokal?**
   * *Jawaban:* Karena proses `JvmInlineClassLowering` mereduksi objek wrapper tersebut secara langsung menjadi tipe primitif dasar pada JVM stack frame (unboxing).

#### Kategori B: Penerapan & Analisis Bytecode (Intermediate)
6. **Perhatikan kode berikut:**
   ```kotlin
   class SdkConfig {
       companion object {
           @JvmField val TIMEOUT_MS: Long = 30000L
       }
   }
   ```
   **Bagaimana pemanggilan field ini dari Java dan apa bytecode JVM yang dieksekusi?**
   * *Jawaban:* Java memanggil via `SdkConfig.TIMEOUT_MS;`. Bytecode yang dieksekusi adalah `GETSTATIC SdkConfig.TIMEOUT_MS : J`. Tidak ada instance Companion yang dibuat atau dipanggil.
7. **Jika class Kotlin memiliki method: `fun execute(token: SecureToken)` di mana `SecureToken` adalah `value class`, mengapa Java tidak bisa memanggilnya dengan nama `execute` tanpa bantuan `@JvmName`?**
   * *Jawaban:* Karena compiler menerapkan *name mangling* struktural (misal: `execute-5Xy4z0k(String)`) untuk menghindari ambiguitas tanda tangan JVM jika ada overload lain yang menggunakan tipe dasar yang sama.
8. **Diberikan interface Kotlin:**
   ```kotlin
   interface NetworkClient {
       fun ping() = "PONG"
   }
   ```
   **Apa perbedaan bytecode yang dihasilkan ketika dikompilasi dengan flag `-Xjvm-default=all` dibandingkan tanpa flag tersebut?**
   * *Jawaban:* Tanpa flag, interface menghasilkan kelas pendamping sintesis `NetworkClient$DefaultImpls` yang berisi static method untuk implementasi default. Dengan `-Xjvm-default=all`, implementasi dikompilasi langsung menjadi JVM 8 default method di dalam antarmuka interface itu sendiri.
9. **Kapan implementasi `expect`/`actual` lebih diunggulkan dibanding Dependency Injection menggunakan Interface murni?**
   * *Jawaban:* Pada kasus di mana efisiensi pemanggilan metode absolut diperlukan (menghindari dynamic dispatch / virtual method table) dan saat butuh mengakses konstruktor atau tipe statis platform secara native tanpa *runtime plumbing overhead*.
10. **Bagaimana cara mencegah reflection Java mengeksekusi private constructor pada Kotlin `object` Singleton?**
    * *Jawaban:* Mengintegrasikan runtime check pada constructor private singleton yang melempar exception jika instansiasi kedua terdeteksi (seperti `if (INSTANCE != null) throw UnsupportedOperationException()`), atau memproteksi paket via JPMS (`module-info.java`).

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Rancang & Bangun: Zero-Overhead Multiplatform Metric Collector Engine

#### Spesifikasi Arsitektural:
1. **Target Multiplatform:** Bangun KMP library yang mendukung target `jvm` dan setidaknya satu target `native` (misal: `linuxX64` atau `macosArm64`). Aktifkan **K2 Compiler** secara eksplisit di script Gradle Anda.
2. **Abstraksi Low-Level:** Buat kelas `expect class HighResolutionTimer`:
   * Method `fun captureNanoseconds(): Long`
   * Platform JVM `actual` harus memanggil `System.nanoTime()`.
   * Platform Native `actual` harus menggunakan fungsi POSIX C-interop (`clock_gettime`).
3. **Strict Java Interop Requirement (Target JVM):**
   * Buat class `MetricDispatcher` pada source-set `jvmMain`.
   * Sediakan fungsi `recordMetric(String metricName, long valueNano, MetricCategory category)`.
   * Harus menyediakan `@JvmOverloads` di mana default `category` adalah `MetricCategory.GENERAL`.
   * Anotasikan tipe enum / inline class metrik agar di Java tampak sebagai primitif atau enum bersih tanpa synthetic noise.
   * Method harus mendokumentasikan checked exception `MetricBufferOverflowException` dan diekspos menggunakan `@Throws`.
4. **Verifikasi Artefak:**
   * Ekstrak class file hasil kompilasi menggunakan perintah:  
     `javap -c -p build/classes/kotlin/jvm/main/.../MetricDispatcher.class`
   * Buktikan bahwa:
     1. Overloaded static methods terbentuk sempurna.
     2. Tidak ada *synthetic companion accessor methods* yang di-generate.
     3. Exceptions table terkonfigurasi dengan benar.
5. **Evaluasi Runtime:**
   * Tulis sebuah file `TestRunner.java` murni di `src/test/java` untuk mengonsumsi library Kotlin tersebut tanpa mengimpor pustaka `kotlin-stdlib` secara eksplisit pada consumer code. Pastikan program Java berjalan mulus dengan Java 17 Runtime.