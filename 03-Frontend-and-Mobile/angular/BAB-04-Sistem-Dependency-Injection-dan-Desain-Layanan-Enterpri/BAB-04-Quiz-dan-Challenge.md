# BAB 04: Quiz, Challenge, & Knowledge Check
**Sistem Dependency Injection (DI) & Desain Layanan Enterprise**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Topologi Hierarki DI (ElementInjector vs. EnvironmentInjector):**  
   Jelaskan perbedaan struktural, siklus hidup (*lifecycle*), dan algoritma resolusi pencarian token antara `ElementInjector` dan `EnvironmentInjector` (termasuk evolusinya dari `ModuleInjector`) pada Angular modern (v14+ Standalone API). Bagaimana Angular menentukan jalur delegasi ketika sebuah token tidak ditemukan pada level node DOM komponen saat ini?

2. **Perilaku Resolusi Modifiers (`@Self`, `@SkipSelf`, `@Host`, `@Optional`):**  
   Bandingkan batasan pencarian injeksi token saat menggunakan kombinasi `@Host() @Optional()` versus `@SkipSelf() @Self()` (jika sintaksis tersebut valid secara runtime/kompilasi). Apa definisi spesifik dari batasan "Host" dalam konteks View Encapsulation, `ng-template`, dan *projected content* (`<ng-content>`)?

3. **Mekanika `inject()` Function vs Constructor Injection:**  
   Fungsi `inject()` beroperasi berdasarkan *synchronous Injection Context*. Jelaskan secara teknis mengapa pemanggilan `inject()` di dalam *asynchronous callback* (misalnya di dalam blok `.then()` atau `setTimeout`) akan melempar error `NG0203: inject() must be called from an injection context`. Bagaimana cara kerja internal stack frame Angular dalam mencatat active injector untuk mendukung `inject()`?

4. **Semantik Provider Token: `useClass` vs `useExisting`:**  
   Diberikan dua deklarasi provider:  
   `{ provide: LoggerService, useClass: CustomLoggerService }`  
   dan  
   `{ provide: LoggerService, useExisting: CustomLoggerService }`.  
   Jelaskan perbedaan mendasar kedua deklarasi tersebut terhadap instansiasi objek, alokasi memori, dan integritas *singleton pattern* jika `CustomLoggerService` juga didaftarkan sebagai provider di injector yang sama atau injector induk.

5. **Dampak Pohon Kompilasi `providedIn: 'root'` vs Component-Level `providers: []`:**  
   Mengapa mendaftarkan service melalui metadata komponen (`@Component({ providers: [...] })`) secara inheren mematikan optimasi *tree-shaking* bundler untuk service tersebut, sedangkan `providedIn: 'root'` atau `providedIn: null` dengan fungsi `provideX()` berbasis Functional API mampu memfasilitasi dead-code elimination secara optimal?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Resolusi Multi-Provider (`multi: true`) & Execution Order:**  
   Ketika beberapa library atau modul enterprise mendaftarkan token yang sama menggunakan `{ provide: HTTP_INTERCEPTORS, useClass: InterceptorX, multi: true }` pada berbagai level hierarki (root, feature environment, dan child routing), bagaimana urutan eksekusi array ditentukan oleh Angular? Apa konsekuensinya jika salah satu provider perantara tidak mendeklarasikan flag `multi: true`?

2. **Dilema Circular Dependency & Runtime Instantiation (`forwardRef`):**  
   Secara arsitektural, penggunaan `forwardRef(() => TargetService)` menandakan adanya *code smell*. Bedah bagaimana JavaScript runtime engine mengevaluasi circular dependency injection sebelum metadata class diinisialisasi, dan berikan strategi dekomposisi antarmuka (misalnya melalui *Abstract Class Tokens* atau *Mediator Pattern*) untuk mengeliminasi circular reference secara total tanpa `forwardRef`.

3. **Injeksi Dinamis Berbasis Runtime via `runInInjectionContext`:**  
   Analisis use-case di mana Anda perlu mengeksekusi logika yang membutuhkan token DI di luar *constructor phase* (misalnya di dalam event handler web worker, custom RxJS operator, atau dynamic plugin loader). Bagaimana implementasi `runInInjectionContext(injector, fn)` bekerja di bawah kap mesin untuk memanipulasi pointer `currentInjector` internal Angular secara thread-safe (single-threaded event loop context)?

4. **Memory Leak Induced by Scoped Providers & Unsubscription Retention:**  
   Sebuah *heavy stateful service* didaftarkan pada tingkat komponen yang sering di-render ulang secara dinamis via `*ngIf`. Komponen tersebut menginjeksi service tersebut, dan service tersebut berlangganan (`subscribe`) ke singleton Observable yang hidup di root (`providedIn: 'root'`). Mengapa instance service dan komponen penampungnya gagal di-*garbage collect* meskipun komponen telah di-destroy dari DOM? Rancang siklus hidup pembersihan memori menggunakan `DestroyRef`.

5. **Multi-Platform & Environment Abstraction via `InjectionToken<T>` Factory:**  
   Buat evaluasi teknis implementasi custom `InjectionToken` dengan factory:
   ```typescript
   export const API_ENDPOINT = new InjectionToken<string>('API_ENDPOINT', {
     providedIn: 'root',
     factory: () => {
       const platformId = inject(PLATFORM_ID);
       const config = inject(APP_CONFIG, { optional: true });
       return isPlatformBrowser(platformId) ? config?.browserUrl ?? '/api' : config?.ssrUrl ?? 'http://internal-svc:8080';
     }
   });
   ```
   Apa keuntungan pendekatan ini dibanding mengonfigurasi provider melalui `AppModule` atau `ApplicationConfig` tradisional? Bagaimana perilakunya terhadap mocking pada automated integration tests?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Kebocoran State Antar-Tenant pada Portal SaaS Finansial
*Konteks:*  
Aplikasi Core Banking enterprise menggunakan arsitektur micro-frontend dinamis. Terdapat `TenantContextService` yang menyimpan metadata sensitif per sesi organisasi (ID Organisasi, token otentikasi, encryption keys). Service ini awalnya didesain sebagai:
```typescript
@Injectable({ providedIn: 'root' })
export class TenantContextService {
  private activeTenantState = signal<TenantMetadata | null>(null);
  // ... setter & getter
}
```
Ketika pengguna melakukan *switch tenant* melalui menu navigasi tanpa reload halaman penuh, atau membuka tab transaksi terisolasi via dynamic routing, data transaksi dari Tenant A secara acak bocor dan tereksekusi pada akun Tenant B. Audit menunjukkan bahwa beberapa sub-router fitur menggunakan modul lazy-loaded yang menduplikasi instantiation, sementara yang lain menggunakan instance stale dari root injector.

*Pertanyaan Diagnostik:*
1. Mengapa desain `providedIn: 'root'` sangat berbahaya untuk arsitektur multi-tenant dengan per-route / per-workspace lifecycle?
2. Bagaimana Anda mendesain ulang hierarki injector menggunakan `EnvironmentInjector` kustom atau scoped route providers (`Route.providers`) untuk menjamin isolasi mutlak antar-tenant tanpa memory leak?
3. Rancang guard/interceptor berbasis DI untuk memvalidasi bahwa setiap HTTP outbound request membawa token yang diekstrak strictly dari injector yang tepat sesuai konteks rute aktif.

---

### Skenario B: Race Condition dan State Desynchronization pada Nested Enterprise Form Facade
*Konteks:*  
Sebuah sistem asuransi kompleks memiliki form deklarasi bertingkat dengan kedalaman 4 level (Polis -> Tertanggung Utama -> Tertanggung Tambahan -> Manfaat Tambahan). Setiap level merupakan komponen mandiri yang di-load secara dinamis. Arsitek tim mengimplementasikan *Component-Level State Facade*:
```typescript
@Component({
  selector: 'app-beneficiary-level',
  providers: [ClaimStateFacade] // Di-provide ulang di setiap level komponen
})
export class BeneficiaryLevelComponent {
  constructor(private facade: ClaimStateFacade) {}
}
```
*Problem:*  
Ketika form di-submit dari tombol utama di Root Level, terjadi inkonsistensi data parah: 40% payload form kehilangan data level terbawah (*undefined/stale*), dan validasi cross-field antar-level gagal mendeteksi state error secara realtime.

*Pertanyaan Diagnostik:*
1. Bedah bagaimana `ElementInjector` mengisolasi instance `ClaimStateFacade` pada masing-masing level komponen sehingga menyulitkan sinkronisasi ke atas (*bottom-up propagation*).
2. Bagaimana Anda mengatasi limitasi ini menggunakan teknik *hierarchical DI traversal* (misalnya penggunaan decorator `@SkipSelf()`, structural tree tokens, atau hierarchical state composition) tanpa memindahkan instance facade ke root singleton yang melanggar enkapsulasi komponen?
3. Tunjukkan implementasi konkret bagaimana sub-komponen dapat mereferensikan instance facade milik induk terdekatnya secara dinamis sekaligus mendaftarkan state lokalnya ke dalam aggregate root.

---

### Skenario C: Migrasi Monolit Legacy ke Standalone Plugin Architecture
*Konteks:*  
Aplikasi ERP enterprise lama memiliki 50+ modul lazy-loaded yang sangat bergantung pada module-level singleton providers (`forFeature()` pattern). Perusahaan memutuskan untuk memigrasikan arsitektur secara bertahap ke *Strict Standalone Components* menggunakan `loadChildren` dengan route configuration. Selama migrasi parsial, ditemukan bahwa service tertentu dieksekusi dua kali (terjadi duplikasi instance singleton per rute), dan beberapa third-party token library melempar runtime error `NullInjectorError: No provider for FeatureConfigToken!`.

*Pertanyaan Diagnostik:*
1. Identifikasi akar penyebab terjadinya duplikasi instansiasi service saat rute berpindah dari `NgModule` lazy loading ke standalone route `providers: [...]`.
2. Jelaskan bagaimana Anda merekayasa abstraksi `EnvironmentProviders` (menggunakan `makeEnvironmentProviders`) untuk mencegah developer junior meregistrasikan provider berbasis modul ke dalam `ElementInjector` komponen standalone.
3. Rancang arsitektur extensibility berbasis plugin di mana modul eksternal dapat mendaftarkan implementasi fiturnya via injection token dinamis, tanpa mengubah kode inti aplikasi (*Open/Closed Principle*).

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise Auditable Event-Bus & Dynamic Pipeline Injector

#### Problem Statement
Pada sistem Core Processing enterprise, setiap mutasi transaksi keuangan harus melewati serangkaian rantai interceptor/middleware dinamis (Audit Trail, Deduplication, Data Masking, dan Cryptographic Signing) sebelum dikirim ke engine backend. Urutan, jenis, dan konfigurasi middleware ini bervariasi bergantung pada unit bisnis (*Business Unit*) yang memuat transaksi tersebut di antarmuka frontend. Anda diminta membangun engine eksekusi berbasis Dependency Injection murni yang modular, *type-safe*, decoupled, dan dapat diuji secara isolatif.

#### Requirements
1. **Dynamic Pipeline Injection Tokens:**
   - Definisikan `InjectionToken<TransactionPipelineStep>` bertipe `multi: true` bernama `PIPELINE_STEPS`.
   - Setiap pipeline step harus mengimplementasikan interface `TransactionPipelineStep`:
     ```typescript
     export interface TransactionPipelineStep {
       readonly name: string;
       readonly priority: number; // Urutan eksekusi: semakin rendah semakin awal
       process(payload: TransactionPayload, next: () => Promise<TransactionResult>): Promise<TransactionResult>;
     }
     ```
2. **Context-Aware Scoped Injector Engine:**
   - Bangun sebuah service `TransactionEngineService` yang bertindak sebagai orchestrator pipeline.
   - Engine harus mampu mengeksekusi pipeline berdasarkan hierarki injector: mengambil global steps dari root context, menggabungkannya dengan tenant/scoped steps dari active `EnvironmentInjector`, dan mengeksekusinya secara berurutan sesuai `priority`.
3. **Dynamic Child Injector Creation:**
   - Sediakan fungsi factory atau service method yang menggunakan `createEnvironmentInjector()` secara programmatic untuk membuat isolated injection context on-the-fly ketika sebuah workflow transaksi dibuka di dalam modal/dialog terisolasi.
4. **Lifecycle & Cleanup Contract:**
   - Injector dinamis yang dibuat harus dibersihkan (`destroy()`) secara eksplisit ketika modal ditutup untuk mencegah *detached DOM/memory retention leak*.
   - Pasang tracking via `DestroyRef` untuk memastikan tidak ada memory leak dari token instances.

#### Constraints
- Dilarang keras menggunakan array mutasi global atau dependency injection berbasis string primitives (`useValue: 'my-token'`). Wajib menggunakan typed `InjectionToken`.
- Eksekusi middleware pipeline harus mengadopsi mekanisme *Onion Architecture* (mirip Koa / modern Angular HTTP Interceptors chaining) via promise resolution / async-await.
- Wajib menggunakan standalone API murni (tanpa referensi ke `NgModule`).
- Harus menyertakan mekanisme error recovery: jika salah satu middleware step gagal (throw error), engine harus mengeksekusi rollback hook pada step yang telah berhasil dieksekusi sebelumnya.

#### Expected Output
1. File struktur token & interface: `pipeline.tokens.ts`.
2. Implementasi minimal 2 pipeline step konkret (misal: `AuditStep` & `CryptoSigningStep`).
3. Core Orchestrator: `TransactionEngineService` yang menyelesaikan dependency via `inject(PIPELINE_STEPS, { optional: true })` dan menyusun execution chain.
4. Programmatic Scoped Injector Factory: fungsi/komponen yang mendemonstrasikan instansiasi dynamic child injector menggunakan `createEnvironmentInjector`, eksekusi workflow, dan eksekusi `.destroy()`.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur internal dual-tree injection: bagaimana `ElementInjector` (komponen, direktif) dan `EnvironmentInjector` (root, platform, routes) hidup berdampingan dan berinteraksi.
- [ ] Algoritma resolusi Angular DI: dari node yang meminta token hingga `NullInjector` / `PLATFORM_INITIALIZER`.
- [ ] Aturan ketat *Injection Context*: kapan konteks injeksi tersedia (constructor, property initializer, factory function) dan kapan konteks hilang.
- [ ] Mekanisme kerja Provider Recipes: `useClass`, `useExisting`, `useValue`, `useFactory` beserta implikasi memory allocation dan bundle size-nya.
- [ ] Signifikansi arsitektur Standalone: peran `EnvironmentProviders`, fungsi `makeEnvironmentProviders()`, dan migrasi dari `forRoot()` / `forChild()` patterns.
- [ ] Fungsi dan implikasi arsitektur dari resolution modifiers: `@Self()`, `@SkipSelf()`, `@Host()`, `@Optional()`.

### Saya tidak perlu menghafal:
- [ ] Kode internal hash table/bloom filter yang digunakan compiler Angular untuk mengoptimalkan lookup token di level binary template instruction.
- [ ] Seluruh nomor error code internal Angular DI (misal: `NG0200`, `NG0203`, `NG0204`) di luar kepala; fokus pada interpretasi deskripsi error dan stack trace-nya.
- [ ] Signature private API internal compiler seperti `ɵɵdefineInjectable` atau `ɵɵdirectiveInject`.

### Saya harus bisa melakukan:
- [ ] Melakukan debugging dan menyelesaikan error klasik DI: `NullInjectorError`, `Circular dependency detected`, dan `NG0203: inject() must be called from an injection context`.
- [ ] Merancang custom dynamic injector programmatic menggunakan `createEnvironmentInjector` untuk skenario micro-frontends, dynamic popups, atau worker contexts.
- [ ] Mengonstruksi arsitektur *Facade Pattern* tingkat enterprise yang memadukan Signal state, resolution modifiers (`@SkipSelf`), dan isolasi hierarkis antar-fitur.
- [ ] Mengonversi modul enterprise lama berbasis `ModuleWithProviders` menjadi functional provider pattern modern yang *tree-shakable* dan mendukung SSR safe-execution.
- [ ] Mencegah dan mengaudit memory leaks yang bersumber dari retainment object graph DI menggunakan Chrome DevTools Heap Snapshot dan `DestroyRef`.