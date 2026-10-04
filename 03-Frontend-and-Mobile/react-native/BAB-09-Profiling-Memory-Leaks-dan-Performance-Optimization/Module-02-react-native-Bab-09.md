# BAB 09: Profiling, Memory Leaks, dan Performance Optimization
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- Mengidentifikasi, mengisolasi, dan memitigasi kebocoran memori (*memory leaks*) pada runtime JavaScript (Hermes VM) dan native layer (Android ART/JVM dan iOS Mach/Objective-C/Swift runtime).
- Membedah internal arsitektur memori React Native New Architecture (Fabric Renderer, TurboModules, Bridgeless Mode, dan C++ JSI runtime lifecycle).
- Mengoperasikan tooling profiling tingkat lanjut: Hermes Sampling Profiler, Android Studio Memory Profiler, Xcode Instruments (Allocations, Leaks, VM Tracker), dan Perfetto/Systrace.
- Merancang arsitektur komponen berperforma tinggi yang bebas dari *retain cycles*, *dangling pointers*, dan pemborosan alokasi memori heap.
- Mengimplementasikan sistem observabilitas performa produksi (APM, OOM Tracking, Frame Drop metrics) dengan presisi tingkat enterprise.

---

### 2. Prerequisite
Untuk menyerap materi ini secara optimal, Anda harus memahami:
- Arsitektur dasar React Native New Architecture: JSI (JavaScript Interface), Fabric, TurboModules.
- Pengetahuan runtime C++ (RAII, `std::shared_ptr`, `std::weak_ptr`, reference counting).
- Manajemen memori dasar: Stack vs Heap, Mark-and-Sweep Garbage Collection, dan Automatic Reference Counting (ARC) di iOS.
- Konfigurasi React Native CLI, Android SDK (NDK), dan Xcode build tools.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Hermes Garbage Collector & Memory Allocation Lifecycles
Hermes menggunakan arsitektur Garbage Collector (GC) generasi berbasis *generational compaction* yang dioptimalkan untuk perangkat mobile berkemampuan terbatas. 

```
+-------------------------------------------------------------------------+
|                              Hermes VM                                  |
|                                                                         |
|  Young Generation (Nursery)               Old Generation (Tenured)      |
|  +---------------------------+            +---------------------------+ |
|  | Transient Objects         | --Promote->| Long-lived Objects        | |
|  | Fast allocation via bump- |            | Segment-based allocation  | |
|  | pointer                   |            | Card table marking        | |
|  +---------------------------+            +---------------------------+ |
|               |                                         |               |
|               v                                         v               |
|       YG Sweep / Evacuate                       Mark-Compact GC         |
+-------------------------------------------------------------------------+
                                    | JSI
+-------------------------------------------------------------------------+
| C++ Runtime Layer (ReactCommon / Fabric)                                |
| - jsi::HostObject references                                            |
| - ShadowTree Node instances (C++ ref-counted via std::shared_ptr)       |
+-------------------------------------------------------------------------+
                                    | JNI / Objective-C++
+-------------------------------------------------------------------------+
| Native Platform Host (Android ART / iOS Darwin)                         |
| - Android: Bitmaps, Native View Hierarchy (ViewGroup)                  |
| - iOS: CoreAnimation Layers, UIView/UIWindow, CALayer backing store     |
+-------------------------------------------------------------------------+
```

1. **Young Generation (YG / Nursery):** Alokasi objek JS baru terjadi di sini secara linear (*bump pointer*). Siklus hidup sangat pendek. Ketika nursery penuh, dilakukan *NCGC (Nursery Collect Garbage)* yang menyalin objek yang masih bertahan ke *Old Generation*.
2. **Old Generation (OG / Tenured):** Menyimpan objek jangka panjang. Ketika ambang batas heap terlampaui, Hermes mengeksekusi *Mark-Compact GC* (MCGC) atau *Full GC*. Jika terjadi fragmentasi berlebih, proses *compaction* menggeser objek di memori fisik untuk menyatukan ruang bebas.
3. **WeakReferences & Finalizers:** Hermes mengelola pointer *HostObject* via JSI. Objek C++ yang dibungkus oleh JSI `HostObject` hanya akan dihancurkan ketika garbage collector Hermes memicu *finalizer* pada objek JS wrapper tersebut. Keterlambatan siklus GC di JS dapat menyebabkan retensi memori native yang masif (*Native Memory Drag*).

#### 3.2 Shadow Tree, Fabric Node, dan Retain Cycles
Pada New Architecture (Fabric):
- Setiap elemen UI memiliki representasi triplet: **React Element (JS)** $\leftrightarrow$ **ShadowNode (C++)** $\leftrightarrow$ **Platform View (Java/Obj-C)**.
- `ShadowNode` di C++ bersifat *immutable*. Setiap perubahan state memicu pembuatan clone `ShadowNode` baru, membentuk *Shadow Tree* baru yang kemudian di-*commit*, di-*calculate layout* (Yoga), dan di-*mount* ke Native View.
- **Titik Kebocoran Kritis:** Jika event callback native menyimpan referensi kuat (`std::shared_ptr` atau strong Objective-C block / Android lambda) ke wrapper C++ yang memegang `jsi::Value` atau Native View instance yang seharusnya sudah di-*unmount*, satu cabang penuh Shadow Node dan backing Native View tidak akan bisa di-garbage collect.

#### 3.3 Bridge vs Bridgeless JSI Boundary Leaks
- **Old Bridge Architecture:** Data diserialisasi menjadi string JSON asinkron. Kebocoran memori native umumnya disebabkan oleh event listener yang tidak di-*unregister* di `NativeModules`, meninggalkan referensi instance native di memory heap Java/Obj-C.
- **Bridgeless JSI Architecture:** JavaScript memegang referensi langsung via memory pointer ke C++ struct/class. Kesalahan dalam manajemen referensi C++ (misal: siklus circular `std::shared_ptr<A>` merujuk `std::shared_ptr<B>` dan sebaliknya) tidak dapat dideteksi oleh Hermes GC maupun JVM/ARC. Hal ini menghasilkan **Silent Zombie Memory Allocations**.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Old Arch / Naive Profiling) | Pendekatan Enterprise (New Arch / Deep Profiling) |
| :--- | :--- | :--- |
| **Pendeteksian GC** | Mengandalkan peringatan `console.warn` atau Crashlytics saat crash OOM. | Tracking alokasi real-time via V8/Hermes Memory Tracing, Perfetto trace slices, dan native instrumentation. |
| **Ruang Lingkup Analisis** | Hanya memeriksa JavaScript Heap di Chrome DevTools Inspector. | Analisis komprehensif lintas batas: JS Heap (Hermes) + C++ Heap (JSI) + Native Heap (ART/Mach). |
| **Mitigasi Retensi Native** | Menghapus interval `useEffect` sederhana. | Audit alokasi C++ `HostObject`, pembatalan task concurrency native, dekonstruksi RAII pattern. |
| **Lifecycle Hooks** | Polling state tanpa cleanup token. | AbortController propagation, lifecycle-bound unsubscription, weak-referencing closures. |

- **Why:** Pada platform mobile kelas enterprise, kebocoran memori sebesar 20MB–50MB dapat menyebabkan OS (khususnya low-end Android dengan `dalvik.vm.heapgrowthlimit` ketat, misal 192MB) langsung mengeksekusi LMK (*Low Memory Killer*).
- **What:** Modul ini menetapkan protokol eliminasi kebocoran memori secara deterministik melalui profiling multi-layer runtime, audit C++ JSI object graph, dan standardisasi kode produksi.

---

### 5. How (Workflow Profiling Detail)

#### Fase 1: Isolasi Masalah dengan Hermes Sampling Profiler & DevTools
1. Jalankan aplikasi pada mode release/profile (jangan gunakan mode debug karena interpretasi debugger menambahkan overhead alokasi stack):
   ```bash
   npx react-native run-android --variant=release
   ```
2. Tangkap Hermes CPU & Memory Profile via ADB:
   ```bash
   adb shell input keyevent 82 # Buka Dev Menu
   # Atau via hermes-engine CLI profile dump
   adb pull /data/data/com.enterpriseapp/files/sampling-profile.cpuprofile .
   ```
3. Buka Chrome DevTools (`chrome://inspect`) dan visualisasikan memory heap snapshot. Identifikasi constructor objek JS yang jumlah alokasinya (*retained size*) terus meningkat secara monoton setelah navigasi bolak-balik (Pola Sawtooth yang naik tanpa kembali ke baseline).

#### Fase 2: Audit Native Memory Leak (Android Studio Memory Profiler)
1. Sambungkan Android Studio ke proses release aplikasi yang menyertakan debug symbols (`jniLibs`).
2. Buat alur uji (Record Native Allocations):
   - Buka Screen target $\rightarrow$ Lakukan interaksi $\rightarrow$ Kembali ke Screen awal.
   - Paksakan Garbage Collection (Force GC) di Android Studio.
3. Analisis **Capture Heap Dump**:
   - Filter berdasarkan package aplikasi Anda.
   - Cari instance yang bocor: `ReactContext`, `FabricUIManager`, atau custom `ViewManagers`.
   - Gunakan fitur **Go to GC Root** untuk menelusuri rantai referensi yang menahan objek.

#### Fase 3: Audit Native Memory Leak (Xcode Instruments)
1. Buka workspace via Xcode $\rightarrow$ `Product` $\rightarrow$ `Profile` (Cmd + I).
2. Pilih template **Allocations** dan **Leaks**.
3. Gunakan **Generation Analysis**:
   - Tekan tombol **Mark Generation** saat aplikasi berada di baseline screen.
   - Navigasi ke screen target, lalu navigasi kembali.
   - Tekan **Mark Generation** kedua.
   - Ulangi 3–5 kali. Jika setiap generasi menyisakan pertumbuhan alokasi (`Growth > 0`), telusuri *Heapshot* untuk menemukan *Malloc* block yang tidak di-*free*.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Hotel Tanpa Pembersihan Kamar (The Leaky Hotel)
Bayangkan Hermes VM adalah **Resepsionis Hotel**, C++ JSI adalah **Manajer Operasional**, dan Platform Native (Android/iOS) adalah **Kamar Fisik Hotel**.
- Ketika tamu (komponen JS) check-in, resepsionis memesan kamar fisik via manajer operasional.
- Saat tamu check-out (komponen di-*unmount*), resepsionis menandai bahwa tamu telah pergi. Namun, jika manajer operasional (C++ JSI) masih menyimpan daftar referensi kunci kamar (`strong pointer`), kamar fisik tetap terkunci dan tidak pernah dibersihkan oleh tim *cleaning service* (Native GC / ARC).
- Akibatnya, meskipun di sistem resepsionis terlihat kosong, hotel fisik kehabisan kamar nyata hingga bangunan terpaksa ditutup paksa oleh Satpol PP (OS Low Memory Killer).

#### Diagram Alur GC Multi-Runtime Boundary
```
[JavaScript Heap (Hermes)]
       |
       | (1) jsi::Object holding HostObject pointer
       v
+===================== JSI BOUNDARY =====================+
       |
       | (2) std::shared_ptr<NativeTurboModuleState>
       v
[C++ Runtime / Fabric Engine]
  |               ^
  | (3) Retains   | (4) PROBLEM: Retained circular lambda closure
  v               |
[Platform Native Layer (Android ART / iOS Darwin ARC)]
  - Context / Activity Reference
  - Native UI Components (e.g. SurfaceView, Heavy Bitmaps)
  - Result: Android Activity Leaks, Native OOM Crash
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Deteksi dan Pembersihan Event Retain Cycle
Kode anti-pattern yang menahan referensi instance komponen secara permanen:

```typescript
// ANTI-PATTERN: Closure Leak via Native EventEmitter
import React, { useEffect, useState } from 'react';
import { NativeEventEmitter, NativeModules, Text, View } from 'react-native';

const { TelemetryModule } = NativeModules;
const telemetryEmitter = new NativeEventEmitter(TelemetryModule);

export const BadSensorComponent: React.FC = () => {
  const [data, setData] = useState<number>(0);

  useEffect(() => {
    // KESALAHAN: Callback memegang referensi ke state setData,
    // dan subscription tidak dibersihkan saat unmount.
    telemetryEmitter.addListener('onSensorChanged', (event) => {
      setData(event.value);
    });
  }, []); // Emitter tetap hidup di native layer membawa closure component

  return <View><Text>Sensor: {data}</Text></View>;
};
```

Solusi produksi yang aman secara deterministik:

```typescript
// PRODUCTION-READY: Safe Unsubscription Pattern
import React, { useEffect, useState } from 'react';
import { NativeEventEmitter, NativeModules, Text, View } from 'react-native';

const { TelemetryModule } = NativeModules;
const telemetryEmitter = new NativeEventEmitter(TelemetryModule);

export const GoodSensorComponent: React.FC = () => {
  const [data, setData] = useState<number>(0);

  useEffect(() => {
    let isMounted = true;
    
    const subscription = telemetryEmitter.addListener(
      'onSensorChanged',
      (event: { value: number }) => {
        if (isMounted) {
          setData(event.value);
        }
      }
    );

    return () => {
      isMounted = false;
      subscription.remove(); // Memutus referensi closure dari Native Layer
    };
  }, []);

  return <View><Text>Sensor: {data}</Text></View>;
};
```

#### 7.2 Practical Example: Enterprise Custom Hook untuk Mengamankan Async Tasks & JSI Subscriptions
Implementasi custom lifecycle hook yang mengabstraksi pencegahan kebocoran memori pada network call, synchronous listener, dan native task concurrency.

```typescript
// hooks/useSafeAsyncLifecycle.ts
import { useEffect, useRef, useCallback } from 'react';

interface UseSafeAsyncLifecycleResult {
  runSafeAsync: <T>(promiseFactory: (signal: AbortSignal) => Promise<T>) => Promise<T | null>;
  isMounted: () => boolean;
}

export function useSafeAsyncLifecycle(): UseSafeAsyncLifecycleResult {
  const isMountedRef = useRef<boolean>(true);
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    isMountedRef.current = true;
    abortControllerRef.current = new AbortController();

    return () => {
      isMountedRef.current = false;
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
    };
  }, []);

  const isMounted = useCallback(() => isMountedRef.current, []);

  const runSafeAsync = useCallback(
    async <T>(promiseFactory: (signal: AbortSignal) => Promise<T>): Promise<T | null> => {
      if (!abortControllerRef.current) {
        abortControllerRef.current = new AbortController();
      }
      
      const signal = abortControllerRef.current.signal;

      try {
        const result = await promiseFactory(signal);
        if (!isMountedRef.current) {
          return null;
        }
        return result;
      } catch (error: unknown) {
        if (signal.aborted || !isMountedRef.current) {
          // Swallow error jika unmounted untuk mencegah unhandled rejection pada zombie view
          return null;
        }
        throw error;
      }
    },
    []
  );

  return { runSafeAsync, isMounted };
}
```

Implementasi pada komponen Consumer:

```typescript
// components/UserProfileEngine.tsx
import React, { useState, useEffect } from 'react';
import { View, Text, ActivityIndicator } from 'react-native';
import { useSafeAsyncLifecycle } from '../hooks/useSafeAsyncLifecycle';

interface UserData {
  id: string;
  name: string;
}

export const UserProfileEngine: React.FC<{ userId: string }> = ({ userId }) => {
  const [user, setUser] = useState<UserData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const { runSafeAsync } = useSafeAsyncLifecycle();

  useEffect(() => {
    setLoading(true);
    runSafeAsync(async (signal) => {
      const response = await fetch(`https://api.enterprise.com/users/${userId}`, {
        signal,
      });
      const data: UserData = await response.json();
      return data;
    }).then((result) => {
      if (result) {
        setUser(result);
        setLoading(false);
      }
    });
  }, [userId, runSafeAsync]);

  if (loading) return <ActivityIndicator testID="loading-indicator" />;
  if (!user) return null;

  return (
    <View>
      <Text>{user.name}</Text>
    </View>
  );
};
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
- **Aplikasi:** SuperApp FinTech dengan $10M+$ Monthly Active Users (MAU).
- **Masalah:** Crash-free sessions anjlok ke 93.4% pada perangkat Android tier rendah (RAM 2GB–3GB, Android 10–12).
- **Gejala Crash:** Laporan Crashlytics didominasi oleh `OutOfMemoryError: Failed to allocate a X-byte allocation with Y free bytes and Z until OOM`. Crash terjadi setelah pengguna menjelajahi infinite feed katalog promo investasi selama 5–10 menit.

#### Root Cause Analysis (RCA)
1. **Analisis Heap Dump:** Menggunakan Android Studio Memory Profiler, ditemukan 142 instance `BitmapDrawable` tersimpan di heap, menahan lebih dari 380MB native memory.
2. **Penelusuran Retain Path:**
   - Komponen list menggunakan wrapper kustom di atas native image component.
   - Komponen tersebut menggunakan global singleton event emitter untuk memonitor status scroll dan visibilitas analitik.
   - Handler listener didaftarkan di dalam komponen tanpa memanggil `.remove()` di unmount phase.
   - Listener closure mereferensikan instance shadow node/platform context secara sirkular.

```
[Global AnalyticsManager Singleton]
   └── listeners array
        └── Listener Closure
             └── Capture: context (Android Activity)
                  └── WindowManager
                       └── DecorView
                            └── Fabric Component Hierarchy (Bitmaps Cached)
```

#### Remediasi Arsitektur
1. **Pemutusan Circular Reference:** Mengubah registrasi listener pada Analytics Module menjadi `WeakReference` pada layer Java/Kotlin NativeModule dan menggunakan ID listener berbasis integer token yang dapat di-*unregister* secara deterministik dari C++ core.
2. **Implementasi Virtualisasi Ketat:** Migrasi dari naive list implementasi ke FlashList (`@shopify/flash-list`) dengan setelan `estimatedItemSize` presisi dan membatasi `maxToRenderPerBatch`.
3. **Decoupling Bitmap Memory:** Mengonfigurasi library gambar native (Fresco/Glide) untuk menggunakan memory cache pool yang mengosongkan diri secara agresif saat menerima OS memory warning (`ComponentCallbacks2.TRIM_MEMORY_RUNNING_CRITICAL`).

#### Hasil Metrik
- Crash-Free Rate meningkat dari **93.4%** menjadi **99.85%**.
- Rata-rata memory footprint pada Android tier bawah turun dari **410MB** ke **118MB**.
- Alokasi Native Bitmaps turun drastis hingga **74%** saat scrolling intensif.

---

### 9. Trade-offs

| Pendekatan / Solusi | Keuntungan (Pros) | Biaya / Konsekuensi (Cons) | Dampak Latensi & Performa |
| :--- | :--- | :--- | :--- |
| **Object Pooling (Reusable Elements)** | Menekan alokasi memory heap baru; GC cycle sangat jarang terjadi. | Kompleksitas tinggi dalam mereset internal state objek secara manual; rawan UI bug "stale state". | Mengurangi CPU overhead saat rendering list yang sangat panjang. |
| **Agresif Native Image Cache Eviction** | Memori native bebas dari OOM; footprint RAM stabil di batas aman. | Re-fetching / re-decoding gambar saat list di-scroll balik ke atas; konsumsi bandwidth/CPU meningkat. | Peningkatan risiko visual flickering (blank placeholder) sementara saat scroll cepat. |
| **WeakRef / WeakMap untuk Listener** | Mengurangi potensi memory leak secara otomatis jika engineer lupa membersihkan resource. | Garbage collection timing tidak dapat diprediksi secara deterministik; sulit di-debug jika referensi hilang tiba-tiba. | Sedikit overhead micro-level saat engine menyelesaikan reference tracking. |
| **Full Immutability Shadow Clones (Fabric)** | Thread-safe UI rendering; arsitektur concurrent UI modern tanpa race condition. | Peningkatan alokasi memori C++ heap transient jangka pendek; memicu Nursery GC lebih sering. | Latensi JS thread sangat minim, namun memerlukan throughput memori RAM yang stabil. |

---

### 10. Common Mistakes & Troubleshooting

#### Mistake 1: Lingkup Closure yang Menahan Instance View (Stale Scope Leak)
- **Problem:** Menulis callback event di hook `useEffect` atau `useCallback` yang meng-capture state/props lokal tanpa dependency array yang tepat, atau passing callback inline ke instance TurboModule singleton.
- **Deteksi:** Periksa via DevTools Memory snapshot. Cari string nama komponen Anda di tab *Summary* -> ketik nama komponen di filter class -> jika instance bertambah terus padahal layar sudah ditutup, closure menahan instance tersebut.
- **Solusi:** Gunakan cleanup function untuk memutuskan capture context, atau manfaatkan `useRef` yang di-nullify pada saat cleanup.

#### Mistake 2: Retensi Timer dan Polling Interval Global
- **Problem:** `setInterval` dijalankan pada screen tingkat child namun referensi interval id tidak disimpan di level komponen root atau tidak di-clear saat layar di-pop dari stack navigasi.
- **Troubleshooting:** Monitor CPU usage melalui Perfetto/Systrace. Jika JS thread tetap aktif melakukan periodic task saat aplikasi dalam keadaan idle, terdapat background interval yang bocor.
- **Solusi:** Selalu pasangkan pattern:
  ```typescript
  useEffect(() => {
    const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
  }, []);
  ```

#### Mistake 3: Native Module Context Leaks (Android Context Retention)
- **Problem:** TurboModule atau NativeModule menyimpan referensi `Activity` context ke dalam static field C++/Java.
- **Troubleshooting:** Buka Android Studio Memory Profiler $\rightarrow$ Heap Dump $\rightarrow$ Filter `Activity` $\rightarrow$ Periksa instance count. Jika jumlah `MainActivity` lebih dari 1 setelah orientasi layar berubah atau setelah navigasi berulang, context bocor.
- **Solusi:** Selalu gunakan `reactApplicationContext` (Application Context) bukan Activity context untuk inisialisasi modul jangka panjang. Gunakan `ActivityEventListener` yang berbasis weak reference jika memerlukan Activity lifecycle.

---

### 11. Best Practices (Production Checklist)

#### Kode Arsitektur UI (React Native)
- [ ] Semua `useEffect` yang memiliki async task, event emitter, subscription, atau animasi native harus mengembalikan cleanup function.
- [ ] Hindari menyimpan JSX Element atau large arrays di dalam global state (Zustand, Redux) secara persisten; simpan data skalar atau ID saja.
- [ ] Gunakan library list modern (FlashList) yang menerapkan view recycling daripada ScrollView/FlatList primitif untuk data di atas 50 item.
- [ ] Kompresi dimensi bitmap sebelum di-render ke UI; pastikan atribut resolusi gambar tidak melebihi dimensi fisik display perangkat (`pixelDensity`).

#### Tooling & Observabilitas Produksi
- [ ] Mengaktifkan integrasi Sentry / Datadog / Crashlytics Memory Warning tracking untuk memonitor OS Low Memory Events (`TRIM_MEMORY`).
- [ ] Memastikan `enableHermes: true` dan memverifikasi kompilasi Hermes Bytecode aktif di Release build variant.
- [ ] Menjalankan pipeline CI/CD automatisasi pendeteksian regresi alokasi memori menggunakan instrumentasi end-to-end (misal: Maestro / Detox yang dikombinasikan dengan pembacaan metrics via ADB).

---

### 12. Hands-on Practice

Buat dan simpan seluruh implementasi praktikum di folder: `hands-on/m02/`.

#### Langkah 1: Setup Workspace & Memory Guard Module
Buat file `hands-on/m02/MemoryLeakDetector.ts` untuk memonitor siklus dekonstruksi komponen pada environment development:

```typescript
// hands-on/m02/MemoryLeakDetector.ts
export class MemoryLeakDetector {
  private static registry = new FinalizationRegistry((heldValue: string) => {
    console.warn(`[MEMORY LEAK WARNING]: Komponen "${heldValue}" telah di-garbage collect oleh runtime.`);
  });

  public static watch(target: object, componentName: string): void {
    if (__DEV__) {
      this.registry.register(target, componentName);
    }
  }
}
```

#### Langkah 2: Pembuatan Virtualized Large Feed Component Bebas Leak
Buat file `hands-on/m02/HighPerformanceFeed.tsx`:

```typescript
// hands-on/m02/HighPerformanceFeed.tsx
import React, { useState, useEffect, useCallback, memo } from 'react';
import { View, Text, StyleSheet, Dimensions } from 'react-native';
import { FlashList } from '@shopify/flash-list';
import { MemoryLeakDetector } from './MemoryLeakDetector';

const { width } = Dimensions.get('window');

interface FeedItem {
  id: string;
  title: string;
  timestamp: number;
}

const FeedRow = memo(({ item }: { item: FeedItem }) => {
  return (
    <View style={styles.card}>
      <Text style={styles.title}>{item.title}</Text>
      <Text style={styles.subtitle}>{new Date(item.timestamp).toISOString()}</Text>
    </View>
  );
});

export const HighPerformanceFeed: React.FC = () => {
  const [items, setItems] = useState<FeedItem[]>([]);

  useEffect(() => {
    MemoryLeakDetector.watch(this, 'HighPerformanceFeed');
    
    // Generate synthetic enterprise payload
    const dummyData: FeedItem[] = Array.from({ length: 500 }).map((_, index) => ({
      id: `item-${index}`,
      title: `Laporan Transaksi FinTech Keuangan #${index}`,
      timestamp: Date.now() - index * 60000,
    }));
    
    setItems(dummyData);

    return () => {
      // Deterministic cleanup
      setItems([]);
    };
  }, []);

  const renderItem = useCallback(({ item }: { item: FeedItem }) => {
    return <FeedRow item={item} />;
  }, []);

  const keyExtractor = useCallback((item: FeedItem) => item.id, []);

  return (
    <View style={styles.container}>
      <FlashList
        data={items}
        renderItem={renderItem}
        keyExtractor={keyExtractor}
        estimatedItemSize={72}
        drawDistance={width * 2}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0F172A',
  },
  card: {
    height: 72,
    paddingHorizontal: 16,
    justifyContent: 'center',
    borderBottomWidth: 1,
    borderBottomColor: '#1E293B',
  },
  title: {
    color: '#F8FAFC',
    fontSize: 14,
    fontWeight: '600',
  },
  subtitle: {
    color: '#64748B',
    fontSize: 12,
    marginTop: 4,
  },
});
```

---

### 13. Exercise

#### Level Easy
Buat sebuah hook bernama `useInterval` yang menerima callback dan delay, namun memiliki garansi mutlak tidak akan mengeksekusi callback jika komponen sudah di-*unmount*, serta otomatis membersihkan interval ID saat delay berubah atau komponen terlepas dari tree.

#### Level Medium
Sebuah modul analitik NativeEventEmitter menghasilkan data GPS setiap 100ms. Buat komponen consumer yang membatasi (*throttle*) update data ke JS state menggunakan windowing rate 1000ms, serta implementasikan mekanisme pembatalan subscription yang kebal terhadap race-condition unmount saat data sedang di-dispatch dari native layer.

#### Level Hard
Rancang modul integrasi C++ TurboModule JSI sederhana (`TurboBufferModule`) yang mengalokasikan buffer memory array mentah di heap C++ (`malloc`/`new`). Implementasikan wrapper `HostObject` pada JSI yang menggunakan `FinalizationRegistry` di sisi TypeScript atau RAII destructor di C++ untuk memastikan alokasi buffer C++ tersebut otomatis terhapus tanpa ada kebocoran memory natif saat variabel JS-nya terkena *garbage collection*.

---

### 14. Challenge

#### Skenario Kasus Kompleks
Aplikasi Enterprise Media Streaming Anda memiliki fitur "Picture-in-Picture" (PiP) mini-player video native yang dikendalikan oleh React Native state.
- **Kondisi Saat Ini:** Setiap kali pengguna membuka dan menutup video player sebanyak 20 kali berturut-turut, heap size aplikasi bertambah sebesar 180MB hingga akhirnya sistem Android memicu `LMK` (SIGKILL).
- **Karakteristik Masalah:**
  1. Profiling di Hermes GC menunjukkan JS Heap tetap stabil pada kisaran 25MB (tidak ada leak di layer JS).
  2. Alokasi di Native Memory Profiler memperlihatkan instance `ExoPlayer` / `AVPlayer` native beserta internal decoding texture surfaces tetap hidup di heap native.
  3. Video player ini dikontrol oleh state management global yang mengikat event listener ke TurboModule native bridge.

#### Tugas Anda:
1. Buat dokumen arsitektur dan rancang pseudocode/kode integrasi Native-to-JS lifecycle boundary yang mengatasi retensi instance decoder native tersebut.
2. Jelaskan struktur referensi pointer mana yang harus diubah menjadi `weak reference`.
3. Tunjukkan protokol handling jika event lifecycle native `onDestroy` / `dealloc` berjalan mendahului atau tertunda relatif terhadap siklus *unmounting* React Native Fabric component tree.

*(Catatan: Solusi ini harus mempertahankan performa latency video playback instan tanpa mematikan caching stream data).*

---

### 15. Quiz Evaluasi Pemahaman

#### 5 Pertanyaan Basic
1. Apa perbedaan mendasar antara siklus GC Young Generation (Nursery) dan Old Generation pada Hermes VM?
2. Mengapa kebocoran memori native (C++/Java/Obj-C) jauh lebih berbahaya bagi kestabilan aplikasi daripada kebocoran variabel JS skalar berukuran kecil?
3. Pada fase lifecycle manakah event subscription native sebaiknya dibersihkan dalam komponen fungsional React?
4. Apa fungsi dari tools Android Studio Profiler "Dump Java/Kotlin Heap" dalam konteks aplikasi React Native?
5. Mengapa penggunaan Chrome DevTools Inspector standar tidak dapat mendeteksi kebocoran memori pada C++ ShadowTree Fabric?

#### 5 Pertanyaan Intermediate
6. Bagaimana circular reference antara C++ `std::shared_ptr` dan JavaScript `jsi::Value` dapat menggagalkan proses garbage collection pada Hermes?
7. Jelaskan fenomena "Native Memory Drag" dan bagaimana frekuensi siklus GC di Hermes mempengaruhi pembebasan objek di native layer.
8. Mengapa `FlashList` jauh lebih hemat alokasi memori dibandingkan `FlatList` bawaan ketika merender ribuan elemen?
9. Apa fungsi `FinalizationRegistry` pada arsitektur modern memory monitoring dan apa batasannya?
10. Bagaimana mekanisme kerja `TRIM_MEMORY` callback pada OS Android dan apa dampaknya jika aplikasi mengabaikan callback tersebut?

#### 3 Skenario Kasus Produksi
11. **Skenario A:** Tim QA melaporkan bahwa memory usage meningkat pesat hanya ketika berpindah tab navigasi bolak-balik (Bottom Tab Navigator), padahal layar sebelumnya sudah tidak terlihat di layar. Jelaskan mengapa hal ini terjadi pada stack navigation standar dan bagaimana arsitektur screen detachment (`react-native-screens`) mengatasinya.
12. **Skenario B:** Sebuah komponen chart real-time menerima 60 payload data per detik via WebSocket. Setelah berjalan 15 menit, aplikasi mulai drop frame dari 60fps ke 15fps sebelum akhirnya crash. Di heap dump, Hermes memori sangat tinggi dengan jutaan objek closures. Langkah eliminasi apa yang harus diterapkan pada JS memory loop ini?
13. **Skenario C:** Anda mendeteksi bahwa alokasi memori naik drastis saat screen yang memiliki video native ditutup, namun crash baru terjadi 5 menit kemudian di screen yang sama sekali tidak berhubungan. Bagaimana cara Anda mengonfirmasi bahwa akar masalahnya berada pada unreleased hardware codec surfaces dari screen sebelumnya?

---

### 16. Summary

- Performa dan kestabilan React Native enterprise ditentukan oleh kebersihan batas alokasi tiga runtime: **Hermes VM (JS)**, **Fabric Core (C++)**, dan **Platform OS Host (Java/Kotlin/Obj-C/Swift)**.
- Kebocoran memori yang paling merusak sistem (*silent killers*) sering kali tidak terjadi di dalam JS Heap, melainkan pada retensi native backing views, bitmaps, dan C++ HostObjects yang tertahan oleh closure, retain cycle, atau lifecycle listener yang menggantung.
- Melalui tooling analisis komprehensif (Hermes Sampling Profiler, Android Studio Memory Profiler, Xcode Allocations) dan pola arsitektur deterministik (safe lifecycle hooks, component virtualization, weak references), engineer dapat menjamin aplikasi beroperasi di bawah batas alokasi memori yang aman, mengeliminasi OOM crashes, serta memaksimalkan crash-free sessions di tingkat produksi.