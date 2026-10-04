# Kurikulum Enterprise Node.js: Native Addons & Low-Level Interoperability
**Bab 09:** Native Addons & Low-Level Interoperability  
**Modul 02:** Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menguasai Arsitektur Memori Lintas-Batas (Cross-Boundary Memory Architecture):** Menjelaskan dan mengimplementasikan transfer data zero-copy antara V8 Heap dan Native Heap (C/C++) menggunakan `Napi::ArrayBuffer` dan `Napi::Buffer`.
2. **Mengimplementasikan Asynchronous Multithreading Native:** Membangun eksekusi non-blocking menggunakan `Napi::AsyncWorker` dan native background threads (`std::thread`) yang berinteroperasi secara aman dengan V8 Event Loop via `Napi::ThreadSafeFunction` (TSFN).
3. **Mencegah Kerusakan Fatal Engine (Crash Prevention):** Mendiagnosis dan mengeliminasi *undefined behavior*, *segmentation faults* (`SIGSEGV`), *thread race conditions*, dan *memory leaks* menggunakan AddressSanitizer (ASan), Valgrind, dan Core Dump analysis.
4. **Membangun Pipeline Distribusi Addon Standar Industri:** Menyusun sistem otomatisasi kompilasi cross-platform (Linux glibc/musl, macOS, Windows) menggunakan `prebuildify` / `cmake-js` dan GitHub Actions matrix tanpa mewajibkan compiler native di mesin target produksi.
5. **Merancang Native Module Tingkat Enterprise:** Mengintegrasikan library native C/C++ pihak ketiga ke dalam backend Node.js berlatensi ultra-rendah (<1ms) dengan throughput tinggi.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, engineer harus memiliki pemahaman mendalam tentang:
- **Node.js Internals:** Libuv event loop phases, V8 engine lifecycle, microtask/macrotask queues.
- **Konsep C++ Tingkat Lanjut (C++14/C++17):** Pointers, references, RAII (*Resource Acquisition Is Initialization*), smart pointers (`std::unique_ptr`, `std::shared_ptr`), `std::thread`, dan memory fences/atomics (`std::atomic`).
- **Fondasi Node-API (N-API):** Memahami perbedaan antara legacy NAN (*Native Abstractions for Node.js*) dan Node-API yang stabil secara ABI (*Application Binary Interface*).
- **Tooling Kompilasi C/C++:** `gcc`, `clang`, `make`, `node-gyp`, dan dasar konfigurasi compiler flags (`-O3`, `-fPIC`, `-fsanitize=address`).

---

## 3. Concept & Internal Architecture

Integrasi tingkat rendah antara Node.js dan C++ melibatkan dua boundary utama: **Runtime/Engine Boundary (V8)** dan **Threading Boundary (Libuv / OS Threads)**.

```
+-------------------------------------------------------------------------------+
|                               NODE.JS RUNTIME                                 |
|                                                                               |
|  +-------------------------------------+   +-------------------------------+  |
|  |           V8 HEAP MEMORY            |   |          NATIVE HEAP          |  |
|  |                                     |   |        (glibc / jemalloc)     |  |
|  |  +-------------------------------+  |   |                               |  |
|  |  | JS Object / Fast Properties   |  |   |  +-------------------------+  |  |
|  |  +-------------------------------+  |   |  | C++ Class Allocations   |  |  |
|  |  | v8::ArrayBuffer View          |======|==> Shared Backing Store    |  |  |
|  |  | (Zero-Copy Target)            |  |   |  | (Raw malloc/mmap memory)|  |  |
|  |  +-------------------------------+  |   |  +-------------------------+  |  |
|  +-------------------------------------+   +-------------------------------+  |
|                     |                                      ^                  |
|                     | N-API (ABI Boundary)                 | Direct Pointer   |
|                     v                                      | Access           |
|  +-------------------------------------------------------------------------+  |
|  |                   NODE-API LAYER (node-addon-api)                       |  |
|  +-------------------------------------------------------------------------+  |
|         |                                              ^                      |
|         | Non-blocking Task                            | ThreadSafeFunction   |
|         v                                              | Callback Queue       |
|  +-------------------------+               +-------------------------------+  |
|  |    LIBUV EVENT LOOP     |               |     DETACHED OS THREADS       |  |
|  |  +-------------------+  |               |  (Hardware / Worker Threads)  |  |
|  |  | UV Worker Pool    |  |               |  +-------------------------+  |  |
|  |  | (default: 4 thds) |  |               |  | POSIX / C++11 Threads   |  |  |
|  |  +-------------------+  |               |  | (High-load computation) |  |  |
|  +-------------------------+               +-------------------------------+  |
+-------------------------------------------------------------------------------+
```

### 3.1. Dual-Heap Architecture & Memory Pinning
JavaScript berjalan di atas V8 Heap, yang secara agresif dikelola oleh V8 Garbage Collector (Scavenger untuk Young Generation, Major GC / Full Mark-Sweep-Compact untuk Old Generation). Saat GC berjalan, pointer objek dapat berpindah (*memory compaction*).
- Jika kode native menyimpan raw pointer ke JS Object secara langsung, objek tersebut dapat direlokasi oleh GC, menghasilkan **dangling pointer** dan memory corruption.
- Node-API memecahkan ini melalui **Handle Scopes** (`Napi::HandleScope`, `Napi::EscapableHandleScope`) dan **References** (`Napi::Reference<T>`). Reference memberitahu GC V8 untuk mempertahankan referensi objek atau meningkatkan referensinya menjadi weak/strong reference.
- **Zero-Copy Memory Access:** Node.js `Buffer` atau `ArrayBuffer` dialokasikan di luar V8 Heap reguler menggunakan V8 ArrayBuffer Allocator (sering kali dialokasikan di Native Heap). Kita dapat mengakses raw pointer memori ini dari C++ tanpa menyalin byte sama sekali (`Napi::Buffer::Data()`).

### 3.2. Threading Model: Main Thread vs Background Execution
Node.js bersifat single-threaded pada context eksekusi V8 JavaScript. **Aturan Utama:** Objek V8 (`Napi::Value`, `Napi::Object`, `Napi::Function`, dll.) **TIDAK BOLEH** diakses di luar V8 Main Thread. Pelanggaran terhadap aturan ini menyebabkan crash deterministik atau data corruption yang sulit dilacak.

Untuk menjalankan kalkulasi native intensif tanpa memblokir event loop:
1. **Libuv Worker Pool (`Napi::AsyncWorker`):** Tugas dikirim ke worker pool internal Node.js (ukuran diatur via `UV_THREADPOOL_SIZE`). Cocok untuk I/O native pendek atau CPU tasks moderat.
2. **Dedicated OS Threads + `Napi::ThreadSafeFunction` (TSFN):** Addon membuat thread OS independen (`std::thread`). Thread ini memproses komputasi secara berkelanjutan dan mengirimkan hasilnya kembali ke V8 main thread melalui TSFN queue. TSFN bertindak sebagai thread-safe message bridge yang menjadwalkan eksekusi callback V8 pada putaran event loop berikutnya.

---

## 4. Why & What

| Dimensi | JavaScript / TypeScript Murni | WebAssembly (Wasm) | Node.js Native Addon (Node-API) |
| :--- | :--- | :--- | :--- |
| **Akses Hardware/OS** | Terisolasi Sandbox OS | Sangat Terbatas (WASI) | **Akses Penuh** (Direct syscall, ioctl, GPU/CUDA, SIMD, AVX-512) |
| **Model Memori** | Garbage-collected V8 Heap | Linear Memory terisolasi (Salin via bridge) | **Shared Heap / Direct Pointer** (Zero-copy interop langsung) |
| **Dukungan Multithreading** | Worker Threads (Isolated Memory) | Web Workers / SharedArrayBuffer atomics | **Full Native Multithreading** (`std::thread`, Thread Pools, SIMD parallelism) |
| **Performa Komputasi Berat** | Rendah - Menengah (JIT overhead) | Mendekati Native (~70-90% C++) | **100% Native Bare-Metal Performance** |
| **Integrasi Legacy SDK** | Tidak bisa langsung (Butuh wrapper daemon) | Harus dikompilasi via Emscripten | **Dukungan Native C/C++ SDK Langsung** (RocksDB, OpenCV, OpenSSL) |

### Kapan Menggunakan Native Addon?
- **Throughput Ekstrem & Latensi Mikrodetik:** Pemrosesan feed audio/video biner, machine learning inference langsung via TensorRT/ONNX Runtime native, atau engine transaksi finansial frekuensi tinggi (HFT).
- **Wrapper Proprietary C++ SDK:** Mengintegrasikan library hardware (e.g., PCIe capture cards, HSM devices, proprietary DB drivers) yang hanya mendistribusikan C/C++ header dan binary `.so`/`.dylib`/`.dll`.
- **Optimalisasi Memori Skala Gigabyte:** Menghindari beban Garbage Collector V8 saat memproses buffer data raksasa dalam memori (misalnya pemrosesan image batch) dengan mengelolanya langsung di Native Heap via custom allocator (`jemalloc`).

---

## 5. How (Workflow Detail)

Alur kerja implementasi C++ Addon modern berbasis `node-addon-api` dan `ThreadSafeFunction`:

```
[ JavaScript Caller ]
        |
        | 1. Memanggil Native Method: addon.startProcessing(buffer, onProgress)
        v
[ N-API Main Thread Boundary ]
        |
        | 2. Validasi argumen & Pin Memory (Ambil raw byte pointer dari Buffer)
        | 3. Inisialisasi Napi::ThreadSafeFunction membungkus callback JS
        | 4. Spawn std::thread (Background Native Thread)
        | 5. Return immediate Promise / Status ke JS
        v
[ Background Native OS Thread ]
        |
        | 6. Menjalankan komputasi CPU intensif / pemrosesan data SIMD
        | 7. Periodik: Memanggil TSFN.NonBlockingCall(payload)
        v
[ Libuv Event Loop Synchronization ]
        |
        | 8. TSFN menaruh callback execution request ke Libuv loop queue
        v
[ V8 Main Thread Callback Dispatch ]
        |
        | 9. Main loop membaca queue -> Konversi data C++ ke Napi::Value
        | 10. Mengeksekusi callback onProgress() di JavaScript runtime
        v
[ Background Thread Selesai ]
        |
        | 11. TSFN.Release() -> Menutup thread lifecycle & Resolve Promise
```

---

## 6. Analogy & Diagram ASCII

Bayangkan Node.js sebagai **Restoran Bintang Lima**:
- **JavaScript Main Thread** adalah **Pelayan Restoran (Waiter)**. Ia harus selalu bergerak melayani tamu (Event Loop). Jika pelayan disuruh memotong 100 kg daging sapi di dapur, seluruh tamu restoran akan terlantar (Event Loop Freeze).
- **V8 Heap** adalah **Meja Pelanggan**. Bersih, otomatis dibersihkan oleh petugas kebersihan (Garbage Collector). Tetapi petugas kebersihan sering memindahkan piring saat membersihkan meja.
- **Native Addon (C++)** adalah **Dapur Khusus Eksekutif**. Di sini koki memegang pisau bedah mesin berkecepatan tinggi.
- **Zero-Copy Buffer** adalah **Baki Bersama (Shared Tray)** yang dapat diakses langsung oleh Pelayan dan Koki tanpa perlu menyalin makanan ke piring baru.
- **ThreadSafeFunction (TSFN)** adalah **Lonceng Pesanan Dapur**. Saat koki selesai memotong daging di ruang belakang, ia menekan lonceng agar pelayan mengambil pesanan saat pelayan memiliki waktu luang, tanpa koki perlu keluar mengganggu tamu di depan.

```
JS Event Loop (Pelayan)                Native Background Worker (Dapur Khusus)
  +-------------------------+              +-------------------------------+
  |  Menerima Order         |              |  Menerima Raw Memory Pointer  |
  |  Daftar TSFN Callback   |              |  (Zero-Copy Input Buffer)     |
  +-------------------------+              +-------------------------------+
               |                                           |
               |                                           v
               |                             [Looping Pemrosesan Berat]
               |                                           |
               |   TSFN NonBlockingCall()                  |
               |<==========================================+
               v
  +-------------------------+
  |  Callback JS Dipanggil  |
  |  (Update Progress UI)   |
  +-------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Zero-Copy Fast Buffer Inverter

Contoh ini menunjukkan manipulasi bit langsung pada Node.js `Buffer` tanpa alokasi memori tambahan dari C++.

#### `binding.gyp`
```python
{
  "targets": [
    {
      "target_name": "native_inverter",
      "sources": [ "inverter.cc" ],
      "include_dirs": [
        "<!@(node -p \"require('node-addon-api').include\")"
      ],
      "dependencies": [
        "<!(node -p \"require('node-addon-api').gyp\")"
      ],
      "cflags!": [ "-fno-exceptions" ],
      "cflags_cc!": [ "-fno-exceptions" ],
      "defines": [ "NAPI_DISABLE_CPP_EXCEPTIONS" ]
    }
  ]
}
```

#### `inverter.cc`
```cpp
#include <napi.h>

Napi::Value InvertBufferZeroCopy(const Napi::CallbackInfo& info) {
    Napi::Env env = info.Env();

    // 1. Validasi argumen
    if (info.Length() < 1 || !info[0].IsBuffer()) {
        Napi::TypeError::New(env, "Argument 0 harus bertipe Buffer").ThrowAsJavaScriptException();
        return env.Null();
    }

    // 2. Ambil referensi Buffer dan raw pointer
    Napi::Buffer<uint8_t> buffer = info[0].As<Napi::Buffer<uint8_t>>();
    uint8_t* raw_data = buffer.Data();
    size_t length = buffer.Length();

    // 3. Modifikasi in-place secara langsung (Zero-Copy)
    for (size_t i = 0; i < length; ++i) {
        raw_data[i] = ~raw_data[i]; // Bitwise NOT
    }

    return Napi::Boolean::New(env, true);
}

Napi::Object Init(Napi::Env env, Napi::Object exports) {
    exports.Set(Napi::String::New(env, "invertBufferZeroCopy"), 
                Napi::Function::New(env, InvertBufferZeroCopy));
    return exports;
}

NODE_API_MODULE(native_inverter, Init)
```

---

### 7.2. Practical Example: Multithreaded Hash Computation Engine with Progress Streaming

Contoh enterprise menggunakan thread native C++ independen (`std::thread`), streaming progress via `Napi::ThreadSafeFunction`, dan pemrosesan chunk memori secara non-blocking.

#### `hasher.cc`
```cpp
#include <napi.h>
#include <thread>
#include <vector>
#include <chrono>
#include <atomic>

struct ProgressData {
    size_t processed_bytes;
    size_t total_bytes;
};

class StreamingHasherContext {
public:
    StreamingHasherContext(Napi::Env env, Napi::Function progressCallback, Napi::Promise::Deferred deferred, 
                           uint8_t* data, size_t length)
        : deferred_(deferred), data_(data), length_(length), is_aborted_(false) {
        
        // Buat ThreadSafeFunction
        tsfn_ = Napi::ThreadSafeFunction::New(
            env,
            progressCallback,
            "StreamingHasherResource",
            0, // Queue size tak terbatas
            1  // Hanya 1 thread yang akan mereferensikan TSFN ini
        );
    }

    void Start() {
        worker_thread_ = std::thread(&StreamingHasherContext::Execute, this);
        worker_thread_.detach(); // Lepaskan thread agar berjalan independen di background
    }

    void Abort() {
        is_aborted_.store(true);
    }

private:
    void Execute() {
        const size_t CHUNK_SIZE = 1024 * 64; // 64KB per chunk
        size_t processed = 0;
        uint32_t rolling_hash = 0x811c9dc5; // FNV-1a basis

        while (processed < length_ && !is_aborted_.load()) {
            size_t current_chunk = std::min(CHUNK_SIZE, length_ - processed);
            
            // Simulasi operasi CPU yang berat
            for (size_t i = 0; i < current_chunk; ++i) {
                rolling_hash ^= data_[processed + i];
                rolling_hash *= 0x01000193;
            }
            processed += current_chunk;

            // Alokasikan progress data untuk TSFN
            ProgressData* progress = new ProgressData{ processed, length_ };

            // Kirim progress kembali ke V8 main thread
            auto callback = [](Napi::Env env, Napi::Function jsCallback, ProgressData* data) {
                if (env != nullptr && jsCallback != nullptr) {
                    Napi::Object obj = Napi::Object::New(env);
                    obj.Set("processed", Napi::Number::New(env, data->processed_bytes));
                    obj.Set("total", Napi::Number::New(env, data->total_bytes));
                    jsCallback.Call({ obj });
                }
                delete data; // Bersihkan heap memory di main thread
            };

            napi_status status = tsfn_.NonBlockingCall(progress, callback);
            if (status != napi_ok) {
                delete progress;
            }

            std::this_thread::sleep_for(std::chrono::milliseconds(10));
        }

        // Finalisasi: Beritahu JavaScript via Promise
        auto finalCallback = [this, rolling_hash](Napi::Env env, Napi::Function /*jsCallback*/) {
            if (is_aborted_.load()) {
                deferred_.Reject(Napi::String::New(env, "Operation Aborted").Value());
            } else {
                Napi::Object result = Napi::Object::New(env);
                result.Set("hash", Napi::Number::New(env, rolling_hash));
                result.Set("totalBytes", Napi::Number::New(env, length_));
                deferred_.Resolve(result);
            }
            delete this; // Self-destruction aman setelah lifecycle selesai
        };

        tsfn_.NonBlockingCall(finalCallback);
        tsfn_.Release(); // Kurangi thread counter agar event loop dapat selesai secara natural
    }

    Napi::ThreadSafeFunction tsfn_;
    Napi::Promise::Deferred deferred_;
    uint8_t* data_;
    size_t length_;
    std::atomic<bool> is_aborted_;
    std::thread worker_thread_;
};

Napi::Value CalculateHashStreaming(const Napi::CallbackInfo& info) {
    Napi::Env env = info.Env();

    if (info.Length() < 2 || !info[0].IsBuffer() || !info[1].IsFunction()) {
        Napi::TypeError::New(env, "Format argumen: (buffer: Buffer, progressCb: Function)").ThrowAsJavaScriptException();
        return env.Null();
    }

    Napi::Buffer<uint8_t> buf = info[0].As<Napi::Buffer<uint8_t>>();
    Napi::Function progressCb = info[1].As<Napi::Function>();

    Napi::Promise::Deferred deferred = Napi::Promise::Deferred::New(env);

    StreamingHasherContext* context = new StreamingHasherContext(
        env,
        progressCb,
        deferred,
        buf.Data(),
        buf.Length()
    );

    context->Start();

    return deferred.Promise();
}

Napi::Object InitAll(Napi::Env env, Napi::Object exports) {
    exports.Set("calculateHashStreaming", Napi::Function::New(env, CalculateHashStreaming));
    return exports;
}

NODE_API_MODULE(streaming_hasher, InitAll)
```

#### `app.js` (JavaScript Consumer)
```javascript
const path = require('path');
// Asumsi addon telah di-compile via node-gyp build
const { calculateHashStreaming } = require('./build/Release/streaming_hasher');

async function run() {
    console.log("[JS Main] Alokasi Buffer 20MB...");
    const largeBuffer = Buffer.alloc(20 * 1024 * 1024, 0xAB);

    console.log("[JS Main] Menjalankan Native Asynchronous Hasher...");
    const startTime = Date.now();

    const promise = calculateHashStreaming(largeBuffer, (progress) => {
        const percent = ((progress.processed / progress.total) * 100).toFixed(2);
        process.stdout.write(`\r[Progress Callback]: ${percent}% (${progress.processed}/${progress.total} bytes)`);
    });

    console.log("[JS Main] Event loop tetap aktif dan tidak terblokir!");
    
    // Demonstrasi event loop tetap melayani timer saat C++ thread bekerja
    const ticker = setInterval(() => {
        // Operasi non-blocking
    }, 50);

    const result = await promise;
    clearInterval(ticker);

    console.log("\n[JS Main] Komputasi Selesai!");
    console.log("Result:", result);
    console.log(`Durasi: ${Date.now() - startTime}ms`);
}

run().catch(console.error);
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Real-Time Financial Market Feed Transcoder (FX & Crypto L2 Order Book)
- **Konteks:** Perusahaan fintech multi-aset menerima snapshot dan delta order book tingkat tinggi melalui WebSocket biner terkompresi Zstandard (zstd) dengan payload hingga 50.000 pesan/detik.
- **Masalah:**
  - Parsing JSON murni di JavaScript menghasilkan latensi p99 sebesar 85ms akibat overhead string allocation dan tekanan GC V8 yang memicu "Stop-The-World" collection.
  - Implementasi binding native awal menggunakan `Napi::AsyncWorker` memicu starvation pada Libuv worker pool standar (4 thread), mengakibatkan operasi file I/O dan DNS lookup server terblokir.
- **Arsitektur Solusi:**
  1. Dibangun C++ Addon kustom yang membungkus `libzstd` dan serializer biner kustom (FlatBuffers/SBE).
  2. Addon membuat dedicated background worker thread-pool sendiri (terisolasi dari Libuv thread pool) dengan affinity CPU tertentu via `pthread_setaffinity_np`.
  3. Memanfaatkan **Zero-Copy Memory Buffer**: Node.js WebSocket engine (`ws` atau custom native client) meletakkan raw frame biner langsung ke native memory.
  4. Dekompresi dan delta parsing dieksekusi 100% di Native Heap C++.
  5. Hanya snapshot teragregasi yang diproyeksikan ke JS Main Loop setiap 16ms (tick interval) menggunakan `Napi::ThreadSafeFunction` dengan strategi **Drop-Oldest Queue** untuk mencegah V8 main thread overwhelmed.
- **Hasil:**
  - Latensi end-to-end p99 terpangkas dari **85ms menjadi 1.2ms**.
  - GC pause time berkurang hingga **94%**.
  - Pemanfaatan memori server stabil, zero memory fragmentation.

---

## 9. Trade-offs

| Aspek | Solusi Native (C++ / Node-API) | Pendekatan Pure JS / Worker Threads |
| :--- | :--- | :--- |
| **Performance & Compute** | **Sangat Tinggi:** Akses instruksi CPU modern, SIMD, cache locality manual. | **Sedang:** Dibatasi oleh optimasi turbofan V8 dan isolasi struktur heap. |
| **Latency Consistency (Jitter)**| **Konsisten:** Tidak terpengaruh Garbage Collector V8 untuk heap internal native. | **Fluktuatif:** GC GC pause ("Stop-The-World") memicu jitter latensi tinggi pada p99/p999. |
| **Development Velocity** | **Rendah:** Membutuhkan keahlian C++, manajemen memori manual, dan debugging pointer. | **Tinggi:** Siklus dev standar TypeScript/JavaScript dengan rapid prototyping. |
| **Crash Blast Radius** | **Kritis (Catastrophic):** Buffer overflow atau `SIGSEGV` seketika mematikan seluruh proses Node.js OS (`kill -9`). | **Aman:** Error menghasilkan `Error` exception yang dapat ditangkap oleh `try/catch` tanpa mematikan proses. |
| **Cross-Platform Delivery** | **Kompleks:** Harus mengompilasi matrix binary (glibc, musl/Alpine, arm64, x64, Windows MSVC). | **Sederhana:** File `.js` identik berjalan di semua platform ("Write Once, Run Anywhere"). |

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Mengakses `Napi::Value` / V8 Context di Luar Main Thread
- **Kesalahan:**
  ```cpp
  // FATAL CRASH: Memanggil V8 API di dalam std::thread
  std::thread([=]() {
      // Baris ini akan langsung melempar SIGSEGV atau abort()
      v8Callback.Call({ Napi::String::New(env, "Done") }); 
  }).detach();
  ```
- **Solusi:** Selalu gunakan `Napi::ThreadSafeFunction` untuk menyeberang dari native thread kembali ke V8 main loop.

### 10.2. Dangling Raw Pointer pada Zero-Copy Buffers
- **Kesalahan:** Addon mengambil pointer `buffer.Data()` dan memberikannya ke thread asynchronous native. Di sisi JS, variabel buffer keluar dari scope dan dibersihkan oleh GC V8 saat thread C++ masih melakukan read/write.
- **Solusi:** Buat `Napi::Reference<Napi::Buffer<uint8_t>>` pada context sebelum thread dimulai untuk menaikkan ref count di mata GC, dan panggil `ref.Unref()` atau hapus context hanya setelah background thread selesai bekerja.

### 10.3. Deadlock pada Penutupan Aplikasi (Process Teardown)
- **Kesalahan:** Node.js mencoba exit, tetapi masih ada `Napi::ThreadSafeFunction` atau worker thread native yang berstatus `joinable()` atau queue TSFN yang memegang active handle tanpa pemanggilan `Release()`.
- **Solusi:** Tangani event hook `napi_add_env_cleanup_hook` untuk memutus perulangan thread native dan memanggil `tsfn.Abort()` saat context Node.js dihancurkan.

### 10.4. Debugging & Diagnostic Tools

#### Mengaktifkan AddressSanitizer (ASan) pada `node-gyp`
Tambahkan compiler flags pada `binding.gyp`:
```python
"cflags": [ "-fsanitize=address", "-g" ],
"ldflags": [ "-fsanitize=address" ]
```
Jalankan Node.js dengan LD_PRELOAD:
```bash
LD_PRELOAD=$(clang -print-file-name=libclang_rt.asan-x86_64.so) node app.js
```
Jika terjadi *buffer over-read* atau *use-after-free*, ASan akan mencetak detail stack trace memory secara presisi ke console sebelum crash terjadi.

---

## 11. Best Practices (Production Checklist)

- [ ] **Gunakan Node-API Eksklusif:** Hindari NAN atau direct header V8 internal (`<v8.h>`). Pastikan mengompilasi dengan `NAPI_VERSION` yang ditargetkan (misal versi 8).
- [ ] **ABI Stability Guard:** Pastikan modul dapat berjalan lintas versi Node.js tanpa recompile selama minor/major ABI stabil.
- [ ] **Exception Handling:** Kompilasi dengan flag `-fno-exceptions` dan selalu cek `env.IsExceptionPending()` atau gunakan wrapper `Napi::Error::Fatal()` untuk situasi unrecoverable.
- [ ] **Prebuild Binaries Distribution:** Gunakan `prebuildify` untuk membundel compiled artifacts ke direktori `prebuilds/linux-x64`, `prebuilds/darwin-arm64`, dll., sehingga konsumen `npm install` tidak memerlukan compiler Python/C++.
- [ ] **Cleanup Hooks:** Selalu daftarkan `AddEnvironmentCleanupHook` untuk melepaskan resource native (koneksi native thread, file descriptors) saat instance worker_threads atau context di-terminate.
- [ ] **Hindari Worker Pool Starvation:** Jika komputasi berjalan > 5ms terus-menerus, gunakan dedicated `std::thread` daripada default `Napi::AsyncWorker` agar pool Libuv tidak macet.
- [ ] **Bound TSFN Queue Size:** Jangan gunakan queue size tak terbatas pada `ThreadSafeFunction` jika native thread memproduksi event lebih cepat daripada V8 main loop dapat mengonsumsinya (mencegah OOM).

---

## 12. Hands-on Practice

Implementasikan addon produksi lengkap dengan pipeline kompilasi mandiri.

### Struktur Direktori (`hands-on/m02/`)
```
hands-on/m02/
├── binding.gyp
├── package.json
├── src/
│   └── native_processor.cc
└── test/
    └── run.js
```

### File: `hands-on/m02/package.json`
```json
{
  "name": "enterprise-native-processor",
  "version": "1.0.0",
  "main": "test/run.js",
  "scripts": {
    "install": "node-gyp rebuild",
    "test": "node test/run.js"
  },
  "dependencies": {
    "node-addon-api": "^7.1.0"
  },
  "devDependencies": {
    "node-gyp": "^10.0.1"
  }
}
```

### File: `hands-on/m02/binding.gyp`
```python
{
  "targets": [
    {
      "target_name": "native_processor",
      "sources": [ "src/native_processor.cc" ],
      "include_dirs": [
        "<!@(node -p \"require('node-addon-api').include\")"
      ],
      "dependencies": [
        "<!(node -p \"require('node-addon-api').gyp\")"
      ],
      "cflags_cc": [ "-std=c++17", "-O3" ],
      "defines": [ "NAPI_CPP_EXCEPTIONS" ],
      "conditions": [
        ['OS=="mac"', {
          "xcode_settings": {
            "CLANG_CXX_LANGUAGE_STANDARD": "c++17",
            "MACOSX_DEPLOYMENT_TARGET": "10.15"
          }
        }]
      ]
    }
  ]
}
```

### File: `hands-on/m02/src/native_processor.cc`
```cpp
#include <napi.h>
#include <vector>
#include <numeric>

class TransformWorker : public Napi::AsyncWorker {
public:
    TransformWorker(Napi::Function& callback, Napi::Reference<Napi::Buffer<uint8_t>>& bufRef, size_t length, uint8_t scalar)
        : Napi::AsyncWorker(callback), bufRef_(bufRef), length_(length), scalar_(scalar), checksum_(0) {}

    ~TransformWorker() {
        bufRef_.Reset(); // Bebaskan pinning V8 buffer memory
    }

    // Dieksekusi pada Libuv background thread (Aman dari V8 Lock)
    void Execute() override {
        uint8_t* data = bufRef_.Value().Data();
        for (size_t i = 0; i < length_; ++i) {
            data[i] ^= scalar_; // XOR cipher transformasi
            checksum_ += data[i];
        }
    }

    // Dieksekusi kembali pada V8 Main Thread
    void OnOK() override {
        Napi::HandleScope scope(Env());
        Napi::Object result = Napi::Object::New(Env());
        result.Set("bytesProcessed", Napi::Number::New(Env(), length_));
        result.Set("checksum", Napi::Number::New(Env(), checksum_));
        Callback().Call({ Env().Null(), result });
    }

    void OnError(const Napi::Error& e) override {
        Napi::HandleScope scope(Env());
        Callback().Call({ e.Value(), Env().Null() });
    }

private:
    Napi::Reference<Napi::Buffer<uint8_t>> bufRef_;
    size_t length_;
    uint8_t scalar_;
    uint64_t checksum_;
};

Napi::Value ProcessBufferAsync(const Napi::CallbackInfo& info) {
    Napi::Env env = info.Env();

    if (info.Length() < 3 || !info[0].IsBuffer() || !info[1].IsNumber() || !info[2].IsFunction()) {
        Napi::TypeError::New(env, "Argumen dibutuhkan: Buffer, Scalar (Number), Callback").ThrowAsJavaScriptException();
        return env.Null();
    }

    Napi::Buffer<uint8_t> buffer = info[0].As<Napi::Buffer<uint8_t>>();
    uint8_t scalar = static_cast<uint8_t>(info[1].As<Napi::Number>().Uint32Value());
    Napi::Function callback = info[2].As<Napi::Function>();

    // Buat Reference untuk mencegah Buffer terkena Garbage Collection saat worker bekerja
    Napi::Reference<Napi::Buffer<uint8_t>> bufRef = Napi::Reference<Napi::Buffer<uint8_t>>::New(buffer, 1);

    TransformWorker* worker = new TransformWorker(callback, bufRef, buffer.Length(), scalar);
    worker->Queue();

    return env.Undefined();
}

Napi::Object Init(Napi::Env env, Napi::Object exports) {
    exports.Set("processBufferAsync", Napi::Function::New(env, ProcessBufferAsync));
    return exports;
}

NODE_API_MODULE(native_processor, Init)
```

### File: `hands-on/m02/test/run.js`
```javascript
const path = require('path');
const addon = require('../build/Release/native_processor');

console.log("[Test] Mengalokasikan 10MB Buffer...");
const size = 10 * 1024 * 1024;
const buffer = Buffer.alloc(size, 0x55); // Nilai awal: 01010101 biner
const scalar = 0xAA;                   // Operator XOR: 10101010 biner

console.log(`[Test] Byte awal (index 0): 0x${buffer[0].toString(16)}`);

addon.processBufferAsync(buffer, scalar, (err, result) => {
    if (err) {
        console.error("[Test] Gagal:", err);
        process.exit(1);
    }
    console.log("[Test] Callback dieksekusi dengan sukses!");
    console.log("[Test] Result:", result);
    console.log(`[Test] Byte hasil transformasi (index 0): 0x${buffer[0].toString(16)}`);

    if (buffer[0] === (0x55 ^ scalar)) {
        console.log(">> VERIFIKASI BERHASIL: Transformasi Zero-Copy Terbukti Sinkron! <<");
    } else {
        console.error(">> VERIFIKASI GAGAL! <<");
        process.exit(1);
    }
});
```

---

## 13. Exercise

### Level Easy
Ubah `native_processor.cc` pada sesi hands-on agar fungsi menerima parameter validasi batas (boundary limit): jika buffer yang diberikan memiliki ukuran lebih dari 50MB, lempar exception JavaScript `RangeError` secara synchronous sebelum task dikirimkan ke worker pool.

### Level Medium
Bangun native method `batchHashSHA256(Buffer[] buffers): Promise<Buffer[]>` yang menerima sebuah Array of Buffers dari JavaScript, mendistribusikan komputasi hashing SHA-256 tiap buffer tersebut secara paralel memanfaatkan `uv_queue_work` atau `std::async`, dan me-resolve hasilnya berupa Array buffer hash secara utuh.

### Level Hard
Implementasikan native Ring-Buffer IPC:
Buat C++ Addon yang mengalokasikan circular memory buffer tetap (misal 64MB) menggunakan POSIX shared memory (`shm_open`, `mmap`). Implementasikan reader dan writer menggunakan C++ `std::atomic<size_t>` untuk head/tail index. Buat stream Node.js yang membaca data secara continuous dari ring-buffer tersebut ke V8 main thread menggunakan `Napi::ThreadSafeFunction` dengan alokasi zero copy buffer.

---

## 14. Challenge (Enterprise Scenario - Tanpa Solusi Instan)

### Arsitektur Zero-Downtime Native Machine Learning Scoring Engine
Sebuah platform fraud detection finansial membutuhkan integrasi model C++ scoring biner berukuran 1.2 GB yang beroperasi di dalam Node.js API Gateway.

**Spesifikasi Persyaratan:**
1. **Dynamic Model Reloading:** Addon harus mampu memuat ulang file model biner baru dari disk ke memori ketika menerima sinyal OS `SIGHUP` atau pemanggilan method JS `.reloadModel(path)` tanpa menghentikan Node.js event loop dan tanpa me-reject *in-flight requests* yang sedang berjalan pada model versi lama.
2. **Double-Buffering & Resource Reclamation:** Model lama harus tetap berada di memori hingga request terakhir yang menggunakannya selesai, lalu dibersihkan secara atomik (*safe memory reclamation* via pointer counting / atomic smart pointers).
3. **Hard Latency SLA:** Response scoring harus kembali dalam waktu kurang dari 2.5 milidetik pada persentil p99.
4. **Resiliency:** Jika data payload input mengalami malformasi atau merusak algoritma internal inference C++, addon tidak boleh menghasilkan `SIGSEGV` crash. Addon harus menangkap OS hardware exceptions (seperti SEH pada Windows atau signal bus error pada Linux) dan mengubahnya menjadi penolakan Promise JavaScript standar (`Promise.reject()`).

---

## 15. Quiz Evaluasi Pemahaman

### 15.1. Pertanyaan Basic

1. **Mengapa Node-API (N-API) lebih dianjurkan daripada implementasi native langsung menggunakan header V8 engine (`<v8.h>`)?**
   - A. Karena Node-API berjalan lebih cepat daripada kode assembly V8 langsung.
   - B. Karena Node-API mempertahankan Application Binary Interface (ABI) yang stabil lintas versi mayor Node.js, menghilangkan keharusan mengompilasi ulang binary tiap kali versi Node.js diperbarui.
   - C. Karena Node-API secara otomatis mengubah kode C++ menjadi bytecode WebAssembly.
   - D. Karena Node-API meniadakan keberadaan C++ pointer.
   *Kunci: B* — Node-API menyediakan kestabilan ABI, mengisolasi native module dari perubahan internal V8 engine antar-versi Node.js.

2. **Apa fungsi utama dari `Napi::HandleScope` di dalam native function?**
   - A. Mencegah V8 Main Thread berpindah thread CPU.
   - B. Mengontrol masa hidup handle referensi lokal V8 agar memori objek JS temporer dapat dibersihkan oleh Garbage Collector saat scope keluar.
   - C. Mengonversi buffer memori C++ menjadi string JSON.
   - D. Mengunci mutex sistem operasi.
   *Kunci: B* — `HandleScope` mengelola alokasi handle lokal V8 dalam stack frame native sehingga GC dapat membersihkannya saat keluar dari scope.

3. **Apa yang terjadi secara langsung jika thread OS native (`std::thread`) memanggil `Napi::Value::ToString()`?**
   - A. Method berhasil dieksekusi normal dan menghasilkan std::string.
   - B. Node.js otomatis menunda eksekusi native thread tersebut hingga giliran event loop tiba.
   - C. Terjadi *Undefined Behavior* yang biasanya langsung memicu *Segmentation Fault* (`SIGSEGV`) atau *abort* karena V8 context disentuh di luar Main Thread.
   - D. Nilai konversi otomatis dialokasikan ke Libuv worker pool.
   *Kunci: C* — Engine V8 tidak bersifat thread-safe. Mengakses tipe V8 di luar main thread memicu crash fatal.

4. **Bagaimana cara membaca data biner dari Node.js `Buffer` secara zero-copy di Node-API?**
   - A. Memanggil `buffer.ToString()` lalu menyalinnya ke `std::string`.
   - B. Menggunakan fungsi `buffer.Data()` untuk mengakses raw pointer memory address secara langsung.
   - C. Mengirimkan buffer melalui `JSON.stringify()`.
   - D. Menduplikasi memori buffer menggunakan `memcpy` ke heap OS.
   *Kunci: B* — Method `Data()` mengembalikan pointer `uint8_t*` langsung ke memori yang dialokasikan oleh Node.js tanpa copy.

5. **Apa peranan file `binding.gyp` dalam siklus pengembangan C++ Addon?**
   - A. Sebagai unit test runner untuk native code.
   - B. File konfigurasi deklaratif berbasis Python dictionary yang digunakan oleh `node-gyp` untuk men-generate build file (Makefile, Ninja, Visual Studio Project).
   - C. Engine compiler pengganti Clang dan GCC.
   - D. Bundle packager yang mendistribusikan binary ke npm registry.
   *Kunci: B* — `binding.gyp` adalah spesifikasi build konfigurasi yang mendefinisikan target binary, source files, dan compiler flags.

---

### 15.2. Pertanyaan Intermediate

6. **Kapan seorang Software Architect harus memilih `Napi::ThreadSafeFunction` dibandingkan `Napi::AsyncWorker`?**
   - A. Ketika tugas komputasi native hanya berjalan satu kali dan langsung selesai mengembalikan Promise tunggal.
   - B. Ketika tugas native dieksekusi di long-running background thread independen dan perlu mengirimkan multiple event atau stream progress secara berkala ke JavaScript.
   - C. Ketika modul tidak membutuhkan interaksi dengan thread C++ sama sekali.
   - D. Ketika addon ingin menghindari kompilasi native C++.
   *Kunci: B* — `ThreadSafeFunction` didesain untuk streaming event dari background native thread yang berjalan kontinu menuju JavaScript.

7. **Mengapa alokasi memori via `Napi::Reference<T>::New(jsObject, 1)` penting saat mengeksekusi asynchronous native task?**
   - A. Untuk mengompres ukuran objek di dalam V8 Heap.
   - B. Untuk menaikkan reference count objek tersebut menjadi 1 (strong reference), mencegah Garbage Collector V8 menghancurkan objek tersebut saat proses native di background masih berjalan.
   - C. Agar objek tersebut dapat diakses secara concurrent oleh 10 CPU core tanpa locks.
   - D. Memaksa objek JS berubah menjadi C++ Struct.
   *Kunci: B* — Reference count > 0 menandakan GC V8 tidak boleh menghapus objek tersebut dari memori.

8. **Apa dampak performa buruk jika addon C++ Anda terlalu sering memanggil `napi_create_string_utf8` di dalam loop komputasi throughput tinggi?**
   - A. Terjadi kebocoran memori pada level kernel OS.
   - B. Memicu GC pressure yang sangat tinggi di V8 Young Generation, menyebabkan tingginya frekuensi Scavenge GC yang menghentikan sementara Main Thread.
   - C. Libuv thread pool akan hang secara permanen.
   - D. Addon otomatis ditolak oleh compiler C++.
   *Kunci: B* — Setiap alokasi V8 String baru menghasilkan objek di V8 Heap, yang menaikkan frekuensi garbage collection.

9. **Tool manakah yang paling efektif digunakan untuk mendeteksi silent memory corruption (seperti Heap Buffer Overflow) pada Native Addon saat runtime development?**
   - A. ESLint.
   - B. Chrome DevTools Network Tab.
   - C. AddressSanitizer (ASan) yang diaktifkan melalui flag `-fsanitize=address`.
   - D. PM2 Cluster Manager.
   *Kunci: C* — AddressSanitizer adalah compiler instrumentation tool standar industri untuk mendeteksi memory corruption pada aplikasi C/C++.

10. **Bagaimana cara mencegah `prebuildify` addon gagal berjalan pada distribusi Linux berbasis musl (seperti Alpine Linux) jika dikompilasi di Ubuntu?**
    - A. Membuka file binary dan mengedit string glibc secara manual.
    - B. Mengompilasi binary target terpisah di dalam container environment berbasis Alpine/musl dan memisahkannya di path target `prebuilds/linux-x64-musl`.
    - C. Mengganti semua tipe data C++ menjadi JavaScript numbers.
    - D. Menambahkan flag `static-everything` pada konfigurasi npm.
    *Kunci: B* — Perbedaan libc (glibc vs musl) mewajibkan kompilasi terisolasi untuk tiap C-runtime target.

---

### 15.3. Skenario Kasus Produksi

11. **Skenario 1:** Addon transcoding video memicu `SIGSEGV (Segmentation Fault)` secara acak hanya ketika beban trafik server mencapai lebih dari 5.000 req/detik. Pada saat beban rendah (<500 req/detik), pengujian unit test dan QA lulus 100%. Apa hipotesis arsitektural yang paling mungkin menjelaskan fenomena ini?
    - A. File video corrupt secara acak dari sisi user.
    - B. Terdapat *Race Condition* atau *Dangling Pointer* di mana buffer memori V8 yang diakses oleh thread worker C++ telah dibebaskan oleh V8 GC di bawah memory pressure tinggi, karena addon tidak menahan `Napi::Reference` dengan benar.
    - C. Versi Node.js di server berubah secara otomatis saat beban tinggi.
    - D. JavaScript engine V8 mematikan fungsi native jika CPU usage menyentuh 90%.
    *Kunci: B* — Di bawah memory pressure tinggi, GC V8 berjalan lebih agresif. Jika memory buffer tidak di-pin dengan `Napi::Reference`, V8 akan membersihkan memory buffer tersebut, meninggalkan dangling pointer pada thread C++.

12. **Skenario 2:** Sebuah microservice Node.js menggunakan C++ native addon untuk memverifikasi kriptografi signature. Setelah berjalan 48 jam di cluster Kubernetes, Pod tersebut terkena *OOMKilled (Out Of Memory)* dari sistem Linux, meskipun metrik V8 Heap (`process.memoryUsage().heapUsed`) hanya mencatat konsumsi sebesar 120MB dari limit Pod 2GB. Di manakah kebocoran memori terjadi?
    - A. Memori bocor di dalam V8 New Space Heap.
    - B. Terjadi kebocoran memori native di Native Heap C++ (memori dialokasikan melalui `malloc` atau `new` oleh library native tetapi tidak pernah dibebaskan via `free` atau `delete`), yang tidak terlihat di V8 Heap metrics.
    - C. Kubernetes salah menghitung penggunaan memori Node.js.
    - D. V8 Engine secara otomatis memesan sisa memori host untuk swap.
    *Kunci: B* — `heapUsed` hanya mencatat memori yang dikelola V8 Garbage Collector. Alokasi native C/C++ berada di luar V8 Heap dan hanya terdeteksi via Resident Set Size (`rss`).

13. **Skenario 3:** Tim Anda mengimplementasikan native worker menggunakan `Napi::AsyncWorker` untuk mengeksekusi operasi komputasi yang memakan waktu 400ms per panggilan. Setelah merilis fitur ini, latensi endpoint lain di aplikasi yang melakukan query file via `fs.readFile` dan resolusi DNS `dns.lookup` melonjak drastis hingga puluhan detik. Mengapa ini terjadi dan apa solusi arsitekturalnya?
    - A. V8 Main Thread kehabisan memori RAM.
    - B. Komputasi `Napi::AsyncWorker` tersebut membanjiri dan memonopoli 4 thread default Libuv Worker Pool (`UV_THREADPOOL_SIZE`), menyebabkan tugas internal Node.js lainnya (I/O file dan DNS) mengalami antrean panjang (*thread pool starvation*). Solusinya adalah menaikkan `UV_THREADPOOL_SIZE` atau memindahkan komputasi berat ke `std::thread` terpisah.
    - C. Modul native merusak event loop timers.
    - D. File descriptor sistem operasi telah habis.
    *Kunci: B* — Libuv worker pool digunakan bersama oleh native async workers dan internal API seperti `fs` dan `dns`. CPU-bound long-running task memicu starvation pada pool tersebut.

---

## 16. Summary

Implementasi Native Addons di Node.js menggunakan **Node-API (node-addon-api)** adalah mekanisme esensial untuk mencapai performa bare-metal, komputasi berlatensi mikrodetik, dan integrasi library C/C++ pihak ketiga ke dalam ekosistem JavaScript. 

Keberhasilan implementasi tingkat enterprise bertumpu pada disiplin ketat terhadap batas arsitektur (*architectural boundaries*):
1. **Disiplin Heap & Zero-Copy:** Hindari penyalinan payload biner berukuran besar dengan memanfaatkan raw memory pointer V8 Buffers (`Data()`), sembari menjaga integritas siklus GC V8 melalui penguncian referensi (`Napi::Reference`).
2. **Disiplin Multithreading:** Jangan pernah memanggil API V8 di luar main thread. Gunakan **Libuv Worker Pool** untuk operasi pendek, atau **Dedicated OS Threads** yang dikombinasikan dengan **`Napi::ThreadSafeFunction`** untuk pemrosesan paralel throughput tinggi yang streaming.
3. **Stabilitas & Operasional:** Gunakan tool diagnosa tingkat rendah seperti **AddressSanitizer** untuk mematikan potensi `SIGSEGV` sedini mungkin, dan bangun pipeline CI/CD berbasis **`prebuildify`** untuk mendistribusikan binary siap pakai lintas platform tanpa memberatkan host target produksi.