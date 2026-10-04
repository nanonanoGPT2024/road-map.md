# Modul 08.01: Platform Interoperability — Channels & FFI

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** Frontend and Mobile Engineering (`03-Frontend-and-Mobile`)
*   **Track:** Flutter Enterprise Architecture & Systems Engineering
*   **Bab:** 08 — Advanced Engine Mechanics, Native Interoperability & Low-Level Flutter
*   **Modul:** 01 — Platform Interoperability: Channels & FFI
*   **Prasyarat Pengetahuan:**
    *   Memahami Flutter Engine lifecycle, event loop, microtask queue, dan Dart Isolate concurrency model.
    *   Kemahiran intermediate dalam Dart (termasuk tipe data asinkron dan memory pointers), Kotlin/Swift modern, serta dasar-dasar C/C++ memory management (heap allocation, pointers, struct layout, stack lifecycle).
    *   Pengalaman menggunakan Android NDK (JNI) dan Swift/Objective-C Clang tooling.
*   **Estimasi Waktu Selesai:** 4 Jam 30 Menit (Teori Komprehensif, Bedah Kode Kernel/Engine, dan Praktikum Implementasi Sistem)

---

## SEKSI 02 — LEARNING OBJECTIVES

Pada akhir modul ini, peserta didik memiliki kemampuan terukur untuk:
1.  **Mendekomposisi Mekanisme Encoding/Decoding Platform Channels:** Memetakan dan merekonstruksi bagaimana data binary dimutasi antara Dart VM dan Platform Host via `StandardMessageCodec` dan binary messaging boundary.
2.  **Mengoptimalkan Komunikasi Native Berlatensi Rendah:** Mengeliminasi thread hopping overhead dan JSON serialization cost dengan memilih arsitektur yang tepat antara `MethodChannel`, `BasicMessageChannel`, dan Direct Memory Access via `dart:ffi`.
3.  **Mengimplementasikan High-Performance C/C++ Interop (dart:ffi):** Merancang integrasi zero-copy data processing menggunakan dynamic libraries (`.so`, `.dylib`), alokasi memori manual (`calloc`/`malloc`), dan struct mapping yang aman dari memory leak.
4.  **Mencegah Memory Leaks & Memory Corruption Lintas Boundary:** Menemukan dan memitigasi pointer dangling, boundary memory leaks, serta data misalignment pada arsitektur hybrid ARM64/x86_64.
5.  **Merancang Thread-Safe Native Bridge Berstandar Enterprise:** Membangun modul native yang mengeksekusi operasi komputasi berat di luar UI thread host (Android Main Thread / iOS Main RunLoop) tanpa memblokir rendering pipeline 120 FPS Flutter.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Mengembangkan aplikasi Flutter pada skala enterprise menuntut Anda berhenti memandang Flutter sebagai sekadar "framework UI cross-platform". Mental model yang benar adalah: **Flutter adalah canvas rendering berkinerja tinggi berbasis C++ engine, sedangkan Host Platform (Android/iOS) adalah sistem operasi host yang mengontrol hardware lifecycle.**

```
+---------------------------------------------------------------------------------+
|                                 MENTAL MODEL                                    |
+---------------------------------------------------------------------------------+
|  PARADIGMA PLATFORM CHANNELS                 PARADIGMA DART:FFI                 |
|  "Sistem Pengiriman Paket Antar-Kota"        "Pemberian Alamat Memori Bersama"  |
|                                                                                 |
|  [ Dart VM ]                                 [ Dart VM ]      [ Native C/C++ ]  |
|      |                                             \              /             |
|   Serilisasi (StandardMessageCodec)                 \            /              |
|      v                                          Akses Pointers Langsung         |
|  [ IPC Byte Packet ]                                (Shared Memory Space)       |
|      v                                                                          |
|   Deserialisasi                                 Keuntungan:                     |
|      v                                          - Zero-Copy Overhead            |
|  [ Host Platform (Android/iOS) ]                - Sinkron, Sub-mikrodetik Latensi|
|                                                 - Cocok untuk: Kriptografi, ML, |
|  Konsekuensi: Serialization + Thread Hopping                  Pemrosesan Citra  |
+---------------------------------------------------------------------------------+
```

### Aturan Emas Arsitek Platform:
1.  **Gunakan Platform Channels jika:** Anda memerlukan interoperabilitas API yang terikat ketat dengan framework UI OS (misal: HealthKit, Android BiometricPrompt, StoreKit, Sensor Listeners, Window Management).
2.  **Gunakan `dart:ffi` jika:** Anda berhadapan dengan komputasi murni, manipulasi byte buffer besar, audio/video streaming, enkripsi/dekripsi, inferensi machine learning, atau basis kode C/C++/Rust yang sudah ada tanpa ketergantungan pada Android context / iOS UIWindow.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di balik pemanggilan sebuah `MethodChannel`, paket melintasi sejumlah layer abstraksi. Diagram berikut mengilustrasikan jalur lengkap data dari Dart UI layer hingga ke Native Platform, serta perbandingannya dengan direct execution via `dart:ffi`.

```
========================================================================================================================
                                      FLUTTER NATIVE INTEROPERABILITY PIPELINE
========================================================================================================================

   [ DART LAYER ]
         |
         +-----> (A) Platform Channel Path: MethodChannel.invokeMethod('processData', payload)
         |            |
         |            v
         |       StandardMethodCodec / StandardMessageCodec
         |       (Serialisasi Objek Dart -> Binary Data: ByteBuffer)
         |            |
         |            v
         |       BinaryMessages.send('channel_name', byteBuffer)
         |            |
  ~~~~~~~~~~~~~~~~~~~~|~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
   [ DART VM / C++ ENGINE BOUNDARY ]
  ~~~~~~~~~~~~~~~~~~~~|~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
         |            v
         |       flutter::PlatformView::SendPlatformMessage
         |            |
         |            v
         |       TaskRunner Switch: TaskRunners::GetPlatformTaskRunner()
         |       (Thread Hop: Engine Raster/UI Thread ---> Platform Main Thread)
         |            |
  ~~~~~~~~~~~~~~~~~~~~|~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
   [ HOST PLATFORM OS ]
  ~~~~~~~~~~~~~~~~~~~~|~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
         |            +--------------------------------------------+
         |            |                                            |
         |            v (Android)                                  v (iOS)
         |       JNI Envoy Call                               Native Message Handler
         |            |                                            |
         |       FlutterJNI.handlePlatformMessage()           FlutterEngine.sendPlatformMessage()
         |            |                                            |
         |       MethodChannel.MethodCallHandler              FlutterMethodCallHandler
         |            |                                            |
         |       Platform Thread Menjalankan Operasi Native   Platform Thread Menjalankan Operasi Native
         |
         |
         +-----> (B) Direct Memory FFI Path: DynamicLibrary.lookupFunction<NativeFn, DartFn>('processRawData')
                      |
  ~~~~~~~~~~~~~~~~~~~~|~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
   [ DIRECT DART VM C-CALL (NO ENGINE INTERMEDIARY, ZERO SERIALIZATION) ]
  ~~~~~~~~~~~~~~~~~~~~|~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                      |
                      v
                 Direct Pointer Address Resolution (Memory Address: 0x7FFF5BE0)
                      |
                      v
                 Native C/C++/Rust Execution (.so / .dylib)
                 (Berjalan pada Isolate Thread atau C Background Thread)
                      |
                      v
                 Return Struct Value / Direct Memory Mutation
========================================================================================================================
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Dekonstruksi Platform Channels: `StandardMessageCodec`

`MethodChannel` tidak mengirimkan objek Dart secara langsung. Ia bergantung pada `StandardMessageCodec` yang mengonversi tipe primitif dan koleksi ke dalam representasi biner terstandarisasi.

Struktur biner dari `StandardMessageCodec` selalu diawali dengan 1 byte identifikasi tipe (Type Tag byte):
*   `0x00`: Null
*   `0x01`: True
*   `0x02`: False
*   `0x03`: 32-bit Signed Integer (Little-endian)
*   `0x04`: 64-bit Signed Integer (Little-endian)
*   `0x07`: String (Panjang string yang di-encode via ULEB128, diikuti raw payload UTF-8)
*   `0x08`: List/Array (Jumlah elemen [ULEB128], diikuti serialisasi elemen berurutan)
*   `0x09`: Map/Dictionary (Jumlah entri [ULEB128], diikuti pasangan Key-Value berurutan)

**Biaya Komputasi Tersembunyi (Hidden Computational Cost):**
1.  **Memory Allocation:** Setiap enkapsulasi data menghasilkan alokasi buffer baru di Dart heap.
2.  **Thread Hopping Overhead:** Mengirimkan pesan melalui BinaryMessenger memaksa pesan di-enqueue ke Platform Task Runner. Jika Platform Thread (UI thread Android/iOS) sedang sibuk merender frame atau memproses UI native, respon Dart akan mengalami *frame dropping* (jank) meskipun Dart Isolate dalam status idle.

### 2. Dekonstruksi `dart:ffi`: ABI (Application Binary Interface) & Pointers

`dart:ffi` mengeliminasi seluruh pipeline serialization, buffering, dan TaskRunner switching. Dart VM langsung memanggil machine code C/C++ menggunakan Foreign Function Interface yang mematuhi System V AMD64 ABI (Linux/macOS) atau ARM64 AAPCS standard ABI (Android/iOS).

*   **Pointers (`Pointer<T>`):** Merepresentasikan direct 64-bit (atau 32-bit pada legacy chip) memory address dari native heap (bukan Dart GC-managed heap).
*   **Memory Allocators (`calloc` / `malloc`):** Mengalokasikan raw memory di luar jangkauan Dart Garbage Collector. Memori ini **wajib** dideallokasikan secara manual (`calloc.free(pointer)`). Dart GC **tidak akan pernah** membersihkan memori yang dialokasikan via allocator FFI.
*   **Native Finalizers:** Mekanisme keamanan memory Dart modern (`NativeFinalizer`) yang mengikat siklus hidup objek Dart pada raw pointer native, memastikan fungsi C-free terpanggil ketika objek Dart diklaim oleh GC.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Perbedaan Arsitektural: Channel Flavors

Flutter menyediakan 3 rasa (flavors) utama pada platform channels:

| Tipe Channel | Tipe Operasi | Pola Penggunaan Ideal | Bottleneck / Keterbatasan |
| :--- | :--- | :--- | :--- |
| **`BasicMessageChannel<T>`** | Asynchronous Bi-directional Request-Response atau Fire-and-forget | Mengirim raw bytes, JSON strings, atau stream byte murni tanpa RPC semantics metadata | Memerlukan pemilihan Codec yang manual (`BinaryCodec`, `StringCodec`, `JSONMessageCodec`) |
| **`MethodChannel`** | RPC Async (`invokeMethod`) | Menjalankan fungsi spesifik di platform host yang mengembalikan satu nilai respon | Overhead parsing method name string dan argument map boxing/unboxing |
| **`EventChannel`** | Asynchronous Uni-directional Stream (Native $\to$ Dart) | Menerima event hardware berlanjut (Sensor Gyroscope, Geolocation updates, Bluetooth signals) | Tidak mendukung backpressure native secara langsung jika Dart thread lambat mengonsumsi |

### Mekanika Eksekusi `dart:ffi`: Synchronous vs Asynchronous

Secara default, panggilan fungsi `dart:ffi` bersifat **synchronous** dan dieksekusi secara **in-place**.
Jika Anda memanggil fungsi C++ yang membutuhkan waktu 500ms di root isolate, **UI Flutter Anda akan freeze total selama 500ms**.

Untuk menangani komputasi berat dengan FFI tanpa memblokir UI thread:
1.  **Isolate Spawning:** Spawn Dart `Isolate.spawn()` dan lakukan pemanggilan FFI synchronous di dalam Isolate baru tersebut.
2.  **Native Async Ports (`Dart_PostCObject`):** Fungsi C++ melepaskan thread baru via C++ `std::thread`, dan mengirimkan hasil kalkulasi langsung ke Dart VM message loop menggunakan port native C Dart API (`Dart_PostCObject_DL`).

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah perbandingan implementasi fundamental: Menghitung Hash Payload menggunakan **Standard MethodChannel** vs **Zero-Copy dart:ffi**.

### Bagian A: Pendekatan MethodChannel (Konvensional)

#### 1. Sisi Dart
```dart
import 'package:flutter/services.dart';

class NativeHasherChannel {
  static const MethodChannel _channel = MethodChannel('com.enterprise.security/hasher');

  static Future<String> hashPayload(String payload) async {
    try {
      final String result = await _channel.invokeMethod('hashPayload', {
        'input': payload,
      });
      return result;
    } on PlatformException catch (e) {
      throw Exception('Gagal melakukan hashing di native: ${e.message}');
    }
  }
}
```

#### 2. Sisi Host Android (Kotlin)
```kotlin
package com.enterprise.security

import io.flutter.embedding.engine.plugins.FlutterPlugin
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel
import java.security.MessageDigest

class SecurityPlugin : FlutterPlugin, MethodChannel.MethodCallHandler {
    private lateinit var channel: MethodChannel

    override fun onAttachedToEngine(binding: FlutterPlugin.FlutterPluginBinding) {
        channel = MethodChannel(binding.binaryMessenger, "com.enterprise.security/hasher")
        channel.setMethodCallHandler(this)
    }

    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        if (call.method == "hashPayload") {
            val input = call.argument<String>("input")
            if (input == null) {
                result.error("INVALID_ARGUMENT", "Payload input bernilai null", null)
                return
            }
            
            try {
                val digest = MessageDigest.getInstance("SHA-256")
                val hashBytes = digest.digest(input.toByteArray(Charsets.UTF_8))
                val hexString = hashBytes.joinToString("") { "%02x".format(it) }
                result.success(hexString)
            } catch (e: Exception) {
                result.error("HASH_FAILURE", e.localizedMessage, null)
            }
        } else {
            result.notImplemented()
        }
    }

    override fun onDetachedFromEngine(binding: FlutterPlugin.FlutterPluginBinding) {
        channel.setMethodCallHandler(null)
    }
}
```

---

### Bagian B: Pendekatan `dart:ffi` (Direct Memory Execution)

#### 1. Sisi C Library (`native_hasher.c`)
```c
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

// Definisi Export ABI untuk cross-platform compilation
#if defined(_WIN32)
#define FFI_EXPORT __declspec(dllexport)
#else
#define FFI_EXPORT __attribute__((visibility("default"))) __attribute__((used))
#endif

// Implementasi hashing sederhana 32-bit FNV-1a (untuk demonstrasi interop memory murni)
FFI_EXPORT uint32_t fast_fnv1a_hash(const uint8_t* data, size_t length) {
    uint32_t hash = 2166136261u;
    for (size_t i = 0; i < length; ++i) {
        hash ^= data[i];
        hash *= 16777619u;
    }
    return hash;
}
```

#### 2. Sisi Dart FFI Binding
```dart
import 'dart:ffi' as ffi;
import 'dart:io';
import 'package:ffi/ffi.dart';

// Type definitions untuk C Signature dan Dart Signature
typedef NativeHashFunc = ffi.Uint32 Function(ffi.Pointer<ffi.Uint8> data, ffi.Size length);
typedef DartHashFunc = int Function(ffi.Pointer<ffi.Uint8> data, int length);

class NativeHasherFFI {
  late final ffi.DynamicLibrary _lib;
  late final DartHashFunc _fastFnv1aHash;

  NativeHasherFFI() {
    _lib = Platform.isAndroid
        ? ffi.DynamicLibrary.open('libnative_hasher.so')
        : (Platform.isIOS || Platform.isMacOS)
            ? ffi.DynamicLibrary.process()
            : ffi.DynamicLibrary.open('native_hasher.dll');

    _fastFnv1aHash = _lib
        .lookup<ffi.NativeFunction<NativeHashFunc>>('fast_fnv1a_hash')
        .asFunction<DartHashFunc>();
  }

  int computeHash(List<int> rawBytes) {
    final int length = rawBytes.length;
    // Mengalokasikan memory native secara manual di Heap OS
    final ffi.Pointer<ffi.Uint8> nativeBuffer = calloc<ffi.Uint8>(length);

    try {
      // Mengisi memory native langsung dari TypedData/Byte Dart
      final pointerList = nativeBuffer.asTypedList(length);
      pointerList.setAll(0, rawBytes);

      // Eksekusi direct function call secara sinkron
      final int hash = _fastFnv1aHash(nativeBuffer, length);
      return hash;
    } finally {
      // Wajib membebaskan pointer untuk mencegah memory leak permanen
      calloc.free(nativeBuffer);
    }
  }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis FFI Binding (Dart & C)

```c
// native_hasher.c
FFI_EXPORT uint32_t fast_fnv1a_hash(const uint8_t* data, size_t length) {
```
*   `FFI_EXPORT`: Macro preprocessor yang memastikan symbol function diekspor ke Dynamic Symbol Table `.dynsym`. Tanpa atribut visibilitas ini, compiler GCC/Clang akan membuang (strip) simbol saat optimasi rilis (`-O3`), sehingga Dart akan melempar runtime error `ArgumentError: Failed to lookup symbol`.
*   `const uint8_t* data`: Menerima raw address memory pointer langsung tanpa metadata wrapper atau payload length descriptor bawaan bahasa runtime tinggi.

```dart
// native_hasher.dart
final ffi.Pointer<ffi.Uint8> nativeBuffer = calloc<ffi.Uint8>(length);
```
*   `calloc<ffi.Uint8>(length)`: Memanggil underlying C system allocator (`malloc` + `memset(0)`). Ini mengalokasikan array unmanaged memori sebesar $length \times 1 \text{ byte}$ di native process memory. Objek ini **berada di luar kendali GC Dart**.

```dart
final pointerList = nativeBuffer.asTypedList(length);
pointerList.setAll(0, rawBytes);
```
*   `nativeBuffer.asTypedList(length)`: Mengembalikan wrapper `Uint8List` yang merepresentasikan buffer native tanpa menyalin memori (*zero-copy view*).
*   `pointerList.setAll(0, rawBytes)`: Memindahkan bytes ke memory space native.

```dart
calloc.free(nativeBuffer);
```
*   `calloc.free(nativeBuffer)`: Blok `finally` memastikan instruksi dealokasi ini wajib dijalankan meskipun `_fastFnv1aHash` mengalami segmentation fault atau Dart melempar exception, mencegah Native Memory Leakage.

---

## SEKSI 09 — STUDI KASUS NYATA (ENTERPRISE)

### Arsitektur Sistem Streaming & Dekripsi Telemetri Medis Real-time

**Konteks Masalah:**
Sebuah platform software medis IoT menerima aliran paket telemetri elektrokardiogram (ECG/EKG) berkecepatan 4.000 sampel per detik via antarmuka Bluetooth Low Energy (BLE) yang terenkripsi AES-256-GCM berpemilik.

**Kegagalan Arsitektur Awal (Platform Channels):**
Implementasi awal menggunakan `MethodChannel` untuk mengirim byte array mentah dari native iOS/Android BLE stack ke Dart:
*   Serialisasi 4.000 paket/detik menyebabkan CPU throttling dan memory churn parah di Android GC dan iOS Garbage/ARC Collector.
*   Flutter UI thread mengalami micro-stutters kronis (jatuh ke 34 FPS) karena Platform TaskRunner tertekan oleh ribuan `StandardMessageCodec.decodeMessage` operations per detik.

**Solusi Rekayasa:**
1.  **Platform Channel (Control Plane):** Hanya digunakan untuk operasi metadata ringan: `connect()`, `disconnect()`, dan validasi security lifecycle.
2.  **Shared Memory + `dart:ffi` Worker Isolate (Data Plane):** Aliran raw byte langsung dialirkan ke background C++ circular buffer. Worker Isolate Flutter membaca pointer tersebut melalui `dart:ffi`, melakukan dekripsi dan transformasi FFT (Fast Fourier Transform) langsung di C++, lalu memproyeksikan hasil render matriks ke UI via `TransferableTypedData`.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah arsitektur lengkap C++ Core, Android Host Connector, dan Dart FFI Isolate Worker untuk pipeline pemrosesan data real-time:

### 1. File C++ High-Performance Data Processing (`telemetry_core.cpp`)

```cpp
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#define EXPORT extern "C" __declspec(dllexport)
#else
#define EXPORT extern "C" __attribute__((visibility("default"))) __attribute__((used))
#endif

// Representasi struct telemetry yang dipetakan secara biner ke struct Dart FFI
#pragma pack(push, 1) // Memaksa byte alignment tanpa padding compiler yang tak terduga
typedef struct {
    uint64_t timestamp_ms;
    float ecg_channel_1;
    float ecg_channel_2;
    uint32_t heart_rate;
} TelemetryPacket;
#pragma pack(pop)

EXPORT int32_t process_telemetry_frame(
    const uint8_t* raw_encrypted_stream,
    int32_t stream_length,
    TelemetryPacket* output_packet
) {
    if (raw_encrypted_stream == nullptr || output_packet == nullptr) {
        return -1; // Pointer tidak valid
    }

    if (stream_length < 16) {
        return -2; // Ukuran paket rusak (corrupt payload)
    }

    // Simulasi dekripsi matematis cepat dan rekonstruksi paket terpadu
    output_packet->timestamp_ms = 1711929600000ULL;
    output_packet->ecg_channel_1 = ((float)(raw_encrypted_stream[0] ^ 0xAA) / 255.0f) * 3.3f;
    output_packet->ecg_channel_2 = ((float)(raw_encrypted_stream[1] ^ 0xBB) / 255.0f) * 3.3f;
    output_packet->heart_rate = (uint32_t)(raw_encrypted_stream[2] + 40);

    return 0; // Success
}
```

### 2. File Dart: Model Struct Interop (`telemetry_bindings.dart`)

```dart
import 'dart:ffi' as ffi;
import 'dart:io';

// Memetakan C struct TelemetryPacket ke class Dart ffi.Struct
final class TelemetryPacketStruct extends ffi.Struct {
  @ffi.Uint64()
  external int timestampMs;

  @ffi.Float()
  external double ecgChannel1;

  @ffi.Float()
  external double ecgChannel2;

  @ffi.Uint32()
  external int heartRate;
}

typedef NativeProcessTelemetry = ffi.Int32 Function(
  ffi.Pointer<ffi.Uint8> rawStream,
  ffi.Int32 length,
  ffi.Pointer<TelemetryPacketStruct> outPacket,
);

typedef DartProcessTelemetry = int Function(
  ffi.Pointer<ffi.Uint8> rawStream,
  int length,
  ffi.Pointer<TelemetryPacketStruct> outPacket,
);

class NativeTelemetryEngine {
  late final ffi.DynamicLibrary _nativeLib;
  late final DartProcessTelemetry _processFrame;

  NativeTelemetryEngine() {
    _nativeLib = Platform.isAndroid
        ? ffi.DynamicLibrary.open('libtelemetry_core.so')
        : ffi.DynamicLibrary.process();

    _processFrame = _nativeLib
        .lookup<ffi.NativeFunction<NativeProcessTelemetry>>('process_telemetry_frame')
        .asFunction<DartProcessTelemetry>();
  }

  DartProcessTelemetry get processFrame => _processFrame;
}
```

### 3. File Dart: Background Isolate Worker (`telemetry_isolate_worker.dart`)

```dart
import 'dart:async';
import 'dart:ffi' as ffi;
import 'dart:isolate';
import 'dart:typed_data';
import 'package:ffi/ffi.dart';
import 'telemetry_bindings.dart';

class DecodedTelemetry {
  final int timestamp;
  final double lead1;
  final double lead2;
  final int bpm;

  const DecodedTelemetry(this.timestamp, this.lead1, this.lead2, this.bpm);
}

class TelemetryProcessingWorker {
  late final SendPort _commandsSendPort;
  late final Isolate _workerIsolate;
  final Completer<void> _readyCompleter = Completer<void>();

  Future<void> initialize() async {
    final ReceivePort initReceivePort = ReceivePort();
    _workerIsolate = await Isolate.spawn(
      _isolateEntryPoint,
      initReceivePort.sendPort,
      debugName: "TelemetryWorkerIsolate",
    );

    final events = StreamQueue<dynamic>(initReceivePort);
    _commandsSendPort = await events.next as SendPort;
    _readyCompleter.complete();
  }

  static void _isolateEntryPoint(SendPort sendPort) {
    final ReceivePort workerReceivePort = ReceivePort();
    sendPort.send(workerReceivePort.sendPort);

    // Inisialisasi engine C/C++ di dalam thread isolate khusus ini
    final engine = NativeTelemetryEngine();
    
    // Alokasikan reusable output buffer di memory C Heap
    final ffi.Pointer<TelemetryPacketStruct> packetOutputPtr =
        calloc<TelemetryPacketStruct>();

    workerReceivePort.listen((message) {
      if (message is List) {
        final Uint8List rawBytes = message[0] as Uint8List;
        final SendPort replyTo = message[1] as SendPort;

        final int length = rawBytes.length;
        final ffi.Pointer<ffi.Uint8> rawBuffer = calloc<ffi.Uint8>(length);

        try {
          rawBuffer.asTypedList(length).setAll(0, rawBytes);
          
          final int result = engine.processFrame(
            rawBuffer,
            length,
            packetOutputPtr,
          );

          if (result == 0) {
            // Membaca struct C dan mengonversinya menjadi objek Immutable Dart
            final data = DecodedTelemetry(
              packetOutputPtr.ref.timestampMs,
              packetOutputPtr.ref.ecgChannel1,
              packetOutputPtr.ref.ecgChannel2,
              packetOutputPtr.ref.heartRate,
            );
            replyTo.send(data);
          } else {
            replyTo.send(Exception("Native C++ Error Code: $result"));
          }
        } finally {
          calloc.free(rawBuffer);
        }
      } else if (message == "DISPOSE") {
        calloc.free(packetOutputPtr);
        workerReceivePort.close();
      }
    });
  }

  Future<DecodedTelemetry> processPacket(Uint8List rawFrame) async {
    await _readyCompleter.future;
    final ReceivePort responsePort = ReceivePort();
    _commandsSendPort.send([rawFrame, responsePort.sendPort]);
    
    final result = await responsePort.first;
    if (result is Exception) {
      throw result;
    }
    return result as DecodedTelemetry;
  }

  void dispose() {
    _commandsSendPort.send("DISPOSE");
    _workerIsolate.kill(priority: Isolate.beforeNextEvent);
  }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter Arsitektural | Platform Channels (`MethodChannel`) | Direct `dart:ffi` |
| :--- | :--- | :--- |
| **Eksekusi Execution Time** | Asynchronous (Tertunda oleh scheduler thread loop) | Synchronous / In-Place (Seketika dieksekusi pada CPU thread pemanggil) |
| **Biaya Serialisasi Data** | **Tinggi:** Dart $\to$ Binary Envelope $\to$ JNI/Obj-C Boxing | **Nol (Zero-Copy):** Menyerahkan direct memory pointer alamat C |
| **Overhead Latensi** | $\approx 1.5\text{ms} - 15.0\text{ms}$ (bergantung pada UI platform queue load) | $\approx 0.0001\text{ms} - 0.002\text{ms}$ (Direct hardware instruction jump) |
| **Aksesibilitas UI Framework** | **Penuh:** Mengakses `Activity`, `UIViewController`, SDK UIKit | **Nol:** Tidak memiliki konteks UI Platform (Hanya C-Runtime OS) |
| **Tingkat Bahaya Fatal Crash** | **Rendah:** Platform Exception dapat ditangkap via `catchError` | **Kritis:** Fatal SIGSEGV / Memory Corruption langsung menghentikan app |
| **Kompleksitas Kompilasi Build** | Sederhana: Standar Gradle / CocoaPods project setup | Kompleks: Wajib Android NDK, CMakeLists.txt, Toolchains, Clang linkage |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Pointer Aliasing & Struct Padding Pitfall
*   **Kasus Gagal:** Kompiler C/C++ secara default menambahkan padding bytes ke dalam `struct` untuk menyesuaikan dengan batas 4-byte atau 8-byte CPU word alignment. Jika Dart FFI Struct tidak memetakan padding ini secara identik, pembacaan nilai data Dart akan bergeser (misal: field timestamp menimpa channel ECG).
*   **Mitigasi:** Selalu gunakan `#pragma pack(push, 1)` pada header C++ dan lakukan verifikasi unit test komparatif antara `sizeof(C_Struct)` dan `sizeOf<Dart_Struct>()`.

### 2. iOS Symbol Stripping
*   **Kasus Gagal:** Ketika memanggil `DynamicLibrary.process()` di iOS, fungsi C gagal ditemukan (`symbol not found`), meskipun berjalan lancar di Android `.so`.
*   **Mitigasi:** Xcode Build Settings menerapkan *Dead Code Stripping*. Anda wajib menandai simbol fungsi C dengan atribut:
    `__attribute__((visibility("default"))) __attribute__((used))`

### 3. Background Task Thread Death pada Platform Channels
*   **Kasus Gagal:** Memanggil listener `result.success()` pada Android dari background thread native tanpa me-looping kembali ke MainLooper akan memicu crash:
    `java.lang.RuntimeException: Methods marked with @UiThread must be executed on the main thread`.
*   **Mitigasi:** Selalu bungkus eksekusi callback Android dalam Handler utama:
    ```kotlin
    Handler(Looper.getMainLooper()).post {
        result.success(data)
    }
    ```

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Anti-Pattern: Pengiriman Citra/Video Frame via `MethodChannel`
*   **Kesalahan Fatal:** Mengirimkan raw frame byte array resolusi $1920\times1080$ ($8.29\text{ MB}$ per frame) pada 60 FPS melewati `MethodChannel`.
*   **Dampak:** Flutter UI membeku (freeze), memory footprint melonjak hingga Out-Of-Memory (OOM) crash karena GC menduplikasi array berkali-kali di memori Dart dan Java heap.
*   **Solusi Benar:** Gunakan mekanisme Flutter `Texture` widget dengan register native `SurfaceTexture` / `CVPixelBuffer`, atau kirimkan via shared pointer `dart:ffi`.

### 2. Anti-Pattern: Melupakan `calloc.free()`
*   **Kesalahan Fatal:** Mengalokasikan memory via `calloc<T>()` di dalam fungsi Dart berulang kali tanpa memanggil `free()`.
*   **Dampak:** Terjadi silent native memory leak. Dart DevTools Memory Inspector tidak akan mendeteksi peningkatan memori ini karena memori dialokasikan langsung dari OS Heap, bukan Dart Virtual Machine Heap.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Gunakan Tooling Code Generator `ffigen`:**
    Jangan menulis Dart FFI bindings secara manual untuk C library besar. Gunakan package resmi Flutter `ffigen` yang membaca file C header (`.h`) dan menghasilkan struktur binding secara otomatis dan akurat via LLVM.
2.  **Terapkan Strict Type Channels via Pigeon:**
    Hindari string-based invocation `channel.invokeMethod('someString')` di level enterprise. Gunakan **Pigeon** (official code generator dari Flutter team). Pigeon menghasilkan interface type-safe end-to-end (Dart, Kotlin, Swift) yang menjamin compile-time checking antar bahasa native.
3.  **Terapkan Native Finalizer:**
    Untuk resource native berumur panjang (misal: pointer handle ke database engine C++), pasangkan objek Dart dengan `NativeFinalizer`:
    ```dart
    final NativeFinalizer _nativeFinalizer = NativeFinalizer(
      _lib.lookup<ffi.NativeFunction<ffi.Void Function(ffi.Pointer)>>('release_handle').cast(),
    );
    // Pasang target
    _nativeFinalizer.attach(this, nativePointerHandle, detached: this);
    ```

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI

### Optimasi Binary Messenger Menggunakan Direct Buffers

Jika terpaksa menggunakan platform channel untuk transmisi payload biner yang agak besar (misal: 100 KB - 1 MB), hindari `MethodChannel` dan beralihlah ke **`BasicMessageChannel<ByteData>`** dengan `BinaryCodec`:

```dart
// Zero-serialization overhead di level envelope
final basicChannel = BasicMessageChannel<ByteData>(
  'com.enterprise.binary',
  BinaryCodec(),
);

// Mengirim byte buffer langsung tanpa konversi Map/Object
final ByteData rawData = ByteData.sublistView(myUint8List);
await basicChannel.send(rawData);
```

Dengan cara ini, Flutter Engine melewati serialization encoding `StandardMessageCodec` dan langsung mengantarkan byte stream mentah ke native buffer, menghemat hingga