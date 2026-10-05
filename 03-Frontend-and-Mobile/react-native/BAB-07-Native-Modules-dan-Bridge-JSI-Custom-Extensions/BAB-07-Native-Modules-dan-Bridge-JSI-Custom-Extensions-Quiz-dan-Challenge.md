# BAB-07-Native-Modules-dan-Bridge-JSI-Custom-Extensions: Quiz, Challenge, & Knowledge Check

Dokumen ini dirancang untuk menguji, memvalidasi, dan mengonsolidasikan pemahaman arsitektur mendalam seputar interaksi antara JavaScript/TypeScript runtime dan lapisan native (Android/iOS/C++) di React Native. Fokus mencakup transisi dari Legacy Bridge berbasis JSON serialization menuju JavaScript Interface (JSI), TurboModules, Codegen spec typing, memori thread-boundary, hingga pembuatan Custom C++ Native Extensions.

---

## Bagian 1: Basic Questions (5 Soal Pilihan Ganda & Analisis Konseptual)

### Soal 1.1: Arsitektur Legacy Bridge vs JSI
**Pertanyaan:**
Pada arsitektur lama React Native (Legacy Bridge), komunikasi antara JavaScript Thread dan Native Thread (UI/Background) berjalan secara asynchronous melalui JSON serialization over serialized message queue. Mengapa pendekatan ini menyebabkan frame drops atau bottleneck pada operasi yang membutuhkan throughput tinggi (seperti gesture tracking, real-time audio processing, atau direct cryptographic hashing)?
- A. Karena JSON parser di Android Native menggunakan Java Reflection yang memicu Garbage Collection loop.
- B. Karena setiap payload objek JavaScript harus di-serialize menjadi string JSON, ditransfer lewat asynchronous batching queue, dan di-deserialize kembali di native runtime, menimbulkan serialization overhead, alokasi memori ganda, dan latensi asinkron.
- C. Karena JavaScript Thread berjalan di Web Worker terpisah yang tidak memiliki akses TCP socket ke Native OS.
- D. Karena Legacy Bridge memblokir Main UI Thread secara synchronous pada setiap pemanggilan method native.

**Kunci Jawaban:** **B**
**Pembahasan Teknis:**
Legacy Bridge bergantung pada antrean asinkron (`MessageQueue.js` ke Native C++ bridge). Data dari JS harus dikonversi menjadi string JSON lalu diurai kembali di native (Java/Kotlin atau Obj-C/Swift), begitu pula sebaliknya. Overhead ini menghasilkan latensi non-deterministik dan lonjakan alokasi memori (heap churn). Sebaliknya, JSI (JavaScript Interface) mengekspos C++ host objects langsung ke JavaScript Engine (Hermes/V8/JSC) melalui pointer C++, memungkinkan pemanggilan fungsi synchronous tanpa JSON serialization.

---

### Soal 1.2: Peran JSI (JavaScript Interface) Host Objects
**Pertanyaan:**
Bagaimana mekanisme internal JSI memungkinkan JavaScript memanggil method C++ secara langsung tanpa overhead serialization?
- A. JSI mengompilasi kode JavaScript menjadi machine code native assembly saat runtime (AOT compilation).
- B. JSI menyematkan WebAssembly runtime di dalam thread UI native.
- C. JSI menyediakan layer C++ abstrak (`facebook::jsi::HostObject`) di mana engine JavaScript menyimpan referensi langsung (`jsi::Object`) ke C++ struct/class, sehingga pemanggilan fungsi di JS langsung memicu pemanggilan method C++ virtual secara in-memory.
- D. JSI menggunakan shared memory via POSIX shared memory (`shm_open`) antara dua proses Linux/Darwin terpisah.

**Kunci Jawaban:** **C**
**Pembahasan Teknis:**
Melalui `jsi::HostObject`, kita meng-override method `get()` dan `set()`. Saat JavaScript mengevaluasi `nativeModule.calculateHash(data)`, JavaScript Engine menanyakan HostObject C++ yang bersangkutan dan langsung mengeksekusi function pointer C++ di thread yang sama tanpa context-switch OS process ataupun serialization string.

---

### Soal 1.3: TurboModules vs Legacy Native Modules
**Pertanyaan:**
Apa keuntungan utama siklus hidup (lifecycle) TurboModules dibandingkan dengan `@ReactMethod` pada Legacy Native Modules saat aplikasi pertama kali di-boot (app startup)?
- A. TurboModules secara otomatis mengabaikan izin akses runtime Android (runtime permissions).
- B. Legacy Native Modules diinisialisasi secara eager (semua module di-instantiate saat startup meskipun belum digunakan), sedangkan TurboModules dimuat secara lazy (hanya diinisialisasi saat pertama kali dipanggil via `TurboModuleRegistry.getEnforcing(...)`).
- C. TurboModules memindahkan eksekusi kode UI langsung ke GPU hardware pipeline tanpa melewati Yoga layout.
- D. Legacy Native Modules hanya mendukung bahasa C, sedangkan TurboModules hanya mendukung Swift dan Kotlin.

**Kunci Jawaban:** **B**
**Pembahasan Teknis:**
Pada Legacy Bridge, semua modul yang terdaftar dalam package list diinisialisasi saat boot aplikasi, memperlambat Time-To-Interactive (TTI). TurboModules menggunakan arsitektur lazy loading berbasis JSI: modul native hanya dialokasikan di heap saat JavaScript benar-benar memanggil method modul tersebut.

---

### Soal 1.4: Peran React Native Codegen
**Pertanyaan:**
Dalam New Architecture, apa peran utama React Native Codegen ketika kita mendefinisikan file spec TypeScript/Flow (misalnya `NativeMathSpec.ts`)?
- A. Mengonversi kode TypeScript secara otomatis menjadi aplikasi Swift/Kotlin siap publish ke Play Store.
- B. Menghasilkan boilerplate C++ interface, abstract classes Java/Obj-C, glue code JSI, dan type-safe protocol scaffolding secara otomatis sebelum proses kompilasi native (pre-build phase).
- C. Mengoptimalkan bundle size JavaScript dengan melakukan dead-code elimination menggunakan Webpack.
- D. Mengganti Hermes Engine dengan V8 Engine khusus untuk platform Android.

**Kunci Jawaban:** **B**
**Pembahasan Teknis:**
Codegen memverifikasi kontrak tipe data antara JS dan Native saat compile-time. Dari spec TypeScript bertipe `TurboModule`, Codegen menggenerasi file C++ specs (`NativeMathSpecJSI.h`, `NativeMathSpecJSI-generated.cpp`) dan abstract classes native (Java/Obj-C). Jika tipe data di JS tidak cocok dengan native, kompilasi build akan langsung gagal (compile-time safety).

---

### Soal 1.5: Threading Model di React Native Native Modules
**Pertanyaan:**
Jika sebuah native method melakukan pembacaan file I/O berukuran 200 MB atau query SQLite blocking secara synchronous pada JSI, apa dampak langsungnya terhadap UI aplikasi jika method tersebut dipanggil langsung dari JS Thread?
- A. Tidak ada dampak karena JS runtime di React Native selalu multi-threaded.
- B. JS Thread akan terblokir hingga pembacaan selesai, menghentikan penanganan event touch dan eksekusi callback JS, yang berpotensi memicu ANR (Application Not Responding) di Android atau UI stutter parah.
- C. Main UI Thread di Android otomatis membuat coroutine baru tanpa konfigurasi pengembang.
- D. JSI secara otomatis membatalkan pemanggilan fungsi jika durasinya lebih dari 16 milidetik.

**Kunci Jawaban:** **B**
**Pembahasan Teknis:**
JSI memungkinkan eksekusi synchronous. Jika method synchronous melakukan operasi I/O atau komputasi berat, eksekusi dilakukan di thread tempat pemanggil berada (umumnya JS Thread). Terblokirnya JS Thread menyebabkan touch events, re-render React, dan timers terhenti total. Operasi I/O berat tetap harus didelegasikan ke thread pool/worker thread native via Promise asynchronous.

---

## Bagian 2: Intermediate Questions (5 Soal Analisis Teknis & Debugging)

### Soal 2.1: Analisis Race Condition & Thread Affinity pada JSI C++ Callback
**Pertanyaan:**
Perhatikan implementasi C++ JSI berikut yang bertujuan mengirim data sensor gyroscope ke JavaScript:
```cpp
void registerSensorListener(jsi::Runtime& runtime, const jsi::Value& thisValue, const jsi::Value* args, size_t count) {
    auto callback = std::make_shared<jsi::Function>(args[0].asObject(runtime).asFunction(runtime));
    
    sensorHardware->onRead([&runtime, callback](float x, float y, float z) {
        // Callback hardware terpanggil di OS Background Thread
        jsi::Object data(runtime);
        data.setProperty(runtime, "x", x);
        callback->call(runtime, data); // CRASH / SEGMENTATION FAULT!
    });
}
```
Mengapa kode di atas memicu memory corruption atau hard crash (`SIGSEGV`) saat dijalankan?
- A. Karena parameter `x`, `y`, dan `z` tidak dikonversi menjadi `std::string`.
- B. Karena `jsi::Runtime` tidak thread-safe; method dan alokasi `runtime` dieksekusi dari background hardware thread, melanggar JavaScript Engine single-thread ownership tanpa berpindah kembali ke JS CallInvoker thread.
- C. Karena `std::make_shared` dilarang digunakan di environment C++ React Native.
- D. Karena `jsi::Object` tidak mendukung penambahan property dengan tipe numeric primitive.

**Kunci Jawaban:** **B**
**Pembahasan Teknis:**
Instance `jsi::Runtime` (Hermes/JSC) strictly single-threaded dan terikat pada JS Thread. Memanggil `callback->call(runtime, ...)` atau membuat `jsi::Object` dari thread native sembarang (hardware worker thread) menyebabkan concurrent memory access violation di engine garbage collector. Solusinya adalah menggunakan `react::CallInvoker` (`jsInvoker->invokeAsync(...)`) untuk menjadwalkan eksekusi lambda kembali ke JS Thread.

---

### Soal 2.2: Memory Leak via JSI WeakReference & Persistent References
**Pertanyaan:**
Seorang engineer membuat custom JSI wrapper untuk modul C++ image cache. Objek JavaScript menyimpan pointer ke C++ struct. Namun, setelah navigasi berulang-ulang, memory usage aplikasi naik drastis dan tidak turun saat garbage collection (GC) dijalankan. Apa penyebab paling umum kebocoran memori ini pada implementasi JSI custom?
- A. C++ struct tidak menggunakan keyword `volatile` pada semua member variabelnya.
- B. Pengembang menyimpan `jsi::Value` di C++ global variable menggunakan copy constructor tanpa melepaskannya.
- C. JSI HostObject mengalokasikan memori native di heap C++ (`malloc`/`new`), tetapi tidak mengimplementasikan custom destructor atau smart pointer (`std::shared_ptr` / `std::unique_ptr`) saat HostObject di-garbage collect oleh JS Engine.
- D. Hermes Engine tidak mendukung proses pembersihan memori objek jika aplikasi dibangun dalam mode release.

**Kunci Jawaban:** **C**
**Pembahasan Teknis:**
JS Engine GC hanya memonitor dan mereklamasi memori heap JavaScript yang dikelolanya. Jika sebuah JSI HostObject memegang pointer memori C++ native (`char* buffer = new char[size]`) tanpa mengaitkannya ke destructor C++ yang dipanggil saat wrapper JS dihancurkan, memori native tersebut akan tetap bocor di heap OS (resident memory) meskipun referensi JS-nya sudah mati.

---

### Soal 2.3: Type Mismatch & Codegen Specification Inconsistency
**Pertanyaan:**
Diberikan TurboModule specification di TypeScript:
```typescript
import { TurboModule, TurboModuleRegistry } from 'react-native';

export interface Spec extends TurboModule {
  readonly getHardwareInfo: () => {
    readonly cpuCores: number;
    readonly isRooted: boolean;
    readonly deviceId: string | null;
  };
}

export default TurboModuleRegistry.getEnforcing<Spec>('DeviceSecurityModule');
```
Saat build Android via `./gradlew generateCodegenArtifactsFromSchema`, terjadi kompilasi error pada C++ glue code. Manakah dari penyebab berikut yang merupakan akar masalahnya terkait tipe data Codegen?
- A. TurboModule Codegen tidak mendukung method synchronous bertipe object return; semua fungsi harus mengembalikan `Promise<T>`.
- B. Tipe return object anonim harus didefinisikan secara eksplisit atau Codegen versi tertentu tidak mengizinkan inline object tanpa mendeklarasikan `type HardwareInfo = { ... }` atau penggunaan union `string | null` memerlukan generic type handling khusus (seperti Flow/TS exact object mapping).
- C. Nama interface wajib diawali dengan nama modul, misalnya `DeviceSecurityModuleSpec`.
- D. Keyword `readonly` dilarang oleh AST parser Babel pada New Architecture.

**Kunci Jawaban:** **B**
**Pembahasan Teknis:**
React Native Codegen memiliki parser schema yang sangat ketat terhadap AST TypeScript/Flow. Inline nested anonymous objects dan nullable union types (`string | null` vs `?string`) sering memicu parsing failure di Codegen CLI jika tidak dideklarasikan sebagai named type alias atau jika tipe nullability tidak sesuai dengan konvensi Codegen (misal `UnsafeObject` vs typed struct Codegen C++ generator).

---

### Soal 2.4: Mengirim Event dari Native ke JS: DeviceEventEmitter vs EventEmitter TurboModule
**Pertanyaan:**
Dalam New Architecture, apa perbedaan mendasar dalam pengiriman event hardware (misal: perubahan status baterai) antara `RCTDeviceEventEmitter` (Legacy) dengan event berbasis Typed EventEmitter di TurboModules?
- A. `RCTDeviceEventEmitter` memancarkan broadcast global string-based tanpa kontrak tipe data compile-time, sedangkan TurboModules event emitter dapat menggunakan typed callback spec yang di-generate Codegen, mencegah mismatch payload nama event dan tipe parameter antara native dan TypeScript.
- B. `RCTDeviceEventEmitter` hanya berjalan di iOS dan tidak pernah didukung di Android.
- C. TurboModules sama sekali melarang pengiriman event dari native ke JS; JS wajib melakukan polling setiap 100ms.
- D. TurboModules mengirim event langsung melalui WebSocket internal debugger.

**Kunci Jawaban:** **A**
**Pembahasan Teknis:**
Legacy `DeviceEventEmitter.addListener('onBatteryChange', ...)` rentan terhadap typo nama string event dan perubahan struktur JSON tanpa peringatan compile-time. Pada New Architecture dengan typed specs, interface TurboModule dapat mendeklarasikan event emitter signature yang diverifikasi oleh Codegen, meminimalkan bug runtime dan payload drift.

---

### Soal 2.5: Bridging Zero-Copy Data Menggunakan JSI ArrayBuffer
**Pertanyaan:**
Untuk memproses stream frame kamera beresolusi 4K (60 FPS) dari Native C++ ke JavaScript guna pemrosesan tensor neural network lokal, teknik manakah yang memberikan performa throughput tertinggi dengan zero-copy (tanpa duplikasi buffer memori)?
- A. Mengonversi buffer byte native menjadi Base64 string lalu mengirimkannya via standard TurboModule string argument.
- B. Mengonversi buffer byte menjadi array of integers di JavaScript (`number[]`).
- C. Menggunakan `jsi::ArrayBuffer` C++ API untuk membungkus pointer raw memory native (`uint8_t*`) langsung ke dalam typed `Uint8Array` di JavaScript runtime tanpa duplikasi alokasi memori heap.
- D. Menyimpan frame ke file temporer di filesystem SSD lalu membaca path filenya dari JS.

**Kunci Jawaban:** **C**
**Pembahasan Teknis:**
`jsi::ArrayBuffer` memungkinkan pembuatan instance ArrayBuffer JavaScript yang langsung mereferensikan blok memori kontinu native (`uint8_t*`). Hal ini meniadakan kebutuhan menyalin (zero-copy), encoding Base64, atau translasi struktur data, sehingga pemrosesan frame video 4K atau raw audio sample dapat berjalan pada 60-120 FPS tanpa GC thrashing.

---

## Bagian 3: Skenario Kasus Nyata Produksi (Production Scenarios)

### Skenario 3.1: Audio Streaming Glitch & Main Thread Saturation
**Konteks Masalah:**
Sebuah aplikasi pemutar audio lossless profesional mengimplementasikan equalizer custom via Legacy Native Module. Pengguna melaporkan bahwa saat mereka melakukan scroll cepat pada daftar lagu (FlatList besar) atau saat transisi animasi layar berlangsung, suara audio mengalami "stutter", "crackle", atau audio dropouts selama 200–500ms.

**Investigasi:**
Setelah profiling dengan Android Systrace dan Xcode Instruments:
1. Native Module mengeksekusi kalkulasi equalizer di Main Thread (UI Thread) Android (`@ReactMethod` tanpa background thread queue).
2. Di saat yang sama, layouting elemen FlatList dan render frame memonopoli Main Thread selama animasi.
3. Buffer audio native mengalami *underrun* karena thread tidak sempat memompa PCM data ke OpenSL ES / AAudio stream.

**Pertanyaan Analisis:**
Bagaimana arsitektur refactoring komprehensif untuk mengatasi masalah ini dengan standar New Architecture?
**Solusi & Mitigasi Teknis:**
1. **Thread Separation:** Pindahkan pipeline audio processing keluar dari UI Thread dan JS Thread. Alokasikan dedicated realtime priority thread di C++ (menggunakan pthread dengan `SCHED_FIFO` atau AAudio callback).
2. **JSI Direct Control:** Implementasikan Custom C++ TurboModule via JSI untuk kontrol parameter equalizer (gain, cutoff frequency). Perubahan slider di JS memanggil C++ method secara synchronous tanpa latency queue Legacy Bridge.
3. **Atomic State Sharing:** Parameter equalizer di-update menggunakan `std::atomic<float>` di C++ core audio engine, memastikan realtime audio thread membaca parameter terbaru secara thread-safe dan lock-free tanpa menghentikan streaming buffer.

---

### Skenario 3.2: Crash Fatal `EXC_BAD_ACCESS` / `SIGSEGV` pada Hermes Engine
**Konteks Masalah:**
Sebuah aplikasi fintech mengintegrasikan modul biometrik keamanan tingkat tinggi berbasis C++ JSI. Pada 2% pengguna di perangkat low-end Android dan iOS lawas, aplikasi mengalami crash tiba-tiba dengan tombstone log:
`SIGSEGV (SEGV_MAPERR) at address 0x00000000` di dalam `hermes::vm::GC::markRoots`.

**Penyelidikan Kode C++ Native:**
```cpp
class SecurityContextHolder {
    jsi::Value cachedCallback; // Menyimpan callback JavaScript secara permanen
public:
    void setCallback(jsi::Runtime& rt, const jsi::Value& cb) {
        cachedCallback = jsi::Value(rt, cb); // Direct copy assignment
    }
    void triggerAuth(jsi::Runtime& rt) {
        if (!cachedCallback.isUndefined()) {
            cachedCallback.asObject(rt).asFunction(rt).call(rt);
        }
    }
};
```

**Pertanyaan Analisis:**
Mengapa penyimpanan `jsi::Value` secara global/field object seperti di atas memicu memory crash saat Hermes Garbage Collector aktif?
**Solusi & Mitigasi Teknis:**
1. **Lifecycle Mismatch:** `jsi::Value` dan `jsi::Object` merepresentasikan referensi yang diasumsikan berada di stack, bukan heap jangka panjang. Jika JavaScript Engine melakukan GC collection atau cycle compaction, alamat memori objek JS yang direferensikan oleh `cachedCallback` dapat dipindahkan atau dihapus, meninggalkan *dangling pointer*.
2. **Perbaikan:** Gunakan `jsi::Value` hanya untuk passing data transien di function scope. Untuk referensi persistent jangka panjang lintas siklus GC, gunakan pattern `facebook::jsi::Function` yang di-wrap di dalam pointer aman atau manfaatkan `std::shared_ptr<jsi::Function>`. Pastikan lifecycle objek native terikat kuat dengan lifecycle `Runtime`. Jika runtime di-destroy (misalnya reload bundle saat Fast Refresh), referensi native harus di-nullify untuk mencegah dereferencing invalid runtime pointer.

---

### Skenario 3.3: Migrasi Legacy Bridge ke TurboModule Mengakibatkan ANR Saat Cold Boot
**Konteks Masalah:**
Sebuah tim e-commerce memigrasikan 35 custom native modules mereka ke TurboModules untuk mengaktifkan New Architecture. Namun setelah rilis, dashboard crash reporting menunjukkan lonjakan ANR (Application Not Responding) sebesar 300% pada saat aplikasi pertama kali dibuka (Cold Launch) di Android.

**Investigasi:**
Ditemukan bahwa di file `MainApplication.kt`:
```kotlin
override fun getTurboModuleManagerDelegateBuilder(): ReactPackageTurboModuleManagerDelegate.Builder {
    return ReactPackageTurboModuleManagerDelegate.Builder()
        .addPackage(CustomAnalyticsPackage())
        .addPackage(DatabaseSyncPackage())
        // ... 33 packages lainnya
}
```
Di dalam implementasi C++ JSI/Java TurboModule untuk `DatabaseSyncModule`, developer memanggil synchronous initialization yang membaca enkripsi database SQLite terenkripsi berukuran besar di konstruktor modul atau di method `getHardwareKey()` yang langsung dieksekusi di root `index.js`.

**Pertanyaan Analisis:**
Mengapa TurboModules justru memperparah ANR pada kasus di atas jika developer tidak berhati-hati dengan synchronous method?
**Solusi & Mitigasi Teknis:**
1. **False Sense of Lazy Loading:** Meskipun TurboModules bersifat lazy loaded, pemanggilan method synchronous di baris pertama `index.js` (seperti `const key = SecurityModule.getHardwareKey()`) memaksa modul langsung diinisialisasi saat bundle pertama kali dievaluasi.
2. **Blocking JS Init Queue:** Jika inisialisasi modul native tersebut memblokir JS Thread lebih dari 5 detik saat bootstrap, Android OS akan menembakkan ANR.
3. **Mitigasi:**
   - Pisahkan inisialisasi berat ke background worker thread (`ExecutorService` di Android atau `DispatchQueue` di iOS).
   - Hindari inisialisasi blocking di konstruktor modul C++/Kotlin.
   - Gunakan Promise asynchronous untuk pembacaan key/database saat startup, atau lakukan pre-warming di background sebelum UI interaktif ditampilkan.

---

## Bagian 4: Practical Chapter Challenge

### Tantangan Implementasi: Membangun TurboModule C++ High-Performance Hash Engine

#### Deskripsi Tantangan:
Anda diminta merancang spesifikasi dan implementasi TurboModule bernama `NativeCryptoEngine` yang menyediakan fungsi perhitungan hashing data secara synchronous dan asynchronous menggunakan C++ core algorithm (misalnya algoritma FNV-1a atau custom lightweight hash) yang dapat dipanggil dari TypeScript dengan performa tinggi.

#### Kriteria Keberhasilan (Acceptance Criteria):
1. **Spec Typing (Codegen Contract):**
   - Buat file `NativeCryptoEngine.ts` yang mendefinisikan TurboModule Spec.
   - Sediakan method synchronous: `hashFastSync(input: string): number`.
   - Sediakan method asynchronous: `hashHeavyAsync(input: string): Promise<string>`.
2. **C++ Implementation Header & Source:**
   - Tulis interface dan implementasi C++ yang mengimplementasikan spec hasil Codegen.
   - Terapkan fungsi kalkulasi hash FNV-1a (32-bit atau 64-bit) murni di C++.
3. **Thread Safety & Async Invocation:**
   - Method asynchronous `hashHeavyAsync` harus mengeksekusi komputasi di thread C++ terpisah (`std::async` atau `std::thread`), dan memanggil resolve/reject kembali ke JS runtime menggunakan `CallInvoker`.

---

### Panduan Solusi Kode Implementasi:

#### 1. TypeScript Specification (`NativeCryptoEngine.ts`)
```typescript
import { TurboModule, TurboModuleRegistry } from 'react-native';

export interface Spec extends TurboModule {
  // Method synchronous via JSI direct execution
  hashFastSync(input: string): number;

  // Method asynchronous via background thread & Promise
  hashHeavyAsync(input: string): Promise<string>;
}

export default TurboModuleRegistry.getEnforcing<Spec>('NativeCryptoEngine');
```

#### 2. C++ Header (`NativeCryptoEngine.h`)
```cpp
#pragma once

#include <ReactCommon/CallInvoker.h>
#include <memory>
#include <string>
#include "NativeCryptoEngineSpecJSI.h"

namespace facebook::react {

class NativeCryptoEngine : public NativeCryptoEngineCxxSpec<NativeCryptoEngine> {
public:
    NativeCryptoEngine(std::shared_ptr<CallInvoker> jsInvoker);

    // Synchronous execution (runs on caller JS Thread)
    double hashFastSync(jsi::Runtime& rt, std::string input);

    // Asynchronous execution (dispatched to background worker)
    jsi::Value hashHeavyAsync(jsi::Runtime& rt, std::string input);

private:
    static uint32_t calculateFNV1a(const std::string& str);
};

} // namespace facebook::react
```

#### 3. C++ Source Implementation (`NativeCryptoEngine.cpp`)
```cpp
#include "NativeCryptoEngine.h"
#include <thread>
#include <future>
#include <sstream>
#include <iomanip>

namespace facebook::react {

NativeCryptoEngine::NativeCryptoEngine(std::shared_ptr<CallInvoker> jsInvoker)
    : NativeCryptoEngineCxxSpec<NativeCryptoEngine>(std::move(jsInvoker)) {}

uint32_t NativeCryptoEngine::calculateFNV1a(const std::string& str) {
    uint32_t hash = 2166136261u;
    for (char c : str) {
        hash ^= static_cast<uint8_t>(c);
        hash *= 16777619u;
    }
    return hash;
}

double NativeCryptoEngine::hashFastSync(jsi::Runtime& rt, std::string input) {
    // Synchronous direct C++ return via JSI
    uint32_t result = calculateFNV1a(input);
    return static_cast<double>(result);
}

jsi::Value NativeCryptoEngine::hashHeavyAsync(jsi::Runtime& rt, std::string input) {
    // Buat Promise via JSI Promise constructor
    auto promiseConstructor = rt.global().getPropertyAsFunction(rt, "Promise");
    
    // Simpan invoker agar callback dapat dipanggil di JS Thread
    auto jsInvoker = this->jsInvoker_;

    auto executor = jsi::Function::createFromHostFunction(
        rt,
        jsi::PropNameID::forAscii(rt, "executor"),
        2,
        [input, jsInvoker](jsi::Runtime& runtime, const jsi::Value& thisVal, const jsi::Value* args, size_t count) -> jsi::Value {
            auto resolve = std::make_shared<jsi::Value>(runtime, args[0]);
            auto reject = std::make_shared<jsi::Value>(runtime, args[1]);

            // Eksekusi komputasi berat di background thread
            std::thread([input, jsInvoker, resolve, reject]() {
                // Simulasi komputasi intensif / multi-pass hashing
                uint32_t hash = 2166136261u;
                for (int round = 0; round < 100000; ++round) {
                    for (char c : input) {
                        hash ^= static_cast<uint8_t>(c);
                        hash *= 16777619u;
                    }
                }

                std::stringstream ss;
                ss << std::hex << std::setfill('0') << std::setw(8) << hash;
                std::string hashHex = ss.str();

                // Jadwalkan callback resolve kembali ke JS Thread via CallInvoker
                jsInvoker->invokeAsync([resolve, hashHex](jsi::Runtime& rt) {
                    resolve->asObject(rt).asFunction(rt).call(rt, jsi::String::createFromUtf8(rt, hashHex));
                });
            }).detach();

            return jsi::Value::undefined();
        }
    );

    return promiseConstructor.callAsConstructor(rt, executor);
}

} // namespace facebook::react
```

---

## Bagian 5: Checklist Pemahaman (Self-Assessment Checklist)

Gunakan checklist ini untuk menguji kesiapan arsitektural Anda sebelum mengklaim penguasaan penuh atas Native Modules, JSI, dan New Architecture:

| Area Kompetensi | Indikator Keberhasilan | Status (Paham / Butuh Review) |
|---|---|---|
| **Arsitektur Dasar Bridge vs JSI** | Mampu menjelaskan secara visual alur eksekusi JSON message queue vs direct memory C++ pointer call via JSI. | [ ] |
| **Hermes Engine & JSI Integration** | Memahami peran `jsi::Runtime`, `jsi::HostObject`, `jsi::Value`, dan aturan thread-safety (single-threaded JS runtime). | [ ] |
| **TurboModules & Lazy Loading** | Mengetahui cara kerja lazy instantiation TurboModules saat startup dan perbandingannya dengan eager loading legacy modules. | [ ] |
| **React Native Codegen** | Mampu menulis file spec TypeScript (`TurboModule`) dan memahami proses generasi glue code C++ / Java / Obj-C. | [ ] |
| **Memory Management C++ / JS** | Memahami lifecycle host object, bahaya dangling pointer pada GC sweep, dan penggunaan zero-copy via `jsi::ArrayBuffer`. | [ ] |
| **Thread Boundary & CallInvoker** | Mampu mendispatch komputasi native ke background thread dan mengembalikan hasil ke JS Thread secara aman via `react::CallInvoker`. | [ ] |
| **Cross-Platform Native Extension** | Memahami integrasi C++ murni yang dapat di-share 100% antara platform Android (NDK/CMake) dan iOS (CocoaPods/Clang). | [ ] |
| **Production Diagnostics** | Mampu mendeteksi dan menyelesaikan issue memory leaks, ANR pada cold launch, dan crash `SIGSEGV` akibat concurrent runtime access. | [ ] |
