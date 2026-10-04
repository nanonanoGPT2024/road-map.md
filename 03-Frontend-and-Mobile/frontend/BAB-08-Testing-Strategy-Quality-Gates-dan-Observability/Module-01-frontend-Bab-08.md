# BAB 08 / MODUL 01: Testing Strategy, Quality Gates & Observability

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** Frontend & Mobile Engineering
*   **Kategori:** 03-Frontend-and-Mobile
*   **Kode Modul:** FE-08-01
*   **Tingkat Kesulitan:** Advanced / Staff Engineer
*   **Prasyarat Konseptual:** 
    *   Pemahaman mendalam mengenai siklus hidup komponen frontend (React/Virtual DOM atau Web Components).
    *   Pengalaman mengelola *State Management* terdistribusi (Redux, Zustand, atau Context).
    *   Penguasaan dasar tooling build system (Vite, Webpack, Rollup) dan eksekusi Node.js.
    *   Pemahaman protokol HTTP/REST/GraphQL dan model asinkronus browser (Event Loop, Microtasks).
*   **Alokasi Waktu Belajar:** 14 Jam (Teori, Bedah Kode Produksi, Implementasi Pipeline, dan Pengujian Telemetri).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1.  **Merancang Piramida Pengujian Frontend Modern:** Mengalokasikan proporsi uji yang optimal antara Unit, Component Integration, Contract, End-to-End (E2E), dan Visual Regression guna menyeimbangkan execution speed, cost, dan confidence score.
2.  **Mengimplementasikan Contract & Integration Testing Mutakhir:** Menerapkan pengujian integrasi berorientasi interaksi pengguna menggunakan React Testing Library dan Mock Service Worker (MSW) tanpa membocorkan detail implementasi internal (*implementation-agnostic testing*).
3.  **Membangun Quality Gates Deterministik dalam CI/CD:** Mengonfigurasi automated enforcement (Linter, Typecheck, Mutation Testing, Bundle Size Gates, Test Coverage) pada GitHub Actions yang memblokir regresi kode secara presisi.
4.  **Menerapkan Real-User Monitoring (RUM) & Tracing Terdistribusi:** Menginstrumentasi aplikasi klien menggunakan OpenTelemetry Web SDK untuk melacak context propagation W3C `traceparent` dari klik UI hingga service backend, serta mengukur Core Web Vitals (CWV).
5.  **Mendeteksi & Memitigasi Flakiness Secara Matematis:** Menganalisis sumber nondeterminisme dalam uji E2E (Playwright) dan mengeliminasi race condition tanpa menggunakan hardcoded delay (`setTimeout`).

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### 1. Shift-Left Testing vs. Shift-Right Observability
Pengujian tradisional memperlakukan QA sebagai gerbang downstream sesaat sebelum rilis. Paradigma modern Staff Engineer mengintegrasikan pengujian ke arah kiri (*Shift-Left*)—mulai dari type safety, linter, dan isolated unit tests selama developer mengetik—sembari secara bersamaan mendorong verifikasi performa serta ketahanan sistem ke arah kanan (*Shift-Right*) menggunakan RUM, synthetic monitoring, dan telemetry tracing di lingkungan produksi.

### 2. Testing Trophy vs. Testing Pyramid
Piramida pengujian klasik (didominasi Unit Test kecil-kecil) sering kali gagal mendeteksi kerusakan pada arsitektur web modern karena unit-unit logika terisolasi tidak menjamin integrasi antarmuka bekerja harmonis. Model mental yang diadopsi adalah **Testing Trophy**:
*   *Static Analysis* (TypeScript, ESLint) sebagai fondasi tak berbiaya runtime.
*   *Unit Tests* khusus untuk komputasi matematis/algoritmik murni.
*   *Integration Tests* (bobot terbesar) menguji interaksi nyata antara komponen UI, state store, dan mock network network level (MSW).
*   *End-to-End Tests* (Playwright) secara hemat menguji alur kritis bisnis (*Critical User Journeys*).

### 3. Observabilitas Klien Bukan Sekadar "Sentry Error Logging"
Frontend adalah lingkungan yang heterogen: berjalan di hardware yang tidak terkontrol, koneksi jaringan fluktuatif, dan konfigurasi ekstensi browser liar. Observabilitas klien bukanlah menangkap `console.error` pasca-bencana, melainkan kemampuan merekonstruksi *state journey* pengguna secara telemetrik: korelasi antara alokasi memori, metrik Core Web Vitals (LCP, INP, CLS), interaksi DOM, dan network latency via distributed trace IDs.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

```
+----------------------------------------------------------------------------------------------------+
|                                    QUALITY GATES & DEPLOY PIPELINE                                 |
+----------------------------------------------------------------------------------------------------+
       |
       v
+------------------+     Static Checks      +------------------+     Unit & Integration
| Developer Commit | ---------------------> | TypeCheck & Lint | ------------------------+
+------------------+  (ESLint, TS compiler) +------------------+   (Vitest + MSW DOM)    |
                                                                                         v
+---------------------------------------------------------------------------------------------+
| CI Quality Gate Phase 1: Fail Fast                                                          |
|  - Types: 0 Errors       - Bundle Size: < Threshold      - Mutation Score: > 80% (Stryker)  |
+---------------------------------------------------------------------------------------------+
       |
       | Passed
       v
+---------------------------------------------------------------------------------------------+
| CI Quality Gate Phase 2: Hermetic Dynamic Testing                                           |
|  - Playwright E2E Containers (Mocked Identity Provider, Production Build Preview)           |
|  - Visual Regression Testing (Pixelmatch / Lost-Pixel screenshot diffing)                   |
+---------------------------------------------------------------------------------------------+
       |
       | Deployed to Production
       v
+----------------------------------------------------------------------------------------------------+
|                          CLIENT RUNTIME: DISTRIBUTED OBSERVABILITY ARCHITECTURE                    |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [ Browser DOM Window ]                                                                            |
|        |                                                                                           |
|        |-- (User Clicks Button)                                                                    |
|        v                                                                                           |
|  [ OpenTelemetry Tracer ] === (Context Propagation) =============================================+ |
|        |                                                                                         | |
|        |-- Generates Trace ID: 4bf92f3577b34da6a3ce929d0e0e4736                                  | |
|        |-- Injects Header: 'traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'| |
|        v                                                                                         | |
|  [ Fetch / XHR Hook ] -----------------------------------------------> [ Backend Gateway API ]   | |
|        |                                                                     |                   | |
|        |-- Logs RUM Metrics                                                  v                   | |
|        |   - INP (Interaction to Next Paint)                   [ Backend Distributed Spans ]     | |
|        |   - Long Animation Frames (LoAF)                                    |                   | |
|        v                                                                     |                   | |
|  [ OTLP Batch Span Processor ]                                               |                   | |
|        |                                                                     |                   | |
|        +---- Export JSON over HTTP/Protobuf ------------------------+        |                   | |
|                                                                     |        |                   | |
+---------------------------------------------------------------------|--------|---------------------+
                                                                      v        v
                                                       +-------------------------------+
                                                       | APM Telemetry Collector (OTel)|
                                                       | (Jaeger / Grafana / Datadog)  |
                                                       +-------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Mock Service Worker (MSW) Network Virtualization
Berbeda dari pustaka mocking lama (`jest.mock` atau `axios-mock-adapter`) yang memodifikasi prototype modul JavaScript, MSW beroperasi pada level interceptor:
*   **Di Node.js (Unit/Integration Test):** Menggunakan paket `node-request-interceptor` (kini `@mswjs/interceptors`) yang menambal modul global `http`, `https`, `fetch`, dan `XMLHttpRequest` pada level socket native Node.js.
*   **Di Browser (E2E/Storybook):** Mendaftarkan sebuah `Service Worker` via browser API. Worker bertindak sebagai reverse proxy lokal, mencegat pemanggilan `fetch` melalui event listener `fetch`, mencocokkan pola URL, dan mengembalikan HTTP Response tiruan tanpa membiarkan paket data keluar ke adapter jaringan fisik.

### 2. Mutation Testing Engine (Stryker)
Test coverage 100% adalah metrik vanity jika tes tidak memiliki daya asersi kritis. Mutator bekerja dengan tahapan:
1.  **AST Parsing:** Stryker membaca Abstract Syntax Tree dari source code file target via Babel/TypeScript parser.
2.  **Mutant Generation:** Mengubah operator logika (`&&` menjadi `||`), membalik kondisi boolean (`true` menjadi `false`), atau mengosongkan blok fungsi return.
3.  **Test Suite Execution:** Menjalankan test suite untuk setiap mutant dalam sub-proses terisolasi.
4.  **Survival Evaluation:**
    *   *Mutant Killed:* Test suite gagal (ASSERTION FAILED). Ini kondisi valid.
    *   *Mutant Survived:* Test suite tetap lolos (PASSED) meski kode telah disabotase. Ini menandakan celah fatal pada kualitas assertion pengujian.

### 3. OpenTelemetry Web Instrumentations & W3C Trace Context
Tracing terdistribusi frontend memanfaatkan implementasi standar W3C `Trace Context`:
*   Struktur Header `traceparent`: `version-trace_id-parent_id-trace_flags`
    *   `version`: format 2 digit hex (saat ini `00`).
    *   `trace_id`: 32 digit hex yang unik untuk satu transaksi end-to-end global.
    *   `parent_id` (Span ID): 16 digit hex yang merepresentasikan operasi spesifik dari komponen frontend pemanggil.
    *   `trace_flags`: 8-bit field, di mana `01` berarti transaksi ini di-sampling untuk perekaman penuh.
*   Saat request keluar dari browser, instrumentasi OTel mengikat `PerformanceObserver` API (mengamati `resource` timing) dan membungkus `window.fetch` native untuk menjamin `span` diekspor secara asynchronous melalui `navigator.sendBeacon` guna mencegah pemblokiran rendering pipeline browser.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Flakiness Deterministik dan The Microtask Race
Penyebab utama tes flaky pada frontend adalah desinkronisasi antara Event Loop browser dengan runner eksekusi tes:

$$\text{Total Execution Time} = T_{\text{DOM Mutation}} + T_{\text{Microtask Flush}} + T_{\text{Paint}} + T_{\text{GC}}$$

Jika pengujian melakukan assertion sebelum siklus `Microtask Flush` (penyelesaian Promise, re-render React) selesai, pengujian akan mengalami intermittent failure. Cara yang salah untuk mengatasi hal ini adalah dengan menggunakan arbitrary timeout:
```typescript
// ANTI-PATTERN: Menambah delay arbitrer yang memperlambat CI dan tetap flaky
await new Promise(resolve => setTimeout(resolve, 3000));
```
Pendekatan deterministik berakar pada **State-Driven Observability Waiting**: runner tes memantau perubahan kondisi DOM atau state snapshot secara atomik menggunakan polling berbasis `MutationObserver`:

```typescript
// POLA DETERMINISTIK: Mengamati mutasi DOM real-time
await waitFor(() => {
  expect(screen.getByRole('alert')).toHaveTextContent(/transaksi sukses/i);
});
```

### Core Web Vitals (CWV) Telemetry: Interaction to Next Paint (INP)
INP mengukur responsivitas halaman secara holistik sepanjang siklus hidup sesi pengguna. INP menghitung latensi dari interaksi pengguna (klik, ketukan keyboard) hingga browser selesai me-render frame visual berikutnya:

$$\text{Latency} = \text{Input Delay} + \text{Processing Time} + \text{Presentation Delay}$$

1.  **Input Delay:** Waktu tunggu antrean event queue akibat thread utama sibuk mengeksekusi long tasks.
2.  **Processing Time:** Durasi yang dihabiskan untuk menjalankan callback event handler di JavaScript.
3.  **Presentation Delay:** Waktu yang dihabiskan oleh pipeline browser untuk menghitung style layout, compositing, dan menggambar (paint) frame baru.

Frontend observability pipeline harus menangkap `PerformanceLongAnimationFrameTiming` (LoAF) API yang menyediakan detail script attribution terhadap task yang memblokir rendering di atas batas 50ms.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi isolated unit test dengan assertion kuat, mock API terisolasi berbasis MSW, dan custom hook testing tanpa ketergantungan wrapper UI besar.

### 1. Komponen: `useTransferFund.ts` & `PaymentSummary.tsx`

```typescript
// src/features/payments/useTransferFund.ts
import { useState } from 'react';

interface TransferPayload {
  recipientId: string;
  amount: number;
}

interface TransferResult {
  transactionId: string;
  status: 'SUCCESS' | 'FAILED';
}

export function useTransferFund() {
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const transfer = async (payload: TransferPayload): Promise<TransferResult> => {
    if (payload.amount <= 0) {
      throw new Error('Nominal transfer harus lebih besar dari 0');
    }

    setIsProcessing(true);
    setError(null);

    try {
      const response = await fetch('/api/v1/transfers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || 'Gagal memproses transfer');
      }

      const data: TransferResult = await response.json();
      return data;
    } catch (err: unknown) {
      const parsedError = err instanceof Error ? err.message : 'Kesalahan sistem';
      setError(parsedError);
      throw err;
    } finally {
      setIsProcessing(false);
    }
  };

  return { transfer, isProcessing, error };
}
```

### 2. Network Isolation Test via MSW: `useTransferFund.test.ts`

```typescript
// src/features/payments/useTransferFund.test.ts
import { describe, it, expect, beforeAll, afterEach, afterAll } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';
import { useTransferFund } from './useTransferFund';

const server = setupServer(
  http.post('/api/v1/transfers', async ({ request }) => {
    const body = (await request.json()) as { recipientId: string; amount: number };

    if (body.recipientId === 'INVALID_ACCOUNT') {
      return HttpResponse.json(
        { message: 'Rekening tujuan tidak ditemukan' },
        { status: 404 }
      );
    }

    return HttpResponse.json({
      transactionId: 'trx-99882233',
      status: 'SUCCESS',
    });
  })
);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('Integration Test: useTransferFund Hook', () => {
  it('harus berhasil memproses transfer dan membalikkan flag isProcessing', async () => {
    const { result } = renderHook(() => useTransferFund());

    expect(result.current.isProcessing).toBe(false);
    expect(result.current.error).toBeNull();

    let transactionResponse;
    await act(async () => {
      transactionResponse = await result.current.transfer({
        recipientId: 'ACC-001',
        amount: 500000,
      });
    });

    expect(transactionResponse).toEqual({
      transactionId: 'trx-99882233',
      status: 'SUCCESS',
    });
    expect(result.current.isProcessing).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('harus melempar error dan mencatat state saat rekening tidak ditemukan', async () => {
    const { result } = renderHook(() => useTransferFund());

    await act(async () => {
      await expect(
        result.current.transfer({
          recipientId: 'INVALID_ACCOUNT',
          amount: 100000,
        })
      ).rejects.toThrow('Rekening tujuan tidak ditemukan');
    });

    expect(result.current.error).toBe('Rekening tujuan tidak ditemukan');
    expect(result.current.isProcessing).toBe(false);
  });

  it('harus memvalidasi client-side tanpa memanggil network jika nominal <= 0', async () => {
    const { result } = renderHook(() => useTransferFund());

    await act(async () => {
      await expect(
        result.current.transfer({
          recipientId: 'ACC-001',
          amount: -50,
        })
      ).rejects.toThrow('Nominal transfer harus lebih besar dari 0');
    });

    expect(result.current.isProcessing).toBe(false);
  });
});
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis komponen pengujian di atas:

*   **Baris 9 (`setupServer(...)`):** Menginisialisasi instance mock server runtime Node.js menggunakan primitive interceptor MSW. Tidak memodifikasi runtime client-side code, melainkan mendengarkan pada level koneksi socket HTTP node loopback.
*   **Baris 10 (`http.post(...)`):** Mencegat panggilan HTTP secara deterministik dengan matching method dan path deklaratif, mensimulasikan parsing stream payload request via `await request.json()`.
*   **Baris 24 (`onUnhandledRequest: 'error'`):** Konfigurasi kritikal untuk quality gates. Opsi ini memaksa test runner melempar error fatal jika ada panggilan network dari komponen yang tidak tertangkap oleh mock handler. Mencegah tes bocor ke internet publik secara tidak sengaja (*zero network leakage*).
*   **Baris 25 (`server.resetHandlers()`):** Membersihkan interceptor kustom yang didefinisikan secara lokal di tingkat test suite individual, mencegah kontaminasi state handler ke tes selanjutnya.
*   **Baris 30 (`renderHook(...)`):** Membungkus execution lifecycle hook React ke dalam Virtual Harness Document tanpa memerlukan mounting visual HTML DOM browser secara utuh.
*   **Baris 36 (`await act(async () => ...)`):** Memastikan semua state transitions, context flushes, dan resolution Promise di dalam hook telah dieksekusi tuntas pada task queue sebelum assertion dijalankan. Menghilangkan warning `not wrapped in act(...)` pada React runner.
*   **Baris 62 (`result.current.transfer({ amount: -50 })`):** Memverifikasi *short-circuit logic*. Assertion ini membuktikan bahwa validasi edge case client-side terjadi sebelum IO blocking network request dijalankan.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Insiden Produksi: Regresi "Ghost Checkout" pada Transaksi Flash Sale
*   **Konteks Perusahaan:** Platform e-commerce skala Enterprise dengan volume 10.000 transaksi checkout per menit saat flash sale.
*   **Akar Masalah (The Failure):**
    1.  Sebuah commit meloloskan penanganan race condition pada tombol "Bayar Sekarang". Ketika jaringan klien melambat, pengguna menekan tombol dua kali (*double tap*).
    2.  CI Pipeline lama hanya memeriksa unit test dasar tanpa dynamic network-throttled integration tests dan bundle size gate.
    3.  Frontend melempar unhandled exception karena payload mutating idempotency key tidak sinkron dengan backend, menyebabkan ribuan checkout terdegradasi tanpa alert real-time yang jelas. Metrik HTTP status dari backend tetap mengembalikan `400 Bad Request` yang disalahartikan sebagai "user error biasa".
*   **Dampak Finansial:** Kerugian GMV sebesar ~$140,000 dalam 35 menit transaksi, lonjakan tiket eskalasi CS sebesar 300%, dan churn rate pengguna meningkat drastis.
*   **Solusi Rekayasa:**
    1.  Membangun **Quality Gate Pipeline multi-stage** yang mewajibkan E2E browser tests dengan Playwright di bawah simulasi jaringan *Slow 3G*.
    2.  Penerapan **OpenTelemetry Web Tracing** dengan propagasi context trace parent, mengaitkan interaksi klik tombol klien secara langsung dengan span gateway backend.
    3.  Pemasangan **INP & Performance Budget Quality Gates** pada pipeline CI untuk membatalkan proses deployment jika bundle size naik > 2% atau thread blocking time naik melampaui toleransi limit.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Arsitektur solusi mencakup pipeline observabilitas OpenTelemetry klien yang memancarkan spans dengan konteks HTTP, pengujian E2E Playwright dengan simulasi throttling, dan skrip GitHub Actions CI yang memberlakukan quality gates anti-regresi.

### 1. Instrumentasi Frontend OpenTelemetry: `telemetry.ts`

```typescript
// src/monitoring/telemetry.ts
import { WebTracerProvider } from '@opentelemetry/sdk-trace-web';
import { SimpleSpanProcessor, BatchSpanProcessor } from '@opentelemetry/sdk-trace-base';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { ZoneContextManager } from '@opentelemetry/context-zone';
import { registerInstrumentations } from '@opentelemetry/instrumentation';
import { FetchInstrumentation } from '@opentelemetry/instrumentation-fetch';
import { Resource } from '@opentelemetry/resources';
import { SemanticResourceAttributes } from '@opentelemetry/semantic-conventions';

const isProduction = process.env.NODE_ENV === 'production';

export function initializeTelemetry() {
  const exporter = new OTLPTraceExporter({
    url: isProduction
      ? 'https://telemetry-gateway.enterprise.internal/v1/traces'
      : 'http://localhost:4318/v1/traces',
  });

  const provider = new WebTracerProvider({
    resource: new Resource({
      [SemanticResourceAttributes.SERVICE_NAME]: 'checkout-frontend-spa',
      [SemanticResourceAttributes.SERVICE_VERSION]: '2.4.1',
      [SemanticResourceAttributes.DEPLOYMENT_ENVIRONMENT]: process.env.NODE_ENV,
    }),
  });

  // BatchSpanProcessor untuk throughput optimal di lingkungan produksi
  provider.addSpanProcessor(
    isProduction ? new BatchSpanProcessor(exporter) : new SimpleSpanProcessor(exporter)
  );

  provider.register({
    contextManager: new ZoneContextManager(),
  });

  registerInstrumentations({
    instrumentations: [
      new FetchInstrumentation({
        propagateTraceHeaderCorsUrls: [
          /https:\/\/api\.enterprise\.internal\/.*/,
          /\/api\/v1\/.*/,
        ],
        clearTimingResources: true,
      }),
    ],
  });

  return provider.getTracer('checkout-tracer');
}
```

### 2. Pengujian E2E Anti-Race Condition: `checkout.spec.ts`

```typescript
// tests/e2e/checkout.spec.ts
import { test, expect } from '@playwright/test';

test.describe('E2E Checkout Flow with Latency & Concurrency Stress', () => {
  test('harus memblokir double submission secara deterministik dalam kondisi jaringan lambat', async ({
    page,
    context,
  }) => {
    // 1. Simulasikan profil jaringan lambat (Slow 3G)
    const cdpSession = await context.newCDPSession(page);
    await cdpSession.send('Network.emulateNetworkConditions', {
      offline: false,
      latency: 500, // 500ms delay
      downloadThroughput: ((500 * 1024) / 8), // 500 kbps
      uploadThroughput: ((500 * 1024) / 8),
    });

    let checkoutPostCounter = 0;
    // Intersep route network untuk memvalidasi idempotency call
    await page.route('**/api/v1/checkout', async (route) => {
      checkoutPostCounter++;
      // Tahan response selama 300ms untuk mensimulasikan latensi server
      await new Promise((r) => setTimeout(r, 300));
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          orderId: 'ORD-99120',
          status: 'COMPLETED',
        }),
      });
    });

    await page.goto('/checkout');

    const payButton = page.getByRole('button', { name: /Bayar Sekarang/i });
    await expect(payButton).toBeVisible();
    await expect(payButton).toBeEnabled();

    // 2. Eksekusi rapid clicking (Double Click Stress)
    await payButton.click({ clickCount: 1 });
    // Klik kedua instan saat request pertama sedang berjalan
    await payButton.click({ force: true }).catch(() => {
      // Tombol idealnya langsung ter-disable, proteksi assertion
    });

    // 3. Verifikasi UI State
    await expect(payButton).toBeDisabled();
    await expect(page.getByTestId('loading-spinner')).toBeVisible();

    // 4. Verifikasi notifikasi konfirmasi muncul
    const successAlert = page.getByRole('alert');
    await expect(successAlert).toHaveText(/Pembayaran Berhasil Diverifikasi/i, {
      timeout: 10000,
    });

    // CRITICAL QUALITY ASSERTION:
    // Pastikan request network hanya terjadi TEPAT SATU KALI meski ditekan multi-click
    expect(checkoutPostCounter).toBe(1);
  });
});
```

### 3. CI/CD Enterprise Quality Gates Pipeline: `.github/workflows/quality-gates.yml`

```yaml
name: Production Quality Gates

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  static-and-mutation-analysis:
    name: Code Integrity & Mutation Analysis
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code Repository
        uses: actions/checkout@v4

      - name: Setup Node.js Environment
        uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'npm'

      - name: Install Dependencies
        run: npm ci

      - name: Strict Typecheck
        run: npm run typecheck

      - name: ESLint Static Guard
        run: npm run lint -- --max-warnings=0

      - name: Unit & Component Integration Tests
        run: npm run test:coverage -- --coverage.thresholds='{"lines":85,"branches":80,"functions":85}'

      - name: Execute Mutation Testing (Stryker)
        run: npx stryker run --scoreThreshold.break 80

  bundle-size-and-perf-gate:
    name: Asset Budget & Performance Guard
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'npm'

      - name: Install Dependencies
        run: npm ci

      - name: Production Build
        run: npm run build

      - name: Check Bundle Size Threshold
        uses: andresz1/size-limit-action@v1
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}

  e2e-matrix-testing:
    name: Playwright Dynamic E2E Testing
    needs: [static-and-mutation-analysis, bundle-size-and-perf-gate]
    runs-on: ubuntu-latest
    strategy:
      fail-fast: true
      matrix:
        shard: [1/3, 2/3, 3/3]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'npm'

      - name: Install Dependencies
        run: npm ci

      - name: Install Playwright Browsers
        run: npx playwright install --with-deps chromium

      - name: Run Sharded Playwright Suite
        run: npx playwright test --shard=${{ matrix.shard }}

      - name: Upload Test Report Artifact
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-report-${{ strategy.job-index }}
          path: playwright-report/
          retention-days: 7
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter Dimensi | Unit Testing Murni | Integration (RTL + MSW) | End-to-End (Playwright) | Visual Regression (Lost-Pixel) |
| :--- | :--- | :--- | :--- | :--- |
| **Execution Velocity** | Sub-milidetik per tes (Sangat Cepat) | 50ms - 300ms per tes suite | 2s - 15s per flow (Lambat) | 1s - 5s per snapshot render |
| **Maintenance Cost** | Rendah (Kecuali overmocking logic) | Rendah ke Moderat | Tinggi (Flakiness DOM, Layout Shift) | Moderat (Sering diff false-positive) |
| **Confidence Level** | Rendah (Hanya isolasi fungsi/algoritma) | Sangat Tinggi (Menguji realita interaksi) | Maksimal (Menguji browser engine nyata) | Tinggi (Khusus fidelitas tata letak visual) |
| **CI Resource Cost** | Minimal (Single core CPU) | Efisien (Multi-thread concurrent) | Tinggi (Perlu GPU/Headless Browser & RAM) | Sangat Tinggi (Compute visual diffing) |
| **Network Reality** | Full Mocking / No IO | Mocked Network Layer (Virtual Service) | Full Stack / Sandbox Server | Static / Mock Data Only |
| **Lokasi Deteksi Bug** | Logika kalkulasi, transformasi data | State race condition, form lifecycle | SSO, Routing, Gateway proxy mismatch | CSS breakage, Z-Index collision, font shift |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Memory Leaks pada Unmounted Observers
*   **Edge Case:** Pengujian SPA yang mendaftarkan listener telemetri `PerformanceObserver` atau `IntersectionObserver`. Komponen dilepas (*unmounted*), namun observer tetap hidup di memori lingkungan pengujian Jest/JSDOM.
*   **Dampak:** Terjadinya *heap memory blowup* saat mengeksekusi ribuan tes suite dalam satu proses runner CI, menyebabkan *Exit Code 137 (OOM KILLED)*.
*   **Mitigasi:** Selalu implementasikan lifecycle teardown mutlak menggunakan blok cleanup:
    ```typescript
    useEffect(() => {
      const observer = new PerformanceObserver((list) => { ... });
      observer.observe({ entryTypes: ['largest-contentful-paint'] });
      return () => observer.disconnect(); // WAJIB: Mencegah kebocoran context
    }, []);
    ```

### 2. Microtask Starvation via Unmocked Recursive Polling
*   **Edge Case:** Komponen menggunakan long-polling internal berbasis `requestAnimationFrame` atau self-invoking `setTimeout` rekursif untuk memperbarui status transaksi.
*   **Dampak:** `waitFor()` dari React Testing Library mengalami timeout eksekusi tanpa batas karena microtask queue tidak pernah berada dalam kondisi idle.
*   **Mitigasi:** Manfaatkan fake timers secara deterministik melalui Vitest engine:
    ```typescript
    it('menguji timeout dengan fake timers', async () => {
      vi.useFakeTimers();
      // Render dan trigger aksi
      vi.advanceTimersByTime(5000); // Gerakkan clock virtual
      vi.useRealTimers(); // Teardown kembali ke normal
    });
    ```

### 3. Masking Status HTTP Code melalui Soft-Fails
*   **Edge Case:** Pustaka telemetri klien menangkap error HTTP 500 dan hanya mencatatnya sebagai `console.warn`, mengembalikan state fallback kosong `{ data: [] }`.
*   **Dampak:** Integration test membaca UI valid (tampilan kosong), test tetap pass, namun di produksi pengguna mengalami kegagalan operasional tanpa peringatan alert sentry/APM.
*   **Mitigasi:** Tegakkan Quality Gate yang menangkap penulisan `console.error` atau `console.warn` tak terduga sebagai kegagalan tes:
    ```typescript
    // vitest.setup.ts
    beforeEach(() => {
      vi.spyOn(console, 'error').mockImplementation((msg) => {
        throw new Error(`Unexpected console.error detected: ${msg}`);
      });
    });
    ```

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Menguji Detail Implementasi (Testing Internal State)
```typescript
// SALAH (Menguji state internal/detail implementasi)
test('menguji state modal', () => {
  const wrapper = shallow(<CheckoutModal />);
  expect(wrapper.state('isOpen')).toBe(true); // Rapuh! Pecah saat refactor ke Hooks/Zustand
});

// BENAR (Menguji perilaku observable dari perspektif pengguna)
test('menguji modal muncul secara semantik', () => {
  render(<CheckoutModal />);
  expect(screen.getByRole('dialog', { name: /konfirmasi bayar/i })).toBeVisible();
});
```

### Kesalahan 2: Menggunakan Mocking Granular Berlebih (`jest.mock('axios')`)
```typescript
// SALAH: Mencegah eksekusi middleware network dan parsing internal
vi.mock('axios');
axios.get.mockResolvedValue({ data: { id: 1 } });

// BENAR: Gunakan MSW untuk menangani request pada tingkat HTTP primitives
server.use(
  http.get('/api/resource', () => {
    return HttpResponse.json({ id: 1 });
  })
);
```

### Kesalahan 3: Tidak Mengisolasi Storage State di Antara Sesi Pengujian E2E
```typescript
// SALAH: Sesi tes berikutnya mewarisi Cookie/LocalStorage dari tes sebelumnya
test('Test B User Login', async ({ page }) => {
  await page.goto('/dashboard'); // Gagal karena token dari Test A masih ada!
