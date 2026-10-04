# BAB-01-Fondasi-dan-Arsitektur: Quiz, Challenge, & Knowledge Check

Dokumen ini dirancang untuk menguji pemahaman konseptual dan kapabilitas teknis Anda terkait arsitektur internal React Native, evolusi dari Old Architecture (Bridge-based) menuju New Architecture (Fabric, TurboModules, Codegen, dan JSI), serta optimalisasi JavaScript Engine Hermes.

---

## Bagian 1: Basic Questions (Fondasi Konseptual)

### Pertanyaan 1: Peran JavaScript Interface (JSI)
**Pertanyaan:**
Apa perbedaan mendasar antara mekanisme komunikasi melalui **Bridge (Old Architecture)** dengan **JavaScript Interface / JSI (New Architecture)** dalam eksekusi kode native dari JavaScript thread?

*Jawaban Singkat & Pembahasan Teknis:*
- **Bridge (Old Architecture):** Beroperasi secara asinkron dengan serialisasi/deserialisasi payload berbasis string JSON. Data dikirimkan melewati antrean FIFO asinkron antara JavaScript runtime dan Native Host (Java/Kotlin/Obj-C). Hal ini menimbulkan overhead alokasi memori berlebih dan latensi serialization, serta tidak mendukung eksekusi sinkron langsung.
- **JSI (New Architecture):** Menyediakan layer abstraksi C++ ringan yang mengekspos C++ Host Objects langsung ke dalam runtime JavaScript. JS thread memegang referensi memori langsung ke object native (C++ pointer), memungkinkan pemanggilan metode native secara sinkron (synchronous direct invocation) tanpa konversi JSON.

---

### Pertanyaan 2: Karakteristik Hermes Engine
**Pertanyaan:**
Mengapa Hermes Engine menghasilkan waktu **Time-to-Interactive (TTI)** yang jauh lebih cepat dibandingkan JavaScriptCore (JSC) pada perangkat mobile?

*Jawaban Singkat & Pembahasan Teknis:*
Hermes mengadopsi pendekatan **Ahead-of-Time (AOT) Bytecode Compilation**. Saat proses build aplikasi (bundling), Hermes Compiler mentranspilasi kode JavaScript ke format bytecode biner (`.hbc`). Saat aplikasi diluncurkan di runtime:
1. Engine tidak perlu melakukan parsing syntax tree (AST parsing) dan kompilasi sumber JavaScript secara on-the-fly.
2. Bytecode langsung dipetakan ke memori virtual menggunakan `mmap()`, mengurangi alokasi RAM secara signifikan dan memotong waktu inisialisasi JS runtime.

---

### Pertanyaan 3: Peran Codegen dalam New Architecture
**Pertanyaan:**
Apa fungsi utama dari tool **Codegen** pada arsitektur React Native modern dan masalah apa yang dieliminasinya?

*Jawaban Singkat & Pembahasan Teknis:*
Codegen membaca file spesifikasi bertipe statis (TypeScript atau Flow interface) untuk menghasilkan boilerplate kode C++ statis (JSI bindings), Java JNI interfaces, dan Objective-C protocols secara otomatis saat build-time.
- **Masalah yang Dieliminasi:** Menghilangkan mismatch tipe data pada saat runtime (runtime type mismatch errors) antara layer JavaScript dan native, serta menghapus kebutuhan menulis binding JSI/JNI manual yang rentan memory leak dan undefined behavior.

---

### Pertanyaan 4: Threading Model di React Native
**Pertanyaan:**
Sebutkan 3 thread utama yang beroperasi dalam runtime React Native serta fungsinya masing-masing.

*Jawaban Singkat & Pembahasan Teknis:*
1. **UI Thread (Main Thread):** Bertanggung jawab menangani rendering grafis native host platform, kalkulasi layout native, dan delegasi event interaksi pengguna (touch gesture handling).
2. **JS Thread:** Menjalankan bundle logika React (reconciliation, state management, lifecycle hooks, network callbacks, dan business logic).
3. **Shadow Thread (pada Old Architecture) / Layout Engine (pada New Architecture):** Bertugas menghitung dimensi matematis dan koordinat layout pohon komponen menggunakan engine Yoga (Flexbox layout calculation) sebelum dikirimkan ke UI thread untuk di-instansiasi menjadi native views.

---

### Pertanyaan 5: Komponen Pengganti Bridge
**Pertanyaan:**
Sebutkan dua subsistem utama yang menggantikan fungsi Bridge di New Architecture untuk layer rendering UI dan layer modul fungsional native.

*Jawaban Singkat & Pembahasan Teknis:*
1. **Fabric:** Sistem rendering baru yang menggantikan arsitektur legacy `UIManager`. Fabric mengintegrasikan React renderer dengan C++ core, mendukung sinkronisasi layout langsung, dan memanfaatkan React 18 Concurrent Features.
2. **TurboModules:** Sistem modular native baru yang menggantikan legacy NativeModules. Memanfaatkan JSI untuk mengaktifkan lazy loading modul native (hanya di-load saat dipanggil pertama kali) dan pemanggilan metode sinkron.

---

## Bagian 2: Intermediate Questions (Analisis & Arsitektur Mendalam)

### Pertanyaan 6: Fabric Render Pipeline (3 Fase)
**Pertanyaan:**
Jelaskan alur 3 fase pipeline rendering pada Fabric: **Render**, **Commit**, dan **Mount**.

*Jawaban & Pembahasan Teknis:*
1. **Render Phase:** React mengeksekusi elemen pohon komponen di JS thread, lalu Fabric membuat *React Shadow Tree* yang terdiri dari C++ Shadow Nodes yang bersifat immutable.
2. **Commit Phase:** Tree traversal dan perhitungan layout Flexbox dijalankan menggunakan Yoga C++. Dua sub-fase terjadi di sini:
   - *Cross-Component Layout:* Perhitungan dimensi fisik (`x, y, width, height`).
   - *Tree Promotion:* React Shadow Tree dipromosikan menjadi *Next Shadow Tree* yang siap di-mount.
3. **Mount Phase:** *Next Shadow Tree* ditransformasikan menjadi representasi view native aktual pada target platform (misalnya `UIView` di iOS atau `android.view.View` di Android). Operasi mutasi tree dijalankan secara atomic di UI thread untuk menghindari visual tearing.

---

### Pertanyaan 7: Lazy Loading pada TurboModules
**Pertanyaan:**
Pada Old Architecture, seluruh `NativeModules` didaftarkan secara eager saat proses boot sequence aplikasi. Bagaimana TurboModules mengatasi inefisiensi memori ini dan bagaimana mekanisme resolusinya bekerja di C++?

*Jawaban & Pembahasan Teknis:*
TurboModules mengimplementasikan pola arsitektur **Service Provider Registry berbasis JSI**:
- Saat inisialisasi, hanya C++ host object registry ringan yang diekspos ke JS runtime. Modul native platform (Java/Kotlin atau Obj-C/Swift) belum diinstansiasi ke dalam memori.
- Ketika JavaScript memanggil property atau method modul terkait (misal: `TurboModuleRegistry.get('SecureStorage')`), C++ layer memeriksa apakah instance native telah dibuat.
- Jika belum, native class baru di-instansiasi (lazy initialization), disimpan di cache, dan JSI binding dihubungkan ke JavaScript object. Hal ini memotong konsumsi heap memory saat cold start secara drastis.

---

### Pertanyaan 8: State Immutability pada C++ Shadow Nodes
**Pertanyaan:**
Mengapa Fabric mengadopsi struktur data *immutable* untuk C++ Shadow Nodes? Keuntungan apa yang didapatkan dalam konteks konkurensi (concurrency) dan thread safety?

*Jawaban & Pembahasan Teknis:*
Dengan sifat *immutable*:
1. **Thread Safety Tanpa Locking Overhead:** Shadow Node tidak dapat dimodifikasi setelah dibuat. JS thread, Background Layout thread, dan UI Main thread dapat membaca tree state secara simultan tanpa risiko race condition atau kebutuhan mutex/lock yang memicu deadlock.
2. **Concurrent React Support:** Fabric dapat melakukan fork render tree di background tanpa merusak tree yang sedang aktif ditampilkan di layar. Jika prioritas user input masuk (misal typing atau scrolling), rendering background dapat dibatalkan (aborted) secara instan tanpa menyisakan *dirty state*.

---

### Pertanyaan 9: Synchronous Native Invocation via JSI & UI Freezing Risk
**Pertanyaan:**
JSI memungkinkan pemanggilan fungsi native secara sinkron (`sync method`). Dalam kondisi apa synchronous call sangat krusial, dan apa risiko performa jika fitur ini disalahgunakan?

*Jawaban & Pembahasan Teknis:*
- **Kebutuhan Krusial:** Sinkronisasi posisi scroll (`onScroll`), kalkulasi frame animasi gestur real-time, atau akses sinkron ke memory buffer / hardware crypto key di mana delay asinkron 1 frame (16ms pada 60fps) dapat menghasilkan dropped frames atau layout jumping.
- **Risiko Performa:** Jika fungsi native yang dipanggil secara sinkron melakukan komputasi berat (heavy I/O, network fetch, atau file parsing besar), JS Thread atau UI Thread akan terblokir total (UI freezing), memicu framedrop parah dan sistem operasi dapat memicu dialog *Application Not Responding (ANR)* di Android.

---

### Pertanyaan 10: Hermes Bytecode Alignment & Memory-Mapped File (`mmap`)
**Pertanyaan:**
Jelaskan prinsip kerja `mmap` pada Hermes Engine dalam mengonsumsi bundle `.hbc` dari file system platform Android/iOS!

*Jawaban & Pembahasan Teknis:*
Sistem operasi memetakan file bytecode `.hbc` langsung dari storage disk ke dalam address space virtual process aplikasi tanpa perlu membaca seluruh file ke RAM (heap allocation):
1. **Demand Paging:** Sistem operasi hanya memuat halaman memori (pages berukuran 4KB) yang dieksekusi oleh interpreter Hermes saat dibutuhkan.
2. **Clean Memory:** Memory pages yang di-mmap bersifat read-only ("clean memory"). Jika OS mengalami memory pressure, pages ini dapat langsung didrop dari RAM tanpa ditulis ke swap disk, karena OS dapat membacanya kembali dari storage disk kapan saja, mencegah crash akibat Out-of-Memory (OOM).

---

## Bagian 3: Skenario Kasus Nyata Produksi (Root Cause Analysis)

### Skenario 1: Frame Drop Masif pada List Virtualisasi Berisi Komponen Kompleks
**Kasus:**
Aplikasi e-commerce skala besar mengalami dropped frames (FPS turun dari 60 ke 18-24 FPS) saat user melakukan fast scrolling pada katalog produk tak terbatas (`FlashList`/`FlatList`). Profiling pada Old Architecture menunjukkan antrean Bridge mengalami saturasi tinggi dengan latency pengiriman pesan >120ms.

**Tugas Analisis:**
1. Analisis akar masalah (root cause) pada tingkat thread communication.
2. Bagaimana migrasi ke New Architecture (Fabric + JSI) menyelesaikan permasalahan ini secara arsitektural?

*Solusi & Pembahasan Teknis:*
1. **Root Cause:**
   - Setiap event scroll menghasilkan event payload (`onScroll`) dari Main UI thread yang diserialisasi ke JSON, dikirim via Bridge ke JS thread.
   - JS thread menghitung item windowing dan mengirimkan serangkaian perintah mutasi DOM/View kembali via Bridge berupa array JSON perintah layout (`measure`, `insertChild`, `updateView`).
   - Karena Bridge bersifat single-channel dan asinkron, terjadi kemacetan antrean (Bridge congestion/traffic jam). JS thread terlambat mengirimkan instruksi render, menyebabkan "white blank boxes" dan UI thread terblokir menunggu response.
2. **Resolusi New Architecture:**
   - **Fabric Direct Measurement:** Layout kalkulasi dilakukan langsung pada level C++ Shadow Tree tanpa bolak-balik serialization JSON.
   - **Synchronous View Flattening:** Fabric secara otomatis meratakan hirarki view (view flattening) di C++, memangkas jumlah view native aktual di memory Android/iOS.
   - **Priority Scheduling:** Fabric mendukung prioritasi event, sehingga event rendering layout item list dikerjakan mendahului event analitik non-kritis.

---

### Skenario 2: Out of Memory (OOM) Crash saat Cold Launch di Android Low-End
**Kasus:**
Aplikasi fintech mengalami lonjakan crash rate sebesar 8.5% spesifik pada perangkat Android RAM 2GB - 3GB dengan pesan logcat: `Fatal signal 11 (SIGSEGV), code 1 (SEGV_MAPERR)` atau `OutOfMemoryError: Failed to allocate a [...] byte allocation with [...] free bytes`. Bundle JavaScript berukuran 22 MB (minified JS).

**Tugas Analisis:**
Identifikasi mengapa arsitektur non-Hermes (JavaScriptCore) gagal dalam skenario ini, dan jelaskan langkah optimasi deployment Hermes untuk menekan konsumsi resident memory (RSS).

*Solusi & Pembahasan Teknis:*
1. **Root Cause pada JSC:**
   - JSC membaca file JavaScript mentah (22 MB plaintext) ke dalam RAM heap.
   - Parser JSC mengonversi teks menjadi Abstract Syntax Tree (AST), menghasilkan duplikasi alokasi memori hingga 2x-3x ukuran file asli.
   - Bytecode compiler JSC mengompilasi AST ke bytecode di memori perangkat saat inisialisasi aplikasi.
   - Total konsumsi memori instan dapat melompat melampaui limit heap per-process (sering kali hanya 192MB-256MB pada device low-end), memicu OOM killer dari kernel Linux.
2. **Langkah Optimasi dengan Hermes:**
   - Aktifkan kompilasi Hermes Bytecode di `android/app/build.gradle`: `project.ext.react = [ enableHermes: true ]`.
   - Pastikan Hermes menghasilkan single runtime bytecode file (`index.android.bundle.hbc`).
   - Manfaatkan `mmap()` native Hermes: alokasi memori heap berkurang drastis karena file dibaca per-page demand tanpa parsing AST di memori RAM.
   - Optimasi Garbage Collection Hermes dengan menyetel flag heap size tuning pada native initialization jika diperlukan (`hermes::vm::RuntimeConfig`).

---

### Skenario 3: UI Glitch & Layout Jumping pada Form Interaktif dengan Keyboard
**Kasus:**
Pada screen checkout, terdapat text field input dinamis. Ketika keyboard native muncul, layout melakukan resize. Pada Old Architecture, tombol CTA (Call-to-Action) di bagian bawah terlihat "tertinggal" (lagging 2-3 frame) dan melompat secara kasar, menciptakan efek flicker visual yang mengganggu.

**Tugas Analisis:**
Jelaskan fenomena "Asynchronous Layout Desynchronization" yang menjadi kelemahan mendasar Old Architecture dalam menangani keyboard avoidance, serta bagaimana Fabric mengeliminasi jeda frame tersebut.

*Solusi & Pembahasan Teknis:*
1. **Mekanisme Desinkronisasi:**
   - Native UI thread mendeteksi keyboard height change dan memodifikasi window frame.
   - Event dikirimkan via Bridge ke JS thread untuk menjalankan hook `KeyboardAvoidingView` atau state update posisi layout.
   - JS thread mengeksekusi state update dan menghitung layout baru, lalu mengirim kembali instruksi update ukuran view ke Native UI thread via Bridge.
   - Selama proses asinkron 2-way trip ini (membutuhkan waktu 32ms - 64ms atau 2-4 frame pada 60Hz), UI native sudah merender frame baru keyboard sementara view React Native masih berada pada koordinat lama. Hasilnya adalah visual tearing/jumping.
2. **Resolusi Fabric:**
   - Fabric memungkinkan update layout sinkron langsung ke C++ Shadow Tree menggunakan koordinat native secara real-time.
   - Tree mutation dapat diintegrasikan dengan transaksi animasi native host platform (`UIView.animate` atau Android Window Insets Animation), sehingga proses kalkulasi frame tombol CTA dan frame keyboard berjalan pada siklus VSYNC yang persis sama.

---

## Bagian 4: Practical Chapter Challenge

### Judul Tantangan:
**Arsitektur Spesifikasi TurboModule "DeviceEntropyEngine" dengan Strict Type Codegen**

### Deskripsi Proyek:
Anda diminta merancang spesifikasi TurboModule C++ / Native modern untuk enkripsi perangkat bernama `DeviceEntropyEngine`. Modul ini harus mampu:
1. Menghasilkan token entropi acak secara sinkron (`generateEntropySync`) untuk kebutuhan tokenisasi kriptografi instan.
2. Membaca status integritas hardware secara asinkron (`verifyHardwareIntegrity`) yang mengembalikan Promise boolean.
3. Menyediakan EventEmitter untuk mendengarkan perubahan status hardware security level secara real-time.

### Instruksi Kerja:
1. Tuliskan file TypeScript Specification `NativeDeviceEntropyEngine.ts` yang mematuhi standar Codegen React Native New Architecture (`TurboModuleRegistry`).
2. Definisikan C++ JSI Native Module Header Specification (`NativeDeviceEntropyEngineSpec.h`) yang mencerminkan kontrak tipe dari Codegen.
3. Berikan penjelasan ringkas mengenai siklus pendaftaran modul melalui `TurboModuleProvider`.

---

### Solusi Referensi Implementasi:

#### 1. File Spesifikasi Codegen: `NativeDeviceEntropyEngine.ts`
```typescript
import { TurboModule, TurboModuleRegistry } from 'react-native';

export interface HardwareIntegrityResult {
  readonly isValid: boolean;
  readonly securityPatchLevel: string;
  readonly biometricAvailable: boolean;
}

export interface Spec extends TurboModule {
  // Synchronous method via JSI
  generateEntropySync(length: number): string;

  // Asynchronous method via Promise
  verifyHardwareIntegrity(): Promise<HardwareIntegrityResult>;

  // Lifecycle EventEmitter support
  addListener(eventName: string): void;
  removeListeners(count: number): void;
}

export default TurboModuleRegistry.getEnforcing<Spec>('DeviceEntropyEngine');
```

#### 2. C++ Generated Spec Binding (Representasi Header Codegen):
```cpp
// NativeDeviceEntropyEngineSpec.h
#pragma once

#include <ReactCommon/TurboModule.h>
#include <jsi/jsi.h>

namespace facebook::react {

class JSI_EXPORT NativeDeviceEntropyEngineCxxSpec : public TurboModule {
protected:
  NativeDeviceEntropyEngineCxxSpec(std::shared_ptr<CallInvoker> jsInvoker);

public:
  virtual jsi::String generateEntropySync(jsi::Runtime &rt, double length) = 0;
  virtual jsi::Value verifyHardwareIntegrity(jsi::Runtime &rt) = 0;
  virtual void addListener(jsi::Runtime &rt, jsi::String eventName) = 0;
  virtual void removeListeners(jsi::Runtime &rt, double count) = 0;
};

} // namespace facebook::react
```

#### 3. Analisis Mekanisme TurboModuleProvider:
- Codegen membaca `NativeDeviceEntropyEngine.ts` saat build phase dan menghasilkan file C++ abstract class `NativeDeviceEntropyEngineCxxSpec`.
- Developer mengimplementasikan logika C++ native atau JNI bridge yang mewarisi class tersebut.
- Modul didaftarkan ke `RCTTurboModuleManager` (iOS) atau `TurboModuleManager` (Android).
- Ketika JS memanggil `DeviceEntropyEngine.generateEntropySync(32)`, JSI runtime langsung mengeksekusi C++ function pointer di context thread pemanggil tanpa serialisasi data, mengembalikan raw string buffer langsung ke v8/Hermes engine.

---

## Bagian 5: Checklist Pemahaman Mandiri

Gunakan matriks checklist berikut untuk memvalidasi kesiapan Anda sebelum melangkah ke Bab 2:

| Konsep Kunci | Tingkat Pemahaman (1-5) | Verifikasi Mandiri |
|---|:---:|---|
| **Evolusi Arsitektur (Old vs New)** | [ ] | Mampu menjelaskan bottleneck serialisasi JSON pada Bridge dan solusinya via JSI pointer referential sharing. |
| **Hermes Internals & AOT** | [ ] | Paham perbedaan kompilasi bytecode AOT `.hbc` vs runtime JIT/interpreter tradisional serta dampak `mmap()`. |
| **Fabric Rendering Engine** | [ ] | Menguasai 3 tahapan pipeline: Render (Shadow Tree C++), Commit (Yoga Layout), dan Mount (Native View updates). |
| **TurboModules & Codegen** | [ ] | Mampu menulis kontrak TypeScript untuk Codegen dan memahami lazy-loading native modules saat runtime. |
| **Threading & Concurrency** | [ ] | Memahami interaksi antara Main UI Thread, JS Thread, dan Background Layout Thread tanpa risiko race condition. |
| **Debugging & Root Cause Analysis** | [ ] | Sanggup menganalisis bottleneck performa, memory leaks, ANR, dan layout tearing pada profil produksi. |

---
*Status: Dokumen Kuis, Challenge, dan Knowledge Check Bab 1 siap digunakan untuk evaluasi kompetensi kurikulum.*
