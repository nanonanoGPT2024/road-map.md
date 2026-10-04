# Bab 09 Module 01: Profiling, Memory Leaks & Performance Optimization

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** 03-Frontend-and-Mobile
*   **Topik Spesifik:** React Native Performance Engineering
*   **Modul:** Bab 09 Module 01 — Profiling, Memory Leaks & Performance Optimization
*   **Tingkat Kesulitan:** Advanced / Staff Engineer Level
*   **Prasyarat Pengetahuan:** 
    *   Arsitektur Internal React Native (New Architecture: JSI, Fabric, TurboModules).
    *   Siklus Hidup Engine JavaScript (Hermes Bytecode, GC Compaction & Sweeping).
    *   Memori Platform Asli (Android JVM/ART Heap & Native Ashmem/C++ Heap; iOS Objective-C/Swift ARC & Native Mach Virtual Memory).
    *   Pengalaman hands-on menggunakan React Hooks, Context API, dan navigasi aplikasi skala besar.

---

## SEKSI 02 — LEARNING OBJECTIVES

1.  **Mendiagnosis Frame Drops (UI/JS Thread Bottlenecks):** Mengisolasi perbedaan antara bottlenecks pada JavaScript thread (Hermes) dan UI main thread (Choreographer/CADisplayLink) menggunakan React DevTools Profiler, Flipper, dan Android Studio Profiler/Xcode Instruments.
2.  **Menganalisis dan Memitigasi Retained Memory Leaks:** Menemukan siklus referensi (*retain cycles*), listeners yang tidak di-*unbind*, serta *detached window nodes* menggunakan heap memory snapshots di Hermes CLI/Chrome DevTools Protocol dan Xcode Leaks Instrument.
3.  **Mengoptimalkan Rendering Skala Besar:** Mengimplementasikan strategi komputasi virtualisasi mutakhir untuk struktur data masif menggunakan FlashList/Shopify Engine, menghilangkan alokasi objek transien, dan menstabilkan rekursi reconciler.
4.  **Mengimplementasikan Off-Thread Heavy Computations:** Mengalihkan beban kerja kalkulasi berat ke thread terpisah di luar Main JS Thread melalui JSI-based C++ host objects, Web Workers alternatives, atau modul native teroptimasi.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Mental Model: The Distributed Decoupled Runtime

Aplikasi React Native beroperasi sebagai sistem terdistribusi mikro pada satu perangkat keras. Terdapat pemisahan batas fisik memori antara:
1. **JavaScript V8/Hermes Virtual Machine Environment** (Memori terkelola GC).
2. **Native Mobile Environment** (Android ART Garbage Collector dan iOS Automatic Reference Counting).
3. **Hardware Display Subsystem** (V-Sync pulse pada 60Hz/120Hz yang dikelola oleh SurfaceFlinger atau RenderServer).

```
+-------------------------------------------------------------------------+
|                              FRAME DEADLINE                             |
|       60 FPS = 16.67ms per frame   |   120 FPS = 8.33ms per frame       |
+-------------------------------------------------------------------------+
| JAVASCRIPT THREAD (Hermes)         | UI / RENDER THREAD (Host OS)       |
| - Parse Events                     | - Layout Calculations (Yoga / C++) |
| - State Transitions (React Fiber)  | - Draw Calls & GPU Command Buffers |
| - Payload Preparation via JSI      | - View Mutation Tree Commit        |
+-------------------------------------------------------------------------+
```

Jika JavaScript thread membutuhkan waktu 22ms untuk memproses sebuah event reducers atau serialization, event loop tersebut melewatkan frame (*dropped frame*). Jika UI thread terblokir oleh operasi IO sinkron atau bridging traversal berlebih, layar mengalami *stutter* visual (*jank*), memicu *Application Not Responding* (ANR) atau *Watchdog Termination*.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Siklus Frame Rendering & Jalur Akuisisi Telemetri Profiling

```
+-------------+
| Choreographer| (Android) / CADisplayLink (iOS)
+------+------+
       | Menembakkan V-SYNC Tick (setiap 16.6ms / 8.3ms)
       v
+-----------------------------------------------------------------------+
| NATIVE RUNTIME (UI THREAD)                                            |
| 1. Handle Touch Events                                                |
| 2. Enqueue Touch Event ke JSI                                         |
+-----------------------------------+-----------------------------------+
                                    |
                                    v (Non-blocking via C++ JSI Pointer)
+-----------------------------------------------------------------------+
| JAVASCRIPT THREAD (HERMES ENGINE)                                     |
| 3. Hermes Event Loop mengambil event dari MessageQueue                |
| 4. React Fiber Reconciliation (Work Loop: Diffing Virtual DOM)        |
| 5. Mutasi State, Evaluasi Hooks (useMemo, useCallback)                |
| 6. Schedulkan Shadow Tree Mutation (Fabric C++)                       |
+-----------------------------------+-----------------------------------+
                                    |
                                    v (Direct C++ Memory Mutation)
+-----------------------------------------------------------------------+
| SHADOW TREE (C++ CORE - YOGA ENGINE)                                  |
| 7. Layout Metrics Computation (Width, Height, Flexbox Constraints)    |
| 8. Commit & Diffs kalkulasi tata letak ke UI Thread                   |
+-----------------------------------+-----------------------------------+
                                    |
                                    v (Transaction Commit)
+-----------------------------------------------------------------------+
| NATIVE UI THREAD                                                      |
| 9. Mutasi Platform Views (Android View / iOS UIView hierarchy)        |
| 10. Rasterization & GPU Pipeline Execution                            |
| 11. Frame di-swap ke Front Framebuffer (Tampil di Layar)              |
+-----------------------------------------------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Hermes Garbage Collector (Hades)
Hermes menggunakan *Generational, Mostly-Concurrent Garbage Collector* bernama Hades:
*   **Young Generation (Nursery):** Mengalokasikan objek baru dengan skema *bump-pointer allocation*. Siklus hidup pendek dikoleksi dengan jeda STW (*Stop-the-World*) sub-milidetik.
*   **Old Generation:** Objek yang bertahan dipromosikan ke sini. Hades menjalankan penandaan secara paralel (*concurrent background marking*) di thread terpisah bersamaan dengan eksekusi JavaScript thread untuk menghindari jank.
*   **GC Pause Triggers:** Ketika heap jenuh melampaui limit (`max_heap_size`), Hades terpaksa melakukan STW Sweeping penuh, yang dapat memakan waktu 30-100ms dan menyebabkan dropped frames masif.

### 2. JSI Memory Retain Cycle (C++ ke JS Boundaries)
Dalam New Architecture (Fabric), komponen Native berinteraksi melalui JSI:
*   Objek JavaScript direferensikan dalam C++ menggunakan `jsi::Value` atau `jsi::Object`.
*   Jika Host Object native C++ menyimpan `jsi::Value` sebagai `jsi::HostObject` global tanpa siklus *invalidation* eksplisit saat Unmount, objek tersebut tidak dapat di-garbage collect oleh Hermes GC.
*   Jika objek JS tersebut secara simultan mengikat referensi ke Host Object native melalui closures callback, terbentuklah *Cross-Runtimes Cyclic Reference*, yang tidak terlihat oleh Hermes GC maupun ARC/ART GC.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Kebocoran Memori (Memory Leaks) Spesifik React Native

#### 1. Unbound Native Listeners & Singletons
Event emitter platform bawaan (seperti `AppState`, `Dimensions`, `Keyboard`, atau custom native modules) berakar di Java/Obj-C VM root. Callback subscription yang mempertahankan scope closure komponen menyimpan seluruh pohon variabel lokal komponen tersebut dalam memori selamanya.

```typescript
// ANTI-PATTERN: Closure Retains Entire Parent Scope
useEffect(() => {
  const onKeyboardShow = (event: KeyboardEvent) => {
    // Closure menangkap 'heavyDataset' yang diakses di dalam scope
    processData(heavyDataset, event);
  };
  Keyboard.addListener('keyboardDidShow', onKeyboardShow);
  // LUPA: Tidak ada return cleanup () => subscription.remove()
}, []);
```

#### 2. Closures pada Timer dan Async Promises
Memanggil asynchronous fetch atau `setInterval` tanpa membatalkan token/aborsi (melalui `AbortController`) saat unmount komponen menyebabkan objek closure tetap terikat di Microtask Queue Hermes hingga promise selesai atau interval dihentikan.

#### 3. Image Memory Footprint (Bukan Sekadar Ukuran File)
Beban RAM gambar dihitung berdasarkan dimensi resolusi piksel mentah saat didekompresi, bukan ukuran file terkompresi (JPG/PNG/WebP):

$$\text{Konsumsi Memori RAM} = \text{Lebar Pixel} \times \text{Tinggi Pixel} \times 4 \text{ Bytes (RGBA\_8888)}$$

Gambar $4000 \times 3000$ berukuran 1.2 MB di disk akan memakan memori runtime sebesar:
$$4000 \times 3000 \times 4 = 48\,000\,000 \text{ Bytes} \approx 45.77\text{ MB}$$
Jika 10 gambar tersebut dimuat sekaligus di memori native tanpa *downsampling*, perangkat kelas menengah Android akan langsung mengalami **OOM (Out Of Memory) Crash**.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi Custom Hook anti-memory leak untuk melacak dan mengamankan operasi asynchronous serta referensi callback terhadap siklus hidup komponen.

```typescript
// hooks/useSafeAsyncOperation.ts
import { useRef, useEffect, useCallback } from 'react';

interface UseSafeAsyncOperationReturn {
  isMounted: () => boolean;
  runSafeAsync: <T>(asyncTask: () => Promise<T>) => Promise<T | undefined>;
}

export const useSafeAsyncOperation = (): UseSafeAsyncOperationReturn => {
  const isMountedRef = useRef<boolean>(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      // Invalidation mutlak saat unmount
      isMountedRef.current = false;
    };
  }, []);

  const isMounted = useCallback((): boolean => {
    return isMountedRef.current;
  }, []);

  const runSafeAsync = useCallback(
    async <T>(asyncTask: () => Promise<T>): Promise<T | undefined> => {
      try {
        const result = await asyncTask();
        if (!isMountedRef.current) {
          return undefined;
        }
        return result;
      } catch (error) {
        if (!isMountedRef.current) {
          // Swallow atau route ke unmounted boundary telemetry
          return undefined;
        }
        throw error;
      }
    },
    []
  );

  return { isMounted, runSafeAsync };
};
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

*   **Baris 10:** `const isMountedRef = useRef<boolean>(true);` — Menginisialisasi ref boolean mutabel. Properti `useRef` tidak memicu re-render saat nilainya bermutasi dan bertahan sepanjang masa hidup instance komponen.
*   **Baris 12-17:** Blok `useEffect` mengembalikan *cleanup function*. Ketika lifecycle unmount terjadi, `isMountedRef.current = false;` dieksekusi secara sinkron tepat sebelum node komponen dihapus dari UI tree.
*   **Baris 19-21:** Fungsi `isMounted` membungkus status referensi ke dalam callback yang distabilkan (`useCallback`), memungkinkan sub-komponen memeriksa status komponen induk tanpa langganan observer tambahan.
*   **Baris 24-37:** Method `runSafeAsync` mengeksekusi asynchronous microtask via `await`. Setelah eksekusi microtask selesai, eksekusi dilanjutkan hanya jika `isMountedRef.current === true`. Jika komponen telah di-unmount selama operasi jaringan/IO berjalan, hasil dibuang secara aman dari tumpukan memori, memotong rantai closure memory leak ke UI state setters.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Aplikasi Bursa Kripto FinTech (Real-Time Orderbook)
*   **Masalah:** Pada aplikasi bursa kripto tier-1, orderbook memperbarui data via WebSocket dengan frekuensi 50 pesan/detik. Pengguna di perangkat mid-end (misal: Samsung Galaxy A-series) mengalami UI freeze, crash OOM setelah 3 menit di layar orderbook, dan baterai terkuras signifikan.
*   **Akar Masalah (Root Cause):**
    1.  Setiap pesan WebSocket men-trigger deserialisasi JSON di JS thread dan memicu `setState` pada root list orderbook.
    2.  Pohon komponen melakukan *re-render penuh* pada seluruh list (500 baris orderbook) 50 kali per detik.
    3.  Alokasi array objek baru di dalam event loop memicu siklus Hades GC *Stop-The-World* setiap 4 detik.
    4.  Komponen grafik Canvas menahan referensi konteks C++ render tanpa rilis resource saat navigasi pop back.
*   **Metrik Pra-Optimasi:**
    *   JS Frame Rate: 12 FPS.
    *   UI Frame Rate: 28 FPS.
    *   Konsumsi Memori: Naik 4MB/detik hingga crash di 680MB (OOM).
*   **Target Pasca-Optimasi:**
    *   JS Frame Rate: 58-60 FPS konsisten.
    *   UI Frame Rate: 60 FPS konsisten.
    *   Memori: Stabil di angka ~115MB (Flat memory leak profile).

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Solusi performa tinggi menggunakan buffer *Time-Slicing Windowing*, atomisasi mutasi via FlashList, dan kompilasi rendering granular.

```typescript
// components/OrderBookOptimized.tsx
import React, { memo, useRef, useEffect, useState, useCallback } from 'react';
import { View, Text, StyleSheet, LayoutAnimation, Platform } from 'react-native';
import { FlashList, ListRenderItemInfo } from '@shopify/flash-list';

export interface OrderLevel {
  id: string;
  price: number;
  amount: number;
  total: number;
  type: 'ask' | 'bid';
}

interface OrderBookProps {
  streamUrl: string;
}

// 1. Ekstraksi Item Component ter-memoisasi dengan prop komparator presisi
const OrderBookRow = memo(
  ({ item }: { item: OrderLevel }) => {
    return (
      <View style={styles.row}>
        <Text
          style={[
            styles.cell,
            item.type === 'ask' ? styles.askText : styles.bidText,
          ]}
        >
          {item.price.toFixed(2)}
        </Text>
        <Text style={styles.cell}>{item.amount.toFixed(4)}</Text>
        <Text style={[styles.cell, styles.alignRight]}>
          {item.total.toFixed(4)}
        </Text>
      </View>
    );
  },
  (prevProps, nextProps) => {
    // Hindari re-render jika field harga & total identik
    return (
      prevProps.item.id === nextProps.item.id &&
      prevProps.item.amount === nextProps.item.amount &&
      prevProps.item.total === nextProps.item.total
    );
  }
);

export const OrderBookOptimized: React.FC<OrderBookProps> = ({ streamUrl }) => {
  const [orders, setOrders] = useState<OrderLevel[]>([]);
  
  // Menggunakan Ref sebagai Mutable Ring Buffer untuk menghindari GC pressure
  const incomingBufferRef = useRef<OrderLevel[]>([]);
  const frameRequestRef = useRef<number | null>(null);
  const webSocketRef = useRef<WebSocket | null>(null);

  // 2. Scheduler Pembacaan Buffer: Throttling tersinkronisasi dengan Screen Refresh Rate
  const flushBufferToState = useCallback(() => {
    if (incomingBufferRef.current.length > 0) {
      setOrders((prevOrders) => {
        // Terapkan partial mutations atau replace list dengan instansiasi terukur
        const updated = [...incomingBufferRef.current];
        incomingBufferRef.current = []; // Drain buffer
        return updated;
      });
    }
    // Jadwalkan batch flush pada frame berikutnya
    frameRequestRef.current = requestAnimationFrame(flushBufferToState);
  }, []);

  useEffect(() => {
    // Mulai render loop scheduler
    frameRequestRef.current = requestAnimationFrame(flushBufferToState);

    // Setup High-Speed WebSocket Connection
    const ws = new WebSocket(streamUrl);
    webSocketRef.current = ws;

    ws.onmessage = (event: WebSocketMessageEvent) => {
      try {
        const payload: OrderLevel[] = JSON.parse(event.data);
        // MUTASI IN-PLACE PADA BUFFER: Menghindari JS Garbage Collection Cycle berlebih
        incomingBufferRef.current = payload;
      } catch (err) {
        // Drop payload korup tanpa alokasi objek error kompleks
      }
    };

    return () => {
      // TEARDOWN COMPREHENSIVE: Menghindari cross-bridge memory leak
      if (frameRequestRef.current !== null) {
        cancelAnimationFrame(frameRequestRef.current);
      }
      if (webSocketRef.current) {
        webSocketRef.current.onmessage = null;
        webSocketRef.current.onerror = null;
        webSocketRef.current.onclose = null;
        webSocketRef.current.close();
        webSocketRef.current = null;
      }
    };
  }, [streamUrl, flushBufferToState]);

  const renderItem = useCallback(
    ({ item }: ListRenderItemInfo<OrderLevel>) => <OrderBookRow item={item} />,
    []
  );

  const keyExtractor = useCallback((item: OrderLevel) => item.id, []);

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerText}>Price</Text>
        <Text style={styles.headerText}>Amount</Text>
        <Text style={[styles.headerText, styles.alignRight]}>Total</Text>
      </View>
      <FlashList
        data={orders}
        renderItem={renderItem}
        keyExtractor={keyExtractor}
        estimatedItemSize={24}
        drawDistance={150}
        removeClippedSubviews={Platform.OS === 'android'}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0e1118' },
  header: {
    flexDirection: 'row',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderColor: '#262932',
  },
  headerText: { flex: 1, color: '#848e9c', fontSize: 12, fontWeight: '600' },
  row: {
    flexDirection: 'row',
    paddingHorizontal: 12,
    height: 24,
    alignItems: 'center',
  },
  cell: { flex: 1, fontSize: 12, color: '#d1d4dc', fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace' },
  askText: { color: '#f6465d' },
  bidText: { color: '#0ecb81' },
  alignRight: { textAlign: 'right' },
});
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Dimensi Pendekatan | `FlatList` (Bawaan RN Core) | `@shopify/flash-list` | Canvas / Skia Render Engine |
| :--- | :--- | :--- | :--- |
| **Mekanisme Virtualisasi** | Unmount komponen off-screen, menyisakan blank spacer nodes. | **View Recycling Native Platform** (Mirip Android `RecyclerView` & iOS `UICollectionView`). | Total By-Pass Native Views; Direct C++ Pixel Buffer Painting via Skia. |
| **Alokasi Objek & GC** | **Tinggi:** Alokasi/Dealokasi instansiasi komponen baru saat scroll. | **Sangat Rendah:** Menggunakan kembali Host Component yang ada, hanya re-binding props. | **Nol:** Dikelola penuh di native memory heap (GPU Textures). |
| **Blank Cells Saat Fast Scroll** | Sering terlihat jika render JS lambat. | Jarang sekali terjadi karena alokasi view 0 ms. | Tidak ada; rendering sinkron dengan GPU Draw. |
| **Kompleksitas Implementasi** | Rendah (Out of the box). | Menengah (Wajib mendefinisikan `estimatedItemSize` secara presisi). | Tinggi (Kehilangan accessibility bawaan, input handling rumit). |
| **Konsumsi Memori UI Thread** | Membengkak jika `windowSize` besar. | Datar (*Constant Flat Curve*). | Terikat sepenuhnya pada Framebuffer VRAM. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Retained Fast Image Cache Dilemma
*   **Kasus:** Menggunakan library image caching (seperti `react-native-fast-image`) dengan gambar beresolusi tinggi di dalam list daur ulang.
*   **Kegagalan:** Meskipun FlashList mendaur ulang komponen tampilan, native context cache layer tidak melepaskan *decompressed bitmap allocation* di RAM perangkat. Sistem mengalami silent crash dengan exit code `SIGKILL` (High Watermark Memory Violation) dari iOS OS Jetsam.
*   **Mitigasi:** Atur batas maksimum disk/in-memory cache limits pada layer native AppDelegate / MainApplication dan sediakan ukuran canvas tetap (*downsampling target width & height*) sebelum me-render.

### 2. Anonymous Functions & Objek Literal Inline pada Sub-Trees
*   **Kasus:** Menuliskan `style={{ margin: 10 }}` atau `onPress={() => doSomething(id)}` di setiap baris komponen virtual.
*   **Kegagalan:** Setiap evaluasi functional component menghasilkan instansiasi pointer baru di Nursery Heap Hermes. Hal ini membatalkan optimasi `React.memo` (karena alokasi referensi objek baru selalu gagal pada perbandingan kesetaraan identitas `===`).
*   **Mitigasi:** Gunakan `StyleSheet.create` (yang menghasilkan numeric ID statis di bridge) dan delegasikan callback via `useCallback` atau event target bubbling.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. `useCallback` Tanpa Dependensi yang Tepat (Stale Closures)
*   **Kesalahan:** Menambahkan array dependensi kosong `[]` secara serampangan untuk "optimasi", menyebabkan fungsi mengakses variabel dari render siklus lampau.
*   **Solusi:** Gunakan functional state updates (`setVal(prev => prev + 1)`) atau pasang ESLint rule `react-hooks/exhaustive-deps` sebagai *blocking error* di pipeline CI.

### 2. Menggunakan `JSON.stringify` untuk Deep Equality Check di Props Memo
*   **Kesalahan:**
    ```typescript
    export default memo(MyComponent, (prev, next) => {
      return JSON.stringify(prev) === JSON.stringify(next); // ANTI-PATTERN FATAL
    });
    ```
*   **Analisis Kerusakan:** Serialisasi JSON adalah operasi sinkronus pemblokir CPU ($O(N)$ traversal). Biaya serialisasi JSON seringkali jauh lebih lambat daripada waktu yang dibutuhkan React reconciler untuk sekadar melakukan re-render komponen virtual tersebut.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Aktifkan Hermes secara Eksklusif:** Pastikan `hermesEnabled: true` pada `android/app/build.gradle` dan Podfile iOS. Konfigurasikan Hermes Sampling Profiler untuk audit performa berkala.
2.  **Gunakan Native Driver untuk Animasi Komputasi:** Gunakan library Reanimated v3/v4 yang mengeksekusi worklets langsung pada UI thread runtime melalui JSI tanpa menyentuh JS MessageQueue thread.
3.  **Audit Render Frequency Limits:** Terapkan alat ukur dev-dependency seperti `@welldone-software/why-did-you-render` pada tahap development testing untuk mendeteksi re-render yang tidak disengaja secara real-time.
4.  **Terapkan Image Downsampling:** Selalu terapkan properti pembatasan ukuran native decoding buffer pada elemen gambar:
    ```typescript
    <Image
      source={{ uri: item.imageUrl }}
      style={{ width: 100, height: 100 }}
      // Android Native Level Resizing: Dekompresi hanya sebesar resolusi target
      resizeMethod="resize" 
    />
    ```

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### Optimasi Hermes Engine: Memory-Mapped Files (mmap)
Hermes mengompilasi JavaScript ke bytecode (`.hbc`) secara *ahead-of-time* (AOT). Bytecode ini di-load ke dalam memori native menggunakan pemanggilan kernel `mmap()`.
*   **Efisiensi:** Berkas bytecode tidak dialokasikan di RAM aktif. Kernel OS dapat langsung menukar (*page-out*) instruksi bytecode dari memori ketika RAM rendah tanpa memicu OOM, dan membaca kembali (*page-in*) saat dibutuhkan secara instan.
*   **Penerapan:** Hindari pemanggilan `eval()` atau `new Function()` yang memaksa engine beralih ke kompilasi dinamis runtime di RAM, yang membatalkan optimasi native paging bytecode.

---

## SEKSI 16 — KEAMANAN & HARDENING

Saat mengoptimalkan performa, memory dumps dan trace profiles rentan mengekspos data sensitif:
1.  **Purge PII dari Memory Snapshots:** Heap profiler Hermes merekam seluruh string flat di dalam heap. Pastikan data sensitif seperti access token, nomor kartu kredit, atau private key didekripsi seperlunya di memori, dienkapsulasi menggunakan primitive pointers, dan segera ditimpa (*zeroed out*) jika memungkinkan.
2.  **Nonaktifkan Hermes Profiling Endpoints di Release Build:** Pastikan port Chrome DevTools Protocol (default: `8081` atau native debugging sockets) sepenuhnya mati (*stripped*) dari binary kompilasi rilis produksi.
    ```groovy
    // android/app/build.gradle
    project.ext.react = [
        enableHermes: true,
        // Pastikan flags debugging terisolasi
        hermesFlagsRelease: ["-O", "-output-source-map"]
    ]
    ```

---

## SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

### Menangkap Hermes Sampling Profiler Secara Terprogram

Untuk mendiagnosis masalah performa yang hanya muncul di lingkungan produksi:

```typescript
// utils/performanceProfiler.ts
import { Profiler } from 'react-native';

export class AppProfilerSession {
  private static isRunning = false;

  public static startTrace(): void {
    if (__DEV__ || (global as any).HermesInternal) {
      if (!this.isRunning) {
        (global as any).HermesInternal?.enableSamplingProfiler();
        this.isRunning = true;
        console.log('[PROFILER] Trace Hermes diinisialisasi.');
      }
    }
  }

  public static stopAndExportTrace(): string | null {
    if (this.isRunning && (global as any).HermesInternal) {
      // Dump trace file path
      const filePath = `/data/user/0/com.app/cache/hermes_trace_${Date.now()}.cpuprofile`;
      (global as any).HermesInternal?.dumpProfile(filePath);
      (global as any).HermesInternal?.disableSamplingProfiler();
      this.isRunning = false;
      console.log(`[PROFILER] Trace file tersimpan di: ${filePath}`);
      return filePath;
    }
    return null;
  }
}
```

Trace yang dihasilkan dapat dikonversi ke format yang kompatibel dengan Chrome Tracing menggunakan CLI:
```bash
npx react-native hermes-profile-transformer <profile-input.cpuprofile> <output-converted.json>
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

*   **UI Thread Drop:** Masalah pada native layout, draw calls GPU yang terlalu padat, atau rendering view hierarchy yang terlalu dalam (> 15-20 level).
*   **JS Thread Drop:** Eksekusi task synchronous JS > 16.6ms, komputasi loops berat, serialization JSON raksasa, atau siklus reconciler React yang berlebihan.
*   **Leak Detection Checkpoints:**
    1.  Apakah subscription global memiliki fungsi dereferensiasi/pembersihan (`return () => sub.remove()`)?
    2.  Apakah objek ref (`useRef`) menyimpan node instance platform yang sudah di-unmount?
    3.  Apakah timer (`setTimeout`, `setInterval`, `requestAnimationFrame`) dihentikan saat siklus hidup selesai?
*   **Golden Rule Virtualisasi:** Gunakan `FlashList` sebagai standar utama list virtualisasi. Pastikan prop `estimatedItemSize` akurat sesuai tinggi layout rata-rata untuk mencegah layout shift.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### 1. Pilihan Ganda: Evaluasi Hades GC
Apa implikasi performa dari arsitektur *mostly-concurrent* pada Hades Garbage Collector di Hermes dibandingkan dengan Mark-and-Sweep konvensional?
*   A. Hades menghapus seluruh Stop-The-World pauses menjadi tepat 0 milidetik dalam segala skenario.
*   B. Hades menandai objek Old Generation di background thread, mengurangi waktu jeda Stop-the-World secara signifikan pada JS thread.
*   C. Hades mengeksekusi kompilasi JavaScript runtime langsung ke native machine assembly ARM tanpa alokasi heap.
*   D. Hades hanya mengalokasikan memori pada stack perangkat keras dan mematikan heap management.

### 2. Pilihan Ganda: Image Decoding Memory
Sebuah gambar JPEG berukuran file 500 KB di disk memiliki dimensi resolusi $2048 \times 1536$ piksel. Berapa estimasi RAM yang dialokasikan oleh Native Raster Engine saat gambar tersebut didekompresi sepenuhnya ke layar tanpa proses downsampling?
*   A. ~500 KB
*   B. ~3.14 MB
*   C. ~12.58 MB
*   D. ~1.50 MB

### 3. Kasus Diagnosis: Memory Profiler
Saat menganalisis snapshot heap Chrome DevTools untuk aplikasi React Native, Anda menemukan bahwa jumlah objek `Closure` meningkat secara linear setiap kali navigasi bolak-balik antara Screen A dan Screen B dilakukan. Objek penahan (*retaining path*) teratas menunjukkan akar pada `EventEmitter` modul native. Apa penyebab utama kebocoran tersebut?
*   A. Screen B tidak dibungkus dengan komponen `React.memo`.
*   B. Hermes tidak mendukung eksekusi Native Event Emitters.
*   C. Listener event di dalam Screen B tidak melepaskan referensi subscription saat komponen di-unmount.
*   D. Garbage Collector Android ART mengalami crash tersembunyi.

### 4. Pilihan Ganda: Virtualisasi List
Mengapa `@shopify/flash-list` menghasilkan penggunaan memori yang jauh lebih stabil dan frame drop yang lebih rendah daripada `FlatList` bawaan pada scroll yang cepat?
*   A. FlashList menghapus seluruh item list dan tidak pernah me-render ulang item di luar layar.
*   B. FlashList mendaur ulang (*recycles*) platform native views yang sudah ada alih-alih menghancurkan dan mengalokasikan ulang elemen DOM/Views baru.
*   C. FlashList menjalankan React Fiber Reconciler langsung di dalam GPU Shaders.
*   D. FlashList mengompresi data list menggunakan enkripsi zip sebelum diproses.

### 5. Analisis Kode: Identifikasi Memory Leak
Tinjau potongan kode berikut:
```typescript
useEffect(() => {
  const channel = createStreamingChannel(channelId);
  channel.onData((data) => {
    setData((current) => [...current, data]);
  });
}, [channelId]);
```
Apa potensi *resource leak* terburuk yang ada pada kode di atas jika props `channelId` berubah 10 kali secara dinamis?
*   A. React akan melempar fatal error karena dependensi array tidak memiliki `setData`.
*   B. Channel sebelumnya tidak ditutup/dibersihkan, menghasilkan 10 instance koneksi streaming paralel yang terus memperbarui state dan menahan referensi instance komponen di memori.
*   C. Operator spread `[...current, data]` akan memblokir main thread secara permanen.
*   D. Hermes akan menolak alokasi memori untuk array yang diperbarui.

---

### Kunci Jawaban & Analisis Evaluasi

1.  **Jawaban: B.** Hades menjalankan proses *marking* untuk *Old Generation* pada background thread secara konkuren dengan eksekusi JS, sehingga meminimalkan jeda *Stop-The-World* (STW) hanya pada inisiasi dan finalisasi singkat.
2.  **Jawaban: C.** Memori gambar pada RAM dihitung: $2048 \times 1536 \times 4 \text{ bytes} = 12\,582\,912 \text{ bytes} \approx 12.58\text{ MB}$, terlepas dari kompresi file di disk.
3.  **Jawaban: C.** Listener yang tidak dilepas mempertahankan closure scope fungsi callback, yang pada gilirannya menahan seluruh referensi memori Screen B dari siklus pengumpulan Garbage Collector.
4.  **Jawaban: B.** Konsep recycling native cell views menghindari alokasi baru dan dekonstruksi memori secara berulang pada UI thread dan platform layout engine.
5.  **Jawaban: B.** Tanpa cleanup function yang menutup `channel` lama saat `channelId` berubah, koneksi lama tetap aktif di background dan mempertahankan referensi closure ke `setData`, memicu kebocoran memori dan konsumsi bandwidth ganda.

---

## SEKSI 20 — TANTANGAN MANDIRI & PROYEK PRAKTIKUM

### Proyek Praktikum: Large-Scale Infinite Feed & Profiling Audit

#### Sasaran Tugas:
Bangun sebuah aplikasi prototipe katalog e-commerce berperforma tinggi dengan dataset masif (10.000 item katalog sintetis) yang harus berjalan lancar pada 60/120 FPS tanpa frame drop dan dengan profil memori yang stabil.

#### Spesifikasi Fungsional & Teknis:
1.  **Implementasi Virtualisasi:**
    *   Gunakan `@shopify/flash-list`.
    *   Tampilkan grid dua kolom yang berisi data gambar, judul, harga, dan rating.
    *   Wajib menerapkan *dynamic view recycling* dengan toleransi error layout 0 px.
2.  **Optimasi Aset Visual:**
    *   Simulasikan downsampling gambar lokal atau remote menggunakan properti decoding dimensi terukur.
    *   Batasi resolusi rendering maksimal sesuai densitas layar perangkat ($Width \times PixelRatio$).
3.  **Stress Testing Memory Leak Harness:**
    *   Buat tombol "Auto-Navigator" buatan yang melakukan siklus `Push` dan `Pop` halaman