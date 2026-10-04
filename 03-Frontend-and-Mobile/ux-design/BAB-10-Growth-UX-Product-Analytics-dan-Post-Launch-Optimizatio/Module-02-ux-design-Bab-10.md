# BAB 10: Growth UX, Product Analytics, & Post-Launch Optimization
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Merancang dan mengimplementasikan** arsitektur telemetri *event-driven* berskala *enterprise* pada sisi klien tanpa mendegradasi *Core Web Vitals* (khususnya INP dan TBT).
- **Membangun** sistem eksperimentasi (*A/B Testing*) deterministik berbasis *edge computing* menggunakan algoritma *hashing* terdistribusi (MurmurHash3) dengan latensi sub-10ms.
- **Mengeliminasi** bias eksperimen melalui deteksi otomatis *Sample Ratio Mismatch* (SRM) dan reduksi varians menggunakan metode statistika lanjut (*Controlled Experiments Using Pre-Experiment Data* / CUPED).
- **Mengamankan** jalur transmisi data analitik produk dengan kepatuhan privasi ketat (GDPR/HIPAA) melalui *in-memory PII sanitization* dan *client-side zero-knowledge masking*.
- **Menganalisis dan mengotomatisasi** *Growth Loops* (retensi, aktivasi, reaktivasi) berbasis analisis corong (*funnel drop-off*) dan *telemetry stream processing* secara *near-real-time*.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib memiliki pemahaman mendalam tentang:
- **Advanced TypeScript & DOM Lifecycle:** Pemahaman mendalam tentang *Event Loop*, *Web Workers*, `requestIdleCallback`, `MutationObserver`, dan *Page Lifecycle API* (`freeze`, `resume`, `pagehide`).
- **Distributed Systems & Telemetry Basics:** Konsep dasar *Message Broker* (Kafka/Pulsar), *Columnar Databases* (ClickHouse/BigQuery), dan struktur *JSON Schema*.
- **Dasar Statistika Inferensial:** Distribusi normal, *p-value*, *statistical power* ($1-\beta$), ukuran sampel minimum (*Minimum Detectable Effect* / MDE), dan *confidence interval*.
- **Edge Runtimes:** Konsep eksekusi kode pada CDN *edge compute* (Cloudflare Workers, Fastly Compute, Vercel Edge Middleware).

---

### 3. Concept & Internal Architecture

Arsitektur analitik produk dan *Growth UX* modern tidak lagi mengandalkan tag skrip pihak ketiga yang disuntikkan langsung via *Tag Manager* konvensional. Pendekatan usang tersebut memicu *main-thread blocking*, *memory leak*, dan pelanggaran regulasi privasi data. Arsitektur produksi modern memisahkan sistem menjadi dua *plane*: **Data Plane (Telemetri)** dan **Control Plane (Eksperimentasi & Personalisasi)**.

```
+---------------------------------------------------------------------------------------+
|                                    CLIENT BROWSER                                     |
|                                                                                       |
|   +-------------------+    +--------------------+    +----------------------------+   |
|   |   UI Components   |--->| Growth SDK Client  |--->|   Web Worker (Off-thread)  |   |
|   | (React/Vue/Svelte)|    | (MurmurHash3 Edge) |    |  - PII Scrubbing Engine    |   |
|   +-------------------+    +--------------------+    |  - Schema Validation       |   |
|             ^                        |               |  - Compression (gzip/zstd) |   |
|             |                        v               +----------------------------+   |
|             |              +--------------------+                  |                  |
|             |              | IndexedDB Buffer   |                  v                  |
|             |              | (Offline Fallback) |         +-----------------+         |
|             |              +--------------------+         |  Fetch KeepAlive|         |
|             |                                             | / sendBeacon    |         |
|             |                                             +-----------------+         |
+-------------|------------------------------------------------------|------------------+
              |                                                      |
       Flag Assignment                                          HTTP POST Batch
       Sub-10ms Cache                                                |
              |                                                      v
+-------------------------------+                     +---------------------------------+
|      EDGE MIDDLEWARE          |                     |    INGESTION GATEWAY            |
| (Cloudflare / Edge Functions) |                     |  (Reverse Proxy / Rust Envoy)   |
+-------------------------------+                     +---------------------------------+
              ^                                                      |
              | Sync Metadata Config                                 v
+-------------------------------+                     +---------------------------------+
| CONTROL PLANE SERVICE         |                     | EVENT STREAM (Kafka/Pulsar)     |
| - Experiment Registry (CUPED) |                     +---------------------------------+
| - Feature Flags & Segments    |                                    |
| - PII Scrubbing Rules         |                                    v
+-------------------------------+                     +---------------------------------+
                                                      | REAL-TIME ANALYTICS ENGINE      |
                                                      | (ClickHouse / OLAP Storage)     |
                                                      +---------------------------------+
```

#### Komponen Kunci Arsitektur

1. **Deterministic Edge Hashing (Experiment Assignment Engine):**
   Untuk menghindari *flicker effect* (Cumulative Layout Shift) dan latensi jaringan, penentuan varian eksperimen dihitung secara deterministik menggunakan fungsi hash (seperti MurmurHash3 32-bit). Rumusnya:
   $$\text{Variant Index} = \text{MurmurHash3}(\text{UserID} + \text{ExperimentKey}) \pmod{100}$$
   Hasil *hashing* menghasilkan *bucket value* (0–99). Jika varian A dialokasikan untuk 0–49 dan varian B untuk 50–99, alokasi pengguna selalu konsisten secara stateless di seluruh *edge nodes* tanpa perlu melakukan *database lookup*.

2. **Decoupled Telemetry Pipeline (Data Plane):**
   *Event tracking* tidak boleh mengeksekusi I/O langsung pada *main thread*. SDK mengoperasikan *in-memory ring buffer*. Event dialirkan ke *Web Worker* untuk validasi skema (JSON Schema) dan sanitasi PII (*Personally Identifiable Information*). Jika browser mendadak dimatikan (*page unload*), data dievakuasi menggunakan API `navigator.sendBeacon()` atau `fetch` dengan opsi `keepalive: true`.

3. **Resilience & Storage Engine:**
   Jika perangkat berada dalam kondisi *offline* atau jaringan tidak stabil, *Worker* menulis event ke `IndexedDB`. Ketika konektivitas pulih, sinkronisasi dijalankan secara bertahap (*exponential backoff with jitter*) untuk mencegah skenario *thundering herd* pada *ingestion gateway*.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional | Pendekatan Enterprise Modern |
| :--- | :--- | :--- |
| **Integrasi Eksperimen** | *Client-side DOM rewriting* via script tag eksternal (Optimizely/VWO lama). | *Edge-rendered assignment* atau *Stateless isomorphic deterministic hashing*. |
| **Metrik Web Vitals** | Menyebabkan CLS tinggi (*flickering* UI) dan mendegradasi TBT/INP. | Zero CLS (*pre-rendered* di edge), TBT = 0ms (komputasi di luar *main thread*). |
| **Pengiriman Telemetri** | Pengiriman synchronous HTTP POST via XHR/Fetch langsung pada interaksi pengguna. | *Micro-batched*, dialirkan melalui *Dedicated Web Worker*, menggunakan `sendBeacon` saat terminasi. |
| **Kepatuhan Privasi** | Sanitasi dilakukan di server setelah data ditransmisikan. | *Zero-trust client-side scrubbing*; data PII tidak pernah keluar dari memori browser pengguna. |
| **Validasi Skema Data** | *Unstructured loose JSON*, rentan *data pollution* dan inkonsistensi penamaan. | Skema ketat berbasis *Contract-First* (TypeScript types yang divalidasi via *JSON Schema/TypeBox*). |

---

### 5. How (Workflow Detail)

Alur kerja evaluasi eksperimen hingga analitik corong berjalan melalui siklus berikut:

```
[User Navigate] 
       │
       ▼
[Edge Worker Evaluates Cookie/Header] 
       │
       ├─► (Known User) ──► Compute MurmurHash3(userId + expKey) ──┐
       │                                                          │
       └─► (New User)   ──► Generate anonymousId & Assign Hash ───┤
                                                                   │
       ┌───────────────────────────────────────────────────────────┘
       ▼
[Inject Experiment Metadata into Request Context / HTML Headers]
       │
       ▼
[Client Hydrates with Assigned Variant (Zero UI Flicker)]
       │
       ▼
[User Triggers Action (e.g., CTA Click)]
       │
       ▼
[SDK Enqueues Event to Ring Buffer]
       │
       ▼
[Worker Intercepts: Scrub PII -> Validate Schema -> Batch]
       │
       ├─► [Network Online]  ──► POST payload to Gateway (gzip)
       │
       └─► [Network Offline] ──► Persist payload to IndexedDB
                                        │
                                        └──► Retry on 'online' event
```

---

### 6. Analogy & Diagram ASCII

Bayangkan eksperimen dan telemetri seperti sistem **Pintu Masuk Gerbang Tol Otomatis (A/B Testing)** dan **Sensor Jembatan Timbang Truk (Telemetri Analitik)**:

- **Eksperimentasi Konvensional:** Mobil mendekati gerbang, berhenti total, supir membuka jendela, satpam menelepon kantor pusat untuk bertanya mobil harus masuk jalur mana, lalu mobil disuruh pindah jalur mendadak (menimbulkan kemacetan / CLS & latensi tinggi).
- **Arsitektur Deterministic Edge:** Plat nomor mobil dipindai kamera secara instan di gerbang luar. Komputer gerbang menerapkan algoritma matematika sederhana pada angka plat nomor tanpa membuka koneksi internet, lalu lampu hijau instan mengarahkan mobil ke jalur A atau B secara mulus tanpa berhenti sekejap pun.
- **Telemetri Modern:** Setiap pergerakan mobil di jalan tol dicatat oleh sensor jalan dan dikumpulkan ke pos penampungan lokal (Web Worker & IndexedDB). Setelah 50 mobil melintas atau 5 detik berlalu, data dikirim secara kolektif menggunakan helikopter logistik (*batch HTTP*), bukan mengirim satu kurir motor untuk setiap satu mobil yang melintas.

```
          Algoritma MurmurHash3 (Stateless Bucket)
User UUID: "u-9843-abcd" + Exp: "checkout_v2"
                      │
                      ▼
            [ MurmurHash3 Engine ]
                      │
                      ▼
            Hash Output: 2,748,913,541
                      │
                      ▼  Modulus 100
             Bucket Value: 41
                      │
       ┌──────────────┴──────────────┐
       ▼                             ▼
 [Bucket 0 - 49]              [Bucket 50 - 99]
    Control                     Treatment
(Variant Alpha)               (Variant Beta)
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Telemetry Transport Engine Menggunakan `sendBeacon` & Lifecycle Handling

```typescript
// TelemetryBeacon.ts
export interface TelemetryPayload {
  eventName: string;
  properties: Record<string, unknown>;
  timestamp: number;
}

export class TelemetryBeacon {
  private endpoint: string;

  constructor(endpoint: string) {
    this.endpoint = endpoint;
  }

  public track(eventName: string, properties: Record<string, unknown> = {}): void {
    const payload: TelemetryPayload = {
      eventName,
      properties,
      timestamp: Date.now(),
    };

    const serializedData = JSON.stringify(payload);

    // Prioritaskan sendBeacon untuk keandalan unload, fallback ke fetch keepalive
    if (navigator.sendBeacon) {
      const blob = new Blob([serializedData], { type: 'application/json' });
      const success = navigator.sendBeacon(this.endpoint, blob);
      if (!success) {
        this.fallbackFetch(serializedData);
      }
    } else {
      this.fallbackFetch(serializedData);
    }
  }

  private fallbackFetch(body: string): void {
    fetch(this.endpoint, {
      method: 'POST',
      body,
      headers: { 'Content-Type': 'application/json' },
      keepalive: true,
    }).catch((err) => console.error('[Telemetry] Fallback dispatch failed', err));
  }
}
```

#### Practical Example: Production-Ready Edge Experiment Hashing Engine & Telemetry Pipeline

File ini mengimplementasikan algoritma deterministik MurmurHash3 dan sistem antrean telemetri berbasis *IndexedDB backoff* dengan penapisan PII otomatis.

```typescript
// ProductionGrowthEngine.ts

/**
 * 1. DETERMINISTIC MURMURHASH3 (32-bit Implementation)
 * Menghitung hash integer 32-bit tanpa dependensi eksternal.
 */
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

/**
 * 2. EXPERIMENT ENGINE
 */
export interface ExperimentConfig {
  key: string;
  variants: { name: string; weight: number }[]; // Bobot dalam persentase (total 100)
}

export class ExperimentAssignmentEngine {
  public static getVariant(userId: string, experiment: ExperimentConfig): string {
    const hashInput = `${userId}:${experiment.key}`;
    const hash = murmurhash3_32_gc(hashInput);
    const bucket = hash % 100; // 0..99

    let accumulatedWeight = 0;
    for (const variant of experiment.variants) {
      accumulatedWeight += variant.weight;
      if (bucket < accumulatedWeight) {
        return variant.name;
      }
    }
    return experiment.variants[0].name; // Default fallback
  }
}

/**
 * 3. PRODUCTION RESILIENT TELEMETRY AGENT
 */
export interface EventContract {
  eventId: string;
  userId: string;
  eventName: string;
  schemaVersion: number;
  traits: Record<string, unknown>;
  timestamp: number;
}

export class EnterpriseTelemetryQueue {
  private queue: EventContract[] = [];
  private flushThreshold: number = 10;
  private flushIntervalMs: number = 3000;
  private timer: number | null = null;
  private endpoint: string;
  private piiBlacklist: RegExp[] = [
    /password/i,
    /email/i,
    /token/i,
    /credit_?card/i,
    /cvv/i,
    /phone/i,
  ];

  constructor(endpoint: string) {
    this.endpoint = endpoint;
    this.initLifecycle();
  }

  private initLifecycle(): void {
    if (typeof window !== 'undefined') {
      window.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'hidden') {
          this.flush();
        }
      });
      window.addEventListener('pagehide', () => this.flush());
    }
    this.scheduleFlush();
  }

  private scheduleFlush(): void {
    if (typeof window !== 'undefined') {
      this.timer = window.setTimeout(() => {
        this.flush();
        this.scheduleFlush();
      }, this.flushIntervalMs);
    }
  }

  private sanitizeTraits(traits: Record<string, unknown>): Record<string, unknown> {
    const cleaned: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(traits)) {
      const isBlacklisted = this.piiBlacklist.some((rx) => rx.test(key));
      if (isBlacklisted) {
        cleaned[key] = '[REDACTED]';
      } else if (typeof value === 'object' && value !== null) {
        cleaned[key] = this.sanitizeTraits(value as Record<string, unknown>);
      } else {
        cleaned[key] = value;
      }
    }
    return cleaned;
  }

  public track(userId: string, eventName: string, traits: Record<string, unknown>): void {
    const payload: EventContract = {
      eventId: crypto.randomUUID(),
      userId,
      eventName,
      schemaVersion: 1,
      traits: this.sanitizeTraits(traits),
      timestamp: Date.now(),
    };

    this.queue.push(payload);

    if (this.queue.length >= this.flushThreshold) {
      this.flush();
    }
  }

  public flush(): void {
    if (this.queue.length === 0) return;

    const itemsToSend = [...this.queue];
    this.queue = [];

    const body = JSON.stringify({ batch: itemsToSend });

    if (navigator.sendBeacon) {
      const blob = new Blob([body], { type: 'application/json' });
      const success = navigator.sendBeacon(this.endpoint, blob);
      if (!success) {
        this.executeFetch(body, itemsToSend);
      }
    } else {
      this.executeFetch(body, itemsToSend);
    }
  }

  private executeFetch(body: string, fallbackItems: EventContract[]): void {
    fetch(this.endpoint, {
      method: 'POST',
      body,
      headers: { 'Content-Type': 'application/json' },
      keepalive: true,
    }).catch(() => {
      // Re-queue ke depan antrean jika pengiriman gagal akibat fluktuasi jaringan
      this.queue = [...fallbackItems, ...this.queue];
    });
  }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario: Redesain Alur Checkout & Migrasi Eksperimen pada Platform Fintech Unicorn

* **Konteks:** Perusahaan fintech dengan 15 juta *Monthly Active Users* (MAU) merancang perombakan arsitektur checkout untuk meningkatkan konversi metode pembayaran instan.
* **Tantangan:** 
  1. *Flickering UI* akibat script A/B testing pihak ketiga menyebabkan metrik CLS melonjak hingga `0.32` (kategori *Poor*), menurunkan skor Google Search Page Experience.
  2. Ditemukan anomali *Sample Ratio Mismatch* (SRM) dengan $p < 0.001$, di mana kelompok *Treatment* menerima rasio pengguna browser mobile 20% lebih sedikit daripada *Control*.
  3. Latensi checkout meningkat 180ms karena pelacakan telemetri dijalankan secara sinkron sebelum navigasi diarahkan ke *Payment Gateway*.

#### Analisis Akar Masalah (Root Cause Analysis)
1. **Penyebab CLS:** Script A/B testing disuntikkan secara asinkron; saat DOM selesai dirender, script membaca varian lalu memanipulasi elemen via `document.querySelector().innerHTML`, menyebabkan pergeseran layout masif.
2. **Penyebab SRM:** Edge proxy mengalami kegagalan saat mengevaluasi kondisi HTTP user-agent pada perangkat berspesifikasi rendah, memicu *fail-open* otomatis yang menjatuhkan pengguna kembali ke kelompok *Control*.
3. **Penyebab Latensi Checkout:** Komponen tombol checkout memasang `e.preventDefault()`, mengirimkan telemetri menggunakan `await fetch()`, dan baru mengeksekusi *redirect* setelah menerima respons 200 OK dari server analitik.

#### Solusi Rekayasa
1. **Edge-Driven Deterministic Allocation:** Logika pembagian varian dipindahkan langsung ke *Edge Middleware* (Cloudflare Workers). Cookie eksperimen dievaluasi langsung di edge node terdekat. Dokumen HTML yang dikirim ke browser sudah memuat layout spesifik dari varian yang ditugaskan (*zero-flicker*, CLS turun menjadi `0.002`).
2. **SRM Real-Time Alerting Engine:** Menerapkan uji statistik Chi-Square Pearson ($\chi^2$) secara otomatis pada stream ClickHouse. Jika rasio alokasi terdistribusi di luar toleransi toleransi $p < 0.01$, sistem *flagging* otomatis membekukan eksperimen untuk mencegah kesimpulan yang salah.
3. **Decoupled Non-Blocking Tracking:** Menghapus pencegahan navigasi default. Tombol checkout memicu `TelemetryQueue.track()` yang mendistribusikan muatan data melalui `navigator.sendBeacon` secara *background non-blocking*.

```
HASIL METRIK UTAMA SETELAH 30 HARI:
┌─────────────────────────────────┬──────────────────┬──────────────────┐
│ Metrik                          │ Sebelum Optimasi │ Sesudah Optimasi │
├─────────────────────────────────┼──────────────────┼──────────────────┤
│ Cumulative Layout Shift (CLS)   │ 0.32 (Buruk)     │ 0.002 (Bagus)    │
│ Interaction to Next Paint (INP) │ 340ms            │ 48ms             │
│ Checkout Drop-off Rate          │ 14.8%            │ 9.1%             │
│ SRM Anomalies Detected          │ 4 Kasus / Kuartal│ 0 Kasus Lolos    │
│ Total Conversion Rate Uplift    │ Base             │ +5.2% (p=0.004)  │
└─────────────────────────────────┴──────────────────┴──────────────────┘
```

---

### 9. Trade-offs

Setiap keputusan arsitektur telemetri dan eksperimen membawa konsekuensi struktural:

| Keputusan Arsitektur | Keuntungan | Biaya / Kerugian | Rekomendasi Kontekstual |
| :--- | :--- | :--- | :--- |
| **Edge-Compute Flagging** | Latensi sub-10ms, eliminasi CLS, tidak ada komputasi berulang di client. | Biaya CDN Edge Workers bertambah seiring peningkatan *request volume*. | Wajib untuk halaman kritis konversi (*Landing pages*, *Checkout funnel*). |
| **Worker-Based Telemetry** | Beban komputasi JSON serialization & PII scrubbing lepas dari *main thread*. | Overhead inisialisasi Worker (~20-40ms); kompleksitas transfer objek via `postMessage`. | Terapkan jika volume telemetri per sesi > 50 event atau menyertakan session recording. |
| **Batching Micro-Queue** | Mengurangi beban request server & menghemat konsumsi daya baterai perangkat. | Potensi kehilangan sejumlah kecil data terakhir jika browser ditutup paksa (*crash* OS). | Gunakan interval flush $\le$ 3000ms yang dipadukan dengan handler `visibilitychange`. |
| **CUPED Variance Reduction** | Mempersingkat durasi eksperimen hingga ~40-50% untuk mencapai signifikansi statistik. | Membutuhkan pipeline data terpadu untuk mengekstrak metrik *pre-experiment* pengguna. | Terapkan pada eksperimen produk yang memiliki basis pengguna aktif reguler. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Mengabaikan Sample Ratio Mismatch (SRM)
* **Gejala:** Varian treatment menunjukkan peningkatan konversi masif (+40%), tetapi setelah diluncurkan ke 100% pengguna, konversi bisnis justru turun.
* **Investigasi:** Jalankan uji statistik Chi-Square goodness-of-fit antara sampel aktual ($O$) dan sampel ekspektasi ($E$):
  $$\chi^2 = \sum \frac{(O_i - E_i)^2}{E_i}$$
* **Solusi:** Jika nilai $\chi^2$ menghasilkan $p < 0.01$, data terkontaminasi (misal: bot filter hanya memblokir varian tertentu, atau varian tertentu *crash* di Safari). Buang hasil eksperimen dan audit pipeline alokasi edge.

#### Kesalahan 2: Menggunakan Event Listener `unload` untuk Telemetri Terakhir
* **Gejala:** Data drop-off pada langkah akhir funnel hilang hingga 25-30% pada browser berbasis Chromium dan WebKit mobile.
* **Investigasi:** Event `unload` dan `beforeunload` telah ditinggalkan (*deprecated*) dan tidak dapat diandalkan pada arsitektur browser modern karena proses dapat langsung diterminasi oleh *Process-Per-Tab Model*.
* **Solusi:** Gunakan event `visibilitychange` (kondisi `document.visibilityState === 'hidden'`) atau `pagehide` bersama dengan `navigator.sendBeacon`.

#### Kesalahan 3: PII Leakage ke Platform Analytics
* **Gejala:** Alamat email atau nomor telepon pengguna muncul pada URL parameter atau atribut *traits* di dasbor analisis pihak ketiga.
* **Investigasi:** Form checkout menyertakan *auto-tracking* DOM klik yang merekam nilai `input.value` secara tidak sengaja.
* **Solusi:** Pasang *zero-trust sanitization regex layer* di level SDK (lihat *Practical Example*) dan matikan pengumpulan teks otomatis (*unconstrained input capture*) pada alat perekam sesi.

---

### 11. Best Practices (Production Checklist)

#### Kode & Performa
- [ ] Logika eksperimen dijalankan tanpa manipulasi DOM pasca-render (*Zero CLS*).
- [ ] Ukuran payload SDK analitik < 15KB (gzipped).
- [ ] Tidak ada eksekusi `JSON.stringify` berukuran besar secara sinkron di *main thread*.
- [ ] Gunakan `navigator.sendBeacon` atau `fetch` dengan `keepalive: true` untuk panggilan pemutus sesi.

#### Keamanan & Kepatuhan
- [ ] Masking PII aktif secara default pada layer SDK (*client-side*).
- [ ] Setiap event telemetri divalidasi terhadap kontrak skema ketat (*strict schema*) sebelum dikirim.
- [ ] Mekanisme *opt-in/opt-out* (Consent Management) terintegrasi ke dalam *lifecycle* SDK.

#### Observabilitas & Metrik
- [ ] Pengecekan otomatis SRM dihitung secara terjadwal pada level analitik.
- [ ] Metrik Web Vitals dihubungkan langsung ke *event properties* untuk mendeteksi degradasi performa antar varian.
- [ ] Rasio kegagalan jaringan pengiriman telemetri (*telemetry drop-rate*) dipantau di bawah ambang batas < 0.5%.

---

### 12. Hands-on Practice

Buatlah struktur folder `hands-on/m02/` dan selesaikan skenario implementasi berikut:

#### Struktur Proyek
```
hands-on/m02/
├── package.json
├── tsconfig.json
├── src/
│   ├── experiment/
│   │   ├── MurmurHash.ts
│   │   └── Engine.ts
│   ├── telemetry/
│   │   ├── Contract.ts
│   │   ├── Sanitizer.ts
│   │   └── Queue.ts
│   └── index.ts
└── tests/
    └── experiment.test.ts
```

#### Langkah-langkah Praktikum

1. **Inisialisasi Project:**
   ```bash
   mkdir -p hands-on/m02/src/experiment hands-on/m02/src/telemetry hands-on/m02/tests
   cd hands-on/m02
   npm init -y
   npm install typescript @types/node ts-node jest @types/jest ts-jest --save-dev
   npx tsc --init
   ```

2. **Implementasikan Logika MurmurHash3 & Engine:**
   Salin logika fungsi hash dari *Practical Example* ke dalam `src/experiment/MurmurHash.ts`.
   Implementasikan penentuan varian pada `src/experiment/Engine.ts`.

3. **Implementasikan Sanitasi PII & Antrean Telemetri:**
   Tulis modul pembersih data pada `src/telemetry/Sanitizer.ts` yang mampu mendeteksi dan melakukan *redaction* format email, nomor kartu kredit, dan pola nama parameter terlarang.
   Bangun *Queue Manager* pada `src/telemetry/Queue.ts` dengan penanganan *batching*.

4. **Uji Validitas Distribusi:**
   Tulis unit test pada `tests/experiment.test.ts` untuk memverifikasi bahwa 10,000 UUID yang dihasilkan secara acak terdistribusi secara seimbang pada eksperimen alokasi 50:50 dengan toleransi deviasi statistik < 2%.

---

### 13. Exercise

#### Level: Easy
Implementasikan fungsi utilitas TypeScript `validateEventContract(payload: unknown, schema: JSONSchema): boolean` yang memverifikasi atribut minimal: `eventId` (UUID), `userId` (string), `timestamp` (number), dan membuang properti tambahan yang tidak terdaftar (*strip undeclared properties*).

#### Level: Medium
Bangun *custom React hook* `useExperiment(experimentKey: string, variants: VariantConfig[])` yang:
1. Membaca identitas pengguna dari Context.
2. Mengevaluasi varian secara deterministik (menggunakan MurmurHash3) saat render pertama tanpa memicu re-render tambahan.
3. Mengirimkan event telemetri `Experiment_Viewed` tepat satu kali (*idempotent*) per siklus hidup halaman.

#### Level: Hard
Rancang modul kalkulasi **Chi-Square Sample Ratio Mismatch (SRM) Detector** dalam TypeScript murni:
1. Fungsi menerima input: `observed: number[]` dan `expectedRatios: number[]`.
2. Menghitung statistik uji $\chi^2$.
3. Mengestimasi derajat kebebasan (*degrees of freedom*).
4. Menghitung aproksimasi *p-value* menggunakan fungsi distribusi kumulatif Chi-Square.
5. Mengembalikan boolean `hasSRM: true` jika $p < 0.01$.

---

### 14. Challenge

**Skenario Rekayasa:**
Anda adalah Principal Frontend Architect di sebuah platform *SaaS Enterprise* multi-tenant. Pengguna sering beralih antara beberapa tab kerja secara bersamaan, bekerja dalam mode offline di pesawat, dan memiliki batasan regulasi data perbankan yang ketat.

**Spesifikasi Masalah:**
Rancang dan bangun arsitektur sistem SDK terintegrasi (*Growth & Telemetry*) yang:
1. Menggunakan **SharedWorker** sebagai sentral sinkronisasi antar beberapa browser tab yang terbuka, sehingga koneksi telemetri dan batched dispatch hanya dieksekusi oleh tepat satu tab (*Leader Election* pattern).
2. Jika browser tidak mendukung *SharedWorker*, secara otomatis *fallback* ke kombinasi `BroadcastChannel` dan `IndexedDB`.
3. Memastikan bahwa dalam skenario *hard crash* (misal proses browser dihentikan via Task Manager), data interaksi sebelum terminasi tersimpan di media persisten dan otomatis dikirimkan saat aplikasi dibuka kembali pada sesi berikutnya.
4. Terapkan algoritma kompresi data sisi klien menggunakan *Compression Streams API* (`gzip`) sebelum data dipancarkan ke jaringan untuk menghemat bandwidth pengguna seluler.

**Deliverable Arsitektur:**
Diagram alur detail state machine penanganan worker, struktur penyimpanan IndexedDB, kode implementasi isolasi kompresi, serta mitigasi *race conditions* saat beberapa tab mencoba mengosongkan antrean data yang sama.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Tunggal / Singkat)
1. Mengapa algoritma MurmurHash3 lebih dipilih daripada SHA-256 untuk penentuan varian A/B testing di sisi klien/edge?
2. Kapan sebaiknya Anda menggunakan `navigator.sendBeacon()` dibandingkan `fetch()` biasa?
3. Event browser siklus hidup (*lifecycle*) mana yang paling andal untuk menandai evakuasi data telemetri terakhir sebelum tab ditutup?
4. Apa yang dimaksud dengan *flicker effect* pada eksperimen A/B testing dan bagaimana edge routing mengatasinya?
5. Mengapa penyimpanan sementara telemetri offline lebih direkomendasikan menggunakan `IndexedDB` daripada `localStorage`?

#### Bagian 2: Intermediate (Analisis Konseptual)
6. Jelaskan bagaimana anomali *Sample Ratio Mismatch* (SRM) dapat menghasilkan keputusan bisnis yang salah meskipun metrik $p$-value menunjukkan signifikansi ($p < 0.05$).
7. Bagaimana integrasi metode CUPED (*Controlled Experiments Using Pre-Experiment Data*) dapat mengurangi varians metrik eksperimen?
8. Mengapa sanitasi PII (*Personally Identifiable Information*) wajib dieksekusi pada *main/worker thread* klien sebelum data masuk ke jaringan transmisi?
9. Jelaskan mekanisme kerja `requestIdleCallback` dalam konteks penjadwalan pemrosesan antrean telemetri analitik.
10. Sebutkan kelemahan utama penggunaan *Client-Side DOM Injection* via tag manager pihak ketiga ditinjau dari metrik *Interaction to Next Paint* (INP).

#### Bagian 3: Skenario Kasus Produksi
11. **Kasus A:** Sebuah situs e-commerce melaporkan peningkatan rasio pentalan (*bounce rate*) sebesar 8% sesaat setelah mengaktifkan script analitik baru. Dari analisis DevTools, TBT (*Total Blocking Time*) naik dari 50ms menjadi 420ms. Langkah profiling dan perbaikan apa yang harus Anda ambil pada arsitektur tracking Anda?
12. **Kasus B:** Eksperimen alokasi 50:50 pada alur pendaftaran menunjukkan pembagian aktual: Control = 48,200 pengguna, Treatment = 51,800 pengguna dari total 100,000 partisipan. Apakah eksperimen ini valid untuk diambil kesimpulannya? Buktikan dasar analisis Anda.
13. **Kasus C:** Pengguna melaporkan bahwa saat jaringan mereka terputus di tengah pengisian formulir multi-tahap dan terhubung kembali, event telemetri membanjiri server secara serentak sehingga memicu status respons HTTP `429 Too Many Requests`. Mekanisme apa yang harus ditambahkan pada SDK klien untuk mengatasinya?

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Bagian 1
1. **MurmurHash3 vs SHA-256:** MurmurHash3 adalah algoritma *non-cryptographic* yang sangat cepat (latensi komputasi mikrodetik, CPU cost minimal) dengan sifat distribusi uniform yang sangat baik untuk bucketing, sedangkan SHA-256 memiliki beban komputasi kriptografis yang tinggi dan tidak diperlukan untuk alokasi varian.
2. **Penggunaan `sendBeacon`:** Digunakan saat proses pembongkaran halaman (*page unload/hide*), karena browser menjamin pengiriman data secara asinkron di background tanpa menahan thread penutupan halaman.
3. **Lifecycle Event Paling Andal:** `visibilitychange` (saat `document.visibilityState === 'hidden'`).
4. **Flicker Effect:** Terjadinya pergeseran tampilan elemen UI asli sebelum digantikan oleh varian modifikasi script client-side; Edge routing menyelesaikannya dengan menyuntikkan varian langsung ke HTML sebelum dokumen tiba di browser pengguna.
5. **IndexedDB vs localStorage:** IndexedDB bersifat asinkron (tidak memblokir main thread), memiliki batas kuota penyimpanan jauh lebih besar (>50MB vs ~5MB), dan mendukung struktur data transaksional yang kompleks.

#### Bagian 2
6. **Dampak SRM:** SRM mengindikasikan adanya bias seleksi sistematis (misal: varian tertentu crash pada versi OS tertentu sehingga data pengguna tersebut tidak masuk). Akibatnya, perbandingan antar kelompok tidak lagi *ceteris paribus* (apel-ke-apel), membuat nilai signifikansi statistik menjadi tidak valid.
7. **CUPED:** Menggunakan data kovariat pengguna dari masa sebelum eksperimen berjalan untuk menghilangkan varians alami yang sudah ada sebelumnya, sehingga *noise* mengecil dan efek murni dari perlakuan (*treatment*) dapat dideteksi lebih cepat.
8. **Sanitasi PII di Klien:** Untuk mematuhi prinsip *privacy-by-design* dan regulasi hukum (GDPR/HIPAA); jika PII dikirim mentah, data tersebut berisiko terekspos di log server jaringan, proxy, atau tersimpan di sistem pihak ketiga tanpa enkripsi.
9. **`requestIdleCallback`:** Memungkinkan SDK menunda proses serialisasi atau batching data hingga CPU browser memiliki waktu luang (*idle*), sehingga tidak bersaing dengan interaksi animasi atau input pengguna di *main thread*.
10. **Kelemahan Tag Manager terhadap INP:** Menyisipkan handler mutasi DOM global dan script tracking pihak ketiga yang berat secara sinkron, memperpanjang durasi antrean pemrosesan event pada *main thread* yang secara langsung memperburuk metrik responsivitas INP.

#### Bagian 3
11. **Analisis Kasus A:**
    * *Profiling:* Buka tab Performance di Chrome DevTools, cari *Long Tasks* (>50ms) yang dipicu oleh fungsi tracking analitik.
    * *Tindakan Perbaikan:* Pindahkan logika sanitasi PII dan serialisasi JSON ke *Dedicated Web Worker*. Ganti direct tracking pada click listener dengan *event delegation*, dan gunakan *micro-batching* alih-alih melakukan *fetch* individual pada setiap interaksi.
12. **Analisis Kasus B:**
    * Hitung Chi-Square ($\chi^2$):
      $$E_1 = 50,000, \quad O_1 = 48,200$$
      $$E_2 = 50,000, \quad O_2 = 51,800$$
      $$\chi^2 = \frac{(48,200 - 50,000)^2}{50,000} + \frac{(51,800 - 50,000)^2}{50,000} = \frac{(-1,800)^2}{50,000} + \frac{(1,800)^2}{50,000} = \frac{3,240,000}{50,000} \times 2 = 64.8 + 64.8 = 129.6$$
    * Untuk 1 degree of freedom, batas kritis pada signifikansi $\alpha = 0.01$ adalah $6.635$. Nilai $\chi^2 = 129.6$ menghasilkan $p \ll 0.00001$.
    * *Kesimpulan:* Terjadi **Sample Ratio Mismatch masif**. Hasil eksperimen **TIDAK VALID** dan tidak boleh digunakan untuk pengambilan keputusan.
13. **Analisis Kasus C:**
    * Tambahkan algoritma **Exponential Backoff dengan Full Jitter** pada antrean flush:
      $$T_{\text{delay}} = \min(M, T_{\text{base}} \times 2^{\text{attempt}}) \times \text{random}(0, 1)$$
    * Batasi kapasitas flush per gelombang (*rate-limiting/batch sizing limit*, misal maksimal 20 event per request) dan ratakan jadwal pengiriman (*request smoothing*) di sisi SDK klien.

---

### 16. Summary

1. Arsitektur *Growth UX* dan analitik enterprise modern menuntut pemisahan mutlak antara logika tampilan dan eksekusi telemetri, bergeser dari manipulasi DOM sisi klien yang lambat ke evaluasi deterministik berbasis *Edge Computing*.
2. Penggunaan algoritma stateless seperti **MurmurHash3** memungkinkan alokasi varian A/B testing secara konsisten, deterministik, dan berlatensi ultra-rendah tanpa *flicker effect* (CLS = 0).
3. Jalur data telemetri harus dirancang tahan banting (*resilient*) menggunakan *Web Workers*, penampungan *IndexedDB*, sanitasi privasi PII otomatis sebelum transit, dan transmisi menggunakan `navigator.sendBeacon` atau `fetch keepalive`.
4. Integritas eksperimen wajib divalidasi secara real-time terhadap indikator bias seperti **Sample Ratio Mismatch (SRM)** agar keputusan optimasi produk pasca-peluncuran didasarkan pada signifikansi data statistik yang valid dan terbebas dari artefak rekayasa sistem.