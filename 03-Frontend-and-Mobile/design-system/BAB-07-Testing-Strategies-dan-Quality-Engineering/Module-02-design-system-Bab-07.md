# Kurikulum Enterprise: Design System Engineering
## Kategori: 03-Frontend-and-Mobile
### BAB 07: Testing Strategies & Quality Engineering
#### Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Mendesain dan Mengorkestrasi Pipeline Visual Regression Testing (VRT)** berskala enterprise menggunakan Playwright dan headless container yang deterministik untuk memitigasi flakiness akibat *sub-pixel antialiasing*, *font-rendering*, dan variasi GPU.
2. **Mengimplementasikan Behavioral & Interaction Testing** berbasis *Component Story Format* (CSF 3) dan Storybook Test Runner yang memanfaatkan instrumentasi `@storybook/addon-interactions` dan `@testing-library` di level browser nyata.
3. **Membangun Automated Accessibility (a11y) Engine** berbasis `axe-core` yang terintegrasi secara modular ke dalam pipeline pengujian unit, interaksi, dan E2E tanpa menciptakan *alert fatigue*.
4. **Menerapkan Contract & Token Testing** guna memvalidasi kepatuhan semantik token desain (W3C Design Tokens Community Group specification) dari hulu (*design tool*) ke hilir (*runtime CSS/JS/Native*).
5. **Mengintegrasikan Mutation Testing** menggunakan Stryker Mutator untuk mengaudit ketahanan test suite pada komponen atomik dan molekuler kritis.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, engineer wajib memiliki pemahaman mendalam tentang:
*   Arsitektur dasar React 18+ (Fiber reconciler, concurrent rendering, dynamic layout effects).
*   Dasar-dasar Storybook 7/8 (CSF 3, Args, Decorators, Loaders).
*   Dasar pengujian unit dengan Vitest atau Jest.
*   Spesifikasi W3C Web Content Accessibility Guidelines (WCAG) 2.1/2.2 AA.
*   Containerization dasar dengan Docker untuk determinisme OS-level rendering.
*   Node.js runtime v18/v20 LTS dan package manager (pnpm workspace diutamakan).

---

### 3. Concept & Internal Architecture

Memastikan reliabilitas sebuah enterprise design system membutuhkan pendekatan multi-tier yang jauh melampaui pengujian unit murni berbasis DOM tiruan (seperti JSDOM/HappyDOM). 

#### 3.1. Keterbatasan JSDOM vs Browser Engine Asli
JSDOM tidak memiliki *layout engine*, *compositor*, maupun subsistem rendering grafis. Akibatnya, properti layout kompleks seperti:
*   CSS Grid subgrid alignment
*   Flexbox edge-cases
*   Container queries
*   Z-index stacking context isolation
*   BoundingClientRect calculations
*   Pseudo-element rendering (`::before`, `::after`)

sepenuhnya tidak terverifikasi jika hanya mengandalkan unit test berbasis node.js. Oleh karena itu, arsitektur quality engineering design system modern beroperasi di level *real browser engine* (Blink/WebKit/Gecko) melalui protokol CDP (Chrome DevTools Protocol) atau WebDriver BiDi.

#### 3.2. Anatomi Engine Visual Regression Testing
Pipeline Visual Regression memotret representasi raster (skia/pixel buffer) dari komponen dan membandingkannya menggunakan algoritma *pixel-diffing* (misalnya `pixelmatch` atau library berbasis SSIM—*Structural Similarity Index Measure*).

```
[Component Story / Fixture]
          │
          ▼
┌─────────────────────────┐
│ Browser Instance (CDP)  │ ◄─── Disable Animations (prefers-reduced-motion)
│ (Chromium / WebKit)     │ ◄─── Force Fixed Viewport & High-DPI Scaling
└──────────┬──────────────┘ ◄─── Freeze Web Fonts (document.fonts.ready)
           │
           ▼
┌─────────────────────────┐
│ Rasterizer Buffer (PNG) │
└──────────┬──────────────┘
           │
           ├────────────────────────────┐
           ▼                            ▼
┌─────────────────────┐      ┌─────────────────────┐
│  Baseline Artifact  │      │   Current Render    │
└──────────┬──────────┘      └──────────┬──────────┘
           │                            │
           └──────────────┬─────────────┘
                          ▼
           ┌─────────────────────────────┐
           │ Pixelmatch / SSIM Engine    │
           │ (Color Tolerance: Delta E)  │
           └──────────────┬──────────────┘
                          │
          ┌───────────────┴───────────────┐
          ▼                               ▼
[Delta == 0 or < Threshold]    [Delta > Threshold -> FAIL]
  (Auto-approved)                (Diff Artifact Generation)
```

Tiga pilar determinisme visual dalam engine ini adalah:
1.  **Font Stabilization**: Menghindari *Flash of Unstyled Text* (FOUT) atau *Flash of Invisible Text* (FOIT) dengan memblokir execution loop sampai promise `document.fonts.ready` resolve secara penuh dan menyuntikkan font biner lokal via CSS `@font-face`.
2.  **Clock Virtualization & Dynamic Content Freezing**: Menghentikan CSS animations, Web Animations API (WAAPI), GIF loops, dan mock timer sistem via `Date.now()` virtualization.
3.  **Headless Host Virtualization**: Menjalankan browser di dalam container Linux standar (misal: Debian/Ubuntu dengan library fontconfig seragam) untuk menghilangkan perbedaan antialiasing font rendering antara macOS, Windows, dan Linux runner CI.

#### 3.3. Arsitektur Aksesibilitas Terautomasi (a11y Engine)
`axe-core` bekerja dengan memindai DOM Tree yang telah ter-render secara penuh, mengevaluasi representasi aksesibilitas (*Accessibility Tree* / AOM) terhadap aturan WCAG. Pembedahan arsitektural:
*   **Ruleset Matrix**: Rules dievaluasi berdasarkan selector, context (misal `role`, `aria-*`), dan computed style.
*   **Contrast Calculation Engine**: Memvalidasi rasio kontras warna latar belakang dan teks, dengan memperhitungkan *blending mode*, *alpha channel*, dan *pseudo-background* elemen tumpuk.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional | Enterprise Production Quality Architecture |
| :--- | :--- | :--- |
| **Testing Target** | Logic JS/TS via JSDOM mocks. | UI visual raster, AOM (Accessibility Tree), dan behavioral interaction di real-browser engine. |
| **Visual Regressions**| Manual visual QA testing oleh tim QA di stage staging. | Automated Pixel-by-Pixel Diffing & SSIM terintegrasi pada setiap Pull Request. |
| **A11y Strategy** | Manual audit berkala via screen reader (lambat, non-preventive). | Automated continuous axe-core linting + programmatic keyboard traversal assertation. |
| **Design Tokens** | Dianggap statis, diverifikasi via penglihatan desainer. | Dynamic token schema validation (JSON Schema/Zod) + automated cross-check style rendering. |
| **Determinisme** | Test suite "hijau" di lokal, gagal/flaky di CI pipeline karena latency rendering. | Containerized deterministic rendering environments dengan freezing viewport, font, dan motion clock. |

---

### 5. How (Workflow Detail)

Alur kerja arsitektural pengujian enterprise design system mengikuti state machine berikut:

```
[Developer pushes commit]
          │
          ▼
┌────────────────────────────────────────────────────────┐
│ 1. Static Contract & Token Tests                       │
│    - Schema validation (Zod)                           │
│    - CSS Variable compilation sanity                   │
└──────────────────────────┬─────────────────────────────┘
                           │ Pass
                           ▼
┌────────────────────────────────────────────────────────┐
│ 2. Unit & Logic Mutation Validation (Vitest + Stryker) │
│    - Pure logic validation (Aria utils, math clamps)   │
│    - Mutation Score threshold check (Min. 80%)         │
└──────────────────────────┬─────────────────────────────┘
                           │ Pass
                           ▼
┌────────────────────────────────────────────────────────┐
│ 3. Isolated Component Story Compilation (Storybook)    │
│    - Build static static-storybook target              │
└──────────────────────────┬─────────────────────────────┘
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
┌──────────────────────────┐┌──────────────────────────┐
│ 4a. Interaction & A11y   ││ 4b. Containerized VRT    │
│     Tests                ││     Execution            │
│  - Playwright Testrunner ││  - Matrix: Chromium,     │
│  - Storybook Play-fn     ││    WebKit, Mobile        │
│  - Injected Axe audits   ││  - Threshold: SSIM 0.99  │
└────────────┬─────────────┘└────────────┬─────────────┘
             │                           │
             └─────────────┬─────────────┘
                           │ Aggregated Report
                           ▼
┌────────────────────────────────────────────────────────┐
│ 5. Pull Request Gate Evaluation                        │
│    - If Visual Diff > 0: Request Designer Approval     │
│    - If A11y Violations > 0: Block Merge               │
│    - If All Pass: Green Light to Canary Release        │
└────────────────────────────────────────────────────────┘
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Sistem
Komponen Design System ibarat **komponen presisi pada industri otomotif**. 
*   **Unit testing (JSDOM)** sama dengan mengukur volume blok silinder mesin di atas kertas kalkulasi tanpa pernah mencobanya dengan cairan bahan bakar.
*   **Visual Regression Testing (Playwright/Pixel Diff)** adalah kamera inspeksi optik berkecepatan tinggi yang memindai toleransi mikron fisik baut dan rangka untuk mendeteksi pembengkokan yang kasat mata.
*   **Accessibility Testing (axe-core)** adalah uji sertifikasi kelayakan keselamatan jalan: jika pintu tidak bisa dibuka dari dalam (analog: tombol tidak bisa diakses keyboard/screen reader), mobil dilarang keluar pabrik.

#### Arsitektur Test Harness:
```
+-----------------------------------------------------------------------------------+
| Host CI Agent (e.g., GitHub Actions Runner / Linux x86_64)                        |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | Docker Container (e.g., mcr.microsoft.com/playwright:v1.40.0-focal)         |  |
|  |                                                                             |  |
|  |  +------------------------+  IPC / CDP     +-----------------------------+  |  |
|  |  | Playwright Engine      | <============> | Headless Chromium Context   |  |  |
|  |  | (Runner Process)       |                | - Fixed GPU/Software Raster |  |  |
|  |  | - Viewport: 1280x720   |                | - System Fonts Injected     |  |  |
|  |  | - ScaleFactor: 2 (HiDPI)|               | - CSS Animations: Disabled  |  |  |
|  |  +-----------┬------------+                +--------------┬--------------+  |  |
|  |              │                                             │                |  |
|  |              │ Run Storybook Play Interaction              │ Native Paint   |  |
|  |              ▼                                             ▼                |  |
|  |    +-------------------+                         +------------------+       |  |
|  |    | @testing-library  |                         | Raw Frame Buffer |       |  |
|  |    | axe-core Engine   |                         | (Pixel Matrix)   |       |  |
|  |    +---------┬---------+                         +--------┬---------+       |  |
|  |              │ Violations?                                │ Pixel Diff?     |  |
|  +--------------┼────────────────────────────────────────────┼-----------------+  |
|                 │                                            │                    |
+-----------------┼--------------------------------------------┼--------------------+
                  ▼                                            ▼
          [Exit Code: 1/0]                             [Diff Image Artifact]
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Validasi Desain Token Semantik (Zod)
Sebelum merender komponen, kontrak token harus diuji integritasnya.

```typescript
// tokens/token-schema.test.ts
import { describe, it, expect } from 'vitest';
import { z } from 'zod';

const ColorTokenSchema = z.object({
  value: z.string().regex(/^#(?:[0-9a-fA-F]{3}){1,2}$|^rgba?\([\d\s,%.]+\)$/, {
    message: 'Token color value harus berupa hex valid atau format rgb/rgba',
  }),
  type: z.literal('color'),
  description: z.string().min(5),
  extensions: z.object({
    wcagTargetContrast: z.enum(['AA', 'AAA']),
  }),
});

const DesignTokensPayload = {
  'color-action-primary-default': {
    value: '#0052CC',
    type: 'color',
    description: 'Tombol interaktif state primer',
    extensions: {
      wcagTargetContrast: 'AA',
    },
  },
};

describe('Design Tokens Contract Testing', () => {
  it('harus mematuhi spesifikasi W3C DTCG Token format', () => {
    Object.entries(DesignTokensPayload).forEach(([tokenName, tokenData]) => {
      const result = ColorTokenSchema.safeParse(tokenData);
      expect(
        result.success,
        `Token "${tokenName}" melanggar skema: ${result.error?.message}`
      ).toBe(true);
    });
  });
});
```

#### 7.2. Practical Example: Production-Ready Behavioral, A11y & Visual Test Harness

Berikut adalah implementasi komponen enterprise `DropdownMenu` beserta test suite lengkap yang mencakup behavioral interaction, automated accessibility audit via axe, dan visual snapshotting deterministik.

##### Komponen & Story (CSF 3)
```typescript
// src/components/DropdownMenu/DropdownMenu.stories.tsx
import type { Meta, StoryObj } from '@storybook/react';
import { within, userEvent, expect } from '@storybook/test';
import { DropdownMenu } from './DropdownMenu';

const meta: Meta<typeof DropdownMenu> = {
  title: 'Components/DropdownMenu',
  component: DropdownMenu,
  parameters: {
    layout: 'centered',
  },
};

export default meta;
type Story = StoryObj<typeof DropdownMenu>;

export const Default: Story = {
  args: {
    label: 'Preferensi Akun',
    items: [
      { id: '1', label: 'Profil Pengguna' },
      { id: '2', label: 'Keamanan' },
      { id: '3', label: 'Keluar', isDestructive: true },
    ],
  },
  play: async ({ canvasElement, step }) => {
    const canvas = within(canvasElement);
    const triggerButton = canvas.getByRole('button', { name: /preferensi akun/i });

    await step('Initial State Check', async () => {
      await expect(triggerButton).toHaveAttribute('aria-expanded', 'false');
      await expect(canvas.queryByRole('menu')).toBeNull();
    });

    await step('Trigger Click Opens Menu & Sets Focus', async () => {
      await userEvent.click(triggerButton);
      const menu = await canvas.findByRole('menu');
      await expect(menu).toBeInTheDocument();
      await expect(triggerButton).toHaveAttribute('aria-expanded', 'true');
      
      const firstItem = canvas.getByRole('menuitem', { name: /profil pengguna/i });
      await expect(firstItem).toHaveFocus();
    });

    await step('Keyboard Navigation Traversal', async () => {
      await userEvent.keyboard('{ArrowDown}');
      const secondItem = canvas.getByRole('menuitem', { name: /keamanan/i });
      await expect(secondItem).toHaveFocus();
    });
  },
};
```

##### Production Playwright Test Harness (A11y + Visual Snapshotting)
```typescript
// tests/dropdown-menu.vrt.spec.ts
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const TARGET_URL = 'http://localhost:6006/iframe.html?id=components-dropdownmenu--default&viewMode=story';

test.describe('DropdownMenu Component: Quality Audit Suite', () => {
  test.beforeEach(async ({ page }) => {
    // 1. Stabilisasi Browser Environment
    await page.goto(TARGET_URL);
    await page.evaluate(async () => {
      // Pastikan semua fonts telah ter-download dan terpasang di layout
      await document.fonts.ready;
    });

    // 2. Inject CSS untuk mendisable semua transisi dan animasi CSS
    await page.addStyleTag({
      content: `
        *, *::before, *::after {
          -moz-animation: none !important;
          -webkit-animation: none !important;
          animation: none !important;
          -moz-transition: none !important;
          -webkit-transition: none !important;
          transition: none !important;
          caret-color: transparent !important;
        }
      `,
    });
  });

  test('harus lolos audit aksesibilitas (axe-core WCAG 2.1 AA) pada status terbuka', async ({ page }) => {
    const trigger = page.getByRole('button', { name: /preferensi akun/i });
    await trigger.click();
    await page.waitForSelector('[role="menu"]');

    const accessibilityScanResults = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
      .include('[role="menu"]')
      .analyze();

    expect(accessibilityScanResults.violations).toEqual([]);
  });

  test('harus memvalidasi pixel snapshot secara deterministik pada state menu terbuka', async ({ page }) => {
    const trigger = page.getByRole('button', { name: /preferensi akun/i });
    await trigger.click();
    await page.waitForSelector('[role="menu"]');

    // Menstabilkan posisi kursor mouse keluar viewport agar tidak memicu hover state pseudo-classes
    await page.mouse.move(0, 0);

    // Visual Snapshot Capture
    const menuElement = page.locator('[data-test-id="dropdown-container"]');
    await expect(menuElement).toHaveScreenshot('dropdown-menu-open.png', {
      animations: 'disabled',
      threshold: 0.05, // 5% toleransi maksimum per-pixel channel threshold
      maxDiffPixels: 0, // Toleransi 0 piksel deviasi untuk elemen presisi
    });
  });
});
```

---

### 8. Real World Case Study: Global Multi-Brand Fintech

#### Konteks & Masalah
Sebuah korporasi multi-fintech mengelola **3 aplikasi Super-App** (Brand Alpha, Brand Beta, Brand Gamma) dari satu repository inti monorepo Design System. Mereka menghadapi masalah:
1.  **Cross-tenant Collision**: Update komponen `ModalDialog` untuk Brand Alpha tanpa sengaja mematahkan tampilan Brand Beta (padding terpotong) dan Brand Gamma (kontras warna teks turun menjadi 2.1:1, memicu risiko audit regulasi keuangan).
2.  **Flaky Pipelines**: CI memakan waktu 48 menit dengan *false-positive* visual failure sebesar 32% setiap kali pipeline berjalan di GitHub Actions karena perbedaan dynamic font rendering antar sistem operasi worker.

#### Arsitektur Solusi
Tim Platform Engineering mengimplementasikan strategi:
1.  **Multi-Theme Matrix Isolation**: Setiap Storybook story digenerasi silang (cross-product) dengan parameter tema:
    `[Component] x [Brand Alpha, Brand Beta, Brand Gamma] x [Light, Dark] x [RTL, LTR]`.
2.  **Containerized Headless Visual Runner**: Membungkus Playwright dalam custom Docker Image (`debian:bookworm-slim` + Google Fonts cached biner lokal).
3.  **Sharding Pipeline**: Menjalankan matrix visual tests pada 8 parallel shard nodes di CI.

#### Hasil Terukur (Metrics)
*   Durasi Pipeline CI terpangkas dari **48 menit** menjadi **6.2 menit** berkat sharding pararel.
*   *Flakiness rate* Visual Test turun dari **32%** menjadi **0.02%**.
*   Menangkap **17 regresi visual fatal** dan **4 pelanggaran aksesibilitas WCAG** di tingkat PR sebelum mencapai environment staging sepanjang Q3.

---

### 9. Trade-offs

Mengadopsi strategi testing level mendalam melibatkan kalkulasi kompromi arsitektural yang ketat:

| Strategi | Keuntungan (Pros) | Biaya & Konsekuensi (Cons) | Mitigasi Solutif |
| :--- | :--- | :--- | :--- |
| **Self-Hosted Containerized Playwright vs Cloud SaaS (Chromatic/Percy)** | Zero SaaS seat cost; Kontrol penuh atas data sekuritas dan network boundary lokal. | Beban pemeliharaan storage baseline artifact (S3/GCS); Beban komputasi CI mandiri tinggi. | Gunakan Git LFS atau AWS S3 Bucket ber-lifecycle policy untuk menyimpan baseline visual snapshots. |
| **Broad Axe-core Scanning vs Strict Zero-Violation Gate** | Menangkap pelanggaran aksesibilitas langsung di PR. | *Alert fatigue* akibat false positives pada dynamic calculation elemen pihak ketiga. | Batasi selector audit (`include`/`exclude`), filter hanya ruleset non-eksperimental (`wcag2aa`). |
| **Mutation Testing (Stryker)** | Menjamin kualitas dan integritas assertion test, bukan sekadar *line coverage* palsu. | Sangat rakus CPU; Memperpanjang durasi CI berlipat-lipat. | Jalankan Stryker hanya pada komponen inti (Atoms) secara berkala (Nightly Cron Job), bukan di setiap PR. |
| **Threshold Pixel Diffing (Strict: 0px vs Permissive: >1%)** | Menjamin konsistensi visual 100% presisi. | Rentan gagal karena perbedaan antialiasing GPU raster rendering tipis. | Terapkan algoritma SSIM (Structural Similarity) daripada Raw Pixel Difference, dan set fixed DPI. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Mengabaikan Dynamic Scrollbars dan Mouse Position
*   **Masalah**: Visual test acak gagal (*intermittent failure*) karena scrollbar sistem kadang muncul, atau kursor mouse default berada di atas elemen sehingga memicu status `:hover`.
*   **Solusi**:
    ```typescript
    // playwright.config.ts
    use: {
      viewport: { width: 1280, height: 720 },
      deviceScaleFactor: 1, // Hindari non-integer scale factor
      launchOptions: {
        args: [
          '--hide-scrollbars',
          '--disable-font-subpixel-positioning',
          '--disable-lcd-text',
        ],
      },
    }
    ```

#### 10.2. Font Flashing (FOUT/FOIT)
*   **Masalah**: Playwright mengambil screenshot sebelum web fonts selesai dirender, menghasilkan snapshot dengan font fallback sistem (Times New Roman / Arial).
*   **Solusi**: Block snapshot sampai layout siap:
    ```typescript
    await page.evaluate(() => document.fonts.ready);
    ```

#### 10.3. Piercing Web Components & Shadow DOM pada Audit Aksesibilitas
*   **Masalah**: Komponen yang menggunakan encapsulation Shadow DOM tidak terpindai oleh standard document querySelector pada beberapa versi rule runner.
*   **Solusi**: Pastikan engine `axe-core` dikonfigurasi melintasi Shadow Root boundaries secara eksplisit (secara default diaktifkan pada `@axe-core/playwright` v4.6+ via tree-traversal context).

---

### 11. Best Practices (Production Checklist)

1. [ ] **Deterministic Rendering Environment**: Semua baseline visual digenerasi HANYA dari dalam Docker image identik yang sama dengan environment CI.
2. [ ] **Disable All Animations**: Matikan CSS Transition, Animation, dan smooth-scrolling di level browser testing context.
3. [ ] **A11y Automated Rule Gating**: Blok PR jika ditemukan pelanggaran kategori `critical` dan `serious` dari audit `axe-core`.
4. [ ] **Color Contrast under Context**: Verifikasi rasio kontras teks (minimal 4.5:1 untuk normal text, 3:1 untuk large text) pada semua tema (Light, Dark, High-Contrast).
5. [ ] **Keyboard Interaction Completeness**: Setiap komponen interaktif harus lolos uji: `Focus trap` (untuk dialog modal), `Esc` to dismiss, serta arrow navigation untuk menu dan combobox.
6. [ ] **Explicit Viewports**: Tes komponen pada breakpoint standar: Mobile (375px), Tablet (768px), Desktop (1280px).
7. [ ] **No Dynamic Mock Timestamps**: Hilangkan komponen jam, tanggal acak, atau placeholder dinamis (`faker.js`) dari visual fixtures.

---

### 12. Hands-on Practice

Siapkan struktur berikut untuk implementasi hands-on mandiri:

#### Direktori Target: `hands-on/m02/`

```bash
mkdir -p hands-on/m02
cd hands-on/m02
pnpm init
pnpm add -D @playwright/test @axe-core/playwright typescript
npx playwright install --with-deps chromium
```

#### Langkah 1: Buat Konfigurasi Playwright Deterministik
Simpan pada `hands-on/m02/playwright.config.ts`:

```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    viewport: { width: 1280, height: 720 },
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        launchOptions: {
          args: ['--hide-scrollbars', '--disable-lcd-text'],
        },
      },
    },
  ],
});
```

#### Langkah 2: Buat Test Suite Lengkap (A11y & VRT)
Simpan pada `hands-on/m02/tests/button.spec.ts`:

```typescript
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

// Simulasi HTML fixture langsung dalam pengujian mandiri
const HTML_PAYLOAD = `
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <title>Sandbox Component</title>
  <style>
    body { margin: 0; padding: 40px; font-family: sans-serif; }
    .btn {
      background-color: #0052cc;
      color: #ffffff;
      padding: 10px 20px;
      border: none;
      border-radius: 4px;
      cursor: pointer;
      font-size: 16px;
    }
    .btn:focus-visible {
      outline: 3px solid #ffab00;
      outline-offset: 2px;
    }
    .btn-disabled {
      background-color: #ebecf0;
      color: #a5adba;
      cursor: not-allowed;
    }
  </style>
</head>
<body>
  <main>
    <button class="btn" id="btn-primary">Aksi Utama</button>
  </main>
</body>
</html>
`;

test.describe('Hands-on: Quality Harness Verification', () => {
  test.beforeEach(async ({ page }) => {
    await page.setContent(HTML_PAYLOAD);
    await page.evaluate(() => document.fonts.ready);
  });

  test('Eksekusi Audit Aksesibilitas Terintegrasi', async ({ page }) => {
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa'])
      .analyze();
    
    expect(results.violations).toHaveLength(0);
  });

  test('Eksekusi Capture Visual Snapshot', async ({ page }) => {
    const button = page.locator('#btn-primary');
    await expect(button).toHaveScreenshot('button-primary-default.png');
  });
});
```

#### Langkah 3: Eksekusi dan Verifikasi Baseline
Jalankan perintah ini di terminal:
```bash
# Generate visual baseline pertama kali
npx playwright test --update-snapshots

# Jalankan pengujian untuk memverifikasi kecocokan
npx playwright test
```

---

### 13. Exercise

#### Level: Easy
*   **Tugas**: Konfigurasikan rule `color-contrast` pada `AxeBuilder` untuk mengabaikan selektor spesifik yang sengaja menggunakan style watermarked brand (misal `.brand-watermark`) agar tidak memicu alert kegagalan.
*   **Kriteria Keberhasilan**: Script Playwright menjalankan test dengan aturan axe, mengecualikan selektor tersebut, dan menghasilkan output test passed.

#### Level: Medium
*   **Tugas**: Buatlah custom Storybook CSF 3 Play Function untuk komponen `AccordionItem` yang menguji:
    1. Klik awal memperluas konten (`aria-expanded` berubah true).
    2. Menekan tombol `Space` atau `Enter` menutup kembali konten.
    3. Validasi bahwa konten yang tertutup memiliki attribute `hidden` atau `display: none` sehingga tidak terbaca oleh tab keyboard focus.
*   **Kriteria Keberhasilan**: Menggunakan `@storybook/test` assertions secara presisi tanpa error linting.

#### Level: Hard
*   **Tugas**: Rancang script validasi token multi-tier menggunakan Node.js dan Zod. Script harus membaca token JSON, mengompilasi CSS Custom Properties, kemudian memverifikasi menggunakan Playwright headless browser apakah nilai *computed style* (`window.getComputedStyle()`) dari dummy component benar-benar mencerminkan nilai token desimal yang dikonversi dari unit rem ke pixel secara akurat.
*   **Kriteria Keberhasilan**: Script otomatis mendeteksi jika terjadi kesalahan pembulatan (*rounding precision error*) pada konversi `rem` di level browser engine.

---

### 14. Challenge

#### Skenario: Arsitektur Continuous Visual & A11y Gate pada Monorepo Skala Raksasa

**Konteks Masalah**: 
Anda adalah Principal Quality Architect di sebuah perbankan digital. Sistem monorepo Anda mencakup **120 komponen atomik, molekuler, dan organismik** yang disajikan ke dalam 4 varian merk platform. Total stories mencapai lebih dari **1.500 variasi**. 

Saat ini, developer mengeluhkan waktu tunggu CI yang mencapai 90 menit dan storage artifact yang membengkak hingga puluhan gigabyte akibat ribuan image baseline PNG. Di sisi lain, perubahan kecil pada token global (misal: penyesuaian `$radius-sm` dari 4px ke 6px) menyebabkan kegagalan 1.200 visual snapshot secara bersamaan, melumpuhkan produktivitas rilis (PR merge lock).

**Spesifikasi Tantangan**:
1.  **Algoritma Smart Impact Detection**: Rancang arsitektur dependency graph parser (menggunakan tools seperti Turborepo / Nx / custom AST script) yang mampu menentukan stories mana saja yang secara langsung maupun tak langsung terpengaruh oleh perubahan file commit tertentu, sehingga VRT dan A11y tests *hanya* dijalankan pada subset komponen yang terdampak.
2.  **Mitigasi Blanket Failure**: Tentukan strategi penanganan ketika token level fondasi sengaja diperbarui. Bagaimana mengotomatisasi mekanisme *batch baseline approval* secara aman tanpa risiko menelan regresi yang tidak disengaja?
3.  **Toleransi Rendering Arsitektural**: Jelaskan pendekatan teknis arsitektur rendering layer Anda untuk menangani anti-aliasing font discrepancies lintas arsitektur mesin pengembang (M1/M2/M3 Apple Silicon ARM) dengan host CI (x86_64 AMD Linux Runners).

**Keluaran yang Diharapkan**:
*   Dokumen spesifikasi arsitektur teknis lengkap dengan diagram aliran proses (ASCII).
*   Pseudo-code atau script orkestrator pipeline CI (GitHub Actions workflow syntax terperinci).
*   SOP (Standard Operating Procedure) mitigasi *breaking visual changes* pada skala global token.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Pertanyaan)
1. **Mengapa JSDOM tidak memadai untuk mengeksekusi visual regression testing secara akurat?**
   - A. JSDOM tidak mendukung sintaks JavaScript ES6+.
   - B. JSDOM tidak memiliki layout, rasterization, dan typography-compositing engine asli.
   - C. JSDOM memerlukan akses root privilege pada mesin CI.
   - D. JSDOM tidak dapat membaca struktur file JSON.
   *Jawaban yang benar*: **B**. JSDOM adalah implementasi murni struktur DOM berbasis Node.js tanpa graphical layout computation dan rendering engine nyata.

2. **Apa fungsi dari pemanggilan `await page.evaluate(() => document.fonts.ready)` sebelum pengambilan screenshot visual?**
   - A. Mengompres ukuran file snapshot gambar.
   - B. Memastikan semua aset font telah ter-render penuh di memory guna mencegah FOUT/FOIT.
   - C. Mengubah seluruh font sistem menjadi monospace.
   - D. Mencegah user mengakses DOM komponen.
   *Jawaban yang benar*: **B**. Ini menjamin determinisme visual sehingga font kustom tidak terlambat dirender saat snapshot diambil.

3. **Komponen mana dari `axe-core` yang bertugas mendeteksi kontras rasio warna?**
   - A. DOM Traversal Node Parser.
   - B. Color Contrast Calculation Module yang menghitung delta luminansi WCAG 2.1.
   - C. Focus Trap Interceptor.
   - D. Canvas Blitter.
   *Jawaban yang benar*: **B**. Modul ini mengevaluasi relative luminance antara foreground dan background element.

4. **Dalam Storybook CSF 3, metode apa yang digunakan untuk mensimulasikan interaksi penekanan tombol oleh end-user secara asinkron?**
   - A. `userEvent.click()` dari `@storybook/test` / `@testing-library`.
   - B. `document.getElementById().click()`.
   - C. `process.nextTick()`.
   - D. `window.dispatchEvent(new Event('press'))`.
   *Jawaban yang benar*: **A**. `userEvent` menduplikasi siklus interaksi browser asli secara lengkap, termasuk focus, mouse down, mouse up, dan click.

5. **Apa fungsi utama dari CSS rule: `caret-color: transparent !important;` dalam pipeline pengujian visual Playwright?**
   - A. Menghapus border komponen.
   - B. Menghilangkan kedipan cursor teks (*blinking cursor*) pada elemen input form agar snapshot deterministik.
   - C. Meningkatkan kontras warna komponen.
   - D. Mempercepat eksekusi rendering browser.
   *Jawaban yang benar*: **B**. Kedipan kursor teks (animasi interval bawaan browser) adalah salah satu sumber utama *flakiness* pada VRT form components.

#### Intermediate (5 Pertanyaan)
6. **Perbedaan fundamental antara algoritma SSIM (Structural Similarity) dengan Raw Pixel Diffing (e.g., Pixelmatch standard) terletak pada:**
   - A. SSIM hanya memproses gambar grayscale murni tanpa warna.
   - B. SSIM mengevaluasi persepsi struktural, kontras, dan tekstur manusiawi, bukan sekadar perbedaan nilai warna individual per-koordinat piksel secara matematis kaku.
   - C. SSIM mengeksekusi testing secara langsung di database.
   - D. Pixelmatch membutuhkan GPU dedicated Nvidia CUDA.
   *Jawaban yang benar*: **B**. SSIM lebih tangguh terhadap pergeseran sub-pixel rendering mikro yang secara kasat mata tidak tampak oleh mata manusia.

7. **Bagaimana cara mencegah memory leak pada worker Playwright saat menjalankan ribuan visual stories dalam satu test run?**
   - A. Menghindari penutupan context browser.
   - B. Menetapkan parameter `reuseExistingServer: true`.
   - C. Membagi proses ke dalam multi-node sharding dan mengisolasi browser context per story (fresh context instantiation) serta me-recycle browser process secara berkala.
   - D. Menjalankan test tanpa opsi `--headed`.
   *Jawaban yang benar*: **C**. Context isolation dan process recycling mencegah pemborosan buffer V8 engine dan memory heap Chromium.

8. **Jika komponen `Tooltip` memunculkan violation axe-core `aria-describedby does not point to an existing ID`, kesalahan arsitektural apa yang paling mungkin terjadi?**
   - A. Browser kehabisan memori rendering.
   - B. Target referensi ID dinamis pada tooltip body belum ter-render di DOM saat event trigger dievaluasi, atau terjadi race-condition auto-generated ID.
   - C. Tooltip melanggar rasio kontras warna.
   - D. Komponen Tooltip tidak boleh menggunakan atribut ARIA.
   *Jawaban yang benar*: **B**. WAI-ARIA mewajibkan target referensi ID terdaftar di AOM sebelum atribut penunjuk diarahkan ke elemen tersebut.

9. **Apa peran Mutation Testing (seperti Stryker) di dalam design system core components?**
   - A. Mempercepat proses build TypeScript.
   - B. Menguji apakah test suite kita benar-benar mendeteksi kesalahan (fail-safe) dengan cara menyuntikkan kerusakan buatan (mutan) ke dalam source code logika komponen.
   - C. Mengubah warna komponen secara dinamis saat runtime.
   - D. Melakukan snapshot visual secara otomatis tanpa Playwright.
   *Jawaban yang benar*: **B**. Mutation testing menguji kualitas assertions pada unit tests agar tidak terjadi 100% code coverage semu tanpa validasi fungsional substantif.

10. **Mengapa nilai toleransi snapshot `threshold` tidak boleh disetel terlalu tinggi (misal: > 15%) pada design system?**
    - A. Memperlambat runtime eksekusi Playwright.
    - B. Dapat menoleransi dan meloloskan regresi visual fatal, seperti teks hilang, icon bergeser keluar container, atau perubahan warna brand yang signifikan.
    - C. Mengakibatkan CPU overheating pada runner CI.
    - D. Menghapus konfigurasi CSS variables.
    *Jawaban yang benar*: **B**. Threshold yang terlalu longgar meniadakan esensi dari Visual Regression Testing itu sendiri.

#### Skenario Kasus Produksi (3 Pertanyaan)

11. **Skenario 1**: 
    Pipeline Visual Regression Anda lolos 100% pada mesin developer lokal berbasis macOS (Apple Silicon M-Series), namun secara konsisten gagal sebanyak 45% saat dijalankan di GitHub Actions Runner (Ubuntu Linux x86_64). File diff menunjukkan sedikit pergeseran garis tepi teks (*kerning/antialiasing*) sebesar 0.5px di seluruh komponen tipografi. 
    **Keputusan rekayasa paling tepat adalah:**
    - A. Menaikkan threshold diff menjadi 20% secara global untuk semua tes.
    - B. Menginstruksikan seluruh developer untuk tidak menjalankan test di lokal.
    - C. Mengisolasi lingkungan pengujian lokal dan CI di dalam Docker Image Linux identik dengan font system binary seragam, atau mendelegasikan capture visual snapshot sepenuhnya ke containerized CI target.
    - D. Mengganti semua font berbasis web menjadi gambar statis Bitmap.
    *Jawaban yang benar*: **C**. Antialiasing font diatur oleh sistem operasi dan library FreeType/Skia di level OS host. Mengisolasi proses rendering di dalam Docker container seragam menghilangkan fragmentasi antialiasing OS.

12. **Skenario 2**: 
    Sebuah modal konfirmasi kritis digunakan di aplikasi pembayaran. Komponen ini memiliki tombol "Hapus Akun" dengan `color: #ff3333` dan latar belakang dialog `#ffffff`. Unit test logic berhasil, tetapi pipeline axe-core otomatis melempar kegagalan `color-contrast (WCAG AA)`. Desainer bersikeras warna merah tersebut sesuai identitas brand.
    **Tindakan arsitektural quality engineering Anda:**
    - A. Menghapus audit axe-core dari pipeline modal dialog.
    - B. Mengubah mode audit menjadi warning tanpa memblokir merge.
    - C. Menolak merge, memperlihatkan kalkulasi matematis luminansi bahwa `#ff3333` pada `#ffffff` memiliki rasio 3.96:1 (kurang dari standar minimum 4.5:1 untuk normal text), dan mengorkestrasi update token warna accessible yang disetujui tim desain (misal `#d91414` dengan rasio 5.3:1).
    - D. Menambahkan border hitam 10px pada teks.
    *Jawaban yang benar*: **C**. Standar WCAG AA mewajibkan rasio kontras 4.5:1 untuk teks berukuran reguler. Tim Design System wajib mempertahankan standar aksesibilitas inklusif legal dan tidak mengorbankannya demi preferensi subjektif yang tidak patuh spesifikasi.

13. **Skenario 3**: 
    Tim Anda mengimplementasikan Storybook CSF 3 Play Function untuk menguji form interaktif. Ketika dijalankan di browser lokal via Storybook UI, test berhasil. Namun saat Storybook Test Runner (berbasis headless Playwright) mengeksekusinya di CI, test tersebut timeout pada pemanggilan `await userEvent.type(input, 'Data')`.
    **Penyebab root cause dan resolusi paling tepat:**
    - A. CI Server tidak terkoneksi ke jaringan internet.
    - B. Komponen input memiliki autofocus atau animasi fade-in yang belum selesai, sehingga elemen target belum berstatus actionable saat Playwright berupaya mengirim keyboard events. Solusinya adalah memanggil assertion visibility eksplisit `await expect(input).toBeVisible()` sebelum berinteraksi.
    - C. UserEvent tidak mendukung pengetikan karakter string alfabet.
    - D. Versi Node.js di CI terlalu baru.
    *Jawaban yang benar*: **B**. *Actionability check* browser headless menuntut elemen telah stabil di layout tree (visible, non-moving, un-obscured) sebelum interaksi disalurkan.

---

### 16. Summary

1.  **Level Testing Mendalam**: Validasi kualitas modern pada design system tidak cukup mengandalkan abstraksi DOM palsu (JSDOM). Layout, CSS Cascade, Inheritance, Stacking Context, dan Web Typography hanya dapat diverifikasi secara sahih melalui browser engine asli (*real headless browser*).
2.  **Triad Quality Design System**: Arsitektur pengujian yang matang bertumpu pada tiga pilar simultan:
    *   **Behavioral & Interaction (CSF 3 Play Functions)**: Memvalidasi state machines & WAI-ARIA interaction patterns.
    *   **Automated Accessibility (axe-core engine)**: Memastikan pemenuhan hukum dan etika inklusivitas WCAG 2.1/2.2 AA.
    *   **Visual Regression Testing (Deterministic VRT)**: Membentengi visual pixel integrity lintas brand, platform, dan varian tema.
3.  **Determinisme Rendering**: Musuh utama VRT adalah *flakiness*. Determinisme mutlak hanya tercapai bila browser environments distandarisasi secara ketat: containerized OS, zero CSS animations, static mock clocks, explicit HiDPI scalefactor, dan font layout stabilization via `document.fonts.ready`.
4.  **Continuous Governance**: Mengotomatisasi pengetesan ke dalam CI pipeline dengan teknik *dependency-aware sharding* memotong durasi deployment secara radikal tanpa mengorbankan kepatuhan kualitas enterprise.