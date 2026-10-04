# Bab 07 Module 01: Testing Strategies & Quality Engineering dalam Design System

---

## SEKSI 01 — IDENTITAS MODUL
* **Track:** 03-Frontend-and-Mobile
* **Kurikulum:** Design System Architecture
* **Topik:** Testing Strategies & Quality Engineering
* **Level:** Advanced / Staff Engineer
* **Prasyarat:** TypeScript Strict Mode, React Internals, DOM Event Loop, Accessibility Tree (AXTree), Continuous Integration Pipelines.
* **Target Ekosistem:** Monorepo UI Library (React 19, Storybook 8, Playwright, Vitest, axe-core).

---

## SEKSI 02 — LEARNING OBJECTIVES
1. **Merancang Piramida Pengujian Multi-Layer:** Membangun matriks validasi terintegrasi mencakup *Unit Contract Testing*, *Visual Regression Testing (VRT)*, *Automated & Headless Accessibility Testing (a11y)*, serta *Interaction/Integration Testing*.
2. **Mengeliminasi Non-Determinism (Flakiness):** Menganalisis dan meniadakan penyebab *flaky tests* pada visual regression akibat font rendering, sub-pixel antialiasing, CSS layout shift, dan asynchronous state transitions.
3. **Menerapkan Contract-Driven Quality Gates:** Mengintegrasikan tooling pengujian ke dalam pipeline CI/CD dengan threshold berbasis zero-breaking-change untuk desain token, komponen polimorfik, dan aksesibilitas WCAG 2.2 Level AA.
4. **Mengotomatisasi Audit Aksesibilitas Terprogram:** Menjalankan audit AXTree dinamis menggunakan engine `axe-core` pada headless browser untuk mendeteksi pelanggaran APG (ARIA Authoring Practices Guide).

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam rekayasa aplikasi produk (*product engineering*), pengujian difokuskan pada *user journeys* dan transaksi bisnis (misal: "apakah checkout berhasil?"). Sebaliknya, dalam **Design System Engineering**, mental model pengujian bergeser dari alur bisnis ke **pengujian invarian kontrak teknis** (*contract invariance testing*).

```
+-------------------------------------------------------------------+
|               PRODUCT APPLICATION TESTING MENTAL MODEL            |
|       "Apakah pengguna dapat menyelesaikan alur checkout?"        |
|  [State A] ---> [Action: Click Buy] ---> [State B: API Success]   |
+-------------------------------------------------------------------+
                                  VS
+-------------------------------------------------------------------+
|                 DESIGN SYSTEM TESTING MENTAL MODEL                |
|       "Apakah antarmuka ini memenuhi semua invarian primitif?"    |
|  1. Kontrak Tipe:   Apakah props inferensi bekerja eksak?         |
|  2. Kontrak Akses:  Apakah AXTree mengumumkan state aria-expanded?|
|  3. Kontrak Visual: Apakah bounding box bergeser 0.5px?           |
|  4. Kontrak Runtime:Apakah komponen mount tanpa memory leak?      |
+-------------------------------------------------------------------+
```

Sebuah komponen design system adalah sebuah SDK antarmuka grafis. Kerusakan pada satu komponen primitif (misalnya `Button`) akan teramplifikasi secara eksponensial ke ratusan aplikasi hilir (*downstream apps*). Oleh karena itu:
* **UI Komponen adalah State Machine:** Setiap kombinasi prop, state internal, dan pseudo-class CSS (`:hover`, `:focus-visible`, `:disabled`) adalah deterministik.
* **Tampilan adalah Kode:** Regresi visual bernilai sama fatalnya dengan runtime exception, karena pergeseran tata letak dapat memutus *fitts' law* atau merusak hierarki visual brand enterprise.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Pipeline pengujian design system beroperasi secara bertingkat (*fail-fast pipeline*). Validasi termurah secara komputasi dieksekusi terlebih dahulu, menyaring galat sebelum memasuki runner visual berbasis browser engine nyata.

```
[ Git Push / PR Triggered ]
             │
             ▼
┌─────────────────────────┐
│ Phase 1: Static Gates   │  --> TypeScript Compiler (tsc --noEmit)
│ (Cost: Rendah, ~5s)     │  --> ESLint AST Rules (react-hooks, a11y)
└────────────┬────────────┘
             │ PASS
             ▼
┌─────────────────────────┐
│ Phase 2: Unit Contract  │  --> Vitest + HappyDOM / JSDOM
│ (Cost: Rendah, ~15s)    │  --> State transitions, render tree parsing
└────────────┬────────────┘
             │ PASS
             ▼
┌─────────────────────────┐
│ Phase 3: Component A11y │  --> axe-core integration
│ (Cost: Sedang, ~30s)    │  --> ARIA spec compliance, contrast validation
└────────────┬────────────┘
             │ PASS
             ▼
┌─────────────────────────┐
│ Phase 4: Visual Regression│ --> Playwright Execution Engine
│ (Cost: Tinggi, ~3m)     │  --> Headless Chromium / WebKit / Firefox
└────────────┬────────────┘  --> Dockerized Pixel-by-Pixel Diff
             │ PASS
             ▼
┌─────────────────────────┐
│ Artifacts & Package     │  --> Bundle Analysis & Types Generation
│ Verification            │  --> PR Gate Approval Signal
└─────────────────────────┘
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Visual Regression Diff Engine (Pixelmatch / SSIM)
Proses VRT modern tidak sekadar membandingkan array byte PNG, melainkan menggunakan algoritma perceptual hashing atau structural similarity:
* **Pixelmatch:** Membandingkan array buffer `[R, G, B, A]` piksel demi piksel. Nilai delta warna dihitung via rumus jarak Euclidean dalam ruang warna YIQ:
  $$\Delta Y = 0.29889R + 0.58662G + 0.11449B$$
* **Antialiasing Detection:** Engine memeriksa 8 piksel tetangga di sekitar piksel target untuk membedakan pergeseran sub-piksel antialiasing rasterizer GPU dari perubahan layout aktual, mencegah *false positive*.

### 2. Accessibility Tree Construction
Runner a11y mengkompilasi DOM internal ke representasi AXTree browser:
* Browser memetakan elemen HTML native (misal `<button>`) atau elemen dengan atribut WAI-ARIA (`role="button"`) ke platform-specific accessible objects (misal NSAccessibility di macOS, IAccessible2 di Windows).
* Engine `axe-core` mengevaluasi aturan komputasi:
  * Memeriksa kalkulasi kontras luminansi relatif ($L_1 / L_2$).
  * Memvalidasi relasi ID reference (`aria-labelledby`, `aria-describedby`).
  * Memverifikasi pemenuhan status *keyboard focusable* via tab order (`tabIndex`).

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Flakiness Determinism pada Headless Browsers
Penyebab utama kegagalan VRT pada CI enterprise adalah inkonsistensi rendering lintas environment (Local macOS vs. Linux Docker CI). Faktor-faktor penentunya meliputi:
1. **Font Font-Rasterization Engine:** Linux menggunakan FreeType, macOS menggunakan Core Text. Kurva Bézier glyph dirender berbeda pada level sub-piksel. Solusi: Gunakan Docker container dengan pinning dependensi `fontconfig` dan webfont internal (format WOFF2 statis), matikan fallback system font.
2. **GPU Acceleration vs Software Rasterizer:** CI server sering kali tidak memiliki kartu grafis dedicated, memaksa rendering via CPU (Mesa/SwiftShader). Parameter browser Playwright wajib mengisolasi flag grafis:
   ```bash
   --disable-gpu --disable-software-rasterizer --font-render-hinting=none
   ```
3. **Animations & Kinetic Scrolling:** CSS transition, scrollbar rendering, dan blinking cursor mengacaukan hash snapshot. Engine VRT wajib membekukan CSS animations melalui media query emulasi (`prefers-reduced-motion: reduce`) atau menginjeksi stylesheet penonaktif animasi secara global sebelum capture screenshot.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi pengujian tingkat enterprise untuk komponen `Dialog` polimorfik, mencakup **Unit Testing**, **Automated Accessibility Testing**, dan **Visual Snapshot Testing**.

### Struktur File
```
src/components/Dialog/
├── Dialog.tsx
├── Dialog.test.tsx
└── Dialog.visual.spec.ts
```

### Implementasi Unit & A11y Test (`Dialog.test.tsx`)

```typescript
import { render, screen, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe, toHaveNoViolations } from 'jest-axe';
import { describe, it, expect, afterEach } from 'vitest';
import * as React from 'react';

// Ekstensi matcher Vitest
expect.extend(toHaveNoViolations);

// SUT (System Under Test): Dialog Component Sederhana
interface DialogProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}

export const Dialog: React.FC<DialogProps> = ({ isOpen, onClose, title, children }) => {
  if (!isOpen) return null;
  const titleId = React.useId();

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
    >
      <div className="bg-white p-6 rounded-lg shadow-xl max-w-md w-full">
        <h2 id={titleId} className="text-xl font-bold mb-4">{title}</h2>
        <div className="mb-4">{children}</div>
        <button
          onClick={onClose}
          aria-label="Tutup dialog"
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          Tutup
        </button>
      </div>
    </div>
  );
};

describe('Dialog Component Unit & Accessibility Tests', () => {
  afterEach(() => {
    cleanup();
  });

  it('harus merender dialog dengan peran aksesibilitas dan atribut yang benar', () => {
    const handleClose = vi.fn();
    render(
      <Dialog isOpen={true} onClose={handleClose} title="Konfirmasi Penghapusan">
        <p>Apakah Anda yakin ingin melanjutkan?</p>
      </Dialog>
    );

    const dialogElement = screen.getByRole('dialog');
    expect(dialogElement).toBeInTheDocument();
    expect(dialogElement).toHaveAttribute('aria-modal', 'true');
    expect(dialogElement).toHaveAccessibleName('Konfirmasi Penghapusan');
  });

  it('tidak boleh memiliki pelanggaran aksesibilitas terdeteksi via axe-core', async () => {
    const { container } = render(
      <main>
        <Dialog isOpen={true} onClose={() => {}} title="Aksesibilitas Sempurna">
          <p>Konten modal ramah pembaca layar.</p>
        </Dialog>
      </main>
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('harus memicu callback onClose ketika tombol aksi ditutup diklik', async () => {
    const user = userEvent.setup();
    const handleClose = vi.fn();

    render(
      <Dialog isOpen={true} onClose={handleClose} title="Modal Aksi">
        <p>Klik tombol untuk menutup modal.</p>
      </Dialog>
    );

    const closeButton = screen.getByRole('button', { name: /tutup dialog/i });
    await user.click(closeButton);

    expect(handleClose).toHaveBeenCalledTimes(1);
  });
});
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis File `Dialog.test.tsx`
* **Baris 3:** `import { axe, toHaveNoViolations } from 'jest-axe';`
  Mengimpor engine auditing `axe-core` yang telah dibungkus untuk assertions Jest/Vitest.
* **Baris 7:** `expect.extend(toHaveNoViolations);`
  Mendaftarkan custom assertion matcher ke Vitest runner agar dapat memproses objek laporan pelanggaran AXTree secara native.
* **Baris 19:** `const titleId = React.useId();`
  Mencegah tabrakan identifier DOM ketika modal dirender berkali-kali secara konkuren.
* **Baris 24-25:** `role="dialog" aria-modal="true" aria-labelledby={titleId}`
  Fondasi WAI-ARIA untuk modal: memberi sinyal pada teknologi asistif untuk mengisolasi mode navigasi dan mengambil nama modal langsung dari elemen header terkait via ID.
* **Baris 54-63:** Test Suite `axe-core`
  `const results = await axe(container);` melakukan evaluasi DOM saat ini terhadap rule-set WCAG AA/AAA. Jika rasio kontras teks kurang dari 4.5:1 atau referensi aria label hilang, assertions akan melempar detailed error logs.
* **Baris 67:** `const user = userEvent.setup();`
  Menggunakan `userEvent` alih-alih `fireEvent`. `userEvent` menyimulasikan event loop lengkap browser (pointerdown, mousedown, focus, pointerup, mouseup, click) secara realistis.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Enterprise: The "Invisible" Color Contrast & Layout Regression
* **Perusahaan:** Multi-tenant Fintech Platform.
* **Insiden:** Tim Design Token mengubah formula opacity warna netral `surface-muted` dari hex statis `#f3f4f6` ke token dinamis `hsl(var(--palette-gray-200) / <alpha-value>)`. 
* **Dampak:** Komponen `Button` varian `secondary` secara visual terlihat normal di monitor IPS developer, namun di monitor kontras rendah dan pada kalkulasi WAI-ARIA, rasio kontras teks terhadap background anjlok menjadi `2.8:1` (Gagal WCAG AA standar 4.5:1). Secara bersamaan, CSS sub-pixel rendering menyebabkan ikon di dalam button melompat 1 piksel ke bawah pada engine browser WebKit (Safari).
* **Solusi Arsitektural:** Membangun CI Quality Gate terotomatisasi yang memblokir PR sebelum fase staging:
  1. Automated headless visual regression via Playwright lintas Chromium dan WebKit dengan ambang batas *anti-aliasing threshold* terukur.
  2. Snapshot token komputasi yang membandingkan computed CSS styles secara absolut.
  3. Continuous Accessibility Testing via `@axe-core/playwright`.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah setup spesifikasi pengujian visual dan aksesibilitas end-to-end multi-browser menggunakan Playwright untuk komponen design system.

### Konfigurasi Framework Playwright (`playwright.config.ts`)

```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: [['html'], ['json', { outputFile: 'test-results.json' }]],
  use: {
    baseURL: 'http://localhost:6006', // URL Storybook Instance
    trace: 'on-first-retry',
    viewport: { width: 1280, height: 720 },
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        launchOptions: {
          args: ['--font-render-hinting=none', '--disable-skia-runtime-opts'],
        },
      },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
  ],
});
```

### Spec Pengujian VRT & Accessibility (`e2e/button.visual.spec.ts`)

```typescript
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.describe('Component: Button Visual Regression & A11y Contract', () => {
  const storyUrl = '/iframe.html?id=primitives-button--all-variants&viewMode=story';

  test.beforeEach(async ({ page }) => {
    // 1. Navigasi ke representasi komponen isolasi di Storybook
    await page.goto(storyUrl, { waitUntil: 'networkidle' });

    // 2. Bekukan rendering: Reduksi transisi dan hentikan kedipan caret kursor
    await page.addStyleTag({
      content: `
        *, *::before, *::after {
          animation-duration: 0s !important;
          animation-delay: 0s !important;
          transition-duration: 0s !important;
          transition-delay: 0s !important;
          caret-color: transparent !important;
        }
      `,
    });

    // 3. Pastikan font web selesai terunduh dan terpasang pada canvas DOM
    await page.evaluate(async () => {
      await document.fonts.ready;
    });
  });

  test('harus lolos audit aksesibilitas otomatis tanpa anomali', async ({ page }) => {
    const accessibilityScanResults = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag22aa'])
      .analyze();

    expect(accessibilityScanResults.violations).toEqual([]);
  });

  test('harus memvalidasi pixel perfection pada default state', async ({ page }) => {
    const componentWrapper = page.locator('#storybook-root');

    // Screenshot assertions dengan micro-tolerance threshold
    await expect(componentWrapper).toHaveScreenshot('button-variants-default.png', {
      maxDiffPixelRatio: 0.002, // 0.2% max pixel error tolerance
      threshold: 0.1,           // Perceptual color threshold (YIQ delta)
      animations: 'disabled',
    });
  });

  test('harus memvalidasi state fokus visual (:focus-visible)', async ({ page }) => {
    const primaryButton = page.locator('button', { hasText: 'Primary Action' }).first();
    
    // Picu keyboard navigation focus ring
    await primaryButton.focus();

    await expect(primaryButton).toHaveScreenshot('button-primary-focus-state.png', {
      maxDiffPixels: 50,
      threshold: 0.1,
    });
  });
});
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter Arsitektur | Snapshot Testing DOM (JSDOM) | Component Screenshot (Playwright) | E2E Scenario Testing (Cypress) |
| :--- | :--- | :--- | :--- |
| **Execution Speed** | Ultra Cepat (~5-10ms per test) | Sedang (~500ms - 2s per story) | Lambat (~5s - 15s per flow) |
| **Infrastruktur / Biaya**| Rendah (Hanya Node.js process) | Sedang-Tinggi (Docker Container / GPU) | Tinggi (Dedicated Browser Grid) |
| **Kekuatan Deteksi** | Hanya regresi teks/markup HTML | Perubahan layout, CSS, rendering font | User path, integrasi micro-frontend |
| **Tingkat Flakiness** | Nol (Deterministik murni) | Rentan jika rasterizer berubah | Tinggi akibat latency jaringan |
| **Akurasi CSS Engine** | Tidak ada (JSDOM tidak parse layout) | 100% Native (Blink, WebKit, Gecko) | 100% Native |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Pseudo-element Rendering (`::before` / `::after`)
Banyak komponen icon-button mengandalkan pseudo-element CSS. JSDOM tidak membangun CSS box tree untuk pseudo-elements. Pengujian berbasis Unit/RTL tidak akan pernah mendeteksi jika layout pseudo-element rusak.
* *Mitigasi:* Wajibkan pengujian CSS layout menggunakan browser engine nyata via Playwright Component Testing.

### 2. Viewport-Dependent Elements (Layout Shifting di Responsive Breakpoints)
Komponen yang menggunakan responsive media queries sering kali gagal dirender secara deterministik jika resolusi browser uji default bergeser 1px.
* *Mitigasi:* Jalankan matrix project Playwright dengan dimensi viewport tetap secara hardcoded (`1280x720`, `390x844` untuk mobile), hindari dynamic auto-resizing.

### 3. Font Engine Anti-Aliasing Mismatch
Rendering teks pada CI OS (Debian/Ubuntu) menghasilkan ketebalan garis font yang berbeda tipis dibandingkan macOS/Windows lokal.
* *Mitigasi:* Selalu jalankan update snapshot Playwright via Docker container terstandarisasi:
  ```bash
  docker run --rm --network host -v $(pwd):/work/ -w /work/ mcr.microsoft.com/playwright:v1.44.0-jammy npx playwright test --update-snapshots
  ```

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Snapshotting Seluruh Raw DOM HTML
* **Kesalahan:** Melakukan `expect(container).toMatchSnapshot()` pada Jest/Vitest. Setiap perubahan refaktor internal komponen (misalnya merapikan class atau mengubah identifier div internal) merusak ribuan snapshot lama tanpa menandakan bug visual yang nyata.
* **Perbaikan:** Gunakan testing berbasis perilaku interaksi (`screen.getByRole`) dan delegasikan validasi visual ke Playwright visual screenshot testing.

### 2. Menguji "Implementation Details" Alih-alih "Accessibility Tree"
* **Kesalahan:** Menggunakan query CSS selector yang rapuh: `document.querySelector('.btn-primary > span')`.
* **Perbaikan:** Gunakan accessibility locator: `page.getByRole('button', { name: 'Submit' })`. Hal ini memastikan jika komponen tidak terbaca oleh screen reader, tes akan otomatis gagal.

### 3. Mengabaikan Dynamic Timeouts & Asynchronous Layout
* **Kesalahan:** Menggunakan `page.waitForTimeout(1000)` untuk menunggu animasi selesai sebelum capture screenshot. Pendekatan ini membuat eksekusi lambat dan tetap memicu *race condition*.
* **Perbaikan:** Gunakan assertion auto-retrying atau nonaktifkan CSS transitions secara global pada level DOM fixture.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

* **Storybook as Testing Canonical Fixtures:** Jangan menulis ulang markup uji coba di file test. Buat Storybook Stories terlebih dahulu, lalu jadikan *stories* tersebut sebagai unit masukan bagi pengujian Vitest dan Playwright.
* **Zero Threshold untuk Color Palette:** Jangan gunakan toleransi deviasi (`maxDiffPixelRatio: 0`) pada pengujian visual token warna. Satu tingkat deviasi warna menandakan perubahan identitas brand atau penurunan level aksesibilitas.
* **Hermetic Component Isolation:** Pastikan Storybook/Component runner membersihkan (unmount) state global, local storage, dan mock network request sebelum instansiasi komponen baru dieksekusi.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI

Pada monorepo enterprise dengan ratusan komponen, eksekusi VRT memakan komputasi besar. Berikut teknik optimasinya:

```
[ Monorepo PR Event ]
          │
          ▼
┌────────────────────────────────────────┐
│ Turborepo / Nx Affected Discovery     │ 
│ (Identifikasi komponen yang termodifikasi)
└──────────────────┬─────────────────────┘
                   │
         [ Hanya run affected stories ]
                   │
                   ▼
┌────────────────────────────────────────┐
│ Playwright Sharding Strategy           │
│ Worker 1 (Shard 1/4)  Worker 2 (2/4)   │
│ Worker 3 (Shard 3/4)  Worker 4 (4/4)   │
└──────────────────┬─────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────┐
│ Shared S3 Blob Storage for Base Images │
│ (Download referensi snapshot on demand)│
└────────────────────────────────────────┘
```

1. **Test Sharding:** Bagi pengujian secara paralel di CI menggunakan flag sharding bawaan Playwright:
   ```bash
   npx playwright test --shard=${{ matrix.shardIndex }}/${{ matrix.shardTotal }}
   ```
2. **Affected-Only Testing:** Gunakan tooling monorepo seperti Nx atau Turborepo untuk menjalankan pengujian VRT hanya pada paket atau komponen yang memiliki git diff terhadap branch `main`.

---

## SEKSI 16 — KEAMANAN & HARDENING

* **CSS Injection Vulnerability:** Pastikan komponen design system yang mengonsumsi props style kustom (`style={{ ... }}` atau string CSS dinamis) memvalidasi input terhadap serangan CSS Injection yang dapat mengekstrak data sensitif melalui manipulasi selector attribute:
  ```typescript
  // Buruk: Mengizinkan injeksi style tanpa validasi
  <Box style={{ background: userProvidedColor }} />
  
  // Baik: Validasi via token sanitizer
  const safeColor = designTokens.colors[userProvidedColor] ?? 'transparent';
  ```
* **Dependency Auditing axe-core:** Lakukan pinning engine versi rule accessibility. Aturan baru WCAG yang masuk ke minor version dependency dapat menggagalkan pipeline deployment kritis secara mendadak. Gunakan lockfile deterministik (`pnpm-lock.yaml`).

---

## SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

Ketika terjadi kegagalan pada pengujian Playwright di environment headless CI, gunakan teknik tracing berikut:

1. **Playwright Trace Viewer:** Simpan artefak trace yang merekam network call, console log, dan snapshot DOM pada tiap microsecond aksi:
   ```bash
   npx playwright show-trace ./test-results/trace.zip
   ```
2. **Visual Diff Highlighting:** Pipeline wajib menghasilkan gambar komposit 3-panel secara otomatis:
   * **Actual Image** (Kiri)
   * **Pixel Difference** (Tengah - ditandai dengan warna magenta neon untuk piksel yang tidak cocok)
   * **Baseline Expected** (Kanan)

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

```
┌────────────────────────────────────────────────────────────────────────────┐
│                    DESIGN SYSTEM TESTING CHEAT SHEET                       │
├──────────────────────┬─────────────────────────┬───────────────────────────┤
│ JENIS PENGUJIAN      │ RUNNER UTAMA            │ TARGET VERIFIKASI         │
├──────────────────────┼─────────────────────────┼───────────────────────────┤
│ Static Analysis      │ tsc / ESLint            │ Tipe props, linting aturan│
│ Unit Testing         │ Vitest + RTL            │ State reducers, event emit│
│ Accessibility (a11y) │ Vitest + jest-axe       │ Role, ARIA states, names  │
│ Visual Regression    │ Playwright + Chromium   │ Snapshot piksel, tokens   │
│ Cross-Engine VRT     │ Playwright + WebKit     │ Layout bug, font-rendering│
└──────────────────────┴─────────────────────────┴───────────────────────────┘
```

* **Command Cepat Update Baseline Playwright (via Docker):**
  `docker run --rm -v $(pwd):/work/ -w /work/ mcr.microsoft.com/playwright:v1.44.0-jammy npx playwright test --update-snapshots`
* **Rule Mandatory A11y:** Jangan pernah menyematkan atribut `aria-hidden="true"` pada elemen yang memiliki turunan interaktif/fokusabel.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal 1: Pilihan Ganda
Mengapa pengujian visual regression (VRT) yang dijalankan pada sistem operasi macOS developer sering kali menghasilkan failure diff ketika divalidasi pada pipeline Linux (Ubuntu) CI, meskipun markup dan file CSS identik?
* A) Karena Linux mengabaikan flexbox box-sizing context.
* B) Karena perbedaan internal font rasterization engine antara macOS (Core Text) dan Linux (FreeType) pada sub-pixel level.
* C) Karena Node.js di Linux tidak mendukung format gambar PNG kompresi tinggi.
* D) Karena Playwright tidak dapat menjalankan headless browser di dalam container Linux.

### Soal 2: Pilihan Ganda
Pada saat menjalankan automated accessibility test via `axe-core`, komponen Anda dilaporkan gagal memenuhi kriteria WCAG SC 4.1.2. Apa penyebab paling mungkin dari pelanggaran ini?
* A) Tombol penutup modal tidak memiliki teks internal atau atribut `aria-label` / `aria-labelledby`.
* B) Komponen menggunakan CSS padding yang terlalu besar untuk standar mobile.
* C) Komponen tidak menggunakan Tailwind CSS class.
* D) Animasi CSS modal berjalan lebih lambat dari 300ms.

### Soal 3: Pilihan Ganda
Apa kelemahan utama dari strategi "DOM Snapshot Testing" (`expect(tree).toMatchSnapshot()`) dalam pengujian library komponen UI?
* A) Memerlukan server GPU yang mahal untuk dijalankan.
* B) Tidak kompatibel dengan bahasa TypeScript.
* C) Sangat rapuh (*brittle*); perubahan markup yang tidak berpengaruh pada visual/fungsi tetap memicu kegagalan uji, mendorong developer melakukan update snapshot membabi buta tanpa inspeksi (*blind updating*).
* D) Snapshot DOM tidak dapat disimpan di dalam version control Git.

### Soal 4: Analisis Kasus Singkat
Sebuah komponen Button memiliki prop `disabled={true}`. Pengujian Unit Anda memvalidasi bahwa event `onClick` tidak dipanggil ketika tombol diklik. Namun, tim aksesibilitas melaporkan pengguna screen reader terjebak dan tidak memahami bahwa tombol tersebut ada. Mengapa situasi ini terjadi jika Anda menggunakan `<div onClick={handleClick} disabled />` alih-alih elemen native `<button>`?

### Soal 5: Pilihan Ganda
Metrik perbandingan visual apa yang paling optimal untuk mengabaikan artefak kompresi gambar mikro namun tetap mampu menangkap perubahan saturasi warna brand token?
* A) Menggunakan komparasi String Base64 secara absolut.
* B) Algoritma Euclidean Distance YIQ / SSIM dengan threshold ambang toleransi terkontrol (misal `threshold: 0.1`).
* C) Melakukan hash SHA-256 langsung pada raw file image buffer.
* D) Menghitung total ukuran bytes dari gambar hasil capture.

---

### Kunci Jawaban & Pembahasan

1. **Jawaban: B.** Engine rendering font berbeda secara native pada tiap kernel OS. Linux mengandalkan engine FreeType yang menghasilkan anti-aliasing berbeda dengan Core Text bawaan macOS.
2. **Jawaban: A.** WCAG 4.1.2 (Name, Role, Value) menuntut setiap elemen interaktif memiliki nama yang dapat diakses (*accessible name*). Jika button hanya berisi SVG ikon tanpa teks pendukung atau `aria-label`, AXTree tidak dapat mengabstraksikannya ke assistive tech.
3. **Jawaban: C.** Snapshot markup mentah mendeteksi perubahan sintaksis yang tidak esensial, bukan perilaku visual atau fungsionalitas komponen, sehingga sering menciptakan *alert fatigue* pada engineer.
4. **Pembahasan Analisis Kasus:** Tag non-interaktif seperti `<div>` tidak memiliki semantik aksesibilitas native. Atribut `disabled` pada `div` bukan atribut HTML valid. Elemen tersebut tidak akan dimasukkan ke dalam keyboard navigation tree (`tabIndex`), tidak mengumumkan status *disabled* ke screen reader, dan tidak memicu APG button contracts. Solusinya adalah menggunakan tag `<button disabled>` native atau menambahkan `role="button"`, `tabIndex={-1}`, dan `aria-disabled="true"`.
5. **Jawaban: B.** SSIM / Perceptual YIQ Color Delta membandingkan kemiripan visual yang memperhitungkan persepsi mata manusia, mengabaikan artefak kompresi mikroskopis tanpa meloloskan pergeseran warna token atau layout.

---

## SEKSI 20 — TANTANGAN MANDIRI & PROYEK PRAKTIKUM

### Deskripsi Proyek: Automated QA Gatekeeper untuk "Accordion Primitive"
Anda ditugaskan membangun sistem pengujian lengkap dari nol untuk komponen primitif `Accordion` (Compound Component yang mencakup `Accordion.Root`, `Accordion.Item`, `Accordion.Trigger`, `Accordion.Content`).

### Spesifikasi Kebutuhan Teknis
1. **Unit Contract Tests (Vitest & RTL):**
   * Validasi mekanisme keyboard navigation WAI-ARIA APG:
     * Menekan tombol `ArrowDown` memindahkan fokus ke Trigger berikutnya.
     * Menekan tombol `ArrowUp` memindahkan fokus ke Trigger sebelumnya.
     * Menekan tombol `Home` memindahkan fokus ke Trigger pertama.
     * Menekan tombol `End` memindahkan fokus ke Trigger terakhir.
2. **A11y Tests (axe-core):**
   * Pastikan `aria-expanded` berubah secara dinamis (`true` / `false`) saat di-trigger.
   * Pastikan `aria-controls` pada trigger cocok secara eksak dengan `id` dari elemen content panel.
3. **Playwright Visual Tests:**
   * Ambil snapshot state default (seluruh panel tertutup).
   * Ambil snapshot state terbuka (panel pertama aktif).
   * Ambil snapshot state focus ring pada trigger panel kedua.
   * Pastikan uji VRT dijalankan dengan menonaktifkan seluruh animasi CSS accordion collapse/expand agar deterministik.
4. **Deliverables:**
   * Script CI execution command yang membungkus seluruh rangkaian tes dalam satu target single-pass pipeline command: `pnpm test:quality-gate`. Pipeline harus mengembalikan exit code 1 jika ada satu pelanggaran WCAG AA atau visual threshold > 0.1%.