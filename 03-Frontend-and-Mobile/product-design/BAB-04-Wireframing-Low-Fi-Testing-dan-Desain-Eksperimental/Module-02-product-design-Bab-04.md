# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 04: Wireframing, Low-Fi Testing, dan Desain Eksperimental**  
**Kategori: 03-Frontend-and-Mobile / product-design**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Merancang dan mengimplementasikan arsitektur sistem berbasis Server-Driven UI (SDUI) dan Feature Flagging engine untuk memvalidasi wireframe dan purwarupa *low-fidelity* (Low-Fi) langsung di lingkungan staging/produksi tanpa siklus rilis *native binary* yang lambat.
- Mengotomatisasi translasi *wireframe layout contract* berbasis JSON Schema ke dalam *runtime component harness* menggunakan TypeScript dan React/React Native.
- Membangun *instrumentation telemetry pipeline* tingkat lanjut (event tracking, latency monitoring, dan interaction heatmaps) guna mengukur metrik keberhasilan validasi desain eksperimental (*task completion rate*, *time-to-task*, *drop-off rate*).
- Menerapkan metodologi A/B/n testing dan *Multi-Armed Bandit* (MAB) di tingkat arsitektur front-end untuk memitigasi risiko regresi UX sebelum merilis desain *high-fidelity*.
- Mengelola mitigasi performa dan tata kelola *design debt* saat mengeksekusi puluhan varian eksperimen secara paralel pada aplikasi enterprise berskala jutaan pengguna aktif harian (DAU).

---

## 2. Prerequisite

Peserta wajib menguasai:
- **Core Frontend Engineering**: TypeScript tingkat lanjut (conditional types, generics, mapped types, template literal types), React 18+ (Suspense, Concurrent Mode, Profiler API).
- **State Management & Data Fetching**: React Query/TanStack Query, State Machine (XState) untuk orchestrating UX user flows.
- **Micro-Frontend / SDUI Concept**: Pemahaman tentang decoupling UI layout dari hardcoded view layer melalui remote JSON Schema.
- **Dasar Testing UX**: Familiaritas dengan System Usability Scale (SUS), cognitive walkthroughs, dan statistical testing (Hypothesis testing, P-value, Sample Size calculation, Bayesian vs Frequentist).
- **Tooling**: Node.js v18+, Docker, Kafka/Event Bus primitives, serta OpenFeature/LaunchDarkly/GrowthBook SDKs.

---

## 3. Concept & Internal Architecture (Mendalam)

Eksperimen desain dan validasi wireframe skala enterprise tidak lagi bertumpu pada file statis Figma atau mockups semata. Pada tingkat arsitektur produksi, validasi Low-Fi/Wireframe diterapkan secara dinamis melalui pola **Server-Driven Experimental Harness**.

### Arsitektur Inti: The Wireframe-to-Experiment Engine

```
[ Layout/Wireframe Spec ] (Figma Tokens / JSON Schema)
           │
           ▼
[ Design-to-Code Schema Compiler ]
           │
           ▼
┌────────────────────────────────────────────────────────┐
│ Edge / API Gateway (Routing & User Segmentation Engine)│
│  - Edge Workers (Cloudflare Workers / Vercel Edge)     │
│  - Context Injection (User ID, Device, Geolocation)    │
└────────────────────────────────────────────────────────┘
           │
           ├── Variant A (Baseline / Control)
           ├── Variant B (Wireframe Low-Fi Layout v1 - High Information Density)
           └── Variant C (Wireframe Low-Fi Layout v2 - Progressive Disclosure)
           │
           ▼
┌────────────────────────────────────────────────────────┐
│ Client-side Experimental Core Harness                  │
│  - Dynamic Component Registry                          │
│  - Schema Dynamic Renderer (SDUI Fallback Engine)      │
│  - Telemetry & Event Interceptor (Click, Scroll, Idle) │
└────────────────────────────────────────────────────────┘
           │
           ▼
[ High-Throughput Ingestion Pipeline (Kafka -> ClickHouse) ]
           │
           ▼
[ Statistical Significance Engine (Bayesian Inference API) ]
```

### Mekanisme Internal Komponen:

1. **Schema Registry & Wireframe Contract**:
   Komponen wireframe diabstraksikan menjadi blok fungsional: `LayoutContainer`, `PlaceholderSlot`, `ActionTrigger`, `TextContent`, dan `MediaSkeleton`. Blok-blok ini tidak memiliki dependensi terhadap visual polish (CSS gradient, rounded corner mikro, dsb.), melainkan didefinisikan secara ketat oleh *spatial geometry*, *visual hierarchy*, dan *action pathways*.
   
2. **Server-Driven UI (SDUI) Renderer**:
   Client tidak lagi mengompilasi view secara statis. Server mengembalikan payload JSON terkompresi yang menginstruksikan client komponen apa yang harus di-mount, urutan hierarki layout-nya, serta target mutasi state (`action_id`).

3. **Contextual Feature Flag Evaluation**:
   Variasi wireframe diinjeksi via edge proxy menggunakan Zero-Latency Flag Evaluation Engine (berbasis WASM). Segmentasi pengguna dievaluasi dalam waktu kurang dari 5ms sebelum dokumen HTML atau tree JSON direspons ke client, menghilangkan Cumulative Layout Shift (CLS) dan FOUC (Flash of Unstyled Content).

4. **Telemetry Ingestion Loop**:
   Setiap interaksi pada elemen Low-Fi di-proxy oleh *Telemetry Interceptor*. Payload interaksi memuat data struktural (`component_id`, `layout_version`, `viewport_density`, `interaction_timestamp`, `dwell_time_ms`) yang dipancarkan secara asynchronous melalui Web Worker atau `navigator.sendBeacon` ke Kafka cluster untuk dianalisis oleh statistical compute pipeline.

---

## 4. Why & What

| Dimensi | Pendekatan Konvensional (Static Mockup/Hi-Fi First) | Pendekatan Enterprise Engineering (Code-Level Low-Fi Testing) |
| :--- | :--- | :--- |
| **Siklus Umpan Balik** | 4-6 minggu (Figma -> Usertesting -> Sprint Hi-Fi Dev -> App Store Review). | 24-48 jam (Wireframe Schema -> Edge Rollout -> 10.000 live sessions -> Data Signal). |
| **Bias Validasi** | *Aesthetic-Usability Effect* palsu; user menyukai desain karena warna/ilustrasi indah, padahal navigasi rusak. | Reduksi bias visual total; user dipaksa berfokus mutlak pada *information architecture*, *flow logic*, dan *affordance*. |
| **Delivery Cost** | Mahal; engineer menulis kode CSS mikro, animasi kompleks, dan asset berat untuk flow yang mungkin dibuang. | Rendah; menggunakan semantic tokens, wireframe component skeletons, dan programmatic data binding. |
| **Skala Testing** | N = 5-10 user moderated sessions (rawan sampling bias). | N = ribuan hingga jutaan pengguna melalui unmoderated in-app production experiment testing. |
| **Arsitektur Front-End** | Monolitik, view component di-hardcode di dalam client bundle. | Decoupled; UI bersifat contract-driven, mempermudah eksperimen paralel tanpa merge conflict. |

---

## 5. How (Workflow Detail)

Alur kerja production-grade untuk menjalankan *Experimental Low-Fi Testing*:

```
1. Design Spec Phase
   ├── Desainer mendefinisikan Information Architecture & Task Flow.
   └── Output: Wireframe Blueprint JSON Schema (bukan mockup pixel-perfect).

2. Contract Validation & Tokenization
   ├── Validasi Schema melalui CI/CD pipeline (AJV / Zod).
   └── Mapping Token Layout: Pengecekan semantic spacing, grid layout, dan responsive breakpoints.

3. Edge Deployment & Variant Assignment
   ├── Deployment konfigurasi ke Edge Flag Engine.
   └── Hashing User ID (misal: MurmurHash3) untuk deterministic variant allocation (Control vs Experiment).

4. Dynamic Execution & Instrumentation
   ├── Client bootstrap -> Request SDUI layout payload.
   ├── Dynamic Component Loader me-render Low-Fi Harness Components.
   └── Telemetry Engine merekam seluruh interaksi mikro (dwell time, misclicks, dead clicks, task completion).

5. Quantitative Telemetry Aggregation
   ├── Kafka -> Streaming pipeline (Apache Flink / Vector) -> ClickHouse.
   └── Komputasi konversi secara continuous menggunakan model Bayesian A/B test.

6. Gradual Rollout / Termination
   ├── Jika Probability of Being Best (PBB) > 95% dan Value Remaining < 1%:
   │     Promosikan Wireframe ke fase Hi-Fi Engineering (Sprint Dev).
   └── Jika terdeteksi peningkatan bounce rate secara statistically significant:
         Circuit breaker terpicu otomatis; matikan variant via Edge Engine.
```

---

## 6. Analogy & Diagram ASCII

### Analogi Teknik Sipil: Konstruksi Baja vs Pengecatan Interior
Mengembangkan produk langsung ke tahap *High-Fidelity* tanpa pengujian *Low-Fidelity* fungsional diibaratkan seperti membangun gedung pencakar langit dengan langsung memasang wallpaper mewah, marmer Italia, dan kaca patri, sebelum struktur kolom beton dan jalur pipa air diuji tekanannya. 

Jika terdapat kebocoran pipa utama (masalah *Information Architecture*), Anda harus meruntuhkan seluruh marmer mahal tersebut untuk memperbaiki sambungan pipa. Wireframing dan Low-Fi Testing di level kode adalah pemasangan rangka baja fungsional dan pipa *dry-run*: tidak menarik dipandang, namun memastikan integritas struktural, gravitasi alur beban, dan jalur darurat berjalan sempurna sebelum lapisan estetika diinvestasikan.

### Arsitektur Alur Interaksi dan Telemetri Runtime

```
+-----------------------------------------------------------------------------------+
| BROWSER / CLIENT RUNTIME (Next.js / React Native)                                 |
|                                                                                   |
|  +--------------------+         +-----------------------------------------------+  |
|  | Context Provider   |         | Component Registry                            |  |
|  | (User, Experiment) |         |  - "wireframe-container" -> LowFiContainer    |  |
|  +---------+----------+         |  - "cta-action"           -> LowFiCTAButton   |  |
|            |                    |  - "data-slot"            -> WireframeSkeleton|  |
|            v                    +-----------------------+-----------------------+  |
|  +--------------------+                                 |                         |
|  | SDUI Layout Parser | <───────────────────────────────+                         |
|  +---------+----------+                                                           |
|            |                                                                      |
|            v                                                                      |
|  +-----------------------------------------------------------------------------+  |
|  | Render Tree (Wireframe Layout Test Harness)                                 |  |
|  |                                                                             |  |
|  |  [ LowFiContainer (Border: 1px dashed; Background: #f4f4f4) ]              |  |
|  |     ├── [ WireframeSkeleton (Type: 'headline', Width: '80%') ]              |  |
|  |     ├── [ WireframeSkeleton (Type: 'paragraph', Lines: 3) ]                 |  |
|  |     └── [ LowFiCTAButton (Action: 'SUBMIT_APPLICATION') ]                  |  |
|  |               │                                                             |  |
|  +---------------+-------------------------------------------------------------+  |
|                  │ Click/Interaction Event                                        |
|                  v                                                                |
|  +-----------------------------------------------------------------------------+  |
|  | Telemetry Interceptor Hub                                                   |  |
|  |   - Enqueue event: { variant: 'wireframe_B', action: 'click', latency: 120ms}|  |
|  |   - Batch dispatch via navigator.sendBeacon                                 |  |
|  +---------------------------------------+-------------------------------------+  |
+------------------------------------------|----------------------------------------+
                                           |
                                           v HTTPS POST (Batched Analytics Payload)
+-----------------------------------------------------------------------------------+
| INGESTION EDGE API / EVENT BUS                                                    |
|                                                                                   |
|   /api/v1/telemetry/ux-experiment                                                 |
|     │                                                                             |
|     ├── Validate Event Schema (Protobuf / JSON Schema)                            |
|     └── Produce to Kafka Topic: `experiment.telemetry.events`                     |
+-----------------------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### Simple Example: Deklarasi Schema Wireframe Kontrak Antarmuka

```typescript
// types/wireframe.ts
export type WireframeNodeType = 
  | 'layout-container'
  | 'text-skeleton'
  | 'button-slot'
  | 'input-wireframe';

export interface WireframeNode {
  id: string;
  type: WireframeNodeType;
  props: {
    label?: string;
    width?: string | number;
    height?: string | number;
    lines?: number;
    actionId?: string;
    testId: string;
  };
  children?: WireframeNode[];
}

export interface WireframeLayoutContract {
  layoutId: string;
  experimentKey: string;
  version: number;
  root: WireframeNode;
}
```

### Practical Example: Production-Grade SDUI Layout Engine dengan Dynamic Tracking

Di bawah ini adalah implementasi sistem produksi yang mengevaluasi varian eksperimen secara asinkron, memetakan schema wireframe ke dalam komponen antarmuka, dan mencegat seluruh interaksi untuk telemetri analitik unmoderated.

```tsx
// components/experimental/WireframeHarness.tsx
import React, { createContext, useContext, useEffect, useRef } from 'react';

// --- CONTRACT & INTERFACES ---
export interface WireframeTelemetryPayload {
  experimentId: string;
  variantId: string;
  elementId: string;
  actionId?: string;
  eventType: 'impression' | 'click' | 'dwell';
  durationMs?: number;
  metadata?: Record<string, unknown>;
}

export interface TelemetryClient {
  track: (payload: WireframeTelemetryPayload) => void;
}

const TelemetryContext = createContext<{
  experimentId: string;
  variantId: string;
  client: TelemetryClient;
} | null>(null);

// --- TELEMETRY HOOK ---
export const useWireframeTelemetry = (elementId: string, actionId?: string) => {
  const context = useContext(TelemetryContext);
  const mountTime = useRef<number>(Date.now());

  useEffect(() => {
    if (!context) return;
    
    // Track Impression on mount
    context.client.track({
      experimentId: context.experimentId,
      variantId: context.variantId,
      elementId,
      eventType: 'impression',
    });

    return () => {
      // Track Dwell Time on unmount
      const dwellTime = Date.now() - mountTime.current;
      context.client.track({
        experimentId: context.experimentId,
        variantId: context.variantId,
        elementId,
        eventType: 'dwell',
        durationMs: dwellTime,
      });
    };
  }, [elementId, context]);

  const recordClick = () => {
    if (!context) return;
    context.client.track({
      experimentId: context.experimentId,
      variantId: context.variantId,
      elementId,
      actionId,
      eventType: 'click',
    });
  };

  return { recordClick };
};

// --- LOW-FI HARNESS COMPONENTS ---
export const WireframeContainer: React.FC<{
  direction?: 'row' | 'column';
  spacing?: number;
  padding?: number;
  children: React.ReactNode;
  testId: string;
}> = ({ direction = 'column', spacing = 16, padding = 16, children, testId }) => {
  return (
    <div
      data-testid={testId}
      style={{
        display: 'flex',
        flexDirection: direction,
        gap: `${spacing}px`,
        padding: `${padding}px`,
        border: '1px dashed #A0AEC0',
        backgroundColor: '#F7FAFC',
        borderRadius: '4px',
        width: '100%',
        boxSizing: 'border-box',
      }}
    >
      {children}
    </div>
  );
};

export const WireframeTextSkeleton: React.FC<{
  lines?: number;
  width?: string;
  elementId: string;
}> = ({ lines = 1, width = '100%', elementId }) => {
  useWireframeTelemetry(elementId);

  return (
    <div style={{ width, display: 'flex', flexDirection: 'column', gap: '8px' }}>
      {Array.from({ length: lines }).map((_, idx) => (
        <div
          key={idx}
          style={{
            height: '14px',
            backgroundColor: '#CBD5E0',
            borderRadius: '2px',
            width: idx === lines - 1 && lines > 1 ? '60%' : '100%',
          }}
        />
      ))}
    </div>
  );
};

export const WireframeButtonSlot: React.FC<{
  elementId: string;
  actionId: string;
  label: string;
  onExecuteAction: (actionId: string) => void;
}> = ({ elementId, actionId, label, onExecuteAction }) => {
  const { recordClick } = useWireframeTelemetry(elementId, actionId);

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    recordClick();
    onExecuteAction(actionId);
  };

  return (
    <button
      onClick={handleClick}
      style={{
        padding: '12px 24px',
        backgroundColor: '#4A5568',
        color: '#FFFFFF',
        border: 'none',
        borderRadius: '4px',
        cursor: 'pointer',
        fontWeight: 600,
        fontSize: '14px',
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
        outline: 'none',
      }}
    >
      {label}
    </button>
  );
};

// --- DYNAMIC RUNTIME ENGINE ---
export interface NodeConfig {
  id: string;
  type: 'container' | 'skeleton' | 'button';
  props: Record<string, any>;
  children?: NodeConfig[];
}

export const WireframeRenderer: React.FC<{
  node: NodeConfig;
  onAction: (actionId: string) => void;
}> = ({ node, onAction }) => {
  switch (node.type) {
    case 'container':
      return (
        <WireframeContainer
          testId={node.props.testId || node.id}
          direction={node.props.direction}
          spacing={node.props.spacing}
          padding={node.props.padding}
        >
          {node.children?.map((child) => (
            <WireframeRenderer key={child.id} node={child} onAction={onAction} />
          ))}
        </WireframeContainer>
      );
    case 'skeleton':
      return (
        <WireframeTextSkeleton
          elementId={node.id}
          lines={node.props.lines}
          width={node.props.width}
        />
      );
    case 'button':
      return (
        <WireframeButtonSlot
          elementId={node.id}
          actionId={node.props.actionId}
          label={node.props.label}
          onExecuteAction={onAction}
        />
      );
    default:
      console.warn(`Unrecognized schema node type: ${(node as any).type}`);
      return null;
  }
};

// --- TELEMETRY DISPATCH SINK (HTTP TRANSPORT) ---
export const createProductionTelemetrySink = (endpoint: string): TelemetryClient => ({
  track: (payload: WireframeTelemetryPayload) => {
    const blob = new Blob([JSON.stringify(payload)], { type: 'application/json' });
    if (navigator.sendBeacon) {
      navigator.sendBeacon(endpoint, blob);
    } else {
      fetch(endpoint, {
        method: 'POST',
        body: blob,
        keepalive: true,
        headers: { 'Content-Type': 'application/json' },
      }).catch((err) => console.error('Telemetry fallback failed', err));
    }
  },
});
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Re-Arsitektur Sistem Checkout Marketplace Fintech Internasional
- **Konteks**: Platform e-commerce B2B/Fintech multi-regional dengan volume transaksi bruto harian (GTV) USD $12 juta dan rerata checkout harian 450.000 transaksi.
- **Masalah**: Funnel konversi checkout desktop & mobile web stagnan di angka 62.4%. Tim Design mengusulkan perombakan total dari *Accordion Flow* konvensional menjadi *Single-Page Adaptive Flow*. Namun, merekayasa desain *High-Fidelity* lengkap (termasuk micro-interactions, localization, asset visual, dan revisi state manajemen kompleks) diproyeksikan memakan waktu 12 minggu sprint engineer (estimasi biaya opportunity loss: ~$300k).
- **Implementasi Solusi Menggunakan Code-Level Low-Fi Testing**:
  1. Frontend Core Team memetakan struktur checkout ke dalam *Server-Driven Wireframe JSON Schema*.
  2. Dibuat 3 varian arsitektural berbasis komponen *monochrome wireframe* tanpa elemen grafis riil:
     - **Variant 0 (Control)**: UI High-Fi Lama (Accordion).
     - **Variant 1 (Wireframe Low-Fi A)**: Single Page Linear dengan Sticky Floating Action.
     - **Variant 2 (Wireframe Low-Fi B)**: Multi-step Wizard dengan Progressive Contextual Disclosure.
  3. Menggunakan Cloudflare Workers di level Edge, 10% traffic dialihkan ke varian Low-Fi. User diberikan micro-copy eksplisit: *"Anda sedang menggunakan Antarmuka Eksperimental Cepat"* untuk mengisolasi ekspektasi visual.
  4. Telemetri mencatat: *Time-to-Transaction*, *Validation Error Triggers*, *Scroll Drop-off*, dan *Payment Success Rate*.
- **Hasil Metrik Produksi**:
  - *Variant 1* menghasilkan penurunan *Time-to-Transaction* sebesar 34% (dari 3 menit 12 detik menjadi 2 menit 07 detik).
  - Terjadi peningkatan penyelesaian transaksi sebesar +4.8% secara statistically significant ($p < 0.001$, Bayesian Credible Interval [3.9%, 5.7%]).
  - Sebaliknya, *Variant 2* memperlihatkan cognitive load berlebih pada tahap pemilihan metode termin kredit (lonjakan *drop-off* 14%).
- **Dampak Finansial**: Desain High-Fidelity hanya diimplementasikan untuk *Variant 1*, menghemat 8 minggu siklus engineering sia-sia dan mengamankan proyeksi tambahan pendapatan tahunan sebesar $21.6 Juta.

---

## 9. Trade-offs (Performance, Latency, Scalability, Cost)

```
                       [ Architectural Trade-Off Space ]
                               
                                Dynamic Agility
                                     ▲
                                    / \
                                   /   \
                                  /  *  \  <-- Edge SDUI + Wireframe Engine
                                 /       \     (High Agility, Moderate Latency)
                                /         \
       Static Client Bundle    /___________\  Edge SSR / Streaming
  (Zero Latency, Low Agility)                 (High Cost, Extreme Scale)
```

| Parameter | Statis Hardcoded (Native Bundle) | Server-Driven Wireframe Harness | Client-Side Injected Overlays |
| :--- | :--- | :--- | :--- |
| **First Contentful Paint (FCP)** | Sangat Rendah (~0.8s) – Komponen sudah di-*compile* sebelumnya. | Rendah (~1.1s) – Butuh extra round-trip fetch layout JSON Schema jika tidak di-edge SSR. | Buruk (~2.5s) – FOUC dan DOM patching berat via third-party scripts. |
| **Edge Compute Cost** | Nol (Static Assets dilayani via CDN Storage biasa). | Sedang – Perlu komputasi edge worker untuk resolusi segmentasi dan AB routing. | Nol untuk infrastruktur sendiri, namun vendor cost platform pihak ketiga sangat mahal. |
| **Engineering Rigidity** | Kaku – Perubahan struktur wireframe menuntut CI/CD pipeline lengkap & app release. | Sangat Fleksibel – Perubahan layout cukup dengan memodifikasi payload di database schema. | Sangat Fleksibel, namun menghasilkan *technical debt* berupa brittle CSS selectors. |
| **Bundle Size Overhead** | Minimal – Tree-shaking optimal berjalan pada build time. | Sedang – Dynamic schema parser library dan Wireframe Harness skeletons menambah ~15-25KB gzipped. | Masif – Pihak ketiga menginjeksi runtime script 100KB+. |
| **Data Integrity / Privacy** | 100% terkontrol di bawah First-Party Network Domain. | 100% terkontrol (Audit compliance internal/GDPR/SOC2 terjamin). | Rentan kebocoran PII melalui script analitik pihak ketiga. |

---

## 10. Common Mistakes & Troubleshooting

### 1. The Aesthetic-Contamination Trap
* **Gejala**: Engineer menambahkan micro-styling (shadows, gradients, rounded corners kompleks, custom typography) ke dalam komponen Low-Fi testing karena inisiatif pribadi.
* **Akar Masalah**: Ketidakpahaman prinsip isolasi variabel. Ketika visual dipercantik, kita tidak lagi menguji *Information Architecture (IA)*, melainkan *Visual Appeal*.
* **Mitigasi**: Kunci design tokens pada komponen harness secara statis: hanya gunakan palet Grayscale (`#000000`, `#FFFFFF`, `#A0AEC0`, `#EDF2F7`), sans-serif standar OS (`system-ui`), dan tidak ada transisi CSS berdurasi di atas 0ms.

### 2. Layout Shift Flashing (CLS Penalty)
* **Gejala**: Skor CLS (Cumulative Layout Shift) melonjak di atas 0.25 pada varian eksperimen saat testing di live environment.
* **Akar Masalah**: Dynamic Schema di-fetch di client-side menggunakan `useEffect` setelah DOM utama ter-render (*client-side mounting race condition*).
* **Mitigasi**: Lakukan layout injection di Edge Middleware atau Server Component (RSC) level. Injeksi skeleton placeholder dengan dimensi eksplisit (`aspect-ratio` atau fixed `min-height`) sebelum data skema selesai di-resolve.

### 3. Asynchronous Telemetry Loss (Beacon Drop)
* **Gejala**: Event metrik drop-off menunjukkan anomali data (misal: 0% bounce rate pada page tertentu, yang secara statistik mustahil).
* **Akar Masalah**: Panggilan API tracking dibatalkan oleh browser ketika user menutup tab atau melakukan navigasi halaman karena menggunakan `fetch()` standar tanpa `keepalive: true`.
* **Mitigasi**: Gunakan `navigator.sendBeacon(url, data)` sebagai transport layer mutlak untuk telemetri unmount/leave page. Buat fallback transparan ke `fetch` berstatus `keepalive: true` bila ukuran buffer melebihi 64KB.

---

## 11. Best Practices (Production Checklist)

### Fase Desain & Kontrak
- [ ] Schema wireframe memiliki validasi tipe ketat (menggunakan Zod / JSON Schema Draft-07).
- [ ] Kontrak antarmuka tidak memuat atribut visual styling individual (tidak ada field `color`, `box-shadow`, dsb.); hanya properti struktural (`layout`, `gap`, `hierarchy`, `actionId`).
- [ ] Seluruh *Action ID* terpetakan ke dalam State Machine global yang memiliki handler validasi error yang seragam.

### Fase Implementasi Front-End & Telemetri
- [ ] Harness komponen memiliki fallback default jika schema JSON yang diterima korup atau parsial.
- [ ] Semua komponen interaktif wireframe mengimplementasikan atribut `data-testid` dan `aria-*` tags secara semantik untuk menjamin pengujian aksesibilitas (a11y).
- [ ] Interceptor telemetri menerapkan mekanisme throttling & batching (mengirimkan array event tiap interval 2000ms atau jika buffer mencapai 10 item).
- [ ] Perekaman waktu interaksi menggunakan `performance.now()` presisi tinggi, bukan `Date.now()`, guna mencegah skew akibat sinkronisasi jam OS.

### Fase Rollout & Analisis
- [ ] Edge router dikonfigurasi dengan fallback statis (*circuit breaker*): jika runtime parser gagal me-render wireframe dalam 50ms, sajikan Control UI original.
- [ ] Eksperimen dihitung menggunakan uji signifikansi Bayesian untuk meminimalkan durasi uji (*sample size starvation*).
- [ ] Seluruh flag eksperimental Low-Fi diberi TTL (Time-To-Live) maksimal 14 hari di edge engine untuk mencegah akumulasi *dead code* di sistem produksi.

---

## 12. Hands-on Practice

Simpan seluruh file praktikum ini di direktori: `hands-on/m02/`

### Struktur Direktori:
```
hands-on/m02/
├── package.json
├── tsconfig.json
├── schema/
│   └── wireframe-schema.json
├── src/
│   ├── engine.ts
│   ├── components.tsx
│   ├── telemetry.ts
│   └── index.ts
```

### File 1: `hands-on/m02/package.json`
```json
{
  "name": "enterprise-wireframe-testing-harness",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "build": "tsc",
    "start": "ts-node src/index.ts"
  },
  "dependencies": {
    "zod": "^3.22.4"
  },
  "devDependencies": {
    "@types/node": "^20.10.0",
    "ts-node": "^10.9.2",
    "typescript": "^5.3.3"
  }
}
```

### File 2: `hands-on/m02/src/telemetry.ts`
```typescript
export interface InteractionEvent {
  experimentId: string;
  variantId: string;
  elementId: string;
  actionId?: string;
  timestamp: number;
  durationMs?: number;
}

export class ProductionTelemetryPipeline {
  private buffer: InteractionEvent[] = [];
  private readonly flushThreshold: number = 5;

  constructor(private readonly endpoint: string) {}

  public record(event: Omit<InteractionEvent, 'timestamp'>): void {
    const fullEvent: InteractionEvent = {
      ...event,
      timestamp: Date.now(),
    };
    
    this.buffer.push(fullEvent);
    console.log(`[Telemetry Ingested] Element: ${event.elementId} | Variant: ${event.variantId}`);

    if (this.buffer.length >= this.flushThreshold) {
      this.flush();
    }
  }

  public flush(): void {
    if (this.buffer.length === 0) return;
    const payload = [...this.buffer];
    this.buffer = [];

    console.log(`[Telemetry Flush] Transmitting ${payload.length} events to ${this.endpoint}`);
    // Simulasi Network Dispatch
  }
}
```

### File 3: `hands-on/m02/src/engine.ts`
```typescript
import { z } from 'zod';

export const WireframeNodeSchema: z.ZodType<any> = z.lazy(() =>
  z.object({
    id: z.string(),
    type: z.enum(['container', 'text-skeleton', 'action-slot']),
    props: z.record(z.any()).default({}),
    children: z.array(WireframeNodeSchema).optional(),
  })
);

export const LayoutPayloadSchema = z.object({
  experimentId: z.string(),
  variantId: z.string(),
  targetFlow: z.string(),
  structure: WireframeNodeSchema,
});

export type WireframeNode = z.infer<typeof WireframeNodeSchema>;
export type LayoutPayload = z.infer<typeof LayoutPayloadSchema>;

export class WireframeCompiler {
  public static validateAndCompile(rawJson: unknown): LayoutPayload {
    const result = LayoutPayloadSchema.safeParse(rawJson);
    if (!result.success) {
      throw new Error(`Invalid Wireframe Contract: ${result.error.message}`);
    }
    return result.data;
  }
}
```

### File 4: `hands-on/m02/src/index.ts`
```typescript
import { WireframeCompiler } from './engine';
import { ProductionTelemetryPipeline } from './telemetry';

const mockRawServerPayload = {
  experimentId: "exp_checkout_streamline_001",
  variantId: "wireframe_variant_b",
  targetFlow: "quick_checkout",
  structure: {
    id: "root-container",
    type: "container",
    props: { direction: "column", spacing: 24 },
    children: [
      {
        id: "header-skeleton",
        type: "text-skeleton",
        props: { lines: 2, width: "75%" }
      },
      {
        id: "payment-methods-slot",
        type: "container",
        props: { direction: "row", spacing: 12 },
        children: [
          {
            id: "btn-pay-card",
            type: "action-slot",
            props: { label: "Credit Card", actionId: "SELECT_CC" }
          },
          {
            id: "btn-pay-crypto",
            type: "action-slot",
            props: { label: "Crypto Currency", actionId: "SELECT_CRYPTO" }
          }
        ]
      }
    ]
  }
};

function bootstrapExecution() {
  console.log("=== Mengompilasi Kontrak Wireframe Low-Fi ===");
  const compiledLayout = WireframeCompiler.validateAndCompile(mockRawServerPayload);
  console.log(`Berhasil memvalidasi Experiment: ${compiledLayout.experimentId}`);

  const telemetry = new ProductionTelemetryPipeline("https://telemetry.edge.internal/events");

  // Simulasi Interaksi User Melalui Runtime Runner
  console.log("\n=== Mensimulasikan Sesi Interaksi Pengguna ===");
  telemetry.record({
    experimentId: compiledLayout.experimentId,
    variantId: compiledLayout.variantId,
    elementId: "header-skeleton"
  });

  telemetry.record({
    experimentId: compiledLayout.experimentId,
    variantId: compiledLayout.variantId,
    elementId: "btn-pay-card",
    actionId: "SELECT_CC"
  });

  telemetry.record({
    experimentId: compiledLayout.experimentId,
    variantId: compiledLayout.variantId,
    elementId: "btn-pay-crypto",
    actionId: "SELECT_CRYPTO"
  });

  telemetry.record({
    experimentId: compiledLayout.experimentId,
    variantId: compiledLayout.variantId,
    elementId: "root-container",
    durationMs: 1420
  });

  telemetry.record({
    experimentId: compiledLayout.experimentId,
    variantId: compiledLayout.variantId,
    elementId: "btn-pay-card",
    actionId: "EXECUTE_SUBMISSION"
  });
  
  // Buffer harus otomatis flush pada event ke-5
}

bootstrapExecution();
```

---

## 13. Exercise

### Level Easy
Modifikasi skema `WireframeNodeSchema` pada `hands-on/m02/src/engine.ts` untuk mendukung tipe node baru bernama `'input-field-skeleton'`. Node ini harus menerima properti opsional `placeholder` (string) dan `isRequired` (boolean). Pastikan kompilasi validasi berhasil dengan payload pengujian.

### Level Medium
Implementasikan interceptor telemetri berbasis *Dead Click Detection* pada modul `telemetry.ts`. Jika sebuah elemen non-interaktif (seperti `text-skeleton`) diklik lebih dari 3 kali dalam durasi kurang dari 1.5 detik oleh user, pipeline harus secara otomatis menghasilkan event bertipe `rage_click` lengkap dengan atribut `frequency` dan `targetElementId`.

### Level Hard
Buat fungsi simulasi *Edge Evaluator Router* yang mengimplementasikan deterministic hashing (misal: FNV-1a atau MurmurHash sederhana) berbasis string `userId`. Fungsi ini menerima `userId: string` dan daftar `variants: Array<{ id: string; weight: number }>`. Router harus mengalokasikan user ke varian layout wireframe secara konsisten tanpa menyimpan status (stateless) dan memverifikasi bahwa rasio distribusi traffic mendekati target bobot (uji dengan sampel $N = 100.000$ iterasi).

---

## 14. Challenge

**Skenario**: Anda adalah Staff Frontend Architect pada sistem Perbankan Inti (Core Banking). Tim Produk ingin merombak alur transfer antarbank bernilai tinggi (*High-Value Wire Transfer*) yang rentan terhadap human error (salah transfer rekening).

**Tantangan**:
1. Rancang arsitektur sistem berbasis **Server-Driven Dynamic Wireframing Harness** yang menguji 3 varian informasi hierarki Low-Fi pada 50.000 nasabah bisnis aktif tanpa merilis binary build baru ke iOS App Store dan Google Play Store.
2. Arsitektur harus mengisolasi sistem sedemikian rupa sehingga:
   - Tidak ada kebocoran nomor rekening atau saldo pengguna (PII) ke pipeline telemetri eksperimen.
   - Jika schema layout yang dikirimkan oleh remote edge mengalami latency network > 200ms, sistem secara mulus melakukan fallback (*fail-safe zero-overhead*) ke antarmuka native konvensional tanpa adanya pergeseran layout (layout shift) yang terlihat oleh nasabah.
   - Sediakan dokumen arsitektur dan state transition diagram (menggunakan format ASCII) yang memetakan bagaimana state mesin menangani kegagalan parsial pada koneksi ketika pengguna berada di tengah-tengah alur wireframe kritis tersebut.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Basic (Pilihan Ganda / Konseptual)
1. **Apa tujuan teknis utama dari pelaksanaan testing antarmuka menggunakan komponen Low-Fi / Wireframe dibandingkan langsung ke High-Fi?**
   - a. Meminimalkan biaya cloud hosting server.
   - b. Mengisolasi variabel Information Architecture dan cognitive task flow dari bias estetika visual (Aesthetic-Usability Effect).
   - c. Menghindari integrasi API backend pada antarmuka.
   - d. Menghilangkan kebutuhan penulisan unit test pada frontend code.

2. **Mengapa properti visual seperti gradient, drop shadow, dan hex warna custom harus ditiadakan dari Design Contract dalam Low-Fi experimental harness?**
   - a. Karena engine browser tidak sanggup me-render warna pada sistem A/B test.
   - b. Untuk mempertahankan prinsip deterministik tata letak dan memastikan user murni berinteraksi dengan struktur hierarki.
   - c. Karena standardisasi WCAG melarang penggunaan warna pada antarmuka eksperimen.
   - d. Agar ukuran file JSON schema selalu di bawah 100 bytes.

3. **Metode transport browser manakah yang paling reliabel untuk mengirimkan data analitik unmount/page exit pada pengujian UI?**
   - a. `WebSocket.send()`
   - b. Standard synchronous `XMLHttpRequest`
   - c. `navigator.sendBeacon()` dengan fallback ke `fetch` berstatus `keepalive: true`
   - d. Mengikatnya pada event `window.onclose` menggunakan recursive promise

4. **Dalam konteks Core Web Vitals, metrik apakah yang paling berisiko rusak jika rendering Server-Driven UI dinamis diimplementasikan secara buruk di sisi client?**
   - a. TTFB (Time to First Byte)
   - b. CLS (Cumulative Layout Shift)
   - c. INP (Interaction to Next Paint)
   - d. FCP (First Contentful Paint) saja

5. **Apa fungsi utama dari Dynamic Component Registry pada arsitektur eksperimen wireframe?**
   - a. Mengonversi kode JSON schema struktural menjadi pasangan komponen React/Native runtime yang valid secara deterministik.
   - b. Mengirimkan error logs secara langsung ke Sentry.
   - c. Menyimpan cache data profil pengguna di IndexedDB.
   - d. Mengatur autentikasi JWT token nasabah.

### Bagian B: Intermediate (Analisis Arsitektur)
1. **Jelaskan perbedaan mendasar dampak arsitektural antara Client-Side Script Injection (misal via Google Optimize / pihak ketiga) vs Server-Driven Feature Experimentation Engine.**
2. **Bagaimana cara mencegah Cumulative Layout Shift (CLS) ketika merender wireframe dinamis dari server yang membutuhkan waktu resolusi API ~80ms?**
3. **Mengapa evaluasi signifikansi berbasis Bayesian Inference sering kali lebih disukai daripada Frequentist t-test dalam eksperimen antarmuka Low-Fi tingkat produksi?**
4. **Sebutkan minimal 3 parameter telemetri esensial yang harus dicatat pada setiap elemen interaktif dalam eksperimen wireframe untuk mengukur *Usability Friction*.**
5. **Bagaimana arsitektur fallback (Circuit Breaker) harus bertindak jika payload JSON schema dari varian eksperimen terputus di tengah jalan (truncated/malformed payload)?**

### Bagian C: Skenario Kasus Produksi
1. **Skenario 1**: Sebuah platform e-commerce multi-kategori meluncurkan varian wireframe Low-Fi untuk sistem filter produk baru. Pada pengujian 20.000 user pertama, varian tersebut mencatatkan *Task Completion Rate* 15% lebih cepat, tetapi tingkat konversi pembelian akhir (*Checkout Conversion*) justru anjlok sebesar 8%. Jelaskan analisis investigasi Anda sebagai Staff Frontend Architect: apa anomali yang kemungkinan besar terjadi pada alur Information Architecture tersebut, dan metrik telemetri mikro apa yang harus Anda verifikasi?
2. **Skenario 2**: Sistem telemetri pengujian wireframe Anda menghasilkan lonjakan traffic 100.000 request per detik pada endpoint ingestion analitik. Hal ini menyebabkan degradation performa pada database relasional utama aplikasi. Jelaskan bagaimana Anda merekayasa ulang arsitektur ingestion pipeline telemetri dari client hingga storage data warehousing untuk menahan beban tersebut tanpa kehilangan satu pun event telemetri.
3. **Skenario 3**: Sebuah tim engineering mendapati bahwa varian A/B test wireframe mereka memicu perbedaan performa render yang drastis: Varian A (Control) memiliki frame rate 60 FPS stabil, sedangkan Varian B (Dynamic SDUI Wireframe) turun ke 35 FPS pada perangkat mobile low-end. Diagnosa kemungkinan bottleneck pada siklus rendering React/browser dan formulasikan rencana profiling serta remediasinya!

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Bagian A
1. **b** — Mengisolasi variabel Information Architecture dan cognitive flow tanpa distorsi visual polish.
2. **b** — Menjaga kemurnian pengujian kegunaan layout dan hierarki fungsional.
3. **c** — `navigator.sendBeacon()` dijamin dieksekusi secara asinkron oleh browser process background bahkan setelah konteks rendering dokumen hancur (page unload).
4. **b** — Perubahan struktur DOM secara dinamis di client-side tanpa reservasi spatial box memicu pergeseran elemen yang masif (CLS tinggi).
5. **a** — Component Registry adalah mapper antara nama string node dari contract JSON ke React Component implementation sesungguhnya.

#### Bagian B
1. **Analisis Jawaban**: Client-side injection memanipulasi DOM setelah parsing selesai, memicu FOUC/layout flicker hebat, ketergantungan script eksternal pemblokir render, dan celah keamanan CSP. Server-driven engine mengevaluasi alur pada Edge/Server, menyajikan DOM yang valid sejak awal, aman, dan tanpa penalti performa Core Web Vitals.
2. **Analisis Jawaban**: Memanfaatkan CSS `content-visibility`, styling SSR skeleton placeholder dengan dimensi tetap (`height`/`aspect-ratio`), atau menahan rendering stream menggunakan React Server Components (RSC) dengan Suspense boundaries yang terisolasi.
3. **Analisis Jawaban**: Bayesian memungkinkan interpretasi probabilitas langsung ("Varian B memiliki peluang 96% lebih unggul dari A"), dapat dievaluasi secara kontinu tanpa penalti *peeking problem* (seperti pada p-value stopping rules Frequentist), dan mempercepat pengambilan keputusan bisnis saat volume sampel belum masif.
4. **Analisis Jawaban**: (1) *Time-to-first-interaction*, (2) *Dead click / Rage click frequency*, (3) *Misclick rate* (interaksi di luar target hit box), dan (4) *Dwell time* pra-aksi.
5. **Analisis Jawaban**: Harness parser menangkap exception parsing via Zod error boundary, secara instan men-discard tree eksperimen yang korup, dan me-render default hardcoded fallback layout (Control UI) secara deterministik sembari memancarkan log kegagalan telemetri tingkat tinggi (*Error Event*).

#### Bagian C
1. **Panduan Evaluasi**: Pengguna menyelesaikan task filter lebih cepat bukan karena mereka menemukan barang yang tepat, melainkan karena *Affordance* filter Low-Fi yang keliru mengarahkan mereka pada hasil pencarian kosong (*Zero-results page*), sehingga mereka menyerah lebih awal (meninggalkan flow). Metrik mikro yang harus dicek: *Result set cardinality*, *Zero-result frequency*, *Search-to-cart conversion*, dan *Filter-reset action rate*.
2. **Panduan Evaluasi**: Putuskan kopling antara client tracking endpoint dan transactional DB. Rancang: (1) Client batching (buffer 5-10 event), (2) Edge API proxy ingest langsung ke message broker terdistribusi (Apache Kafka / AWS Kinesis), (3) Stream processor (Flink / Vector) mengonsumsi topic dan melakukan micro-batching insertion ke Columnar OLAP Database (ClickHouse / Snowflake) untuk reporting.
3. **Panduan Evaluasi**: Bottleneck kemungkinan terjadi akibat: (1) Dynamic SDUI parser menghasilkan unmemoized complex JSON trees yang memicu infinite re-render, (2) Penggunaan anonymous functions/objects di dalam loop mapping komponen wireframe, (3) Deep component nesting yang memicu layout recalculation berulang. Remediasi: Profiling via React DevTools Profiler & Chrome Performance panel, implementasikan memoization (`React.memo`, stable keys), ratakan struktur hirarki pohon komponen (flatten DOM), dan virtualisasi list yang panjang.

---

## 16. Summary

- **Validasi Desain Berbasis Rekayasa**: Wireframing dan Low-Fi testing skala produksi adalah metodologi ilmiah untuk mengeliminasi bias estetika visual dan memverifikasi arsitektur informasi secara objektif sebelum komitmen resource engineering Hi-Fi dilakukan.
- **Contract-Driven UI**: Penggunaan representasi layout berbasis JSON Schema yang terlepas dari implementasi visual micro-styling memungkinkan eksekusi eksperimen yang fleksibel, terukur, dan aman.
- **Arsitektur Tanpa Latensi**: Mengintegrasikan segmentasi pengguna di Edge Workers dan parsing skema secara server-driven menjamin validasi antarmuka eksperimental tidak merusak Core Web Vitals (khususnya CLS dan FCP).
- **Integritas Telemetri**: Instrumentasi unmoderated testing membutuhkan pipeline data presisi tinggi yang memanfaatkan mekanisme non-blocking seperti `navigator.sendBeacon`, buffer batching, dan pemodelan statistik Bayesian guna mengonfirmasi signifikansi hasil eksperimen sebelum deployment skala penuh.