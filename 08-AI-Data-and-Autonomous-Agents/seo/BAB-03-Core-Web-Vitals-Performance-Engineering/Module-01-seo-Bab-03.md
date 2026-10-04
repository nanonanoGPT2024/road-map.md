# Bab 03: Core Web Vitals & Performance Engineering
**Module 01: Advanced Runtime Performance, Modern Web Vitals (LCP, INP, CLS), and Bot Execution Budget**

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Principal Engineer dan Technical SEO Specialist diharapkan mampu:

1. **Menganalisis dan Membedah Siklus Hidup Rendering Engine Chromium:** Memahami secara mendalam interaksi antara Main Thread, Compositor Thread, dan Raster Thread saat mengeksekusi Core Web Vitals (CWV).
2. **Mengkuantifikasi Metrik LCP, INP, dan CLS pada Level Arsitektur:** Mengidentifikasi akar penyebab degradasi metrik hingga ke tingkat *sub-millisecond resource contention*, *Long Animation Frames (LoAF)*, dan *layout instability attribution*.
3. **Membangun Pipeline Telemetri Real User Monitoring (RUM):** Mengembangkan sistem ingest data performa real-time berbasis browser API menggunakan TypeScript dan backend telemetri berperforma tinggi.
4. **Mengoptimalkan Bot-Specific Rendering Budget:** Menganalisis bagaimana Web Rendering Service (WRS) Googlebot memproses resource rendering, mengeliminasi risiko *crawl budget starvation* akibat eksekusi JavaScript yang tidak efisien.
5. **Mengimplementasikan Teknik Remediasi Lanjutan:** Menerapkan *speculative loading*, *scheduler-based task chunking*, prioritas fetch deterministik, dan *zero-layout-shift hydration* pada arsitektur web modern (Next.js/Nuxt/Astro).

---

### 2. Concept Overview

Core Web Vitals bukan sekadar kumpulan angka acak Lighthouse; CWV adalah representasi matematis dari persepsi pengguna terhadap kecepatan, responsivitas, dan stabilitas visual halaman web yang divalidasi oleh *Chrome User Experience Report (CrUX)* pada persentil ke-75 (p75).

```
+---------------------------------------------------------------------------------------+
|                               CRITICAL RENDERING PATH                                 |
+---------------------------------------------------------------------------------------+
|  Network Phase   |               Main Thread Execution              | Compositor/GPU  |
|  (TTFB + Fetch)  |  (Parse HTML -> Build DOM -> Style -> Layout)    | (Paint -> Comp) |
+------------------+--------------------------------------------------+-----------------+
       |                                      |                                |
   [  TTFB  ]                                 |                                |
       |                                      |                                |
       +-------------> [      LCP Resource Load / Element Render     ]-------->|
                                              |
                                      [  INP Latency  ] (Input -> Processing -> Presentation)
                                              |
                                     [ CLS Instability ] (Node Shift Distance * Impact)
```

#### Mental Model Metrik Inti:

1. **Largest Contentful Paint (LCP):**
   $$LCP = T_{TTFB} + T_{ResourceLoadDelay} + T_{ResourceLoadDuration} + T_{ElementRenderDelay}$$
   Mengukur waktu hingga elemen visual terbesar di *viewport* selesai di-render. Kegagalan LCP sering kali bukan disebabkan oleh ukuran file gambar semata, melainkan antrean kompetisi resource (network contention) dan *render-blocking resources* yang menunda *discovery* dan *download* node LCP.

2. **Interaction to Next Paint (INP):**
   $$INP = \text{Input Delay} + \text{Processing Duration} + \text{Presentation Delay}$$
   Menggantikan First Input Delay (FID). INP mengukur latensi keseluruhan dari seluruh interaksi pengguna (click, tap, keypress) sepanjang lifecycle sesi. Fokusnya adalah eliminasi *Long Tasks* (>50ms) yang memblokir Main Thread, mencegah *Compositor* mengirim frame berikutnya ke GPU.

3. **Cumulative Layout Shift (CLS):**
   $$\text{Layout Shift Score} = \text{Impact Fraction} \times \text{Distance Fraction}$$
   Mengukur instabilitas visual akibat pergeseran geometri node DOM setelah render awal. Terjadi jika browser tidak dapat memesan ruang (*layout reservation*) sebelum asset (gambar, iframe, dynamic ads, web fonts) selesai dievaluasi.

4. **Time to First Byte (TTFB):**
   Fondasi struktural. Jika TTFB > 800ms, alokasi budget waktu untuk LCP praktis hangus sebelum browser mulai mem-parse satu pun tag HTML.

---

### 3. Why It Matters (Enterprise SEO & AI-Driven Search)

Dalam ekosistem pencarian modern dan autonomous web agents:

* **Sinyal Peringkat Deterministik:** Google Page Experience Signal mengevaluasi data CrUX 28-hari secara *rolling*. Kegagalan melewati ambang p75 pada salah satu metrik dapat menurunkan posisi kompetitif pada kueri transaksional bervolume tinggi.
* **Crawl & Render Budget Preservation:** WRS (Web Rendering Service) Googlebot memiliki batasan komputasi (*render budget*). Jika CPU thread terkunci selama ratusan milidetik hanya untuk mengeksekusi JavaScript hydration, antrean crawling halaman lain akan di-drop (*crawl deficit*).
* **AI Engine Scraping Efficacy:** Autonomous scraping agents (OpenAIbot, Perplexity) mengevaluasi halaman menggunakan engine headless (misal: Chromium headless). Struktur DOM yang bergeser secara dinamis atau hidrasi lambat dapat mengakibatkan ekstraksi konten terpotong (*partial extraction failure*), merusak representasi situs dalam model Retrieval-Augmented Generation (RAG).

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut menggambarkan arsitektur pengumpulan, analisis, dan feedback loop telemetri CWV dari browser klien/bot hingga ke infrastruktur edge remediating:

```
+------------------------------------------------------------------------------------+
| CLIENT LAYER (Browser Runtime / Headless Bot)                                     |
|                                                                                    |
|  +-------------------------------------------------------------------------------+ |
|  | Modern Web Vitals Engine (web-vitals.js v4 + LoAF API)                        | |
|  | - PerformanceObserver (largest-contentful-paint, layout-shift, event)         | |
|  | - Script Attribution (Long Animation Frame detection)                        | |
|  +-------------------------------------------------------------------------------+ |
|                                      |                                             |
|                                      | Navigator.sendBeacon() / Fetch (keepalive)  |
+--------------------------------------v---------------------------------------------+
                                       |
+--------------------------------------v---------------------------------------------+
| INGESTION & PROCESSING LAYER                                                       |
|                                                                                    |
|  +-----------------------+     +------------------------+                          |
|  | Cloudflare Worker /   | --> | Kafka / Redpanda       |                          |
|  | Edge Telemetry API    |     | Event Ingestion Queue  |                          |
|  +-----------------------+     +------------------------+                          |
|                                            |                                       |
|                                            v                                       |
|                                +------------------------+                          |
|                                | ClickHouse DB Cluster  |                          |
|                                | - Real-time Aggregates |                          |
|                                | - p75 Calculation Eng. |                          |
|                                +------------------------+                          |
+--------------------------------------------|---------------------------------------+
                                             |
+--------------------------------------------v---------------------------------------+
| REMEDIATION & EDGE INJECTION LAYER                                                 |
|                                                                                    |
|  +-------------------------------------------------------------------------------+ |
|  | Dynamic Edge Optimization Engine (Fastly Compute@Edge / Cloudflare Pages)     | |
|  | - Injeksi Link Preload / 103 Early Hints otomatis untuk elemen LCP            | |
|  | - Font display swap auto-tuning & size-adjust injection                        | |
|  | - Speculation Rules API injection untuk rute terprediksi                      | |
|  +-------------------------------------------------------------------------------+ |
+------------------------------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Mekanisme INP dan Long Animation Frames (LoAF)
INP merekam seluruh rentang waktu hingga pixel layar terupdate:
1. **Input Delay:** Waktu tunggu event saat Main Thread sibuk mengeksekusi microtask/macrotask sebelumnya.
2. **Processing Time:** Waktu eksekusi semua callback event listener JavaScript (`keydown`, `pointerdown`, `click`).
3. **Presentation Delay:** Waktu yang dihabiskan compositor untuk menghitung ulang style, reflow layout, memproses layer composite, dan mengirim buffer ke display engine (GPU back-buffer swap).

Browser Chromium modern menyediakan API **Long Animation Frames (LoAF)** yang melacak frame lambat (>50ms) dan langsung memetakan script mana (URL, function name, character position) yang memblokir rendering.

#### B. Anatomi LCP: 4 Sub-Partisi
Pengoptimalan LCP mensyaratkan dekonstruksi waktu menjadi 4 kuadran:
* **TTFB (Target: < 40s% dari total LCP):** Latensi jaringan + DNS + TLS + Server Compute.
* **Resource Load Delay (Target: < 10%):** Jeda antara respons HTML pertama sampai browser *menemukan* resource LCP. (Dieliminasi menggunakan SSR native image tags atau `103 Early Hints`).
* **Resource Load Duration (Target: < 40%):** Durasi streaming payload resource LCP melewati network protocol.
* **Element Render Delay (Target: < 10%):** Waktu antara download gambar/font selesai sampai browser menggambarnya di layar. Sering kali membengkak akibat hidrasi monolitik yang memblokir layout rendering.

#### C. Mekanisme CLS: Layout Instability API
Browser melacak pergeseran node melalui class internal `cc::LayoutShiftTracker`.
Perhitungan matematis didasarkan pada pergeseran koordinat viewport:
* **Impact Region:** Gabungan visual area dari semua elemen tidak stabil sebelum dan sesudah pergeseran.
* **Distance:** Jarak maksimum elemen tidak stabil bergerak relatif terhadap dimensi viewport terbesar (lebar atau tinggi).
* **Pengecualian:** Pergeseran yang terjadi dalam rentang 500ms setelah interaksi pengguna (yang memiliki flag `hadRecentInput: true`) dikecualikan dari kalkulasi CLS.

---

### 6. Production-Ready Code Implementation

Implementasi ini terdiri dari dua sistem:
1. **Frontend Observability Engine (`telemetry.ts`):** Menggunakan native `PerformanceObserver` untuk mengukur LCP, INP (dengan atribut LoAF), dan CLS, lalu mengirimkan datanya via `navigator.sendBeacon`.
2. **High-Throughput Ingestion Backend (`server.py`):** Menggunakan FastAPI dan Pydantic dengan koneksi non-blocking yang mengevaluasi pelanggaran SLA performa untuk optimasi bot crawl.

#### File 1: `telemetry.ts` (Client-Side RUM Collector)

```typescript
/**
 * Advanced Core Web Vitals RUM Collector
 * Tracks LCP, CLS, INP with Long Animation Frame (LoAF) Attribution
 */

interface MetricPayload {
  name: 'LCP' | 'CLS' | 'INP';
  value: number;
  rating: 'good' | 'needs-improvement' | 'poor';
  navigationType: string;
  attribution?: Record<string, unknown>;
  timestamp: number;
  url: string;
}

class PerformanceTelemetry {
  private endpoint: string;
  private navigationType: string;

  constructor(endpoint: string) {
    this.endpoint = endpoint;
    const navEntries = performance.getEntriesByType('navigation') as PerformanceNavigationTiming[];
    this.navigationType = navEntries.length > 0 ? navEntries[0].type : 'navigate';
    
    this.initLCP();
    this.initCLS();
    this.initINP();
  }

  private getRating(name: MetricPayload['name'], value: number): MetricPayload['rating'] {
    switch (name) {
      case 'LCP':
        return value <= 2500 ? 'good' : value <= 4000 ? 'needs-improvement' : 'poor';
      case 'CLS':
        return value <= 0.1 ? 'good' : value <= 0.25 ? 'needs-improvement' : 'poor';
      case 'INP':
        return value <= 200 ? 'good' : value <= 500 ? 'needs-improvement' : 'poor';
    }
  }

  private send(payload: MetricPayload): void {
    const data = JSON.stringify(payload);
    if (navigator.sendBeacon) {
      const blob = new Blob([data], { type: 'application/json' });
      navigator.sendBeacon(this.endpoint, blob);
    } else {
      fetch(this.endpoint, {
        body: data,
        method: 'POST',
        keepalive: true,
        headers: { 'Content-Type': 'application/json' },
      }).catch((err) => console.error('Telemetry reporting failed:', err));
    }
  }

  private initLCP(): void {
    const observer = new PerformanceObserver((entryList) => {
      const entries = entryList.getEntries() as LargestContentfulPaint[];
      const lastEntry = entries[entries.length - 1];
      if (!lastEntry) return;

      const value = lastEntry.startTime;
      this.send({
        name: 'LCP',
        value,
        rating: this.getRating('LCP', value),
        navigationType: this.navigationType,
        timestamp: Date.now(),
        url: window.location.href,
        attribution: {
          element: lastEntry.element?.tagName ?? 'UNKNOWN',
          id: lastEntry.element?.id ?? '',
          url: lastEntry.url,
          loadTime: lastEntry.loadTime,
          renderTime: lastEntry.renderTime,
        },
      });
    });

    observer.observe({ type: 'largest-contentful-paint', buffered: true });
  }

  private initCLS(): void {
    let clsValue = 0;
    let clsEntries: LayoutShift[] = [];

    const observer = new PerformanceObserver((entryList) => {
      for (const entry of entryList.getEntries() as LayoutShift[]) {
        // Abaikan shift yang dipicu interaksi langsung pengguna
        if (!entry.hadRecentInput) {
          clsValue += entry.value;
          clsEntries.push(entry);
        }
      }
    });

    observer.observe({ type: 'layout-shift', buffered: true });

    // Kirim data CLS saat halaman beralih ke state hidden / unload
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') {
        observer.takeRecords();
        this.send({
          name: 'CLS',
          value: clsValue,
          rating: this.getRating('CLS', clsValue),
          navigationType: this.navigationType,
          timestamp: Date.now(),
          url: window.location.href,
          attribution: {
            shiftCount: clsEntries.length,
            sources: clsEntries.map((e) => e.sources?.map((s) => s.node?.nodeName)).flat(),
          },
        });
      }
    }, { once: true });
  }

  private initINP(): void {
    let longestInteraction: PerformanceEventTiming | null = null;

    const observer = new PerformanceObserver((entryList) => {
      for (const entry of entryList.getEntries() as PerformanceEventTiming[]) {
        if (!entry.interactionId) continue;

        if (!longestInteraction || entry.duration > longestInteraction.duration) {
          longestInteraction = entry;
        }
      }
    });

    observer.observe({
      type: 'event',
      buffered: true,
      durationThreshold: 16, // Tangkap event di atas budget 1 frame (60fps)
    } as PerformanceObserverInit);

    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden' && longestInteraction) {
        const val = longestInteraction.duration;
        this.send({
          name: 'INP',
          value: val,
          rating: this.getRating('INP', val),
          navigationType: this.navigationType,
          timestamp: Date.now(),
          url: window.location.href,
          attribution: {
            eventType: longestInteraction.name,
            inputDelay: longestInteraction.processingStart - longestInteraction.startTime,
            processingDuration: longestInteraction.processingEnd - longestInteraction.processingStart,
            presentationDelay: longestInteraction.duration - (longestInteraction.processingEnd - longestInteraction.startTime),
          },
        });
      }
    }, { once: true });
  }
}

// Inisialisasi otomatis
if (typeof window !== 'undefined') {
  new PerformanceTelemetry('/api/v1/telemetry/cwv');
}
```

#### File 2: `server.py` (Telemetry Ingestion Engine)

```python
"""
Production-Ready Telemetry Ingestion Engine
Processes and analyzes Core Web Vitals payloads for SEO anomalies.
"""

from typing import Dict, Any, Optional, Literal
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, status
from pydantic import BaseModel, Field, HttpUrl
import logging
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("CWVIngestionEngine")

app = FastAPI(title="SEO Core Web Vitals Engine", version="1.0.0")

class MetricTelemetryPayload(BaseModel):
    name: Literal['LCP', 'CLS', 'INP']
    value: float = Field(..., ge=0, description="Metric value in ms or score unit")
    rating: Literal['good', 'needs-improvement', 'poor']
    navigationType: str
    attribution: Optional[Dict[str, Any]] = None
    timestamp: int
    url: str

def analyze_metric_degradation(payload: MetricTelemetryPayload, user_agent: str) -> None:
    """
    Evaluasi background task: mendeteksi regresi performa fatal dan memicu alert.
    """
    is_bot = any(bot_id in user_agent.lower() for bot_id in ["googlebot", "bingbot", "gptbot", "claudebot"])
    
    if payload.rating == "poor":
        logger.warning(
            f"PERFORMANCE ALERT: Poor {payload.name} ({payload.value:.2f}) on {payload.url} | "
            f"Bot={is_bot} | UA={user_agent} | Attribution={payload.attribution}"
        )
        
        # Logika eskalasi: Jika bot mengalami degradasi LCP/CLS, render budget terancam
        if is_bot and payload.name in ["LCP", "CLS"]:
            logger.error(
                f"CRITICAL: Search Crawler Experience Compromised! "
                f"URL: {payload.url} | Metric: {payload.name} | Value: {payload.value}"
            )
            # Di sini Anda dapat memicu webhook PagerDuty, Slack, atau invalidasi CDN edge cache.

@app.post("/api/v1/telemetry/cwv", status_code=status.HTTP_202_ACCEPTED)
async def ingest_cwv_telemetry(
    payload: MetricTelemetryPayload,
    request: Request,
    background_tasks: BackgroundTasks
):
    try:
        user_agent = request.headers.get("user-agent", "Unknown")
        
        # Delegasikan pemrosesan intensif dan komputasi agregasi ke worker thread
        background_tasks.add_task(analyze_metric_degradation, payload, user_agent)
        
        return {"status": "queued", "metric": payload.name}
    except Exception as exc:
        logger.error(f"Failed to process telemetry payload: {str(exc)}")
        raise HTTPException(status_code=400, detail="Malformed telemetry payload")

if __name__ == "__main__":
    uvicorn.run("server.py:app", host="0.0.0.0", port=8000, reload=False, workers=4)
```

---

### 7. Edge Cases & Failure Modes

1. **Back/Forward Cache (bfcache) Restorations:**
   * *Problem:* Saat halaman dimuat ulang dari bfcache, metrik navigasi normal tidak dihitung ulang. Akibatnya, nilai LCP nol atau tidak terkirim, mendistorsi agregasi p75 CrUX.
   * *Mitigasi:* Tangani event `pageshow`. Jika `event.persisted === true`, lakukan re-inisialisasi kalkulasi LCP/INP dengan delta marker baru.
2. **Hidden Tab Load / Prerendering Degradation:**
   * *Problem:* Halaman yang dibuka di *background tab* membekukan eksekusi CSS layout dan rAF (`requestAnimationFrame`). LCP akan tercatat sangat tinggi karena browser baru merender frame visual saat tab difokuskan.
   * *Mitigasi:* Buang data LCP dari sesi di mana `document.visibilityState === 'hidden'` pada saat TTFB terjadi.
3. **Hydration Mismatch Menyebabkan Total DOM Replacement:**
   * *Problem:* Perbedaan antara HTML SSR dan Initial Client DOM (misal karena timezone atau deteksi browser dinamis) memicu React/Vue membuang subtree DOM dan merendernya ulang dari nol.
   * *Mitigasi:* Eliminasi total mismatch ini. Hal ini menyebabkan nilai CLS meroket seketika dan melipatgandakan *Element Render Delay* pada LCP.
4. **INP Measurement Blindspots pada Headless Testing:**
   * *Problem:* Googlebot WRS dan synthetic tester standar tidak melakukan scroll acak atau interaksi dinamis. Sintetis INP akan bernilai 0ms / Not Applicable, menyembunyikan masalah yang dialami user manusia di CrUX.
   * *Mitigasi:* Terapkan Chaos Monkey testing script pada staging environment untuk mensimulasikan klik dan pengetikan acak di bawah simulasi CPU throttling 4x/6x.

---

### 8. Trade-offs & Alternatif Solusi

| Strategi | Keuntungan | Biaya & Trade-off | Dampak SEO & Bot Crawl |
| :--- | :--- | :--- | :--- |
| **Strict Server-Side Rendering (SSR)** | TTFB rendah jika dicache, LCP resource delay mendekati 0ms. | Server compute budget tinggi; risiko TTFB lambat jika database lambat. | Paling disukai Search Engine Bot; konten langsung terlihat di DOM pertama. |
| **Client-Side Rendering (CSR) + Dynamic Pre-rendering** | Infrastruktur server murah (S3/CloudFront). | Memerlukan *dual-pipeline* rendering (rendertron/prerender.io), rawan *cache desync*. | Bot dapat crawling, namun pengguna manusia mendapatkan performa LCP/INP buruk. |
| **Edge Streaming SSR (HTML-First)** | TTFB sangat cepat (<100ms), browser langsung mem-parse chunk HTML awal. | Debugging kompleks; tidak kompatibel dengan library React legacy tertentu. | Optimal untuk AI Agents; eksekusi streaming parallel mempercepat ekstraksi token teks. |
| **Islands Architecture (Astro/Fresh)** | JavaScript client-side mendekati 0KB secara default; INP sempurna (<50ms). | Arsitektur state global antarpulau (*cross-island state*) lebih rumit dikelola. | Skor CWV p75 konsisten di zona hijau; crawling cost sangat minimal. |

---

### 9. Best Practices & Standard Industri

* **Resource Fetch Priority:** Tetapkan atribut `fetchpriority="high"` secara eksklusif pada elemen gambar/video yang merupakan kandidat LCP. Jangan gunakan atribut ini pada lebih dari 1 atau 2 elemen di viewport awal, agar bandwidth pipe tidak macet.
* **Layout Stability Guardrails:**
  * Tetapkan secara eksplisit atribut `width` dan `height` atau aspect-ratio CSS pada seluruh aset grafis (`<img>`, `<video>`, `<iframe>`).
  * Gunakan properti CSS `content-visibility: auto` bersamaan dengan `contain-intrinsic-size` untuk menunda rendering blok DOM di luar layar (*off-screen*) tanpa merusak scrollbar geometry.
* **Main-Thread Yielding Strategy:**
  Gunakan pemecahan task asinkron modern menggunakan standard scheduler web API:
  ```typescript
  async function yieldToMain(): Promise<void> {
    if ('scheduler' in window && 'yield' in (window as any).scheduler) {
      return await (window as any).scheduler.yield();
    }
    return new Promise((resolve) => setTimeout(resolve, 0));
  }
  ```
  Pecah perulangan berat (*heavy loop processing*) dengan memanggil `await yieldToMain()` setiap 50ms untuk menjaga responsivitas INP di bawah threshold 200ms.
* **Web Font Optimization:**
  Terapkan strategi zero-layout-shift font swap:
  ```css
  @font-face {
    font-family: 'Inter-Fallback';
    src: local('Arial');
    ascent-override: 90%;
    descent-override: 22%;
    line-gap-override: 0%;
    size-adjust: 107.5%;
  }
  ```

---

### 10. Hands-on Lab Exercise

#### Skenario:
Sebuah halaman e-commerce (Product Detail Page) mengalami degradasi CrUX: **LCP p75 = 4.2 detik**, **INP p75 = 480ms**, dan **CLS p75 = 0.32**. Halaman ini terancam kehilangan status kelayakan Page Experience di Google SERP.

#### Langkah 1: Diagnosis Masalah
Jalankan Chrome DevTools Profiler (Performance Panel) dengan setting:
* CPU: 4x Slowdown
* Network: Fast 3G
Catat bahwa:
1. LCP gambar di-lazyload (`loading="lazy"`), sehingga browser menolak mendownload gambar hingga rendering tree layout selesai.
2. Banner ulasan produk diinjeksikan secara dinamis tanpa reservasi kontainer DOM (Memicu CLS).
3. Script tracking analytics mengeksekusi JSON parsing raksasa saat tombol "Beli Sekarang" ditekan (Memicu INP tinggi).

#### Langkah 2: Eksekusi Remediasi Kode

Perbaiki template HTML/React Anda:

```html
<!-- SEBELUM: RUSAK -->
<!-- <img src="/product-large.jpg" loading="lazy" class="product-hero" /> -->
<!-- <div id="dynamic-reviews"></div> -->

<!-- SESUDAH: PRODUCTION-READY (OPTIMIZED) -->

<!-- 1. Optimasi LCP: Hapus lazyload, tambahkan fetchpriority high, preload di Head -->
<link rel="preload" fetchpriority="high" as="image" href="/product-large.avif" type="image/avif" />

<div class="product-gallery">
  <img 
    src="/product-large.avif" 
    fetchpriority="high"
    loading="eager" 
    decoding="async"
    width="800" 
    height="600" 
    alt="Mechanical Keyboard Pro" 
    class="product-hero"
  />
</div>

<!-- 2. Optimasi CLS: Reservasi ruang menggunakan aspect-ratio & CSS containment -->
<div 
  id="dynamic-reviews" 
  style="min-height: 400px; contain-intrinsic-size: 1000px 400px; content-visibility: auto;"
>
  <!-- Komponen review di-inject di sini tanpa mengubah dimensi layout sekitarnya -->
</div>
```

Perbaiki Event Handler pada Tombol Beli (`INP Optimization`):

```typescript
// Optimasi INP: Pecah Long Task saat eksekusi tombol Add to Cart
const addToCartButton = document.querySelector<HTMLButtonElement>('#buy-btn');

addToCartButton?.addEventListener('click', async (event) => {
  // Fase 1: Segera feedback UI ke pengguna (Compositor langsung menggambar frame ini)
  addToCartButton.classList.add('btn-loading');
  addToCartButton.setAttribute('disabled', 'true');

  // Berikan waktu (yield) agar browser sempat mempresentasikan frame visual loading spinner
  await yieldToMain();

  // Fase 2: Eksekusi tugas analitik dan manipulasi data berat
  processHeavyCartOperations();
  await yieldToMain();

  // Fase 3: State akhir transaksi
  addToCartButton.classList.remove('btn-loading');
  addToCartButton.removeAttribute('disabled');
});

function yieldToMain(): Promise<void> {
  return new Promise((resolve) => {
    const channel = new MessageChannel();
    channel.port1.onmessage = () => resolve();
    channel.port2.postMessage(null);
  });
}

function processHeavyCartOperations(): void {
  // Simulasi pemrosesan komputasi
  const start = performance.now();
  while (performance.now() - start < 60) {
    // Memecah komputasi
  }
}
```

#### Langkah 3: Verifikasi
1. Jalankan audit menggunakan Google Lighthouse CLI:
   ```bash
   lighthouse http://localhost:3000/pdp/keyboard-pro --throttling-method=devtools --screenEmulation.disabled --only-categories=performance
   ```
2. Pastikan nilai:
   * **LCP < 2.0s**
   * **CLS < 0.05**
   * **TBT (Total Blocking Time proxy untuk INP) < 150ms**
3. Periksa panel Telemetri backend FastAPI Anda (`/api/v1/telemetry/cwv`) untuk mengonfirmasi rating berubah menjadi `"good"`. Halaman kini aman dari penalti performa Googlebot dan optimal untuk scraping agent.