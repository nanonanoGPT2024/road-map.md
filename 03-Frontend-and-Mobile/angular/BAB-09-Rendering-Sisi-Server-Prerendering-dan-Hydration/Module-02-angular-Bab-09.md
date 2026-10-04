# Kurikulum Enterprise Angular: Modul 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 09: Rendering Sisi Server (SSR), Prerendering, dan Hydration**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Principal Engineer/Architect diharapkan mampu:
- Menguasai arsitektur internal *Non-Destructive Hydration Engine*, *Event Replay Engine* (JSAction), dan rekonsiliasi struktur DOM (`LView`/`TView`) antara server dan klien.
- Mengeliminasi fenomena *double data fetching* dengan mengimplementasikan pola arsitektur `TransferState` berbasis Signal dan HTTP Interceptor.
- Merancang dan mengeksekusi strategi *Hybrid Rendering* (kombinasi SSG, Dynamic SSR, Incremental Hydration via Deferrable Views, dan Client-Only boundaries) pada aplikasi skala enterprise multi-wilayah.
- Menjamin stabilitas *runtime* SSR pada level infrastruktur Node.js/Edge: mencegah kebocoran memori (*memory leaks*), mengisolasi konteks *per-request*, serta mengabstraksi manipulasi DOM secara aman menggunakan `DOCUMENT` dan `Renderer2`.
- Mengimplementasikan sistem *caching tiering* berlapis (Reverse Proxy CDN, Redis-backed dynamic SSR, dan Stale-While-Revalidate HTTP cache headers).

---

## 2. Prerequisite

Peserta pelatihan wajib memiliki pemahaman mendalam tentang:
- Arsitektur Angular Standalone Components, Dependency Injection Token, dan Reactive Primitives (Signals, Computed, Effects).
- Dasar-dasar SSR: Siklus hidup HTTP Request-Response, Node.js Event Loop, dan DOM API vs Node.js runtime globals.
- Penggunaan RxJS lanjutan (konsep leak via unmanaged long-lived subscriptions).
- Konsep dasar Web Vitals: LCP (*Largest Contentful Paint*), INP (*Interaction to Next Paint*), dan CLS (*Cumulative Layout Shift*).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Non-Destructive Hydration & DOM Reconciliation

Sebelum Angular 16, sistem Angular Universal menggunakan pendekatan *Destructive Hydration*: server me-render HTML mentah, dikirim ke *browser*, lalu Angular di sisi klien menghapus seluruh node DOM yang telah dibuat server dan membangun ulang (*re-render*) DOM tree dari nol. Hal ini memicu *screen flickering*, degradasi LCP drastis, serta pemborosan siklus CPU klien.

Sejak Angular 17+, Angular beralih sepenuhnya ke **Non-Destructive Hydration**.

```
[Browser menerima SSR HTML]
       │
       ├──> Node DOM telah memuat metadata hidrasi: ngh="0"
       │
[Angular Client Bootstrapping]
       │
       ├──> Angular TIDAK menghapus node DOM
       ├──> Traversing DOM existing & membaca struktur LView/TView
       ├──> Mengaitkan (Attach) listeners & Signal bindings ke node DOM yang cocok
       │
[Hydration Selesai (Seamless)]
```

#### Komponen Internal Engine:
1. **Serialization Metadata (`ngh` attribute)**:
   Saat me-render di server, Angular menyisipkan atribut khusus (misal: `ngh="c0"`) pada elemen host root atau komponen. Atribut ini memuat representasi kompak dari state hierarki komponen:
   - Posisi node DOM proyeksi konten (`ng-content`).
   - Indeks container view untuk *structural directives* (`@if`, `@for`).
   - Slot kosong (*empty text nodes*) yang sengaja dipertahankan sebagai penanda batas.
2. **Reconciliation Engine**:
   Ketika klien melakukan *bootstrap*, Angular memindai DOM tree yang ada dan mencocokkannya dengan `TView` (struktur cetak biru komponen) dan `LView` (instance data spesifik per-view). Jika ditemukan ketidaksesuaian (misalnya DOM klien memiliki elemen berbeda dibanding server), Angular melempar galat *Hydration Node Mismatch* dan melakukan *fallback* lokal ke *re-rendering* destruktif hanya pada node tersebut.
3. **Event Replay (JSAction Engine)**:
   Diaktifkan via `withEventReplay()`. Sebelum Angular selesai me-load seluruh bundle JavaScript dan melakukan hidrasi, pengguna mungkin sudah mengklik tombol. Engine menyisipkan *inline script* ringan (~1KB) yang menangkap *early events* (click, input, submit) di tingkat *document root*, menyimpannya ke dalam *buffer FIFO*, dan memainkannya ulang (*replays*) secara deterministik setelah hidrasi komponen selesai tanpa menghilangkan interaksi pengguna.
4. **Incremental Hydration (`@defer (hydrate on ...)` - Angular 19+)**:
   Memungkinkan pemisahan proses hidrasi. HTML komponen dikirim secara utuh via SSR, namun JS hydration engine untuk blok tersebut tidak dieksekusi sampai pemicu terpenuhi (misal: `hydrate on viewport`, `hydrate on interaction`, atau `hydrate when condition`).

---

## 4. Why & What

| Kategori | Client-Side Rendering (CSR) | Pure Dynamic SSR | Modern Hybrid SSR + Hydration |
| :--- | :--- | :--- | :--- |
| **First Contentful Paint (FCP)** | Lambat (tergantung ukuran JS bundle) | Cepat (HTML langsung dikirim) | Cepat (HTML ter-render dari server) |
| **Interaction to Next Paint (INP)** | Normal setelah JS siap | Rentang bahaya: *Uncanny Valley* tinggi | Rendah berkat *Event Replay* |
| **Server Resource Overhead** | Nol (static storage CDN) | Sangat Tinggi (CPU Node.js per-request) | Terukur (via dynamic SSG + Edge Caching) |
| **State Redundancy** | Nol | Rawan *double fetching* tanpa `TransferState` | Zero Redundant Fetch via `TransferState` |
| **SEO Indexability** | Buruk/Bergantung pada Bot Execution | Sempurna | Sempurna |

### Definisi Kunci
- **TransferState**: Mekanisme penyimpanan *key-value* sinkron yang menanamkan respons data dari server ke dalam *payload* HTML (sebagai `<script id="ng-state" type="application/json">`). Ketika klien menginisiasi service, klien memeriksa `TransferState` terlebih dahulu sebelum menembak jaringan.
- **Uncanny Valley**: Kondisi ketika antarmuka visual sudah tampil sempurna (ter-render oleh SSR), namun tidak merespons interaksi pengguna karena JavaScript belum selesai dieksekusi atau proses hidrasi belum selesai.

---

## 5. How: Workflow Detail

```
[User Browser]             [CDN / Edge Layer]           [SSR Node.js Engine]          [Backend Microservices]
      │                             │                             │                              │
   1. │ GET /products/sku-99        │                             │                              │
      ├────────────────────────────>│                             │                              │
      │                             │ 2. Cache Miss               │                              │
      │                             ├────────────────────────────>│                              │
      │                             │                             │ 3. Execute Angular Engine    │
      │                             │                             │    - CommonEngine.render()   │
      │                             │                             │ 4. HTTP Fetch Data           │
      │                             │                             ├─────────────────────────────>│
      │                             │                             │ 5. Response Data             │
      │                             │                             │<─────────────────────────────┤
      │                             │                             │ 6. Inject TransferState      │
      │                             │                             │ 7. Generate Static Markup    │
      │                             │ 8. Return HTML + Metadata   │                              │
      │                             │<────────────────────────────┤                              │
      │                             │ 9. Save Cache (Redis/Edge)  │                              │
      │ 10. Deliver HTML + State    │                             │                              │
      │<────────────────────────────┤                             │                              │
 11.  Parse DOM & Paint (LCP)       │                             │                              │
 12.  Load Bundles (main.js)        │                             │                              │
 13.  [Event Buffer Active]         │                             │                              │
 14.  Hydration Phase:              │                             │                              │
      - Match ngh nodes             │                             │                              │
      - Extract TransferState       │                             │                              │
      - Bind Signals & Listeners    │                             │                              │
 15.  Replay Buffered Events        │                             │                              │
 16.  App Fully Interactive (TTI)   │                             │                              │
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Merakit Furnitur Rumah Kontrak
- **CSR**: Truk datang hanya membawa buku panduan dan tumpukan kayu mentah. Anda harus memotong, memaku, dan mengecat sendiri dari nol sebelum bisa duduk (LCP lambat, TTI lambat).
- **Destructive SSR**: Kontraktor membawa sofa jadi ke ruang tamu. Anda melihatnya langsung (LCP cepat). Tiba-tiba kontraktor kedua datang, menghancurkan sofa itu dengan martil sampai hancur, lalu merakit ulang sofa identik di titik yang sama (Flicker, boros tenaga).
- **Non-Destructive Hydration**: Kontraktor membawa sofa jadi yang kokoh. Petugas kedua datang membawa sekrup pengaman dan kabel listrik, langsung mencolokkan kabel dan memastikan sandaran terkunci tanpa memindahkan atau membongkar sofa tersebut sama sekali (Seamless, LCP cepat, TTI instan).

### Diagram DOM Matching Hydration Engine

```
Server Output HTML:
<app-root ngh="0">
  <header ngh="1">Dashboard</header>
  <main ngh="2">
    <!--nghm=3-->
    <p>Halo, <span ngh="4">Budi</span></p>
  </main>
</app-root>

           │
           │ Match against Client TView Tree
           ▼
Client Hydration Pipeline:
[TView Identifier] ──> Match Node [ngh="0"] ── Attach Root Component
[TView Identifier] ──> Match Node [ngh="1"] ── Retain static node
[TView Identifier] ──> Match Node [ngh="2"] ── Retain structure
[LView Bindings]   ──> Point directly to <span ngh="4"> textContent Signal
                       (Zero DOM creation calls, pure pointer attachment!)
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Safe Platform Detection & TransferState Primitives

Berikut adalah implementasi standalone component yang aman dari error `window is not defined` dan mencegah double data fetch menggunakan `TransferState`.

```typescript
// src/app/features/profile/user-profile.component.ts
import { 
  Component, 
  OnInit, 
  inject, 
  signal, 
  PLATFORM_ID, 
  makeStateKey, 
  TransferState 
} from '@angular/core';
import { isPlatformBrowser, isPlatformServer } from '@angular/common';
import { HttpClient } from '@angular/common/http';

export interface UserProfile {
  id: string;
  name: string;
  role: string;
}

const USER_PROFILE_KEY = makeStateKey<UserProfile>('CURRENT_USER_PROFILE');

@Component({
  selector: 'app-user-profile',
  standalone: true,
  template: `
    <section class="profile-card">
      @if (profile(); as user) {
        <h2>{{ user.name }}</h2>
        <p>Peran: {{ user.role }}</p>
      } @else {
        <p>Memuat profil pengguna...</p>
      }
      <p><small>Platform: {{ currentPlatform() }}</small></p>
    </section>
  `
})
export class UserProfileComponent implements OnInit {
  private readonly platformId = inject(PLATFORM_ID);
  private readonly transferState = inject(TransferState);
  private readonly http = inject(HttpClient);

  readonly profile = signal<UserProfile | null>(null);
  readonly currentPlatform = signal<string>(
    isPlatformServer(this.platformId) ? 'Server (SSR Engine)' : 'Client (Browser Engine)'
  );

  ngOnInit(): void {
    if (this.transferState.hasKey(USER_PROFILE_KEY)) {
      // 1. Ambil data dari TransferState jika tersedia (Sisi Klien)
      const cachedProfile = this.transferState.get(USER_PROFILE_KEY, null);
      this.profile.set(cachedProfile);
      this.transferState.remove(USER_PROFILE_KEY); // Bersihkan memori setelah dikonsumsi
    } else {
      // 2. Fetch HTTP (Dieksekusi di Server atau di Client jika navigasi SPA murni)
      this.fetchProfile();
    }

    // Eksekusi aman API spesifik browser
    if (isPlatformBrowser(this.platformId)) {
      console.log('Resolusi layar pengguna:', window.innerWidth, 'x', window.innerHeight);
    }
  }

  private fetchProfile(): void {
    this.http.get<UserProfile>('https://api.enterprise.internal/v1/user/me')
      .subscribe({
        next: (data) => {
          this.profile.set(data);
          // Jika berjalan di server, tanamkan hasil response ke TransferState
          if (isPlatformServer(this.platformId)) {
            this.transferState.set(USER_PROFILE_KEY, data);
          }
        },
        error: (err) => console.error('Gagal mengambil data profil:', err)
      });
  }
}
```

---

### 7.2 Practical Example: Enterprise-Grade HTTP TransferState Interceptor & Production SSR Server

Arsitektur produksi tidak boleh mengelola `TransferState` secara manual di setiap komponen. Pendekatan standar enterprise adalah menggunakan **Global TransferState HTTP Interceptor** yang secara otomatis mencatat respons `GET` di server dan langsung me-*replay* respons tersebut di klien tanpa modifikasi kode komponen.

#### 1. Global TransferState Interceptor
```typescript
// src/app/core/interceptors/transfer-state.interceptor.ts
import { 
  HttpInterceptorFn, 
  HttpResponse 
} from '@angular/common/http';
import { inject, PLATFORM_ID, makeStateKey, TransferState } from '@angular/core';
import { isPlatformBrowser, isPlatformServer } from '@angular/common';
import { of, tap } from 'rxjs';

export const transferStateInterceptor: HttpInterceptorFn = (req, next) => {
  // Hanya intersep metode GET yang bersifat idempotent
  if (req.method !== 'GET') {
    return next(req);
  }

  const platformId = inject(PLATFORM_ID);
  const transferState = inject(TransferState);
  
  // Normalisasi URL dan query parameter sebagai cache key unik
  const stateKey = makeStateKey<unknown>(`HTTP_CACHE_${req.urlWithParams}`);

  // SISI CLIENT: Cek apakah data tersedia di TransferState
  if (isPlatformBrowser(platformId)) {
    if (transferState.hasKey(stateKey)) {
      const cachedResponse = transferState.get(stateKey, null);
      transferState.remove(stateKey); // Clean up memory footprint

      if (cachedResponse) {
        return of(new HttpResponse({
          body: cachedResponse,
          status: 200,
          statusText: 'OK (Hydrated from TransferState)'
        }));
      }
    }
    return next(req);
  }

  // SISI SERVER: Eksekusi HTTP dan simpan respons ke TransferState
  if (isPlatformServer(platformId)) {
    return next(req).pipe(
      tap((event) => {
        if (event instanceof HttpResponse && event.status >= 200 && event.status < 300) {
          transferState.set(stateKey, event.body);
        }
      })
    );
  }

  return next(req);
};
```

#### 2. Konfigurasi Aplikasi (`app.config.ts` & `app.config.server.ts`)

```typescript
// src/app/app.config.ts (Shared & Browser Configuration)
import { ApplicationConfig, provideZoneChangeDetection } from '@angular/core';
import { provideRouter, withComponentInputBinding } from '@angular/router';
import { provideHttpClient, withFetch, withInterceptors } from '@angular/common/http';
import { provideClientHydration, withEventReplay() } from '@angular/platform-browser';
import { routes } from './app.routes';
import { transferStateInterceptor } from './core/interceptors/transfer-state.interceptor';

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes, withComponentInputBinding()),
    provideHttpClient(
      withFetch(), // Gunakan Fetch API alih-alih XMLHttpRequest
      withInterceptors([transferStateInterceptor])
    ),
    provideClientHydration(
      withEventReplay() // Mencegah hilangnya event klik/input selama fase bootstrapping
    )
  ]
};
```

```typescript
// src/app/app.config.server.ts (Server-Specific Configuration)
import { mergeApplicationConfig, ApplicationConfig } from '@angular/core';
import { provideServerRendering } from '@angular/platform-server';
import { appConfig } from './app.config';

const serverConfig: ApplicationConfig = {
  providers: [
    provideServerRendering()
  ]
};

export const config = mergeApplicationConfig(appConfig, serverConfig);
```

#### 3. Production Node.js Engine (`server.ts`) dengan Isolasi & Redis Cache Caching Layer

```typescript
// server.ts
import { APP_BASE_HREF } from '@angular/common';
import { CommonEngine } from '@angular/ssr';
import express, { Request, Response, NextFunction } from 'express';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';
import bootstrap from './src/main.server';

export function app(): express.Express {
  const server = express();
  const serverDistFolder = dirname(fileURLToPath(import.meta.url));
  const browserDistFolder = resolve(serverDistFolder, '../browser');
  const indexHtml = join(serverDistFolder, 'index.server.html');

  const commonEngine = new CommonEngine();

  server.set('view engine', 'html');
  server.set('views', browserDistFolder);

  // Health check endpoint untuk Kubernetes / Load Balancer
  server.get('/healthz', (_req, res) => {
    res.status(200).send({ status: 'UP', timestamp: new Date().toISOString() });
  });

  // Serve static assets dengan Cache-Control agresif (immutable)
  server.get('*.*', express.static(browserDistFolder, {
    maxAge: '1y',
    immutable: true,
    index: false
  }));

  // Dynamic SSR Rendering Handler dengan HTTP Cache Control
  server.get('*', (req: Request, res: Response, next: NextFunction) => {
    const { protocol, originalUrl, baseUrl, headers } = req;

    // Terapkan Cache-Control Stale-While-Revalidate untuk Reverse Proxy (CDN)
    res.setHeader('Cache-Control', 'public, max-age=60, s-maxage=300, stale-while-revalidate=600');

    commonEngine
      .render({
        bootstrap,
        documentFilePath: indexHtml,
        url: `${protocol}://${headers.host}${originalUrl}`,
        publicPath: browserDistFolder,
        providers: [
          { provide: APP_BASE_HREF, useValue: baseUrl },
          // Contoh passing request context ke dalam dependency injection token
          { provide: 'REQUEST_HEADERS', useValue: headers }
        ],
      })
      .then((html) => res.send(html))
      .catch((err) => {
        // Fallback: Jika rendering server melempar error, delegasikan ke Next handler atau kirim index mentah
        console.error(`[SSR Engine Error] Path: ${originalUrl} | Error:`, err);
        return next(err);
      });
  });

  return server;
}

function run(): void {
  const port = process.env['PORT'] || 4000;
  const server = app();
  server.listen(port, () => {
    console.log(`Node Express SSR server aktif di http://localhost:${port}`);
  });
}

run();
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Global Multi-Tenant E-Commerce Platform
- **Volume**: 45 juta *pageviews*/hari, 120 negara, 8.000 tenant independen.
- **Problem Statement**:
  1. *LCP Kritis*: Google merekam skor LCP rata-rata 4.8 detik pada halaman PDP (*Product Detail Page*).
  2. *Uncanny Valley*: Rata-rata 12% *Add to Cart* klik pertama hilang (*lost interaction*) karena dieksekusi sebelum JS selesai menghidrasi halaman.
  3. *Node.js Pod OOM*: Cluster Kubernetes SSR mengalami *Out of Memory* (CrashLoopBackOff) setiap jam sibuk akibat kebocoran memori pada *RxJS Event Stream*.

### Solusi Arsitektur

```
[Global Route Route53]
         │
         ▼
[Cloudflare Enterprise Edge Workers]
         ├── Static Assets (*.js, *.css, *.webp) ─────────> AWS S3 Origin (Edge Cached)
         └── HTML Route (/p/:sku)
                  │
                  ├── Cache HIT (Edge S-MaxAge) ──────────> Return cached SSR Page (12ms)
                  └── Cache MISS
                           │
                           ▼
                  [AWS EKS SSR Cluster]
                  (Node.js + Angular Engine)
                           ├── Microservices Fetch via TransferState Interceptor
                           └── Render via CommonEngine + EventReplay
```

#### Langkah Perbaikan:
1. **Penerapan Event Replay**:
   Mengaktifkan `provideClientHydration(withEventReplay())` memulihkan seluruh interaksi pengguna yang tertunda saat proses bootstrap, menurunkan *Cart abandonment* sebesar 11.4%.
2. **Koreksi RxJS Leakage di SSR**:
   Ditemukan adanya *Auth State Service* singleton yang melakukan `BehaviorSubject.subscribe()` tanpa mekanisme pelepasan memori. Di server, setiap request HTTP membuat listener baru yang terakumulasi di memori global instance Node.js. Diubah menjadi sinyal berbasis scope atau menggunakan operator `takeUntilDestroyed()`.
3. **Pemisahan Dynamic SSR vs Incremental Hydration**:
   Ulasan produk (komentar ribuan item) dikeluarkan dari hidrasi awal menggunakan `@defer (hydrate on viewport; prefetch on idle)`. Server tetap me-render kerangka HTML untuk SEO, tetapi bundle JS untuk ulasan tidak diunduh/dihidrasi sebelum pengguna menggulir ke area tersebut.

### Hasil Metrik:
- **LCP**: Turun dari 4.8s menjadi 1.1s (Status: *Good* di Core Web Vitals).
- **INP**: Rata-rata turun dari 380ms ke 45ms.
- **Node.js RAM Usage**: Turun stabil dari ~1.4GB per pod menjadi flat di ~280MB konstan.

---

## 9. Trade-offs

| Aspek | Sisi Positif (Advantage) | Biaya/Konsekuensi (Trade-off) | Mitigasi Desain |
| :--- | :--- | :--- | :--- |
| **Non-Destructive Hydration** | Tidak ada flicker; mempertahankan integritas DOM; meningkatkan LCP & INP secara drastis. | Memerlukan *memory footprint* ekstra di browser untuk menyimpan metadata tabel relasi DOM. | Hilangkan DOM wrapper yang tidak perlu, gunakan struktur markup seringkas mungkin. |
| **TransferState Interceptor** | Mengeliminasi redundansi request API ganda (server lalu browser). | Ukuran HTML bertambah besar karena JSON diserialisasi ke dalam DOM. | Jangan simpan seluruh field respons backend; buat DTO minimal khusus konsumsi UI. |
| **Dynamic Node.js SSR** | Menghasilkan metadata dinamis (SEO/OpenGraph) secara *real-time* per tenant. | Memerlukan manajemen compute yang kompleks (CPU bound, risiko kebocoran memori). | Terapkan Reverse Proxy Caching agresif (`stale-while-revalidate`), batasi rendering concurrent. |
| **Event Replay** | Menjamin tidak ada event klik yang hilang selama bootstrap. | Berpotensi memicu lonjakan eksekusi (*event flood*) jika hidrasi tertunda sangat lama. | Hindari waktu hidrasi total > 3 detik; gunakan *Deferrable Views* untuk memecah beban. |

---

## 10. Common Mistakes & Troubleshooting

### Mistake 1: DOM Manipulation via Native Elements (Bypass Renderer/Angular)
```typescript
// FATAL ERROR: Menyebabkan Hydration Node Mismatch Error di Produksi
export class HeaderComponent implements OnInit {
  ngOnInit() {
    // Mengakses document secara langsung tanpa abstraksi
    const el = document.getElementById('user-badge');
    el?.setAttribute('class', 'active-badge');
  }
}
```
**Perbaikan**:
Gunakan Angular template bindings atau `Renderer2` jika manipulasi langsung tidak terhindarkan.
```typescript
@Component({
  template: `<div id="user-badge" [class.active-badge]="isActive()"></div>`
})
export class HeaderComponent {
  readonly isActive = signal(true);
}
```

### Mistake 2: ReferenceError: `window` is not defined (atau `localStorage`/`document`)
Server Node.js tidak memiliki objek runtime `window`. Jika file dieksekusi langsung tanpa guards, thread server akan langsung *crash* (500 Internal Server Error).
```typescript
// SALAH
export class TrackerService {
  constructor() {
    const token = localStorage.getItem('auth_token'); // CRASH di Server!
  }
}

// BENAR
export class TrackerService {
  private readonly platformId = inject(PLATFORM_ID);

  getToken(): string | null {
    if (isPlatformBrowser(this.platformId)) {
      return localStorage.getItem('auth_token');
    }
    return null; // Return fallback default di lingkungan server
  }
}
```

### Mistake 3: SSR Memory Leak Melalui Long-Lived Observable Singletons
```typescript
// FATAL ERROR: Memory leak di Node.js instance
@Injectable({ providedIn: 'root' })
export class GlobalNotificationService {
  private eventStream$ = interval(1000);

  initListener() {
    this.eventStream$.subscribe(val => { // Subscribe tidak pernah di-teardown
      console.log('Value:', val);
    });
  }
}
```
**Perbaikan**:
Gunakan `DestroyRef` atau batasi eksekusi streaming hanya pada platform klien (`isPlatformBrowser`).

---

## 11. Best Practices (Production Checklist)

- [ ] **Modern Hydration Enabler**: Pastikan `provideClientHydration(withEventReplay())` aktif di `app.config.ts`.
- [ ] **TransferState Interceptor**: Validasi bahwa tidak ada duplikasi request GET pada *Network Tab* browser saat halaman pertama kali dimuat.
- [ ] **Fetch Engine**: Gunakan `provideHttpClient(withFetch())` untuk mendukung *streaming response* native pada Node 18+ dan Edge Workers.
- [ ] **No Destructive DOM Mutations**: Audit kode dari penggunaan `innerHTML`, manipulasi class via `document.querySelector`, atau modifikasi langsung node di luar Angular lifecycle.
- [ ] **Prerendering Targets**: Konfigurasikan file `routes.txt` untuk SSG pada rute yang kontennya statis (contoh: `/terms`, `/privacy`, `/about`).
- [ ] **Edge Cache Headers**: Pasang header `Cache-Control: public, s-maxage=..., stale-while-revalidate=...` di depan server SSR untuk memangkas *load* CPU Node.js.
- [ ] **Size Budget TransferState**: Filter respons backend sebelum masuk ke `TransferState`; jangan menyertakan *stack trace*, *internal IDs*, atau metadata sensitif.

---

## 12. Hands-on Practice

Buat dan implementasikan arsitektur SSR berikut pada direktori: `hands-on/m02/`

### Struktur Target
```
hands-on/m02/
├── package.json
├── src/
│   ├── app/
│   │   ├── core/
│   │   │   ├── tokens/request-context.token.ts
│   │   │   └── interceptors/caching-transfer.interceptor.ts
│   │   ├── features/
│   │   │   └── telemetry/telemetry.component.ts
│   │   ├── app.config.ts
│   │   ├── app.config.server.ts
│   │   └── app.routes.ts
│   ├── main.ts
│   └── main.server.ts
└── server.ts
```

### Langkah Praktikum

#### Langkah 1: Buat Token Injeksi Konteks Request Server
```typescript
// hands-on/m02/src/app/core/tokens/request-context.token.ts
import { InjectionToken } from '@angular/core';

export interface RequestContext {
  clientIp: string;
  userAgent: string;
}

export const REQUEST_CONTEXT = new InjectionToken<RequestContext>('REQUEST_CONTEXT');
```

#### Langkah 2: Buat Interceptor TransferState Berkinerja Tinggi
```typescript
// hands-on/m02/src/app/core/interceptors/caching-transfer.interceptor.ts
import { HttpInterceptorFn, HttpResponse } from '@angular/common/http';
import { inject, PLATFORM_ID, makeStateKey, TransferState } from '@angular/core';
import { isPlatformBrowser, isPlatformServer } from '@angular/common';
import { of, tap } from 'rxjs';

export const cachingTransferInterceptor: HttpInterceptorFn = (req, next) => {
  if (req.method !== 'GET') {
    return next(req);
  }

  const transferState = inject(TransferState);
  const platformId = inject(PLATFORM_ID);
  const key = makeStateKey<unknown>(`STATE_KEY_${req.urlWithParams}`);

  if (isPlatformBrowser(platformId)) {
    if (transferState.hasKey(key)) {
      const data = transferState.get(key, null);
      transferState.remove(key);
      return of(new HttpResponse({ status: 200, body: data }));
    }
    return next(req);
  }

  return next(req).pipe(
    tap((event) => {
      if (isPlatformServer(platformId) && event instanceof HttpResponse) {
        transferState.set(key, event.body);
      }
    })
  );
};
```

#### Langkah 3: Implementasi Komponen Telemetri SSR yang Tahan Error
```typescript
// hands-on/m02/src/app/features/telemetry/telemetry.component.ts
import { Component, inject, OnInit, signal, optional } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { REQUEST_CONTEXT } from '../../core/tokens/request-context.token';

interface PingResponse {
  serverTime: string;
  loadAvg: number[];
}

@Component({
  selector: 'app-telemetry',
  standalone: true,
  template: `
    <div class="telemetry-panel">
      <h1>Sistem Telemetri Node</h1>
      @if (data(); as metric) {
        <p>Waktu Server: <strong>{{ metric.serverTime }}</strong></p>
        <p>Load Average: {{ metric.loadAvg.join(', ') }}</p>
      } @else {
        <p>Mengambil metrik server...</p>
      }

      @if (context) {
        <div class="client-meta">
          <small>IP Akses (via SSR Inject): {{ context.clientIp }}</small>
        </div>
      }
    </div>
  `
})
export class TelemetryComponent implements OnInit {
  private readonly http = inject(HttpClient);
  // Context injected safely using optional flag since it's only available on server
  protected readonly context = inject(REQUEST_CONTEXT, { optional: true });

  readonly data = signal<PingResponse | null>(null);

  ngOnInit(): void {
    // API ini di-intersep TransferState; aman dipanggil tanpa double roundtrip
    this.http.get<PingResponse>('https://api.mocki.io/v2/telemetry-sample')
      .subscribe({
        next: (res) => this.data.set(res),
        error: () => this.data.set({ serverTime: 'Fallback SSR', loadAvg: [0.1, 0.2, 0.15] })
      });
  }
}
```

#### Langkah 4: Hubungkan App Config dengan Event Replay
```typescript
// hands-on/m02/src/app/app.config.ts
import { ApplicationConfig, provideZoneChangeDetection } from '@angular/core';
import { provideRouter, Routes } from '@angular/router';
import { provideHttpClient, withFetch, withInterceptors } from '@angular/common/http';
import { provideClientHydration, withEventReplay() } from '@angular/platform-browser';
import { cachingTransferInterceptor } from './core/interceptors/caching-transfer.interceptor';
import { TelemetryComponent } from './features/telemetry/telemetry.component';

export const routes: Routes = [
  { path: '', component: TelemetryComponent }
];

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes),
    provideHttpClient(
      withFetch(),
      withInterceptors([cachingTransferInterceptor])
    ),
    provideClientHydration(withEventReplay())
  ]
};
```

#### Langkah 5: Node.js Express Server Setup Menyuntikkan Konteks Request
```typescript
// hands-on/m02/server.ts
import { APP_BASE_HREF } from '@angular/common';
import { CommonEngine } from '@angular/ssr';
import express from 'express';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';
import bootstrap from './src/main.server';
import { REQUEST_CONTEXT } from './src/app/core/tokens/request-context.token';

export function app(): express.Express {
  const server = express();
  const serverDistFolder = dirname(fileURLToPath(import.meta.url));
  const browserDistFolder = resolve(serverDistFolder, '../browser');
  const indexHtml = join(serverDistFolder, 'index.server.html');
  const commonEngine = new CommonEngine();

  server.set('view engine', 'html');
  server.set('views', browserDistFolder);

  server.get('*.*', express.static(browserDistFolder, { maxAge: '1y' }));

  server.get('*', (req, res, next) => {
    const { protocol, originalUrl, baseUrl, headers, ip } = req;

    commonEngine
      .render({
        bootstrap,
        documentFilePath: indexHtml,
        url: `${protocol}://${headers.host}${originalUrl}`,
        publicPath: browserDistFolder,
        providers: [
          { provide: APP_BASE_HREF, useValue: baseUrl },
          { 
            provide: REQUEST_CONTEXT, 
            useValue: { 
              clientIp: ip || '127.0.0.1', 
              userAgent: headers['user-agent'] || 'Unknown' 
            } 
          }
        ],
      })
      .then((html) => res.send(html))
      .catch((err) => next(err));
  });

  return server;
}
```

---

## 13. Exercise

### Level Easy
Ubah sebuah komponen yang masih menggunakan `window.location.href` agar menggunakan Angular `Router` service dan terlindungi oleh guard pengecekan `isPlatformBrowser(platformId)` sehingga aman saat dirender pada server.

### Level Medium
Buat sebuah mekanisme *Prerendering Parameter Provider* dinamis menggunakan `getPrerenderParams` untuk rute artikel `/article/:slug`. Service harus membaca daftar 100 *slug* terpopuler saat build-time dari API internal dan memproduksi 100 file HTML statis saat pipeline `ng build` dieksekusi.

### Level Hard
Bangun sebuah custom Angular Directive bernama `[safeHydrateDirective]` yang memonitor apakah elemen tersebut sudah terhidrasi secara penuh. Jika proses hidrasi mengalami *Node Mismatch*, directive harus mendeteksi error tersebut via console hooking/zone diagnostics, melakukan penataan DOM kembali tanpa memicu full page reload, dan melaporkan event kesalahan tersebut ke endpoint logging backend.

---

## 14. Challenge

### Studi Kasus: High-Traffic Dynamic Hybrid Multi-Region Edge Rendering
Sebuah platform berita finansial global membutuhkan waktu muat halaman *Breaking News* di bawah **300 milidetik** secara global dengan *live updates* per detik.

#### Batasan Arsitektur:
1. **Header & Breaking News**: Harus di-render via SSR di Edge Worker (Cloudflare Workers/V8 Isolate) dengan latensi rendering < 50ms.
2. **Grafik Saham Live**: Harus sepenuhnya Client-Side Rendering (CSR) via WebSocket, tidak boleh di-render di server untuk mencegah *hydration mismatch* akibat fluktuasi angka saham real-time per milidetik.
3. **Kolom Komentar Pengguna (Bawahan Halaman)**: Menggunakan Incremental Hydration. HTML harus ada untuk kebutuhan indexing mesin pencari (SEO), tetapi hidrasi JavaScript ditangguhkan sampai pengguna berhenti scroll (*idle*) atau elemen berjarak 200px dari layar (*viewport*).
4. **Zero Double Fetching**: Semua metadata ticker pasar yang diambil Edge Server wajib ditransfer secara aman ke browser tanpa serialisasi data internal yang tidak perlu.

#### Tugas:
Rancang struktur routing, konfigurasi `server.ts` / edge entry point, pemetaan `@defer` block, dan arsitektur `TransferState` untuk memenuhi seluruh batasan di atas tanpa menurunkan skor Core Web Vitals.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Basic (5 Soal)

1. **Apa perbedaan fundamental antara Destructive Hydration dan Non-Destructive Hydration di Angular?**
   - *Jawaban*: Destructive Hydration menghapus seluruh node DOM yang telah dibuat server saat bootstrapping di browser dan membangun ulang semuanya dari awal (menyebabkan flicker). Non-Destructive Hydration mempertahankan DOM server, mencocokkannya ke view data struktur (`TView`/`LView`), dan langsung menyematkan event listener serta reactive bindings ke node yang sudah ada.

2. **Mengapa error `ReferenceError: document is not defined` sering muncul saat pertama kali mengaktifkan SSR?**
   - *Jawaban*: Karena lingkungan eksekusi server adalah runtime Node.js yang tidak memiliki global browser API seperti `document`, `window`, atau `navigator`.

3. **Apa fungsi utama dari `provideClientHydration(withEventReplay())`?**
   - *Jawaban*: Merekam interaksi pengguna (misal: click) yang terjadi sebelum JavaScript Angular selesai dimuat dan melakukan replay secara otomatis setelah proses hidrasi selesai agar interaksi tidak hilang.

4. **Bagaimana cara mendeteksi apakah kode sedang dieksekusi di Node.js atau di Browser?**
   - *Jawaban*: Menggunakan fungsi `isPlatformServer(platformId)` atau `isPlatformBrowser(platformId)` dengan menginjeksi token `PLATFORM_ID`.

5. **Apa tujuan dari penggunaan `TransferState` pada SSR?**
   - *Jawaban*: Menghindari *double data fetching* dengan mentransfer data hasil query API di server ke dalam format JSON di HTML, sehingga browser bisa langsung membaca data lokal tersebut tanpa menembak ulang HTTP request.

---

### Bagian B: Intermediate (5 Soal)

6. **Mengapa manipulasi DOM langsung menggunakan `ElementRef.nativeElement.appendChild()` dapat merusak proses hidrasi?**
   - *Jawaban*: Karena Angular bergantung pada kestabilan susunan node DOM hasil rendering server untuk dicocokkan dengan `LView`. Menambah atau memindahkan child node secara manual akan mengubah struktur DOM fisik sehingga menimbulkan *Hydration Node Mismatch Error*.

7. **Bagaimana cara kerja metadata atribut `ngh` yang disisipkan oleh server render?**
   - *Jawaban*: Atribut `ngh` menyimpan payload representasi ringkas posisi struktural view, penanda template, dan indeks container. Engine hidrasi browser menggunakannya sebagai peta untuk mencocokkan setiap instance komponen Angular dengan DOM tree yang tepat tanpa perlu melakukan query berat.

8. **Kapan sebaiknya rute dikonfigurasi sebagai SSG (Prerendered) dibanding Dynamic SSR?**
   - *Jawaban*: Gunakan SSG jika konten bersifat publik, jarang berubah (atau berubah pada siklus build), dan identik untuk semua pengguna (contoh: Blog, Landing Page, FAQ). Gunakan Dynamic SSR jika konten tergantung data sesi pengguna, request headers dinamis, atau memiliki jutaan variasi rute yang mustahil dibuild di awal.

9. **Apa bahaya mengabaikan lifecycle `DestroyRef` atau unsubscription pada singleton service yang berjalan di SSR?**
   - *Jawaban*: Di server, instance proses Node.js melayani banyak request secara bersamaan. Subscription yang tidak di-teardown akan terus hidup di memory space server, menahan referensi konteks request sebelumnya, dan memicu *Memory Leak* parah yang berujung pada Node.js Crash (OOM).

10. **Bagaimana sintaks Deferrable Views untuk memastikan blok komponen di-render di server untuk SEO tetapi hanya dihidrasi ketika elemen masuk ke area viewport?**
    - *Jawaban*:
      ```html
      @defer (hydrate on viewport) {
        <app-heavy-content />
      } @placeholder {
        <div class="skeleton">Memuat...</div>
      }
      ```

---

### Bagian C: Skenario Kasus Produksi (3 Soal)

11. **Skenario 1**:
    Sebuah aplikasi e-commerce mendapati bahwa nilai `Date.now()` yang ditampilkan pada halaman flash sale berbeda 5 detik antara saat HTML diterima dari server dan saat hidrasi selesai di browser. Hal ini memicu error mismatch hidrasi: *Text content does not match server-rendered HTML*. Bagaimana solusi arsitekturnya?
    - *Solusi*:
      Waktu server dan waktu klien hampir selalu berbeda. Solusinya:
      1. Masukkan timestamp awal server ke dalam `TransferState`.
      2. Klien membaca timestamp awal tersebut dari `TransferState` untuk menginisialisasi Signal timer/counter.
      3. Atau pisahkan komponen clock/countdown ke dalam blok deferrable view yang tidak dirender/dihidrasi secara identik, melainkan diinisialisasi murni di sisi browser (`isPlatformBrowser`).

12. **Skenario 2**:
    Setelah migrasi ke Angular 18 SSR, monitoring infra AWS mencatat utilisasi CPU pod Node.js menyentuh 100% saat lonjakan traffic 10.000 RPS, sehingga menyebabkan server menolak koneksi (HTTP 503). Padahal backend microservice hanya memiliki beban CPU 15%. Mengapa hal ini terjadi dan bagaimana mitigasinya?
    - *Solusi*:
      Operasi `renderApplication` / `CommonEngine.render()` di Node.js adalah proses intensif yang bersifat *synchronous CPU-bound* (string concatenation & virtual DOM traversal). Node.js event-loop terblokir jika menangani ribuan rendering simultan. Mitigasi:
      1. Terapkan Reverse Proxy Caching di CDN (Cloudflare/CloudFront) menggunakan header `Cache-Control: s-maxage=60, stale-while-revalidate=120`. Dengan cara ini, 99% request diserap oleh CDN edge cache.
      2. Pasang rate limiting & antrean rendering pada instance Node.js.
      3. Identifikasi rute yang dapat diubah statusnya menjadi SSG (Prerender).

13. **Skenario 3**:
    Pengguna melaporkan bahwa saat mereka login di perangkat publik, mereka sesekali melihat data nama profil pengguna lain yang sebelumnya baru saja mengakses website dari belahan negara lain. Di mana letak kegagalan arsitektur SSR ini?
    - *Solusi*:
      Telah terjadi kebocoran *State Antar-Request* (State Pollution). Penyebab umumnya adalah penyimpanan data pengguna/token di dalam properti kelas singleton `@Injectable({ providedIn: 'root' })`. Karena proses Node.js bersifat multi-request pada instance singleton yang sama, state global tersebut tertimpa oleh request pengguna lain yang dieksekusi secara paralel.
      *Perbaikan*: Jangan pernah menyimpan data per-request di singleton service. Selalu inject konteks request per-eksekusi atau gunakan request-scoped execution context (misalnya Node.js `AsyncLocalStorage`) untuk mengisolasi data user per HTTP request.

---

## 16. Summary

1. **Non-Destructive Hydration** adalah pilar performa Angular modern yang meniadakan *DOM replacement*, mempertahankan rendering server secara mulus, dan mengoptimalkan Core Web Vitals (LCP, CLS, INP).
2. **Event Replay** memastikan bahwa interaksi pengguna yang dilakukan saat status aplikasi berada dalam *Uncanny Valley* tidak terbuang, melainkan direkam dan diputar ulang secara deterministik.
3. **TransferState Interceptor** merupakan pola wajib enterprise untuk menyinkronkan data antara server dan klien tanpa membebani jaringan dengan *double data fetch*.
4. **Isolasi State Server** adalah aturan kritis dalam arsitektur SSR: hindari mutasi data global pada singleton service, amankan akses browser-specific globals menggunakan `isPlatformBrowser` / `Renderer2`, dan kelola memori subscription secara ketat menggunakan `DestroyRef`.
5. Kombinasi **Edge Caching**, **Stale-While-Revalidate**, dan **Incremental Hydration (`@defer`)** menghasilkan aplikasi web yang memiliki kecepatan instan static site tanpa mengorbankan kedalaman fitur aplikasi enterprise dinamis.