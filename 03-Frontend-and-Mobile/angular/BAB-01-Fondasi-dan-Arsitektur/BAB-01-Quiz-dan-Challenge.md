# BAB 01: Quiz, Challenge, & Knowledge Check
**Fondasi Arsitektur Modern & Standalone Components**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Eliminasi Indireksi Kompilasi Ivy
Dalam arsitektur legacy Angular, `NgModule` bertindak sebagai *compilation context* sekaligus unit deklarasi dependensi template. Jelaskan bagaimana kompilator Ivy mengompilasi `@Component({ standalone: true, imports: [...] })` secara internal! Mengapa pendekatan deklarasi langsung ini secara fundamental meningkatkan efisiensi *tree-shaking* pada build bundler (seperti ESBuild) dibandingkan pendekatan `NgModule`?

### Soal 1.2: Paradigma Bootstrapping Modern vs Legacy
Analisis perbedaan arsitektural antara:
```typescript
platformBrowserDynamic().bootstrapModule(AppModule);
```
dan
```typescript
bootstrapApplication(AppComponent, appConfig);
```
Fokuskan jawaban Anda pada inisialisasi runtime platform, eliminasi overhead *root module factory*, dan bagaimana konfigurasi aplikasi diorganisir menggunakan `ApplicationConfig` serta fungsi utilitas `provide*()`.

### Soal 1.3: Mekanisme Scoping Template Dependencies
Pada komponen Standalone, array `imports: [...]` diletakkan langsung di dalam metadata `@Component`. Jika Komponen `ParentComponent` mengimpor `ChildComponent`, apakah sub-dependensi (directive, pipe, komponen lain) yang diimpor oleh `ChildComponent` secara otomatis bocor (*leaked*) dan dapat digunakan di dalam template `ParentComponent`? Jelaskan batas isolasi (*boundary isolation*) template scope pada Standalone Components!

### Soal 1.4: Injection Context dan Paradigma `inject()`
Angular modern mengadopsi fungsi `inject()` sebagai standar baru resolusi dependensi menggantikan *Constructor Injection*.
1. Apa yang dimaksud dengan *Injection Context*, dan kapan context ini aktif?
2. Mengapa penggunaan `inject()` jauh lebih fleksibel saat membuat *functional composition patterns* (seperti higher-order functions untuk reusable logic) dibandingkan constructor injection?

### Soal 1.5: Built-in Control Flow vs Structural Directives
Evaluasi transformasi dari structural directives legacy (`*ngIf`, `*ngFor`, `*ngSwitch`) ke modern built-in control flow (`@if`, `@for`, `@switch`). Mengapa sintaksis `@for` mewajibkan ekspresi `track` (tidak seperti `*ngFor` yang menjadikan `trackBy` opsional), dan bagaimana arsitektur internal Angular memanfaatkan informasi tersebut untuk meminimalkan manipulasi DOM secara deterministik?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Resolusi Circular Dependency pada Standalone Trees
Dalam arsitektur standalone murni, Anda memiliki dua komponen UI rekursif: `FolderTreeComponent` yang harus merender `FileItemComponent`, namun dalam kondisi tertentu `FileItemComponent` dapat memuat sub-folder yang merender kembali `FolderTreeComponent`. 
1. Masalah runtime/build apa yang akan terjadi pada array `imports: [...]`?
2. Bagaimana cara mengatasinya secara elegan tanpa mengorbankan type safety dan tanpa harus mengembalikan implementasi ke `NgModule`?

### Soal 2.2: Dual-Hierarchy Injector: `EnvironmentInjector` vs `ElementInjector`
Dalam ekosistem Standalone, di mana `NgModuleInjector` tidak lagi menjadi poros utama, jelaskan resolusi dependency injection antara `EnvironmentInjector` dan `ElementInjector`! Apabila sebuah token disediakan pada:
* Root via `bootstrapApplication(..., { providers: [ provideFeatureToken() ] })`
* Route definition via `{ path: 'feature', providers: [ FeatureService ] }`
* Component decorator via `@Component({ providers: [ ComponentLocalService ] })`

Bagaimana urutan resolusi hierarkinya (*lookup chain*), dan apa yang terjadi jika `ComponentLocalService` menginjeksi token yang hanya didefinisikan pada route definition?

### Soal 2.3: Root Cause Analysis: Error `NG0203`
Seorang engineer melakukan refactoring logic asynchronous ke dalam sebuah utility function:
```typescript
export async function fetchUserData(userId: string) {
  const http = inject(HttpClient); // Baris ini melempar runtime error NG0203
  return await firstValueFrom(http.get(`/api/users/${userId}`));
}
```
1. Jelaskan secara mendalam mengapa error `NG0203: inject() must be called from an injection context` terjadi pada kode di atas saat fungsi dipanggil di dalam event listener atau lifecycle hook asynchronous.
2. Tunjukkan implementasi perbaikan menggunakan `runInInjectionContext` beserta instance `EnvironmentInjector`.

### Soal 2.4: Interoperabilitas Hybrid (NgModule <-> Standalone)
Arsitektur monolit perusahaan sedang dalam fase migrasi parsial. 
1. Bagaimana cara mengimpor dan menggunakan Standalone Component di dalam modul monolitik legacy yang dideklarasikan dengan `@NgModule`?
2. Sebaliknya, bagaimana cara mengimpor library legacy berbasis `NgModule` (misal: library UI pihak ketiga yang belum mendukung standalone) ke dalam Standalone Component baru?
3. Sebutkan aturan mutlak deklarasi (*declaration rules*) yang dilanggar jika sebuah Standalone Component dimasukkan ke dalam array `declarations: [...]` sebuah `NgModule`!

### Soal 2.5: Dynamic Component Instantiation Tanpa Resolver Legacy
Metode lama perenderan komponen dinamis bergantung pada `ComponentFactoryResolver` yang kini telah di-deprecate.
Tuliskan contoh kode idiomatis Angular modern untuk merender sebuah Standalone Component secara dinamis ke dalam sebuah `ViewContainerRef` menggunakan fungsi `createComponent()`. Jelaskan bagaimana Anda meneruskan *custom injector* atau environment injector ke dalam pemanggilan fungsi tersebut!

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Bundle Bloat Akibat "God SharedModule" Migrasi Parsial
* **Konteks:** Tim frontend enterprise memigrasikan aplikasi monolitik ke Standalone Components. Untuk mempercepat migrasi, tim memutuskan mengimpor `SharedModule` lama (yang berisi 120 komponen, puluhan directives, Angular Material, dan utilities) langsung ke dalam array `imports: [...]` pada setiap Standalone Component baru.
* **Gejala:** Hasil audit Webpack Bundle Analyzer menunjukkan ukuran bundle initial chunk melonjak 45%, dan metrik Core Web Vitals (Largest Contentful Paint & Total Blocking Time) memburuk secara drastis di jaringan 4G. Lazy-loaded chunks kini menduplikasi potongan vendor yang sama.
* **Pertanyaan Diagnostik & Solusi:**
  1. Mengapa mengimpor `SharedModule` legacy ke dalam Standalone Components merusak kapabilitas tree-shaking Ivy dan ESBuild?
  2. Rancang rencana mitigasi (*step-by-step refactoring plan*) untuk mengeliminasi `SharedModule` tanpa menghentikan delivery fitur tim lain!

### Skenario B: State Leakage & Token Collision pada Route-Level Providers
* **Konteks:** Aplikasi SaaS B2B memiliki modul lazy-loaded `/workspace/:workspaceId`. Setiap workspace memiliki state lokal yang diisolasi menggunakan service:
  ```typescript
  export const WORKSPACE_ROUTES: Route[] = [
    {
      path: '',
      providers: [WorkspaceStateService],
      component: WorkspaceShellComponent,
      children: [ ... ]
    }
  ];
  ```
  Di dalam `WorkspaceStateService`, tim menyimpan cache dokumen yang sedang diedit. Pengguna melaporkan bug integritas data fatal: ketika beralih dari Workspace A ke Workspace B melalui navigasi router internal, data formulir dari Workspace A terkadang muncul sesaat atau menimpa data di Workspace B.
* **Pertanyaan Diagnostik & Solusi:**
  1. Bagaimana lifecycle dari route-level `EnvironmentInjector` dieksekusi oleh router saat navigasi terjadi antar parameter rute yang sama (`:workspaceId`)?
  2. Mengapa instance `WorkspaceStateService` tidak di-destroy secara default saat navigasi terjadi jika komponennya di-reuse?
  3. Bagaimana arsitektur injeksi yang benar untuk menjamin bahwa service dihancurkan dan diinisialisasi ulang secara deterministik setiap kali ID workspace berubah?

### Skenario C: Migrasi Arsitektur Micro-Frontend Menuju Pure Standalone
* **Konteks:** Perusahaan Anda mengoperasikan arsitektur Micro-Frontend (MFE) menggunakan Module Federation. Host Shell dan Remote MFE saat ini saling berbagi `AppModule` dan context `NgModuleInjector`. Ada inisiatif arsitektur untuk memigrasikan Shell dan Remote ke Pure Standalone Application (Angular 17+).
* **Kendala Teknis:**
  * Remote MFE harus dapat dijalankan secara independen (*standalone mode*) saat local development, tetapi juga dapat di-*mount* ke dalam Host Shell sebagai route lazy-load dinamis.
  * Dependency singleton seperti `AuthService` dan `EventBusService` harus berasal dari Host jika dijalankan di dalam Shell, namun harus menggunakan *mock implementation* jika remote dijalankan mandiri.
* **Pertanyaan Diagnostik & Solusi:**
  1. Bagaimana konfigurasi bootstrapping route-level yang harus diimplementasikan pada remote MFE agar dapat di-expose langsung via Webpack/Rspack Module Federation tanpa memerlukan wrapper module?
  2. Bagaimana mendesain abstraksi Dependency Injection menggunakan `InjectionToken` dan dynamic routing provider agar Remote MFE dapat secara mulus beroperasi di kedua mode tanpa tabrakan injector?

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise Dynamic Widget Dashboard Shell

#### Deskripsi Masalah:
Platform analitik enterprise memerlukan sistem dashboard modular yang dapat dikonfigurasi oleh pengguna (*user-configurable widgets*). Setiap widget harus berupa Standalone Component terisolasi yang di-*lazy load* secara on-demand hanya ketika widget tersebut masuk ke dalam viewport layar (memanfaatkan integrasi native `@defer`). Sistem tidak boleh bergantung pada hardcoded component maps berskala besar atau `NgModule`.

#### Kebutuhan Fungsional & Teknis (Requirements):
1. **Dynamic Shell:** Bangun komponen `DashboardShellComponent` yang menerima konfigurasi JSON daftar widget (misal: widget grafik, widget tabel log, widget metrik status).
2. **Pure Standalone & Lazy Loading:**
   * Widget **wajib** berupa Standalone Component terpisah: `ChartWidgetComponent`, `MetricsWidgetComponent`, dan `AlertsWidgetComponent`.
   * Widget harus di-load secara dinamis via dynamic import (`import('./widgets/...')`).
3. **Viewport-Triggered Deferral:**
   * Gunakan blok `@defer (on viewport)` atau integrasi custom Intersection Observer dengan `ViewContainerRef` modern untuk memastikan kode JavaScript widget tidak diunduh sebelum posisinya mendekati layar pengguna.
4. **Isolated Injection Boundary:**
   * Setiap widget harus menerima konfigurasi instans uniknya (`WidgetConfigToken`) via custom `Injector` lokal tanpa mencemari Root Injector atau sibling widget lainnya.
5. **Modern Control Flow & Signals:**
   * Seluruh template dashboard wajib menggunakan Built-in Control Flow (`@if`, `@for` dengan tracking yang benar).
   * Status loading dan error handling rendering widget wajib ditangani secara native (misal via `@loading` dan `@placeholder` jika menggunakan `@defer`).

#### Batasan Arsitektural (Constraints):
* Dilarang menggunakan satupun `NgModule` (termasuk modul bawaan seperti `CommonModule`; gunakan impor langsung per-directive/pipe jika memang dibutuhkan).
* Dilarang menggunakan `ComponentFactoryResolver`.
* Seluruh deklarasi injection wajib menggunakan fungsi `inject()`.
* Strict TypeScript Mode aktif (`noImplicitAny: true`, `strictNullChecks: true`).

#### Output yang Diharapkan:
1. Kode lengkap `DashboardShellComponent` (TypeScript logic + Template inline/eksternal).
2. Contoh salah satu implementasi widget (`ChartWidgetComponent`) yang membuktikan isolasi injeksi konfigurasi.
3. Kode helper/service pembuat *runtime injector* untuk pembuatan komponen dinamis.

---

## 5. Knowledge Check & Checklist

Tandai checklist ini untuk mengevaluasi kesiapan konseptual dan praktis Anda sebelum melangkah ke Bab 02.

### Saya harus memahami:
- [ ] Mekanisme kompilasi Ivy dalam memproses array `imports: [...]` pada `@Component` tanpa memerlukan metadata konteks dari `NgModule`.
- [ ] Hubungan dan batasan arsitektural antara `EnvironmentInjector` (platform/root/routes) dan `ElementInjector` (DOM/komponen/directive).
- [ ] Definisi teknis dari *Injection Context*, kapan context tersebut dibuat, kapan dihancurkan, dan mekanisme internal fungsi `inject()`.
- [ ] Mengapa built-in control flow (`@if`, `@for`, `@switch`) secara struktural lebih unggul dalam tree-shaking dan runtime diffing dibandingkan structural directives (`*ngIf`, `*ngFor`).
- [ ] Aturan isolasi skop template: komponen yang diimpor oleh Standalone Component B tidak otomatis tersedia bagi Standalone Component A yang mengimpor B.
- [ ] Siklus hidup (*lifecycle*) pembersihan dependensi yang disediakan pada route-level provider saat navigasi dieksekusi.

### Saya tidak perlu menghafal:
- [ ] Seluruh kode internal error Angular (misalnya nomor error eksak `NG0203` atau `NG0201`), melainkan mengerti root cause dan cara membacanya dari stack trace compiler.
- [ ] Konfigurasi webpack internal tingkat rendah yang dijalankan oleh Angular CLI di balik layar saat memproses standalone trees.
- [ ] Nama-nama class internal compiler Ivy (seperti `R3Injector` atau `BloomFilter` implementation details), cukup memahami alur logis resolusi dependensinya.

### Saya harus bisa melakukan:
- [ ] Menginisialisasi aplikasi Angular murni dari nol menggunakan `bootstrapApplication` dan `provideX()` functions tanpa satupun deklarasi `NgModule`.
- [ ] Mengonversi komponen berbasis `NgModule` (termasuk yang terjebak dalam `SharedModule` raksasa) menjadi Standalone Component secara bertahap dan aman.
- [ ] Menggunakan fungsi `runInInjectionContext` untuk mengeksekusi asynchronous injection logic secara manual tanpa memicu crash runtime.
- [ ] Melakukan lazy-loading komponen individual secara dinamis menggunakan sintaks modern `ViewContainerRef.createComponent()` yang dikombinasikan dengan custom `Injector`.
- [ ] Memanfaatkan blok `@defer` beserta trigger-nya (`on viewport`, `on idle`, `when condition`) untuk mengoptimalkan performa loading halaman pada Standalone Components.