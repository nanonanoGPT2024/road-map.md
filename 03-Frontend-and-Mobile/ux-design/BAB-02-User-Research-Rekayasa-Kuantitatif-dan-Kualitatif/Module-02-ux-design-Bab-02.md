# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 02: User Research Rekayasa Kuantitatif dan Kualitatif**  
**Kategori: 03-Frontend-and-Mobile | Topik: UX Design Engineering**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik pada tingkat *Staff/Principal UX Engineer* dan *Frontend Architect* diharapkan mampu:

1. **Merancang dan Mengimplementasikan Arsitektur Telemetri UX Berperforma Tinggi:** Membangun *client-side instrumentation engine* yang mampu menangkap metrik perilaku (*rage clicks*, *dead clicks*, *dwell time*, *scroll velocity*) tanpa membebani *main thread* (0ms Frame Drop / 60 FPS minimum).
2. **Mengintegrasikan Riset Kualitatif dan Kuantitatif Secara Terprogram:** Membangun *event-driven trigger engine* untuk memicu intervensi kualitatif kontekstual (*micro-surveys*, *intercept interviews*) berdasarkan anomali kuantitatif secara *real-time*.
3. **Mengamankan dan Mematuhi Regulasi Privasi Data (GDPR/PCI-DSS):** Menerapkan mekanisme *client-side PII (Personally Identifiable Information) masking* dan *deterministic sampling* sebelum data dikirim ke *data lakehouse/OLAP engine*.
4. **Membangun Statistical Validation Engine untuk UX:** Menganalisis data telemetri kuantitatif menggunakan kalkulasi signifikansi statistik (*Bayesian & Frequentist approaches*) serta *Google HEART Framework* yang terotomatisasi.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta harus menguasai:
* **TypeScript & Web API Tingkat Lanjut:** Pemahaman mendalam mengenai DOM MutationObserver, IntersectionObserver, PerformanceObserver, serta arsitektur Web Workers.
* **Sistem Terdistribusi & Pipeline Data:** Konsep streaming data (Kafka/Redpanda), basis data analitik berorientasi kolom (ClickHouse/BigQuery), serta protokol transmisi data (`navigator.sendBeacon`, WebSocket, Fetch Keepalive).
* **Statistika Probabilistik:** Pengetahuan dasar mengenai *hypothesis testing*, interval kepercayaan (*confidence interval*), *p-value*, serta distribusi Normal dan Beta.
* **Dasar UX Telemetry:** Pemahaman tentang Metrik Sukses UX (SUS, SUPR-Q, CSAT, CES, Task Completion Rate).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Konvergensi Rekayasa Telemetri UX dan Data Streaming

Riset pengguna (*User Research*) modern di tingkat enterprise telah bergeser dari metodologi terisolasi (survei manual berkala atau tes lab kecil) menjadi sistem rekayasa perangkat lunak terdistribusi yang berkelanjutan. Sistem ini menggabungkan dua aliran data:

1. **Aliran Kuantitatif (Continuous Telemetry):** Data telemetri deterministik tingkat rendah (koordinat klik, *viewport layout shifts*, *network latency metrics*, *event timeline*).
2. **Aliran Kualitatif (Contextual Sampling):** Data subjektif kontekstual (umpan balik berbasis mikro-interaksi, transkrip rekaman sesi, anotasi visual) yang dipicu saat terjadi anomali perilaku.

```
+---------------------------------------------------------------------------------------+
|                                     BROWSER RUNTIME                                   |
|                                                                                       |
|  +------------------------+  +------------------------+  +-------------------------+  |
|  |   UI Interactions      |  |  PerformanceObserver   |  |   MutationObserver      |  |
|  | (Click, Scroll, Input) |  |   (LCP, CLS, INP, FID) |  | (DOM Shifts, Render Del)|  |
|  +-----------+------------+  +-----------+------------+  +------------+------------+  |
|              |                           |                            |               |
|              +-------------------+       |       +--------------------+               |
|                                  v       v       v                                    |
|                      +---------------------------------------+                        |
|                      |  UX Telemetry Core Engine (Off-Main)  |                        |
|                      |  - Heuristic Anomaly Detectors        |                        |
|                      |  - Client-Side Deterministic Sampler  |                        |
|                      |  - RegEx & DOM-Tree PII Scrubber      |                        |
|                      +-------------------+-------------------+                        |
+------------------------------------------|--------------------------------------------+
                                           | ArrayBuffer / Encrypted JSON
                                           | via navigator.sendBeacon / Fetch Keepalive
                                           v
+---------------------------------------------------------------------------------------+
|                                EDGE INGESTION & PROCESSING                            |
|                                                                                       |
|      +-----------------------------------------------------------------------+        |
|      | Cloudflare Workers / AWS CloudFront Edge (Authorizer & Schema Enforcer)|       |
|      +-----------------------------------+-----------------------------------+        |
+------------------------------------------|--------------------------------------------+
                                           v
+---------------------------------------------------------------------------------------+
|                            ENTERPRISE DATA PLATFORM (CORE)                            |
|                                                                                       |
|                 +-------------------------------------------------+                   |
|                 | Message Broker (Apache Kafka / Redpanda Cluster)|                   |
|                 +------------------------+------------------------+                   |
|                                          |                                            |
|                 +------------------------+------------------------+                   |
|                 v                                                 v                   |
|  +-----------------------------+               +-----------------------------------+  |
|  | ClickHouse OLAP Engine      |               | Contextual Survey / Intercept Svc |  |
|  | (Aggregasi Metrik HEART &   |               | (Trigger Qualitative Prompt Engine|  |
|  | Funnel Dropout Telemetry)   |               | via WebSocket Real-time)          |  |
|  +-----------------------------+               +-----------------------------------+  |
+---------------------------------------------------------------------------------------+
```

### 3.2 Komponen Arsitektur Kritis

1. **The Behavioral Heuristic Engine (Client-Side):**
   * Berfungsi mendeteksi pola frustrasi pengguna secara lokal sebelum mengirimkan *payload*. 
   * **Rage Click Detection:** Mendeteksi $\ge N$ klik pada target area berjarak $\le \epsilon$ piksel dalam jendela waktu $\Delta t$ milidetik.
   * **Dead Click Detection:** Mendeteksi interaksi klik pada elemen statis yang tidak menghasilkan mutasi DOM, permintaan jaringan (*network request*), maupun modifikasi visual dalam batas waktu $T_{threshold}$.
   * **Excessive Scrolling / Thrashed Navigation:** Mengidentifikasi pola pemindaian visual tanpa fokus yang mengindikasikan informasi yang dicari pengguna sulit ditemukan (*lostness metric*).

2. **PII Masking & Privacy Boundary:**
   * Sanitasi data harus dieksekusi secara sinkron sebelum proses serialisasi JSON.
   * Node input pengguna (`input`, `textarea`, `[contenteditable]`) disaring melalui *allowlist-based schema*. Nilai teks diganti dengan masker deterministik berukuran setara (`\u2588` atau karakter asterisk `*`) untuk mempertahankan representasi dimensi tata letak (*layout dimensions*) tanpa mengekspos data sensitif.

3. **Hybrid Statistical Processing Engine:**
   * Menggabungkan metrik **HEART** (*Happiness, Engagement, Adoption, Retention, Task Success*) ke dalam model analitik multivariat.
   * Menghubungkan *Task Success Latency* (Kuantitatif) dengan skor *CSAT/CES* (Kualitatif) menggunakan matriks korelasi *Pearson/Spearman* pada *storage layer* berbasis ClickHouse.

---

## 4. Why & What

| Dimensi | Pendekatan UX Tradisional (Siloed) | Pendekatan Rekayasa Telemetri UX Modern |
| :--- | :--- | :--- |
| **Pengumpulan Data** | Uji kegunaan berkala (8–10 partisipan) sekali tiap kuartal. | Telemetri berkelanjutan dari 100% populasi dengan *dynamic sampling*. |
| **Korelasi Data** | Tim riset menebak penyebab penurunan metrik konversi. | Anomali metrik secara instan memicu rekaman audit konteks dan intervensi kualitatif. |
| **Sensitivitas Performa** | Pustaka pihak ketiga pihak berat menginjeksi *tracker* yang memblokir *main thread*. | SDK khusus internal berukuran $< 8 \text{ KB}$ berbasis *zero-overhead primitives* (Beacon API). |
| **Kepatuhan Privasi** | *Raw text* dan token sensitif terekam di server pihak ketiga, menimbulkan risiko GDPR/PCI. | Sensor *client-side* melakukan sensor PII berbasis skema DOM secara *air-gapped*. |

---

## 5. How (Workflow Detail)

Alur kerja rekayasa telemetri riset pengguna dijalankan melalui fase-fase berikut:

1. **Tahap 1: Inisialisasi & Dynamic Sampling:**
   SDK memeriksa sesi pengguna menggunakan *hashing deterministik* (misal: MurmurHash3 dari `user_id` atau `session_id`). Sesi dialokasikan ke dalam kuadran pelacakan kuantitatif atau target intervensi kualitatif.
2. **Tahap 2: Non-blocking Event Capture:**
   Event didengarkan pada tingkat *window capture phase* (bukan *bubbling*) untuk mencegah `stopPropagation()` dari pustaka UI merusak rantai analitik.
3. **Tahap 3: Heuristic Evaluation & PII Scrubbing:**
   Ketika terdeteksi *dead click* atau *rage click*, algoritma heuristik melakukan evaluasi. String DOM ditranslasikan menjadi CSS Path selektor abstrak (misal: `div#app > main > button.btn-pay`), dan atribut nilai disanitasi.
4. **Tahap 4: Ring Buffer & Transport Batching:**
   Payload dimasukkan ke dalam ring buffer memori sirkular (`CircularBuffer`). Transmisi dijalankan saat buffer mencapai kapasitas threshold atau dipicu oleh event `visibilitychange` menggunakan `navigator.sendBeacon`.
5. **Tahap 5: Qualitative Trigger Engine:**
   Jika skor heuristik frustrasi melewati batas deviasi standar ($\mu + 2\sigma$), *Event Dispatcher* secara lokal atau via sinyal edge memunculkan *Contextual Micro-Survey Modal* yang menanyakan masalah spesifik yang dialami pengguna tepat pada saat kejadian.

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem
Sistem ini dapat diibaratkan seperti **Sistem Telemetri Kotak Hitam Pesawat Komersial yang Terhubung ke Radar Menara Pengawas**. 
* Sensor fisik (tekanan kabin, posisi sayap, kecepatan) merekam ratusan kali per detik secara senyap tanpa membebani mesin jet (**Aliran Kuantitatif**).
* Ketika sensor mendeteksi getaran abnormal yang tajam (*Rage Click*), sistem kokpit tidak hanya mencatat lonjakan data, tetapi langsung menyalakan radio komunikasi ke pilot untuk mengonfirmasi situasi secara lisan (**Aliran Kualitatif Terprogram**).

### Siklus Integrasi Data Kualitatif & Kuantitatif
```
                 [Interaksi Pengguna pada Aplikasi]
                                 |
           +---------------------+---------------------+
           |                                           |
           v                                           v
[Metrik Kuantitatif]                         [Metrik Kualitatif]
(Event Stream, Web Vitals,                    (Micro-survey, CSAT,
Clickstream, Task Time)                        Feedback Anotasi)
           |                                           |
           |-----> [Pipeline Anomali Terdeteksi] ------>|
           |       (Rage Click, Drop-off Funnel)        |
           |                                           |
           v                                           v
[ClickHouse Engine (OLAP)]                  [Natural Language Cluster Engine]
           \                                           /
            \                                         /
             v                                       v
        +-------------------------------------------------+
        |     Synthesized UX Intelligence Dashboard       |
        |   "Task Completion Turun 14% karena Pengguna    |
        |    Menganggap Elemen X Bukan Tombol Interaktif"  |
        +-------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Basic Batching Telemetry Beacon

Implementasi transmisi telemetri mendasar tanpa memblokir thread eksekusi browser:

```typescript
// basic-telemetry.ts
interface TelemetryPayload {
  eventName: string;
  timestamp: number;
  metadata: Record<string, unknown>;
}

export class SimpleTelemetry {
  private buffer: TelemetryPayload[] = [];
  private readonly endpoint: string;

  constructor(endpoint: string) {
    this.endpoint = endpoint;
    window.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') {
        this.flush();
      }
    });
  }

  public track(eventName: string, metadata: Record<string, unknown> = {}): void {
    this.buffer.push({
      eventName,
      timestamp: Date.now(),
      metadata,
    });

    if (this.buffer.length >= 10) {
      this.flush();
    }
  }

  public flush(): void {
    if (this.buffer.length === 0) return;

    const data = JSON.stringify(this.buffer);
    const sent = navigator.sendBeacon(this.endpoint, data);

    if (!sent) {
      // Fallback via Fetch Keepalive jika buffer melampaui limit ukuran sendBeacon (64KB)
      fetch(this.endpoint, {
        method: 'POST',
        body: data,
        headers: { 'Content-Type': 'application/json' },
        keepalive: true,
      }).catch((err) => console.error('Telemetry flush failed', err));
    }

    this.buffer = [];
  }
}
```

### 7.2 Practical Example: Enterprise UX Telemetry Core Engine

Berikut adalah implementasi SDK telemetri enterprise dengan arsitektur produksi:
* Mendeteksi *Rage Click* dan *Dead Click*.
* *Scrubbing PII* secara rekursif pada node DOM.
* *Intersection Observer* untuk mengukur *Dwell Time* per komponen UX.
* Integrasi *Dynamic Qualitative Intercept Trigger*.

```typescript
// UxEngine.ts
export interface TelemetryConfig {
  endpoint: string;
  sampleRate: number; // 0.0 to 1.0
  rageClickThreshold: number; // Jumlah klik
  rageClickTimeWindowMs: number; // Jendela waktu (ms)
  onFrustrationDetected?: (detail: FrustrationDetail) => void;
}

export interface FrustrationDetail {
  type: 'RAGE_CLICK' | 'DEAD_CLICK';
  targetSelector: string;
  timestamp: number;
  metadata: Record<string, unknown>;
}

export class ProductionUxEngine {
  private static instance: ProductionUxEngine;
  private config: TelemetryConfig;
  private isSampled: boolean;
  private clickHistory: { time: number; target: HTMLElement }[] = [];
  private observer: IntersectionObserver | null = null;
  private dwellMap: Map<string, number> = new Map();

  private constructor(config: TelemetryConfig) {
    this.config = config;
    this.isSampled = Math.random() <= this.config.sampleRate;

    if (this.isSampled && typeof window !== 'undefined') {
      this.initListeners();
      this.initDwellObserver();
    }
  }

  public static initialize(config: TelemetryConfig): ProductionUxEngine {
    if (!ProductionUxEngine.instance) {
      ProductionUxEngine.instance = new ProductionUxEngine(config);
    }
    return ProductionUxEngine.instance;
  }

  private initListeners(): void {
    // Window Capture Phase listener untuk menjamin penangkapan event
    window.addEventListener('pointerdown', (e) => this.handlePointerDown(e), true);
  }

  private handlePointerDown(event: PointerEvent): void {
    const target = event.target as HTMLElement;
    if (!target) return;

    const now = performance.now();
    this.clickHistory.push({ time: now, target });

    // Bersihkan klik di luar jendela observasi
    this.clickHistory = this.clickHistory.filter(
      (click) => now - click.time <= this.config.rageClickTimeWindowMs
    );

    // Evaluasi Heuristik: Rage Click
    const nearbyClicks = this.clickHistory.filter(
      (click) => click.target === target || target.contains(click.target)
    );

    if (nearbyClicks.length >= this.config.rageClickThreshold) {
      this.dispatchFrustration({
        type: 'RAGE_CLICK',
        targetSelector: this.sanitizeDOMSelector(target),
        timestamp: Date.now(),
        metadata: { clickCount: nearbyClicks.length },
      });
      this.clickHistory = []; // Reset setelah konfirmasi
    }

    // Evaluasi Heuristik: Dead Click
    this.evaluateDeadClick(target, now);
  }

  private evaluateDeadClick(element: HTMLElement, triggerTime: number): void {
    const isInteractive = this.isInteractiveElement(element);
    
    // Periksa apakah DOM bermutasi dalam 350ms
    let mutated = false;
    const mutationObserver = new MutationObserver(() => {
      mutated = true;
    });

    mutationObserver.observe(document.body, {
      attributes: true,
      childList: true,
      subtree: true,
    });

    window.setTimeout(() => {
      mutationObserver.disconnect();
      
      // Jika pengguna mengklik elemen yang nampak interaktif tetapi tidak menghasilkan efek
      if (!mutated && !isInteractive && element.getAttribute('role') === 'button') {
        this.dispatchFrustration({
          type: 'DEAD_CLICK',
          targetSelector: this.sanitizeDOMSelector(element),
          timestamp: Date.now(),
          metadata: { textSnapshot: this.maskPII(element.innerText || '') },
        });
      }
    }, 350);
  }

  private isInteractiveElement(element: HTMLElement): boolean {
    const tagName = element.tagName.toLowerCase();
    const isStandardInteractive = ['a', 'button', 'input', 'select', 'textarea'].includes(tagName);
    const hasInteractiveRole = ['button', 'link', 'checkbox', 'tab'].includes(element.getAttribute('role') || '');
    return isStandardInteractive || hasInteractiveRole;
  }

  private initDwellObserver(): void {
    this.observer = new IntersectionObserver(
      (entries) => {
        const now = performance.now();
        entries.forEach((entry) => {
          const selector = this.sanitizeDOMSelector(entry.target as HTMLElement);
          if (entry.isIntersecting) {
            this.dwellMap.set(selector, now);
          } else {
            const entryTime = this.dwellMap.get(selector);
            if (entryTime) {
              const dwellDuration = Math.round(now - entryTime);
              this.dwellMap.delete(selector);
              this.sendPayload({
                eventName: 'UX_COMPONENT_DWELL',
                selector,
                durationMs: dwellDuration,
                timestamp: Date.now(),
              });
            }
          }
        });
      },
      { threshold: 0.5 } // Elemen minimal terlihat 50% di viewport
    );
  }

  public registerComponentForObservation(element: HTMLElement): void {
    if (this.observer && this.isSampled) {
      this.observer.observe(element);
    }
  }

  public maskPII(text: string): string {
    // Masking email, nomor kartu kredit / ID numerik panjang, dan nomor telepon
    return text
      .replace(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g, '[REDACTED_EMAIL]')
      .replace(/\b(?:\d{4}[ -]?){3}(?=\d{4}\b)\d{4}\b/g, '[REDACTED_CARD]')
      .replace(/\+?[0-9]{10,14}/g, '[REDACTED_PHONE]');
  }

  public sanitizeDOMSelector(element: HTMLElement): string {
    const parts: string[] = [];
    let current: HTMLElement | null = element;

    while (current && current !== document.body && parts.length < 3) {
      let identifier = current.tagName.toLowerCase();
      if (current.id) {
        // Redact jika ID terlihat dinamis (UUID/Auto-generated)
        identifier += /^[0-9a-fA-F-]{8,}$/.test(current.id) ? '' : `#${current.id}`;
      } else if (current.className && typeof current.className === 'string') {
        const primaryClass = current.className.split(' ').filter(c => !c.includes(':'))[0];
        if (primaryClass) identifier += `.${primaryClass}`;
      }
      parts.unshift(identifier);
      current = current.parentElement;
    }

    return parts.join(' > ');
  }

  private dispatchFrustration(detail: FrustrationDetail): void {
    this.sendPayload({
      eventName: 'UX_FRUSTRATION_EVENT',
      ...detail,
    });

    if (this.config.onFrustrationDetected) {
      this.config.onFrustrationDetected(detail);
    }
  }

  private sendPayload(data: Record<string, unknown>): void {
    if (!this.isSampled) return;

    const payload = JSON.stringify(data);
    if (navigator.sendBeacon) {
      navigator.sendBeacon(this.config.endpoint, payload);
    } else {
      fetch(this.config.endpoint, {
        method: 'POST',
        body: payload,
        headers: { 'Content-Type': 'application/json' },
        keepalive: true,
      });
    }
  }
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### 8.1 Skenario Kasus: Platform Perbankan Digital Super-App (20 Juta DAU)
* **Problem Statement:** Menu konversi transaksi pinjaman mikro mengalami penurunan drastis (*drop-off*) sebesar 34% pada tahap akhir pengisian instrumen data finansial. Tim riset kuantitatif mendeteksi adanya penurunan *completion rate*, tetapi *analytics dashboard* konvensional gagal memberikan alasan penyebab kegagalan tersebut (*What vs Why problem*).
* **Solusi Terpasang:**
  * Implementasi *Enterprise UX Telemetry Engine* menggunakan *MutationObserver* untuk mengamati status form interaktif.
  * Menerapkan pelacakan otomatis metrik frustrasi: *Rage clicks* dan waktu tunggu input lebih dari 5 detik (*Input Form Hesitation Time*).
  * Menyiapkan intervensi kualitatif terprogram: Saat heuristik keraguan terdeteksi lebih dari $3\times$ pada elemen yang sama, sistem secara dinamis menyajikan *Single Question Survey Modal* (CSAT mikro): *"Apa yang membingungkan dari verifikasi ini?"*.
* **Hasil Diagnostik:**
  * Telemetri mendeteksi tingkat *dead click* sebesar 72% pada ikon informasi suku bunga yang dikira oleh pengguna sebagai *dropdown toggle*.
  * Hasil riset kualitatif dari *intercept survey* (1.200 responden dalam 2 jam) mengonfirmasi bahwa label teks "Suku Bunga Efektif Tahunan" dianggap ambigu dan menakutkan bagi target segmen pengguna.
* **Tindakan Korektif & Dampak Finansial:**
  * Tim UX Engineering mengubah tooltip menjadi panel *accordion collapsible* dengan perbaikan terminologi visual.
  * *Conversion rate* pulih, naik sebesar 28% dalam 14 hari pasca-rilis.
  * Waktu penyelesaian form (*Task Completion Time*) terpangkas 42 detik secara rata-rata.

---

## 9. Trade-offs (Performance, Latency, Scalability, Cost)

```
                  [Tingkat Granularitas UX Engine]
                              /      \
                             /        \
                            /          \
  [Full DOM Snapshot / Replay]         [Heuristic Micro-Telemetry]
  - Overhead Memori Tinggi (~80MB)     - Overhead Memori Minimal (<2MB)
  - Biaya Komputasi & Network Besar    - Biaya Ingest Sangat Efisien
  - Risiko Kebocoran PII Tinggi        - Sanitasi PII Terjamin di Edge
  - Rekonstruksi Visual Sempurna       - Berfokus pada Metrik Inti & Pola Frustrasi
```

| Parameter | Skenario Full Session Recording (e.g., Hotjar/FullStory) | Skenario Custom Lightweight Telemetry Engine | Justifikasi Arsitektur |
| :--- | :--- | :--- | :--- |
| **Main Thread Overhead** | Tinggi (5ms - 25ms per DOM mutation). Sering memicu Long Tasks. | Rendah ($< 0.5\text{ ms}$). Observasi dilakukan secara terisolasi. | Menjamin performa runtime aplikasi frontend tetap berada pada batasan *Interaction to Next Paint* (INP $< 200\text{ ms}$). |
| **Network Payload** | Berat ($500\text{ KB} - 3\text{ MB}$ per sesi terkompresi). | Sangat Ringan ($5\text{ KB} - 20\text{ KB}$ per sesi). | Menjaga konsumsi bandwidth pengguna seluler pada koneksi jaringan marginal (3G/4G). |
| **Biaya Ingest & Storage**| Sangat Tinggi ($>\$0.15$ per 1.000 sesi). | Rendah ($<\$0.005$ per 1.000 sesi pada ClickHouse cluster). | Skalabilitas biaya ketika memproses skala jutaan *Daily Active Users* (DAU). |
| **Kepatuhan Privasi (GDPR)**| Risiko Tinggi: Potensi kebocoran data sensitif (*raw inputs*) melalui DOM cloning. | Terkendali: *Allowlist-based masking* diterapkan sebelum data masuk ke jaringan. | Mengeliminasi penyimpanan informasi PII di basis data analitik. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Kesalahan Umum (Anti-Patterns)
1. **Synchronous Full-Tree DOM Traversal:** Mengeksekusi penelusuran DOM rekursif yang berat di dalam *event listener* `scroll` atau `mousemove`. Hal ini menyebabkan *jank* parah pada antarmuka pengguna.
2. **Naive PII Regex Masking:** Menggunakan ekspresi reguler yang tidak efisien (*catastrophic backtracking*) pada string teks besar di dalam *main thread*, yang memicu pemblokiran eksekusi UI.
3. **Survey Fatigue Over-triggering:** Tidak membatasi frekuensi (*rate limiting*) pemunculan survei kualitatif. Menampilkan modal intervensi kepada pengguna yang sama berulang kali akan merusak pengalaman pengguna dan memicu bias seleksi responden.
4. **Data Desynchronization (Lost on Unload):** Mengandalkan metode `fetch()` atau `XMLHttpRequest` asinkron biasa saat event `beforeunload` atau `pagehide`, yang menyebabkan hilangnya data ketika tab browser ditutup seketika.

### 10.2 Panduan Troubleshooting
* **Masalah: Metrik INP melonjak tajam setelah SDK telemetri diaktifkan.**
  * *Solusi:* Pindahkan logika pemrosesan heuristik ke dalam `requestIdleCallback` atau eksekusi di dalam dedicated `Web Worker`. Pastikan *event listener* menggunakan opsi `{ passive: true }` untuk interaksi scroll.
* **Masalah: Tingkat event hilang (*dropped events*) mencapai > 15% pada perangkat mobile.**
  * *Solusi:* Migrasikan transmisi dari fetch biasa ke `navigator.sendBeacon`. Jika payload melebihi limit 64 KB beacon browser, lakukan segmentasi buffer (*chunking*) atau simpan sementara ke `IndexedDB` untuk dikirimkan pada siklus *lifecycle* berikutnya.
* **Masalah: ClickHouse OLAP lambat saat memproses agregasi data funnel.**
  * *Solusi:* Hindari melakukan query langsung pada tabel event mentah. Buat tabel proyeksi *AggregatingMergeTree* yang mengelompokkan data berdasarkan dimensi waktu, jenis event, dan cohort pengguna secara bertahap.

---

## 11. Best Practices (Production Checklist)

### Client-Side Engine Checklist
- [ ] Listener terpasang menggunakan *Capture Phase* untuk mengabaikan manipulasi `stopPropagation()`.
- [ ] Seluruh event listener scroll/touch menggunakan atribut `{ passive: true }`.
- [ ] DOM MutationObserver dibatasi pada target *container subtree* tertentu, bukan memantau keseluruhan `document.documentElement` secara terus-menerus.
- [ ] Logika sanitasi PII telah divalidasi menggunakan pengujian unit (*unit testing*) terhadap skema format data sensitif internasional.
- [ ] Alur pengiriman data cadangan (*fallback*) disiapkan jika `navigator.sendBeacon` gagal atau tidak didukung oleh lingkungan browser.

### Data & Privacy Checklist
- [ ] Atribut data penanda privasi (`data-ux-mask="true"`) diterapkan pada seluruh komponen antarmuka yang mengelola data pribadi pengguna.
- [ ] Menjalankan *sampling rate* yang fleksibel dan dapat dikendalikan secara dinamis melalui *remote feature flag*.
- [ ] Data telemetri tidak menyimpan alamat IP publik secara permanen (lakukan hashing atau potong oktet IP di API Edge Gateway).

---

## 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun sebuah instrumen telemetri detektor frustrasi pengguna modular yang siap digunakan di lingkungan produksi.

### Struktur Direktori
```
hands-on/m02/
├── package.json
├── tsconfig.json
├── src/
│   ├── core/
│   │   ├── FrustrationDetector.ts
│   │   ├── PIIScrubber.ts
│   │   └── TransportQueue.ts
│   ├── index.ts
│   └── index.html
└── tests/
    └── FrustrationDetector.test.ts
```

### Langkah 1: Persiapan Environment
Inisialisasi direktori proyek dan pasang pustaka pendukung untuk pengujian:
```bash
mkdir -p hands-on/m02/src/core hands-on/m02/tests
cd hands-on/m02
npm init -y
npm install -D typescript ts-node vitest @types/node jsdom
npx tsc --init
```

### Langkah 2: Implementasi Pembersih Data Sensitif (PIIScrubber.ts)
Buat modul pembersih data pada `src/core/PIIScrubber.ts`:
```typescript
export class PIIScrubber {
  private static readonly EMAIL_REGEX = /[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+/g;
  private static readonly PHONE_REGEX = /(\+?\d{1,4}[\s-]?)?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{4}/g;
  private static readonly CC_REGEX = /\b(?:\d[ -]*?){13,16}\b/g;

  public static scrub(input: string): string {
    if (!input) return '';
    return input
      .replace(this.EMAIL_REGEX, '***@***.***')
      .replace(this.PHONE_REGEX, '***-***-****')
      .replace(this.CC_REGEX, '****-****-****-****');
  }

  public static sanitizeElementText(el: HTMLElement): string {
    if (el.hasAttribute('data-ux-mask') || el.getAttribute('type') === 'password') {
      return '[MASKED_SECURE_FIELD]';
    }
    return this.scrub(el.innerText || el.textContent || '');
  }
}
```

### Langkah 3: Implementasi Transport Queue (TransportQueue.ts)
Buat pipeline antrean data pada `src/core/TransportQueue.ts`:
```typescript
export class TransportQueue {
  private queue: any[] = [];
  private endpoint: string;
  private maxBatchSize: number;

  constructor(endpoint: string, maxBatchSize = 5) {
    this.endpoint = endpoint;
    this.maxBatchSize = maxBatchSize;
    this.setupUnloadHandler();
  }

  public enqueue(item: any): void {
    this.queue.push(item);
    if (this.queue.length >= this.maxBatchSize) {
      this.flush();
    }
  }

  public flush(): void {
    if (this.queue.length === 0) return;
    const payload = JSON.stringify(this.queue);
    
    if (typeof navigator !== 'undefined' && navigator.sendBeacon) {
      const success = navigator.sendBeacon(this.endpoint, payload);
      if (success) {
        this.queue = [];
        return;
      }
    }

    // Fallback Fetch
    fetch(this.endpoint, {
      method: 'POST',
      body: payload,
      headers: { 'Content-Type': 'application/json' },
      keepalive: true,
    }).then(() => {
      this.queue = [];
    }).catch(err => console.error('Gagal mengirim telemetri', err));
  }

  private setupUnloadHandler(): void {
    if (typeof window !== 'undefined') {
      window.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'hidden') {
          this.flush();
        }
      });
    }
  }
}
```

### Langkah 4: Implementasi Core Engine (FrustrationDetector.ts)
Integrasikan pelacak interaksi pada `src/core/FrustrationDetector.ts`:
```typescript
import { PIIScrubber } from './PIIScrubber';
import { TransportQueue } from './TransportQueue';

export interface DetectorOptions {
  endpoint: string;
  rageClickLimit: number;
  windowMs: number;
}

export class FrustrationDetector {
  private queue: TransportQueue;
  private clickHistory: { x: number; y: number; time: number; target: HTMLElement }[] = [];
  private options: DetectorOptions;

  constructor(options: DetectorOptions) {
    this.options = options;
    this.queue = new TransportQueue(options.endpoint);
    this.attachEvents();
  }

  private attachEvents(): void {
    window.addEventListener('click', (e) => this.handleClick(e), true);
  }

  private handleClick(event: MouseEvent): void {
    const now = performance.now();
    const target = event.target as HTMLElement;

    if (!target) return;

    this.clickHistory.push({
      x: event.clientX,
      y: event.clientY,
      time: now,
      target,
    });

    // Pruning
    this.clickHistory = this.clickHistory.filter(
      (c) => now - c.time <= this.options.windowMs
    );

    // Filter klik pada area yang sama
    const clusteredClicks = this.clickHistory.filter((c) => {
      const dist = Math.hypot(c.x - event.clientX, c.y - event.clientY);
      return dist < 30; // Radius toleransi piksel
    });

    if (clusteredClicks.length >= this.options.rageClickLimit) {
      this.recordFrustration('RAGE_CLICK', target, clusteredClicks.length);
      this.clickHistory = [];
    }
  }

  private recordFrustration(type: string, element: HTMLElement, intensity: number): void {
    const payload = {
      event: type,
      timestamp: Date.now(),
      elementTag: element.tagName.toLowerCase(),
      elementClasses: element.className,
      sanitizedText: PIIScrubber.sanitizeElementText(element),
      intensity,
    };

    console.warn(`[UX Telemetry] Frustrasi terdeteksi:`, payload);
    this.queue.enqueue(payload);
  }
}
```

### Langkah 5: Eksekusi dan Verifikasi
Jalankan pengujian unit berbasis Vitest:
```bash
npx vitest run
```

---

## 13. Exercise

### Level Easy
Modifikasi kelas `PIIScrubber` agar mampu melakukan sensor terhadap format identitas Nomor Induk Kependudukan (NIK) Indonesia (pola: 16 digit numerik unik) serta format Nomor Pokok Wajib Pajak (NPWP).
* *Syarat:* Tuliskan regex scrubbing yang tidak menghasilkan kerentanan ReDoS (*Regular Expression Denial of Service*).

### Level Medium
Kembangkan modul evaluasi metrik kuantitatif berbasis **Google HEART Task Success**:
* Bangun sebuah utility function `trackTaskExecution(taskName: string): { finish: (status: 'SUCCESS' | 'FAILURE') => void }`.
* Fungsi tersebut harus menghitung durasi waktu secara presisi menggunakan `performance.now()`, mengamati perubahan rute/URL halaman, serta mengirimkan metrik latensi penyelesaian tugas ke antrean telemetri.

### Level Hard
Bangun implementasi arsitektur **Bayesian Multi-Armed Bandit Selector** untuk pengujian micro-copy UX secara dinamis:
* Sistem harus mendistribusikan lalu lintas kunjungan (*traffic*) secara otomatis ke 3 variasi desain call-to-action (CTA) yang berbeda.
* Gunakan fungsi kalkulasi *Beta Distribution Sampling* sederhana di sisi klien untuk memilih variasi UI yang menghasilkan rasio klik (*Click-Through Rate*) tertinggi secara adaptif, meminimalkan paparan pengguna terhadap desain antarmuka dengan performa rendah (*regret minimization*).

---

## 14. Challenge

### Studi Kasus: Telemetri UX Berkelanjutan pada Aplikasi Sistem Kasir (Point of Sale) Offline-First Skala Besar
* **Konteks:** Perusahaan retail multinasional mengoperasikan 50.000 terminal kasir berbasis web/Electron di area dengan koneksi internet terbatas dan tidak stabil. Kasir sering kali mengalami *hang* atau kebingungan antarmuka saat memproses transaksi antrean panjang.
* **Spesifikasi Kebutuhan Teknis:**
  1. Rancang arsitektur telemetri yang mampu mencatat metrik kualitatif mikro (kebingungan alur transaksi) dan metrik kuantitatif (waktu input pemindaian barcode per item) tanpa ketergantungan koneksi jaringan (*Zero Network Dependency*).
  2. Implementasikan mekanisme penyimpanan lokal persisten (*Local Storage/IndexedDB Persistence Buffer*) dengan kuota data maksimal $5\text{ MB}$. Terapkan strategi rotasi log *FIFO (First In, First Out)* jika kuota penyimpanan tercapai.
  3. Saat koneksi jaringan pulih, data telemetri harus disinkronkan ke server secara bertahap menggunakan mekanisme *Exponential Backoff with Jitter* guna mencegah *Thundering Herd Problem* pada klaster API server pusat.
  4. Bangun aturan heuristik yang memicu dialog umpan balik kasir: Jika waktu jeda antar-item yang dipindai menyimpang $> 3\times$ deviasi standar dari kecepatan normal kasir tersebut, sistem harus menandai nomor antarmuka tersebut sebagai kandidat audit UX.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)

1. Mengapa `navigator.sendBeacon()` lebih direkomendasikan daripada `fetch()` standar untuk mengirimkan telemetri UX saat siklus navigasi halaman berakhir?
   * A) Karena `navigator.sendBeacon()` selalu mentransmisikan data melalui protokol WebSocket berkecepatan tinggi.
   * B) Karena `sendBeacon()` menjamin pengiriman data secara asinkron di latar belakang oleh browser tanpa menahan proses pembongkaran dokumen (*document unload*).
   * C) Karena ukuran payload `sendBeacon()` tidak memiliki batasan volume data.
   * D) Karena `sendBeacon()` secara otomatis melakukan enkripsi data simetris di sisi klien.

2. Apa yang diidentifikasi oleh heuristik *Dead Click* dalam analisis pengalaman pengguna?
   * A) Interaksi klik cepat berulang-ulang pada target yang sama akibat kemarahan pengguna.
   * B) Perangkat mouse pengguna yang mengalami kegagalan transmisi sinyal hardware.
   * C) Interaksi klik pada elemen UI yang tidak menghasilkan mutasi visual, modifikasi DOM, atau permintaan jaringan.
   * D) Klik yang diarahkan secara spesifik ke area halaman kosong untuk menghapus seleksi teks.

3. Kapan waktu yang tepat untuk melakukan sanitasi data sensitif (PII Scrubbing) dalam pipeline telemetri?
   * A) Di server analitik setelah data telemetri berhasil didekripsi.
   * B) Di sisi browser pengguna sebelum data diserialisasi dan ditransmisikan melalui jaringan.
   * C) Di database warehouse saat proses cron job malam hari dijalankan.
   * D) Di antarmuka dashboard analitik saat tim produk membuka visualisasi data.

4. Apa dampak penggunaan event listener non-passive pada interaksi `touchstart` atau `wheel` terhadap performa antarmuka?
   * A) Meningkatkan akurasi kalkulasi koordinat piksel layar secara presisi.
   * B) Memicu pemblokiran scroll pada browser karena antarmuka harus menunggu thread JavaScript menyelesaikan evaluasi fungsi.
   * C) Memaksa engine browser beralih ke rendering berbasis WebGL.
   * D) Tidak memberikan efek dampak apa pun pada browser desktop generasi terbaru.

5. Dalam framework Google HEART, dimensi yang mengukur kemudahan pengguna dalam menyelesaikan suatu alur alur fungsional kerja adalah:
   * A) Happiness
   * B) Engagement
   * C) Adoption
   * D) Task Success

---

### Bagian 2: Intermediate (Pilihan Ganda)

6. Apa risiko utama dari penerapan *Full DOM Snapshot Recording* secara terus-menerus tanpa pembatasan konteks pada aplikasi frontend berskala besar?
   * A) Penggunaan memori browser meningkat signifikan (*memory bloat*) dan berpotensi memicu Long Tasks yang memperburuk skor metrik Interaction to Next Paint (INP).
   * B) Server API akan mengalami kegagalan menerima payload karena keterbatasan kapasitas SSL handshake.
   * C) CSS Flexbox dan CSS Grid pada aplikasi akan gagal dirender oleh engine browser.
   * D) Pengguna secara otomatis dikeluarkan dari sesi autentikasi OAuth aktif mereka.

7. Jika Anda ingin mendeteksi elemen navigasi yang hanya dilalui pengguna tanpa sempat dibaca secara mendalam, indikator telemetri kuantitatif apa yang paling akurat?
   * A) Rasio klik tinggi (*Click-Through Rate*) dengan waktu retensi halaman yang lama.
   * B) Rasio kecepatan scroll tinggi (*High Scroll Velocity*) dipadukan dengan durasi tampil komponen (*Dwell Time*) yang berada di bawah ambang batas persepsi visual ($< 200\text{ ms}$).
   * C) Tingginya tingkat mutasi DOM pada komponen footer dokumen.
   * D) Terjadinya anomali *Cumulative Layout Shift* (CLS) pada elemen penampung teks.

8. Bagaimana metode paling efisien untuk meminimalkan dampak pengumpulan telemetri pada aplikasi berkapasitas jutaan pengguna aktif harian (*high-traffic enterprise*)?
   * A) Menghapus seluruh instrumen telemetri dan hanya mengandalkan wawancara riset manual tahunan.
   * B) Menggunakan *Client-side Deterministic Sampling* berbasis hash identitas sesi pengguna, sehingga instrumen hanya diaktifkan pada proporsi sampel pengguna yang ditargetkan.
   * C) Mengirimkan data telemetri mentah secara langsung ke server melalui protokol UDP tanpa parsing skema.
   * D) Membatasi waktu sesi pengguna agar tidak melebihi durasi 3 menit operasional.

9. Apa kelemahan utama dari memicu survei kualitatif konteks (*Micro-intercept survey*) murni berdasarkan ambang batas waktu (*timer-based trigger*, misal: muncul setelah 30 detik)?
   * A) Kebutuhan alokasi memori RAM browser melonjak tinggi untuk mengelola fungsi `setTimeout`.
   * B) Munculnya survei menginterupsi pengguna secara sembarangan tanpa memahami apakah pengguna sedang berada di tengah transaksi penting atau sedang mengalami kebingungan alur.
   * C) Survey timer membatalkan pengiriman data telemetri analitik kuantitatif yang sedang berjalan.
   * D) Browser modern secara otomatis memblokir modal yang dipicu oleh fungsi berbasis waktu.

10. Manakah kombinasi metrik kuantitatif berikut yang memberikan sinyal terkuat bahwa pengguna mengalami kebingungan arsitektur informasi (*Information Architecture Disorientation*)?
    * A) Task completion rate 100% dan bounce rate 0%.
    * B) Tingkat *Lostness Metric* tinggi, diiringi peningkatan drastis navigasi bolak-balik (*Thrashing Navigation*) dan pencarian kata kunci berulang di search bar.
    * C) Nilai *Largest Contentful Paint* (LCP) berada di bawah rentang waktu 1,2 detik.
    * D) Penurunan volume total interaksi klik harian di landing page promosi.

---

### Bagian 3: Skenario Kasus Produksi

11. **Skenario Kasus 1:**  
    Aplikasi web e-commerce Anda memiliki skor *Interaction to Next Paint* (INP) yang buruk ($> 450\text{ ms}$) pada perangkat seluler kelas menengah ke bawah. Setelah ditelusuri menggunakan *Chrome DevTools Performance Profiler*, SDK telemetri UX internal Anda teridentifikasi menjalankan skrip eksekusi penelusuran DOM (`querySelectorAll`) setiap kali terjadi interaksi klik untuk mencari atribut masking PII.  
    **Tindakan rekayasa perangkat lunak apa yang wajib Anda ambil untuk mengeliminasi latensi eksekusi ini ke level ideal ($< 50\text{ ms}$) tanpa menghilangkan fungsi sensor privasi data?**

12. **Skenario Kasus 2:**  
    Tim kepatuhan hukum (*Legal & Compliance*) menemukan bahwa pada formulir pengajuan asuransi, data sensitif riwayat medis pengguna sempat terekam ke klaster Kafka analitik selama 3 hari akibat perilisan dinamis komponen form baru yang belum disematkan atribut penanda `data-ux-mask="true"`.  
    **Bagaimana Anda merancang ulang arsitektur client-side telemetry engine agar memiliki mekanisme perlindungan ganda (*fail-safe zero-trust*) terhadap risiko kebocoran atribut form yang tidak sengaja terlewat oleh tim developer?**

13. **Skenario Kasus 3:**  
    Sebuah platform B2B SaaS mendapati bahwa tingkat respons survei kualitatif *micro-intercept* CSAT mereka merosot dari 22% menjadi hanya 1,8% dalam rentang waktu dua bulan, sementara komplain pengguna di kanal *customer support* terkait kesulitan alur kerja transaksi justru meningkat tajam.  
    **Lakukan analisis komprehensif terhadap kegagalan strategi trigger riset kualitatif ini, dan formulasikan arsitektur sistem intercept baru berbasis penyesuaian konteks perilaku (*Behavioral State Machine*)!**

---

### Kunci Jawaban & Panduan Evaluasi

#### Jawaban Bagian 1 & 2
1. **B** — `sendBeacon` didesain secara spesifik untuk memproses pengiriman data di latar belakang siklus *page unload* tanpa menghalangi pergantian dokumen.
2. **C** — *Dead Click* secara heuristik didefinisikan sebagai klik pada komponen yang terlihat interaktif tetapi tidak menghasilkan responsivitas DOM, mutasi CSS, maupun pertukaran data jaringan.
3. **B** — Sanitasi PII wajib dilakukan secara lokal pada lingkungan klien sebelum dikirimkan ke jaringan eksternal guna mematuhi prinsip kedaulatan data dan regulasi GDPR.
4. **B** — Ketiadaan flag `{ passive: true }` memaksa browser menunda eksekusi proses rendering scroll untuk memastikan tidak ada panggilan fungsi `preventDefault()`.
5. **D** — Dimensi *Task Success* pada framework HEART berfokus pada metrik keberhasilan, tingkat kesalahan, dan durasi penyelesaian alur tugas spesifik.
6. **A** — Operasi kloning mutasi DOM berskala penuh secara terus-menerus memakan siklus alokasi memori heap yang besar dan memblokir eksekusi thread utama (*Long Tasks*), menurunkan performa INP.
7. **B** — Gerakan scroll cepat yang dikombinasikan dengan waktu dwell rendah mengindikasikan komponen tersebut diabaikan (*scanned past*) oleh atensi pengguna.
8. **B** — Pendekatan *Deterministic Sampling* mengalokasikan kuota observasi berdasarkan algoritma hash identitas pengguna, menjaga representasi statistik tanpa perlu membebani infrastruktur data ingest secara penuh.
9. **B** — Trigger berbasis jeda waktu statis mengabaikan konteks pengguna, berisiko tinggi memunculkan gangguan antarmuka saat pengguna sedang berkonsentrasi penuh pada alur kerja utama.
10. **B** — Navigasi thrashing bolak-balik dipadukan dengan skor lostness yang tinggi adalah manifestasi terukur dari ketidakmampuan pengguna memahami tata letak navigasi antarmuka.

#### Panduan Jawaban Bagian 3 (Skenario Produksi)
11. **Solusi INP Optimization:**  
    * Mengganti metode `querySelectorAll` global dengan strategi traversal hierarki terbatas dari event target ke atas (`Element.closest()` atau navigasi via `parentElement` dengan kedalaman dibatasi maksimal 3–4 node).
    * Alternatif arsitektur: Pindahkan ekstraksi komputasi atribut teks ke dalam callback `requestIdleCallback` atau eksekusi melalui Web Worker sehingga thread rendering UI dapat segera merespons input sentuhan pengguna tanpa hambatan (*zero-latency interaction*).
12. **Solusi Fail-Safe Zero-Trust PII Engine:**  
    * Terapkan pendekatan *Deny-All / Whitelist-Only by Default*: Seluruh elemen input formulir (`input`, `textarea`, `select`, `[contenteditable]`) secara otomatis dianggap mengandung data rahasia (*fully redacted* secara default).
    * Nilai input hanya diperbolehkan direkam jika komponen secara eksplisit menyertakan metadata konfirmasi keamanan, misalnya: `data-ux-safe-public="true"`.
    * Tambahkan lapisan filter ekspresi reguler deterministik di sisi Edge API Gateway sebelum event dimasukkan ke message broker Kafka sebagai lapis pertahanan sekunder (*defense-in-depth*).
13. **Solusi Recovery Qualitative Intercept:**  
    * Masalah utama adalah timbulnya *Survey Fatigue* akibat trigger yang agresif dan tidak relevan, menyebabkan efek kebutaan modal (*modal blindness*).
    * Rancang ulang menggunakan *Behavioral State Machine*:
      1. Terapkan batasan global (*Global Cooldown*): Pengguna maksimal hanya boleh menerima 1 kali survei kualitatif per 30 hari kalender.
      2. Ganti trigger berbasis waktu dengan trigger berbasis kejadian masalah (*Event-Driven Heuristics*): Survei hanya muncul jika pengguna mengalami kombinasi anomali: $\ge 2$ kali *Rage Clicks* pada form error ATAU membatalkan alur checkout setelah menghabiskan waktu $> 3$ menit di layar yang sama.
      3. Format survei diubah dari tipe modal yang memblokir layar (*blocking overlay*) menjadi *non-intrusive embedded floating badge* di pojok layar yang dapat diabaikan tanpa mengganggu alur navigasi.

---

## 16. Summary

* **Rekayasa Telemetri UX Berkelanjutan:** Riset pengguna enterprise modern membutuhkan konvergensi antara data observasi kuantitatif (telemetri perilaku) dan data konteks kualitatif (intervensi mikro terprogram) yang diintegrasikan langsung ke dalam arsitektur kode frontend.
* **Performa sebagai Fondasi:** Pelacakan interaksi antarmuka tidak boleh mengorbankan performa runtime antarmuka pengguna. Pemanfaatan *Browser Primitives* yang efisien (`IntersectionObserver`, `sendBeacon`, pemrosesan non-blocking) menjamin metrik vital seperti *Interaction to Next Paint* (INP) dan stabilitas *frame rate* tetap terjaga pada standar tertinggi.
* **Privasi Bersifat Non-Negotiable:** Sanitasi PII berbasis prinsip *Zero-Trust* wajib diselesaikan di lingkungan runtime klien sebelum data meninggalkan batasan memori browser, memastikan kepatuhan regulasi privasi global tanpa bergantung pada sistem sanitasi downstream.
* **Tindakan Berbasis Anomali:** Mengidentifikasi metrik frustrasi pengguna (*rage clicks, dead clicks, thrashing navigation*) secara real-time memungkinkan otomatisasi investigasi kualitatif, mentransformasikan analitik UX dari sekadar laporan retrospektif pasif menjadi sistem perbaikan produk yang proaktif.