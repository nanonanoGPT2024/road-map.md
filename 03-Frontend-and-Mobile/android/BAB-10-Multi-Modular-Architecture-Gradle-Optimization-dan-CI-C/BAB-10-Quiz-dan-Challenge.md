# BAB 10: Quiz, Challenge, & Knowledge Check
**Multi-Modular Architecture, Gradle Optimization, & CI/CD**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: ABI vs Non-ABI Breaking Changes & Dependency Scope
Jelaskan perbedaan mendasar antara Application Binary Interface (ABI) breaking changes dan non-ABI changes dalam konteks kompilasi inkremental Gradle pada proyek multi-module. Analisis mengapa penggunaan `implementation` secara ketat mengisolasi siklus kompilasi ulang (recompilation DAG), sedangkan penggunaan `api` secara ceroboh dapat memicu *cascading rebuild* di seluruh modul downstream!

### Soal 1.2: Anatomi Gradle Lifecycle & Dual Caching Mechanism
Bedakan secara arsitektural antara **Configuration Cache** dan **Build Cache** (Local & Remote) pada Gradle runtime. Jelaskan fase lifecycle Gradle (*Initialization*, *Configuration*, *Execution*) di mana masing-masing mekanisme bekerja, kondisi apa yang membatalkan (*invalidate*) cache masing-masing, serta dampaknya terhadap alokasi resource CPU dan disk I/O.

### Soal 1.3: Topologi Modularisasi: Layer vs Feature
Bandingkan arsitektur modularisasi **Feature-by-Layer** (e.g., `:core:data`, `:core:network`, `:core:ui`) dengan **Feature-by-Feature** (e.g., `:feature:checkout:impl`, `:feature:checkout:api`). Mengapa pendekatan Feature-by-Layer cenderung menghasilkan *circular dependency* tersembunyi dan *high coupling* seiring pertumbuhan tim engineering? Evaluasi dari sudut pandang *Single Responsibility Principle* (SRP) pada level arsitektur modul.

### Soal 1.4: Inverted Dependency Injection & Module Decoupling
Dalam arsitektur di mana `:feature:checkout` membutuhkan navigasi langsung ke `:feature:profile`, bagaimana pola **Interface/Implementation Module Split** (API-Impl pattern) atau **Dependency Inversion Principle** (DIP) memecahkan ketergantungan langsung antar-fitur tanpa memicu *circular dependency* dan tanpa membuat dependensi transitif ke `:app` module?

### Soal 1.5: Determinisme R8/ProGuard dan Baseline Profiles pada App Startup
Jelaskan korelasi antara R8 optimizer (tree shaking, class merging, desugaring), DEX layout optimization, dan **Baseline Profiles** dalam memangkas latensi *Cold Start* aplikasi. Mengapa verifikasi Baseline Profile wajib diintegrasikan ke dalam pipeline CI/CD sebagai langkah preventif terhadap regresi performa *runtime bytecode* (AOT/Cloud Profile compilation)?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Debugging Configuration Cache Violations
Perhatikan deklarasi task kustom pada skrip build berikut:

```kotlin
abstract class GenerateMetadataTask : DefaultTask() {
    @get:OutputFile
    abstract val outputFile: RegularFileProperty

    @TaskAction
    fun execute() {
        val rootDir = project.rootDir // VIOLATION
        val gitHash = project.providers.exec { /* ... */ } // POTENTIAL VIOLATION
        outputFile.get().asFile.writeText("Root: $rootDir, Git: $gitHash")
    }
}
```

Jelaskan secara mendalam mengapa task di atas gagal saat `--configuration-cache` diaktifkan dengan pesan galat *"Accessing Gradle API 'Project.rootDir' at execution time is unsupported"*. Tuliskan refaktor konkret menggunakan `ProjectLayout`, `ValueSource`, atau `Provider API` agar task sepenuhnya *configuration-cache compatible* dan thread-safe.

### Soal 2.2: Resolusi Diamond Dependency Conflict & ABI Mismatch
Sebuah proyek modular memiliki relasi dependensi berikut:
* `:feature:order` bergantung pada `com.squareup.okhttp3:okhttp:4.9.3`
* `:feature:payment` bergantung pada library pihak ketiga `:thirdparty:sdk`, yang secara transitif memaksa dependensi ke `com.squareup.okhttp3:okhttp:4.12.0`
* Modul `:core:network` mendeklarasikan versi internal via Gradle Version Catalog.

Saat aplikasi di-*merge* pada `:app`, terjadi runtime crash:
`java.lang.NoSuchMethodError: 'okhttp3.internal.concurrent.TaskRunner okhttp3.OkHttpClient.getTaskRunner$okhttp()'`

Bagaimana Gradle mengeksekusi *Conflict Resolution Strategy* secara default? Bagaimana Anda melakukan investigasi menggunakan task `dependencies` atau `dependencyInsight`, dan bagaimana cara mengamankan integritas versi tersebut menggunakan `Strict Versioning` (`strictly`) atau `Enforced Platform` (BOM)?

### Soal 2.3: Non-Deterministic Build Cache Key Profiling
Build scan lokal menunjukkan bahwa task `:feature:auth:kspKotlin` konsisten mengalami **Cache Miss** padahal tidak ada kode sumber Kotlin di modul `:feature:auth` yang berubah. 
Sebutkan 4 akar masalah teknis (root causes) yang menyebabkan *build cache key* bermutasi (misal: absolute path leakage, volatile resource injection seperti timestamp/Git commit hash, dynamic JVM arguments, atau non-deterministic file order output). Bagaimana Anda memverifikasi perbedaannya menggunakan *Gradle Build Scan Comparison*?

### Soal 2.4: Daemon Heap Exhaustion & Metaspace Leakage
Pada CI server berkapasitas 32 GB RAM yang menjalankan build multithreaded paralel (`org.gradle.parallel=true`, `org.gradle.workers.max=8`), Gradle Daemon sering *crash* dengan pesan:
`java.lang.OutOfMemoryError: Metaspace` atau `Daemon disappeared unexpectedly`.

Analisis akar masalah mengapa migrasi besar-besaran ke Kotlin DSL (`.gradle.kts`) dan eksekusi ratusan dynamic classloaders pada compile tasks membebani Metaspace JVM. Bagaimana Anda menyusun konfigurasi `org.gradle.jvmargs` yang presisi (termasuk GC policy seperti G1GC, `-XX:MaxMetaspaceSize`, `-XX:+HeapDumpOnOutOfMemoryError`) untuk menyeimbangkan performa daemon reuse tanpa memicu OOM killer di level OS?

### Soal 2.5: Test Sharding & Flakiness Isolation pada Matrix CI
Dalam pipeline CI/CD skala enterprise dengan 4.000+ unit test dan 800+ instrumentation test, strategi *single runner execution* memicu bottleneck waktu (35+ menit) dan kegagalan pipeline akibat 0.5% flaky test.
Jelaskan rancangan arsitektur pipeline untuk mengimplementasikan:
1. **Dynamic Test Sharding** berbasis algoritma historical execution time.
2. Isolasi otomatis flaky test menggunakan mekanisme *selective retry* (Gradle test runner `--rerun-failing-tests-first` atau custom test filter) tanpa menutupi *true positive failures*.
3. Evaluasi trade-off pengujian multi-module menggunakan **Android Test Orchestrator** vs **Marathon/Flank** pada managed cloud device farm.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Remote Build Cache Poisoning & Invalidation Breakdown
* **Konteks:** Perusahaan fintech dengan 60 engineer dan 200+ modul Android mengaktifkan Gradle Remote Build Cache yang di-host menggunakan HTTP/S storage cluster. Tiba-tiba, 80% engineer melaporkan bahwa build lokal mereka sukses menarik cache (`FROM-CACHE`), namun aplikasi langsung mengalami `AbstractMethodError` atau *resource missing crash* (`Resources$NotFoundException`) sesaat setelah diluncurkan di emulator. Sementara itu, build dari clean branch di server CI utama lulus kompilasi tanpa issue.
* **Pertanyaan Diagnostik:**
  1. Bagaimana mekanisme kalkulasi input snapshot Gradle bekerja pada task compilation/packaging, dan skenario apa yang memicu *Cache Poisoning* (artifact yang korup atau bervarian salah masuk ke cache server)?
  2. Langkah mitigasi cepat apa yang harus diambil pada level remote cache node dan client daemon?
  3. Desain kebijakan sanitasi (validation hook) apa yang harus dipasang pada CI write-back pipeline untuk menjamin hanya build deterministik dari branch terlindungi (misal: `main`) yang memiliki otorisasi menulis (`push=true`) ke remote cache?

### Skenario B: Race Condition pada Custom Gradle Plugin & Build Logic Migration
* **Konteks:** Tim Platform Architecture sedang memigrasikan skrip build dari legacy Groovy `allprojects {} / subprojects {}` ke **Convention Plugins via `build-logic`**. Salah satu plugin bertugas menginjeksi konfigurasi proteksi keamanan dan menandatangani file `.apk` / `.aab` menggunakan vault secret. Ketika build dijalankan dengan `--parallel`, pipeline acak mengalami build failure:
  `org.gradle.api.UnknownProjectException: Project with path ':core:security' not found`
  atau file signing payload terisi nilai null/kosong pada beberapa modul fitur saja.
* **Pertanyaan Diagnostik:**
  1. Mengapa manipulasi state cross-project menggunakan `allprojects`/`subprojects` atau akses langsung `project.findProject(":other")` melanggar isolasi modul dan memicu race condition pada fase Configuration di Gradle parallel execution?
  2. Bagaimana arsitektur `build-logic` yang benar menggunakan standard `Plugin<Project>` dan `libs.versions.toml` untuk mendistribusikan konfigurasi secara reaktif via `pluginManager.withPlugin(...)` tanpa mengevaluasi project lain secara prematur?
  3. Bagaimana memodelkan dependency order antar task yang berbeda module menggunakan Gradle Task Provider API tanpa melanggar *Project Isolation*?

### Skenario C: Dynamic Feature Module (Play Feature Delivery) vs Flat Multi-Module Trade-Off
* **Konteks:** Aplikasi SuperApp e-commerce memiliki ukuran download APK awal sebesar 85 MB. Manajemen menargetkan pengurangan *initial download size* hingga di bawah 30 MB. Tim merencanakan ekstraksi modul `:feature:insurance`, `:feature:flights`, dan `:feature:gaming` menjadi **Dynamic Feature Modules (DFM)** dengan model instalasi *on-demand*. Namun, modul-modul ini bergantung pada dependency injection global (Hilt), database lokal (Room), dan library navigasi jetpack.
* **Pertanyaan Diagnostik:**
  1. Analisis implikasi arsitektur terhadap Dependency Inversion: Mengapa DFM membalikkan panah dependensi (`:app` tidak lagi compile-time depend ke DFM, melainkan DFM yang depend ke `:app`), dan bagaimana hal ini memengaruhi kompilasi Hilt component graph?
  2. Bagaimana strategi penanganan *Application Context* dan dynamic class loading (`SplitCompat`) agar resource layout, asset, dan native library (`.so`) dapat diakses tanpa memory leak atau crash saat module diunduh secara runtime?
  3. Bandingkan trade-off kompleksitas antara adopsi DFM vs modularisasi flat berbasis micro-features dikombinasikan dengan ProGuard tuning, WebP conversion, dan R8 full mode. Kapan DFM menjadi *anti-pattern*?

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise Build-Logic Modernization, Strict Boundaries, & Zero-Violation CI Pipeline

#### Problem Statement
Anda mewarisi sistem monolitik Android berumur 5 tahun yang baru dipecah setengah jalan menjadi 35 modul. Proyek masih menggunakan skrip `build.gradle` Groovy usang dengan blok `subprojects {}` sepanjang 400 baris di root build script. 
Kondisi saat ini:
- Build time lokal (clean build): **18 menit 40 detik**.
- `--configuration-cache` gagal total dengan 42 violation errors.
- Terjadi kebocoran transitive dependencies di mana modul `:feature:cart` bisa mengakses kelas implementasi internal dari `:core:database`.
- Developer sering mengabaikan dependency graph cycles dan memasukkan dynamic dependency version (`1.2.+`).

#### Requirements
1. **Build-Logic Engine:** Rancang dan implementasikan struktur `build-logic` berbasis Kotlin DSL convention plugins (`composite build` via `includeBuild("build-logic")`) yang mengabstraksi:
   - `android.library` convention (compileSdk, minSdk, desugaring, compiler flags).
   - `android.feature` convention (UI stack: Compose, Lifecycle, navigation).
   - `android.hilt` convention.
   - `android.lint` & quality gates convention.
2. **Dependency Boundary Enforcement:** Konfigurasikan dependensi menggunakan `api` dan `implementation` secara disiplin dengan struktur *API-Implementation module pairing* untuk minimal 1 modul fitur (`:feature:checkout:api` dan `:feature:checkout:impl`).
3. **Configuration Cache Compliance:** Bersihkan seluruh deklarasi custom task agar 100% kompatibel dengan Gradle Configuration Cache. Tidak boleh ada pemanggilan `project` API di dalam Task Execution.
4. **Production CI Pipeline (GitHub Actions / GitLab CI):**
   - Tulis pipeline deklaratif YAML yang mengimplementasikan remote cache read/write separation.
   - Mengimplementasikan matrix compilation paralel, Baseline Profile generation verification, dan auto-cancellation pada push commit baru.

#### Constraints
- Wajib menggunakan Gradle Version Catalogs (`gradle/libs.versions.toml`).
- Penggunaan `allprojects {}` dan `subprojects {}` di root `build.gradle.kts` **dilarang keras** (harus 0 baris code konfigurasi modul).
- R8/ProGuard harus tervalidasi pada modul release dengan setting `isMinifyEnabled = true` dan `isShrinkResources = true`.
- Semua dependensi internal project wajib menggunakan type-safe project accessors (`projects.core.network`).

#### Expected Output
1. File struktur direktori dari `build-logic` beserta implementasi satu file convention plugin lengkap (`AndroidFeatureConventionPlugin.kt`).
2. Snapshot file `libs.versions.toml` yang mendemonstrasikan catalogs, bundle, dan plugins.
3. Contoh task implementasi kustom Gradle yang kompatibel dengan Configuration Cache via Worker API / Provider API.
4. File definisi pipeline CI (`.github/workflows/ci.yml` atau `.gitlab-ci.yml`) yang aman, scalable, dan mendemonstrasikan optimasi caching.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan siklus hidup Gradle (*Initialization*, *Configuration*, *Execution*) dan kapan execution graph dibangun.
- [ ] Mekanisme deteksi input-output snapshotting Gradle untuk menentukan status `UP-TO-DATE` vs `FROM-CACHE`.
- [ ] Perbedaan fundamental arsitektur `implementation`, `api`, `compileOnly`, dan `runtimeOnly` dalam konteks *Compilation Classpath* vs *Runtime Classpath*.
- [ ] Batasan Gradle Configuration Cache: Larangan referensi instans `Project`, `Task`, atau mutable global state di dalam *task action*.
- [ ] Prinsip *Dependency Inversion* pada multi-module Android untuk menghindari *tight coupling* dan *circular dependencies* (khususnya pola Navigation & DI).
- [ ] Mekanisme eksekusi R8 compiler: Tree-shaking, Obfuscation, Desugaring, Class Merging, dan optimasi relokasi DEX.
- [ ] Prinsip kerja Baseline Profile: *AOT Compilation vs JIT*, compilation profile loading saat deployment package di Android Runtime (ART).
- [ ] Peran Composite Builds (`includeBuild`) sebagai pengganti `buildSrc` untuk portabilitas dan invalidasi cache minimal.

### Saya tidak perlu menghafal:
- [ ] Seluruh flag compiler bytecode JVM internal atau string ProGuard mapping manual (gunakan template resmi AndroidX/AGP).
- [ ] Sintaks exact dari ratusan API internal Gradle tools yang kerap didegradasi antar versi AGP (cukup pahami pola deklarasi Provider/Property API).
- [ ] Daftar SHA-256 hash atau raw URL dependensi binary secara hardcoded (cukup manfaatkan Version Catalog dan checksum verification metadata).

### Saya harus bisa melakukan:
- [ ] Mendiagnosis bottleneck build menggunakan **Gradle Build Scan** (Critical Path analysis, Task execution duration, Memory profiling).
- [ ] Memecah modul monolithic `:app` menjadi decoupled architecture (`:core`, `:feature:api`, `:feature:impl`) menggunakan *Type-Safe Project Accessors*.
- [ ] Membangun dan mengelola Gradle Convention Plugins di dalam direktori `build-logic` untuk standardisasi corporate build script.
- [ ] Menyelesaikan konflik dependensi kustom menggunakan Gradle resolution strategy rules (`enforce`, `strictly`, `exclude`).
- [ ] Mengonfigurasi dan mengamankan Remote Build Cache pada CI/CD agent dengan pemisahan kredensial read-only (developer/PR) dan read-write (protected trunk branch).
- [ ] Menulis custom Gradle Task yang 100% *Configuration-Cache compliant* memanfaatkan `Worker API` untuk konkurensi performa tinggi.
- [ ] Mengonfigurasi automated performance instrumentation profiling (Baseline Profiles) ke dalam pipeline continuous deployment.