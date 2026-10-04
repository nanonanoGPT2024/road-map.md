# BAB 08: Testing Strategy, Quality Gates, dan Observability
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Merancang dan Mengimplementasikan Arsitektur Pengujian Boundary-Level**: Mengisolasi dependensi eksternal menggunakan Mock Service Worker (MSW v2) pada level Network Interception (Service Worker API) tanpa melakukan *monkey patching* modul JavaScript.
2. **Mengorkestrasi End-to-End (E2E) Testing Berskala Besar**: Mengonfigurasi Playwright Test Framework dengan *matrix sharding*, *browser context isolation*, *network mocking/routing*, dan *visual regression testing* berbasis threshold toleransi deviasi piksel.
3. **Membangun Automated Quality Gates**: Mengimplementasikan *Mutation Testing* (Stryker) dan *Performance Budget Gates* (Lighthouse CI & Bundlesize) ke dalam pipeline CI/CD modern (GitHub Actions).
4. **Mengimplementasikan End-to-End Frontend Observability**: Mengintegrasikan OpenTelemetry Browser SDK untuk *Distributed Tracing* (W3C TraceContext propagation), melacak Core Web Vitals (INP, LCP, CLS) secara programmatic, serta mengonfigurasi *Error Tracking* berbasis *Source Maps* dan *Session Replay*.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
* **TypeScript Lanjutan**: Generics, Utility Types, Async/Await internals, Promise execution lifecycle.
* **Testing Fundamentals**: Unit testing dan assertions menggunakan Vitest atau Jest.
* **DOM & Browser Internals**: Event Loop, Browser Rendering Pipeline (Layout, Paint, Composite), Service Worker Lifecycle, Web Performance API (`PerformanceObserver`).
* **DevOps & Tooling**: Dasar-dasar GitHub Actions (Workflows, Jobs, Matrix), Docker, dan Node.js runtime environment.

---

### 3. Concept & Internal Architecture

Arsitektur pengujian dan observabilitas modern memandang aplikasi frontend bukan lagi sekadar dokumen statis, melainkan sistem terdistribusi yang berjalan di lingkungan klien yang *untrusted* dan heterogen.

```
+---------------------------------------------------------------------------------------+
|                                    BROWSER RUNTIME                                    |
|                                                                                       |
|   +-------------------+       HTTP/Fetch       +----------------------------------+   |
|   |  UI Components /  | ---------------------> | Service Worker Thread (MSW v2)   |   |
|   |  App State        |                        | Intercepts at Network Boundary   |   |
|   +-------------------+                        +----------------------------------+   |
|             |                                                    |                    |
|             | Telemetry API (DOM Events / Performance)          | Passthrough / Mock |
|             v                                                    v                    |
|   +---------------------------------------+             +------------------+          |
|   | OpenTelemetry Web SDK & Web-Vitals   |             | Backend API /    |          |
|   | - BatchSpanProcessor                  |             | WireMock / Proxy |          |
|   | - W3C TraceContext Injector           |             +------------------+          |
|   +---------------------------------------+                      |                    |
|             |                                                    | Distributed Trace  |
|             | OTLP / JSON via Beacon or Fetch                    v (traceparent)      |
|             v                                           +------------------+          |
|   +---------------------------------------+             | Distributed APM  |          |
|   | Observability Collector / Sentry / RUM| <---------- | (Jaeger / Datadog|          |
|   +---------------------------------------+             +------------------+          |
+---------------------------------------------------------------------------------------+
```

#### A. Network Boundary Mocking (MSW v2 Internals)
Berbeda dengan Jest/Vitest *module mocking* (`vi.mock('axios')`) yang memodifikasi Node module resolution cache, MSW mencegat lalu lintas HTTP/HTTPS pada tingkat sistem operasi browser menggunakan **Service Worker API**. 
* Ketika fetch/XHR dieksekusi, request dialihkan melalui event listener `fetch` di Service Worker thread.
* Service Worker mengirim pesan melalui `BroadcastChannel` atau `MessagePort` ke worker client (aplikasi).
* Jika resolver menangani request tersebut, Service Worker menghasilkan instance `Response` standar WHATWG Fetch API dan mengembalikannya langsung ke rendering engine browser. Jika tidak, request diteruskan (*passthrough*) ke server aktual.
* **Hasil**: Zero-code-modification pada kode produksi; aplikasi beroperasi seolah-olah berkomunikasi dengan server riil.

#### B. Playwright Browser Isolation & Sharding Model
Playwright tidak mengeksekusi tes di dalam instance browser baru untuk setiap file tes karena *cost* overhead proses browser (CPU & memori).
* **Browser Instance** di-spawn sekali per worker process.
* **BrowserContext** (setara dengan profil incognito baru yang memiliki cache, cookies, dan local storage independen) di-instansiasi dalam hitungan milidetik untuk setiap tes terisolasi.
* **Sharding Architecture**: Pipeline CI memecah rangkaian tes menjadi $N$ bagian independen (`--shard=x/N`), memungkinkan orkestrasi paralel lintas worker mesin virtual secara horizontal tanpa dependensi *race condition*.

#### C. Distributed Tracing & W3C TraceContext Propagation
Frontend Observability modern menghubungkan interaksi UI pengguna dengan trace database backend.
1. Saat pengguna memicu aksi (misal: klik "Checkout"), OpenTelemetry Web Tracer membuat **Span** root lokal.
2. HTTP interceptor menambahkan HTTP header standar W3C:
   * `traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`
     *(Version - Trace ID - Parent Span ID - Trace Flags)*
3. Backend service mengekstrak `traceparent`, menjadikannya parent span dari operasi backend, sehingga menghasilkan satu grafik trace terpadu dari *click-to-database*.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional | Enterprise Production Standard |
| :--- | :--- | :--- |
| **API Mocking** | Module/Spy Mocking (`jest.mock`, `sinon.stub`). Mengabaikan deserialisasi network layer & serialization bugs. | **MSW (Mock Service Worker)**. Mencegat di boundary network browser via Service Worker, menguji serializer & HTTP client riil. |
| **E2E Strategy** | Monolithic Selenium/Cypress execution pada single runner. Lambat, sering *flaky*, *retry* berlebihan. | **Playwright Sharded Execution**. Terisolasi via Browser Context, native auto-wait, paralel lintas ephemeral CI nodes. |
| **Visual Testing** | Manual QA checklist atau DOM snapshotting (HTML string comparison yang rapuh). | **Visual Regression Testing (Pixelmatch Engine)**. Perbandingan bitmap kanvas berbasis threshold deviasi anti-aliasing. |
| **Pipeline Gates** | Line coverage semata (`>80%`), rawan *assertion-free tests* (tes lewat tanpa validasi logika). | **Mutation Testing (Stryker)** + **Performance/Bundle Budgets (Lighthouse CI)**. Mengukur kualitas asersi sesungguhnya. |
| **Observability** | `console.error` diarahkan ke log agregator generik tanpa metadata konteks atau trace id. | **OpenTelemetry Web SDK + RUM Core Web Vitals + Sentry Source-Mapped Traces**. |

---

### 5. How (Workflow Detail)

Alur kerja integrasi komprehensif dari fase lokal hingga produksi:

```
[Developer Machine]
       │
       ├─► 1. Pre-Commit Hook (Husky/Lint-Staged): Types, Linting, Unit Test Vitest.
       │
[CI/CD Engine: PR Quality Gate]
       │
       ├─► 2. Build Pipeline: Production artifact generation + Source Map upload (Private S3/Sentry).
       ├─► 3. Mutation Testing: Stryker mengeksekusi mutasi kode pada diff files. Skor > 75%.
       ├─► 4. Bundle Analysis: Validasi batas ukuran chunk JS via @next/bundle-analyzer atau bundlesize.
       ├─► 5. Playwright Matrix Sharded E2E: Menjalankan 4 shard paralel dengan MSW / Staging API.
       ├─► 6. Visual Regression Gate: Membandingkan snapshot screenshot dengan branch base.
       │
[Deployment: Production Runtime]
       │
       ├─► 7. RUM Telemetry Bootstrap: Inisialisasi OpenTelemetry WebTracer & Sentry Error Tracing.
       ├─► 8. Performance Monitoring: PerformanceObserver mengukur LCP, CLS, INP -> OTLP Exporter.
       └─► 9. Distributed Context Injection: Menambahkan traceparent header ke semua outgoing fetch.
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Sistem
* **Unit Test dengan Module Mocking** seperti menguji rem mobil yang dilepas di atas meja kerja mekanik. Anda tahu pedalnya bergerak, tetapi tidak tahu apakah minyak rem bocor saat dipasang ke roda.
* **Component Testing dengan MSW** seperti menguji mobil di atas mesin *dynamometer*. Mesin mobil berjalan, transmisi berputar, sistem hidrolik bekerja, tetapi jalanannya disimulasikan oleh roller berputar.
* **Playwright E2E** seperti melakukan *test drive* di sirkuit pengujian tertutup dengan semua kondisi cuaca disimulasikan secara presisi.
* **Observability (OTel/RUM)** seperti kotak hitam (*Flight Data Recorder*) dan sensor telemetri pesawat komersial yang mengirimkan data performa dan kerusakan secara real-time ke stasiun pusat saat operasi penerbangan aktual.

#### Diagram Interaksi Observability & Context Propagation

```
BROWSER (Client Context)                     BACKEND (Server Context)
========================                     ========================

User Click Event
  │
  ├─► Start OTel Span ("checkout-click")
  │     │
  │     ├─► Capture Web Vitals (INP context)
  │     │
  │     ├─► Inject Trace Context into Headers
  │     │   Headers: {
  │     │     'traceparent': '00-abc1234...-def567-01'
  │     │   }
  │     │
  │     └─► window.fetch('/api/v1/order', { headers })
  │               │
  │               │ (HTTP Request via Internet)
  │               v
  │         [API Gateway] ──────────────────────┐
  │               │                             │
  │               ├─ Extract Trace Context      │
  │               ├─ Continue Root Span         ├─► Jaeger/Tempo
  │               ├─ Database Transaction       │   (Single Distributed
  │               └─ Return JSON 201 Created    │    Trace Waterfall)
  │                      │                      │
  │◄─────────────────────┘                      │
  │                                             │
  ├─► End OTel Span ("checkout-click")          │
  └─► Batch Export Spans via OTLP/HTTP ─────────┘
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: MSW v2 Network Interception Setup

Konfigurasi isolasi network boundary untuk pengujian komponen.

```typescript
// src/mocks/handlers.ts
import { http, HttpResponse } from 'msw';

export interface UserResponse {
  id: string;
  name: string;
  role: 'admin' | 'user';
}

export const handlers = [
  http.get('https://api.enterprise.com/v1/me', () => {
    const mockUser: UserResponse = {
      id: 'usr-88912',
      name: 'Jane Doe',
      role: 'admin',
    };
    return HttpResponse.json(mockUser, { status: 200 });
  }),
];
```

```typescript
// src/mocks/server.ts (Untuk Vitest / Node Environment)
import { setupServer } from 'msw/node';
import { handlers } from './handlers';

export const server = setupServer(...handlers);
```

```typescript
// src/components/UserProfile.test.tsx
import { describe, it, expect, beforeAll, afterEach, afterAll } from 'vitest';
import { render, screen } from '@testing-library/react';
import { server } from '../mocks/server';
import { http, HttpResponse } from 'msw';
import { UserProfile } from './UserProfile';

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('UserProfile Enterprise Component', () => {
  it('berhasil merender data pengguna dari network layer', async () => {
    render(<UserProfile />);
    
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
    expect(await screen.findByRole('heading', { name: /jane doe/i })).toBeInTheDocument();
    expect(screen.getByText(/role: admin/i)).toBeInTheDocument();
  });

  it('menangani skenario HTTP 500 dengan *graceful degradation UI*', async () => {
    // Override handler khusus untuk edge-case pengujian ini
    server.use(
      http.get('https://api.enterprise.com/v1/me', () => {
        return new HttpResponse(null, { status: 500 });
      })
    );

    render(<UserProfile />);
    expect(await screen.findByRole('alert')).toHaveTextContent(/gagal memuat profil/i);
  });
});
```

#### B. Practical Example: Enterprise Playwright E2E Setup with Visual Regression & Custom Fixtures

Implementasi arsitektur E2E berbasis fixture untuk menginjeksi status autentikasi bypass dan perbandingan visual piksel kanvas.

```typescript
// tests/e2e/fixtures/auth.fixture.ts
import { test as base, Page } from '@playwright/test';

type WorkerFixtures = {
  authenticatedPage: Page;
};

export const test = base.extend<{}, WorkerFixtures>({
  authenticatedPage: [
    async ({ browser }, use) => {
      // Inisialisasi BrowserContext terisolasi
      const context = await browser.newContext({
        viewport: { width: 1440, height: 900 },
        storageState: undefined, // Kosongkan initial state
      });

      const page = await context.newPage();

      // Bypass Login UI: Injeksi session JWT langsung ke boundary HTTP / Web Storage
      await page.addInitScript(() => {
        window.localStorage.setItem('auth_token', 'mocked-jwt-token-production-standard');
        window.localStorage.setItem('tenant_id', 'enterprise-corp-01');
      });

      // Mock network call tertentu jika backend dependencies belum tersedia
      await page.route('**/api/v1/features', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ billingV2: true, advancedAnalytics: true }),
        });
      });

      await use(page);

      // Cleanup context setelah tes selesai
      await context.close();
    },
    { scope: 'test' },
  ],
});

export { expect } from '@playwright/test';
```

```typescript
// tests/e2e/specs/dashboard-visual.spec.ts
import { test, expect } from '../fixtures/auth.fixture';

test.describe('Enterprise Dashboard Visual & Functional Integrity', () => {
  test('harus memuat dashboard transaksi dan lolos uji regresi visual', async ({ authenticatedPage: page }) => {
    // Navigasi ke halaman target
    await page.goto('/dashboard/analytics');

    // Auto-wait terhadap network idle dan specific skeleton loader hilang
    await page.waitForSelector('[data-testid="loading-skeleton"]', { state: 'detached' });
    
    const chartCard = page.locator('[data-testid="financial-chart-card"]');
    await expect(chartCard).toBeVisible();

    // Verifikasi data integrity
    await expect(page.locator('[data-testid="total-revenue-value"]')).toHaveText('$1,245,800.00');

    // Visual Regression Testing dengan toleransi anti-aliasing (Pixelmatch Engine)
    await expect(page).toHaveScreenshot('dashboard-analytics-baseline.png', {
      maxDiffPixelRatio: 0.02, // Maksimum toleransi 2% deviasi piksel
      animations: 'disabled', // Nonaktifkan CSS/JS animation guna menghindari flakiness
      mask: [page.locator('[data-testid="realtime-timestamp"]')], // Mask elemen non-deterministik
    });
  });
});
```

#### C. Practical Example: OpenTelemetry Browser SDK & Core Web Vitals Setup

Bootstrap arsitektur observabilitas pada runtime browser klien.

```typescript
// src/observability/tracer.ts
import { WebTracerProvider } from '@opentelemetry/sdk-trace-web';
import { BatchSpanProcessor } from '@opentelemetry/sdk-trace-base';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { Resource } from '@opentelemetry/resources';
import { SemanticResourceAttributes } from '@opentelemetry/semantic-conventions';
import { ZoneContextManager } from '@opentelemetry/context-zone';
import { registerInstrumentations } from '@opentelemetry/instrumentation';
import { FetchInstrumentation } from '@opentelemetry/instrumentation-fetch';

export function initializeTelemetry(): void {
  if (typeof window === 'undefined') return;

  const exporter = new OTLPTraceExporter({
    url: 'https://telemetry-gateway.enterprise.com/v1/traces',
    headers: {
      'x-api-key': 'production-telemetry-token-xyz',
    },
  });

  const provider = new WebTracerProvider({
    resource: new Resource({
      [SemanticResourceAttributes.SERVICE_NAME]: 'corporate-banking-portal',
      [SemanticResourceAttributes.SERVICE_VERSION]: '2.14.0',
      [SemanticResourceAttributes.DEPLOYMENT_ENVIRONMENT]: 'production',
    }),
  });

  // Batch processor mengelompokkan span agar tidak mengganggu performa browser event loop
  provider.addSpanProcessor(
    new BatchSpanProcessor(exporter, {
      maxQueueSize: 250,
      scheduledDelayMillis: 5000,
      exportTimeoutMillis: 10000,
      maxExportBatchSize: 50,
    })
  );

  provider.register({
    contextManager: new ZoneContextManager(),
  });

  // Injeksi otomatis W3C TraceContext ke outgoing HTTP requests
  registerInstrumentations({
    instrumentations: [
      new FetchInstrumentation({
        propagateTraceHeaderCorsUrls: [
          /https:\/\/api\.enterprise\.com\/.*/,
        ],
        clearTimingResources: true,
      }),
    ],
  });
}
```

```typescript
// src/observability/vitals.ts
import { onCLS, onINP, onLCP, Metric } from 'web-vitals';
import { trace, getSpan, context } from '@opentelemetry/api';

const tracer = trace.getTracer('web-vitals-reporter');

function reportMetricToTelemetry(metric: Metric): void {
  const currentSpan = tracer.startSpan(`web_vital_${metric.name.toLowerCase()}`);
  
  currentSpan.setAttributes({
    'vital.name': metric.name,
    'vital.value': metric.value,
    'vital.rating': metric.rating, // 'good' | 'needs-improvement' | 'poor'
    'vital.delta': metric.delta,
    'vital.id': metric.id,
    'vital.navigationType': metric.navigationType,
  });

  // Kirim data dan akhiri span secara instan
  currentSpan.end();
}

export function initWebVitalsReporting(): void {
  // Melacak Interaction to Next Paint (INP), Largest Contentful Paint (LCP), Cumulative Layout Shift (CLS)
  onCLS(reportMetricToTelemetry);
  onINP(reportMetricToTelemetry);
  onLCP(reportMetricToTelemetry);
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: Insiden Keranjang Belanja "Phantom Dropoff" FinTech Global
* **Platform**: Portal Pembayaran & E-Commerce FinTech B2B dengan $120M Monthly GMV.
* **Gejala**: Drop-off checkout melonjak sebesar 8.5% secara mendadak paska rilis versi 4.12.0. Namun, dashboard backend APM mencatat respons API `HTTP 200 OK` tanpa lonjakan error 5xx sama sekali.
* **Investigasi Akar Masalah**:
  1. *E2E Test Gap*: Pengujian E2E eksisting berjalan dengan *headless chromium* pada resolusi desktop statis tanpa validasi layout dinamis dan responsivitas elemen checkout di viewport tablet/ponsel.
  2. *CSS Stacking Context Regression*: Modifikasi pada z-index navbar global menyebabkan modal form pembayaran 3D Secure terhalang oleh transparent overlay tak terlihat (*unclickable DOM layer*).
  3. *Blind Spot Observability*: Sistem hanya mengandalkan Google Analytics dan Sentry console log. User yang tidak bisa menekan tombol checkout tidak menghasilkan error JavaScript, sehingga sistem Sentry diam (*zero exception captured*).

#### Solusi Arsitektural:
1. **Implementasi Quality Gate CI/CD Baru**:
   * Menambahkan **Visual Regression Testing** via Playwright di 3 breakpoint standar (Desktop 1920x1080, Tablet 768x1024, Mobile 375x812) dengan masking elemen timestamp/avatar dinamis.
   * Mengintegrasikan **Mutation Testing (Stryker)**: Memastikan assertion test memvalidasi tombol pembayaran benar-benar `toBeEnabled()` dan `toBeInViewport()`.
2. **Implementasi Observability INP & Synthetic Monitoring**:
   * Mengintegrasikan OpenTelemetry Browser Tracer yang melacak metrik **Interaction to Next Paint (INP)**. Ketika user mengeklik tombol "Bayar", sistem memancarkan custom interaction span. Jika delay input > 500ms atau tombol diklik berulang kali tanpa trigger request (*Rage Clicks*), event dipancarkan otomatis ke collector sebagai anomali performa.
   * Menjalankan Playwright Synthetic Agent di cloud setiap 5 menit yang menguji transaksi end-to-end nyata di staging & canary release.

---

### 9. Trade-offs

| Pendekatan / Teknologi | Trade-off Matrix | Analisis Biaya & Komputasi |
| :--- | :--- | :--- |
| **Playwright Sharded Matrix (CI/CD)** | **Pros**: Mengurangi total build time dari 45 menit menjadi 7 menit.<br>**Cons**: Penggunaan compute hours virtual machine meningkat $N \times$ lipat. | Meningkatkan pengeluaran GitHub Actions / GitLab Runners sebesar ~30-40%, namun memangkas engineering blocked time secara masif. |
| **Visual Regression Testing** | **Pros**: Mencegah bug CSS/UI regressions yang lolos dari DOM assertions.<br>**Cons**: Rawan *false positives* akibat OS font-rendering engine, anti-aliasing GPU, dan update minor browser. | Membutuhkan dependensi Docker container standar (`mcr.microsoft.com/playwright`) dalam CI agar rendering font identik 100%. |
| **Mutation Testing (Stryker)** | **Pros**: Mengeliminasi ilusi "False Confidence" dari standard 100% code coverage.<br>**Cons**: Sangat membebani CPU. Waktu eksekusi dapat mencapai 1-3 jam jika dijalankan di seluruh codebase. | Harus dibatasi hanya berjalan pada *git diff* (PR basis) atau dijalankan terjadwal saat *nightly build*. |
| **Full Browser OTel Tracing** | **Pros**: Visibilitas mutlak dari aksi DOM klien hingga eksekusi query SQL database.<br>**Cons**: Menambah bundle size (~35KB gzipped), potensi membebani network jika *sampling rate* tidak diatur. | Wajib menggunakan *Head-based* atau *Adaptive Sampling* (misal: capture 100% error dan hanya 2-5% sesi sukses di production). |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Flaky E2E Tests Akibat Arbitrary Sleep / Timeout
* **Kesalahan**: Menggunakan `await page.waitForTimeout(5000)` untuk menunggu data selesai dimuat. Jika server lambat 5001ms, tes gagal (*false negative*).
* **Solusi**: Gunakan Playwright Web-First Assertions dan explicit condition waiting:
  ```typescript
  // SALAH
  await page.click('#submit-btn');
  await page.waitForTimeout(3000);
  expect(await page.isVisible('.success-badge')).toBeTruthy();

  // BENAR
  await page.click('#submit-btn');
  await expect(page.locator('.success-badge')).toBeVisible({ timeout: 10000 });
  ```

#### 2. Service Worker Mocking Leakage di Integrasi Vitest / JSDOM
* **Kesalahan**: Menjalankan MSW `setupWorker` di lingkungan JSDOM Node.js. `setupWorker` eksklusif untuk lingkungan peramban aktual.
* **Solusi**: Gunakan `setupServer` dari `msw/node` saat berjalan di vitest/node, dan gunakan `setupWorker` dari `msw/browser` saat dijalankan via Storybook atau browser E2E dev preview.

#### 3. Kebocoran Source Map di Production Environment
* **Kesalahan**: Mengunggah `*.js.map` ke CDN publik agar Sentry dapat memetakan stack trace, yang berakibat pada tereksposnya seluruh proprietary source code TypeScript ke publik.
* **Solusi**: Generate sourcemaps pada saat build, unggah langsung ke artifact storage Sentry melalui CI token, lalu hapus seluruh berkas `*.map` dari build output directory sebelum dideploy ke web server/CDN.

---

### 11. Best Practices (Production Checklist)

1. [ ] **MSW Protocol**: Pastikan parameter `onUnhandledRequest: 'error'` diaktifkan pada unit/integration test suite untuk mencegah request bocor ke internet secara tak sengaja.
2. [ ] **E2E Browser Identity**: Terapkan *Storage State Reusability* pada Playwright guna menghindari pengulangan langkah otentikasi UI (Login form) pada setiap test case.
3. [ ] **Deterministic Clock**: Bekukan waktu (*freeze time*) pada pengujian visual snapshot via `page.clock.setFixedTime()` untuk mencegah perubahan tampilan tanggal dinamis.
4. [ ] **Deterministic Animations**: Nonaktifkan CSS Transitions dan animations (`prefers-reduced-motion`) di tingkat root runner E2E.
5. [ ] **Core Web Vitals Metric Budget**: Tetapkan ambang batas INP < 200ms, LCP < 2.5s, dan CLS < 0.1 di monitoring production.
6. [ ] **OpenTelemetry Trace Sampling**: Konfigurasikan sampling rate telemetri (misal: 5% dari sesi normal, 100% dari trace yang memiliki status HTTP 4xx/5xx).
7. [ ] **Bundle Size Budget CI Gate**: Gagalkan build PR jika base chunk JavaScript bertambah melebihi delta threshold yang diizinkan (misal: max delta +5KB gzip).
8. [ ] **Secure Source Map Management**: Hapus file `.map` dari folder `./dist` setelah proses CI step Sentry Release upload selesai.
9. [ ] **Trace Context Header Whitelisting**: Pastikan konfigurasi `propagateTraceHeaderCorsUrls` pada instrumentation fetch hanya mengirimkan header `traceparent` ke domain internal, hindari pengiriman ke 3rd-party vendors (Analytics/CDN).
10. [ ] **CI Test Parallelization**: Konfigurasi Playwright Sharding (`--shard=$SHARD/$TOTAL`) dalam matriks workflow CI.
11. [ ] **Mutation Score Target**: Tetapkan Mutation Score threshold minimal 70% pada komponen-komponen kritis (Payment, Authentication, Data Calculations).
12. [ ] **Synthetic Heartbeat**: Jalankan monitoring browser sintetis minimal tiap 5 menit sekali pada critical paths (Checkout, Registration, Transfer).

---

### 12. Hands-on Practice

Berikut panduan langkah demi langkah untuk mengonfigurasi arsitektur testing modern dan quality gate pada project lokal.

#### Struktur Direktori Target
```
hands-on/m02/
├── .github/
│   └── workflows/
│       └── quality-gate.yml
├── src/
│   ├── components/
│   │   ├── CheckoutButton.tsx
│   │   └── CheckoutButton.test.tsx
│   ├── mocks/
│   │   ├── handlers.ts
│   │   └── server.ts
│   └── observability/
│       └── vitals.ts
├── tests/
│   └── e2e/
│       ├── fixtures.ts
│       └── checkout.spec.ts
├── playwright.config.ts
├── stryker.config.json
├── package.json
└── tsconfig.json
```

#### Langkah 1: Inisialisasi Dependensi Enterprise Testing & Observability
Buka terminal dan jalankan instalasi paket-paket berikut di folder `hands-on/m02/`:

```bash
mkdir -p hands-on/m02
cd hands-on/m02
npm init -y

# Install Core & TypeScript
npm install react react-dom
npm install -D typescript @types/react @types/react-dom

# Install MSW, Vitest, Testing Library
npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom msw@latest

# Install Playwright
npm install -D @playwright/test
npx playwright install --with-deps chromium

# Install Stryker Mutator
npm install -D @stryker-mutator/core @stryker-mutator/vitest-runner

# Install Observability SDKs
npm install web-vitals @opentelemetry/api @opentelemetry/sdk-trace-web @opentelemetry/instrumentation-fetch
```

#### Langkah 2: Setup Konfigurasi Playwright
Buat berkas `playwright.config.ts`:

```typescript
// hands-on/m02/playwright.config.ts
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30 * 1000,
  expect: {
    timeout: 5000,
    toHaveScreenshot: { maxDiffPixelRatio: 0.01 },
  },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: [['html'], ['list']],
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'Desktop Chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
```

#### Langkah 3: Setup Konfigurasi Stryker Mutation Testing
Buat berkas `stryker.config.json`:

```json
{
  "$schema": "https://raw.githubusercontent.com/stryker-mutator/stryker-js/master/packages/core/schema/stryker-schema.json",
  "packageManager": "npm",
  "reporters": ["html", "clear-text", "progress"],
  "testRunner": "vitest",
  "coverageAnalysis": "perTest",
  "mutate": [
    "src/components/**/*.ts?(x)",
    "!src/**/*.test.ts?(x)",
    "!src/mocks/**"
  ],
  "thresholds": {
    "high": 80,
    "low": 60,
    "break": 70
  }
}
```

#### Langkah 4: Setup Komponen Kritis & Unit/Boundary Test
Buat berkas `src/components/CheckoutButton.tsx`:

```tsx
// hands-on/m02/src/components/CheckoutButton.tsx
import React, { useState } from 'react';

interface CheckoutButtonProps {
  amount: number;
  onSuccess: (transactionId: string) => void;
}

export const CheckoutButton: React.FC<CheckoutButtonProps> = ({ amount, onSuccess }) => {
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCheckout = async () => {
    // Validasi input mutasi
    if (amount <= 0) {
      setError('Invalid Amount');
      return;
    }

    setIsProcessing(true);
    setError(null);

    try {
      const response = await fetch('/api/v1/charge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ amount }),
      });

      if (!response.ok) {
        throw new Error('Payment Failed');
      }

      const data = await response.json();
      onSuccess(data.transactionId);
    } catch (err: any) {
      setError(err.message || 'Unknown Error');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div>
      <button 
        data-testid="checkout-button"
        disabled={isProcessing} 
        onClick={handleCheckout}
      >
        {isProcessing ? 'Processing...' : `Pay $${amount}`}
      </button>
      {error && <p data-testid="error-message" role="alert">{error}</p>}
    </div>
  );
};
```

Buat handler mocking pada `src/mocks/handlers.ts`:

```typescript
// hands-on/m02/src/mocks/handlers.ts
import { http, HttpResponse } from 'msw';

export const handlers = [
  http.post('/api/v1/charge', async ({ request }) => {
    const body = (await request.json()) as { amount: number };
    if (body.amount > 10000) {
      return HttpResponse.json({ error: 'Limit Exceeded' }, { status: 422 });
    }
    return HttpResponse.json({ transactionId: 'tx-mock-998231' }, { status: 200 });
  }),
];
```

Buat berkas tes `src/components/CheckoutButton.test.tsx`:

```tsx
// hands-on/m02/src/components/CheckoutButton.test.tsx
import { describe, it, expect, vi, beforeAll, afterEach, afterAll } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { setupServer } from 'msw/node';
import { handlers } from '../mocks/handlers';
import { CheckoutButton } from './CheckoutButton';

const server = setupServer(...handlers);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('CheckoutButton Component Mutation-Proof Suite', () => {
  it('berhasil memproses pembayaran dan memanggil onSuccess', async () => {
    const handleSuccess = vi.fn();
    render(<CheckoutButton amount={500} onSuccess={handleSuccess} />);

    const btn = screen.getByTestId('checkout-button');
    expect(btn).toHaveTextContent('Pay $500');

    fireEvent.click(btn);

    expect(btn).toBeDisabled();
    expect(btn).toHaveTextContent('Processing...');

    await waitFor(() => {
      expect(handleSuccess).toHaveBeenCalledWith('tx-mock-998231');
    });

    expect(btn).toBeEnabled();
  });

  it('menghentikan eksekusi jika nilai amount <= 0', async () => {
    const handleSuccess = vi.fn();
    render(<CheckoutButton amount={-10} onSuccess={handleSuccess} />);

    fireEvent.click(screen.getByTestId('checkout-button'));

    expect(await screen.findByTestId('error-message')).toHaveTextContent('Invalid Amount');
    expect(handleSuccess).not.toHaveBeenCalled();
  });
});
```

#### Langkah 5: CI Quality Gate Workflow Script
Buat file CI GitHub Actions pada `.github/workflows/quality-gate.yml`:

```yaml
name: Enterprise Frontend Quality Gate

on:
  pull_request:
    branches: [main]

jobs:
  test-and-mutate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'npm'

      - name: Install Dependencies
        run: npm ci

      - name: Run Vitest Unit & Boundary Tests
        run: npx vitest run --coverage

      - name: Execute Mutation Testing (Stryker)
        run: npx stryker run

  playwright-e2e-matrix:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        shardIndex: [1, 2]
        shardTotal: [2]
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'npm'

      - name: Install Dependencies
        run: npm ci

      - name: Install Playwright Browsers
        run: npx playwright install --with-deps chromium

      - name: Run E2E Sharded Tests
        run: npx playwright test --shard=${{ matrix.shardIndex }}/${{ matrix.shardTotal }}

      - name: Upload Playwright Blob Report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-report-shard-${{ matrix.shardIndex }}
          path: blob-report/
          retention-days: 7
```

---

### 13. Exercise

#### Level Easy
Konfigurasikan mock handler MSW v2 yang mencegat query parameter `?status=pending` pada endpoint `/api/v1/orders`. Pastikan handler mengembalikan HTTP 200 dengan struktur array kosong jika query tersebut ada, dan HTTP 400 jika query tidak disertakan. Tuliskan satu unit test assertion untuk memvalidasi skenario tersebut.

#### Level Medium
Buat sebuah custom Playwright fixture bernama `consoleErrorTracker` yang otomatis mendengarkan event peramban `page.on('console')` dan `page.on('pageerror')`. Pastikan setiap test runner yang menggunakan fixture ini otomatis gagal (*fail the test*) jika ada `console.error` yang tidak sengaja tertembak ke browser console selama interaksi pengguna berlangsung.

#### Level Hard
Rancang modul pelacak metrik interaksi kustom bernama `trackLongTaskWithContext()`. Modul ini harus:
1. Memanfaatkan `PerformanceObserver` browser untuk membaca entry `longtask`.
2. Mengambil active span id OpenTelemetry yang sedang berjalan di memory context.
3. Menciptakan span baru yang menautkan (*links*) konteks aktif ke durasi blocking task tersebut, lengkap dengan atribusi container/DOM yang memicunya.

---

### 14. Challenge

**Skenario**: Anda memimpin tim core platform di institusi perbankan yang mengelola aplikasi web Multi-Tenant Micro-Frontend (MFE). Arsitektur terdiri dari Shell Host dan 5 Remote MFE (Account, Transfer, Card, Lending, Settings).
* **Kendala**: Tim QA sering mengeluhkan pengujian integrasi E2E yang sering *timeout* (flaky) akibat microservice backend staging yang tidak stabil. Di saat yang sama, tim Security melarang keras injeksi test token jangka panjang pada production canary release.
* **Tantangan Arsitektur**:
  1. Rancang arsitektur pengujian hibrida (Contract Testing + Playwright + MSW) di mana MFE Remote dapat diuji secara independen tanpa bergantung pada keberadaan host Shell ataupun backend nyata, namun tetap menjamin validitas payload JSON schema backend.
  2. Implementasikan observabilitas terdistribusi (Distributed Tracing) yang mampu menembus batasan `iframe` atau Web Components (Shadow DOM) yang diisolasi oleh sandbox sekuritas perbankan, menyatukan seluruh lifecycle klik pengguna hingga respon sub-service MFE ke dalam satu Trace ID OpenTelemetry yang koheren.
  3. Sajikan dokumen arsitektur teknis lengkap berupa alur quality gate, strategi sharding E2E pipeline, penanganan deterministik data state, dan mitigasi tracing payload overhead.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic Questions
1. **Apa perbedaan teknis mendasar antara memodifikasi response menggunakan `vi.spyOn(global, 'fetch')` vs Mock Service Worker (MSW)?**
   * *Jawaban*: `vi.spyOn` melakukan monkey patching pada objek runtime JavaScript di environment pengujian dan mengabaikan interaksi jaringan browser yang sebenarnya. Sementara MSW beroperasi pada level Network Boundary menggunakan Service Worker thread (WHATWG Fetch standards), menguji fungsionalitas fetcher, transformer header, cookie serialization, dan parsing stream persis seperti di lingkungan produksi.
2. **Mengapa Playwright BrowserContext jauh lebih efisien dibandingkan membuat Browser Instance baru untuk setiap file test?**
   * *Jawaban*: Browser Instance memerlukan spawning proses sistem operasi baru yang mahal dari segi CPU dan alokasi memori. BrowserContext hanyalah isolasi sesi logis (setara dengan sesi Incognito) di dalam proses browser yang sama, sehingga instansiasi berlangsung dalam hitungan milidetik dengan isolasi cache, cookie, dan storage yang tetap absolut.
3. **Apa kegunaan utama header HTTP `traceparent` dalam standar W3C Distributed Tracing?**
   * *Jawaban*: Untuk meneruskan konteks trace ID dan parent span ID dari klien browser ke server downstream. Hal ini memungkinkan APM mengkorelasikan operasi frontend (klik, render) dan operasi backend (query DB, panggilan microservice) ke dalam satu waterfall trace yang terpadu.
4. **Apa yang diukur oleh Mutation Testing (seperti Stryker) yang tidak dapat diukur oleh kalkulasi Line Coverage tradisional?**
   * *Jawaban*: Mutation testing mengukur efektivitas dan kualitas logika assertions di dalam tes dengan cara sengaja menyisipkan bug (mutasi). Line coverage hanya membuktikan bahwa suatu baris kode pernah dieksekusi, bukan membuktikan bahwa assertions dalam tes mampu mendeteksi kesalahan jika baris tersebut rusak.
5. **Mengapa masking elemen (seperti timestamp dinamis) sangat krusial dalam Visual Regression Testing?**
   * *Jawaban*: Karena timestamp, angka acak, atau animasi adalah elemen non-deterministik yang akan selalu menghasilkan perbedaan piksel (pixel mismatch) pada setiap run, yang menyebabkan pengujian visual gagal secara keliru (*false positive*).

#### Intermediate Questions
1. **Bagaimana cara mencegah memory leak saat menggunakan OpenTelemetry Web SDK dengan `BatchSpanProcessor` pada SPA (Single Page Application)?**
   * *Jawaban*: Pastikan buffer queue dibatasi (`maxQueueSize`), delay transmisi disesuaikan (`scheduledDelayMillis`), implementasikan graceful shutdown handler pada event `beforeunload` atau `pagehide` menggunakan API `provider.shutdown()`, dan pastikan navigasi routing tidak mendaftarkan interceptor ganda pada objek window yang sama.
2. **Jika sebuah pipeline Playwright dijalankan dengan parameter `--shard=3/8`, apa yang sebenarnya dilakukan oleh test runner?**
   * *Jawaban*: Test runner menghitung seluruh file tes yang ada, membaginya ke dalam 8 subset yang seragam secara deterministik, dan worker tersebut hanya mengeksekusi subset bagian ke-3 dari total 8 bagian.
3. **Mengapa CSS transitions atau web animations harus di-disabled saat mengeksekusi visual snapshot testing di CI?**
   * *Jawaban*: Karena waktu rendering animasi bergantung pada clock hardware dan performa CPU virtual machine CI. Mengambil screenshot di tengah-tengah frame animasi yang belum rampung menghasilkan ketidakkonsistenan frame tangkapan (*flakiness*).
4. **Apa implikasi performa browser terhadap pengumpulan metrik Web Vital `Interaction to Next Paint` (INP) secara programmatic?**
   * *Jawaban*: Pengumpulan INP via Web Vitals SDK menggunakan `PerformanceObserver` pasif yang ditenagai oleh background engine browser. Overhead komputasi JavaScript-nya sangat rendah dan tidak memblokir main thread, asalkan pelaporan datanya tidak melakukan blocking HTTP POST melainkan menggunakan `navigator.sendBeacon` atau `BatchSpanProcessor`.
5. **Bagaimana cara menangani pengujian integrasi komponen yang bergantung pada LocalStorage tanpa mengotori status test suite lainnya di Vitest?**
   * *Jawaban*: Gunakan lifecycle hook `beforeEach` dan `afterEach` untuk mengeksekusi `window.localStorage.clear()`, atau bungkus penyimpanan storage menggunakan abstraction provider yang dapat diinjeksi (*Dependency Injection*) dengan mock in-memory storage per test context.

#### Skenario Kasus Produksi
1. **Skenario 1**: Tim Anda merilis fitur baru dan CI Pipeline menyatakan 100% test lulus. Namun pada rilis canary, beberapa pengguna mengeluhkan tombol submit formulir tidak melakukan apa pun. Setelah diinvestigasi, ada perubahan kode dari `onClick={handleSubmit}` menjadi `onClick={handleSubmit()}` yang menyebabkan handler dieksekusi saat render, bukan saat diklik. Tes unit lolos karena test suite hanya memverifikasi keberadaan elemen tanpa menyimulasikan interaksi klik pengguna. **Bagaimana Anda mendesain Quality Gate untuk mencegah pola kegagalan ini terulang?**
   * *Solusi*: Terapkan Mutation Testing (Stryker) di PR Gate. Stryker akan memutasi return statement handler atau menghapus binding click. Jika tidak ada test yang memanggil `fireEvent.click()` atau `userEvent.click()` dan memvalidasi efek sampingnya, mutant akan berstatus *Survived* dan skor mutation testing akan anjlok di bawah threshold break (misal: < 70%), yang secara otomatis memblokir merger PR.
2. **Skenario 2**: Pengujian Visual Regression di lingkungan lokal developer (macOS) selalu lolos, namun ketika dieksekusi di GitHub Actions runner (Ubuntu Linux), tes selalu gagal dengan perbedaan 1.2% piksel pada semua teks font tipografi. **Apa akar masalahnya dan bagaimana arsitektur CI harus diperbaiki?**
   * *Solusi*: Akar masalahnya adalah perbedaan font anti-aliasing dan text rasterization engine antara CoreText (macOS) dan FreeType (Linux). Solusinya: Jangan pernah menghasilkan *baseline golden screenshot* di mesin lokal non-standar. Jalankan pengujian visual di dalam container Docker resmi yang terstandarisasi (`mcr.microsoft.com/playwright`) baik di lokal maupun di CI, sehingga rendering environment 100% identik bit-by-bit.
3. **Skenario 3**: Trace OpenTelemetry frontend berhasil terkirim ke collector, namun saat dicek di distributed tracing dashboard (Grafana Tempo / Jaeger), trace dari frontend terpisah sebagai trace baru dan tidak menyatu dengan trace backend API Gateway. **Langkah diagnostik teknis apa yang harus Anda lakukan untuk memulihkan unified distributed trace?**
   * *Solusi*: Lakukan pengecekan pada tiga titik: (1) Verifikasi bahwa `FetchInstrumentation` di browser mengonfigurasi `propagateTraceHeaderCorsUrls` dengan regex yang cocok dengan origin API Gateway. (2) Pastikan server backend / API Gateway telah mengaktifkan CORS header `Access-Control-Allow-Headers: traceparent, tracestate`. Jika tidak, browser akan memblokir outgoing request atau melucuti header tersebut pada CORS preflight. (3) Pastikan middleware distributed tracing backend mengekstrak context menggunakan W3C TraceContext Propagator bukan B3 atau Jaeger propagation format lawas.

---

### 16. Summary

1. **Network Boundary Interception (MSW)** adalah fondasi pengujian integrasi frontend modern, mengeliminasi kerapuhan *module mocking* dan memastikan HTTP client menguji alur serialisasi, headers, dan status response nyata.
2. **Playwright E2E Sharding & Fixture Pattern** memungkinkan orkestrasi ribuan skenario browser secara paralel tanpa isolasi kompromi, memotong drastis durasi runtime CI pipeline enterprise.
3. **Visual Regression Testing** menutup celah lolosnya degradasi tampilan visual (CSS context/layout shifting) yang tidak dapat dideteksi oleh assertion DOM tekstual tradisional.
4. **Mutation Testing** mengubah paradigma metrik kualitas dari kuantitas pasif (*Code Coverage*) menjadi kualitas asersi aktif (*Mutation Score*), mencegah *false sense of security*.
5. **Frontend Observability Terpadu** menggabungkan OpenTelemetry Distributed Tracing (W3C context), pelacakan Core Web Vitals (INP, LCP, CLS), dan Source-Mapped Error Tracking ke dalam satu sistem telemetri terintegrasi untuk visibilitas holistik dari browser klien hingga infrastruktur backend.