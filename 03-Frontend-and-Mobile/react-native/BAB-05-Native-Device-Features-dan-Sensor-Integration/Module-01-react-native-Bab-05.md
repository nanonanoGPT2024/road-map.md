# Bab 05 Module 01: Native Device Features & Sensor Integration

---

## SEKSI 01 — IDENTITAS MODUL
* **Track:** Frontend & Mobile Engineering
* **Kategori:** 03-Frontend-and-Mobile
* **Topik:** Native Device Features & Sensor Integration
* **Level:** Advanced (L5 / Senior Engineer)
* **Prasyarat:** Pemahaman mendalam tentang React Native New Architecture (Fabric & TurboModules), C++ JSI Basics, Native Permissions Lifecycle (Android NDK/POSIX & iOS Cocoa Touch), Concurrency (Event Loop & Native Threads).

---

## SEKSI 02 — LEARNING OBJECTIVES
1. Menguasai arsitektur pengumpulan data telemetri sensor frekuensi tinggi (≥60Hz) melintasi JavaScript Interface (JSI) tanpa memicu UI stutter atau saturasi Garbage Collection (GC).
2. Mengimplementasikan sub-sistem geolokasi presisi tinggi dengan strategi adaptif berbasis baterai, state perpindahan gerak (*activity recognition*), dan pembatasan *geofencing*.
3. Menganalisis siklus hidup OS tingkat rendah (Android Foreground Services, Doze Mode, WakeLocks, serta iOS CoreLocation Background Execution & SigMotion Modes).
4. Merancang arsitektur ring-buffer berbasis shared memory/C++ JSI bindings untuk agregasi sensor kontinu (Akselerometer, Giroskop, Magnetometer).
5. Mengidentifikasi, mengukur, dan memitigasi *thermal throttling*, *battery drain*, serta memory leak yang diakibatkan oleh unmanaged native subscriptions.

---

## SEKSI 03 — MINDSET & MENTAL MODEL
### Paradigma Hardware Streaming vs. React State
Mayoritas engineer frontend mendekati integrasi hardware dengan mental model berbasis event listener DOM biasa:
```typescript
// ANTI-PATTERN: Merusak JavaScript Event Loop pada frekuensi tinggi
sensor.subscribe(data => setSensorData(data));
```
Pada sensor frekuensi tinggi (misalnya Inertial Measurement Unit atau IMU pada 100Hz), pendekatan di atas mengirimkan 100 event per detik melewati React Native bridge/JSI dispatcher, memicu 100 kali re-render UI, serialisasi JSON, dan alokasi memori heap yang masif. Hal ini menyebabkan *Garbage Collection thrashing* dan penurunan drastis pada frame rate aplikasi (turun ke < 20 FPS).

```
[Hardware Clock] ---> [Hardware FIFO Buffer] ---> [Kernel Drivers]
                                                          │
[React Render Cycle] <--- [JSI Ring Buffer (C++)] <--- [Native Event Thread]
       (16ms/60fps)              (Batching / Low-pass Filter)     (100Hz - 200Hz)
```

Mental model yang benar: **Perlakukan Hardware sebagai Stream Berkelanjutan Tanpa Batas (High-Frequency Unbounded Stream)**. UI React Native hanyalah observer pasif berfrekuensi rendah (misal: 15–30 FPS atau berbasis *threshold event*) terhadap *state* hardware yang diolah, difilter, dan diagregasi pada native layer (C++/JSI) sebelum diekspos ke runtime JavaScript.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

```
+---------------------------------------------------------------------------------------+
|                                    REACT NATIVE RUNTIME                               |
|                                                                                       |
|   +-------------------------+                       +-----------------------------+   |
|   |   JavaScript Engine     |                       |    React Component (UI)     |   |
|   |       (Hermes)          |                       | (Consumes Batched Aggregates|   |
|   |                         |                       |      at 15-30 Hz max)       |   |
|   +------------+------------+                       +--------------^--------------+   |
|                |                                                   |                  |
|          Direct C++ Call                                           | Subscription     |
|          via TurboModule                                           | (Decoupled)      |
|                |                                                   |                  |
|                v                                                   |                  |
|   +----------------------------------------------------------------+--------------+   |
|   |                       C++ Core / JSI Host Objects                             |   |
|   |  - Native Ring Buffer (Lock-free SPSC Queue)                                  |   |
|   |  - Math Filtering (Butterworth / Kalman Filter / Sensor Fusion)                |   |
|   |  - Downsampling & Batch Scheduler (Dispatch to JS Thread @ fixed intervals)  |   |
|   +--------------------+-------------------------------------------+--------------+   |
+------------------------|-------------------------------------------|------------------+
                         | JNI Calls                                 | Objective-C++
                         v                                           v
+----------------------------------------------------+ +--------------------------------+
|                   ANDROID OS                       | |            APPLE IOS           |
|                                                    | |                                |
|  +----------------------------------------------+  | |  +--------------------------+  |
|  | SensorManager / FusedLocationProviderClient  |  | |  | CMMotionManager /        |  |
|  | (Hardware Event Thread)                      |  | |  | CLLocationManager        |  |
|  +----------------------+-----------------------+  | |  +------------+-------------+  |
|                         |                          | |               |                |
|                         v                          | |               v                |
|  +----------------------------------------------+  | |  +--------------------------+  |
|  | Android Foreground Service                   |  | |  | CoreLocation Daemon      |  |
|  | (PARTIAL_WAKE_LOCK + STICKY Notification)    |  | |  | (UIBackgroundModes)      |  |
|  +----------------------+-----------------------+  | |  +------------+-------------+  |
+-------------------------|--------------------------+ +---------------|----------------+
                          |                                            |
                          +-------------------+------------------------+
                                              |
                                              v
                              +-------------------------------+
                              |    PHYSICAL SENSOR HARDWARE   |
                              |  - Accelerometer (MEMS)       |
                              |  - Gyroscope (MEMS)           |
                              |  - GPS / GNSS / GLONASS Base  |
                              |  - Barometer / Magnetometer   |
                              +-------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Hardware Sensing Pipeline
Sistem sensor fisik (MEMS - *Micro-Electro-Mechanical Systems*) mendeteksi perubahan fisik (kapasitansi mikro karena akselerasi atau gaya coriolis). Perubahan ini dikonversi menjadi data digital oleh ADC (*Analog-to-Digital Converter*) internal chip dan disimpan sementara pada register hardware FIFO (First-In, First-Out).

### 2. Kernel Interrupt & Driver Layer
Ketika FIFO mendekati penuh atau berada pada siklus pengambilan sampel yang ditentukan:
* Hardware memicu *hardware interrupt* (IRQ) ke CPU.
* Kernel driver (Linux kernel pada Android, XNU kernel pada iOS) menangani interrupt tersebut dan memindahkan data dari register I2C/SPI ke kernel input buffer.

### 3. OS Sensor Framework & Dispatching
* **Android:** `SensorManager` mendaftarkan `SensorEventListener`. Subsistem sensor Android menggunakan socket Unix lokal untuk streaming struct data `ASensorEvent` dari `sensorservice` sistem ke process thread milik aplikasi.
* **iOS:** `CMMotionManager` mengeksekusi thread dedicated melalui `NSOperationQueue`. Pada update lokasi, `CLLocationManager` berkomunikasi dengan daemon `locationd` melalui Mach message IPC (*Inter-Process Communication*).

### 4. Bridge vs JSI Architecture Impact
* **Legacy Bridge:** Event sensor dibungkus menjadi payload serialized JSON:
  `[ModuleID, MethodID, [{"x": 0.12, "y": 9.81, "z": 0.05}]]`
  Payload ini dilewatkan melalui antrean serial asynchronous. Pada 100Hz, bridge mengalami kongesti parah.
* **Modern Architecture (JSI & TurboModules):** Callback native C++ dapat langsung mengakses instance runtime Hermes melalui `jsi::Runtime`. Data sensor dapat dimutasi langsung pada typed array (misal: `Float64Array`) yang menunjuk ke buffer memori C++ yang sama, mengeliminasi kebutuhan copy memori dan serialisasi secara menyeluruh.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### High-Frequency IMU Sampling & Nyquist-Shannon Theorem
Frekuensi pengambilan sampel (*sampling rate*) harus mematuhi Teorema Sampling Nyquist-Shannon: untuk merekonstruksi sinyal dengan benar tanpa fenomena *aliasing*, frekuensi sampling ($f_s$) harus lebih besar dari dua kali frekuensi tertinggi sinyal ($f_{max}$):

$$f_s > 2 \cdot f_{max}$$

Untuk mendeteksi dinamika gerak tubuh manusia (misal: analisis langkah berjalan atau deteksi tabrakan kendaraan), frekuensi target biasanya berada di rentang $50\text{ Hz} - 100\text{ Hz}$.

### Signal Processing: Low-Pass Filter vs High-Pass Filter
Data accelerometer mentah terdiri dari dua komponen:
1. Gravitasi bumi konstan ($g \approx 9.81 \text{ m/s}^2$) — Sinyal frekuensi rendah.
2. Akselerasi pengguna — Sinyal frekuensi tinggi.

Untuk memisahkan gravitasi (*low-pass filter*):

$$\alpha = \frac{t_{interval}}{t_{interval} + \tau}$$

$$\text{gravity}_t = \alpha \cdot \text{gravity}_{t-1} + (1 - \alpha) \cdot \text{raw}_t$$

Untuk mendapatkan akselerasi linier murni bebas gravitasi (*high-pass filter*):

$$\text{linear\_acceleration}_t = \text{raw}_t - \text{gravity}_t$$

### OS Energy Management & Suspension Dynamics
* **Android Doze Mode:** Ketika perangkat diam tanpa pengisian daya dan layar mati, sistem mematikan akses jaringan, mengabaikan `WakeLocks`, dan menunda eksekusi alarm serta sensor update kecuali didefinisikan sebagai sensor tipe non-wake-up atau dijalankan dalam *Foreground Service* dengan metadata `foregroundServiceType="location"`.
* **iOS Background Suspension:** Jika aplikasi tidak memiliki hak `UIBackgroundModes` dengan nilai `location` yang valid, sistem akan membekukan thread eksekusi (*SIGSTOP*) dalam kurun waktu 10–30 detik setelah aplikasi berpindah ke background.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut implementasi production-ready native module TurboModule/JSI pattern layer abstraction untuk sensor accelerometer dengan filter low-pass terintegrasi dan pooling frekuensi adaptif di TypeScript:

```typescript
// SensorEngine.ts
import { NativeEventEmitter, NativeModules, Platform } from 'react-native';

export interface AccelerometerData {
  x: number;
  y: number;
  z: number;
  timestamp: number;
}

export type SensorCallback = (data: AccelerometerData) => void;

interface NativeSensorModuleInterface {
  startAccelerometerUpdates(intervalMs: number): Promise<boolean>;
  stopAccelerometerUpdates(): Promise<boolean>;
  setLowPassFilterAlpha(alpha: number): Promise<void>;
}

// Fallback gracefully jika native TurboModule belum dimuat
const NativeSensorModule: NativeSensorModuleInterface = NativeModules.CustomSensorModule;

class SensorEngineManager {
  private static instance: SensorEngineManager;
  private emitter: NativeEventEmitter;
  private subscribers: Set<SensorCallback> = new Set();
  private isRunning: boolean = false;
  private currentIntervalMs: number = 20; // Default 50Hz (1000/20)

  private constructor() {
    this.emitter = new NativeEventEmitter(NativeModules.CustomSensorModule);
  }

  public static getInstance(): SensorEngineManager {
    if (!SensorEngineManager.instance) {
      SensorEngineManager.instance = new SensorEngineManager();
    }
    return SensorEngineManager.instance;
  }

  public async configureFilter(alpha: number): Promise<void> {
    if (alpha <= 0 || alpha >= 1) {
      throw new RangeError("Alpha filter harus berada di antara (0, 1)");
    }
    await NativeSensorModule.setLowPassFilterAlpha(alpha);
  }

  public subscribe(callback: SensorCallback, intervalMs: number = 20): () => void {
    this.subscribers.add(callback);

    if (!this.isRunning) {
      this.currentIntervalMs = intervalMs;
      this.startNativeStream(intervalMs);
    }

    // Cleanup subscription
    return () => {
      this.subscribers.delete(callback);
      if (this.subscribers.size === 0) {
        this.stopNativeStream();
      }
    };
  }

  private async startNativeStream(intervalMs: number): Promise<void> {
    try {
      this.emitter.addListener('onAccelerometerData', this.handleNativePayload);
      await NativeSensorModule.startAccelerometerUpdates(intervalMs);
      this.isRunning = true;
    } catch (error) {
      this.emitter.removeAllListeners('onAccelerometerData');
      throw new Error(`Gagal menginisialisasi hardware accelerometer: ${error}`);
    }
  }

  private async stopNativeStream(): Promise<void> {
    try {
      await NativeSensorModule.stopAccelerometerUpdates();
    } finally {
      this.emitter.removeAllListeners('onAccelerometerData');
      this.isRunning = false;
    }
  }

  private handleNativePayload = (event: AccelerometerData): void => {
    // Dispatch ke JavaScript subscribers tanpa alokasi object baru berlebih
    this.subscribers.forEach((callback) => {
      callback(event);
    });
  };
}

export const SensorEngine = SensorEngineManager.getInstance();
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

| Baris / Rentang Kode | Mekanisme & Target Operasi | Konsekuensi Arsitektural / Hardware |
| :--- | :--- | :--- |
| `class SensorEngineManager` | Menerapkan Singleton Pattern. | Memastikan hanya ada 1 listener aktif ke native hardware buffer, mencegah instansiasi ganda yang menguras baterai. |
| `this.subscribers: Set<SensorCallback>` | Subscription Pool pattern berbasis Set primitif. | Memisahkan lifecycle listening di layer JS dari lifecycle driver hardware; registrasi baru tidak memicu restart native pipeline. |
| `setLowPassFilterAlpha(alpha: number)` | Komunikasi konfigurasi matematika ke native bridge/JSI. | Mengatur nilai smoothing filter langsung di memory space native sebelum data dipaketkan ke JS runtime. |
| `this.emitter.addListener(...)` | Memasang binding event native via `NativeEventEmitter`. | Mengonsumsi pipeline stream data dari layer C++/Platform Native tanpa polling aktif. |
| `if (this.subscribers.size === 0)` | Resource De-allocation check pada return teardown. | Langsung mematikan sensor hardware (`stopAccelerometerUpdates`) saat subscriber terakhir unmount untuk mencegah thermal runaway. |
| `handleNativePayload = (event) => ...` | Bound lexical-scope handler. | Menghindari instansiasi handler function baru di setiap tick transmisi sensor yang akan memicu eksekusi GC Hermes. |

---

## SEKSI 09 — STUDI KASUS NYATA
### Domain: Logistik & Fleet Safety Telematics Platform
Aplikasi enterprise driver monitoring membutuhkan pelacakan rute kurir motor secara berkelanjutan selama 12 jam shift kerja. Persyaratan sistem:
1. **Pendeteksian Tabrakan & Rem Mendadak (*Hard Braking*):** Membutuhkan frekuensi IMU kontinu 50Hz.
2. **Geolokasi Presisi Tinggi:** Update GPS tiap 5 detik atau perpindahan 10 meter.
3. **Efisiensi Baterai Ekstrem:** Driver seringkali tidak memiliki charger stabil; device tidak boleh kehabisan daya lebih dari 4% per jam.
4. **Resistensi Terhadap Aggressive Background OS Killing:** Xiaomi MIUI/HyperOS, Samsung OneUI, dan iOS CoreLocation Background Execution.

### Solusi Arsitektural:
* Menerapkan **Adaptive Dual-Tier State Engine**:
  * **Stationary Mode:** Hanya dengarkan geofence circular buffer + Android `SignificantMotionSensor` (mengonsumsi arus $< 0.1 \text{ mA}$).
  * **In-Motion Mode:** Mengaktifkan GPS secara penuh via Fused Location Provider dan accelerometer stream yang diarahkan langsung ke C++ circular memory buffer.
* Android diikat dengan **Sticky Foreground Service** dengan tipe spesifik `location | health` serta notifikasi persisten prioritas rendah.
* iOS menggunakan konfigurasi `CLLocationManager` dengan `pausesLocationUpdatesAutomatically = false`, `allowsBackgroundLocationUpdates = true`, dan `activityType = CLActivityTypeAutomotiveNavigation`.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi Production-Ready Telematics Engine yang menggabungkan Location, Accelerometer, Ring Buffering, dan Native Foreground Management:

```typescript
// TelematicsCore.ts
import {
  NativeModules,
  NativeEventEmitter,
  Platform,
  PermissionsAndroid,
  AppState,
  AppStateStatus,
} from 'react-native';

export interface TelemetryPacket {
  latitude: number;
  longitude: number;
  accuracy: number;
  speed: number;
  maxGForce: number;
  timestamp: number;
  anomalyDetected: boolean;
}

interface NativeTelematicsBridge {
  startTelemetryDaemon(config: {
    notificationTitle: string;
    notificationBody: string;
    sampleRateHz: number;
    gForceThreshold: number;
  }): Promise<boolean>;
  stopTelemetryDaemon(): Promise<boolean>;
  flushRingBuffer(): Promise<TelemetryPacket[]>;
}

const { TelematicsBridgeModule } = NativeModules;
const telematicsEmitter = new NativeEventEmitter(TelematicsBridgeModule);

export class TelematicsEngine {
  private static instance: TelematicsEngine;
  private isProcessing: boolean = false;
  private appState: AppStateStatus = AppState.currentState;

  private constructor() {
    this.setupLifecycleHooks();
  }

  public static getEngine(): TelematicsEngine {
    if (!TelematicsEngine.instance) {
      TelematicsEngine.instance = new TelematicsEngine();
    }
    return TelematicsEngine.instance;
  }

  private setupLifecycleHooks(): void {
    AppState.addEventListener('change', (nextState: AppStateStatus) => {
      // Menangani transisi state aplikasi untuk logging atau optimasi non-kritis
      this.appState = nextState;
    });
  }

  public async requestRequiredPermissions(): Promise<boolean> {
    if (Platform.OS === 'android') {
      const fineLocationGranted = await PermissionsAndroid.request(
        PermissionsAndroid.PERMISSIONS.ACCESS_FINE_LOCATION,
        {
          title: 'Izin Akses Lokasi Presisi Tinggi Diperlukan',
          message: 'Sistem Telematika memerlukan akses GPS untuk audit keselamatan armada.',
          buttonPositive: 'Beri Izin',
        }
      );

      if (fineLocationGranted !== PermissionsAndroid.RESULTS.GRANTED) {
        return false;
      }

      // Android 10+ (API Level 29) memerlukan izin background location eksplisit terpisah
      if (Platform.Version >= 29) {
        const bgGranted = await PermissionsAndroid.request(
          PermissionsAndroid.PERMISSIONS.ACCESS_BACKGROUND_LOCATION,
          {
            title: 'Izin Lokasi Latar Belakang Diperlukan',
            message: 'Telematika harus tetap aktif saat aplikasi diminimalkan.',
            buttonPositive: 'Izinkan Sepanjang Waktu',
          }
        );
        if (bgGranted !== PermissionsAndroid.RESULTS.GRANTED) {
          return false;
        }
      }

      // Android 13+ (API Level 33) memerlukan runtime izin notifikasi untuk Foreground Service
      if (Platform.Version >= 33) {
        const notificationGranted = await PermissionsAndroid.request(
          PermissionsAndroid.PERMISSIONS.POST_NOTIFICATIONS
        );
        if (notificationGranted !== PermissionsAndroid.RESULTS.GRANTED) {
          return false;
        }
      }

      return true;
    }

    if (Platform.OS === 'ios') {
      // iOS permission handled via Info.plist runtime triggers pada native call
      return true;
    }

    return false;
  }

  public async initializeTelemetryPipeline(
    onCriticalEvent: (event: TelemetryPacket) => void
  ): Promise<void> {
    const hasPermission = await this.requestRequiredPermissions();
    if (!hasPermission) {
      throw new Error('Sistem izin ditolak oleh pengguna. Pipeline gagal dimulai.');
    }

    try {
      // Hubungkan event listener untuk anomali telemetri (misal: Crash Detection)
      telematicsEmitter.addListener('onTelemetryAnomaly', onCriticalEvent);

      await TelematicsBridgeModule.startTelemetryDaemon({
        notificationTitle: 'Telematika Armada Aktif',
        notificationBody: 'Memantau akselerasi sensorik dan koordinat telematika.',
        sampleRateHz: 50, // 50 Hz internal buffer sampling
        gForceThreshold: 2.5, // 2.5G trigger threshold untuk crash/hard braking
      });

      this.isProcessing = true;
    } catch (nativeException) {
      telematicsEmitter.removeAllListeners('onTelemetryAnomaly');
      this.isProcessing = false;
      throw new Error(`Inisialisasi Native Daemon Gagal: ${nativeException}`);
    }
  }

  public async terminatePipeline(): Promise<void> {
    if (!this.isProcessing) return;

    try {
      await TelematicsBridgeModule.stopTelemetryDaemon();
    } finally {
      telematicsEmitter.removeAllListeners('onTelemetryAnomaly');
      this.isProcessing = false;
    }
  }

  public async pullTelemetryBatch(): Promise<TelemetryPacket[]> {
    if (!this.isProcessing) {
      return [];
    }
    // Menarik isi data buffer tanpa memblokir native sensor writing thread
    return await TelematicsBridgeModule.flushRingBuffer();
  }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter Arsitektural | Polling via JSI (Bridge-less Direct Fetch) | Event-Driven Native Emitter | Native Foreground Service Buffer Ring |
| :--- | :--- | :--- | :--- |
| **Beban JS Event Loop** | Rendah (Tergantung interval polling JS). | Sangat Tinggi pada Frekuensi > 60Hz. | Nol (Eksekusi terisolasi di C++/Native). |
| **Presisi Waktu (*Jitter*)** | Sangat Buruk (Terdistorsi JS thread ticks). | Moderat (Fluktuasi bridge crossing). | Sangat Akurat (Hardware Clock Tick / $\mu s$). |
| **Konsumsi Baterai** | Variatif tergantung implementasi polling. | Tinggi (Serialize/Deserialize intensif). | Minimal (Buffer dialokasikan di memory C++). |
| **Ketahanan di Background** | Nol (Terminasi seketika saat JS freeze). | Nol (Terminasi saat JS freeze). | Maksimal (Dilindungi oleh OS Foreground Daemon).|
| **Kompleksitas Implementasi** | Sangat Sederhana (Kode murni TypeScript). | Moderat (Perlu native event emitter). | Sangat Tinggi (Perlu NDK, Swift, C++, IPC Native). |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Thermal Throttling & Sensor Drift
Ketika smartphone terpapar sinar matahari langsung (misal: di holder dashboard pengemudi) dan CPU bekerja memproses streaming sensor, suhu internal baterai melonjak ke $>45^\circ\text{C}$.
* **Failure Mode:** CPU membatasi clock (*throttling*), menyebabkan native thread kehilangan sampel sensor (sample dropping) dan osilator kristal accelerometer mengalami pergeseran titik nol (*temperature drift*).
* **Mitigasi:** Kurangi sampling rate secara adaptif dari 100Hz ke 25Hz jika native API mendeteksi `ThermalStatus` bernilai `SEVERE` atau `CRITICAL` via Android `PowerManager.OnThermalStatusChangedListener`.

### 2. Battery Optimization "OEM Aggressive Killing"
* **Failure Mode:** Sistem seperti Huawei EMUI atau Xiaomi HyperOS mematikan Native Background Worker meskipun berstatus foreground service standar.
* **Mitigasi:** Tambahkan pengecekan native intent ke `PowerManager.isIgnoringBatteryOptimizations()`. Jika false, arahkan pengguna ke menu settings:
  `ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`.

### 3. False Positives pada Deteksi G-Force
* **Failure Mode:** Ponsel terjatuh di dalam kabin menghasilkan spike akselerasi instan ($>4G$) menyerupai benturan tabrakan kendaraan.
* **Mitigasi:** Sensor Fusion Validation. Validasi event tabrakan akselerometer dengan data GPS speed delta: Tabrakan nyata selalu diikuti oleh penurunan kecepatan GPS yang instan mendekati $0 \text{ km/jam}$.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Re-instantiating NativeEventEmitter di Render Scope
```typescript
// KESALAHAN FATAL:
function BadSensorComponent() {
  useEffect(() => {
    // MEMBUAT INSTANCE SETIAP RENDER ATAU REMOUNT MENINGGALKAN DANGLING LISTENER DI NATIVE MEMORY!
    const emitter = new NativeEventEmitter(NativeModules.SensorModule);
    emitter.addListener('onData', (d) => console.log(d));
  }, []);
}

// CARA BENAR:
// Pertahankan SATU emitter static global di luar scope lifecyle komponen (Singleton Layer).
```

### 2. Mengabaikan Desinkronisasi Timestamp Antara Sensor & GPS
* **Masalah:** Accelerometer sering menggunakan waktu monotonic berbasis hardware clock sejak boot perangkat (`SystemClock.elapsedRealtimeNanos()`), sedangkan modul GPS menggunakan waktu absolut epoch satelit UTC (`System.currentTimeMillis()`).
* **Solusi:** Jangan mencampur timestamp mentah. Lakukan konversi epoch absolut pada native wrapper layer saat sampel sensor diakuisisi sebelum dimasukkan ke ring buffer.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Gunakan Direct Struct Passing via JSI (TurboModules):** Hindari pengiriman string JSON melalui legacy bridge. Gunakan `jsi::ArrayBuffer` atau `HostObject` untuk melewatkan data biner sensor ke JS runtime.
2. **Penerapan Dynamic Sample Rate Switching:**
   * App di Active UI: 60Hz.
   * App di Background (Kecepatan $>15\text{ km/jam}$): 30Hz.
   * App di Background (Kecepatan $<2\text{ km/jam}$): 1Hz atau matikan sampling secara penuh dan dengarkan `SignificantMotion`.
3. **Penyimpanan Lokal Menggunakan WAL Mode:** Tulis data sensor batch ke SQLite lokal menggunakan Write-Ahead Logging (WAL) untuk menghindari blocking pada UI reading operations.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### Implementasi Native Ring Buffer (C++ Mockup untuk TurboModule)
Alih-alih mengalokasikan object JS baru pada setiap event, alokasikan *single-producer single-consumer* (SPSC) circular ring buffer di layer C++ native:

```cpp
// SensorRingBuffer.hpp
#pragma once
#include <vector>
#include <atomic>

struct SensorReading {
    double x;
    double y;
    double z;
    uint64_t timestamp;
};

class SensorRingBuffer {
private:
    std::vector<SensorReading> buffer_;
    size_t capacity_;
    std::atomic<size_t> head_{0};
    std::atomic<size_t> tail_{0};

public:
    explicit SensorRingBuffer(size_t capacity) : capacity_(capacity), buffer_(capacity) {}

    bool push(const SensorReading& item) {
        size_t current_head = head_.load(std::memory_order_relaxed);
        size_t next_head = (current_head + 1) % capacity_;
        if (next_head == tail_.load(std::memory_order_acquire)) {
            return false; // Buffer penuh, drop data tertua atau tolak data
        }
        buffer_[current_head] = item;
        head_.store(next_head, std::memory_order_release);
        return true;
    }

    size_t drainTo(std::vector<SensorReading>& output) {
        size_t count = 0;
        size_t current_tail = tail_.load(std::memory_order_relaxed);
        while (current_tail != head_.load(std::memory_order_acquire)) {
            output.push_back(buffer_[current_tail]);
            current_tail = (current_tail + 1) % capacity_;
            count++;
        }
        tail_.store(current_tail, std::memory_order_release);
        return count;
    }
};
```
Pendekatan ini memangkas overhead garbage collection di JavaScript engine hingga 100% untuk operasi akuisisi sensor.

---

## SEKSI 16 — KEAMANAN & HARDENING

1. **Eksfiltrasi Lokasi Silang & Obfuscation:**
   Untuk analitik data sensor yang tidak memerlukan lokasi geografis presisi, aplikasikan *differential privacy noise* (penambahan noise berbasis Gaussian atau Laplace) pada koordinat lokasi sebelum data dikirimkan ke backend:
   
   $$\text{lat}_{obfuscated} = \text{lat} + \mathcal{N}(0, \sigma^2)$$

2. **Deteksi Root/Jailbreak untuk Mencegah GPS Spoofing:**
   Periksa flags `isMockMode` / `isFromMockProvider` pada native Android `Location` struct. Blokir data jika lokasi terbukti berasal dari *mock location provider*:
   ```java
   if (location.isFromMockProvider()) {
       throw new SecurityException("Mock GPS location terdeteksi. Integritas data ditolak.");
   }
   ```
3. **Payload Encryption at Rest:**
   Data batch sensor yang disimpan sementara di SQLite lokal sebelum dikirimkan ke cloud harus dienkripsi menggunakan SQLCipher dengan kunci enkripsi yang diamankan di Android Keystore / iOS Keychain.

---

## SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

### Metrics to Track
1. **Sampling Frequency Drift:** Delta antara target interval vs interval aktual hardware clock.
2. **Buffer Drop Count:** Jumlah frame/packet sensor yang terpaksa di-drop karena circular buffer mengalami saturasi.
3. **Battery Consumption per Hour (Normalized mAh):** Menghitung pengurasan daya spesifik selama sensor pipeline berjalan menggunakan Android `BatteryStats` dump.

### Debugging Menggunakan ADB (Android Debug Bridge)
Untuk menganalisis apakah hardware sensor tetap memicu CPU saat aplikasi diminimalkan:
```bash
# Pantau wake locks aktif yang dipegang oleh aplikasi telematika
adb shell dumpsys power | grep -i "TelematicsWakeLock"

# Dump status frekuensi sensor dan listener yang sedang aktif
adb shell dumpsys sensorservice

# Simulasikan Doze Mode untuk menguji background survivability
adb shell dumpsys deviceidle force-idle
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

* **Frekuensi Tinggi ($\ge 50\text{Hz}$):** Selalu lakukan batching atau proses di layer native/C++. Jangan pernah langsung menembakkan event ke layer React UI melalui bridge biasa.
* **Low-Pass Filter:** Menghilangkan noise akselerasi mendadak untuk mengekstrak vektor orientasi/gravitasi.
* **High-Pass Filter:** Menghilangkan gravitasi untuk mengekstrak dynamic user linear acceleration.
* **Android Background:** Wajib menggunakan *Foreground Service* dengan `ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION`.
* **iOS Background:** Tambahkan `location` ke array `UIBackgroundModes` dan konfigurasikan `allowsBackgroundLocationUpdates = true`.
* **Sensor Lifecycle:** Pasang subscription tepat waktu; cabut event listener secepatnya saat komponen unmount untuk menghindari battery drain instan.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal 1
Aplikasi pelacak fitness Anda mengalami freeze selama 1–2 detik secara berkala setiap 20 detik saat merekam data sensor gerak pada 100Hz di Android, meskipun UI hanya menampilkan angka timer. Apa penyebab teknis paling mendasar dari fenomena ini?
* A. Thread UI Android kehabisan alokasi context switching.
* B. Terjadi saturasi Garbage Collection (GC) pada Hermes/V8 karena instansiasi ratusan payload object JSON per detik yang melintasi bridge.
* C. Kernel Linux mematikan chip accelerometer untuk pendinginan termal.
* D. FusedLocationProviderClient mengalami starvation network access.

### Soal 2
Mengapa data akselerometer mentah ($x, y, z$) dari hardware tetap membaca nilai sebesar $\approx 9.81 \text{ m/s}^2$ pada salah satu sumbunya saat smartphone diletakkan diam di atas meja datar?
* A. Sensor mengalami cacat kalibrasi pabrik (*hardware offset drift*).
* B. Sensor MEMS mendeteksi rotasi putaran bumi pada porosnya.
* C. Sensor mendeteksi gaya normal yang melawan tarikan gravitasi bumi.
* D. OS Android dan iOS menginjeksi mock data saat perangkat berada pada status idle.

### Soal 3
Pada platform Android (API Level 29+), urutan izin yang benar agar aplikasi dapat membaca koordinat GPS driver secara stabil saat layar ponsel dimatikan oleh pengguna adalah:
* A. Cukup meminta izin `ACCESS_COARSE_LOCATION` di AndroidManifest.xml.
* B. Meminta `ACCESS_FINE_LOCATION` terlebih dahulu, lalu meminta runtime permission untuk `ACCESS_BACKGROUND_LOCATION`, serta menyertakan tipe service yang sesuai pada Foreground Service.
* C. Meminta `SYSTEM_ALERT_WINDOW` dan mengabaikan permissions lifecycle.
* D. Cukup mendeklarasikan `WAKE_LOCK` di file runtime settings.

### Soal 4
Apa perbedaan mendasar antara implementasi integrasi sensor menggunakan Legacy Bridge dengan implementasi menggunakan TurboModule berbasis C++ JSI?
* A. JSI memerlukan compiler Java eksternal sedangkan Legacy Bridge tidak.
* B. Legacy Bridge memblokir eksekusi sensor pada level kernel hardware.
* C. JSI memungkinkan JavaScript mengeksekusi referensi memori Native HostObject secara sinkron tanpa serialisasi/deserialisasi payload ke string JSON.
* D. JSI menonaktifkan kebutuhan izin OS (*runtime permissions*).

### Soal 5
Sebuah sistem pendeteksi kecelakaan membaca data akselerasi mendadak sebesar $5G$ selama $5 \text{ ms}$, namun kecepatan GPS kendaraan berada konstan pada $0 \text{ km/jam}$ sebelum dan sesudah kejadian. Keputusan algoritma yang paling tepat berdasarkan Sensor Fusion Theory adalah:
* A. Langsung mengirim sinyal crash darurat ke server pusat armada.
* B. Mengabaikan data GPS karena akselerometer selalu memiliki presisi absolut lebih tinggi.
* C. Mengkategorikan data sebagai anomali/ponsel terjatuh karena tidak ada transisi energi kinetik (kecepatan delta mendekati nol).
* D. Menginisialisasi hard restart pada perangkat Android.

---

### Kunci Jawaban & Analisis Evaluasi
1. **Jawaban: B.** Pada 100Hz, jika data dialirkan melintasi bridge tanpa batching native, ribuan object sementara dialokasikan di memory heap JavaScript. Hermes GC terpaksa melakukan siklus *Stop-the-