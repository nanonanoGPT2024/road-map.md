# BAB 04: Quiz, Challenge, & Knowledge Check
**Dependency Injection Enterprise (Dagger-Hilt & KSP)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Semantik Lifecycle dan Retensi Objek Antar-Scope Hilt
Jelaskan perbedaan mendasar siklus hidup (*lifecycle*), alokasi memori, dan retensi instance antara `@Singleton` (`SingletonComponent`), `@ActivityRetainedScoped` (`ActivityRetainedComponent`), dan `@ActivityScoped` (`ActivityComponent`). Analisis apa yang terjadi pada ketiga objek tersebut saat terjadi *configuration change* (misalnya: rotasi layar) dan saat sistem melakukan *process death* (misalnya: *low-memory kill* oleh OS).

### Soal 1.2: Mekanisme Kompilasi: KSP vs KAPT pada Dependency Graph Generation
Bandingkan mekanisme internal Kotlin Symbol Processing (KSP) dan Kotlin Annotation Processing Tool (KAPT) saat memproses anotasi Dagger/Hilt (`@Inject`, `@Provides`, `@Component`). Mengapa KAPT memerlukan kompilasi *Java Stubs* yang menyebabkan *build-time overhead* signifikan pada multi-module project berskala ratusan modul, dan bagaimana arsitektur KSP mengeliminasi proses tersebut secara langsung pada Abstract Syntax Tree (AST)?

### Soal 1.3: Enkapsulasi & Imutabilitas: Constructor Injection vs Field Injection
Dilihat dari prinsip *Inversion of Control* (IoC) dan *clean architecture*, jelaskan mengapa *Constructor Injection* (`@Inject constructor(...)`) harus selalu diprioritaskan dibandingkan *Field Injection* (`@Inject lateinit var ...`). Kapan *Field Injection* menjadi sebuah keharusan teknis yang tidak dapat dihindari pada platform Android, dan bagaimana Hilt mengotomatisasi jembatan injection tersebut di balik layar?

### Soal 1.4: Bytecode Optimization: `@Binds` vs `@Provides`
Secara teknis, mengapa dokumentasi resmi Dagger sangat merekomendasikan penggunaan `@Binds` di dalam kelas `interface` abstrak alih-alih `@Provides` di dalam `object` atau `class` konkrit untuk melakukan *binding* implementasi ke interface-nya? Jelaskan perbedaan *generated code* (Java bytecode) dari kedua anotasi ini dan dampaknya terhadap ukuran APK (*dex method count*) serta performa *class-loading*.

### Soal 1.5: Dagger 2 Pure Component Hierarchy vs Hilt Monolithic Hierarchy
Dagger murni memungkinkan pembuatan subcomponent graph yang sepenuhnya terkontrol secara arbitrer (*custom component tree*), sementara Hilt memaksakan hierarki komponen tunggal yang seragam (*predefined monolithic hierarchy*). Evaluasi trade-off arsitektur ini dalam konteks *engineering velocity*, standarisasi tim enterprise, dan fleksibilitas *dependency scoping*.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Resolusi Compile-Time Cycle & Evaluasi Lazy vs Provider
Dagger memvalidasi *dependency graph* pada saat kompilasi (*compile-time graph validation*). Jika terjadi *circular dependency* antara `ClassA` dan `ClassB`:
1. Mengapa compiler Dagger gagal mengompilasi kode tersebut?
2. Bagaimana mekanisme kerja internal `dagger.Lazy<T>` versus `javax.inject.Provider<T>` dalam memutus siklus tersebut?
3. Jelaskan risiko retensi memori atau konkurensi (thread-safety) saat menggunakan `Lazy<T>` pada lingkungan *multi-threaded coroutines*.

### Soal 2.2: Dynamic Plugin Architecture via Multibindings
Jelaskan bagaimana `@IntoSet`, `@ElementsIntoSet`, dan `@IntoMap` (Multibindings) digunakan untuk membangun arsitektur *feature-flagging* atau *analytics routing* yang *decoupled* pada multi-module enterprise app. Bagaimana Dagger menyatukan dependensi dari modul Gradle yang berbeda ke dalam satu koleksi tanpa membuat modul-modul tersebut saling mereferensikan dependensi konkritnya secara langsung?

### Soal 2.3: Lifecycle Bridge dengan `@AssistedInject` dan `@AssistedFactory`
Bayangkan sebuah `ViewModel` atau `WorkManager` yang membutuhkan dependensi terkelola dari Dagger (misalnya: `OrderRepository`) dan parameter runtime dinamis yang hanya tersedia saat eksekusi (misalnya: `orderId: String` dari `SavedStateHandle` atau `WorkerParameters`). Jelaskan mengapa Anda tidak boleh memaksakan parameter runtime tersebut ke dalam Dagger graph utama, dan jelaskan langkah teknis implementasi `@AssistedInject` beserta `@AssistedFactory` untuk menyelesaikan masalah ini.

### Soal 2.4: Out-of-Graph Dependency Retrieval Menggunakan `@EntryPoint`
Komponen framework Android tertentu (seperti `ContentProvider`, integrasi library C++ via JNI, atau dynamic push notification service) diinstansiasi oleh OS sebelum atau di luar konteks hierarki standar Hilt (`Application`, `Activity`, `Fragment`, `View`, `Service`). Bagaimana `@EntryPoint` dan `EntryPoints.get(...)` bekerja secara internal untuk menjembatani kode non-Hilt tersebut agar dapat mengakses dependensi dari *Dagger graph* tanpa merusak enkapsulasi graph?

### Soal 2.5: Scope Escalation & Memory Leak Path Analysis
Analisis kode berikut: Sebuah class `@Singleton` menginjeksi sebuah interface `UserSessionListener`. Salah satu implementasi `UserSessionListener` dianotasi dengan `@ActivityScoped` dan memegang referensi ke `Context` activity. 
1. Mengapa Dagger compiler melempar error *scope mismatch* (*scoped provider cannot be referenced from an unscoped/higher-scoped component*)?
2. Jika batasan kompilasi ini dibobol secara sengaja menggunakan manual service-locator atau callback injection, jelaskan rantai *memory leak* (objek apa yang menahan objek apa) yang akan terdeteksi di LeakCanary saat activity di-destroy.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Monorepo Build-Time Degradation & Transitive Graph Pollution
**Konteks Perusahaan:** Aplikasi super-app memiliki 140 modul Gradle. Build time CI/CD meningkat drastis hingga 48 menit. Tim platform mengidentifikasi bahwa modul `:app` bertindak sebagai "dapur raksasa" yang mengompilasi seluruh graph Hilt menggunakan KAPT, sehingga setiap perubahan kecil pada kode di modul domain level bawah memicu kompilasi ulang ribuan generated files di modul `:app`. Selain itu, migrasi ke KSP tertunda karena adanya dependensi sirkular transisi antar module.

**Pertanyaan Diagnostik:**
1. Bagaimana Anda merancang migrasi bertahap dari KAPT ke KSP pada dependency graph Dagger/Hilt tanpa menghentikan *delivery* fitur harian?
2. Bagaimana Anda memanfaatkan isolasi komponen (*Component Dependencies* atau *Public API / Internal Implementation boundaries*) untuk mencegah *invalidation* seluruh Hilt graph saat modul leaf (modul data/domain) berubah?
3. Langkah profiling apa yang akan Anda jalankan (menggunakan Gradle Build Scan / profiling flags) untuk menemukan bottleneck anotasi Dagger secara presisi?

### Skenario B: State Leak & Session Corruption pada Multi-Account Switch
**Konteks Perusahaan:** Aplikasi perbankan digital mendukung fitur *multi-account switching* tanpa me-restart aplikasi (*in-app re-authentication*). Ditemukan insiden keamanan kritis (*Severity 1*): Pengguna A *logout*, lalu Pengguna B *login* pada perangkat yang sama. Token autentikasi dan keranjang transaksi Pengguna A masih terbaca oleh Pengguna B pada beberapa panggilan API Retrofit/OkHttp. Root-cause sementara menunjukkan bahwa tim engineering menandai `AuthInterceptor`, `OkHttpClient`, dan `SessionRepository` dengan anotasi `@Singleton`.

**Pertanyaan Diagnostik:**
1. Mengapa pola `@Singleton` pada Hilt menjadi *anti-pattern* fatal untuk data yang memiliki lifecycle berbasis "user session"?
2. Rancang arsitektur Dagger Component baru (Subcomponent atau dynamic custom scope) yang merepresentasikan `UserSessionComponent`. Bagaimana siklus hidup (*create*, *retain*, *destroy*) dari graph session ini diatur saat event Login dan Logout terjadi?
3. Bagaimana mekanisme pengalihan (*fallback*) dependensi network layer dari keadaan *Unauthenticated State* (menggunakan guest token/no token) ke *Authenticated State* (menggunakan token user spesifik) secara thread-safe tanpa melakukan race condition pada background coroutines yang sedang berjalan?

### Skenario C: Dynamic Feature Module (DFM) Dependency Inversion Failure
**Konteks Perusahaan:** Aplikasi e-commerce mengimplementasikan Play Feature Delivery (Dynamic Feature Module) untuk modul `:checkout`. Modul `:checkout` diunduh secara on-demand saat pengguna menekan tombol pembayaran. Modul `:app` tidak memiliki dependensi compile-time terhadap modul `:checkout` (dependensi terbalik: `:checkout` bergantung pada `:app`). Tim mengalami crash runtime: `ClassNotFoundException` dan Dagger Graph Incomplete error karena Hilt tidak dapat membuat graph dependensi di `:checkout` yang membutuhkan service internal yang dideklarasikan di modul `:app`.

**Pertanyaan Diagnostik:**
1. Mengapa anotasi standar Hilt (`@HiltAndroidApp`, `@AndroidEntryPoint`) memiliki limitasi arsitektural saat digunakan secara murni di dalam Dynamic Feature Modules (DFM)?
2. Bagaimana Anda menyusun integrasi Dagger pada DFM menggunakan `@EntryPoint` atau Dagger Core Subcomponents agar DFM dapat mengonsumsi dependensi `:app` dan sebaliknya mendaftarkan implementasinya ke core app?
3. Rancang mitigasi jika DFM gagal diunduh (network error) atau graph dependency gagal di-instansiasi saat runtime agar aplikasi tidak mengalami *hard crash*.

---

## 4. Chapter Challenge

### Tantangan Praktis: Multi-Tenant Enterprise Session Engine dengan Dagger-Hilt & KSP

#### Problem Statement
Dalam aplikasi multi-tenant enterprise (misalnya SaaS Enterprise Workspace), pengguna dapat beralih antar 3 workspace berbeda secara instan. Setiap tenant/workspace memiliki:
1. `TenantConfiguration` yang unik (Base URL, Timeout, Feature Flags).
2. `OkHttpClient` dan `Retrofit` terisolasi (termasuk Auth Token masing-masing tenant).
3. `DatabaseSession` (Room/SQLDelight) terenkripsi yang berbeda per tenant.

Menggunakan satu graph `@Singleton` untuk menyimpan data tenant terbukti memicu *data bleeding*. Me-restart aplikasi setiap ganti workspace ditolak oleh Product Manager karena merusak User Experience.

#### Requirements
1. **Scope & Hierarchy Architecture:**
   - Pertahankan `@Singleton` / `SingletonComponent` hanya untuk dependensi global (Device Info, Crashlytics, Telemetry, ConnectivityManager).
   - Buat custom session mechanism (misalnya: `UserSessionComponent` atau `TenantComponent`) yang dapat di-instansiasi, di-cache, dan dihancurkan (*invalidated*) secara dinamis di runtime tanpa me-restart proses Android.
2. **KSP Compliance:**
   - Seluruh proyek harus dikompilasi murni menggunakan KSP (tanpa plugin KAPT). Konfigurasikan Dagger KSP processor pada modul multi-tenant.
3. **Dynamic Network Interception:**
   - Setiap API call yang dipicu dari layar aktif tenant harus secara otomatis menggunakan instance `Retrofit` milik tenant yang sedang aktif, diinjeksi ke dalam `ViewModel` menggunakan `@HiltViewModel`.
4. **Thread-Safe Session Invalidation:**
   - Sediakan fungsi `switchTenant(tenantId: String)` dan `invalidateTenant(tenantId: String)`.
   - Proses invalidasi harus membersihkan database connection pool dan in-memory cache milik tenant tersebut secara atomik tanpa memicu race condition pada coroutine worker yang sedang berjalan di background.

#### Constraints
- Dilarang keras menggunakan *anti-pattern* static singleton global (misalnya `MySessionManager.currentTenantId`) yang diakses langsung di dalam `Interceptor`. Tenant Context harus terikat kuat pada *injected graph instance*.
- Memory leak tolerance: 0 byte. Instance tenant lama yang di-invalidate harus dapat di-*garbage collect* sepenuhnya (diverifikasi via assertions pada Heap Dump).
- Wajib menyertakan abstraksi pengujian (Test Doubles / Mocks) untuk menguji skenario pergantian tenant secara unit-test.

#### Expected Output
1. File deklarasi Dagger Component/Subcomponent atau Hilt Custom EntryPoint architecture untuk hierarki tenant session.
2. File `TenantSessionManager` thread-safe yang mengelola lifecycle session graph (menggunakan Kotlin `StateFlow` dan Mutex/Atomic primitives).
3. Unit Test suite (JUnit 5 + Coroutines Test) yang memverifikasi bahwa:
   - Tenant A dan Tenant B memiliki instance `OkHttpClient` dan `RoomDatabase` yang berbeda secara referensial (`assertNotSame`).
   - Saat Tenant A di-invalidate, pemanggilan dependensi Tenant A berikutnya melempar `IllegalStateException("Session Expired")`.
   - Tidak ada kebocoran memory pada session lifecycle.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Siklus hidup hierarki Dilt Built-in Components (`SingletonComponent` $\rightarrow$ `ActivityRetainedComponent` $\rightarrow$ `ActivityComponent` $\rightarrow$ `FragmentComponent` $\rightarrow$ `ViewComponent`) dan kapan tepatnya masing-masing komponen dibuat dan dihancurkan.
- [ ] Perbedaan fundamental antara abstraksi dependensi menggunakan `@Binds` vs instansiasi kode konkrit menggunakan `@Provides`.
- [ ] Arsitektur KSP dalam memproses simbol AST dibandingkan Java stub generation pada KAPT, beserta implikasi performa kompilasinya.
- [ ] Konsep Multibindings (`@IntoMap`, `@IntoSet`) dan fungsinya dalam membangun plugin architecture yang *loosely coupled*.
- [ ] Perbedaan fungsional dan memory footprint antara direct injection (`T`), dynamic deferred injection (`Provider<T>`), dan memoized injection (`Lazy<T>`).
- [ ] Keterbatasan Hilt pada Dynamic Feature Modules (DFM) dan cara mengatasinya via EntryPoints atau pure Dagger subcomponents.

### Saya tidak perlu menghafal:
- [ ] Kode sintaks generated files Dagger (misalnya: `_Factory.java`, `_MembersInjector.java`, `DaggerApplicationComponent.java`).
- [ ] Seluruh anotasi flag experimental compiler flags Dagger/KSP secara detail di luar dokumentasi resmi.
- [ ] Nama package internal Dagger yang berawalan `dagger.internal.*`.

### Saya harus bisa melakukan:
- [ ] Memigrasikan modul Gradle berukuran besar dari `kapt` ke `ksp` untuk dependency Dagger-Hilt tanpa memicu breaking changes pada build graph.
- [ ] Melakukan debugging dan resolving compile-time error Dagger: *Dependency Cycle*, *Missing Binding*, dan *Scope Mismatch*.
- [ ] Mengimplementasikan `@AssistedInject` untuk menginjeksi ViewModel atau Background Workers yang membutuhkan parameter runtime dinamis.
- [ ] Mengekstrak dependensi dari luar hierarki Hilt standar (misalnya di library pihak ketiga atau ContentProvider) menggunakan `@EntryPoint` dan `EntryPoints.get()`.
- [ ] Mengaudit memory leak yang disebabkan oleh Scope Escalation (misalnya Short-lived object tertahan di Long-lived component) menggunakan LeakCanary dan Android Studio Memory Profiler.