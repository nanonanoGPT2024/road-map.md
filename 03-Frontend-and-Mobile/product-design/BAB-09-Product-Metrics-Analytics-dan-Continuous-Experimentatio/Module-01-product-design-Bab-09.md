# Bab 09 Module 01: Product Metrics, Analytics & Continuous Experimentation

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** Frontend & Mobile Engineering (Product-Driven Track)
*   **Kategori:** 03-Frontend-and-Mobile
*   **Topik Spesifik:** Product Metrics, Analytics & Continuous Experimentation
*   **Target Level:** Advanced to Staff Software Engineer / Lead Product Engineer
*   **Prasyarat Pengetahuan:**
    *   Arsitektur Frontend Modern (State Management, DOM Lifecycle, Single Page Applications / Server Components)
    *   Dasar-dasar Probabilitas dan Teori Statistik Terapan (Distribusi Normal, $p$-value, Hipotesis Nol)
    *   Jaringan & Browser Internals (Event Loop, Web Workers, Beacon API, HTTP Caching, Transport Security)
    *   TypeScript Tingkat Lanjut (Generics, Mapped Types, Nominal Typing)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1.  **Merancang dan Mengimplementasikan Telemetri Klien Skala Besar:** Mengembangkan instrumentasi analitik *type-safe* berbasis event streaming yang tahan terhadap degradasi jaringan, *ad-blocker*, dan *browser throttling*.
2.  **Membangun Engine Eksperimentasi Klien (A/B & Feature Flagging):** Membangun sistem evaluasi eksperimen berbasis hashing deterministik di sisi klien dengan overhead latensi mendekati 0ms ($O(1)$ lookup) serta resolusi payload dinamis.
3.  **Mengintegrasikan Metrik Produk dan Metrik Kinerja Teknis:** Menghubungkan Google Core Web Vitals (LCP, INP, CLS) dan *custom user timing metrics* dengan indikator bisnis utama (North Star Metric, Funnel Conversion, ARR, Retention).
4.  **Mencegah dan Menanggulangi Bias Statistik di Lapangan:** Mengidentifikasi dan memitigasi Sample Ratio Mismatch (SRM), *peeking problem*, dan efek Simpson (*Simpson's Paradox*) melalui instrumentasi data yang valid.
5.  **Menerapkan Keamanan dan Privasi Data Berstandar Industri:** Menerapkan teknik *differential privacy*, pseudonimisasi identitas pengguna, pembersihan PII (*Personally Identifiable Information*), serta kepatuhan ketat terhadap GDPR, CCPA, dan regulasi privasi global tanpa mengorbankan integritas data analitik.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Dari "Feature Shipping" Menuju "Causal Impact"

Rekayasa perangkat lunak modern menuntut transisi dari mentalitas penyelesaian tiket (*velocity trap*) menuju validasi dampak kausal (*causal impact validation*). Setiap baris kode antarmuka pengguna bukanlah produk akhir, melainkan sebuah **hipotesis bisnis terukur**.

```
Mentalitas Tradisional:
[Desain UI] ---> [Implementasi Kode] ---> [Deployment] ---> (Selesai / Menganggap Fitur Berhasil)

Mentalitas Eksperimentasi & Data-Driven:
[Hipotesis Masalah] ---> [Desain Eksperimen] ---> [Instrumentasi Telemetri]
         ^                                                  |
         |                                                  v
[Iterasi / Rollback] <--- [Evaluasi Metrik & Kausalitas] <--- [A/B Testing]
```

### Triad Keseimbangan Metrik

Dalam merancang telemetri klien, seorang Staff Engineer harus selalu memandang arsitektur melalui tiga pilar yang saling terikat erat:

1.  **Metrik Bisnis (Primary/Success Metrics):** Mengukur nilai ekonomi langsung (misalnya: *Checkout Conversion Rate*, *Average Order Value*, *30-Day Retention*).
2.  **Metrik Penjaga (Guardrail/Health Metrics):** Memastikan bahwa peningkatan metrik bisnis tidak mengorbankan stabilitas jangka panjang. Terdiri dari:
    *   *System Health:* Crash-free user rate, API error rates, battery consumption.
    *   *Performance:* Core Web Vitals (INP < 200ms, LCP < 2.5s).
    *   *UX Integrity:* Unsubscribe rate, support ticket volume, rage click counts.
3.  **Metrik Pendorong (Input/Driver Metrics):** Tindakan spesifik dalam kontrol tim yang memprediksi metrik primer (misalnya: *Search query submission frequency*, *Time to first search result interaction*).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Arsitektur telemetri dan eksperimentasi modern di sisi klien harus memisahkan jalur eksekusi UI thread utama dari proses serialisasi, penyimpanan sementara, dan pengiriman jaringan.

```
+-------------------------------------------------------------------------------------------------------+
| BROWSER / CLIENT ENVIRONMENT                                                                          |
|                                                                                                       |
|  [ User Interactions ]       [ Application State ]         [ Browser Observer APIs ]                  |
|    (Click, Scroll, Inputs)     (Routing, Redux/Zustand)     (PerformanceObserver, IntersectionObs)   |
|            |                              |                                |                          |
|            +------------------------------+--------------------------------+                          |
|                                           |                                                           |
|                                           v                                                           |
|                       +---------------------------------------+                                       |
|                       |  Type-Safe Tracking Pipeline Gateway  |                                       |
|                       +---------------------------------------+                                       |
|                                           |                                                           |
|               +---------------------------+---------------------------+                               |
|               | Data Enrichment & Sanitization Engine                 |                               |
|               |  - User Identity (Anon Hash)                          |                               |
|               |  - Context Injector (OS, Device, App Version)         |                               |
|               |  - PII Masking & Payload Verification                  |                               |
|               +-------------------------------------------------------+                               |
|                                           |                                                           |
|                                           v                                                           |
|                       +---------------------------------------+                                       |
|                       | Continuous Experimentation Engine     |                                       |
|                       |  - Deterministic MurmurHash3 Layer    |                                       |
|                       |  - Layer/Bucketing/Override Rules     |                                       |
|                       +---------------------------------------+                                       |
|                                           |                                                           |
|                                           v                                                           |
|                       +---------------------------------------+                                       |
|                       | Buffer Manager (IndexedDB / Memory)   |                                       |
|                       |  - Ring Buffer Flush Strategy         |                                       |
|                       |  - Offline-first Retry Circuit Breaker|                                       |
|                       +---------------------------------------+                                       |
|                                           |                                                           |
|                 +-------------------------+-------------------------+                                 |
|                 |                                                   |                                 |
|                 v (Batch Flush / Idle)                              v (Page Dismissal / Emergency)   |
|     +-------------------------+                         +-------------------------+                   |
|     | Web Worker Dispatcher   |                         | Navigator.sendBeacon()  |                   |
|     | (Fetch API via Worker)  |                         | (Zero-blocking Exit)    |                   |
|     +-------------------------+                         +-------------------------+                   |
|                 |                                                   |                                 |
+-----------------|---------------------------------------------------|---------------------------------+
                  |                                                   |
                  +-------------------------+-------------------------+
                                            |
                                            | HTTPS POST (JSON / Protobuf Payload)
                                            v
+-------------------------------------------------------------------------------------------------------+
| CLOUD TELEMETRY & EXPERIMENTATION PLATFORM                                                             |
|                                                                                                       |
|     +----------------------------------+                                                              |
|     | Edge Ingestion Proxy / CDN       |                                                              |
|     +----------------------------------+                                                              |
|                       |                                                                               |
|                       v                                                                               |
|     +----------------------------------+          +---------------------------------------------+     |
|     | Event Bus (Kafka / AWS Kinesis)  | -------> | Real-Time Metrics Validator (SRM Detection) |     |
|     +----------------------------------+          +---------------------------------------------+     |
|                       |                                                                               |
|                       v                                                                               |
|     +----------------------------------+          +---------------------------------------------+     |
|     | Data Lake & Columnar Storage     | -------> | Continuous A/B Testing Engine               |     |
|     | (Snowflake, ClickHouse, BigQuery)|          | (Bayesian / Frequentist Inference Engine)   |     |
|     +----------------------------------+          +---------------------------------------------+     |
+-------------------------------------------------------------------------------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. The Experiment Allocation Mechanism (Hashing Deterministik)

Ketika eksperimen berjalan di sisi klien tanpa latensi jaringan (*zero-network overhead evaluation*), sistem harus menentukan varian pengguna secara deterministik. Mekanisme internal berakar pada fungsi hash deterministik uniform (seperti MurmurHash3):

$$Bucket = \left( \frac{\text{MurmurHash3}(\text{UserID} + \text{ExperimentSalt})}{2^{32} - 1} \right) \times 100$$

*   **Identitas Klien:** ID Pengguna (UUID) atau Anonymous Visitor ID yang disimpan pada *first-party HTTP-only cookie* atau *IndexedDB*.
*   **Salt / Experiment Key:** String unik untuk eksperimen tertentu guna menghindari korelasi antar-eksperimen (*experiment bias coupling*).
*   **Layering:** Partisi pengguna ke dalam lapisan ortogonal (*Orthogonal Layering System*), memastikan pengguna yang berada di Variant A pada Experiment 1 tersebar merata ($50:50$) di seluruh varian pada Experiment 2.

### 2. High-Throughput Client Telemetry Pipeline

Pengiriman telemetri tidak boleh bersaing memperebutkan alokasi sumber daya dengan rendering antarmuka pengguna:

```
[Event Triggered] 
       │
       ▼
[Enrichment Layer] ────────► Tambahkan timestamp, session_id, network_type, platform
       │
       ▼
[Schema Validation] ───────► Validasi tipe payload & sensor PII
       │
       ▼
[In-Memory Ring Buffer] ───► Simpan event ke buffer array lokal
       │
       ├───► Kondisi 1: Ukuran buffer >= THRESHOLD (misal: 10 events)
       ├───► Kondisi 2: Durasi buffer >= FLUSH_INTERVAL (misal: 5000 ms)
       ├───► Kondisi 3: Browser mengalami idle (requestIdleCallback)
       └───► Kondisi 4: Visibilitas halaman berubah (visibilitychange -> hidden)
       │
       ▼
[Dispatch Engine] ─────────► Pilih transport: Worker Fetch atau sendBeacon
```

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Dasar Statistik Pengujian Hipotesis Produk

#### 1. Frequentist vs. Bayesian Inference

*   **Pendekatan Frequentist:**
    *   Menguji Hipotesis Nol ($H_0$: Tidak ada perbedaan antara Varian A dan B) melawan Hipotesis Alternatif ($H_1$).
    *   Tingkat Signifikansi ($\alpha$): Peluang terjadinya Kesalahan Tipe I (*False Positive*), standar industri diatur pada $\alpha = 0.05$.
    *   Kekuatan Statistik ($1 - \beta$): Peluang mendeteksi efek riil jika memang ada, standar industri diatur pada $0.80$ atau $0.90$ (meminimalkan Kesalahan Tipe II / *False Negative*).
    *   Ukuran Sampel Minimum ($N$) per varian dapat dihitung menggunakan rumus formula standard deviation dan Minimum Detectable Effect (MDE):
      
      $$N = \frac{2 \cdot \left( Z_{\alpha/2} + Z_{\beta} \right)^2 \cdot \sigma^2}{\Delta^2}$$
      
      Di mana $\Delta$ adalah MDE, dan $\sigma^2$ adalah varians metrik.

*   **Pendekatan Bayesian:**
    *   Tidak menggunakan $p$-value kaku.
    *   Menghitung distribusi probabilitas aktual dari suatu efek berdasarkan prior knowledge:
      
      $$P(\theta \mid D) = \frac{P(D \mid \theta) P(\theta)}{P(D)}$$
      
    *   Menghitung parameter seperti *Probability to be Best* dan *Expected Loss*, mengurangi risiko salah tafsir bagi pengambil keputusan produk.

#### 2. The Peeking Problem & Data-Dredging Bias

Kesalahan paling umum dalam eksekusi eksperimentasi produk adalah **peeking problem** (memantau $p$-value setiap hari dan menghentikan pengujian segera setelah nilai $p < 0.05$). 

Jika Anda mengevaluasi eksperimen Frequentist secara kontinu tanpa penyesuaian matematika, *False Positive Rate* riil meningkat secara dramatis:

$$\alpha_{\text{riil}} \approx 1 - (1 - \alpha)^k$$

*(di mana $k$ adalah jumlah pengecekan data).* Satu pengujian yang dipantau 10 kali dapat memiliki $\alpha_{\text{riil}} > 30\%$, bukan $5\%$. Untuk mitigasi, tim engineer harus menggunakan teknik **Sequential Testing** (seperti *Always Valid p-values* berbasis mSPRT / *mixture Sequential Probability Ratio Test*).

#### 3. Sample Ratio Mismatch (SRM)

SRM terjadi ketika rasio sampel aktual antara grup kontrol dan perlakuan menyimpang secara signifikan dari rasio yang dirancang. Misal alokasi $50:50$, namun data yang masuk $48,500$ vs $51,500$.

*   **Uji Chi-Square Goodness-of-Fit:**
    
    $$\chi^2 = \sum \frac{(O_i - E_i)^2}{E_i}$$
    
*   Jika $p$-value dari uji Chi-Square $< 0.001$, data eksperimen **batal demi integritas (*invalidated*)**. Penyebab SRM di frontend sering kali melibatkan:
    1.  Varian tertentu memicu crash/white-screen sebelum event eksposur dikirim.
    2.  Varian tertentu memiliki performa payload JavaScript yang jauh lebih lambat, memicu *bounce* sebelum SDK telemetri selesai diinisialisasi.
    3.  Caching browser yang agresif pada aset varian tertentu.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah fondasi *type-safe* Analytics Tracker dan Experiment Allocation Engine murni (vanilla TypeScript) yang mengimplementasikan MurmurHash3 deterministik dan event buffering.

```typescript
// File: TelemetryCore.ts

/**
 * 1. Implementasi MurmurHash3 (32-bit yield) untuk alokasi deterministik
 */
export function murmurHash3_x86_32(key: string, seed: number = 0): number {
  let h1 = seed >>> 0;
  const c1 = 0xcc9e2d51;
  const c2 = 0x1b873593;
  const remainder = key.length & 3;
  const bytes = key.length - remainder;

  for (let i = 0; i < bytes; i += 4) {
    let k1 =
      (key.charCodeAt(i) & 0xff) |
      ((key.charCodeAt(i + 1) & 0xff) << 8) |
      ((key.charCodeAt(i + 2) & 0xff) << 16) |
      ((key.charCodeAt(i + 3) & 0xff) << 24);

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
      k1 ^= (key.charCodeAt(bytes + 2) & 0xff) << 16;
    case 2:
      k1 ^= (key.charCodeAt(bytes + 1) & 0xff) << 8;
    case 1:
      k1 ^= key.charCodeAt(bytes) & 0xff;
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

/**
 * 2. Type Schema untuk Event Analytics
 */
export interface BaseEventPayload {
  readonly timestamp: number;
  readonly sessionId: string;
  readonly userId: string;
}

export interface ExposureEventPayload extends BaseEventPayload {
  readonly experimentId: string;
  readonly variationId: string;
}

export interface MetricEventPayload extends BaseEventPayload {
  readonly metricName: string;
  readonly metricValue: number;
  readonly metadata?: Record<string, string | number | boolean>;
}

export type ProductTelemetryEvent =
  | { type: 'EXPOSURE'; payload: ExposureEventPayload }
  | { type: 'METRIC'; payload: MetricEventPayload };

/**
 * 3. Configuration & Experiment Evaluator
 */
export interface ExperimentConfig {
  id: string;
  salt: string;
  variants: { id: string; weight: number }[]; // weights harus total 100
}

export class ExperimentEngine {
  public static evaluate(userId: string, experiment: ExperimentConfig): string {
    const combinedKey = `${userId}:${experiment.salt}:${experiment.id}`;
    const hash = murmurHash3_x86_32(combinedKey);
    const normalizedBucket = (hash % 10000) / 100; // 0.00 s/d 99.99

    let cumulativeWeight = 0;
    for (const variant of experiment.variants) {
      cumulativeWeight += variant.weight;
      if (normalizedBucket < cumulativeWeight) {
        return variant.id;
      }
    }
    return experiment.variants[0].id;
  }
}

/**
 * 4. Resilient Telemetry Client Buffer
 */
export class TelemetryQueue {
  private queue: ProductTelemetryEvent[] = [];
  private readonly flushThreshold: number = 10;
  private readonly flushIntervalMs: number = 5000;
  private timer: number | null = null;
  private readonly endpoint: string;

  constructor(endpoint: string) {
    this.endpoint = endpoint;
    this.setupLifeCycleListeners();
    this.startPeriodicFlush();
  }

  public enqueue(event: ProductTelemetryEvent): void {
    this.queue.push(event);
    if (this.queue.length >= this.flushThreshold) {
      this.flush();
    }
  }

  private startPeriodicFlush(): void {
    this.timer = window.setInterval(() => {
      if (this.queue.length > 0) {
        this.flush();
      }
    }, this.flushIntervalMs);
  }

  public flush(isEmergency: boolean = false): void {
    if (this.queue.length === 0) return;

    const payload = JSON.stringify(this.queue);
    this.queue = [];

    if (isEmergency && typeof navigator !== 'undefined' && navigator.sendBeacon) {
      const blob = new Blob([payload], { type: 'application/json' });
      const success = navigator.sendBeacon(this.endpoint, blob);
      if (!success) {
        // Fallback synchronous fetch via keepalive jika beacon penuh
        fetch(this.endpoint, { method: 'POST', body: payload, keepalive: true }).catch(() => {});
      }
      return;
    }

    // Standard Non-Blocking Transport
    fetch(this.endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: payload,
    }).catch((err) => {
      console.error('[TelemetryQueue] Failed to dispatch analytics payload:', err);
      // Pada sistem production, requeue atau simpan ke IndexedDB
    });
  }

  private setupLifeCycleListeners(): void {
    if (typeof window === 'undefined') return;

    window.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') {
        this.flush(true);
      }
    });

    window.addEventListener('pagehide', () => {
      this.flush(true);
    });
  }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis Blok MurmurHash3 (`murmurHash3_x86_32`)
*   **Baris 7–29:** Operator `>>> 0` memaksa angka menjadi unsigned integer 32-bit dalam JavaScript V8 Engine. Algoritma membaca string per blok 4 karakter (4 byte), mengalikan dengan konstanta prima biner (`0xcc9e2d51` dan `0x1b873593`) menggunakan `Math.imul` untuk mencegah hilangnya presisi angka 64-bit float JavaScript.
*   **Baris 31–43:** Penanganan sisa (*tail handling*) memproses byte string yang tersisa jika panjang string bukan kelipatan 4.
*   **Baris 45–53:** Tahap *avalanche mixer* akhir. Memastikan perubahan satu bit pada input string menyebabkan perubahan rata-rata 50% dari bit-bit hash output. Ini esensial agar variasi penamaan ID pengguna tidak menyebabkan clustering data bucket.

### Analisis Evaluasi Eksperimen (`ExperimentEngine.evaluate`)
*   **Baris 82:** `combinedKey = ${userId}:${experiment.salt}:${experiment.id}`. Penggabungan `salt` sangat krusial. Jika dua pengujian berbeda mengevaluasi pengguna yang sama tanpa salt unik, kedua eksperimen akan selalu mengalokasikan pengguna ke varian yang identik (*correlation bias*).
*   **Baris 84:** `(hash % 10000) / 100` memetakan hash 32-bit (0 hingga 4,294,967,295) ke spektrum desimal kontinu 0.00 hingga 99.99 dengan presisi 2 digit desimal.
*   **Baris 86–92:** Iterasi kumulatif interval probabilistik. Jika varian A memiliki bobot 30 dan varian B memiliki bobot 70, nilai di bawah 30 dialokasikan ke A, dan nilai 30 ke atas masuk ke B.

### Analisis Telemetry Buffer (`TelemetryQueue`)
*   **Baris 129–140:** Deteksi metode keluar darurat (*emergency flush*). Menggunakan `navigator.sendBeacon` yang mengirimkan data via proses latar belakang browser independen dari rendering thread halaman. Ini menjamin pengiriman analitik saat tab browser ditutup secara tiba-tiba tanpa membekukan thread utama browser.
*   **Baris 156–166:** Event listener `visibilitychange` dan `pagehide`. Standar modern W3C merekomendasikan `visibilityState === 'hidden'` daripada event `unload` yang sudah usang dan sering dibatalkan oleh peramban modern berbasis Chromium dan WebKit.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: Arsitektur Checkout E-Commerce Global Skala Enterprise

*   **Entitas Bisnis:** Platform E-Commerce Global dengan skala 45 juta Active Users harian.
*   **Masalah:**
    Tim produk mendesain ulang alur checkout dari *Multi-Step Wizard* menjadi *One-Page Interactive Checkout*. Peluncuran langsung (*direct release*) sangat berisiko: penurunan 0.5% pada alur konversi berarti kerugian jutaan dolar per jam.
    
    Tim engineering merilis pengujian A/B 50:50. Namun, setelah 48 jam berjalan, sistem telemetri mendeteksi anomali parah:
    1.  Rasio sampel menunjukkan Varian A (Lama) = 52.8%, Varian B (Baru) = 47.2%. Uji Chi-Square menghasilkan $p < 10^{-12}$, membuktikan adanya **Sample Ratio Mismatch (SRM)** ekstrem.
    2.  Metrik konversi pembayaran checkout pada Varian B terlihat anjlok sebesar 4.2%.
    
*   **Investigasi Akar Masalah (Root Cause Analysis):**
    *   Varian B memuat skrip pihak ketiga (pembayaran baru) yang memblokir rendering utama selama 400ms di perangkat mobile low-end.
    *   Pengguna dengan jaringan 3G/4G lambat mengalami crash/freeze dan menutup tab *sebelum* skrip pelacakan exposure SDK standar dieksekusi.
    *   Akibatnya, pengguna yang mentalitas belanjanya paling rendah (low-end mobile) tereksklusi dari metrik Varian B, merusak integritas komparasi secara fatal dan membengkokkan data konversi.

*   **Solusi Rekayasa:**
    1.  Memindahkan alokasi eksperimen ke *Edge Interceptor* (Cloudflare Workers / Next.js Middleware) atau mengeksekusinya secara deterministik synchronous *in-memory* di baris pertama HTML head, mencatat event *exposure* sebelum rendering komponen berat dilakukan.
    2.  Menerapkan pelacakan otomatis metrik INP (*Interaction to Next Paint*) dan Long Animation Frames (LoAF) sebagai *guardrail metrics* yang secara otomatis men-trigger circuit breaker rollback jika ambang batas terlampaui.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi Production-Grade dari Experimentation Framework dan Analytics Manager yang mengintegrasikan Core Web Vitals, deteksi anomali SRM, dan pelacakan berbasis React custom hooks & TypeScript.

```typescript
// File: src/analytics/ProductionAnalyticsSystem.ts

import { onCLS, onINP, onLCP, Metric } from 'web-vitals';

// ----------------------------------------------------
// 1. Tipe Data & Skema Kontrak Telemetri Terstruktur
// ----------------------------------------------------

export interface AnalyticsContext {
  userId: string;
  sessionId: string;
  locale: string;
  networkEffectiveType?: string;
}

export type EventType = 'EXPERIMENT_IMPRESSION' | 'CONVERSION' | 'WEB_VITAL' | 'USER_ACTION';

export interface Envelope<T> {
  eventId: string;
  eventType: EventType;
  context: AnalyticsContext;
  payload: T;
  sentAt: number;
}

export interface ExperimentImpressionPayload {
  experimentId: string;
  variationId: string;
  layerId: string;
}

export interface WebVitalPayload {
  name: 'CLS' | 'INP' | 'LCP';
  value: number;
  rating: 'good' | 'needs-improvement' | 'poor';
  delta: number;
  navigationType: string;
}

// ----------------------------------------------------
// 2. High-Performance Telemetry Dispatcher Engine
// ----------------------------------------------------

export class ResilientAnalyticsDispatcher {
  private static instance: ResilientAnalyticsDispatcher;
  private queue: Envelope<unknown>[] = [];
  private context: AnalyticsContext;
  private readonly endpoint: string;
  private isProcessing: boolean = false;

  private constructor(endpoint: string, initialContext: AnalyticsContext) {
    this.endpoint = endpoint;
    this.context = initialContext;
    this.bindBrowserLifecycle();
    this.initPerformanceTracking();
  }

  public static initialize(endpoint: string, context: AnalyticsContext): ResilientAnalyticsDispatcher {
    if (!ResilientAnalyticsDispatcher.instance) {
      ResilientAnalyticsDispatcher.instance = new ResilientAnalyticsDispatcher(endpoint, context);
    }
    return ResilientAnalyticsDispatcher.instance;
  }

  public static getInstance(): ResilientAnalyticsDispatcher {
    if (!ResilientAnalyticsDispatcher.instance) {
      throw new Error('Analytics Dispatcher must be initialized prior to access.');
    }
    return ResilientAnalyticsDispatcher.instance;
  }

  public updateContext(partialContext: Partial<AnalyticsContext>): void {
    this.context = { ...this.context, ...partialContext };
  }

  public track<T>(eventType: EventType, payload: T): void {
    const envelope: Envelope<T> = {
      eventId: crypto.randomUUID(),
      eventType,
      context: {
        ...this.context,
        networkEffectiveType: (navigator as any)?.connection?.effectiveType || 'unknown',
      },
      payload,
      sentAt: Date.now(),
    };

    this.queue.push(envelope);

    if (this.queue.length >= 5) {
      this.flushBatch();
    }
  }

  private initPerformanceTracking(): void {
    const handleMetric = (metric: Metric) => {
      this.track<WebVitalPayload>('WEB_VITAL', {
        name: metric.name as WebVitalPayload['name'],
        value: metric.value,
        rating: metric.rating,
        delta: metric.delta,
        navigationType: metric.navigationType,
      });
    };

    onCLS(handleMetric);
    onINP(handleMetric);
    onLCP(handleMetric);
  }

  public async flushBatch(): Promise<void> {
    if (this.queue.length === 0 || this.isProcessing) return;

    this.isProcessing = true;
    const itemsToSend = [...this.queue];
    this.queue = [];

    try {
      const response = await fetch(this.endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(itemsToSend),
      });

      if (!response.ok) {
        throw new Error(`Analytics server responded with HTTP status ${response.status}`);
      }
    } catch (error) {
      console.warn('[AnalyticsDispatcher] Network failure, requeuing elements:', error);
      // Re-insert items at the start of queue
      this.queue = [...itemsToSend, ...this.queue];
    } finally {
      this.isProcessing = false;
    }
  }

  private bindBrowserLifecycle(): void {
    if (typeof window === 'undefined') return;

    const handleExit = () => {
      if (this.queue.length === 0) return;
      const payload = JSON.stringify(this.queue);
      this.queue = [];

      if (navigator.sendBeacon) {
        const blob = new Blob([payload], { type: 'application/json' });
        navigator.sendBeacon(this.endpoint, blob);
      } else {
        fetch(this.endpoint, {
          method: 'POST',
          body: payload,
          keepalive: true,
          headers: { 'Content-Type': 'application/json' },
        }).catch(() => {});
      }
    };

    window.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') {
        handleExit();
      }
    });

    window.addEventListener('pagehide', handleExit);
  }
}

// ----------------------------------------------------
// 3. Mathematical SRM (Sample Ratio Mismatch) Checker
// ----------------------------------------------------

export class StatisticalIntegrity {
  /**
   * Menghitung nilai Chi-Square Goodness-of-Fit untuk mengidentifikasi Sample Ratio Mismatch (SRM)
   */
  public static calculateSRM(observed: number[], expectedRatio: number[]): { pValue: number; hasSRM: boolean } {
    const totalObserved = observed.reduce((a, b) => a + b, 0);
    const totalRatio = expectedRatio.reduce((a, b) => a + b, 0);
    
    let chiSquare = 0;
    for (let i = 0; i < observed.length; i++) {
      const expected = (expectedRatio[i] / totalRatio) * totalObserved;
      chiSquare += Math.pow(observed[i] - expected, 2) / expected;
    }

    // Pendekatan p-value 1 Degree of Freedom (df = k - 1)
    const pValue = this.chiSquareCdfDof1(chiSquare);
    return {
      pValue,
      hasSRM: pValue < 0.001, // Threshold standar industri
    };
  }

  private static chiSquareCdfDof1(x: number): number {
    if (x <= 0) return 1.0;
    // Nilai p-value komplemen berbasis complementary error function erfc(sqrt(x / 2))
    const s = Math.sqrt(x / 2);
    return this.erfc(s);
  }

  private static erfc(x: number): number {
    // Chebyshev approximations untuk complementary error function
    const t = 1.0 / (1.0 + 0.5 * Math.abs(x));
    const tau =
      t *
      Math.exp(
        -x * x -
          1.26551223 +
          t *
            (1.00002368 +
              t *
                (0.37409196 +
                  t *
                    (0.09678418 +
                      t *
                        (-0.18628806 +
                          t *
                            (0.27886807 +
                              t *
                                (-1.13520398 +
                                  t *
                                    (1.48851587 +
                                      t * (-0.82215223 + t * 0.17087277))))))))
      );
    return x >= 0 ? tau : 2.0 - tau;
  }
}

// ----------------------------------------------------
// 4. Production React Custom Integration Layer
// ----------------------------------------------------

import React, { createContext, useContext, useEffect, useMemo, useRef } from 'react';
import { murmurHash3_x86_32 } from './TelemetryCore';

interface ExperimentContextValue {
  userId: string;
  activeOverrides?: Record<string, string>;
}

const ExperimentReactContext = createContext<ExperimentContextValue | null>(null);

export const ExperimentProvider: React.FC<{
  userId: string;
  overrides?: Record<string, string>;
  children: React.ReactNode;
}> = ({ userId, overrides, children }) => {
  const value = useMemo(() => ({ userId, active