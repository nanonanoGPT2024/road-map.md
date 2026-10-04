# Bab 07 Module 01: Native Modules & Bridge/JSI Custom Extensions

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** 03-Frontend-and-Mobile
*   **Topik Spesifik:** React Native Core Internals & Native Extension Engine
*   **Modul:** Bab 07 Module 01 — Native Modules & Bridge/JSI Custom Extensions
*   **Prasyarat Pengetahuan Teknis:**
    *   Pemahaman mendalam mengenai JavaScript Engine (V8, Hermes, JavaScriptCore).
    *   Sintaks dasar dan memori model C++ (C++17/C++20, smart pointers, RAII).
    *   Konsep platform-specific programming: Java/Kotlin (Android NDK/JNI) dan Objective-C/Swift (iOS runtime).
    *   Siklus hidup thread pada React Native Legacy Architecture (JS Thread, Shadow Thread, Native Main UI Thread).
*   **Target Kompetensi:**
    *   Mampu menganalisis batas performa dari Legacy Bridge Serialization Engine.
    *   Menguasai arsitektur JavaScript Interface (JSI) untuk merekayasa native binding tanpa overhead marshalling JSON.
    *   Mampu mengimplementasikan C++ TurboModule lintas platform yang dapat diakses secara sinkron (*synchronous execution*) dan asinkron (*asynchronous execution*) dari JavaScript.
    *   Mampu mengonfigurasi build automation (CMake/NDK untuk Android dan CocoaPods/Clang untuk iOS) untuk menyematkan custom extensions.

---

## SEKSI 02 — LEARNING OBJECTIVES

Pada akhir modul ini, engineer diharapkan mampu:

1.  **Membongkar Paradigma Interop React Native:** Mengartikulasikan perbedaan struktural antara asynchronous serialization berbasis JSON stringification pada Legacy Bridge dan direct memory sharing pointer-level pada JavaScript Interface (JSI).
2.  **Membangun C++ Host Object:** Menulis implementasi custom runtime C++ `facebook::jsi::HostObject` yang mengekspos fungsi C++ langsung ke JavaScript context tanpa passing overhead.
3.  **Menerapkan TurboModule Spec-Driven Development:** Menulis typed spec menggunakan Flow/TypeScript, menurunkan interface menggunakan Codegen, dan mengimplementasikannya di level platform native (Android C++/Java dan iOS C++/Objective-C++).
4.  **Mengeliminasi Performance Bottleneck Komputasi Berat:** Memindahkan operasi enkripsi kriptografi, transformasi matriks gambar, atau kalkulasi telemetri berfrekuensi tinggi (60/120 Hz) dari JS thread ke native execution path secara sinkron (latency < 1ms).
5.  **Memitigasi Resource Leak dan Race Condition:** Mengelola alokasi dynamic memory, lifecycle C++ reference counter (`std::shared_ptr`), dan thread synchronization (`std::mutex`, GCD, Android Looper) pada boundary hybrid platform.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Mental Model JSI vs Bridge

Bayangkan dua orang yang bekerja di dua ruangan terpisah: Ruangan JS dan Ruangan Native (C++/Kotlin/Swift).

```
[Ruangan JS] <--- (Kertas Pesan JSON) ---> [Kurir Antar-Jemput: BRIDGE] <--- (Kertas Pesan JSON) ---> [Ruangan Native]
Batasan: Teks harus ditulis (serialize), dilipat (enqueue), diantar (async transport), dan dibaca ulang (deserialize).
```

Pada era **Legacy Bridge**:
Setiap kali JS memanggil fungsi native, data dikonversi menjadi string JSON, diantrekan secara asinkronus ke dalam buffer antrean, dialirkan melalui pipe string, di-deserialize kembali oleh native runtime, lalu dieksekusi. Respons dikembalikan melalui alur lambat yang sama. Ini memicu masalah:
*   Overhead serialisasi/deserialisasi ($O(N)$ ukuran data).
*   Ketidakmampuan memanggil native functions secara instan (synchronous block/read).
*   Bottleneck frame rate saat frekuensi pertukaran data melebihi 60 fps (misalnya animasi interaktif atau streaming sensor).

Sebaliknya, pada era **JavaScript Interface (JSI)**:

```
[Ruangan JS Runtime]
  |
  +---> [Objek Referensi JS] ---> Menunjuk langsung via Memory Pointer (C++ Raw/Smart Pointer)
                                               |
                                     [Ruangan Native Memory]
```

JSI bukan modul komunikasi antrean; **JSI adalah abstraction layer C++ yang menempel langsung ke engine JavaScript (seperti Hermes)**. JS runtime diberikan referensi pointer memori C++ (`HostObject`). Ketika JS mengeksekusi `nativeModule.calculate()`, JS Engine secara harfiah melompati eksekusi fungsi langsung ke memori native C++ melalui functional pointer table (vtable). Tidak ada serialisasi JSON. Tidak ada asynchrony paksaan. Tidak ada antrean frame.

### Mindset Senior Engineer
*   *Legacy Native Modules adalah legacy technical debt:* Jangan bangun arsitektur baru menggunakan `@ReactMethod` Java/Obj-C klasik kecuali untuk legacy maintainability.
*   *Pahami Trade-off Sinkronisasi:* Akses sinkron JSI berarti jika fungsi C++ Anda memakan waktu 50ms, Anda **membekukan (freeze)** JavaScript thread dan menurunkan frame rate aplikasi. Gunakan eksekusi sinkron hanya untuk I/O mikro/kalkulasi cepat (< 1-2ms), dan gunakan C++ thread pool/`std::future` untuk komputasi berat.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Perbandingan Arsitektur Eksekusi: Legacy Bridge vs. Modern JSI TurboModule

```
+===================================================================================================+
|                                    LEGACY BRIDGE ARCHITECTURE                                     |
+===================================================================================================+
 [JS Thread]                                                                         [Native Thread]
      |                                                                                     |
      | 1. Invoke NativeMethod(payload)                                                     |
      | 2. JSON.stringify(payload)                                                          |
      | 3. Push ke MessageQueue Batch                                                       |
      +--------------> [ BRIDGE SERIALIZATION PIPE (JSON String Buffer) ] ----------------->+
                                                                                            | 4. Flush Buffer
                                                                                            | 5. JSON.parse(payload)
                                                                                            | 6. Thread Switch: Background/UI
                                                                                            | 7. Eksekusi Java/ObjC Method
                                                                                            | 8. Hasil di-JSON.stringify
      +<------------- [ BRIDGE SERIALIZATION PIPE (JSON String Buffer) ] <------------------+
      | 9. Deserialize & Resolve Promise                                                    
      v                                                                                     

+===================================================================================================+
|                                  MODERN JSI / TURBOMODULE RUNTIME                                 |
+===================================================================================================+
 [JavaScript Virtual Machine (Hermes / V8)]
  |
  |-- Global Context
       |
       +-- jsObject = global.TurboModuleRegistry.getEnforcing('CustomCryptoModule')
            |
            | (JavaScript Engine memegang jsi::Object yang membungkus jsi::HostObject)
            |
            v
 [JSI Abstraction Layer (C++)]
  |
  |---> Eksekusi: jsObject.computeSHA256("payload")
  |     - Direct Virtual Method Call (vtable pointer lookup)
  |     - Argumen dilewatkan sebagai const jsi::Value& (No Serialization!)
  |
  +---> [C++ Implementation Class: NativeCustomCryptoHostObject : public jsi::HostObject]
         |
         |---> [Opsi 1: Eksekusi Langsung C++ Engine (Synchronous)]
         |     - Zero Bridge overhead
         |     - Zero Context Switch latency
         |     - Return jsi::String (Ref pointer dibuat langsung di JS Heap)
         |
         |---> [Opsi 2: Offload Task via Thread Pool (Asynchronous via Promise)]
               - Eksekusi thread: std::async / ThreadPool / Native WorkQueue
               - Return: jsi::Value yang membungkus instance Promise
               - Resolve via Native JSI Runtime Runner
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### Komponen Internal JavaScript Interface (JSI)

1.  **`facebook::jsi::Runtime`**:
    *   Representasi abstrak dari execution environment JS engine.
    *   Menghilangkan ketergantungan kode C++ pada API spesifik Hermes, V8, atau JSC.
    *   Bertanggung jawab untuk alokasi memori objek, string, simbol, dan eksekusi skrip dalam JS heap.
2.  **`facebook::jsi::Value`**:
    *   Tipe data variadik/union yang merepresentasikan semua kemungkinan tipe primitif dan referensi di JS (Undefined, Null, Boolean, Number, Symbol, String, Object).
    *   Lifecycle-nya dikelola secara cerdas: tipe primitif dialokasikan secara inline, sedangkan tipe kompleks memegang reference handle ke JavaScript Engine heap.
3.  **`facebook::jsi::HostObject`**:
    *   Interface C++ murni dengan dua virtual method utama:
        *   `virtual Value get(Runtime& runtime, const PropNameID& name)`: Dipanggil oleh JS engine setiap kali properti atau fungsi pada host object diakses (`obj.property` atau `obj.function()`).
        *   `virtual void set(Runtime& runtime, const PropNameID& name, const Value& value)`: Mengintersepsi mutasi state properti dari JS runtime.
4.  **`facebook::jsi::PropNameID`**:
    *   Interned string identity yang merepresentasikan identifier kunci/properti pada JavaScript runtime, meminimalkan string comparison overhead.
5.  **`facebook::react::TurboModuleManager`**:
    *   Sistem orkestrasi New Architecture yang mengelola siklus hidup TurboModule.
    *   Mengimplementasikan lazy-loading: Module native tidak akan diinstansiasi ke dalam memori native sampai kode JS memanggil `TurboModuleRegistry.get(...)`.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### 1. Pointer Aliasing dan ABI Stability

Pada JSI, nilai non-primitif (seperti `jsi::Object`, `jsi::String`) bertindak sebagai reference-counted RAII wrapper di sekitar handle internal JS engine:

```cpp
class Object : public Pointer {
  // Mengkapsulasi objek di heap engine target
};
```

Ketika objek JS dikirim ke C++, JSI tidak meng-copy memory buffer. C++ memegang pointer reference ke memori JS. Operasi pemanggilan method adalah direct indirect call melintasi compiled boundary melalui C++ Virtual Method Table (vtable):

$$\text{Latency}_{\text{call}} \approx \text{Cost}(\text{Virtual Function Dispatch}) \approx \mathcal{O}(1) \approx 2 - 5\text{ ns}$$

Bandingkan dengan legacy bridge serialisasi:

$$\text{Latency}_{\text{bridge}} = \mathcal{O}(N) + \text{Cost}_{\text{queue}} + \text{Cost}_{\text{thread\_context\_switch}} \approx 5 - 50\text{ ms}$$

### 2. Memori Lifecycle & RAII Safety Guard
Karena JS Engine memiliki Garbage Collector (GC) dan C++ menggunakan manual/RAII memory model (`std::unique_ptr`, `std::shared_ptr`), ketidakcocokan dapat memicu *dangling pointers* atau *memory leak*:
*   Jika JavaScript objek terhapus oleh Garbage Collection sementara C++ masih menyimpan pointer mentah (*raw pointer*), program akan mengalami crash: `EXC_BAD_ACCESS` (SIGSEGV).
*   Solusi: Bungkus referensi JavaScript persisten yang disimpan di level C++ menggunakan `facebook::jsi::Value` via smart pointer, atau buat `jsi::WeakObject` jika tidak ingin menghalangi GC untuk membersihkan memori.

### 3. JNI Boundary Bypass (Android Optimization)
Di Android, arsitektur lama harus menempuh jalur panjang:
`JS -> C++ Bridge -> JNI -> JVM (Java Native Interface) -> Java Code`. JNI boundary crossing memiliki cost komputasi yang tinggi akibat transformasi tipe data (contoh: `jstring` ke `std::string` atau pinning native array). Dengan JSI modern, modul dapat diimplementasikan **100% pada layer C++**, memotong JVM dan JNI secara total. Java Native Interface hanya disentuh bila akses terhadap Android OS Service (seperti `CameraManager`, `LocationManager`) benar-benar diperlukan.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi fundamental dari **Custom JSI C++ Host Object** yang mengekspos fungsi sinkron: enkripsi XOR ultra-cepat dan sistem benchmark penanda waktu.

### Struktur Properti Proyek
```
cpp/
 ├── SimpleCryptoModule.h
 └── SimpleCryptoModule.cpp
```

### 1. Header: `SimpleCryptoModule.h`

```cpp
#pragma once

#include <jsi/jsi.h>
#include <memory>

namespace customengine {

class SimpleCryptoModule : public facebook::jsi::HostObject {
public:
  SimpleCryptoModule();
  virtual ~SimpleCryptoModule() = default;

  // Mengintersepsi pengaksesan properti & method dari JavaScript
  facebook::jsi::Value get(facebook::jsi::Runtime& runtime, 
                           const facebook::jsi::PropNameID& name) override;

  // Mengintersepsi assignment properti dari JavaScript
  void set(facebook::jsi::Runtime& runtime, 
           const facebook::jsi::PropNameID& name, 
           const facebook::jsi::Value& value) override;

private:
  // Fungsi internal C++
  std::string xorEncryptDecrypt(const std::string& input, char key);
};

} // namespace customengine
```

### 2. Implementasi: `SimpleCryptoModule.cpp`

```cpp
#include "SimpleCryptoModule.h"

namespace customengine {

SimpleCryptoModule::SimpleCryptoModule() {}

std::string SimpleCryptoModule::xorEncryptDecrypt(const std::string& input, char key) {
  std::string output = input;
  for (size_t i = 0; i < input.size(); ++i) {
    output[i] = input[i] ^ key;
  }
  return output;
}

facebook::jsi::Value SimpleCryptoModule::get(facebook::jsi::Runtime& runtime, 
                                             const facebook::jsi::PropNameID& name) {
  std::string propName = name.utf8(runtime);

  // Ekspos method sinkron: xorCipher(text: string, key: number): string
  if (propName == "xorCipher") {
    return facebook::jsi::Function::createFromHostFunction(
      runtime,
      name,
      2, // Jumlah parameter
      [this](facebook::jsi::Runtime& rt, 
             const facebook::jsi::Value& thisValue, 
             const facebook::jsi::Value* arguments, 
             size_t count) -> facebook::jsi::Value {
        
        // 1. Validasi Input Parameter Runtime
        if (count < 2) {
          throw facebook::jsi::JSError(rt, "SimpleCryptoModule.xorCipher: Diperlukan 2 argumen");
        }
        if (!arguments[0].isString()) {
          throw facebook::jsi::JSError(rt, "SimpleCryptoModule.xorCipher: Argumen 1 harus berupa string");
        }
        if (!arguments[1].isNumber()) {
          throw facebook::jsi::JSError(rt, "SimpleCryptoModule.xorCipher: Argumen 2 harus berupa integer char code");
        }

        // 2. Ekstraksi Data dari JSI Values ke Primitive C++
        std::string rawText = arguments[0].getString(rt).utf8(rt);
        char key = static_cast<char>(arguments[1].getNumber());

        // 3. Eksekusi Komputasi Native
        std::string result = this->xorEncryptDecrypt(rawText, key);

        // 4. Return konversi string C++ ke JSI String (Alokasi langsung di JS Heap)
        return facebook::jsi::String::createFromUtf8(rt, result);
      }
    );
  }

  // Ekspos read-only constant properti: version
  if (propName == "version") {
    return facebook::jsi::String::createFromUtf8(runtime, "1.0.0-jsi");
  }

  return facebook::jsi::Value::undefined();
}

void SimpleCryptoModule::set(facebook::jsi::Runtime& runtime, 
                             const facebook::jsi::PropNameID& name, 
                             const facebook::jsi::Value& value) {
  std::string propName = name.utf8(runtime);
  // Proteksi Immutability: Tolak mutasi properti dari JS runtime
  throw facebook::jsi::JSError(runtime, "HostObject SimpleCryptoModule bersifat read-only: " + propName);
}

} // namespace customengine
```

### 3. Pemasangan ke Global Scope (Contoh Runtime Installer)

```cpp
void installSimpleCryptoModule(facebook::jsi::Runtime& jsRuntime) {
  auto moduleInstance = std::make_shared<customengine::SimpleCryptoModule>();
  auto hostObject = facebook::jsi::Object::createFromHostObject(jsRuntime, moduleInstance);
  
  // Inject langsung ke JavaScript `global` object
  jsRuntime.global().setProperty(jsRuntime, "__SimpleCrypto", hostObject);
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi mekanika internal kode pada Seksi 07:

1.  `class SimpleCryptoModule : public facebook::jsi::HostObject`:
    Inheritance dari `HostObject` menandakan bahwa lifecycle memori instance C++ ini dikelola bersama melalui smart pointer (`std::shared_ptr`) dan diikatkan ke dalam JS garbage collection tracking via proxy internal JSI.
2.  `Value get(Runtime& runtime, const PropNameID& name) override`:
    Dieksekusi setiap kali ada evaluasi ekspresi `__SimpleCrypto.<identitas>`. String name di-cache sebagai `PropNameID` guna efisiensi perbandingan identitas.
3.  `facebook::jsi::Function::createFromHostFunction(...)`:
    Membuat JavaScript Function object callable dari closure C++ (lambda).
    *   `runtime`: Context runtime JS aktif.
    *   `name`: Label nama function untuk visualisasi JS stack trace debugger.
    *   `2`: Parameter arity (length) function pada JavaScript reflection inspection.
4.  `const facebook::jsi::Value* arguments`:
    Array pointer mentah yang menampung referensi argumen dari JavaScript. Mencegah overhead pemanggilan vector allocator heap dynamic.
5.  `throw facebook::jsi::JSError(rt, "...")`:
    Mekanisme konversi exception C++ menjadi native JavaScript Exception (`try/catch` pada JS code akan menangkap error ini secara presisi).
6.  `arguments[0].getString(rt).utf8(rt)`:
    Membaca referensi JS string, mengekstrak char buffer, dan mentransformasikannya ke representasi encoding `std::string` berbasis UTF-8 secara manual.
7.  `jsRuntime.global().setProperty(jsRuntime, "__SimpleCrypto", hostObject)`:
    Melakukan injeksi instan ke global runtime object JS tanpa perantara JSON serializer, mengekspos modul ke namespace `global.__SimpleCrypto`.

---

## SEKSI 09 — STUDI KASUS NYATA

### Enterprise Scenario: High-Frequency Secure Sensor Stream & Cryptographic Pipeline
**Platform:** Aplikasi Otentikasi FinTech & IoT Perbankan Terdistribusi.

**Masalah:**
Aplikasi membutuhkan pengiriman data sensor biometrik dan akselerometer frekuensi tinggi (100 Hz/100 reading per detik) yang harus dienkripsi menggunakan algoritma AES-GCM-256 dan ditandatangani via HMAC-SHA256 sebelum dituliskan ke database lokal aman (SQLite/MMKV) dan di-stream melalui WebSocket.
*   **Jika menggunakan Legacy Bridge:** 100 hit/detik membanjiri message queue Bridge, menyebabkan *thread starvation*. Waktu rendering layar drop ke level < 15 FPS, latensi sentuhan melesat hingga 300 ms, dan Garbage Collector Android/iOS kewalahan membersihkan jutaan alokasi JSON string parsing temporer.
*   **Solusi:** Implementasi **TurboModule JSI C++ Native Extension** berbasis engine C++ murni yang mengimplementasikan streaming hashing dan encryption secara langsung, mengekspos non-blocking synchronous zero-copy buffer abstraction ke JS runtime, dan melakukan offloading perhitungan kriptografi berat ke C++ worker background queue secara paralel.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi end-to-end berstandar enterprise untuk custom native extension: **NativeHardwareSecurityEngine**.

### Arsitektur Berkas
```
modules/hardware-security/
 ├── ios/
 │    └── HardwareSecurityModuleProvider.mm
 ├── android/
 │    └── CMakeLists.txt
 ├── cpp/
 │    ├── HardwareSecurityEngine.hpp
 │    └── HardwareSecurityEngine.cpp
 └── src/
      └── index.ts
```

### 1. Core Header C++: `cpp/HardwareSecurityEngine.hpp`

```cpp
#pragma once

#include <jsi/jsi.h>
#include <memory>
#include <string>
#include <vector>

namespace enterprise::security {

class HardwareSecurityEngine : public facebook::jsi::HostObject {
public:
  HardwareSecurityEngine();
  ~HardwareSecurityEngine() override = default;

  facebook::jsi::Value get(facebook::jsi::Runtime& runtime, 
                           const facebook::jsi::PropNameID& name) override;

private:
  // Komputasi SHA-256 murni
  static std::string calculateSHA256(const std::string& input);

  // Helper konversi Bytes Array ke JSI ArrayBuffer
  facebook::jsi::ArrayBuffer createBuffer(facebook::jsi::Runtime& runtime, 
                                          const std::vector<uint8_t>& data);
};

} // namespace enterprise::security
```

### 2. Core Implementation C++: `cpp/HardwareSecurityEngine.cpp`

```cpp
#include "HardwareSecurityEngine.hpp"
#include <sstream>
#include <iomanip>
#include <thread>
#include <future>
#include <stdexcept>

// Sederhana implementation representasi hash internal (Standar FIPS-180-2 simulasi)
#include <functional>

namespace enterprise::security {

HardwareSecurityEngine::HardwareSecurityEngine() {}

std::string HardwareSecurityEngine::calculateSHA256(const std::string& input) {
  // Catatan: Pada produksi nyata, link-kan dengan libcrypto (OpenSSL) atau Apple CommonCrypto
  // Di sini kita merekayasa hashing deterministik 32-byte untuk runtime execution
  uint64_t hash = 14695981039346656037ULL;
  for (char ch : input) {
    hash ^= static_cast<uint64_t>(ch);
    hash *= 1099511628211ULL;
  }
  std::stringstream ss;
  ss << std::hex << std::setw(16) << std::setfill('0') << hash;
  // Pad hingga representasi hash 64 karakter hex
  std::string result = ss.str() + ss.str() + ss.str() + ss.str();
  return result.substr(0, 64);
}

facebook::jsi::Value HardwareSecurityEngine::get(facebook::jsi::Runtime& runtime, 
                                                 const facebook::jsi::PropNameID& name) {
  std::string methodName = name.utf8(runtime);

  // Method 1: SINKRONUS Compute Hash (Latensi mikrodetik: < 0.1ms)
  if (methodName == "computeHashSync") {
    return facebook::jsi::Function::createFromHostFunction(
      runtime,
      name,
      1,
      [](facebook::jsi::Runtime& rt, 
         const facebook::jsi::Value&, 
         const facebook::jsi::Value* args, 
         size_t count) -> facebook::jsi::Value {
        if (count < 1 || !args[0].isString()) {
          throw facebook::jsi::JSError(rt, "TypeError: computeHashSync membutuhkan payload string.");
        }

        std::string payload = args[0].getString(rt).utf8(rt);
        std::string hashResult = calculateSHA256(payload);

        return facebook::jsi::String::createFromUtf8(rt, hashResult);
      }
    );
  }

  // Method 2: ASINKRONUS Heavy Encryption via C++ Worker Thread (Native Promises)
  if (methodName == "processHeavyPayloadAsync") {
    return facebook::jsi::Function::createFromHostFunction(
      runtime,
      name,
      1,
      [](facebook::jsi::Runtime& rt, 
         const facebook::jsi::Value&, 
         const facebook::jsi::Value* args, 
         size_t count) -> facebook::jsi::Value {
        if (count < 1 || !args[0].isString()) {
          throw facebook::jsi::JSError(rt, "TypeError: processHeavyPayloadAsync membutuhkan payload string.");
        }

        std::string payload = args[0].getString(rt).utf8(rt);

        // Akses Constructor Promise dari JavaScript Engine
        auto promiseConstructor = rt.global().getPropertyAsFunction(rt, "Promise");

        // Buat host function executor untuk meneruskan resolve & reject callback
        auto executor = facebook::jsi::Function::createFromHostFunction(
          rt,
          facebook::jsi::PropNameID::forAscii(rt, "executor"),
          2,
          [payload](facebook::jsi::Runtime& innerRt, 
                    const facebook::jsi::Value&, 
                    const facebook::jsi::Value* promiseArgs, 
                    size_t) -> facebook::jsi::Value {
            auto resolve = std::make_shared<facebook::jsi::Value>(innerRt, promiseArgs[0]);
            
            // Offload komputasi berat ke worker thread native C++
            std::thread([&innerRt, resolve, payload]() {
              // Simulasi kalkulasi beban kriptografi berat
              std::this_thread::sleep_for(std::chrono::milliseconds(20));
              std::string computed = calculateSHA256("SECURE_SALT_" + payload);

              // Eksekusi callback JS harus disinkronisasikan ke Runtime loop
              // Di produksi: scheduling menggunakan CallInvoker dari React Native
              // Sederhana representasi eksekusi langsung via lock context:
              resolve->asObject(innerRt).asFunction(innerRt).call(
                innerRt, 
                facebook::jsi::String::createFromUtf8(innerRt, computed)
              );
            }).detach();

            return facebook::jsi::Value::undefined();
          }
        );

        return promiseConstructor.callAsConstructor(rt, executor);
      }
    );
  }

  return facebook::jsi::Value::undefined();
}

} // namespace enterprise::security
```

### 3. Android CMake Setup: `android/CMakeLists.txt`

```cmake
cmake_minimum_required(VERSION 3.13)
project(HardwareSecurityEngine)

set(CMAKE_VERBOSE_MAKEFILE ON)
set(CMAKE_CXX_STANDARD 17)

# Lokasi file source C++
add_library(
  hardware_security_engine
  SHARED
  ../cpp/HardwareSecurityEngine.cpp
  ./HardwareSecurityJniBridge.cpp
)

# Cari lokasi JSI headers yang disediakan oleh react-android framework
find_package(ReactAndroid REQUIRED)

target_include_directories(
  hardware_security_engine
  PRIVATE
  ../cpp
)

target_link_libraries(
  hardware_security_engine
  ReactAndroid::jsi
  log
)
```

### 4. iOS Objective-C++ Provider: `ios/HardwareSecurityModuleProvider.mm`

```objc
#import <Foundation/Foundation.h>
#import <React/RCTBridge+Private.h>
#import <ReactCommon/CallInvoker.h>
#import "HardwareSecurityEngine.hpp"

@interface HardwareSecurityModuleProvider : NSObject <RCTBridgeModule>
@end

@implementation HardwareSecurityModuleProvider

RCT_EXPORT_MODULE(HardwareSecurity)

+ (BOOL)requiresMainQueueSetup {
  return YES;
}

RCT_EXPORT_BLOCKING_SYNCHRONOUS_METHOD(installJSIBindings) {
  RCTBridge *bridge = [RCTBridge currentBridge];
  RCTCxxBridge *cxxBridge = (RCTCxxBridge *)bridge;
  
  if (cxxBridge == nil) {
    return @NO;
  }

  auto jsiRuntime = (facebook::jsi::Runtime *)cxxBridge.runtime;
  if (jsiRuntime == nullptr) {
    return @NO;
  }

  // Daftarkan Module C++ JSI ke JavaScript Global Scope
  auto securityModule = std::make_shared<enterprise::security::HardwareSecurityEngine>();
  auto hostObject = facebook::jsi::Object::createFromHostObject(*jsiRuntime, securityModule);
  
  jsiRuntime->global().setProperty(*jsiRuntime, "__HardwareSecurityEngine", hostObject);

  return @YES;
}

@end
```

### 5. Type-Safe Client Layer (TypeScript): `src/index.ts`

```typescript
import { NativeModules } from 'react-native';

interface HardwareSecurityEngineSpec {
  computeHashSync(payload: string): string;
  processHeavyPayloadAsync(payload: string): Promise<string>;
}

// Deklarasi global augmentasi lingkungan runtime
declare global {
  var __HardwareSecurityEngine: HardwareSecurityEngineSpec | undefined;
}

// Inisialisasi bridge installer saat modul dimuat
if (!global.__HardwareSecurityEngine) {
  const { HardwareSecurity } = NativeModules;
  if (!HardwareSecurity || !HardwareSecurity.installJSIBindings) {
    throw new Error(
      '[HardwareSecurityEngine] Gagal menemukan native module loader. Pastikan autolinking berjalan dengan benar.'
    );
  }
  const installed = HardwareSecurity.installJSIBindings();
  if (!installed || !global.__HardwareSecurityEngine) {
    throw new Error('[HardwareSecurityEngine] JSI Installation failed pada global context scope.');
  }
}

export class CryptoPipeline {
  private static instance: HardwareSecurityEngineSpec = global.__HardwareSecurityEngine!;

  /**
   * Eksekusi enkripsi sinkron mikrodetik tanpa beralih thread.
   * Cocok untuk frame-critical logic (misal: 120fps UI loops).
   */
  public static hashTelemetryDirect(data: string): string {
    return this.instance.computeHashSync(data);
  }

  /**
   * Eksekusi enkripsi asinkron di C++ Thread pool untuk muatan besar.
   */
  public static async processLargeBlob(data: string): Promise<string> {
    return await this.instance.processHeavyPayloadAsync(data);
  }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter Dimensi | Legacy Native Modules (`@ReactMethod`) | C++ JSI Custom Extension (TurboModules) | WebAssembly (Wasm) di JS Thread |
| :--- | :--- | :--- | :--- |
| **Pola Eksekusi** | Asinkron paksaan (Queue-based) | **Bisa Sinkron & Asinkron** | Murni Sinkron pada Engine Thread |
| **Overhead Komunikasi** | Sangat Tinggi ($O(N)$ JSON serialization) | **Nol / Zero-copy pointer reference** | Sedang (Memory boundary copying) |
| **Karakteristik Latensi** | Tinggi ($\approx 5\text{ms} - 50\text{ms}$) | **Hampir Instan ($< 0.05\text{ms}$)** | Rendah ($0.1\text{ms} - 1\text{ms}$) |
| **Akses Native OS API** | Lengkap (Obj-C/Swift/Java/Kotlin) | Memerlukan C++/JNI/Obj-C++ bindings | Terisolasi (Sandbox murni) |
| **Debugging Complexity** | Mudah (Bisa logging di Java/Xcode/Flipper) | **Kompleks (GDB, LLDB, Memory Dumps)** | Kompleks (Wasm bytecode inspection) |
| **Kompatibilitas Platform**| Platform spesifik (Dua codebase) | **Tinggi (Satu C++ core untuk iOS & Android)**| Sangat Tinggi (Portabel) |
| **Resiko Crash** | Terisolasi (Crash native thread) | **Tinggi (Memory leak/SIGSEGV mematikan App)**| Terisolasi di VM JS |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Thread Lock Pitfall (Deadlock pada JS UI Rendering)
*   **Kasus:** Pemanggilan fungsi JSI sinkronus yang mengeksekusi operasi blocking I/O (akses database, file read besar, atau network socket) langsung di dalam C++ host function.
*   **Dampak:** Karena JS engine berjalan pada thread utama React Native JS execution, pemanggilan sinkron yang memakan waktu > 16.6ms akan memicu frame-drop parah (jank). Jika komputasi mencapai 5 detik pada Android, sistem akan melemparkan dialog sistem **ANR (Application Not Responding)**.
*   **Mitigasi:** Aturan baku: Operasi yang membutuhkan waktu lebih dari **2 milidetik** WAJIB dialihkan ke background thread pool (`std::async`, worker queue) dan mengembalikan tipe `Promise`.

### 2. Runtime Pointer Invalidation (Dangling JS References)
*   **Kasus:** Menyimpan `facebook::jsi::Runtime*` atau `jsi::Value*` di dalam static memory pointer C++ atau global scope lintas thread worker tanpa synchronization.
*   **Dampak:** Ketika aplikasi me-reload JS bundle (saat Fast Refresh / OTA Update) atau berganti activity, instance `jsi::Runtime` sebelumnya dihancurkan (*deallocated*). Saat background thread native mencoba mengakses runtime yang sudah tiada, aplikasi mengalami immediate segmentation fault (`SIGSEGV`).
*   **Mitigasi:** Jangan pernah menyimpan instance `jsi::Runtime` dalam variabel global mentah. Selalu sinkronisasikan akses runtime melalui `facebook::react::CallInvoker` yang menjamin eksekusi terjadi saat runtime masih valid dan berada pada thread kepemilikannya.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Melakukan Konversi String Berulang dalam Loop Kritis
```cpp
// SALAH: Mengekstraksi utf8 string di dalam looping JSI
for (size_t i = 0; i < count; ++i) {
  std::string key = propNameId.utf8(runtime); // Alokasi heap string baru di tiap iterasi!
}

// BENAR: Bandingkan menggunakan static PropNameID atau string views
const auto& targetProp = facebook::jsi::PropNameID::forAscii(runtime, "targetKey