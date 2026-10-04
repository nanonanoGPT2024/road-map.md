# BAB 03: Side Effects, Refs, dan Imperative Interop Boundary
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis Internal Scheduling:** Menjelaskan secara presisi urutan eksekusi commit phase React Fiber (*Mutation, Layout, Passive Effects*) dan bagaimana React Engine mengelola siklus hidup DOM Node via Pointer/Ref.
- **Membangun Imperative Interop Boundaries:** Mengenkapsulasi pustaka pihak ketiga non-deklaratif (seperti WebGL/Three.js, D3.js, Leaflet, atau Monaco Editor) ke dalam React Component yang aman terhadap *lifecycle races*, *strict mode re-mounting*, dan *memory leaks*.
- **Mengoptimalkan Render Performance via Ref Isolation:** Mengimplementasikan teknik *uncontrolled state bypass* untuk menangani update data frekuensi tinggi (hingga 60–120 FPS) tanpa memicu reconciler cascade atau re-rendering seluruh pohon komponen.
- **Menguasai API Batas Eksekusi Lanjutan:** Menggunakan kombinasi `forwardRef`, `useImperativeHandle`, `useLayoutEffect`, dan `useInsertionEffect` secara tepat berdasarkan timing CSSOM, DOM layout measurement, dan CSS-in-JS injection.
- **Mencegah & Memitigasi Memory Leaks:** Mengidentifikasi dan memperbaiki *detached DOM tree references*, *dangling event listeners*, dan *unclean closures* menggunakan runtime telemetry dan memory profiling.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
- **React Fundamentals:** Pemahaman mendalam tentang siklus hidup komponen, *Virtual DOM*, *Fiber Tree*, dan dasar `useEffect`/`useRef`.
- **Browser Event Loop & Rendering Pipeline:** Pemahaman tentang microtasks (`Promise.then`, `queueMicrotask`), macrotasks (`setTimeout`, `I/O`), `requestAnimationFrame`, serta tahapan browser rendering (*Style recalculation, Layout/Reflow, Paint, Composite*).
- **TypeScript Intermediate to Advanced:** Generics, Generic Constraints, Polymorphic Components, serta utility types untuk React (`ElementRef`, `ComponentPropsWithRef`).

---

### 3. Concept & Internal Architecture

#### 3.1 Fiber Architecture: Mutasi DOM dan Siklus Ref
React Fiber memisahkan pekerjaannya ke dalam dua fase utama: **Render Phase** (asinkron, dapat diinterupsi) dan **Commit Phase** (sinkron, tidak dapat diinterupsi). Ref dan Side Effects beroperasi hampir seluruhnya pada Commit Phase.

```
+-------------------------------------------------------------------------+
|                              RENDER PHASE                               |
| (WorkLoop: reconciliation, diffing, penciptaan Fiber workInProgress)    |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                              COMMIT PHASE                               |
|                                                                         |
|  1. Before Mutation Phase:                                              |
|     - commitBeforeMutationEffects()                                     |
|     - Membaca snapshot via getSnapshotBeforeUpdate                     |
|                                                                         |
|  2. Mutation Phase:                                                     |
|     - commitMutationEffects()                                           |
|     - Host bindings (DOM) diubah, disisipkan, atau dihapus              |
|     - Unmount ref: ref.current = null (jika ref berubah atau unmount)   |
|                                                                         |
|  3. Layout Phase:                                                       |
|     - commitLayoutEffects()                                             |
|     - Mutasi ref baru di-assign: ref.current = DOMNode / Handle         |
|     - useLayoutEffect dijalankan secara SINKRON                         |
|     - Browser belum melakukan paint (DOM tree siap dibaca/diukur)       |
|                                                                         |
|  ------------------------- BROWSER PAINT -----------------------------  |
|                                                                         |
|  4. Passive Phase:                                                      |
|     - commitPassiveMountEffects()                                       |
|     - Didaftarkan melalui Scheduler via MessageChannel / setTimeout     |
|     - useEffect dieksekusi secara ASINKRON pasca layar ter-render       |
+-------------------------------------------------------------------------+
```

Pada level internal Fiber (`FiberNode`):
- `fiber.memoizedState`: Menyimpan linked-list dari hook instances.
- `fiber.flags`: Bitmask yang menandai efek (misal: `Placement`, `Update`, `Layout`, `Passive`, `Ref`).
- `fiber.ref`: Menyimpan referensi callback atau objek ref yang diikat ke node tersebut.

Ketika React memproses unmount atau update referensi:
1. `commitDetachRef(fiber)`: Mengosongkan target ref (`ref.current = null`).
2. `commitAttachRef(fiber)`: Memasukkan instance DOM host aktual atau nilai dari `useImperativeHandle` ke `ref.current`.

#### 3.2 Perbedaan Kritis: useEffect vs useLayoutEffect vs useInsertionEffect
1. **`useInsertionEffect`**: 
   - Berjalan *sebelum* mutasi DOM terjadi.
   - Ditujukan khusus bagi pustaka CSS-in-JS (seperti Emotion/Styled-Components) untuk menginjeksi tag `<style>` ke DOM sebelum browser menghitung kalkulasi style pada fase layout.
2. **`useLayoutEffect`**:
   - Berjalan *secara sinkron* setelah mutasi DOM selesai dilakukan di commit phase, tetapi *sebelum* browser melakukan paint (layout/reflow phase).
   - Membaca layout (misal: `getBoundingClientRect()`, `scrollWidth`) dan melakukan mutasi layout imperatif secara langsung di sini mencegah terjadinya *visual layout flicker*.
   - **Peringatan:** Menahan jalannya rendering utama (blocking paint); jika komputasi di sini berat, FPS akan anjlok drastis.
3. **`useEffect`**:
   - Berjalan *secara asinkron* setelah browser selesai menggambar frame ke layar (*post-paint*).
   - Tempat aman untuk data fetching, subscription, integrasi analitik, dan sebagian besar interop boundary yang tidak mempengaruhi geometri elemen visual secara langsung.

---

### 4. Why & What

#### Mengapa Kita Membutuhkan Imperative Interop Boundary?
Paradigma React adalah **Declarative UI**: `UI = f(State)`. Namun, ekosistem browser dan dunia nyata rekayasa perangkat lunak penuh dengan entitas yang bersifat **Imperative** (stateful, mutable, lifecycle-bound):
- Komponen Canvas 2D/WebGL rendering engines (Pixi.js, Three.js).
- Pustaka visualisasi data tingkat lanjut (D3.js).
- Text/Code Editors kompleks (Monaco Editor, CodeMirror).
- Media processing primitives (WebRTC tracks, AudioContext, Canvas video capture).

Jika entitas imperatif ini dibiarkan bercampur langsung dengan render lifecycle React tanpa batas (*boundary*) yang terisolasi, aplikasi akan mengalami:
1. **Hydration Mismatch & DOM Collision**: React mencoba merekonsiliasi DOM yang sudah diubah secara mutatif oleh pustaka pihak ketiga, menyebabkan *DOMException: Failed to execute 'removeChild' on 'Node'*.
2. **Memory Leaks**: External engine mengikat listener pada window/canvas tanpa dibersihkan ketika Fiber di-unmount.
3. **Double Invocations Bug**: Mekanisme React 18+ *Strict Mode* melakukan mount -> unmount -> remount instan untuk memeriksa stabilitas lifecycle. Jika cleanup tidak simetris, engine eksternal akan terinisialisasi ganda (*duplicate contexts*).

#### Apa Itu Imperative Interop Boundary?
Sebuah pattern arsitektural di mana sebuah React Component bertindak sebagai "duta konsuler" yang mengisolasi kode deklaratif React dari kode imperatif pihak ketiga. Boundary ini mengekspos API deklaratif ke parent (via props) dan API imperatif terkontrol (via `forwardRef` + `useImperativeHandle`), sambil mengunci seluruh mutasi mutlak di dalam lifecycle yang aman.

---

### 5. How (Workflow Detail)

Alur kerja perancangan Imperative Boundary:

```
[Parent Component]
       |
       | 1. Kirim State & Callbacks via Props
       | 2. Pegang Ref Imperatif (jika perlu intervensi direct execution)
       v
+---------------------------------------------------------------+
|             IMPERATIVE INTEROP BOUNDARY (React)               |
|                                                               |
|  A. Container Mount (<div ref={containerRef} />)              |
|  B. useLayoutEffect / useEffect:                              |
|     - Inisialisasi External Engine Instance                   |
|     - Simpan instance di engineRef (useRef)                   |
|     - Ikat event listener engine ke React props callback      |
|  C. useImperativeHandle:                                      |
|     - Masking instance eksternal (pruning unsafe methods)     |
|     - Expose API terbatas & aman ke Parent                    |
|  D. Prop Mutation Diffing:                                    |
|     - Sinkronisasi perubahan props ke method engine eksternal |
|  E. Teardown / Cleanup:                                       |
|     - Hancurkan instance engine (engine.destroy())            |
|     - Lepas listener, batalkan RAF / Network abort            |
|     - Set engineRef.current = null                            |
+---------------------------------------------------------------+
                               |
                               | Memanipulasi langsung
                               v
               [External Imperative Engine / DOM]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Kedutaan Besar (Diplomatic Embassy)
Pikirkan React Tree sebagai sebuah **Negara Berdaulat yang Bersih** di mana hukum deklaratif berlaku mutlak (tidak boleh ada coret-coret manual, segalanya berdasarkan deklarasi hukum). 

Pustaka pihak ketiga (misalnya library pemetaan C++ berbasis WASM) adalah **Negara Luar yang Imperatif**, di mana orang bebas mengubah tanah kapan saja secara langsung.

**Interop Boundary** adalah **Gedung Kedutaan Besar**:
- Di luar gedung, diplomat berinteraksi dengan protokol resmi React (props, refs).
- Di dalam gedung, ia memiliki otoritas penuh untuk menjalankan hukum negara asalnya (mutasi DOM langsung, panggil `gl.drawArrays()`).
- Jika kedutaan ditutup (*unmount*), diplomat wajib membersihkan semua personelnya tanpa meninggalkan jejak sampah (*no memory leaks*).

```
REACT TREE (Declarative World)
   |
   | Props: { zoom: 10, center: [x, y] }
   | Ref: { focusMarker: (id) => void }
   v
=====================================================
|  BOUNDARY (Kedutaan Besar: Interop Layer)        |
|  - Menyimpan kontainer DOM kosong                 |
|  - Mengubah deklarasi prop menjadi panggilan method|
|    "engine.setZoom(10)"                           |
|  - Mengisolasi mutasi agar React tidak crash     |
=====================================================
   |
   | Direct Memory / GPU / Canvas Mutations
   v
BROWSER ENGINE (Imperative World: WebGL/Canvas/Engine)
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Typed Imperative Handle
Mengekspos interface imperatif yang terisolasi dari native DOM input element untuk mereset dan memfokuskan komponen.

```tsx
import React, { forwardRef, useImperativeHandle, useRef } from "react";

export interface CustomInputHandle {
  focusAndClear: () => void;
  getCharacterCount: () => number;
}

interface CustomInputProps {
  label: string;
  placeholder?: string;
}

export const CustomInput = forwardRef<CustomInputHandle, CustomInputProps>(
  ({ label, placeholder }, ref) => {
    const inputRef = useRef<HTMLInputElement | null>(null);

    // Mengunci eksposur: Parent HANYA bisa mengakses focusAndClear dan getCharacterCount,
    // bukan seluruh DOM node input (prinsip Least Privilege).
    useImperativeHandle(
      ref,
      () => ({
        focusAndClear: () => {
          if (inputRef.current) {
            inputRef.current.value = "";
            inputRef.current.focus();
          }
        },
        getCharacterCount: () => {
          return inputRef.current ? inputRef.current.value.length : 0;
        },
      }),
      [] // dependencies kosong: method references stabil
    );

    return (
      <div className="flex flex-col gap-1">
        <label className="text-sm font-semibold">{label}</label>
        <input
          ref={inputRef}
          type="text"
          placeholder={placeholder}
          className="border p-2 rounded"
        />
      </div>
    );
  }
);

CustomInput.displayName = "CustomInput";
```

#### 7.2 Practical Example: High-Performance Canvas Particle Engine (Production-Grade Boundary)
Komponen React yang membungkus siklus hidup rendering Canvas 2D frame-by-frame dengan *zero re-render*, mitigasi *Strict Mode double invocation*, dan *DevicePixelRatio synchronization*.

```tsx
import React, {
  useRef,
  useEffect,
  useImperativeHandle,
  forwardRef,
  useCallback,
} from "react";

// Kontrak Imperatif untuk Parent
export interface ParticleCanvasHandle {
  burst: (count: number) => void;
  reset: () => void;
  getParticleCount: () => number;
}

interface ParticleCanvasProps {
  width: number;
  height: number;
  particleColor?: string;
  onFPSUpdate?: (fps: number) => void;
}

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  alpha: number;
}

export const ParticleCanvas = forwardRef<
  ParticleCanvasHandle,
  ParticleCanvasProps
>(({ width, height, particleColor = "#3B82F6", onFPSUpdate }, ref) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  
  // Isolated imperative mutable state (Bypass React Reconciler completely)
  const engineState = useRef<{
    particles: Particle[];
    animationFrameId: number | null;
    lastTime: number;
    frameCount: number;
    lastFpsUpdate: number;
  }>({
    particles: [],
    animationFrameId: null,
    lastTime: 0,
    frameCount: 0,
    lastFpsUpdate: 0,
  });

  // Storing stable reference to dynamic callbacks to avoid re-binding loop
  const onFPSUpdateRef = useRef(onFPSUpdate);
  useEffect(() => {
    onFPSUpdateRef.current = onFPSUpdate;
  }, [onFPSUpdate]);

  // Factory untuk partikel
  const createParticle = useCallback(
    (x: number, y: number): Particle => ({
      x,
      y,
      vx: (Math.random() - 0.5) * 4,
      vy: (Math.random() - 0.5) * 4,
      alpha: 1.0,
    }),
    []
  );

  // Implementasi Handle Imperatif
  useImperativeHandle(
    ref,
    () => ({
      burst: (count: number) => {
        const state = engineState.current;
        for (let i = 0; i < count; i++) {
          state.particles.push(createParticle(width / 2, height / 2));
        }
      },
      reset: () => {
        engineState.current.particles = [];
      },
      getParticleCount: () => engineState.current.particles.length,
    }),
    [width, height, createParticle]
  );

  // Lifecycle Interop: Setup Render Engine & RAF Loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d", { alpha: false });
    if (!ctx) return;

    // Handle High-DPI Displays (Retina Screens)
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);

    let isRunning = true;
    const state = engineState.current;

    const loop = (currentTime: number) => {
      if (!isRunning) return;

      const deltaTime = currentTime - state.lastTime;
      state.lastTime = currentTime;

      // Hitung FPS
      state.frameCount++;
      if (currentTime - state.lastFpsUpdate >= 1000) {
        const currentFps = Math.round(
          (state.frameCount * 1000) / (currentTime - state.lastFpsUpdate)
        );
        onFPSUpdateRef.current?.(currentFps);
        state.frameCount = 0;
        state.lastFpsUpdate = currentTime;
      }

      // 1. Clear background
      ctx.fillStyle = "#0F172A";
      ctx.fillRect(0, 0, width, height);

      // 2. Physics & Draw Mutations
      ctx.fillStyle = particleColor;
      for (let i = state.particles.length - 1; i >= 0; i--) {
        const p = state.particles[i];
        p.x += p.vx;
        p.y += p.vy;
        p.alpha -= 0.005;

        if (p.alpha <= 0 || p.x < 0 || p.x > width || p.y < 0 || p.y > height) {
          state.particles.splice(i, 1);
          continue;
        }

        ctx.globalAlpha = p.alpha;
        ctx.beginPath();
        ctx.arc(p.x, p.y, 2.5, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1.0;

      state.animationFrameId = requestAnimationFrame(loop);
    };

    state.lastTime = performance.now();
    state.lastFpsUpdate = performance.now();
    state.animationFrameId = requestAnimationFrame(loop);

    // TEARDOWN: Garansi pembersihan mutlak untuk Strict Mode & Unmount
    return () => {
      isRunning = false;
      if (state.animationFrameId !== null) {
        cancelAnimationFrame(state.animationFrameId);
        state.animationFrameId = null;
      }
    };
  }, [width, height, particleColor]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        width: `${width}px`,
        height: `${height}px`,
        display: "block",
      }}
      className="rounded-lg shadow-xl cursor-crosshair"
      onClick={(e) => {
        const rect = e.currentTarget.getBoundingClientRect();
        const clickX = e.clientX - rect.left;
        const clickY = e.clientY - rect.top;
        const state = engineState.current;
        for (let i = 0; i < 25; i++) {
          state.particles.push(createParticle(clickX, clickY));
        }
      }}
    />
  );
});

ParticleCanvas.displayName = "ParticleCanvas";
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario: Financial Terminal L2 Order Book Heatmap & Charting
Sebuah platform broker valuta asing enterprise memproses data stream pasar via WebSocket dengan frekuensi **1,000 tick updates per detik**. 

##### Masalah Arsitektur:
Arsitektur awal menggunakan standard React State (`useState`) di mana tiap incoming payload memicu render pada komponen pohon order book.
- **Akibat:** Reconciler overhead menelan CPU hingga 100%. Thread UI macet (*frame drop*, input latency > 500ms). React Fiber tree mengalami memory churn yang memicu Garbage Collection pauses setiap 3 detik.

##### Solusi Arsitektur Menggunakan Imperative Boundary:
1. Pisahkan layer visualisasi data berkecepatan tinggi ke dalam elemen `<canvas>` murni yang dibungkus oleh sebuah React Imperative Interop Boundary (`OrderBookHeatmapBoundary`).
2. Komponen boundary menolak semua incoming update data via Props. Sebagai gantinya, WebSocket worker berkomunikasi langsung ke Boundary melalui *ring buffer* (SharedArrayBuffer atau array referensi di dalam `useRef`).
3. Menggunakan `useImperativeHandle` untuk mengekspos kendali viewport (pan, zoom level, highlight order block).
4. Penjadwalan rendering visual digantungkan sepenuhnya pada loop `requestAnimationFrame` internal yang membaca mutasi data buffer secara pasif tanpa melibatkan React reconciler.

```tsx
// Cuplikan Skematis Arsitektur Produksi
export interface HeatmapImperativeController {
  pushOrderDeltas: (deltas: Array<[price: number, size: number]>) => void;
  centerPrice: (price: number) => void;
}

export const OrderBookHeatmapBoundary = forwardRef<HeatmapImperativeController, HeatmapProps>(
  (props, ref) => {
    const canvasContainerRef = useRef<HTMLDivElement | null>(null);
    const internalEngineRef = useRef<NativeHeatmapEngine | null>(null);

    // Initial Engine Binding
    useLayoutEffect(() => {
      if (!canvasContainerRef.current) return;

      const engine = new NativeHeatmapEngine(canvasContainerRef.current, {
        colorPalette: props.colorPalette,
      });
      internalEngineRef.current = engine;

      return () => {
        engine.dispose(); // Destructor imperative engine (clear webgl context, web workers)
        internalEngineRef.current = null;
      };
    }, []);

    // Reactive Props Synchronization tanpa merusak instance WebGL
    useEffect(() => {
      internalEngineRef.current?.updatePalette(props.colorPalette);
    }, [props.colorPalette]);

    // Imperative Pipe: Data Tick Streaming langsung membypass React Reconciliation
    useImperativeHandle(
      ref,
      () => ({
        pushOrderDeltas: (deltas) => {
          // Mutasi direct ke buffer C++ / TypedArray engine eksternal
          internalEngineRef.current?.ingestDeltas(deltas);
        },
        centerPrice: (price) => {
          internalEngineRef.current?.scrollTo(price);
        },
      }),
      []
    );

    return <div ref={canvasContainerRef} className="heatmap-viewport w-full h-full" />;
  }
);
OrderBookHeatmapBoundary.displayName = "OrderBookHeatmapBoundary";
```

##### Hasil:
- Penggunaan CPU UI thread turun dari 98% menjadi 11%.
- FPS stabil pada 60 FPS (atau 120/144 FPS sesuai refresh rate monitor).
- Reconciler React tidak pernah dipanggil untuk data update ticks.

---

### 9. Trade-offs

| Aspek | Declarative Standard React (`useState` / Props) | Imperative Interop Boundary (`useRef` / `useImperativeHandle`) |
| :--- | :--- | :--- |
| **Performance (Throughput)** | Rendah pada frekuensi tinggi (>60 Hz) akibat tree diffing & allocations. | Ekstrem tinggi; mutasi memori langsung melewati reconciler. |
| **Latency (Input-to-Screen)** | Bergantung pada antrean scheduler Fiber dan work priority React. | Sub-millisecond (langsung dieksekusi pada frame buffer/DOM host). |
| **Maintainability** | Sangat Tinggi. Kode predikabel, mudah dilacak melalui *time-travel debugging*. | Lebih Rendah. Rentan *race conditions*, mutasi implisit, dan sulit didebug. |
| **SSR / Hydration** | Seamless (didukung penuh oleh arsitektur Suspense/SSR). | Rawan crash. Seluruh inisialisasi imperatif harus diisolasi di client side (`useEffect`). |
| **Testing Complexity** | Sederhana. Cukup uji via React Testing Library (*behavior testing*). | Kompleks. Memerlukan mocking DOM low-level, WebGL mock, atau E2E test penuh (Playwright). |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Stale Closures pada Event Listeners Eksternal
*Kesalahan:* Mengikat listener engine pihak ketiga pada callback React tanpa membersihkan atau memperbarui pointer ref callback.
```tsx
// RUSAK: onSelect akan menjadi stale closure mengunci nilai state awal
useEffect(() => {
  externalEngine.on('select', (id) => {
    props.onSelect(id, selectedCategory); // selectedCategory selalu initial value
  });
}, []);
```
*Solusi:* Gunakan "Latest Ref Pattern":
```tsx
const latestOnSelect = useRef(props.onSelect);
latestOnSelect.current = props.onSelect;

useEffect(() => {
  const handler = (id: string) => latestOnSelect.current(id);
  externalEngine.on('select', handler);
  return () => externalEngine.off('select', handler);
}, []);
```

#### 10.2 Layout Thrashing pada `useLayoutEffect`
*Kesalahan:* Membaca layout geometri DOM, menulis style mutasi, lalu membaca layout lagi di dalam loop.
```tsx
// RUSAK: Memicu paksa sinkronisasi Layout berulang kali
useLayoutEffect(() => {
  items.forEach(item => {
    const height = elementRef.current.offsetHeight; // READ
    elementRef.current.style.height = `${height + 10}px`; // WRITE
  });
});
```
*Solusi:* Lakukan *Batch Read* terlebih dahulu, kemudian lakukan *Batch Write*.

#### 10.3 Detached DOM Node Memory Leak
*Kesalahan:* Menyimpan referensi DOM di dalam variabel global atau closure pustaka eksternal yang tidak dibersihkan saat komponen di-unmount.
*Pencegahan:* 
- Selalu sediakan destructor simetris pada `useEffect` cleanup.
- Verifikasi via Chrome DevTools **Memory Tab -> Take Heap Snapshot -> Filter "Detached HTMLDivElement"**. Jika count bertambah saat komponen mount/unmount berulang kali, terjadi kebocoran referensi.

---

### 11. Best Practices (Production Checklist)

1. [ ] **Hydration Guard:** Pastikan engine eksternal hanya diinisialisasi di client-side. Gunakan pengecekan `typeof window !== 'undefined'` atau isolasi di dalam `useEffect`/`useLayoutEffect`.
2. [ ] **Strict Mode Resiliency:** Pastikan teardown effect Anda idempoten. Panggilan berurutan: `Mount -> Unmount -> Mount` tidak boleh meninggalkan duplicate instance atau error *"Canvas already in use"*.
3. [ ] **Interface Pruning:** Batasi method yang diekspos melalui `useImperativeHandle`. Jangan pernah mengekspos referensi *raw DOM node* atau instance engine *unprotected* secara penuh kepada parent.
4. [ ] **Abort Controller Integration:** Gunakan `AbortController` untuk membatalkan proses async (fetch assets, texture loading) di dalam imperative setup saat komponen unmount di tengah jalan.
5. [ ] **WeakMap Referencing:** Jika Anda perlu mengaitkan metadata internal dengan DOM node yang dikelola pihak ketiga, gunakan `WeakMap` agar garbage collector dapat mengklaim node saat terlepas dari tree.

---

### 12. Hands-on Practice

Buat sebuah direktori praktikum: `hands-on/m02/`

#### File 1: `hands-on/m02/AudioVisualizerBoundary.tsx`
Implementasikan custom HTML5 Audio Synthesizer Boundary dengan Web Audio API imperatif:
- Melakukan isolasi `AudioContext` & `AnalyserNode`.
- Mencegah React re-render saat audio playback tick.
- Menyediakan Imperative Handle: `playNote(freq: number)`, `stop()`, `getDecibels(): number`.

```tsx
import React, { forwardRef, useImperativeHandle, useEffect, useRef } from "react";

export interface AudioVisualizerHandle {
  playNote: (frequency: number) => void;
  stop: () => void;
  getDecibels: () => number;
}

export const AudioVisualizerBoundary = forwardRef<AudioVisualizerHandle, {}>(
  (_, ref) => {
    const audioContextRef = useRef<AudioContext | null>(null);
    const oscillatorRef = useRef<OscillatorNode | null>(null);
    const analyserRef = useRef<AnalyserNode | null>(null);

    useLayoutEffect(() => {
      // Lazy init AudioContext on user demand to avoid browser autoplay policy warning
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const ctx = new AudioCtx();
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 64;

      audioContextRef.current = ctx;
      analyserRef.current = analyser;

      return () => {
        if (ctx.state !== "closed") {
          ctx.close();
        }
        audioContextRef.current = null;
        analyserRef.current = null;
      };
    }, []);

    useImperativeHandle(ref, () => ({
      playNote: (freq: number) => {
        const ctx = audioContextRef.current;
        const analyser = analyserRef.current;
        if (!ctx || !analyser) return;

        if (ctx.state === "suspended") {
          ctx.resume();
        }

        // Hentikan oscillator sebelumnya jika masih jalan
        if (oscillatorRef.current) {
          oscillatorRef.current.stop();
          oscillatorRef.current.disconnect();
        }

        const osc = ctx.createOscillator();
        const gainNode = ctx.createGain();

        osc.type = "sine";
        osc.frequency.setValueAtTime(freq, ctx.currentTime);

        gainNode.gain.setValueAtTime(0.3, ctx.currentTime);

        osc.connect(gainNode);
        gainNode.connect(analyser);
        analyser.connect(ctx.destination);

        osc.start();
        oscillatorRef.current = osc;
      },
      stop: () => {
        if (oscillatorRef.current) {
          oscillatorRef.current.stop();
          oscillatorRef.current.disconnect();
          oscillatorRef.current = null;
        }
      },
      getDecibels: () => {
        const analyser = analyserRef.current;
        if (!analyser) return 0;

        const dataArray = new Uint8Array(analyser.frequencyBinCount);
        analyser.getByteFrequencyData(dataArray);

        // Average level
        const sum = dataArray.reduce((acc, val) => acc + val, 0);
        return sum / dataArray.length;
      },
    }), []);

    return (
      <div className="p-4 border rounded bg-slate-900 text-white">
        <p className="text-xs uppercase tracking-wider text-slate-400">
          Audio Engine Hardware Boundary (Web Audio API)
        </p>
        <div className="mt-2 text-sm text-green-400">Status: Active & Isolated</div>
      </div>
    );
  }
);

AudioVisualizerBoundary.displayName = "AudioVisualizerBoundary";
```

#### File 2: `hands-on/m02/App.tsx`
Konsumsi boundary tersebut dari komponen root deklaratif:
```tsx
import React, { useRef } from "react";
import { AudioVisualizerBoundary, AudioVisualizerHandle } from "./AudioVisualizerBoundary";

export function App() {
  const audioControllerRef = useRef<AudioVisualizerHandle | null>(null);

  return (
    <div className="p-8 space-y-4">
      <h1 className="text-2xl font-bold">Imperative Boundary Studio</h1>
      <AudioVisualizerBoundary ref={audioControllerRef} />

      <div className="flex gap-2">
        <button
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          onClick={() => audioControllerRef.current?.playNote(440)} // A4 Note
        >
          Play A4 (440Hz)
        </button>
        <button
          className="px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700"
          onClick={() => audioControllerRef.current?.playNote(523.25)} // C5 Note
        >
          Play C5 (523Hz)
        </button>
        <button
          className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
          onClick={() => audioControllerRef.current?.stop()}
        >
          Stop
        </button>
      </div>
    </div>
  );
}
```

---

### 13. Exercise

#### Level: Easy
- **Tugas:** Buat komponen `FocusTrapInput` menggunakan `forwardRef` dan `useImperativeHandle`.
- **Kebutuhan:** Komponen mengekspos method `shakeAndFocus()` yang menambahkan class CSS animasi getar selama 500ms dan memfokuskan kursor ke dalam elemen input.
- **Batasan:** Dilarang mengekspos HTMLInputElement asli secara langsung.

#### Level: Medium
- **Tugas:** Bangun `ThirdPartyMapWrapper` yang mengintegrasikan library pihak ketiga mock (berupa instance kelas imperatif berbasis DOM murni).
- **Kebutuhan:**
  1. Komponen menerima prop `coordinates: { lat: number; lng: number }`.
  2. Map engine harus merespons perubahan koordinat tanpa menginisialisasi ulang kontainer map.
  3. Tangani kasus Strict Mode di mana DOM kontainer dipasang/dilepas dua kali secara berturut-turut.

#### Level: Hard
- **Tugas:** Implementasikan `VirtualCursorStreamer`.
- **Kebutuhan:**
  1. Mampu menerima stream koordinat mouse (x, y) hingga **120 payload per detik** dari simulated WebSocket server.
  2. Render kursor virtual di layar menggunakan boundary Canvas tanpa memicu re-render pada React tree parent.
  3. Sediakan Imperative Handle untuk mengganti warna kursor dan mengekspor snapshot canvas menjadi *Data URL (PNG)* secara sinkron.

---

### 14. Challenge

#### Skenario Kasus: WebGL Complex Mesh Viewer dengan Suspended Lifecycle
Anda ditugaskan merancang modul visualisasi CAD 3D berbasis Three.js/WebGL di dalam arsitektur React modern dengan batasan ekstrem berikut:
1. **Model Loading Asinkron:** Pengambilan binary mesh (.gltf/.bin) memakan waktu 3-5 detik dan harus terintegrasi dengan boundary React Error & Suspense boundary tanpa membuat context WebGL bocor atau ter-recreate.
2. **Context Loss Handling:** GPU browser terkadang mengalami event `webglcontextlost` saat OS kekurangan memory. Boundary Anda harus mampu menangkap event imperatif ini, me-reset state internal, menunggu `webglcontextrestored`, lalu me-restore mesh 3D ke posisi semula tanpa reload halaman.
3. **Zero Frame Overhead:** Kontrol orbit kamera (rotate, pan, zoom) harus berjalan pada 60/120 FPS murni di GPU thread, namun ketika rotasi berhenti, posisi sudut kamera terakhir harus dikirimkan ke state deklaratif parent melalui debounce threshold untuk disimpan ke URL query params.

*Tantangan:* Bangun arsitektur boundary lengkap beserta teardown lifecycle-nya dan buktikan ketiadaan memory leak melalui snapshot memory profiling trace.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Basic (5 Pertanyaan)
1. **Pada fase apakah assignment referensi `ref.current = DOMNode` dijalankan oleh React Fiber?**
   - A. Render Phase
   - B. Mutation Phase
   - C. Layout Phase
   - D. Passive Effect Phase
2. **Apa fungsi utama dari hook `useImperativeHandle`?**
   - A. Menggantikan seluruh peran `useState` di komponen anak
   - B. Mengontrol dan membatasi method/properti instance yang diekspos melalui ref ke parent
   - C. Mempercepat eksekusi rendering deklaratif React
   - D. Melakukan sinkronisasi state antar komponen sibling tanpa Context
3. **Kapan `useLayoutEffect` dieksekusi oleh React?**
   - A. Secara asinkron setelah browser melukis (post-paint)
   - B. Secara sinkron sebelum browser melukis, tepat setelah mutasi DOM selesai
   - C. Sebelum Fiber melakukan diffing komponen
   - D. Pada background thread Web Worker
4. **Mengapa React 18+ Strict Mode menjalankan efek setup & cleanup sebanyak dua kali saat fase mount di development mode?**
   - A. Merupakan bug yang belum terselesaikan di React Engine
   - B. Untuk mengecek kompatibilitas browser lama
   - C. Untuk memverifikasi bahwa effect memiliki cleanup yang idempoten dan aman terhadap unmount instan
   - D. Untuk mengompilasi TypeScript menjadi WebAssembly
5. **Apa yang terjadi jika Anda memanggil `setState` di dalam `useLayoutEffect`?**
   - A. React menjadwalkannya di idle frame berikutnya
   - B. React akan melakukan re-render secara sinkron sebelum layar di-paint oleh browser, berpotensi memblokir UI thread
   - C. Terjadi silent error dan mutasi dibatalkan
   - D. Tidak ada dampak sama sekali dibanding `useEffect`

#### Bagian B: Intermediate (5 Pertanyaan)
6. **Kapan Anda sebaiknya menggunakan `useInsertionEffect` dibandingkan `useLayoutEffect`?**
   - A. Saat melakukan fetching data via Axios
   - B. Saat membaca ukuran elemen dengan `getBoundingClientRect()`
   - C. Khusus saat menginjeksi tag `<style>` secara dinamis untuk pustaka CSS-in-JS sebelum layout dihitung
   - D. Saat membuat koneksi WebSocket
7. **Apa bahaya terbesar membiarkan pustaka eksternal (seperti jQuery atau D3) memodifikasi node anak secara langsung di dalam kontainer yang juga diatur oleh JSX React?**
   - A. Bundle size aplikasi membesar 2x lipat
   - B. Terjadi error reconciler React (*Failed to execute 'removeChild' on 'Node'*) karena DOM tree aktual tidak sinkron dengan Fiber
   - C. File CSS global akan terhapus
   - D. Semua network request otomatis terhenti
8. **Bagaimana cara mencegah stale closures pada listener pustaka eksternal yang diinisialisasi hanya sekali pada mount phase?**
   - A. Memasukkan seluruh state ke dalam dependency array dan membiarkan instance dihancurkan berulang kali
   - B. Menggunakan referensi mutable (`useRef`) yang selalu di-update pada setiap render untuk menampung callback terbaru
   - C. Menghilangkan TypeScript strict mode
   - D. Mengubah fungsi listener menjadi fungsi asinkron
9. **Mengapa mutasi langsung ke `ref.current` tidak memicu re-render pada komponen React?**
   - A. Karena React sengaja mengabaikan objek JavaScript
   - B. Karena `ref` bukan merupakan immutable pointer
   - C. Karena mutasi properti objek tidak mengubah referensi pointer objek `ref` itu sendiri, sehingga reconciler tidak mendeteksi perubahan state
   - D. Karena `useRef` di-render di luar thread V8 engine
10. **Apa strategi paling efektif membungkus pustaka Canvas yang memerlukan ukuran piksel akurat pada layar High-DPI (Retina)?**
    - A. Memperbesar ukuran font menggunakan CSS
    - B. Mengalikan properti width/height internal Canvas dengan `window.devicePixelRatio` dan menskalakan context 2D via `ctx.scale()`, sambil menjaga style CSS width/height tetap pada ukuran CSS pixel
    - C. Mengurangi resolusi viewport sebesar 50%
    - D. Memaksa rendering menggunakan SVG

#### Bagian C: Skenario Kasus Produksi (3 Pertanyaan)

11. **Skenario 1:** Tim frontend Anda melaporkan bahwa sebuah komponen editor teks pihak ketiga (misalnya Monaco Editor) mengalami kehilangan kursor dan duplikasi teks saat dijalankan di React 18 development mode dengan Strict Mode aktif. Apa akar penyebab masalah ini dan bagaimana solusi teknisnya?
12. **Skenario 2:** Anda melihat memory browser membengkak secara linier dari 50MB hingga mencapai 1.2GB setelah user berpindah halaman bolak-balik antara halaman Dashboard dan halaman Chart (yang menggunakan pustaka grafik Canvas pihak ketiga). Profiling heap snapshot menunjukkan ribuan node bertuliskan `Detached HTMLCanvasElement`. Di mana letak kegagalan implementasi boundary komponen tersebut?
13. **Skenario 3:** Sebuah modal interaktif yang dibungkus `useLayoutEffect` untuk menghitung posisi tooltip selalu menyebabkan frame drop (jank) sekitar 120ms setiap kali dibuka. Setelah diaudit, terdapat pemanggilan `element.getBoundingClientRect()` di dalam loop iterasi 200 elemen DOM di dalam effect tersebut. Tindakan optimasi apa yang mutlak dilakukan?

---

### Kunci Jawaban & Evaluasi

#### Bagian A: Basic
1. **C** — Penugasan ref baru (`commitAttachRef`) terjadi pada Layout Phase, setelah mutasi DOM selesai dilakukan namun sebelum Paint.
2. **B** — Hook `useImperativeHandle` membatasi dan memodifikasi objek ref yang diteruskan ke parent agar tidak mengekspos seluruh native host object secara mentah.
3. **B** — `useLayoutEffect` dieksekusi sinkron pasca-mutasi DOM sebelum frame digambar ke layar browser (*pre-paint*).
4. **C** — Untuk memvalidasi bahwa komponen mampu bertahan terhadap unmounting/remounting instan tanpa menimbulkan memory leaks atau duplicate resource subscriptions.
5. **B** — `setState` di dalam `useLayoutEffect` memaksa React untuk memproses ulang reconciliation dan render phase secara sinkron sebelum browser paint, berpotensi memblokir rendering UI thread (menimbulkan UI freeze jika berat).

#### Bagian B: Intermediate
6. **C** — `useInsertionEffect` dieksekusi sebelum mutasi DOM apapun dilakukan, dirancang spesifik untuk injeksi aturan CSS dinamis oleh library CSS-in-JS guna menghindari re-kalkulasi style yang tidak perlu.
7. **B** — Mutasi DOM langsung pada node yang dikuasai React akan membuat *Fiber Virtual DOM mismatch* dengan *Real DOM*, menghasilkan fatal error saat React mencoba menghapus atau memindahkan node yang sudah tidak ada.
8. **B** — Pola *Latest Ref Pattern* menampung closure callback terbaru ke dalam `ref.current` setiap render tanpa perlu meregistrasi ulang listener imperatif di lifecycle effect.
9. **C** — Objek ref mempertahankan identitas referensial yang sama (`Object.is` bernilai true). Reconciler React hanya menjadwalkan render jika ada dispatch state (`useState`/`useReducer`).
10. **B** — Mengalikan atribut internal kanvas dengan Device Pixel Ratio mencegah hasil render terlihat buram (*blurry*) pada monitor resolusi tinggi, sementara dimensi CSS menjaga ukuran fisik di halaman.

#### Bagian C: Skenario Kasus Produksi
11. **Akar Masalah:** Monaco Editor membutuhkan kontainer DOM bersih. Ketika Strict Mode mengeksekusi *Mount -> Unmount -> Mount*, fungsi setup Monaco dijalankan dua kali tetapi fungsi unmount/cleanup tidak memanggil method `editor.dispose()`. Akibatnya, dua instance Monaco terpasang pada satu container DOM yang sama, saling memicu collision event.  
    **Solusi:** Kembalikan fungsi destructor simetris di dalam effect hook:
    ```tsx
    useEffect(() => {
      const editorInstance = monaco.editor.create(containerRef.current, options);
      return () => {
        editorInstance.dispose(); // Wajib untuk isolasi lifecycle
      };
    }, []);
    ```
12. **Akar Masalah:** Pustaka grafik eksternal mengikat event listener ke objek global (`window`, `document`) atau menyimpan referensi container canvas di dalam cache internal (misal singleton registry) yang tidak dilepas saat unmount. Hal ini menahan DOM node di memori (*detached node*), mencegah JavaScript Engine Garbage Collector mengklaim memori canvas dan buffer grafiknya.  
    **Solusi:** Pastikan lifecycle cleanup memanggil method `chart.destroy()`, melepas listener window (`window.removeEventListener`), dan mengosongkan referensi lokal: `engineRef.current = null`.
13. **Akar Masalah:** Terjadi fenomena *Layout Thrashing (Forced Synchronous Layout)*. Membaca dimensi geometri (`getBoundingClientRect()`) di dalam iterasi yang diselingi manipulasi style memaksa browser menghitung ulang reflow layout pohon DOM berkali-kali secara sinkron.  
    **Solusi:** Pisahkan loop ke dalam dua fase:
    1. Fase Baca: Lakukan pengukuran seluruh 200 elemen terlebih dahulu ke dalam array memori.
    2. Fase Tulis: Lakukan mutasi koordinat style secara massal, atau lebih baik delegasikan mutasi tersebut via CSS Transform atau requestAnimationFrame batching.

---

### 16. Summary

- **Imperative Interop Boundary** adalah pola arsitektural penting untuk menjembatani ekosistem React yang murni deklaratif dengan dunia imperatif (WebGL, Canvas, Media API, dan Third-party non-React libraries).
- Siklus Commit Phase React Fiber terbagi atas: **Before Mutation**, **Mutation** (ref detached), **Layout** (ref attached, `useLayoutEffect`), dilanjutkan oleh **Browser Paint**, lalu **Passive Phase** (`useEffect`).
- Gunakan `useLayoutEffect` hanya ketika mutasi langsung pada DOM harus diselesaikan sebelum browser melukis layar guna menghindari *visual glitch/flicker*. Untuk logika non-visual, selalu gunakan `useEffect`.
- Isolasi mutasi state frekuensi tinggi (game loops, telemetry streams, visualizer) menggunakan `useRef` dan method imperatif via `useImperativeHandle` untuk mendapatkan performa 60–120 FPS tanpa overhead React reconciliation.
- Kunci ketahanan produksi: Selalu implementasikan **symmetric cleanup lifecycle** untuk menjamin sistem bebas memory leaks dan tahan terhadap siklus unmount-remount React Strict Mode.