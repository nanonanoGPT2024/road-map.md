# BAB 01: Quiz, Challenge, & Knowledge Check
**Core Runtime, Dart Internals & Platform Fundamentals**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Event Loop Model & Queue Prioritization
Jelaskan secara mendalam arsitektur Single-Threaded Event Loop pada Dart Runtime. Bagaimana Dart mengelola eksekusi kode antara **Microtask Queue** dan **Event Queue**? Jelaskan konsekuensi langsung terhadap rendering UI Flutter jika developer mengeksekusi komputasi rekursif atau loop berulang yang terus-menerus mendaftarkan tugas ke dalam `scheduleMicrotask()`.

### Soal 1.2: Dart Compilation Pipeline (JIT vs AOT)
Bandingkan pipeline kompilasi Dart pada fase Development (JIT) dan Production (AOT). Bedah peran **Kernel Intermediate Representation (Kernel AST / `.dill`)**, **Dart VM Runtime**, dan mekanisme **Snapshotting** (Core snapshot, Script snapshot, AOT snapshot). Mengapa arsitektur kompilasi ini memungkinkan fitur Stateful Hot Reload yang instan pada Debug mode namun menghasilkan zero-JIT-overhead native binary pada Release mode?

### Soal 1.3: Dart Memory Subsystem & Dual-Generation GC
Dart Runtime mengimplementasikan Generational Garbage Collector yang terdiri dari **Young Generation (Nursery & Intermediate)** dan **Old Generation**.
1. Jelaskan siklus hidup suatu objek dari pertama kali dialokasikan di Nursery Space hingga dipromosikan (*tenured*) ke Old Generation.
2. Mengapa algoritma *Semispace Scavenger* pada Young Generation sangat optimal untuk paradigma Flutter yang memproduksi ribuan objek ephemeral (*immutable widgets*) per detik?

### Soal 1.4: Isolates Execution & Memory Isolation
Secara struktural, apa yang membedakan Dart **Isolate** dengan native OS thread konvensional? Jelaskan batasan memori antar-isolate (*isolated heap memory*) dan bagaimana Dart VM memfasilitasi komunikasi antar-isolate melalui `SendPort` dan `ReceivePort`. Apa yang terjadi di balik layar pada representasi payload data saat dikirimkan melewati batas isolate tersebut?

### Soal 1.5: Flutter Engine Layering & Platform Host Bridge
Uraikan batas arsitektural (*architectural boundary*) antara **Flutter Framework (Dart)**, **Flutter Engine (C++)**, dan **Platform Embedder (Native OS - Android/iOS/Desktop)**. Bagaimana sinyal `vsync` dari native display driver diteruskan melalui Engine hingga memicu eksekusi *window frame callback* pada Dart UI framework?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Diagnostik Microtask Starvation & Frame Jank
Sebuah aplikasi analitik finansial mengalami frame drop parah (turun ke 12-15 FPS) tepat saat sinkronisasi data lokal dijalankan, meskipun proses I/O file dibungkus dalam `Future`. Setelah ditelusuri dengan Dart DevTools Timeline/Performance View, ditemukan bahwa Event Queue tidak pernah dieksekusi selama window 200ms. 
* Identifikasi akar masalah (*root cause*) mekanistis di level Dart runtime loop.
* Bagaimana cara menginspeksi alokasi antrean ini via Dart DevTools Profiler?
* Tuliskan refaktor arsitektur kode untuk menjamin Event Queue (khususnya rendering frame pipeline) tetap mendapatkan alokasi *time slice* tanpa mengorbankan integritas sinkronisasi.

### Soal 2.2: Isolates: Serialization Overhead vs `TransferableTypedData`
Ketika mengirim payload data binary sebesar 50MB (misal: uncompressed sensor array) dari Worker Isolate ke Main Isolate menggunakan `SendPort.send(rawBytes)`:
1. Analisis alokasi CPU dan RAM yang terjadi selama proses *deep copy / serialization / OOM-risk*.
2. Jelaskan bagaimana `TransferableTypedData` memitigasi overhead tersebut secara mekanistis di level pointer memori Dart VM (Zero-Copy mechanics).
3. Apa implikasi struktural terhadap variabel asal di Isolate pengirim setelah `TransferableTypedData` ditransfer?

### Soal 2.3: Platform Channels Latency & Serialization Bottlenecks
Pada arsitektur `MethodChannel` standar:
* Bedah alur transmisi data dari Dart Layer -> `BinaryMessenger` -> C++ Engine (`flutter::MethodCodec`) -> Platform Embedder (Java/Kotlin JNI atau Objective-C/Swift RunLoop).
* Mengapa mengirimkan stream data 60 FPS berukuran besar (misal: raw YUV video frames) melalui `MethodChannel` menyebabkan bottleneck parah (jank dan context-switch overhead)?
* Jelaskan alternatif solusi arsitektural menggunakan **Flutter Texture Widget** (Hardware Surface) atau **Dart FFI direct memory access**.

### Soal 2.4: Old Generation GC Tracing & UI Hitch Analysis
Ketika aplikasi memiliki *in-memory cache* berukuran besar yang terdiri dari jutaan node objek kecil yang berumur panjang di Old Generation:
* Jelaskan bagaimana algoritma *Concurrent Mark* dan *Parallel Compact/Sweep* bekerja di Dart VM.
* Mengapa fase *Stop-the-World* (STW) singkat tetap tidak bisa dihindari, dan bagaimana hal ini berujung pada status "UI Hitch" di layar dengan refresh rate tinggi (90Hz / 120Hz ProMotion)?
* Rekomendasikan pola mitigasi manajemen memori pada Dart heap untuk mengurangi densitas penelusuran pointer oleh Old Gen GC.

### Soal 2.5: Dart FFI Internals: Pointer Lifecycle & Threading Boundary
Dalam implementasi `dart:ffi`:
* Jelaskan bahaya alokasi memori via `calloc` / `malloc` dari Dart layer jika tidak di-free secara eksplisit. Mengapa Dart Garbage Collector **tidak dapat** mendeteksi atau mereklamasi alokasi tersebut (*GC blindness*)?
* Bagaimana cara memanfaatkan `NativeFinalizer` (Dart 2.17+) untuk mengikat siklus hidup alokasi C/Rust native memory dengan siklus hidup Dart object wrapper?
* Jika native function C++ melakukan operasi blocking jangka panjang pada thread yang sama dengan thread Isolate Dart, apa yang terjadi pada runtime Flutter, dan bagaimana solusinya?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Frame Drop Akibat Parsing Payload WebSocket Ekstrem
Sebuah sistem High-Frequency Trading Mobile Client menerima payload JSON sebesar 4MB setiap 500ms melalui secure WebSocket. Developer menulis kode berikut:
```dart
channel.stream.listen((jsonString) {
  final data = jsonDecode(jsonString); // Parsing JSON
  processMarketData(data);             // Update in-memory state & notify UI
});
```
**Gejala di Produksi:**
Aplikasi mengalami freeze periodik (~150ms-300ms) setiap kali data tiba. Profiler menunjukkan lonjakan alokasi memori tajam (saw-tooth graph) dan eksekusi GC Scavenger yang berulang-ulang, bertepatan dengan hilangnya *frame rasterization budget* (8.33ms untuk 120Hz).

**Tugas Diagnostik:**
1. Mengapa `jsonDecode` membebani GC Scavenger secara eksponensial di Main Isolate?
2. Jika Anda memindahkan parsing ke fungsi `compute(parseJson, jsonString)`, jelaskan mengapa overhead komputasi total terkadang justru **meningkat** jika string JSON yang dipindahkan ke Isolate sangat besar.
3. Rancang arsitektur pemrosesan data end-to-end yang ideal untuk skenario streaming berkecepatan tinggi ini menggunakan kombinasi Worker Isolate persisten, raw binary formatting (e.g., Protobuf/FlatBuffers), dan memory pooling.

---

### Skenario B: Race Condition dan Deadlock pada Async Bridge Native-Dart
Aplikasi enterprise logistik mengintegrasikan SDK Hardware Barcode Scanner native melalui `EventChannel` (untuk stream data barcode) dan `MethodChannel` (untuk konfigurasi hardware). Developer melaporkan bahwa pada device scanner industri tertentu:
* Aplikasi mengalami silent freeze (*deadlock*) ketika user menekan trigger scanner fisik berkali-kali secara simultan (rapid hardware scanning).
* Data barcode sering datang dalam urutan yang salah (*out-of-order execution*), mengakibatkan verifikasi data di Main Isolate korup.

**Tugas Diagnostik:**
1. Bedah bagaimana OS Platform Thread (Android UI Thread / iOS Main Thread) berinteraksi dengan Dart Isolate Thread melalui `BinaryMessenger`. Apa yang terjadi jika platform side memanggil callback ke Dart saat Dart UI thread sedang sibuk memproses layout?
2. Mengapa arsitektur asynchronous `MethodChannel` tidak menjamin *strict sequential consistency* jika dipanggil beruntun tanpa queuing mechanism?
3. Rancang solusi arsitektur platform bridge yang *reentrant-safe*, *backpressure-aware*, dan menjamin integritas urutan eksekusi (*FIFO sequence integrity*).

---

### Skenario C: Crash OOM (Out-of-Memory) pada POS Berdaya Rendah (Embedded Linux / Low-RAM Android)
Sebuah sistem POS (Point-of-Sale) berbasis Flutter didistribusikan ke 20.000 terminal pintar berbasis Custom Android OS dengan RAM sangat terbatas (total 1GB, alokasi heap per-app dibatasi oleh platform OS maksimal 192MB).
* Setelah berjalan kontinu selama 48 jam di outlet retail, aplikasi tiba-tiba terminasi oleh OS (SIGKILL / Low Memory Killer / LMK).
* Analisis dump menunjukkan Dart heap memory sebenarnya hanya menggunakan 75MB, namun native memory footprint (`PSS - Proportional Set Size`) aplikasi tembus melampaui limit 192MB.

**Tugas Diagnostik:**
1. Mengapa terjadi diskrepansi masif antara alokasi Dart VM Heap dengan total Resident Set Size / PSS process di level sistem operasi?
2. Bagaimana subsistem grafis (Impeller/Skia glyph cache, decoded image memory cache, dan swap chain buffers) berkontribusi terhadap native heap di luar pantauan Dart GC?
3. Tuliskan rencana mitigasi sistemik:
   - Parameter konfigurasi `PaintingBinding.instance.imageCache`.
   - Strategi eviksi resource Engine.
   - Diagnostik menggunakan `adb shell dumpsys meminfo` dan Dart DevTools Memory Allocation Tracing untuk mengidentifikasi unmanaged memory leak.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Zero-Copy Stream Processing Engine via Dart Worker Isolates and FFI

#### 1. Deskripsi Masalah
Dalam aplikasi medical imaging portabel, aplikasi Flutter harus menerima stream raw signal continuous dari modul hardware native (via C-library dynamic library / `.so` / `.dylib`). Sinyal ini mengalirkan array sensor data berkecepatan tinggi: 50.000 data point per detik dalam format binary float array (`Float32List`). Data ini harus diproses melalui filtering matematika, diubah menjadi data koordinat visualisasi, dan dirender ke layar tanpa menyebabkan satu pun frame jank (wajib stabil di 60 FPS / 16.6ms frame time) dan tanpa menyebabkan GC Old-Generation pressure.

#### 2. Kebutuhan Implementasi (Requirements)
1. **Long-Running Persistent Worker Isolate:** Bangun satu worker isolate khusus yang hidup sepanjang siklus aplikasi, memiliki komunikasi dua arah (*bidirectional communication channel*) dengan Main Isolate melalui `SendPort`/`ReceivePort`.
2. **Backpressure & Task Throttling:** Implementasikan mekanisme antrean (*command queue*) dengan strategi backpressure (drop oldest/buffer) agar UI Isolate tidak kebanjiran message event.
3. **Zero-Copy / Native Pointer Bridge:** 
   - Gunakan `dart:ffi` untuk menerima pointer memori binary langsung dari modul simulasi native C/C++.
   - Bungkus native pointer tersebut ke dalam typed data array di Dart side tanpa menduplikasi memori heap (`Float32List.view` dari memory pointer).
   - Manfaatkan `TransferableTypedData` atau direct pointer passing antar-isolate untuk eliminasi alokasi salinan data di Young Gen GC.
4. **Lifecycle & Native Resource Cleanup:** Implementasikan `NativeFinalizer` atau explicit pointer disposal pattern guna memastikan tidak ada kebocoran memori native (0-leak verification).

#### 3. Batasan Teknis (Constraints)
* Dilarang menggunakan dependency packages eksternal (murni Dart SDK: `dart:isolate`, `dart:ffi`, `dart:typed_data`, `dart:async`).
* UI Isolate mutlak dilarang melakukan komputasi floating-point array (semua perhitungan analitik harus berjalan di Worker Isolate).
* Tidak boleh ada lonjakan alokasi memori Dart Heap yang memicu Old Gen GC STW (Stop-the-World) hitch selama 60 detik stress test.

#### 4. Kriteria Keberhasilan (Expected Output)
1. Source code arsitektural lengkap:
   - File 1: `native_bridge.dart` (FFI bindings & memory management).
   - File 2: `signal_worker_isolate.dart` (Isolate loop, port handler, zero-copy processor).
   - File 3: `telemetry_controller.dart` (Main isolate interface, backpressure handling, stream binding to UI).
2. Laporan Analisis Kinerja:
   - Tunjukkan bukti perbandingan profiling konseptual: Alokasi memori dan CPU overhead antara pendekatan standar (`MethodChannel` + standard `List<double>`) vs implementasi FFI + `TransferableTypedData`.

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk memverifikasi kesiapan arsitektural Anda sebelum melanjutkan ke bab berikutnya.

### Saya harus memahami:
- [ ] Siklus kerja deterministik Event Loop: Prioritas mutlak Microtask Queue di atas Event Queue dan risiko starvation.
- [ ] Perbedaan fundamental arsitektur kompilasi JIT (Dart VM Kernel Interpreter + JIT compiler) vs AOT (Mach-O / ELF native machine code assembly).
- [ ] Algoritma dual-generation Garbage Collector Dart: Semispace Copying/Scavenging pada Young Gen dan Concurrent-Mark / Parallel-Sweep pada Old Gen.
- [ ] Isolasi heap memori Isolate, implikasi threading OS, dan biaya serialization message-passing.
- [ ] Alur komunikasi low-level Platform Channels melalui `BinaryMessenger`, `MethodCodec`, dan batasan context-switch pada native OS threads.
- [ ] Arsitektur Dart FFI (`dart:ffi`): Pointer dereferencing, ABI matching, native heap vs Dart heap, serta mekanisme `NativeFinalizer`.
- [ ] Struktur grafis Flutter Engine: Pipeline bridge penghubung antara UI Dart framework, Engine (C++), dan Renderer (Impeller / Skia).

### Saya tidak perlu menghafal:
- [ ] Konstanta numerik internal pada source code Dart VM C++ (misal: ukuran default fixed page size atau threshold spesifik nursery size dalam kilobyte).
- [ ] Bitwise opcode internal dari Dart Kernel Binary AST format (`.dill`).
- [ ] Detail implementasi spesifik platform embedder assembly pada tiap varian arsitektur CPU (ARMv7, ARMv8, x86_64).
- [ ] Source code exact C++ bindings class `flutter::BinaryMessenger` di level engine.

### Saya harus bisa melakukan:
- [ ] Menganalisis CPU Flame Chart dan Memory Allocation Profile pada Dart DevTools untuk mendeteksi event loop blockage, memory leak, dan GC pauses.
- [ ] Merancang arsitektur multithreading menggunakan persistent background isolates dan zero-copy primitives (`TransferableTypedData` / Pointer passing) untuk komputasi berat.
- [ ] Menentukan kapan harus menggunakan `MethodChannel`, `EventChannel`, `Flutter Texture`, atau `dart:ffi` berdasarkan SLA latency dan payload footprint.
- [ ] Mengidentifikasi dan memperbaiki akar masalah Native Memory Leak vs Dart Heap Leak pada aplikasi berskala besar.
- [ ] Mengonfigurasi strategi backpressure untuk aliran data bervolume tinggi agar tidak mengorbankan rendering budget 60/120 FPS.