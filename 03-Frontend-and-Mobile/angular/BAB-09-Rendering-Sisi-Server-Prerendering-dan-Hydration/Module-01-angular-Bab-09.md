# KATEGORI: 03-Frontend-and-Mobile
# KURIKULUM: Angular
# BAB 09: Rendering Sisi Server (SSR), Prerendering (SSG), & Hydration
# MODUL 01: Arsitektur Rendering Modern: SSR, SSG, dan Non-Destructive Hydration

---

## SEKSI 01 — IDENTITAS MODUL

* **Domain Kurikulum:** Frontend and Mobile Engineering
* **Spesialisasi:** Angular Enterprise Architecture (Angular 17/18+)
* **Kode Modul:** ANG-09-01
* **Level Teknis:** Advanced / Staff Engineer
* **Prasyarat:** Pemahaman mendalam tentang Angular Dependency Injection, Component Lifecycle, Reactive State Management (Signals & RxJS), Node.js Runtime Engine, dan HTTP/Web Standards.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1. **Menganalisis dan Membedakan Paradigma Rendering:** Membedakan secara anatomis mekanisme eksekusi Client-Side Rendering (CSR), Server-Side Rendering (SSR), Static Site Generation / Prerendering (SSG), dan Incremental Static Regeneration (ISR) dalam ekosistem Angular Universal/@angular/ssr.
2. **Menguasai Internal Mekanisme Hydration:** Menjelaskan dan mengimplementasikan algoritma *Non-Destructive Hydration*, DOM node reconciliation, serta serialisasi transfer state dari server ke client tanpa flickering.
3. **Mengoperasikan Engine Node.js Server:** Mengonfigurasi, mengoptimalkan, dan mengamankan rendering pipeline berbasis Angular SSR pada Node.js/Express (`CommonEngine`).
4. **Mitigasi Masalah Platform:** Mengatasi disparitas browser global context (`window`, `document`, `localStorage`) vs server context (`Node.js/V8`) menggunakan token `PLATFORM_ID`, `isPlatformBrowser`, `isPlatformServer`, dan safe abstraction.
5. **Menerapkan Optimalisasi Web Vitals:** Mengoptimalkan metrik Core Web Vitals (Largest Contentful Paint [LCP], First Input Delay [FID]/Interaction to Next Paint [INP], dan Cumulative Layout Shift [CLS]) pada skala enterprise.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Mental model rendering web modern bukanlah dikotomi "Client vs Server", melainkan **Continuous Continuum of Execution**. 

Dalam Single Page Application (CSR tradisional), browser mengunduh HTML kosong (`<app-root></app-root>`), mengunduh JavaScript raksasa, mengompilasi JS, mengeksekusi inisialisasi framework, melakukan HTTP request data, dan akhirnya merender Document Object Model (DOM). Selama proses ini, pengguna melihat layar putih (*white screen of death*) dan bot search engine membaca halaman kosong.

```
CSR Mindset:
Server (Empty HTML) ──> Client Downloads JS ──> Client Executes JS ──> API Fetch ──> Final Paint

SSR + Non-Destructive Hydration Mindset:
Server (Fetch Data + Render Full HTML) ──> Client Paints Full HTML (Instant FCP/LCP)
                                                          │
                                     Client Downloads JS in Background
                                                          │
                                     Reconciliation / Event Binding (Hydration)
                                                          │
                                                Interactive SPA
```

Pada mental model SSR modern Angular:
* **Server adalah Instant Painter:** Tugas server adalah menghitung state awal, menyusun tree DOM representatif, dan mengirimkannya sebagai HTML terkompresi. Server bertanggung jawab atas persepsi kecepatan visual (FCP, LCP).
* **Transfer State adalah Jembatan:** Jangan pernah membiarkan client meminta ulang data yang telah di-fetch oleh server. Data server dikemas ke dalam payload `<script type="application/json" id="ng-state">` dan diimpor langsung oleh runtime client.
* **Hydration adalah "Pembangkit Jiwa":** Hydration bukan merusak dan mengganti DOM (*destructive hydration* warisan Angular masa lalu). Hydration modern adalah proses *reconciliation* non-destruktif di mana runtime Angular berjalan di client, membaca struktur DOM yang sudah ada di HTML, menempelkan *event listener*, dan menghubungkan Signals/Change Detector tanpa mengedipkan (flicker) satu pun node DOM fisik.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

```
                                      ANGULAR SSR & HYDRATION PIPELINE
                                      
  USER / BOT                                 EDGE / NODE.JS (SERVER)                      CLIENT BROWSER (V8)
      │                                                │                                           │
  1.  │─── HTTP GET /products/42 ─────────────────────>│                                           │
      │                                                │                                           │
      │                                    ┌───────────────────────┐                               │
      │                                    │ Express Engine Entry  │                               │
      │                                    └───────────┬───────────┘                               │
      │                                                │                                           │
      │                                    ┌───────────▼───────────┐                               │
      │                                    │  Angular CommonEngine │                               │
      │                                    └───────────┬───────────┘                               │
      │                                                │                                           │
      │                                    ┌───────────▼───────────┐                               │
      │                                    │  Execute AppServer    │                               │
      │                                    │  Bootstrap Tree       │                               │
      │                                    └───────────┬───────────┘                               │
      │                                                │                                           │
      │                                    ┌───────────▼───────────┐                               │
      │                                    │ HTTP Client Intercept │                               │
      │                                    │ & Fetch Product Data  │                               │
      │                                    └───────────┬───────────┘                               │
      │                                                │                                           │
      │                                    ┌───────────▼───────────┐                               │
      │                                    │ TransferState Store   │                               │
      │                                    │ Serialized in Script  │                               │
      │                                    └───────────┬───────────┘                               │
      │                                                │                                           │
      │                                    ┌───────────▼───────────┐                               │
      │                                    │ Render to Static HTML │                               │
      │                                    └───────────┬───────────┘                               │
      │                                                │                                           │
  2.  │<── Fully Rendered HTML + Inlined TransferState ┼──────────────────────────────────────────>│ (Cache/Read)
      │    (First Contentful Paint Achieved Here!)     │                                           │
      │                                                                                            │
  3.  │─── Browser parses HTML & paints UI immediately ───────────────────────────────────────────>│ (Paint UI)
      │                                                                                            │
  4.  │─── Browser requests JS Bundles (main.js, chunk.js) ────────────────────────────────────────>│ (Load JS)
      │                                                                                            │
      │                                                                                ┌───────────▼───────────┐
      │                                                                                │ Angular Bootstrap     │
      │                                                                                │ (Client Application)  │
      │                                                                                └───────────┬───────────┘
      │                                                                                            │
      │                                                                                ┌───────────▼───────────┐
      │                                                                                │ Non-Destructive       │
      │                                                                                │ Hydration Protocol    │
      │                                                                                └───────────┬───────────┘
      │                                                                                            │
      │                                                                                ┌───────────▼───────────┐
      │                                                                                │ Claim existing DOM;   │
      │                                                                                │ Consume TransferState;│
      │                                                                                │ Attach event listeners│
      │                                                                                └───────────┬───────────┘
      │                                                                                            │
  5.  │<── Application fully interactive (INP / TTI optimized) ────────────────────────────────────┘
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Angular CommonEngine (`@angular/ssr`)
Ketika permintaan HTTP masuk ke server Express/Node.js, request dialihkan ke instance `CommonEngine`.
* Engine membuat instance `PlatformRef` khusus untuk server (`platformServer`).
* Meneruskan URI yang diminta ke Angular Router.
* Menginisialisasi `ApplicationRef`, memicu siklus initial change detection, merender view tree hingga stabil (*Zone stable* atau *Signals settle*), dan mengekstrak DOM tree yang dihasilkan menjadi plain text HTML menggunakan deserializer internal V8.

### 2. TransferState Serializer
Jika server melakukan query HTTP ke backend, engine menyimpan payload tersebut dalam service terpusat bernama `TransferState`.
* Komponen menyimpan state: `transferState.set(KEY, data)`.
* Ketika Angular merender HTML akhir, Angular menambahkan tag `<script id="ng-state" type="application/json">` di bagian bawah `<body>` yang berisi map JSON terserialisasi.
* Di client, `HttpClient` memanggil interceptor bawaan yang mengecek keberadaan key di `TransferState`. Jika ada, data langsung dibaca dari tag skrip tersebut tanpa melakukan outgoing network request melalui TCP client.

### 3. Non-Destructive Hydration Node Claiming Engine
Pada versi lawas (Angular Universal lama), client-side bootstrap akan menghancurkan (destroy) seluruh DOM yang telah dirender server dari `<app-root>` dan merender ulang dari nol. Hal ini menimbulkan screen blinking dan kehilangan input focus.

Pada Non-Destructive Hydration (Angular 17/18+):
1. **DOM Annotation:** Server menambahkan atribut metadata `ngh` (contoh: `ngh="0"`) pada node HTML untuk merepresentasikan topologi Component Tree.
2. **Hydration Node Claiming:** Saat bootstrap client berjalan, Angular berjalan dalam mode traversal. Alih-alih memanggil `document.createElement()`, engine menjalankan *node claiming algorithm*. Engine mengambil referensi DOM node yang ada di memori browser berdasarkan index/topologi tree.
3. **Event Delegator & Listener Attachment:** Setelah node di-claim, framework menempelkan synthetic & direct event listener (`click`, `input`, dsb.) ke DOM yang sudah eksis di layar.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Perbedaan Paradigma Rendering: SSR vs SSG vs Client Rehydration

| Aspek | CSR (Client-Side Rendering) | SSR (Server-Side Rendering) | SSG / Prerendering (Static Generation) |
| :--- | :--- | :--- | :--- |
| **Build Artifact** | `index.html` kosong + Bundle JS | Bundle Server (`server.mjs`) + Client Bundles | File `.html` individual per route pada build-time |
| **Compute Overhead**| Client CPU tinggi, Server CPU minimal (Static CDN) | Server CPU tinggi (Node.js runtime render per request) | Server CPU nol pada runtime (Static CDN) |
| **Data Latency** | Ditunda sampai client JS bootstrap | Rendered at server request-time (Real-time data) | Static snapshot at compile-time (Potensi stale data) |
| **SEO & Crawlers** | Bergantung pada dynamic crawler execution | Indeksasi optimal secara instan | Indeksasi optimal secara instan |
| **Best Used For** | Dashboard privat, platform SaaS tertutup | E-commerce dinamis, portal berita, media sosial | Blog, halaman dokumentasi, landing page statis |

### Siklus Hidup Hydration dan Problem Mismatch
Proses Hydration bergantung pada kesesuaian satu banding satu (1:1 parity) antara DOM yang dibuat oleh server dan DOM yang diantisipasi oleh client saat bootstrap. 

Jika terjadi perbedaan, misalnya:
* Server merender: `<div class="user-greeting">Selamat Pagi</div>` (karena timezone server UTC)
* Client mengevaluasi: `<div class="user-greeting">Selamat Malam</div>` (karena timezone client UTC+7)

Maka terjadi **Hydration Mismatch Error**. Pada mode development, Angular akan melempar error:
`NG0500: During hydration, Angular expected an element matching the selector... but found...`

Ketika terjadi mismatch yang fatal, Angular terpaksa mematikan non-destructive hydration untuk subtree komponen tersebut dan kembali ke mode destruktif: menghapus node yang mismatch dan membuat node baru, yang menyebabkan penalti performa (CLS spike dan layout reflow).

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi konfigurasi arsitektur dasar Angular SSR dengan integrasi `TransferState` dan safe platform checking.

### 1. Server Configuration Entry (`src/main.server.ts`)
```typescript
import { bootstrapApplication } from '@angular/platform-browser';
import { AppComponent } from './app/app.component';
import { config } from './app/app.config.server';

const bootstrap = () => bootstrapApplication(AppComponent, config);

export default bootstrap;
```

### 2. Application Config Server (`src/app/app.config.server.ts`)
```typescript
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

### 3. Application Config Client/Shared (`src/app/app.config.ts`)
```typescript
import { ApplicationConfig, provideZoneChangeDetection } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideClientHydration, withHttpTransferCacheOptions } from '@angular/platform-browser';
import { provideHttpClient, withFetch } from '@angular/common/http';
import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes),
    provideHttpClient(withFetch()),
    // Mengaktifkan Non-Destructive Hydration & Caching HTTP Otomatis
    provideClientHydration(
      withHttpTransferCacheOptions({
        includePostRequests: false
      })
    )
  ]
};
```

### 4. Safe Platform Component (`src/app/product-view.component.ts`)
```typescript
import { 
  Component, 
  OnInit, 
  inject, 
  PLATFORM_ID, 
  signal, 
  makeStateKey, 
  TransferState 
} from '@angular/core';
import { isPlatformBrowser, isPlatformServer } from '@angular/common';
import { HttpClient } from '@angular/common/http';

interface Product {
  id: string;
  name: string;
  price: number;
}

const PRODUCT_KEY = makeStateKey<Product>('product_data_42');

@Component({
  selector: 'app-product-view',
  standalone: true,
  template: `
    <div class="product-container">
      @if (product(); as prod) {
        <h1>{{ prod.name }}</h1>
        <p>Harga: {{ prod.price | currency:'IDR' }}</p>
      } @else {
        <p class="loading">Memuat data produk...</p>
      }

      <div class="metrics">
        Platform: {{ platformName() }}
      </div>
    </div>
  `
})
export class ProductViewComponent implements OnInit {
  private readonly platformId = inject(PLATFORM_ID);
  private readonly http = inject(HttpClient);
  private readonly transferState = inject(TransferState);

  public readonly product = signal<Product | null>(null);
  public readonly platformName = signal<string>('Unknown');

  ngOnInit(): void {
    if (isPlatformServer(this.platformId)) {
      this.platformName.set('Dijalankan di Server (Node.js)');
    } else if (isPlatformBrowser(this.platformId)) {
      this.platformName.set('Dijalankan di Browser Client');
      // Akses window/localStorage aman dilakukan di sini
      console.log('User-Agent Client:', window.navigator.userAgent);
    }

    this.resolveProductData();
  }

  private resolveProductData(): void {
    // 1. Cek apakah state sudah ada di TransferState
    if (this.transferState.hasKey(PRODUCT_KEY)) {
      const cached = this.transferState.get(PRODUCT_KEY, null);
      this.product.set(cached);
      // Hapus key setelah digunakan agar tidak menumpuk di memori client
      this.transferState.remove(PRODUCT_KEY);
      return;
    }

    // 2. Fetch data jika tidak ada cache (misal pada dynamic client-side navigation)
    this.http.get<Product>('https://api.example.com/products/42').subscribe({
      next: (data) => {
        this.product.set(data);
        // Jika berjalan di server, simpan ke TransferState untuk di-serialize ke HTML
        if (isPlatformServer(this.platformId)) {
          this.transferState.set(PRODUCT_KEY, data);
        }
      },
      error: (err) => console.error('Fetch error:', err)
    });
  }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis dari listing kode di Seksi 07:

1. **`app.config.server.ts`:**
   * `provideServerRendering()`: Provider inti yang meregistrasi service internal server seperti renderer berbasis Domino/V8 server engine, context mock token, dan serialization hooks untuk output string HTML.
2. **`app.config.ts`:**
   * `provideClientHydration(...)`: Fungsi bootstrap yang mendaftarkan interceptor hydration pada Angular runtime. Tanpa provider ini, Angular akan fallback ke legacy destructive rendering.
   * `withHttpTransferCacheOptions(...)`: Mengaktifkan HTTP cache sharing otomatis. Setiap request `GET` yang dilakukan oleh `HttpClient` saat berada di server akan langsung di-cache dan disuntikkan ke HTML tanpa perlu memanggil `TransferState` manual untuk tiap service.
   * `withFetch()`: Mengonfigurasi `HttpClient` untuk menggunakan API standar `fetch()` ketimbang `XMLHttpRequest`, yang merupakan syarat wajib performa tinggi di Node.js runtime environment modern.
3. **`product-view.component.ts`:**
   * `makeStateKey<Product>('product_data_42')`: Menghasilkan typed unique key untuk alokasi data di dictionary `TransferState`. Mencegah string mismatch collision antar service.
   * `inject(PLATFORM_ID)`: Mengambil token penanda konteks runtime.
   * `isPlatformServer(this.platformId)` vs `isPlatformBrowser(this.platformId)`: Evaluasi boolean deterministik. Kode di dalam blok `isPlatformBrowser` dijamin tidak akan dieksekusi di Node.js, sehingga mencegah error fatal `ReferenceError: window is not defined` yang dapat menumbangkan process server SSR.
   * `this.transferState.remove(PRODUCT_KEY)`: Manajemen siklus memori client. Membersihkan dictionary state client setelah hydrating selesai untuk menghindari *memory leak* jangka panjang di browser.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Enterprise E-Commerce Platform (Flash Sale Engine)
Sebuah perusahaan e-commerce skala besar menghadapi masalah kritis dengan Single Page Application mereka:
1. **Bounce Rate Tinggi:** Halaman detail produk (PDP) membutuhkan waktu 4.8 detik untuk LCP di koneksi 4G mobile.
2. **SEO Penalty:** Mesin pencari mengindeks halaman dengan harga dan ketersediaan stok yang salah karena eksekusi crawler timeout sebelum dynamic AJAX response selesai.
3. **Double API Bombardment:** Ketika SSR versi awal diterapkan tanpa caching terpadu, database backend kolaps karena menerima *dua kali lipat traffic*: 1 request dari Server SSR saat merender HTML, dan 1 request dari Browser Client yang melakukan bootstrap ulang komponen.

### Solusi Arsitektural:
* Migrasi ke Angular SSR dengan **Non-Destructive Hydration** dan **Selective Prerendering (SSG)** untuk halaman produk katalog statis.
* Implementasi **Distributed In-Memory Transfer State Cache** dan penanganan dynamic live stock updates pasca-hydration.
* Konfigurasi Node.js server menggunakan `@angular/ssr/node` (`CommonEngine`) dengan integrasi reverse-proxy CDN caching (Cloudflare/Fastly via `Cache-Control: s-maxage`).

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi arsitektur enterprise lengkap untuk SSR Server Engine teroptimasi, penanganan Transfer State otomatis, dan selective rendering lifecycle.

### 1. Production Express SSR Engine (`server.ts`)
```typescript
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

  // 1. Static Assets Servicing dengan Caching Agresif (Cache-Control 1 Tahun)
  server.get('*.*', express.static(browserDistFolder, {
    maxAge: '1y',
    index: false,
    immutable: true
  }));

  // 2. Healthcheck Endpoint untuk Kubernetes Liveness / Readiness Probe
  server.get('/healthz', (req: Request, res: Response) => {
    res.status(200).json({ status: 'UP', timestamp: new Date().toISOString() });
  });

  // 3. Dynamic SSR Engine Handler
  server.get('*', (req: Request, res: Response, next: NextFunction) => {
    const { protocol, originalUrl, baseUrl, headers } = req;

    // Tambahkan header caching edge untuk page render
    res.setHeader('Cache-Control', 'public, max-age=60, s-maxage=600, stale-while-revalidate=120');

    commonEngine
      .render({
        bootstrap,
        documentFilePath: indexHtml,
        url: `${protocol}://${headers.host}${originalUrl}`,
        publicPath: browserDistFolder,
        providers: [
          { provide: APP_BASE_HREF, useValue: baseUrl },
          // Inject Request / Response token jika diperlukan oleh dependency injection
          { provide: 'EXPRESS_REQUEST', useValue: req },
          { provide: 'EXPRESS_RESPONSE', useValue: res }
        ],
      })
      .then((html) => res.send(html))
      .catch((err) => {
        // Fallback: Jika server render crash, delegasikan ke client-side index.html kosong
        console.error(`[SSR Critical Crash] URL: ${originalUrl} | Error:`, err);
        res.sendFile(join(browserDistFolder, 'index.html'));
      });
  });

  return server;
}

function run(): void {
  const port = process.env['PORT'] || 4000;
  const server = app();
  server.listen(port, () => {
    console.log(`[Production Server] Angular SSR listening on http://localhost:${port}`);
  });
}

run();
```

### 2. Enterprise Product Detail Component (`src/app/pdp.component.ts`)
```typescript
import { 
  Component, 
  OnInit, 
  inject, 
  signal, 
  PLATFORM_ID 
} from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute } from '@angular/router';
import { Meta, Title } from '@angular/platform-browser';

export interface ProductDetail {
  sku: string;
  title: string;
  description: string;
  stock: number;
  price: number;
  imageUrl: string;
}

@Component({
  selector: 'app-product-detail',
  standalone: true,
  template: `
    <main class="pdp-wrapper">
      @if (product(); as p) {
        <article class="pdp-grid">
          <section class="gallery-col">
            <!-- Prioritaskan image fetching untuk server-rendered HTML via fetchpriority -->
            <img 
              [src]="p.imageUrl" 
              [alt]="p.title"
              width="600" 
              height="600"
              fetchpriority="high"
              loading="eager"
            />
          </section>

          <section class="info-col">
            <h1 class="pdp-title">{{ p.title }}</h1>
            <p class="sku">SKU: {{ p.sku }}</p>
            <div class="pricing">
              <span class="currency">IDR</span>
              <span class="amount">{{ p.price | number:'1.0-0' }}</span>
            </div>

            <div class="inventory-status" [class.out-of-stock]="p.stock <= 0">
              @if (p.stock > 0) {
                <span>Tersedia: {{ p.stock }} unit</span>
              } @else {
                <span>Stok Habis</span>
              }
            </div>

            <!-- Interaktivitas hanya aktif pasca hydration -->
            <button 
              type="button" 
              class="btn-cta" 
              [disabled]="p.stock <= 0"
              (click)="onAddToCart(p)">
              Tambahkan ke Keranjang
            </button>
          </section>
        </article>
      } @else {
        <div class="skeleton-loader" aria-busy="true">
          Mengambil data produk...
        </div>
      }
    </main>
  `,
  styles: [`
    .pdp-wrapper { max-width: 1200px; margin: 0 auto; padding: 2rem; }
    .pdp-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 3rem; }
    .pdp-title { font-size: 2rem; font-weight: 700; }
    .pricing { font-size: 1.5rem; color: #16a34a; font-weight: 600; }
    .out-of-stock { color: #dc2626; font-weight: 600; }
    .btn-cta { background: #2563eb; color: #fff; padding: 1rem 2rem; border: none; cursor: pointer; border-radius: 4px; }
    .btn-cta:disabled { background: #94a3b8; cursor: not-allowed; }
  `]
})
export class ProductDetailComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly http = inject(HttpClient);
  private readonly meta = inject(Meta);
  private readonly title = inject(Title);
  private readonly platformId = inject(PLATFORM_ID);

  public readonly product = signal<ProductDetail | null>(null);

  ngOnInit(): void {
    const sku = this.route.snapshot.paramMap.get('sku') || 'DEFAULT-SKU';
    this.fetchData(sku);
  }

  private fetchData(sku: string): void {
    // Berkat provideClientHydration(withHttpTransferCacheOptions()),
    // panggilan GET ini otomatis ditransfer via ng-state payload tanpa double invocation.
    this.http.get<ProductDetail>(`https://api.enterprise.com/v1/products/${sku}`)
      .subscribe({
        next: (data) => {
          this.product.set(data);
          this.updateSearchEngineMetadata(data);

          // Jika di browser, inisialisasi polling stok real-time via WebSocket/SSE
          if (isPlatformBrowser(this.platformId)) {
            this.initRealtimeStockSync(sku);
          }
        },
        error: (err) => console.error('Gagal mengambil detail produk:', err)
      });
  }

  private updateSearchEngineMetadata(product: ProductDetail): void {
    this.title.setTitle(`${product.title} - Official Enterprise Store`);
    this.meta.updateTag({ name: 'description', content: product.description });
    this.meta.updateTag({ property: 'og:title', content: product.title });
    this.meta.updateTag({ property: 'og:image', content: product.imageUrl });
    this.meta.updateTag({ property: 'og:price:amount', content: product.price.toString() });
    this.meta.updateTag({ property: 'og:price:currency', content: 'IDR' });
  }

  private initRealtimeStockSync(sku: string): void {
    // Mengamankan side-effect browser spesifik
    console.log(`[Browser Only] Mengaktifkan WebSocket stock stream untuk SKU: ${sku}`);
  }

  public onAddToCart(product: ProductDetail): void {
    console.log('Produk berhasil masuk keranjang:', product.sku);
  }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

Memilih antara strategi rendering memerlukan evaluasi multidimensi:

| Karakteristik | Full CSR | On-Demand SSR | Static SSG / Prerender | Hybrid SSR + SSG |
| :--- | :--- | :--- | :--- | :--- |
| **First Contentful Paint (FCP)** | Sangat Lambat (1.5s - 4.5s) | Sangat Cepat (< 0.8s) | Ekstrem Cepat (< 0.3s) | Ekstrem Cepat (< 0.4s) |
| **Time to Interactive (TTI)** | Berbarengan dengan FCP | Sedang (Terdapat gap hydration) | Sedang (Terdapat gap hydration) | Sedang (Terdapat gap hydration) |
| **Beban Infrastruktur Server** | Sangat Rendah (Static File Host) | Sangat Tinggi (Membutuhkan Node/Kube cluster) | Sangat Rendah (Edge CDN) | Rendah (Edge SSG + Selective SSR) |
| **Kompleksitas Kode Sumber** | Rendah (Standard DOM APIs) | Tinggi (Platform-agnostic architecture) | Tinggi (Agnostic + Build-step routes) | Maksimal (Membutuhkan routing taxonomy) |
| **Toleransi Data Dinamis** | Instan (Dynamic by default) | Real-Time (Server evaluates per request) | Buruk (Memerlukan rebuild & deploy) | Sangat Baik (Dynamic routing logic) |
| **Kegagalan Server (Failure Impact)**| 404 dari file host (jarang) | 500 Internal Error menumbangkan website | Minimal (Edge CDN redundansi tinggi) | Terisolasi pada dynamic SSR paths |

### Kapan Memilih SSR Dibanding SSG?
* **Pilih SSG jika:** Data tidak berubah berdasarkan user identity, jumlah URL terbatas dan dapat diprediksi saat build time (contoh: < 5,000 halaman produk atau dokumentasi teknis), dan update data terjadi via deployment pipeline atau webhook build.
* **Pilih SSR jika:** Terdapat jutaan halaman (skala katalog masif yang tidak praktis di-build secara statis), layout bergantung pada geolocation atau cookie pengguna secara langsung, atau data berubah dalam hitungan detik.

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Penggunaan Objek Browser Global di Server
* **Failure Mode:** Mengakses `window`, `document`, `navigator`, atau `localStorage` langsung di lifecycle hook component (seperti `constructor` atau field initializer).
* **Akibat:** `ReferenceError: window is not defined` yang melempar exception fatal dan mematikan eksekusi worker thread Node.js.
* **Mitigasi:**
  * Pindahkan seluruh code execution yang bergantung pada DOM/browser ke dalam hook `afterNextRender()` atau `afterRender()`, yang hanya dieksekusi di platform browser.
  * Gunakan wrapper injection: `inject(DOCUMENT)` alih-alih global `document`.

```typescript
import { Component, afterNextRender } from '@angular/core';

@Component({ standalone: true, template: `...` })
export class SafeCanvasComponent {
  constructor() {
    // AMAN: afterNextRender dijamin HANYA berjalan di Browser
    afterNextRender(() => {
      const width = window.innerWidth;
      console.log('Window width aman diakses:', width);
    });
  }
}
```

### 2. Task Asinkron Tanpa Akhir (Zone.js Stabilization Hang)
* **Failure Mode:** Menjalankan `setInterval()` berulang kali tanpa henti, atau memanggil RxJS stream yang tidak pernah complete (`Subject` tanpa unsubscribing/first).
* **Akibat:** Node.js render engine menunggu kondisi `isStable` dari microtask queue selamanya. Request browser menggantung (*hanging*) hingga terjadi HTTP Gateway Timeout (504).
* **Mitigasi:**
  * Gunakan operator `take(1)` atau `first()` pada HTTP streams.
  * Jalankan asynchronous background loop di luar Angular Zone via `NgZone.runOutsideAngular()`, atau bungkus pemanggilan dalam blok `isPlatformBrowser`.

### 3. Ketidakcocokan Serialization State (State Deserialization Leak)
* **Failure Mode:** Menyimpan object Class kompleks yang memiliki circular dependency atau method prototypes ke dalam `TransferState`.
* **Akibat:** JSON serializer gagal (`TypeError: Converting circular structure to JSON`) atau prototype method hilang saat dibaca di client, menghasilkan error runtime runtime downstream.
* **Mitigasi:** Pastikan payload TransferState murni berupa plain Data Transfer Object (DTO/JSON serializable).

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Mistake 1: Merender Tanggal/Waktu Lokal Menggunakan DatePipe Tanpa Explicit Timezone
* **Penyebab:** Server Express berjalan di server container Alpine Linux dengan default timezone `UTC`. Browser user berada di Jakarta (`UTC+7`).
* **Dampak:** Server menghasilkan string HTML `"10/05/2026, 03:00"`, sedangkan saat hydration di client menghasilkan `"10/05/2026, 10:00"`. Terjadi Hydration DOM Mismatch Warning (NG0500).
* **Solusi:** Selalu definisikan explicit timezone dan locale pada injection token atau pipe parameters:
  ```html
  <!-- BAD -->
  <p>{{ orderDate | date:'short' }}</p>

  <!-- GOOD -->
  <p>{{ orderDate | date:'short':'UTC' }}</p>
  ```

### Mistake 2: Memodifikasi Struktur DOM Secara Direct (Direct DOM Mutation)
* **Penyebab:** Memanggil `ElementRef.nativeElement.appendChild()` atau mengintegrasikan library pihak ketiga seperti jQuery / vanilla dynamic plugins.
* **Dampak:** Hydration node reconciliation algorithm mengalami disorientasi karena tree arsitektur DOM lokal tidak lagi identik dengan virtual DOM mapping compiler Angular.
* **Solusi:** Gunakan manipulasi template deklaratif (`@if`, `@for`, structural directives) atau abstraksi `Renderer2`.

### Mistake 3: Mengabaikan Atribut `ngSkipHydration` Saat Menggunakan Library Third-Party Tak Bersahabat
* **Penyebab:** Mengintegrasikan library charts atau legacy rich-