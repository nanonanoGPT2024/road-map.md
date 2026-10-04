# MODUL 02: DEEP DIVE, IMPLEMENTASI LANJUTAN & ARSITEKTUR PRODUKSI
**Bab 09: Product Metrics, Analytics, dan Continuous Experimentation**  
**Kategori: 03-Frontend-and-Mobile / product-design**

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Merancang dan mengimplementasikan arsitektur *continuous experimentation* dan *event collection* terdistribusi dengan latensi P99 < 15ms pada sisi frontend/edge.
- Menguasai determinasi varian (*bucketing*) deterministik menggunakan algoritma hashing (MurmurHash3) di Edge Middleware tanpa memicu *flicker* (Layout Shift) dan *hydration mismatch*.
- Membangun pipeline analitik *first-party data collection* yang tahan terhadap ad-blocker, meminimalkan *main-thread blocking*, dan mengoptimalkan kompresi *payload* telemetry.
- Mendeteksi anomali eksperimentasi teknis secara otomatis, termasuk *Sample Ratio Mismatch* (SRM) dan *network delivery degradation*.
- Mengimplementasikan teknik *variance reduction* (CUPED) dan evaluasi statistik sekuensial pada data analitik produk.

---

## 2. Prerequisite
Untuk memahami modul ini secara komprehensif, peserta wajib menguasai:
- **TypeScript Lanjutan:** Utility types, generic constraints, conditional types, dan memory safety.
- **Frontend Architecture:** Next.js (App Router), React Server Components (RSC), Edge Runtime, dan Web Workers API.
- **Sistem Terdistribusi Dasar:** Event-driven architecture, message broker (Apache Kafka), dan columnar OLAP database (ClickHouse/BigQuery).
- **Statistika Inferensial Dasar:** Hipotesis null ($H_0$), p-value, confidence interval, statistical power ($1-\beta$), dan Type I/II errors.

---

## 3. Concept & Internal Architecture

Eksperimentasi dan instrumentasi analitik modern di level enterprise tidak lagi mengandalkan tag injection client-side pihak ketiga (seperti Google Optimize lama atau vanilla vendor scripts). Pendekatan lawas memicu tiga masalah fatal: degradasi Core Web Vitals (terutama Cumulative Layout Shift/CLS dan Interaction to Next Paint/INP), kebocoran data privasi (GDPR/CPRA non-compliance), serta *flickering effect* saat rendering.

Arsitektur produksi modern menerapkan **Hybrid Edge-First Telemetry & Experimentation Loop**:

```
                       [ CLIENT LAYER ]
               Browser / Mobile Native Client
       +---------------------------------------------+
       | React UI Tree (RSC / Client Islands)        |
       |  |                                          |
       |  +--> Web Worker (Analytics Ingestion Pipe) |
       +---------------------------------------------+
                        |                 |
     HTTP/3 Edge Eval   |                 | navigator.sendBeacon
     (Context Headers)  |                 | (Batched Proto/JSON)
                        v                 v
       +---------------------------------------------+
       |          EDGE COMPUTING LAYER               |
       | (Cloudflare Workers / Vercel Edge Runtime)  |
       |  - MurmurHash3 Bucketing                    |
       |  - Geo/Device Enrichment                    |
       |  - Reverse Proxy Event Forwarder            |
       +---------------------------------------------+
                        |                 |
         Deterministic  |                 | HTTP Ingestion API
         Payload Inject |                 | (TLS Termination)
                        v                 v
       +--------------------+    +-------------------+
       | Origin Application |    | Ingestion Gateway |
       | (SSR / Edge Render)|    | (Go / Rust)       |
       +--------------------+    +-------------------+
                                           |
                                           v
                                 +-------------------+
                                 | Apache Kafka Topic|
                                 +-------------------+
                                           |
                                           v
                                 +-------------------+
                                 | ClickHouse / OLAP |
                                 +-------------------+
                                           |
                                           v
                                 +-------------------+
                                 | Automated SRM &   |
                                 | Stats Engine      |
                                 +-------------------+
```

### Mekanisme Internal:
1. **Edge-Driven Variant Allocation:** Routing layer membaca persistent identifier (contoh: `anonymous_id` dari secure first-party cookie). Algoritma `MurmurHash3` memetakan hash string `experiment_id + ":" + anonymous_id` ke dalam integer `[0..99]`.
2. **Context Propagation Tanpa Blocking:** Varian langsung disuntikkan ke HTTP Request Headers (`x-experiment-variants`) menuju origin SSR, menghilangkan CLS secara total karena HTML yang dikirim sudah dalam kondisi *targeted variant*.
3. **Web Worker Event Offloading:** Interaksi pengguna (klik, impresi, konversi) ditangkap oleh lightweight client SDK dan dialihkan dari *main thread* ke dedicated Web Worker via `postMessage()`. Worker menyusun buffer event, mengompresi payload via `CompressionStream` (GZIP/Brotli), dan mengirimkannya via `navigator.sendBeacon()` atau raw fetch keep-alive.
4. **Ingestion & Real-time OLAP:** Gateway memvalidasi event contract (menggunakan JSON Schema / Protocol Buffers), meneruskan data ke partitioned Kafka stream, lalu disimpan secara columnar di ClickHouse untuk analisis konversi dan deteksi SRM real-time.

---

## 4. Why & What

| Dimensi | Pendekatan Tradisional (Client-Side Tag) | Pendekatan Modern (Edge & In-House Telemetry) |
| :--- | :--- | :--- |
| **Lokasi Evaluasi** | Client Browser via JavaScript runtime | CDN Edge Middleware / RSC Origin |
| **Dampak Layout Shift** | Tinggi (Flicker: Konten default dirender lalu di-swap) | Nol (Zero CLS: Varian di-render langsung di server) |
| **Dampak Web Vitals** | TBT/INP melonjak akibat eksekusi script 50-100kb | TBT/INP netral; eksekusi analitik diisolasi ke Web Worker |
| **Integritas Data** | Rentan Ad-Blocker (data drop 15% - 40%) | Tahan Ad-Blocker (First-Party Domain Reverse Proxy) |
| **Validasi Skema** | Loose / Runtime exceptions silently ignored | Strict Typed Contract (Contract-Driven Telemetry) |
| **Keamanan Data** | PII berisiko terekspos ke vendor SaaS pihak ketiga | PII di-masking/hashing di Edge sebelum masuk pipeline |

---

## 5. How (Workflow Detail)

Alur kerja implementasi sistem eksperimentasi dan analitik end-to-end:

### Langkah 1: Definisi Kontrak Eksperimen & Event
Rancang konfigurasi eksperimen terstruktur menggunakan tipe immutable. Skema event divalidasi dua arah: build-time static checking (TypeScript) dan ingest-time schema validation.

### Langkah 2: Edge Bucketing & State Hydration
Pada edge middleware:
- Ekstraksi atau inisialisasi `device_id` / `user_id`.
- Ambil manifest eksperimen aktif dari fast distributed cache (Upstash Redis / Cloudflare KV).
- Hitung bucket varian menggunakan hashing deterministik.
- Set HTTP response header untuk caching variant-aware (`Vary: x-experiment-variants`).

### Langkah 3: Eksekusi Komponen Frontend
Komponen React membaca nilai varian langsung dari React Server Context atau Page Props:
- Render varian A atau varian B secara deterministik tanpa `useEffect`.
- Tembakkan event impresi `experiment_viewed` yang membawa context payload lengkap (`experiment_id`, `variant_id`, `routing_layer`).

### Langkah 4: Batching & Egress Pipeline
- Event ditampung dalam memory buffer client-side (`maxQueueSize: 20`, `flushIntervalMs: 5000`).
- Menggunakan `Page Lifecycle API` (`freeze`, `hidden`) untuk memastikan event terakhir tidak hilang saat tab ditutup (*unload handling*).

---

## 6. Analogy & Diagram ASCII

Bayangkan eksperimentasi sebagai **Pintu Gerbang Tol Otomatis Pintar**:

```
[Pengendara Mobil (Pengguna)]
             |
             v
+-----------------------------+
|    Pintu Gerbang Tol (Edge) |
|   Scan Plat Nomor (User ID) |
+-----------------------------+
      /                     \
[Plat Ganjil]          [Plat Genap]
     |                      |
     v                      v
+------------+         +------------+
| Jalur A    |         | Jalur B    |
| (Jalan     |         | (Jalan     |
| Beton)     |         | Aspal)     |
+------------+         +------------+
      \                     /
       v                   v
+-------------------------------+
|  Kamera Sensor Kecepatan      | ---> [Server Rekam Data (OLAP)]
|  (Web Worker Telemetry Engine)|      Menganalisis: "Jalur mana yang
+-------------------------------+      membuat mobil berjalan lebih cepat?"
```

Jika evaluasi dilakukan secara tradisional (client-side), ini seperti menyuruh mobil masuk ke Jalur Beton, lalu 100 meter kemudian mobil mendadak dipaksa mundur dan diarahkan ke Jalur Aspal. Penumpang akan terguncang hebat (**Flicker / CLS**).  
Dengan arsitektur Edge, plat nomor dipindai di gerbang masuk utama, dan palang otomatis mengarahkan mobil ke jalur yang tepat sejak awal tanpa deselerasi.

---

## 7. Simple Example & Practical Example

### A. Simple Example: Deterministik MurmurHash3 Bucketing (Pure TypeScript)

Implementasi algoritma bucketing 32-bit integer deterministik untuk memastikan alokasi varian konsisten tanpa stateful database call:

```typescript
// utils/murmurhash3.ts
export function murmurhash3_32_gc(key: string, seed: number = 0): number {
  let remainder = key.length & 3;
  let bytes = key.length - remainder;
  let h1 = seed;
  const c1 = 0xcc9e2d51;
  const c2 = 0x1b873593;
  let i = 0;

  while (i < bytes) {
    let k1 =
      (key.charCodeAt(i) & 0xff) |
      ((key.charCodeAt(++i) & 0xff) << 8) |
      ((key.charCodeAt(++i) & 0xff) << 16) |
      ((key.charCodeAt(++i) & 0xff) << 24);
    ++i;

    k1 = Math.imul(k1, c1);
    k1 = (k1 << 15) | (k1 >>> 17);
    k1 = Math.imul(k1, c2);

    h1 ^= k1;
    h1 = (h1 << 13) | (h1 >>> 19);
    h1 = Math.imul(h1, 5) + 0xe6546b64;
  }

  let k1 = 0;
  switch (remainder) {
    case 3:
      k1 ^= (key.charCodeAt(i + 2) & 0xff) << 16;
    case 2:
      k1 ^= (key.charCodeAt(i + 1) & 0xff) << 8;
    case 1:
      k1 ^= key.charCodeAt(i) & 0xff;
      k1 = Math.imul(k1, c1);
      k1 = (k1 << 15) | (k1 >>> 17);
      k1 = Math.imul(k1, c2);
      h1 ^= k1;
  }

  h1 ^= key.length;
  h1 ^= h1 >>> 16;
  h1 = Math.imul(h1, 0x85ebca6b);
  h1 ^= h1 >>> 13;
  h1 = Math.imul(h1, 0xc2b2ae35);
  h1 ^= h1 >>> 16;

  return h1 >>> 0;
}

export function getVariantBucket(
  userId: string,
  experimentId: string,
  trafficAllocation: number = 100 // 0 to 100%
): number {
  const hashKey = `${experimentId}:${userId}`;
  const hash = murmurhash3_32_gc(hashKey, 42);
  const normalizedValue = hash % 100; // Value 0 - 99

  if (normalizedValue >= trafficAllocation) {
    return -1; // Excluded from experiment
  }
  return normalizedValue;
}
```

---

### B. Practical Example: Production Edge Middleware Experimentation & Web Worker Telemetry Ingestion

#### 1. Edge Middleware (Next.js Edge Runtime)
Menghitung varian sebelum rendering HTML, memasang context cookie, dan meneruskan state via header.

```typescript
// middleware.ts
import { NextRequest, NextResponse } from "next/server";
import { getVariantBucket } from "@/utils/murmurhash3";

interface ExperimentConfig {
  id: string;
  variants: Array<{ id: string; weight: number }>; // Weight cumulative: e.g. [{id: 'control', weight: 50}, {id: 'treatment', weight: 100}]
}

const ACTIVE_EXPERIMENTS: Record<string, ExperimentConfig> = {
  "exp_checkout_redesign_v2": {
    id: "exp_checkout_redesign_v2",
    variants: [
      { id: "control", weight: 50 },
      { id: "streamlined_v2", weight: 100 },
    ],
  },
};

export function middleware(req: NextRequest) {
  const res = NextResponse.next();
  let anonymousId = req.cookies.get("aid")?.value;

  if (!anonymousId) {
    anonymousId = crypto.randomUUID();
    res.cookies.set("aid", anonymousId, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      maxAge: 60 * 60 * 24 * 365, // 1 Year
    });
  }

  const assignedVariants: Record<string, string> = {};

  for (const [expId, config] of Object.entries(ACTIVE_EXPERIMENTS)) {
    const bucket = getVariantBucket(anonymousId, expId, 100);
    if (bucket !== -1) {
      let cumulative = 0;
      for (const variant of config.variants) {
        cumulative = variant.weight;
        if (bucket < cumulative) {
          assignedVariants[expId] = variant.id;
          break;
        }
      }
    }
  }

  // Pass variant mapping into downstream SSR context via headers
  const variantHeaderPayload = JSON.stringify(assignedVariants);
  res.headers.set("x-experiments-context", variantHeaderPayload);
  req.headers.set("x-experiments-context", variantHeaderPayload);

  return res;
}

export const config = {
  matcher: ["/checkout/:path*", "/pricing/:path*"],
};
```

#### 2. Worker-Thread Telemetry Engine (Web Worker Isolation)
Mencegah `JSON.stringify`, hashing, dan transmisi jaringan mengonsumsi frame budget (16.6ms) main-thread.

```typescript
// public/workers/analytics-worker.js
(() => {
  let queue = [];
  const FLUSH_INTERVAL_MS = 3000;
  const BATCH_SIZE_THRESHOLD = 15;
  const INGESTION_ENDPOINT = "/api/v1/telemetry";

  function flush() {
    if (queue.length === 0) return;

    const payload = JSON.stringify({
      sent_at: Date.now(),
      batch: queue,
    });

    // Reset buffer instantly
    queue = [];

    if (navigator.sendBeacon) {
      const blob = new Blob([payload], { type: "application/json" });
      const success = navigator.sendBeacon(INGESTION_ENDPOINT, blob);
      if (!success) {
        fallbackFetch(payload);
      }
    } else {
      fallbackFetch(payload);
    }
  }

  function fallbackFetch(payload) {
    fetch(INGESTION_ENDPOINT, {
      method: "POST",
      body: payload,
      headers: { "Content-Type": "application/json" },
      keepalive: true,
    }).catch((err) => {
      // Worker silent drop or write to IndexedDB in enterprise resiliency scenario
      console.error("[TelemetryWorker] Egress failed:", err);
    });
  }

  setInterval(flush, FLUSH_INTERVAL_MS);

  self.onmessage = (event) => {
    const { type, data } = event.data;
    if (type === "TRACK_EVENT") {
      queue.push(data);
      if (queue.length >= BATCH_SIZE_THRESHOLD) {
        flush();
      }
    } else if (type === "FORCE_FLUSH") {
      flush();
    }
  };
})();
```

#### 3. Client Facade SDK (Zero Overhead React Hook)

```typescript
// hooks/useExperimentTelemetry.ts
"use client";

import { useEffect, useRef } from "react";

interface TelemetryEvent {
  event_name: string;
  properties: Record<string, unknown>;
  timestamp: number;
}

export function useExperimentTelemetry(experimentId: string, currentVariant: string) {
  const workerRef = useRef<Worker | null>(null);

  useEffect(() => {
    // Spin-up worker safely in browser environment
    workerRef.current = new Worker("/workers/analytics-worker.js");

    // Track automatically when component mounts
    track("experiment_exposure", {
      experiment_id: experimentId,
      variant_id: currentVariant,
      url: window.location.href,
      referrer: document.referrer,
    });

    const handleVisibilityChange = () => {
      if (document.visibilityState === "hidden") {
        workerRef.current?.postMessage({ type: "FORCE_FLUSH" });
      }
    };

    window.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      window.removeEventListener("visibilitychange", handleVisibilityChange);
      workerRef.current?.terminate();
    };
  }, [experimentId, currentVariant]);

  const track = (eventName: string, props: Record<string, unknown> = {}) => {
    if (!workerRef.current) return;

    const payload: TelemetryEvent = {
      event_name: eventName,
      properties: {
        ...props,
        experiment_id: experimentId,
        variant_id: currentVariant,
      },
      timestamp: Date.now(),
    };

    workerRef.current.postMessage({
      type: "TRACK_EVENT",
      data: payload,
    });
  };

  return { track };
}
```

#### 4. Server-Rendered Component Mengonsumsi Varian

```typescript
// app/checkout/page.tsx
import { headers } from "next/headers";
import { CheckoutTreatment } from "@/components/checkout/Treatment";
import { CheckoutControl } from "@/components/checkout/Control";

export default async function CheckoutPage() {
  const headersList = await headers();
  const rawContext = headersList.get("x-experiments-context") || "{}";
  const experiments = JSON.parse(rawContext) as Record<string, string>;

  const variant = experiments["exp_checkout_redesign_v2"] ?? "control";

  return (
    <main className="container mx-auto p-4">
      {variant === "streamlined_v2" ? (
        <CheckoutTreatment variantId={variant} />
      ) : (
        <CheckoutControl variantId={variant} />
      )}
    </main>
  );
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario:
Platform Fintech Skala Regional (15 Juta Monthly Active Users) meluncurkan flow "One-Click Instant Loan Disbursal". Eksperimen dilakukan dengan membandingkan Flow Standar (3 langkah wizard) dengan Flow Cepat (1 langkah bottom-sheet modal).

### Insiden & Investigasi:
- **Gejala Awal:** Dashboard analitik konvensional menunjukkan varian baru (Flow Cepat) meningkatkan *drop-off* sebesar 35%. Namun, total nominal pinjaman yang cair tidak turun secara agregat.
- **Investigasi Sistem Tingkat Lanjut:**
  1. *Deteksi SRM (Sample Ratio Mismatch):* Pengujian chi-square ($\chi^2$) pada volume impresi menunjukkan distribusi Varian A (Control) = 1.050.210 dan Varian B (Treatment) = 740.120 ($p < 0.00001$). Terjadi SRM ekstrem. Rasio seharusnya 50:50.
  2. *Root Cause Analysis:* Varian B menggunakan komponen modern yang memicu *bundle lazy-loading* berukuran besar di koneksi 3G/Low-end device. Script timeout membatalkan rendering komponen sebelum event tracking impresi terkirim. Pengguna di jaringan lambat otomatis gagal merender varian dan mental ke error boundary tanpa tercatat di analitik.
  3. Ad-blocker berbasis DNS lokal memblokir endpoint vendor analitik SaaS pihak ketiga, khususnya di kalangan pengguna segmen tech-savvy/higher loan limits.

### Solusi Arsitektural Enterprise:
1. **Migrasi ke First-Party Reverse Proxy & Edge Injection:** Memindahkan pipeline telemetri ke endpoint domain internal (`api.fintech.com/t`), sehingga lolos dari blokir DNS level filter list (uBlock Origin, Pi-hole).
2. **Pre-fetching Asset di Level CDN:** Edge middleware menyisipkan HTTP header `Link: </bundles/treatment.js>; rel=preload; as=script` saat mendeteksi pengguna masuk ke Varian B, melenyapkan time-lag pemuatan bundle.
3. **Automated SRM Alerting Guardrail:** Memasang worker script di ClickHouse yang mengevaluasi $p$-value distribusi traffic setiap 10 menit. Jika $p < 0.001$, flag eksperimen otomatis di-rollback ke Control secara programmatic.

---

## 9. Trade-offs

| Aspek Arsitektur | Pilihan A: Client-Side Evaluation (SaaS SDK) | Pilihan B: Server/Edge Middleware Evaluation |
| :--- | :--- | :--- |
| **P99 Rendering Latency** | **Rendah pada Edge, Buruk pada Client:** HTML cepat dikirim, namun client mengalami blocking thread 50-120ms + layout flicker. | **Optimal & Konsisten:** Tambahan overhead 5-15ms di Edge Middleware, namun 0ms flicker dan 0 layout shift di client. |
| **Infrastruktur & Maintenance** | **Rendah:** Manajemen dashboard didelegasikan ke vendor (LaunchDarkly, Split, Optimizely). | **Tinggi:** Perlu merawat Edge Worker, Kafka clustering, Ingestion Gateway, dan database analitik (ClickHouse). |
| **Network Egress Cost** | **Tinggi (Finansial SaaS):** Vendor analitik menagih berbasis Monthly Tracked Users (MTU) atau Event Volume (sangat mahal pada >100M events). | **Rendah Finansial, Beban di Bandwidth:** Biaya komputasi Kafka & VM internal jauh lebih murah vs SaaS pricing tiers. |
| **Tingkat Akurasi Data** | **Rentan Bias (60-80%):** Kehilangan data signifikan karena pemblokiran browser modern (Brave Shields, Safari ITP, Adblock). | **Tinggi (>99%):** Menggunakan secure first-party HTTP cookies dan payload proxying internal. |

---

## 10. Common Mistakes & Troubleshooting

### Mistake 1: Hydration Mismatch Akibat Evaluasi Random di Komponen Client
```typescript
// FATAL ANTI-PATTERN:
export function BadComponent() {
  // Evaluasi Math.random() di browser menghasilkan tree yang berbeda dengan SSR!
  const variant = Math.random() > 0.5 ? 'variant_b' : 'variant_a';
  return <div>{variant}</div>; // Error: Text content does not match server-rendered HTML.
}
```
*Solusi:* Evaluasi wajib dilakukan di Server/Edge, lalu di-passing ke client component melalui Server Components props atau Edge-injected headers.

### Mistake 2: Missing Cleanup pada Visibility State saat Pengiriman Event
Menggunakan event `window.addEventListener('unload', ...)` untuk menembakkan telemetry beacon. Pada browser mobile modern (iOS Safari, Android Chrome), event `unload` dan `beforeunload` sering di-skip demi menghemat memori (*back-forward cache activation*).  
*Solusi:* Gunakan `visibilitychange` event listener dengan pengecekan `document.visibilityState === 'hidden'`.

### Mistake 3: Mengabaikan Sample Ratio Mismatch (SRM)
Melakukan kalkulasi konversi langsung saat proporsi traffic tidak seimbang secara statistik.
*Troubleshooting Rule:* Jika implementasi split adalah 50:50, jalankan uji Chi-Square Goodness-of-Fit:
$$\chi^2 = \sum \frac{(O_i - E_i)^2}{E_i}$$
Jika nilai $\chi^2 > 6.635$ ($p < 0.01$ untuk degree of freedom = 1), **batalkan kesimpulan eksperimen**. Jangan pernah mengambil keputusan bisnis dari eksperimen yang mengalami SRM.

---

## 11. Best Practices (Production Checklist)

- [ ] **Zero Layout Shift:** Tidak ada conditional injection elemen struktural UI secara async via `useEffect`. Seluruh branching dieksekusi di Edge Middleware atau Server Component.
- [ ] **First-Party Telemetry Domain:** Event endpoint dialihkan ke subdomain yang sama dengan web utama (misal: `metrics.example.com` atau `/api/t`).
- [ ] **Payload Sanitization (Strict Privacy):** Strip string berformat Email, NIK/SSN, Nomor Kartu Kredit menggunakan Regex masking engine di level Web Worker sebelum transmisi keluar.
- [ ] **Batching & Exponential Backoff:** Buffer telemetry memiliki toleransi offline (retrying dengan exponential backoff dan fallback ke `IndexedDB` jika terjadi status HTTP 5xx/429).
- [ ] **Automated SRM Detection:** Pipeline analitik memiliki background task berkala untuk menghitung chi-square test pada sampel aktual vs yang diekspektasikan.
- [ ] **Cache Segmentation:** Menggunakan header `Vary: x-experiments-context` jika CDN layer (Cloudflare/Akamai/Fastly) melakukan caching terhadap dynamic SSR pages.

---

## 12. Hands-on Practice

Buka terminal dan bangun direktori praktikum pada `hands-on/m02/`:

### Langkah 1: Inisialisasi Environment
```bash
mkdir -p hands-on/m02/experiment-engine
cd hands-on/m02/experiment-engine
npm init -y
npm install typescript @types/node tsx --save-dev
npx tsc --init
```

### Langkah 2: Bangun Script Validasi SRM Otomatis
Buat file `hands-on/m02/experiment-engine/srm-detector.ts` untuk memverifikasi integritas sampel eksperimen:

```typescript
// hands-on/m02/experiment-engine/srm-detector.ts

export interface VariantCount {
  variantId: string;
  observed: number;
  expectedRatio: number; // e.g. 0.5 for 50%
}

export function calculateChiSquareSRM(variants: VariantCount[]): {
  chiSquare: number;
  hasSRM: number; // 1 = Critical SRM, 0 = Normal
  pApprox: number;
} {
  const totalObserved = variants.reduce((acc, v) => acc + v.observed, 0);

  if (totalObserved === 0) {
    return { chiSquare: 0, hasSRM: 0, pApprox: 1.0 };
  }

  let chiSquare = 0;
  for (const variant of variants) {
    const expected = totalObserved * variant.expectedRatio;
    const diff = variant.observed - expected;
    chiSquare += (diff * diff) / expected;
  }

  // Pendekatan p-value untuk degree of freedom = 1 (df = k - 1, untuk 2 varian)
  // Nilai kritis untuk df = 1: p=0.01 -> chi2=6.635, p=0.001 -> chi2=10.828
  const hasSRM = chiSquare > 6.635 ? 1 : 0;
  
  // Aproksimasi eksponensial sederhana untuk reporting
  const pApprox = Math.exp(-chiSquare / 2);

  return {
    chiSquare: Number(chiSquare.toFixed(4)),
    hasSRM,
    pApprox: Number(pApprox.toFixed(8)),
  };
}

// Simulasi Kasus
const sampleHealthy: VariantCount[] = [
  { variantId: "control", observed: 50120, expectedRatio: 0.5 },
  { variantId: "treatment", observed: 49880, expectedRatio: 0.5 },
];

const sampleCorrupted: VariantCount[] = [
  { variantId: "control", observed: 52400, expectedRatio: 0.5 },
  { variantId: "treatment", observed: 47600, expectedRatio: 0.5 },
];

console.log("Healthy Test Result:", calculateChiSquareSRM(sampleHealthy));
console.log("Corrupted Test Result (SRM Alert):", calculateChiSquareSRM(sampleCorrupted));
```

### Langkah 3: Eksekusi Engine SRM
```bash
npx tsx hands-on/m02/experiment-engine/srm-detector.ts
```

Output yang diharapkan:
```text
Healthy Test Result: { chiSquare: 0.576, hasSRM: 0, pApprox: 0.74976077 }
Corrupted Test Result (SRM Alert): { chiSquare: 230.4, hasSRM: 1, pApprox: 0 }
```

---

## 13. Exercise

### Level Easy
Tuliskan fungsi TypeScript murni bernama `sanitizeTelemetryProps(props: Record<string, unknown>): Record<string, unknown>` yang memindai seluruh key-value pair secara rekursif dan menyamarkan (*masking*) value yang mengandung pola alamat email valid menjadi format `u***@domain.com`.

### Level Medium
Rancanglah sebuah stateful buffer class `TelemetryBuffer` di TypeScript yang:
1. Menampung event secara thread-safe di memory.
2. Memiliki batas maksimal `maxBatchSize = 50`.
3. Memiliki auto-flush interval setiap `1000ms`.
4. Jika dipanggil method `flush()`, class tersebut mengembalikan seluruh data tanpa kehilangan event baru yang masuk saat proses flush asynchronous sedang berlangsung.

### Level Hard
Implementasikan algoritma **CUPED (Controlled-experiment Using Pre-Experiment Data)** dalam TypeScript untuk mereduksi variansi metric konversi pengguna:
- Input: Dataset array berisi data user: `{ preMetric: number, postMetric: number }`.
- Output: Estimasi rata-rata metric baru yang telah disesuaikan ($\hat{Y}_{CUPED}$) dan kalkulasi reduksi variansinya dalam persentase:
$$\hat{Y}_{CUPED} = Y - \theta (X - \bar{X}), \quad \text{dimana } \theta = \frac{\text{Cov}(X, Y)}{\text{Var}(X)}$$

---

## 14. Challenge (Studi Kasus Kompleks)

**Konteks Sistem:**  
Anda adalah Staff Software Engineer di platform marketplace global. Perusahaan ingin meluncurkan algoritma sistem rekomendasi baru pada checkout funnel bernilai transaksi \$100M/bulan.

**Kondisi Lingkungan:**
1. Halaman web di-cache secara masif di CDN Edge PoP (Cloudflare) global dengan target *Cache Hit Ratio* > 85% untuk menjaga server origin tidak tumbang saat flash sale.
2. Algoritma rekomendasi bergantung pada profile user yang dinamis (kategori belanja favorit 24 jam terakhir).
3. Tim Product Management menuntut eksperimen dilakukan pada 3 varian berbeda (Control, Model-A, Model-B) dengan pembagian 34%:33%:33%.
4. Ad-blocker browser di negara-negara Eropa memblokir 35% telemetry tracking standar.

**Misi Arsitektur Anda:**
Rancang arsitektur implementasi teknis menyeluruh (spesifikasi dokumen teknis dan pseudocode/kode arsitektur) yang menjawab:
- Bagaimana menyajikan halaman HTML yang ter-cache di Cloudflare CDN Edge, namun tetap merender rekomendasi dinamis sesuai varian eksperimen tanpa layout shift?
- Bagaimana memastikan determinasi varian tetap stateless dan konsisten antar perangkat (Desktop ke Mobile) jika user beralih dari mode *anonymous* ke *logged-in* di tengah sesi?
- Bagaimana merancang jalur telemetry analitik yang 100% lolos ad-blocker serta menjamin data ingestion tidak pernah membebani latency database transaksional?

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Basic (5 Soal)
1. **Mengapa algoritma hashing non-kriptografis seperti MurmurHash3 lebih dipilih daripada SHA-256 untuk bucketing varian pada Edge Middleware?**
   - A. MurmurHash3 menghasilkan string hash yang jauh lebih panjang.
   - B. MurmurHash3 memiliki latensi komputasi sangat rendah (eksekusi CPU lebih cepat) dan distribusi uniform yang cukup merata.
   - C. SHA-256 tidak dapat dieksekusi di lingkungan JavaScript/Node.js.
   - D. SHA-256 selalu menghasilkan tabrakan hash (collision) pada string yang pendek.

2. **Apa yang dimaksud dengan Layout Shift (CLS) yang disebabkan oleh eksperimentasi client-side?**
   - A. Perubahan struktur DOM yang terjadi saat browser men-swap elemen default dengan elemen varian setelah fase parsing awal.
   - B. Kerusakan visual akibat browser gagal men-download file gambar berukuran besar.
   - C. Render ulang komponen React karena terjadi perubahan URL path secara native.
   - D. Perbedaan ukuran font pada dynamic text loading.

3. **Kapan waktu terbaik untuk mengirimkan batch telemetry saat pengguna meninggalkan aplikasi web?**
   - A. Di dalam blok method `componentWillUnmount`.
   - B. Saat event `window.onbeforeunload` terpanggil.
   - C. Saat `document.visibilityState` berubah menjadi `'hidden'`.
   - D. Menggunakan interval looping polling `setInterval` per 60 detik.

4. **Apa tujuan utama penambahan header `Vary: <header-name>` pada HTTP response SSR page yang membawa pengujian A/B?**
   - A. Mengompresi payload HTML menggunakan algoritma Brotli.
   - B. Menginstruksikan CDN cache layer untuk menyimpan salinan halaman yang terpisah berdasarkan nilai header eksperimen tersebut.
   - C. Memblokir serangan Cross-Site Scripting (XSS).
   - D. Mengubah response HTTP dari status 200 OK menjadi 304 Not Modified.

5. **Apa fungsi dari API `navigator.sendBeacon()` dibandingkan standar `fetch()` asinkron biasa?**
   - A. Menjamin pengiriman data HTTP POST kecil secara reliable di background browser bahkan setelah tab dokumen ditutup tanpa menahan proses unloading.
   - B. Mempercepat koneksi TCP handshake dengan memotong proses validasi sertifikat TLS.
   - C. Mengizinkan transfer file multi-gigabyte tanpa menggunakan alokasi memori RAM.
   - D. Mengenkripsi payload otomatis menggunakan public-key infrastructure client.

---

### Bagian B: Intermediate (5 Soal)
6. **Sebuah eksperimen di-setting dengan target alokasi 50% Control dan 50% Treatment. Setelah 1 minggu, terdata 100.000 traffic Control dan 85.000 traffic Treatment. Apa diagnosa teknis yang paling tepat?**
   - A. Eksperimen sukses besar; Treatment mengurangi traffic bounce secara signifikan.
   - B. Terjadi Sample Ratio Mismatch (SRM); varian Treatment kemungkinan memicu runtime crash, performance drop, atau drop network telemetry sebelum logging event.
   - C. Data valid, variansi tersebut lumrah terjadi dalam proses stokastik internet.
   - D. Algoritma hashing mengalami memory leak sehingga bucketing bergeser.

7. **Mengapa pemrosesan telemetry client-side sebaiknya didelegasikan ke dedicated Web Worker?**
   - A. Web Worker memiliki akses penuh langsung untuk memanipulasi elemen DOM secara instan.
   - B. Memindahkan serialization payload JSON (`JSON.stringify`) dan dispatch IO dari Main Thread untuk mencegah penurunan skor Interaction to Next Paint (INP).
   - C. Web Worker kebal terhadap network throttling browser.
   - D. Web Worker tidak membutuhkan alokasi memori heap browser.

8. **Bagaimana cara mencegah Layout Hydration Mismatch di React saat membaca data eksperimen di Client Component?**
   - A. Membungkus component menggunakan dynamic import `ssr: false` di seluruh halaman.
   - B. Menghitung varian via `localStorage` di dalam blok `useLayoutEffect`.
   - C. Menyuntikkan nilai varian dari Server Component via `props` atau Server Context yang bersumber dari Edge Middleware Headers.
   - D. Memaksa component melakukan reload native via `window.location.reload()`.

9. **Apa kegunaan teknik statistik CUPED (Controlled-experiment Using Pre-Experiment Data) dalam continuous experimentation?**
   - A. Menggandakan volume sample traffic pengguna secara artifisial tanpa menambah pengguna baru.
   - B. Menghilangkan kebutuhan menghitung standard deviation dari sampel data.
   - C. Mengurangi variansi pada metrik evaluasi dengan memanfaatkan historical pre-exposure data, mempercepat konvergensi signifikansi statistik (mempersingkat durasi tes).
   - D. Menghindari hukum GDPR saat melacak konversi data pengguna.

10. **Manakah format payload berikut yang paling optimal untuk telemetri high-throughput mobile app di koneksi lambat?**
    - A. Format XML dengan standard SOAP headers.
    - B. Batched and compressed Protocol Buffers (Protobuf) via binary transmission.
    - C. Plain JSON arrays dikirimkan satu per satu setiap ada interaksi klik.
    - D. URL-encoded form data yang disisipkan di Query Parameter URL gambar 1x1 GIF.

---

### Bagian C: Skenario Kasus Produksi (3 Soal)

11. **Skenario 1:**  
    Aplikasi e-commerce Anda meluncurkan A/B test pada alur Checkout. Varian Treatment menggunakan model form autocomplete baru. Dari dashboard analytics, p-value dari metrik conversion rate bernilai $0.002$ ($p < 0.05$, dinyatakan signifikan). Namun, automated test tool internal Anda menunjukkan bahwa `checkout_started` event tercatat:  
    - Control: 400.000  
    - Treatment: 380.000  
    *(Target alokasi konfigurasi sistem adalah 50:50)*.  
    **Tindakan engineering apa yang wajib diambil sebelum tim marketing merilis varian Treatment ke 100% user?**
    - A. Langsung deploy Varian Treatment karena p-value membuktikan hasil signifikan secara statistik.
    - B. Tahan deployment, tandai hasil eksperimen invalid, selidiki kegagalan teknis (SRM) yang menyebabkan 20.000 user Treatment hilang dari pipeline sebelum metrik conversion dihitung.
    - C. Normalisasi data secara manual dengan membagi conversion Treatment dengan faktor 0.95.
    - D. Perpanjang durasi eksperimen selama 3 bulan lagi tanpa mengubah kode apapun.

12. **Skenario 2:**  
    Perusahaan Anda mengalami masalah *data discrepancy*: 30% metrik page view yang terlacak di Google Analytics hilang jika dibandingkan dengan internal database transaction logs. Audit infrastruktur mengonfirmasi banyak user menggunakan browser seperti Brave atau ekstensi AdBlocker.  
    **Langkah arsitektur apa yang paling efektif melenyapkan gap diskrepansi tersebut tanpa melanggar privasi pengguna?**
    - A. Memaksa user mematikan AdBlocker menggunakan intrusive anti-adblock overlay modal.
    - B. Mengalihkan pengiriman telemetri melalui Edge Reverse Proxy internal (`/api/v1/collect`) menggunakan domain first-party yang sama dengan domain utama aplikasi, serta menonaktifkan pelacak vendor pihak ketiga.
    - C. Menyimpan log transaksi di client `localStorage` dan mengirimkannya via WebSocket tak terenkripsi.
    - D. Mengganti semua event tracking menjadi URL Query Parameter di tautan navigasi anchor tag (`<a href="...?click=true">`).

13. **Skenario 3:**  
    Eksperimen baru pada Edge Middleware menambahkan komputasi bucketing dan pembacaan Redis KV untuk 100 eksperimen aktif secara paralel. Akibatnya, P99 Time to First Byte (TTFB) melonjak dari 40ms menjadi 220ms, merusak skor Web Vitals.  
    **Optimasi arsitektur apa yang harus diimplementasikan?**
    - A. Pindahkan evaluasi eksperimen kembali ke client browser via React `useEffect`.
    - B. Muat seluruh manifest konfigurasi eksperimen aktif ke dalam In-Memory Cache di Edge instance (Edge Local Memory Cache) dan lakukan evaluasi offline murni via hashing tanpa dependensi distributed I/O network call ke Redis per request.
    - C. Hentikan seluruh program A/B testing perusahaan secara permanen.
    - D. Panggil Redis menggunakan synchronous blocking execution di origin server utama.

---

### Kunci Jawaban & Pembahasan Evaluasi

#### Bagian A: Basic
1. **B** — Algoritma non-kriptografis (MurmurHash3) didesain murni untuk speed dan distribusi seragam pada hash-table indexing, memakan resource CPU minimal dibanding fungsi kriptografis (SHA-256) yang berat.
2. **A** — CLS pada client-side A/B test terjadi ketika struktur layout awal digantikan elemen baru setelah file JS eksperimen selesai diunduh dan dieksekusi.
3. **C** — `visibilitychange` (state: `hidden`) adalah siklus hidup aplikasi yang paling konsisten dieksekusi pada browser desktop maupun mobile modern sebelum tab/aplikasi dihentikan.
4. **B** — Header `Vary: x-experiments-context` mencegah CDN memberikan cache HTML Varian A kepada pengguna yang seharusnya mendapatkan Varian B.
5. **A** — `sendBeacon` diatur langsung oleh browser process agar tetap berjalan di background secara non-blocking meskipun konteks dokumen window/tab telah dihancurkan (unloaded).

#### Bagian B: Intermediate
6. **B** — Rasio 100k vs 85k pada rasio target 50:50 menghasilkan deviasi ekstrem (Chi-Square >> 6.635). Ini indikasi kuat Sample Ratio Mismatch (SRM) yang disebabkan anomali teknis pada varian Treatment.
7. **B** — Proses komputasi berat seperti eksekusi JSON parsing, validasi skema, dan kompresi buffer telemetri jika dieksekusi di Main Thread akan memblokir rendering dan menaikkan nilai INP.
8. **C** — Membaca state varian dari Edge Middleware yang diteruskan via RSC props memastikan server HTML dan initial client bundle memiliki tree yang 100% identik sejak render pertama.
9. **C** — CUPED menggunakan data historis pengguna sebelum eksperimen berlangsung sebagai kovariat untuk mengurangi variansi metrik acak, sehingga ukuran sampel yang dibutuhkan lebih kecil dan durasi eksperimen lebih singkat.
10. **B** — Protocol Buffers adalah format serialisasi binary yang sangat ringkas dibanding JSON atau string plain text, menghemat kuota jaringan dan mempercepat serialisasi di koneksi buruk.

#### Bagian C: Skenario Kasus Produksi
11. **B** — Eksperimen yang terindikasi SRM menghasilkan bias seleksi (selection bias) mendasar. Signifikansi statistik ($p = 0.002$) menjadi tidak valid karena populasi kedua grup tidak lagi ekuivalen. Investigasi akar masalah wajib dilakukan.
12. **B** — Menggunakan domain first-party via Reverse Proxy internal membuat request analitik dianggap sebagai native communication internal aplikasi, sehingga tidak diblokir oleh daftar domain filter pihak ketiga (blocklist) bawaan ad-blocker.
13. **B** — Menghubungi database terdistribusi (seperti Redis) over-the-network pada setiap request di Edge Middleware merusak latensi network. Solusinya adalah menyimpan compiled state experiments di memory lokal Edge Worker dan mengevaluasinya secara statis via hashing.

---

## 16. Summary

Implementasi arsitektur continuous experimentation dan telemetry modern menuntut pergeseran paradigma dari *client-side reactive hacking* menuju **Edge-First System Architecture**:

1. **Deterministic Bucketing at the Edge:** Menghitung alokasi varian di layer CDN Edge via MurmurHash3 mengeliminasi Layout Shifts (CLS), mencegah hydration mismatch, dan menjaga integritas performa rendering SSR.
2. **Worker-Isolated Ingestion Pipeline:** Seluruh tracing telemetri harus diisolasi dari main-thread menggunakan Web Workers dan dikirimkan via non-blocking APIs (`sendBeacon`) melalui first-party reverse proxy endpoint.
3. **Statistical Rigor as an Engineering Guardrail:** Metrik bisnis tidak dapat dipercaya tanpa audit kesehatan sampel teknis. Pengecekan otomatis Sample Ratio Mismatch (SRM) via Chi-Square testing dan reduksi variansi (CUPED) wajib tertanam langsung di dalam analytic pipeline produksi.