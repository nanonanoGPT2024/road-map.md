# Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 10: Multi-Modular Architecture, Gradle Optimization, dan CI/CD**  
**Kategori: 03-Frontend-and-Mobile / Android Enterprise Engineering**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mengimplementasikan arsitektur Android Multi-Module tingkat lanjut (*Feature-by-Layer*, *Dynamic Feature Module*, dan *Core Isolation*) tanpa menimbulkan *cyclic dependency* atau *transitive dependency leak*.
- Membangun ekosistem build otomatis berbasis **Gradle Convention Plugins** menggunakan *Composite Builds* (`build-logic`) dan Version Catalogs (`libs.versions.toml`).
- Mengisolasi dan menginjeksi dependensi lintas modul menggunakan Dagger/Hilt melalui pola *Component Dependencies* dan *Dynamic Feature Injection*.
- Mengoptimalkan waktu build enterprise melalui aktivasi dan penyetelan **Configuration Cache**, **Remote Build Cache**, **Non-transitive R Classes**, dan **Worker API**.
- Menerapkan strategi navigasi terdesentralisasi lintas modul menggunakan *Dynamic Deep Linking* dan *Interface-based Navigation Providers*.
- Menganalisis *build profiling* menggunakan Gradle Build Scan dan mengatasi *bottleneck* kompilasi pada skala *codebase* dengan ratusan modul.

---

## 2. Prerequisite

Peserta wajib memahami dan menguasai konsep-konsep berikut:
- **Core Kotlin**: Kotlin Coroutines, Flow, Kotlin Symbol Processing (KSP), Delegation, dan Kotlin DSL.
- **Android Architecture Components**: Lifecycle, ViewModel, Navigation Component, Clean Architecture dasar.
- **Dependency Injection**: Dagger 2 / Hilt fundamentals (Scope, Subcomponent, Component, Multibindings).
- **Gradle Basics**: Groovy vs Kotlin DSL, Source Sets, Artifact Repository Management, dan lifecycle build Gradle dasar (`initialization`, `configuration`, `execution`).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Topologi Multi-Module Skala Enterprise

Pada skala enterprise dengan puluhan insinyur, struktur modular monolitik (*flat modules*) menyebabkan degradasi build time dan batas kepemilikan (*code ownership*) yang kabur. Topologi modern membagi modul ke dalam empat lapisan isolasi (*Layered Hexagonal Architecture*):

```
+--------------------------------------------------------------------------+
|                            :app (Application)                            |
+--------------------------------------------------------------------------+
        |                                                  |
        v                                                  v
+-----------------------------+                  +-------------------------+
| :feature:checkout (Dynamic) |                  | :feature:auth (Library) |
+-----------------------------+                  +-------------------------+
        |                  \                        /                  |
        |                   \                      /                   |
        v                    v                    v                    v
+--------------------------------------------------------------------------+
|                       :feature:api:* (Public APIs)                       |
+--------------------------------------------------------------------------+
        |                                                  |
        v                                                  v
+-----------------------------+                  +-------------------------+
|     :core:domain:order      |                  |    :core:domain:user    |
+-----------------------------+                  +-------------------------+
        |                                                  |
        v                                                  v
+--------------------------------------------------------------------------+
|                  :core:data (Repositories & DataSources)                  |
+--------------------------------------------------------------------------+
        |                                                  |
        v                                                  v
+--------------------------------------------------------------------------+
|          :core:network | :core:database | :core:designsystem             |
+--------------------------------------------------------------------------+
```

1. **App Layer (`:app`)**: Modul agregator. Hanya bertugas merakit graph dependensi Dagger/Hilt, mendaftarkan modul dynamic delivery, dan menginisialisasi aplikasi. Modul ini tidak boleh berisi logika bisnis atau UI.
2. **Feature Implementation Layer (`:feature:impl:*`)**: Modul UI dan ViewModel spesifik domain. Bergantung pada modul domain dan modul API fitur lain, bukan pada modul implementasi fitur lain.
3. **Feature Public API Layer (`:feature:api:*`)**: Kontrak antarmuka (*interface*), model navigasi, dan entry point fitur. Tujuannya adalah memutus ketergantungan langsung antar-fitur (*decoupling*) sehingga kompilasi berlangsung paralel.
4. **Core Domain & Data Layer (`:core:*`)**: Domain logic, repository pattern, abstraction, serta infrastructure primitives (Network, Database, Design System).

### 3.2 Dynamic Feature Module (DFM) vs Android Library

Perbedaan mendasar antara Android Library (`com.android.library`) dan Dynamic Feature Module (`com.android.dynamic-feature`):

- **Android Library Module**: Dikompilasi langsung menjadi Android Archive (AAR). Seluruh kode dan aset digabungkan (*merged*) ke dalam Base APK saat proses packaging akhir. Modul dependensi berada di bawah modul konsumen secara struktural (`app -> library`).
- **Dynamic Feature Module (DFM)**: Membalikkan dependensi kompilasi (`feature -> app`). DFM dikemas terpisah menjadi split APK (`split-feature.apk`). DFM dapat diunduh secara on-demand menggunakan Play Core API, memangkas *Initial Download Size* secara signifikan.

```
Relasi Dependensi Kompilasi:
Android Library:     :app  =======================>  :core:network
Dynamic Feature:     :feature:checkout  ===========>  :app
```

### 3.3 Gradle Internal Architecture & Build Phases

Gradle beroperasi melalui tiga fase utama yang dieksekusi secara serial:

1. **Initialization Phase**:
   - Mendeteksi file `settings.gradle.kts`.
   - Menentukan modul-modul yang termasuk dalam graph (`include(":feature:profile")`).
   - Menginisialisasi *Composite Builds* yang didefinisikan via `includeBuild("build-logic")`.
2. **Configuration Phase**:
   - Mengeksekusi script build (`build.gradle.kts`) dari seluruh modul yang terdaftar.
   - Mengonstruksi DAG (*Directed Acyclic Graph*) dari seluruh Task.
   - *Bottleneck*: Logic non-declarative (eksekusi I/O, resolusi dependency prematur) pada fase ini akan memperlambat build sekalipun task yang dijalankan hanya task up-to-date.
3. **Execution Phase**:
   - Gradle mengeksekusi task-task yang terpilih dalam urutan topologis berdasarkan DAG.
   - Task yang *inputs* dan *outputs*-nya tidak berubah ditandai sebagai `UP-TO-DATE` atau diambil dari build cache (`FROM-CACHE`).

#### Configuration Cache Internals
Configuration Cache mengeliminasi Configuration Phase pada build berikutnya jika tidak ada modifikasi pada build script atau environment. Gradle menserialisasikan state DAG Task ke dalam disk cache. Syarat utama:
- Task tidak boleh mengakses state Gradle runtime langsung (misal: `project.property`, `project.rootDir`) saat execution.
- Harus menggunakan Gradle Property/Provider API (`Property<T>`, `Provider<T>`) untuk mereferensikan input secara lazy.

---

## 4. Why & What

| Dimensi | Pendekatan Monolitik / Flat Multi-Module | Multi-Modular Berbasis Build-Logic & DFM |
| :--- | :--- | :--- |
| **Build Time (Incremental)** | Lambat; perubahan 1 baris memicu kompilasi ulang seluruh modul downstream. | Sangat cepat; isolasi ABI via `implementation` dan interface API meminimalisir recompilation path. |
| **Code Ownership** | Rawan konflik merge; batas domain kabur; arsitektur rentan degradasi (*architecture erosion*). | Tegas; domain boundary diisolasi oleh modul terpisah; permission git CODEOWNERS per direktori modul. |
| **Ukuran APK (Download)** | Seluruh fitur terpasang default; APK bloating akibat fitur minoritas user. | Fitur berukuran besar dikirimkan via *Play Feature Delivery* secara on-demand saat dibutuhkan. |
| **Dependency Governance**| Duplikasi deklarasi dependensi di puluhan `build.gradle.kts`; versi library tidak sinkron. | Terpusat melalui `libs.versions.toml` dan Gradle Convention Plugins (`build-logic`). |

---

## 5. How (Workflow detail)

Alur kerja implementasi arsitektur modular berkinerja tinggi:

```
+-----------------------------------------------------------------------------+
| 1. Arsitektur Infrastruktur Build                                            |
|    - Buat Composite Build 'build-logic'                                     |
|    - Definisikan Version Catalog ('gradle/libs.versions.toml')             |
|    - Buat Custom Convention Plugins (AndroidApplication, Feature, Library)   |
+-----------------------------------------------------------------------------+
                                      |
                                      v
+-----------------------------------------------------------------------------+
| 2. Refaktorisasi Domain & Boundary Fitur                                    |
|    - Pecah modul fitur menjadi :feature:xxx:api dan :feature:xxx:impl       |
|    - Expose antarmuka abstraksi; sembunyikan internal implementasi           |
+-----------------------------------------------------------------------------+
                                      |
                                      v
+-----------------------------------------------------------------------------+
| 3. Dependency Injection Multi-Module Graph                                  |
|    - Modul reguler: Hilt Modules terpisah per feature/core                  |
|    - DFM: Dagger Component Dependencies dengan @Component.Builder            |
|      mengambil dependensi dari App Component                                |
+-----------------------------------------------------------------------------+
                                      |
                                      v
+-----------------------------------------------------------------------------+
| 4. Desentralisasi Navigasi                                                  |
|    - Menerapkan Navigation Provider Pattern via Multibinding Dagger         |
|    - Alternatif: Deep link URL routing terpusat                             |
+-----------------------------------------------------------------------------+
                                      |
                                      v
+-----------------------------------------------------------------------------+
| 5. Tuning Build Cache & Profiling                                           |
|    - Aktifkan org.gradle.configuration-cache=true                            |
|    - Aktifkan org.gradle.caching=true                                        |
|    - Eksekusi build profiling via Gradle Build Scan                          |
+-----------------------------------------------------------------------------+
```

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem Manufaktur Pabrik Otomotif

Arsitektur multi-module dapat dianalogikan dengan perakitan mobil modern:
- **Modul Monolitik**: Satu perakitan raksasa di mana jika ban diubah vendornya, seluruh rangka, mesin, dan interior harus dibongkar dan dirakit ulang dari nol.
- **Multi-Module dengan Convention Plugins**: Pabrik dengan modul independen terstandarisasi. Mesin dirakit di divisi mesin, transmisi di divisi transmisi.
  - `libs.versions.toml` adalah katalog spesifikasi baut dan mur standar pabrik.
  - `build-logic` adalah instruksi protokol kontrol kualitas (SOP) perakitan yang wajib diikuti setiap workstation.
  - `:api` adalah ukuran socket, flange, dan poros penghubung yang telah distandardisasi.
  - `Dynamic Feature` adalah aksesoris opsional (misal: *sunroof modular*) yang tidak dipasang di pabrik utama, melainkan dipasang di bengkel dealer saat pembeli memintanya.

### Diagram Alir Kompilasi & Injeksi DFM

```
+-------------------------------------------------------------+
|                        :core:di                             |
|       Provides: CoreApplication, NetworkClient, etc.        |
+-------------------------------------------------------------+
                              ^
                              | (implements CoreBridge)
+-------------------------------------------------------------+
|                           :app                              |
|   AppProvidesComponent: DaggerAppComponent (Singleton Scope)|
+-------------------------------------------------------------+
                              ^
                              | (compileOnly / runtime download)
                              | Component Dependencies
+-------------------------------------------------------------+
|                 :feature:checkout (DFM)                     |
|  @Component(dependencies = [CheckoutDependencies::class])   |
|  class CheckoutComponent                                    |
+-------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Setup Version Catalog & Composite Build (`build-logic`)

Struktur root direktori:
```text
root-project/
├── build-logic/
│   ├── settings.gradle.kts
│   ├── build.gradle.kts
│   └── src/main/kotlin/
│       ├── AndroidApplicationConventionPlugin.kt
│       ├── AndroidFeatureConventionPlugin.kt
│       └── AndroidLibraryConventionPlugin.kt
├── gradle/
│   └── libs.versions.toml
├── settings.gradle.kts
└── build.gradle.kts
```

#### File: `gradle/libs.versions.toml`
```toml
[versions]
agp = "8.3.1"
kotlin = "1.9.23"
coreKtx = "1.12.0"
lifecycle = "2.7.0"
hilt = "2.51"
coroutines = "1.8.0"

[libraries]
android-gradlePlugin = { group = "com.android.tools.build", name = "gradle", version.ref = "agp" }
kotlin-gradlePlugin = { group = "org.jetbrains.kotlin", name = "kotlin-gradle-plugin", version.ref = "kotlin" }
androidx-core-ktx = { group = "androidx.core", name = "core-ktx", version.ref = "coreKtx" }
androidx-lifecycle-viewmodel = { group = "androidx.lifecycle", name = "lifecycle-viewmodel-ktx", version.ref = "lifecycle" }
hilt-android = { group = "com.google.dagger", name = "hilt-android", version.ref = "hilt" }
hilt-compiler = { group = "com.google.dagger", name = "hilt-compiler", version.ref = "hilt" }
kotlinx-coroutines-core = { group = "org.jetbrains.kotlinx", name = "kotlinx-coroutines-core", version.ref = "coroutines" }

[plugins]
android-application = { id = "com.android.application", version.ref = "agp" }
android-library = { id = "com.android.library", version.ref = "agp" }
android-dynamicFeature = { id = "com.android.dynamic-feature", version.ref = "agp" }
kotlin-android = { id = "org.jetbrains.kotlin.android", version.ref = "kotlin" }
kotlin-kapt = { id = "org.jetbrains.kotlin.kapt", version.ref = "kotlin" }
hilt-gradle = { id = "com.google.dagger.hilt.android.plugin", version.ref = "hilt" }
```

#### File: `build-logic/settings.gradle.kts`
```kotlin
dependencyResolutionManagement {
    repositories {
        google()
        mavenCentral()
    }
    versionCatalogs {
        create("libs") {
            from(files("../gradle/libs.versions.toml"))
        }
    }
}

rootProject.name = "build-logic"
```

#### File: `build-logic/build.gradle.kts`
```kotlin
plugins {
    `kotlin-dsl`
}

dependencies {
    compileOnly(libs.android.gradlePlugin)
    compileOnly(libs.kotlin.gradlePlugin)
}
```

#### File: `build-logic/src/main/kotlin/AndroidLibraryConventionPlugin.kt`
```kotlin
import com.android.build.gradle.LibraryExtension
import org.gradle.api.Plugin
import org.gradle.api.Project
import org.gradle.api.artifacts.VersionCatalogsExtension
import org.gradle.kotlin.dsl.configure
import org.gradle.kotlin.dsl.dependencies
import org.gradle.kotlin.dsl.getByType

class AndroidLibraryConventionPlugin : Plugin<Project> {
    override fun apply(target: Project) {
        with(target) {
            with(pluginManager) {
                apply("com.android.library")
                apply("org.jetbrains.kotlin.android")
            }

            val libs = extensions.getByType<VersionCatalogsExtension>().named("libs")

            extensions.configure<LibraryExtension> {
                compileSdk = 34

                defaultConfig {
                    minSdk = 24
                    testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
                    consumerProguardFiles("consumer-rules.pro")
                }

                compileOptions {
                    sourceCompatibility = org.gradle.api.JavaVersion.VERSION_17
                    targetCompatibility = org.gradle.api.JavaVersion.VERSION_17
                }

                buildFeatures {
                    buildConfig = false
                }
            }

            dependencies {
                add("implementation", libs.findLibrary("androidx.core.ktx").get())
                add("implementation", libs.findLibrary("kotlinx.coroutines.core").get())
            }
        }
    }
}
```

### 7.2 Implementasi Dagger Component Dependencies pada Dynamic Feature Module

Karena DFM (`:feature:checkout`) bergantung pada `:app`, Hilt standar tidak dapat menginjeksi dependensi dari DFM ke `:app` secara langsung tanpa konfigurasi khusus. DFM harus menggunakan Dagger *Component Dependencies* untuk mengakses *singleton scope* dari `:app`.

#### File: `:core:di:src/main/kotlin/com/enterprise/di/CoreDependencies.kt`
```kotlin
package com.enterprise.di

import okhttp3.OkHttpClient
import retrofit2.Retrofit

interface CoreDependencies {
    fun okHttpClient(): OkHttpClient
    fun retrofit(): Retrofit
}

interface CoreDependenciesProvider {
    fun provideCoreDependencies(): CoreDependencies
}
```

#### File: `:app:src/main/kotlin/com/enterprise/app/di/AppComponent.kt`
```kotlin
package com.enterprise.app.di

import com.enterprise.di.CoreDependencies
import dagger.Component
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import javax.inject.Singleton

@Singleton
@Component(modules = [NetworkModule::class])
interface AppComponent : CoreDependencies {
    override fun okHttpClient(): OkHttpClient
    override fun retrofit(): Retrofit

    @Component.Factory
    interface Factory {
        fun create(): AppComponent
    }
}
```

#### File: `:feature:checkout:src/main/kotlin/com/enterprise/checkout/di/CheckoutComponent.kt`
```kotlin
package com.enterprise.checkout.di

import com.enterprise.checkout.presentation.CheckoutActivity
import com.enterprise.di.CoreDependencies
import dagger.Component
import javax.inject.Scope

@Scope
@Retention(AnnotationRetention.RUNTIME)
annotation class FeatureScope

@FeatureScope
@Component(
    dependencies = [CoreDependencies::class],
    modules = [CheckoutModule::class]
)
interface CheckoutComponent {
    fun inject(activity: CheckoutActivity)

    @Component.Factory
    interface Factory {
        fun create(coreDependencies: CoreDependencies): CheckoutComponent
    }
}
```

#### File: `:feature:checkout:src/main/kotlin/com/enterprise/checkout/presentation/CheckoutActivity.kt`
```kotlin
package com.enterprise.checkout.presentation

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.enterprise.checkout.di.DaggerCheckoutComponent
import com.enterprise.di.CoreDependenciesProvider
import okhttp3.OkHttpClient
import javax.inject.Inject

class CheckoutActivity : AppCompatActivity() {

    @Inject
    lateinit var client: OkHttpClient

    override fun onCreate(savedInstanceState: Bundle?) {
        val coreDependencies = (applicationContext as CoreDependenciesProvider)
            .provideCoreDependencies()

        DaggerCheckoutComponent.factory()
            .create(coreDependencies)
            .inject(this)

        super.onCreate(savedInstanceState)
        // Client berhasil diinjeksi via Dependency Component tanpa circular build leak
        assert(client != null)
    }
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: SuperApp E-Commerce & FinTech (150+ Modul, 80 Insinyur)

**Masalah:**
- Full Clean Build memakan waktu **24 menit** di mesin developer (Apple Silicon M1 Pro, 32GB) dan **38 menit** di CI runner.
- Incremental build rata-rata **3.5 menit** hanya untuk mengubah satu baris UI pada checkout screen.
- APK size mencapai **115 MB**, menyebabkan conversion rate install Play Store drop sebesar 8.4%.
- Perubahan pada `:core:database` memicu kompilasi ulang dari 92 modul lainnya.

### Akar Masalah (Root Causes)
1. **API Dependency Leakage**: Sebagian besar modul menggunakan `api()` alih-alih `implementation()`, memaksa kompilasi ulang transitif (*ABI invalidation cascade*).
2. **Kekurangan Caching**: Gradle Remote Build Cache belum diaktifkan, Configuration Cache gagal di-cache karena task build script mengakses `System.currentTimeMillis()` dan mutable environment state selama fase konfigurasi.
3. **Monolithic Packaging**: Fitur complex seperti *Insurance Flow* dan *PayLater Registration* jarang digunakan pengguna umum, namun tetap masuk ke Base APK.

### Solusi Teknis Terapan
1. **Migrasi `api` ke `implementation` + Modul API Terisolasi**:
   - Memecah modul fitur `:feature:paylater` menjadi `:feature:paylater:api` (berisi DTO, Interface navigasi, Provider) dan `:feature:paylater:impl`.
   - Modul lain yang perlu membuka layar PayLater hanya bergantung pada `:feature:paylater:api`.
2. **Play Feature Delivery (DFM)**:
   - Modul `:feature:insurance` dan `:feature:paylater:impl` dikonversi menjadi Dynamic Feature Modules. Diunduh via `SplitInstallManager` secara asinkron saat user membuka tile menu terkait.
3. **Optimasi Gradle Caching & Configuration Cache**:
   - Membersihkan akses ilegal terhadap project instance pada task actions.
   - Mengaktifkan Remote Build Cache berbasis S3/MinIO HTTP Storage.
   - Mengaktifkan build optimizations pada `gradle.properties`:
     ```properties
     org.gradle.caching=true
     org.gradle.configuration-cache=true
     org.gradle.parallel=true
     org.gradle.vfs.watch=true
     org.gradle.jvmargs=-Xmx8g -XX:+UseZGC -XX:+ClassUnloading
     android.nonTransitiveRClass=true
     android.enableR8.fullMode=true
     ```

### Hasil Metrik Setelah 6 Minggu Implementasi

| Metrik | Sebelum Optimasi | Sesudah Optimasi | Dampak Bisnis / Teknikal |
| :--- | :--- | :--- | :--- |
| **Clean Build (Local)** | 24m 10s | 4m 20s (from Remote Cache) | Penghematan 82% waktu kompilasi |
| **Incremental Build** | 3m 35s | 11.2 detik | Peningkatan iterasi per developer 19x lipat |
| **CI Pipeline Time** | 38m 00s | 7m 45s | Penghematan biaya CI Runners $2,400/bulan |
| **Base APK Size** | 115 MB | 42 MB | Peningkatan Install Conversion Rate +11.3% |

---

## 9. Trade-offs

| Dimensi Arsitektur | Keuntungan | Biaya / Trade-off |
| :--- | :--- | :--- |
| **Pemisahan `:api` dan `:impl`** | Memaksimalkan paralelisasi kompilasi; ABI stabil; compile classpath terisolasi. | Jumlah modul berlipat ganda (overhead *settings.gradle* traversal); boilerplate interface code meningkat. |
| **Dynamic Feature Delivery** | Memangkas ukuran install download; penghematan storage bagi user. | Kompleksitas tinggi pada navigasi, pengujian testing offline, dan manajemen siklus hidup download status. |
| **Convention Plugins (`build-logic`)** | Type-safe Kotlin DSL; zero copy-paste gradle; konsistensi plugin lintas modul. | Waktu cold compilation project awal meningkat karena `build-logic` harus dikompilasi lebih dulu. |
| **Non-transitive R Classes** | Mempercepat build time drastis; menghindari class bytecode duplication di setiap modul. | Harus mereferensikan package R class modul secara eksplisit (e.g., `com.feature.payment.R.string.title`). |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Circular Dependency Antar Modul
- **Gejala**: Error `Circular dependency between the following tasks: ...` saat sync atau compile.
- **Penyebab**: Modul `:feature:cart` membutuhkan data dari `:feature:user`, dan `:feature:user` mengimpor model dari `:feature:cart`.
- **Solusi**: Pindahkan model yang dipakai bersama ke `:core:model` atau `:feature:cart:api`. Skema dependensi harus unidirectional (Graph Asiklik).

### 10.2 Configuration Cache Serialization Failure
- **Gejala**: `Configuration cache state could not be cached: field 'project' from type 'com.sample.MyCustomTask' is not serializable`.
- **Penyebab**: Custom task memegang referensi ke objek Gradle `Project` di dalam execution logic (`@TaskAction`).
- **Solusi**: Gunakan Gradle Property Injection:
  ```kotlin
  // SALAH
  abstract class CustomTask : DefaultTask() {
      @TaskAction
      fun run() {
          println(project.rootDir.absolutePath) // Runtime error pada Configuration Cache
      }
  }

  // BENAR
  abstract class CustomTask : DefaultTask() {
      @get:InputDirectory
      abstract val rootDirectory: DirectoryProperty

      @TaskAction
      fun run() {
          println(rootDirectory.get().asFile.absolutePath)
      }
  }
  ```

### 10.3 Dynamic Feature Dependency Injection Crash
- **Gejala**: `ClassCastException: android.app.Application cannot be cast to CoreDependenciesProvider` saat membuka DFM.
- **Penyebab**: `SplitCompat.install(this)` belum dieksekusi pada `attachBaseContext` di Custom Application class, atau Activity DFM belum mengimplementasikan `SplitCompat`.
- **Solusi**:
  ```kotlin
  override fun attachBaseContext(base: Context) {
      super.attachBaseContext(base)
      SplitCompat.install(this)
  }
  ```

---

## 11. Best Practices (Production Checklist)

- [ ] **Gunakan Version Catalog**: Sentralisasikan semua third-party libraries dan plugin di `gradle/libs.versions.toml`.
- [ ] **Terapkan `implementation` sebagai Default**: Hindari penggunaan `api` kecuali modul tersebut memang sengaja mengekspos public interface ke consumer di atasnya.
- [ ] **Aktifkan Non-Transitive R Classes**: Pastikan `android.nonTransitiveRClass=true` menyala di `gradle.properties`.
- [ ] **Isolasi Logika Build di `build-logic`**: Hapus script scriptlet Groovy (`apply from: "common.gradle"`). Gunakan Kotlin Convention Plugins dengan type-safe schema.
- [ ] **Cegah Direct Inter-Feature Dependency**: Modul `:feature:A` **dilarang keras** menambahkan dependensi langsung ke `:feature:B`. Gunakan interaksi via `:feature:B:api` atau Event Bus / Deep Link routing terdesentralisasi.
- [ ] **Verifikasi Configuration Cache**: Uji kompatibilitas build dengan flag `--configuration-cache` di CI untuk mendeteksi *cache invalidation* sedini mungkin.
- [ ] **Enforce Module Graph Rules**: Gunakan architectural linters seperti Module-Check atau custom lint guard untuk menggagalkan commit yang merusak batasan layer arsitektur.

---

## 12. Hands-on Practice

Buat implementasi arsitektur multi-module enterprise dengan struktur direktori `hands-on/m02/` mengikuti langkah teknis berikut:

### Step 1: Inisialisasi Root Workspace
Buka terminal dan bangun direktori dasar:
```bash
mkdir -p hands-on/m02/enterprise-modular
cd hands-on/m02/enterprise-modular
mkdir -p gradle build-logic/src/main/kotlin core/di core/network feature/login/api feature/login/impl app
touch settings.gradle.kts build.gradle.kts gradle.properties
```

### Step 2: Konfigurasi `gradle.properties` untuk Optimasi Mutakhir
Tuliskan pada `hands-on/m02/enterprise-modular/gradle.properties`:
```properties
org.gradle.jvmargs=-Xmx4g -XX:+UseParallelGC
org.gradle.parallel=true
org.gradle.caching=true
org.gradle.configuration-cache=true
android.useAndroidX=true
android.nonTransitiveRClass=true
```

### Step 3: Implementasi Navigation Provider Decoupling
Implementasikan pola desentralisasi navigasi antar fitur tanpa ketergantungan langsung.

File: `feature/login/api/src/main/kotlin/com/enterprise/login/api/LoginNavigationProvider.kt`
```kotlin
package com.enterprise.login.api

import android.content.Context

interface LoginNavigationProvider {
    fun navigateToLogin(context: Context, origin: String)
}
```

File: `feature/login/impl/src/main/kotlin/com/enterprise/login/impl/LoginNavigationProviderImpl.kt`
```kotlin
package com.enterprise.login.impl

import android.content.Context
import android.content.Intent
import com.enterprise.login.api.LoginNavigationProvider

class LoginNavigationProviderImpl : LoginNavigationProvider {
    override fun navigateToLogin(context: Context, origin: String) {
        val intent = Intent(context, LoginActivity::class.java).apply {
            putExtra("EXTRA_ORIGIN", origin)
        }
        context.startActivity(intent)
    }
}
```

File: `feature/login/impl/src/main/kotlin/com/enterprise/login/impl/LoginActivity.kt`
```kotlin
package com.enterprise.login.impl

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity

class LoginActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Implementation logic
    }
}
```

---

## 13. Exercise

### Level Easy
1. Ubah sebuah project monolitik sederhana menjadi 2 modul: `:app` dan `:core:designsystem`. Ekstrak seluruh komponen Colors, Typography, dan Material Themes ke dalam `:core:designsystem` dan hubungkan ke `:app` menggunakan custom convention plugin `AndroidLibraryConventionPlugin`.

### Level Medium
2. Buat skema registrasi routing navigasi dinamis berbasis Dagger Multibindings:
   - Buat modul `:core:navigation` yang mendefinisikan interface `FeatureEntrypoint`.
   - Modul `:feature:dashboard` dan `:feature:profile` mengimplementasikan interface ini dan mengikatnya ke dalam `@IntoMap` menggunakan custom key.
   - Modul `:app` mengumpulkan Map of FeatureEntrypoint untuk me-routing intent tanpa mengetahui dependensi internal activity implementasi masing-masing fitur.

### Level Hard
3. Bangun custom Gradle Plugin pada `build-logic` bernama `ModuleDependencyGuardPlugin`:
   - Plugin harus membaca metadata task graph.
   - Jika ada modul di dalam namespace `:feature:*` yang menambahkan dependensi kompilasi ke modul `:feature:*` lain (selain subpath `:api`), batalkan proses build (*throw BuildException*) dengan pesan error spesifik yang melarang dependency leakage antar-implementasi fitur.

---

## 14. Challenge

**Skenario Rekayasa Lanjut**: Perusahaan Anda sedang mengembangkan fitur transaksi sensitif PCI-DSS yang hanya boleh ada di dalam perangkat saat user melakukan verifikasi biometrik. 

**Tugas Anda:**
1. Desain modul arsitektur `:feature:secure-vault` sebagai Play Dynamic Feature Module berstatus *On-Demand Delivery*.
2. Buat state machine terisolasi yang mengelola alur:
   - *Check module installed status* -> *Download dynamic split APK via Google SplitInstallManager* -> *Observe download progress stream* -> *Install & SplitCompat reload* -> *Inject secure encryption keys via Dagger component dependency*.
3. Tangani skenario edge case:
   - Kegagalan download di jaringan lambat / offline (exponential backoff & retry mechanism).
   - Insufficient device storage error (`SplitInstallErrorCode.INSUFFICIENT_STORAGE`).
   - Eksekusi dynamic injection jika user mematikan koneksi tepat saat proses download selesai namun sebelum APK termuat di memory.
4. Buat arsitektur integrasi ini dengan decoupling penuh tanpa mereferensikan kelas concrete dari `:feature:secure-vault` ke dalam class `:app` secara langsung. Tuliskan blueprint arsitektur, interface, dan state machine management class-nya.

---

## 15. Quiz Evaluasi Pemahaman

### 5 Pertanyaan Basic
1. Apa perbedaan performa mendasar antara deklarasi dependency `api` dan `implementation` pada modul Gradle?
   - *Jawaban/Analisis*: `api` mengekspos dependensi secara transitif ke consumer di atasnya. Mengubah implementasi internal dari dependensi `api` akan memicu kompilasi ulang seluruh modul downstream. `implementation` membatasi dependensi hanya pada compile classpath modul saat ini, mencegah recompilation cascade.
2. Mengapa penggunaan Version Catalog (`libs.versions.toml`) lebih direkomendasikan dibanding `ext` blocks atau `buildSrc`?
   - *Jawaban/Analisis*: `buildSrc` membatalkan seluruh cache build root project setiap kali ada 1 baris perubahan di dalamnya. Version Catalog menyediakan dependensi deklaratif yang type-safe tanpa memicu invalidasi build classpath secara agresif.
3. Apa peran dari `android.nonTransitiveRClass=true` di `gradle.properties`?
   - *Jawaban/Analisis*: Mencegah R class sebuah modul menduplikasi seluruh resource ID dari dependensi downstream-nya. Menjaga bytecode R class tetap kecil dan memotong waktu namespacing resource.
4. Bagaimana relasi arah dependensi kompilasi antara Base App (`:app`) dan Dynamic Feature Module?
   - *Jawaban/Analisis*: Relasinya terbalik dibanding library biasa. DFM bergantung secara compile classpath langsung ke `:app` (`implementation(project(":app"))`), bukan sebaliknya.
5. Apa kegunaan utama dari Gradle Configuration Cache?
   - *Jawaban/Analisis*: Meng-cache hasil konstruksi DAG task graph pada execution phase sebelumnya, sehingga build berikutnya dapat melewati Configuration Phase sepenuhnya jika input build script tidak bermutasi.

### 5 Pertanyaan Intermediate
6. Mengapa task Gradle custom dilarang memegang referensi ke objek `org.gradle.api.Project` saat Configuration Cache aktif?
   - *Jawaban/Analisis*: Objek `Project` menyimpan state mutable Gradle engine yang sangat besar dan referensi dinamis yang tidak dapat diserialisasikan ke disk storage secara deterministik.
7. Bagaimana cara Hilt melakukan scoping singleton di dalam Dynamic Feature Module, dan mengapa pendekatan Component Dependencies sering dibutuhkan?
   - *Jawaban/Analisis*: Hilt standar mengasumsikan monolithic classpath saat compile-time graph validation. Pada DFM, class dikompilasi terpisah dari base APK. Oleh karena itu, kita membutuhkan Dagger Component Dependencies manual untuk mengikat interface graph yang terekspos dari base application ke sub-graph fitur.
8. Apa yang dimaksud dengan *ABI-breaking change* dalam kompilasi Android Library dan apa dampaknya terhadap caching?
   - *Jawaban/Analisis*: ABI (Application Binary Interface) breaking change adalah perubahan pada signature publik (method, class visibility, return type). Dampaknya: Gradle membatalkan build cache seluruh modul konsumen dependent dan memaksa re-kompilasi penuh.
9. Apa perbedaan teknis mendasar antara *Composite Builds* (`includeBuild`) dan multi-project builds biasa (`include`)?
   - *Jawaban/Analisis*: Multi-project builds berbagi build configuration execution context yang sama. *Composite Builds* mengisolasi build execution engine secara independen; modul yang di-include dikompilasi terpisah layaknya binary artifact eksternal.
10. Bagaimana `SplitCompat.install(context)` bekerja di level runtime Android OS?
    - *Jawaban/Analisis*: `SplitCompat.install()` menyisipkan path file split APK yang baru diunduh ke dalam runtime ClassLoader (`BaseDexClassLoader`) dan `AssetManager` aplikasi yang sedang berjalan secara dinamis tanpa perlu me-restart proses aplikasi utama.

### 3 Skenario Kasus Produksi
11. **Skenario 1**: Sebuah tim memiliki 50 modul. Developer melaporkan bahwa task `:app:mergeDexDebug` membutuhkan waktu 70% dari total incremental compilation time meskipun mereka hanya mengubah 1 baris kode dalam function lokal di sebuah feature module. Apa analisis bottleneck Anda dan solusi terkonfigurasinya?
    - *Solusi Analisis*: Bottleneck terjadi karena Minification/Dexing step memproses library yang tidak terpecah dengan benar, atau `minSdk` disetel di bawah 21 tanpa Native Multidex di mode debug, atau *ABI leakage* menyebabkan DEX rebucketing secara massal. Solusi: Pastikan `minSdk` debug disetel ke API 24+ untuk native pre-dexing per modul, aktifkan `android.enableDexingArtifactTransform=true`, dan pastikan dependencies modul feature terkait berstatus `implementation`.
12. **Skenario 2**: CI pipeline mengalami kegagalan intermiten dengan log: `Gradle Build Cache: Corrupted cache artifact found`. Hal ini terjadi setelah implementasi Remote Build Cache menggunakan node storage terdistribusi. Apa investigasi Anda dan langkah mitigasinya?
    - *Solusi Analisis*: Penyebab utama adalah *non-deterministic task outputs* (misal: Task menyematkan timestamp, path absolute mesin lokal, atau output list direktori yang tidak terurut). Ketika mesin lain menarik cache, verifikasi checksum gagal. Solusi: Gunakan `@PathSensitive(PathSensitivity.RELATIVE)` pada input path, bersihkan task yang menghasilkan non-deterministic metadata, dan buat cache read-only untuk branch feature (hanya branch main/CI trunk yang memiliki permission `push: true` ke Remote Cache).
13. **Skenario 3**: Dua feature module (`:feature:booking` dan `:feature:payment`) memiliki flow layar yang saling memanggil secara kondisional, memicu god-module `:core:common` membengkak karena developer menaruh seluruh interface booking dan payment di sana. Bagaimana cara Anda mendesain ulang modul tersebut tanpa menimbulkan *circular dependency* dan mereduksi ukuran `:core:common`?
    - *Solusi Analisis*: Terapkan pola `:feature:booking:api` dan `:feature:payment:api`. Pindahkan kontrak interface, state models, dan router interface masing-masing ke modul `:api` fitur tersebut. Modul implementasi `:feature:booking:impl` hanya bergantung pada `:feature:payment:api`, dan `:feature:payment:impl` hanya bergantung pada `:feature:booking:api`. Hapus seluruh business logic dari `:core:common` sehingga kembali menjadi murni infrastructure primitives.

---

## 16. Summary

- **Struktur Modular Modern**: Memisahkan aplikasi ke dalam layer `:feature:*:impl`, `:feature:*:api`, dan `:core:*` mengeliminasi coupling, memaksimalkan paralelisasi proses compile, dan mencegah recompilation cascade yang destruktif terhadap produktivitas tim.
- **Gradle Ecosystem Optimization**: Transisi ke Kotlin DSL Convention Plugins via `build-logic`, Version Catalog (`libs.versions.toml`), Configuration Cache, Remote Caching, dan Non-transitive R Classes merupakan fondasi absolut dalam rekayasa sistem Android enterprise untuk mencapai *sub-minute incremental build times*.
- **Dynamic Feature Delivery**: Memberikan arsitektur modular kemampuan untuk memecah boundary monolitik APK runtime, mengurangi Initial Download Size melalui download dinamis on-demand yang diikat secara independen melalui Dagger Component Dependencies.