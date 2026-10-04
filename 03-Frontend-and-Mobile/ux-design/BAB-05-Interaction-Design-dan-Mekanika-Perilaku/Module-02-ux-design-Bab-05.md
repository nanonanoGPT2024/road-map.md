# BAB 05: Interaction Design & Mekanika Perilaku
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Merancang & Mengimplementasikan Finite State Machines (FSM)** untuk interaksi antarmuka kompleks guna mengeliminasi *impossible UI states*, *race conditions*, dan *ghost clicks*.
2. **Menguasai Gesture Disambiguation & Physics-based Animations** yang beroperasi secara deterministik pada *compositor thread* (60/120 FPS) tanpa menyebabkan *layout thrashing*.
3. **Mengarsitekturi Pola Optimistic UI & Reversibilitas Transaksional** dengan mekanisme *automatic rollback*, reconciler lokal, dan kompensasi latensi perseptual (*perceptual latency optimization*).
4. **Menerapkan Standar Aksesibilitas Perilaku (WAI-ARIA 1.2 State & Focus Management)** pada komponen interaktif tingkat lanjut secara programatis.
5. **Menganalisis Trade-off Kinerja Interaksi** (Frame Budget, Memory Leaks pada Event Streams, Event Delegation Overhead) pada aplikasi web dan mobile enterprise skala masif.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
* Konsep dasar DOM Event Loop, Macro/Microtasks, dan bubbling/capturing phase.
* Pemahaman fundamental CSS Compositing: `transform`, `opacity`, `will-change`, dan layer promotion.
* JavaScript/TypeScript tingkat lanjut (Typed Events, Observables/Event Streams, WeakMaps, Closures).
* Desain sistem dasar: Pola State/Action dasar (React/Vue/Svelte reactivity model).

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Mekanika Event Loop, Input Queues, dan Frame Budgeting
Interaksi pengguna dimulai dari hardware level (digitizer/mouse) yang mengalir melalui driver sistem operasi hingga ke browser engine. Browser memproses *input events* (seperti `touchstart`, `pointermove`) di OS thread, memindahkannya ke Browser Process, lalu mengantarkannya ke Renderer Process.

```
[Hardware/Digitizer] 
        │
        ▼
[OS Window Server / Kernel Driver]
        │ (Raw Pointer Coordinates)
        ▼
[Browser Process: IO Thread]
        │
        ├── (Input Event Queued)
        ▼
[Renderer Process: Compositor Thread]
        │
        ├── [Hit Test Target via Layer Tree]
        │       │
        │       ├── Kasus A: Fast Path (Non-blocking touch-action)
        │       │      └── Langsung eksekusi Scroll/Pinch di Compositor (120 FPS)
        │       │
        │       └── Kasus B: Slow Path (Ada Event Listener aktif / JS Hook)
        │              └── Delegasikan ke Main Thread
        ▼
[Renderer Process: Main Thread]
        │
        ├── [JavaScript Execution: FSM & Interaction Logic]
        ├── [Recalculate Style & Reflow (Layout)]
        ├── [Paint: Display Lists Generation]
        └── [Layer Commit]
        ▼
[Compositor Thread] ──> [GPU Rasterization] ──> [Display Frame Buffer]
```

Pada *high-refresh-rate displays* (120Hz), **Frame Budget** adalah **8.33ms** per frame (16.67ms pada 60Hz). Jika JavaScript memproses interaksi melebihi budget ini:
$$\text{Frame Drop} = \Delta t_{\text{execution}} > t_{\text{frame\_budget}}$$
Browser akan melewatkan (*drop*) frame tersebut, menghasilkan fenomena *jank* atau *stutter*. Oleh karena itu, interaksi modern membagi beban kerja:
1. **Compositor Worker / Gestures**: Dijalankan murni melalui property compositing (misal: CSS `transform`) dengan deklarasi CSS `touch-action: none` untuk memotong siklus tunggu main-thread hit testing.
2. **Main Thread Logic**: Hanya dieksekusi untuk pembaruan state logis dan side-effects transaksional.

#### B. Finite State Machine (FSM) dalam Interaction Design
Kelemahan arsitektur UI berbasis boolean flag (misal: `isLoading`, `hasError`, `isDragging`) adalah ledakan kombinatorik status:
$$N \text{ boolean flags} \implies 2^N \text{ kemungkinan states}$$
Sebagian besar dari state ini adalah kondisi cacat (*impossible states*), seperti `{ isLoading: true, isSuccess: true }`.

FSM memodelkan interaksi sebagai tuple matematis formal:
$$M = (S, \Sigma, \delta, s_0, F)$$
* $S$: Himpunan state diskret yang terbatas (`idle`, `pressing`, `dragging`, `settling`, `committing`).
* $\Sigma$: Himpunan event/transisi (`POINTER_DOWN`, `MOVE`, `THRESHOLD_BREACHED`, `RELEASE`, `ROLLBACK`).
* $\delta$: Fungsi transisi $S \times \Sigma \to S$.
* $s_0$: Initial state (`idle`).
* $F$: Set of final/terminal states.

Dengan FSM, input yang datang saat sistem berada di state yang tidak valid akan diabaikan secara mutlak (*deterministic rejection*).

#### C. Optimistic UI Reconciler Architecture
Optimistic UI memanipulasi Local Memory State secara instan sebelum network call selesai:

```
[User Action] 
     │
     ├── 1. Snapshot State Saat Ini (Rollback Capsule)
     ├── 2. Mutasi Local State (Optimistic DOM Render)
     ├── 3. Dispatch Async Network Mutation (AbortController Aware)
     │
     ▼
[Network Response Loop]
     ├── Kasus Sukses (2xx):
     │       └── Commit State Permanen & Hapus Snapshot
     │
     └── Kasus Gagal (4xx/5xx/Timeout):
             ├── Restore State dari Snapshot
             ├── Dispatch Perceptual Feedback (Toast/Haptic/Inline Alert)
             └── Transisi FSM ke State 'RECOVERED_ERROR'
```

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Ad-Hoc / Flags) | Pendekatan Behavioral Enterprise (FSM + Compositor First) |
| :--- | :--- | :--- |
| **State Handling** | Boolean scattering (`isSubmitting`, `isHovered`, `canDrag`). Rawan race condition & phantom triggers. | Deterministic Finite State Machine. State tak valid secara matematis mustahil dicapai. |
| **Respons Frame** | Mutasi layout langsung di main-thread via direct DOM style manipulation (Layout Thrashing). | Isolasi mutasi ke transform/opacity via CSS variables/Web Animations API (WAAPI) di layer GPU. |
| **Handling Network** | UI diblokir oleh spinner (*blocking latency*), pengguna tidak memiliki kendali visual. | Optimistic updates dengan rollback transactional context; latensi dipersepsi sebagai zero ms. |
| **Aksesibilitas** | Event mouse dan touch terpisah, seringkali mengabaikan WAI-ARIA states & Focus Traps. | Pola pointer agnostik terpadu yang memetakan status FSM ke ARIA attributes (`aria-expanded`, `aria-busy`). |

---

### 5. How (Workflow Detail)

1. **Phase 1: Input Registration & Arbitration**
   Menggunakan `PointerEvents` untuk menangkap interaksi multi-device (Mouse, Pen, Touch). Gunakan CSS `touch-action` untuk mendeklarasikan apakah browser diizinkan mengambil alih gesture (misal: native vertical scrolling) atau menyerahkannya sepenuhnya ke aplikasi.

2. **Phase 2: Intent Thresholding (Dead-zone Calculation)**
   Jangan langsung mengeksekusi drag/swipe pada pointer move pertama. Hitung delta Euclidean:
   $$d = \sqrt{(\Delta x)^2 + (\Delta y)^2}$$
   Jika $d < \text{threshold}$ (umumnya 4-8px), interaksi tetap dipertahankan pada status `TAP_CANDIDATE`. Begitu $d \ge \text{threshold}$, transisikan FSM ke `DRAGGING` dan panggil `setPointerCapture`.

3. **Phase 3: Execution via Compositor Hooks**
   Hindari pembaruan React/Vue state secara synchronous pada event `pointermove`. Perbarui CSS Custom Properties pada element style secara langsung atau gunakan `requestAnimationFrame` (rAF) batching.

4. **Phase 4: Resolution & Reconcile**
   Saat `pointerup`, evaluasi kecepatan pelepasan (*release velocity*) menggunakan moving average. Tentukan apakah aksi harus diselesaikan (*settle to destination*) atau dibatalkan (*snap back*). Jika memicu mutasi data, inisialisasi optimistic engine.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Pintu Air Kapal Terusan Panama
Bayangkan antarmuka seperti Pintu Air Kanal Panama. Kapal tidak dapat bergerak bebas ke level air berikutnya jika pintu depan dan belakang terbuka bersamaan (kondisi invalid). Pintu hanya terbuka jika ruang kedap mencapai elevasi yang sama (*Deterministic State Transition*). Jika sistem pompa hidrolik gagal di tengah jalan (*Network Error*), pintu tidak dibiarkan menggantung; sistem darurat mengembalikan air ke elevasi asal secara otomatis (*Optimistic Rollback*).

#### Diagram Interaksi Runtime
```
User Event          Pointer Pipeline                FSM Context             Compositor / GPU
    │                      │                             │                         │
    │── PointerDown ──────>│                             │                         │
    │                      │── [Evt: POINTER_DOWN] ─────>│                         │
    │                      │                             │── [State: PENDING]      │
    │                      │                             │                         │
    │── PointerMove ──────>│                             │                         │
    │   (Delta > 6px)      │── [Evt: THRESHOLD_PASS] ───>│                         │
    │                      │                             │── [State: DRAGGING]     │
    │                      │                             │                         │
    │                      │<── setPointerCapture ───────│                         │
    │                      │                                                       │
    │                      │── Update CSS Var (--tx) ─────────────────────────────>│ (Direct Layer Update)
    │                      │                                                       │ (Zero Main Thread Reflow)
    │── PointerUp ────────>│                                                       │
    │                      │── [Evt: RELEASE] ──────────>│                         │
    │                      │                             │── Check Threshold Met   │
    │                      │                             │   ├── YES -> [COMMIT]   │
    │                      │                             │   └── NO  -> [REVERT]   │
    │                      │                                                       │
    │                      │<── Apply Spring Physics Animation (WAAPI) ───────────>│ (Interpolasi Settle)
    │                      │                             │                         │
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Vanilla JS Pointer FSM (Core Concept)
FSM sederhana untuk mengunci gesture dan mencegah overlapping multi-pointer race conditions:

```typescript
type DragState = 'IDLE' | 'TRACKING' | 'DRAGGING';

class ButtonInteractionFSM {
  private state: DragState = 'IDLE';
  private startX = 0;
  private readonly threshold = 8;

  constructor(private element: HTMLElement) {
    this.element.addEventListener('pointerdown', this.onPointerDown);
    this.element.addEventListener('pointermove', this.onPointerMove);
    this.element.addEventListener('pointerup', this.onPointerUp);
    this.element.addEventListener('pointercancel', this.onPointerUp);
  }

  private onPointerDown = (e: PointerEvent) => {
    if (this.state !== 'IDLE') return;
    this.startX = e.clientX;
    this.state = 'TRACKING';
    this.element.setPointerCapture(e.pointerId);
  };

  private onPointerMove = (e: PointerEvent) => {
    if (this.state === 'TRACKING') {
      const deltaX = Math.abs(e.clientX - this.startX);
      if (deltaX > this.threshold) {
        this.state = 'DRAGGING';
        this.element.setAttribute('data-interaction-state', 'dragging');
      }
    }

    if (this.state === 'DRAGGING') {
      const offset = e.clientX - this.startX;
      this.element.style.transform = `translateX(${offset}px)`;
    }
  };

  private onPointerUp = (e: PointerEvent) => {
    if (this.state === 'DRAGGING') {
      this.element.style.transition = 'transform 0.2s cubic-bezier(0.2, 0.9, 0.3, 1)';
      this.element.style.transform = 'translateX(0px)';
      setTimeout(() => {
        this.element.style.transition = '';
      }, 200);
    }
    this.state = 'IDLE';
    this.element.removeAttribute('data-interaction-state');
    try {
      this.element.releasePointerCapture(e.pointerId);
    } catch {
      // Graceful fallback jika pointer capture dilepas browser secara paksa
    }
  };
}
```

#### B. Practical Enterprise Example: Swipe-to-Action dengan Optimistic Rollback
Komponen React + TypeScript tingkat produksi dengan integrasi Spring Physics, Accessibility, dan Network Mutation Rollback.

```tsx
import React, { useState, useRef, useEffect, useCallback } from 'react';

// --- Tipe State Interaksi ---
type SwipePhase = 'IDLE' | 'PANNING' | 'ANIMATING' | 'COMMITTED';

interface OptimisticItem {
  id: string;
  label: string;
  status: 'active' | 'deleted';
}

interface SwipeActionProps {
  item: OptimisticItem;
  onDeleteAsync: (id: string) => Promise<void>;
  onRollback: (error: Error, previousItem: OptimisticItem) => void;
}

export const EnterpriseSwipeAction: React.FC<SwipeActionProps> = ({
  item,
  onDeleteAsync,
  onRollback,
}) => {
  const [phase, setPhase] = useState<SwipePhase>('IDLE');
  const containerRef = useRef<HTMLDivElement>(null);
  
  // Koordinat & Tracking Kinematik (Mutable refs untuk bypass main-thread React re-renders)
  const kinematicRef = useRef({
    startX: 0,
    currentX: 0,
    pointerId: -1,
    velocity: 0,
    lastTime: 0,
  });

  const SWIPE_DISMISS_THRESHOLD = -120; // Geser kiri sejauh 120px untuk aksi hapus

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (phase !== 'IDLE' || e.button !== 0) return; // Khusus Primary Mouse Click atau Touch
    
    kinematicRef.current.startX = e.clientX;
    kinematicRef.current.currentX = e.clientX;
    kinematicRef.current.pointerId = e.pointerId;
    kinematicRef.current.velocity = 0;
    kinematicRef.current.lastTime = performance.now();

    e.currentTarget.setPointerCapture(e.pointerId);
    setPhase('PANNING');
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (phase !== 'PANNING' || e.pointerId !== kinematicRef.current.pointerId) return;

    const now = performance.now();
    const dt = now - kinematicRef.current.lastTime;
    const deltaX = e.clientX - kinematicRef.current.startX;

    // Batasi swipe: hanya izinkan ke kiri (nilai negatif), tolak geser kanan
    if (deltaX > 0) return;

    // Hitung moving velocity (px/ms)
    if (dt > 0) {
      kinematicRef.current.velocity = (e.clientX - kinematicRef.current.currentX) / dt;
    }
    
    kinematicRef.current.currentX = e.clientX;
    kinematicRef.current.lastTime = now;

    // Manipulasi CSS custom property secara langsung tanpa React Virtual DOM re-render
    if (containerRef.current) {
      containerRef.current.style.setProperty('--swipe-offset', `${deltaX}px`);
    }
  };

  const executeRollbackAnimation = useCallback(() => {
    setPhase('ANIMATING');
    if (!containerRef.current) return;

    const animation = containerRef.current.animate(
      [
        { transform: `translateX(${containerRef.current.style.getPropertyValue('--swipe-offset') || '0px'})` },
        { transform: 'translateX(0px)' }
      ],
      {
        duration: 250,
        easing: 'cubic-bezier(0.175, 0.885, 0.32, 1.275)', // Overshoot spring
        fill: 'forwards'
      }
    );

    animation.onfinish = () => {
      if (containerRef.current) {
        containerRef.current.style.setProperty('--swipe-offset', '0px');
      }
      animation.cancel();
      setPhase('IDLE');
    };
  }, []);

  const handlePointerUp = async (e: React.PointerEvent<HTMLDivElement>) => {
    if (phase !== 'PANNING' || e.pointerId !== kinematicRef.current.pointerId) return;

    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {
      // Handle fallback jika pointer release di-revoke OS
    }

    const totalDeltaX = kinematicRef.current.currentX - kinematicRef.current.startX;
    const finalVelocity = kinematicRef.current.velocity;

    // Threshold tercapai jika offset cukup jauh ATAU kecepatan flick memadai
    const isDismissed = totalDeltaX < SWIPE_DISMISS_THRESHOLD || finalVelocity < -0.8;

    if (isDismissed) {
      // 1. Masuk ke Phase Committed (Optimistic Execution)
      setPhase('COMMITTED');

      // 2. Animate out
      if (containerRef.current) {
        const exitAnim = containerRef.current.animate(
          [
            { transform: `translateX(${totalDeltaX}px)`, opacity: 1 },
            { transform: 'translateX(-100%)', opacity: 0 }
          ],
          { duration: 200, easing: 'cubic-bezier(0.4, 0.0, 0.2, 1)', fill: 'forwards' }
        );

        exitAnim.onfinish = async () => {
          // 3. Trigger network dispatch dengan state isolation
          try {
            await onDeleteAsync(item.id);
          } catch (err) {
            // 4. TRANSACTION ROLLBACK jika network error
            exitAnim.cancel();
            executeRollbackAnimation();
            onRollback(err as Error, item);
          }
        };
      }
    } else {
      executeRollbackAnimation();
    }
  };

  return (
    <div 
      className="relative overflow-hidden w-full max-w-md bg-neutral-900 select-none rounded-lg border border-neutral-800"
      style={{ touchAction: 'pan-y' }} // Membiarkan OS mengambil vertical scroll, mengunci horizontal
    >
      {/* Background Action Indicator Layer */}
      <div 
        aria-hidden="true" 
        className="absolute inset-0 bg-red-600 flex items-center justify-end pr-6 text-white font-semibold text-sm"
      >
        Hapus Item
      </div>

      {/* Foreground Swipeable Layer */}
      <div
        ref={containerRef}
        role="listitem"
        aria-label={`${item.label}, swipe left to delete`}
        tabIndex={0}
        onKeyDown={(e) => {
          // Fallback Aksesibilitas Keyboard: Delete key memicu action langsung
          if (e.key === 'Delete' || e.key === 'Backspace') {
            setPhase('COMMITTED');
            onDeleteAsync(item.id).catch((err) => onRollback(err, item));
          }
        }}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
        style={{
          transform: 'translateX(var(--swipe-offset, 0px))',
          willChange: phase === 'PANNING' ? 'transform' : 'auto',
        }}
        className={`relative z-10 p-4 bg-neutral-800 text-white cursor-grab active:cursor-grabbing transition-colors duration-150 ${
          phase === 'COMMITTED' ? 'pointer-events-none' : ''
        }`}
      >
        <span className="font-medium">{item.label}</span>
      </div>
    </div>
  );
};
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Ultra-Low Latency "Slide to Execute Order" pada Institutional Crypto Exchange
* **Skala Sistem**: 1.2 juta active daily users, volume transaksi > $500M/hari.
* **Problem**: Pada implementasi awal, slider konfirmasi eksekusi order menggunakan library slider berbasis React state update pada event `mousemove`. Hal ini menghasilkan *layout thrashing* parah pada perangkat mobile mid-end saat market crash (ribuan update orderbook per detik melalui WebSocket).
* **Insiden Produksi**: Pengguna mengalami race-condition: slider macet di 85%, namun order tereksekusi ganda di backend akibat *double tap* yang tidak di-filter oleh state machine, mengakibatkan *over-allocation* margin modal senilai $140,000.
* **Solusi Arsitektural**:
  1. Mengganti continuous state slider dengan **XState-based Pointer Machine**. Interaksi hanya mengenal 4 state diskret: `READY`, `SLIDING`, `LOCKED_EVALUATING`, `EXECUTED`. State `LOCKED_EVALUATING` langsung men-detach semua pointer event handlers di microtask pertama.
  2. Implementasi CSS `touch-action: none` langsung pada track slider dan mengisolasi offset transform murni ke CSS variable yang di-update via event listener `{ passive: true }`.
  3. Memisahkan eksekusi render visual dan payload dispatch:
     - Main thread: Dispatch idempotent request ID (`UUIDv4`) ke broker service worker via background message queue.
     - Compositor: Eksekusi haptic feedback (`navigator.vibrate([15, 50, 15])`) dan trigger particle success animation menggunakan `OffscreenCanvas`.
* **Dampak**: 
  - 0% insiden double execution tercatat kembali pasca deployment.
  - Latensi gesture-to-paint turun drastis dari **68ms** (jank level) menjadi **4.1ms** (Compositor-only lockup).

---

### 9. Trade-offs

| Aspek | Pendekatan FSM + GPU Layering | Pendekatan Re-render Reaktif (Declarative-Only) |
| :--- | :--- | :--- |
| **Kinerja (Frame Latency)** | **Sangat Baik (~4-8ms)**: Bypass Virtual DOM reconciliation engine. Berjalan langsung pada layer composite GPU. | **Sedang hingga Buruk (~16-60ms)**: Setiap pixel pergerakan memicu component lifecycle, diffing, dan layout reflow. |
| **Kompleksitas Kode & Maintainability** | **Tinggi**: Membutuhkan boilerplates FSM formal, pointer lifecycle tracking, cleanup ref manual, dan penanganan fallback aksesibilitas. | **Rendah**: Sangat deklaratif; cukup memetakan `style={{ left: x }}` via standard state. |
| **Skalabilitas Fitur** | **Sangat Terprediksi**: Penambahan edge case baru (misal: interrupt modal, multi-touch cancellation) mudah diakomodasi dalam transition matrix FSM. | **Rapuh**: Menambahkan flag status baru sering menimbulkan bug regresi pada state combinations yang belum diuji. |
| **Memory Footprint** | **Minimal**: Tidak menghasilkan alokasi objek VNode berulang pada rentang pointer event streams frekuensi tinggi. | **Boros**: Ribuan closures dan temporary VNodes teralokasi per detik, memicu Garbage Collection pauses. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Layout Thrashing di dalam Event Loop Pointer
* **Gejala**: FPS anjlok dari 120 ke 20 saat user menggeser elemen. Tab DevTools Performance menampilkan deretan bar merah "Forced Reflow".
* **Akar Masalah**: Membaca properti layout geometri (misal: `element.offsetWidth`, `getBoundingClientRect()`) sesaat setelah menulis modifikasi layout (misal: `element.style.left = ...`) di dalam `pointermove`.
* **Solusi**: Pisahkan tahap Read dan Write. Gunakan `transform: translate3d()` sebagai pengganti manipulasi top/left/right/bottom.

#### 2. Phantom Pointer Capture Memory Leak
* **Gejala**: UI berhenti merespons klik atau input di seluruh halaman setelah gestur swipe dibatalkan secara abnormal (misal: muncul notifikasi sistem operasi / dialog alert browser).
* **Akar Masalah**: Memanggil `setPointerCapture(id)` tanpa menyertakan listener pembatalan `pointercancel` atau tidak membungkus `releasePointerCapture` dalam blok `try/catch`.
* **Solusi**: Selalu pasang event handler `pointercancel` yang mengembalikan FSM ke initial state `IDLE` dan membersihkan pointer captures.

#### 3. Optimistic Sync Divergence (Zombie UI)
* **Gejala**: Pengguna melihat item telah terhapus, tetapi setelah me-refresh halaman atau berpindah tab, item tersebut muncul kembali tanpa ada indikator error.
* **Akar Masalah**: Pola Optimistic UI menelan (*swallow*) rejection Promise atau gagal menyediakan fallback state machine transisi ketika response HTTP 409 (Conflict) / 500 terjadi.
* **Solusi**: Selalu sediakan *reversibility capsule* yang dapat me-restore snapshot struktur data lengkap beserta visual notification contextual (bukan sekadar silent fail).

---

### 11. Best Practices (Production Checklist)

- [ ] **CSS Pointer Confinement**: Komponen gestur wajib menyertakan properti `touch-action: pan-y` (untuk gestur horizontal) atau `touch-action: none` (untuk bidirectional control) guna mencegah konflik scroll container native.
- [ ] **Hardware Acceleration Layer**: Elemen yang digerakkan wajib memiliki instruksi compositing eksplisit: `will-change: transform`. Hapus nilai properti ini saat state kembali ke `IDLE` untuk menghemat alokasi memori VRAM GPU.
- [ ] **Agnostic Pointer Support**: Hentikan pemakaian event `touchstart`/`mousedown` terpisah. Gunakan W3C standard `PointerEvent` (`pointerdown`, `pointermove`, `pointerup`, `pointercancel`).
- [ ] **State Machine Invariant Guarding**: Hindari deklarasi multiple boolean status. Seluruh status transisi interaksi harus dimodelkan melalui Discriminated Unions / Enum FSM.
- [ ] **Accessibility Parity**: Setiap gestur berbasis swipe, drag, atau long-press wajib memiliki aksi ekuivalen yang dapat diakses penuh via **Keyboard** (`Enter`, `Space`, `Delete`, `Arrow Keys`) dan terekspos ke screen reader (`aria-live`, `aria-roledescription`).
- [ ] **Reconciliation Rollback Audit**: Setiap pembaruan Optimistic UI wajib memiliki fungsi unit test yang memvalidasi integritas rollback data ketika API downstream mengembalikan network timeout.

---

### 12. Hands-on Practice

Simpan seluruh file berikut ke dalam direktori: `hands-on/m02/`

#### Struktur Proyek
```
hands-on/m02/
├── package.json
├── index.html
├── src/
│   ├── main.ts
│   ├── fsm/
│   │   └── buttonFsm.ts
│   └── styles/
│       └── main.css
```

#### File: `hands-on/m02/package.json`
```json
{
  "name": "enterprise-interaction-m02",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "vite"
  },
  "devDependencies": {
    "typescript": "^5.3.3",
    "vite": "^5.1.4"
  }
}
```

#### File: `hands-on/m02/index.html`
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
  <title>Production Interaction Demo</title>
  <link rel="stylesheet" href="./src/styles/main.css">
</head>
<body class="bg-slate-950 text-white min-h-screen flex items-center justify-center p-4">
  <main class="w-full max-w-sm flex flex-col gap-4">
    <div id="interactive-target" class="swipe-card" role="button" tabindex="0">
      <div class="swipe-content">
        <span>Geser ke Kanan untuk Verifikasi</span>
      </div>
      <div class="swipe-tracker"></div>
    </div>
    <div id="status-log" class="text-xs font-mono text-slate-400 text-center" aria-live="polite">
      Status: IDLE
    </div>
  </main>
  <script type="module" src="./src/main.ts"></script>
</body>
</html>
```

#### File: `hands-on/m02/src/styles/main.css`
```css
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  background-color: #020617;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  overflow: hidden;
}

.swipe-card {
  position: relative;
  width: 100%;
  height: 64px;
  background-color: #1e293b;
  border-radius: 9999px;
  overflow: hidden;
  touch-action: none; /* Ambil alih total kendali pointer dari OS */
  user-select: none;
  border: 1px solid #334155;
  display: flex;
  align-items: center;
  padding: 4px;
}

.swipe-content {
  position: absolute;
  width: 100%;
  text-align: center;
  font-size: 0.875rem;
  font-weight: 500;
  color: #94a3b8;
  pointer-events: none;
  z-index: 1;
}

.swipe-tracker {
  position: relative;
  width: 56px;
  height: 56px;
  background-color: #3b82f6;
  border-radius: 50%;
  z-index: 2;
  will-change: transform;
  transform: translate3d(var(--slider-x, 0px), 0, 0);
  cursor: grab;
}

.swipe-tracker:active {
  cursor: grabbing;
}
```

#### File: `hands-on/m02/src/fsm/buttonFsm.ts`
```typescript
export type State = 'IDLE' | 'TRACKING' | 'SETTLING' | 'RESOLVED';
export type Event = 
  | { type: 'POINTER_DOWN'; pointerId: number; clientX: number }
  | { type: 'POINTER_MOVE'; clientX: number }
  | { type: 'POINTER_UP' }
  | { type: 'RESET' };

export interface FSMContext {
  startX: number;
  currentX: number;
  maxDistance: number;
  pointerId: number | null;
}

export class InteractionFSM {
  private currentState: State = 'IDLE';
  private ctx: FSMContext;
  private subscribers: Array<(state: State, ctx: FSMContext) => void> = [];

  constructor(maxDistance: number) {
    this.ctx = {
      startX: 0,
      currentX: 0,
      maxDistance,
      pointerId: null
    };
  }

  public subscribe(cb: (state: State, ctx: FSMContext) => void) {
    this.subscribers.push(cb);
    cb(this.currentState, this.ctx);
  }

  private notify() {
    this.subscribers.forEach((cb) => cb(this.currentState, this.ctx));
  }

  public send(event: Event): void {
    const prevState = this.currentState;

    switch (this.currentState) {
      case 'IDLE':
        if (event.type === 'POINTER_DOWN') {
          this.ctx.startX = event.clientX;
          this.ctx.currentX = 0;
          this.ctx.pointerId = event.pointerId;
          this.currentState = 'TRACKING';
        }
        break;

      case 'TRACKING':
        if (event.type === 'POINTER_MOVE') {
          const delta = event.clientX - this.ctx.startX;
          // Clamp nilai antara 0 dan maxDistance
          this.ctx.currentX = Math.max(0, Math.min(delta, this.ctx.maxDistance));
        } else if (event.type === 'POINTER_UP') {
          if (this.ctx.currentX >= this.ctx.maxDistance * 0.9) {
            this.currentState = 'RESOLVED';
          } else {
            this.currentState = 'SETTLING';
          }
        }
        break;

      case 'SETTLING':
        if (event.type === 'RESET') {
          this.ctx.currentX = 0;
          this.ctx.pointerId = null;
          this.currentState = 'IDLE';
        }
        break;

      case 'RESOLVED':
        if (event.type === 'RESET') {
          this.ctx.currentX = 0;
          this.ctx.pointerId = null;
          this.currentState = 'IDLE';
        }
        break;
    }

    if (prevState !== this.currentState || this.currentState === 'TRACKING') {
      this.notify();
    }
  }

  public getState(): State {
    return this.currentState;
  }
}
```

#### File: `hands-on/m02/src/main.ts`
```typescript
import { InteractionFSM } from './fsm/buttonFsm';

const container = document.getElementById('interactive-target') as HTMLElement;
const tracker = container.querySelector('.swipe-tracker') as HTMLElement;
const statusLog = document.getElementById('status-log') as HTMLElement;

const MAX_DRAG = container.clientWidth - tracker.clientWidth - 8;
const fsm = new InteractionFSM(MAX_DRAG);

fsm.subscribe((state, ctx) => {
  statusLog.textContent = `Status: ${state} (Offset: ${Math.round(ctx.currentX)}px)`;

  if (state === 'TRACKING') {
    tracker.style.setProperty('--slider-x', `${ctx.currentX}px`);
  } else if (state === 'SETTLING') {
    // Jalankan Physics Spring Snapback via WAAPI
    const currentOffset = ctx.currentX;
    const anim = tracker.animate([
      { transform: `translate3d(${currentOffset}px, 0, 0)` },
      { transform: 'translate3d(0px, 0, 0)' }
    ], {
      duration: 300,
      easing: 'cubic-bezier(0.2, 0.9, 0.3, 1)'
    });

    anim.onfinish = () => {
      tracker.style.setProperty('--slider-x', '0px');
      fsm.send({ type: 'RESET' });
    };
  } else if (state === 'RESOLVED') {
    tracker.style.setProperty('--slider-x', `${MAX_DRAG}px`);
    statusLog.textContent = 'Status: SUCCESSFUL COMMIT';
    container.style.borderColor = '#22c55e';
    setTimeout(() => {
      container.style.borderColor = '#334155';
      fsm.send({ type: 'RESET' });
    }, 1500);
  } else if (state === 'IDLE') {
    tracker.style.setProperty('--slider-x', '0px');
  }
});

tracker.addEventListener('pointerdown', (e) => {
  if (fsm.getState() !== 'IDLE') return;
  tracker.setPointerCapture(e.pointerId);
  fsm.send({ type: 'POINTER_DOWN', pointerId: e.pointerId, clientX: e.clientX });
});

tracker.addEventListener('pointermove', (e) => {
  if (fsm.getState() !== 'TRACKING') return;
  fsm.send({ type: 'POINTER_MOVE', clientX: e.clientX });
});

const handlePointerEnd = (e: PointerEvent) => {
  if (fsm.getState() !== 'TRACKING') return;
  try {
    tracker.releasePointerCapture(e.pointerId);
  } catch {
    // Pointer sudah dilepas oleh sistem
  }
  fsm.send({ type: 'POINTER_UP' });
};

tracker.addEventListener('pointerup', handlePointerEnd);
tracker.addEventListener('pointercancel', handlePointerEnd);

// Keyboard Accessibility Trigger
container.addEventListener('keydown', (e) => {
  if (e.key === 'ArrowRight' && fsm.getState() === 'IDLE') {
    fsm.send({ type: 'POINTER_DOWN', pointerId: 0, clientX: 0 });
    fsm.send({ type: 'POINTER_MOVE', clientX: MAX_DRAG });
    fsm.send({ type: 'POINTER_UP' });
  }
});
```

---

### 13. Exercise

#### Level Easy
Ubah berkas `hands-on/m02/src/fsm/buttonFsm.ts` untuk menambahkan batasan ambang batas (*dead-zone threshold*):
* **Spesifikasi**: Tracker tidak boleh bergeser sebelum perubahan pergerakan pointer melebihi `5px` dari titik `startX`.
* **Kriteria Evaluasi**: Nilai `ctx.currentX` tetap `0` jika user hanya melakukan jitter atau pergerakan halus di bawah `5px`.

#### Level Medium
Tambahkan mekanisme *Dynamic Resistance* pada logic `TRACKING`:
* **Spesifikasi**: Jika pengguna menggeser melebihi 70% perjalanan, kurangi sensitivitas pergerakan menjadi $0.3\times$ (efek tarikan elastis/karet).
* **Kriteria Evaluasi**: Pergerakan pointer 10px fisik di layar hanya menambah pergeseran tracker sebesar 3px pada rentang `[0.7 * MAX_DRAG, MAX_DRAG]`.

#### Level Hard
Rancang dan integrasikan mekanika **Bidirectional Gestures with Cancellation Boundary**:
* **Spesifikasi**: Jika pengguna menyeret tracker vertikal ke atas/bawah melebihi rentang `±40px` saat gestur berlangsung, batalkan interaksi secara deterministik:
  1. Transisikan FSM ke status pembatalan darurat `ABORTED`.
  2. Mainkan animasi snap-back instan dengan warna border merah selama 300ms.
  3. Lepaskan pointer capture secara aman tanpa melempar runtime exception.
* **Kriteria Evaluasi**: Tidak ada kondisi unhandled pointer tracking, memori event listeners terbebas dari kebocoran, dan status kembali ke `IDLE`.

---

### 14. Challenge

**Skenario**: Anda adalah Principal UI/UX Architect di aplikasi perbankan tier-1. Anda diminta merancang interaksi **Multi-Currency Drag & Drop Swapper**:
1. User dapat men-drag "Kartu Dompet A" dan men-drop ke "Kartu Dompet B" untuk memicu transfer konversi mata uang.
2. Selama pergerakan, kartu yang di-drag harus menampilkan preview floating state dengan physics-spring yang terikat langsung ke pointer koordinat GPU.
3. Seluruh viewport container harus tetap mengizinkan native momentum scrolling jika gesekan pointer dimulai dengan arah vertikal $>45^{\circ}$, namun jika pergerakan didominasi sudut horizontal, scroll container harus di-lock secara instan tanpa glitch visual.
4. Implementasikan protokol rollback: Jika rate valuta asing (FX Rate) berubah di backend selama drag berlangsung, drop target harus menolak kartu dengan animasi gempa (*shake error animation*), mengembalikan kartu ke slot semula via FLIP (*First, Last, Invert, Play*), dan screen reader membacakan peringatan perubahan kurs via dynamic `aria-live`.

**Instruksi Deliverable**:
* Susun Diagram State Machine spesifik (State, Event, Transition guards).
* Tuliskan kode integrasi inti TypeScript yang membedakan intent sudut kemiringan gesture (Directional Locking Math).
* Buktikan bahwa alur rendering Anda bebas dari *Layout Thrashing* dengan memanfaatkan Web Animations API (WAAPI) secara eksklusif.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Pertanyaan)
1. **Mengapa manipulasi properti CSS `transform` lebih disukai dibandingkan `top` atau `margin-left` saat merender interaksi gesture drag?**
   * *Jawaban*: `transform` diproses langsung oleh GPU pada tahap Compositing tanpa memicu Recalculate Style, Layout (Reflow), dan Paint di Main Thread, sehingga terhindar dari dropped frames.

2. **Apa fungsi utama dari pemanggilan `element.setPointerCapture(pointerId)`?**
   * *Jawaban*: Untuk memastikan semua event pointer berikutnya tetap dialirkan ke elemen target tersebut, bahkan jika koordinat pointer keluar dari batas fisik bounding box elemen atau keluar dari viewport layar.

3. **Kapan status `touch-action: none` mutlak harus dideklarasikan pada elemen antarmuka?**
   * *Jawaban*: Saat elemen tersebut menangani interaksi pointer gesture kustom multi-arah secara mandiri dan browser dilarang mengambil alih untuk gesture bawaan OS seperti pinch-zoom atau native scrolling.

4. **Apa yang dimaksud dengan "Impossible State" dalam konteks arsitektur antarmuka pengguna?**
   * *Jawaban*: Kombinasi dua atau lebih state flags boolean yang menghasilkan anomali visual atau perilaku yang secara logika mustahil terjadi (contoh: status antarmuka bernilai `isSuccess: true` dan `isError: true` secara bersamaan).

5. **Apa peran dari metode `Animation.cancel()` pada Web Animations API (WAAPI) sebelum mengaplikasikan style baru?**
   * *Jawaban*: Untuk membatalkan status fill aktif dari animasi sebelumnya dan membersihkan alokasi composite layer animasi tersebut dari memori browser rendering engine.

#### Intermediate (5 Pertanyaan)
6. **Jelaskan perbedaan mendasar antara *Passive Event Listener* (`{ passive: true }`) dan implementasi gestur interaktif FSM!**
   * *Jawaban*: Passive event listener memberi sinyal ke browser bahwa callback tidak akan pernah memanggil `e.preventDefault()`, memungkinkan scrolling native berjalan instan. Gestur FSM yang membutuhkan interupsi aksi native browser justru TIDAK BOLEH passive karena harus mampu memanggil `preventDefault()` atau mengandalkan deklarasi eksplisit CSS `touch-action`.

7. **Bagaimana cara menghitung moving velocity pelepasan gestur (release flick velocity) secara stabil tanpa bias interval waktu?**
   * *Jawaban*: Dengan mencatat stempel waktu frekuensi tinggi (`performance.now()`) bersama koordinat pointer terakhir, kemudian membagi diferensial perpindahan ruang terhadap diferensial waktu ($\Delta x / \Delta t$) menggunakan bobot smoothing rolling window (moving average) untuk meredam noise jitter hardware.

8. **Mengapa teknik FLIP (*First, Last, Invert, Play*) krusial untuk animasi transisi layout yang mahal secara komputasi?**
   * *Jawaban*: FLIP mengubah animasi layout yang memakan biaya komputasi Reflow tinggi menjadi operasi translasi dan penskalaan transformasi yang murah di GPU. Perhitungan layout hanya terjadi dua kali (First dan Last state), sementara fase transisi sesungguhnya (Invert dan Play) dieksekusi via `transform`.

9. **Bagaimana arsitektur Optimistic UI menangani latensi jaringan yang sangat cepat (< 50ms) agar antarmuka tidak terlihat mengalami *micro-stutter / visual flashing*?**
   * *Jawaban*: Menggunakan *Artificial Latency Threshold* atau menunda render skeleton/spinner minimal selama 150-200ms. Jika respon jaringan kembali di bawah batas tersebut, UI langsung beralih ke state final tanpa merender intermediate loading visual.

10. **Jelaskan risiko aksesibilitas yang muncul saat aksi interaksi berbasis swipe tidak dilengkapi padanan kontrol native!**
    * *Jawaban*: Pengguna motorik terbatas, pengguna switch device, serta tunanetra yang mengandalkan screen reader tidak dapat mengeksekusi gesture sapuan fisik tersebut. Sistem wajib menyediakan aksi ekuivalen via focused button click, keyboard keys, atau dropdown menu.

#### Kasus Produksi (3 Skenario)

11. **Skenario Kasus 1: Micro-interaction Frame Drop pada High-end Device**
    * *Masalah*: Sebuah aplikasi trading crypto mengimplementasikan bottom sheet gesture. Pada Google Pixel 8 Pro (120Hz), bottom sheet sering *stutter* ketika ditarik ke atas, padahal CPU usage hanya 12%. Profiling di Chrome DevTools menunjukkan Garbage Collection (GC) terpanggil setiap 80ms.
    * *Pertanyaan*: Apa akar arsitektural dari tingginya GC pause tersebut dan bagaimana solusinya?
    * *Jawaban*: Callback event listener `pointermove` mengalokasikan objek baru di memori pada setiap firing (misal: objek state baru, perhitungan inline array, atau callback closure). Pada display 120Hz, pointermove dapat dipanggil 120 kali per detik. Solusinya: Alokasikan state kinematic secara mutabel di dalam pre-allocated memory context (`useRef` atau WeakMap singleton instance), hindari instansiasi objek baru di dalam event loop, dan update style langsung melalui CSS Custom Properties.

12. **Skenario Kasus 2: Race Condition pada Optimistic List Reordering**
    * *Masalah*: User melakukan drag-and-drop untuk mengurutkan daftar putar (playlist). Ketika item di-drop, UI langsung mengupdate urutan secara optimis. Namun, jika user memindahkan item A, lalu secara kilat memindahkan item B sebelum mutasi API item A selesai, urutan playlist sering rusak (*out of order*) setelah API network response selesai.
    * *Pertanyaan*: Bagaimana merancang state machine dan sync reconciler untuk mengatasi skenario ini?
    * *Jawaban*: Terapkan pola **Transaction Queue with Optimistic Aggregation**:
      1. Mutasi lokal diizinkan terus berjalan secara optimis, namun setiap mutasi menghasilkan sequence ID dan differential action (delta patch).
      2. Panggilan API tidak boleh ditembakkan secara raw/paralel; ia harus melewati *Mutation Serializer Queue* atau dibatalkan via `AbortController` lalu dikirim sebagai single batch state payload akhir (Debounced Snapshot Sync).
      3. Jika salah satu mutation gagal di server, seluruh queue dihentikan (*circuit breaker*), dan reconciler mengembalikan local memory state ke *Last Known Server State* terverifikasi.

13. **Skenario Kasus 3: Gestural Conflicts pada Nested Scrollable Contexts**
    * *Masalah*: Sebuah modal dialog menampilkan tabel data yang memiliki horizontal scrollbar mandiri. Pengguna mengeluh ketika mereka mencoba men-scroll tabel secara horizontal dari perangkat mobile, modal dialog seringkali malah tertutup secara tidak sengaja (karena modal memiliki gesture swipe-down-to-dismiss).
    * *Pertanyaan*: Bagaimana mengisolasi algoritma pengenalan gesture antar parent container dan nested child container secara deterministik?
    * *Jawaban*: 
      1. Gunakan directional intent vector calculation pada event capture phase. Hitung rasio sudut pergerakan: $\theta = \arctan2(|\Delta y|, |\Delta x|) \times (180/\pi)$.
      2. Jika pergerakan awal dominan horizontal ($\theta < 45^\circ$), child container segera memanggil `e.stopPropagation()` dan menerapkan `touch-action: pan-x`, mencegah event merembes ke parent gesture listener.
      3. Modal swipe-down gesture listener di level parent harus memverifikasi bahwa `event.target` tidak berada di dalam scrollable context yang memiliki `scrollLeft > 0` atau `scrollWidth > clientWidth`.

---

### 16. Summary

* **Interaction Architecture** modern bergeser dari penanganan event deklaratif murni menuju arsitektur hybrid: eksekusi kinematik deterministik pada GPU Layer (Compositor Thread) yang dipadukan dengan Finite State Machines (FSM) di Main Thread untuk tata kelola state.
* Menghilangkan **Impossible States** adalah syarat fundamental stabilitas antarmuka enterprise; FSM menjamin bahwa sistem hanya merespons input yang valid sesuai konteks transisinya.
* **Optimistic UI** bukan sekadar manipulasi visual tanpa spinner, melainkan sebuah arsitektur transaksi yang membutuhkan snapshot rollback capsule, penanganan error transaksional, dan integrasi feedback perceptual kompensatif.
* Kesuksesan mekanika perilaku antarmuka diukur dari kepatuhan terhadap **Frame Budget** (8.33ms pada 120 FPS / 16.67ms pada 60 FPS), eliminasi Forced Synchronous Layouts (Layout Thrashing), serta ketersediaan parity aksesibilitas via keyboard dan pembaca layar (WAI-ARIA).