# Kurikulum Enterprise: Product Design & Frontend Architecture
## BAB 07: Advanced Interaction Design, Micro-interactions, dan Motion Architecture
### Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, engineer dan desainer sistem interaksi tingkat lanjut diharapkan mampu:

1. **Menganalisis dan Mengoptimasi Pipeline Rendering UI**: Mengidentifikasi dan mengeliminasi *layout thrashing*, *forced synchronous layout*, dan *composite invalidation* pada animasi 60 FPS dan 120 FPS di browser web modern (Chromium/WebKit/Gecko) dan mobile runtime (React Native/iOS Metal/Android Skia).
2. **Merancang Motion System Berbasis Fisika Terukur**: Mengimplementasikan model matematika *damped harmonic oscillator* (massa, kekakuan/*stiffness*, redaman/*damping*) untuk menggantikan fungsi *cubic-bezier* statis demi pengalaman interaksi yang interupsi-toleran (*interruptible interactions*).
3. **Mengembangkan Arsitektur State-Driven Micro-interactions**: Mengintegrasikan Finite State Machines (FSM) untuk memetakan transisi state mikro yang deterministik, bebas dari kondisi balapan (*race conditions*) antarevent gestur, I/O jaringan, dan animasi visual.
4. **Menerapkan Motion Tokens Terstandardisasi Lintas Platform**: Membangun pipeline token animasi terpusat (Style Dictionary, JSON/CSS Variables) yang menyinkronkan token *duration*, *spring parameters*, dan *choreography* antara Figma, Web, dan Mobile Client.
5. **Memenuhi Regulasi Aksesibilitas Motion**: Mengimplementasikan mitigasi vestibular disorder secara otomatis melalui *media queries* runtime (`prefers-reduced-motion`) dan fallback arsitektural sesuai standar WCAG 2.2 Success Criterion 2.2.2, 2.3.1, dan 2.3.3.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
* Konsep internal browser: DOM Tree, CSSOM, Render Tree, Layout (Reflow), Paint, dan Compositing.
* Pemrograman berbasis event dan asynchronous handling (JavaScript Event Loop, Microtasks, `requestAnimationFrame`, Pointer Events Level 3).
* Aljabar linear dasar: Vektor 2D/3D, matriks transformasi (`matrix3d`), dan kalkulus diferensial dasar untuk menghitung laju perubahan (kecepatan & akselerasi gestur).
* Konsep Finite State Machine (State, Event, Transition, Action).
* Pengalaman kerja dengan framework modern (React/TypeScript, React Native, atau CSS Houdini).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1. Browser & Device Rendering Pipeline Internals

Untuk menghasilkan micro-interaction yang mulus (*jank-free*), arsitektur animasi harus mengeksploitasi layer rendering paling efisien dalam arsitektur GPU:

```
[ JavaScript / Event Handler ]
              │
              ▼
    [ Recalculate Style ] 
              │
              ▼
          [ Layout ]          <-- HINDARI (Memakan CPU Main Thread drastis)
              │
              ▼
          [ Paint ]           <-- HINDARI (Rasterisasi ulang bitmap)
              │
              ▼
        [ Composite ]         <-- TARGET ARSITEKTUR KITA (Offloaded ke GPU Thread)
```

1. **Main Thread vs Compositor Thread**:
   * **Main Thread**: Mengeksekusi JavaScript, memproses input events, menghitung CSS Cascading, menjalankan Layout (menghitung geometri elemen: `width`, `height`, `top`, `left`), dan melakukan Paint (menggambar piksel: `color`, `background-color`, `box-shadow`).
   * **Compositor Thread**: Bertanggung jawab memotong layer menjadi ubin (*tiles*), mengirimkannya ke GPU Raster Thread, dan menggabungkan (*compositing*) layer-layer tersebut di layar.
   * **Promosi Layer (`will-change: transform, opacity`)**: Menginstruksikan Graphics Engine untuk memisahkan elemen menjadi layer kompositor tersendiri (*RenderLayer* ke *GraphicsLayer*). Modifikasi pada properti `transform` dan `opacity` berjalan sepenuhnya di Compositor Thread tanpa memicu siklus Layout maupun Paint.

2. **Matematika Spring Physics: Damped Harmonic Oscillator**:
   Animasi tradisional berbasis waktu (*duration-based easing*) memiliki cacat mendasar: apabila sebuah gestur dilepaskan di tengah jalan dengan inersia tinggi, animasi *ease-out* statis akan mematahkan momentum tersebut secara instan (*velocity clipping*).
   
   Sistem berbasis fisika menyelesaikan masalah ini menggunakan Persamaan Diferensial Biasa (ODE) orde kedua:

   $$m\frac{d^2x}{dt^2} + c\frac{dx}{dt} + kx = 0$$

   Di mana:
   * $m$ = Massa (*mass*): Mengontrol inersia objek. Nilai lebih besar memerlukan gaya lebih besar untuk berakselerasi dan membutuhkan waktu lebih lama untuk berhenti.
   * $k$ = Kekakuan (*stiffness / spring constant*): Menentukan daya tarik kembali ke titik setimbang (*target position*).
   * $c$ = Koefisien Redaman (*damping ratio* $\zeta$): Mengontrol seberapa cepat osilasi berhenti.
     * $\zeta < 1$: *Underdamped* (terjadi osilasi bolak-balik sebelum diam).
     * $\zeta = 1$: *Critically damped* (kembali ke titik diam dalam waktu tercepat tanpa osilasi).
     * $\zeta > 1$: *Overdamped* (kembali ke titik diam tanpa osilasi, tetapi lambat).

```
Damping Ratio Effects:
Pos
 ^
 │      /\
 │     /  \   Underdamped (zeta < 1: Bouncy)
 │    /    \    /\
 ├---/------\--/--\------- Target Rest Position
 │  /        \/
 │ / Critically Damped (zeta = 1: Snappy, No overshoot)
 │/_______________________ Overdamped (zeta > 1: Sluggish)
 └─────────────────────────> Time
```

3. **Interruption Tolerance & Dynamic Velocity Injection**:
   Ketika interaksi pengguna berganti di tengah siklus animasi (misal: tombol ditekan, dilepas sebelum selesai, lalu ditekan kembali), model fisika mempertahankan *initial velocity* ($v_0$) dari animasi sebelumnya dan menyuntikkannya ke persamaan diferensial berikutnya, menghasilkan transisi visual yang kontinu tanpa patahan (*tangent continuity* $C^1$).

---

### 4. Why & What

| Dimensi | Animasi Ad-Hoc / Legacy Transition | Physics-Driven State Motion Architecture |
| :--- | :--- | :--- |
| **Paradigma** | Berbasis waktu statis (Durasi: `300ms ease-in-out`) | Berbasis momentum dinamis (Massa, Kekakuan, Redaman, Kecepatan Awal) |
| **Responsivitas Interupsi** | Patah (*abrupt snap*) atau me-reset ulang timeline dari frame nol | *Continuous momentum transfer* tanpa *layout shift* |
| **Eksekusi Thread** | Sering memicu CPU Layout/Paint (`top`, `margin`, `max-height`) | Strictly Compositor/GPU-bound (`transform`, `opacity`) |
| **Determinisme State** | Kondisi balapan rentan terjadi saat input event bertumpuk | Terkendali secara mutlak lewat Finite State Machine (FSM) |
| **Aksesibilitas** | Sering diabaikan atau manual di-override per file CSS | Terintegrasi di level token arsitektur melalui *reduced-motion engine* |

#### Keunggulan Arsitektur:
* **Perceived Latency Reduction**: Micro-interactions yang memvalidasi sentuhan secara instan (<16ms respons visual) menurunkan persepsi latensi jaringan backend hingga 300%.
* **Cognitive Mapping**: Gerakan spasial memberikan konteks fungsional kepada pengguna mengenai asal mula data, hierarki layar, dan konsekuensi aksi (misal: item yang dihapus meluncur keluar ke keranjang sampah).

---

### 5. How (Workflow Detail)

Alur kerja perancangan hingga deployment motion tingkat enterprise mengikuti tahapan berikut:

1. **Definisi Token Desain (Design Tokens Architecture)**:
   * Motion designer dan Design System Architect menentukan token parametrik untuk web dan mobile.
   * *Contoh*: Token `motion.spring.snappy` = `{ mass: 1, stiffness: 400, damping: 30 }`.

2. **Parsing & Interpolasi Runtime**:
   * Token dibaca oleh Motion Engine (misalnya via CSS Variables atau JavaScript Spring Resolver).
   * Nilai dihitung per-frame (60Hz = 16.6ms, 120Hz = 8.3ms) menggunakan algoritma integrasi numerik (seperti Runge-Kutta Orde ke-4 / RK4 atau Symplectic Euler).

3. **Orkestrasi Gestur dan State Machine**:
   * Event pointer (`pointerdown`, `pointermove`, `pointerup`) mengirim event ke Finite State Machine (misal: IDLE $\rightarrow$ DRAGGING $\rightarrow$ RELEASING $\rightarrow$ SETTLED).
   * Kecepatan gestur (*gesture velocity*) dihitung via selisih $\Delta d / \Delta t$ pada 3 frame terakhir sebelum *pointer up*.

4. **Compositor Projection via Matrix3D Transforms**:
   * Nilai output animasi langsung dimutasi ke GPU transform layer via inline CSS custom property atau Web Animations API (WAAPI), menghindari mutasi atribut layout.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Rel Kereta Api vs Suspensi Mobil Reli

Animasi *CSS Easing* tradisional itu seperti **Rel Kereta Api**:
Begitu kereta dijalankan dengan rute `ease-in-out 300ms`, ia terkunci pada lintasan tersebut. Jika pengguna tiba-tiba menarik rem atau mengubah arah (menginterupsi gestur), kereta harus berhenti mendadak atau anjlok secara visual (patah/glitch).

Animasi *Spring Physics* adalah **Suspensi Mobil Reli**:
Elemen antarmuka terhubung ke input sentuhan melalui pegas dan peredam kejut fisik. Jika pengguna melempar elemen dengan cepat, suspensi menyerap kecepatannya secara proporsional. Jika pengguna tiba-tiba menangkapnya kembali di udara, pegas langsung bereaksi terhadap gaya baru dari titik koordinat saat itu tanpa lonjakan visual.

#### Diagram Interaksi Arsitektur

```
[ User Interaction ] ──(Pointer Move + Velocity)──┐
                                                  ▼
                                       ┌─────────────────────┐
                                       │ Finite State Engine │
                                       │   (XState / FSM)    │
                                       └──────────┬──────────┘
                                                  │ Valid Transition
                                                  ▼
┌──────────────────────┐               ┌─────────────────────┐
│ Motion Design Tokens │ ──(Params)──> │ Runge-Kutta (RK4)   │
│ (Mass/Stiff/Damp)    │               │ Spring Solver Loop  │
└──────────────────────┘               └──────────┬──────────┘
                                                  │ Next Matrix Transform
                                                  ▼
                                       ┌─────────────────────┐
                                       │ Render Scheduler    │
                                       │ (requestFrame/WAAPI)│
                                       └──────────┬──────────┘
                                                  │ Direct Layer Write
                                                  ▼
                                       ┌─────────────────────┐
                                       │ GPU Compositor      │
                                       │ (Zero-Layout Thrash)│
                                       └─────────────────────┘
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Mengukur dan Menghentikan Layout Thrashing

Berikut adalah contoh anti-pattern yang sering ditemukan di aplikasi enterprise yang menyebabkan frame drop, beserta solusinya menggunakan *read-then-write batching*.

##### Anti-Pattern (Forced Synchronous Layout):
```typescript
// BURUK: Membaca (Layout Read) lalu Menulis (Layout Write) berulang kali di dalam loop
function animateElementsBad(elements: HTMLElement[]) {
  elements.forEach((el) => {
    // READ: Memaksa browser menghitung layout saat itu juga (Forced Reflow)
    const currentHeight = el.getBoundingClientRect().height;
    // WRITE: Membatalkan layout cache
    el.style.height = `${currentHeight + 10}px`;
  });
}
```

##### Optimized Architecture:
```typescript
// BAIK: Memisahkan Fase Read dan Write secara mutlak
function animateElementsGood(elements: HTMLElement[]) {
  // Fase 1: Batch Reads
  const heights = elements.map((el) => el.getBoundingClientRect().height);

  // Fase 2: Batch Writes via GPU Transform (Menghindari mutasi properti layout)
  requestAnimationFrame(() => {
    elements.forEach((el, index) => {
      const targetScale = (heights[index] + 10) / heights[index];
      el.style.transform = `scaleY(${targetScale})`;
      el.style.transformOrigin = 'top';
    });
  });
}
```

---

#### Practical Example: Production-Grade Physics Spring Swipe-to-Action

Komponen swipe-to-action enterprise dengan penanganan akselerasi gesture, interruptibility, integrasi state machine deterministik, dan adaptasi `prefers-reduced-motion`.

```typescript
// Types & Interfaces
export type SwipeState = 'IDLE' | 'DRAGGING' | 'SNAPPING' | 'DISMISSED';

export interface SpringConfig {
  mass: number;
  stiffness: number;
  damping: number;
  restThreshold: number;
}

export interface DragContext {
  startX: number;
  currentX: number;
  velocityX: number;
  lastTimestamp: number;
}

// Enterprise Spring Engine (Menggunakan Integrator Symplectic Euler)
export class SpringSimulator {
  private position: number;
  private targetPosition: number;
  private velocity: number;
  private config: SpringConfig;

  constructor(initialPosition: number, config: SpringConfig) {
    this.position = initialPosition;
    this.targetPosition = initialPosition;
    this.velocity = 0;
    this.config = config;
  }

  public setTarget(target: number, initialVelocity?: number): void {
    this.targetPosition = target;
    if (initialVelocity !== undefined) {
      this.velocity = initialVelocity;
    }
  }

  public step(deltaTimeSec: number): { position: number; isAtRest: boolean } {
    const { mass, stiffness, damping, restThreshold } = this.config;

    // Force = -k * (x - x_target) - c * v
    const displacement = this.position - this.targetPosition;
    const springForce = -stiffness * displacement;
    const dampingForce = -damping * this.velocity;
    const totalForce = springForce + dampingForce;

    // a = F / m
    const acceleration = totalForce / mass;

    // Update integrasi
    this.velocity += acceleration * deltaTimeSec;
    this.position += this.velocity * deltaTimeSec;

    // Pengecekan kondisi diam (Rest state check)
    const isAtRest =
      Math.abs(this.velocity) < restThreshold &&
      Math.abs(displacement) < restThreshold;

    if (isAtRest) {
      this.position = this.targetPosition;
      this.velocity = 0;
    }

    return { position: this.position, isAtRest };
  }

  public getPosition(): number {
    return this.position;
  }
}

// Controller Implementasi Komponen
export class SwipeableCardController {
  private element: HTMLElement;
  private state: SwipeState = 'IDLE';
  private context: DragContext = { startX: 0, currentX: 0, velocityX: 0, lastTimestamp: 0 };
  private spring: SpringSimulator;
  private animationFrameId: number | null = null;
  private prefersReducedMotion: boolean = false;
  private readonly thresholdDistance = 150; // Jarak trigger aksi

  constructor(element: HTMLElement) {
    this.element = element;
    
    // Default Spring Config: Snappy, low bounce
    this.spring = new SpringSimulator(0, {
      mass: 1.0,
      stiffness: 280,
      damping: 24,
      restThreshold: 0.5,
    });

    this.checkAccessibilityPreference();
    this.attachEvents();
  }

  private checkAccessibilityPreference(): void {
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    this.prefersReducedMotion = mediaQuery.matches;
    mediaQuery.addEventListener('change', (e) => {
      this.prefersReducedMotion = e.matches;
    });
  }

  private attachEvents(): void {
    this.element.addEventListener('pointerdown', this.onPointerDown.bind(this));
    window.addEventListener('pointermove', this.onPointerMove.bind(this));
    window.addEventListener('pointerup', this.onPointerUp.bind(this));
    window.addEventListener('pointercancel', this.onPointerUp.bind(this));
  }

  private onPointerDown(event: PointerEvent): void {
    if (this.state === 'DISMISSED') return;

    // Menghentikan running animation untuk interupsi instan
    if (this.animationFrameId !== null) {
      cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }

    this.state = 'DRAGGING';
    this.element.setPointerCapture(event.pointerId);

    this.context.startX = event.clientX;
    this.context.currentX = this.spring.getPosition();
    this.context.lastTimestamp = performance.now();
    this.context.velocityX = 0;

    this.element.style.willChange = 'transform';
  }

  private onPointerMove(event: PointerEvent): void {
    if (this.state !== 'DRAGGING') return;

    const now = performance.now();
    const deltaTime = Math.max(now - this.context.lastTimestamp, 1); // Hindari divide by zero
    const deltaX = event.clientX - this.context.startX;

    const newPosition = this.context.currentX + deltaX;

    // Hitung momentum instan (px/sec)
    this.context.velocityX = ((newPosition - this.spring.getPosition()) / deltaTime) * 1000;
    this.context.lastTimestamp = now;

    // Update target langsung saat dragging (1:1 tracking)
    this.spring.setTarget(newPosition);
    this.updateVisual(newPosition);
  }

  private onPointerUp(event: PointerEvent): void {
    if (this.state !== 'DRAGGING') return;

    this.state = 'SNAPPING';
    if (this.element.hasPointerCapture(event.pointerId)) {
      this.element.releasePointerCapture(event.pointerId);
    }

    const currentPos = this.spring.getPosition();
    const isOverThreshold = Math.abs(currentPos) > this.thresholdDistance;
    const hasHighVelocity = Math.abs(this.context.velocityX) > 500;

    let targetX = 0;

    if (isOverThreshold || hasHighVelocity) {
      // Dismiss card ke arah swipe
      const direction = currentPos !== 0 ? Math.sign(currentPos) : Math.sign(this.context.velocityX);
      targetX = direction * window.innerWidth * 1.2;
      this.state = 'DISMISSED';
    } else {
      // Rebound ke titik nol
      targetX = 0;
    }

    // Jika reduced motion aktif, bypass kalkulasi fisika
    if (this.prefersReducedMotion) {
      this.applyInstantTransition(targetX);
      return;
    }

    // Suntikkan velocity terakhir ke model fisika spring
    this.spring.setTarget(targetX, this.context.velocityX);
    this.runPhysicsLoop();
  }

  private runPhysicsLoop(): void {
    let lastTime = performance.now();

    const frame = (currentTime: number) => {
      const dt = Math.min((currentTime - lastTime) / 1000, 0.032); // Clamp dt max 32ms
      lastTime = currentTime;

      const { position, isAtRest } = this.spring.step(dt);
      this.updateVisual(position);

      if (!isAtRest) {
        this.animationFrameId = requestAnimationFrame(frame);
      } else {
        this.animationFrameId = null;
        this.element.style.willChange = 'auto';
        if (this.state === 'SNAPPING') this.state = 'IDLE';
      }
    };

    this.animationFrameId = requestAnimationFrame(frame);
  }

  private updateVisual(xOffset: number): void {
    // STRICT RULE: Hanya transform matrix dan opacity untuk performa 120 FPS
    const rotateDeg = xOffset * 0.05;
    this.element.style.transform = `translate3d(${xOffset}px, 0px, 0px) rotate(${rotateDeg}deg)`;
  }

  private applyInstantTransition(targetX: number): void {
    this.element.style.transform = `translate3d(${targetX}px, 0px, 0px)`;
    this.element.style.willChange = 'auto';
    if (this.state === 'DISMISSED') {
      this.element.style.opacity = '0';
    }
  }

  public destroy(): void {
    if (this.animationFrameId !== null) {
      cancelAnimationFrame(this.animationFrameId);
    }
    // Clean up pointers & listeners
  }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Slide-to-Pay pada Aplikasi Finansial "PayGlobal"
* **Skala Sistem**: Digunakan oleh 45 juta pengguna aktif bulanan (MAU) di berbagai tipe perangkat, mulai dari high-end flagships (120 Hz ProMotion) hingga low-end budget Android (60 Hz dengan thermal throttling).
* **Kendala Arsitektur**:
  1. Pengguna sering membatalkan aksi pembayaran secara tak sengaja atau mencoba membalikkan swipe di detik terakhir.
  2. Terjadi lonjakan *dropped frames* drastis (jank hingga 24 FPS) saat animasi berlangsung berbarengan dengan eksekusi enkripsi Payload JSON dan komunikasi Biometric API di background thread.
  3. Regulasi perbankan: Pembayaran tidak boleh tereksekusi dua kali akibat *race condition* antara transisi gestur dan penyelesaian callback.

#### Solusi Rekayasa Sistem:
1. **Penerapan XState Finite State Machine**:
   Memisahkan status komponen secara rigid:
   `UNTOUCHED` $\rightarrow$ `INTERACTING` $\rightarrow$ `EVALUATING_CONFIRMATION` $\rightarrow$ `TRIGGERING_BIOMETRICS` $\rightarrow$ `SUCCESS` / `ROLLBACK`.
   State machine menolak semua input sentuhan baru begitu state berpindah ke `TRIGGERING_BIOMETRICS`.

2. **Offloading Komputasi Frame via Compositor Layering**:
   Slider thumb diisolasi dalam satu Graphics Layer tersendiri dengan `contain: strict; will-change: transform`. Animasi visual dipisahkan total dari proses kriptografi dengan mendelegasikan enkripsi ke Web Worker, menjaga UI thread tetap memiliki budget frame 8ms (120 FPS).

3. **Interruption-Aware Spring Rebound**:
   Jika pengguna menggeser hingga 85% lalu melepaskan dengan akselerasi negatif (ditarik kembali), sistem secara cerdas membaca *vector direction* alih-alih hanya berpatokan pada ambang batas statis (*threshold distance*).

#### Hasil Evaluasi Produksi:
* Penurunan tingkat keluhan transaksi ganda (*unintended transactions*) hingga **99.4%**.
* Rata-rata frame rate di perangkat kelas bawah meningkat dari **37 FPS menjadi 59.2 FPS**.
* Drop-off rate pada checkout payment funnel turun sebesar **4.8%**.

---

### 9. Trade-offs

| Pendekatan / Keputusan | Keuntungan | Biaya / Trade-off | Mitigasi Arsitektur |
| :--- | :--- | :--- | :--- |
| **Physics Spring vs CSS Keyframe** | Interupsi natural, penanganan momentum bebas patahan (*no jumps*). | Perhitungan numerik intensif per frame di JavaScript thread. | Batasi kalkulasi hanya pada pointer aktif; gunakan RK4 solver yang dioptimalkan; lepas loop saat elemen diam. |
| **Promosi Layer (`will-change`)** | Render offloaded ke GPU, bebas dari Layout dan Paint pipeline. | Konsumsi Video RAM (VRAM) melonjak signifikan jika disematkan ke banyak elemen. | Aktifkan `will-change` saat `pointerdown` dan hapus (`will-change: auto`) segera setelah mencapai *rest state*. |
| **High Frequency Sampling (PointerEvents)** | Pelacakan posisi super akurat, latensi input mendekati nol. | Event flood membanjiri event loop; memicu eksekusi JS yang tak sinkron dengan refresh rate. | Selalu tampung koordinat di variabel context dan update elemen hanya dalam siklus `requestAnimationFrame`. |
| **Strict FSM untuk Mikro-interaksi** | Determinisme total, mengeliminasi race conditions dan status UI hantu. | Overhead kode bertambah (*boilerplate* state machine lebih besar). | Gunakan FSM terpusat berbasis library ringan atau pattern reducer modular. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Layout Thrashing di dalam `requestAnimationFrame`
* **Gejala**: CPU spike, drop frame berkelanjutan di DevTools Performance tab (ditandai dengan bar merah bertuliskan "Forced Reflow").
* **Penyebab**: Membaca properti layout geometris (seperti `offsetWidth`, `scrollTop`, atau `getComputedStyle()`) tepat setelah memanipulasi DOM.
* **Solusi**: Terapkan arsitektur **Read/Write separation**. Lakukan pembacaan data di awal siklus frame sebelum mutasi visual dilakukan.

#### 2. GPU Layer Memory Leak
* **Gejala**: Aplikasi crash tiba-tiba di mobile browser (khususnya Safari iOS) saat scrolling list panjang yang berisi kartu interaktif.
* **Penyebab**: Menyematkan CSS `will-change: transform` atau `transform: translateZ(0)` secara permanen pada ratusan elemen di dalam DOM. GPU kehabisan memory texture (VRAM).
* **Solusi**: Hanya tambahkan style compositing secara dinamis ketika elemen disentuh, dan hapus saat elemen diam atau keluar dari viewport (Virtualization).

#### 3. Kehilangan Velocity Data Akibat Pointer Coalescing
* **Gejala**: Animasi spring terasa kaku dan kehilangan momentum lemparan saat jari diangkat dengan cepat.
* **Penyebab**: Browser menggabungkan event (`coalesced events`) untuk menghemat konsumsi proses, sehingga membaca `event.clientX` pada saat `pointerup` sering mengembalikan nilai dengan selisih waktu ($\Delta t$) yang terlambat.
* **Solusi**: Gunakan `event.getCoalescedEvents()` untuk mengekstrak titik-titik sampel riil di antara frame sebelum menghitung inersia akhir.

---

### 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum merilis modul motion dan micro-interaction ke staging/production:

- [ ] **Compositing Validation**: Tidak ada animasi yang mengubah `width`, `height`, `margin`, `padding`, `top`, `left`, atau `box-shadow`. Hanya `transform` dan `opacity` yang dimutasi.
- [ ] **Frame Budget**: Eksekusi script per frame tidak melebihi **8.3ms** (untuk target 120Hz) atau **16.6ms** (untuk target 60Hz) pada profiling throttling CPU 4x slow-down.
- [ ] **Memory Footprint**: `will-change: transform` dicopot secara otomatis saat animasi mencapai *rest position*.
- [ ] **Aksesibilitas (WCAG 2.2)**:
  - [ ] Implementasi runtime `@media (prefers-reduced-motion: reduce)`.
  - [ ] Transisi esensial (seperti validasi form error) tetap ada namun durasi dipersingkat menjadi 0-10ms tanpa transisi spasial.
  - [ ] Tidak ada kilatan visual lebih dari 3 kali dalam jendela 1 detik (mitigasi photosensitive seizure).
- [ ] **Interruptibility Audit**: Elemen yang sedang beranimasi menuju target dapat disentuh dan ditarik kembali secara instan tanpa glitch posisi (*no teleports*).
- [ ] **Touch Action Handling**: CSS `touch-action: none` atau `pan-y` diterapkan pada node interaktif untuk mencegah browser menginterupsi gesture dengan native scrolling.

---

### 12. Hands-on Practice

Struktur direktori kerja:
```
hands-on/
└── m02/
    ├── package.json
    ├── tsconfig.json
    ├── src/
    │   ├── core/
    │   │   ├── SpringEngine.ts
    │   │   └── StateMachine.ts
    │   ├── components/
    │   │   ├── PullToRefresh.ts
    │   │   └── pull-to-refresh.css
    │   └── index.ts
    └── index.html
```

#### Langkah 1: Buat Setup Proyek TypeScript Dasar
File: `hands-on/m02/package.json`
```json
{
  "name": "enterprise-motion-architecture",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build"
  },
  "devDependencies": {
    "typescript": "^5.3.3",
    "vite": "^5.1.4"
  }
}
```

#### Langkah 2: Bangun Arsitektur State Machine Terisolasi
File: `hands-on/m02/src/core/StateMachine.ts`
```typescript
export type StateListener<T extends string> = (currentState: T, previousState: T) => void;

export class FiniteStateMachine<TState extends string, TEvent extends string> {
  private currentState: TState;
  private transitions: Map<TState, Map<TEvent, TState>>;
  private listeners: Set<StateListener<TState>> = new Set();

  constructor(initialState: TState) {
    this.currentState = initialState;
    this.transitions = new Map();
  }

  public addTransition(from: TState, on: TEvent, to: TState): void {
    if (!this.transitions.has(from)) {
      this.transitions.set(from, new Map());
    }
    this.transitions.get(from)!.set(on, to);
  }

  public send(event: TEvent): boolean {
    const availableTransitions = this.transitions.get(this.currentState);
    if (!availableTransitions || !availableTransitions.has(event)) {
      console.warn(`[FSM] Invalid event "${event}" for state "${this.currentState}"`);
      return false;
    }

    const previousState = this.currentState;
    this.currentState = availableTransitions.get(event)!;
    
    this.listeners.forEach((listener) => listener(this.currentState, previousState));
    return true;
  }

  public getState(): TState {
    return this.currentState;
  }

  public subscribe(listener: StateListener<TState>): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }
}
```

#### Langkah 3: Implementasi Pull-To-Refresh dengan Haptic Feedback
File: `hands-on/m02/src/components/PullToRefresh.ts`
```typescript
import { SpringSimulator } from './../core/SpringEngine';
import { FiniteStateMachine } from './../core/StateMachine';

type PTRState = 'IDLE' | 'PULLING' | 'REFRESHING' | 'RESTORING';
type PTREvent = 'PULL' | 'RELEASE' | 'RESOLVE';

export class PullToRefreshComponent {
  private container: HTMLElement;
  private indicator: HTMLElement;
  private fsm: FiniteStateMachine<PTRState, PTREvent>;
  private spring: SpringSimulator;
  private startY: number = 0;
  private currentY: number = 0;
  private readonly threshold = 80;
  private animId: number | null = null;

  constructor(container: HTMLElement, indicator: HTMLElement) {
    this.container = container;
    this.indicator = indicator;

    this.fsm = new FiniteStateMachine<PTRState, PTREvent>('IDLE');
    this.setupTransitions();

    this.spring = new SpringSimulator(0, {
      mass: 0.8,
      stiffness: 200,
      damping: 18,
      restThreshold: 0.2,
    });

    this.bindEvents();
  }

  private setupTransitions(): void {
    this.fsm.addTransition('IDLE', 'PULL', 'PULLING');
    this.fsm.addTransition('PULLING', 'PULL', 'PULLING');
    this.fsm.addTransition('PULLING', 'RELEASE', 'REFRESHING');
    this.fsm.addTransition('PULLING', 'RESOLVE', 'RESTORING');
    this.fsm.addTransition('REFRESHING', 'RESOLVE', 'RESTORING');
    this.fsm.addTransition('RESTORING', 'RESOLVE', 'IDLE');

    this.fsm.subscribe((state) => {
      this.indicator.setAttribute('data-state', state);
      if (state === 'REFRESHING') {
        this.triggerHapticFeedback();
        this.simulateNetworkCall();
      }
    });
  }

  private triggerHapticFeedback(): void {
    if ('vibrate' in navigator) {
      navigator.vibrate(15); // Haptic impact ringan
    }
  }

  private bindEvents(): void {
    this.container.addEventListener('pointerdown', (e) => {
      if (this.container.scrollTop === 0 && this.fsm.getState() === 'IDLE') {
        this.startY = e.clientY;
        this.fsm.send('PULL');
      }
    });

    window.addEventListener('pointermove', (e) => {
      if (this.fsm.getState() !== 'PULLING') return;

      const rawDelta = e.clientY - this.startY;
      if (rawDelta > 0) {
        // Terapkan non-linear resistance formula (rubber banding)
        this.currentY = Math.pow(rawDelta, 0.82);
        this.indicator.style.transform = `translate3d(0px, ${this.currentY}px, 0px)`;
      }
    });

    window.addEventListener('pointerup', () => {
      if (this.fsm.getState() !== 'PULLING') return;

      if (this.currentY >= this.threshold) {
        this.fsm.send('RELEASE');
        this.animateToTarget(this.threshold);
      } else {
        this.fsm.send('RESOLVE');
        this.animateToTarget(0);
      }
    });
  }

  private animateToTarget(target: number): void {
    if (this.animId) cancelAnimationFrame(this.animId);
    this.spring.setTarget(target);

    let lastTime = performance.now();
    const step = (now: number) => {
      const dt = (now - lastTime) / 1000;
      lastTime = now;

      const { position, isAtRest } = this.spring.step(dt);
      this.indicator.style.transform = `translate3d(0px, ${position}px, 0px)`;

      if (!isAtRest) {
        this.animId = requestAnimationFrame(step);
      } else {
        this.animId = null;
        if (target === 0) {
          this.fsm.send('RESOLVE');
        }
      }
    };
    this.animId = requestAnimationFrame(step);
  }

  private simulateNetworkCall(): void {
    setTimeout(() => {
      this.animateToTarget(0);
    }, 2000);
  }
}
```

---

### 13. Exercise

#### Level: Easy
1. Ubah parameter `SpringSimulator` pada contoh kode praktikal agar menghasilkan efek *hyper-bouncy* ($\zeta \approx 0.35$).
2. Hitung nilai kritis parameter $c$ (*damping*) jika diketahui $m = 1$ dan $k = 400$ agar sistem menghasilkan gerakan *critically damped*.

#### Level: Medium
1. Implementasikan gesture canceller: Jika pengguna menahan pointer pada satu titik selama lebih dari 500ms tanpa pergerakan signifikan ($\Delta < 5\text{px}$), batalkan transisi geser dan kembalikan elemen ke origin menggunakan spring animation.
2. Tambahkan observasi dinamis terhadap parameter baterai via Battery Status API. Jika `battery.charging === false` dan `battery.level < 0.2`, nonaktifkan spring loop JS dan beralih ke CSS transitions statis.

#### Level: Hard
1. Buat arsitektur koordinasi multi-layer (Choreography): Hubungkan 3 elemen terpisah (misalnya Header, List Body, Floating Action Button) sedemikian rupa sehingga jika List di-pull, Header bergerak dengan rasio redaman 0.3x, List bergerak dengan rasio 1.0x, dan FAB mengalami deformasi skala (*stretch squashing*) berbasis kecepatan swipe secara simultan tanpa memicu reflow.

---

### 14. Challenge

**Skenario Kasus**: Bangun komponen "Reorderable Kanban Column" interaktif kelas enterprise dengan kriteria berikut:
1. **Interruptible Drag and Drop**: Kartu dapat diseret secara vertikal untuk mengubah urutan. Ketika kartu dilepas, ia harus meluncur ke posisi finalnya menggunakan animasi pegas. Jika di tengah luncuran pengguna menekan kartu itu kembali, momentum luncuran harus diserap secara kontinu tanpa ada lompatan visual 1 frame pun.
2. **Dynamic FLIP Transitions**: Kartu-kartu di sekitarnya yang tergeser harus berpindah posisi menggunakan strategi FLIP (*First, Last, Invert, Play*), di mana pembalikan (*Invert*) dihitung via transform matrix, bukan layout mutations.
3. **Zero Jitter Guarantee**: Animasi harus berjalan stabil di angka **60 FPS pada Android low-end** (misalnya simulasi throttling Chrome DevTools 6x CPU slowdown) dan **120 FPS pada Apple ProMotion Display**.
4. **Disability Access Support**: Saat `prefers-reduced-motion` aktif, drag-and-drop harus secara deterministik menonaktifkan seluruh animasi inersia, dan beralih langsung ke snapping grid instan.

*Target Evaluasi*: Buktikan lewat profiler browser bahwa Layout Shift (`CLS`) bernilai `0` dan tidak ada satupun pemanggilan method geometri dalam blok per-frame loop.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)

1. Properti CSS manakah di bawah ini yang eksekusinya dapat sepenuhnya ditangani oleh Compositor Thread tanpa memicu siklus Layout maupun Paint?
   * A. `top` dan `left`
   * B. `width` dan `height`
   * C. `transform` dan `opacity`
   * D. `margin` dan `padding`

2. Apa efek fisik yang dihasilkan jika sebuah sistem pegas memiliki Damping Ratio ($\zeta$) lebih kecil dari 1 ($\zeta < 1$)?
   * A. Objek berhenti seketika tanpa pergerakan.
   * B. Objek berosilasi bolak-balik melewati titik setimbang (*underdamped/bouncy*).
   * C. Objek membutuhkan waktu tak terhingga untuk mencapai target (*overdamped*).
   * D. Nilai kekakuan elemen menjadi nol.

3. Apa bahaya arsitektural dari menambahkan `will-change: transform` pada seluruh elemen list di halaman web?
   * A. Menyebabkan memori layout cache terkunci permanen.
   * B. Menguras Video RAM (VRAM) secara berlebihan karena pembuatan GPU layer yang tidak perlu.
   * C. Menghentikan event bubbling pada pointer events.
   * D. Menyebabkan thread JavaScript mengalami dead-lock.

4. Kriteria keberhasilan WCAG 2.2 manakah yang secara khusus mengatur pencegahan motion sickness dan vestibular disorder akibat animasi interaksi?
   * A. 1.1.1 Non-text Content
   * B. 2.3.3 Animation from Interactions
   * C. 3.1.2 Language of Parts
   * D. 4.1.3 Status Messages

5. Kapan `requestAnimationFrame` mengeksekusi callback yang didaftarkan dalam siklus event loop browser?
   * A. Tepat sebelum proses rendering dan repainting layar berikutnya.
   * B. Tepat setelah microtask queue dikosongkan secara asynchronous.
   * C. Bersamaan dengan eksekusi `setTimeout(fn, 0)`.
   * D. Di dalam Worker thread terpisah.

---

#### Bagian 2: Intermediate (Analisis Singkat)

1. Jelaskan mengapa *velocity injection* sangat penting dalam menciptakan micro-interaction yang bersifat *interruptible*!
2. Mengapa pembacaan `element.getBoundingClientRect()` di dalam loop animasi dianggap sebagai *anti-pattern* performa tinggi?
3. Sebutkan perbedaan mekanis antara integrasi numerik *Explicit Euler* dan *Symplectic Euler* dalam simulasi spring interaction!
4. Bagaimana arsitektur Finite State Machine (FSM) mencegah terjadinya *double submit* saat micro-interaction tombol transaksi ditekan berulang kali secara agresif?
5. Mengapa teknik CSS `transform: translate3d(x, y, 0)` secara historis digunakan untuk akselerasi perangkat keras, dan mengapa `will-change` lebih direkomendasikan pada browser modern?

---

#### Bagian 3: Skenario Kasus Produksi

1. **Skenario Diagnostik**: Tim Anda merilis fitur bottom-sheet drawer dengan animasi berbasis spring JS. Pada perangkat high-end iOS, drawer bergerak mulus. Namun, pada perangkat Android mid-range, drawer tersendat-sendat (*stuttering* parah) saat diseret. Profiler menunjukkan JavaScript execution time hanya 2ms per frame, namun rendering pipeline memakan waktu 28ms. Apa akar masalah arsitektural yang paling mungkin terjadi, dan bagaimana solusinya?
2. **Skenario Desain Arsitektur**: Anda diminta merancang sistem animasi *fluid drag* untuk checkout e-commerce. Komponen harus mendukung pembatalan sentuhan (*pointercancel* akibat panggilan telepon masuk) tanpa memicu aksi beli atau merusak layout. Rancang struktur transisi FSM dan penanganan event-nya!
3. **Skenario Aksesibilitas Skala Besar**: Aplikasi perbankan enterprise Anda memiliki lebih dari 100 komponen interaktif mikro. Buatlah strategi arsitektur sistem token agar preferensi `prefers-reduced-motion` dapat diubah oleh pengguna baik dari level OS maupun dari toggle in-app settings tanpa me-reload aplikasi.

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Kunci Bagian 1 (Basic)
1. **C** - `transform` dan `opacity` tidak mempengaruhi layout geometri halaman dan di-composite langsung di GPU.
2. **B** - $\zeta < 1$ menunjukkan sistem kurang redaman (*underdamped*), menyebabkan osilasi bolak-balik.
3. **B** - Setiap elemen dengan `will-change` dipromosikan menjadi render layer terpisah yang mengalokasikan backing store di VRAM.
4. **B** - WCAG 2.3.3 mengatur bahwa animasi yang dipicu oleh interaksi pengguna harus dapat dinonaktifkan kecuali bersifat esensial.
5. **A** - `requestAnimationFrame` sinkron dengan siklus refresh display dan dieksekusi sebelum fase style, layout, dan paint.

#### Panduan Jawaban Bagian 2 (Intermediate)
1. *Velocity injection* menjaga kekekalan momentum visual ($\Delta v \neq 0$). Jika jari pengguna bergerak cepat saat dilepas, kecepatan tersebut dimasukkan ke kondisi awal pegas, mencegah objek tampak tertahan (*clamped*) mendadak.
2. Membaca dimensi geometri elemen memaksa browser untuk langsung menyelesaikan perhitungan style dan layout yang tertunda (*flush the queue*), menyebabkan *Forced Synchronous Layout* / *Layout Thrashing*.
3. *Explicit Euler* mengevaluasi posisi dan kecepatan secara terpisah yang sering menambahkan energi palsu ke sistem (membuat simulasi pegas meledak/tidak stabil). *Symplectic Euler* memperbarui kecepatan lebih dulu lalu menggunakannya untuk memperbarui posisi, menjaga konservasi energi dalam sistem harmonik.
4. FSM mendefinisikan state transisi yang mutlak. Ketika event `SUBMIT` pertama diterima pada state `IDLE`, state berubah menjadi `PROCESSING`. Pada state `PROCESSING`, transisi untuk event `SUBMIT` berikutnya bernilai `null` / diabaikan secara deterministik.
5. `translate3d` adalah *hack* untuk memaksa pembuatan layer kompositor (*compositing trigger*). `will-change` adalah API standar W3C yang memberi tahu browser maksud pengembang secara eksplisit sehingga browser dapat mengalokasikan resource secara adaptif tanpa overhead alokasi permanen.

#### Panduan Jawaban Bagian 3 (Skenario Kasus Produksi)
1. **Akar Masalah**: Drawer memicu *Paint Invalidation* pada layer di belakangnya (misalnya karena mengubah bayangan `box-shadow` dinamis atau properti dimensi seperti `height`/`top` saat ditarik, bukan strictly `transform: translate3d`). Kemungkinan lain: layer drawer belum dipisahkan dari layer root document, memaksa seluruh layar di-raster ulang pada tiap frame.  
   **Solusi**: Terapkan `contain: paint` atau `will-change: transform` pada container drawer, ganti semua mutasi posisi ke `transform`, dan render bayangan (*shadow*) menggunakan layer opacity terpisah.
2. **Struktur FSM**:
   * States: `IDLE`, `DRAGGING`, `SNAPPING_BACK`, `COMMITTED`.
   * Events: `POINTER_DOWN`, `POINTER_MOVE`, `POINTER_UP`, `POINTER_CANCEL`.
   * Logika: Ketika event `POINTER_CANCEL` ditembakkan oleh sistem OS, FSM secara otomatis beralih dari `DRAGGING` ke `SNAPPING_BACK` dengan target koordinat $X=0$, mengabaikan ambang batas jarak transaksi, dan melepaskan seluruh event capture pointer.
3. **Strategi Arsitektur Token**:
   * Definisikan token durasi dan stiffness menggunakan CSS Custom Properties di root level (misal: `--motion-duration-scale: 1`).
   * Buat React Context / State Store global yang memantau event `matchMedia('(prefers-reduced-motion: reduce)')` dan in-app toggle.
   * Jika salah satu aktif, set `--motion-duration-scale: 0` dan ubah parameter spring global ke mode instant (stiffness tak terhingga, durasi pegas 0ms). Seluruh komponen turunan membaca token CSS/JS terpusat ini sehingga transisi mati seketika tanpa perlu modifikasi lokal di tiap komponen.

---

### 16. Summary

1. **Efisiensi Rendering Mutlak**: Micro-interaction performa tinggi enterprise bertumpu pada Compositor-only properties (`transform`, `opacity`). Segala bentuk mutasi properti geometri layout di dalam per-frame loop adalah cacat arsitektur.
2. **Physics Menggantikan Bezier Statis**: Kurva durasi statis (`cubic-bezier`) tidak fleksibel terhadap interupsi pengguna. Model fisika *Damped Harmonic Oscillator* menyerap inersia gestur dan mempertahankan kontinuitas kecepatan gerak (*interruptible systems*).
3. **Determinisme State**: Animasi interaktif yang kompleks harus dipandu oleh Finite State Machine untuk menyingkirkan *race conditions*, input spam, dan inkonsistensi status visual.
4. **Disiplin Resource GPU**: Alokasi Compositor Layering via `will-change` harus dikelola secara dinamis: pasang saat interaksi dimulai, cabut seketika saat elemen diam (*settled/at rest*), guna mencegah kehabisan memori grafis (VRAM) pada mobile device.
5. **Universal Accessibility**: Aksesibilitas gerakan bukan fitur tambahan opsional, melainkan fondasi arsitektur. Dukungan runtime terhadap `prefers-reduced-motion` wajib diintegrasikan di level token sistem desain secara deterministik.