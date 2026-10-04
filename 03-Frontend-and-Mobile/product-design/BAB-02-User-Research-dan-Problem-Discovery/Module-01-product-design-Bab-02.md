# User Research & Problem Discovery

---

## SEKSI 01 — IDENTITAS MODUL

* **Domain Kurikulum:** Product Design & Engineering Track
* **Kategori:** 03-Frontend-and-Mobile
* **Bab:** 02 (Discovery, Architecture, & Interaction Foundations)
* **Modul:** 01
* **Topik Utama:** User Research, Problem Discovery, Telemetri UX, dan Analisis Data Kualitatif-Kuantitatif
* **Tingkat Kesulitan:** Intermediate to Advanced Staff-Level Engineer
* **Prasyarat Pengetahuan:** Dasar Arsitektur Frontend/Mobile (React/TypeScript/React Native/iOS/Android), Dasar REST/GraphQL, Pemahaman Siklus Hidup Produk (SDLC/Agile), Pengetahuan Analisis Data Dasar (SQL/Panda-like data manipulation).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta mampu:
1. Membedakan secara granular metodologi riset kualitatif (Generative, Evaluative) dan kuantitatif (Telemetry-driven, In-app Experiments) serta memetakan implementasi teknisnya pada platform Frontend dan Mobile.
2. Merancang arsitektur telemetri *privacy-first* untuk menangkap perilaku pengguna (interaction metrics, session replay hooks, contextual feedback triggers) tanpa mengorbankan performa *render pipeline* atau menghabiskan kapasitas *network payload*.
3. Menerapkan metodologi *Opportunity Solution Tree* (Teresa Torres) dan *Jobs-to-be-Done* (JTBD) ke dalam representasi data teknis, memetakan metrik friction ke dalam *Root Cause Analysis* (RCA).
4. Membangun modul *In-App Micro-Survey Engine* interaktif berbasis TypeScript/React yang dapat dieksekusi secara asynchronous, terisolasi dari *main-thread blocking*, dan mematuhi aturan strict CSP (Content Security Policy) serta standar regulasi data (GDPR/CCPA/UU PDP).
5. Mencegah cognitive bias (Confirmation Bias, Survivorship Bias, Observer Effect/Hawthorne Effect) dalam tahap pembacaan metrik performa aplikasi dan feedback kualitatif menggunakan teknik triangulasi data.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: "Code-First" Menuju "Problem-Discovery-First"
Mayoritas rekayasawan frontend dan mobile menganggap discovery adalah domain eksklusif Product Manager (PM) atau UI/UX Researcher. Pandangan ini adalah anti-pattern teknis. Engineer yang tidak memahami *mental model* pengguna akan menghasilkan solusi over-engineered: membangun arsitektur state management yang rumit untuk fitur yang sebenarnya tidak menyelesaikan friksi utama pengguna, atau mengoptimalkan *micro-benchmarks* rendering pada layar yang 80% ditinggalkan oleh user (*churn*) akibat alur navigasi yang membingungkan.

```
       MENTAL MODEL: TRIANGULASI DISCOVERY REKAYASA SISTEM

             [ KUALITATIF ]
        (Wawancara, Observasi,
          Usability Testing)
                 /\
                /  \
               /    \  Validasi Empiris
 Context &    /      \ Contextual "Why"
 Problem Root/        \
            /          \
           /____________\
   [ KUANTITATIF ]       [ TELEMETRI SISTEM ]
 (A/B Test, Analytics,   (Network Latency, Crashlytics,
 Funnel Drop-off Rate)   Rage Clicks, ANR, Frame Drops)
            
         ===> PROVEN PROBLEM STATEMENT (GROUND TRUTH)
```

1. **Aturan 1: Telemetri Tanpa Konteks Adalah Noise.** Lonjakan *drop-off* 40% pada form checkout bisa berarti dua hal: validasi field terlalu ketat (UX Friction) atau API gateway timeout (Technical Failure). Problem discovery mensyaratkan triangulasi antara event logging aplikasi dan umpan balik pengguna langsung.
2. **Aturan 2: Dengarkan Apa yang Dilakukan Pengguna, Bukan Hanya Apa yang Dikatakan.** Data kualitatif murni (interview) rentan terhadap *Social Desirability Bias*. Data sistem analitik mencerminkan *actual behavior*. Engineer harus mengintegrasikan observabilitas perilaku (rage clicks, drop-offs, navigation loops) langsung ke dalam platform engineering.
3. **Aturan 3: Telemetri Tidak Boleh Mengubah Hasil Ukur.** Mengumpulkan data research (misal: heatmaps, session recording) tidak boleh memicu memory leak, mendegradasi Interaction to Next Paint (INP), atau menguras daya baterai pada platform mobile.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Arsitektur penemuan masalah modern mengawinkan *Behavioral Telemetry Engine* di sisi klien dengan *Contextual Feedback Dispatcher*.

### Diagram Alur Discovery Engine Terintegrasi

```
+---------------------------------------------------------------------------------------------------+
| CLIENT LAYER (React / React Native Application)                                                   |
|                                                                                                   |
|  [ User Interacting with UI ]                                                                     |
|            |                                                                                      |
|            v                                                                                      |
|  +---------------------------------------------------------------------------------------------+  |
|  | Event Interceptor & Interaction Observer                                                    |  |
|  |  - MutationObserver (DOM Mutations)                                                         |  |
|  |  - Pointer / Touch Event Listeners (Passive)                                                |  |
|  |  - Navigation / Route Transitions                                                           |  |
|  +---------------------------------------------------------------------------------------------+  |
|            |                                                                                      |
|            |-- (Event Detection: e.g., Rapid Sequential Clicks in < 500ms)                        |
|            v                                                                                      |
|  +-------------------------------------+        +----------------------------------------------+  |
|  | Heuristic Engine (In-Memory)        |        | Masking & Sanitization Engine                |  |
|  | Detects:                            |        | Strips:                                      |  |
|  |  - Rage Click (Target Friction)     |------->|  - PII (Email, Phone, Credit Card, Passwords)|  |
|  |  - Dead Click (Unresponsive Element)|        |  - Input element textual values              |  |
|  |  - Error Loop (Retry loop pattern)  |        |  - Cryptographic Hash on Unique Identifiers  |  |
|  +-------------------------------------+        +----------------------------------------------+  |
|            |                                                              |                       |
|            | Contextual Trigger Hit?                                      | Sanitized Events      |
|            v                                                              v                       |
|  +-------------------------------------+        +----------------------------------------------+  |
|  | Dynamic Micro-Survey Trigger Hook   |        | Telemetry Queue Manager                      |  |
|  | (e.g., Mount prompt after 3 rage    |        | (RingBuffer / IndexedDB Persistence)         |  |
|  |  clicks without state change)       |        +----------------------------------------------+  |
|  +-------------------------------------+                                  |                       |
|            |                                                              | Batch Sync            |
+------------|--------------------------------------------------------------|-----------------------+
             | Trigger UI (Modal/Toast)                                     | Web Worker / Beacon
             v                                                              v
+----------------------------------------+        +-------------------------------------------------+
| CLIENT SCREEN / USER PROMPT            |        | HTTP INGESTION GATEWAY                          |
| "Kami mendeteksi kendala pada tombol   |        | (Edge Ingestion Worker / Kafka Producer)        |
| ini. Apa yang Anda harapkan terjadi?"  |        +-------------------------------------------------+
+----------------------------------------+                                  |
             | User Response Data                                           v
             |                                    +-------------------------------------------------+
             +----------------------------------->| ANALYTICS & TELEMETRY AGGREGATOR ENGINE         |
                                                  | - Elasticsearch / ClickHouse (Logs/Metrics)     |
                                                  | - Data Lakehouse (S3 / Parquet)                 |
                                                  | - NLP & Theme Extraction Cluster                |
                                                  +-------------------------------------------------+
                                                                            |
                                                                            v
                                                  +-------------------------------------------------+
                                                  | PROBLEM DISCOVERY DASHBOARD                     |
                                                  | - Correlated "Rage Clicks" vs User Frustration  |
                                                  | - JTBD Opportunity Scoring Matrix               |
                                                  +-------------------------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. The Interaction Signal Processor
Mendeteksi anomali interaksi di lapisan presentation tanpa menambahkan beban synchronous ke main execution thread. Menggunakan algoritma *sliding window accumulator* untuk mengevaluasi *threshold*:
* **Rage Clicks/Taps:** Minimal $N$ klik (misal: 3-5 klik) pada koordinat target radius $\le r$ (misal: 24 CSS pixels) dalam jendela waktu $\Delta t \le 500\text{ ms}$.
* **Dead Clicks:** Klik pada elemen interaktif semantik (`<button>`, `<a>`, role `button`) yang tidak menghasilkan mutasi DOM, request jaringan (Fetch/XHR), perubahan state style, atau transisi route dalam interval $\Delta t \ge 1500\text{ ms}$.
* **Form Abandonment:** Input field yang menerima fokus (`focusin`), dimodifikasi (`input`), tetapi ditinggalkan (`focusout`) tanpa adanya event `submit` pada form container dalam rentang waktu tertentu, disusul oleh route unload.

### 2. Client-Side Sanitization Pipeline
Sebelum data perilaku atau feedback disimpan pada memory buffer, pipeline sanitasi mengeksekusi validasi deterministik:
* Mengganti node text bertanda atribut PII (atau secara default semua `<input>`, `<textarea>`) dengan token masking `***`.
* Penggunaan `data-research-mask="true"` untuk komponen kustom.
* Reduksi payload: Objek event di-*flatten* menjadi format compact array untuk menghemat byte serialization.

### 3. Asynchronous Non-Blocking Dispatch Engine
Agar riset performa dan penemuan masalah tidak mendegradasi metrik Web Vitals (INP, LCP, CLS), transmisi data menggunakan dua saluran:
* **Background Ingestion:** Memanfaatkan `navigator.sendBeacon()` saat window unload atau ketika event batch threshold terpenuhi ($M \ge 10$ events).
* **Worker Execution:** Kalkulasi agregasi heuristic (seperti menghitung deviasi klik atau hashing payload) didelegasikan ke `Web Worker` (Frontend Web) atau background task context (Mobile).

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Metodologi Jobs-to-be-Done (JTBD) & Problem Discovery
JTBD memandang produk bukan dari fitur yang dimilikinya, melainkan dari "pekerjaan" yang didelegasikan pengguna kepada sistem:

$$\text{Tingkat Kepentingan} + \max(\text{Tingkat Kepentingan} - \text{Tingkat Kepuasan}, 0) = \text{Opportunity Score}$$

Dalam konteks arsitektur frontend, engineering harus memetakan User Journey ke dalam state machine:
* **Core Functional Job:** Tugas utama yang ingin diselesaikan user (misal: transfer dana antar bank).
* **Emotional Job:** Perasaan yang dicari (misal: merasa transaksinya aman dan instan).
* **Consumption Chain Jobs:** Setup, konfigurasi, pembersihan data error, interpretasi pesan kegagalan.

Jika arsitektur aplikasi Anda menyembunyikan error API di balik pesan generic `"Something went wrong"`, Anda merusak fase *Consumption Chain Job*, menciptakan kegagalan penemuan masalah (problem blindness).

### Quantitative Behavioral Detection Theory: Sliding-Window Heuristic
Untuk mendeteksi friksi secara real-time tanpa *false positive* yang tinggi, digunakan algoritma *Sliding Window Accumulator*. Misalkan rentetan klik dinyatakan sebagai deret waktu $E = \{(t_1, p_1), (t_2, p_2), \dots, (t_n, p_n)\}$ di mana $t$ adalah timestamp dan $p = (x, y)$ adalah koordinat layar.

Kondisi Rage Click pada jendela waktu $W$ didefinisikan sebagai:

$$\text{RageClick}(E) \iff \exists \{e_i, \dots, e_{i+k}\} \subseteq E \quad \text{s.t.} \quad k \ge N_{\text{min}}, \quad (t_{i+k} - t_i) \le \Delta t_{\text{threshold}}, \quad \forall j \in [i, i+k], \, \|p_j - p_i\| \le R_{\text{max}}$$

```
Time ------------------------------------------------------------>
[Click 1] ---- (80ms) ----> [Click 2] ---- (90ms) ----> [Click 3]
  (x: 100, y: 150)           (x: 102, y: 151)           (x: 101, y: 150)
  \___________________________________________________________/
          Window Duration: 170ms <= 500ms
          Max Radial Distance: ~2px <= 24px
          Status: RAGE CLICK IDENTIFIED -> Trigger Discovery Interceptor
```

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi Production-Grade Discovery Core: Telemetry Interaction Engine, PII Masking, Sliding-Window Rage Detector, dan Contextual Survey Dispatcher terintegrasi.

```typescript
// File: src/telemetry/DiscoveryCore.ts

export interface InteractionCoordinate {
  x: number;
  y: number;
}

export interface InteractionEvent {
  type: 'click' | 'input' | 'error' | 'navigation';
  targetSelector: string;
  timestamp: number;
  coordinates?: InteractionCoordinate;
  metadata?: Record<string, unknown>;
}

export interface HeuristicRuleConfig {
  rageClickThreshold: number;
  windowDurationMs: number;
  maxDistancePx: number;
}

export interface SurveyTriggerCallback {
  (reason: string, context: { targetSelector: string; timestamp: number }): void;
}

export class InteractionDiscoveryEngine {
  private eventBuffer: InteractionEvent[] = [];
  private readonly config: HeuristicRuleConfig;
  private readonly onTriggerSurvey: SurveyTriggerCallback;
  private isDestroyed = false;

  constructor(
    config: HeuristicRuleConfig = {
      rageClickThreshold: 3,
      windowDurationMs: 500,
      maxDistancePx: 24,
    },
    onTriggerSurvey: SurveyTriggerCallback
  ) {
    this.config = config;
    this.onTriggerSurvey = onTriggerSurvey;
    this.attachGlobalListeners();
  }

  private attachGlobalListeners(): void {
    if (typeof window === 'undefined') return;

    window.addEventListener('click', this.handleGlobalClick, {
      capture: true,
      passive: true,
    });
  }

  private handleGlobalClick = (event: MouseEvent): void => {
    if (this.isDestroyed) return;

    const target = event.target as HTMLElement | null;
    if (!target) return;

    const selector = this.sanitizeAndGenerateSelector(target);
    const interaction: InteractionEvent = {
      type: 'click',
      targetSelector: selector,
      timestamp: performance.now(),
      coordinates: { x: event.clientX, y: event.clientY },
    };

    this.processInteraction(interaction);
  };

  private sanitizeAndGenerateSelector(element: HTMLElement): string {
    // Hindari membocorkan data teks atau PII dari id/class tertentu
    if (element.hasAttribute('data-research-mask')) {
      return 'masked-element';
    }

    const tagName = element.tagName.toLowerCase();
    const id = element.id ? `#${element.id.replace(/[^\w-]/g, '')}` : '';
    const classList = Array.from(element.classList)
      .filter((c) => !c.match(/(token|secret|pii|value|active|focus)/i))
      .map((c) => `.${c.replace(/[^\w-]/g, '')}`)
      .slice(0, 2)
      .join('');

    return `${tagName}${id}${classList}`;
  }

  private processInteraction(event: InteractionEvent): void {
    this.eventBuffer.push(event);
    this.pruneOldEvents(event.timestamp);

    if (event.type === 'click' && event.coordinates) {
      this.evaluateRageClicks(event);
    }
  }

  private pruneOldEvents(currentTime: number): void {
    const horizon = currentTime - this.config.windowDurationMs;
    this.eventBuffer = this.eventBuffer.filter((e) => e.timestamp >= horizon);
  }

  private evaluateRageClicks(latestClick: InteractionEvent): void {
    if (!latestClick.coordinates) return;

    const recentClicks = this.eventBuffer.filter(
      (e) =>
        e.type === 'click' &&
        e.coordinates &&
        latestClick.timestamp - e.timestamp <= this.config.windowDurationMs
    );

    if (recentClicks.length >= this.config.rageClickThreshold) {
      const isClustered = recentClicks.every((c) => {
        const dx = c.coordinates!.x - latestClick.coordinates!.x;
        const dy = c.coordinates!.y - latestClick.coordinates!.y;
        return Math.sqrt(dx * dx + dy * dy) <= this.config.maxDistancePx;
      });

      if (isClustered) {
        this.triggerContextualDiscovery('RAGE_CLICK_DETECTED', latestClick);
        // Flush buffer agar trigger tidak berulang secara spamming
        this.eventBuffer = [];
      }
    }
  }

  private triggerContextualDiscovery(reason: string, event: InteractionEvent): void {
    try {
      this.onTriggerSurvey(reason, {
        targetSelector: event.targetSelector,
        timestamp: Math.round(event.timestamp),
      });
    } catch (err) {
      console.error('[DiscoveryEngine] Gagal memicu contextual handler:', err);
    }
  }

  public destroy(): void {
    this.isDestroyed = true;
    if (typeof window !== 'undefined') {
      window.removeEventListener('click', this.handleGlobalClick, { capture: true });
    }
    this.eventBuffer = [];
  }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

* **Baris 2–19:** Deklarasi Interface Domain Teknis. Interface `InteractionEvent` merepresentasikan struktur atomik sinyal interaksi pengguna. Tipe koordinat opsional digunakan untuk deteksi spasial tanpa mencatat teks atau state aplikasi sensitif.
* **Baris 38–48:** Registrasi *Event Listener* Global. Menggunakan parameter `{ capture: true, passive: true }`. 
  * `capture: true` menjamin sinyal terdeteksi bahkan jika library UI turunan menjalankan `event.stopPropagation()` pada bubbling phase.
  * `passive: true` memberi garansi kepada browser rendering engine bahwa listener ini tidak akan pernah memanggil `preventDefault()`, mencegah lag eksekusi frame/scroll (menjaga skor INP).
* **Baris 63–76:** `sanitizeAndGenerateSelector(element)`. Sanitizer deterministik. Mencegah selector menelan class dinamis yang memuat token otentikasi atau data masukan user. Jika atribut `data-research-mask` aktif, informasi node diisolasi secara total menjadi `'masked-element'`.
* **Baris 87–90:** `pruneOldEvents(currentTime)`. Membersihkan memory footprint buffer secara berkala menggunakan model Time-to-Live (TTL) berdasar `windowDurationMs`. Ini mencegah *memory bloat* jangka panjang pada Single Page Applications (SPA).
* **Baris 92–114:** Evaluasi Heuristik Rage Click. Menggunakan kalkulasi Jarak Euclidean ($\sqrt{dx^2 + dy^2}$). Jika frekuensi klik dalam bounding box $\le 24\text{px}$ melebihi ambang batas ($\ge 3$), status *frustration condition* terpenuhi. Buffer langsung di-flush untuk mitigasi cascading micro-survey popups.
* **Baris 125–131:** `destroy()`. Lifecycle cleanup method. Menghapus event listener dan referensi array guna mencegah *detached DOM node leak* pada saat komponen unmount.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Skala Enterprise: "FinTech OmniPay Multi-Platform Merchant Checkout"
* **Konteks:** OmniPay memproses \$40 juta volume transaksi harian dari 85.000 merchant e-commerce via Web SDK dan Mobile App.
* **Gejala Masalah:** Terjadi penurunan drastis pada conversion rate checkout sebesar 14.8% setelah perilisan v3.4. Tim Product berasumsi bahwa skema pembayaran baru membingungkan user dan merencanakan pemugaran desain ulang UI (estimasi pengerjaan: 6 sprint engineering).
* **Investigasi Melalui Problem Discovery Engine:**
  1. *Kuantitatif Telemetry:* Interaction Engine mendeteksi anomali: tombol `[Pay Now]` mengalami *Rage Click Rate* 31.2% pada perangkat Safari iOS dan WebKit-based Mobile WebView.
  2. *In-App Micro-Survey Contextual Triggers:* Mesin riset secara otomatis memunculkan 1-click micro-survey kepada 200 user yang mengalami rage click: *"Apakah tombol berfungsi saat ditekan?"*. 89% menjawab *"Saya menekannya berulang kali, tidak ada respon apapun."*
  3. *Root Cause Analysis (RCA):* Ditemukan bahwa event listener tombol menggunakan `onPointerUp` yang bertabrakan dengan *gesture recognizer wrapper* milik payment security SDK pihak ketiga, menyebabkan event *swallowed* tanpa melempar runtime JavaScript error ke Sentry/Crashlytics.
* **Hasil:** Solusi tidak membutuhkan redesign antarmuka senilai 6 sprint. Masalah diselesaikan dalam 1 hari kerja melalui perbaikan penanganan propagation event pointer. Metrik konversi langsung pulih ke tingkat normal (penyelamatan estimasi omzet \$5.9 juta/bulan).

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Komponen React berikut mengintegrasikan runtime Heuristic Interaction Discovery dengan *Contextual In-App Micro Survey Drawer* yang accessible dan non-intrusif.

```tsx
// File: src/components/DiscoveryFeedbackWidget.tsx
import React, { useState, useEffect, useCallback, useId } from 'react';
import { InteractionDiscoveryEngine } from '../telemetry/DiscoveryCore';

interface FeedbackPayload {
  reason: string;
  targetSelector: string;
  comment: string;
  userRating: 'friction' | 'neutral' | 'smooth';
  timestamp: number;
}

interface DiscoveryFeedbackWidgetProps {
  apiEndpoint: string;
  sampleRate?: number; // 0.0 to 1.0
}

export const DiscoveryFeedbackWidget: React.FC<DiscoveryFeedbackWidgetProps> = ({
  apiEndpoint,
  sampleRate = 1.0,
}) => {
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [discoveryContext, setDiscoveryContext] = useState<{
    reason: string;
    targetSelector: string;
    timestamp: number;
  } | null>(null);
  const [comment, setComment] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const titleId = useId();
  const descId = useId();

  const handleSurveyTrigger = useCallback(
    (reason: string, context: { targetSelector: string; timestamp: number }) => {
      // Sampling guard untuk menghindari survei berlebihan ke seluruh populasi
      if (Math.random() > sampleRate) return;

      // Cegah trigger jika survei sedang aktif
      setIsOpen((prevOpen) => {
        if (prevOpen) return prevOpen;
        setDiscoveryContext({ reason, ...context });
        return true;
      });
    },
    [sampleRate]
  );

  useEffect(() => {
    const engine = new InteractionDiscoveryEngine(
      { rageClickThreshold: 3, windowDurationMs: 600, maxDistancePx: 30 },
      handleSurveyTrigger
    );

    return () => {
      engine.destroy();
    };
  }, [handleSurveyTrigger]);

  const dispatchTelemetry = async (payload: FeedbackPayload): Promise<void> => {
    const serialized = JSON.stringify(payload);

    // Prioritaskan sendBeacon untuk keandalan transmisi tanpa memblokir thread
    if (typeof navigator !== 'undefined' && navigator.sendBeacon) {
      const blob = new Blob([serialized], { type: 'application/json' });
      const success = navigator.sendBeacon(apiEndpoint, blob);
      if (success) return;
    }

    // Fallback menggunakan fetch async jika sendBeacon gagal/tidak tersedia
    await fetch(apiEndpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: serialized,
      keepalive: true,
    });
  };

  const handleSubmit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    if (!discoveryContext) return;

    setIsSubmitting(true);
    const payload: FeedbackPayload = {
      reason: discoveryContext.reason,
      targetSelector: discoveryContext.targetSelector,
      comment: comment.trim(),
      userRating: 'friction',
      timestamp: Date.now(),
    };

    try {
      await dispatchTelemetry(payload);
    } catch (err) {
      console.warn('[DiscoveryFeedback] Gagal mengirim data telemetri:', err);
    } finally {
      setIsSubmitting(false);
      setIsOpen(false);
      setComment('');
      setDiscoveryContext(null);
    }
  };

  if (!isOpen) return null;

  return (
    <aside
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      aria-describedby={descId}
      style={{
        position: 'fixed',
        bottom: '24px',
        right: '24px',
        width: '320px',
        backgroundColor: '#ffffff',
        boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)',
        borderRadius: '8px',
        padding: '16px',
        zIndex: 99999,
        border: '1px solid #e2e8f0',
        fontFamily: 'system-ui, -apple-system, sans-serif',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 id={titleId} style={{ margin: 0, fontSize: '14px', fontWeight: 600, color: '#0f172a' }}>
          Kendala Terdeteksi
        </h3>
        <button
          onClick={() => setIsOpen(false)}
          aria-label="Tutup dialog feedback"
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            fontSize: '16px',
            color: '#64748b',
          }}
        >
          ×
        </button>
      </div>

      <p id={descId} style={{ fontSize: '12px', color: '#475569', margin: '8px 0 12px 0' }}>
        Sepertinya terjadi kendala saat Anda menekan area antarmuka ini. Boleh beri tahu kami apa
        yang Anda harapkan?
      </p>

      <form onSubmit={handleSubmit}>
        <textarea
          required
          rows={3}
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder="Contoh: Saya menekan tombol, tapi halaman tidak berpindah..."
          aria-label="Jelaskan kendala Anda"
          style={{
            width: '100%',
            boxSizing: 'border-box',
            fontSize: '12px',
            padding: '8px',
            borderRadius: '4px',
            border: '1px solid #cbd5e1',
            resize: 'none',
            marginBottom: '12px',
          }}
        />

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
          <button
            type="button"
            disabled={isSubmitting}
            onClick={() => setIsOpen(false)}
            style={{
              padding: '6px 12px',
              fontSize: '12px',
              backgroundColor: '#f1f5f9',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
            }}
          >
            Abaikan
          </button>
          <button
            type="submit"
            disabled={isSubmitting || !comment.trim()}
            style={{
              padding: '6px 12px',
              fontSize: '12px',
              backgroundColor: '#0284c7',
              color: '#ffffff',
              border: 'none',
              borderRadius: '4px',
              cursor: isSubmitting || !comment.trim() ? 'not-allowed' : 'pointer',
            }}
          >
            {isSubmitting ? 'Mengirim...' : 'Kirim'}
          </button>
        </div>
      </form>
    </aside>
  );
};
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Aspek Pendekatan | Micro-Survey Kontekstual In-App | Session Replay Penuh (misal: LogRocket/FullStory) | Telemetri Kuantitatif Murni (Aggregated APM) | User Interview Kualitatif Tradisional |
| :--- | :--- | :--- | :--- | :--- |
| **Overhead CPU / Render** | **Sangat Rendah** (Event pointer pasif, sliding window array kecil) | **Tinggi** (MutationObserver konstan, DOM cloning serialization) | **Sangat Rendah** (Counter metrics & batching log network) | **Nol** (Tidak menyentuh lingkungan sistem produksi) |
| **Konsumsi Network Payload** | **Rendah** (< 1 KB data JSON saat dipicu insiden) | **Sangat Tinggi** (Ratusan KB hingga MB per sesi kompresi) | **Sangat Rendah** (Payload batching teragregasi) | **Nol** |
| **Akurasi Konteks Masalah** | **Tinggi** (Pengguna mengartikulasikan maksud secara instan di tempat kejadian) | **Tinggi** (Visual inspeksi alur langkah pengguna) | **Rendah** (Hanya tahu ada drop-off, tidak tahu motif "mengapa") | **Sangat Tinggi secara emosional**, tetapi rentan bias lupa alur |
| **Kepatuhan Privasi Data** | **Tinggi secara Inheren** (Tidak menyimpan state/input kecuali text feedback) | **Sangat Kritis** (Risiko kebocoran form PII tinggi jika masking bocor) | **Tinggi** (Hanya numeric aggregates tanpa identifier personal) | **Tinggi** (Sesuai protokol NDA dan informed consent eksplisit) |
| **Skalabilitas Eksekusi** | **Sangat Luas** (Berjalan otomatis melalui kode produksi) | **Terbatas Biaya** (Biaya storage & ingestion vendor sangat mahal) | **Sangat Luas** (Mampu menampung jutaan RPS) | **Sangat Sempit** (Dibatasi kapasitas waktu jam kerja manusia) |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Dynamic Virtualized List Trap
* **Problem:** Pada virtual list (`react-window`, `FlatList`), target DOM element di-unmount seketika saat pengguna scroll cepat.
* **Failure Mode:** Selector resolver merujuk ke elemen yang sudah terhapus (`detached DOM node`). Jika engine mempertahankan referensi native node, terjadi Memory Leak parah.
* **Mitigasi:** Segera serialisasi elemen ke bentuk string primitif (`tagName + stable data attributes`) dan jangan simpan *hard reference* ke `HTMLElement`.

### 2. Gesture Collisions pada Mobile & Hybrid WebView
* **Problem:** Pada perangkat sentuh, *double tap to zoom* atau *pinch gestures* dapat secara keliru didiagnosis sebagai *Rage Taps*.
* **Failure Mode:** Survey popup muncul terus-menerus saat user sedang mencoba membaca teks kecil melalui interaksi zoom-in.
* **Mitigasi:** Tambahkan verifikasi `event.pointerType !== 'touch'` atau filter multi-touch pointer event via `event.isPrimary === true`. Deteksi jumlah touch pointers aktif (`touches.length === 1`).

### 3. Loop Triggering Survey Fatigue
* **Problem:** Bug UI yang fatal pada tombol checkout memicu 50 rage click beruntun dalam 1 menit.
* **Failure Mode:** Pop-up feedback muncul berulang kali setiap 3 klik, menutupi layar dan memperburuk frustrasi pengguna.
* **Mitigasi:** Implementasikan **Session Cooldown Guard**. Gunakan state lokal `sessionStorage.setItem('discovery_survey_cooldown', timestamp)` untuk membatasi pemunculan survei maksimal 1 kali per pengguna per sesi.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Tracking Keystroke Input Menggunakan Global Keystroke Logger
* *Kesalahan Fatal:* Menambahkan global listener `window.addEventListener('keydown')` untuk mendeteksi *typing hesitation*.
* *Konsekuensi:* Password, nomor kartu kredit, dan PIN otentikasi terekam ke memory string buffer; pelanggaran hukum berat (GDPR / PCI-DSS).
* *Solusi:* Jangan pernah merekam keystroke karakter. Hanya ukur metrik abstrak seperti `timeToFirstKeypress` atau hitung jumlah event `keydown` tanpa mengakses atribut `event.key` atau `event.code`.

### 2. Blocking Render Thread dengan Heavy Selectors
* *Kesalahan Fatal:* Menghitung DOM path menggunakan traversal rekursif mendalam (`parent.parentElement...`) di dalam click listener synchronous.
* *Konsekuensi:* Mengakibatkan frame jank langsung pada interaksi pengguna, mendegradasi metrik Interaction to Next Paint (INP) di atas 200ms.
* *Solusi:* Batasi kedalaman pencarian selector maksimal 2 level ke atas (depth $\le 2$) dan gunakan atribut `data-testid` atau `data-tracking-id` deterministik.

### 3. Mengandalkan Data Kualitatif dari "Vocal Minority"
* *Kesalahan Fatal:* Mengubah roadmap rekayasa sistem hanya berdasarkan komplain satu akun enterprise di media sosial atau user interview tanpa memeriksa telemetri analitik.
* *Konsekuensi:* Tim menghabiskan kuartal kerja membangun fitur yang hanya digunakan oleh < 0.01% dari total basis pengguna.
* *Solusi:* Sebelum menulis satu baris kode untuk solusi, kuantifikasi dampak menggunakan query agregat telemetri sistem:
  
  $$\text{Impact Metric} = \text{Unique Impacted Users} \times \text{Transaction Drop Rate}$$

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

### Skema Pelabelan Semantik Data Tracking
Jangan gunakan nama kelas dinamis CSS modules atau Styled