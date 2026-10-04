# Bab 07 Module 01: Advanced Interaction Design, Micro-interactions & Motion

---

## SEKSI 01 — IDENTITAS MODUL

* **Jalur Kurikulum:** Product Design Engineering
* **Kategori:** 03-Frontend-and-Mobile
* **Kode Modul:** PDE-03-07-01
* **Nama Modul:** Advanced Interaction Design, Micro-interactions & Motion
* **Tingkat Kompleksitas:** Advanced (Staff / Principal Level)
* **Prasyarat:** Pemahaman mendalam mengenai DOM Lifecycle, Event Loop, CSS Compositor Threads, Render Pipeline (Layout, Paint, Composite), React Core (Hooks, Reconciliation), TypeScript, serta dasar-dasar Graphic Math (vektor, matriks transformasi).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta ajar diharapkan mampu:

1. **Menganalisis & Mengisolasi Rendering Pipeline Web:** Mengidentifikasi secara deterministik kapan suatu animasi memicu relayout/reflow, repaint, atau hanya compositing murni, serta mengonfigurasi properti CSS dan layer GPU untuk menjamin eksekusi pada 60/120 FPS tanpa frame drop.
2. **Mengimplementasikan Physics-Based Spring Engine:** Membangun dan mengonfigurasi model matematis gerak berbasis pegas (Damped Harmonic Oscillator) untuk menggantikan model durasi-kurva kaku (*easing curves*), menghasilkan interaksi pengguna yang adaptif dan kinetik.
3. **Mendesain Finite State Micro-interactions:** Mengembangkan mikro-interaksi enterprise tingkat tinggi menggunakan Finite State Machine (FSM) yang mengikat triggers, rules, feedback, dan loops secara atomik.
4. **Menguasai Teknik Transisi Terbalik (FLIP):** Menghitung koordinat translasi dan skala secara manual (*First, Last, Invert, Play*) untuk mengorkestrasi transisi antarelemen kompleks tanpa penalti layout thrashing.
5. **Menerapkan Standar Aksesibilitas Kinetik (a11y):** Mengintegrasikan media queries `prefers-reduced-motion` secara programmatic ke dalam arsitektur animasi deklaratif dan imperatif.
6. **Membangun Telemetri Kinerja Interaksi:** Mengukur dan memantau degradasi frame rate (jank), cumulative layout shifts (CLS), dan interaction to next paint (INP) yang disebabkan oleh beban animasi menggunakan browser profiling API.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: "Dekorasi Grafis" Menuju "Kontinuitas Kognitif Spasial"

Motion dalam konteks rekayasa produk tingkat lanjut bukan elemen estetis pelengkap (*eye candy*). Motion adalah jembatan kognitif yang memandu model mental pengguna saat terjadi perubahan status sistem (*system state*).

```
Paradigma Konvensional (Salah):
[User Action] ---> [Instan / Layar Berkedip] ---> [State Berubah Tanpa Konteks]
                       ^ Mengakibatkan disorientasi kognitif

Paradigma Advanced Interaction (Benar):
[User Action] ---> [Micro-interaction Feedback] ---> [Spatial Choreography] ---> [State Terkonfirmasi]
                       ^ Mempertahankan fokus, membangun intuisi fisik
```

* **Physical Realism over Arbitrary Time:** Di dunia nyata, tidak ada objek bermassa yang bergerak secara linier instan atau berhenti mendadak tanpa perlambatan alami. Menggunakan *cubic-bezier* dengan durasi statis 300ms untuk semua skenario adalah kesalahan desain. Sistem yang matang menggunakan *physics-based simulation* (massa, kekakuan/stiffness, dan redaman/damping), di mana durasi gerak merupakan hasil kalkulasi energi kinetik dan jarak tempuh, bukan parameter input konstan.
* **The Frame Budget Imperative:** Layar modern berjalan pada 60Hz (16.67ms per frame) hingga 120Hz (8.33ms per frame). Setiap instruksi JavaScript pada *Main Thread* yang bersaing dengan proses animasi akan memicu *dropped frame* (jank). Mental model engineer frontend harus bergeser dari: "Bagaimana cara menganimasikan ini?" menjadi: "Bagaimana cara memindahkan komputasi dan rendering animasi ini langsung ke Compositor Thread / GPU dan membebaskan Main Thread?"

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Siklus Hidup Rendering Browser vs. Jalur Interaksi Kinetik

Diagram berikut menggambarkan jalur kritis saat input pengguna memicu animasi, membedakan jalur destruktif (*Layout/Paint pipeline*) dan jalur performan (*Direct Compositing pipeline*):

```
+---------------------------------------------------------------------------------------+
|                                    INPUT EVENT TRIGGER                                |
|                        (PointerDown, Drag, Gesture, State Mutation)                   |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
|                                      MAIN THREAD                                      |
|  +-----------------------+      +--------------------+      +----------------------+  |
|  |   JavaScript Event    | ---> | Recalculate Styles | ---> | Frame Budget Check   |  |
|  | Execution / State FSM |      |     (DOM Tree)     |      |  (16.67ms / 8.33ms)  |  |
|  +-----------------------+      +--------------------+      +----------------------+  |
|              |                                                                        |
|    [Jalur Buruk: Mutasi top/left/width/height]           [Jalur Ideal: Mutasi transform/opacity]
|              v                                                                 |      |
|  +-----------------------+                                                     |      |
|  |     LAYOUT (Reflow)   |                                                     |      |
|  | Menghitung geometri   |                                                     |      |
|  | seluruh hierarki tree |                                                     |      |
|  +-----------------------+                                                     |      |
|              |                                                                 |      |
|              v                                                                 |      |
|  +-----------------------+                                                     |      |
|  |         PAINT         |                                                     |      |
|  | Rasterisasi layer ke  |                                                     |      |
|  | bitmap (CPU Intensive)|                                                     |      |
|  +-----------------------+                                                     |      |
|              |                                                                 |      |
|              +-----------------------------------+                             |      |
|                                                  |                             |      |
+--------------------------------------------------|-----------------------------|------+
                                                   v                             v
+---------------------------------------------------------------------------------------+
|                                   COMPOSITOR THREAD                                   |
|  +---------------------------------------------------------------------------------+  |
|  | Create Layers / Commit / Tiling                                                 |  |
|  +---------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
|                                     GPU PROCESS                                       |
|  +---------------------------------------------------------------------------------+  |
|  | Draw Quads -> GPU Memory (VRAM) -> Screen Display Engine (VSync Signal)         |  |
|  +---------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------+
```

### State Machine Micro-interaction Terdistribusi

Mikro-interaksi dikontrol oleh state machine deterministik berikut:

```
    +-------------------------------------------------------------------+
    |                                                                   |
    v                                                                   |
+--------+   PointerEnter    +---------+   PointerDown   +-----------+  |
|  IDLE  | ----------------> | HOVERED | --------------> |  PRESSED  |  |
+--------+                   +---------+                 +-----------+  |
    ^                             |                            |        |
    |       PointerLeave          |                            |        |
    +-----------------------------+                            |        |
    |                                                          |        |
    |                                                          v        |
+---------+         Execution Failure / Timeout          +-----------+  |
|  ERROR  | <------------------------------------------- | EXECUTING |  |
+---------+                                              +-----------+  |
    |                                                          |        |
    |                                      Execution Success   |        |
    |                                                          v        |
    |       Cooldown Complete / Ack                      +-----------+  |
    +--------------------------------------------------- |  SUCCESS  | -+
                                                         +-----------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Model Mikro-interaksi Dan Saffer

Setiap mikro-interaksi tingkat tinggi terdiri dari empat komponen struktural yang tidak dapat dipisahkan:

1. **Trigger:** Inisiator mikro-interaksi. Dapat berupa *User-initiated* (klik, seret, hover, gestur sentuh) atau *System-initiated* (kondisi tercapai, kedatangan data SSE/WebSocket, baterai lemah).
2. **Rules:** Algoritma yang mendikte apa yang boleh dan tidak boleh terjadi setelah pemicu aktif. Dijalankan oleh State Machine (misal: "Jika tombol sedang dalam state `Executing`, trigger baru `PointerDown` diabaikan").
3. **Feedback:** Verifikasi visual, audio, atau haptik kepada pengguna yang mengomunikasikan status perubahan rule. Feedback harus beroperasi pada *immediate paint* threshold (< 100ms) untuk mempertahankan ilusi instanitas.
4. **Loops & Modes:** Meta-aturan yang menentukan durasi siklus mikro-interaksi. *Loops* menentukan pengulangan (misal: getaran berulang jika terjadi error konstan), sedangkan *Modes* mengubah perilaku elemen ketika kondisi sistem global berubah (misal: mode "Edit Mode" vs "View Mode").

### 2. Fisika Gerak: The Damped Harmonic Oscillator

Alih-alih menggunakan persamaan kurva Bézier standar ($P(t) = (1-t)^3 P_0 + 3(1-t)^2 t P_1 + 3(1-t) t^2 P_2 + t^3 P_3$), animasi modern berbasis pegas bergantung pada persamaan diferensial orde kedua:

$$m \frac{d^2x}{dt^2} + c \frac{dx}{dt} + k x = 0$$

Di mana:
* $m$ = Mass (Massa objek; semakin besar, semakin tinggi inersia/kelembaman).
* $c$ = Damping coefficient (Redaman gesekan; menghentikan osilasi pegas).
* $k$ = Stiffness / Spring constant (Kekakuan pegas; semakin besar, semakin cepat tarikan ke target).
* $x$ = Perpindahan posisi dari titik setimbang (*displacement*).

Rasio redaman dinotasikan dengan:

$$\zeta = \frac{c}{2\sqrt{mk}}$$

* $\zeta < 1$: **Underdamped** (Sistem berosilasi melewari target/bouncing sebelum stabil).
* $\zeta = 1$: **Critically Damped** (Sistem kembali ke posisi setimbang secepat mungkin tanpa osilasi berlebih).
* $\zeta > 1$: **Overdamped** (Sistem bergerak lambat menuju setimbang tanpa osilasi).

### 3. Teknik Mekanisme FLIP (First, Last, Invert, Play)

FLIP adalah komputasi performa tinggi yang mengubah animasi perubahan tata letak yang mahal menjadi manipulasi transformasi GPU:

1. **First:** Mengukur posisi dan dimensi awal elemen menggunakan `getBoundingClientRect()`.
2. **Last:** Menjalankan manipulasi layout instan (mengubah state DOM, penambahan kelas), lalu membaca posisi dan dimensi akhir elemen (`getBoundingClientRect()`).
3. **Invert:** Menghitung perbedaan koordinat ($\Delta x, \Delta y$) dan skala ($\text{scale}_x, \text{scale}_y$). Terapkan properti `transform` inversi secara instan ke elemen sehingga elemen terlihat seolah-olah masih berada di posisi *First*.
4. **Play:** Hapus `transform` inversi dan aktifkan transisi CSS atau Web Animations API (WAAPI). Elemen akan bertransisi secara mulus dari posisi inversi ke posisi aslinya di layer kompositor.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Orchestration, Choreography, dan Shared Element Transitions

Koreografi antarmuka menuntut kontinuitas spasial. Ketika beberapa elemen bertransisi secara simultan, penggunaan waktu yang seragam menciptakan beban kognitif tinggi (*visual noise*). Koreografi tingkat lanjut bergantung pada:

* **Staggering:** Menunda titik awal animasi antaranggota kelompok elemen menggunakan fungsi derivatif:
  $$\text{delay}(i) = i \times \Delta t$$
  Staggering mengarahkan mata pengguna membaca konten secara berurutan (misalnya dari kiri-atas ke kanan-bawah).
* **Directionality & Focal Point Vectors:** Transisi harus menghormati arah aksi pengguna. Jika pengguna mengklik kartu di kuadran kanan bawah layar untuk membuka modal, modal harus mengekspansi *keluar* dari pusat koordinat kartu tersebut, bukan muncul secara arbitrer dari tengah layar.
* **Shared Element Transitions (Layout Continuity):** Elemen identitas (seperti thumbnail gambar atau avatar profil) harus mempertahankan eksistensinya melintasi perubahan rute atau pergantian hierarki halaman. Pengguna tidak boleh melihat penghapusan elemen A diikuti pembuatan elemen B; mereka harus melihat elemen A bermutasi menjadi B melalui interpolasi spasial terpadu.

### Compositor Layers vs. Paint Invalidation

Secara mekanis, browser mengisolasi node DOM tertentu ke dalam layer rendering independen (*RenderLayers* -> *GraphicsLayers*). Layer-layer ini diunggah sebagai tekstur ke VRAM GPU.

Jika properti non-kompositor diubah:
* Mengubah `left` atau `margin-left`: Browser memicu tahapan **Layout**, menghitung ulang posisi node lain di sekitarnya, meregenerasi struktur geometri, lalu memicu **Paint** untuk seluruh area yang terdampak, kemudian memicu **Composite**. Ini dapat menghabiskan waktu 15ms-50ms CPU pada DOM tree yang besar, menyebabkan frame drop seketika.
* Mengubah `transform: translate3d(x, y, 0)` atau `opacity`: Browser mempertahankan pohon Layout dan struktur Paint. Sinyal perubahan langsung dikirimkan ke Compositor Thread. GPU hanya perlu mengubah transformasi matriks tekstur layer di VRAM. Waktu eksekusi: < 1ms CPU.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi murni *Spring Physics Engine* menggunakan TypeScript dan Web Animations API (WAAPI), dibangun dari dasar tanpa ketergantungan library pihak ketiga.

```typescript
// spring-engine.ts

export interface SpringConfig {
  mass: number;
  stiffness: number;
  damping: number;
  initialVelocity?: number;
  precision?: number;
}

export interface SpringKeyframe {
  transform: string;
  offset: number;
}

export class SpringSimulation {
  private mass: number;
  private stiffness: number;
  private damping: number;
  private initialVelocity: number;
  private precision: number;

  constructor(config: SpringConfig) {
    this.mass = Math.max(0.001, config.mass);
    this.stiffness = Math.max(0.001, config.stiffness);
    this.damping = Math.max(0.001, config.damping);
    this.initialVelocity = config.initialVelocity ?? 0;
    this.precision = config.precision ?? 1 / 1000;
  }

  /**
   * Menghitung posisi pegas pada waktu t (detik)
   * Berdasarkan persamaan penyelesaian diferensial orde 2
   */
  public solve(t: number): { position: number; velocity: number } {
    const m = this.mass;
    const k = this.stiffness;
    const c = this.damping;

    const dampingRatio = c / (2 * Math.sqrt(k * m));
    const angularFrequency = Math.sqrt(k / m);
    const initialDisplacement = 1.0; // Normalisasi dari 1 ke 0

    let position = 0;
    let velocity = 0;

    if (dampingRatio < 1) {
      // Underdamped
      const dampedFrequency = angularFrequency * Math.sqrt(1 - dampingRatio * dampingRatio);
      const decay = Math.exp(-dampingRatio * angularFrequency * t);
      const c1 = initialDisplacement;
      const c2 = (this.initialVelocity + dampingRatio * angularFrequency * initialDisplacement) / dampedFrequency;

      const cos = Math.cos(dampedFrequency * t);
      const sin = Math.sin(dampedFrequency * t);

      position = decay * (c1 * cos + c2 * sin);
      velocity = -dampingRatio * angularFrequency * position +
        decay * (-c1 * dampedFrequency * sin + c2 * dampedFrequency * cos);
    } else if (dampingRatio === 1) {
      // Critically Damped
      const decay = Math.exp(-angularFrequency * t);
      const c1 = initialDisplacement;
      const c2 = this.initialVelocity + angularFrequency * initialDisplacement;

      position = decay * (c1 + c2 * t);
      velocity = decay * (c2 - angularFrequency * (c1 + c2 * t));
    } else {
      // Overdamped
      const r1 = -angularFrequency * (dampingRatio - Math.sqrt(dampingRatio * dampingRatio - 1));
      const r2 = -angularFrequency * (dampingRatio + Math.sqrt(dampingRatio * dampingRatio - 1));
      const c2 = (this.initialVelocity - r1 * initialDisplacement) / (r2 - r1);
      const c1 = initialDisplacement - c2;

      position = c1 * Math.exp(r1 * t) + c2 * Math.exp(r2 * t);
      velocity = c1 * r1 * Math.exp(r1 * t) + c2 * r2 * Math.exp(r2 * t);
    }

    return { position, velocity };
  }

  /**
   * Menghasilkan keyframes untuk Web Animations API
   */
  public generateKeyframes(
    fromX: number,
    toX: number,
    fromY: number,
    toY: number,
    fps: number = 60
  ): { keyframes: Keyframe[]; durationMs: number } {
    const deltaX = fromX - toX;
    const deltaY = fromY - toY;
    const step = 1 / fps;
    let t = 0;
    const rawFrames: { x: number; y: number }[] = [];

    // Simulasi sampai pergerakan di bawah batas ambang presisi
    while (t < 5.0) { // Limit keselamatan maksimum 5 detik
      const { position, velocity } = this.solve(t);
      const currentX = toX + deltaX * position;
      const currentY = toY + deltaY * position;

      rawFrames.push({ x: currentX, y: currentY });

      if (Math.abs(position) < this.precision && Math.abs(velocity) < this.precision) {
        break;
      }
      t += step;
    }

    const durationMs = Math.max(16, t * 1000);
    const totalFrames = rawFrames.length;

    const keyframes: Keyframe[] = rawFrames.map((frame, index) => {
      const progress = index / (totalFrames - 1);
      return {
        offset: progress,
        transform: `translate3d(${frame.x.toFixed(3)}px, ${frame.y.toFixed(3)}px, 0px)`,
      };
    });

    return { keyframes, durationMs };
  }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis logika kelas `SpringSimulation`:

* **Baris 23–27:** `Math.max(0.001, config.property)`. Memastikan variabel massa, kekakuan, dan redaman tidak bernilai 0 atau negatif. Nilai 0 pada kalkulasi ini dapat memicu pembagian nol (*division by zero*) yang menghasilkan `NaN` atau `Infinity` pada thread matriks WAAPI.
* **Baris 38–41:** `dampingRatio = c / (2 * Math.sqrt(k * m))`. Menghitung nilai $\zeta$. Ini menentukan formula deterministik mana yang harus dieksekusi oleh mesin matematika: *underdamped*, *critically damped*, atau *overdamped*.
* **Baris 48–56:** Implementasi formula trigonometri eksponensial teredam untuk $\zeta < 1$. Konstanta integrasi `c1` dan `c2` diselesaikan berdasarkan nilai awal perpindahan dan kecepatan `this.initialVelocity`.
* **Baris 82–83:** Inversi delta koordinat (`deltaX = fromX - toX`). Mesin ini menormalisasi pegas di mana pergerakan bergerak dari nilai deviasi $1.0$ (kondisi tertekan/tertarik) menuju kondisi ekuilibrium $0.0$.
* **Baris 92–95:** Ambang terminasi simulasi (`Math.abs(position) < this.precision`). Tanpa evaluasi ambang batas ini, animasi akan berjalan tanpa henti mendekati asimtot numerik, mengonsumsi array memori untuk frame yang secara visual tidak mengalami perubahan piksel (*imperceptible sub-pixel movement*).
* **Baris 102–107:** Transformasi array menjadi array objek `Keyframe` dengan properti `translate3d(X, Y, 0px)`. Penggunaan format 3D memaksa pipeline browser mengalokasikan context grafis pada hardware acceleration langsung tanpa memicu layer repainting.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: "High-Frequency Interactive Kanban Board dengan Gestur Kinetik & FLIP"

**Skala Aplikasi:** Enterprise Project Management Dashboard (misal: Jira / Linear / Asana) dengan ribuan sub-task, 60 task per kolom, dan 12 kolom independen.

**Masalah Kritis Kinerja:**
Ketika pengguna menyeret kartu tugas (*card drag-and-drop*) ke kolom lain:
1. Operasi penataan ulang DOM standar memicu *Layout Thrashing* (rekalkulasi layout berantai di seluruh container kolom).
2. Perubahan dimensi kolom akibat mutasi child memicu pergeseran layout kumulatif (CLS).
3. Frame rate anjlok dari 120 FPS ke 23 FPS saat proses dragging (*jank parah*), yang memicu penalti pada metrik Interaction to Next Paint (INP > 400ms).

**Solusi Arsitektur:**
1. Bangun komponen orkestrator yang mengisolasi proses *dragging* sepenuhnya di compositor layer dengan pointer capture.
2. Saat kartu dilepas (*drop*), gunakan kalkulasi deterministik **FLIP Matrix Transformer** untuk menganimasikan kartu-kartu lain yang terdampak tanpa memicu layout tree recalculation secara redundant.
3. Pisahkan arsitektur ke dalam Finite State Machine untuk mengeliminasi event race-conditions antara event mouse pointer, touch, dan API response.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Implementasi berikut menggunakan React 18/19, TypeScript murni, tanpa dependensi eksternal seperti Framer Motion, GSAP, atau React Spring. Solusi ini berjalan murni di atas DOM API, React hooks, dan Web Animations API (WAAPI).

```tsx
// InteractiveKanbanCard.tsx
import React, { useState, useRef, useLayoutEffect, useCallback } from 'react';
import { SpringSimulation } from './spring-engine';

export interface CardData {
  id: string;
  title: string;
  description: string;
  columnId: string;
}

interface InteractiveKanbanCardProps {
  card: CardData;
  onMoveColumn: (cardId: string, targetColumnId: string) => void;
}

type CardInteractionState = 'IDLE' | 'HOVERED' | 'DRAGGING' | 'SETTLING';

export const InteractiveKanbanCard: React.FC<InteractiveKanbanCardProps> = ({
  card,
  onMoveColumn,
}) => {
  const cardRef = useRef<HTMLDivElement | null>(null);
  const [state, setState] = useState<CardInteractionState>('IDLE');
  
  // Track pointer positions secara imperatif untuk menghindari re-render React berlebihan
  const pointerOrigin = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const currentOffset = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const activeAnimation = useRef<Animation | null>(null);

  // Aksesibilitas: Periksa preferensi reduced motion
  const prefersReducedMotion = useRef<boolean>(
    typeof window !== 'undefined'
      ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
      : false
  );

  const handlePointerDown = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0 || !cardRef.current) return; // Hanya proses klik kiri
    
    // Batalkan animasi settling yang sedang berjalan jika ada
    if (activeAnimation.current) {
      activeAnimation.current.cancel();
      activeAnimation.current = null;
    }

    cardRef.current.setPointerCapture(e.pointerId);
    pointerOrigin.current = { x: e.clientX, y: e.clientY };
    currentOffset.current = { x: 0, y: 0 };

    setState('DRAGGING');
  }, []);

  const handlePointerMove = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    if (state !== 'DRAGGING' || !cardRef.current) return;

    const deltaX = e.clientX - pointerOrigin.current.x;
    const deltaY = e.clientY - pointerOrigin.current.y;
    currentOffset.current = { x: deltaX, y: deltaY };

    // Manipulasi langsung layer GPU tanpa memicu React Render Lifecycle
    cardRef.current.style.transform = `translate3d(${deltaX}px, ${deltaY}px, 0px) scale(1.03)`;
    cardRef.current.style.zIndex = '999';
    cardRef.current.style.boxShadow = '0 20px 25px -5px rgba(0, 0, 0, 0.2), 0 10px 10px -5px rgba(0, 0, 0, 0.04)';
  }, [state]);

  const handlePointerUp = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    if (state !== 'DRAGGING' || !cardRef.current) return;

    cardRef.current.releasePointerCapture(e.pointerId);
    setState('SETTLING');

    const finalX = currentOffset.current.x;
    const finalY = currentOffset.current.y;

    if (prefersReducedMotion.current) {
      // Jalur fallback instan untuk pengguna reduced-motion
      if (cardRef.current) {
        cardRef.current.style.transform = 'translate3d(0px, 0px, 0px) scale(1)';
        cardRef.current.style.zIndex = '1';
        cardRef.current.style.boxShadow = 'none';
      }
      setState('IDLE');
      return;
    }

    // Inisialisasi Spring Physics Engine
    const spring = new SpringSimulation({
      mass: 1.0,
      stiffness: 180,
      damping: 18, // Rasio underdamped terkontrol untuk feedback kinetik natural
      initialVelocity: 0,
    });

    const { keyframes, durationMs } = spring.generateKeyframes(finalX, 0, finalY, 0);

    // Jalankan via Web Animations API (Hardware Accelerated)
    const animation = cardRef.current.animate(keyframes, {
      duration: durationMs,
      easing: 'linear', // Interpolasi dikontrol langsung oleh mathematical keyframes
      fill: 'forwards',
    });

    activeAnimation.current = animation;

    animation.onfinish = () => {
      if (cardRef.current) {
        cardRef.current.style.transform = 'translate3d(0px, 0px, 0px) scale(1)';
        cardRef.current.style.zIndex = '1';
        cardRef.current.style.boxShadow = 'none';
      }
      activeAnimation.current = null;
      setState('IDLE');

      // Evaluasi apakah drop memicu perpindahan kolom (threshold > 150px)
      if (Math.abs(finalX) > 150) {
        const targetColumn = finalX > 0 ? 'col-done' : 'col-todo';
        onMoveColumn(card.id, targetColumn);
      }
    };
  }, [state, card.id, onMoveColumn]);

  return (
    <div
      ref={cardRef}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerUp}
      onPointerEnter={() => state === 'IDLE' && setState('HOVERED')}
      onPointerLeave={() => state === 'HOVERED' && setState('IDLE')}
      style={{
        touchAction: 'none',
        userSelect: 'none',
        cursor: state === 'DRAGGING' ? 'grabbing' : 'grab',
        transition: state === 'HOVERED' ? 'transform 150ms ease, box-shadow 150ms ease' : 'none',
        transform: state === 'HOVERED' ? 'translate3d(0, -2px, 0)' : undefined,
      }}
      className={`relative p-4 mb-3 rounded-lg border bg-white dark:bg-zinc-900 border-zinc-200 dark:border-zinc-800 select-none will-change-[transform] ${
        state === 'DRAGGING' ? 'ring-2 ring-blue-500' : ''
      }`}
      role="button"
      tabIndex={0}
      aria-grabbed={state === 'DRAGGING'}
      aria-label={`Task: ${card.title}`}
    >
      <div className="font-semibold text-zinc-900 dark:text-zinc-100">{card.title}</div>
      <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">{card.description}</p>
      <div className="mt-2 flex items-center gap-2">
        <span className="text-xs px-2 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300">
          State: {state}
        </span>
      </div>
    </div>
  );
};
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter Evaluasi | CSS Keyframes / Transitions | Web Animations API (WAAPI) | JS Runtime Simulation (Framer/GSAP) | Physics-Engine Hand-Rolled (Kode Seksi 07 & 10) |
| :--- | :--- | :--- | :--- | :--- |
| **Thread Execution** | Compositor Thread (GPU) | Compositor Thread (GPU) | Main Thread (CPU) | Compositor via generated Keyframes |
| **Dukungan Dynamic Physics**| ❌ Tidak mungkin (terbatas Bézier statis) | ⚠️ Terbatas (harus generate array keyframes) | ✅ Penuh (interpolasi real-time per frame) | ✅ Penuh (dihitung deterministik di awal) |
| **Overhead Bundle Size** | 0 KB | 0 KB (Browser Native) | ~30 KB - 70 KB (Gzipped) | < 2 KB (Zero-dependency) |
| **Interruptibility / Cancel**| Buruk (memicu jump visual jika dicancel) | ✅ Luar biasa (`animation.cancel()`, `reverse()`) | ✅ Luar biasa (State reconciliation) | ✅ Sangat Baik (Pembatalan native via WAAPI) |
| **Memory Allocation** | Minimum mutlak | Sangat Rendah | Sedang hingga Tinggi (GC pressure tinggi) | Sangat Rendah |
| **Tingkat Kompleksitas Kode**| Sangat Rendah | Menengah | Rendah (Abstraksi deklaratif) | Menengah ke Tinggi |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Pointer Event Desynchronization & Lost Pointer Capture
* **Kondisi Kegagalan:** Ketika pengguna menyeret elemen dengan kecepatan tinggi ke luar viewport peramban, event `pointermove` atau `pointerup` berhenti ditembakkan ke node DOM elemen tersebut.
* **Mitigasi:** Wajib memanggil `element.setPointerCapture(e.pointerId)` pada hook `onPointerDown`. Hal ini menjamin bahwa seluruh pergerakan kursor berikutnya diarahkan secara eksklusif ke node tersebut, bahkan jika posisi fisik pointer keluar dari jendela browser. Jangan lupa melepasnya via `releasePointerCapture` saat terminasi interaksi.

### 2. Layout Thrashing pada Kalkulasi FLIP
* **Kondisi Kegagalan:** Menjalankan eksekusi FLIP pada banyak elemen secara linear:
  ```typescript
  // PITFALL: Membaca dan menulis secara bergantian memicu multiple synchronous reflows
  elements.forEach(el => {
    const first = el.getBoundingClientRect(); // READ (Reflow)
    el.classList.add('new-pos');             // WRITE (Invalidate)
    const last = el.getBoundingClientRect();  // READ (Forced Synchronous Layout!)
  });
  ```
* **Mitigasi:** Batasi eksekusi menggunakan teknik *Batch Processing*—baca seluruh koordinat awal secara serentak, terapkan seluruh mutasi DOM secara serentak, lalu baca kembali seluruh koordinat akhir secara serentak.

### 3. VRAM Bleed dari Penyalahgunaan `will-change`
* **Kondisi Kegagalan:** Menempatkan deklarasi CSS `will-change: transform` secara permanen pada ratusan elemen di daftar tabel atau list.
* **Mitigasi:** Setiap deklarasi `will-change` yang mempromosikan elemen ke Graphics Layer independen mengonsumsi alokasi memori kartu grafis (VRAM) untuk menyimpan bitmap layer tersebut. Pasang `will-change` hanya sesaat sebelum animasi berjalan (misalnya pada event `hover` atau `pointerdown`), lalu hapus nilainya (`will-change: auto`) segera setelah animasi selesai.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Animasi Properti Box-Model (`width`, `height`, `padding`, `top`, `left`)
* **Kesalahan Fatal:** Menggunakan transisi CSS:
  ```css
  /* SALAH: Memicu Reflow pada tiap frame */
  .accordion-content {
    transition: height 300ms ease;
  }
  ```
* **Solusi Standar Industri:** Gunakan manipulasi `transform: scaleY()` yang dikombinasikan dengan transformasi inversi pada konten teks anak agar teks tidak terlihat gepeng/terdistorsi, atau gunakan teknik WAAPI FLIP untuk menganimasikan kontainer.

### 2. Mengabaikan Frame Budget Saat Menggunakan State