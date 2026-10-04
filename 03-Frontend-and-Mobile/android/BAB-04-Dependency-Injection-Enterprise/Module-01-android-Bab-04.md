# Kurikulum Enterprise Android Engineering: 03-Frontend-and-Mobile

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** 03-Frontend-and-Mobile
*   **Topik Spesialisasi:** Android Platform Engineering & System Architecture
*   **Bab:** 04 — Modern Android Architecture & Concurrency
*   **Modul:** 01 — Dependency Injection Enterprise (Dagger-Hilt & KSP)
*   **Prasyarat Tingkat Keahlian:** Pemahaman mendalam terkait Kotlin Metaprogramming (Symbol Processing), Android Application Lifecycle, JVM Bytecode Generation, serta Inversion of Control (IoC) Pattern.

---

## SEKSI 02 — LEARNING OBJECTIVES

Pada akhir modul ini, engineer diharapkan mampu:

1.  **Mendekomposisi Metaprogramming Lifecycle:** Menjelaskan secara presisi bagaimana Kotlin Symbol Processing (KSP) mengurai Abstract Syntax Tree (AST), mengekstraksi metadata anotasi, dan menginstruksikan Dagger compiler untuk menghasilkan Java source files tanpa overhead pemrosesan KAPT (Kotlin Annotation Processing Tool) yang berbasis *stub generation*.
2.  **Mengarsitekturi Hierarki Komponen Dilt:** Merancang dependensi multi-modul yang aman secara *compile-time* menggunakan `@InstallIn`, Custom Component Scopes, dan Subcomponents untuk mencegah retensi memori ilegal antar-siklus hidup Android.
3.  **Mengimplementasikan Pola Injeksi Lanjutan:** Menerapkan Assisted Injection (`@AssistedInject`), dynamic multi-bindings (`@IntoSet`, `@IntoMap`), serta Dynamic Feature Module (DFM) injection via Entry Points.
4.  **Melakukan Profiling dan Eliminasi Bottleneck Injeksi:** Mengidentifikasi dan memitigasi latensi inisialisasi pada *Cold Start* aplikasi yang diakibatkan oleh *deep dependency graph traversal* dan inisialisasi instansiasi eager.
5.  **Mendeteksi dan Memitigasi Memory Leak Terkait DI:** Menganalisis *retained references* dari Android Framework classes (`Activity`, `Fragment`, `View`) dalam `@Singleton` graph menggunakan Heap Dump Analysis (Memory Analyzer Tool / LeakCanary).

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Mental Model: Dependency Graph Sebagai Directed Acyclic Graph (DAG) Terkompilasi

Banyak engineer memandang Dependency Injection sekadar sebagai "alat pembuat objek secara otomatis". Mental model ini keliru dan berbahaya pada skala enterprise. 

Pandanglah dependency injection engine (Dagger) sebagai **Static Graph Compiler**. 

```
[Simpul Sumber: Factory / Provider] ---> [Busur Terarah: Dependencies] ---> [Simpul Tujuan: Consumer]
```

Dagger tidak bertindak sebagai *Service Locator* yang mencari dependensi secara dinamis pada *runtime*. Sebaliknya, Dagger memvalidasi bahwa seluruh *Directed Acyclic Graph* (DAG) valid, tertutup, dan tidak memiliki dependensi siklik (*cyclic dependency*) sebelum kode dikompilasi menjadi bytecode.

### Paradigma KSP vs KAPT: Pemrosesan AST Langsung

Peralihan dari KAPT ke KSP adalah peralihan dari ilusi Java ke realitas Kotlin native:

*   **KAPT:** Memaksa Kotlin compiler mengonversi seluruh source code Kotlin menjadi Java Stubs (representasi Java palsu tanpa method body) hanya agar Java Annotation Processor (Javac APT) standar dapat membaca anotasi. Hal ini menghasilkan penalti I/O disk dan CPU yang masif (hingga 30-40% dari total build time).
*   **KSP:** Beroperasi langsung pada tingkat Abstract Syntax Tree (AST) compiler Kotlin (menggunakan antarmuka `SymbolProcessor`). KSP membaca symbol deklarasi (`KSClassDeclaration`, `KSFunctionDeclaration`) secara native, melewati fase stub generation, dan menghasilkan Java/Kotlin code langsung ke target build directory.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Diagram 1: Siklus Hidup Kompilasi KSP dengan Dagger-Hilt

```
+-------------------------------------------------------------------------------+
|                             KOTLINC COMPILER PASS                             |
+-------------------------------------------------------------------------------+
                                      |
                       [Source Code (.kt files)]
                                      |
                                      v
                        [Abstract Syntax Tree (AST)]
                                      |
            +-------------------------+-------------------------+
            |                                                   |
            v                                                   v
   [KSP Symbol Processing]                             [Core Compilation]
   | - Hilt Symbol Processor                           | (Waiting for Generated Sources)
   | - Scans: @HiltAndroidApp,                          |
   |   @AndroidEntryPoint, @Inject                     |
   +---------------------------------------------------+
            |
            v  Emits
   [Generated Source Artifacts]
   | - Hilt_MainActivity.java
   | - DaggerMyApplication_HiltComponents_SingletonC.java
   | - FeatureRepository_Factory.java
            |
            +-------------------------+
                                      |
                                      v
                        [Final Bytecode Generation]
                                      |
                                      v
                           [Classes.dex (Dalvik)]
```

### Diagram 2: Hierarki Komponen Runtime Dagger-Hilt & Retensi Siklus Hidup

```
+---------------------------------------------------------------------------------+
| SingletonComponent (@Singleton)                                                 |
| Scope: Menempel pada Application instance (Sepanjang proses OS hidup)           |
+---------------------------------------------------------------------------------+
        |
        +-----------------------------------+
        |                                   |
        v                                   v
+-----------------------------------+   +-----------------------------------+
| ActivityRetainedComponent         |   | ServiceComponent                  |
| Scope: @ActivityRetainedScoped    |   | Scope: @ServiceScoped             |
| Bertahan saat Configuration Change|   | Menempel pada Service lifecycle   |
+-----------------------------------+   +-----------------------------------+
        |
        v
+-----------------------------------+
| ActivityComponent                 |
| Scope: @ActivityScoped            |
| Hancur saat Activity.onDestroy()  |
+-----------------------------------+
        |
        +-----------------------------------+
        |                                   |
        v                                   v
+-----------------------------------+   +-----------------------------------+
| FragmentComponent                 |   | ViewComponent                     |
| Scope: @FragmentScoped            |   | Scope: @ViewScoped                |
| Hancur saat Fragment.onDestroy()  |   | Terikat pada Siklus Hidup View    |
+-----------------------------------+   +-----------------------------------+
        |
        v
+-----------------------------------+
| ViewWithFragmentComponent         |
| Scope: @ViewScoped                |
+-----------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Injeksi Lapangan (Field Injection) Tanpa Refleksi
Ketika sebuah Android framework class diannotasikan dengan `@AndroidEntryPoint`:
```kotlin
@AndroidEntryPoint
class OrderActivity : AppCompatActivity() {
    @Inject lateinit var orderProcessor: OrderProcessor
}
```
Dagger-Hilt tidak memanggil `Class.getDeclaredFields()` pada *runtime*. Sebaliknya, Hilt bytecode transformer (via Gradle Plugin) menulis ulang *bytecode* `OrderActivity` untuk mewarisi `Hilt_OrderActivity`.

Di dalam `Hilt_OrderActivity`:
```java
// Hasil Dekompilasi / Konseptual Bytecode
public abstract class Hilt_OrderActivity extends AppCompatActivity implements GeneratedComponentManagerHolder {
    protected void inject() {
        if (!injected) {
            injected = true;
            ((OrderActivity_GeneratedInjector) this.generatedComponent()).injectOrderActivity(UnsafeCast.unsafeCast(this));
        }
    }

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        inject();
        super.onCreate(savedInstanceState);
    }
}
```

### 2. Double-Check Idiom pada Instance Scoping
Ketika sebuah dependensi di-*scope* (misalnya `@Singleton` atau `@ActivityScoped`), Dagger menjamin single-instance via kelas internal `DoubleCheck<T>`.

Implementasi mekanismenya:
```java
public final class DoubleCheck<T> implements Provider<T>, Lazy<T> {
    private static final Object UNINITIALIZED = new Object();
    private volatile Provider<T> provider;
    private volatile Object instance = UNINITIALIZED;

    public DoubleCheck(Provider<T> provider) {
        this.provider = provider;
    }

    @Override
    public T get() {
        Object result = instance;
        if (result == UNINITIALIZED) {
            synchronized (this) {
                result = instance;
                if (result == UNINITIALIZED) {
                    result = provider.get();
                    instance = recheck(instance, result);
                    /* Nulling out the reference to the provider allows 
                       the memory to be freed if it's no longer needed. */
                    provider = null;
                }
            }
        }
        return (T) result;
    }
}
```
*   **Volatile read:** Membaca variabel `instance` tanpa *synchronization cost* pada kondisi *steady state* (sudah diinisialisasi).
*   **Synchronized block:** Hanya dieksekusi satu kali saat inisialisasi awal.
*   **Double checking:** Menghindari *race condition* antar dua thread yang sama-sama menemukan `instance == UNINITIALIZED` secara bersamaan.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Migrasi Kompilasi KAPT ke KSP: Dampak Terhadap Dagger 2
Dagger secara historis bergantung pada `javax.annotation.processing.Processor` (standard JSR-269). Pada Kotlin 1.9/2.0+, Google merombak total Dagger internals untuk mendukung KSP secara langsung.

*KAPT Graph Generation:*
1. Mengubah Kotlin Source $\to$ Java Stubs.
2. Membaca Type Mirror via Javac.
3. Menghasilkan Java Code.
4. Mengompilasi Java Code + Kotlin Code bersama-sama via Javac + Kotlinc.

*KSP Graph Generation:*
1. Kotlinc mengurai Kotlin Source langsung ke dalam KSP Model (`Resolver`, `KSAnnotated`).
2. Dagger KSP processor mengurai relasi tipe secara langsung via Symbol Types (`KSType`).
3. Menghasilkan Java atau Kotlin Source code secara instan.
4. Melewatkan seluruh proses pembuatan stub Java, mereduksi build overhead secara linier terhadap jumlah dependensi graph.

### Multibindings: `@IntoSet` dan `@IntoMap`
Mekanisme multibindings memungkinkan pemisahan modul secara absolut (*Decoupled Plugin Architecture*). Sebuah modul dapat menyumbangkan implementasi ke dalam `Set<T>` atau `Map<K, V>` tanpa modul penyedia mengetahui siapa saja konsumer atau kontributor lainnya.

Dagger menyelesaikan ini dengan membuat kelas koleksi sintetis:
*   `SetFactory<T>`: Mengumpulkan sejumlah `Provider<T>` atau `Provider<Collection<T>>` dan menginstansiasinya menjadi `Collections.unmodifiableSet()` saat di-*inject*.
*   `MapProviderFactory<K, V>`: Memetakan key bertipe statis (di-hash menggunakan `@MapKey`) ke `Provider<V>`.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah setup modern enterprise menggunakan Gradle Version Catalog (`libs.versions.toml`), KSP, dan Dagger-Hilt.

### 1. `gradle/libs.versions.toml`
```toml
[versions]
agp = "8.4.0"
kotlin = "2.0.0"
ksp = "2.0.0-1.0.21"
hilt = "2.51.1"

[libraries]
hilt-android = { group = "com.google.dagger", name = "hilt-android", version.ref = "hilt" }
hilt-compiler = { group = "com.google.dagger", name = "hilt-compiler", version.ref = "hilt" }

[plugins]
android-application = { id = "com.android.application", version.ref = "agp" }
kotlin-android = { id = "org.jetbrains.kotlin.android", version.ref = "kotlin" }
ksp = { id = "com.google.devtools.ksp", version.ref = "ksp" }
hilt-android = { id = "com.google.dagger.hilt.android", version.ref = "hilt" }
```

### 2. `build.gradle.kts` (Module: `:app`)
```kotlin
plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.ksp)
    alias(libs.plugins.hilt.android)
}

android {
    namespace = "com.enterprise.di"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.enterprise.di"
        minSdk = 26
        targetSdk = 34
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)
}
```

### 3. Implementasi Graph Fundamental
```kotlin
package com.enterprise.di.fundamental

import android.app.Application
import dagger.Binds
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.HiltAndroidApp
import dagger.hilt.components.SingletonComponent
import javax.inject.Inject
import javax.inject.Qualifier
import javax.inject.Singleton

@HiltAndroidApp
class BaseApplication : Application()

// 1. Abstraksi Layanan
interface CryptographyEngine {
    fun encrypt(data: ByteArray): ByteArray
}

// 2. Implementasi Konkret
class AesCryptographyEngine @Inject constructor(
    private val keySpec: EncryptionKeySpec
) : CryptographyEngine {
    override fun encrypt(data: ByteArray): ByteArray {
        // Implementasi enkripsi AES
        return data.reversedArray() // Simulasi transformasi
    }
}

// 3. Konfigurasi POJO yang membutuhkan factory eksternal
data class EncryptionKeySpec(val algorithm: String, val bitLength: Int)

// 4. Custom Qualifier untuk menghindari ambiguasi tipe data primitif/umum
@Qualifier
@Retention(AnnotationRetention.BINARY)
annotation class MasterKey

@Qualifier
@Retention(AnnotationRetention.BINARY)
annotation class SessionKey

// 5. Modul Dependency
@Module
@InstallIn(SingletonComponent::class)
abstract class SecurityModule {

    @Binds
    @Singleton
    abstract fun bindCryptographyEngine(
        impl: AesCryptographyEngine
    ): CryptographyEngine

    companion object {
        @Provides
        @MasterKey
        @Singleton
        fun provideMasterKeySpec(): EncryptionKeySpec {
            return EncryptionKeySpec(algorithm = "AES-GCM", bitLength = 256)
        }

        @Provides
        @SessionKey
        fun provideSessionKeySpec(): EncryptionKeySpec {
            return EncryptionKeySpec(algorithm = "AES-CBC", bitLength = 128)
        }

        @Provides
        @Singleton
        fun provideDefaultEngine(
            @MasterKey keySpec: EncryptionKeySpec
        ): AesCryptographyEngine {
            return AesCryptographyEngine(keySpec)
        }
    }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Menganalisis implementasi pada **Seksi 07**:

*   `@HiltAndroidApp`: Menginstruksikan Hilt untuk memicu generator bytecode yang membuat kelas `Hilt_BaseApplication`. Kelas ini bertindak sebagai pemegang root graph (`SingletonComponent`) yang diikat langsung pada siklus hidup OS Process aplikasi.
*   `interface CryptographyEngine`: Mendefinisikan kontrak interface. Aturan arsitektur enterprise menyatakan dependensi harus bergantung pada abstraksi, bukan konkrete.
*   `class AesCryptographyEngine @Inject constructor(...)`: Memberitahu Dagger bahwa Dagger memiliki otoritas untuk menginstansiasi kelas ini. `@Inject` pada konstruktor secara otomatis mendaftarkan kelas ini ke dalam *unscoped graph* tanpa perlu menulis method `@Provides` eksplisit, kecuali jika diatur secara khusus.
*   `@Qualifier @Retention(AnnotationRetention.BINARY)`: Membedakan dua instance dari kelas yang identik (`EncryptionKeySpec`). Retensi disetel ke `BINARY` karena Dagger/KSP bekerja pada level *compile-time/binary analysis*, sehingga retensi `RUNTIME` tidak diperlukan (menghemat alokasi memori metadata refleksi).
*   `abstract class SecurityModule`: Mendeklarasikan modul Dagger. Menggunakan `abstract class` alih-alih `object` atau `open class` untuk efisiensi kompilasi maksimal.
*   `@Binds abstract fun bindCryptographyEngine(...)`: Pola performa tinggi. `@Binds` **tidak menghasilkan bytecode Java implementasi method**. Dagger murni memetakan tipe `CryptographyEngine` ke tipe `AesCryptographyEngine` pada tabel routing internalnya, mengeliminasi delegasi pemanggilan fungsi yang terjadi jika menggunakan `@Provides`.
*   `companion object { @Provides ... }`: Mengizinkan fungsi `@Provides` berada di dalam modul `abstract`. Method statis di dalam companion object memastikan pemanggilan langsung tanpa perlu mengalokasikan instansiasi objek `SecurityModule` di dalam memory heap JVM.

---

## SEKSI 09 — STUDI KASUS NYATA (ENTERPRISE PRODUCTION)

### Skenario: Arsitektur Multi-Modul E-Commerce Skala Enterprise
Sebuah aplikasi e-commerce enterprise memiliki fitur dynamic core:
1.  **Core-Network Module:** Menyediakan HTTP client, refresh token interceptor yang bersifat singleton.
2.  **Checkout Feature Module:** Memiliki proses *Payment Processing Session* yang sifatnya berumur pendek (*short-lived*), hanya hidup selama alur checkout berjalan dari input keranjang hingga verifikasi PIN, dan harus musnah seketika saat user keluar dari alur transaksi. Menggunakan `@ActivityRetainedScoped` tidak cukup karena jika transaksi sukses, status sesi pembayaran harus dihancurkan sebelum Activity dihancurkan secara asinkron.
3.  **Masalah:** Default lifecycle Dagger Hilt tidak memiliki *PaymentSessionComponent*. Kita harus mendesain custom scoping dan Dynamic Component Management menggunakan `@DefineComponent` untuk mencegah memory leak data kartu kredit di heap memory.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA (ENTERPRISE CODE)

Berikut adalah implementasi sistem checkout terisolasi menggunakan Hilt Custom Component dan Assisted Injection.

### 1. Definisi Custom Component & Scope
```kotlin
package com.enterprise.di.realworld.scope

import dagger.hilt.DefineComponent
import dagger.hilt.components.SingletonComponent
import javax.inject.Scope

@Scope
@Retention(AnnotationRetention.BINARY)
annotation class PaymentSessionScoped

@PaymentSessionScoped
@DefineComponent(parent = SingletonComponent::class)
interface PaymentSessionComponent {

    @DefineComponent.Builder
    interface Builder {
        fun build(): PaymentSessionComponent
    }
}
```

### 2. Custom Component Manager
```kotlin
package com.enterprise.di.realworld.scope

import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class PaymentSessionManager @Inject constructor(
    private val componentBuilder: PaymentSessionComponent.Builder
) {
    private var component: PaymentSessionComponent? = null

    fun startSession(): PaymentSessionComponent {
        if (component == null) {
            component = componentBuilder.build()
        }
        return component!!
    }

    fun endSession() {
        component = null // Membuka jalan bagi Garbage Collector untuk membersihkan seluruh sub-graph
    }

    fun getSessionComponent(): PaymentSessionComponent? = component
}
```

### 3. Layanan Checkout & Assisted Injection
```kotlin
package com.enterprise.di.realworld.payment

import dagger.assisted.Assisted
import dagger.assisted.AssistedFactory
import dagger.assisted.AssistedInject
import com.enterprise.di.realworld.scope.PaymentSessionScoped
import java.math.BigDecimal

// State internal yang hanya boleh hidup selama sesi pembayaran aktif
@PaymentSessionScoped
class PaymentSessionState @Inject constructor() {
    var transactionId: String? = null
    var isVerified: Boolean = false
}

// Processor yang membutuhkan parameter dinamis Runtime (Amount & Currency)
// DIGABUNGKAN dengan dependensi dari Graph DI (State & Gateway)
class CheckoutProcessor @AssistedInject constructor(
    private val sessionState: PaymentSessionState,
    @Assisted private val amount: BigDecimal,
    @Assisted private val currency: String
) {
    fun executePayment(): String {
        checkNotNull(sessionState.transactionId) { "Transaction ID belum terinisialisasi!" }
        return "Memproses pembayaran $currency $amount untuk TRX: ${sessionState.transactionId}"
    }

    @AssistedFactory
    interface Factory {
        fun create(
            amount: BigDecimal,
            currency: String
        ): CheckoutProcessor
    }
}
```

### 4. Entry Point untuk Dynamic Access
Ketika kita butuh menarik dependensi dari Custom Component secara manual:
```kotlin
package com.enterprise.di.realworld.payment

import com.enterprise.di.realworld.scope.PaymentSessionComponent
import dagger.hilt.EntryPoint
import dagger.hilt.InstallIn
import dagger.hilt.android.EntryPointAccessors

@EntryPoint
@InstallIn(PaymentSessionComponent::class)
interface PaymentSessionEntryPoint {
    fun getCheckoutProcessorFactory(): CheckoutProcessor.Factory
    fun getSessionState(): PaymentSessionState
}

// Consumer Class (Bisa dijalankan di Activity, Service, atau Kiosk Terminal SDK)
class CheckoutCoordinator(
    private val sessionComponent: PaymentSessionComponent
) {
    fun run(orderAmount: BigDecimal) {
        val entryPoint = EntryPointAccessors.fromComponent(
            sessionComponent,
            PaymentSessionEntryPoint::class.java
        )

        // Akses state
        val state = entryPoint.getSessionState()
        state.transactionId = "TRX-998877"
        state.isVerified = true

        // Eksekusi via Assisted Factory
        val factory = entryPoint.getCheckoutProcessorFactory()
        val processor = factory.create(orderAmount, "IDR")
        
        val result = processor.executePayment()
        println(result)
    }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS KOMPARATIF

| Parameter Evaluasi | Dagger-Hilt (KSP) | Koin (Core DSL) | Dagger Vanilla (Java APT/KAPT) |
| :--- | :--- | :--- | :--- |
| **Waktu Inisialisasi App (Cold Start)** | **Sangat Cepat (~0 ms overhead)**. Semua Factory terhubung via kode Java statis. | **Lebat/Lambat**. Resolusi graph melalui *reflection/service locator map lookup* di runtime. | **Sangat Cepat**. Menggunakan pendekatan statis yang sama dengan Hilt. |
| **Validasi Compile-Time Safety** | **Total (100%)**. Jika graph ada yang hilang/siklik, proses kompilasi langsung gagal. | **Nihil (0%)**. Runtime crash (`NoBeanDefFoundException`) terjadi jika definisi dependensi terlewat. | **Total (100%)**. Kompilasi gagal jika dependensi tidak terpenuhi. |
| **Kecepatan Build Gradle** | **Cepat**. Berkat pemrosesan AST langsung oleh KSP tanpa Java stub generation. | **Sangat Cepat**. Tidak ada proses code generation atau anotasi compile-time. | **Sangat Lambat**. KAPT menghasilkan jutaan baris stub Java yang membebani disk I/O. |
| **Kompleksitas Multi-Module** | **Menengah-Tinggi**. Membutuhkan modul terisolasi, `@InstallIn`, dan manajemen visibilitas internal. | **Rendah**. Sangat fleksibel memuat modul via DSL di mana saja. | **Sangat Tinggi**. Perlu manual setup subcomponents, component dependencies, dan module bridging. |
| **Penggunaan Heap Memory** | **Rendah**. Hanya instance yang di-resolve yang disimpan. Tidak ada lookup map besar. | **Tinggi**. Mempertahankan global registry berupa hash map dari semua definitions. | **Rendah**. Memory footprint sepenuhnya berbasis pure code reference. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. DFM (Dynamic Feature Module) Graph Inversion
*Problem:* Modul `:app` tidak dapat melihat kode di dalam `:dynamic_feature` (karena arah dependensi Gradle adalah kebalikannya: `:dynamic_feature` $\to$ `:app`). Akibatnya, `@InstallIn(SingletonComponent::class)` yang didefinisikan di dalam DFM akan gagal atau ditolak.
*Mitigasi:* Gunakan `@EntryPoint` di dalam DFM dan pasang Hilt component manager berbasis refleksi class interface atau implementasikan `Component Dependencies` manual untuk menarik graph dari Core Application.

### 2. Retained Fragment View Lifecycle Leak
*Problem:* Melakukan injeksi instance yang memegang referensi ke `Binding` atau `View` ke dalam objek `@FragmentScoped`.
*Mekanisme:* Siklus hidup `Fragment` melebihi siklus hidup `Fragment.view`. Fragment dapat berpindah ke Backstack (View dihancurkan via `onDestroyView()`), tetapi Fragment instance tetap hidup. Jika `@FragmentScoped` menahan view hierarchy, seluruh UI subtree bocor (*leaked*).
*Mitigasi:* Jangan pernah menandai presenter/helper yang menyimpan `View` dengan `@FragmentScoped`. Gunakan dependensi unscoped atau lepaskan referensi view pada `onDestroyView()`.

### 3. Assisted Injection dengan Parameter Tipe Primitif Ganda
*Problem:* Jika interface `@AssistedFactory` memiliki dua parameter bertipe identik (misal: dua buah `String`), Dagger KSP dapat tertukar saat memetakan argumen ke konstruktor jika tidak ditandai secara presisi.
*Mitigasi:* Gunakan `@Assisted("identifier")` dengan parameter string literal yang eksplisit:
```kotlin
class UserSession @AssistedInject constructor(
    @Assisted("userId") private val userId: String,
    @Assisted("authToken") private val authToken: String
)
```

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan Fatal 1: Menginjeksikan Activity Context ke Objek Singleton
```kotlin
// SALAH: Menyebabkan fatal memory leak pada seluruh activity lifecycle
@Singleton
class AnalyticsTracker @Inject constructor(
    private val context: Context // Tanpa qualifier, rentan menangkap Activity Context jika salah binding
)

// BENAR: Gunakan @ApplicationContext secara eksplisit
@Singleton
class AnalyticsTracker @Inject constructor(
    @ApplicationContext private val context: Context
)
```

### Kesalahan Fatal 2: Ketergantungan Siklik Tersembunyi via Interface
Dagger akan melempar error kompilasi: `[Dagger/DependencyCycle] Found a dependency cycle`.
*Contoh:* Class `A` butuh `B`, Class `B` butuh `A`.
*Cara Menghindari:*
Gunakan `dagger.Lazy<T>` atau `Provider<T>` pada salah satu konstruktor untuk memecah siklus instansiasi:
```kotlin
class ServiceA @Inject constructor(
    private val serviceB: dagger.Lazy<ServiceB>
) {
    fun execute() {
        serviceB.get().doSomething() // Instansiasi ditunda hingga runtime call
    }
}
```

### Kesalahan Fatal 3: Mendaftarkan Module dengan Instansiasi State Tanpa Alasan
```kotlin
// SALAH: Mengharuskan instansiasi NetworkModule di heap memory
@Module
@InstallIn(SingletonComponent::class)
class NetworkModule {
    @Provides
    fun provideOkHttpClient(): OkHttpClient = OkHttpClient.Builder().build()
}

// BENAR: Jadikan object statis murni
@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {
    @Provides
    fun provideOkHttpClient(): OkHttpClient = OkHttpClient.Builder().build()
}
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Favor `@Binds` over `@Provides`:** Setiap kali memetakan sebuah implementasi konkret ke interface, selalu gunakan `@Binds` di dalam kelas abstrak. Ini menghemat alokasi method execution stack JVM dan meminimalkan ukuran bytecode class factory Dagger.
2.  **Immutability pada Injected Fields:** Seluruh dependency yang diinjeksi via constructor injection harus dideklarasikan sebagai `private val`. Hindari `var` pada constructor injection.
3.  **Scoped Minimalis:** Hindari dorongan untuk memberikan anotasi `@Singleton` pada semua kelas. Semakin banyak objek di-scope ke `@Singleton`, semakin besar memori aplikasi yang terkunci permanen di *Tenured (Old) Heap Generation*, yang memicu frekuensi *Major Garbage Collection* lebih sering dan berujung pada UI Jank/Stutter. Biarkan objek bersifat unscoped kecuali jika memiliki state yang mutlak harus di-share.
4.  **Isolasi Modul Pihak Ketiga (Third-Party Wrapping):** Bungkus library pihak ketiga (misal: Retrofit, Room, Firebase) di dalam abstraksi internal interface Anda sendiri sebelum mendaftarkannya ke Hilt graph.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI

### Optimasi Cold Start: Lazy vs Provider vs Direct Injection

Saat memuat kelas seperti `SplashActivity` atau `Application.onCreate()`, grafik dependensi yang besar dapat memicu *Cascading Initialization*:

```kotlin
// Direct: Memaksa UserDataSynchronizer dan seluruh dependency cabangnya diinstansiasi saat init
class AppInitializer @Inject constructor(
    private val synchronizer: UserDataSynchronizer 
)

// Optimized: Instansiasi ditunda sampai benar-benar dibutuhkan
class AppInitializer @Inject constructor(
    private val synchronizer: dagger.Lazy<UserDataSynchronizer>
) {
    fun initializeIfUserLoggedIn(isLoggedIn: Boolean) {
        if (isLoggedIn) {
            synchronizer.get().sync() // Inisialisasi baru berjalan di sini
        }
    }
}
```

### Analisis Efisiensi Bytecode KSP
Dagger KSP mengurangi kompilasi I/O dengan mengonversi pola factory menjadi instansiasi langsung:
Ketika Anda mendeklarasikan:
```kotlin
class Engine @Inject constructor()
```
Dagger KSP menghasilkan:
```java
public final class Engine_Factory implements Factory<Engine> {
    @Override
    public Engine get() {
        return newInstance();
    }
    public static Engine newInstance() {
        return new Engine();
    }
}
```
Metode statis `newInstance()` memungkinkan Dagger memanggil inisialisasi secara *inlined* di dalam root-graph tanpa harus menginstansiasi objek `Engine_Factory` itu sendiri ke memori, memangkas *object allocation rate* secara signifikan saat cold startup.

---

## SEKSI 16 — KEAMANAN & HARDENING

### Mencegah Injeksi Dependency yang Mengekspos Kredensial di Memory Heap
Saat menginjeksi komponen keamanan tinggi (seperti Token Vault, Master Password, Private Key), dependensi tersebut tidak boleh bocor melalui dependensi *unscoped* yang disimpan di view layer atau ViewModel yang dipertahankan di luar siklus hidup sesi terotentikasi.

### Implementasi Clearable Security Graph
Gunakan konsep Custom Component (mirip dengan implementasi pada Seksi 10) khusus untuk **AuthenticatedSessionComponent**:

```kotlin
@Scope
@Retention(AnnotationRetention.BINARY)
annotation class UserSessionScope

@UserSessionScope
class EncryptedTokenStorage @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private var inMemoryToken: CharArray? = null

    fun setToken(token: CharArray) {
        this.inMemoryToken = token.clone()
    }

    fun purgeSecurityContext() {
        // Hancurkan data sensitif dari memori, menimpa array sebelum dihapus
        inMemoryToken?.let { array ->
            java.util.Arrays.fill(array, '0')
        }
        inMemoryToken = null
    }
}
```
Ketika user melakukan *Logout*, jangan hanya menghapus token dari Shared Preferences/EncryptedSharedPreferences. Panggil `sessionManager.endSession()` yang memicu pelepasan referensi root dari `UserSessionComponent`, memaksa seluruh state memori yang ter-scope pada sesi user musnah dari JVM Heap dan dibersihkan oleh Garbage Collector.

---

## SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

### Diagnostik Dependensi Lambat Menggunakan Trace Profiler
Kita dapat memasang custom provider interseptor untuk mengukur durasi inisialisasi setiap dependensi selama pengembangan (*Debug builds*).

### Implementasi Traceable Provider (Bytecode Inspection Friendly)
```kotlin
package com.enterprise.di.telemetry

import android.os.Trace
import javax.inject.Provider

class TraceableProvider<T>(
    private val providerName: String,
    private val delegate: Provider<T>
) : Provider<T> {
    override fun get(): T {
        Trace.beginSection("DI_Init: $providerName")
        try {
            return delegate.get()
        } finally {
            Trace.endSection()
        }
    }
}
```

### Teknik Analisis Memory Analyzer Tool (MAT)
Jika Anda menduga adanya memory leak terkait Dagger:
1.  Ambil *HPROF* file melalui Android Studio Profiler (Dump Java Heap).
2.  Buka di Eclipse MAT atau Heap Analysis tool.
3.  Jalankan query *Dominator Tree*.
4.  Cari keyword `HiltComponents_SingletonC` atau `_Factory`.
5.  Analisis *Incoming References* $\to$ *Path to GC Roots* (kecualikan weak/soft references).
6.  Jika ada `Activity` yang ditahan oleh field di dalam `SingletonC`, Anda baru saja menemukan `@Singleton` class yang menyimpan context atau UI callback tanpa dilepas.

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

*   **`@Inject constructor()`:** Metode default untuk memberi tahu Dagger cara membuat instance. Selalu utamakan ini dibanding `@Provides`.
*   **`@Binds`:** Gunakan di dalam `abstract class` atau `interface` modul untuk memetakan Interface $\to$ Implementation. Tidak menghasilkan overhead bytecode.
*   **`@Provides`:** Gunakan hanya jika mengonfigurasi library eksternal yang tidak memiliki `@Inject constructor` atau membutuhkan pola *Builder/Configuration*. Pastikan berada di dalam `object` statis.
*   **`@InstallIn`:** Menentukan di mana modul Anda hidup dan mati. Wajib disertakan di setiap `@Module`.
*   **`Lazy<T>`:** Menunda inisialisasi objek hingga method `get()` pertama kali dipanggil. Mempercepat Startup. Membagikan instance yang sama setelah diinisialisasi.
*   **`Provider<T>`:** Memanggil konstruksi/pengambilan objek baru setiap kali method `get()` dipanggil (kecuali jika target di-scope).
*   **KSP Migration:** Selalu gunakan `ksp(libs.hilt.compiler)` alih-alih `kapt(libs.hilt.compiler)` pada Gradle untuk memangkas waktu kompilasi proyek secara signifikan.
*   **`@EntryPoint`:** Pintu darurat untuk mengambil dependensi Dagger dari kelas yang tidak didukung secara native oleh Hilt (seperti Dynamic Feature Module, WorkManager Worker, Custom Views level rendah).

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

Pilihlah satu jawaban yang paling tepat serta berikan analisis arsitekturnya.

### Pertanyaan 1
Mengapa penggunaan `@Binds` lebih direkomendasikan daripada `@Provides` untuk pengikatan antarmuka (interface binding) sederhana?
*   A. Karena `@Binds` melakukan pengece