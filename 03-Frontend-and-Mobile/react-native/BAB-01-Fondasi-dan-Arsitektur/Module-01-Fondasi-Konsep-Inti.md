# Bab 01 Modul 01: Arsitektur Eksekusi React Native — Transisi dari Legacy Bridge ke New Architecture (JSI, Fabric, TurboModules, Codegen)

---

## 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis** batasan struktural *Legacy Bridge Architecture* yang menyebabkan *bottleneck* performa serialisasi JSON asinkron.
- **Mengartikulasikan** mekanisme kerja internal *New Architecture*: JavaScript Interface (JSI), Fabric Renderer, TurboModules, dan Codegen.
- **Mengevaluasi** siklus hidup pemanggilan fungsi native secara langsung (sinkron dan asinkron) melalui pointer C++ menggunakan JSI tanpa dependensi pada *message queue*.
- **Merancang dan Mengimplementasikan** spesifikasi modul native typed menggunakan Codegen untuk *TurboModule* kustom berbasis C++ / Platform Native (Android/iOS).
- **Mendiagnosis** *frame drop* dan *thread starvation* menggunakan profiling tools native (Systrace, Instruments, Chrome Profiler).

---

## 2. Conceptual Foundation
React Native dirancang dengan prinsip deklaratif: mendefinisikan antarmuka menggunakan JavaScript/TypeScript, sementara rendering aktual didelegasikan ke subsistem UI native (UIKit pada iOS dan Android View System).

Tantangan fundamental arsitektur ini adalah interkoneksi antara dua runtime yang terisolasi secara memori:
1. **JavaScript VM (V8/JSC/Hermes):** Runtime dinamis dengan *garbage collection* otomatis dan *single-threaded execution model*.
2. **Native Platform Runtime (Obj-C/Swift pada iOS, Java/Kotlin pada Android):** Lingkungan terkonsolidasi dengan eksekusi multithreaded dan akses langsung ke sistem operasi.

Menghubungkan kedua dunia ini menuntut abstraksi komunikasi lintas runtime (*cross-runtime inter-process communication* / IPC internal).

---

## 3. Why This Exists: Historical Context & Problems Solved
Pada arsitektur klasik (Legacy Bridge):
- **Serialisasi JSON Asinkron:** Seluruh pertukaran data (UI calls, event listeners, API native) diubah menjadi string JSON, di-antrekan di *bridge queue*, lalu di-deserialisasi di sisi penerima.
- **Overhead & Jitter:** Untuk payload besar (misal: parsing video frames, streaming koordinat gestur 60/120 FPS), proses stringifikasi dan deserialisasi memakan siklus CPU yang signifikan, menyebabkan antrean tersumbat (*bridge congestion*).
- **Asinkronitas Mutlak:** JavaScript tidak dapat membaca status native secara atomik atau sinkron. Sebagai contoh, sinkronisasi scroll position native ke JS view seringkali menghasilkan efek *white flash* saat scrolling cepat karena layout baru terlambat di-render oleh JS thread.

New Architecture lahir untuk memutus model serialisasi ini dengan mengekspos API Native langsung ke konteks JavaScript menggunakan binding C++.

---

## 4. What It Is: Technical Definition & Mental Model
**New Architecture** adalah perombakan radikal mesin internal React Native yang berpusat pada empat komponen inti:

1. **JSI (JavaScript Interface):** Lapisan abstraksi C++ yang memungkinkan JavaScript Engine memegang referensi langsung (*host objects*) ke objek C++ native, dan sebaliknya. Tidak ada lagi serialisasi JSON. Pemanggilan fungsi native menjadi pemanggilan fungsi C++ langsung (*direct synchronous execution*).
2. **Fabric:** Sistem rendering baru yang memanfaatkan JSI. Fabric memproses pohon render UI (*Shadow Tree*) secara langsung di layer C++ dan dapat menginstruksikan platform UI thread secara sinkron maupun ter-orkestrasi melalui prioritasi React Concurrent Features.
3. **TurboModules:** Evolusi Native Modules di atas JSI. Modul di-load secara *lazy* (hanya saat dibutuhkan oleh JavaScript), memotong konsumsi memori dan mempercepat waktu *cold start* aplikasi secara drastis.
4. **Codegen:** Tool kompilasi statis berbasis deklarasi tipe (TypeScript/Flow) yang menghasilkan boilerplate C++ dan Java/Obj-C interfaces secara otomatis. Ini menjamin *type safety* lintas batas JS-Native pada saat kompilasi (*compile-time contract*).

---

## 5. How It Works Under the Hood
Proses eksekusi New Architecture berjalan melalui mekanisme berikut:

```
[ JavaScript Engine: Hermes ]
         │
   Direct C++ Host Object Pointer (via JSI)
         │
         ▼
[ JSI Abstraction Layer (C++) ]
   ├── TurboModules (Direct C++ Call -> Kotlin/Swift)
   └── Fabric Renderer (Yoga Layout Engine + C++ Shadow Tree)
         │
   Native OS Mount Instructions
         │
         ▼
[ Host Platform UI Thread (Android View / iOS UIView) ]
```

1. **Inisialisasi Runtime:** Saat aplikasi dibuka, Hermes diinisialisasi. Runtime C++ mendaftarkan fungsi-fungsi JSI ke dalam *global object* JavaScript.
2. **Kompilasi Spek (Codegen):** Sebelum runtime, Codegen membaca berkas spesifikasi TypeScript (`NativeSpec.ts`) dan memproduksi *abstract class* di C++ dan Java/Obj-C.
3. **Pemanggilan TurboModule:** Ketika JavaScript mengeksekusi method modul, ia tidak mengirim pesan teks ke Bridge. Ia memanggil *HostObject method wrapper* di C++. C++ meneruskan panggilan langsung ke thread yang ditentukan (atau thread saat ini) pada level native.
4. **Mutasi UI (Fabric):**
   - React membentuk *Element Graph* di JavaScript.
   - Fabric menciptakan *C++ Shadow Tree* yang mereplikasi struktur element menggunakan Yoga layout engine langsung di memori C++.
   - Menggunakan algoritma immutability, Fabric melakukan *cloning* dan *diffing* pada Shadow Nodes.
   - Hasil kalkulasi dimensi dikirim ke UI Thread sebagai operasi mutasi (*Mounting phase*) melalui satu instruksi atomik native.

---

## 6. High-Level Architecture Diagram

```
+-------------------------------------------------------------------------+
|                         JAVASCRIPT ENVIRONMENT                         |
|  React Components   │   Concurrent Features   │   Application Logic     |
+-------------------------------------------------------------------------+
                                    │
                                    │ (Direct Execution via JSI)
                                    ▼
+-------------------------------------------------------------------------+
|                         C++ CORE RUNTIME LAYER                          |
|                                                                         |
|   +-----------------------+                 +-----------------------+   |
|   |      JSI Engine       |                 |        Codegen        |   |
|   | (Hermes / V8 C++ API) |                 | (C++ Type Contracts)  |   |
|   +-----------------------+                 +-----------------------+   |
|               │                                         │               |
|               ├───────────────────┬─────────────────────┘               |
|               ▼                   ▼                                     |
|   +-----------------------+  +--------------------------------------+   |
|   |     TurboModules      |  |           Fabric Renderer            |   |
|   |  - Lazy Initialized   |  |  - C++ Shadow Tree                   |   |
|   |  - Direct Invocations |  |  - Yoga Cross-Platform Layout Engine |   |
|   +-----------------------+  +--------------------------------------+   |
+-------------------------------------------------------------------------+
               │                                         │
               │ (JNI / ObjC Runtime)                    │ (Atomic Mounting)
               ▼                                         ▼
+-------------------------------------------------------------------------+
|                          HOST PLATFORM RUNTIME                          |
|                                                                         |
|        iOS (Cocoa Touch / UIKit)   │    Android (ART / View System)     |
+-------------------------------------------------------------------------+
```

---

## 7. Detailed Flow Diagram: UI Interaction & State Update

Alur siklus hidup peristiwa gestur hingga rendering ulang pada Fabric:

```
[User Touch] ──> [OS Event Queue (Native Thread)]
                       │
                       │ High Priority Event (Synchronous path)
                       ▼
                 [Fabric C++ Manager]
                       │
                       │ JSI Event Trigger
                       ▼
                 [JavaScript / React Runtime]
                       │
                       │ React State Mutation (e.g., setState)
                       ▼
                 [React Render Phase (WorkLoop)]
                       │
                       │ Direct C++ Shadow Node Allocation
                       ▼
                 [Fabric: C++ Shadow Tree Cloning & Diffing]
                       │
                       │ Yoga recalculates Flexbox Layout
                       ▼
                 [Generate Mutation Instructions]
                       │
                       │ Dispatched to Native Main Thread
                       ▼
                 [Native Mounting: Update UIView / Android.View]
                       │
                       ▼
                 [Pixel Rendered to Display Buffer (120Hz/60Hz)]
```

---

## 8. Minimal Working Example: Typed TurboModule Specification
Berikut adalah kontrak TurboModule berbasis Codegen untuk membaca nilai entropi sistem secara sinkron dan asinkron.

### File: `NativeHardwareEntropy.ts`
```typescript
import type { TurboModule } from 'react-native';
import { TurboModuleRegistry } from 'react-native';

export interface Spec extends TurboModule {
  // Direct synchronous invocation via JSI (Returns instantly without Promise)
  getHardwareEntropySync(): number;

  // Asynchronous invocation via Thread Pool
  generateSecureToken(length: number): Promise<string>;
}

export default TurboModuleRegistry.getEnforcing<Spec>('NativeHardwareEntropy');
```

### File: `package.json` (Codegen Configuration Snippet)
```json
{
  "name": "hardware-entropy",
  "version": "1.0.0",
  "codegenConfig": {
    "name": "NativeHardwareEntropySpec",
    "type": "modules",
    "jsTransforms": true,
    "android": {
      "javaPackageName": "com.hardwareentropy"
    }
  }
}
```

---

## 9. Real-World Production Scenario: High-Throughput Sensor Processing
Implementasi pembacaan akselerometer frekuensi tinggi (100Hz) yang mengalirkan data mentah langsung ke thread C++ untuk filtering tanpa mengotori UI thread dan tanpa overhead serialisasi JSON.

### File: `NativeSensorPipeline.ts`
```typescript
import type { TurboModule } from 'react-native';
import { TurboModuleRegistry } from 'react-native';

export interface Spec extends TurboModule {
  startSensorStream(sampleRateHz: number): void;
  stopSensorStream(): void;
  // Membaca komputasi vektor terakhir secara sinkron via JSI
  getLatestVectorSync(): { x: number; y: number; z: number; timestamp: number };
}

export default TurboModuleRegistry.getEnforcing<Spec>('NativeSensorPipeline');
```

### File: C++ Implementation Header `NativeSensorPipeline.h`
```cpp
#pragma once

#include <NativeSensorPipelineSpecJSI.h>
#include <memory>

namespace facebook::react {

class NativeSensorPipeline : public NativeSensorPipelineCxxSpec<NativeSensorPipeline> {
public:
  NativeSensorPipeline(std::shared_ptr<CallInvoker> jsInvoker);

  void startSensorStream(double sampleRateHz);
  void stopSensorStream();
  jsi::Object getLatestVectorSync(jsi::Runtime &rt);

private:
  struct Vector3D {
    double x{0.0};
    double y{0.0};
    double z{0.0};
    double timestamp{0.0};
  };

  std::atomic<bool> isStreaming_{false};
  Vector3D latestVector_{};
};

} // namespace facebook::react
```

### File: C++ Implementation Source `NativeSensorPipeline.cpp`
```cpp
#include "NativeSensorPipeline.h"

namespace facebook::react {

NativeSensorPipeline::NativeSensorPipeline(std::shared_ptr<CallInvoker> jsInvoker)
    : NativeSensorPipelineCxxSpec<NativeSensorPipeline>(std::move(jsInvoker)) {}

void NativeSensorPipeline::startSensorStream(double sampleRateHz) {
  isStreaming_.store(true, std::memory_order_relaxed);
  // Hardware listener thread logic omitted for brevity
}

void NativeSensorPipeline::stopSensorStream() {
  isStreaming_.store(false, std::memory_order_relaxed);
}

jsi::Object NativeSensorPipeline::getLatestVectorSync(jsi::Runtime &rt) {
  // Alokasi langsung pada JavaScript Runtime via JSI tanpa marshalling JSON
  jsi::Object result(rt);
  result.setProperty(rt, "x", latestVector_.x);
  result.setProperty(rt, "y", latestVector_.y);
  result.setProperty(rt, "z", latestVector_.z);
  result.setProperty(rt, "timestamp", latestVector_.timestamp);
  return result;
}

} // namespace facebook::react
```

---

## 10. Step-by-Step Implementation Guide

1. **Aktivasi New Architecture pada Template Proyek:**
   - **Android:** Buka file `android/gradle.properties`, ubah flag:
     ```properties
     newArchEnabled=true
     ```
   - **iOS:** Jalankan CocoaPods dengan flag env:
     ```bash
     cd ios && RCT_NEW_ARCH_ENABLED=1 bundle exec pod install
     ```

2. **Verifikasi Runtime Execution:**
   Tambahkan blok verifikasi pada entri utama aplikasi (`App.tsx`):
   ```typescript
   import React, { useEffect } from 'react';
   import { View, Text, StyleSheet } from 'react-native';

   export function ArchitectureIndicator(): React.JSX.Element {
     const isFabricEnabled = Boolean(
       (global as unknown as { nativeFabricUIManager?: unknown }).nativeFabricUIManager
     );

     useEffect(() => {
       console.log(`[Runtime Matrix] Fabric Status: ${isFabricEnabled ? 'ACTIVE' : 'LEGACY'}`);
     }, [isFabricEnabled]);

     return (
       <View style={styles.container}>
         <Text style={styles.metricText}>
           Engine: Hermes | Architecture: {isFabricEnabled ? 'New (Fabric/JSI)' : 'Bridge'}
         </Text>
       </View>
     );
   }

   const styles = StyleSheet.create({
     container: { padding: 16, backgroundColor: '#0f172a' },
     metricText: { color: '#38bdf8', fontFamily: 'monospace', fontSize: 12 },
   });
   ```

3. **Validasi Kompilasi Codegen:**
   Jalankan build untuk memicu pembuatan scaffold C++:
   - Android: `./gradlew generateCodegenArtifactsFromSchema`
   - iOS: Scaffolding dieksekusi secara otomatis di dalam tahap pre-build CocoaPods.

---

## 11. Edge Cases, Failure Modes & Mitigations

| Failure Mode / Edge Case | Akar Masalah (Root Cause) | Mitigasi Arsitektural |
| :--- | :--- | :--- |
| **Deadlock on Synchronous JSI Call** | JavaScript thread memanggil method JSI sinkron yang menunggu kunci mutex dari UI thread yang sedang memblokir JS thread. | Hindari mutex blocking dalam JSI sinkron. Operasi berat sistematis harus dieksekusi asinkron via *WorkLoop/Background Thread*. |
| **Out-of-Memory (OOM) via Unbounded C++ Allocation** | JS garbage collector tidak melacak memori native internal C++ yang dialokasikan di dalam `HostObject`. | Implementasikan custom `HostObject` finalizer dan limitasi siklus alokasi menggunakan smart pointer (`std::unique_ptr` / RAII). |
| **Shadow Node Mutation Inconsistency** | Thread native mencoba memodifikasi C++ Shadow Tree saat Fabric sedang menjalankan fase *Commit*. | Hormati paradigma immutability Fabric: kloning node yang dimutasi alih-alih melakukan modifikasi in-place. |
| **Codegen Type-Mismatch Compilation Error** | Definisi TypeScript menggunakan tipe union kompleks yang tidak didukung generator schema C++. | Gunakan tipe primitif yang diizinkan (`string`, `number`, `boolean`, `Array<T>`, `Object`) sesuai spesifikasi resmi Codegen. |

---

## 12. Trade-offs & Alternatives Matrix

| Dimensi | Legacy Bridge Architecture | New Architecture (JSI / Fabric / Turbo) | Native Platform Murni (Swift/Kotlin) |
| :--- | :--- | :--- | :--- |
| **Model Eksekusi** | Asinkron sepenuhnya (JSON text batching) | Sinkron & Asinkron terpadu via C++ memory pointer | Sinkron & Asinkron native direct compilation |
| **Waktu Startup (TTI)** | Lambat (Eager loading seluruh native modules) | Sangat Cepat (Lazy initialization via TurboModules) | Maksimal (Native execution tanpa VM spin-up) |
| **Kompleksitas Debugging** | Menengah (Dapat menginspeksi traffic JSON bridge) | Tinggi (Memerlukan tracing lintas runtime JS, C++, dan Native) | Terstandarisasi (Xcode Instruments, Android Profiler) |
| **Memory Footprint** | Tinggi (Duplikasi data string JSON di kedua layer) | Rendah (Berbagi pointer memori referensial via JSI) | Teroptimalisasi (Direct single-layer allocation) |
| **Interop Overhead** | Signifikan (~1ms - puluhan ms per frame pada payload masif) | Sangat Rendah (Sub-mikrodetik direct function call) | Nol (Zero cross-runtime overhead) |

---

## 13. Best Practices & Optimization Checklist

- [ ] **Gunakan Hermes Engine:** Pastikan `hermesEngine: true` aktif di `android/app/build.gradle` dan `Podfile` untuk memaksimalkan efisiensi kompilasi bytecode *Ahead-of-Time* (AOT) dengan integrasi direct memory JSI.
- [ ] **Minimalkan JSI Synchronous Calls di Jalur Render:** Meskipun JSI instan, menjalankan kalkulasi berat secara sinkron pada JS thread tetap akan memicu *frame drop* jika total durasi melebihi batas frame rate (16.6ms untuk 60 FPS, 8.3ms untuk 120 FPS).
- [ ] **Validasi Immutable Updates di Fabric:** Jangan pernah memodifikasi properti instance view native secara langsung di luar siklus reconciliation React.
- [ ] **Definisikan Tipe Skema TurboModule dengan Ketat:** Hindari tipe `Object` atau `any` umum pada skema TypeScript Codegen untuk mencegah kegagalan pembuatan type binding C++ statis.
- [ ] **Audit Library Eksternal:** Pastikan dependensi pihak ketiga sudah mendukung Fabric dan TurboModules (cek direktori modul apakah menyediakan spesifikasi Codegen).

---

## 14. Common Pitfalls & Antipatterns

### Antipattern: Polling Sinkron Berfrekuensi Tinggi Menggunakan JSI
```typescript
// BURUK: Menghancurkan performa UI Thread dengan polling berkelanjutan
function BadDataPoller() {
  useEffect(() => {
    const interval = setInterval(() => {
      // Direct JSI invocation dilakukan setiap 1ms
      const metrics = NativeHardwareEntropy.getHardwareEntropySync();
      applyMetrics(metrics);
    }, 1);
    return () => clearInterval(interval);
  }, []);
}
```
**Konsekuensi:** Mengunci JavaScript event loop, menahan garbage collector, dan menghentikan concurrent render passes React.

### Best Practice: Pola Berbasis Event Reaktif
```typescript
// BENAR: Menggunakan event subscription asinkron dari Native Event Emitter
function GoodDataListener() {
  useEffect(() => {
    const subscription = EntropyEventEmitter.addListener(
      'onEntropySampled',
      (data) => {
        // Event diproses sesuai scheduling window
        applyMetrics(data);
      }
    );
    return () => subscription.remove();
  }, []);
}
```

---

## 15. Debugging, Tracing & Instrumentation Guide

### 1. Pelacakan Eksekusi Menggunakan Perfetto / Systrace
Untuk melihat batas thread C++ dan JS secara real-time pada Android:
```bash
adb shell setprop debug.fbreact.trace 1
adb shell atrace --async_start -b 40960 sched am app view res
# Jalankan interaksi pada aplikasi
adb shell atrace --async_stop -o /data/local/tmp/trace.html
adb pull /data/local/tmp/trace.html .
```
Analisis section:
- `FabricUIManager::commit`: Menunjukkan durasi parsing dan penciptaan Shadow Tree di C++.
- `JSIExecutor::callFunction`: Menunjukkan waktu eksekusi aktual kode JavaScript di atas pointer native.

### 2. Validasi JSI Bridge di Console
Jalankan verifikasi status pointer engine langsung di runtime:
```javascript
if (global.__turboModuleProxy != null) {
  console.info('TurboModules Runtime Proxy terhubung langsung via C++ Memory Context');
} else {
  console.warn('Fallback: Berjalan di atas Legacy MessageQueue Bridge');
}
```

---

## 16. Security & Compliance Considerations
1. **Memory Safety pada Lapisan C++ (JSI):**
   Penggunaan JSI mengharuskan pengelolaan alokasi memori mentah (*raw pointer* atau *smart pointer*). Buffer overflow atau invalid pointer dereference pada level C++ tidak akan melempar exception JavaScript yang dapat ditangkap dengan `try/catch`, melainkan menyebabkan aplikasi mengalami **Hard Native Crash** (SIGSEGV / EXC_BAD_ACCESS).
2. **Exposition of Sensitive Logic via Reflection:**
   Jangan mengekspos logic autentikasi sistem secara sinkron melalui JSI tanpa validasi cryptographic context. Membuka native API secara langsung tanpa bridge sandboxing dapat membuka celah ekstraksi data via *runtime injection* (contoh: tools seperti Frida dapat mem-hook pointer JSI lebih mudah dibanding menganalisis serialize/deserialize pipeline bridge).

---

## 17. Production Readiness Checklist

| No | Parameter Pemeriksaan | Kriteria Lolos (Pass) | Status |
| :--- | :--- | :--- | :--- |
| 1 | **Codegen Build Phase** | Tidak ada peringatan `CodegenSchemaValidationFailed` saat proses kompilasi native build. | [ ] |
| 2 | **Hermes Integration** | Runtime Hermes tervalidasi aktif (`typeof HermesInternal !== 'undefined'`). | [ ] |
| 3 | **Eliminasi Paket Bridge Dependen** | Zero dependency terhadap package usang yang masih mengandalkan global bridge listener tanpa modul fallback. | [ ] |
| 4 | **Memory Leak Profiling** | Tidak terjadi eskalasi native heap memory saat me-mount/unmount komponen Fabric kompleks secara berulang (100x unmount cycle test). | [ ] |
| 5 | **Crash Rate Telemetry** | Tracking error native (C++ SIGSEGV) terkonfigurasi pada Sentry/Crashlytics dengan source map C++ & dSYM yang terpasang. | [ ] |

---

## 18. Hands-On Lab Exercise

### Deskripsi Skenario:
Sistem aplikasi financial streaming Anda mengalami *micro-stuttering* (frame drop di bawah 30 FPS) saat grafik candlestick me-render order book baru. Anda ditugaskan mengisolasi modul kalkulasi checksum keamanan historis dari Legacy Bridge ke Typed TurboModule berbasis JSI.

### Tugas:
1. Konfigurasikan skema TurboModule bernama `NativeCryptoChecksum` yang memiliki signature:
   ```typescript
   sha256Sync(payload: string): string;
   ```
2. Pastikan file skema tersebut menghasilkan boilerplate otomatis melalui Codegen.
3. Tulis implementasi dummy C++ untuk fungsi `sha256Sync` yang secara instan mengembalikan hash string menggunakan manipulasi native pointer tanpa JSON stringification.
4. Buat tes profiling sederhana menggunakan `console.time` untuk membandingkan 10,000 iterasi hash antara implementasi JavaScript murni vs TurboModule native tersebut.

---

## 19. Deep Diagnostic & Scenario-Based Quiz

### Pertanyaan 1:
Aplikasi Anda mengalami drop frame drastis sesaat setelah user melakukan fast scrolling pada Fabric-enabled flat list. Profiler menunjukkan JavaScript Thread idle (penggunaan CPU < 5%), namun UI Thread Android mentok di 100%. Apa kemungkinan besar sumber masalahnya, dan bagaimana arsitektur Fabric menjelaskan fenomena ini?
- A. Hermes engine crash dan mengalihkan rendering ke interpreted mode secara fallback.
- B. Yoga Layout Engine di C++ menghasilkan Shadow Tree yang terlalu dalam, memaksa UI thread native melakukan rekalkulasi ukuran View (*requestLayout*) secara sinkron dalam jumlah masif.
- C. JSI memblokir UI thread karena garbage collection di JS thread terkunci oleh concurrent render phase.
- D. Codegen salah mengidentifikasi props TypeScript sehingga terjadi infinite serialization loop pada JSON bridge.

*Jawaban yang Benar:* **B**  
*Analisis:* Pada Fabric, kalkulasi Flexbox didelegasikan ke Yoga di layer C++. Meskipun proses diffing dan kompilasi layout terjadi di luar UI thread, hasil mutasi akhirnya harus di-*mount* ke host views platform native. Jika hierarki komponen menghasilkan instruksi mutasi struktural native yang masif secara bersamaan, UI Thread akan kewalahan mengeksekusi operasi penataan ukuran layout native (*layout pass*), meskipun JS thread telah menyelesaikan pekerjaannya.

### Pertanyaan 2:
Manakah karakteristik yang paling akurat membedakan eksekusi method melalui JSI dibandingkan dengan Legacy Bridge?
- A. JSI membungkus parameter ke dalam protobuff alih-alih JSON string.
- B. JSI mengeksekusi panggilan fungsi melalui dynamic socket network internal loopback.
- C. JSI menyematkan referensi C++ `HostObject` langsung ke dalam *global memory scope* JavaScript VM, memungkinkan pemanggilan method lintas runtime secara sinkron dalam thread stack yang sama.
- D. JSI secara otomatis memindahkan seluruh eksekusi kode JavaScript dari Hermes langsung ke CPU instructions platform host.

*Jawaban yang Benar:* **C**  
*Analisis:* JSI bukan merupakan protokol serialization atau socket transport baru. JSI adalah runtime bridging API tipis yang membuat JavaScript engine mengenali method native C++ sebagai fungsi callable biasa di memori (*in-process memory sharing* via Host Objects), mengeliminasi kebutuhan transport layer sama sekali.

---

## 20. Advanced Mental Model & Architectural Recap
Untuk menguasai React Native pada level sistem, singkirkan analogi bahwa *"React Native adalah webview yang disamarkan"*. 

Mental model yang benar:
> **React Native adalah aplikasi native C++ multi-threaded utuh yang menyematkan mesin eksekusi JavaScript (Hermes) sebagai mesin kalkulasi logikanya.** 

Dengan **New Architecture**, batas antara JavaScript dan Platform Host dihapuskan melalui interoperabilitas C++ (JSI). UI bukan lagi sekadar respons terhadap pesan JSON yang dikirim melintasi jembatan (*Bridge*), melainkan sinkronisasi terpadu pohon state native (*Shadow Tree*) yang di-mount secara deterministik pada platform host dengan latensi mendekati performa kompilasi native murni.