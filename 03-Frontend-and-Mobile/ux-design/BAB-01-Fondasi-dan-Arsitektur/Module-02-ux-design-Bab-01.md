# BAB 01: FONDASI DAN ARSITEKTUR
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi (UX Design Engineering)

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Merancang dan mengimplementasikan **Multi-Tier Design Token Architecture** (W3C DTCG Format) yang terintegrasi secara otomatis dari Figma ke multi-platform target (*Web, iOS, Android*) melalui CI/CD pipeline.
- Mengonstruksi interaksi UX yang deterministik menggunakan **Finite State Machines (FSM)** untuk mengeliminasi *illegal states* pada alur kerja pengguna yang kompleks.
- Menganalisis dan merekayasa struktur antarmuka untuk kompatibilitas penuh dengan **Accessibility Object Model (AOM)** dan standar WCAG 2.2 Level AA/AAA.
- Mengintegrasikan metrik **Core Web Vitals** (khususnya *Interaction to Next Paint* [INP] dan *Cumulative Layout Shift* [CLS]) ke dalam *UX Performance Budget* berbasis telemetri *Real User Monitoring* (RUM).
- Mengorkestrasi sistem arsitektur UX multi-tenant dan multi-brand tanpa menimbulkan regresi visual maupun redundansi basis kode.

---

### 2. Prerequisite
Untuk memahami materi modul ini secara optimal, peserta wajib menguasai:
- Pemahaman mendalam tentang siklus hidup DOM (*Document Object Model*), *Rendering Pipeline* (Recalculate Style, Layout, Paint, Composite), dan *Event Loop* browser.
- Kemahiran tingkat lanjut dalam **TypeScript** (generics, template literal types, AST manipulation dasar).
- Pengalaman praktis dengan *CSS Architecture* modern (*CSS Custom Properties*, CSS Houdini, PostCSS, subgrid, container queries).
- Konsep dasar teori *State Machine* (State, Transition, Event, Guard, Action).
- Pemahaman dasar arsitektur Git dan GitHub Actions / GitLab CI.

---

### 3. Concept & Internal Architecture (Mendalam)

Arsitektur UX modern pada skala *enterprise* memisahkan antara **Abstraksi Niat Desain (*Design Intent*)**, **Representasi Status (*State Representation*)**, dan **Proyeksi Render (*Render Projection*)**.

```
+---------------------------------------------------------------------------------------+
|                               DESIGN INTENT LAYER                                    |
|  +---------------------------------------------------------------------------------+  |
|  | Figma Token Studio / DTCG JSON Spec (W3C Standard)                              |  |
|  | Multi-Tier Architecture: Global (Primitive) -> Semantic (Alias) -> Component   |  |
|  +---------------------------------------------------------------------------------+  |
+------------------------------------------+--------------------------------------------+
                                           | Transform Engine (Style Dictionary Engine)
                                           v
+---------------------------------------------------------------------------------------+
|                                STATE & CONTRACT LAYER                                |
|  +----------------------------------+    +-----------------------------------------+  |
|  | Deterministic FSM Engine (XState)|    | Accessibility Object Model (AOM)        |  |
|  | Guards, Actions, Context, Actors |    | Semantic Role Matrix & ARIA Live Bus    |  |
|  +----------------------------------+    +-----------------------------------------+  |
+------------------------------------------+--------------------------------------------+
                                           | Continuous Binding
                                           v
+---------------------------------------------------------------------------------------+
|                               RUNTIME RENDERING LAYER                                 |
|  +----------------------------------+    +-----------------------------------------+  |
|  | CSS Custom Properties Engine     |    | UX Telemetry & Web Vitals Guard         |  |
|  | Dynamic Theming & Shadow DOM Scp |    | INP/CLS Real-User Monitoring Observer   |  |
|  +----------------------------------+    +-----------------------------------------+  |
+---------------------------------------------------------------------------------------+
```

#### 3.1 Multi-Tier Design Token Pipeline
Token bukan sekadar variabel CSS; token adalah kontrak data atomik. Desain sistem enterprise mengadopsi struktur 3-tier:
1. **Global/Primitive Tokens**: Nilai mentah tanpa konteks semantik (contoh: `blue.500: "#1E40AF"`). Tidak boleh dikonsumsi langsung oleh komponen antarmuka.
2. **Semantic/System Tokens**: Token berbasis peran yang memetakan primitive token ke dalam konteks fungsional (contoh: `color.background.interactive.hover: "{blue.500}"`).
3. **Component Tokens**: Lingkup privat sebuah komponen yang mengekspos API styling terbatas (contoh: `button.primary.hover.background: "{color.background.interactive.hover}"`).

#### 3.2 Deterministic UX via Finite State Machines (FSM)
Masalah terbesar dalam UX tingkat lanjut adalah **state bloat** dan **race conditions** (misalnya: tombol disabled tetapi tetap merespons event `onClick`, atau layout menampilkan loader dan error message secara bersamaan). Dengan memodelkan UX sebagai State Chart:
$$\text{State Chart} = (S, S_0, \Sigma, \delta, H)$$
di mana:
- $S$ adalah himpunan finite state.
- $S_0$ adalah initial state.
- $\Sigma$ adalah himpunan input event.
- $\delta: S \times \Sigma \rightarrow S$ adalah fungsi transisi.
- $H$ adalah hierarki context/extended state.

Sistem menjamin hanya ada tepat satu state aktif primer pada satu waktu, mengeliminasi variasi state liar yang tidak terprediksi oleh UX Researcher dan Designer.

#### 3.3 The Accessibility Object Model (AOM) & Interaction Pipeline
AOM menjembatani DOM grafis dengan *assistive technology* (screen reader, braille display). Di balik layar:
1. Peramban membangun Render Tree dan secara paralel mengompilasi **Accessibility Tree**.
2. Setiap kali mutasi UI terjadi, browser memicu event komputasi aksesibilitas.
3. Arsitektur UX yang baik mendesain transisi visual berjalan paralel dengan notifikasi ARIA live region tanpa memicu *layout thrashing* atau penundaan *main thread* yang mendegradasi skor INP.

---

### 4. Why & What

| Dimensi | Pendekatan Ad-Hoc / Legacy UX | Enterprise UX Engineering Architecture |
| :--- | :--- | :--- |
| **Token Distribution** | *Copy-paste* manual nilai HEX/Px dari Figma ke CSS/SCSS. | *Single-source-of-truth* JSON via W3C DTCG spec diekspor via GitHub Actions ke NPM registry. |
| **State Handling** | Boolean flags bertumpuk (`isLoading`, `isError`, `isSuccess`, `isDirty`). Sering terjadi benturan status. | Formal Finite State Machine/Statecharts; *impossible states* mustahil terjadi secara matematis. |
| **Aksesibilitas (a11y)** | Audit retrospektif pasca rilis; *patching* manual dengan menambahkan atribut `aria-*` seadanya. | *Accessibility-by-contract*; state UI otomatis mengekspos status ARIA yang sinkron dengan *state machine*. |
| **Performansi UX** | Fokus pasif pada ukuran bundel JS (`bundle size`). | Fokus aktif pada *User-Centric Performance Metrics*: INP $< 200\text{ms}$, CLS $< 0.1$, LCP $< 2.5\text{s}$. |
| **Multi-Brand Scale** | Membuat duplikat repositori/komponen untuk tiap brand anak perusahaan. | *Token aliasing & dynamic stylesheet switching* pada runtime tanpa duplikasi logika komponen. |

---

### 5. How (Workflow Detail)

Alur kerja arsitektural untuk mendistribusikan dan mengeksekusi sistem UX enterprise:

```
[Designer] Updates Semantic Tokens in Figma
   │
   ▼
[Webhook Trigger] Figma REST API / Tokens Studio syncs to Git Repo
   │
   ▼
[CI/CD Pipeline] Runs Build Transformer (Style Dictionary)
   │─── Validate JSON against JSON Schema (DTCG format)
   │─── Transform: Casing, Math ops, Color Space Conversion (OKLCH)
   │─── Format Output: CSS Custom Properties, TS Typings, Android XML, iOS Swift
   ▼
[Artifact Delivery] Published to Internal NPM Registry (@enterprise/design-tokens)
   │
   ▼
[Frontend Component Architecture]
   │─── Consume CSS variables for dynamic rendering
   │─── Feed State Machine with Token Transitions
   │─── Run Layout Mutation Observer for UX Telemetry (CLS/INP guards)
```

1. **Token Ingestion**: File konfigurasi token berbasis JSON divalidasi menggunakan skema validasi ketat (*JSON Schema*). Token tidak valid (misal: rasio kontras warna teks dan latar belakang kurang dari 4.5:1 untuk WCAG AA) akan menggagalkan pipeline CI.
2. **Compilation**: Style Dictionary membaca tokens, mengompilasi alias menjadi referensi absolut, melakukan konversi ruang warna ke `oklch()` untuk representasi warna yang konsisten di berbagai panel display, dan mengekspor output platform-specific.
3. **Runtime Execution**: Aplikasi web memuat CSS variables secara dinamis pada root element (`:root[data-theme="brand-a"]`), mengisolasi re-rendering hanya pada node yang terpengaruh tanpa me-reload DOM tree.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Pengatur Lalu Lintas Rel Kereta Api Modern
Bayangkan sistem UX ad-hoc seperti persimpangan jalan tanpa lampu lalu lintas di mana pengemudi (event klik, data response, animasi) hanya mengandalkan klakson (banyak flag boolean: `isCarComing`, `isBusCrossing`). Tabrakan data (*race condition*) pasti terjadi.

Arsitektur UX Engineering berbasis FSM dan Design Tokens berfungsi seperti sistem persinyalan interlocking rel kereta api:
- **Design Tokens** adalah *standar ukuran rel dan voltase daya*: Semua lokomotif dan gerbong (komponen UI) di seluruh negara bagian (platform Web/Mobile) dipaksa menggunakan spesifikasi ukuran yang seragam secara absolut.
- **Finite State Machine** adalah *sistem sinyal interlocking*: Jalur tidak akan pernah bisa dibuka untuk kereta lain sebelum blok rel benar-benar kosong. Tidak ada kondisi di mana pintu palang terbuka setengah, bel berbunyi, dan lampu mati bersamaan.

#### Diagram Arsitektur State & Token Rendering
```
+---------------------------------------------------------------------------+
|                          BROWSER MAIN THREAD                              |
|                                                                           |
|  +------------------------+      Dispatch(EVENT)    +------------------+  |
|  | UI Component Template  | ----------------------> | State Machine    |  |
|  | (React / WebComponent) |                         | (XState Service) |  |
|  +------------------------+                         +------------------+  |
|              ^                                                |           |
|              | Reflects New Snapshot                         | State     |
|              | (ARIA + Classes)                              | Transition|
|              +------------------------------------------------+           |
|                                                                           |
|  +---------------------------------------------------------------------+  |
|  | CSS Engine (Cascading & Custom Properties)                          |  |
|  |  :root {                                                            |  |
|  |    --btn-bg: var(--color-interactive-primary);                      |  |
|  |    --btn-pad: var(--spacing-md);                                    |  |
|  |  }                                                                  |  |
|  +---------------------------------------------------------------------+  |
|                                  |                                        |
|                                  v                                        |
|  +---------------------------------------------------------------------+  |
|  | Layout & Paint Stage (Target: Frame budget < 16.6ms | INP < 200ms)  |  |
|  +---------------------------------------------------------------------+  |
+---------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example (Kode Standar Industri)

#### 7.1 Simple Example: W3C DTCG Token Definition & Basic Translation
Contoh file token standar W3C DTCG (`tokens/globals.json`):

```json
{
  "color": {
    "brand": {
      "primary": {
        "$value": "#0052cc",
        "$type": "color",
        "$description": "Primary brand identity color"
      }
    }
  },
  "spacing": {
    "base": {
      "$value": "4px",
      "$type": "dimension"
    },
    "md": {
      "$value": "{spacing.base} * 4",
      "$type": "dimension"
    }
  }
}
```

#### 7.2 Practical Example: Enterprise Multi-Tier Token Build Engine & FSM Form Component

##### A. Build Pipeline Script (`build-tokens.ts`)
Menggunakan Style Dictionary v4 dengan transformer khusus untuk validasi kontras warna WCAG runtime.

```typescript
import StyleDictionary from 'style-dictionary';
import { formatHelpers } from 'style-dictionary/utils';
import type { Config, TransformedToken } from 'style-dictionary/types';

// Helper: Hitung relative luminance untuk validasi WCAG
function getLuminance(r: number, g: number, b: number): number {
  const [rs, gs, bs] = [r, g, b].map((c) => {
    c = c / 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
}

// Custom transformer untuk mengubah token HEX ke modern OKLCH
StyleDictionary.registerTransform({
  name: 'color/oklch-transform',
  type: 'value',
  transitive: true,
  matcher: (token: TransformedToken) => token.$type === 'color',
  transform: (token: TransformedToken) => {
    // Simulasi parsing hex ke format representasi aman (contoh implementatif)
    return `oklch(from ${token.$value} l c h)`;
  }
});

const config: Config = {
  source: ['tokens/**/*.json'],
  platforms: {
    css: {
      transformGroup: 'css',
      transforms: ['color/oklch-transform'],
      buildPath: 'dist/css/',
      files: [
        {
          destination: 'tokens.css',
          format: 'css/variables',
          options: {
            outputReferences: true,
            selector: ':root'
          }
        }
      ]
    },
    typescript: {
      transformGroup: 'js',
      buildPath: 'dist/ts/',
      files: [
        {
          destination: 'tokens.ts',
          format: 'javascript/es6'
        }
      ]
    }
  }
};

const sd = new StyleDictionary(config);
await sd.buildAllPlatforms();
console.log('✅ Enterprise Token Pipeline Successfully Compiled.');
```

##### B. Deterministic UX State Machine (`checkoutMachine.ts`)
Implementasi state machine form transaksi checkout menggunakan `xstate` (v5) untuk menjamin user experience bebas dari status ganda (*conflicting feedback*).

```typescript
import { createMachine, assign } from 'xstate';

export interface CheckoutContext {
  userId: string | null;
  paymentMethod: string | null;
  errorMessage: string | null;
  retryCount: number;
}

export type CheckoutEvent =
  | { type: 'SUBMIT_PAYMENT'; method: string }
  | { type: 'PAYMENT_RESOLVED' }
  | { type: 'PAYMENT_REJECTED'; error: string }
  | { type: 'RETRY' }
  | { type: 'RESET' };

export const checkoutUXMachine = createMachine({
  id: 'checkoutUX',
  types: {} as {
    context: CheckoutContext;
    events: CheckoutEvent;
  },
  initial: 'idle',
  context: {
    userId: 'USR-8821',
    paymentMethod: null,
    errorMessage: null,
    retryCount: 0
  },
  states: {
    idle: {
      on: {
        SUBMIT_PAYMENT: {
          target: 'validatingClient',
          actions: assign({
            paymentMethod: ({ event }) => event.method,
            errorMessage: () => null
          })
        }
      }
    },
    validatingClient: {
      entry: 'announceAccessibilityValidation',
      after: {
        150: [
          {
            guard: ({ context }) => !!context.paymentMethod,
            target: 'processingPayment'
          },
          {
            target: 'error',
            actions: assign({
              errorMessage: () => 'Metode pembayaran tidak valid.'
            })
          }
        ]
      }
    },
    processingPayment: {
      // Menjamin tombol UI terkunci dan loader aria-busy aktif
      tags: ['locked', 'showLoader'],
      on: {
        PAYMENT_RESOLVED: {
          target: 'success'
        },
        PAYMENT_REJECTED: {
          target: 'error',
          actions: assign({
            errorMessage: ({ event }) => event.error,
            retryCount: ({ context }) => context.retryCount + 1
          })
        }
      }
    },
    error: {
      entry: 'announceAccessibilityError',
      on: {
        RETRY: [
          {
            guard: ({ context }) => context.retryCount < 3,
            target: 'processingPayment'
          },
          {
            target: 'terminalFailure'
          }
        ],
        RESET: {
          target: 'idle',
          actions: assign({
            paymentMethod: () => null,
            errorMessage: () => null,
            retryCount: () => 0
          })
        }
      }
    },
    terminalFailure: {
      entry: 'escalateToCustomerSupportUX',
      tags: ['locked']
    },
    success: {
      entry: 'announceAccessibilitySuccess',
      type: 'final'
    }
  }
});
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Arsitektur Multi-Brand Perbankan Global ("FinCorp International")
* **Konteks**: FinCorp mengelola 4 brand perbankan retail di 12 negara dengan satu codebase frontend tunggal berbasis Micro-frontend.
* **Tantangan Utama**:
  1. *Visual Inconsistency & Regresi*: Pengembang di brand A tidak sengaja memodifikasi styling tombol yang merusak tata letak visual brand B.
  2. *UX Performance Degradation*: Bundle style membengkak hingga $4.2\text{ MB}$ karena memuat framework CSS masing-masing brand secara paralel.
  3. *Aksesibilitas Gagal*: Perubahan kontras dinamis antar tema membuat skor WCAG anjlok di bawah batas audit kepatuhan regulasi finansial (EAA & ADA).
* **Solusi Arsitektural yang Diterapkan**:
  1. **Strict Token Domain Scoping**:
     Menggunakan 3-Tier token architecture di mana variabel CSS di-namespace per brand:
     ```css
     [data-brand="aurora"] {
       --sys-color-surface: var(--aurora-blue-50);
       --sys-color-primary: var(--aurora-blue-600);
     }
     [data-brand="solis"] {
       --sys-color-surface: var(--solis-amber-50);
       --sys-color-primary: var(--solis-amber-700);
     }
     ```
  2. **Zero-Runtime CSS Extraction**:
     Style Dictionary mengompilasi artefak menjadi file *CSS Module* statis yang diinjeksi via layer konfigurasi micro-frontend.
  3. **Automated WCAG CI Check**:
     Setiap commit token dievaluasi secara otomatis oleh script kalkulator rasio kontras APCA (*Advanced Perceptual Contrast Algorithm*). Jika rasio latar belakang dan teks $< 60$ Lc, build digagalkan secara otomatis di GitHub Actions.
* **Hasil Pengukuran Terverifikasi**:
  - Ukuran bundel CSS global terpangkas dari **$4.2\text{ MB}$** menjadi **$64\text{ KB}$** per tenant.
  - Skor *Cumulative Layout Shift* (CLS) membaik dari **0.24** menjadi **0.002** (zero perceptible shift).
  - Laporan temuan audit aksesibilitas legal berkurang **100%** untuk elemen dasar sistem desain.

---

### 9. Trade-offs

Setiap keputusan arsitektur sistem UX membawa konsekuensi teknis yang harus diseimbangkan:

| Opsi Desain | Keuntungan | Biaya / Trade-off | Mitigasi Arsitektur |
| :--- | :--- | :--- | :--- |
| **Pure CSS Variables Runtime Engine** | Perubahan tema (*theming*) instan tanpa render ulang komponen; integrasi DOM langsung. | *Cascading overhead* dapat meningkat jika terdapat puluhan ribu token yang dideklarasikan pada selector dalam. | Terapkan token hanya pada level root `:root` atau root micro-frontend, bukan di sub-tree scoped selector yang dalam. |
| **Finite State Machine UX (XState)** | Menjamin zero-illegal states, memudahkan visualisasi flow, trace status deterministik. | Menambah ukuran *runtime library* (~15-30KB gzipped) dan kurva belajar (*steep learning curve*) tim. | Gunakan state machine ringan buatan sendiri (*lightweight reducer FSM*) untuk komponen atomik, simpan XState untuk modul *flow-critical*. |
| **Strict Token Restrictions (Design Linter)** | Mencegah deviasi desain (misal desainer/engineer memakai padding acak seperti `13px`). | Menurunkan kecepatan fleksibilitas prototipe cepat (*rapid prototyping*) pada tahap eksplorasi awal produk. | Buat sandbox mode / *escape hatches* berbatas waktu dengan peringatan audit otomatis di build log. |
| **Dynamic Accessibility Trees via ARIA Live** | Notifikasi instan bagi pengguna disabilitas visual pada setiap transisi asynchronous. | Bila terlalu sering digunakan (*spamming*), pembaca layar (*screen reader*) menjadi tidak dapat dipahami (*cognitive overload*). | Implementasikan *Debounced ARIA Live Announcer Bus* terpusat yang memprioritaskan antrean pesan secara bergantian. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan Fatal: Mengabaikan Layout Shift pada Font & Icon Loading
* **Gejala**: Skor CLS melonjak tajam saat halaman selesai diunduh; teks meloncat dan tombol bergerak sebelum pengguna sempat menekan.
* **Penyebab**: Web font kustom menggantikan font sistem tanpa konfigurasi metrik perataan teks (*fallback size-adjust*).
* **Solusi Perbaikan (CSS)**:
```css
@font-face {
  font-family: 'EnterpriseSans-Fallback';
  src: local('Arial');
  ascent-override: 95%;
  descent-override: 25%;
  line-gap-override: 0%;
  size-adjust: 102%;
}

:root {
  font-family: 'EnterpriseSans', 'EnterpriseSans-Fallback', sans-serif;
}
```

#### 2. Anti-pattern: Sinkronisasi Ganda State Machine dan Local UI State
* **Gejala**: Tampilan visual menampilkan status berhasil, namun tombol checkout tetap berputar (*infinite spinner*).
* **Penyebab**: Terjadi desinkronisasi antara status boolean lokal (`useState(true)`) dan state machine aktor parent.
* **Solusi**: Jangan pernah menduplikasi status FSM ke dalam local state framework. Jadikan *State Machine Snapshot* sebagai **Single Source of Truth** absolut.

```typescript
// ❌ ANTI-PATTERN: State terduplikasi
const [loading, setLoading] = useState(false);
const [state, send] = useMachine(checkoutMachine);
// 'loading' dan 'state.matches("processingPayment")' bisa bertentangan!

// ✅ BENAR: Mengandalkan status komputasi state machine secara murni
const [state, send] = useMachine(checkoutMachine);
const isLoading = state.hasTag('showLoader');
const isLocked = state.hasTag('locked');
```

#### 3. Bug: Screen Reader Mengabaikan Modal Dinamis
* **Gejala**: Screen reader tetap membaca konten di belakang modal dialog yang terbuka (*focus trapping failure*).
* **Penyebab**: Atribut `aria-modal="true"` tidak disertai dengan pemindahan fokus eksplisit atau tidak adanya manipulasi properti `inert` pada kontainer root aplikasi.
* **Solusi**: Pasang atribut `inert` pada node sibling saat modal dibuka:
```typescript
function toggleModalAccessibility(isOpen: boolean, modalElement: HTMLElement, mainAppRoot: HTMLElement) {
  if (isOpen) {
    mainAppRoot.setAttribute('inert', '');
    modalElement.removeAttribute('inert');
    modalElement.focus();
  } else {
    mainAppRoot.removeAttribute('inert');
    // Kembalikan fokus ke trigger element
  }
}
```

---

### 11. Best Practices (Production Checklist)

#### Design Tokens & Theming
- [ ] Semua token warna wajib lulus uji rasio kontras WCAG 2.2: minimal **4.5:1** untuk teks reguler, dan **3:1** untuk elemen grafis interaktif.
- [ ] Tidak ada referensi hardcoded nilai (*HEX, RGB, static px*) di dalam basis kode komponen UI.
- [ ] Seluruh token komputasi dipetakan menggunakan *CSS Custom Properties* dengan fallback value.

#### UX Determinism & State Machine
- [ ] Tombol aksi interaktif wajib dinonaktifkan secara komputasi (*pointer-events: none* dan *aria-disabled="true"*) saat transisi asinkron sedang berlangsung.
- [ ] Transisi status kritis (Pending, Resolved, Rejected) memiliki pemetaan visual yang terpisah dan terverifikasi secara isolatif.
- [ ] Setiap skenario kegagalan jaringan atau timeout memiliki status pemulihan (*recovery transition*) yang jelas bagi pengguna.

#### User-Centric Performance Budgets
- [ ] **Interaction to Next Paint (INP)** di bawah **$200\text{ms}$** diuji pada perangkat mobile low-tier (CPU throttling 4x).
- [ ] **Cumulative Layout Shift (CLS)** di bawah **0.05** pada seluruh alur pengguna utama.
- [ ] Skeleton loading states memiliki dimensi identik dengan payload visual akhir untuk mencegah lonjakan layout.

---

### 12. Hands-on Practice

Buat dan simpan file praktikum berikut di direktori: `hands-on/m02/`

#### Langkah 1: Setup Struktur Proyek
Jalankan perintah berikut di terminal:
```bash
mkdir -p hands-on/m02/src
cd hands-on/m02
npm init -y
npm install xstate style-dictionary typescript @types/node
npx tsc --init
```

#### Langkah 2: Buat File Token W3C Format
Simpan file berikut di `hands-on/m02/tokens.json`:
```json
{
  "semantic": {
    "action": {
      "primary": {
        "bg": {
          "$value": "#0284c7",
          "$type": "color"
        },
        "text": {
          "$value": "#ffffff",
          "$type": "color"
        }
      }
    },
    "feedback": {
      "error": {
        "$value": "#dc2626",
        "$type": "color"
      }
    }
  }
}
```

#### Langkah 3: Buat Token Builder Engine
Simpan file berikut di `hands-on/m02/build.js`:
```javascript
const StyleDictionary = require('style-dictionary');

const sd = new StyleDictionary({
  source: ['tokens.json'],
  platforms: {
    css: {
      transformGroup: 'css',
      buildPath: 'dist/',
      files: [{
        destination: 'variables.css',
        format: 'css/variables'
      }]
    }
  }
});

sd.buildAllPlatforms();
console.log('Build complete. Periksa dist/variables.css');
```

#### Langkah 4: Buat Runtime UI Controller Interaktif
Simpan file berikut di `hands-on/m02/src/runtime.ts`:
```typescript
import { createMachine, createActor } from 'xstate';

const toggleMachine = createMachine({
  id: 'interactiveButton',
  initial: 'idle',
  states: {
    idle: {
      on: { CLICK: 'processing' }
    },
    processing: {
      after: {
        1000: 'completed'
      }
    },
    completed: {
      on: { CLICK: 'idle' }
    }
  }
});

const actor = createActor(toggleMachine);
actor.subscribe((snapshot) => {
  console.log(`[UX State Monitor]: Status Saat Ini = ${snapshot.value}`);
});

actor.start();
console.log('--- Trigger Event CLICK ---');
actor.send({ type: 'CLICK' });

setTimeout(() => {
  console.log('--- Trigger Event CLICK Setelah Complete ---');
  actor.send({ type: 'CLICK' });
}, 1500);
```

#### Langkah 5: Eksekusi dan Verifikasi
Jalankan di terminal:
```bash
node build.js
npx ts-node src/runtime.ts
```

Verifikasi bahwa file `dist/variables.css` berhasil dibuat dan transisi state machine tercetak secara konsisten di console output.

---

### 13. Exercise

#### Level: Easy
Ubah file `tokens.json` di latihan hands-on di atas untuk menambahkan token semantic baru: `semantic.action.secondary.bg` dengan nilai `#e2e8f0` dan tipe `color`. Jalankan kembali build engine dan verifikasi apakah CSS variable `--semantic-action-secondary-bg` terbentuk di `dist/variables.css`.

#### Level: Medium
Buat sebuah fungsi utilitas validasi aksesibilitas runtime sederhana dalam TypeScript (`validateContrast(hexForeground: string, hexBackground: string): boolean`) yang menghitung nilai luminance kontras warna berdasarkan standar WCAG 2.1 Level AA (minimal 4.5:1). Kembalikan nilai `false` dan cetak pesan error peringatan jika warna tidak memenuhi standar.

#### Level: Hard
Kembangkan state machine `checkoutUXMachine` dari subbab 7.2 untuk menangani status **`networkOffline`**. 
- Ketika peramban kehilangan koneksi internet (`OFFLINE_EVENT`), mesin harus beralih ke state `offlineSuspended` tanpa membatalkan konteks transaksi yang sudah diisi pengguna.
- Ketika koneksi pulih (`ONLINE_EVENT`), mesin harus memicu validasi ulang background otomatis dan melanjutkan status ke state sebelumnya secara transparan (*optimistic UX pattern*).

---

### 14. Challenge

**Skenario Sistem Enterprise**:
Sebuah platform streaming video global memiliki masalah kritis: Pada saat pergantian orientasi layar (Portrait ke Landscape) di perangkat mobile lipat (*foldable devices*), terjadi lonjakan metrik performa UX:
- **CLS melonjak ke angka 0.65** karena komponen kontrol pemutar video, teks sinopsis, dan komentar dirender ulang secara serampangan.
- **INP memburuk hingga 650ms** akibat perhitungan posisi dinamis *floating video control* yang memicu *synchronous forced layout reflow* berulang-ulang pada *Main Thread*.

**Tugas Arsitektur**:
Rancang arsitektur komponen UX berbasis **CSS Container Queries + Web Performance Observer** yang memenuhi kriteria ketat berikut:
1. Tidak ada dependensi JavaScript berbasis event listener `window.onresize` untuk mengubah styling kontrol video (ganti seluruh logika tata letak ke *Pure Declarative CSS modern*).
2. Tuliskan implementasi skrip **Real-Time Performance Guard** menggunakan peramban `PerformanceObserver` API untuk memantau metrik INP dan CLS saat perubahan dimensi antarmuka berlangsung. Jika CLS $> 0.05$ atau INP $> 150\text{ms}$, kirim data telemetri analitik terstruktur ke mock endpoint analitik tanpa memblokir thread rendering visual.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic (5 Soal)
1. Apa perbedaan arsitektural utama antara *Global/Primitive Tokens* dan *Semantic Tokens*?
2. Mengapa penggunaan banyak status boolean (`isLoading`, `isError`, dll.) dianggap berbahaya pada perancangan antarmuka berskala besar?
3. Apa kepanjangan dari metrik INP pada Core Web Vitals, dan berapa batas ambang batas (*threshold*) maksimal untuk pengalaman pengguna yang dikategorikan "Baik"?
4. Di layer mana konversi token menjadi *CSS Custom Properties* sebaiknya dilakukan dalam pipeline desain sistem modern?
5. Apa peran atribut `inert` pada node DOM HTML5 dalam konteks aksesibilitas antarmuka (*accessibility tree*)?

#### B. Pertanyaan Intermediate (5 Soal)
6. Bagaimana keterkaitan matematis antara pemisahan State dan Event dalam Finite State Machine (FSM) dengan pencegahan kondisi balapan (*race condition*) pada UI?
7. Mengapa penggunaan properti layout CSS seperti `width`, `height`, `top`, dan `left` saat animasi transisi UX sangat dihindari untuk menjaga stabilitas skor CLS?
8. Bagaimana format standar W3C Design Token Community Group (DTCG) mengatasi kebutuhan pewarisan (*aliasing*) antar token?
9. Jelaskan mekanisme browser saat memperbarui *Accessibility Object Model* (AOM) ketika sebuah elemen dimutasi oleh framework JavaScript reaktif!
10. Bagaimana pemanfaatan ruang warna `oklch()` memberikan keuntungan teknis dalam arsitektur sistem token dinamis dibandingkan ruang warna konvensional `sRGB` atau `HEX`?

#### C. Skenario Kasus Produksi (3 Soal)
11. **Skenario 1**: Tim Quality Assurance menemukan bahwa pembaca layar (screen reader) terus membacakan pembaruan angka counter live chat secara berulang-ulang setiap 500 milidetik, sehingga menenggelamkan navigasi utama aplikasi. Solusi arsitektur ARIA apa yang paling tepat untuk mengatasi masalah degradasi UX ini tanpa menghentikan pembaruan chat visual?
12. **Skenario 2**: Setelah merilis tema baru bernuansa gelap (*Dark Mode*), pengguna melaporkan bahwa interaksi dropdown menu terasa tersendat (*laggy*) pada perangkat smartphone kelas menengah ke bawah, meskipun kode JavaScript logika bisnis tidak diubah. Investigasi menunjukkan lonjakan waktu eksekusi rendering CSS. Analisislah apa penyebab arsitektural yang paling mungkin pada level token/CSS!
13. **Skenario 3**: Sebuah aplikasi perbankan enterprise memerlukan alur otentikasi multi-langkah (*multi-step KYC*). Saat pengguna berada di langkah ke-3 (unggah dokumen identitas) dan koneksi internet mengalami drop sesaat, UI melompat kembali ke langkah ke-1 dan menghapus seluruh formulir input. Bagaimana Anda mendesain ulang arsitektur state management antarmuka ini menggunakan pendekatan FSM dan caching storage yang aman?

---

### Kunci Jawaban & Rubrik Evaluasi Quiz

#### Jawaban Basic
1. *Primitive tokens* menyimpan nilai mentah tanpa makna spesifik (contoh: `#ff0000`), sedangkan *Semantic tokens* memberikan konteks fungsional bagaimana nilai tersebut digunakan dalam aplikasi (contoh: `--color-feedback-danger: var(--red-500)`).
2. Menghasilkan kombinasi status yang tidak valid (*impossible/illegal states*), seperti kondisi di mana aplikasi secara bersamaan berada pada kondisi `isLoading: true` dan `isSuccess: true`.
3. *Interaction to Next Paint*. Ambang batas performa "Baik" adalah $\le 200\text{ milidetik}$.
4. Di layer *Build/Compilation time* via transformer engine (seperti Style Dictionary), mendistribusikan variabel statis siap pakai tanpa membebani runtime komputasi browser.
5. `inert` secara komprehensif memberi tahu browser untuk mengabaikan input pengguna (keyboard, pointer) sekaligus menyembunyikan node dan seluruh anak-anaknya dari Accessibility Tree pembaca layar.

#### Jawaban Intermediate
6. FSM membatasi sistem sehingga hanya satu state primer yang aktif dalam satu waktu. Transisi antar state bersifat deterministik hanya melalui input `event` eksplisit dan evaluasi `guard`, sehingga dua proses asinkron yang tiba bersamaan tidak dapat memicu dua status UI yang bertentangan.
7. Memodifikasi properti dimensi/posisi geometrik memaksa browser memicu fase *Layout/Reflow* dan *Repaint* pada rendering tree, yang secara langsung menggeser elemen di sekitarnya dan meningkatkan metrik CLS. Properti transform (`transform: translate()`) dieksekusi di fase *Composite* pada GPU thread tanpa memicu reflow.
8. Melalui sintaks referensi kurung kurawal, misalnya `"$value": "{color.brand.primary}"`. Build engine mengenali kurung kurawal ini sebagai pointer graph dan mengompilasinya menjadi dependensi cascading yang tepat.
9. Mutasi pada DOM memicu internal engine browser untuk menjadwalkan kalkulasi ulang accessibility node yang relevan. Browser mengevaluasi peran (roles), states, dan atribut ARIA, lalu memancarkan accessibility event ke interface OS Assistive Technology tanpa me-reload seluruh struktur tree secara global.
10. `oklch` didasarkan pada persepsi visual manusia (perceptually uniform). Mengubah lightness atau hue pada satu warna tidak akan merusak persepsi kontras visual relatif terhadap elemen lain, sangat krusial untuk otomasi kalkulasi varian token dark mode secara programatik.

#### Jawaban Skenario Kasus Produksi
11. **Solusi Skenario 1**: Ubah konfigurasi live region pada counter chat. Ganti dari `aria-live="assertive"` ke `aria-live="off"` atau `aria-live="polite"`, dan terapkan debounce. Pisahkan container counter teks visual dari elemen semantic live region yang hanya memancarkan rangkuman pesan berkala jika terdapat interaksi pengguna langsung, bukan pada setiap mutasi tick data streaming.
12. **Solusi Skenario 2**: Masalah terjadi akibat penerapan filter kompleks yang berlebihan (seperti `backdrop-filter: blur()`), penggunaan efek `box-shadow` berlapis yang luas pada selector universal dark mode, atau deklarasi ulang ribuan variabel CSS di level selector anak yang dalam (`* { --token: ... }`) yang memicu *recalculate style thrashing* pada setiap paint. Solusinya: pindahkan semua pendefinisian token tema gelap ke scope `:root[data-theme="dark"]` murni dan manfaatkan akselerasi hardware (`will-change: transform` jika relevan) serta mematikan efek visual berat pada perangkat low-end.
13. **Solusi Skenario 3**: Rekayasa ulang alur menggunakan hierarchical state machine (FSM). Definisikan tiap tahap KYC sebagai child-state dengan persistent *Context Layer*. Setiap transisi state yang berhasil harus melakukan sinkronisasi context ke encrypted session storage. Ketika jaringan drop, tangkap event via mesin dan alihkan ke state `idle.reconnecting` yang mengunci input UI sementara tanpa me-reset context form, sehingga saat jaringan pulih, FSM dapat melanjutkan alur tepat di step ke-3.

---

### 16. Summary

1. **Arsitektur UX Modern adalah Disiplin Rekayasa**: Bukan sekadar visual styling, UX modern di tingkat enterprise bergantung pada kontrak data yang kaku, aliran desain-ke-kode yang terotomatisasi, dan eliminasi cacat interaksi secara matematis.
2. **Design Tokens Sebagai Single Source of Truth**: Memisahkan nilai atomik melalui struktur 3-tier (Global $\rightarrow$ Semantic $\rightarrow$ Component) menjamin fleksibilitas visual multi-brand tanpa merusak basis kode logika aplikasi.
3. **Deterministik Melalui FSM**: Menghilangkan *UI race condition* dan *impossible states* dengan memodelkan interaksi kompleks pengguna sebagai Finite State Machines eksplisit yang terikat langsung dengan status aksesibilitas antarmuka.
4. **Performa UX Berbasis Metrik Objektif**: Integrasi sadar performa (INP, CLS, LCP) dan aksesibilitas (AOM, WCAG 2.2 AA) yang terukur melalui telemetri real-time adalah fondasi utama dalam menciptakan aplikasi enterprise kelas dunia yang inklusif dan responsif.