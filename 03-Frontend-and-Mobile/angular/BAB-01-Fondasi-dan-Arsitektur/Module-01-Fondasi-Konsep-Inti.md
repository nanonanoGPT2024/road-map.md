# Bab 01: Arsitektur Modern Angular & Standalone Ecosystem

## 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis** arsitektur runtime modern Angular (v17/v18+) yang berbasis *standalone components* dan membandingkannya dengan paradigma modular lawas (*NgModule*).
- **Mengimplementasikan** struktur aplikasi Angular berbasis *primitive reactivity* menggunakan Signals dan *control flow syntax* baru (`@if`, `@for`, `@switch`).
- **Mendiagnosis** proses *bootstrapping* platform tingkat rendah dari `main.ts` hingga inisialisasi *Component Tree* dan *Dependency Injection* (DI) Container.
- **Mengevaluasi** konsekuensi performa dari siklus *Change Detection* standar (*Zone.js*) versus paradigma reaktif *fine-grained* (*Signals*).

---

## 2. Introduction & Conceptual Background
Angular adalah platform pengembangan aplikasi web berbasis TypeScript yang dikembangkan oleh Google. Sejak kemunculannya sebagai perombakan total dari AngularJS pada tahun 2016, Angular berevolusi dari *framework* monolitik berbasis modul (*NgModule*) menjadi ekosistem berorientasi performa tinggi yang mengadopsi kompilator Ivy, *tree-shaking* agresif, dan integrasi *build system* berbasis esbuild/Vite.

Evolusi arsitektur modern Angular berfokus pada eliminasi *boilerplate* mental model modul, penyederhanaan reaktivitas melalui Signals, dan optimasi *Server-Side Rendering* (SSR) dengan *non-destructive hydration*. Modul ini berfokus pada fondasi arsitektur dasar: bagaimana Angular menyusun antarmuka, mengelola state lokal, dan menginstansiasi dependensi melalui struktur Standalone.

---

## 3. The "Why" (Motivasi & Masalah Riil)
Pada arsitektur Angular tradisional (< v14), setiap komponen, direktif, dan *pipe* wajib didaftarkan di dalam sebuah konteks kompilasi yang disebut `@NgModule`. Pola ini memicu masalah struktural pada skala *enterprise*:

1. **Cognitive Overhead & Indirection**: Pengembang harus mengelola `declarations`, `imports`, dan `exports` secara manual. Mengetahui dependensi spesifik dari suatu komponen memerlukan penelusuran hierarki modul yang rumit.
2. **Suboptimal Tree-Shaking**: Bundler kesulitan mengeliminasi kode mati (*dead code*) karena `@NgModule` mengelompokkan berbagai kapabilitas dalam satu *bundle chunk*, mengakibatkan ukuran unduhan awal (*initial payload*) membengkak.
3. **Traceability Error Kompilasi**: Kesalahan referensi komponen sering kali baru terdeteksi pada *runtime* atau melalui pesan kompilasi Angular Compiler (ngc) yang tidak intuitif.

Model *Standalone Components* mengeliminasi `@NgModule` sebagai perantara. Komponen kini menjadi unit isolasi mandiri yang secara eksplisit mendeklarasikan dependensi templatenya sendiri, menghasilkan arsitektur yang lebih mudah dipahami, modularitas yang ketat, dan ukuran *bundle* yang jauh lebih kecil.

---

## 4. The "What" (Definisi & Terminologi Kunci)

### Istilah Inti
- **Standalone Component**: Komponen Angular yang memiliki properti `standalone: true` (opsi *default* pada Angular v17+). Komponen ini mengimpor dependensi secara langsung melalui array `imports` miliknya.
- **ApplicationConfig**: Objek konfigurasi modular pengganti modul root (`AppModule`) untuk mendeklarasikan *providers*, *routing*, dan *platform features* saat proses *bootstrap*.
- **Ivy Compiler Engine**: Kompilator generasi baru Angular yang menghasilkan instruksi *runtime* internal berbasis LView (*Logical View*) dan TView (*Template View*).
- **Signals**: Primitif reaktivitas *fine-grained* yang membungkus nilai dan secara otomatis memberi tahu dependensi ketika nilai tersebut bermutasi.
- **Dependency Injection (DI) Hierarki**: Sistem penyediaan dependensi berlapis (*hierarchical injector tree*) yang mengelola *lifecycle* dan *scoping* dari *service*.

---

## 5. Architecture & Internal Mechanisms
Ketika sebuah aplikasi modern Angular dijalankan, alur eksekusi internal melewati fase-fase berikut:

1. **Platform Initialization (`main.ts`)**: Fungsi `bootstrapApplication()` dipanggil bersama komponen *root* dan objek `ApplicationConfig`.
2. **Injector Tree Generation**: Angular membangun hierarki *Environment Injector* (tingkat aplikasi) dan mengonfigurasi *providers* global seperti router dan HTTP interceptors.
3. **Template Compilation & LView Creation**: Kompilator Ivy menerjemahkan komponen menjadi struktur data:
   - **TView (Template View)**: Struktur statis yang menyimpan *blueprint*, metadata, dan *instruction bytecode* komponen (dibagikan ke seluruh *instance*).
   - **LView (Logical View)**: Struktur data dinamis berbentuk array yang menyimpan status riil dari *instance* komponen, nilai *bindings*, dan referensi DOM.
4. **Hydration / DOM Attachment**: Angular menautkan LView ke elemen host pada DOM fisik, menginisialisasi deteksi perubahan via *Zone.js* atau memetakan dependensi sinyal (*Signal consumer graph*).

---

## 6. ASCII Diagram

```
+-------------------------------------------------------------+
|                          main.ts                            |
|       bootstrapApplication(AppComponent, appConfig)         |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|               Root Environment Injector                     |
|  - provideRouter()                                          |
|  - provideHttpClient()                                      |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|                    AppComponent (Host)                      |
|  +-------------------------------------------------------+  |
|  | Template:                                             |  |
|  |   <header />                                          |  |
|  |   <app-user-profile [userId]="selectedId()" />        |  |
|  +---------------------------+---------------------------+  |
|                              |                              |
|                              v                              |
|     +-------------------------------------------------+     |
|     |       UserProfileComponent (Standalone)         |     |
|     |  - imports: [CommonModule, StatusBadgeComponent]|     |
|     |  - Injector: Element Injector (Scoped DI)       |     |
|     |  - State: Signal<UserData>                      |     |
|     +------------------------+------------------------+     |
|                              |                              |
|                              v                              |
|     +-------------------------------------------------+     |
|     |         StatusBadgeComponent (Child)            |     |
|     |  - Reads: computed(() => user.status())         |     |
|     +-------------------------------------------------+     |
+-------------------------------------------------------------+
```

---

## 7. The "How" (Panduan Implementasi Langkah demi Langkah)

### Langkah 1: Setup Proyek Standalone
Gunakan Angular CLI untuk membuat proyek modern tanpa modul warisan:
```bash
npx @angular/cli@latest new angular-core-architect --standalone --routing --style=scss --ssr=false
cd angular-core-architect
```

### Langkah 2: Mengonfigurasi `main.ts` dan `app.config.ts`
Struktur entri modern Angular memisahkan inisialisasi lingkungan dari deklarasi UI.

```typescript
// src/app/app.config.ts
import { ApplicationConfig, provideZoneChangeDetection } from '@angular/core';
import { provideRouter, withComponentInputBinding } from '@angular/router';
import { routes } from './app.routes';
import { provideHttpClient, withFetch } from '@angular/common/http';

export const appConfig: ApplicationConfig = {
  providers: [
    // Optimasi Zone.js event coalescing
    provideZoneChangeDetection({ eventCoalescing: true }),
    // Routing modern dengan binding parameter URL otomatis ke @Input()
    provideRouter(routes, withComponentInputBinding()),
    // HTTP Client dengan API Fetch modern
    provideHttpClient(withFetch())
  ]
};
```

```typescript
// src/main.ts
import { bootstrapApplication } from '@angular/platform-browser';
import { AppComponent } from './app/app.component';
import { appConfig } from './app/app.config';

bootstrapApplication(AppComponent, appConfig)
  .catch((err: unknown) => console.error('Bootstrap Exception:', err));
```

---

## 8. Simple Working Example
Berikut implementasi dasar komponen *standalone* menggunakan manipulasi state berbasis Signal dan *built-in control flow*.

```typescript
// src/app/counter.component.ts
import { Component, signal, computed, ChangeDetectionStrategy } from '@angular/core';

@Component({
  selector: 'app-counter',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="counter-box">
      <h2>Counter Module</h2>
      <p>Nilai Saat Ini: <strong>{{ count() }}</strong></p>
      <p>Klasifikasi: <span>{{ status() }}</span></p>

      <div class="actions">
        <button (click)="decrement()">-1</button>
        <button (click)="reset()">Reset</button>
        <button (click)="increment()">+1</button>
      </div>

      @if (count() >= 10) {
        <p class="warning-banner">Batas ambang sistem tercapai!</p>
      }
    </section>
  `,
  styles: [`
    .counter-box { border: 1px solid #ccc; padding: 1rem; border-radius: 8px; }
    .warning-banner { color: #d32f2f; font-weight: bold; }
    button { margin-right: 0.5rem; padding: 0.25rem 0.75rem; }
  `]
})
export class CounterComponent {
  // Primitif Reaktivitas
  readonly count = signal<number>(0);
  
  // Derivasi State Terkomputasi
  readonly status = computed<'Genap' | 'Ganjil'>(() => {
    return this.count() % 2 === 0 ? 'Genap' : 'Ganjil';
  });

  increment(): void {
    this.count.update((v) => v + 1);
  }

  decrement(): void {
    this.count.update((v) => v - 1);
  }

  reset(): void {
    this.count.set(0);
  }
}
```

---

## 9. Production-Grade Example
Implementasi penanganan operasi asinkron, *State Machine Pattern*, penghentian memori (*cancellation token pattern* via `DestroyRef`), serta injeksi dependensi via fungsi `inject()`.

### Definisi Model & Service
```typescript
// src/app/core/user.service.ts
import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, catchError, throwError } from 'rxjs';

export interface User {
  id: number;
  name: string;
  email: string;
  role: 'Admin' | 'Member' | 'Guest';
}

@Injectable({
  providedIn: 'root'
})
export class UserService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = 'https://jsonplaceholder.typicode.com/users';

  getUsers(): Observable<User[]> {
    return this.http.get<User[]>(this.apiUrl).pipe(
      catchError((error: unknown) => {
        return throwError(() => new Error(`Gagal memuat pengguna: ${JSON.stringify(error)}`));
      })
    );
  }
}
```

### Komponen Pengelola State Terisolasi
```typescript
// src/app/features/user-list/user-list.component.ts
import { 
  Component, 
  OnInit, 
  inject, 
  signal, 
  computed, 
  DestroyRef, 
  ChangeDetectionStrategy 
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { UserService, User } from '../../core/user.service';
import { FormsModule } from '@angular/forms';

type LoadingState = 'IDLE' | 'LOADING' | 'SUCCESS' | 'ERROR';

@Component({
  selector: 'app-user-list',
  standalone: true,
  imports: [FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="user-manager">
      <header>
        <h3>Manajemen Pengguna Terdaftar</h3>
        <input 
          type="text" 
          placeholder="Cari berdasarkan nama..."
          [ngModel]="searchQuery()"
          (ngModelChange)="searchQuery.set($event)"
        />
      </header>

      @switch (state()) {
        @case ('LOADING') {
          <div class="skeleton-loader">Memuat data dari server...</div>
        }
        @case ('ERROR') {
          <div class="error-panel">
            <p>{{ errorMessage() }}</p>
            <button (click)="fetchData()">Coba Lagi</button>
          </div>
        }
        @case ('SUCCESS') {
          <table class="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Nama</th>
                <th>Email</th>
              </tr>
            </thead>
            <tbody>
              @for (user of filteredUsers(); track user.id) {
                <tr>
                  <td>{{ user.id }}</td>
                  <td>{{ user.name }}</td>
                  <td>{{ user.email }}</td>
                </tr>
              } @empty {
                <tr>
                  <td colspan="3">Tidak ada data pengguna yang cocok.</td>
                </tr>
              }
            </tbody>
          </table>
        }
      }
    </div>
  `,
  styles: [`
    .user-manager { max-width: 800px; margin: auto; font-family: sans-serif; }
    .data-table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
    .data-table th, .data-table td { border: 1px solid #ddd; padding: 8px; text-align: left; }
    .data-table th { background-color: #f4f4f4; }
    .error-panel { padding: 1rem; background-color: #ffebee; border: 1px solid #ef5350; }
  `]
})
export class UserListComponent implements OnInit {
  private readonly userService = inject(UserService);
  private readonly destroyRef = inject(DestroyRef);

  // States
  readonly users = signal<User[]>([]);
  readonly searchQuery = signal<string>('');
  readonly state = signal<LoadingState>('IDLE');
  readonly errorMessage = signal<string | null>(null);

  // Computed State (Filtering Engine)
  readonly filteredUsers = computed(() => {
    const query = this.searchQuery().toLowerCase().trim();
    if (!query) return this.users();
    return this.users().filter(u => u.name.toLowerCase().includes(query));
  });

  ngOnInit(): void {
    this.fetchData();
  }

  fetchData(): void {
    this.state.set('LOADING');
    this.errorMessage.set(null);

    this.userService.getUsers()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (data) => {
          this.users.set(data);
          this.state.set('SUCCESS');
        },
        error: (err: Error) => {
          this.errorMessage.set(err.message);
          this.state.set('ERROR');
        }
      });
  }
}
```

---

## 10. Deep-Dive Edge Cases & Failure Modes

### 1. `NG0100: ExpressionChangedAfterItHasBeenCheckedError`
- **Skenario Root Cause**: Terjadi ketika *parent component* membaca properti dari *child component* yang dimutasi dalam *lifecycle hook* `ngAfterViewInit()`. Dalam mode *development*, Angular menjalankan fase *Change Detection* kedua untuk memverifikasi kestabilan data bindings. Jika nilai berubah antara fase render dan fase verifikasi, eksepsi dilempar.
- **Solusi**: Alihkan mutasi state ke microtask queue menggunakan `Promise.resolve()`, gunakan Signals (yang menjamin *unidirectional reactive updates* tanpa manipulasi DOM manual), atau lakukan update pada siklus `ngOnInit`.

### 2. Signal Cyclic Dependency (Infinite Loops)
```typescript
// Skenario Bahaya:
const a = signal(1);
const b = computed(() => a() + 1);
effect(() => {
  if (b() > 2) {
    a.set(10); // Run-time exception: NG0600: Writing to signals is not allowed inside computed/effects by default.
  }
});
```
- **Solusi**: Jangan memodifikasi Sinyal lain di dalam `computed()` atau `effect()`. Pisahkan efek samping (*side effects*) ke dalam event handlers deterministik. Hindari pengaktifan opsi `{ allowSignalWrites: true }` kecuali pada skenario transisi state yang benar-benar terisolasi.

### 3. Circular Dependency pada Hierarchical Injector
Terjadi ketika Service A menyuntikkan Service B via konstruktor, dan Service B juga menyuntikkan Service A. Angular akan melempar `NG0200: Circular dependency detected`.
- **Solusi**: Lakukan refaktorisasi *shared logic* ke Service C baru, atau gunakan lazy resolution menggunakan API `Injector`:
```typescript
private readonly injector = inject(Injector);
get serviceB() {
  return this.injector.get(ServiceB);
}
```

---

## 11. Performance Considerations & Optimization

1. **Penggunaan Wajib `ChangeDetectionStrategy.OnPush`**: Secara default, Angular memeriksa seluruh komponen pada pohon DOM ketika ada event browser. Dengan `OnPush`, Angular hanya memeriksa komponen jika:
   - Sinyal yang dibaca dalam template berubah.
   - Properti `@Input()` menerima referensi memori baru (`Object.is()` check).
   - Event emitter dari template komponen tersebut dipicu.
2. **Kinerja Loop `@for` dengan `track`**:
   Sintaks `@for (item of items; track item.id)` bersifat wajib (non-opsional). Tanpa identifikasi unik, mutasi array sekecil apa pun akan menghancurkan dan merender ulang seluruh node DOM terkait, merusak efisiensi DOM recycling.
3. **Tree-Shaking Standalone Packages**: Hindari mengekspor komponen utilitas secara kolektif dari *barrel files* (`index.ts`) besar jika tidak dikonfigurasi dengan `sideEffects: false` pada `package.json`, karena dapat merusak optimasi dead-code elimination Webpack/esbuild.

---

## 12. Security Implications
1. **Cross-Site Scripting (XSS) & Sanitization**:
   Angular menganggap semua nilai input secara *default* tidak terpercaya. Interpolasi `{{ content }}` secara otomatis membersihkan kode HTML berbahaya.
   *Vulnerability Vector*: Penggunaan manipulasi `ElementRef.nativeElement.innerHTML` langsung atau penyalahgunaan `DomSanitizer.bypassSecurityTrustHtml()`.
   ```typescript
   // Bahaya:
   this.elementRef.nativeElement.innerHTML = untrustedUserData; // Membuka celah XSS
   
   // Benar:
   // Gunakan sanitasi bawaan Angular pada template binding:
   // <div [innerHTML]="sanitizedContent"></div>
   ```
2. **Strict Template Type Checking**:
   Aktifkan konfigurasi `strictTemplates: true` pada `tsconfig.json`. Ini mencegah *property injection* ilegal dan memastikan ekspresi tipe divalidasi saat kompilasi sebelum kode sampai di tahap eksekusi.

---

## 13. Testing Strategies
Pengujian unit untuk komponen *standalone* dilakukan menggunakan `TestBed` tanpa mendeklarasikan `@NgModule` perantara.

```typescript
// src/app/counter.component.spec.ts
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { CounterComponent } from './counter.component';

describe('CounterComponent (Standalone Unit Test)', () => {
  let component: CounterComponent;
  let fixture: ComponentFixture<CounterComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CounterComponent] // Standalone diimpor langsung ke test bed
    }).compileComponents();

    fixture = TestBed.createComponent(CounterComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('harus menginisialisasi nilai awal count dengan 0', () => {
    expect(component.count()).toBe(0);
    expect(component.status()).toBe('Genap');
  });

  it('harus menaikkan counter dan mengubah status komputasi ketika fungsi increment dipanggil', () => {
    component.increment();
    fixture.detectChanges(); // Evaluasi template

    expect(component.count()).toBe(1);
    expect(component.status()).toBe('Ganjil');

    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('strong')?.textContent).toBe('1');
  });

  it('harus menampilkan pesan warning ketika count mencapai nilai >= 10', () => {
    component.count.set(10);
    fixture.detectChanges();

    const compiled = fixture.nativeElement as HTMLElement;
    const warning = compiled.querySelector('.warning-banner');
    expect(warning).not.toBeNull();
    expect(warning?.textContent).toContain('Batas ambang sistem tercapai!');
  });
});
```

---

## 14. Alternative Approaches & Trade-offs

| Parameter Arsitektur | Standalone Components (Modern) | NgModules (Legacy Approach) |
| :--- | :--- | :--- |
| **Keterbacaan Kode** | Eksplisit per komponen (`imports: [...]`) | Implisit; dependensi tersebar di modul deklarator |
| **Ukuran Bundel** | Optimal (Tree-shakeable granular) | Rentan mengikutsertakan modul non-esensial |
| **Lazy Loading Strategy** | `loadComponent: () => import(...)` | `loadChildren: () => import(...).then(m => m.Module)` |
| **Learning Curve** | Rendah (Menyerupai React/Vue/Svelte) | Tinggi (Harus paham konfigurasi metadata modular) |
| **Kompatibilitas** | Angular v14+ (Standar utama sejak v17) | Angular v2 hingga v16 (Mode pemeliharaan) |

---

## 15. Real-World Case Studies / Industry Scenarios
Sebuah platform perbankan digital skala enterprise memigrasikan sistem back-office mereka dari Angular v12 berbasis *monolithic SharedModule* ke Angular v18 Standalone.

- **Kondisi Awal**: Waktu *build production* memakan waktu 14 menit. Setiap kali modul kecil dimodifikasi, *SharedModule* yang berisi ratusan komponen memaksa bundler untuk mengompilasi ulang hampir seluruh aplikasi. File bundle vendor berukuran 9.2 MB.
- **Implementasi Migrasi**:
  1. Menjalankan *automated migration schematics*: `ng g @angular/core:standalone`.
  2. Memecah `SharedModule` menjadi *individual standalone directives* dan *pipes*.
  3. Memperbarui router agar memuat rute secara langsung via `loadComponent`.
- **Hasil**: Ukuran initial chunk turun 42% (menjadi 5.3 MB), waktu build esbuild terpangkas menjadi 1.2 menit, dan *First Contentful Paint* (FCP) sistem meningkat dari 3.8 detik menjadi 1.4 detik pada koneksi jaringan terbatas.

---

## 16. Best Practices & Do's/Don'ts Checklist

- [x] **DO**: Gunakan `inject(ServiceName)` alih-alih *constructor injection* tradisional untuk deklarasi dependensi yang lebih ringkas dan fleksibel pada *factory functions*.
- [x] **DO**: Selalu aktifkan `ChangeDetectionStrategy.OnPush` pada seluruh komponen baru.
- [x] **DO**: Tentukan `track` function secara unik dan deterministik pada setiap iterasi `@for`.
- [x] **DO**: Gunakan `takeUntilDestroyed()` untuk auto-cleanup subscription RxJS tanpa mengelola objek `Subject` atau memanggil manual `unsubscribe` di `ngOnDestroy`.
- [ ] **DON'T**: Jangan mengimpor `CommonModule` secara keseluruhan jika Anda hanya butuh subset kecil; manfaatkan sintaks *built-in control flow* (`@if`, `@for`) yang tidak membutuhkan impor modul apa pun.
- [ ] **DON'T**: Jangan memodifikasi status DOM secara imperatif melalui objek `ElementRef.nativeElement`; gunakan *declarative data binding* atau Angular Animation API.
- [ ] **DON'T**: Jangan membuat sinyal lokal untuk state yang sepenuhnya dapat dikalkulasi; gunakan `computed()` guna menghindari inkonsistensi sinkronisasi data.

---

## 17. Tooling & Ecosystem Integration
- **Kompilasi & Build**: Integrasi **esbuild** + **Vite** secara default di Angular CLI (`@angular-devkit/build-angular:application`). Menyediakan *Instant Hot Module Replacement* (HMR).
- **Inspeksi Runtime**: **Angular DevTools** (Ekstensi Chrome/Firefox). Digunakan untuk melacak pohon komponen, menganalisis *profiler cycle* deteksi perubahan, dan menginspeksi graph Sinyal.
- **Linting**: `@angular-eslint/schematics` untuk menegakkan aturan komponen standalone, pelarangan *lifecycle hook* yang salah, serta pencegahan mutasi state di luar aturan Zone/Signals.

---

## 18. Troubleshooting Guide

### Issue 1: Komponen Tidak Mengenali Directive Standard
- **Pesan Kesalahan**: `NG8002: Can't bind to 'ngModel' since it isn't a known property of 'input'`.
- **Penyebab**: Komponen *standalone* tidak mewarisi modul konteks secara global.
- **Solusi**: Tambahkan `FormsModule` secara eksplisit ke dalam array `imports` pada metadata komponen target:
  ```typescript
  @Component({
    standalone: true,
    imports: [FormsModule], // Tambahkan ini
    ...
  })
  ```

### Issue 2: Service Provider Bernilai `Null` atau Not Found
- **Pesan Kesalahan**: `NG0204: Can't resolve all parameters for MyService: (?)`.
- **Penyebab**: Service tidak memiliki decorator `@Injectable()` atau tidak disediakan di level root maupun element injector.
- **Solusi**: Pastikan service didekorasi dengan:
  ```typescript
  @Injectable({ providedIn: 'root' })
  export class MyService {}
  ```

---

## 19. Exercises & Hands-on Challenges

### Tingkat Dasar
Buat sebuah standalone component bernama `UserProfileToggleComponent`. Komponen ini harus:
1. Memiliki state Signal boolean `isExpanded` (nilai awal `false`).
2. Menampilkan tombol yang membalikkan nilai `isExpanded` saat diklik.
3. Menampilkan paragraf deskripsi profil hanya jika `isExpanded` bernilai `true` menggunakan kontrol alur `@if`.

### Tingkat Menengah
Kembangkan sebuah `SearchFilterComponent` yang:
1. Menerima list data string via Signal input (`input<string[]>()`).
2. Memiliki form input teks yang terhubung ke Signal lokal `query`.
3. Menggunakan fungsi `computed()` untuk memfilter data string secara real-time berdasarkan teks pencarian tanpa manipulasi array mutatif.

### Tingkat Lanjut (Skenario Produksi)
Bangun arsitektur mini dashboard yang memuat data analitik secara konkuren dari dua API asinkron berbeda:
1. Buat Service `MetricsService` yang mengembalikan Observable metrik server dan data logs.
2. Konsumsi data tersebut di dalam standalone component tanpa *memory leak* menggunakan `toSignal()` atau integrasi `DestroyRef` + `takeUntilDestroyed`.
3. Komponen harus mampu menampilkan status skeleton loading terintegrasi, visualisasi error state jika salah satu API gagal, dan mekanisme tombol *retry* tanpa me-reload browser.

---

## 20. Summary & Next Steps
Pada modul ini, Anda telah menguasai:
- Transisi arsitektur modern Angular menuju ekosistem terpadu **Standalone Components**.
- Mekanisme internal eksekusi aplikasi via `bootstrapApplication()` dan pembentukan struktur *LView/TView* oleh Ivy Engine.
- Fondasi manipulasi data reaktif berbasis **Signals** (`signal`, `computed`) dan penggunaan *built-in control flow* modern (`@if`, `@for`).

**Langkah Selanjutnya**:
Pada **Bab 01 Module 02**, kita akan mendalami secara komprehensif sistem reaktivitas: *Deep Dive into Angular Signals, Effects, & RxJS Interoperability (`toSignal`, `toObservable`)* guna membangun pipeline data yang kompleks dan deterministik.