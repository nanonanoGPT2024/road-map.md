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
