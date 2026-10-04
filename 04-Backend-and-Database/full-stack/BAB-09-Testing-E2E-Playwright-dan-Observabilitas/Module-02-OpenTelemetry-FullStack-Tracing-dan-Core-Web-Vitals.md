---
[⬅️ Module 01: Playwright E2E Testing](./Module-01-Playwright-E2E-Automation-dan-Component-Testing.md) | [📋 Silabus Induk](../README.md) | [BAB 09 Quiz & Challenge ➡️](./BAB-09-Quiz-dan-Challenge.md)
---

# Module 02: Full-Stack Observability: OpenTelemetry Tracing (Browser RUM to Database Spans) & Core Web Vitals

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Memahami tiga pilar utama observabilitas modern: **Metrics**, **Logs**, dan **Distributed Traces**.
- Menguasai standar industri **OpenTelemetry (OTel)** dan protokol **W3C Trace Context (`traceparent`)** untuk menghubungkan jejak eksekusi (*trace*) dari klik mouse di browser, melewati Edge Middleware, masuk ke Node.js Server Components, hingga ke span query database PostgreSQL.
- Mengimplementasikan pemantauan performa pengguna nyata (**Real User Monitoring / RUM**) untuk mengukur tiga metrik **Google Core Web Vitals (CWV)** utama: **Largest Contentful Paint (LCP)**, **Interaction to Next Paint (INP)**, dan **Cumulative Layout Shift (CLS)**.
- Mendiagnosis dan mengeliminasi *latency bottlenecks* pada backend: mendeteksi *sequential async waterfall*, kueri database tanpa indeks, dan overhead serialization.
- Mengintegrasikan OpenTelemetry SDK dengan backend telemetri modern (Grafana Tempo, Jaeger, Datadog, atau Honeycomb) menggunakan protokol OTLP (*OpenTelemetry Protocol*).

---

## 2. Prerequisite
- Memahami arsitektur full-stack client-server dan header HTTP.
- Memahami siklus rendering browser (DOM, Paint, Layout) dari Bab 01.
- Memahami query database SQL dari Bab 05.

---

## 3. Concept
Ketika aplikasi full-stack berjalan di lingkungan produksi dan seorang pengguna mengeluh: *"Website lambat sekali saat saya menekan tombol checkout!"*, developer tradisional sering kali kebingungan:
- Apakah masalahnya ada di koneksi internet pengguna?
- Apakah React memakan waktu terlalu lama untuk me-render komponen?
- Apakah ada middleware serverless yang mengalami *cold start*?
- Atau apakah ada query SQL di database yang terkunci (*deadlock / unindexed scan*)?

**Distributed Tracing dengan OpenTelemetry** menjawab pertanyaan ini secara ilmiah. OpenTelemetry menyematkan sebuah ID pelacak unik bernama **Trace ID** pada awal interaksi pengguna di browser, lalu meneruskan ID tersebut melintasi seluruh jaringan melalui header standar **W3C `traceparent`**:

```
[ BROWSER CLIENT (RUM) ]
  Span: "User Click: Checkout Button" (Duration: 1.2s)
  Header dikirim: traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
        |
        v
[ NEXT.JS EDGE MIDDLEWARE ]
  Span: "Verify Session Token & Nonce" (Duration: 2ms)
        |
        v
[ NODE.JS BACKEND (Server Action / tRPC) ]
  Span: "Process Payment Order Logic" (Duration: 180ms)
        |
        v
[ DATABASE LAYER (PostgreSQL) ]
  Span: "db.query: SELECT * FROM stock FOR UPDATE" (Duration: 15ms)
```

Hasilnya adalah sebuah grafik visual terpadu (*Flame Graph / Waterfall Timeline*) yang memperlihatkan durasi setiap milidetik eksekusi dari frontend hingga database terdalam dalam satu kesatuan cerita!

---

## 4. Why? (Mengapa Core Web Vitals & Tracing Krusial?)
1. **Dampak Langsung terhadap SEO & Konversi Finansial**:
   - Google secara resmi menggunakan Core Web Vitals sebagai **faktor penentu peringkat SEO pencarian (Search Ranking Factor)**.
   - Studi industri menunjukkan bahwa setiap penundaan 100 milidetik pada LCP dapat menurunkan angka konversi e-commerce hingga 7%.
2. **Standar Metrik Baru INP (Interaction to Next Paint)**:
   - Menggantikan metrik lama *First Input Delay (FID)*. INP mengukur responsivitas visual halaman terhadap **seluruh interaksi klik, ketukan keyboard, dan tap** sepanjang pengguna berada di website, bukan hanya interaksi pertama.
3. **Meniadakan Perdebatan Antar-Tim (No More Blame Game)**:
   - Tracing membuktikan secara objektif di mana letak latensi sebenarnya: apakah di JavaScript bundle frontend atau query SQL backend.

---

## 5. What? (Tiga Metrik Utama Google Core Web Vitals)

### A. Largest Contentful Paint (LCP)
- **Definisi**: Waktu yang dibutuhkan untuk merender elemen visual terbesar (biasanya gambar hero banner atau blok teks heading utama) di layar.
- **Standar**:
  - 🟢 **Baik**: $\le 2.5$ detik.
  - 🟡 **Perlu Peningkatan**: $2.5 - 4.0$ detik.
  - 🔴 **Buruk**: $> 4.0$ detik.

### B. Interaction to Next Paint (INP)
- **Definisi**: Menilai responsivitas antarmuka dengan mengukur jeda waktu terlama antara input pengguna (misal: klik tombol) hingga browser selesai menggambar frame visual berikutnya di layar.
- **Standar**:
  - 🟢 **Baik**: $\le 200$ milidetik.
  - 🟡 **Perlu Peningkatan**: $200 - 500$ milidetik.
  - 🔴 **Buruk**: $> 500$ milidetik.

### C. Cumulative Layout Shift (CLS)
- **Definisi**: Mengukur stabilitas visual halaman dengan menghitung total pergeseran tata letak tak terduga (*unexpected layout shift*) saat halaman sedang dimuat (misalnya: teks mendadak melompat ke bawah karena iklan atau gambar tanpa dimensi tinggi/lebar baru selesai diunduh).
- **Standar**:
  - 🟢 **Baik**: $\le 0.1$.
  - 🟡 **Perlu Peningkatan**: $0.1 - 0.25$.
  - 🔴 **Buruk**: $> 0.25$.

---

## 6. How? (Implementasi OpenTelemetry & Core Web Vitals)

### 1. Inisialisasi OpenTelemetry di Next.js (instrumentation.ts)
Next.js menyediakan fitur eksperimental `instrumentationHook` untuk mendaftarkan OTel SDK:

```typescript
// instrumentation.ts
export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    const { NodeSDK } = await import("@opentelemetry/sdk-node");
    const { OTLPTraceExporter } = await import("@opentelemetry/exporter-trace-otlp-http");
    const { Resource } = await import("@opentelemetry/resources");
    const { SemanticResourceAttributes } = await import("@opentelemetry/semantic-conventions");
    const { getNodeAutoInstrumentations } = await import("@opentelemetry/auto-instrumentations-node");

    const sdk = new NodeSDK({
      resource: new Resource({
        [SemanticResourceAttributes.SERVICE_NAME]: "enterprise-saas-frontend",
        [SemanticResourceAttributes.DEPLOYMENT_ENVIRONMENT]: process.env.NODE_ENV,
      }),
      traceExporter: new OTLPTraceExporter({
        url: process.env.OTEL_EXPORTER_OTLP_ENDPOINT || "http://localhost:4318/v1/traces",
      }),
      instrumentations: [
        getNodeAutoInstrumentations({
          "@opentelemetry/instrumentation-fs": { enabled: false }, // Matikan noise I/O file
        }),
      ],
    });

    sdk.start();
    console.log("🔭 OpenTelemetry Node SDK berhasil diinisialisasi!");
  }
}
```

### 2. Melaporkan Core Web Vitals di Frontend (app/layout.tsx / reportWebVitals)
```typescript
// app/web-vitals.tsx
"use client";
import { useReportWebVitals } from "next/web-vitals";

export function WebVitalsReporter() {
  useReportWebVitals((metric) => {
    // Format metric: { id, name, value, rating, navigationType }
    console.log(`[CWV] ${metric.name}: ${metric.value.toFixed(2)} (${metric.rating})`);

    // Kirim metrik ke endpoint analitik telemetri internal
    if (navigator.sendBeacon) {
      const payload = JSON.stringify({
        name: metric.name,
        value: metric.value,
        rating: metric.rating,
        page: window.location.pathname,
        timestamp: Date.now(),
      });
      navigator.sendBeacon("/api/telemetry/vitals", payload);
    }
  });

  return null;
}
```

### 3. Membuat Custom Span Manual pada Logika Bisnis Kritis
```typescript
import { trace } from "@opentelemetry/api";

const tracer = trace.getTracer("payment-service");

export async function processOrderWithTelemetry(orderId: string, amount: number) {
  // Buat custom span khusus untuk memonitor blok ini
  return await tracer.startActiveSpan("payment.execute_settlement", async (span) => {
    try {
      span.setAttribute("order.id", orderId);
      span.setAttribute("payment.amount", amount);

      const result = await executePaymentGateway(orderId, amount);

      span.setStatus({ code: 1 }); // 1 = OK
      return result;
    } catch (err: any) {
      span.recordException(err);
      span.setStatus({ code: 2, message: err.message }); // 2 = ERROR
      throw err;
    } finally {
      span.end(); // Wajib ditutup!
    }
  });
}
```

---

## 7. Analogy
Bayangkan sebuah paket kilat yang Anda kirim ke luar negeri:
- **Logging Biasa**: Masing-masing kurir mencatat di buku catatan kecil masing-masing tanpa nomor referensi yang sama. Jika paket hilang di tengah jalan, Anda harus menelepon 5 kantor berbeda di 3 negara dan mencocokkan jam secara manual (*Siloed Logs*).
- **OpenTelemetry Distributed Tracing**: Paket ditempel barcode pelacak internasional (**Trace ID / W3C Traceparent**). Saat paket dipindai di bandara Jakarta (*Browser RUM*), lalu di pabean Singapura (*Edge Middleware*), lalu di gudang transit Frankfurt (*Node.js Server*), hingga diserahkan ke kurir lokal (*Database*), Anda dapat melihat status pelacakan detik demi detik pada satu layar peta digital secara real-time!

---

## 8. Diagram Anatomi W3C Traceparent Header & Span Waterfall

```
FORMAT STANDAR W3C TRACEPARENT:
version - trace_id (32 hex)                - parent_id (16 hex) - trace_flags (2 hex)
00      - 4bf92f3577b34da6a3ce929d0e0e4736 - 00f067aa0ba902b7   - 01

FLAME GRAPH TIMELINE TRACE:
0ms                             500ms                           1000ms
+--------------------------------------------------------------------+
| [Root Span] HTTP POST /api/checkout (Total: 950ms)                 |
+--------------------------------------------------------------------+
  |-- [Span 1] Edge Middleware Verify Auth (12ms)
  |-- [Span 2] Server Action Input Parsing via Zod (2ms)
  |-- [Span 3] PostgreSQL: BEGIN TRANSACTION (4ms)
  |-- [Span 4] PostgreSQL: SELECT * FROM inventory FOR UPDATE (120ms)
  |-- [Span 5] HTTP Call to Stripe Payment Gateway (650ms) <--- BOTTLENECK!
  |-- [Span 6] PostgreSQL: COMMIT (8ms)
```

---

## 9. Simple Example: Anatomi Format W3C Trace Context
Standar W3C (RFC Recommendation) mewajibkan dua header HTTP untuk propagasi jejak:
1. `traceparent`: Berisi 4 field dipisahkan tanda strip `-`:
   - `00`: Versi protokol saat ini.
   - `4bf92f3577b34da6a3ce929d0e0e4736`: ID Jejak Global (*Trace ID*) yang menghubungkan seluruh microservice.
   - `00f067aa0ba902b7`: ID Span Induk (*Parent Span ID*).
   - `01`: Flag tracing (`01` artinya trace di-sample dan direkam).
2. `tracestate`: Menyimpan informasi vendor sistem khusus (seperti `rojo=1,congo=2`).

---

## 10. Practical Example: Mengeliminasi Sequential Async Waterfall
Salah satu penyebab paling umum hancurnya metrik LCP dan Server Latency adalah kueri serial yang tidak perlu:

```typescript
// ❌ KODE LAMBAT (Sequential Waterfall: Total Waktu = 100ms + 150ms + 80ms = 330ms):
const user = await db.getUser(userId);        // butuh 100ms
const orders = await db.getOrders(userId);    // butuh 150ms
const settings = await db.getSettings(userId);// butuh 80ms

// ✅ KODE CEPAT (Parallel Execution via Promise.all: Total Waktu = MAX(100, 150, 80) = 150ms!):
const [user, orders, settings] = await Promise.all([
  db.getUser(userId),
  db.getOrders(userId),
  db.getSettings(userId),
]);
```
Perubahan sederhana ini memotong latensi server hingga lebih dari 50%!

---

## 11. Real-World Example: Real User Monitoring (RUM) Dashboard Pipeline
Alur data metrik Core Web Vitals dari jutaan pengguna ke sistem analitik:

```
[ Browser Jutaan Pengguna ] ---> `navigator.sendBeacon('/api/vitals')`
              |
              v
[ Cloudflare Edge Worker / Ingestion Route ]
              |
              v
[ ClickHouse / Prometheus Timeseries DB ]
              |
              v
[ Grafana Dashboard ]
  -> P75 LCP: 1.8 detik (🟢 Sehat)
  -> P75 INP: 120 ms (🟢 Sehat)
  -> P75 CLS: 0.04 (🟢 Sehat)
```

---

## 12. Trade-offs: Observability Overhead vs Visibility

| Kriteria | Full Distributed Tracing (100% Sampling) | Head-Based Adaptive Sampling (5-10%) | No Tracing (Hanya Logs) |
| :--- | :--- | :--- | :--- |
| **Visibilitas Masalah** | **100% Sempurna (Setiap error terekam)** | Sangat Baik (Cukup untuk statistik) | Lemah (Sulit korelasi) |
| **Overhead CPU & Network**| Menengah (~3-5% komputasi) | **Sangat Rendah (<0.5%)** | Minimal |
| **Biaya Penyimpanan (Storage)**| Sangat Mahal (Terabyte data trace per hari)| **Optimal & Terkendali** | Murah |

---

## 13. When To Use OpenTelemetry & Web Vitals
- Aplikasi web skala enterprise dengan banyak microservice atau arsitektur serverless terdistribusi.
- Platform e-commerce di mana performa visual (LCP & INP) berkorelasi langsung dengan pendapatan bisnis.
- Sistem yang menuntut jaminan Service Level Agreement (SLA) latensi tinggi (Fintech, Healthcare).

---

## 14. When NOT To Use Full Tracing
- Proyek prototipe sampingan (*hobby projects*) di mana biaya infrastruktur collector OTel melebihi biaya aplikasi itu sendiri.
- Situs statis murni tanpa backend (cukup gunakan Google Search Console Core Web Vitals audit).

---

## 15. Common Mistakes
1. **Mengabaikan Pergeseran Tata Letak (CLS) Akibat Dimensi Gambar Hilang**:
   - Menulis tag `<img src="/banner.jpg" />` tanpa atribut `width` dan `height`. Browser tidak tahu rasio aspek gambar sebelum diunduh, menyebabkan seluruh teks di bawahnya melompat mendadak saat gambar muncul (*Layout Shift*).
   - *Solusi*: Selalu gunakan komponen Next.js `<Image src="..." width={800} height={400} />` yang secara otomatis memesan ruang layout (*aspect-ratio reservation*).
2. **Membiarkan Span Terbuka Tanpa Memanggil `span.end()`**:
   - Jika span tidak ditutup di blok `finally`, memori server akan mengalami kebocoran (*memory leak*) dan trace tidak akan pernah dikirimkan ke collector.
3. **Merekam Data Sensitif Pengguna (PII) ke dalam Span Attributes**:
   - Menyimpan password mentah, nomor kartu kredit, atau token autentikasi ke dalam atribut span OTel yang dapat dibaca oleh seluruh tim di dashboard Grafana/Datadog.

---

## 16. Best Practices

### Must Have
- Terapkan W3C `traceparent` header propagation pada seluruh panggilan `fetch` antar-service.
- Monitor metrik Core Web Vitals pada **Persentil ke-75 (P75)** pengguna, bukan rata-rata (*Average*), untuk menangkap pengalaman pengguna dengan koneksi lambat.

### Recommended
- Gunakan Next.js `<Image>` dan `@next/font` untuk mengeliminasi Cumulative Layout Shift (CLS) dan font flash (FOIT/FOUT).
- Bungkus panggilan database dengan OpenTelemetry auto-instrumentation untuk melacak kueri lambat secara otomatis.

### Advanced
- Konfigurasikan *Tail-Based Sampling* pada OTel Collector: buang 99% trace yang sukses cepat, tetapi simpan 100% trace yang mengalami error atau memiliki latensi di atas 2 detik.

### Avoid
- Jangan menggunakan `fetch` berantai di dalam loop `for` jika data dapat diambil secara bersamaan (*concurrently*) menggunakan `Promise.all()`.

---

## 17. Troubleshooting Guide

| Gejala Masalah | Kemungkinan Akar Masalah | Solusi |
| :--- | :--- | :--- |
| Trace terputus di tengah jalan (*Broken Trace Context*). | Ada service perantara yang tidak meneruskan header `traceparent` HTTP ke service berikutnya. | Pastikan seluruh HTTP client menggunakan library instrumentasi OTel atau menyalin header `traceparent` secara manual. |
| Skor INP melonjak merah (>500ms) di perangkat seluler. | Ada tugas JavaScript berat (*Long Task* > 50ms) yang memblokir main thread browser saat pengguna mengklik tombol. | Pecah komputasi berat menggunakan `requestIdleCallback()` atau pindahkan ke Web Worker. |
| Skor LCP buruk padahal server cepat (TTFB rendah). | Gambar hero banner berukuran raksasa (5MB) dan tidak dioptimalkan format WebP/AVIF. | Kompres gambar hero, gunakan format AVIF, dan tambahkan atribut `priority` pada tag `<Image priority />`. |

---

## 18. Exercise
- **Easy**: Buat komponen gambar React yang menerapkan atribut `width`, `height`, dan style `aspect-ratio` untuk mencegah CLS.
- **Medium**: Tulis fungsi helper `traceparent` generator di JavaScript yang menghasilkan string format W3C yang valid dengan Trace ID acak 32 hex.
- **Hard**: Rancang script simulasi OTel Tracing yang melacak durasi eksekusi request full-stack: mengukur span browser, span middleware, dan span database, lalu mencatatnya dalam format representasi grafik hierarki.

---

## 19. Challenge
Rancang arsitektur observabilitas end-to-end untuk platform marketplace: Sistem harus mengumpulkan metrik Core Web Vitals dari 50.000 browser pengguna setiap menit menggunakan `navigator.sendBeacon`, menyaring anomali LCP di atas 4 detik, mengorelasikan metrik tersebut dengan Distributed Tracing OTel di backend, dan memicu notifikasi otomatis ke tim engineer jika P75 INP melebihi ambang batas toleransi 200ms.

---

## 20. Summary
- Observabilitas sejati menuntut pandangan menyeluruh dari mata pengguna akhir hingga ke baris terdalam database SQL.
- **Google Core Web Vitals (LCP, INP, CLS)** adalah kompas utama performa pengalaman pengguna dan keberhasilan SEO aplikasi web modern.
- **OpenTelemetry & W3C Trace Context** menyatukan logs, metrics, dan traces menjadi standar terbuka global, memungkinkan diagnosis bottleneck performa full-stack dalam hitungan detik.

---

## Hands-on Practice: Simulasi OpenTelemetry Tracing & Web Vitals Collector
Jalankan simulator pelacak distributed trace W3C, korelasi span, dan analitik Core Web Vitals mandiri:

```bash
node Full-Stack/BAB-09-Testing-E2E-Playwright-dan-Observabilitas/hands-on/m02/opentelemetry_fullstack_tracing_sim.js
```

---
[⬅️ Module 01: Playwright E2E Testing](./Module-01-Playwright-E2E-Automation-dan-Component-Testing.md) | [📋 Silabus Induk](../README.md) | [BAB 09 Quiz & Challenge ➡️](./BAB-09-Quiz-dan-Challenge.md)
---
