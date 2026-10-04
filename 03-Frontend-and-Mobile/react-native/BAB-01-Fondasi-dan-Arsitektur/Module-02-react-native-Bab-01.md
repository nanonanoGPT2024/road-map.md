# Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 01: Fondasi dan Arsitektur**  
**Kategori: 03-Frontend-and-Mobile (React Native)**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:

1. **Menganalisis dan Membedah Arsitektur Internal React Native Baru (New Architecture)**: Memahami secara komprehensif mekanisme kerja JavaScript Interface (JSI), Fabric Renderer, TurboModules, Hermes VM (Hades Garbage Collector), dan Codegen.
2. **Mengeliminasi Overhead Serialisasi Antar-Thread**: Menggantikan komunikasi asinkron berbasis JSON over Bridge warisan (*legacy bridge*) dengan direct memory pointer execution melalui C++ Host Objects pada JSI.
3. **Mengembangkan dan Mengintegrasikan Custom TurboModules Berkinerja Tinggi**: Menulis spesifikasi TypeScript berkategori *type-safe*, menjalankan generator Codegen, dan mengimplementasikan C++ core implementation yang kompatibel secara lintas platform (Android/iOS).
4. **Mendiagnosis Lifecycle Rendering Fabric**: Memahami tahapan *Render*, *Commit*, dan *Mount*, serta interaksinya dengan Yoga Engine untuk kalkulasi tata letak sinkron (*synchronous layout measurement*).
5. **Mengoptimalkan Pipeline Runtime Tingkat Enterprise**: Menerapkan strategi optimasi memori, zero-copy buffer sharing, dan penanganan konkurensi multi-threading native untuk aplikasi berskala jutaan pengguna aktif.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:

* Fondasi JavaScript Lanjutan: Event Loop, Microtasks, ArrayBuffers, TypedArrays, dan Garbage Collection semantics.
* Fondasi React Core: Virtual DOM, Fiber Reconciliation, Concurrent Mode, Batched Updates, dan Component Lifecycle.
* Pemahaman Arsitektur Native Tingkat Dasar:
  * **Android**: Java Native Interface (JNI), Activity/View Lifecycle, ART (Android Runtime).
  * **iOS**: Objective-C runtime, ARC (Automatic Reference Counting), UIKit View Hierarchy.
* Dasar Bahasa Pemrograman C++ (standar C++17 atau C++20): Pointer, Smart Pointers (`std::shared_ptr`, `std::unique_ptr`), STL Containers, dan Move Semantics.
* Pemahaman Module 01: Siklus hidup runtime React Native konvensional (Legacy Architecture) dan keterbatasan Bridge.

---

## 3. Concept & Internal Architecture

React Native New Architecture merevolusi paradigma eksekusi aplikasi mobile hibrida dengan membuang model komunikasi asinkronus berbasis *stringified JSON* dan menggantinya dengan model eksekusi memori langsung (*in-process shared memory*).

```
+-------------------------------------------------------------------------+
|                           JavaScript Realm                              |
|   +-----------------------------------------------------------------+   |
|   |         Hermes VM (Bytecode Precompiled, Hades GC)              |   |
|   |   +-----------------------+     +---------------------------+   |   |
|   |   | React 18+ App Code    |     | JS Specs (TurboModules)   |   |   |
|   |   +-----------+-----------+     +-------------+-------------+   |   |
|   +---------------|-------------------------------|-----------------+   |
+-------------------|-------------------------------|---------------------+
                    |                               |
                    | (Direct Pointer / JSI Calls)  | (Direct C++ HostObject)
                    v                               v
+-------------------------------------------------------------------------+
|                  C++ Core (Bridgeless / JSI Layer)                      |
|                                                                         |
|   +-----------------------------------------------------------------+   |
|   | JSI (JavaScript Interface - C++ Abstract Layer)                 |   |
|   | - Runtime-agnostic bindings (Hermes, V8, JSC)                   |   |
|   | - Zero serialization, Direct Host Objects reference             |   |
|   +-------------------+---------------------------+-----------------+   |
|                       |                           |                     |
|                       v                           v                     |
|   +------------------------------+   +------------------------------+   |
|   | Fabric Renderer              |   | TurboModule Engine           |   |
|   | - ComponentDescriptor Registry|   | - Lazy Initialization        |   |
|   | - Shadow Tree (Thread-safe)  |   | - C++ Core Business Logic    |   |
|   | - Yoga Layout Engine (C++)   |   | - Codegen generated glue     |   |
|   +---------------+--------------+   +--------------+---------------+   |
+-------------------|---------------------------------|-------------------+
                    |                                 |
     (Thread-safe Host Tree Mutation)     (Direct JNI/Obj-C Calls)
                    |                                 |
                    v                                 v
+-------------------------------------------------------------------------+
|                             Native OS Realm                             |
|   +-----------------------------------------------------------------+   |
|   | Android (ART/JVM)                         iOS (Cocoa/ObjC/Swift)|   |
|   | - SurfaceView / ViewGroup                - UIView Hierarchy     |   |
|   | - Yoga Node JNI Bindings                 - CoreAnimation Layers |   |
|   | - Platform Threads (Main UI)             - Platform Threads(UI) |   |
|   +-----------------------------------------------------------------+   |
+-------------------------------------------------------------------------+
```

### 3.1. JSI (JavaScript Interface)

Legacy Architecture mengandalkan Bridge: struktur FIFO berbasis antrean asinkron di mana JS memanggil `JSON.stringify()`, mentransfer payload melalui platform bridge, lalu thread native memanggil `JSON.parse()`. 

JSI mengeliminasi abstraksi ini sepenuhnya. JSI adalah C++ abstract class framework yang memungkinkan JavaScript Runtime (Hermes/JSC/V8) berinteraksi langsung dengan objek native C++.
* Objek C++ dapat diekspos ke JavaScript sebagai `jsi::HostObject`.
* JavaScript Engine memegang referensi memori langsung (*raw reference*) ke objek C++ melalui pointer.
* Pemanggilan fungsi native menjadi pemanggilan fungsi sinkronus berbobot sangat rendah (*synchronous in-memory invocation*), mirip dengan pemanggilan modul C++ di Node.js via N-API.

### 3.2. Hermes Runtime & Hades GC

Hermes adalah JavaScript engine yang dioptimalkan secara eksplisit untuk menjalankan React Native:
* **Ahead-of-Time (AOT) Compilation**: Kode JavaScript dikompilasi menjadi Hermes Bytecode (`.hbc`) saat fase build (CI/CD), mengeliminasi parsing dan Just-in-Time (JIT) compilation overhead saat aplikasi melakukan *warm-up*.
* **Hades GC**: Generational garbage collector yang menjalankan sebagian besar penandaan (*marking*) dan penyapuan (*sweeping*) memori pada thread latar belakang terpisah, mengurangi *stop-the-world pauses* hingga mendekati batas ~2-4 milidetik, mencegah frame drop (jank).

### 3.3. Fabric Renderer

Fabric adalah sistem rendering generasi baru yang menggantikan rendering pipeline warisan (`UIManager`):
* **Thread-safe**: Pohon komponen dapat dibuat, dibaca, dan dimutasi dari berbagai thread (UI thread, background worker thread, atau JS thread).
* **Immutability of Shadow Nodes**: Node UI direpresentasikan dalam C++ sebagai *Shadow Tree* yang bersifat *immutable*. Setiap perubahan state menghasilkan node baru melalui algoritma kloning hemat alokasi (structural sharing), meminimalisasi lock contention.
* **Synchronous Layout**: Integrasi langsung dengan Yoga Engine di layer C++ memungkinkan kalkulasi layout (flexbox) dan pembacaan metrik ukuran (`getBoundingClientRect` setara native) dieksekusi secara sinkron tanpa jeda frame render native.

### 3.4. TurboModules

TurboModules adalah evolusi dari Native Modules:
* **Lazy Loading**: Pada arsitektur lama, seluruh modul native (kamera, sensor, storage, enkripsi) diinstansiasi secara *eager* pada saat inisialisasi aplikasi (aplikasi start), menyebabkan lonjakan konsumsi CPU dan waktu TTI (*Time to Interactive*) lambat. TurboModules hanya diinisialisasi ketika modul tersebut pertama kali diakses oleh kode JavaScript.
* **Type-Safe Binding via Codegen**: Skrip spesifikasi TypeScript atau Flow digunakan untuk memicu *build tool* C++ (Codegen) untuk membuat *boilerplate glue code*, *type definitions*, dan C++ interface secara otomatis, menjamin integritas tipe data antara JS dan Native layer saat compile-time.

---

## 4. Why & What

### Karakteristik Pembanding: Legacy vs New Architecture

| Dimensi Arsitektur | Legacy Architecture (Bridge) | New Architecture (JSI, Fabric, TurboModules) |
| :--- | :--- | :--- |
| **Mekanisme Komunikasi** | Asinkron via batched JSON strings over FIFO queue | Sinkron/Konkuren via Direct Memory Pointer (JSI C++) |
| **Inisialisasi Native Module** | Eager (seluruh modul diinstansiasi saat cold start) | Lazy (diinstansiasi on-demand saat dibutuhkan) |
| **Type Safety Lintas Bahasa** | Lemah (mengandalkan manual mapping di Java/Obj-C) | Sangat Kuat (Divalidasi compile-time via Codegen) |
| **Layout & Measuring** | Asinkron (rentan blank canvas / layout jump) | Sinkronus (Dihitung langsung via C++ Yoga Tree) |
| **Interoperabilitas Threading** | Kaku: Terbatas pada JS Thread, UI Thread, Native Module Queue | Bebas: Mutasi Shadow Tree dapat dilakukan di sembarang thread native |
| **Overhead Memori** | Duplikasi representasi data (JSON serialization buffer) | Zero-copy memory view (Shared Array Buffer / Direct Pointers) |

### Mengapa Perubahan Ini Krusial?

1. **Eliminasi Frame Drops pada Animasi dan Gestur**: Pada arsitektur lama, event sentuhan (UI Thread) dikirim via Bridge ke JS Thread, dihitung, lalu dikembalikan ke Native UI via Bridge. Jika JS thread terblokir kalkulasi berat, animasi macet. Dengan JSI dan Fabric, logika animasi/gestur dapat diakses langsung tanpa latensi serialisasi.
2. **Konsistensi UI Sinkron**: Pada implementasi list berkecepatan tinggi (`FlatList` / `FlashList`), arsitektur lama sering menampilkan area putih (*white blank boxes*) karena UI Thread merender viewport sebelum JS sempat mengembalikan layout item via JSON Bridge. Fabric mengeksekusi ini secara sinkron.
3. **Standarisasi Ekosistem Mobile Multi-core**: Menghilangkan batasan arsitektur single-threaded, mengizinkan React 18 Concurrent Features (`useTransition`, `Suspense`, batched rendering) berjalan maksimal di lingkungan mobile multi-core.

---

## 5. How (Workflow Detail)

Siklus eksekusi dari komponen React hingga native view rendering melalui Fabric dan TurboModules berlangsung dalam 3 fase mutlak:

```
[JS Realm]                      [C++ Shadow World]                 [Native Platform]
    |                                   |                                  |
1. Render Phase                         |                                  |
   React executes JSX                   |                                  |
   Calls Codegen Specs                  |                                  |
   ----------------------------> Creates/Clones                            |
                                 ShadowNodes (Immutable)                   |
                                        |                                  |
2. Commit Phase                         |                                  |
                                 Calculates layout                         |
                                 via Yoga Engine (C++)                     |
                                        |                                  |
                                 Completes Shadow Tree                     |
                                        |                                  |
3. Mount Phase                          |                                  |
                                        +----------------------------> Mutates Native
                                        Emits Minimal Diff             OS Host Tree
                                        Operations (Mutations)         (Views/Subviews)
                                                                           |
                                                                       Renders UI
```

### Tahap 1: Render Phase
1. React mengeksekusi fungsi komponen di JavaScript VM (Hermes).
2. Host components (seperti `<View>`, `<Text>`) tidak lagi menghasilkan *payload call queue*. Melalui JSI, fungsi C++ langsung dipanggil untuk membuat atau mengkloning *Shadow Node* baru (`ParagraphShadowNode`, `ViewShadowNode`).
3. Dibuat sebuah *Shadow Tree* baru yang bersifat *immutable*. Jika state diperbarui, node yang terpengaruh dan leluhurnya dikloning menggunakan teknik *structural sharing*.

### Tahap 2: Commit Phase
1. Thread commit (bisa JS Thread atau Background Thread) memicu reconciler.
2. Yoga Engine (C++) menghitung kalkulasi matematis CSS Flexbox untuk *Shadow Tree* baru tersebut (kalkulasi *width*, *height*, *padding*, *margins*, dan *coordinates*).
3. Shadow Tree baru ditandai sebagai "committed" dan siap dipasang ke antarmuka native.

### Tahap 3: Mount Phase
1. Perbedaan (*diffing*) dihitung antara Shadow Tree lama dan Shadow Tree baru yang sudah di-layout oleh Yoga.
2. Fabric menghasilkan daftar instruksi mutasi atomik minimal (*Mutation Instruction Set*: `CreateView`, `UpdateProps`, `InsertSubView`, `RemoveSubView`).
3. Instruksi ini dikirim ke Thread UI utama (Main Thread OS: Android Looper / iOS RunLoop) untuk diterapkan langsung pada native view hierarki platform (*Platform Host View Tree*).

---

## 6. Analogy & Diagram ASCII

### Analogi Industri: Sistem Pemesanan Logistik Pabrik

* **Legacy Architecture (The Bridge)**: 
  Ibarat manajer JS dan mekanik Pabrik Native berada di dua gedung terpisah tanpa koneksi visual atau radio. Setiap ada tugas, manajer harus menulis formulir kertas (JSON), memasukkannya ke dalam kapsul pneumatik (Bridge Queue), kapsul meluncur perlahan ke seberang. Di seberang, formulir dibaca ulang, baru mesin digerakkan. Jika formulir bertumpuk ribuan lembar, terjadi kemacetan (*congestion*), menyebabkan operasional pabrik macet mendadak (*lagging*).

* **New Architecture (JSI & Fabric)**: 
  Ibarat manajer JS dan mekanik Native bekerja berdampingan di satu meja kendali C++. Manajer JS tidak perlu menulis surat; ia cukup menunjuk tombol dan tuas fisik yang sama (Direct Memory Pointer/JSI). Mekanik melihat instruksi tepat di detik tombol disentuh (*zero latency*).

### Diagram Detail Alur Komunikasi Direct-Pointer JSI

```
+-------------------------------------------------------------------------+
|                  VIRTUAL ADDRESS SPACE (IN-PROCESS)                     |
|                                                                         |
|   JavaScript Engine (Hermes)              Native Engine (C++/OS)        |
|   +-----------------------+              +--------------------------+   |
|   | Global Object (JS)    |              | C++ HostObject Instance  |   |
|   |                       |              |                          |   |
|   |  const nativeCrypto = |              | class FastCryptoEngine : |   |
|   |  TurboModuleRegistry  |              | public jsi::HostObject { |   |
|   |        |              |              | public:                  |   |
|   +--------|--------------+              |   jsi::Value get(...);   |   |
|            |                             |   void process(...);     |   |
|            |                             | }                        |   |
|            |                             +-------------^------------+   |
|            |                                           |                |
|            +-------------------------------------------+                |
|               Pointer Reference: 0x7FFEED49B2A0                        |
|               (No JSON serialization, Direct function invocation)        |
|                                                                         |
+-------------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Definisi Codegen TurboModule Spec

File ini mendefinisikan interface yang akan diproses oleh build tool Codegen untuk menggenerasikan bindings C++, Java, dan Objective-C.

```typescript
// path: src/specs/NativePerformanceMonitor.ts
import type { TurboModule } from 'react-native';
import { TurboModuleRegistry } from 'react-native';

export interface Spec extends TurboModule {
  // Synchronous JSI Call: Eksekusi langsung tanpa jeda antrean event loop
  getCpuUsageSync(): number;
  
  // Asynchronous Call: Mengembalikan Promise untuk operasi I/O
  collectMemoryFootprint(tag: string): Promise<{
    heapUsed: number;
    heapTotal: number;
    nativeRss: number;
  }>;
  
  // Mengirim event terstruktur menggunakan direct typed callback
  registerSamplingHook(threshold: number, onThresholdExceeded: (current: number) => void): void;
}

export default TurboModuleRegistry.getEnforcing<Spec>('NativePerformanceMonitor');
```

---

### 7.2. Practical Example: Custom C++ TurboModule (Zero-Copy Data Transfer)

Implementasi native module C++ murni yang mengeksekusi operasi hashing kriptografis tanpa melalui jembatan native platform OS layer (berjalan murni di C++ JSI layer untuk performa ekstrem).

#### Langkah 1: Spesifikasi TypeScript
```typescript
// path: src/specs/NativeCryptoEngine.ts
import type { TurboModule } from 'react-native';
import { TurboModuleRegistry } from 'react-native';

export interface Spec extends TurboModule {
  sha256Hex(input: string): string;
  computeHmacSync(key: string, message: string): string;
}

export default TurboModuleRegistry.getEnforcing<Spec>('NativeCryptoEngine');
```

#### Langkah 2: C++ Header (`NativeCryptoEngine.h`)
```cpp
// path: cpp/NativeCryptoEngine.h
#pragma once

#include <string>
#include <vector>
#include <jsi/jsi.h>

namespace enterprise::crypto {

using namespace facebook;

class NativeCryptoEngine : public jsi::HostObject {
public:
  NativeCryptoEngine();
  virtual ~NativeCryptoEngine() = default;

  // JSI HostObject Virtual Methods
  jsi::Value get(jsi::Runtime &runtime, const jsi::PropNameID &name) override;
  std::vector<jsi::PropNameID> getPropertyNames(jsi::Runtime &runtime) override;

private:
  static std::string calculateSha256(const std::string &input);
  static std::string calculateHmac(const std::string &key, const std::string &message);
};

} // namespace enterprise::crypto
```

#### Langkah 3: C++ Implementation (`NativeCryptoEngine.cpp`)
```cpp
// path: cpp/NativeCryptoEngine.cpp
#include "NativeCryptoEngine.h"
#include <sstream>
#include <iomanip>
#include <chrono>

namespace enterprise::crypto {

NativeCryptoEngine::NativeCryptoEngine() {}

// Custom minimal hashing untuk demonstrasi direct computation
std::string NativeCryptoEngine::calculateSha256(const std::string &input) {
  // Catatan Produksi: Gunakan OpenSSL atau platform-specific crypto (CommonCrypto/BoringSSL)
  unsigned long hash = 5381;
  for (char c : input) {
    hash = ((hash << 5) + hash) + c; /* hash * 33 + c */
  }
  std::stringstream ss;
  ss << std::hex << std::setfill('0') << std::setw(16) << hash;
  return ss.str();
}

std::string NativeCryptoEngine::calculateHmac(const std::string &key, const std::string &message) {
  return calculateSha256(key + ":" + message);
}

jsi::Value NativeCryptoEngine::get(jsi::Runtime &runtime, const jsi::PropNameID &name) {
  std::string methodName = name.utf8(runtime);

  if (methodName == "sha256Hex") {
    return jsi::Function::createFromHostFunction(
      runtime,
      name,
      1, // Jumlah parameter
      [](jsi::Runtime &rt, const jsi::Value &thisVal, const jsi::Value *args, size_t count) -> jsi::Value {
        if (count < 1 || !args[0].isString()) {
          throw jsi::JSError(rt, "sha256Hex expects 1 argument of type string");
        }
        std::string input = args[0].getString(rt).utf8(rt);
        std::string result = calculateSha256(input);
        return jsi::String::createFromUtf8(rt, result);
      }
    );
  }

  if (methodName == "computeHmacSync") {
    return jsi::Function::createFromHostFunction(
      runtime,
      name,
      2, // Jumlah parameter: key, message
      [](jsi::Runtime &rt, const jsi::Value &thisVal, const jsi::Value *args, size_t count) -> jsi::Value {
        if (count < 2 || !args[0].isString() || !args[1].isString()) {
          throw jsi::JSError(rt, "computeHmacSync expects (key: string, message: string)");
        }
        std::string key = args[0].getString(rt).utf8(rt);
        std::string msg = args[1].getString(rt).utf8(rt);
        std::string result = calculateHmac(key, msg);
        return jsi::String::createFromUtf8(rt, result);
      }
    );
  }

  return jsi::Value::undefined();
}

std::vector<jsi::PropNameID> NativeCryptoEngine::getPropertyNames(jsi::Runtime &runtime) {
  std::vector<jsi::PropNameID> properties;
  properties.push_back(jsi::PropNameID::forUtf8(runtime, "sha256Hex"));
  properties.push_back(jsi::PropNameID::forUtf8(runtime, "computeHmacSync"));
  return properties;
}

} // namespace enterprise::crypto
```

#### Langkah 4: Konsumsi di React Native Application
```tsx
// path: src/screens/SecurityVerificationScreen.tsx
import React, { useState, useTransition, useCallback } from 'react';
import { View, Text, TextInput, StyleSheet, Pressable } from 'react-native';
import NativeCryptoEngine from '../specs/NativeCryptoEngine';

export const SecurityVerificationScreen: React.FC = () => {
  const [payload, setPayload] = useState<string>('');
  const [checksum, setChecksum] = useState<string>('');
  const [isPending, startTransition] = useTransition();

  const handleComputeHash = useCallback(() => {
    // Sinkron, zero bridge queue overhead, sub-millisecond execution
    const startTime = performance.now();
    const result = NativeCryptoEngine.sha256Hex(payload);
    const duration = performance.now() - startTime;

    console.log(`Hash dihitung dalam ${duration.toFixed(3)} ms melalui C++ JSI direct call`);

    startTransition(() => {
      setChecksum(result);
    });
  }, [payload]);

  return (
    <View style={styles.container}>
      <Text style={styles.header}>JSI Fast Crypto Pipeline</Text>
      
      <TextInput
        style={styles.input}
        placeholder="Ketik payload transaksi..."
        value={payload}
        onChangeText={setPayload}
        autoCapitalize="none"
      />

      <Pressable 
        style={({ pressed }) => [styles.button, pressed && styles.buttonPressed]}
        onPress={handleComputeHash}
      >
        <Text style={styles.buttonText}>
          {isPending ? 'Memproses...' : 'Generate SHA-256 (JSI)'}
        </Text>
      </Pressable>

      {checksum ? (
        <View style={styles.resultBox}>
          <Text style={styles.resultLabel}>Direct C++ Output:</Text>
          <Text style={styles.resultText}>{checksum}</Text>
        </View>
      ) : null}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 24,
    backgroundColor: '#0F172A',
    justifyContent: 'center',
  },
  header: {
    fontSize: 22,
    fontWeight: '700',
    color: '#F8FAFC',
    marginBottom: 20,
    textAlign: 'center',
  },
  input: {
    backgroundColor: '#1E293B',
    borderColor: '#334155',
    borderWidth: 1,
    borderRadius: 8,
    padding: 14,
    color: '#FFFFFF',
    fontSize: 16,
    marginBottom: 16,
  },
  button: {
    backgroundColor: '#38BDF8',
    paddingVertical: 14,
    borderRadius: 8,
    alignItems: 'center',
  },
  buttonPressed: {
    opacity: 0.8,
  },
  buttonText: {
    color: '#0F172A',
    fontWeight: '600',
    fontSize: 16,
  },
  resultBox: {
    marginTop: 24,
    padding: 16,
    backgroundColor: '#1E293B',
    borderRadius: 8,
    borderLeftWidth: 4,
    borderLeftColor: '#38BDF8',
  },
  resultLabel: {
    fontSize: 12,
    color: '#94A3B8',
    textTransform: 'uppercase',
    fontWeight: '700',
    marginBottom: 4,
  },
  resultText: {
    fontSize: 14,
    fontFamily: 'monospace',
    color: '#38BDF8',
  },
});
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Migrasi Sistem Ledger & Order Book Fintech Superapp (10 Juta DAU)

#### Konteks & Masalah
Sebuah superapp perbankan dan bursa investasi memproses streaming data ticker saham dan enkripsi tanda tangan transaksi pada perangkat pengguna.
* **Gejala Sistem Lama**:
  * Ketika market volatile (500+ tick updates per detik via WebSocket), UI aplikasi mengalami *total freeze* (framerate anjlok ke < 12 FPS).
  * Terjadi *memory leak* bertahap; alokasi heap naik 250 MB dalam 15 menit, memicu OOM (Out Of Memory) crash di perangkat Android low-tier (RAM <= 3GB).
  * Pelanggan komplain transaksi telat tereksekusi karena antrean thread bridge menumpuk ribuan pesan JSON string.

#### Investigasi Akar Masalah (*Root Cause Analysis*)
Profil performa menggunakan Systrace dan Android Studio Profiler mengungkap:
1. **JSON Serialization Bottleneck**: Konversi JSON data ticker bervolume tinggi di thread background ke UI Thread melalui Bridge mengonsumsi 75% waktu siklus CPU Android Looper.
2. **Garbage Collection Pressure**: Pembuatan jutaan objek string JSON sementara (*ephemeral objects*) memicu Java GC dan V8 GC berulang kali menjalankan *Stop-The-World*, menyebabkan jank grafis parah.

#### Arsitektur Solusi (Migrasi ke New Architecture)
1. **Penerapan JSI TurboModule untuk Ingestion Stream**:
   Koneksi WebSocket native (C++ WebSocket client) dikaitkan langsung ke Hermes JavaScript Runtime melalui C++ Host Objects. Data biner (ArrayBuffer) dibaca langsung dari native memory tanpa konversi ke String JSON.
2. **Fabric Custom View untuk Order Book Component**:
   Mengubah antarmuka Order Book menjadi native Fabric Component. Pembaruan harga langsung memutasi *Shadow Tree C++* secara sinkron.
3. **Konfigurasi Hermes Hades Garbage Collector**:
   Mengaktifkan *Hades Concurrent GC* yang menjalankan alokasi dan pembersihan generasi muda secara non-blocking di thread sekunder.

#### Hasil Metrik Pasca Migrasi

| Metrik Kinerja | Arsitektur Lama (Legacy Bridge) | Pasca Migrasi (New Architecture) | Dampak Bisnis |
| :--- | :--- | :--- | :--- |
| **P99 UI Frame Render Time** | 83.2 ms (~12 FPS) | 14.1 ms (~60-120 FPS Stabil) | 0% stutter saat lonjakan market |
| **Cold Start Time (TTI)** | 3.8 detik | 1.4 detik | Bounce rate onboarding turun 22% |
| **Alokasi Memori Heap Rata-rata**| ~380 MB | ~110 MB | Zero-copy JSI menghemat 71% RAM |
| **Tingkat Crash (OOM Rate)** | 2.14% per sesi | 0.03% per sesi | Masuk standar stabilitas SLA 99.9% |

---

## 9. Trade-offs

Mengadopsi React Native New Architecture bukan keputusan tanpa konsekuensi. Diperlukan analisis untung-rugi secara objektif:

```
+-----------------------------------------------------------------------------------+
| KEUNTUNGAN (ADVANTAGES)                  | KERUGIAN / BIAYA (DISADVANTAGES)        |
+------------------------------------------+-----------------------------------------+
| + Eksekusi instan via direct pointer     | - Durasi kompilasi build naik signifikan|
|   (Eliminasi latency JSON serialize)     |   (CMake/NDK & Xcode C++ tooling)       |
|                                          |                                         |
| + Dynamic lazy loading TurboModules      | - Kompleksitas debugging melintasi      |
|   membuat cold start jauh lebih cepat    |   3 bahasa sekaligus (TS, C++, Kotlin/  |
|                                          |   Swift)                                |
|                                          |                                         |
| + Sinkronisasi layout via Yoga C++       | - Memerlukan penguasaan C++ modern bagi |
|   menghilangkan layout flicker & jumps   |   tim mobile engineer level enterprise  |
|                                          |                                         |
| + Strict type safety via Codegen         | - Ekosistem library third-party belum   |
|   mencegah runtime mismatch errors       |   100% mendukung Fabric/TurboModules    |
+-----------------------------------------------------------------------------------+
```

### Matriks Evaluasi Parameter Sistem

1. **Throughput vs Build Time**:
   * *Gain*: Throughput data processing antara JS dan native meningkat hingga 10x-50x.
   * *Loss*: Waktu kompilasi build Android (via Ninja/CMake) dan iOS (Clang) meningkat 30% hingga 80% pada continuous integration (CI) pipeline.
2. **Memory Efficiency vs Developer Velocity**:
   * *Gain*: Penggunaan RAM sangat hemat karena zero-copy memory references.
   * *Loss*: Pengembangan fitur native baru membutuhkan definisi skema interface Codegen dan pemahaman manajemen pointer C++ (`std::unique_ptr`, reference cycles), memperlambat *feature rollout* awal bagi tim yang belum terlatih C++.
3. **Debugging Overhead**:
   * *Issue*: *Crash stack trace* dari JSI sering kali menunjuk pada alokasi C++ internal (misal: `SIGSEGV` di `facebook::jsi::Runtime`) alih-alih file `.tsx` yang familiar, menuntut integrasi simbol *Native NDK/Crashlytics unwinding* yang mutakhir.

---

## 10. Common Mistakes & Troubleshooting

### 1. Pointer Dereference Memory Crash (`SIGSEGV` / `EXC_BAD_ACCESS`)
* **Penyebab**: Menyimpan referensi `jsi::Value` atau `jsi::Object` dalam variabel global atau thread worker tanpa mengubahnya menjadi `jsi::Value` yang di-*pinned* via `jsi::SharedArrayBuffer` atau melepaskan kepemilikan setelah runtime JS di-reload/hancur.
* **Solusi**: Jangan pernah mempertahankan raw reference `jsi::Value` di luar scope fungsi host invocation tanpa membungkusnya dalam smart lifecycle tracker atau menyalin data primitif ke dalam C++ data structures (`std::string`, `double`).

### 2. Codegen Spec Mismatch Saat Build Time
* **Gejala Error**: 
  ```text
  FAILURE: Build failed with an exception.
  Execution failed for task ':app:generateCodegenArtifactsFromSchema'.
  > Type 'Float' is not supported in TurboModule specs. Use 'Double' instead.
  ```
* **Solusi**: Periksa aturan tipe Codegen React Native: Codegen tidak mendukung tipe angka arbitrary atau union dinamis bebas. Hanya gunakan tipe yang valid: `number` (diterjemahkan ke `double`), `boolean`, `string`, `Object` (dengan bentuk strict), atau `unsafe-to-use` types jika terpaksa.

### 3. Hermes Bytecode Version Incompatibility
* **Gejala Error**: Aplikasi mengalami instan crash saat peluncuran: `Hermes engine bytecode version mismatch`.
* **Solusi**: Terjadi ketika versi compiler bytecode CLI (host machine) tidak identik dengan versi runtime library Hermes VM yang di-link ke APK/IPA. Wajib samakan versi `react-native` dan runtime artifacts di `android/app/build.gradle` atau gunakan dynamic Hermes linking:
  ```groovy
  // android/app/build.gradle
  project.ext.react = [
      enableHermes: true,  // Hermes otomatis tersinkronisasi via React Native Gradle Plugin
  ]
  ```

### 4. Sinkronisasi Antar-Thread yang Memblokir UI Thread (Deadlock)
* **Penyebab**: Memanggil fungsi native sinkron via JSI dari JS Thread, di mana fungsi C++ tersebut mencoba menunggu lock (`std::mutex`) yang sedang dipegang oleh Main UI Thread.
* **Solusi**: Jangan pernah menaruh mutex synchronizations yang menunggu operasi Main Thread di dalam JSI direct call. JSI synchronous calls harus bersifat *compute-only* atau *lock-free thread-safe atomic access*.

---

## 11. Best Practices (Production Checklist)

Gunakan daftar periksa teknis ini sebelum merilis aplikasi berbasis New Architecture ke tahap produksi:

- [ ] **Aktifkan Hermes Compaction & Hades GC**: Pastikan bendera compiler Hermes menyertakan optimasi ukuran bytecode `-O` dan profiling aktif pada stage build release.
- [ ] **Isolasi Logika Komputasi Berat di TurboModules C++**: Operasi seperti pengolahan parsing JSON berukuran > 5MB, enkripsi, dan kompresi gambar harus di-porting ke C++ JSI Module.
- [ ] **Minimalisasi Bridge Invocations Tersisa**: Pastikan tidak ada dependensi lama (*legacy libraries*) yang memaksa aplikasi menjalankan compatibility layer (`Bridge Subsystem`) secara aktif di latar belakang.
- [ ] **Gunakan Direct Struct Initialization**: Hindari *unnecessary casting* antar `std::string` dan `jsi::String` di dalam hot path perulangan C++.
- [ ] **Validasi Proguard / R8 Preservation Rules**: Pastikan class generator Codegen tidak terhapus oleh optimizer byte-code:
  ```proguard
  # Proguard rules for Codegen & JSI
  -keep class com.facebook.react.turbomodule.** { *; }
  -keep class com.facebook.jni.** { *; }
  -keep class com.facebook.react.bridge.JavaScriptContextHolder { *; }
  ```
- [ ] **Strict Typing pada TS Specs**: Tidak boleh ada tipe `any` pada spesifikasi TypeScript TurboModule. Seluruh field payload harus typed eksplisit.
- [ ] **Konfigurasi C++ Build Caching (ccache)**: Pasang `ccache` di pipeline CI/CD untuk memangkas durasi build kompilasi native C++ hingga 60%.

---

## 12. Hands-on Practice

Implementasi langkah demi langkah pembuatan modul produksi berkinerja tinggi: **`NativeDeviceIntegrity` TurboModule** yang mendeteksi rooting/jailbreak via C++ dan mengeksposnya ke TypeScript via JSI.

Direktori target: `hands-on/m02/`

### Struktur Direktori yang Akan Dibuat
```text
hands-on/m02/
├── package.json
├── src/
│   ├── index.ts
│   └── specs/
│       └── NativeDeviceIntegrity.ts
├── android/
│   ├── CMakeLists.txt
│   └── build.gradle
├── cpp/
│   ├── NativeDeviceIntegrity.h
│   └── NativeDeviceIntegrity.cpp
└── ios/
    └── NativeDeviceIntegrity.podspec
```

### Langkah 1: Siapkan `package.json` untuk Modul TurboModule
```json
{
  "name": "native-device-integrity",
  "version": "1.0.0",
  "description": "High performance C++ JSI Device Integrity Engine",
  "main": "src/index.ts",
  "codegenConfig": {
    "name": "NativeDeviceIntegritySpec",
    "type": "modules",
    "jsTransforms": false,
    "android": {
      "javaPackageName": "com.enterprisecrypto.integrity"
    }
  },
  "peerDependencies": {
    "react-native": "*"
  }
}
```

### Langkah 2: Buat Spesifikasi TypeScript Codegen
```typescript
// path: hands-on/m02/src/specs/NativeDeviceIntegrity.ts
import type { TurboModule } from 'react-native';
import { TurboModuleRegistry } from 'react-native';

export interface Spec extends TurboModule {
  isCompromisedSync(): boolean;
  getDeviceRiskScore(salt: string): Promise<number>;
}

export default TurboModuleRegistry.getEnforcing<Spec>('NativeDeviceIntegrity');
```

### Langkah 3: Implementasi Native C++ Header
```cpp
// path: hands-on/m02/cpp/NativeDeviceIntegrity.h
#pragma once

#include <jsi/jsi.h>
#include <memory>

namespace enterprise::security {

using namespace facebook;

class NativeDeviceIntegrity : public jsi::HostObject {
public:
  NativeDeviceIntegrity();
  virtual ~NativeDeviceIntegrity() = default;

  jsi::Value get(jsi::Runtime &runtime, const jsi::PropNameID &name) override;
  std::vector<jsi::PropNameID> getPropertyNames(jsi::Runtime &runtime) override;

private:
  bool evaluateJailbreakSigns();
  double calculateRiskScore(const std::string &salt);
};

} // namespace enterprise::security
```

### Langkah 4: Implementasi Native C++ Logic
```cpp
// path: hands-on/m02/cpp/NativeDeviceIntegrity.cpp
#include "NativeDeviceIntegrity.h"
#include <sys/stat.h>
#include <unistd.h>
#include <vector>
#include <string>

namespace enterprise::security {

NativeDeviceIntegrity::NativeDeviceIntegrity() {}

bool NativeDeviceIntegrity::evaluateJailbreakSigns() {
  // Simulasi deteksi keberadaan binary su / dangerous paths
  const std::vector<std::string> dangerousPaths = {
    "/system/app/Superuser.apk",
    "/sbin/su",
    "/system/bin/su",
    "/system/xbin/su",
    "/data/local/xbin/su",
    "/Applications/Cydia.app",
    "/Library/MobileSubstrate/MobileSubstrate.dylib",
    "/bin/bash",
    "/usr/sbin/sshd"
  };

  for (const auto &path : dangerousPaths) {
    struct stat buffer;
    if (stat(path.c_str(), &buffer) == 0) {
      return true; // Perangkat terindikasi di-root / jailbreak
    }
  }
  return false;
}

double NativeDeviceIntegrity::calculateRiskScore(const std::string &salt) {
  bool compromised = evaluateJailbreakSigns();
  double baseScore = compromised ? 85.0 : 5.0;
  // Kalkulasi berbasis parameter
  return baseScore + (salt.length() % 10);
}

jsi::Value NativeDeviceIntegrity::get(jsi::Runtime &runtime, const jsi::PropNameID &name) {
  std::string prop = name.utf8(runtime);

  if (prop == "isCompromisedSync") {
    return jsi::Function::createFromHostFunction(
      runtime,
      name,
      0,
      [this](jsi::Runtime &rt, const jsi::Value &thisVal, const jsi::Value *args, size_t count) -> jsi::Value {
        bool isCompromised = this->evaluateJailbreakSigns();
        return jsi::Value(isCompromised);
      }
    );
  }

  if (prop == "getDeviceRiskScore") {
    return jsi::Function::createFromHostFunction(
      runtime,
      name,
      1,
      [this](jsi::Runtime &rt, const jsi::Value &thisVal, const jsi::Value *args, size_t count) -> jsi::Value {
        if (count < 1 || !args[0].isString()) {
          throw jsi::JSError(rt, "Parameter salt (string) diperlukan.");
        }
        std::string salt = args[0].getString(rt).utf8(rt);
        
        // Buat Promise via JSI Object API
        auto promiseConstructor = rt.global().getPropertyAsFunction(rt, "Promise");
        
        auto hostPromiseCallback = [this, salt](jsi::Runtime &innerRt, const jsi::Value &innerThis, const jsi::Value *innerArgs, size_t innerCount) -> jsi::Value {
          auto resolve = innerArgs[0].getObject(innerRt).getFunction(innerRt);
          double score = this->calculateRiskScore(salt);
          resolve.call(innerRt, jsi::Value(score));
          return jsi::Value::undefined();
        };

        return promiseConstructor.callAsConstructor(
          rt,
          jsi::Function::createFromHostFunction(rt, jsi::PropNameID::forUtf8(rt, "PromiseExecutor"), 2, hostPromiseCallback)
        );
      }
    );
  }

  return jsi::Value::undefined();
}

std::vector<jsi::PropNameID> NativeDeviceIntegrity::getPropertyNames(jsi::Runtime &runtime) {
  std::vector<jsi::PropNameID> props;
  props.push_back(jsi::PropNameID::forUtf8(runtime, "isCompromisedSync"));
  props.push_back(jsi::PropNameID::forUtf8(runtime, "getDeviceRiskScore"));
  return props;
}

} // namespace enterprise::security
```

### Langkah 5: Android Build Descriptor (`CMakeLists.txt`)
```cmake
# path: hands-on/m02/android/CMakeLists.txt
cmake_minimum_required(VERSION 3.13)
project(NativeDeviceIntegrity)

set(CMAKE_CXX_STANDARD 17)

add_library(
  nativedeviceintegrity
  SHARED
  ../cpp/NativeDeviceIntegrity.cpp
)

find_package(ReactAndroid REQUIRED)

target_include_directories(
  nativedeviceintegrity
  PRIVATE
  ../cpp
  ${REACT_COMMON_DIR}
)

target_link_libraries(
  nativedeviceintegrity
  ReactAndroid::jsi
)
```

### Langkah 6: Entry Point File (`src/index.ts`)
```typescript
// path: hands-on/m02/src/index.ts
import NativeDeviceIntegrity from './specs/NativeDeviceIntegrity';

export class DeviceIntegrityService {
  /**
   * Eksekusi langsung tanpa asynchronous frame lag.
   * Sangat krusial untuk dipanggil sebelum merender sensitive transaction screen.
   */
  public static verifyDeviceSafetyInstant(): boolean {
    const isRooted = NativeDeviceIntegrity.isCompromisedSync();
    if (isRooted) {
      console.error("[CRITICAL] Integritas device terkompromi! Menolak eksekusi flow.");
      return false;
    }
    return true;
  }

  public static async fetchRiskAssessment(sessionSalt: string): Promise<number> {
    return await NativeDeviceIntegrity.getDeviceRiskScore(sessionSalt);
  }
}

export default NativeDeviceIntegrity;
```

---

## 13. Exercise

### Latihan 1: Level Easy
* **Tugas**: Buat sebuah spesifikasi TypeScript Codegen bernama `NativeSystemInfo` yang memiliki method sinkronus `getDeviceUptime(): number` dan method asinkronus `getHardwareModel(): Promise<string>`.
* **Kebutuhan**: Validasi tipe secara ketat menggunakan generic interface `TurboModule` dan daftarkan melalui `TurboModuleRegistry.getEnforcing`.

### Latihan 2: Level Medium
* **Tugas**: Implementasikan fungsi C++ JSI host function `calculateLevenshteinDistance(str1: string, str2: string): number` di dalam sebuah HostObject.
* **Kebutuhan**: Algoritma kalkulasi jarak string harus murni berjalan di C++ memori buffer tanpa membuat alokasi string baru di level JavaScript. Error handling harus melempar `jsi::JSError` jika input bukan string.

### Latihan 3: Level Hard
* **Tugas**: Buat sebuah arsitektur background thread dispatcher menggunakan C++ `std::thread` yang menerima array numerik besar (1.000.000 data floats) dari JavaScript via `jsi::ArrayBuffer`.
* **Kebutuhan**: Lakukan kalkulasi Fast Fourier Transform (FFT) atau penghitungan standard deviation di C++ background thread tersebut, lalu kembalikan hasilnya via JavaScript Promise resolution tanpa memblokir thread render utama UI maupun Hermes JS thread.

---

## 14. Challenge

### Studi Kasus: High-Frequency Real-Time Financial L2-OrderBook Engine

#### Skenario Masalah
Sebuah bursa komoditas internasional memerlukan modul orderbook yang mampu memproses **10.000 mutasi volume per detik** yang diterima via gRPC stream langsung di perangkat mobile.

Jika mutasi dialirkan melalui `setState` React tradisional, Virtual DOM reconciliation akan menumpuk di antrean event loop JS, memicu alokasi memory leak hingga 500 MB, serta menurunkan frame rate antarmuka ke 0 FPS (*total application crash*).

#### Spesifikasi Tantangan
1. Bangun pipeline custom **Fabric Component** bernama `<HighThroughputOrderBookView />` yang terhubung langsung dengan **C++ JSI Shared Ring Buffer**.
2. Aliran paket data biner masuk langsung ditangani oleh C++ background thread worker. Thread ini memutasi *Fabric Shadow Tree* secara langsung tanpa memicu JavaScript React Reconciliation loop.
3. Buat skema *Double-Buffering C++ mechanism*: UI thread hanya membaca buffer render yang telah distabilkan, sementara background network thread mengisi buffer sekunder secara atomic (`std::atomic_flag`).
4. Komponen UI native harus merender visual depth-chart dan order book list secara mulus pada kecepatan rendering native 120Hz pada layar iPad Pro / Samsung Galaxy Ultra tanpa kehilangan frame (*zero frame drop*).

#### Kriteria Keberhasilan
* Penggunaan CPU perangkat secara keseluruhan tidak melebihi 15% pada beban 10.000 updates/detik.
* Alokasi RAM konstan (flatline profile, toleransi fluktuasi < 5%).
* Tidak ada jeda atau glitch pada sentuhan pengguna (gestur *pinch-to-zoom* pada chart tetap responsif di 120 FPS).

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Soal)

1. **Apa perbedaan mendasar antara JSI (JavaScript Interface) dan Legacy Bridge?**
   * *Jawaban*: Legacy Bridge mengandalkan serialisasi asinkronus pesan berbasis string JSON yang dikirim melalui antrean FIFO lintas proses/thread, sedangkan JSI mengekspos objek dan method native (C++) secara langsung ke JavaScript engine via shared memory pointer, memungkinkan eksekusi sinkronus dan zero-serialization.

2. **Mengapa TurboModules diinisialisasi secara lazy, dan apa dampaknya pada cold start aplikasi?**
   * *Jawaban*: Karena TurboModules hanya dibuat dan dimuat ke memori saat kode JavaScript pertama kali memanggilnya (`on-demand`). Ini memangkas waktu inisialisasi awal (*cold start time*) secara signifikan dibanding Legacy Modules yang seluruhnya diinstansiasi secara *eager* saat aplikasi pertama kali menyala.

3. **Apa peran dari Yoga Engine dalam Fabric Renderer?**
   * *Jawaban*: Yoga Engine adalah pustaka layout lintas platform berbasis C++ yang bertugas menerjemahkan aturan flexbox styling menjadi koordinat fisik pixel absolut (*width, height, top, left*) secara langsung di level C++ Shadow Tree sebelum dimount ke native view OS.

4. **Apa fungsi utama dari Hades Garbage Collector pada Hermes VM?**
   * *Jawaban*: Hades berfungsi menjalankan mayoritas operasi penandaan (*marking*) dan pembersihan (*sweeping*) memori JavaScript di background thread secara konkuren, meminimalkan jeda waktu henti sistem (*stop-the-world pauses*) demi mencegah terjadinya frame drop/jank pada UI.

5. **Apa fungsi Codegen dalam implementasi TurboModules dan Fabric?**
   * *Jawaban*: Codegen secara statis mem-parsing file spesifikasi bertipe ketat (TypeScript atau Flow) untuk menghasilkan file interface C++, Java JNI, dan Objective-C secara otomatis saat proses build, menjamin validitas tipe (*compile-time type safety*) antar bahasa.

---

### Bagian 2: Intermediate (5 Soal)

6. **Mengapa Fabric Shadow Tree didesain bersifat *immutable* (tidak dapat dimutasi langsung)?**
   * *Jawaban*: Desain *immutable* memungkinkan Shadow Tree dimanipulasi secara aman di lintas banyak thread (*thread-safe*) tanpa memerlukan mekanisme thread-locking yang kompleks dan rawan deadlock. Setiap perubahan status menghasilkan kloningan node baru melalui prinsip *structural sharing*.

7. **Bagaimana cara menangani pemanggilan method native yang memerlukan waktu komputasi panjang via JSI tanpa memblokir JS thread?**
   * *Jawaban*: Dengan membuat fungsi C++ yang mengembalikan JavaScript `Promise` via JSI. Komputasi berat kemudian dilempar ke thread pool C++ terpisah (`std::async` atau thread worker), dan setelah selesai, thread pool tersebut memanggil callback `resolve` atau `reject` pada runtime JS.

8. **Apa yang terjadi jika Anda memanggil method JSI yang mengakses UI View langsung dari non-UI thread di platform Android?**
   * *Jawaban*: Android akan melempar exception fatal `CalledFromWrongThreadException`, karena subsistem view Android hanya dapat dimutasi secara legal dari Main UI Thread (Looper thread). Modifikasi view harus dijadwalkan ke Main Looper via dispatch queue.

9. **Apa perbedaan mendasar siklus rendering Fabric: Fase *Render*, *Commit*, dan *Mount*?**
   * *Jawaban*: Fase *Render* mengeksekusi JSX dan membangun C++ Shadow Tree; Fase *Commit* menjalankan kalkulasi tata letak flexbox menggunakan Yoga Engine; Fase *Mount* menghitung selisih (diffing) antar Shadow Tree dan mengeksekusi mutasi tampilan fisik di Native View OS layer.

10. **Bagaimana JSI mengelola siklus hidup memori objek C++ yang direferensikan oleh variabel JavaScript?**
    * *Jawaban*: Menggunakan kelas pembungkus `jsi::HostObject`. Hermes VM melacak masa pakai referensi JavaScript tersebut. Saat objek JS di-garbage collect oleh Hades GC, destruktor C++ HostObject yang terikat secara otomatis dipicu dan memori native dibebaskan.

---

### Bagian 3: Skenario Kasus Produksi (3 Soal)

11. **Skenario A**: Tim Anda mendapati crash log di produksi dengan error `SIGSEGV: Fault address: 0x0` yang terjadi acak di dalam method `jsi::Function::call`. Setelah diteliti, pemanggilan native ini terjadi sesaat setelah user menutup (unmount) layar kamera. Apa penyebab arsitekturalnya dan bagaimana memperbaikinya?
    * *Analisis & Solusi*: Ini adalah skenario *dangling pointer* atau *use-after-free*. JavaScript runtime mencoba memanggil callback native C++ yang dependensinya (misal: camera hardware handle) telah dihancurkan saat komponen React unmount. Solusinya: Implementasikan mekanisme validasi thread-safe token (`std::weak_ptr` atau atomic cancellation flags) pada C++ HostObject untuk membatalkan eksekusi jika native context telah hancur sebelum callback dieksekusi.

12. **Skenario B**: Aplikasi e-commerce enterprise Anda yang telah bermigrasi ke New Architecture mengalami kegagalan build di pipeline CI/CD Linux Docker, namun berjalan normal di MacBook lokal milik tim developer. Pesan log build error adalah `Ninja: error: build.ninja: No such file or directory` pada langkah `:app:generateCodegenArtifactsFromSchema`. Di mana letak masalahnya?
    * *Analisis & Solusi*: Masalah berasal dari perbedaan path file system (*case-sensitivity*) atau ketidakcocokan versi NDK/CMake pada image Docker Linux dibanding macOS. Selain itu, Codegen memerlukan Node binary environment yang terdefinisi dengan benar di pipeline CI untuk mengeksekusi script generator. Solusinya: Pastikan versi Android NDK spesifik (misal: 25.1.8937393) didefinisikan secara eksplisit di file `android/app/build.gradle` dan environment path `NODE_BINARY` dipassing ke proses build Gradle di dalam Docker script.

13. **Skenario C**: Modul grafik performa tinggi aplikasi trading Anda merender grafik candlestick. Saat menggunakan Bridge lama, data 60 frame per detik mengalami jeda yang membuat scrolling lag. Setelah di-porting ke Fabric dan TurboModules, scrolling lancar, namun konsumsi daya baterai perangkat melonjak drastis. Apa kesalahan optimasi yang mungkin terjadi di layer C++ Fabric?
    * *Analisis & Solusi*: Lonjakan konsumsi baterai mengindikasikan terjadinya *over-commit* atau *busy-waiting looping* pada kalkulasi layout C++. Kemungkinan besar, custom Fabric component memicu instruksi *Shadow Tree recreation* secara terus-menerus pada setiap frame tanpa memanfaatkan mekanisme memoization atau structural diffing Yoga Engine. Solusinya: Terapkan dirty flags pada Shadow Node C++ (`setDirty(true)` hanya jika input data benar-benar berubah), dan hindari mutasi properti yang memicu relayout seluruh root tree hierarchy.

---

## 16. Summary

1. **JSI (JavaScript Interface)** mengakhiri era komunikasi asinkron berbasis JSON string Bridge, menggantikannya dengan interaksi memori langsung (*in-memory shared pointers*) yang mengeksekusi fungsi lintas bahasa secara instan.
2. **TurboModules** menyelesaikan masalah konsumsi memori dan kelambatan startup aplikasi melalui pemuatan modul secara bertahap (*lazy-loading*) serta integritas tipe lintas platform yang diverifikasi sejak kompilasi (*compile-time safety*) via **Codegen**.
3. **Fabric Renderer** memisahkan pipeline rendering ke dalam 3 tahapan formal (*Render, Commit, Mount*), memanfaatkan **Yoga Engine** secara native di layer C++ untuk kalkulasi layout yang sepenuhnya sinkron dan anti-flicker.
4. **Hermes & Hades GC** dioptimalkan secara arsitektural untuk ekosistem React Native, memangkas ukuran memori, mempercepat eksekusi via *Ahead-Of-Time bytecode compilation*, dan mengeliminasi *stop-the-world GC lag*.
5. Penguasaan New Architecture adalah syarat mutlak bagi software engineer tingkat lanjut untuk merancang aplikasi mobile berskala enterprise yang stabil, aman, dan beroperasi mulus pada frame rate 60/120 FPS.