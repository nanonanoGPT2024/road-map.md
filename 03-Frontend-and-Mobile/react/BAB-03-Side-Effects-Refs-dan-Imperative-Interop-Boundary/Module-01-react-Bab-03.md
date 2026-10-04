# Bab 03 Module 01: Side Effects, Refs, & Imperative Interop Boundary

---

## SEKSI 01 — IDENTITAS MODUL
* **Track:** 03-Frontend-and-Mobile
* **Kurikulum:** React Architecture & Advanced Patterns
* **Modul:** Bab 03 Module 01
* **Topik:** Side Effects, Refs, & Imperative Interop Boundary
* **Tingkat Kesulitan:** Advanced / Staff Engineer
* **Prasyarat:** Pemahaman mendalam mengenai React Render Lifecycle, Reconciliation (Fiber Tree), Hooks Core Semantics, JavaScript Memory Model, dan Browser Event Loop.

---

## SEKSI 02 — LEARNING OBJECTIVES
1. **Menganalisis Siklus Hidup Efek pada Concurrent React:** Menguasai perbedaan deterministik antara Render Phase (Pure Computation) dan Commit Phase (Mutation, Passive Effects, Layout Effects).
2. **Menguasai Semantik Refs & Escape Hatches:** Memahami alokasi memori objek Ref di tingkat Fiber Node serta mengelola siklus hidup persistensi nilai mutabel tanpa memicu rekonsiliasi.
3. **Membangun Batas Interoperabilitas Imperatif (Imperative Interop Boundary):** Mengintegrasikan librari non-React (imperatif seperti Leaflet, D3, Monaco Editor) ke dalam arsitektur deklaratif React secara deterministik, bebas *memory leak*, dan aman terhadap *Strict Mode remounting*.
4. **Mengeliminasi Race Conditions Asinkron:** Mengimplementasikan pola pembatalan efek menggunakan `AbortController` dan sinkronisasi transaksional via `useEffect` / `useLayoutEffect`.
5. **Mengisolasi Manipulasi DOM:** Memanfaatkan `forwardRef` dan `useImperativeHandle` untuk membatasi eksposur mutasi DOM langsung sesuai prinsip Enkapsulasi OOP/SOP modern.

---

## SEKSI 03 — MINDSET & MENTAL MODEL
React pada intinya adalah sebuah fungsi matematika proyeksi murni: $UI = f(State)$. Namun, dunia nyata tempat aplikasi beroperasi bersifat imperatif, stateful, dan memiliki efek samping (*asynchronous APIs*, WebSocket, mutasi DOM riil, integrasi SDK pihak ketiga, analitik).

```
Dunia Deklaratif React                 Batas Isolasi (Escape Hatch)        Dunia Imperatif Luar
+-------------------------+             +---------------------------+       +---------------------+
| Pure State & Props      |             | Refs & Effects            |       | Browser DOM         |
| Render = Deterministic  | ----------> | Synchronize State to Ext  | ----> | WebSocket Engine    |
| No mutation allowed     |             | Handle Cleanup explicitly |       | Non-React 3rd Party |
+-------------------------+             +---------------------------+       +---------------------+
```

Mental model yang benar:
* **Render adalah kalkulasi murni:** Jangan pernah memicu efek samping, mengubah variabel di luar fungsi, atau membaca/menulis `ref.current` selama fase eksekusi render.
* **`useEffect` adalah mekanisme sinkronisasi, bukan Lifecycle Hook:** Tinggalkan pemikiran berbasis `componentDidMount` / `componentDidUpdate`. Pandanglah `useEffect` sebagai cara untuk menyinkronkan sistem eksternal terhadap perubahan $State/Props$.
* **`useRef` adalah kantong memori mutabel yang stabil:** `useRef` mempertahankan referensi identitas objek antar-render tanpa memicu rantai komputasi ulang reconciler.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Berikut adalah siklus eksekusi React Fiber dari Render hingga Effect Execution:

```
[ TRIGGER ] -> State/Prop Update
     │
     ▼
┌────────────────────────────────────────────────────────────────────────┐
│ RENDER PHASE (Concurrent, Pervasive, Pure, Interruptible)               │
│ - Menjalankan komponen fungsi: MyComponent(props)                      │
│ - Membangun WorkInProgress Fiber Tree                                  │
│ - DILARANG: Mutasi Ref, DOM manipulation, side-effects                 │
└────────────────────────────────────────────────────────────────────────┘
     │
     ▼
┌────────────────────────────────────────────────────────────────────────┐
│ COMMIT PHASE - MUTATION SUB-PHASE (Synchronous, Uninterruptible)       │
│ - React merefleksikan perubahan ke Host DOM (appendChild, removeChild) │
│ - React melepaskan (unmount) Ref lama dan mengikat Host Instance baru  │
└────────────────────────────────────────────────────────────────────────┘
     │
     ▼
┌────────────────────────────────────────────────────────────────────────┐
│ COMMIT PHASE - LAYOUT EFFECTS (Synchronous execution)                  │
│ - Eksekusi cleanup `useLayoutEffect` render sebelumnya                │
│ - Eksekusi callback `useLayoutEffect` aktif                            │
│ - Browser BELUM melukis (Paint blocked)                                │
│ - Aman untuk: Mengukur boundingClientRect, mutasi DOM sinkron          │
└────────────────────────────────────────────────────────────────────────┘
     │
     ▼
[ BROWSER PAINT ] -> Frame di-render ke layar monitor (Pixel terlukis)
     │
     ▼
┌────────────────────────────────────────────────────────────────────────┐
│ COMMIT PHASE - PASSIVE EFFECTS (Asynchronous via Post-Message/Task)    │
│ - Eksekusi cleanup `useEffect` render sebelumnya                       │
│ - Eksekusi callback `useEffect` aktif                                  │
│ - Aman untuk: Network call, Subscription, Inisialisasi SDK non-DOM blk │
└────────────────────────────────────────────────────────────────────────┘
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Struktur Internal Fiber Node dan Hook
Di dalam arsitektur React Fiber (V16+ hingga V19), sebuah komponen direpresentasikan sebagai objek `FiberNode`. Setiap *Hook* disimpan dalam senarai berantai (*singly linked list*) yang ditunjuk oleh `fiber.memoizedState`.

```
FiberNode
  ├── memoizedState ───> Hook 1 (useRef)
  │                        ├── memoizedState = { current: DOMElement }
  │                        └── next ───> Hook 2 (useEffect)
  │                                        ├── memoizedState = EffectRecord
  │                                        │     ├── tag = Passive / Layout
  │                                        │     ├── create = fn()
  │                                        │     ├── destroy = fn() | undefined
  │                                        │     └── deps = [dep1, dep2]
  │                                        └── next ───> null
  └── stateNode ───> DOM Element / Class Instance
```

### 2. Anatomi `useRef`
Secara implementasi internal mesin React (`react-reconciler`), pembuatan Ref sangat primitif namun efisien:
```typescript
// Konseptual implementasi internal React reconciler untuk mountRef & updateRef
function mountRef<T>(initialValue: T): { current: T } {
  const hook = mountWorkInProgressHook();
  const ref = { current: initialValue };
  hook.memoizedState = ref;
  return ref;
}

function updateRef<T>(): { current: T } {
  const hook = updateWorkInProgressHook();
  return hook.memoizedState; // Mengembalikan objek wrapper referensi yang sama persis
}
```
Inilah mengapa memutasi `ref.current` bersifat sinkron, tidak memicu *re-render*, dan tetap persisten antar fase render: referensi objek pointer `ref` di `hook.memoizedState` tidak pernah diganti.

### 3. Anatomi `useEffect` & Effect Flags
Setiap pemanggilan `useEffect` membentuk node `Effect` yang disimpan pada linked list sirkular pada `fiber.updateQueue`. 
React mengombinasikan bitwise flags (misal: `HookHasEffect`, `HookPassive`, `HookLayout`) untuk mengontrol eksekusi:
1. **Mount:** Hook didaftarkan, diberi flag `HookPassive | HookHasEffect`.
2. **Update:** React membandingkan array dependensi menggunakan `Object.is`. Jika setidaknya satu dependensi berbeda, React menandai efek tersebut dengan bitmask `HookHasEffect`.
3. **Commit:** React hanya mengeksekusi efek yang memiliki bitmask `HookHasEffect`.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Batas Interoperabilitas Imperatif (Imperative Interop Boundary)
Ketika bekerja dengan SDK eksternal (misal: Canvas Engine, Peta GIS, Code Editor), sistem tersebut memerlukan kontrol langsung terhadap suatu simpul DOM, mempertahankan status internalnya sendiri, dan biasanya menyediakan metode berantai seperti `.destroy()`, `.update()`, atau `.on('event')`.

React mengharuskan kita membangun **Dinding Batas (Boundary)**:
1. **Ref sebagai Penahan DOM Host:** Menyediakan simpul fisik DOM kontainer.
2. **Layout Phase vs Passive Phase Boundary:** Menentukan kapan librari harus diinisialisasi. Jika librari perlu menghitung geometri DOM saat itu juga untuk mencegah kedipan visual (*visual flicker*), gunakan `useLayoutEffect`. Jika inisialisasi berat dan berbasis I/O, gunakan `useEffect`.
3. **Tear-down Idempotency:** Cleanup function *wajib* menghancurkan semua event listener eksternal, membatalkan request, dan melepaskan referensi memori untuk menghindari *leak* saat Strict Mode me-remount komponen dalam hitungan milidetik.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Contoh berikut menunjukkan pola penanganan efek sinkronisasi DOM mentah, penanganan abort controller terhadap network race condition, serta isolasi interop imperatif.

```typescript
import React, { useState, useEffect, useLayoutEffect, useRef } from 'react';

// Tipe untuk data yang diambil
interface ProfileData {
  name: string;
  bio: string;
}

export const SafeProfileFetcher: React.FC<{ userId: string }> = ({ userId }) => {
  const [data, setData] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const bioContainerRef = useRef<HTMLDivElement | null>(null);

  // 1. Asynchronous Side Effect dengan Pola Pembersihan AbortController
  useEffect(() => {
    const abortController = new AbortController();
    setLoading(true);

    async function fetchUserData() {
      try {
        const response = await fetch(`/api/users/${userId}`, {
          signal: abortController.signal,
        });
        if (!response.ok) throw new Error('Network response was not ok');
        const json: ProfileData = await response.json();
        setData(json);
      } catch (err: unknown) {
        if (err instanceof Error && err.name === 'AbortError') {
          // Permintaan dibatalkan karena komponen unmount atau userId berubah: Bukan error
          return;
        }
        console.error('Fetch error:', err);
      } finally {
        if (!abortController.signal.aborted) {
          setLoading(false);
        }
      }
    }

    fetchUserData();

    // Cleanup: Menghentikan request tertunda jika props berubah atau unmount
    return () => {
      abortController.abort();
    };
  }, [userId]);

  // 2. Synchronous DOM Measurement menggunakan useLayoutEffect
  useLayoutEffect(() => {
    if (bioContainerRef.current) {
      // Mengukur dimensi DOM secara sinkron sebelum paint untuk menghindari flicker
      const rect = bioContainerRef.current.getBoundingClientRect();
      if (rect.height > 200) {
        bioContainerRef.current.style.borderColor = 'crimson';
      } else {
        bioContainerRef.current.style.borderColor = 'lightgray';
      }
    }
  }, [data]);

  return (
    <div style={{ padding: '1rem', border: '1px solid gray' }}>
      {loading ? (
        <p>Memuat profil...</p>
      ) : (
        <div>
          <h2>{data?.name}</h2>
          <div
            ref={bioContainerRef}
            style={{ padding: '0.5rem', borderWidth: 2, borderStyle: 'solid' }}
          >
            {data?.bio}
          </div>
        </div>
      )}
    </div>
  );
};
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

* **Baris 13-14 (`const abortController = new AbortController(); setLoading(true);`)**: Diinstansiasi dalam tubuh callback efek. Menghasilkan token sinyal baru setiap kali dependensi `userId` beralih nilai.
* **Baris 18 (`signal: abortController.signal`)**: Mengintegrasikan sinyal pembatalan native fetch API. Ini adalah *imperative-to-declarative bridge* level transport layer.
* **Baris 24-27 (`if (err.name === 'AbortError') return;`)**: Menyaring kegagalan buatan. Komponen mengabaikan error pembatalan sinyal dan mencegah mutasi state liar pada fiber yang telah basi (*stale fiber*).
* **Baris 35-37 (`return () => { abortController.abort(); }`)**: *Destructor* (efek pembersihan). React menjamin baris ini dieksekusi sebelum efek siklus baru dijalankan, mengeliminasi race conditions ketika pemanggilan `userId=2` kembali lebih lambat daripada `userId=3`.
* **Baris 41-51 (`useLayoutEffect(...)`)**: Berjalan secara sinkron setelah mutasi DOM oleh React selesai tetapi sebelum Browser Compositor menggambar piksel (*blocking paint*). Hal ini menjamin bahwa mutasi gaya `style.borderColor` terjadi pada frame yang sama, meniadakan anomali *flash of unstyled content* (FOUC).

---

## SEKSI 09 — STUDI KASUS NYATA
### Integrasi Real-Time Financial Trading Chart Engine (High-Frequency Trading Dashboard)
**Masalah Arsitektural:** Sebuah platform HFT fintech membutuhkan grafik candlestick interaktif berlatar WebGL/Canvas (menggunakan librari imperatif pihak ketiga murni, misal: Lightweight Charts / TradingView Engine). Library ini mengelola kanvas sendiri, memiliki thread rendering sendiri, dan mengonsumsi stream WebSocket data tick berkecepatan 100ms.

**Kebutuhan:**
1. Mengintegrasikan charting engine imperatif ke dalam React component tree.
2. Mencegah Canvas me-reinitiate (flickering/re-allocating GPU contexts) saat props UI React di luar chart (seperti Dark Mode toggle atau Sidebar drawer) berubah.
3. Memastikan pembersihan memory GPU context dan subscription WebSocket bersih total saat user menutup tab chart.
4. Mengekspos API imperatif aman ke komponen induk (misal: `zoomIn()`, `resetView()`) tanpa mengekspos DOM Canvas secara telanjang.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah batas imperatif produksi penuh dengan enkapsulasi via `useImperativeHandle` dan isolasi konteks eksternal.

```typescript
// File: src/components/TradingChartBoundary.tsx
import React, {
  useRef,
  useEffect,
  useLayoutEffect,
  useImperativeHandle,
  forwardRef,
  memo,
} from 'react';

// 1. Kontrak Antarmuka Komponen & Tipe Engine Eksternal
export interface CandleData {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface ChartImperativeHandle {
  resetZoom: () => void;
  exportChartAsBlob: () => Promise<Blob | null>;
}

interface TradingChartProps {
  data: CandleData[];
  theme: 'dark' | 'light';
  onCrosshairMove?: (price: number | null) => void;
}

// Mocking External Imperative Engine API (seperti Lightweight Charts)
class ImperativeChartEngine {
  private container: HTMLElement;
  private options: { theme: string };
  private isDestroyed = false;

  constructor(container: HTMLElement, options: { theme: string }) {
    this.container = container;
    this.options = options;
    this.initCanvas();
  }

  private initCanvas() {
    this.container.innerHTML = `<div class="chart-canvas-mock" style="width: 100%; height: 400px; background: ${
      this.options.theme === 'dark' ? '#1e1e1e' : '#f5f5f5'
    };"></div>`;
  }

  public setData(data: CandleData[]) {
    if (this.isDestroyed) return;
    // Logika transmisi buffer ke WebGL/Canvas
  }

  public applyOptions(options: { theme: string }) {
    if (this.isDestroyed) return;
    this.options = { ...this.options, ...options };
    this.initCanvas();
  }

  public resetViewport() {
    // Logika kalkulasi matriks kamera chart
  }

  public capture(): Promise<Blob | null> {
    return Promise.resolve(new Blob([], { type: 'image/png' }));
  }

  public destroy() {
    this.isDestroyed = true;
    this.container.innerHTML = '';
  }
}

// 2. Komponen Batas Imperatif (Imperative Boundary Component)
export const TradingChartBoundary = memo(
  forwardRef<ChartImperativeHandle, TradingChartProps>(
    ({ data, theme, onCrosshairMove }, ref) => {
      // Simpul DOM yang akan "diserahkan" kepemilikannya ke Engine Imperatif
      const containerRef = useRef<HTMLDivElement | null>(null);
      
      // Instance engine disimpan dalam Ref murni: BUKAN STATE (tidak memicu re-render)
      const engineInstanceRef = useRef<ImperativeChartEngine | null>(null);

      // Callback ref mutable untuk memotong dependensi effect yang volatil
      const crosshairCallbackRef = useRef(onCrosshairMove);
      useLayoutEffect(() => {
        crosshairCallbackRef.current = onCrosshairMove;
      });

      // 3. Batas Lifecycle & Instansiasi Engine (Mount / Destroy Boundary)
      useEffect(() => {
        const hostElement = containerRef.current;
        if (!hostElement) return;

        // Inisialisasi Engine Imperatif
        const engine = new ImperativeChartEngine(hostElement, { theme });
        engineInstanceRef.current = engine;

        // Strict Cleanup Phase
        return () => {
          engine.destroy();
          engineInstanceRef.current = null;
        };
      }, []); // Dependency kosong: Engine hanya dibuat 1x sepanjang masa hidup elemen host

      // 4. Sinkronisasi Data Properti Reaktif Terpisah
      useEffect(() => {
        if (engineInstanceRef.current) {
          engineInstanceRef.current.setData(data);
        }
      }, [data]);

      // 5. Sinkronisasi Konfigurasi UI (Theme)
      useEffect(() => {
        if (engineInstanceRef.current) {
          engineInstanceRef.current.applyOptions({ theme });
        }
      }, [theme]);

      // 6. Mengabstraksikan dan Membatasi Antarmuka via useImperativeHandle
      useImperativeHandle(
        ref,
        () => ({
          resetZoom: () => {
            if (engineInstanceRef.current) {
              engineInstanceRef.current.resetViewport();
            }
          },
          exportChartAsBlob: async () => {
            if (!engineInstanceRef.current) return null;
            return await engineInstanceRef.current.capture();
          },
        }),
        [] // Tidak ada dependency: fungsi delegate mengevaluasi engineInstanceRef yang mutabel secara stabil
      );

      return (
        <div 
          className="chart-wrapper-host" 
          style={{ position: 'relative', width: '100%' }}
        >
          {/* Host node murni: React dilarang merekonsiliasi anak-anak div ini */}
          <div ref={containerRef} style={{ width: '100%', minHeight: '400px' }} />
        </div>
      );
    }
  )
);

TradingChartBoundary.displayName = 'TradingChartBoundary';
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter Evaluasi | `useEffect` | `useLayoutEffect` | `useRef` Mutation (Direct) |
| :--- | :--- | :--- | :--- |
| **Waktu Eksekusi** | Asinkron setelah Paint | Sinkron sebelum Paint | Seketika saat Render / Callback |
| **Dampak Performa** | Non-blocking (High FPS) | Blocking frame rendering | Zero Overhead (O(1)) |
| **Akses Bounding DOM** | Rentan Visual Jitter | Deterministik & Presisi | Tidak relevan jika tanpa commit |
| **Kasus Penggunaan Utama**| Fetch data, subscriptions | Pengukuran DOM, Tooltip CSS positioning | Menyimpan state transient, referensi DOM node |
| **SSR Compatibility** | Aman (Tidak jalan di server) | Memunculkan peringatan SSR | Aman |

---

## SEKSI 12 — EDGE CASES & PITFALLS (Failure Modes & Mitigation)

### 1. The Strict Mode Double Mount Gotcha (React 18 & 19)
Pada mode pengembangan (`React.StrictMode`), React mengeksekusi urutan:
`Mount -> Unmount -> Mount`.
* **Failure Mode:** Librari imperatif menambahkan event listener ke `window` saat setup efek, namun fungsi cleanup tidak mencabutnya. Hasilnya: memory leak berlipat ganda dan bug duplikasi event listener.
* **Mitigasi:** Fungsi pembersihan (*destructor*) wajib bersifat *symmetric*. Jika setup memanggil `subscribe()`, cleanup harus memanggil `unsubscribe()`.

### 2. Mutasi `ref.current` Selama Render Phase
* **Failure Mode:** 
  ```typescript
  function BadComponent() {
    const countRef = useRef(0);
    countRef.current++; // BERBAHAYA! Merusak arsitektur Concurrent Mode
    return <div>{countRef.current}</div>;
  }
  ```
  Pada Concurrent React, render phase dapat dibatalkan, diulang (*re-yield*), atau dijalankan secara bersamaan pada *lane* yang berbeda. Memutasi ref pada render menyebabkan perilaku nondeterministik dan merusak time-travel debugging.
* **Mitigasi:** Pindahkan mutasi ref ke dalam `useEffect`, `useLayoutEffect`, atau *event handler*.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Mistake 1: Mengabaikan Dependency Array (Stale Closures)
```typescript
// SALAH: Stale Closure
useEffect(() => {
  const timer = setInterval(() => {
    console.log(count); // 'count' akan selalu bernilai state saat mount (misal: 0)
  }, 1000);
  return () => clearInterval(timer);
}, []); // Warning ESLint diabaikan
```
**Perbaikan:**
Gunakan functional updates atau masukkan nilai ke dalam dependency array secara jujur:
```typescript
// BENAR
useEffect(() => {
  const timer = setInterval(() => {
    setCount((prev) => prev + 1); // Tidak perlu capture variabel lokal 'count'
  }, 1000);
  return () => clearInterval(timer);
}, []);
```

### Mistake 2: Membaca Layout DOM menggunakan `useEffect`
Membaca elemen layout (seperti `element.offsetWidth`) lalu memperbarui state di dalam `useEffect` akan menghasilkan kedipan visual (*layout thrashing* dan *flash of content*), karena browser telah menyelesaikan render pass pertama sebelum React menginstruksikan perubahan DOM baru.
**Perbaikan:** Gunakan `useLayoutEffect` secara eksklusif untuk mutasi berbasis pembacaan geometris.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Aturan Single-Responsibility Effect:** Pisahkan satu efek besar menjadi beberapa efek kecil yang berfokus pada sinkronisasi variabel independen (lihat Seksi 10, data dan tema dipecah menjadi dua `useEffect`).
2. **Abstraksi Library Eksternal via Custom Hook:** Jangan mengekspos logic instansiasi library langsung di komponen presentasional. Bungkus dalam Hook: `useExternalEngine(containerRef, config)`.
3. **Ref Callback vs Ref Object:** Manfaatkan *Callback Ref* jika Anda butuh bereaksi secara instan ketika node DOM terpasang atau dilepas, alih-alih mengandalkan `useRef` + `useEffect` kosong.

```typescript
// Pola Callback Ref Tingkat Lanjut
const measureRef = useCallback((node: HTMLDivElement | null) => {
  if (node !== null) {
    new ResizeObserver((entries) => {
      // Menangani perubahan ukuran host secara reaktif
    }).observe(node);
  }
}, []);
```

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### 1. Pola 'Event Listener' Tanpa Trigger Re-render
Jika Anda mendengarkan event berkecepatan tinggi (seperti `window.onscroll` atau `mousemove`), hindari melempar nilai ke React State lokal. Simpan nilai ke dalam Ref, dan komunikasikan perubahannya secara imperatif ke elemen target:

```typescript
const scrollPos = useRef(0);

useEffect(() => {
  const onScroll = () => {
    scrollPos.current = window.scrollY;
    // Mutasi gaya elemen tertentu langsung lewat pointer ref tanpa re-render rekursif
    if (headerRef.current) {
      headerRef.current.style.transform = `translateY(${scrollPos.current}px)`;
    }
  };
  window.addEventListener('scroll', onScroll, { passive: true });
  return () => window.removeEventListener('scroll', onScroll);
}, []);
```

### 2. Garbaging Memory pada Boundary Teardown
Pastikan semua instansiasi Canvas 2D/3D melepaskan konteks grafis secara eksplisit:
```typescript
return () => {
  canvasContext.clearRect(0, 0, width, height);
  renderer.dispose(); // Wajib untuk engine seperti Three.js / WebGL
  node.remove();
};
```

---

## SEKSI 16 — KEAMANAN & HARDENING

1. **DOM Injection XSS Boundary:** Saat berinteraksi dengan librari manipulasi teks imperatif (misal Quill, CKEditor), jangan mem-bypass sanitasi. Gunakan DOMPurify sebelum mem-passing HTML mentah ke method imperatif.
   ```typescript
   import DOMPurify from 'dompurify';
   
   // Hardening boundary
   const cleanHTML = DOMPurify.sanitize(externalContent);
   imperativeLib.setContent(cleanHTML);
   ```
2. **Ref Pollution & Leakage:** Hindari mengekspos elemen DOM internal mentah keluar dari komponen melalui `forwardRef` secara terbuka. Gunakan `useImperativeHandle` untuk membatasi aksi manipulasi (prinsip hak istimewa terendah / *Least Privilege*).

---

## SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

Lacak daur hidup efek samping dan kebocoran instansiasi menggunakan *tracing metadata* kustom pada development runtime:

```typescript
useEffect(() => {
  const effectTraceId = crypto.randomUUID();
  performance.mark(`effect-start-${effectTraceId}`);

  // Inisialisasi SDK
  ThirdPartySDK.init();

  return () => {
    performance.mark(`effect-cleanup-${effectTraceId}`);
    performance.measure(
      `Effect-Lifespan: ${effectTraceId}`,
      `effect-start-${effectTraceId}`,
      `effect-cleanup-${effectTraceId}`
    );
    ThirdPartySDK.cleanup();
  };
}, []);
```

Gunakan **React DevTools Profiler** untuk melihat *"Passive Effects"* commit phase bar dan periksa apakah durasi cleanup membebani main thread.

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

* **`useRef(initialValue)`:** Mengembalikan container mutabel `{ current: initialValue }` yang identitas referensinya persisten sepanjang siklus hidup komponen tanpa memicu re-render.
* **`useEffect(fn, deps)`:** Sinkronisasi asinkron pasca-render. Digunakan untuk I/O, API network, analitik, dan langganan event eksternal. Dijalankan *setelah* browser melukis layar.
* **`useLayoutEffect(fn, deps)`:** Sinkronisasi pra-render/paint. Dijalankan *sebelum* browser melukis layar. Wajib digunakan untuk perhitungan geometri DOM dan mutasi visual langsung untuk mencegah *screen flickering*.
* **`forwardRef` & `useImperativeHandle`:** Membangun *Imperative Interop Boundary* yang aman dan terenkapsulasi, mengabstraksikan fungsi eksekusi langsung ke komponen induk.
* **Aturan Emas Boundary:** *Always clean up what you instantiate.* Satu siklus setup harus diimbangi dengan satu siklus teardown yang simetris.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal 1
Kapan `useLayoutEffect` dieksekusi oleh mesin runtime React?
* A. Bersamaan dengan fase eksekusi fungsi komponen (Render Phase).
* B. Secara asinkron setelah browser selesai menggambar elemen ke layar (Post-Paint).
* C. Secara sinkron pada Commit Phase, setelah DOM dimutasi oleh React, tetapi sebelum browser melukis piksel ke layar.
* D. Sebelum WorkInProgress Fiber Tree selesai dibangun.

### Soal 2
Mengapa mutasi langsung properti `ref.current` di dalam badan fungsi utama komponen (*render phase*) dianggap sebagai anti-pattern dalam arsitektur Concurrent React?
* A. Karena akan memicu infinite re-render loop secara otomatis.
* B. Karena Render Phase dapat dibatalkan atau dijalankan berulang kali oleh Reconciler, menghasilkan inkonsistensi data.
* C. Karena `useRef` di-reset ke nilai default setiap kali komponen me-render ulang.
* D. Karena memutasi Ref memerlukan hak istimewa DOM Node yang belum tersedia di memori.

### Soal 3
Perhatikan kode berikut:
```typescript
useEffect(() => {
  const socket = new WebSocket('wss://stream.app/ticks');
  socket.onmessage = (e) => handleData(e.data);
}, []);
```
Apa dampak arsitektural utama kode di atas pada React 18 / 19 dalam lingkungan `StrictMode`?
* A. WebSocket menolak koneksi karena StrictMode memblokir komunikasi I/O.
* B. Terjadi kebocoran memori (memory leak) dan duplikasi koneksi terbuka ganda karena efek pembersihan koneksi ditiadakan.
* C. Browser akan crash seketika karena soket mencoba menulis langsung ke Fiber state.
* D. Hook memicu layout thrashing karena dijalankan pada Layout Phase.

### Soal 4
Tujuan utama penggunaan Hook `useImperativeHandle` yang digabungkan dengan `forwardRef` adalah:
* A. Meningkatkan kecepatan rendering komponen turunan hingga 2 kali lipat.
* B. Memaksa komponen turunan berubah menjadi class component imperatif murni.
* C. Mengenkapsulasi dan membatasi akses imperatif ke DOM instance/method tertentu yang aman untuk dipanggil oleh komponen induk.
* D. Mengotomatisasi penulisan dependency array pada seluruh `useEffect` internal.

### Soal 5
Manakah dari skenario berikut yang **wajib** menggunakan `useLayoutEffect` daripada `useEffect`?
* A. Melakukan panggilan API REST `fetch()` saat komponen selesai dimuat.
* B. Menghubungkan client ke Firebase Cloud Messaging subscription.
* C. Membaca ukuran tinggi (`clientHeight`) sebuah tooltip lalu mengatur posisinya tepat di atas sebuah tombol tanpa kedipan (*jitter*).
* D. Mengirim sinyal event analitik Page View ke server Datadog.

---

### KUNCI JAWABAN & ANALISIS EVALUASI
* **Soal 1: C.** `useLayoutEffect` berjalan sinkron pada commit phase tepat sebelum browser melukis layar, memberikan kesempatan untuk mengukur/mengubah DOM tanpa kedipan visual.
* **Soal 2: B.** Pada Concurrent React, render phase bersifat non-deterministik dan dapat diinterupsi atau diulang. Mutasi ref pada fase ini menciptakan *side-effect* yang merusak integritas state rendering.
* **Soal 3: B.** Tanpa fungsi pembersihan (`return () => socket.close()`), perilaku mount-unmount-mount StrictMode akan membuka dua instance koneksi WebSocket bersamaan dan menelantarkan yang pertama sebagai *memory/resource leak*.
* **Soal 4: C.** Hook ini berfungsi sebagai batas keamanan enkapsulasi agar parent component tidak mendapatkan referensi mutasi DOM mentah tak terbatas, melainkan hanya fungsi delegasi spesifik yang diizinkan.
* **Soal 5: C.** Kalkulasi posisi elemen yang bergantung pada ukuran dinamis DOM membutuhkan kalkulasi sinkron pra-paint agar pengguna tidak melihat posisi awal elemen melompat (*flickering*).

---

## SEKSI 20 — TANTANGAN MANDIRI & PROYEK PRAKTIKUM

### Judul Lab: "Production-Grade Headless Video Player Canvas Bridge"

### Deskripsi Skenario:
Anda ditugaskan membangun komponen batas imperatif tingkat produksi bernama `<ImperativeVideoCanvas />`. Komponen ini harus memetakan feed elemen video HTML5 native ke dalam kanvas WebGL filter engine kustom dengan ketentuan ketat:

### Spesifikasi Teknis:
1. **Host Isolation:** Komponen tidak boleh me-render ulang keseluruhan komponen React ketika timestamp pemutaran video bergerak (60 frame per detik). Manfaatkan `useRef` untuk tracking delta waktu imperatif.
2. **Encapsulated Controls:** Komponen induk harus mampu mengontrol video melalui ref imperatif yang didefinisikan secara eksplisit:
   ```typescript
   export interface VideoPlayerHandle {
     play: () => Promise<void>;
     pause: () => void;
     seek: (seconds: number) => void;
     captureCurrentFrame: () => string; // Base64 Data URL
   }
   ```
3. **Strict Memory Boundary:** Pastikan saat komponen di-unmount, instance `HTMLVideoElement`, stream object, dan WebGL rendering loop (`requestAnimationFrame`) dimatikan dan dibersihkan dari memori thread secara deterministik.
4. **Resilience to Strict Mode:** Uji komponen Anda di dalam lingkungan `<React.StrictMode>`. Komponen harus tetap berfungsi mulus tanpa melempar peringatan *"WebGL Context Lost"* atau error pemutaran video saat terjadi double mount.