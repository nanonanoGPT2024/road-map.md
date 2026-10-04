# BAB-08: High-Fidelity Dynamic Prototyping
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Merancang Dynamic State Machine**: Mengabstraksikan interaksi multi-step kompleks dan micro-interaction berbasis *Deterministic Finite State Machines* (FSM) serta *Statecharts* (menggunakan XState) untuk prototipe *code-driven* fidelitas tinggi.
2. **Mengintegrasikan Dynamic Mock Data Pipeline**: Membangun arsitektur *network-less API simulation* menggunakan MSW (Mock Service Worker) untuk menguji edge cases (network latency, idempotency errors, dynamic token hydration) tanpa ketergantungan pada backend aktif.
3. **Mengimplementasikan Physics-Based Gestural Animations**: Mengonstruksi interaksi mikro menggunakan Framer Motion atau gesture responder primitives dengan mempertahankan performa 60-120 FPS tanpa menyebabkan *layout thrashing* atau *main-thread blocking*.
4. **Membangun Headless Prototype Architecture**: Mengawinkan Design Tokens tingkat lanjut (W3C Design Token Community Group standard) dengan React/TypeScript untuk menghasilkan prototipe interaktif yang merefleksikan 1:1 batasan teknis lingkungan produksi.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
* Pemahaman mendalam tentang **BAB-08 Module 01** (Dasar-dasar High-Fidelity & Tooling Prototyping: Figma Variables, Component Variants, Boolean Logic).
* Kemahiran bahasa pemrograman **TypeScript** tingkat lanjut (Generics, Discriminated Unions, Type Narrowing).
* Fondasi arsitektur **React 18+** (Concurrent features, custom hooks, reference-based rendering loops).
* Konsep dasar **Design Systems & Token Pipelines** (Style Dictionary, Token Transforms, CSS Custom Properties).
* Teori automata dasar: Pemahaman tentang *State Machines*, *Transitions*, *Guards*, dan *Context Data*.

---

### 3. Concept & Internal Architecture (Mendalam)

High-Fidelity Dynamic Prototyping tingkat enterprise bukan sekadar menyambungkan *artboard* dengan transisi "Smart Animate". Pada skala sistem perangkat lunak modern, prototipe harus berfungsi sebagai **Spesifikasi Perilaku Formal (Executable Specification)** yang memvalidasi hipotesis UX, kompatibilitas payload data, dan performa interaksi sebelum penulisan kode produksi downstream.

```
+-------------------------------------------------------------------------------+
|                       HIGH-FIDELITY RUNTIME ENGINE                            |
+-------------------------------------------------------------------------------+
|                                                                               |
|   +-------------------+    Event E     +----------------------------------+   |
|   |  User Interaction | -------------> |     XState Finite Statechart     |   |
|   | (Gesture/Input)   |                |  - State: idle | validating      |   |
|   +-------------------+                |  - Guards: canSubmit(ctx)        |   |
|                                        |  - Context: Payload State        |   |
|                                        +----------------------------------+   |
|                                                          |                    |
|                                          Invoke Services | Actions            |
|                                                          v                    |
|   +-------------------+                +----------------------------------+   |
|   | Hardware Thread   | <------------- |     MSW (Service Worker Proxy)   |   |
|   | 60/120 FPS Loop   |  Sync Driver   |  - Simulated Latency (Jitter)    |   |
|   | (Framer/CSS Var)  |                |  - Deterministic Failure Injection|  |
|   +-------------------+                +----------------------------------+   |
|                                                                               |
+-------------------------------------------------------------------------------+
```

#### Arsitektur Inti:
1. **Formal State Machine Layer**:
   Prototipe statis sering kali menyembunyikan "impossible states" (contoh: kondisi di mana tombol berstatus *loading* namun field formulir masih menerima input dan transisi error terjadi bersamaan). Dengan memodelkan antarmuka menggunakan **Statecharts**, status UI diatur secara matematis:
   $$\text{State}_{\text{next}} = f(\text{State}_{\text{current}}, \text{Event}, \text{Context})$$
   Kondisi UI menjadi deterministik, menghilangkan bug status hantu (*race conditions*).

2. **Decoupled Data Hydration (MSW Interceptor)**:
   Dynamic prototyping memerlukan data dinamis tanpa dependensi ke database fisik. Menggunakan Service Worker API, setiap *outgoing request* dari prototipe dibelokkan ke interceptor layer di dalam thread terpisah. Ini memungkinkan evaluasi skenario kritis:
   * Jaringan lambat (3G throttling simulasi).
   * Kesalahan 422 Unprocessable Entity dengan respon JSON terperinci.
   * Paginated dynamic streaming.

3. **Render Lifecycle & Animation Budget**:
   Prototipe high-fidelity yang lambat memvalidasi sinyal UX yang salah (bias frustrasi pengguna terhadap latensi UI padahal aplikasi asli performan). Prototipe harus mempertahankan anggaran frame **16.6ms** (60Hz) atau **8.33ms** (120Hz). Oleh karena itu, runtime animasi dynamic prototyping harus mengeksekusi interpolasi posisi melalui GPU transform (*Hardware Compositing*) via `transform: translate3d()` dan `opacity`, menghindari pembacaan DOM seperti `getBoundingClientRect()` dalam siklus render berulang.

---

### 4. Why & What

| Dimensi | Static/Low-Code Prototype (e.g., Basic Figma) | Code-Driven Enterprise Dynamic Prototype |
| :--- | :--- | :--- |
| **State Handling** | Kombinatorik *Frame Explosion* (Butuh puluhan artboard untuk beberapa variasi toggle). | Algoritmik via Finite State Machine (Satu view mengelola $N$ variasi state secara deterministik). |
| **Data Realism** | Teks *Lorem Ipsum* statis, data duplikat kaku. | Dynamic Mock Injection; mendukung parsing JSON, pencarian instan, validasi regex live. |
| **Logic & Guards** | Terbatas pada navigasi "On Click -> Open Frame". | Kondisional kompleks (misal: "Bisa submit jika saldo > total belanja DAN 2FA aktif"). |
| **Handoff Accuracy** | Spesifikasi visual tinggi, namun logika interaksi ambigu bagi Engineer. | Prototipe adalah implementasi referensi; State Machine & Tokens dapat langsung di-port ke produksi. |

* **What**: Prototipe Dinamis Fidelitas Tinggi (High-Fidelity Dynamic Prototype) adalah representasi interaktif berbasis runtime kode atau computational engine yang mereplikasi fungsionalitas, logika bisnis, micro-interactions, validasi edge-case, dan penanganan data dari sistem produksi secara akurat.
* **Why**: Menghilangkan *misalignment* fatal antara Design System dan Production Implementation. Mencegah rework berbiaya miliaran rupiah pada arsitektur frontend dengan menemukan kegagalan arsitektural antarmuka pada fase validasi konsep.

---

### 5. How (Workflow Detail)

Alur kerja rekayasa prototipe dinamis tingkat enterprise mengikuti siklus 5 tahap:

```
[Phase 1: Contract & Tokens]
       │
       ▼
[Phase 2: FSM Architecture Modeling]
       │
       ▼
[Phase 3: Data Mocking & Interception]
       │
       ▼
[Phase 4: Kinetic & Micro-Interaction Engineering]
       │
       ▼
[Phase 5: Telemetry, Observability & Validation]
```

1. **Phase 1: Contract & Tokens Sync**:
   * Desainer merilis Design Tokens (Colors, Spacing, Typography, Motion Specs) via JSON Token Format.
   * Ekstraksi token ke CSS Custom Properties atau Tailwind Theme Extensions via automated pipeline.
2. **Phase 2: FSM Architecture Modeling**:
   * Memetakan alur interaksi kompleks ke diagram statechart visual.
   * Mendefinisikan *States*, *Context* (extended state), *Events*, dan *Guards* menggunakan TypeScript types.
3. **Phase 3: Data Mocking & Interception**:
   * Menyiapkan handler MSW untuk mensimulasikan REST/GraphQL endpoints.
   * Mengintegrasikan skema validasi dinamis (Zod) untuk memvalidasi input user secara real-time di sisi prototipe.
4. **Phase 4: Kinetic & Micro-Interaction Engineering**:
   * Implementasi interaksi gestural (drag, swipe, pinch) terikat pada spring physics engines (damping, stiffness, mass), bukan kurva bezier statis yang tidak adaptif terhadap kecepatan gesture input.
5. **Phase 5: Telemetry, Observability & Validation**:
   * Menanamkan logging event state machine untuk mengukur *Time to Task Completion* dan *Drop-off Path* saat *User Testing Session*.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Kokpit Simulator Penerbangan Full-Motion
Prototipe statis (Figma murni) seperti mockup kokpit kayu: instrumen digambar dengan spidol, saklar tidak dapat ditekan, dan pemandangan luar diganti manual dengan poster. 
**High-Fidelity Dynamic Prototype** adalah simulator penerbangan profesional: seluruh tombol tersambung ke aktuator hidrolik, layar radar merefleksikan cuaca tiruan yang diprogram secara dinamis, dan sistem memberikan resistensi fisik nyata saat terjadi turbulensi buatan. Jika pilot menekan tombol pendaratan darurat dalam urutan yang salah, sistem merespons persis seperti pesawat aslinya.

#### Diagram Interaksi Runtime
```
+---------------------------------------------------------------------------------------+
| BROWSER RUNTIME                                                                       |
|                                                                                       |
|  +--------------------+                                                               |
|  |     DOM / View     | <-----+                                                       |
|  |   (React Virtual)  |       | (6) Render State & Animate                            |
|  +--------------------+       |                                                       |
|            |                  |                                                       |
|   (1) User | Action           |                                                       |
|            v                  |                                                       |
|  +--------------------+  (3) Evaluate   +--------------------+                        |
|  |   Event Dispatch   | --------------> | State Machine Host |                        |
|  +--------------------+                 |      (XState)      |                        |
|                                         +--------------------+                        |
|                                           |                ^                          |
|                                  (2) Send |                | (5) Resolve Event        |
|                                     Event |                |     (Success/Failure)    |
|                                           v                |                          |
|  +-------------------------------------------------------------+                      |
|  | Network Layer Interceptor (MSW Service Worker)              |                      |
|  |   - Parse Payload                                           |                      |
|  |   - Inject Synthetic Latency (e.g. 800ms)                   |                      |
|  |   - Evaluate Mock Schema Database                           |                      |
|  +-------------------------------------------------------------+                      |
|                                                                                       |
+---------------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Accessible Dynamic Switch with Micro-Physics
Implementasi switch interaktif dengan transisi berbasis Spring Physics dan ARIA bindings yang valid.

```tsx
import React, { useState } from 'react';
import { motion } from 'framer-motion';

interface DynamicSwitchProps {
  initialChecked?: boolean;
  onChange?: (checked: boolean) => void;
  label: string;
}

export const DynamicSwitch: React.FC<DynamicSwitchProps> = ({
  initialChecked = false,
  onChange,
  label,
}) => {
  const [isOn, setIsOn] = useState(initialChecked);

  const toggle = () => {
    const nextState = !isOn;
    setIsOn(nextState);
    onChange?.(nextState);
  };

  return (
    <div className="flex items-center gap-3">
      <span id="switch-label" className="text-sm font-medium text-slate-800">
        {label}
      </span>
      <button
        role="switch"
        aria-checked={isOn}
        aria-labelledby="switch-label"
        onClick={toggle}
        className={`w-14 h-8 flex items-center rounded-full p-1 cursor-pointer transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 ${
          isOn ? 'bg-indigo-600 justify-end' : 'bg-slate-300 justify-start'
        }`}
      >
        <motion.div
          className="w-6 h-6 bg-white rounded-full shadow-md"
          layout
          transition={{
            type: "spring",
            stiffness: 700,
            damping: 30
          }}
        />
      </button>
    </div>
  );
};
```

---

#### B. Practical Example: Enterprise Complex Interaction (Multi-Step Transfer Flow)
Arsitektur state machine lengkap untuk formulir transfer dana dengan validasi dinamis, mutasi mock API, dan proteksi kegagalan transaksi.

```tsx
import React from 'react';
import { createMachine, assign } from 'xstate';
import { useMachine } from '@xstate/react';
import { motion, AnimatePresence } from 'framer-motion';

// --- CONTRACT TYPES ---
interface TransferContext {
  accountBalance: number;
  recipientId: string;
  amount: number;
  errorMessage: string | null;
  transactionRef: string | null;
}

type TransferEvent =
  | { type: 'INPUT_RECIPIENT'; value: string }
  | { type: 'INPUT_AMOUNT'; value: number }
  | { type: 'SUBMIT' }
  | { type: 'RETRY' }
  | { type: 'RESET' };

// --- FINITE STATE MACHINE DEFINITION ---
export const transferMachine = createMachine<TransferContext, TransferEvent>({
  id: 'transferFlow',
  initial: 'idle',
  context: {
    accountBalance: 5000000, // Rp 5.000.000
    recipientId: '',
    amount: 0,
    errorMessage: null,
    transactionRef: null,
  },
  states: {
    idle: {
      on: {
        INPUT_RECIPIENT: {
          actions: assign({ recipientId: (_, event) => event.value }),
        },
        INPUT_AMOUNT: {
          actions: assign({ amount: (_, event) => event.value }),
        },
        SUBMIT: [
          {
            target: 'validating',
            cond: (ctx) => ctx.amount > 0 && ctx.recipientId.length >= 5,
          },
          {
            actions: assign({
              errorMessage: (_) => 'Input tidak valid. Periksa rekening tujuan dan nominal.',
            }),
          },
        ],
      },
    },
    validating: {
      always: [
        {
          target: 'authorizing',
          cond: (ctx) => ctx.amount <= ctx.accountBalance,
        },
        {
          target: 'error',
          actions: assign({
            errorMessage: (_) => 'Saldo rekening tidak mencukupi untuk transaksi ini.',
          }),
        },
      ],
    },
    authorizing: {
      invoke: {
        id: 'executeTransfer',
        src: (ctx) => async () => {
          // Synthetic Network Latency
          await new Promise((resolve) => setTimeout(resolve, 1500));
          // Synthetic Deterministic Edge-Case (Demo Trigger)
          if (ctx.amount === 999999) {
            throw new Error('NETWORK_TIMEOUT: Server perbankan sibuk.');
          }
          return { ref: `TRX-${Date.now()}` };
        },
        onDone: {
          target: 'success',
          actions: assign({
            transactionRef: (_, event) => event.data.ref,
            accountBalance: (ctx) => ctx.accountBalance - ctx.amount,
          }),
        },
        onError: {
          target: 'error',
          actions: assign({
            errorMessage: (_, event) => (event.data as Error).message,
          }),
        },
      },
    },
    success: {
      on: {
        RESET: {
          target: 'idle',
          actions: assign({
            recipientId: (_) => '',
            amount: (_) => 0,
            errorMessage: (_) => null,
            transactionRef: (_) => null,
          }),
        },
      },
    },
    error: {
      on: {
        RETRY: { target: 'idle' },
      },
    },
  },
});

// --- HIGH-FIDELITY REACT VIEW COMPONENT ---
export const TransferFlowComponent: React.FC = () => {
  const [current, send] = useMachine(transferMachine);
  const { accountBalance, recipientId, amount, errorMessage, transactionRef } = current.context;

  return (
    <div className="max-w-md mx-auto p-6 bg-white border border-slate-200 rounded-xl shadow-lg font-sans">
      <div className="flex justify-between items-center mb-6 pb-4 border-b border-slate-100">
        <h2 className="text-lg font-bold text-slate-900">Transfer Dana Instan</h2>
        <div className="text-right">
          <p className="text-xs text-slate-500 uppercase">Saldo Aktif</p>
          <p className="text-sm font-semibold text-emerald-600">
            Rp {accountBalance.toLocaleString('id-ID')}
          </p>
        </div>
      </div>

      <AnimatePresence mode="wait">
        {current.matches('idle') && (
          <motion.div
            key="idle"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="space-y-4"
          >
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                NOMOR REKENING TUJUAN
              </label>
              <input
                type="text"
                value={recipientId}
                onChange={(e) => send({ type: 'INPUT_RECIPIENT', value: e.target.value })}
                placeholder="Contoh: 1234567890"
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:outline-none text-sm"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                NOMINAL (IDR)
              </label>
              <input
                type="number"
                value={amount || ''}
                onChange={(e) => send({ type: 'INPUT_AMOUNT', value: Number(e.target.value) })}
                placeholder="0"
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:outline-none text-sm"
              />
              <p className="text-[10px] text-slate-400 mt-1">
                Gunakan nilai 999999 untuk mensimulasikan kegagalan jaringan.
              </p>
            </div>

            {errorMessage && (
              <div className="p-3 bg-red-50 text-red-700 text-xs rounded-md">
                {errorMessage}
              </div>
            )}

            <button
              onClick={() => send({ type: 'SUBMIT' })}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2.5 rounded-md transition-colors text-sm shadow-sm"
            >
              Lanjutkan Transfer
            </button>
          </motion.div>
        )}

        {current.matches('authorizing') && (
          <motion.div
            key="authorizing"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="py-12 flex flex-col items-center justify-center space-y-4"
          >
            <div className="w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
            <p className="text-sm font-medium text-slate-600">
              Mengamankan Jalur Transaksi...
            </p>
          </motion.div>
        )}

        {current.matches('success') && (
          <motion.div
            key="success"
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ opacity: 0 }}
            className="text-center py-6 space-y-4"
          >
            <div className="w-12 h-12 bg-green-100 text-green-600 rounded-full flex items-center justify-center mx-auto text-xl font-bold">
              ✓
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">Transaksi Berhasil!</h3>
              <p className="text-xs text-slate-500 mt-1">
                Referensi: {transactionRef}
              </p>
            </div>
            <div className="bg-slate-50 p-3 rounded text-left text-xs space-y-1">
              <div className="flex justify-between">
                <span className="text-slate-500">Tujuan:</span>
                <span className="font-semibold text-slate-700">{recipientId}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Nominal:</span>
                <span className="font-semibold text-slate-700">Rp {amount.toLocaleString('id-ID')}</span>
              </div>
            </div>
            <button
              onClick={() => send({ type: 'RESET' })}
              className="w-full bg-slate-800 hover:bg-slate-900 text-white font-medium py-2 rounded-md text-xs transition-colors"
            >
              Kirim Transfer Baru
            </button>
          </motion.div>
        )}

        {current.matches('error') && (
          <motion.div
            key="error"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-center py-6 space-y-4"
          >
            <div className="w-12 h-12 bg-red-100 text-red-600 rounded-full flex items-center justify-center mx-auto text-xl font-bold">
              ✕
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">Transaksi Gagal</h3>
              <p className="text-xs text-red-600 mt-1">{errorMessage}</p>
            </div>
            <button
              onClick={() => send({ type: 'RETRY' })}
              className="w-full bg-slate-200 hover:bg-slate-300 text-slate-800 font-medium py-2 rounded-md text-xs transition-colors"
            >
              Coba Lagi
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: Global FinTech Checkout Redesign
Sebuah platform checkout multinasional dengan volume transaksi >$10B/tahun mengalami tingkat drop-off tinggi (14.2%) pada tahap autentikasi 3D-Secure (3DS) dan validasi mata uang multi-tier.
Tim UX memproduksi prototipe berbasis Figma tradisional, namun saat diuji pada *usability testing*, pengguna menyelesaikan skenario dengan tingkat keberhasilan 98%. Saat diimplementasikan oleh tim engineering ke lingkungan *staging*, tingkat kegagalan transaksi justru melonjak menjadi 18%.

#### Investigasi Masalah:
Prototipe Figma:
1. Tidak memperhitungkan **latency window** antara perbankan penerbit (issuer) dan gateway (2.8 detik - 6.5 detik). Pengguna mengira tombol submit macet dan melakukan double click.
2. Mengabaikan validasi **SCA (Strong Customer Authentication)** bersyarat yang mengharuskan redirect browser vs modal in-context iframe.
3. Selalu menyediakan data nominal mata uang bulat, menutupi kecacatan UX saat nilai desimal hasil konversi mata uang dinamis meluap dari batas visual komponen UI mobile.

#### Solusi Arsitektural:
Tim Product Platform membangun **Code-Driven High-Fidelity Simulator** menggunakan Next.js, XState, dan MSW.
* **XState Machine**: Memodelkan kegagalan timeout issuer, multi-factor polling, dan state race-condition prevention.
* **MSW Configuration Engine**: Memungkinkan tim riset UX mengubah simulasi network profiles (Edge 2G, slow 3G, drop paket 5%) langsung melalui *floating debug drawer* di browser penguji.
* **Dynamic Currency Transformer**: Memasukkan live exchange rates yang memicu dynamic text truncation dan formatting locale otomatis.

#### Hasil Produksi:
* Mengidentifikasi kebutuhan perancangan ulang status "Processing" menjadi multi-stage skeleton notification.
* Mengurangi double-submit error rate sebesar **94%** sebelum baris kode produksi pertama ditulis.
* Menghemat sekitar 3 bulan siklus rekayasa perangkat lunak senilai $420,000 dalam rework struktural.

---

### 9. Trade-offs

| Pendekatan Prototyping | Keuntungan | Kerugian & Konsekuensi Teknis |
| :--- | :--- | :--- |
| **Tool-Based Hifi (e.g., Figma Advanced Variables)** | - Rendah hambatan masuk bagi desainer non-koding.<br>- Iterasi cepat terhadap layout dan visual tokens.<br>- Kolaborasi canvas visual instan. | - Tidak dapat memvalidasi payload data asinkronus nyata.<br>- Logika boolean kaku (sulit memodelkan >10 state paralel).<br>- Tidak mencerminkan performa thread DOM aktual. |
| **Code-Driven Hifi (e.g., React + XState + MSW)** | - Identik 100% dengan kapabilitas platform target.<br>- Menghasilkan FSM logic yang bisa di-copy langsung ke codebase produksi.<br>- Pengujian aksesibilitas keyboard & screen reader secara riil. | - Membutuhkan keahlian software engineering penuh.<br>- Waktu setup awal (*lead time*) lebih lama dibandingkan membuat artboard.<br>- Biaya pemeliharaan dependensi package node. |
| **Hybrid (e.g., Framer / Storybook dynamic components)** | - Bridge seimbang antara desainer visual dan engineer.<br>- Reusable component isolation sandbox. | - Kerap terkunci dalam proprietary runtime framework.<br>- Overhead vendor lock-in dan batasan integrasi backend mocking tingkat lanjut. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Layout Thrashing pada Animasi Dinamis
* **Kesalahan**: Mengubah properti geometris (`top`, `left`, `width`, `height`, `margin`) di dalam perulangan interaksi gestural. Ini memaksa browser mengeksekusi tahapan *Recalculate Style*, *Layout/Reflow*, dan *Paint* pada setiap frame.
* **Gejala**: FPS anjlok dari 60 FPS ke <25 FPS pada perangkat mobile, menyebabkan pergerakan patah-patah (*jank*).
* **Solusi**: Hanya animasikan properti yang ditangani langsung oleh GPU Compositor: `transform` (misal `transform: translate3d(x, y, 0)`) dan `opacity`.

#### 2. False Positive Usability Metrics (The Instant Response Trap)
* **Kesalahan**: Tidak menginjeksikan latensi jaringan pada mock prototype.
* **Gejala**: Pengguna terbiasa dengan transisi sekejap mata (0ms latency), sehingga ketika sistem nyata memiliki latensi 800ms, tim menganggap produk lambat dan merombak backend, padahal masalahnya adalah ketiadaan *optimistic UI* atau transisi skeleton pada desain prototipe.
* **Solusi**: Terapkan *jittered network latency simulation* menggunakan interceptor:
  ```typescript
  // MSW Handler Snippet
  rest.post('/api/checkout', async (req, res, ctx) => {
    return res(
      ctx.delay(Math.floor(Math.random() * (1200 - 400 + 1)) + 400),
      ctx.json({ status: 'SUCCESS' })
    );
  });
  ```

#### 3. State Bloat / Boolean Flag Explosion
* **Kesalahan**: Menggunakan puluhan `useState(false)` untuk mengontrol kondisi UI (`isLoading`, `isError`, `isSuccess`, `isSubmitting`, `isModalOpen`).
* **Gejala**: Kondisi kontradiktif di mana `isLoading === true` dan `isError === true` terjadi secara bersamaan.
* **Solusi**: Gunakan strictly typed Discriminated Unions atau XState FSM. Hindari flags boolean jamak yang independen satu sama lain.

---

### 11. Best Practices (Production Checklist)

1. [ ] **Zero Layout Shifts**: Validasi bahwa transisi dinamis tidak memicu CLS (Cumulative Layout Shift) tak terduga dengan mencadangkan container dimensions (*aspect-ratio* atau *min-height*).
2. [ ] **Deterministic Data Seeds**: Pastikan dynamic mock engine menggunakan seed deterministik sehingga pengujian berulang menghasilkan dataset yang konsisten.
3. [ ] **Hardware Acceleration**: Pastikan seluruh node animasi memiliki properti CSS `will-change: transform` jika kompleks, atau dimanipulasi murni via transform matrix.
4. [ ] **Keyboard Navigability**: Prototipe harus dapat dioperasikan penuh via tombol `Tab`, `Enter`, `Escape`, dan `Spacebar` layaknya aplikasi final.
5. [ ] **W3C Design Token Compliance**: Nilai warna, radius, dan jarak tidak boleh di-*hardcode* sebagai nilai heksadesimal mentah di prototipe, melainkan wajib merujuk ke token CSS variables (`var(--semantic-color-action-primary)`).
6. [ ] **Error Path Completeness**: Skenario kegagalan (401 Unauthorized, 404 Not Found, 500 Internal Error, Request Timeout) wajib memiliki representasi visual eksplisit dalam prototipe.

---

### 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun sebuah prototipe interaktif untuk **Optimistic Post Creator** yang mensimulasikan kegagalan jaringan dan rollback state secara otomatis.

#### Struktur Direktori Target:
```
hands-on/
└── m02/
    ├── package.json
    ├── tsconfig.json
    ├── index.html
    └── src/
        ├── mocks/
        │   ├── browser.ts
        │   └── handlers.ts
        ├── machines/
        │   └── postMachine.ts
        ├── components/
        │   └── PostCreator.tsx
        ├── App.tsx
        └── main.tsx
```

#### Langkah 1: Setup Lingkungan
Buka terminal dan inisialisasi project React berbasis Vite + TypeScript di direktori `hands-on/m02/`:
```bash
npm create vite@latest hands-on/m02 -- --template react-ts
cd hands-on/m02
npm install
npm install xstate @xstate/react framer-motion msw clsx
npx msw init public/ --save
```

#### Langkah 2: Setup Mock Service Worker (`src/mocks/handlers.ts`)
```typescript
import { rest } from 'msw';

export const handlers = [
  rest.post('/api/posts', async (req, res, ctx) => {
    const { content } = await req.json();
    
    // Inject dynamic latency 1 detik
    await new Promise((r) => setTimeout(r, 1000));

    // Simulasi kegagalan jika konten mengandung kata "crash"
    if (content.toLowerCase().includes('crash')) {
      return res(
        ctx.status(500),
        ctx.json({ message: 'Database server panic: Internal Transaction Aborted.' })
      );
    }

    return res(
      ctx.status(201),
      ctx.json({
        id: `post_${Date.now()}`,
        content,
        timestamp: new Date().toISOString(),
      })
    );
  }),
];
```

Inisialisasi worker di `src/mocks/browser.ts`:
```typescript
import { setupWorker } from 'msw';
import { handlers } from './handlers';

export const worker = setupWorker(...handlers);
```

#### Langkah 3: Setup Machine dengan Logika Optimistic Rollback (`src/machines/postMachine.ts`)
```typescript
import { createMachine, assign } from 'xstate';

interface Post {
  id: string;
  content: string;
  isOptimistic?: boolean;
}

interface PostContext {
  posts: Post[];
  draftContent: string;
  previousPosts: Post[];
  errorMessage: string | null;
}

type PostEvent =
  | { type: 'CHANGE_DRAFT'; value: string }
  | { type: 'SUBMIT_POST' }
  | { type: 'DISMISS_ERROR' };

export const postMachine = createMachine<PostContext, PostEvent>({
  id: 'postLifecycle',
  initial: 'idle',
  context: {
    posts: [
      { id: '1', content: 'Selamat datang di demonstrasi High-Fidelity Prototyping!' }
    ],
    draftContent: '',
    previousPosts: [],
    errorMessage: null,
  },
  states: {
    idle: {
      on: {
        CHANGE_DRAFT: {
          actions: assign({ draftContent: (_, e) => e.value }),
        },
        SUBMIT_POST: {
          target: 'posting',
          cond: (ctx) => ctx.draftContent.trim().length > 0,
        },
      },
    },
    posting: {
      entry: assign({
        // Simpan snapshot untuk rollback
        previousPosts: (ctx) => [...ctx.posts],
        // Optimistic UI mutation
        posts: (ctx) => [
          { id: `temp_${Date.now()}`, content: ctx.draftContent, isOptimistic: true },
          ...ctx.posts,
        ],
      }),
      invoke: {
        src: (ctx) => async () => {
          const response = await fetch('/api/posts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: ctx.draftContent }),
          });

          if (!response.ok) {
            const err = await response.json();
            throw new Error(err.message || 'Gagal memposting status.');
          }

          return response.json();
        },
        onDone: {
          target: 'idle',
          actions: assign({
            posts: (ctx, event) =>
              ctx.posts.map((p) => (p.isOptimistic ? event.data : p)),
            draftContent: (_) => '',
            errorMessage: (_) => null,
          }),
        },
        onError: {
          target: 'idle',
          actions: assign({
            // Eksekusi Rollback
            posts: (ctx) => ctx.previousPosts,
            errorMessage: (_, event) => (event.data as Error).message,
          }),
        },
      },
    },
  },
});
```

#### Langkah 4: Tautkan Service Worker dan Entry Point UI (`src/main.tsx`)
```tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

async function prepare() {
  const { worker } = await import('./mocks/browser');
  return worker.start({
    onUnhandledRequest: 'bypass',
  });
}

prepare().then(() => {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
});
```

#### Langkah 5: Implementasikan View Interaktif (`src/App.tsx`)
```tsx
import React from 'react';
import { useMachine } from '@xstate/react';
import { motion, AnimatePresence } from 'framer-motion';
import { postMachine } from './machines/postMachine';

export default function App() {
  const [current, send] = useMachine(postMachine);
  const { posts, draftContent, errorMessage } = current.context;
  const isPosting = current.matches('posting');

  return (
    <div style={{ maxWidth: '520px', margin: '40px auto', fontFamily: 'sans-serif', padding: '0 16px' }}>
      <h2>Feed Prototipe Dinamis (Optimistic UI)</h2>
      <p style={{ fontSize: '13px', color: '#666' }}>
        Ketik teks dan kirim. Masukkan kata <strong>"crash"</strong> untuk menguji kegagalan jaringan & rollback instan.
      </p>

      <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <textarea
          rows={3}
          value={draftContent}
          onChange={(e) => send({ type: 'CHANGE_DRAFT', value: e.target.value })}
          placeholder="Apa yang sedang terjadi?"
          style={{ width: '100%', padding: '8px', boxSizing: 'border-box' }}
        />
        <button
          onClick={() => send({ type: 'SUBMIT_POST' })}
          disabled={isPosting || draftContent.trim().length === 0}
          style={{
            alignSelf: 'flex-end',
            padding: '8px 16px',
            background: isPosting ? '#ccc' : '#0066cc',
            color: '#fff',
            border: 'none',
            borderRadius: '4px',
            cursor: isPosting ? 'not-allowed' : 'pointer',
          }}
        >
          {isPosting ? 'Mengirim...' : 'Publikasikan'}
        </button>
      </div>

      {errorMessage && (
        <div style={{ marginTop: '12px', padding: '8px', background: '#ffebee', color: '#c62828', borderRadius: '4px', fontSize: '12px' }}>
          <strong>Error Terdeteksi:</strong> {errorMessage} (Data telah di-rollback)
        </div>
      )}

      <div style={{ marginTop: '24px' }}>
        <h3>Daftar Entri Live</h3>
        <ul style={{ listStyle: 'none', padding: 0 }}>
          <AnimatePresence initial={false}>
            {posts.map((post) => (
              <motion.li
                key={post.id}
                layout
                initial={{ opacity: 0, y: -20, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                transition={{ duration: 0.2 }}
                style={{
                  border: '1px solid #e0e0e0',
                  borderRadius: '6px',
                  padding: '12px',
                  marginBottom: '8px',
                  backgroundColor: post.isOptimistic ? '#f9f9f9' : '#fff',
                  borderLeft: post.isOptimistic ? '4px solid #f59e0b' : '4px solid #10b981',
                }}
              >
                <div style={{ fontSize: '14px' }}>{post.content}</div>
                {post.isOptimistic && (
                  <div style={{ fontSize: '10px', color: '#f59e0b', marginTop: '4px' }}>
                    Sedang menyinkronkan ke server...
                  </div>
                )}
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      </div>
    </div>
  );
}
```

Jalankan perintah pengujian:
```bash
npm run dev
```

---

### 13. Exercise

#### Level Easy
Ubah logika animasi komponen `DynamicSwitch` pada *Section 7.A*:
* Tambahkan state haptic feedback visual: Ketika switch di-klik namun dalam kondisi `disabled`, switch bergetar secara horizontal (*shake animation*: `x: [-4, 4, -4, 4, 0]`) selama 200ms.

#### Level Medium
Perluas `transferMachine` pada *Section 7.B*:
* Tambahkan state `insufficient_funds_warning` yang muncul jika nominal transfer berada di antara 90% hingga 100% dari total saldo, meminta konfirmasi ganda sebelum state berpindah ke `validating`.

#### Level Hard
Kembangkan subsistem form input pada `PostCreator` (*Hands-on 12*):
* Integrasikan skema validasi Zod asinkronus yang mengecek ke server mock `/api/check-profanity` setiap kali user berhenti mengetik selama 400ms (*debounced validation*). Jika server mengembalikan flag pelanggaran, disable tombol submit dan tampilkan invalidation badge dengan transisi *spring pop-in*.

---

### 14. Challenge

#### Skenario: "High-Frequency Algorithmic Trading Seat Allocation Prototype"
Sebuah perusahaan sekuritas enterprise membutuhkan validasi antarmuka untuk fitur *Order Book & Dynamic Liquidity Reservation*. 

**Spesifikasi Desain & Teknis Tantangan:**
1. **Dynamic Streaming Payload**: Prototipe harus mensimulasikan *WebSocket stream* lokal yang memperbarui nilai spread bid/ask setiap 100 milidetik dengan variasi random acak.
2. **Deterministic Race Conditions**: Pengguna harus dapat memesan kuota trading slot. Jika kuota telah diambil oleh sistem simulasi pada milidetik yang sama saat tombol ditekan, UI harus menampilkan dialog interaktif *Conflict Resolution* dengan perbandingan diff harga (*Stale Value* vs *Executed Market Value*).
3. **Strict Zero-Jank Threshold**: Seluruh baris order book yang ter-update 10 kali per detik tidak boleh memicu re-render pada seluruh pohon komponen induk (manfaatkan canvas element isolation atau unmounted subscription primitives).

**Kriteria Keberhasilan:**
* Berhasil memvalidasi alur penyelesaian sengketa transaksi pengguna tanpa freeze main thread sama sekali (tervalidasi via Performance Profiler Chrome DevTools: 0 frame drop di bawah 60 FPS).
* Menghasilkan dokumen pemetaan State Machine formal yang membuktikan tidak ada kemungkinan status *infinite loading*.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Pertanyaan)
1. **Apa perbedaan mendasar antara state machine deterministik (FSM) dengan pendekatan boolean flag jamak dalam prototipe dinamis?**
   * *Jawaban*: FSM membatasi sistem hanya berada pada satu status eksklusif pada satu waktu dari sekumpulan status berhingga yang terdefinisi matematis, sehingga meniadakan kombinasi status ilegal (*impossible states*). Boolean flags jamak dapat aktif bersamaan secara tidak sengaja, memicu bug status yang kontradiktif.

2. **Mengapa interpolasi animasi harus mengutamakan properti `transform` dan `opacity`?**
   * *Jawaban*: Karena kedua properti tersebut diproses langsung oleh GPU Compositor layer tanpa perlu memicu tahapan Layout/Reflow dan Paint pada DOM tree utama, mencegah layout thrashing.

3. **Apa peran Service Worker (misal: MSW) dibandingkan fungsi mock manual lokal (`fetch = jest.fn()`) dalam dynamic prototyping?**
   * *Jawaban*: Service Worker beroperasi pada level jaringan sistem operasi/browser di luar eksekusi runtime aplikasi utama, membelokkan request HTTP sesungguhnya tanpa memodifikasi source code aplikasi target, sehingga mendekati kondisi integrasi produksi yang nyata.

4. **Kapan tim sebaiknya berpindah dari prototipe visual (Figma) ke prototipe berbasis kode (Code-driven Prototype)?**
   * *Jawaban*: Ketika alur interaksi melibatkan logika kondisional tingkat tinggi, penanganan asinkronus jaringan nyata, input gestural rumit, atau pengujian aksesibilitas mendalam yang tidak bisa direpresentasikan secara linier oleh artboard kanvas.

5. **Apa yang dimaksud dengan "Optimistic UI" dalam dynamic prototyping?**
   * *Jawaban*: Pola perancangan antarmuka yang mengasumsikan mutasi data ke server akan selalu berhasil, langsung memperbarui state visual seketika untuk menghilangkan persepsi latensi, sembari menyediakan mekanisme rollback deterministik jika terjadi kegagalan transmisi data.

#### Intermediate (5 Pertanyaan)
6. **Bagaimana cara mencegah memory leak pada prototipe dinamis yang menggunakan subscription timer atau simulasi WebSocket stream?**
   * *Jawaban*: Menjalankan cleanup function pada hook pemusnahan komponen (misal: `useEffect` return callback atau `xstate invoke onDone/exit actions`) yang secara eksplisit memanggil `clearInterval()`, menghentikan listener event, atau membatalkan promise aktif.

7. **Dalam XState, apa perbedaan fungsional antara `actions` dan `services`?**
   * *Jawaban*: `actions` adalah efek samping synchronous yang dijalankan secara "fire-and-forget" saat transisi state terjadi tanpa durasi; sedangkan `services` merepresentasikan aktivitas asynchronous yang memiliki durasi (Promise, Observable, atau sub-machine) dan dapat mengirimkan event kembali ke parent machine setelah selesai atau gagal.

8. **Mengapa prototipe dinamis tidak boleh diuji menggunakan latensi sintetis statis konstan (misal: tepat 500ms setiap kali)?**
   * *Jawaban*: Jaringan dunia nyata memiliki sifat fluktuatif (*jitter*). Menguji dengan latensi statis menutupi potensi *race condition* di mana urutan respon tidak sesuai dengan urutan pengiriman awal (*out-of-order response resolving*).

9. **Apa implikasi penggunaan CSS `will-change: transform` yang berlebihan pada ratusan elemen di dalam prototipe dinamis?**
   * *Jawaban*: Pemakaian berlebihan memaksa browser membuat Compositor Layer terpisah untuk setiap elemen, yang menyebabkan konsumsi memori GPU (VRAM) membengkak secara drastis dan justru memperlambat performa rendering perangkat (*VRAM exhaustion*).

10. **Bagaimana format token W3C DTCG memfasilitasi sinkronisasi antara desainer grafis dan prototipe kode?**
    * *Jawaban*: Menyediakan skema JSON standar terpadu yang memisahkan nilai primitif dari konteks semantik, memungkinkan pipeline automasi (seperti Style Dictionary) mengonversi token desain Figma menjadi variabel platform target (CSS, SCSS, JS, Android XML, iOS Swift) secara presisi tanpa intervensi manual.

#### Skenario Kasus Produksi (3 Pertanyaan)

11. **Skenario 1 (The Ghost Spinner)**:
    Prototipe form pembayaran Anda menunjukkan animasi *spinner* tak berujung ketika MSW di-set ke mode *Offline*. Setelah dianalisis, `catch` block pada fetch call Anda memanggil dispatch action `SUBMIT_ERROR`, tetapi antarmuka tetap menampilkan spinner.
    * *Pertanyaan*: Analisis kesalahan arsitektur tersebut dan jelaskan solusinya menggunakan konsep State Machine.
    * *Solusi*: Sistem mengalami status kebocoran (unhandled transition). Mesin prototipe Anda kemungkinan berada pada sub-state `pending` yang tidak memiliki event listener untuk transisi error, atau event error tidak mereset target visual ke status kegagalan. Solusinya: definisikan status transisi eksplisit `onError: { target: 'failure' }` di dalam blok invoke service XState, yang secara otomatis memutus status pending dan memperbarui context state pesan error.

12. **Skenario 2 (The Multi-Touch Race Condition)**:
    Pada prototipe aplikasi mobile e-commerce, seorang tester menekan tombol "Tambahkan ke Wishlist" dan "Beli Sekarang" secara simultan dengan dua jari pada microsecond yang berdekatan. Terjadi duplikasi mutasi dan layout modal bertumpuk berantakan.
    * *Pertanyaan*: Bagaimana Anda mendesain prototipe untuk memitigasi kejadian ini secara deterministik?
    * *Solusi*: Bungkus kedua aksi dalam Root Statechart yang memprogram status interaksi global. Ketika event pertama diterima (`ADD_TO_WISHLIST`), state segera bertransisi ke `mutating_cart` dan memberlakukan `guard` yang menolak semua interaksi pointer masuk (`pointer-events: none` atau guard condition: `cond: (ctx) => !ctx.isLocked`). Ini menjamin eksekusi atomik pada setiap event tanpa tumpang tindih.

13. **Skenario 3 (Jank on Filter Typing)**:
    Prototipe pencarian instan menampilkan 5,000 baris inventaris mock. Pengguna mengeluhkan input teks terasa "lag" parah saat mengetikkan kueri pencarian baru. Profiler menunjukkan execution time JavaScript mencapai 180ms per keystroke.
    * *Pertanyaan*: Rekomendasikan optimasi arsitektural rendering pada level prototipe kode tanpa mengurangi total baris mock data.
    * *Solusi*:
      1. Terapkan algoritma **List Virtualization/Windowing** (menggunakan library seperti `react-window` atau custom intersection observer), sehingga hanya merender elemen yang masuk ke dalam viewport aktif (sekitar 10-20 elemen, bukan 5,000 DOM nodes).
      2. Pisahkan state input dari state filtering menggunakan React 18 `useDeferredValue` atau `useTransition`, menjaga thread pengetikan tetap responsif pada prioritas tinggi selagi filter array berjalan di prioritas rendah.

---

### 16. Summary

High-Fidelity Dynamic Prototyping adalah puncak rekayasa validasi desain antarmuka. Dengan mentransformasi artboard visual statis menjadi spesifikasi fungsional berbasis **Finite State Machines (XState)**, simulasi jaringan layer rendah (**MSW**), dan micro-interaction berbasis **Spring Physics**, tim pengembang produk enterprise dapat:
1. Mengeliminasi celah interpretasi logika bisnis antara Engineering dan Product Design.
2. Menguji kegagalan jaringan, dependensi API asinkron, dan edge cases secara riil sebelum pengeluaran biaya modal development produksi.
3. Menjamin akurasi metrik pengujian pengguna (*usability testing*) dengan performa rendering 60-120 FPS tanpa gangguan teknis buatan (*artificial jank*).

Melalui disiplin ini, prototipe berhenti menjadi sekadar "gambar visual interaktif" dan beralih fungsi menjadi **fondasi kode arsitektural teruji** yang mempercepat siklus peluncuran produk secara masif dan aman.