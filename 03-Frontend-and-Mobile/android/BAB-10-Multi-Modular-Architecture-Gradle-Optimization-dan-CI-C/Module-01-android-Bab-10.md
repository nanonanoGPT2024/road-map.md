# Bab 10 Module 01: Multi-Modular Architecture, Gradle Optimization, & CI/CD

---

## SEKSI 01 — IDENTITAS MODUL

* **Kategori Kurikulum:** 03-Frontend-and-Mobile
* **Jalur Spesialisasi:** Android Platform Engineering & Enterprise Architecture
* **Kode Modul:** AND-ARCH-1001
* **Tingkat Kesulitan:** Advanced / Staff Engineer Level
* **Prasyarat:** Pemahaman mendalam tentang Kotlin (Coroutines, Flow), Android Architecture Components, Dependency Injection (Dagger/Hilt), serta sintaks dasar Gradle Kotlin DSL.
* **Alokasi Waktu:** 8 Jam Teori Mendalam & 16 Jam Praktik Terpandu

---

## SEKSI 02 — LEARNING OBJECTIVES

Pada akhir modul ini, peserta didik mampu:
1. **Merancang Topologi Modul Enterprise:** Mengisolasi dependensi dan mengimplementasikan pemisahan tanggung jawab berbasis *Feature-by-Layer* menggunakan pola *Api/Implementation separation* guna mencegah *transitive dependency leak*.
2. **Menguasai Mekanisme Internal Gradle Engine:** Mengonfigurasi dan mengoptimalkan siklus hidup *build* Gradle (*Initialization, Configuration, Execution*), memanfaatkan *Configuration Avoidance API*, *Worker API*, *Build Cache*, dan *Configuration Cache*.
3. **Menerapkan Convention Plugins Modern:** Mengabstraksikan duplikasi konfigurasi *build logic* menggunakan *Gradle Included Builds* (`build-logic`) dengan Kotlin DSL terstruktur.
4. **Membangun Pipeline CI/CD Skala Industri:** Menyusun arsitektur integrasi berkelanjutan (*Continuous Integration*) menggunakan GitHub Actions yang menerapkan orkestrasi *remote build cache*, pengujian modular terdistribusi, dan analisis metrik *build profiling*.
5. **Menavigasi Dependency Injection Antar-Modul:** Mengelola graf dependensi multi-modul yang dinamis menggunakan Dagger/Hilt tanpa melanggar prinsip *Inversion of Control* dan batasan *compilation classpath*.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Mental Model 1: "The Directed Acyclic Graph (DAG) Boundary"
Dalam monolit, kode adalah sebuah samudra: perubahan sekecil apa pun pada satu fungsi dapat memicu kompilasi ulang seluruh basis kode secara tidak terduga. Dalam arsitektur multi-modul, basis kode adalah sebuah *Directed Acyclic Graph* (DAG). Setiap modul adalah simpul (*node*), dan dependensi adalah rusuk berarah (*edge*). 

$$G = (V, E)$$

Di mana kompilasi pada node $V_n$ hanya memerlukan evaluasi ulang subgraf yang bergantung langsung padanya jika dan hanya jika *Public Binary Interface* (ABI) berubah. Pola pikir Staff Engineer adalah meminimalkan derajat ketergantungan keluar (*afferent coupling*) dan mempertahankan ABI sestabil mungkin.

### Mental Model 2: "Compilation Classpath vs. Runtime Classpath"
Sebuah kesalahan fundamental adalah menyamakan *compile-time availability* dengan *runtime execution*. Gunakan analogi *kontrak vs. pemenuhan*:
* Modul `api`: Dokumen kontrak hukum (interface dan model data murni).
* Modul `implementation`: Tim operasional yang mengeksekusi kontrak tersebut.
Konsumen hanya perlu membaca kontrak. Jika tim operasional mengganti cara kerjanya tanpa mengubah kontrak, konsumen tidak perlu memperbarui atau mengompilasi ulang dokumen mereka.

### Mental Model 3: "Gradle is a Distributed Compute Engine"
Jangan pandang Gradle sekadar sebagai *tool build script* declaratif berbasis teks. Gradle adalah *state machine* terdistribusi yang mengevaluasi dependensi *task*, mengeksekusi komputasi paralel, dan memvalidasi *I/O snapshotting*. Menulis Gradle script sama halnya dengan menulis kode sistem berkinerja tinggi: alokasi memori yang buruk, pemblokiran I/O, dan pelanggaran *idempotency* pada task akan melipatgandakan waktu *feedback loop* developer secara eksponensial.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Topologi Modul: Api/Impl Separation Pattern

Diagram berikut mengilustrasikan isolasi dependensi antara modul aplikasi utama, modul fitur, modul domain, dan modul infrastruktur inti.

```
                   +---------------------------------------+
                   |              :app                     |
                   |  (Application Assembler & DI Root)    |
                   +-------------------+-------------------+
                                       |
        +------------------------------+------------------------------+
        | runtimeOnly                  | implementation               | runtimeOnly
        v                              v                              v
+---------------+             +------------------+            +---------------+
| :feature:auth |             | :feature:profile |            | :feature:auth |
|     :impl     |             |       :api       |            |     :impl     |
+-------+-------+             +--------+---------+            +-------+-------+
        |                              ^                              |
        | implementation               | api                          | implementation
        v                              |                              v
+---------------+                      |                      +---------------+
| :feature:auth |----------------------+                      |  :core:data   |
|     :api     |                                              +-------+-------+
+-------+-------+                                                     |
        |                                                             | api
        | api                                                         v
+-------v-----------------------------------------------------+---------------+
|                        :core:model / :core:designsystem     |  :core:network|
|                         (Pure Kotlin / Stable Contracts)    |  :core:database
+-------------------------------------------------------------+---------------+
```

### Gradle Execution Engine Lifecycle & Task Execution Graph

```
           [ INITIALIZATION PHASE ]
                      |
                      v
           Settings.gradle.kts dieksekusi
           Identifikasi build-logic & subproject
                      |
                      v
           [ CONFIGURATION PHASE ]
                      |
                      v
           Evaluasi Build Scripts (Semua modul)
           Register Tasks (Avoidance: tasks.register)
           Konstruksi DAG (Directed Acyclic Graph)
                      |
                      v
             [ EXECUTION PHASE ]
                      |
         +------------+------------+
         | Parallel Task Execution |
         +------------+------------+
                      |
       +--------------+--------------+
       |                             |
       v                             v
[ Task: compileKotlin ]       [ Task: compileKotlin ]
   Check Fingerprints            Check Fingerprints
   Inputs == Outputs ?           Inputs == Outputs ?
       |                             |
  +----+----+                   +----+----+
  |         |                   |         |
 YES        NO                 YES        NO
  |         |                   |         |
  v         v                   v         v
UP-TO-DATE  Eksekusi Kompilasi FROM-CACHE Eksekusi Kompilasi
  |         |                   |         |
  +----+----+                   +----+----+
       |                             |
       +--------------+--------------+
                      v
            [ Target Artifact (.apk) ]
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Gradle Task Inputs, Outputs, and Cache Keys
Mekanisme *incremental build* dan *caching* Gradle bergantung pada penentuan *fingerprint* input dan output sebuah task:
* **Task Inputs:** Terdiri dari properti nilai, berkas sumber (*source files*), *classpath*, variabel sistem, dan versi *toolchain*.
* **Task Outputs:** Berkas `.class`, paket `.jar`/`.aar`, resource terkompilasi, atau direktori *build*.
* **Build Cache Key:** Hash SHA-256 terhitung dari seluruh kombinasi fingerprint input task, tipe implementasi task, dan metadata lingkungan kompilasi. Jika hash ini cocok dengan entri yang ada di *local* atau *remote cache*, Gradle melewati eksekusi task (`FROM-CACHE`) dan langsung mengekstrak artefak output ke direktori lokal.

### 2. ABI (Application Binary Interface) vs. Non-ABI Changes
Kotlin Compilation Daemon menerapkan *ABI Fingerprinting*:
* **Perubahan ABI:** Menambahkan fungsi publik baru, mengubah tipe parameter method publik, menghapus *field* publik. Hal ini merusak kontrak biner dan memaksa kompilasi ulang seluruh modul yang bergantung pada modul tersebut secara transitif.
* **Perubahan Non-ABI:** Mengubah implementasi internal dari sebuah fungsi privat atau badan method publik tanpa mengubah *signature*-nya. Gradle mendeteksi bahwa ABI tidak berubah, sehingga hanya mengompilasi modul yang bersangkutan dan mengabaikan modul hilir (*downstream modules*).

### 3. Java/Kotlin Compile Avoidance
Dua konfigurasi utama dependensi pada Gradle:
* `implementation`: Tidak mengekspos dependensi secara transitif ke *compile classpath* modul konsumen. Jika modul `A` melakukan `implementation(project(":B"))`, dan `B` melakukan `implementation(project(":C"))`, modul `A` tidak memiliki akses ke kelas-kelas modul `C` pada saat kompilasi. Perubahan internal pada `C` tidak akan memicu kompilasi ulang pada `A`.
* `api`: Mengekspos dependensi secara transitif ke *compile classpath* konsumen. Modul `A` dapat mengakses kelas modul `C`. Setiap perubahan ABI pada modul `C` memicu kompilasi ulang pada `B` dan juga `A`.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Skema Modularisasi Skala Besar
Dalam arsitektur *clean multi-modular*, modularisasi dikelompokkan dalam matriks multidimensi:
1. **Vertical Slicing (Feature Modules):** Setiap fitur bisnis (misal: *Checkout*, *Authentication*, *Order Tracking*) diisolasi ke dalam modulnya masing-masing.
2. **Horizontal Slicing (Layer Modules):** Setiap domain fungsional dibagi menjadi layer terpisah:
   * `:feature:auth:ui` (Bergantung pada Compose, Design System)
   * `:feature:auth:domain` (Pure Kotlin/Java, Use Cases, Models)
   * `:feature:auth:data` (Repository implementation, Network, Database)
3. **Api/Impl Inversion Pattern:** Membagi modul vertikal menjadi dua sub-modul:
   * `:feature:cart:api` -> Berisi interface repository, interface navigasi, data transfer object publik. Tidak memiliki dependensi Android berat. Modul lain yang perlu memanggil fitur keranjang belanja hanya bergantung pada modul `:api` ini.
   * `:feature:cart:impl` -> Berisi implementasi konkret, internal logic, ViewModel, dan UI. Modul `:app` mengikat (`runtimeOnly` atau Dagger inclusion) modul `:impl` ini ke graf eksekusi.

### Gradle Lifecycle: The Tri-Phase Engine
* **Initialization Phase:** Gradle mencari `settings.gradle.kts`, menentukan proyek/sub-proyek mana yang berpartisipasi dalam build, dan membentuk instansiasi hierarki `ProjectDescriptor`. Jika menggunakan *Composite Builds* (`includeBuild`), logika build eksternal dikompilasi di fase ini sebelum skrip aplikasi dievaluasi.
* **Configuration Phase:** Gradle mengeksekusi skrip `build.gradle.kts` dari setiap proyek yang dikonfigurasi. Selama fase ini, seluruh objek task dibuat dan dikonfigurasi. **Anti-pattern:** Mengeksekusi I/O atau komputasi lambat selama fase konfigurasi akan memperlambat build sekalipun task yang dipanggil adalah task sederhana seperti `help`.
* **Execution Phase:** Gradle menganalisis parameter baris perintah (misal: `:app:assembleRelease`), memilih task yang relevan, menghitung dependensi antar task untuk membentuk DAG eksekusi, lalu menjalankan task tersebut secara paralel menggunakan *worker pool* yang tersedia.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah struktur implementasi *Convention Plugins* berbasis `build-logic` (Included Build) untuk menstandardisasi konfigurasi Android Library dan Compose di seluruh sub-modul.

### Struktur Direktori `build-logic`
```text
build-logic/
├── settings.gradle.kts
├── convention/
│   ├── build.gradle.kts
│   └── src/main/kotlin/
│       ├── AndroidLibraryConventionPlugin.kt
│       └── AndroidComposeConventionPlugin.kt
```

### 1. `build-logic/settings.gradle.kts`
```kotlin
dependencyResolutionManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
    versionCatalogs {
        create("libs") {
            from(files("../gradle/libs.versions.toml"))
        }
    }
}

rootProject.name = "build-logic"
include(":convention")
```

### 2. `build-logic/convention/build.gradle.kts`
```kotlin
plugins {
    `kotlin-dsl`
}

group = "com.enterprise.android.buildlogic"

dependencies {
    compileOnly(libs.android.gradlePlugin)
    compileOnly(libs.kotlin.gradlePlugin)
}

gradlePlugin {
    plugins {
        register("androidLibrary") {
            id = "enterprise.android.library"
            implementationClass = "AndroidLibraryConventionPlugin"
        }
        register("androidCompose") {
            id = "enterprise.android.compose"
            implementationClass = "AndroidComposeConventionPlugin"
        }
    }
}
```

### 3. `build-logic/convention/src/main/kotlin/AndroidLibraryConventionPlugin.kt`
```kotlin
import com.android.build.gradle.LibraryExtension
import org.gradle.api.Plugin
import org.gradle.api.Project
import org.gradle.api.plugins.ExtensionAware
import org.gradle.kotlin.dsl.configure
import org.jetbrains.kotlin.gradle.dsl.KotlinJvmOptions

class AndroidLibraryConventionPlugin : Plugin<Project> {
    override fun apply(target: Project) {
        with(target) {
            with(pluginManager) {
                apply("com.android.library")
                apply("org.jetbrains.kotlin.android")
            }

            extensions.configure<LibraryExtension> {
                compileSdk = 34

                defaultConfig {
                    minSdk = 26
                    testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
                    consumerProguardFiles("consumer-rules.pro")
                }

                compileOptions {
                    sourceCompatibility = org.gradle.api.JavaVersion.VERSION_17
                    targetCompatibility = org.gradle.api.JavaVersion.VERSION_17
                }

                (this as ExtensionAware).extensions.configure<KotlinJvmOptions>("kotlinOptions") {
                    jvmTarget = "17"
                    freeCompilerArgs = freeCompilerArgs + listOf(
                        "-opt-in=kotlinx.coroutines.ExperimentalCoroutinesApi",
                        "-Xexplicit-api=strict"
                    )
                }
            }
        }
    }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Menganalisis file `AndroidLibraryConventionPlugin.kt`:

1. `class AndroidLibraryConventionPlugin : Plugin<Project>`: Mendefinisikan class plugin Gradle khusus yang mengimplementasikan antarmuka `Plugin<T>` dengan target tipe `Project`.
2. `override fun apply(target: Project)`: Entry point Gradle engine ketika plugin diterapkan pada modul via block `plugins { id("...") }`.
3. `with(pluginManager) { apply("com.android.library"); apply("org.jetbrains.kotlin.android") }`: Secara deklaratif menerapkan Android Library Plugin dan Kotlin Android Plugin secara programmatic, menghilangkan kebutuhan penulisan manual di setiap `build.gradle.kts`.
4. `extensions.configure<LibraryExtension>`: Menggunakan *typesafe extension accessor* untuk mengonfigurasi blok `android { ... }` dari Android Gradle Plugin (AGP).
5. `compileSdk = 34` & `minSdk = 26`: Menstandarisasi target kompilasi dan batas minimum OS di satu titik sentral; modifikasi versi masa depan hanya perlu dilakukan di file ini.
6. `consumerProguardFiles("consumer-rules.pro")`: Memastikan aturan obfuscation/shrinking modul ini dibundel secara transitif ke aplikasi utama (`:app`).
7. `(this as ExtensionAware).extensions.configure<KotlinJvmOptions>`: Mengakses ekstensi internal Kotlin untuk memodifikasi pengaturan kompilator Kotlin.
8. `-Xexplicit-api=strict`: Argumen kompilator wajib enterprise. Memaksa pengembang secara eksplisit mendeklarasikan visibilitas (`public`, `internal`) dan tipe kembalian pada deklarasi modul, mencegah kebocoran implementasi privat ke *public API* modul.

---

## SEKSI 09 — STUDI KASUS NYATA (Enterprise FinTech)

### Konteks
Aplikasi FinTech Skala Besar (Digital Banking) memiliki basis kode berukuran 850.000 baris kode Kotlin yang awalnya tersimpan di dalam monolit `:app`.

### Permasalahan
* **Build Time Masif:** Waktu kompilasi lokal bersih (*clean build*) mencapai 18 menit. *Incremental build* rata-rata 3,5 menit bahkan untuk perubahan 1 baris kode di layer UI.
* **High CI Queues:** Build pipeline CI/CD memakan waktu 45 menit per commit. Tim developer mengalami bottleneck pull-request review.
* **High Coupling & Circular Dependency:** Modul transaksi langsung membaca modul kartu kredit, dan sebaliknya, menghasilkan keterikatan siklis yang membuat pengujian unit independen mustahil dijalankan.

### Solusi Rekayasa
1. Memecah basis kode menjadi 65 sub-modul menggunakan pola **Feature API/Impl + Core Separation**.
2. Memigrasikan seluruh logika build script ke `build-logic` berbasis convention plugins.
3. Mengaktifkan Gradle Remote Build Cache yang di-host di distributed storage internal (S3-compatible).
4. Menerapkan CI/CD Pipeline terdistribusi dengan *Path-based Differential Task Filtering* (hanya mengeksekusi test pada subgraf modul yang terpengaruh perubahan Git).

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

### 1. `gradle/libs.versions.toml` (Version Catalog)
```toml
[versions]
agp = "8.2.2"
kotlin = "1.9.22"
coreKtx = "1.12.0"
coroutines = "1.7.3"
hilt = "2.50"

[libraries]
android-gradlePlugin = { group = "com.android.tools.build", name = "gradle", version.ref = "agp" }
kotlin-gradlePlugin = { group = "org.jetbrains.kotlin", name = "kotlin-gradle-plugin", version.ref = "kotlin" }
androidx-core-ktx = { group = "androidx.core", name = "core-ktx", version.ref = "coreKtx" }
kotlinx-coroutines-core = { group = "org.jetbrains.kotlinx", name = "kotlinx-coroutines-core", version.ref = "coroutines" }
hilt-core = { group = "com.google.dagger", name = "hilt-core", version.ref = "hilt" }
hilt-compiler = { group = "com.google.dagger", name = "hilt-compiler", version.ref = "hilt" }

[plugins]
android-application = { id = "com.android.application", version.ref = "agp" }
android-library = { id = "com.android.library", version.ref = "agp" }
kotlin-android = { id = "org.jetbrains.kotlin.android", version.ref = "kotlin" }
hilt = { id = "com.google.dagger.hilt.android", version.ref = "hilt" }
```

### 2. Interface Navigasi & Kontrak Data (`:feature:payment:api`)
```kotlin
// Direktori: :feature:payment:api/src/main/kotlin/com/enterprise/payment/api/
package com.enterprise.payment.api

import kotlinx.coroutines.flow.Flow

public data class PaymentRequest(
    val transactionId: String,
    val amountInCents: Long,
    val currency: String
)

public sealed interface PaymentStatus {
    public object Idle : PaymentStatus
    public object Processing : PaymentStatus
    public data class Success(val receiptId: String) : PaymentStatus
    public data class Failed(val errorCode: String, val message: String) : PaymentStatus
}

public interface PaymentRepository {
    public fun processPayment(request: PaymentRequest): Flow<PaymentStatus>
}

public interface PaymentNavigator {
    public fun openPaymentScreen(transactionId: String)
}
```

### 3. Implementasi Repository & Eksekusi (`:feature:payment:impl`)
```kotlin
// Direktori: :feature:payment:impl/src/main/kotlin/com/enterprise/payment/impl/
package com.enterprise.payment.impl

import com.enterprise.payment.api.PaymentNavigator
import com.enterprise.payment.api.PaymentRepository
import com.enterprise.payment.api.PaymentRequest
import com.enterprise.payment.api.PaymentStatus
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
internal class PaymentRepositoryImpl @Inject constructor(
    // Injeksi dependensi infrastruktur internal (cth: ApiService/Database)
) : PaymentRepository {

    override fun processPayment(request: PaymentRequest): Flow<PaymentStatus> = flow {
        emit(PaymentStatus.Processing)
        try {
            // Simulasi panggilan I/O jaringan internal
            delay(1500)
            if (request.amountInCents <= 0) {
                emit(PaymentStatus.Failed("ERR_INVALID_AMOUNT", "Amount must be greater than 0"))
            } else {
                emit(PaymentStatus.Success("RCPT-${request.transactionId}-${System.currentTimeMillis()}"))
            }
        } catch (e: Exception) {
            emit(PaymentStatus.Failed("ERR_NETWORK", e.localizedMessage ?: "Unknown Error"))
        }
    }
}
```

### 4. Modul Dependency Injection Dagger/Hilt (`:feature:payment:impl`)
```kotlin
package com.enterprise.payment.impl.di

import com.enterprise.payment.api.PaymentRepository
import com.enterprise.payment.impl.PaymentRepositoryImpl
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
internal abstract class PaymentModule {

    @Binds
    @Singleton
    abstract fun bindPaymentRepository(
        impl: PaymentRepositoryImpl
    ): PaymentRepository
}
```

### 5. `gradle.properties` (Optimasi Tingkat Lanjut)
```properties
# Alokasi JVM Memory Heap untuk Gradle Daemon
org.gradle.jvmargs=-Xmx6g -XX:+UseG1GC -XX:MaxMetaspaceSize=1g -XX:+HeapDumpOnOutOfMemoryError

# Eksekusi Paralel Modul Independen
org.gradle.parallel=true

# Cache Eksekusi Antar Build Run
org.gradle.caching=true

# Mengabaikan Fase Konfigurasi jika Task Graph Tidak Berubah
org.gradle.configuration-cache=true

# Kotlin Daemon Fallback & Parallel Compilation
kotlin.daemon.jvmargs=-Xmx3g
kotlin.incremental=true
kotlin.incremental.useClasspathSnapshot=true

# Nonaktifkan Jetifier (Gunakan dependency native AndroidX)
android.useAndroidX=true
android.enableJetifier=false

# Nonaktifkan build config generation secara otomatis jika tidak digunakan
android.defaults.buildfeatures.buildconfig=false
```

### 6. Pipeline CI/CD GitHub Actions Teroptimasi (`.github/workflows/ci.yml`)
```yaml
name: Enterprise Android CI Pipeline

on:
  push:
    branches: [ "main" ]
  pull_request:
    branches: [ "main" ]

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  validate-and-test:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Setup JDK 17
        uses: actions/setup-java@v4
        with:
          distribution: 'temurin'
          java-version: '17'

      - name: Setup Gradle Cache Environment
        uses: gradle/actions/setup-gradle@v3
        with:
          cache-read-only: ${{ github.ref != 'refs/heads/main' }}
          arguments: --profile

      - name: Run Detekt / Static Analysis
        run: ./gradlew detekt --continue

      - name: Run Unit Tests for Affected Modules
        run: ./gradlew testDebugUnitTest --continue

      - name: Assemble Release APK
        if: github.ref == 'refs/heads/main'
        run: ./gradlew :app:assembleRelease
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter | Monolithic (`:app` only) | Multi-Module Layered (`:core`, `:data`, `:domain`, `:ui`) | Multi-Module Feature-API/Impl (`:feature:x:api`, `:feature:x:impl`) |
| :--- | :--- | :--- | :--- |
| **Clean Build Speed** | Cepat (overhead konfigurasi rendah) | Moderat | Paling lambat (overhead manajemen sub-modul tinggi) |
| **Incremental Build Speed** | Sangat Lambat (efek domino pada kompilasi) | Moderat (sering memicu kompilasi ulang jika layer bawah berubah) | Sangat Cepat (ABI diisolasi secara ketat oleh interface murni) |
| **Complexity & Boilerplate** | Sangat Rendah | Sedang | Sangat Tinggi (kebutuhan wiring DI dan interface pemisah) |
| **Boundary Enforcement** | Nol (mudah bocor via modifikator visibilitas) | Lemah (fitur A dapat dengan mudah mengakses UI fitur B) | Sangat Kuat (terisolasi secara compile-time) |
| **Suitability** | Tim kecil (1-4 insinyur), codebase < 30k baris | Tim menengah (5-15 insinyur) | Tim skala besar (> 20 insinyur), codebase enterprise besar |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Circular Dependency Lock
* **Mekanisme Kegagalan:** Modul `:feature:auth` membutuhkan model dari modul `:feature:profile`, sedangkan `:feature:profile` membutuhkan fungsi pengecekan sesi login dari `:feature:auth`. Gradle menolak siklus ini dengan *Circular Dependency Exception* saat parsing DAG.
* **Mitigasi:** Terapkan *Dependency Inversion Principle* (DIP). Ekstraksi kontrak bersama ke dalam modul stateless `:feature:auth-contract` atau bawa model ke tingkatan `:core:model`. Gunakan mediator event bus atau antarmuka navigasi decoupled.

### 2. Configuration Cache Invalidation via System Property Reads
* **Mekanisme Kegagalan:** Membaca parameter dinamis seperti `System.currentTimeMillis()` atau `System.getenv("KEY")` secara langsung di badan konfigurasi task Gradle menyebabkan kegagalan invalidasi *Configuration Cache*. Akibatnya, Gradle selalu mengulang *Configuration Phase* pada setiap pemanggilan.
* **Mitigasi:** Gunakan *Provider API*: `providers.systemProperty(...)` atau `providers.environmentVariable(...)` yang melacak akses nilai secara eksplisit sehingga Gradle dapat membekukan status konfigurasi secara aman.

### 3. Annotation Processor Parallelism Bottlenecks
* **Mekanisme Kegagalan:** Modul yang menggunakan KAPT (Kotlin Annotation Processing Tool) memicu pembuatan stubs Java yang menonaktifkan kompilasi inkremental Kotlin murni dan memakan alokasi heap besar.
* **Mitigasi:** Migrasikan seluruh annotation processor (Room, Moshi, Hilt) ke KSP (Kotlin Symbol Processing). KSP beroperasi secara native di atas Kotlin compiler plugins tanpa *Java stubs generation*, menghasilkan peningkatan performa pemrosesan anotasi hingga 200%.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Menggunakan Dependency `api` Secara Berlebihan
* **Anti-Pattern:**
  ```kotlin
  // Pada :core:network/build.gradle.kts
  dependencies {
      api("com.squareup.retrofit2:retrofit:2.9.0")
  }
  ```
  *Dampak:* Semua modul yang bergantung pada `:core:network` secara otomatis menyertakan Retrofit di compile-classpath mereka. Perubahan versi internal Retrofit akan memicu kompilasi ulang pada seluruh modul aplikasi.
* **Perbaikan:**
  ```kotlin
  dependencies {
      implementation("com.squareup.retrofit2:retrofit:2.9.0")
  }
  ```
  Bungkus response Retrofit menjadi entity domain murni di `:core:network` dan hanya ekspos entity tersebut ke modul lain.

### 2. Mengakses Internal Task Execution Langsung di Configuration Phase
* **Anti-Pattern:**
  ```kotlin
  // build.gradle.kts
  tasks.getByName("test") {
      // Logic konfigurasi langsung dijalankan saat Configuration Phase
  }
  ```
* **Perbaikan (Task Avoidance API):**
  ```kotlin
  tasks.named("test") {
      // Lazy configuration: hanya dieksekusi jika task 'test' benar-benar dijadwalkan jalan
  }
  ```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Explicit API Mode:** Aktifkan `-Xexplicit-api=strict` di modul library untuk memaksa insinyur berpikir apakah sebuah kelas harus menjadi API publik atau `internal`.
2. **Centralized Version Catalogs:** Seluruh dependensi, plugin, dan konstanta versi hanya boleh terdaftar di `gradle/libs.versions.toml`. Tidak diperbolehkan menggunakan hardcoded string dependensi di sub-modul.
3. **No Android Dependency in Domain/Contract:** Sub-modul domain atau antarmuka (`:api`) harus murni Kotlin (`jvm`) tanpa dependensi ke `com.android.library`. Ini memastikan pengetesan unit berjalan secepat kilat langsung di JVM lokal tanpa instansiasi mock Android framework.
4. **Isolasi Dynamic Feature Modules:** Gunakan Dynamic Feature modules untuk fungsionalitas yang jarang digunakan (misal: registrasi KYC verifikasi wajah dengan modul berukuran besar) agar bisa diunduh secara *on-demand*.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### 1. Remote Build Cache Orchestration
Gunakan *HTTP Build Cache* yang disinkronkan antara pipeline CI dan mesin lokal developer. Saat CI berhasil memvalidasi dan mengompilasi PR pada branch utama:
* Artefak kompilasi di-push ke server cache biner.
* Saat developer menarik (*pull*) commit terbaru, eksekusi `./gradlew assembleDebug` lokal akan membaca artefak output langsung dari remote cache via HTTP.
* Mengurangi clean build lokal developer dari hitungan menit menjadi hitungan detik.

### 2. R8/Proguard Optimization di Multi-Module
* Jangan definisikan semua aturan R8 di root `:app`.
* Setiap library harus merilis file `consumer-rules.pro` sendiri yang mengisolasi aturan *keep rules* hanya untuk komponen yang benar-benar membutuhkan refleksi. Hal ini mencegah *bloated configuration* yang memperlambat tahapan shrinking R8.

---

## SEKSI 16 — KEAMANAN & HARDENING

1. **Gradle Wrapper Checksum Verification:**
   Cegah serangan *supply-chain attack* dengan memvalidasi hash biner distribution Gradle Wrapper di `gradle/wrapper/gradle-wrapper.properties`:
   ```properties
   distributionUrl=https\://services.gradle.org/distributions/gradle-8.5-bin.zip
   distributionSha256Sum=92329881881ff573b060d62a93910c2269aab922a945d8b52fa1fb0900b95be0
   ```
2. **Dependency Verification Engine:**
   Aktifkan *Gradle Dependency Verification* untuk memverifikasi checksum SHA-256 dan tanda tangan PGP metadata dari seluruh dependensi eksternal Maven yang diunduh:
   ```bash
   ./gradlew --generate-dependency-verification-metadata sha256
   ```
   Langkah ini menghasilkan berkas `gradle/verification-metadata.xml` yang mencegah injeksi artifact berbahaya di tingkat CDN maven.
3. **Penyembunyian Secrets pada CI/CD Runners:**
   Jangan pernah menyimpan signing key keystore Android di basis git. Masukkan keystore terenkripsi Base64 di secrets CI runner, deskripsi secara temporer saat kompilasi release, dan segera hapus dari memori file system menggunakan skrip pembersih runner pasca eksekusi:
   ```bash
   echo "${{ secrets.ENCRYPTED_KEYSTORE_BASE64 }}" | base64 -d > release.keystore
   # Task eksekusi release
   rm -f release.keystore
   ```

---

## SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

### Profiling Performa Build dengan Gradle Enterprise / Build Scan
Gunakan flag `--scan` untuk menghasilkan profiling visual komprehensif mengenai waktu eksekusi task, pemanfaatan cache, dan alokasi memori GC:
```bash
./gradlew assembleDebug --scan
```

### Investigasi Dependency Graph & Resolution Issues
Untuk menganalisis modul mana yang membawa dependensi yang menyebabkan konflik versi (*dependency divergence*):
```bash
./gradlew :app:dependencies --configuration debugCompileClasspath
```

Jika terjadi masalah *circular dependency*, visualisasikan alur dependensi dengan task `projectReport`:
```bash
./gradlew projectReport
```
Berkas laporan HTML akan dibuat di `build/reports/project/dependencies.html`.

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

* **`includeBuild("build-logic")`**: Mengubah *build logic* menjadi sistem modular terkompilasi sendiri yang independen dari siklus evaluasi skrip utama.
* **`implementation`**: Gunakan secara default untuk mengisolasi classpath kompilasi dan mempercepat proses *incremental build*.
* **`api`**: Gunakan hanya jika tipe atau antarmuka diekspos sebagai bagian dari *public signature* modul pemanggil.
* **`runtimeOnly`**: Gunakan di modul `:app` untuk mengikat implementasi fitur (`:feature:xxx:impl`) tanpa memberikan izin akses compile-time pada modul app tersebut.
* **`tasks.register`**: Selalu gunakan dibanding `tasks.create` untuk memanfaatkan *Configuration Avoidance API*.
* **Build Optimization Flags**:
  * `org.gradle.parallel=true`
  * `org.gradle.caching=true`
  * `org.gradle.configuration-cache=true`
  * `kotlin.incremental.useClasspathSnapshot=true`

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

Pilihlah satu jawaban yang paling tepat dan sertakan analisis teknis penyebabnya!

### Soal 1
Modul `:feature:order` membutuhkan pemanggilan fungsi dari modul `:feature:inventory`. Pendekatan arsitektur mana yang paling ideal untuk mencegah kompilasi ulang pada `:feature:order` saat logika internal `:feature:inventory` dimodifikasi?
* A. `:feature:order` menambahkan `api(project(":feature:inventory"))`
* B. `:feature:order` menambahkan `implementation(project(":feature:inventory"))`
* C. `:feature:order` menambahkan dependensi `implementation(project(":feature:inventory:api"))`, sementara `:feature:inventory:impl` terikat di level aplikasi assembly (`:app`) via `runtimeOnly`
* D. Menggabungkan kedua