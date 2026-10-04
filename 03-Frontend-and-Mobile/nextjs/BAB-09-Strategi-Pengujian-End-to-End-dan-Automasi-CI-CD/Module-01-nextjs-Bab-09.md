# Modul 01: Strategi Pengujian End-to-End & Automasi CI/CD

---

## SEKSI 01 — IDENTITAS MODUL

* **Kategori Kurikulum:** 03-Frontend-and-Mobile
* **Topik Utama:** Next.js Enterprise Testing & CI/CD Lifecycle
* **Judul Modul:** Strategi Pengujian End-to-End & Automasi CI/CD
* **Jalur Dokumen:** `./09-testing-dan-cicd-pipeline/`
* **Target Pembaca:** Senior Frontend Engineer, Full-Stack Architect, DevOps/Platform Engineer
* **Tingkat Kompleksitas:** Tingkat Lanjut (Advanced/Enterprise)
* **Prasyarat:** Pemahaman mendalam tentang Next.js App Router (React Server Components & Server Actions), State Management, Containerization (Docker), serta fondasi alur kerja Git dan Linux runner.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta ajar memiliki kemampuan untuk:
1. Merancang dan mengoperasikan strategi pengujian End-to-End (E2E) deterministik berbasis **Playwright** yang mencakup isolasi autentikasi (*storage state*), bypass reCAPTCHA/bot detection pada lingkungan uji, serta determinisme pengujian.
2. Membedah siklus hidup *rendering* Next.js (RSC, SSR, Suspense boundary, dan Streaming Hydration) dari sudut pandang harness pengujian headless browser.
3. Membangun pipeline CI/CD skala enterprise pada **GitHub Actions** yang mengimplementasikan caching multi-lapisan (Turborepo, Yarn/PNPM Store, Playwright Browser Binaries, `.next/cache`), *matrix sharding*, dan *ephemeral preview deployment*.
4. Menerapkan pola isolasi mutasi data (*test database branching/sandboxing*) guna mencegah *race condition* dan *flaky tests* pada eksekusi pengujian konkuren paralel.
5. Memitigasi ancaman keamanan pipeline (OIDC token hijacking, kebocoran secret pada artefak, supply-chain attack via caching poisoning) serta mengevaluasi telemetri performa dan kegagalan pipeline CI/CD.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Mental Model: Piramida Testing Kontekstual vs. Realitas App Router

Pada paradigma tradisional (Client-Side Rendering), piramida pengujian mengalokasikan 70% pengujian pada level *Unit*, 20% *Integration*, dan 10% *E2E*. Namun, pada Next.js App Router, pemisahan antara server dan client menjadi kabur. Komponen Server (RSC) mengeksekusi *database queries* langsung, sementara Server Actions bertindak sebagai mutasi state dan backend RPC secara transparan.

```
       TRADISIONAL                        NEXT.JS APP ROUTER ENTERPRISE
          / E2E \                                    /  E2E  \  (Kritis: RSC + Hydration + Actions)
         /-------\                                  /---------\
        /  Integ  \                                /   Integ   \ (Server Components + Mocked DB/IO)
       /-----------\                              /-------------\
      /    Unit     \                            /     Unit      \ (Pure Utility & Isolated Hooks)
```

E2E bukan lagi sekadar validasi fungsional browser akhir; ini adalah **satu-satunya lapisan verifikasi yang mengeksekusi integrasi sejati antara runtime Node.js/Edge, serialisasi payload RSC (Flight protocol), revalidasi tag/path cache, dan rendering DOM di browser**.

### Pergeseran Pola Pikir: Dari "Menunggu Rendering" ke "Siklus Reaktif Determinisme"

1. **Anti-Pola `sleep()` / `waitForTimeout()`:** Pengujian E2E yang tangguh memandang UI sebagai *state machine* asinkron. Jangan pernah mengunci thread eksekusi dengan estimasi waktu arbitrary. Selalu bergantung pada *web assertions* berbasis sinyal jaringan atau mutasi DOM deterministik (`expect(locator).toBeVisible()`).
2. **Shift-Left Environment Parity:** Masalah produksi di Next.js sering terjadi akibat perbedaan antara `next dev` dan `next build && next start`. Server Actions dan caching metadata beroperasi secara fundamental berbeda pada mode development. Oleh karena itu, pengujian E2E lokal maupun CI **wajib dieksekusi terhadap *production build standalone artifact***.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Alur pengujian deterministik dan pipeline automasi CI/CD dari Commit hingga Preview Deployment:

```
[ Developer Commit / PR ]
         │
         ▼
[ GitHub Actions: Workflow Trigger ]
         │
         ├─────────────────────────────────────────────┐
         ▼                                             ▼
[ Job: Lint, Typecheck & Static Sec ]       [ Job: Cache Restore Engine ]
(biome/eslint + tsc --noEmit + gitleaks)    (PNPM + Turborepo + Next Cache)
         │                                             │
         └──────────────────────┬──────────────────────┘
                                │
                                ▼
                    [ Job: Production Build ]
                    (next build: Standalone Output)
                                │
                                ├───────────────────────────────┐
                                ▼                               ▼
                [ Ephemeral DB Provisioning ]        [ Artifact Distribution ]
                (Neon/Supabase Branching API)         (Standalone .next + public)
                                │                               │
                                └───────────────┬───────────────┘
                                                │
                                                ▼
                                [ Job: Playwright Orchestration ]
                                (Matrix Shard: 1/4, 2/4, 3/4, 4/4)
                                                │
                ┌───────────────────────────────┴───────────────────────────────┐
                ▼                                                               ▼
        [ Shard 1..N: Browser Pool ]                                [ Global Setup: Auth State ]
   (Chromium, WebKit, Mobile Safari)                                (StorageState JWT Storage)
                │                                                               │
                └───────────────────────────────┬───────────────────────────────┘
                                                │
                                                ▼
                                  [ Target: Standalone Next.js App ]
                                                │
                        ┌───────────────────────┴───────────────────────┐
                        ▼                                               ▼
                [ PASS: Status Green ]                          [ FAIL: Diagnostics ]
                        │                                               │
                        ▼                                               ▼
            [ Ephemeral DB De-provision ]                      [ Upload Traces & Videos ]
                        │                                               │
                        ▼                                               ▼
             [ Trigger Deploy / Merge ]                        [ Notify via Webhook PR ]
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Serialisasi Next.js RSC Flight Protocol pada Headless Browser
Saat Playwright memuat halaman Next.js (`page.goto('/dashboard')`), server mengirimkan respons awal berupa *streamed HTML shell* yang disuntikkan skrip deserialisasi React. Bersamaan dengan itu, data RSC ditransfer via format *Flight data stream* (chunk biner/teks dengan prefix baris seperti `0:["$","div",null,{"children":"...}]`). 

Headless browser harus mengeksekusi hidrasi client-side sebelum event handler seperti `onClick` aktif. Jika pengujian mencoba berinteraksi sebelum hidrasi selesai, browser dapat memicu klik native, tetapi React synthetic event listener belum terikat (kondisi *Uncanny Valley*). Playwright mengatasi hal ini secara internal dengan memantau status stabilitas DOM (*Actionability Checks*), tetapi pengembang wajib memahami bahwa transisi rute Next.js via `<Link>` atau `router.push()` tidak memicu navigasi browser tradisional (tidak ada *Full Page Reload*), melainkan *soft navigation* berbasis `fetch` payload Flight.

### 2. Autentikasi: Storage State vs. Login Loop Redundansi
Eksekusi login via form UI pada setiap test file menghasilkan beban I/O eksponensial. Playwright mengatasi inefisiensi ini melalui mekanika **Storage State**.

```
[ Test Worker Init ]
        │
        ▼
[ Read 'auth.json' ] ─── Cookies: [ 'sb-access-token', 'next-auth.session-token' ]
                     └── LocalStorage / SessionStorage snapshots
        │
        ▼
[ Inject to BrowserContext ]
        │
        ▼
[ Direct Request to Protected RSC ] ──> HTTP 200 (Bypass Landing & Form Login)
```

Dengan menginjeksi token sesi (JWT) langsung ke dalam `BrowserContext`, request RSC menerima header `Cookie` valid sejak *handshake* awal, sehingga mengurangi total waktu eksekusi suite hingga lebih dari 60%.

### 3. Server Actions & CSRF Token Validation
Server Actions di Next.js dipanggil via HTTP `POST` dengan header khusus:
* `Next-Action`: Hash identitas fungsi aksi di server.
* `Next-Router-State-Tree`: Representasi struktur rute aktif saat itu.

Ketika Playwright melakukan intercept atau memicu Server Actions, kegagalan sering muncul bukan dari logika UI, melainkan ketidakcocokan Origin header (`403 Forbidden` akibat proteksi CSRF bawaan Next.js). Harness pengujian harus memastikan domain lokal yang digunakan (`localhost` vs `127.0.0.1`) terkonfigurasi secara konsisten pada opsi `allowedOrigins` di `next.config.mjs`.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Deterministik Sharding dan Paralelisasi
Playwright mendukung pembagian suite pengujian ke beberapa mesin runner secara independen melalui parameter `--shard=x/y`.
Secara matematis, jika sebuah repositori memiliki $T$ total suite pengujian dengan rata-rata waktu eksekusi $\bar{t}$, waktu total pada satu mesin adalah:

$$T_{\text{total}} = \sum_{i=1}^{n} t_i$$

Dengan sharding $K$ runner di CI, batas atas waktu pemrosesan menyusut mendekati:

$$T_{\text{shard}} \approx \frac{T_{\text{total}}}{K} + t_{\text{setup}}$$

Di mana $t_{\text{setup}}$ mencakup pengunduhan browser binaries dan initial build caching. Sharding Playwright bersifat deterministik berdasarkan hashing internal dari jalur file tes:

$$\text{Shard Index} = \text{hash}(\text{testFilePath}) \pmod K$$

Hal ini menjamin bahwa pembagian tes antar-mesin bersifat stabil dan tidak menyebabkan overlap eksekusi.

### Cache Layering Optimization pada CI/CD
Efisiensi CI untuk Next.js bertumpu pada arsitektur pipeline dengan invalidasi cache yang presisi:

1. **Package Manager Store Cache:** Berdasarkan hash dari `pnpm-lock.yaml` atau `yarn.lock`. Mencegah dependensi diunduh ulang dari remote registry.
2. **Next.js Turbopack / Webpack Cache (`.next/cache`):** Menggunakan kombinasi commit hash dan cache dependency key. Memotong durasi kompilasi hingga 70%.
3. **Playwright OS-level Browser Cache:** Binary browser (~300MB per binary) di-cache berdasarkan OS runner dan Playwright core version.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah konfigurasi Playwright skala enterprise untuk Next.js dengan App Router, lengkap dengan isolasi *auth-state* dan web server automation.

### 1. `playwright.config.ts`

```typescript
import { defineConfig, devices } from '@playwright/test';
import path from 'path';

// Definisi path absolut untuk penyimpanan state autentikasi
export const STORAGE_STATE_PATH = path.join(__dirname, 'tests/.auth/user.json');

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? '100%' : undefined,
  reporter: [
    ['html', { open: 'never' }],
    ['list'],
    ...(process.env.CI ? [['github'] as const] : []),
  ],
  use: {
    baseURL: process.env.PLAYWRIGHT_TEST_BASE_URL || 'http://localhost:3000',
    trace: 'on-first-retry',
    video: 'on-first-retry',
    screenshot: 'only-on-failure',
    actionTimeout: 10_000,
    navigationTimeout: 15_000,
  },
  projects: [
    // Setup project untuk menghasilkan auth credentials
    {
      name: 'setup-auth',
      testMatch: /global\.setup\.ts/,
    },
    // Desktop Chromium Testing
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        storageState: STORAGE_STATE_PATH,
      },
      dependencies: ['setup-auth'],
    },
    // Desktop Safari Testing (WebKit)
    {
      name: 'webkit',
      use: {
        ...devices['Desktop Safari'],
        storageState: STORAGE_STATE_PATH,
      },
      dependencies: ['setup-auth'],
    },
    // Mobile Viewport Testing
    {
      name: 'mobile-chrome',
      use: {
        ...devices['Pixel 5'],
        storageState: STORAGE_STATE_PATH,
      },
      dependencies: ['setup-auth'],
    },
  ],
  webServer: {
    command: process.env.CI ? 'node .next/standalone/server.js' : 'pnpm run dev',
    url: 'http://localhost:3000/api/health',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    stdout: 'pipe',
    stderr: 'pipe',
  },
});
```

### 2. `tests/e2e/global.setup.ts`

```typescript
import { test as setup, expect } from '@playwright/test';
import { STORAGE_STATE_PATH } from '../../playwright.config';
import fs from 'fs';
import path from 'path';

setup('Autentikasi global sistem dan serialisasi session state', async ({ page }) => {
  // Pastikan direktori target penyimpanan auth state tersedia
  const authDir = path.dirname(STORAGE_STATE_PATH);
  if (!fs.existsSync(authDir)) {
    fs.mkdirSync(authDir, { recursive: true });
  }

  // Akses halaman otentikasi login
  await page.goto('/login');

  // Isi form autentikasi menggunakan locator berbasis peran aksesibilitas
  const emailInput = page.getByRole('textbox', { name: /alamat email/i });
  const passwordInput = page.getByLabel(/kata sandi/i);
  const submitButton = page.getByRole('button', { name: /masuk/i });

  await emailInput.fill(process.env.E2E_TEST_USER_EMAIL || 'admin@enterprise.internal');
  await passwordInput.fill(process.env.E2E_TEST_USER_PASSWORD || 'SecretSecure123!');
  await submitButton.click();

  // Validasi deterministik bahwa session telah terhidrasi dan dialihkan ke dashboard
  await expect(page).toHaveURL(/\/dashboard/);
  await expect(page.getByRole('heading', { name: /ringkasan metrik/i })).toBeVisible();

  // Serialisasi cookies dan storage state context ke file JSON lokal
  await page.context().storageState({ path: STORAGE_STATE_PATH });
});
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis `playwright.config.ts`
* **Baris 5:** `export const STORAGE_STATE_PATH` mendefinisikan lokasi artefak state auth. Variabel ini diekspor agar dapat diakses oleh runner setup dan proyek browser downstream.
* **Baris 9:** `fullyParallel: true` memerintahkan Playwright menjalankan setiap tes individual di dalam file yang sama secara paralel menggunakan pekerja (*worker threads*) yang terisolasi.
* **Baris 10:** `forbidOnly: !!process.env.CI` adalah mekanisme fail-safe kritis. Ini menggagalkan build jika ada pengembang yang tidak sengaja meninggalkan `test.only()` pada kode sumber yang di-push ke remote repository.
* **Baris 11:** `retries: process.env.CI ? 2 : 0` mengaktifkan mekanisme *automatic retry* khusus di lingkungan CI untuk menangani *transient infrastructure hiccups*, namun mematikan retry di mesin lokal untuk debugging instan.
* **Baris 12:** `workers: process.env.CI ? '100%' : undefined` mengutilisasi seluruh core CPU yang dialokasikan oleh runner runner VM untuk throughput maksimal.
* **Baris 30–33:** Project `setup-auth` dieksekusi terlebih dahulu sebelum browser matrix lainnya berjalan melalui deklarasi `dependencies: ['setup-auth']` pada Baris 41, 49, dan 57.
* **Baris 61–67:** Blok `webServer` mengotomatisasi spawning runtime Next.js. Pada CI, server mengeksekusi langsung `.next/standalone/server.js` (hasil optimasi build produksi Next.js) dan melakukan polling ke endpoint `/api/health` hingga HTTP 200 tercapai sebelum pengujian pertama dieksekusi.

### Analisis `tests/e2e/global.setup.ts`
* **Baris 6–11:** Mencegah runtime exception I/O dengan memastikan direktori penyimpanan state (`tests/.auth/`) dibuat secara rekursif sebelum Playwright mencoba menulis file.
* **Baris 17–19:** Menggunakan `page.getByRole` dan `page.getByLabel`. Ini adalah konvensi pengujian berbasis standar W3C ARIA yang memastikan pengujian memvalidasi aksesibilitas sekaligus tahan terhadap perubahan class CSS (*resilient to styling changes*).
* **Baris 26–27:** `toHaveURL` dan `toBeVisible` mengeksekusi asersi *auto-waiting* (default timeout: 5000ms), mengeliminasi *race condition* yang kerap terjadi saat routing Next.js mengupdate history DOM secara asinkron.
* **Baris 30:** `storageState({ path })` mengekstraksi seluruh cookie HTTP-Only, session cookies, dan snapshot local storage dari context aktif dan menyimpannya secara atomik ke filesystem.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Enterprise: Sistem Checkout Multi-Step E-Commerce B2B
Sebuah platform E-Commerce enterprise berbasis Next.js App Router mengalami insiden produksi kritis:
1. **The Issue:** Pembeli enterprise dialihkan ke keranjang kosong saat memproses invoice pembayaran pesanan bernilai tinggi.
2. **The Root Cause:** Pengembang menggunakan Server Action untuk mutasi stok dan membuat sesi order, diikuti dengan pemanggilan `revalidatePath('/checkout')` dan `redirect('/checkout/confirmation')`. Pada pengujian lokal dengan network tanpa latensi, proses berjalan mulus. Namun di produksi dengan latensi database 150ms, hidrasi form client-side mengalami *race condition*; state optimistik me-reset data cart sebelum server context sepenuhnya ter-resolve.
3. **The Solution:** 
   * Implementasi pengujian E2E integrasi penuh yang mensimulasikan latensi backend nyata (*network throttling/simulation*).
   * Verifikasi mutasi data atomik terhadap database transaksi Postgres yang di-branching via ephemeral databases (bukan mocking fiktif).
   * Eksekusi automasi CI/CD berbasis GitHub Actions yang memvalidasi integritas alur checkout multi-step dari: Seleksi Item -> Lock Quota -> Tanda Tangan Kontrak Digital via Canvas -> Revalidasi Server Actions -> Eksekusi Invoice Confirmation.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi end-to-end lengkap yang memvalidasi skenario B2B checkout, termasuk pipeline GitHub Actions produksi:

### 1. File Pengujian: `tests/e2e/b2b-checkout-flow.spec.ts`

```typescript
import { test, expect } from '@playwright/test';

test.describe('E2E Alur Transaksi B2B Checkout & Mutasi Stok Atomik', () => {
  const TEST_PRODUCT_SKU = 'PROD-ENT-992';

  test.beforeEach(async ({ page }) => {
    // Intercept API telemetry pihak ketiga agar tidak mencemari network trace
    await page.route('https://telemetry.analytics.io/**', (route) => route.abort());
  });

  test('Harus memvalidasi mutasi Server Action dan integritas invoice pesanan', async ({ page, context }) => {
    // 1. Kunjungi halaman katalog produk B2B
    await page.goto(`/products/${TEST_PRODUCT_SKU}`);

    // Validasi SSR render produk berhasil
    const productTitle = page.getByRole('heading', { level: 1, name: /Server Node Alpha/i });
    await expect(productTitle).toBeVisible();

    // 2. Manipulasi Kuantitas Produk
    const quantityInput = page.getByLabel(/jumlah unit/i);
    await quantityInput.clear();
    await quantityInput.fill('50');

    // 3. Masukkan ke keranjang (Memicu Server Action mutasi inventaris)
    const addToCartButton = page.getByRole('button', { name: /tambah ke pengadaan/i });
    
    // Dengarkan mutasi network Server Action (POST dengan header next-action)
    const serverActionPromise = page.waitForResponse(
      (response) =>
        response.url().includes(`/products/${TEST_PRODUCT_SKU}`) &&
        response.request().method() === 'POST' &&
        response.status() === 200
    );

    await addToCartButton.click();
    await serverActionPromise;

    // 4. Navigasi ke halaman checkout
    await page.getByRole('link', { name: /buka keranjang/i }).click();
    await expect(page).toHaveURL(/\/checkout/);

    // 5. Validasi State Order & Suspense Boundary Hydration
    const orderSummaryTable = page.getByRole('table', { name: /rincian item/i });
    await expect(orderSummaryTable).toBeVisible();
    await expect(orderSummaryTable.getByText(TEST_PRODUCT_SKU)).toBeVisible();

    // 6. Masukkan Alamat Pengiriman & Metode Pembayaran Term-of-Payment (TOP)
    await page.getByLabel(/catatan invoice pengadaan/i).fill('PO-CORP-2026-X1');
    const paymentSelect = page.getByRole('combobox', { name: /termin pembayaran/i });
    await paymentSelect.selectOption('NET_60');

    // 7. Submit Checkout Akhir
    const submitOrderButton = page.getByRole('button', { name: /konfirmasi & buat pesanan/i });
    await submitOrderButton.click();

    // 8. Verifikasi Redirect Deterministik ke halaman Sukses
    await expect(page).toHaveURL(/\/checkout\/confirmation\/[a-zA-Z0-9-]+/);
    
    // Asersi bahwa UI konfirmasi merender data transaksi final yang akurat
    const confirmationBanner = page.getByRole('alert');
    await expect(confirmationBanner).toContainText(/pesanan berhasil dibuat/i);
    await expect(page.getByText('Termin: NET 60')).toBeVisible();
  });
});
```

### 2. Workflow Production CI/CD: `.github/workflows/e2e-matrix-cicd.yml`

```yaml
name: Production Quality Gate & E2E Sharded Pipeline

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

permissions:
  contents: read
  id-token: write
  pull-requests: write

concurrency:
  group: ${{ github.workflow }}-${{ github.head_ref || github.run_id }}
  cancel-in-progress: true

env:
  NODE_VERSION: 20.11.0
  PNPM_VERSION: 8.15.4

jobs:
  static-analysis:
    name: Lint, Types & Security Audit
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Source Code
        uses: actions/checkout@v4

      - name: Setup PNPM Environment
        uses: pnpm/action-setup@v3
        with:
          version: ${{ env.PNPM_VERSION }}

      - name: Setup Node.js Runtime
        uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: 'pnpm'

      - name: Install Project Dependencies
        run: pnpm install --frozen-lockfile

      - name: Typecheck Next.js TypeScript
        run: pnpm exec tsc --noEmit

      - name: Lint Rules Validation
        run: pnpm run lint

  build-artifact:
    name: Standalone Production Build
    needs: [static-analysis]
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Source Code
        uses: actions/checkout@v4

      - name: Setup PNPM Environment
        uses: pnpm/action-setup@v3
        with:
          version: ${{ env.PNPM_VERSION }}

      - name: Setup Node.js Runtime
        uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: 'pnpm'

      - name: Setup Next.js Compiler Cache
        uses: actions/cache@v4
        with:
          path: |
            ${{ github.workspace }}/.next/cache
          key: next-cache-${{ runner.os }}-${{ hashFiles('**/pnpm-lock.yaml') }}-${{ github.sha }}
          restore-keys: |
            next-cache-${{ runner.os }}-${{ hashFiles('**/pnpm-lock.yaml') }}-

      - name: Install Dependencies
        run: pnpm install --frozen-lockfile

      - name: Build Next.js Application
        env:
          NEXT_TELEMETRY_DISABLED: 1
          NODE_ENV: production
        run: pnpm run build

      - name: Compress and Upload Build Artifacts
        uses: actions/upload-artifact@v4
        with:
          name: standalone-build
          retention-days: 1
          path: |
            .next/standalone
            .next/static
            public

  e2e-matrix-test:
    name: Playwright Shard ${{ matrix.shardIndex }}/${{ matrix.totalShards }}
    needs: [build-artifact]
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        shardIndex: [1, 2, 3, 4]
        totalShards: [4]
    steps:
      - name: Checkout Source Code
        uses: actions/checkout@v4

      - name: Setup PNPM Environment
        uses: pnpm/action-setup@v3
        with:
          version: ${{ env.PNPM_VERSION }}

      - name: Setup Node.js Runtime
        uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: 'pnpm'

      - name: Install Dependencies
        run: pnpm install --frozen-lockfile

      - name: Download Build Artifact
        uses: actions/download-artifact@v4
        with:
          name: standalone-build

      - name: Restore Standalone Assets Structure
        run: |
          mkdir -p .next/standalone/.next/static
          cp -R .next/static .next/standalone/.next/
          cp -R public .next/standalone/

      - name: Cache Playwright Browser Binaries
        id: playwright-cache
        uses: actions/cache@v4
        with:
          path: ~/.cache/ms-playwright
          key: playwright-${{ runner.os }}-${{ hashFiles('**/pnpm-lock.yaml') }}

      - name: Install Playwright Dependencies & Browsers
        if: steps.playwright-cache.outputs.cache-hit != 'true'
        run: pnpm exec playwright install --with-deps chromium

      - name: Execute E2E Tests on Matrix Shard
        env:
          CI: true
          NODE_ENV: production
          PORT: 3000
        run: >
          pnpm exec playwright test
          --shard=${{ matrix.shardIndex }}/${{ matrix.totalShards }}
          --project=chromium

      - name: Upload Test Results Artifact
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-report-shard-${{ matrix.shardIndex }}
          retention-days: 7
          path: |
            playwright-report/
            test-results/
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Aspek Komparasi | Cypress | Playwright | Puppeteer |
| :--- | :--- | :--- | :--- |
| **Arsitektur Internal** | Berjalan di dalam run-loop browser yang sama (*in-browser DOM injection*). | Mengontrol browser melalui protokol devtools native (*out-of-process WebSocket CDP*). | Mengontrol Chrome via DevTools Protocol mentah (*low-level headless API*). |
| **Dukungan Multi-Tab & Iframe** | Sangat terbatas; memerlukan *workarounds* rumit. | *First-class support*; multi-context dan multi-tab native. | Didukung penuh, namun orkestrasi context manual. |
| **Dukungan App Router & RSC** | Kurang optimal menangani async streaming payload dan RSC without hydration flickers. | Unggul; isolasi *StorageState*, tracing, auto-wait yang kompatibel dengan React Streaming. | Membutuhkan implementasi custom harness untuk meniru fungsionalitas assertion. |
| **Kecepatan Paralelisasi** | Bergantung pada Cypress Cloud komersial atau plugin rumit pihak ketiga. | Built-in CLI Sharding (`--shard=x/y`) tanpa biaya tambahan; threading paralel per core CPU. | Skalabilitas manual; tidak ada test runner terintegrasi. |
| **Resource Footprint (CI)** | Menengah-Tinggi (memory consumption tinggi akibat DOM injection wrapper). | Sangat Efisien (Context browser terisolasi berbagi instance proses induk). | Sangat Ringan, namun beban implementasi tooling jatuh ke tim internal. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The "Hydration Race Condition" pada Dynamic Suspense
* **Gejala:** Playwright mengeklik tombol sebelum Event Handler terikat ke tree DOM. Klik dicatat oleh engine browser, tetapi aksi React (misal Server Action dispatch) tidak pernah terpicu.
* **Akar Masalah:** Next.js melakukan *streaming HTML* terlebih dahulu untuk visual responsif. Tombol tampak sudah aktif (*interactive look*), namun bundle chunk JavaScript client untuk *island* tersebut masih dalam proses transfer jaringan atau parsing execution.
* **Mitigasi:** Pasang indikator deterministik pada elemen interaktif, seperti atribut `data-hydrated="true"` melalui custom hook:
```typescript
// components/submit-button.tsx
'use client';
import { useState, useEffect } from 'react';

export function SubmitButton() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  return (
    <button type="submit" data-hydrated={mounted} disabled={!mounted}>
      Submit Mutasi
    </button>
  );
}
```
Di Playwright, buat locator yang secara eksplisit menunggu atribut tersebut:
```typescript
await expect(page.locator('button[type="submit"][data-hydrated="true"]')).toBeVisible();
await page.locator('button[type="submit"][data-hydrated="true"]').click();
```

### 2. Kebocoran Shared State saat Paralelisasi DB
* **Gejala:** Test Suite A mengedit pengguna dengan ID `user-123`, menyebabkan Test Suite B yang berjalan bersamaan di worker lain gagal membaca state awal (*flaky mutation*).
* **Mitigasi:** Jangan gunakan single database untuk paralel test. Gunakan pola:
  1. *Dynamic Tenant/User Isolation*: Setiap file test meng-generate UUID acak untuk entitas yang dimanipulasi (`test-user-${crypto.randomUUID()}@enterprise.internal`).
  2. *Database Branching*: Pada CI, gunakan API (misal Neon/Supabase API) untuk membuat snapshot database terpisah per shard secara instan, lalu hancurkan branch setelah step selesai.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Menggunakan `page.waitForTimeout(5000)`
* **Kesalahan Fatal:** Menggunakan sleep arbitrary untuk menunggu loading data selesai. Hal ini memperlambat eksekusi dan tetap rentan gagal jika network spike melebihi timeout tersebut.
* **Solusi Anti-Flake:** Selalu gunakan asersi berbasis web assertion atau *network promise*:
```typescript
// SALAH
await page.waitForTimeout(3000);
await page.getByText('Konfirmasi').click();

// BENAR
await expect(page.getByRole('button', { name: 'Konfirmasi' })).toBeEnabled();
await page.getByRole('button', { name: 'Konfirmasi' }).click();
```

### 2. Mengabaikan Copy Static Assets pada Standalone Build
* **Kesalahan Fatal:** Menjalankan standalone build Next.js di CI (`node .next/standalone/server.js`), namun lupa menyalin folder `.next/static` dan `public` ke dalam direktori standalone. Hasilnya, UI kehilangan CSS (Tailwind) dan aset gambar, memicu `404 Not Found` pada ratusan resource statis dan menggagalkan seluruh E2E suite.
* **Solusi Anti-Flake:** Selalu jalankan sinkronisasi folder seperti pada baris konfigurasi CI:
```bash
cp -R .next/static .next/standalone/.next/
cp -R public .next/standalone/
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

### Page Object Model (POM) Berbasis Dekomposisi Fungsional
Abstraksikan seluruh interaksi DOM ke dalam kelas modular yang memetakan boundary arsitektur halaman atau fitur:

```typescript
// tests/e2e/pages/dashboard.page.ts
import { type Page, type Locator, expect } from '@playwright/test';

export class DashboardPage {
  readonly page: Page;
  readonly analyticsHeading: Locator;
  readonly exportReportButton: Locator;

  constructor(page: Page) {
    this.page = page;
    this.analyticsHeading = page.getByRole('heading', { level: 1, name: /dashboard analitik/i });
    this.exportReportButton = page.getByRole('button', { name: /unduh laporan csv/i });
  }

  async navigate() {
    await this.page.goto('/dashboard');
    await expect(this.analyticsHeading).toBeVisible();
  }

  async exportReport() {
    const downloadPromise = this.page.waitForEvent('download');
    await this.exportReportButton.click();
    return await downloadPromise;
  }
}
```

### Standar Penamaan & Labeling Selektor
* **Hierarki Prioritas Locator (Standar W3C):**
  1. `page.getByRole()` (Memvalidasi aksesibilitas screen reader secara implisit)
  2. `page.getByLabel()` (Ideal untuk