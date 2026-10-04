# Kurikulum Enterprise Next.js: Arsitektur Produksi & Rekayasa Perangkat Lunak Modern

* **Topik:** Next.js (Kategori: 03-Frontend-and-Mobile)
* **Bab 09:** Strategi Pengujian End-to-End dan Automasi CI/CD
* **Modul 02:** Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik pada tingkat Staff/Principal Engineer diharapkan mampu:

1. **Mendesain Arsitektur Pengujian E2E Terdistribusi:** Mengorkestrasi pipeline Playwright *sharding* multi-runner yang mampu memotong waktu eksekusi uji regresi dari 45+ menit menjadi < 6 menit secara deterministik.
2. **Mengisolasi & Memvalidasi Primitif App Router:** Menguji karakteristik unik React Server Components (RSC) payload streaming, batas Suspense (`loading.tsx`), *optimistic updates*, dan mutasi Server Actions di bawah kondisi jaringan terdegradasi (*chaos network testing*).
3. **Membangun Strategi Ephemeral Environments & Database Branching:** Mengintegrasikan *preview deployment* berbasis kontainer (Docker/Kubernetes) atau Edge dengan skema *database branching* terisolasi per pull request (PR).
4. **Mengimplementasikan Visual Regression & Contract Validation:** Membangun *zero-flakiness visual testing engine* menggunakan Playwright Snapshot Testing dengan kontrol *font rendering*, animasi deterministik, dan toleransi delta piksel berbasis sub-pixel antialiasing.
5. **Menyusun Enterprise CI/CD Pipeline:** Mengonfigurasi GitHub Actions production-grade dengan Turborepo *remote caching*, Playwright artifact sharding merge report, security policy OIDC AWS/GCP, dan *dynamic smoke-testing canary validation*.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:

* **Next.js App Router Internals:** Pemahaman mendalam tentang siklus hidup RSC vs. Client Components, format serialisasi Flight RPC (`text/x-component`), dan header mutasi Server Actions (`Next-Action`).
* **Playwright Fundamentals:** Pemahaman *locators*, *fixtures*, *storageState*, *tracing*, dan *page context isolation*.
* **Modern CI/CD Engineering:** GitHub Actions (matrix, composite actions, caching, OIDC), Docker multi-stage builds, dan orkestrasi kontainer.
* **Database & State Lifecycle:** PostgreSQL migration cycle, transactional testing, dan skema *branching* (misal: Neon/Supabase/Prisma/Drizzle).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Anatomi Runtime App Router & Implikasinya pada E2E Testing

Pengujian E2E pada Next.js App Router berbeda secara fundamental dibandingkan Pages Router atau SPA konvensional. Pada App Router, terdapat pembagian eksekusi antara Node.js/Edge Runtime (Server Components) dan V8 Browser Runtime (Client Components).

```
[Browser Context]                                [Next.js App Router Server]
       |                                                      |
       |--- 1. HTTP GET /dashboard -------------------------->|
       |                                                      |-- Render RootLayout (RSC)
       |                                                      |-- Stream Suspense Boundary 1 (HTML skeleton)
       |<-- 2. Chunk 1: Transfer-Encoding: Chunked (HTML) ----|
       |       [Paint Skeleton UI]                            |-- Fetch Remote API/DB
       |                                                      |-- Render DashboardContent (RSC)
       |<-- 3. Chunk 2: RSC Flight Payload (JSON-like stream)-|
       |       [Resolve Hydration Boundary]                   |
       |                                                      |
       |--- 4. Invoke Server Action (POST + Next-Action ID) ->|
       |       [Optimistic UI applied in DOM]                 |-- Execute Action Logic
       |                                                      |-- revalidatePath('/dashboard')
       |<-- 5. Updated Flight Data Stream -------------------|
       |       [Commit Real Data to DOM]                      |
```

Ketika Playwright mengeksekusi assertion seperti `await expect(page.locator('.user-card')).toBeVisible()`, runner tidak hanya menunggu DOM paint, tetapi juga bergantung pada penyelesaian:

1. **RSC Flight Stream Resolution:** Server mengirimkan payload serialisasi React Flight secara inkremental melalui HTTP *chunked transfer*. Intersepsi mock network browser tidak dapat menangkap panggilan database yang dilakukan di dalam RSC secara langsung tanpa Node-level mocking (MSW Node) atau database seeding.
2. **Hydration Phase Lag:** HTML statis mungkin sudah muncul di DOM (*Fast First Contentful Paint*), tetapi event listener Client Component belum terpasang (*Time to Interactive delay*). Klik yang dilakukan Playwright pada milidetik transisi ini dapat menyebabkan *dropped events* jika tidak menggunakan mekanisme penanganan kesiapan hidrasi yang deterministik.
3. **Server Action ID Hashing:** Server Actions dieksekusi melalui endpoint POST internal dengan header unik `next-action: <hash>`. Hash ini di-generate pada saat build (`next build`). Menjalankan pengujian E2E pada environment staging/production harus memperhitungkan ketidakcocokan build artifact (*skew protection*).

### 3.2 Topologi CI/CD Matrix Sharding Enterprise

Dalam skala enterprise dengan ribuan skenario E2E, menjalankan pengujian secara sekuensial adalah anti-pattern. Kita menerapkan *horizontal sharding* berbasis hardware matrix runners:

```
[GitHub Actions Orchestrator: Push / PR]
                   |
       +-----------+-----------+
       |   Turborepo Change    | (Halt if no frontend/backend impact)
       |     Detection         |
       +-----------+-----------+
                   |
     [Build Once: Next.js Artifact]
     [Push Ephemeral Preview Image]
                   |
  +----------------+----------------+----------------+
  |                                 |                                 |
[Runner 1/4]                      [Runner 2/4]                      [Runner 3/4]                      [Runner 4/4]
Playwright Shard 1/4              Playwright Shard 2/4              Playwright Shard 3/4              Playwright Shard 4/4
- Tests A-G                       - Tests H-N                       - Tests O-U                       - Tests V-Z
- DB Schema: pr_42_shard_1        - DB Schema: pr_42_shard_2        - DB Schema: pr_42_shard_3        - DB Schema: pr_42_shard_4
  |                                 |                                 |                                 |
  +----------------+----------------+----------------+----------------+
                   |
       [Merge Blobs / Reports]
       [Generate Unified Playwright HTML]
                   |
       [Visual Diff Assertion (Percy/Playwright)]
                   |
      +------------+------------+
      | Fail:                   | Pass:
      v                         v
[Block Merge + Upload Traces] [Allow Merge + Canary Promotion]
```

---

## 4. Why & What

| Dimensi | Pendekatan Tradisional (Naive E2E) | Pendekatan Enterprise Modern |
| :--- | :--- | :--- |
| **Testing Target** | Environment Staging Statis monolitik (sering *out-of-sync* & *state collision*). | **Isolated Ephemeral Environments** atau **Branching Databases per-PR**. |
| **RSC & Data Flow** | Menganggap aplikasi sebagai SPA hitam; sering gagal karena hidrasi *race condition*. | Memahami siklus **Flight Payload Serialisation**, memvalidasi fallback Suspense secara eksplisit. |
| **Waktu CI** | Eksekusi sekuensial/paralel lokal; bottleneck CPU 1 runner (Durasi: 40-60 menit). | **Matrix Sharding lintas N-runner** terdistribusi dengan Turborepo caching (Durasi: < 7 menit). |
| **Data Seeding** | Hardcoded user fixtures di shared staging database (Rawan race condition). | **Transactional isolation** / API dynamic factories dengan auto-cleanup berbasis workers. |
| **Flakiness Handling**| Menambahkan `page.waitForTimeout(5000)` (Anti-pattern perusak performa). | **Custom assertions**, `waitForResponse` filtering pada Action ID, dan auto-retrying web assertions. |
| **Visual Validation**| Mengabaikan layout visual atau mengandalkan QA manual. | **Pixel-perfect deterministic diffing** dengan font smoothing, fixed viewport, & anti-aliasing masks. |

---

## 5. How (Workflow Detail)

1. **Trigger & Cache Invalidation:** PR dibuka. Turborepo mengevaluasi dependensi kode melalui hash git commit. Jika direktori frontend atau API contracts tidak berubah, workflow E2E dibatalkan (*skip*).
2. **Deterministic App Build:** Aplikasi di-build sekali (`next build`) menggunakan target standalone. Node runtime dikunci via `.nvmrc` dan *frozen lockfile*.
3. **Database Branching Provisioning:** CI memanggil API database (misal: Neon/Supabase/Containerized Postgres) untuk membuat cabang (*branch*) skema ephemeral baru yang diturunkan dari *main migration state*.
4. **Auth State Pre-generation:** Runner CI melakukan bypass login form via programmatic API request, menangani enkripsi sesi (NextAuth/Iron Session JWT), dan menyimpan file `storageState.json` untuk dikonsumsi oleh seluruh browser contexts.
5. **Distributed Sharding Execution:** Playwright membagi seluruh test suite menjadi $N$ potongan (`--shard=X/N`). Setiap shard berjalan di runner CI independen dengan pelaporan trace, video kegagalan, dan metrik network.
6. **Artifact Collation & Reporting:** Blob reports dari $N$ runner dikirim ke artifact storage CI, digabungkan menggunakan `@playwright/test merge-reports`, dan dipublikasikan ke GitHub Pages atau internal static bucket.
7. **Teardown:** Database branch dihancurkan, session cache dibersihkan, dan status checks dilaporkan ke branch protection rule GitHub.

---

## 6. Analogy & Diagram ASCII

### Analogi Ruang Uji Dirgantara
Bayangkan menguji performa pesawat jet komersial baru.
* **Unit Testing:** Menguji apakah satu baut atau bilah turbin tahan terhadap panas di laboratorium terisolasi.
* **Integration Testing:** Menguji apakah gearbox terhubung dengan benar ke poros turbin.
* **Naive E2E Testing:** Menerbangkan pesawat langsung ke badai sungguhan dengan penumpang acak, tanpa alat perekam data; jika terjadi turbulensi, Anda tidak tahu sensor mana yang gagal.
* **Enterprise E2E Testing (Modul ini):** Memasukkan pesawat lengkap ke dalam wind tunnel supersonik (*Isolated Ephemeral Environment*) dengan simulator penerbangan digital (*Deterministic Network/Mocking*), sensor telemetri di 10.000 titik (*Playwright Tracing & RSC stream sniffing*), dan pengujian otomatis pada 16 komponen pesawat secara paralel di bawah beban gravitasi ekstrem (*Matrix Sharding*).

### Siklus Intersepsi Network Playwright vs. RSC Architecture

```
+--------------------------------------------------------------------------------+
| Host Environment (CI Runner / Container)                                       |
|                                                                                |
|  [Playwright Test Worker (Node.js Process)]                                    |
|         |                                                                      |
|         |-- (A) Direct Node API Call: Seed Database Branch                     |
|         |-- (B) Inject Auth Cookies / Session Claims via StorageState           |
|         v                                                                      |
|  [Chromium Browser Context]                                                    |
|     |                                                                          |
|     |-- Request: GET /orders ------------------------------------+             |
|     |   (Intercepted by page.route() if client-side fetch)       |             |
|     |                                                            v             |
|     |                                              [Next.js Server Process]    |
|     |                                              - Execute Layout (RSC)      |
|     |                                              - Node.js fetch() to DB/CMS |
|     |                                                *CANNOT be intercepted*   |
|     |                                                *by page.route()!*        |
|     |                                              - Stream Flight Payload     |
|     |                                                            |             |
|     |<-- Chunked Response (Flight Data) <------------------------+             |
|     |                                                                          |
|     |-- Trigger Server Action (POST) with X-Action-ID                           |
|     |   (Interceptable via page.waitForResponse matching action header)        |
|     v                                                                          |
|  [Assert DOM Mutations + Network Telemetry Validated]                          |
+--------------------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Menguji Transisi Suspense & RSC Streaming

Uji sederhana ini memverifikasi bahwa *loading skeleton* benar-benar muncul sebelum data server berhasil di-resolve dan dirender ke dalam DOM.

```typescript
// tests/e2e/streaming.spec.ts
import { test, expect } from '@playwright/test';

test.describe('RSC Streaming & Suspense Boundary', () => {
  test('harus menampilkan fallback loading sebelum data analitik selesai di-stream', async ({ page }) => {
    // Memperlambat respons upstream khusus untuk rute simulasi jika diperlukan
    // Navigasi ke halaman dengan RSC Suspense
    await page.goto('/analytics', { waitUntil: 'commit' });

    // Assert skeleton loading terlihat segera setelah initial commit HTML
    const skeleton = page.getByTestId('analytics-skeleton');
    await expect(skeleton).toBeVisible();

    // Assert data riil telah menggantikan skeleton setelah streaming payload selesai
    const realDataChart = page.getByTestId('analytics-chart');
    await expect(realDataChart).toBeVisible({ timeout: 10_000 });

    // Verifikasi skeleton telah dihapus dari pohon DOM
    await expect(skeleton).not.toBeVisible();
  });
});
```

---

### 7.2 Practical Example: Enterprise Multi-Tier E2E Architecture

Berikut adalah implementasi standar produksi yang mencakup: Custom Fixture, Dynamic Context Seeding, Intersepsi Server Actions, Visual Regression Masking, dan Pipeline GitHub Actions Matrix Sharding.

#### Struktur Direktori Modul
```text
e2e/
├── fixtures/
│   ├── auth.fixture.ts
│   └── database.fixture.ts
├── helpers/
│   └── server-actions.ts
├── specs/
│   ├── checkout.spec.ts
│   └── visual-regression.spec.ts
playwright.config.ts
.github/
└── workflows/
    └── e2e-matrix.yml
```

#### A. Playwright Configuration (`playwright.config.ts`)

```typescript
import { defineConfig, devices } from '@playwright/test';

const isCI = !!process.env.CI;

export default defineConfig({
  testDir: './e2e/specs',
  timeout: 45_000,
  expect: {
    timeout: 7_000,
    toHaveScreenshot: {
      maxDiffPixelRatio: 0.02,
      animations: 'disabled',
    },
  },
  fullyParallel: true,
  forbidOnly: isCI,
  retries: isCI ? 2 : 0,
  workers: isCI ? '100%' : '50%',
  reporter: isCI
    ? [
        ['blob', { outputDir: 'blob-report' }],
        ['github'],
      ]
    : [['html', { open: 'on-failure' }]],
  use: {
    baseURL: process.env.PLAYWRIGHT_TEST_BASE_URL || 'http://localhost:3000',
    trace: isCI ? 'retain-on-failure' : 'on-first-retry',
    video: isCI ? 'retain-on-failure' : 'off',
    screenshot: isCI ? 'only-on-failure' : 'off',
    actionTimeout: 10_000,
    navigationTimeout: 15_000,
  },
  projects: [
    {
      name: 'setup-auth',
      testMatch: /.*\.setup\.ts/,
    },
    {
      name: 'Chromium-Desktop',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1440, height: 900 },
      },
      dependencies: ['setup-auth'],
    },
    {
      name: 'Mobile-Safari',
      use: {
        ...devices['iPhone 14'],
      },
      dependencies: ['setup-auth'],
    },
  ],
});
```

#### B. Auth Fixture & Session Injector (`e2e/fixtures/auth.fixture.ts`)

Menghindari pengujian login UI berulang kali di setiap test suite dengan memanfaatkan *Storage State Injection* secara programmatic.

```typescript
import { test as base, Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

type WorkerAuthFixture = {
  authenticatedPage: Page;
};

export const test = base.extend<{}, WorkerAuthFixture>({
  authenticatedPage: [
    async ({ browser }, use) => {
      // Buat browser context terisolasi dengan state autentikasi yang tersimpan
      const authPath = path.resolve(__dirname, '../.auth/enterprise-user.json');
      
      let context;
      if (fs.existsSync(authPath)) {
        context = await browser.newContext({ storageState: authPath });
      } else {
        // Fallback programmatic generation jika state belum ada
        context = await browser.newContext();
        const page = await context.newPage();
        
        // Eksekusi API login tanpa melewati form UI submission
        const response = await page.request.post('http://localhost:3000/api/auth/callback/credentials', {
          data: {
            username: 'enterprise-qa@enterprise.internal',
            password: process.env.TEST_USER_PASSWORD || 'SecretP@ssw0rd!',
          },
        });
        
        if (!response.ok()) {
          throw new Error(`Programmatic authentication failed: ${response.status()}`);
        }
        
        await context.storageState({ path: authPath });
        await page.close();
      }

      const page = await context.newPage();
      await use(page);
      await context.close();
    },
    { scope: 'worker' },
  ],
});

export { expect } from '@playwright/test';
```

#### C. Testing Server Actions & Optimistic UI (`e2e/specs/checkout.spec.ts`)

```typescript
import { test, expect } from '../fixtures/auth.fixture';

test.describe('E-Commerce Checkout via Server Actions', () => {
  test('harus memvalidasi optimistic UI dan integritas mutasi Next-Action', async ({
    authenticatedPage: page,
  }) => {
    await page.goto('/checkout', { waitUntil: 'networkidle' });

    const orderButton = page.getByRole('button', { name: /Place Order/i });
    const orderStatusBadge = page.getByTestId('order-status');

    // Pastikan status awal idle
    await expect(orderStatusBadge).toHaveText('READY');

    // Intersepsi Server Action POST request
    const actionPromise = page.waitForResponse(
      (response) =>
        response.url().includes('/checkout') &&
        response.request().method() === 'POST' &&
        response.request().headers()['next-action'] !== undefined &&
        response.status() === 200
    );

    // Click checkout button: Memicu Client Optimistic Mutation
    await orderButton.click();

    // Optimistic Update: UI harus langsung berubah ke PROCESSING sebelum network resolve
    await expect(orderStatusBadge).toHaveText('PROCESSING');

    // Tunggu Server Action selesai dieksekusi oleh server
    const actionResponse = await actionPromise;
    const actionPayload = await actionResponse.text();

    // Verifikasi bahwa server action mengembalikan format payload Next.js Flight
    expect(actionResponse.headers()['content-type']).toContain('text/x-component');

    // Validasi final state setelah mutasi data di database dikonfirmasi
    await expect(orderStatusBadge).toHaveText('COMPLETED');
    await expect(page.getByTestId('order-id-display')).toBeVisible();
  });
});
```

#### D. Visual Regression Testing Snapshot (`e2e/specs/visual-regression.spec.ts`)

```typescript
import { test, expect } from '@playwright/test';

test.describe('Enterprise Dashboard Visual Stability', () => {
  test('tampilan dashboard harus stabil tanpa pergeseran layout atau regresi CSS', async ({ page }) => {
    await page.goto('/dashboard/metrics');

    // Stabilkan UI: Matikan animasi CSS aktif dan sembunyikan data dinamis (timestamp/grafik acak)
    await page.addStyleTag({
      content: `
        *, *::before, *::after {
          animation-duration: 0s !important;
          animation-delay: 0s !important;
          transition-duration: 0s !important;
        }
      `,
    });

    // Mask elemen dinamis yang nilainya tidak deterministik
    const liveClock = page.getByTestId('live-clock');
    const dynamicRevenueGraph = page.getByTestId('realtime-chart');

    await expect(page).toHaveScreenshot('dashboard-metrics-golden.png', {
      mask: [liveClock, dynamicRevenueGraph],
      fullPage: true,
      threshold: 0.05, // Toleransi 5% untuk subpixel text antialiasing
    });
  });
});
```

#### E. GitHub Actions Enterprise Sharding Pipeline (`.github/workflows/e2e-matrix.yml`)

```yaml
name: Enterprise E2E Suite & Quality Gate

on:
  pull_request:
    branches: [main, release/*]
    paths:
      - 'apps/web/**'
      - 'packages/**'
      - 'e2e/**'
      - 'playwright.config.ts'
      - '.github/workflows/e2e-matrix.yml'

concurrency:
  group: e2e-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  build-and-cache:
    name: Build Next.js Production Bundle
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js & Corepack
        uses: actions/setup-node@v4
        with:
          node-version-file: '.nvmrc'
          cache: 'pnpm'

      - name: Install pnpm
        run: corepack enable && corepack prepare pnpm@latest --activate

      - name: Install Dependencies
        run: pnpm install --frozen-lockfile

      - name: Next.js Cache
        uses: actions/cache@v4
        with:
          path: |
            ${{ github.workspace }}/.next/cache
          key: ${{ runner.os }}-nextjs-${{ hashFiles('**/pnpm-lock.yaml') }}-${{ hashFiles('apps/web/**/*.ts', 'apps/web/**/*.tsx') }}
          restore-keys: |
            ${{ runner.os }}-nextjs-${{ hashFiles('**/pnpm-lock.yaml') }}-

      - name: Build Standalone
        run: pnpm build
        env:
          NEXT_TELEMETRY_DISABLED: 1
          NODE_ENV: production

      - name: Cache Build Artifact
        uses: actions/upload-artifact@v4
        with:
          name: app-build-artifact
          path: |
            .next
            public
            package.json
          retention-days: 1

  e2e-sharded:
    name: Playwright Shard ${{ matrix.shardIndex }}/${{ matrix.shardTotal }}
    needs: [build-and-cache]
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        shardIndex: [1, 2, 3, 4]
        shardTotal: [4]
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version-file: '.nvmrc'
          cache: 'pnpm'

      - name: Install pnpm
        run: corepack enable && corepack prepare pnpm@latest --activate

      - name: Install Dependencies
        run: pnpm install --frozen-lockfile

      - name: Download Build Artifact
        uses: actions/download-artifact@v4
        with:
          name: app-build-artifact

      - name: Install Playwright Browsers & OS Dependencies
        run: pnpm exec playwright install --with-deps chromium

      - name: Start Next.js Background Server
        run: |
          pnpm start &
          pnpm exec wait-on http://127.0.0.1:3000 --timeout 60000
        env:
          NODE_ENV: production
          PORT: 3000

      - name: Run Playwright Tests (Shard ${{ matrix.shardIndex }}/${{ matrix.shardTotal }})
        run: |
          pnpm exec playwright test --shard=${{ matrix.shardIndex }}/${{ matrix.shardTotal }}
        env:
          CI: 1
          PLAYWRIGHT_TEST_BASE_URL: http://127.0.0.1:3000

      - name: Upload Shard Report Blob
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: all-blob-reports-${{ matrix.shardIndex }}
          path: blob-report
          retention-days: 2

  merge-reports:
    name: Collate & Publish Unified Report
    if: always()
    needs: [e2e-sharded]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version-file: '.nvmrc'

      - name: Download All Blob Artifacts
        uses: actions/download-artifact@v4
        with:
          path: all-blob-reports
          pattern: all-blob-reports-*
          merge-multiple: true

      - name: Install Playwright
        run: npx playwright install --with-deps

      - name: Merge Reports to Unified HTML
        run: |
          npx playwright merge-reports --reporter html ./all-blob-reports

      - name: Upload Final HTML Report
        uses: actions/upload-artifact@v4
        with:
          name: final-playwright-report
          path: playwright-report
          retention-days: 14
```

---

## 8. Real World Case Study (Enterprise Scale)

### Bank Digital Multinasional: Mitigasi Skew Deployment & Eliminasi Flaky Tests

* **Konteks:** Sebuah bank digital dengan 8 juta pengguna aktif memigrasikan portal perbankannya dari Next.js Pages Router ke App Router dengan Server Actions. Tim engineer terdiri atas 120 pengembang yang melakukan deploy 30–50 PR per hari.
* **Insiden Produksi (Problem):** 
  1. Pengujian E2E lama memakan waktu **52 menit** per run, menyebabkan *developer blockage* dan pengabaian hasil tes merah (*merge bypass*).
  2. Saat migrasi ke Server Actions, terjadi insiden di mana tombol transfer dana tidak merespons di Safari, tetapi lolos pengetesan lokal. Hal ini disebabkan oleh *action ID hashing mismatch* antara preview environment dan production runtime.
  3. Terjadi *flakiness rate* hingga 22% akibat race condition antara rendering streaming RSC dan hidrasi Client Component form controller.
* **Solusi Arsitektural:**
  1. **Matrix Sharding & Turborepo Optimization:** Memecah 600 skenario E2E ke dalam 8 shard Playwright concurrent runner di GitHub Actions. Waktu eksekusi turun drastis menjadi **4 menit 45 detik**.
  2. **Strict Hydration Handshake Fixture:** Membuat custom locator yang menunggu atribut hidrasi selesai pada form container:
     ```typescript
     await page.locator('form[data-hydrated="true"]').waitFor({ state: 'attached' });
     ```
  3. **Zero-Skew Action Assertion:** Menambahkan interceptor Playwright yang membaca error header `x-action-error` jika Next.js Server mengembalikan HTTP 404/500 akibat mismatch build ID.
  4. **Dynamic Database Branching:** Mengintegrasikan platform database ephemeral (Neon). Setiap PR runner mendapatkan isolated schema branch yang secara otomatis dieksekusi dan dihapus pasca-testing.
* **Hasil:**
  * Flakiness turun dari **22% ke 0.15%**.
  * Cycle time PR turun dari 1.5 jam menjadi 12 menit.
  * Zero regression defects pada fitur transaksi moneter selama 4 kuartal berturut-turut.

---

## 9. Trade-offs

| Pendekatan / Keputusan | Keuntungan | Biaya / Konsekuensi (Trade-off) |
| :--- | :--- | :--- |
| **8x CI Matrix Sharding** | Waktu eksekusi E2E terpangkas drastis secara linear ($1/N$ durasi total). | Konsumsi menit GitHub Actions (billing) meningkat; kompleksitas reporting artifact merge. |
| **Full Ephemeral DB Branching** | Uji terisolasi 100%; tidak ada state collision antar uji paralel. | Menambah latensi provisioning DB (+15–30 detik per CI run); membutuhkan lisensi vendor database cloud yang mendukung branching via API. |
| **Network Mocking (`page.route()`)** | Cepat, deterministik, tidak bergantung pada microservice pihak ketiga. | Menutupi potensi integrasi bug nyata; tidak dapat memotong database fetch yang terjadi di dalam RSC server-side execution. |
| **Full Visual Snapshot Testing** | Menangkap cacat UI/CSS layout sekecil 1 piksel yang lolos dari DOM assertion. | Sensitif terhadap perbedaan rendering OS/GPU; potensi *false positive* akibat font rendering antialiasing rendering cross-platform. |
| **Mocking via MSW Node.js** | Mampu memotong fetch di level Server Component (RSC) secara runtime. | Mengubah environment runtime Node; risiko perbedaan perilaku antara mock server dan production Node networking. |

---

## 10. Common Mistakes & Troubleshooting

### 1. Intersepsi Network Client untuk Server Component Fetch

* **Kesalahan:** Mencoba menggunakan `page.route('**/api/data', ...)` untuk me-mock data yang dipanggil langsung di dalam React Server Component (`async function Component() { const res = await fetch(...) }`).
* **Mengapa Gagal:** Server Components dieksekusi di Node.js server container, bukan di V8 browser runner. `page.route()` milik Playwright hanya mengintersepsi panggilan network yang keluar dari browser client.
* **Solusi Enterprise:** Gunakan environment variable mock injection (`API_MOCK_SERVER_URL`), atau gunakan mock server terpusat berbasis WireMock/MSW pada level network runner.

### 2. Mengklik Elemen Sebelum Hydration Selesai (*Hydration Gap*)

* **Kesalahan:** `await page.click('button#submit')` langsung setelah navigasi.
* **Mengapa Gagal:** Next.js melakukan streaming HTML secara instan. Elemen `<button>` sudah ada di DOM, tetapi event handler `onClick` (Client Component) belum selesai di-hydrate oleh React runtime. Browser menerima klik tetapi tidak ada event yang dieksekusi.
* **Solusi Enterprise:** Buat indikator hidrasi deterministik dalam aplikasi produksi atau tunggu atribut reaktif:
  ```typescript
  // Di Client Component:
  // useEffect(() => { setIsHydrated(true) }, []);
  // <button data-hydrated={isHydrated}>Submit</button>

  // Di Playwright Spec:
  const submitBtn = page.locator('button#submit[data-hydrated="true"]');
  await submitBtn.click();
  ```

### 3. Font Inconsistency pada Visual Snapshot Testing

* **Kesalahan:** Visual diffing gagal di CI Linux runner padahal lolos di macOS pengembang lokal.
* **Mengapa Gagal:** Rendering font sistem dan font kerning berbeda antara macOS CoreText dan Linux FreeType.
* **Solusi Enterprise:** Gunakan Docker image resmi Playwright (`mcr.microsoft.com/playwright`) baik di lokal maupun di CI, atau injeksi font web seragam dengan font-display: block dan nonaktifkan font smoothing sub-pixel:
  ```typescript
  await page.addStyleTag({
    content: `
      body {
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
        font-family: Arial, sans-serif !important;
      }
    `
  });
  ```

### 4. Debugging Playwright Tracing di CI

Jika pengujian gagal secara acak di CI, jalankan analisis post-mortem menggunakan trace file:
```bash
# Download artifact trace.zip dari GitHub Actions
pnpm exec playwright show-trace path/to/trace.zip
```
Analisis **Console Logs**, **Network Calls** (khususnya header `Next-Action` dan payload serialisasi `_rsc`), serta **DOM Actionability Logs** pada timeline detik terjadinya kegagalan.

---

## 11. Best Practices (Production Checklist)

- [ ] **Deterministic Data Management:** Setiap runner uji membuat data uniknya sendiri (misal: user email berbasis worker ID/UUID: `test-user-${testInfo.workerIndex}-${Date.now()}@test.internal`).
- [ ] **No Hardcoded Sleep:** Hapus semua `page.waitForTimeout()` dari codebase. Ganti dengan state-based assertions (`toBeVisible()`, `toHaveValue()`, atau `waitForResponse()`).
- [ ] **Skew Protection Awareness:** Pastikan deployment preview Next.js menggunakan versi hash build yang identik saat menjalankan E2E matrix.
- [ ] **Fail-Fast Policy:** Konfigurasi `--max-failures=5` di level CI branch PR untuk menghemat resource runner jika terjadi build catastrophe.
- [ ] **Artifact Retention Constraints:** Simpan Playwright traces, videos, dan screenshots hanya untuk pengujian yang gagal (`retain-on-failure`) dengan masa retensi maksimal 7 hari untuk menghemat storage artifacts.
- [ ] **Hermetic Container Testing:** Jalankan build dan test di dalam Docker container yang identik dengan target infrastruktur produksi.
- [ ] **Authentication State Re-use:** Autentikasi dilakukan sekali per worker class menggunakan API login, disimpan dalam disk, dan di-load via `browser.newContext({ storageState })`.
- [ ] **Clock Mocking:** Gunakan `await page.clock.setFixedTime(new Date('2026-01-01T00:00:00Z'))` saat menguji komponen yang sensitif terhadap tanggal atau timer.

---

## 12. Hands-on Practice

Implementasikan test suite enterprise ini pada repositori kerja Anda di direktori `hands-on/m02/`.

### Langkah 1: Inisialisasi Lingkungan Proyek
Buat struktur project Next.js dan pasang Playwright:
```bash
mkdir -p hands-on/m02 && cd hands-on/m02
pnpm init
pnpm add next@latest react@latest react-dom@latest
pnpm add -D @playwright/test @types/node typescript wait-on
pnpm exec playwright install --with-deps chromium
```

### Langkah 2: Setup Komponen Target Uji (Server Actions & Streaming)
Buat file `app/actions.ts`:
```typescript
'use server';

export async function submitApplication(prevState: any, formData: FormData) {
  const applicantName = formData.get('name') as string;
  
  // Simulasi processing delay
  await new Promise((resolve) => setTimeout(resolve, 800));

  if (!applicantName || applicantName.length < 3) {
    return { success: false, error: 'Nama minimal harus 3 karakter.' };
  }

  return { success: true, applicationId: `APP-${Date.now()}` };
}
```

Buat file Client Component dengan feedback hidrasi `app/application-form.tsx`:
```tsx
'use client';

import { useActionState, useEffect, useState } from 'react';
import { submitApplication } from './actions';

export function ApplicationForm() {
  const [state, formAction, isPending] = useActionState(submitApplication, null);
  const [isHydrated, setIsHydrated] = useState(false);

  useEffect(() => {
    setIsHydrated(true);
  }, []);

  return (
    <div className="p-8 max-w-md mx-auto" data-testid="form-container" data-hydrated={isHydrated}>
      <h1 className="text-2xl font-bold mb-4">Enterprise Verification Form</h1>
      <form action={formAction} className="space-y-4">
        <div>
          <label htmlFor="name" className="block text-sm">Nama Lengkap</label>
          <input
            id="name"
            name="name"
            type="text"
            className="border p-2 w-full rounded"
            placeholder="John Doe"
            required
          />
        </div>
        <button
          type="submit"
          disabled={!isHydrated || isPending}
          className="bg-blue-600 text-white px-4 py-2 rounded disabled:bg-gray-400"
          data-testid="submit-btn"
        >
          {isPending ? 'Memproses...' : 'Kirim Berkas'}
        </button>
      </form>

      {state?.error && (
        <p className="mt-4 text-red-600" data-testid="error-alert">{state.error}</p>
      )}

      {state?.success && (
        <p className="mt-4 text-green-600" data-testid="success-alert">
          Sukses! ID: {state.applicationId}
        </p>
      )}
    </div>
  );
}
```

Buat halaman entry `app/page.tsx`:
```tsx
import { Suspense } from 'react';
import { ApplicationForm } from './application-form';

export default function Page() {
  return (
    <main>
      <Suspense fallback={<div data-testid="suspense-fallback">Memuat Form...</div>}>
        <ApplicationForm />
      </Suspense>
    </main>
  );
}
```

### Langkah 3: Implementasi Test Suite Playwright
Buat file `tests/application.spec.ts`:
```typescript
import { test, expect } from '@playwright/test';

test.describe('Form Submission Life-Cycle', () => {
  test('harus memvalidasi kesiapan hidrasi dan eksekusi Server Action', async ({ page }) => {
    await page.goto('/');

    // 1. Validasi Hydration Barrier
    const formContainer = page.getByTestId('form-container');
    await expect(formContainer).toHaveAttribute('data-hydrated', 'true', { timeout: 10_000 });

    const submitBtn = page.getByTestId('submit-btn');
    await expect(submitBtn).toBeEnabled();

    // 2. Input Data Valid
    await page.getByLabel(/Nama Lengkap/i).fill('Alexander Pierce');

    // 3. Setup network listener untuk Next-Action
    const actionPromise = page.waitForResponse(
      (res) =>
        res.request().method() === 'POST' &&
        res.request().headers()['next-action'] !== undefined &&
        res.status() === 200
    );

    // 4. Klik submit & Verifikasi Pending State
    await submitBtn.click();
    await expect(submitBtn).toHaveText('Memproses...');
    await expect(submitBtn).toBeDisabled();

    // 5. Tunggu respon Server Action
    await actionPromise;

    // 6. Validasi Pesan Sukses
    const successAlert = page.getByTestId('success-alert');
    await expect(successAlert).toBeVisible();
    await expect(successAlert).toContainText('Sukses! ID: APP-');
  });
});
```

Jalankan test secara lokal:
```bash
# Build dan start standalone server
pnpm next build
pnpm next start -p 3000 &
pnpm exec wait-on http://127.0.0.1:3000

# Eksekusi test suite
pnpm exec playwright test tests/application.spec.ts --project=Chromium-Desktop --headed
```

---

## 13. Exercise

### Level Easy
Tuliskan sebuah file tes Playwright (`loading-state.spec.ts`) yang memvalidasi bahwa halaman `/products` yang memiliki wrapper `loading.tsx` menampilkan 4 buah skeleton card placeholder sebelum data riil produk tampil di layar. Gunakan matcher `page.getByTestId('product-skeleton')`.

### Level Medium
Buat custom fixture `storageState` yang melakukan login melalui endpoint GraphQL `/api/graphql` menggunakan mutasi token exchange, menyuntikkan cookie HTTP-only `session-token` ke dalam Browser Context, dan memvalidasi akses langsung ke rute terproteksi `/settings/billing` tanpa dialihkan (*redirect*) ke `/login`.

### Level Hard
Rancang suite pengujian Playwright terdistribusi yang menyimulasikan kegagalan jaringan (*chaos fault injection*). Ketika Server Action POST dipanggil, gunakan `page.route()` untuk membatalkan koneksi (*abort*) dengan error `Failed` atau `ConnectionReset` pada upaya pertama. Validasi bahwa UI Client Component menampilkan tombol *Retry*, dan ketika diklik ulang dengan koneksi normal, Server Action berhasil diproses dan data DOM konsisten.

---

## 14. Challenge

### Studi Kasus: Multi-Region Distributed Canary Deployment Gate

**Deskripsi Masalah:**
Perusahaan retail global Anda menerapkan arsitektur *Blue-Green/Canary Deployment* multi-region di AWS (us-east-1 dan eu-central-1). Saat rilis versi baru Next.js, Anda tidak dapat mengarahkan 100% traffic secara instan. Anda diminta membangun sistem validasi automasi CI/CD tingkat lanjut.

**Spesifikasi Persyaratan Arsitektur:**
1. **Dynamic Canary Traffic Routing:** Runner CI harus mengarahkan 5% traffic uji ke environment Canary Next.js melalui header HTTP kustom `X-Canary-Release: next-v15.2`.
2. **Dynamic RSC Integrity Validation:** Buat test runner terotomasi yang secara simultan mengeksekusi 100 interaksi user kritis (add to cart, apply promo code, mutation Server Action) ke pod Canary dan pod Stable.
3. **Automated Rollback Signal:** Jika *error rate* pada Canary melebihi 0.5%, atau latensi response streaming RSC 95th-percentile (p95) naik di atas 300ms, pipeline CI/CD harus secara mandiri menghentikan workflow, mengeluarkan status check `FAILED`, dan memicu Webhook rollback ke infrastruktur routing AWS Route53/CloudFront.
4. **Data Mutex Isolation:** Seluruh mutasi database selama canary automated run harus berjalan di bawah isolasi tenancy khusus agar tidak merusak metrik analitik bisnis live.

**Tugas Anda:**
Tulis dokumen arsitektur teknis lengkap beserta konfigurasi GitHub Actions orchestrator, skrip node custom telemetry sniffer, dan fixture Playwright yang merealisasikan sistem *quality gate* otomatis ini.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Pertanyaan)

1. Mengapa `page.waitForTimeout(milliseconds)` dilarang digunakan dalam arsitektur pengujian E2E enterprise?
   * *Jawaban:* Menyebabkan waktu tunggu statis yang tidak perlu (*slowdown*), tidak adaptif terhadap performa mesin CI yang dinamis, dan merupakan sumber utama terjadinya *flaky tests*. Pengujian modern wajib menggunakan *web-first assertions* berbasis state polling otomatis.
2. Apa fungsi header `next-action` pada HTTP request yang dikirimkan oleh browser di aplikasi Next.js?
   * *Jawaban:* Merupakan identifier unik (*hashed action reference*) yang dihasilkan saat proses build untuk mengarahkan request POST ke fungsi Server Action yang sesuai di backend runtime.
3. Apa perbedaan mendasar antara mode reporter `blob` dan `html` pada Playwright?
   * *Jawaban:* Reporter `blob` menyimpan data mentah hasil test per runner dalam format biner yang ringan untuk digabungkan (*merged*) dari berbagai shard CI. Reporter `html` menghasilkan file laporan visual akhir yang interaktif untuk dibaca manusia.
4. Mengapa Playwright secara default mengeksekusi test dalam status *incognito browser context* terisolasi?
   * *Jawaban:* Untuk menjamin setiap test berjalan hermetis tanpa berbagi cookies, localStorage, cache, atau session state yang dapat mengkontaminasi hasil tes lainnya.
5. Apa dampak penggunaan atribut CSS `animation: disabled` saat menjalankan Visual Regression Testing?
   * *Jawaban:* Mengeliminasi perbedaan tangkapan layar piksel (*pixel diff*) yang disebabkan oleh elemen UI yang sedang berada di tengah-tengah transisi/keyframe animasi ketika screenshot diambil.

### Bagian 2: Intermediate (5 Pertanyaan)

6. Mengapa Playwright `page.route()` tidak dapat memotong (*mock*) network request yang didefinisikan di dalam komponen React Server Component (RSC)?
   * *Jawaban:* Karena RSC dieksekusi di server/Node.js context Next.js sebelum HTML/Flight stream dikirim ke browser. `page.route()` hanya memotong network stack pada layer V8 browser engine client-side.
7. Bagaimana cara menangani testing pada UI yang dibungkus oleh Suspense Boundary agar tidak terjadi race condition assertion?
   * *Jawaban:* Dengan memvalidasi keberadaan elemen fallback terlebih dahulu (`toBeVisible()`), diikuti assertion eksplisit bahwa elemen data final telah muncul, dan elemen fallback telah hilang dari DOM (`not.toBeVisible()`).
8. Apa itu mekanisme *sharding* pada Playwright dan bagaimana formulasi eksekusinya di CI matrix?
   * *Jawaban:* Sharding adalah pembagian test suite ke beberapa runner terpisah. Diformulasikan dengan parameter `--shard=X/N`, di mana $N$ adalah total runner paralel, dan $X$ adalah indeks runner saat ini.
9. Mengapa file `storageState.json` perlu di-generate ulang jika terjadi perubahan deployment hash pada session payload?
   * *Jawaban:* Karena skema session, encryption key, atau signature JWT dapat menjadi tidak valid (*stale*), menyebabkan rute autentikasi me-redirect browser kembali ke `/login` (*auth failure*).
10. Bagaimana cara menstabilkan rendering font pada Linux-based CI runner agar cocok dengan visual snapshot yang dibuat di sistem operasi lokal (misal macOS)?
    * *Jawaban:* Menjalankan Playwright di dalam container Docker seragam (`playwright:vX.Y.Z-focal`), mematikan sub-pixel text rendering font-smoothing, dan menyuntikkan font fallback deterministik via stylesheet fixture.

### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)

11. **Skenario A:** Pipeline E2E Anda sering gagal dengan error `Timeout 30000ms exceeded while waiting for event "networkidle"`. Aplikasi Anda menggunakan fitur Next.js App Router dengan periodic background polling setiap 5 detik dan live WebSocket logging.
    * *Analisis & Solusi:* Event `networkidle` menunggu tidak ada network traffic selama setidaknya 500ms. Adanya WebSocket dan periodic polling menyebabkan status tersebut tidak pernah tercapai. Solusinya: Jangan gunakan `networkidle`. Gunakan `waitUntil: 'commit'` atau `'domcontentloaded'`, lalu tunggu secara deterministik locator spesifik data yang dibutuhkan.

12. **Skenario B:** Setelah merilis fitur baru yang menggunakan Server Actions, tim QA melaporkan bahwa form checkout sering submit data ganda (*duplicate orders*) jika diuji pada jaringan mobile 3G di environment E2E CI.
    * *Analisis & Solusi:* Terjadi *action trigger race condition* sebelum hidrasi selesai atau tombol tidak di-disable saat status `isPending` berjalan. Dalam Playwright, verifikasi bahwa form memiliki disable guard: `disabled={isPending}`. Pada pengujian E2E, injeksikan Playwright Network Emulation (`page.route` throttle atau `emulateNetworkConditions`), klik tombol sekali, lalu assert tombol berstatus `disabled` secara instan, dan pastikan network request dengan header `next-action` hanya dikirimkan tepat satu kali.

13. **Skenario C:** Dalam pengujian sharded matrix di GitHub Actions, Shard 2 dan Shard 4 gagal secara acak dengan HTTP 500 saat mengakses database, sementara Shard 1 dan 3 berhasil. Seluruh shard terhubung ke satu Staging PostgreSQL database yang sama.
    * *Analisis & Solusi:* Terjadi *cross-worker data pollution* dan *table locking/deadlock* akibat operasi mutasi paralel secara bersamaan ke baris database yang sama. Solusinya: Terapkan strategi Database Isolation. Setiap worker atau shard harus menggunakan PostgreSQL schema terisolasi (misal via search_path dinamis: `SET search_path TO shard_2;`), atau gunakan container database ephemeral terpisah per GitHub Actions runner.

---

## 16. Summary

Pengujian End-to-End dan otomatisasi CI/CD untuk aplikasi Next.js modern tingkat enterprise membutuhkan pergeseran paradigma dari *black-box UI clicking* ke arah **arsitektur pengujian sadar-runtime (*runtime-aware testing architecture*)**:

1. **Pemahaman Arsitektur App Router:** Pengujian harus dirancang dengan memahami pemisahan boundary antara Server Components dan Client Components, streaming payload serialisasi React Flight, serta header mutasi Server Actions.
2. **Eksekusi Terdistribusi Deterministic:** Mengurangi cycle time CI menggunakan horizontal matrix sharding dan caching bertingkat (Turborepo + Docker layers) adalah fondasi kecepatan delivery tanpa mengorbankan cakupan uji.
3. **Hermetisitas State & Lingkungan:** Menghilangkan *flakiness* secara absolut dengan mengadopsi ephemeral environments, database schema branching per runner, programmatic storageState authentication, dan web-first assertions yang kebal terhadap jeda hidrasi (*hydration gap*).
4. **Proteksi Kualitas Menyeluruh:** Menggabungkan validasi fungsional, visual regression testing deterministik, dan resilience testing terhadap kegagalan jaringan memastikan aplikasi Next.js siap beroperasi pada level enterprise dengan reliabilitas tinggi.