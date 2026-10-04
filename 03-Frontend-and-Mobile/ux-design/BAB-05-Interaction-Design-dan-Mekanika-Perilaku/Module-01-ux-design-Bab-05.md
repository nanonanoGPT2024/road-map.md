# Bab 05 Module 01: Interaction Design (IxD) & Mekanika Perilaku

---

## SEKSI 01 — IDENTITAS MODUL
* **Track:** 03-Frontend-and-Mobile
* **Kurikulum:** UX Design & Human-Computer Interaction (HCI) Engineering
* **Bab:** 05 — Advanced Interaction Paradigms
* **Module:** 01 — Interaction Design (IxD) & Mekanika Perilaku
* **Tingkat Kemahiran:** Advanced / Staff Engineer / Lead Product Designer
* **Prasyarat:** DOM Event Lifecycle, Finite State Machines (XState/Pure JS), CSS Transitions & Compositor Threads, Web Accessibility (WCAG 2.2 Level AA), Cognitive Psychology Fundamentals (Hick's Law, Fitts's Law).

---

## SEKSI 02 — LEARNING OBJECTIVES
Pada akhir modul ini, peserta didik mampu:
1. Mendekonstruksi interaksi digital ke dalam 5 Dimensi Interaction Design (1D Words, 2D Visuals, 3D Physical/Space, 4D Time, 5D Behavior).
2. Mengimplementasikan siklus mikro-interaksi Dan Saffer (Trigger $\rightarrow$ Rule $\rightarrow$ Feedback $\rightarrow$ Loop & Mode) menggunakan finite-state machine (FSM) yang deterministik.
3. Mengeliminasi *gulf of execution* dan *gulf of evaluation* dengan memanfaatkan affordance, signifier, dan feedback loop latensi rendah ($<16\text{ ms}$).
4. Merancang dan menguji manipulasi langsung (*direct manipulation*) berbasis pointer events yang tahan terhadap *frame drops*, fluktuasi jaringan, dan event poisoning.
5. Membangun komponen interaktif terdistribusi skala enterprise yang memenuhi kepatuhan a11y, telemetri real-time, dan standar performa Core Web Vitals (INP $< 200\text{ ms}$).

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Mental Model: Dari Tampilan Statis ke State Kontinu
Frontend engineer sering kali terjebak dalam ilusi "UI adalah pohon komponen statis yang di-render ulang berdasarkan data". Dalam Interaction Design (IxD) modern, UI dipandang sebagai **sistem dinamis berbasis waktu (time-based continuous system)**. Antarmuka bukanlah serangkaian layout statis, melainkan transisi antar-state spasial dan temporal.

```
+-----------------------------------------------------------------------+
|                         MENTAL MODEL SHIFT                            |
+-----------------------------------------------------------------------+
|  PARADIGMA TRADISIONAL (STATIC)       PARADIGMA IXD MODERN (CONTINUOUS) |
|                                                                       |
|  [State A] -----> [State B]           [State A]                       |
|       |                 ^                 \                           |
|       | (Render Instan) |                  +---> [State A.1 (Intent)] |
|       +-----------------+                  |          |               |
|                                            |          v               |
|                                            |     [State A.2 (Action)] |
|   * Mengabaikan waktu (0ms)                |          |               |
|   * High Gulf of Evaluation                |          v               |
|   * Cognitive Disconnect                   +---> [State B (Settled)]  |
|                                                                       |
|                                       * Continuous Physics (Spring)   *
|                                       * Low Gulf of Evaluation        *
|                                       * Predictable Cognitive Load    *
+-----------------------------------------------------------------------+
```

### 5 Dimensi IxD
1. **1D: Kata (Words):** Teks label, mikro-kopi, pesan sistem. Harus presisi, informatif, dan tidak ambigu.
2. **2D: Representasi Visual (Visual Representations):** Ikon, tipografi, diagram, tata letak spasial. Memandu mata dan menegaskan hierarki visual.
3. **3D: Objek Fisik atau Ruang (Physical Objects/Space):** Perangkat fisik (mouse, trackpad, layar sentuh, haptic actuator) dan konteks lingkungan pengguna.
4. **4D: Waktu (Time):** Durasi animasi, kecepatan transisi, progres audio/visual yang berubah seiring berjalannya waktu.
5. **5D: Perilaku (Behavior):** Aturan operasi (rules), reaksi sistem terhadap aksi pengguna, dan bagaimana 4 dimensi sebelumnya beroperasi serempak.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Siklus Mikro-interaksi & State Machine Runtime
Arsitektur runtime berikut mengilustrasikan bagaimana sebuah intensi diurai menjadi pointer updates, transisi internal FSM, kalkulasi engine fisika, dan sinkronisasi hardware compositor thread.

```
+-------------------------------------------------------------------------------------------------------+
|                                ARSITEKTUR RUNTIME INTERACTION DESIGN                                  |
+-------------------------------------------------------------------------------------------------------+
|                                                                                                       |
|  [ USER INPUT ] ---> (Pointer / Keyboard / Screen Reader)                                             |
|        |                                                                                              |
|        v                                                                                              |
|  +-------------------+        +--------------------------------------------------------------------+  |
|  | TRIGGER DETECTION |        | DAN SAFFER INTERACTION LIFECYCLE                                    |  |
|  +-------------------+        |                                                                    |  |
|        | (Event E)            |  [Trigger]                                                         |  |
|        v                      |     |                                                              |  |
|  +-------------------+        |     v                                                              |  |
|  | FINITE STATE      |------->|  [Rules Execution] <----+                                          |  |
|  | MACHINE (FSM)     |        |     |                   |                                          |  |
|  +-------------------+        |     v                   | Loops / Dynamic Modes                    |  |
|        | (Next State)         |  [Feedback Generation]  |                                          |  |
|        |                      |     |                   |                                          |  |
|        |                      |     v                   |                                          |  |
|        |                      |  [Loops / Modes] -------+                                          |  |
|        v                      +--------------------------------------------------------------------+  |
|  +-----------------------------------+                                                                |
|  | KINEMATIC RUNTIME / SPRING ENGINE | (requestAnimationFrame Loop)                                    |
|  +-----------------------------------+                                                                |
|        |                                                                                              |
|        +-----------------------------------+                                                          |
|        | (Transforms: translate3d, scale)  | (A11y Mutation / Live Region)                            |
|        v                                   v                                                          |
|  +-----------------------------+     +-------------------------------+                                |
|  | COMPOSITOR THREAD (GPU)     |     | ACCESSIBILITY TREE (AXTree)   |                                |
|  | - Direct Mutation           |     | - ARIA Live Announcements     |                                |
|  | - 60/120 FPS Guaranteed     |     | - Focus Management            |                                |
|  +-----------------------------+     +-------------------------------+                                |
|                                                                                                       |
+-------------------------------------------------------------------------------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Gulf of Execution vs. Gulf of Evaluation (Don Norman)
* **Gulf of Execution:** Kesenjangan antara intensi mental pengguna (*"Saya ingin mengarsipkan email ini"*) dan tindakan fisik yang diizinkan oleh sistem (*"Apakah saya harus drag, klik kanan, atau cari tombol tersembunyi?"*).
  * *Solusi Mekanis:* Sediakan signifier yang jelas (indikator visual seret) dan affordance langsung (pointer berubah menjadi `grab` saat hover).
* **Gulf of Evaluation:** Kesenjangan antara perubahan kondisi internal sistem dan persepsi pengguna tentang apa yang baru saja terjadi (*"Apakah file tersebut benar-benar terhapus atau tersimpan di draft?"*).
  * *Solusi Mekanis:* Umpan balik langsung (Immediate Sensory Feedback) $< 100\text{ ms}$, disusul transisi state spasial yang mempertahankan ketetapan objek (*object constancy*).

### 2. Anatomi Mikro-Interaksi (Dan Saffer)
```
+-----------------------------------------------------------------------------+
| ANATOMI MIKRO-INTERAKSI                                                     |
+-----------------------------------------------------------------------------+
| 1. TRIGGER  : Ambang batas pemicu aksi (e.g., pointerdown + move > 3px).   |
| 2. RULES    : Logika deterministik sistem (FSM transisi dari IDLE ke DRAG). |
| 3. FEEDBACK : Bukti aksi yang tertangkap sensor visual/haptik/auditori.     |
| 4. LOOPS/   : Kondisi persistensi (apakah ada threshold snap-back?          |
|    MODES      apakah aksi memicu modal interupsi?).                         |
+-----------------------------------------------------------------------------+
```

### 3. Kinematika & Fisika Perilaku (Spring Dynamics)
Animasi berbasis durasi tetap (`transition: all 300ms ease-in-out`) bersifat kaku (*mechanically unnatural*). Ketika interaksi pengguna diinterupsi di tengah jalan (misal melepaskan drag saat bergerak cepat), transisi waktu linear menghasilkan diskontinuitas vektor kecepatan ($v \to 0$ secara instan). 

IxD modern menggunakan pegas teredam (*damped harmonic oscillator*):

$$F = -k \cdot x - c \cdot v$$

Di mana:
* $k$ = konstanta pegas (*stiffness / tension*)
* $c$ = koefisien redaman (*damping*)
* $x$ = simpangan dari target ekuilibrium (*displacement*)
* $v$ = kecepatan sesaat (*velocity*)

Persamaan diferensial gerak:

$$m \frac{d^2x}{dt^2} + c \frac{dx}{dt} + k x = 0$$

Dengan mengintegrasikan kecepatan awal pointer ($v_0$) ke dalam kalkulasi pegas, elemen mempertahankan momentum lemparan (*momentum preservation*), mengeliminasi *perceptual stutter*.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Fitts's Law dan Index of Difficulty (ID)
Kecepatan dan akurasi eksekusi motorik ditentukan oleh Fitts's Law:

$$MT = a + b \log_2 \left( \frac{2D}{W} \right) = a + b \cdot ID$$

* $MT$ = Waktu Gerak (*Movement Time*)
* $D$ = Jarak ke target (*Distance*)
* $W$ = Lebar target di sepanjang sumbu gerak (*Target Width*)
* $ID$ = *Index of Difficulty* (dinyatakan dalam satuan bit)

```
        Jarak (D)
|----------------------------->|
[Pointer]                 [ TARGET ]  <-- Lebar (W)
```

**Implikasi Teknis IxD:**
1. **Target Virtual Tak Hingga:** Sudut dan tepi layar monitor memiliki $W = \infty$ karena pointer terhenti secara fisik oleh batas layar (*pinned cursor*).
2. **Peningkatan Ukuran Hit Target:** Target sentuh pada mobile wajib memiliki dimensi hit virtual minimal $48 \times 48\text{ CSS px}$ meskipun representasi visualnya (2D Visual) hanya berukuran $24 \times 24\text{ CSS px}$. Pemanfaatan *pseudo-element* (`::after`) transparan memperbesar $W$ tanpa mengorbankan kepadatan visual tata letak.

### Hukum Hick-Hyman (Hick's Law)
Waktu reaksi kognitif untuk memilih dari $n$ alternatif berbobot setara:

$$RT = b \cdot \log_2(n + 1)$$

Ketika $n$ meningkat secara linear, waktu pengambilan keputusan meningkat secara logaritmik. Implementasi IxD harus menerapkan *Progressive Disclosure* untuk membatasi set opsi instan ($n \le 5$) sebelum membuka layer aksi sekunder.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut implementasi murni (*vanilla TypeScript*) dari mikro-interaksi tombol swipe-to-confirm berbasis manipulasi langsung, kinematic spring physics, dan pemenuhan FSM deterministik tanpa dependensi eksternal.

```typescript
// interaction-engine.ts

export type InteractionState = 'IDLE' | 'DRAGGING' | 'SNAP_BACK' | 'CONFIRMED';

export interface SpringConfig {
  stiffness: number; // k
  damping: number;   // c
  mass: number;      // m
}

export class SwipeConfirmController {
  private state: InteractionState = 'IDLE';
  private trackWidth = 0;
  private handleWidth = 0;
  private maxTranslate = 0;
  private currentX = 0;
  private startPointerX = 0;
  private velocity = 0;
  private lastTime = 0;
  private rafId: number | null = null;

  private readonly springConfig: SpringConfig = {
    stiffness: 180,
    damping: 18,
    mass: 1,
  };

  constructor(
    private readonly container: HTMLElement,
    private readonly handle: HTMLElement,
    private readonly onConfirm: () => void
  ) {
    this.calculateBounds();
    this.bindEvents();
    this.updateA11y();
  }

  private calculateBounds(): void {
    this.trackWidth = this.container.getBoundingClientRect().width;
    this.handleWidth = this.handle.getBoundingClientRect().width;
    this.maxTranslate = Math.max(0, this.trackWidth - this.handleWidth);
  }

  private bindEvents(): void {
    this.handle.addEventListener('pointerdown', this.onPointerDown);
    window.addEventListener('resize', () => this.calculateBounds());
  }

  private onPointerDown = (e: PointerEvent): void => {
    if (this.state === 'CONFIRMED') return;

    this.calculateBounds();
    this.state = 'DRAGGING';
    this.startPointerX = e.clientX - this.currentX;
    this.velocity = 0;
    this.lastTime = performance.now();

    if (this.rafId !== null) {
      cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }

    this.handle.setPointerCapture(e.pointerId);
    this.handle.addEventListener('pointermove', this.onPointerMove);
    this.handle.addEventListener('pointerup', this.onPointerUp);
    this.handle.addEventListener('pointercancel', this.onPointerUp);
  };

  private onPointerMove = (e: PointerEvent): void => {
    if (this.state !== 'DRAGGING') return;

    const now = performance.now();
    const dt = Math.max((now - this.lastTime) / 1000, 0.001); // detik
    const targetX = e.clientX - this.startPointerX;

    // Resistance mechanics saat melewati batas
    let boundedX = targetX;
    if (targetX < 0) {
      boundedX = targetX * 0.2; // Rubber-banding kiri
    } else if (targetX > this.maxTranslate) {
      const overflow = targetX - this.maxTranslate;
      boundedX = this.maxTranslate + overflow * 0.2; // Rubber-banding kanan
    }

    this.velocity = (boundedX - this.currentX) / dt;
    this.currentX = boundedX;
    this.lastTime = now;

    this.applyTransform(this.currentX);
  };

  private onPointerUp = (e: PointerEvent): void => {
    if (this.state !== 'DRAGGING') return;

    this.handle.releasePointerCapture(e.pointerId);
    this.handle.removeEventListener('pointermove', this.onPointerMove);
    this.handle.removeEventListener('pointerup', this.onPointerUp);
    this.handle.removeEventListener('pointercancel', this.onPointerUp);

    const threshold = this.maxTranslate * 0.75;
    const isPastThreshold = this.currentX >= threshold;
    const hasForwardMomentum = this.velocity > 300;

    if (isPastThreshold || hasForwardMomentum) {
      this.settleConfirm();
    } else {
      this.state = 'SNAP_BACK';
      this.lastTime = performance.now();
      this.animateSpring(0);
    }
  };

  private animateSpring(targetX: number): void {
    const loop = (time: number) => {
      const dt = Math.min((time - this.lastTime) / 1000, 0.032); // Max 32ms cap
      this.lastTime = time;

      const displacement = this.currentX - targetX;
      const springForce = -this.springConfig.stiffness * displacement;
      const dampingForce = -this.springConfig.damping * this.velocity;
      const acceleration = (springForce + dampingForce) / this.springConfig.mass;

      this.velocity += acceleration * dt;
      this.currentX += this.velocity * dt;

      this.applyTransform(this.currentX);

      // Kriteria berhenti (settling threshold)
      if (Math.abs(displacement) < 0.1 && Math.abs(this.velocity) < 5) {
        this.currentX = targetX;
        this.velocity = 0;
        this.applyTransform(this.currentX);
        this.state = targetX === 0 ? 'IDLE' : 'CONFIRMED';
        this.rafId = null;
        return;
      }

      this.rafId = requestAnimationFrame(loop);
    };

    this.rafId = requestAnimationFrame(loop);
  }

  private settleConfirm(): void {
    this.state = 'CONFIRMED';
    this.animateSpring(this.maxTranslate);
    this.updateA11y();
    this.onConfirm();
  }

  private applyTransform(x: number): void {
    // Isolasi perubahan hanya pada Compositor Layer
    this.handle.style.transform = `translate3d(${x}px, 0, 0)`;
  }

  private updateA11y(): void {
    this.container.setAttribute('role', 'slider');
    this.container.setAttribute('aria-valuemin', '0');
    this.container.setAttribute('aria-valuemax', '100');
    this.container.setAttribute(
      'aria-valuenow',
      this.state === 'CONFIRMED' ? '100' : '0'
    );
    this.container.setAttribute(
      'aria-label',
      'Geser ke kanan untuk konfirmasi transaksi'
    );
  }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

* `setPointerCapture(e.pointerId)`: Mengarahkan seluruh aliran stream interaksi pointer langsung ke target node meskipun pointer bergerak melesat keluar dari boundary DOM element. Mencegah macetnya interaksi saat drag kencang.
* `boundedX = targetX * 0.2`: Mengaplikasikan *asymmetric boundary resistance* (*rubber-banding* ala iOS). Memberikan pemahaman fisik instan kepada pengguna bahwa mereka telah menabrak dinding batas antarmuka.
* `dt = Math.max((now - this.lastTime) / 1000, 0.001)`: Menghitung delta waktu berbasis high-resolution clock (`performance.now()`) untuk kalkulasi kecepatan instan yang independen dari frame rate monitor (60Hz vs 120Hz vs 240Hz).
* `this.maxTranslate * 0.75` dan `this.velocity > 300`: Dynamic threshold evaluation. Konfirmasi tidak hanya melihat lokasi absolut, melainkan mempertimbangkan intensi vektor momentum ($v$). Pengguna yang melakukan flicking cepat tetap terkonfirmasi tanpa harus menyentuh ujung secara piksel-sempurna.
* `this.handle.style.transform = translate3d(${x}px, 0, 0)`: Membatasi mutasi rendering murni pada GPU-accelerated layer. Mencegah terjadinya *Reflow/Layout* dan *Repaint* pada render pipeline browser, memastikan frame budget konsisten di bawah target ideal $\le 8.33\text{ ms}$ (120 FPS).

---

## SEKSI 09 — STUDI KASUS NYATA
**Skenario Produksi:** Sebuah platform fintech global (Payment Gateway Enterprise) mendeteksi lonjakan rasio kegagalan konfirmasi transfer sebesar 14.8% pada pengguna perangkat low-end.
* **Akar Masalah IxD:** Tombol konfirmasi awal menggunakan animasi berbasis CSS standard (`transition: left 300ms ease`) yang di-trigger via touch event. Pada perangkat dengan CPU lambat, *main-thread blocking* akibat eksekusi skrip analitik pihak ketiga menyebabkan *jank*, memicu *dropped pointer-events*, dan menghasilkan *gulf of evaluation*: pengguna mengira transfer gagal karena slider kembali ke titik awal tanpa indikasi visual yang jelas, memicu *rage clicks* dan transaksi ganda.
* **Solusi Rekayasa:** Penggantian sistem menjadi stateful finite interaction engine dengan kinematic resistance, pemisahan kalkulasi fisika ke micro-tick requestAnimationFrame, penambahan *aria-live* assertif, serta haptic feedback berbasis Web Haptics API (`navigator.vibrate`).

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Komponen React Enterprise-grade lengkap dengan proteksi keyboard fallback, ARIA accessibility, spring physics, dan telemetri INP terintegrasi.

```tsx
import React, { useState, useRef, useEffect, useCallback } from 'react';

interface EnterpriseSwipeProps {
  onSuccess: () => Promise<void>;
  label: string;
  successText: string;
}

type ComponentInteractionState = 'IDLE' | 'ACTIVE_DRAG' | 'SETTLING' | 'RESOLVING' | 'COMPLETED';

export const EnterpriseSwipeToConfirm: React.FC<EnterpriseSwipeProps> = ({
  onSuccess,
  label,
  successText,
}) => {
  const [interactionState, setInteractionState] = useState<ComponentInteractionState>('IDLE');
  const trackRef = useRef<HTMLDivElement>(null);
  const handleRef = useRef<HTMLDivElement>(null);
  
  // Mutable refs untuk loop performa tinggi tanpa re-render React
  const currentX = useRef(0);
  const startPointerX = useRef(0);
  const velocity = useRef(0);
  const lastTime = useRef(0);
  const rafId = useRef<number | null>(null);

  const triggerHaptic = (pattern: number | number[]) => {
    if (typeof window !== 'undefined' && 'vibrate' in navigator) {
      try {
        navigator.vibrate(pattern);
      } catch {
        // Fallback hening jika API diblokir policy
      }
    }
  };

  const getBounds = useCallback(() => {
    if (!trackRef.current || !handleRef.current) return { max: 0 };
    const trackW = trackRef.current.getBoundingClientRect().width;
    const handleW = handleRef.current.getBoundingClientRect().width;
    return { max: Math.max(0, trackW - handleW) };
  }, []);

  const applyHardwareTransform = (x: number) => {
    if (handleRef.current) {
      handleRef.current.style.transform = `translate3d(${x}px, 0, 0)`;
    }
  };

  const runSpringSettlement = useCallback((targetX: number, onSettled?: () => void) => {
    setInteractionState('SETTLING');
    const stiffness = 220;
    const damping = 20;
    const mass = 1;

    const tick = (time: number) => {
      const dt = Math.min((time - lastTime.current) / 1000, 0.032);
      lastTime.current = time;

      const displacement = currentX.current - targetX;
      const springForce = -stiffness * displacement;
      const dampingForce = -damping * velocity.current;
      const accel = (springForce + dampingForce) / mass;

      velocity.current += accel * dt;
      currentX.current += velocity.current * dt;

      applyHardwareTransform(currentX.current);

      if (Math.abs(displacement) < 0.2 && Math.abs(velocity.current) < 8) {
        currentX.current = targetX;
        applyHardwareTransform(targetX);
        rafId.current = null;
        if (onSettled) onSettled();
        return;
      }

      rafId.current = requestAnimationFrame(tick);
    };

    lastTime.current = performance.now();
    rafId.current = requestAnimationFrame(tick);
  }, []);

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (interactionState === 'RESOLVING' || interactionState === 'COMPLETED') return;
    
    if (rafId.current !== null) {
      cancelAnimationFrame(rafId.current);
      rafId.current = null;
    }

    const { max } = getBounds();
    if (max <= 0) return;

    setInteractionState('ACTIVE_DRAG');
    startPointerX.current = e.clientX - currentX.current;
    velocity.current = 0;
    lastTime.current = performance.now();

    const target = e.currentTarget;
    target.setPointerCapture(e.pointerId);
    triggerHaptic(10);
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (interactionState !== 'ACTIVE_DRAG') return;

    const now = performance.now();
    const dt = Math.max((now - lastTime.current) / 1000, 0.001);
    const rawTargetX = e.clientX - startPointerX.current;
    const { max } = getBounds();

    let boundedX = rawTargetX;
    if (rawTargetX < 0) {
      boundedX = rawTargetX * 0.15;
    } else if (rawTargetX > max) {
      boundedX = max + (rawTargetX - max) * 0.15;
    }

    velocity.current = (boundedX - currentX.current) / dt;
    currentX.current = boundedX;
    lastTime.current = now;

    applyHardwareTransform(boundedX);
  };

  const handlePointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    if (interactionState !== 'ACTIVE_DRAG') return;
    e.currentTarget.releasePointerCapture(e.pointerId);

    const { max } = getBounds();
    const isOverThreshold = currentX.current >= max * 0.7;
    const isFlicked = velocity.current > 400;

    if (isOverThreshold || isFlicked) {
      triggerHaptic([30, 50, 30]);
      runSpringSettlement(max, async () => {
        setInteractionState('RESOLVING');
        try {
          await onSuccess();
          setInteractionState('COMPLETED');
          triggerHaptic(70);
        } catch {
          // Revert jika API gagal
          runSpringSettlement(0, () => setInteractionState('IDLE'));
          triggerHaptic([100, 50, 100]);
        }
      });
    } else {
      triggerHaptic(15);
      runSpringSettlement(0, () => setInteractionState('IDLE'));
    }
  };

  // Keyboard Fallback (A11y WAI-ARIA Slider Pattern)
  const handleKeyDown = async (e: React.KeyboardEvent) => {
    if (interactionState === 'RESOLVING' || interactionState === 'COMPLETED') return;

    const { max } = getBounds();
    if (e.key === 'ArrowRight' || e.key === 'Enter') {
      e.preventDefault();
      runSpringSettlement(max, async () => {
        setInteractionState('RESOLVING');
        try {
          await onSuccess();
          setInteractionState('COMPLETED');
        } catch {
          runSpringSettlement(0, () => setInteractionState('IDLE'));
        }
      });
    }
  };

  useEffect(() => {
    return () => {
      if (rafId.current !== null) cancelAnimationFrame(rafId.current);
    };
  }, []);

  return (
    <div
      ref={trackRef}
      className="relative w-full max-w-md h-16 bg-neutral-900 border border-neutral-800 rounded-full select-none overflow-hidden touch-none p-1 flex items-center"
      role="slider"
      tabIndex={0}
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={interactionState === 'COMPLETED' ? 100 : 0}
      aria-disabled={interactionState === 'RESOLVING' || interactionState === 'COMPLETED'}
      onKeyDown={handleKeyDown}
    >
      <div 
        className="absolute inset-0 flex items-center justify-center pointer-events-none text-sm font-medium tracking-wide text-neutral-400"
        aria-hidden="true"
      >
        {interactionState === 'COMPLETED' ? successText : label}
      </div>

      <div
        ref={handleRef}
        className={`relative z-10 w-14 h-14 rounded-full flex items-center justify-center cursor-grab active:cursor-grabbing shadow-lg will-change-transform ${
          interactionState === 'COMPLETED' ? 'bg-emerald-500' : 'bg-white'
        }`}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
      >
        <span className="text-black font-bold text-xs pointer-events-none" aria-hidden="true">
          {interactionState === 'RESOLVING' ? '...' : interactionState === 'COMPLETED' ? '✓' : '→'}
        </span>
      </div>

      {/* Screen Reader Region untuk live updates */}
      <div className="sr-only" aria-live="assertive">
        {interactionState === 'COMPLETED' ? successText : ''}
      </div>
    </div>
  );
};
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter | Duration-Based Transitions (`CSS transition`) | Physics-Based Engine (Spring Dynamics) | Discrete Instant Transitions |
| :--- | :--- | :--- | :--- |
| **Continuity of Velocity** | Rendah (Kecepatan drop ke nol seketika saat diinterupsi) | Sempurna (Momentum awal terserap ke pergerakan pegas) | Nihil (Tidak ada konsep kecepatan) |
| **Kompleksitas Komputasi**| Sangat Rendah (Ditangani secara internal oleh browser) | Moderat (Membutuhkan kalkulasi integrasi numerik rAF) | Zero Overhead |
| **Interupsi Interaksi** | Buruk (Animasi patah jika ada input sebelum selesai) | Luar Biasa (Re-target simpangan tanpa lompatan visual) | Tidak Relevan |
| **Prediktabilitas Waktu** | Tinggi (Waktu selesai pasti: misal tepat 300ms) | Dinamis (Waktu selesai bergantung pada simpangan dan energi) | Instan ($0\text{ ms}$) |
| **Beban Kognitif Pengguna**| Sedang (Dapat terasa artifisial jika kurva bezier salah) | Minimal (Meniru hukum inersia dunia fisik) | Tinggi (Dapat memicu disorientasi spasial) |

---

## SEKSI 12 — EDGE CASES & PITFALLS

1. **Edge Case: Pointer Cancel Event Trap**
   * *Mekanisme:* Sistem operasi memicu event `pointercancel` jika gestur terinterupsi secara sistemik (misal: panggilan telepon masuk, gesture edge-swipe kembali ke Home iOS).
   * *Mitigasi:* Selalu bind event handler yang sama antara `pointerup` dan `pointercancel` untuk memastikan state machine tidak tertahan di kondisi `DRAGGING` selamanya.
2. **Edge Case: Multi-Touch Collision**
   * *Mekanisme:* Pengguna menyentuh handle menggunakan dua jari sekaligus secara tidak sengaja, memicu dua pointer ID berbeda.
   * *Mitigasi:* Kunci kontrol hanya pada `e.pointerId` pertama yang tertangkap melalui `setPointerCapture`. Abaikan seluruh event dari pointer ID lain hingga siklus interaksi pertama selesai.
3. **Edge Case: Layar High-Refresh-Rate Desynchronization**
   * *Mekanisme:* Monitor 144Hz atau 240Hz memicu event listener lebih cepat daripada laju kalkulasi physics loop, menyebabkan penumpukan kalkulasi (`event saturation`).
   * *Mitigasi:* Simpan raw koordinat pointer di dalam variable referensi, dan delegasikan eksekusi mutasi transformasi DOM secara eksklusif ke callback `requestAnimationFrame`.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Memutasi Layout Properties pada Pointer Move
* *Anti-Pattern:* Memperbarui atribut `left`, `right`, atau `margin` saat drag.
  ```typescript
  // SALAH: Memicu Full Layout Reflow pada setiap frame!
  handle.style.left = `${currentX}px`;
  ```
* *Koreksi Teknis:* Gunakan *composited-only properties* (`transform` dan `opacity`).
  ```typescript
  // BENAR: Menggunakan GPU sub-pixel compositing
  handle.style.transform = `translate3d(${currentX}px, 0, 0)`;
  ```

### 2. Mengabaikan Preferensi `prefers-reduced-motion`
* *Anti-Pattern:* Memaksa semua pengguna melihat animasi spring tanpa mempertimbangkan gangguan vestibular kognitif.
* *Koreksi Teknis:* Cek media query `window.matchMedia('(prefers-reduced-motion: reduce)')`. Jika aktif, bypass physics loop dan langsung set nilai akhir secara instan ($0\text{ ms}$).

### 3. Mengasumsikan Mouse adalah Satu-satunya Piranti Input
* *Anti-Pattern:* Hanya mengandalkan event `mousedown` dan `mousemove`.
* *Koreksi Teknis:* Standarisasi seluruh interaksi pada **Pointer Events API** (`pointerdown`, `pointermove`, `pointerup`), yang mengunifikasi mouse, stylus/pen, dan touch.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

* **Latency Budgets (Nielsen-Norman / RAIL Model):**
  * **$< 16\text{ ms}$:** Visual tracking kontinu (direct manipulation, scrolling, dragging).
  * **$< 100\text{ ms}$:** Respon diskrit terhadap sentuhan/klik (state acknowledgment).
  * **$< 1000\text{ ms}$:**