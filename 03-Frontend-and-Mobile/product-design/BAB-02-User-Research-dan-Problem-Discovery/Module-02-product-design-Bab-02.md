# Kurikulum Enterprise: Product Design & Engineering
## Kategori: 03-Frontend-and-Mobile
### BAB-02: User Research dan Problem Discovery
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik pada level Enterprise Product Designer & Staff/Principal Engineer diharapkan mampu:
- **Merancang & Mengimplementasikan** arsitektur *Continuous User Discovery Telemetry* yang menghubungkan perilaku pengguna di frontend/mobile client dengan *event pipeline* secara *real-time* dan *privacy-compliant* (GDPR/CCPA/UU PDP).
- **Membangun** sistem *Schema-Driven Product Analytics* menggunakan JSON Schema/Protocol Buffers untuk mencegah *schema drift* antara Product Design, Analytics, dan Engineering.
- **Mengembangkan** mekanisme *Behavioral Intercept Engine* (programmatic micro-surveys, dynamic qualitative intercept) berdasarkan *heuristik friksi interaksi* (misal: *rage clicks*, *dead clicks*, *excessive form backtracking*).
- **Mengevaluasi & Mengoptimalkan** *trade-off* performa, privasi, dan reliabilitas pada pengumpulan data riset pengguna (telemetri, *session replay masking*, dan *painted-door tests*).

---

### 2. Prerequisite
- Pemahaman mendalam tentang siklus Product Discovery (Dual-Track Agile, Continuous Discovery Habits oleh Teresa Torres).
- Pemahaman tingkat lanjut mengenai DOM Event Model, Mobile Lifecycle Events, dan Web Performance Metrics (Core Web Vitals).
- Pengalaman dengan arsitektur data event-driven (Event Emitters, Stream Ingestion dasar seperti Kafka/Kinesis atau REST-based ingestion proxies).
- Kemampuan membaca dan menulis TypeScript tingkat lanjut (Generics, Type Narrowing, AST dasar) dan Node.js/Edge Runtime logic.

---

### 3. Concept & Internal Architecture (Mendalam)

Implementasi modern dari *User Research & Problem Discovery* pada skala enterprise tidak lagi bertumpu pada wawancara ad-hoc manual tiap kuartal, melainkan bergeser ke **Continuous Discovery Architecture**. Arsitektur ini menyatukan sinyal kuantitatif (telemetri telemetrik, *funnel metrics*, *interaction anomalies*) dengan intervensi kualitatif terprogram (*in-app contextual inquiry*, *dynamic session replay triggers*).

```
+-----------------------------------------------------------------------------------+
|                            CLIENT TIER (Web / Mobile)                             |
|  +--------------------+  +----------------------+  +---------------------------+  |
|  | User Interactions  |  | Interaction Friction |  | Session Replay Engine     |  |
|  | (Clicks, Inputs)   |  | Detector (Rage/Dead) |  | (DOM Mutation + PII Mask) |  |
|  +---------+----------+  +----------+-----------+  +-------------+-------------+  |
|            |                        |                            |                |
|            +-------------------+    |    +-----------------------+                |
|                                |    |    |                                        |
|                                v    v    v                                        |
|                   +-------------------------------+                               |
|                   | Discovery Telemetry SDK Core  |                               |
|                   |  - Schema Contract Validation |                               |
|                   |  - PII Scrubbing / Redaction  |                               |
|                   |  - Offline Buffer & Batching  |                               |
|                   +---------------+---------------+                               |
+-----------------------------------|-----------------------------------------------+
                                    | HTTPS / Beacon API
                                    v
+-----------------------------------------------------------------------------------+
|                        EDGE / INGESTION GATEWAY TIER                              |
|  +-----------------------------------------------------------------------------+  |
|  | Edge Worker (Cloudflare / Fastly / Envoy Proxy)                             |  |
|  |  - TLS Termination & Geolocation Enrichment                                 |  |
|  |  - Strict Schema Validation against Central Registry                        |  |
|  |  - Synthetic Bot Redaction & Rate Limiting                                  |  |
|  +-------------------------------------+---------------------------------------+  |
+----------------------------------------|------------------------------------------+
                                         | Stream Ingest
                                         v
+-----------------------------------------------------------------------------------+
|                           STREAMING & ANALYTICS FABRIC                            |
|  +---------------------+   +---------------------+   +--------------------------+ |
|  | Event Broker        |-->| Columnar DB         |-->| Behavioral Intercept     | |
|  | (Kafka / Redpanda)  |   | (ClickHouse/BigQ)   |   | Rules Engine (Real-Time) | |
|  +---------------------+   +---------------------+   +------------+-------------+ |
+-------------------------------------------------------------------|---------------+
                                                                    | Trigger Signal
                                                                    v
                                                       +--------------------------+
                                                       | Targeted User Intercept: |
                                                       | - Dynamic Micro-Survey   |
                                                       | - Interview Invite Modal |
                                                       +--------------------------+
```

#### Komponen Kunci Arsitektur:
1. **Discovery Telemetry SDK Core:**
   - **Interaction Friction Detector:** Menghitung deviasi standar dari waktu interaksi rata-rata dan pola berulang (misal: 3 klik dalam rentang <500ms pada target elemen yang sama tanpa mutasi DOM yang memicu status *Rage Click*).
   - **PII Scrubbing Pipeline:** Mengidentifikasi dan menyamarkan elemen privat secara deterministik sebelum data meninggalkan memori runtime client (regex-based masking + attribute-level masking via `data-private` attribute).
2. **Schema Registry & Edge Validation:**
   - Kontrak data analitik ditentukan menggunakan JSON Schema atau Protocol Buffers.
   - Gateway Edge memvalidasi struktur payload secara *zero-copy*. Event yang melanggar kontrak akan dibuang ke *Dead Letter Queue (DLQ)* untuk mengeliminasi polusi data pada pipeline analitik desainer produk.
3. **Behavioral Intercept Engine:**
   - Mengonsumsi event stream dan mengevaluasi status pengguna secara stateful. Jika pengguna mengalami kegagalan pada suatu *Job-to-be-done* (misalnya: gagal memvalidasi form pembayaran 2x berturut-turut lalu mengunjungi halaman FAQ), sistem secara dinamis menginjeksi survei kualitatif *micro-targeted* (maksimal 2 pertanyaan) atau *scheduling modal* untuk wawancara pengguna dengan insentif otomatis.

---

### 4. Why & What

| Paradigma | Traditional Discovery (Manual & Ad-hoc) | Enterprise Continuous Telemetry-Driven Discovery |
| :--- | :--- | :--- |
| **Siklus Umpan Balik** | 4 - 8 Minggu (Perencanaan, Rekrutmen, Interview, Sintesis). | Sub-menit untuk deteksi friksi; <24 jam untuk sintesis kualitatif terarah. |
| **Akurasi Konteks** | *Recall Bias* tinggi; pengguna sering lupa apa yang mereka lakukan saat insiden terjadi. | *Zero Recall Bias*; instigasi riset terjadi tepat saat anomali perilaku/kegagalan terdeteksi. |
| **Integritas Data** | Data event sering rusak akibat perubahan nama class/ID frontend (*fragile instrumentation*). | *Strict Schema Contract*; *compile-time type safety* dari desain sistem hingga ingestion. |
| **Kepatuhan Privasi** | Sering terjadi kebocoran data sensitif pada rekaman sesi (*Session Replay*) dan logs. | Masking deterministik berlapis (*Client-side DOM Redaction* + *Edge Redaction*). |

---

### 5. How (Workflow Detail)

Alur kerja integrasi penemuan masalah secara kontinu:

```
[Design System Token / UI Component]
               │
               ▼
[1. Declare Interaction Contract (Data-TestID & Schema)]
               │
               ▼
[2. Instrument Client via SDK (Friction & Funnel Listeners)]
               │
               ▼
[3. Real-Time PII Redaction in Memory]
               │
               ▼
[4. Dispatch via navigator.sendBeacon() or keepalive fetch]
               │
               ▼
[5. Edge Proxy Validation against Schema Registry]
       │                              │
  (Valid)                         (Invalid)
       │                              │
       ▼                              ▼
[6. Real-Time Stream]           [Send to DLQ / Alert Sentry]
       │
       ▼
[7. Anomaly & Pattern Evaluation (e.g., Rage Clicks > 2)]
       │
       ▼
[8. Real-time In-App Trigger: Micro-Qualitative Prompt]
```

1. **Deklarasi Kontrak:** Product Designer dan Engineer mendefinisikan *telemetry contract* bersamaan dengan pembuatan komponen UI di Figma/Storybook. Metadata tracking menjadi *first-class prop* pada komponen.
2. **Instrumentasi Komponen:** Komponen membungkus interaksi dengan *telemetry dispatcher* tipe-aman (*type-safe*).
3. **Penyaringan PII:** Runtime DOM observer secara rekursif mengaburkan teks, form value, dan atribut sensitif sebelum data diserialisasi.
4. **Pengiriman Non-Blocking:** Telemetri dikirimkan menggunakan `navigator.sendBeacon` atau `fetch` dengan bendera `keepalive: true` untuk memastikan data tidak hilang saat navigasi/penutupan tab.
5. **Validasi Edge:** Worker memvalidasi format event. Event yang tidak valid langsung ditolak untuk menjaga integritas *discovery warehouse*.
6. **Evaluasi Aturan Intersept:** Jika kondisi terpicu (contoh: *Friction Drop-off*), event engine mengirim sinyal kembali via WebSocket/Server-Sent Events (SSE) atau Response Payload untuk menampilkan modul riset mikro.

---

### 6. Analogy & Diagram ASCII

#### Analogi:
Bayangkan Anda adalah manajer operasional jalan tol.
- **Riset Tradisional:** Anda menaruh petugas di gerbang keluar tol sebulan sekali untuk bertanya, "Apakah tadi ada lubang di jalan tol?" Pengemudi sering lupa di kilometer berapa lubang tersebut berada, atau mengabaikan survei karena terburu-buru.
- **Continuous Discovery Telemetry:** Anda memasang sensor getaran di setiap mobil (dengan enkripsi data pribadi pengemudi). Begitu mobil berguncang hebat 3 kali di KM 42 (*Friction Pattern*), sensor langsung mendeteksi anomali. Sistem secara otomatis menyalakan papan informasi digital tepat di depan pengemudi tersebut: *"Kami mendeteksi guncangan di KM 42, apakah Anda baru saja menghindari lubang?"* Masalah terisolasi seketika dengan akurasi 100%.

#### Diagram Alur Logika State Mesin Deteksi Friksi:

```
    [User Event: PointerDown]
               │
               ▼
       +---------------+
       | Target Element|
       +---------------+
               │
               ├── (Same target within 500ms?)
               │        │
               │       Yes ──> Increment Hit Counter
               │        │             │
               │        │      (Hit Counter >= 3?)
               │        │             │
               │        │            Yes ──> [TRIGGER: RAGE_CLICK_DETECTED]
               │        │                            │
               │        No ──> Reset Counter         v
               │                           +-----------------------+
               │                           | Check MutationObserver|
               │                           +-----------------------+
               │                                     │
               │                      (DOM Changed in <1000ms?)
               │                                     │
               │                                    No ──> [TRIGGER: DEAD_CLICK_DETECTED]
               v                                           (Qualitative Intercept Eligible)
   [Normal Telemetry Track]
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Strongly-Typed Discovery Telemetry Dispatcher (TypeScript)

Implementasi sederhana untuk memastikan desainer dan insinyur memiliki tipe data eksplisit untuk setiap interaksi riset pengguna.

```typescript
// types/telemetry.ts
export type DiscoveryFrictionType = 'RAGE_CLICK' | 'DEAD_CLICK' | 'FORM_ABANDONMENT';

export interface BaseDiscoveryEvent {
  eventId: string;
  timestamp: number;
  userIdHash: string; // Pseudonymized
  sessionId: string;
  currentRoute: string;
}

export interface FrictionEvent extends BaseDiscoveryEvent {
  eventType: 'DISCOVERY_FRICTION';
  payload: {
    frictionType: DiscoveryFrictionType;
    targetComponent: string;
    interactionCount: number;
    viewport: { width: number; height: number };
  };
}

// telemetry/dispatcher.ts
export class DiscoveryTelemetry {
  private static endpoint = 'https://telemetry-gateway.enterprise.internal/v1/collect';

  public static trackFriction(event: Omit<FrictionEvent, 'eventId' | 'timestamp'>): void {
    const payload: FrictionEvent = {
      ...event,
      eventId: crypto.randomUUID(),
      timestamp: Date.now(),
    };

    const blob = new Blob([JSON.stringify(payload)], { type: 'application/json' });
    
    // Non-blocking transmission
    if (navigator.sendBeacon) {
      navigator.sendBeacon(this.endpoint, blob);
    } else {
      fetch(this.endpoint, {
        method: 'POST',
        body: blob,
        keepalive: true,
        credentials: 'omit' // Preserve privacy
      }).catch((err) => console.error('Discovery telemetry failed', err));
    }
  }
}
```

#### Practical Example: Production-Grade Friction Engine & PII-Safe Masking Worker (Enterprise Level)

Kode berikut memantau interaksi pengguna di frontend, memvalidasi apakah terjadi *Dead Click* (indikasi kuat ekspektasi pengguna tidak terpenuhi), melakukan sanitasi PII pada memori client, dan memicu *micro-intercept*.

```typescript
/**
 * Advanced Friction & Discovery Intercept Engine
 * Production-ready client module
 */

interface FrictionThresholds {
  rageClickThreshold: number;
  rageClickWindowMs: number;
  deadClickMutationTimeoutMs: number;
}

export class DiscoveryFrictionMonitor {
  private clickHistory: { target: HTMLElement; timestamp: number }[] = [];
  private observer: MutationObserver;
  private hasDomMutated: boolean = false;
  private thresholds: FrictionThresholds = {
    rageClickThreshold: 3,
    rageClickWindowMs: 600,
    deadClickMutationTimeoutMs: 1000,
  };

  constructor(private interceptCallback: (elementIdentifier: string) => void) {
    this.observer = new MutationObserver(() => {
      this.hasDomMutated = true;
    });

    this.observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
    });

    this.initListeners();
  }

  private initListeners(): void {
    window.addEventListener('pointerdown', this.handlePointerDown.bind(this), {
      passive: true,
    });
  }

  private sanitizeElementIdentifier(el: HTMLElement): string {
    // Scrub PII: Cegah teks pengguna masuk ke telemetry pipeline
    const explicitTestId = el.getAttribute('data-discovery-id');
    if (explicitTestId) return explicitTestId;

    const tagName = el.tagName.toLowerCase();
    const role = el.getAttribute('role') || 'generic';
    const cleanClassList = Array.from(el.classList)
      .filter((cls) => !cls.match(/(user|token|email|auth|name)/i))
      .slice(0, 2)
      .join('.');

    return `${tagName}[role="${role}"]${cleanClassList ? '.' + cleanClassList : ''}`;
  }

  private handlePointerDown(event: PointerEvent): void {
    const target = event.target as HTMLElement;
    if (!target) return;

    const now = Date.now();
    this.clickHistory.push({ target, timestamp: now });

    // Clean old history
    this.clickHistory = this.clickHistory.filter(
      (entry) => now - entry.timestamp <= this.thresholds.rageClickWindowMs
    );

    // 1. Detect Rage Click
    const recentClicksOnSameTarget = this.clickHistory.filter(
      (entry) => entry.target === target || entry.target.contains(target)
    );

    if (recentClicksOnSameTarget.length >= this.thresholds.rageClickThreshold) {
      this.reportFriction('RAGE_CLICK', target);
      this.clickHistory = []; // Reset after trigger
      return;
    }

    // 2. Detect Dead Click (Click occurs, but no DOM mutation or navigation occurs)
    this.hasDomMutated = false;
    setTimeout(() => {
      const isInteractiveElement = [
        'BUTTON',
        'A',
        'INPUT',
        'SELECT',
      ].includes(target.tagName);
      const isRoleInteractive = ['button', 'link'].includes(
        target.getAttribute('role') || ''
      );

      if ((isInteractiveElement || isRoleInteractive) && !this.hasDomMutated) {
        this.reportFriction('DEAD_CLICK', target);
      }
    }, this.thresholds.deadClickMutationTimeoutMs);
  }

  private reportFriction(type: 'RAGE_CLICK' | 'DEAD_CLICK', element: HTMLElement): void {
    const safeIdentifier = this.sanitizeElementIdentifier(element);

    const payload = {
      event: 'DISCOVERY_FRICTION_ANOMALY',
      type,
      selector: safeIdentifier,
      currentUrl: window.location.pathname, // Redact query params explicitly
      clientTimestamp: new Date().toISOString(),
    };

    // Dispatch beacon safely
    if (navigator.sendBeacon) {
      navigator.sendBeacon('/api/v1/discovery/friction', JSON.stringify(payload));
    }

    // Pemicu riset kualitatif kontekstual jika elemen kritikal
    if (element.hasAttribute('data-discovery-critical')) {
      this.interceptCallback(safeIdentifier);
    }
  }

  public destroy(): void {
    window.removeEventListener('pointerdown', this.handlePointerDown);
    this.observer.disconnect();
  }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Global Fintech Payment Gateway (Checkout Funnel Attrition)
- **Konteks:** Perusahaan memproses volume transaksi $50M/bulan. Terjadi penurunan drastis (-18%) pada konversi checkout di perangkat seluler pada rilis versi tertentu. Metrik standar hanya memperlihatkan *Exit Rate* tinggi di `/checkout/review`, namun tidak menjelaskan penyebabnya.
- **Penerapan Solusi Telemetri Riset:**
  1. *Friction Engine* mendeteksi 42.000 *Dead Clicks* dalam 4 jam pertama pasca-rilis pada komponen `PaySecureButton`.
  2. Sistem behavioral routing memicu micro-survey kualitatif secara otomatis hanya kepada 1% dari pengguna yang mengalami *Dead Click* tersebut: *"Apakah Anda mengalami kesulitan menekan tombol Bayar?"*
  3. Integrasi *Session Replay* berkapabilitas masking ketat merekam 150 sesi terintersep.
- **Root Cause Analysis (RCA):**
  Ditemukan bahwa modal syarat & ketentuan (T&C) pihak ketiga merender overlay *invisible* `z-index: 9999` dengan `opacity: 0` akibat kegagalan sinkronisasi hydration pada koneksi jaringan lambat (3G). Tombol `PaySecureButton` terhalang secara fisik pada layer DOM, sehingga klik tidak pernah mencapai handler aksi.
- **Dampak Finansial:** Masalah berhasil diidentifikasi dalam waktu 45 menit pasca peluncuran canary (dibandingkan 2-3 minggu jika menunggu laporan Customer Service dan wawancara pengguna ad-hoc), mencegah estimasi kerugian transaksi sebesar $1.2M.

---

### 9. Trade-offs (Analisis Arsitektur)

| Dimensi Arsitektur | Opsi A: Deep Client-Side Observability (Heavy Replay + Full Event Stream) | Opsi B: Schema-Driven Semantic Telemetry + Dynamic Trigger | Dampak Rekayasa & Keputusan |
| :--- | :--- | :--- | :--- |
| **Performance & CPU** | **Tinggi (Negatif).** Terus memantau mutasi DOM lewat tree-traversal dapat menyebabkan *frame drops* (Jank) pada perangkat low-end. | **Rendah (Optimal).** Hanya memantau pointer events dan mutasi lokal via threshold buffer ringan. | Gunakan Opsi B di produksi umum. Batasi Opsi A hanya untuk canary sample (<1% cohort). |
| **Network Bandwidth & Battery** | Mengirim snapshot DOM terkompresi secara periodik menguras kuota data dan baterai perangkat mobile pengguna. | Mengirimkan payload metadata event berukuran < 1KB per interaksi via `sendBeacon`. | Opsi B unggul jauh dalam UX mobile dan zero-impact terhadap Core Web Vitals (khususnya INP). |
| **Privacy / Compliance Risk** | **Sangat Berisiko.** Potensi capture input sensitif (kartu kredit, password) jika rules masking DOM gagal melacak class dinamis. | **Aman secara Desain.** Zero-text capture. SDK hanya mengabstraksi *component identifier* dan status state, bukan teks/nilai input. | Opsi B mempermudah audit GDPR/UU PDP dan menghindari tanggung jawab hukum kebocoran PII. |
| **Storage & Ingestion Cost** | Biaya penyimpanan data uncompressed/semi-structured mencapai jutaan dollar per kuartal di Datadog/FullStory. | Payload tabular terkompresi disimpan efisien dalam ClickHouse/BigQuery; hemat biaya penyimpanan hingga 85%. | Opsi B sangat bersahabat dengan unit economics enterprise data infra. |

---

### 10. Common Mistakes & Troubleshooting

1. **Mistake: Telemetry Blocking Critical Path (INP Degradation)**
   - *Penyebab:* Melakukan evaluasi regex DOM yang kompleks atau sinkronisasi penyimpanan *local storage* tepat di dalam handler `onClick` utama.
   - *Solusi:* Eksekusi logika kalkulasi friksi di dalam `requestIdleCallback()` atau menggunakan `setTimeout(fn, 0)` untuk membebaskan thread komputasi utama.
2. **Mistake: Event Payload Mengandung Unintended PII**
   - *Penyebab:* Melakukan serialisasi `window.location.href` secara utuh yang berisi token autentikasi atau email pada parameter query URL (misal: `?email=john%40doe.com`).
   - *Solusi:* Buat middleware sanitasi URL wajib yang menghapus semua query params sebelum menyusun telemetry dispatch:
     ```typescript
     const sanitizeUrl = (url: string): string => {
       const parsed = new URL(url);
       return `${parsed.origin}${parsed.pathname}`; // Strips searchParams and hash
     };
     ```
3. **Mistake: Surviving Page Unload Telemetry Drop**
   - *Penyebab:* Menggunakan standar `axios.post` atau `fetch` tanpa bendera `keepalive`. Request dibatalkan oleh browser begitu jendela/tab ditutup saat proses drop-off.
   - *Solusi:* Gunakan `navigator.sendBeacon` secara primer, atau *fallback* ke `fetch(url, { keepalive: true })`.
4. **Mistake: Survey Fatigue Akibat Trigger Intersep yang Terlalu Agresif**
   - *Penyebab:* Interception engine memicu micro-survey setiap kali pengguna mengalami rage click di setiap halaman.
   - *Solusi:* Terapkan *Global Intercept Cooldown System* di browser client menggunakan session/local storage (misal: maksimal 1 intercept per user per 30 hari).

---

### 11. Best Practices (Production Checklist)

| Tahap | Checklist Operasional Discovery Telemetry | Target Standar | Status Verifikasi |
| :--- | :--- | :--- | :--- |
| **Design** | Setiap komponen interaktif di design system (Figma) memiliki token `data-discovery-id` yang unik. | 100% Core Components | [ ] |
| **Security** | PII stripping engine diuji menggunakan unit-test berisi 50+ variasi input sensitif (NIK, Email, Kartu Kredit). | 0% PII Leakage | [ ] |
| **Performance** | Beban runtime Telemetry SDK tidak menambah TBT (Total Blocking Time) lebih dari 15ms. | <= 15ms Overhead | [ ] |
| **Network** | Payload telemetry dikirim menggunakan batching (buffer 5 detik) atau `navigator.sendBeacon`. | HTTP 204 Success | [ ] |
| **Governance** | Skema event terdaftar dan tervalidasi menggunakan Schema Registry pada pipeline Edge. | Zero Schema Drift | [ ] |
| **User Privacy** | SDK menghormati flag `navigator.doNotTrack` dan preferensi CMP (Consent Management Platform). | Consent Compliant | [ ] |

---

### 12. Hands-on Practice: Membangun Production Friction Detection Engine

Simpan berkas latihan ini di dalam direktori `hands-on/m02/`.

#### Langkah 1: Inisialisasi Proyek & File Konfigurasi
Buat direktori baru dan inisialisasi modul:
```bash
mkdir -p hands-on/m02 && cd hands-on/m02
npm init -y
npm install typescript @types/node --save-dev
npx tsc --init
```

#### Langkah 2: Buat File `hands-on/m02/FrictionDiscoveryEngine.ts`
Salin kode berikut yang mengimplementasikan sistem deteksi friksi dengan mekanisme proteksi PII dan batasan frekuensi intersep (cooldown logic).

```typescript
// hands-on/m02/FrictionDiscoveryEngine.ts

export interface DiscoveryConfig {
  rageClickThreshold: number;
  rageClickIntervalMs: number;
  cooldownPeriodDays: number;
  collectorEndpoint: string;
}

export class ProductionDiscoveryEngine {
  private clicks: { target: HTMLElement; time: number }[] = [];
  private static readonly STORAGE_KEY = 'DISCOVERY_INTERCEPT_COOLDOWN';

  constructor(private config: DiscoveryConfig) {
    this.setupListeners();
  }

  private setupListeners(): void {
    if (typeof window === 'undefined') return;

    window.addEventListener('click', (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target) return;

      const now = Date.now();
      this.clicks.push({ target, time: now });

      // Bersihkan riwayat di luar interval evaluasi
      this.clicks = this.clicks.filter(
        (c) => now - c.time <= this.config.rageClickIntervalMs
      );

      // Hitung klik pada target identik
      const identicalClicks = this.clicks.filter(
        (c) => c.target === target || c.target.contains(target)
      );

      if (identicalClicks.length >= this.config.rageClickThreshold) {
        this.handleRageClickFriction(target);
        this.clicks = []; // Reset setelah terdeteksi
      }
    });
  }

  private isUnderCooldown(): boolean {
    const lastIntercept = localStorage.getItem(ProductionDiscoveryEngine.STORAGE_KEY);
    if (!lastIntercept) return false;

    const lastInterceptTime = parseInt(lastIntercept, 10);
    const cooldownMs = this.config.cooldownPeriodDays * 24 * 60 * 60 * 1000;
    return Date.now() - lastInterceptTime < cooldownMs;
  }

  private triggerMicroSurvey(targetId: string): void {
    if (this.isUnderCooldown()) {
      console.log(`[Discovery] Intercept diabaikan: Pengguna sedang dalam masa cooldown.`);
      return;
    }

    console.info(`[Discovery] Memunculkan Micro-Survey Intersep untuk Komponen: ${targetId}`);
    
    // Terapkan cooldown
    localStorage.setItem(
      ProductionDiscoveryEngine.STORAGE_KEY,
      Date.now().toString()
    );

    // Mockup pembuatan modal riset kontekstual pada DOM
    const modal = document.createElement('div');
    modal.id = 'discovery-micro-intercept';
    modal.style.position = 'fixed';
    modal.style.bottom = '24px';
    modal.style.right = '24px';
    modal.style.backgroundColor = '#18181b';
    modal.style.color = '#ffffff';
    modal.style.padding = '16px';
    modal.style.borderRadius = '8px';
    modal.style.boxShadow = '0 10px 15px -3px rgba(0, 0, 0, 0.3)';
    modal.style.zIndex = '10000';
    modal.innerHTML = `
      <div style="font-size: 14px; font-weight: 600; margin-bottom: 8px;">Ada kendala pada tombol ini?</div>
      <p style="font-size: 12px; color: #a1a1aa; margin: 0 0 12px 0;">Kami mendeteksi respon tombol tidak sesuai harapan Anda.</p>
      <button id="survey-action-btn" style="background: #2563eb; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 12px;">Laporkan Kendala</button>
      <button id="survey-dismiss-btn" style="background: transparent; color: #71717a; border: none; margin-left: 8px; cursor: pointer; font-size: 12px;">Tutup</button>
    `;

    document.body.appendChild(modal);

    document.getElementById('survey-dismiss-btn')?.addEventListener('click', () => {
      modal.remove();
    });

    document.getElementById('survey-action-btn')?.addEventListener('click', () => {
      alert(`Membuka form feedback kontekstual untuk elemen: ${targetId}`);
      modal.remove();
    });
  }

  private handleRageClickFriction(target: HTMLElement): void {
    // 1. Ekstraksi Identifier yang Aman (Zero-PII)
    const discoveryId =
      target.getAttribute('data-discovery-id') ||
      target.getAttribute('aria-label') ||
      target.tagName.toLowerCase();

    // 2. Dispatch Data Telemetri
    const payload = {
      event: 'FRICTION_RAGE_CLICK',
      targetComponent: discoveryId,
      url: window.location.pathname,
      timestamp: Date.now(),
    };

    if (navigator.sendBeacon) {
      navigator.sendBeacon(this.config.collectorEndpoint, JSON.stringify(payload));
    }

    // 3. Evaluasi Kelayakan Intervensi Kualitatif
    this.triggerMicroSurvey(discoveryId);
  }
}
```

#### Langkah 3: Eksekusi File Verifikasi (Driver Test)
Buat file `hands-on/m02/index.html` sederhana untuk menguji fungsionalitas di browser lokal:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Hands-on M02 Friction Engine</title>
</head>
<body style="font-family: sans-serif; padding: 40px;">
  <h1>Test Bench Friction Discovery Engine</h1>
  <button data-discovery-id="btn-broken-checkout" style="padding: 12px 24px; font-size: 16px;">
    Tombol Checkout (Simulasi Rusak)
  </button>

  <script type="module">
    import { ProductionDiscoveryEngine } from './FrictionDiscoveryEngine.js';

    // Inisialisasi engine
    const engine = new ProductionDiscoveryEngine({
      rageClickThreshold: 3,
      rageClickIntervalMs: 800,
      cooldownPeriodDays: 1, // 1 hari cooldown
      collectorEndpoint: '/api/mock-telemetry'
    });
  </script>
</body>
</html>
```

---

### 13. Exercise

#### Level Easy
Buat sebuah fungsi utilitas validasi payload `validateDiscoveryPayload(schema: object, event: object): boolean` menggunakan JavaScript murni (tanpa runtime dependency besar). Fungsi ini harus memeriksa apakah `eventId`, `timestamp`, dan `userIdHash` ada dan bertipe data benar.

#### Level Medium
Kembangkan modul telemetry middleware yang mendeteksi **Form Abandonment**. Jika seorang pengguna mengetik di dalam form (`input`, `textarea`) selama lebih dari 5 detik, kemudian mengklik elemen navigasi keluar (`<a href="...">`) tanpa menekan tombol submit, kirimkan event telemetri `FORM_ABANDONED_WITH_INPUT` berisi field `lastInteractedInputName` (pastikan nilainya tidak berisi teks yang diketik pengguna, hanya nama atribut `name` dari elemen input).

#### Level Hard
Rancang arsitektur data pipeline untuk penemuan masalah (problem discovery) dengan ketentuan:
1. Mampu mengonsumsi 50.000 event/detik.
2. Memfilter data PII di layer edge worker sebelum memasuki queue.
3. Menyimpan data ke dalam ClickHouse dengan skema tabular teroptimasi (partisi berdasarkan hari, primary key: `tenant_id`, `event_name`, `timestamp`).
Tuliskan DDL SQL ClickHouse dan pseudo-code handler edge worker-nya.

---

### 14. Challenge

**Studi Kasus Arsitektur: Dynamic Painted-Door Experimentation Engine pada Skala Global**

**Konteks Masalah:**
Perusahaan Anda adalah platform Software-as-a-Service (SaaS) multi-tenant B2B dengan jutaan pengguna harian. Tim Produk ingin menguji minat pengguna terhadap 5 inisiatif fitur baru yang mahal untuk dibangun (*High-cost investments*) menggunakan metodologi *Painted-Door Testing* (menampilkan antarmuka/tombol fitur seolah-olah sudah ada, dan ketika diklik menampilkan dialog: *"Fitur ini sedang dalam pengembangan, apakah Anda ingin bergabung dalam program Early Access?"*).

**Tantangan Rekayasa & Desain:**
1. **Zero UI Blocking & Hydration Safety:** Sistem injeksi painted-door harus dikontrol via Feature Flags terpusat tanpa menyebabkan layout shift (CLS = 0) dan tanpa menyebabkan error *DOM mismatch* pada React Server Components (RSC).
2. **Experimentation Bias Prevention:** Rancang algoritma client/edge agar seorang pengguna tidak terpapar lebih dari satu *Painted-Door Test* dalam rentang 30 hari untuk mencegah erosi kepercayaan (*trust fatigue*) dan bias data riset.
3. **Data Quality & Automated Discovery Synthesis:** Rancang bagaimana data klik painted-door dikorelasikan secara otomatis dengan segmentasi tenant (*Enterprise Tier* vs *Free Tier*) dan langsung membuat tiket penemuan masalah (*Discovery Problem Card*) di Jira/Productboard jika *Conversion Rate* painted-door tersebut melampaui 15% dari total impresi.

**Deliverables:**
- Diagram alur arsitektur (Edge Config -> Client Injection -> Analytics Aggregator -> Product Discovery Automation).
- Analisis kegagalan privasi dan mitigasinya (termasuk mitigasi persepsi negatif pengguna).

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Soal)
1. **Apa perbedaan mendasar antara *Active Inquiry* dan *Passive Continuous Discovery Telemetry*?**
   - A. Active Inquiry menggunakan software, Passive Telemetry menggunakan kertas.
   - B. Active Inquiry meminta pengguna meluangkan waktu menjawab (wawancara, survei), sedangkan Passive Telemetry mengamati perilaku alami pengguna secara terprogram tanpa friksi.
   - C. Passive Telemetry hanya berlaku untuk mobile apps, bukan web.
   - D. Active Inquiry tidak membutuhkan persetujuan pengguna.
   *Jawaban:* **B** | *Rasional:* Active inquiry membutuhkan partisipasi sadar pengguna, sedangkan passive telemetry menangkap jejak interaksi alami secara kontinu.

2. **Mengapa `navigator.sendBeacon()` lebih direkomendasikan daripada `fetch()` standar untuk mengirimkan telemetry penutupan halaman?**
   - A. Karena `sendBeacon` dapat memproses payload berukuran gigabytes.
   - B. Karena `sendBeacon` otomatis mengeksekusi di background thread browser tanpa tertahan penutupan dokumen (*page unload*).
   - C. Karena `sendBeacon` otomatis mengenkripsi data dengan RSA-4096.
   - D. Karena `sendBeacon` membaca state CSS secara otomatis.
   *Jawaban:* **B** | *Rasional:* Standard HTTP requests dapat dibatalkan seketika oleh browser saat halaman beralih/ditutup, sedangkan user agent menjamin pengiriman antrean beacon secara asinkron.

3. **Apa indikasi utama terjadinya fenomena *Rage Click* pada antarmuka frontend?**
   - A. Pengguna menutup browser dalam waktu 1 detik.
   - B. Pengguna melakukan refresh halaman berulang kali.
   - C. Pengguna melakukan serangkaian klik berturut-turut pada koordinat/elemen yang sama dalam interval waktu yang sangat singkat.
   - D. Pengguna mengetik huruf kapital semua pada field input teks.
   *Jawaban:* **C** | *Rasional:* Rage clicks didefinisikan sebagai klik berulang dan cepat pada satu target interaksi, merefleksikan frustrasi atas ketidaktercapaian respons sistem.

4. **Apa yang dimaksud dengan *Dead Click* dalam analisis problem discovery?**
   - A. Klik yang menyebabkan aplikasi crash.
   - B. Klik yang dilakukan oleh software bot otomatis.
   - C. Klik pada elemen interaktif yang tidak menghasilkan perubahan state, mutasi DOM, atau panggilan jaringan sama sekali.
   - D. Klik yang terjadi saat baterai perangkat berada di bawah 5%.
   *Jawaban:* **C** | *Rasional:* Dead click mengindikasikan mismatch ekspektasi antarmuka: pengguna mengira elemen tersebut memiliki fungsi, namun tidak ada feedback visual atau aksi sistem yang terealisasi.

5. **Data apa yang WAJIB dibersihkan (*redacted/scrubbed*) sebelum mengirimkan telemetry interaksi guna mematuhi regulasi privasi global?**
   - A. Timestamp klik.
   - B. Ukuran viewport browser pengguna.
   - C. Tag nama elemen DOM (misal: `BUTTON`).
   - D. Teks masukan form pengguna, email, nomor identitas, dan query parameters sensitif.
   *Jawaban:* **D** | *Rasional:* Nilai-nilai input personal tergolong Personally Identifiable Information (PII) yang dilarang keras dikirim ke pipeline data analytics umum tanpa penanganan enkripsi legal khusus.

---

#### Bagian 2: Intermediate (5 Soal)
6. **Dalam implementasi *MutationObserver* untuk mendeteksi *Dead Clicks*, mengapa penting membatasi lingkup observer atau mendiskoneksikannya segera setelah evaluasi selesai?**
   - A. Karena MutationObserver menyebabkan kebocoran memori pada browser lama jika dibiarkan aktif tanpa henti pada subtree berukuran masif.
   - B. Karena MutationObserver tidak mendukung arsitektur Single Page Application (SPA).
   - C. Karena MutationObserver otomatis menghapus node DOM yang diobservasi.
   - D. Karena MutationObserver mengubah nilai CSS elemen target.
   *Jawaban:* **A** | *Rasional:* Mendengarkan mutasi DOM pada seluruh `document.body` tanpa pembatasan rentang waktu atau filtering dapat menyebabkan performa *main thread* drop secara drastis saat rendering halaman yang kompleks.

7. **Bagaimana mekanisme *Schema-Driven Analytics* mencegah tim riset produk dari mengambil keputusan berdasarkan data yang salah (*corrupted metrics*)?**
   - A. Dengan membatasi akses dasbor hanya kepada Head of Product.
   - B. Dengan memvalidasi kontrak payload secara ketat di layer kompilasi/ingestion; payload yang tidak sesuai skema langsung dikarantina ke DLQ alih-alih merusak visualisasi data analitik.
   - C. Dengan mengubah semua angka conversion rate menjadi nilai persentase bulat.
   - D. Dengan memaksa pengguna mengisi formulir registrasi ulang.
   *Jawaban:* **B** | *Rasional:* Schema registry memastikan data yang masuk ke data warehouse riset selalu memiliki tipe, kunci, dan format yang valid sesuai spesifikasi yang disepakati oleh product engineer dan designer.

8. **Apa bahaya terbesar dari melakukan *Painted-Door Testing* tanpa menerapkan aturan frekuensi intersep (*cooldown logic*)?**
   - A. Server backend akan mengalami Out-Of-Memory (OOM).
   - B. Menurunnya tingkat kepercayaan pengguna (*user trust degradation*) karena mereka berulang kali dijanjikan fitur yang ternyata belum tersedia.
   - C. CSS layout aplikasi akan berantakan secara permanen.
   - D. File bundle JavaScript frontend membengkak secara eksponensial.
   *Jawaban:* **B** | *Rasional:* Eksploitasi painted-door testing yang berlebihan menciptakan ekspektasi palsu dan rasa frustrasi sistemik, yang justru merusak kepuasan dan retensi pelanggan.

9. **Ketika mengukur waktu interaksi pengguna pada frontend, mengapa metrik `performance.now()` lebih disukai dibanding `Date.now()`?**
   - A. Karena `performance.now()` menghasilkan output dalam format ISO String.
   - B. Karena `performance.now()` memiliki resolusi sub-milidetik dan bersifat *monotonic* (tidak terpengaruh oleh penyesuaian waktu sistem operasi lokal pengguna).
   - C. Karena `performance.now()` secara otomatis mengenkripsi data waktu.
   - D. Karena `performance.now()` bekerja tanpa membutuhkan JavaScript engine.
   *Jawaban:* **B** | *Rasional:* `Date.now()` rentan terhadap ketidakakuratan karena jam sistem lokal bisa diubah manual atau disesuaikan via sinkronisasi NTP, sedangkan `performance.now()` mengukur interval secara monotonik sejak dokumen diinisialisasi.

10. **Bagaimana arsitektur *Dynamic Behavioral Intercept* menentukan momen yang tepat untuk memunculkan modal wawancara kualitatif?**
    - A. Ditampilkan secara acak kepada setiap pengunjung ke-10 yang membuka halaman beranda.
    - B. Ditampilkan segera setelah pengguna menyelesaikan transaksi tanpa kendala.
    - C. Ditampilkan secara presisi ketika pengguna memenuhi kombinasi kondisi kegagalan (misal: 2x validasi gagal + 1x rage click) untuk menangkap sentimen frustrasi secara objektif di titik kejadian (*point of friction*).
    - D. Ditampilkan hanya jika pengguna mengakses aplikasi menggunakan koneksi kabel LAN.
    *Jawaban:* **C** | *Rasional:* Intervensi kualitatif memiliki nilai diagnostik tertinggi jika dilakukan secara kontekstual tepat saat friksi perilaku terdeteksi.

---

#### Bagian 3: Production Scenarios (3 Soal)
11. **Skenario:** Aplikasi perbankan enterprise Anda baru saja meluncurkan fitur transfer valuta asing. Data telemetri menunjukkan bahwa 35% pengguna keluar (*drop-off*) di halaman input penerima. Namun, tidak ada laporan error di Sentry/Logstash. Anda diminta merancang investigasi discovery terprogram untuk menemukan akar masalah dalam 24 jam. Tindakan teknis mana yang paling efektif?
    - A. Menghapus fitur transfer valuta asing dan kembali ke versi aplikasi sebelumnya.
    - B. Menginjeksi *Friction Tracker* non-blocking yang mengukur *form field blur count*, *input correction frequency* (penggunaan tombol backspace/delete berlebih), dan *dead click* pada tombol "Lanjut", disertai micro-survey intersep terarah pada cohort yang membatalkan transfer.
    - C. Mengirimkan email massal ke seluruh pengguna aplikasi berisi kuesioner Google Form dengan 25 pertanyaan.
    - D. Mengubah warna tombol "Lanjut" dari hijau menjadi merah terang untuk menarik perhatian.
    *Jawaban:* **B** | *Rasional:* Mengamati metrik interaksi mikro pada form (backtracking, backspacing) memberikan sinyal jelas letak ambiguitas form (misal: format IBAN/SWIFT yang membingungkan) dan micro-survey langsung memvalidasi hipotesis desainer secara instan.

12. **Skenario:** Tim Compliance melaporkan bahwa pipeline riset analytics menerima data mentah yang mengandung data sensitif nama pengguna pada payload event: `{ component: "user-greeting", label: "Halo, Budi Santoso" }`. Data ini masuk ke warehouse analitik pihak ketiga. Apa langkah remediasi arsitektural yang harus diambil segera?
    - A. Meminta pihak ketiga menghapus semua database mereka.
    - B. Menginstruksikan Product Designer untuk berhenti menggunakan komponen sapaan nama.
    - C. Mengimplementasikan Edge Worker sanitizer yang mengevaluasi payload secara regex dan memotong nilai teks dinamis, serta mengupdate Design System SDK agar label hanya mengirimkan Token Kunci Translasi (misal: `label: "greeting_user_title"`), bukan teks hasil render DOM.
    - D. Mematikan seluruh sistem tracking analitik di produksi selama 6 bulan.
    *Jawaban:* **C** | *Rasional:* Memisahkan token semantik dari teks konten dinamis adalah prinsip dasar instrumentasi analitik enterprise. Edge sanitization bertindak sebagai fail-safe lapis kedua untuk memastikan kepatuhan regulasi data privasi.

13. **Skenario:** Telemetry SDK Anda mulai menyebabkan degradasi metrik Interaction to Next Paint (INP) pada halaman e-commerce katalog produk yang memiliki lebih dari 1.000 elemen interaktif per halaman (skor INP naik dari 80ms menjadi 320ms, masuk kategori *Poor*). Setelah profiling, ditemukan bahwa *event listener* `pointerdown` melakukan pengecekan DOM tree rekursif secara sinkron pada setiap sentuhan pengguna. Bagaimana perbaikan arsitektur kode tersebut?
    - A. Mengganti semua pointer listener dengan `window.setInterval` setiap 100ms.
    - B. Menerapkan *Event Delegation* pada root container, membatasi kedalaman transversal DOM (*max depth inspection = 3*), dan membungkus komputasi kalkulasi friksi ke dalam `requestIdleCallback` atau `scheduler.postTask` dengan prioritas background.
    - C. Menghapus semua metrik Core Web Vitals dari pelaporan engineering.
    - D. Memaksa pengguna mematikan browser extensions mereka.
    *Jawaban:* **B** | *Rasional:* Event delegation menghilangkan kebutuhan ratusan listener individu, sementara pembatasan traversal dan deferral komputasi ke browser idle task memastikan *main thread* tetap bebas untuk segera merender respons visual input pengguna.

---

### 16. Summary

1. **Continuous Discovery Telemetry:** Mengubah pendekatan riset reaktif (wawancara retrospektif yang rentan bias) menjadi pendekatan proaktif berbasis data perilaku telemetrik beresolusi tinggi secara *real-time*.
2. **Schema Governance:** Kualitas hasil riset produk berbanding lurus dengan kualitas integritas data. Validasi berbasis skema (*Schema Registry*) di level kode dan *edge ingestion* menjamin tidak adanya polusi metrik akibat perubahan struktural antarmuka frontend.
3. **Friction-Driven Qualitative Intercepts:** Kombinasi telemetri kuantitatif (*Rage Clicks*, *Dead Clicks*, *Form Abandonment*) dengan intervensi kualitatif terarah (micro-surveys, rekaman sesi bertarget) menghasilkan resolusi akar masalah discovery secara presisi tanpa membebani seluruh basis pengguna.
4. **Privacy-by-Design Compliance:** Masking data pribadi (PII Scrubbing) harus diintegrasikan di tingkat arsitektur client SDK (sebelum data ditransmisikan keluar memori perangkat) dan difortifikasi di layer edge gateway untuk memenuhi regulasi perlindungan data global.