# Bab 07: Native Modules, Bridge, JSI & Custom Extensions
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menguasai Arsitektur JSI (JavaScript Interface)**: Memahami secara mendalam abstraksi C++ runtime engine (Hermes/V8), siklus hidup memori objek (`jsi::Runtime`, `jsi::Value`, `jsi::HostObject`), dan eliminasi runtime serialization.
2. **Mengimplementasikan TurboModules Berbasis Spesifikasi (New Architecture)**: Membangun custom TurboModules end-to-end menggunakan React Native Codegen, TypeScript specifications, C++ implementations, serta bridge interface untuk Android (NDK/JNI) dan iOS (Objective-C++).
3. **Mengoptimalkan Zero-Copy Memory Management**: Memanfaatkan `jsi::ArrayBuffer` untuk memproses data biner skala besar (seperti pemrosesan citra, payload terenkripsi, atau stream audio) langsung antara V8/Hermes heap dan memori native tanpa alokasi ganda.
4. **Menerapkan Pola Eksekusi Multi-threaded Asinkron**: Menggunakan `facebook::react::CallInvoker` untuk memindahkan komputasi berat ke worker pool thread native di C++ dan mengeksekusi callback ke JavaScript thread secara thread-safe tanpa memblokir antarmuka UI.
5. **Mendiagnosis Kerusakan Tingkat Rendah (Low-Level Faults)**: Mengidentifikasi, mengisolasi, dan memitigasi memory leak, race conditions, serta fatal signal (`SIGSEGV`, `SIGBUS`, `SIGABRT`) yang terjadi pada layer C++/JNI.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
* Arsitektur dasar React Native: Siklus hidup komponen, rendering pipeline, dan konsep thread JS vs UI Thread.
* Bahasa pemrograman modern **C++ (standar C++17/C++20)**: Pointer semantik, RAII (*Resource Acquisition Is Initialization*), `std::shared_ptr`, `std::unique_ptr`, move semantics, lambda closures, dan concurrent programming (`std::mutex`, `std::atomic`).
* Konsep runtime mesin JavaScript: Call stack, heap allocation, Garbage Collection (GC roots, tracing vs reference counting).
* Konsep platform native:
  * **Android**: NDK (*Native Development Kit*), CMake compilation, JNI (*Java Native Interface*) memory tables (`jobject`, `jclass`, local vs global references).
  * **iOS**: Objective-C++ (`.mm`), ARC (*Automatic Reference Counting*), CocoaPods build system.
* Telah menyelesaikan Bab 07 Modul 01 (*Fundamental Native Modules & Legacy Bridge Architecture*).

---

### 3. Concept & Internal Architecture (Mendalam)

#### Evolusi: Dari JSON Bridge ke JSI

Pada arsitektur lama (Legacy Architecture), seluruh komunikasi antara runtime JavaScript dan layer Native (Java/Kotlin atau Obj-C/Swift) harus melalui antrean asinkron (Bridge). Data di-serialize menjadi untaian JSON string di JS thread, dipindahkan melalui *message queue*, dialokasikan ulang di native thread, dan di-*deserialize*. 

React Native New Architecture menggantikan mekanisme ini dengan **JSI (JavaScript Interface)**. JSI bukanlah framework khusus React Native, melainkan abstraksi layer tipis C++ yang memungkinkan mesin JavaScript (Hermes, V8, JavaScriptCore) mengekspos pointer referensi C++ langsung ke konteks runtime JS, dan sebaliknya.

```
+-------------------------------------------------------------------------+
|                           JavaScript Runtime (Hermes)                   |
|                                                                         |
|  const client = new SecureCryptoClient();                               |
|  const hash = client.sha256(arrayBuffer); // Langsung memanggil JSI     |
+------------------------------------+------------------------------------+
                                     | Pointer Call Langsung (Zero JSON)
                                     v
+------------------------------------+------------------------------------+
|                   JSI Layer (C++ Abstraction)                          |
|                                                                         |
|  - jsi::HostObject::get(...)                                            |
|  - jsi::Value invoke(...)                                               |
|  - jsi::ArrayBuffer memory mapping                                      |
+------------------------------------+------------------------------------+
                                     |
           +-------------------------+-------------------------+
           | Direct C++ Function Binding                       |
           v                                                   v
+-----------------------+                         +-----------------------+
| Android Native Layer  |                         | iOS Native Layer      |
| (JNI / NDK / OpenSSL) |                         | (Obj-C++ / CryptoKit) |
+-----------------------+                         +-----------------------+
```

#### Struktur Data Inti JSI

1. **`facebook::jsi::Runtime`**: Mewakili konteks eksekusi engine JS. Thread yang memegang referensi ke objek `Runtime` harus mematuhi thread-affinity: operasi pemanggilan fungsi JSI **hanya boleh** dilakukan pada thread tempat `Runtime` tersebut terikat (JS Thread).
2. **`facebook::jsi::Value`**: Tipe data serbaguna (tagged union) yang merepresentasikan semua tipe nilai JS: `undefined`, `null`, `boolean`, `number`, `string`, `symbol`, dan `object`.
3. **`facebook::jsi::HostObject`**: Kelas dasar C++ abstrak yang diturunkan oleh developer. Ketika objek turunan didaftarkan ke runtime JS, setiap akses properti atau eksekusi fungsi pada objek JS tersebut dialihkan secara sinkron (*synchronous interception*) ke method C++:
   * `virtual Value get(Runtime& runtime, const PropNameID& name);`
   * `virtual void set(Runtime& runtime, const PropNameID& name, const Value& value);`
   * `virtual std::vector<PropNameID> getPropertyNames(Runtime& runtime);`
4. **`facebook::react::CallInvoker`**: Mekanisme koordinasi thread yang disediakan oleh React Native core. Digunakan untuk memasukkan callback ke antrean eksekusi JS thread dari worker thread C++ independen.

---

### 4. Why & What

| Dimensi | Legacy Bridge | JSI & TurboModules |
| :--- | :--- | :--- |
| **Model Eksekusi** | Asinkron murni (Fire-and-forget dengan asynchronous batching). | Sinkron secara native, dapat dijadikan asinkron via `CallInvoker`. |
| **Overhead Komunikasi** | Serialisasi JSON (CPU & Memory overhead besar, latency berfluktuasi). | Invokasi pointer C++ langsung. Waktu eksekusi instan ($O(1)$ dispatch). |
| **Transfer Data Biner** | Base64 string encoding/decoding (peningkatan ukuran payload ~33%). | `jsi::ArrayBuffer` zero-copy memory access langsung ke native buffer pointer. |
| **Inisialisasi Modul** | Eager loading saat aplikasi startup (memperlambat Cold Start TTI). | Lazy loading via TurboModule Registry (hanya diinisialisasi saat pertama dipanggil). |
| **Type Safety** | Lemah. Mengandalkan validasi manual di Java/Obj-C saat parsing dictionary. | Kuat. Divalidasi di compile-time melalui Codegen (TypeScript $\to$ C++ Spec). |

**Mengapa Anda Membutuhkannya di Enterprise?**
Ketika membangun aplikasi skala besar (misal: trading berkecepatan tinggi, perbankan dengan enkripsi end-to-end, pemrosesan media offline, augmented reality), *Legacy Bridge* menjadi titik leher botol (*bottleneck*). Terjadinya bridge congestion menyebabkan UI stuttering (frame drop). JSI memungkinkan operasi sinkron berlatensi sub-milidetik dan pemrosesan biner murni tanpa menyumbat event loop.

---

### 5. How (Workflow Detail)

Alur kerja implementasi TurboModule berbasis JSI:

```
[1] Tulis TypeScript Spec (.ts)
        |
        v
[2] Eksekusi React Native Codegen
        |
        +---> Output: C++ Interface Abstract Classes (Spec.h & Spec.cpp)
        |
        v
[3] Implementasi Core Logic di C++ (Cross-Platform)
        |
        +---> Integrasi CallInvoker untuk Asynchronous / Thread Pooling
        |
        v
[4] Binding Platform Native
        |
        +---> Android: Register via CMakeLists.txt & JNI OnLoad / Autolinking
        +---> iOS: Register via Podspec & Objective-C++ (.mm) Wrapper
        |
        v
[5] Konsumsi di JavaScript via TurboModuleRegistry
```

1. **Definisi Kontrak Spec**: Buat file `Native<ModuleName>.ts` dengan anotasi `TurboModuleRegistry.getEnforcing<Spec>('<ModuleName>')`.
2. **Kompilasi Codegen**: Skrip build mengonversi spesifikasi TS menjadi abstract base classes C++.
3. **Konkretisasi C++**: Turunkan kelas C++ abstrak tersebut, implementasikan method bisnis, dan atur alokasi memori menggunakan RAII.
4. **Binding Platform**: Konfigurasikan dynamic linker untuk Android (`CMakeLists.txt`) dan iOS (`.podspec`), memastikan simbol teregistrasi pada `TurboModuleManager`.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Kantor Pos vs Teleportasi Memori

* **Legacy Bridge (Kantor Pos)**: Anda (JS Thread) ingin mengirim buku besar ke akuntan (Native Thread). Anda harus memfotokopi buku menjadi kertas-kertas teks (JSON), membungkusnya dalam amplop, membawanya ke kantor pos (Message Queue), menunggu truk pengangkut berangkat, lalu akuntan membuka amplop dan menyusunnya kembali menjadi buku baru. Sangat lambat dan memboroskan kertas.
* **JSI (Teleportasi Memori)**: Anda membuka portal langsung ke meja akuntan. Anda meletakkan penunjuk jari langsung pada halaman buku fisik Anda di C++ heap. Akuntan membaca dan menulis di halaman yang sama seketika tanpa perantara dan tanpa duplikasi data.

#### Arsitektur Aliran Memori & Thread JSI

```
+----------------------------------------------------------------------------------------+
|                                  PROCESS HEAP MEMORY                                   |
|                                                                                        |
|  +-------------------------------------+      +-------------------------------------+  |
|  |           JavaScript Heap           |      |              C++ Heap               |  |
|  |                                     |      |                                     |  |
|  |  +-------------------------------+  |      |  +-------------------------------+  |  |
|  |  | jsi::ArrayBuffer Host Object  |=======> |  | Raw Buffer (uint8_t*)         |  |  |
|  |  | [Pointer: 0x7FFEE4B2]         |  |      |  | Memory Address: 0x7FFEE4B2    |  |  |
|  |  +-------------------------------+  |      |  +---------------+---------------+  |  |
|  +------------------^------------------+      +------------------|------------------+  |
|                     |                                            |                     |
+---------------------|--------------------------------------------|---------------------+
                      | Direct Reference                           | Direct Execution
+---------------------|------------------+      +------------------v------------------+
|          JavaScript Thread             |      |       Native Worker Thread Pool     |
|                                        |      |                                     |
| 1. Memanggil Native Module             |      | 1. Terima raw memory pointer        |
| 2. Menunggu via Promise                |      | 2. Enkripsi / Transformasi paralel  |
| 3. Menerima notifikasi dari Invoker    | <====| 3. Dispatch via CallInvoker         |
+----------------------------------------+      +-------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Raw JSI HostObject (Synchronous Direct Call)

Contoh C++ HostObject yang mengekspos kalkulasi hash sederhana secara sinkron ke JavaScript tanpa melalui Java/Obj-C bridge.

```cpp
// SimpleHashHostObject.h
#pragma once
#include <jsi/jsi.h>

namespace enterprise::crypto {

using namespace facebook;

class SimpleHashHostObject : public jsi::HostObject {
public:
    jsi::Value get(jsi::Runtime& runtime, const jsi::PropNameID& name) override {
        auto methodName = name.utf8(runtime);

        if (methodName == "computeFastHash") {
            return jsi::Function::createFromHostFunction(
                runtime,
                name,
                1, // jumlah argumen
                [](jsi::Runtime& rt, const jsi::Value& thisVal, const jsi::Value* args, size_t count) -> jsi::Value {
                    if (count < 1 || !args[0].isString()) {
                        throw jsi::JSError(rt, "computeFastHash: Argumen 0 harus berupa String.");
                    }

                    std::string input = args[0].asString(rt).utf8(rt);
                    
                    // FNV-1a Hash Algorithm (Contoh komputasi langsung)
                    uint64_t hash = 14695981039346656037ULL;
                    for (char c : input) {
                        hash ^= static_cast<uint8_t>(c);
                        hash *= 1099511628211ULL;
                    }

                    return jsi::Value(static_cast<double>(hash));
                }
            );
        }

        return jsi::Value::undefined();
    }
};

} // namespace enterprise::crypto
```

---

#### B. Practical Example: Production-Grade TurboModule dengan Zero-Copy ArrayBuffer & Asynchronous Thread Pool

Implementasi modul kriptografi berkinerja tinggi yang memproses hashing data biner besar menggunakan multi-threading native C++ dan zero-copy `jsi::ArrayBuffer`.

##### 1. TypeScript Specification (`NativeEnterpriseCrypto.ts`)
```typescript
import { TurboModule, TurboModuleRegistry } from 'react-native';

export interface Spec extends TurboModule {
  // Komputasi sinkron latensi nol
  generateRandomBytesSync(byteLength: number): ArrayBuffer;

  // Komputasi asinkron untuk operasi data besar agar UI tidak macet
  computeSha256Async(data: ArrayBuffer): Promise<ArrayBuffer>;
}

export default TurboModuleRegistry.getEnforcing<Spec>('NativeEnterpriseCrypto');
```

##### 2. C++ Implementation Header (`EnterpriseCryptoModule.h`)
```cpp
#pragma once

#include <ReactCommon/TurboModule.h>
#include <ReactCommon/CallInvoker.h>
#include <memory>
#include <vector>

namespace enterprise::crypto {

class JSI_EXPORT EnterpriseCryptoModule : public facebook::react::TurboModule {
public:
    EnterpriseCryptoModule(std::shared_ptr<facebook::react::CallInvoker> jsInvoker);

    // Registrasi method ke runtime
    facebook::jsi::Value generateRandomBytesSync(facebook::jsi::Runtime& rt, int byteLength);
    facebook::jsi::Value computeSha256Async(facebook::jsi::Runtime& rt, const facebook::jsi::Object& arrayBufferObj);

private:
    std::shared_ptr<facebook::react::CallInvoker> jsInvoker_;
};

} // namespace enterprise::crypto
```

##### 3. C++ Implementation Source (`EnterpriseCryptoModule.cpp`)
```cpp
#include "EnterpriseCryptoModule.h"
#include <random>
#include <thread>
#include <future>

namespace enterprise::crypto {

EnterpriseCryptoModule::EnterpriseCryptoModule(std::shared_ptr<facebook::react::CallInvoker> jsInvoker)
    : TurboModule("NativeEnterpriseCrypto", jsInvoker), jsInvoker_(jsInvoker) {}

// Operasi Sinkron Zero-Copy Alokasi ArrayBuffer
facebook::jsi::Value EnterpriseCryptoModule::generateRandomBytesSync(
    facebook::jsi::Runtime& rt, 
    int byteLength
) {
    if (byteLength <= 0 || byteLength > 10 * 1024 * 1024) { // Proteksi alokasi max 10MB
        throw facebook::jsi::JSError(rt, "Ukuran byte harus antara 1 dan 10485760 bytes.");
    }

    // Alokasikan buffer langsung di JS Runtime via JSI
    facebook::jsi::Function arrayBufferCtor = rt.global().getPropertyAsFunction(rt, "ArrayBuffer");
    facebook::jsi::Object bufferObj = arrayBufferCtor.callAsConstructor(rt, byteLength).getObject(rt);
    facebook::jsi::ArrayBuffer arrayBuffer = bufferObj.getArrayBuffer(rt);

    // Ambil raw pointer ke buffer JS (Zero-copy modification)
    uint8_t* rawData = arrayBuffer.data(rt);

    // Isi dengan secure random bytes (C++11 random engine)
    std::random_device rd;
    std::independent_bits_engine<std::default_random_engine, CHAR_BIT, uint8_t> rbe(rd());
    std::generate(rawData, rawData + byteLength, std::ref(rbe));

    return bufferObj;
}

// Operasi Asinkron: Menggunakan worker thread pool & mengembalikan Promise via ArrayBuffer
facebook::jsi::Value EnterpriseCryptoModule::computeSha256Async(
    facebook::jsi::Runtime& rt, 
    const facebook::jsi::Object& arrayBufferObj
) {
    if (!arrayBufferObj.isArrayBuffer(rt)) {
        throw facebook::jsi::JSError(rt, "Argumen wajib berupa instance ArrayBuffer.");
    }

    auto sourceBuffer = arrayBufferObj.getArrayBuffer(rt);
    size_t size = sourceBuffer.size(rt);
    const uint8_t* sourceData = sourceBuffer.data(rt);

    // Salin data ke memori C++ heap lokal sebelum melompat ke thread lain
    // PENTING: JS Garbage Collector dapat memindahkan atau membebaskan sourceBuffer sewaktu-waktu!
    auto localBuffer = std::make_shared<std::vector<uint8_t>>(sourceData, sourceData + size);

    // Dapatkan Promise Constructor dari JS Runtime
    auto promiseCtor = rt.global().getPropertyAsFunction(rt, "Promise");
    
    // Simpan referensi CallInvoker lokal
    auto invoker = this->jsInvoker_;

    // Buat Promise handler
    auto executor = facebook::jsi::Function::createFromHostFunction(
        rt,
        facebook::jsi::PropNameID::forAscii(rt, "executor"),
        2,
        [localBuffer, invoker](
            facebook::jsi::Runtime& runtime,
            const facebook::jsi::Value& thisVal,
            const facebook::jsi::Value* args,
            size_t count
        ) -> facebook::jsi::Value {
            auto resolve = std::make_shared<facebook::jsi::Value>(runtime, args[0]);
            auto reject = std::make_shared<facebook::jsi::Value>(runtime, args[1]);

            // Eksekusi pekerjaan berat di Thread Pool Native
            std::thread([localBuffer, invoker, resolve, reject]() {
                try {
                    // Simulasi Digest Computation SHA-256 (32 bytes output)
                    // Pada implementasi produksi, panggil OpenSSL / BoringSSL / CommonCrypto di sini
                    std::vector<uint8_t> digest(32, 0xAB); // Dummy digest payload
                    
                    // Kembalikan hasil ke JavaScript Thread menggunakan CallInvoker
                    invoker->invokeAsync([resolve, digest = std::move(digest)](facebook::jsi::Runtime& rt) {
                        // Alokasikan ArrayBuffer untuk hasil hashing
                        facebook::jsi::Function bufCtor = rt.global().getPropertyAsFunction(rt, "ArrayBuffer");
                        facebook::jsi::Object resBuf = bufCtor.callAsConstructor(rt, static_cast<double>(digest.size())).getObject(rt);
                        
                        // Zero-copy memori transfer
                        std::memcpy(resBuf.getArrayBuffer(rt).data(rt), digest.data(), digest.size());

                        // Panggil resolve(resBuf)
                        resolve->asObject(rt).asFunction(rt).call(rt, resBuf);
                    });
                } catch (const std::exception& e) {
                    std::string errorMsg = e.what();
                    invoker->invokeAsync([reject, errorMsg](facebook::jsi::Runtime& rt) {
                        auto errorCtor = rt.global().getPropertyAsFunction(rt, "Error");
                        auto errorObj = errorCtor.callAsConstructor(rt, facebook::jsi::String::createFromUtf8(rt, errorMsg));
                        reject->asObject(rt).asFunction(rt).call(rt, errorObj);
                    });
                }
            }).detach();

            return facebook::jsi::Value::undefined();
        }
    );

    return promiseCtor.callAsConstructor(rt, executor);
}

} // namespace enterprise::crypto
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Neobank High-Throughput Offline-Sync Engine

* **Konteks Masalah**: Sebuah bank digital multinasional memiliki fitur offline-mode yang melakukan sinkronisasi delta basis data transaksional terenkripsi. Ketika aplikasi online, server mengirimkan chunk biner terenkripsi berukuran 15 MB berisi ribuan delta mutasi akun.
* **Gejala Legacy**: Pada arsitektur lama berbasis Bridge:
  1. Payload binary diubah ke format Base64 string di layer Java/Kotlin.
  2. String dikirim lewat bridge via JSON RPC: memory footprint melonjak hingga 4x lipat (memori JS engine meledak dari 15 MB ke > 60 MB), memicu GC pauses selama 400-800 ms.
  3. Aplikasi mengalami UI freeze, animasi macet, dan sering mengalami crash akibat OOM (*Out Of Memory*) pada perangkat entry-level Android.
* **Solusi Berbasis JSI/TurboModule**:
  1. Chunk biner diunduh via Native Networking (OkHttp/NSURLSession) langsung ke native memory ring-buffer.
  2. Modul JSI mengekspos chunk memory ini sebagai `jsi::ArrayBuffer` ke Hermes Engine tanpa penyalinan (*zero-copy reference*).
  3. Mesin dekripsi SQLite C++ menguraikan dan menulis rekaman secara sinkron menggunakan direct pointer execution dalam batch 5000 transaksi/tick.
* **Hasil Pengukuran (Metric Produksi)**:
  * **Waktu Sinkronisasi (100k Records)**: Turun dari 12,4 detik ke 1,1 detik (11x lebih cepat).
  * **Memory Spike**: Turun dari puncak 85 MB menjadi rata 16 MB.
  * **UI Dropped Frames**: Menurun dari 42 frame drops selama proses sinkronisasi menjadi 0 frame drops (stabil 60/120 FPS).

---

### 9. Trade-offs

| Keuntungan (Pros) | Biaya & Risiko (Cons / Trade-offs) |
| :--- | :--- |
| **Eksekusi Seketika (Near-zero latency)**: Pemanggilan fungsi native secepat memanggil fungsi JavaScript lokal ($O(1)$). | **Risiko Fatal Crash (Segmentation Fault)**: Kesalahan dereferensi pointer C++ langsung mematikan aplikasi (*SIGSEGV*), mem-bypass mekanisme proteksi JS Error Boundary. |
| **Kinerja Memori Tak Tertandingi**: Pemanfaatan `jsi::ArrayBuffer` menghilangkan proses serialisasi data besar. | **Kompleksitas Toolchain**: Membutuhkan pemeliharaan NDK, CMake, compiler flags (Clang), serta bridging ke Swift/Kotlin. |
| **Peluang Cross-Platform Reusability**: Logika C++ yang sama persis dapat dibagikan utuh 100% antara Android, iOS, dan platform lain (seperti React Native macOS/Windows). | **Debuggability Rumit**: Debugging membutuhkan runtime hybrid: LLDB untuk breakpoint C++ dan Chrome DevTools/Flipper untuk thread JS. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Melanggar Konsep Thread-Affinity JSI
* **Kesalahan Fatal**: Memanggil `jsi::Runtime` atau memodifikasi objek `jsi::Value` di dalam native thread latar belakang (`std::thread`) secara langsung.
  ```cpp
  // SALAH BESAR: Runtime bukan thread-safe!
  std::thread([&rt, resolve]() {
      resolve.asObject(rt).asFunction(rt).call(rt, true); // CRASH PASTI: SIGSEGV / Assertion failure
  }).detach();
  ```
* **Solusi**: Tangkap referensi `facebook::react::CallInvoker` dan alihkan kembali pemanggilan fungsi ke context JS:
  ```cpp
  // BENAR: Menggunakan CallInvoker
  invoker->invokeAsync([resolve](facebook::jsi::Runtime& rt) {
      resolve->asObject(rt).asFunction(rt).call(rt, true);
  });
  ```

#### 2. Dangling Pointers pada ArrayBuffer Memory
* **Kesalahan**: Menyimpan pointer `arrayBuffer.data(rt)` di worker thread C++ tanpa menyalin datanya terlebih dahulu (*dangling pointer / use-after-free*). JS Engine GC dapat merelokasi atau membersihkan buffer tersebut sebelum worker thread selesai.
* **Solusi**: Salin byte data ke kontainer C++ aman (`std::vector<uint8_t>`) jika komputasi akan dilakukan di worker thread secara asinkron.

#### 3. JNI Local Reference Table Overflow (Khusus Android)
* **Gejala**: Error `JNI ERROR (app bug): local reference table overflow (max=512)`.
* **Penyebab**: Melakukan loop pemanggilan method Java melalui JSI/JNI tanpa menghapus referensi objek Java.
* **Solusi**: Panggil `env->DeleteLocalRef(localRef)` secara eksplisit dalam loop, atau manfaatkan `PushLocalFrame` / `PopLocalFrame`.

---

### 11. Best Practices (Production Checklist)

- [ ] **Tipe Data Strict**: Selalu gunakan Type Definition TypeScript yang ketat pada TurboModule Spec; hindari tipe `Object` generik atau `any`.
- [ ] **RAII Pointer Guards**: Jangan pernah menggunakan alokasi memori manual (`malloc` / `new`) tanpa pembungkus *smart pointer* (`std::unique_ptr` atau `std::shared_ptr`).
- [ ] **Boundary Protection (Exception Handling)**: Bungkus seluruh blok logika C++ dengan `try-catch` dan petakan `std::exception` ke `jsi::JSError`.
- [ ] **CallInvoker Reference Lifecycle**: Pastikan closure thread tidak menahan reference siklik (*cyclic reference*) ke instance module utama untuk mencegah kebocoran memori (memory leak).
- [ ] **Hermes Engine Compatibility**: Pastikan binary C++ dikompilasi dengan flag C++17/C++20 dan ditautkan dengan ABI runtime Hermes (`libhermes.so`).

---

### 12. Hands-on Practice

Panduan membangun custom C++ JSI Module langsung di dalam repositori proyek:

#### Step 1: Struktur Direktori Proyek
Buat struktur direktori di folder proyek:
```text
hands-on/m02/
├── package.json
├── src/
│   └── NativeHardwareEntropy.ts
└── cpp/
    ├── CMakeLists.txt
    ├── HardwareEntropyModule.h
    └── HardwareEntropyModule.cpp
```

#### Step 2: Buat Spesifikasi TurboModule (`src/NativeHardwareEntropy.ts`)
```typescript
import { TurboModule, TurboModuleRegistry } from 'react-native';

export interface Spec extends TurboModule {
  getCPUTicks(): number;
  readEntropy(bytes: number): ArrayBuffer;
}

export default TurboModuleRegistry.getEnforcing<Spec>('NativeHardwareEntropy');
```

#### Step 3: Implementasi Native Header (`cpp/HardwareEntropyModule.h`)
```cpp
#pragma once
#include <jsi/jsi.h>
#include <chrono>

namespace enterprise::entropy {

class HardwareEntropyModule : public facebook::jsi::HostObject {
public:
    facebook::jsi::Value get(facebook::jsi::Runtime& rt, const facebook::jsi::PropNameID& name) override;
    std::vector<facebook::jsi::PropNameID> getPropertyNames(facebook::jsi::Runtime& rt) override;
};

} // namespace enterprise::entropy
```

#### Step 4: Implementasi Native C++ Engine (`cpp/HardwareEntropyModule.cpp`)
```cpp
#include "HardwareEntropyModule.h"
#include <random>

namespace enterprise::entropy {

facebook::jsi::Value HardwareEntropyModule::get(
    facebook::jsi::Runtime& rt, 
    const facebook::jsi::PropNameID& name
) {
    auto propName = name.utf8(rt);

    if (propName == "getCPUTicks") {
        return facebook::jsi::Function::createFromHostFunction(
            rt, name, 0,
            [](facebook::jsi::Runtime& runtime, const facebook::jsi::Value&, const facebook::jsi::Value*, size_t) -> facebook::jsi::Value {
                auto now = std::chrono::high_resolution_clock::now();
                auto ticks = std::chrono::duration_cast<std::chrono::nanoseconds>(now.time_since_epoch()).count();
                return facebook::jsi::Value(static_cast<double>(ticks));
            }
        );
    }

    if (propName == "readEntropy") {
        return facebook::jsi::Function::createFromHostFunction(
            rt, name, 1,
            [](facebook::jsi::Runtime& runtime, const facebook::jsi::Value&, const facebook::jsi::Value* args, size_t count) -> facebook::jsi::Value {
                if (count < 1 || !args[0].isNumber()) {
                    throw facebook::jsi::JSError(runtime, "Ukuran bytes harus berupa angka positif.");
                }

                int size = static_cast<int>(args[0].asNumber());
                facebook::jsi::Function abCtor = runtime.global().getPropertyAsFunction(runtime, "ArrayBuffer");
                facebook::jsi::Object abObj = abCtor.callAsConstructor(runtime, size).getObject(runtime);
                uint8_t* bytePtr = abObj.getArrayBuffer(runtime).data(runtime);

                std::random_device rd;
                for (int i = 0; i < size; ++i) {
                    bytePtr[i] = static_cast<uint8_t>(rd() & 0xFF);
                }

                return abObj;
            }
        );
    }

    return facebook::jsi::Value::undefined();
}

std::vector<facebook::jsi::PropNameID> HardwareEntropyModule::getPropertyNames(facebook::jsi::Runtime& rt) {
    std::vector<facebook::jsi::PropNameID> props;
    props.push_back(facebook::jsi::PropNameID::forAscii(rt, "getCPUTicks"));
    props.push_back(facebook::jsi::PropNameID::forAscii(rt, "readEntropy"));
    return props;
}

} // namespace enterprise::entropy
```

#### Step 5: Android Build Configuration (`cpp/CMakeLists.txt`)
```cmake
cmake_minimum_required(VERSION 3.13)
project(HardwareEntropy)

set(CMAKE_CXX_STANDARD 17)

add_library(hardware_entropy SHARED
    HardwareEntropyModule.cpp
)

target_include_directories(hardware_entropy PRIVATE
    ${REACT_NATIVE_DIR}/ReactCommon/jsi
)

target_link_libraries(hardware_entropy
    android
    log
)
```

---

### 13. Exercise

#### Level: Easy
* **Tugas**: Tambahkan method sinkron `isHardwareAccelerated(): boolean` pada module JSI yang mengecek instruksi CPU (misal: AES-NI atau ARM NEON) via flag macro compiler C++ (`#ifdef __ARM_NEON`) dan langsung mengembalikan nilai boolean ke JS runtime.

#### Level: Medium
* **Tugas**: Buat method `compressBuffer(buffer: ArrayBuffer): ArrayBuffer` yang menggunakan algoritma kompresi cepat (misalnya LZ4 atau Deflate mentah di C++) dengan input dan output berupa `jsi::ArrayBuffer` tanpa melibatkan konversi string atau Base64 sama sekali.

#### Level: Hard
* **Tugas**: Rancang custom event emitter native berbasis C++ JSI yang memicu callback JS interval setiap 16 ms dari background thread. Pastikan sistem menerapkan pooling dan membersihkan thread secara otomatis saat komponen React Native di-unmount tanpa menyebabkan memory leak atau zombie thread.

---

### 14. Challenge

**Skenario**: Anda adalah Principal Mobile Architect di platform Telemedicine Imaging. Aplikasi menerima raw binary frames dari perangkat USG nirkabel beresolusi $1024 \times 1024$ grayscale (1 MB per frame) pada 30 FPS.
* **Tantangan Arsitektur**:
  1. Buat arsitektur pipeline pemrosesan data biner JSI yang membaca data frame tersebut.
  2. Implementasikan thread pool multi-core di C++ untuk menerapkan algoritma *Bilateral Filtering* (noise reduction) pada setiap frame secara real-time.
  3. Kembalikan data frame hasil filter ke layar (via canvas / WebGL context atau Skia) tanpa memicu alokasi memori berulang (*zero allocation in render loop*). Batas toleransi latensi per frame adalah $\le 16.6\text{ ms}$.
* **Kebutuhan Deliverable**: Dokumen spesifikasi arsitektur C++, manajemen pointer siklis (Ring-Buffer allocator), dan kode implementasi inti C++/JSI.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Apa peran utama dari JSI dalam New Architecture React Native?
2. Mengapa JSI dapat mengeksekusi method secara sinkron sedangkan Bridge lama tidak disarankan?
3. Apa fungsi spesifik dari `facebook::jsi::HostObject`?
4. Apa yang membedakan representasi data biner pada Legacy Bridge dibandingkan JSI?
5. Mengapa Lazy Loading penting dalam arsitektur TurboModules?

#### B. Pertanyaan Intermediate
6. Mengapa dereferensi pointer `jsi::Runtime` di dalam background thread C++ menyebabkan *Fatal Crash*?
7. Bagaimana peran `CallInvoker` dalam menjembatani worker thread C++ dengan JavaScript runtime?
8. Kapan developer harus menduplikasi (copy) data dari `jsi::ArrayBuffer`, dan kapan data tersebut aman dibaca langsung?
9. Apa perbedaan siklus hidup antara `jsi::Value` dan native heap pointer C++ standar?
10. Bagaimana React Native Codegen menjamin type safety di antara boundary TypeScript dan C++?

#### C. Skenario Kasus Produksi
11. **Skenario 1**: Aplikasi mengalami crash acak bertipe `SIGSEGV (SEGV_MAPERR)` hanya saat pengguna menavigasi layar dengan cepat keluar dari komponen yang sedang memproses data native asinkron. Komponen mana yang bocor dan bagaimana mitigasinya?
12. **Skenario 2**: Anda menggunakan TurboModule untuk membaca file berukuran 200 MB via memory mapping (`mmap`). Namun, memori sistem (RSS) menunjukkan lonjakan tajam dan aplikasi tertutup oleh OS (OOM Killer). Apa penyebab utama kesalahan arsitektur ini?
13. **Skenario 3**: Sebuah kalkulasi finansial diimplementasikan via JSI sinkron. Di perangkat flagship performa mulus (60 FPS), namun di perangkat kelas bawah aplikasi sering memicu dialog "Application Not Responding" (ANR). Bagaimana strategi remediasi tanpa mengorbankan fungsionalitas?

---

### Kunci Jawaban & Solusi Evaluasi

#### Jawaban Basic
1. Menyediakan abstraction layer C++ engine-agnostic yang memungkinkan JavaScript berkomunikasi langsung dengan C++ melalui pointer objek tanpa serialisasi JSON.
2. JSI mengekspos pointer memori fungsi C++ langsung ke engine JS, sehingga pemanggilan fungsi terjadi langsung pada stack frame yang sama tanpa serialisasi atau antrean message queue.
3. Kelas antarmuka C++ yang memungkinkan developer meng-intercept operasi property access (`get`/`set`) dari JavaScript secara langsung pada objek natif C++.
4. Legacy Bridge membutuhkan encoding Base64 (string-based, CPU overhead tinggi), sedangkan JSI mendukung `jsi::ArrayBuffer` untuk zero-copy memory access langsung ke buffer byte natif.
5. Menghindari pemuatan (loading) dan alokasi memori seluruh native module saat aplikasi baru dibuka, sehingga secara drastis mempercepat TTI (*Time to Interactive*) dan *Cold Start*.

#### Jawaban Intermediate
6. Karena `jsi::Runtime` tidak thread-safe dan terikat secara eksklusif ke thread eksekusi JavaScript (JS Thread). Akses paralel dari native background thread memicu *race condition* pada GC tracking dan pointer corruption.
7. `CallInvoker` bertindak sebagai thread scheduler yang mengantrekan closure C++ ke event loop JavaScript Thread agar eksekusi callback mematuhi thread-affinity runtime JS.
8. Data aman dibaca langsung jika operasi berlangsung **sinkron** di thread JS. Namun jika operasi dilakukan **asinkron** di background thread, data harus disalin (copy) karena GC dapat membebaskan atau mereorganisasi alamat memori buffer tersebut sewaktu-waktu.
9. `jsi::Value` dikelola di bawah kendali Garbage Collector runtime JS dan dapat dipindahkan/dihapus oleh GC. Sementara native heap pointer C++ dikelola manual via model alokasi runtime C++ (misal via RAII/Smart Pointers).
10. Codegen mem-parsing Abstract Syntax Tree (AST) dari interface TypeScript/Flow dan menghasilkan kelas abstrak C++ yang memiliki method signatures identik secara biner saat kompilasi.

#### Solusi Kasus Produksi
11. **Analisis Skenario 1**: Native background thread berusaha memanggil callback/Promise yang mereferensikan instance `Runtime` atau pointer JS Object yang konteksnya telah dihancurkan (*destroyed*) karena React component telah unmount. **Solusi**: Gunakan pembungkus safe-cancellation token (atau `std::weak_ptr`) dan validasi runtime validity sebelum mengeksekusi lambda di dalam `CallInvoker`.
12. **Analisis Skenario 2**: Objek `ArrayBuffer` yang dipetakan mencoba menahan 200 MB data secara contiguous langsung ke dalam virtual address space engine Hermes tanpa streaming atau chunking, sehingga melampaui batas heap limit mobile browser engine. **Solusi**: Terapkan chunked/streaming buffers (misal per 1-4 MB) atau lakukan pemrosesan strictly di layer native C++ dan hanya kirimkan hasil agregat kecil ke runtime JavaScript.
13. **Analisis Skenario 3**: Komputasi sinkron memblokir JS thread terlalu lama pada CPU perangkat low-end dengan clock speed rendah, menyebabkan event loop terhambat dan memicu ANR. **Solusi**: Ubah method menjadi asinkron: operasikan komputasi berat di native worker thread via `std::async` / thread pool C++, lalu teruskan hasil akhirnya kembali ke JS thread melalui `CallInvoker`.

---

### 16. Summary

* **Paradigma JSI**: JSI merevolusi React Native dengan mengeliminasi JSON Bridge. JSI memungkinkan pemanggilan native secepat invokasi fungsi native C++ langsung, membuka jalan bagi integrasi native berlatensi ultra-rendah.
* **Kekuatan TurboModules**: Menggabungkan ketatnya *static typing* dari TypeScript Codegen di fase kompilasi dengan efisiensi lazy-loading C++ di fase runtime.
* **Zero-Copy Memory**: Manipulasi biner skala masif kini dapat ditangani secara elegan via `jsi::ArrayBuffer`, menjadikan React Native layak untuk use-case komputasi berat seperti kriptografi, audio-DSP, dan visual-computing.
* **Prinsip Keamanan Thread**: Operasi JSI wajib sinkron terhadap JS Thread. Pekerjaan latar belakang native mutlak memerlukan pengawalan delegasi melalui `facebook::react::CallInvoker` guna menghindari memory fault dan app crash di level produksi.