# Kurikulum Enterprise: React Native Native Features & Sensor Integration
**Kategori:** 03-Frontend-and-Mobile  
**Bab 05:** Native Device Features dan Sensor Integration  
**Modul 02:** Deep Dive, Implementasi Lanjutan & Arsitektur Produksi  

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, tech lead dan senior mobile engineer diharapkan mampu:

1. **Menganalisis dan Mengoptimalkan Bottleneck JSI/Bridge:** Memahami siklus hidup data streaming frekuensi tinggi (≥60Hz) dari native hardware ke JavaScript runtime tanpa memicu starvation pada JS Event Loop.
2. **Mengarsitekturi Pipeline Pemrosesan Frame Real-Time:** Mengimplementasikan VisionCamera Frame Processors berbasis C++ JSI dan Worklet Runtime untuk computer vision on-device dengan latensi sub-16ms.
3. **Membangun Background Location & Telematics Engine:** Mengintegrasikan CoreLocation (iOS) dan FusedLocationProviderClient (Android Foreground Service) yang resilien terhadap Android Doze Mode dan iOS Memory Pressure Termination.
4. **Menerapkan Zero-Allocation Memory Strategy:** Mencegah degradasi performa akibat Garbage Collection (GC) churn saat streaming data sensor mentah (IMU: Accelerometer, Gyroscope, Magnetometer).
5. **Mengimplementasikan Hardware-Backed Security:** Mengamankan payload sensitif pada level rest dan in-transit menggunakan iOS Secure Enclave (Keychain Services) dan Android Keystore System via Biometric Authentication APIs.

---

## 2. Prerequisites

Sebelum mempelajari modul ini, pastikan Anda telah menguasai:

* **React Native Core Internals:** Memahami arsitektur New Architecture (Fabric Renderer, TurboModules, JSI, CodeGen) pada React Native versi $\ge 0.73$.
* **Native Runtime Basics:** Pemahaman dasar threading model pada iOS (Grand Central Dispatch, RunLoops) dan Android (Looper, HandlerThread, Services).
* **Modern C++ Basics:** Konsep pointer, memory reference, move semantics, dan implementasi interface `facebook::jsi::HostObject`.
* **Sensor Math Fundamentals:** Konsep vektor 3D, quaternion, drift compensation, dan filtering dasar (Low-pass filter, Complementary filter).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1. Old Architecture Bridge vs. New Architecture JSI untuk I/O Sensor

Pada arsitektur lama (Bridge), setiap event hardware (misal: sensor IMU pada 100Hz) harus melalui pipeline:
1. Native Interrupt $\rightarrow$ 2. Driver Layer $\rightarrow$ 3. Native Module $\rightarrow$ 4. Serialisasi JSON $\rightarrow$ 5. MessageQueue Async Bridge $\rightarrow$ 6. Deserialisasi JSON $\rightarrow$ 7. JavaScript Callback.

Proses ini menimbulkan overhead alokasi memori yang masif, GC pressure konstan, dan latency jitter yang tidak dapat diprediksi.

```
[ OLD ARCHITECTURE: BRIDGE BOTTLENECK ]
[Hardware Interrupt (100Hz)]
          │
          ▼
[Native Driver / Thread Pool]
          │
          ▼
[JSON Stringify Buffer] ───(JSON Array Payload)───► [Cross-Bridge Async Serialization]
                                                                    │
                                                                    ▼
                                                        [JSON Parse (JS Thread)]
                                                                    │
                                                                    ▼
                                                        [JS GC Engine Trashed!]
```

Pada arsitektur baru berbasis **JavaScript Style Interface (JSI)**:
Native modul mengekspos C++ `HostObject` langsung ke JavaScript engine (Hermes). JavaScript memegang referensi pointer langsung ke native memory buffer.

```
[ NEW ARCHITECTURE: JSI ZERO-COPY MEMORY PIPELINE ]
[Hardware Interrupt (100Hz)]
          │
          ▼
[Native Driver / Dedicated Thread]
          │
          ▼
[C++ Shared Memory Buffer / HostObject]  ◄─── Direct In-Memory Read ───► [Hermes JS Engine]
(Zero Serialization, No JSON Parse, Microsecond Latency)
```

### 3.2. Background Execution Model: iOS vs. Android

Eksekusi background processing memerlukan pemahaman terhadap arsitektur kernel lifecycle kedua platform:

#### Android
* **Doze Mode & App Standby:** Android membatasi akses network dan menunda sync serta `WAKE_LOCK` jika perangkat tidak bergerak.
* **Foreground Service Lifecycle:** Solusi background streaming berkelanjutan (misal: pelacakan GPS armada) wajib menggunakan `ForegroundService` dengan notifikasi persisten dan deklarasi atribut `android:foregroundServiceType="location"` (target SDK $\ge 34$).
* **Power Management:** WorkManager untuk tugas deferred/periodik; Foreground Service untuk operasi live deterministik.

#### iOS
* **Suspension by Design:** iOS secara agresif men-suspend aplikasi dalam 5–30 detik setelah masuk ke background state (`applicationDidEnterBackground`).
* **Background Execution Capabilities:** Memerlukan deklarasi entitlements:
  * `location` (Updates lokasi berkala via `UIBackgroundModes`).
  * `processing` (Background Tasks via `BGTaskScheduler`).
* **Thermal Throttling & CoreLocation Engine:** iOS menurunkan akurasi GPS secara native ketika thermal state mencapai `ProcessInfo.ThermalState.serious` guna mencegah battery degradation.

---

## 4. Why & What

| Dimensi | Mengapa Ini Krusial? | Apa yang Harus Diimplementasikan? |
| :--- | :--- | :--- |
| **Throughput Data Sensor** | Sensor telematika modern menghasilkan 50–200 payload/detik. Bridge serialisasi konvensional menyebabkan dropped frames (<30 FPS UI). | Direct native memory access via JSI C++ HostObjects atau batching buffer pada native layer sebelum delegasi ke JS thread. |
| **Real-time Computer Vision** | Pemrosesan video frame (1080p @ 30/60 FPS) via bridge menyebabkan app out-of-memory (OOM) seketika. | VisionCamera Frame Processors yang berjalan di secondary JS runtime (Worklet thread), membaca raw pixel buffer (`CMSampleBuffer` / `ImageProxy`). |
| **Battery Life Economics** | Mengaktifkan hardware GPS resolusi tinggi (`kCLLocationAccuracyBestForNavigation`) secara continuous menghabiskan baterai pengguna dalam <3 jam. | Dynamic adaptive sampling engine: Mengubah akurasi dan interval pembacaan berdasarkan kecepatan gerak dan state accelerometer. |
| **Sistem Keamanan Hardware** | Penyimpanan token sesi di AsyncStorage rentan terhadap physical extraction dan rooted/jailbroken devices. | Key pair derivation langsung di dalam Secure Enclave / Android Keystore, diproteksi verifikasi biometrik Level 3 (Strong). |

---

## 5. How (Workflow Detail)

Arsitektur sinkronisasi telematika dan pemrosesan sensor terdistribusi:

```
+---------------------------------------------------------------------------------------+
| NATIVE OPERATING SYSTEM (iOS / Android)                                               |
|                                                                                       |
|  [Hardware Sensors]      [Camera Sensor]             [Biometric Core]                 |
|    (IMU / GPS)                 │                             │                        |
|         │                      ▼                             ▼                        |
|         │             [AVFoundation/CameraX]         [LocalAuthentication]            |
|         ▼                      │                             │                        |
|  [FusedLocation / IMU]         │                             │                        |
|  (Native Ring Buffer)          ▼                             ▼                        |
|         │            [Raw Pixel Buffer]         [Hardware Key Decryption]             |
|         │                      │                             │                        |
+---------┼----------------------┼-----------------------------┼------------------------+
          │ (Zero-Copy JSI Pointer)                      │     │                        |
          ▼                      ▼                             ▼                        |
+---------------------------------------------------------------------------------------+
| REACT NATIVE RUNTIME (C++ / Worklets / TurboModule)                                   |
|                                                                                       |
|  [C++ Aggregator & Filter Engine]    [Vision Worklet Thread]       [Secure Enclave]   |
|  (Complementary / Kalman Filter)     (Run Model / OCR Inference)  (TurboModule Layer) |
|         │                                    │                       │                |
|         ▼ (Batch Throttle: 60Hz -> 5Hz)      ▼ (Inference Result)    │                |
+---------┼────────────────────────────────────┼───────────────────────┼----------------+
          │                                    │                       │                |
          ▼                                    ▼                       ▼                |
+---------------------------------------------------------------------------------------+
| JAVASCRIPT THREAD (Hermes UI Layer)                                                   |
|                                                                                       |
|  - Telematics State Manager (Zustand/Redux)                                           |
|  - Real-time Alerting & Navigation UI Updates                                         |
|  - Secured Network Syncer (Buffered Gzip SQLite / Offline-first DB)                   |
+---------------------------------------------------------------------------------------+
```

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem

Bayangkan sebuah pabrik perakitan berkecepatan tinggi:
* **Sensor Mentah & Frame Kamera:** Aliran air dari air terjun bertekanan tinggi (*Firehose*).
* **JavaScript Thread:** Seorang koki yang sedang menghias kue (*Single-threaded, butuh presisi, mudah terdistraksi*).
* **Pendekatan Lama (Bridge):** Membawa air terjun langsung ke mangkuk adonan koki dengan ember-ember kecil yang diberi label (JSON). Hasilnya: Meja dapur berantakan, koki kebanjiran, kue hancur (*UI Freeze/ANR*).
* **Pendekatan Baru (Native Filter + JSI Worklet):** Memasang bendungan dan turbin mekanis langsung di dasar air terjun. Turbin hanya menyaring partikel emas (*insights/coordinates valid*) dan menyalurkannya lewat pipa presisi kecil (*JSI Shared Memory*) ke koki setiap beberapa detik sekali.

### Diagram Alir State Eksekusi Sensor

```
[IDLE STATE]
     │
     │ Device motion > 1.2G detected (Significant Motion)
     ▼
[WAKE: LOW-POWER INERTIAL TRACKING] (Sample Rate: 10Hz)
     │
     │ Speed threshold > 15 km/h sustained for 10s
     ▼
[TRANSITION: HIGH-PRECISION TELEMATICS] (Sample Rate: GPS 1Hz + IMU 50Hz)
     │
     ├── Battery Level Drops < 20%? ──► [FALLBACK: POWER-CONSERVATION MODE]
     │                                      (GPS: 50m filter, IMU: 10Hz)
     │
     │ Speed < 3 km/h for 3 minutes
     ▼
[AUTO-SUSPEND ENGINE] ──► [SAVE STATE TO SQLITE] ──► [IDLE STATE]
```

---

## 7. Implementation: Simple vs. Enterprise Practical

### 7.1. Contoh Sederhana (Anti-Pattern vs Pattern Dasar)

Menggunakan interval timer JavaScript secara langsung untuk polling sensor adalah anti-pattern berat karena clock drift dan JS thread delay.

```typescript
// BAD: Anti-pattern pada production
useEffect(() => {
  const interval = setInterval(async () => {
    const loc = await getCurrentLocation(); // Bridge round-trip delay variable!
    updateBackend(loc);
  }, 1000);
  return () => clearInterval(interval);
}, []);
```

### 7.2. Implementasi Enterprise Production-Grade

Berikut adalah arsitektur produksi terpadu: Modul telematika sensor berbasis native event, filtering buffer, dan sinkronisasi hardware-accelerated.

#### Tipe Data Sensor & Telematika (`src/types/telematics.ts`)

```typescript
export interface SensorAxesData {
  x: number;
  y: number;
  z: number;
  timestamp: number;
}

export interface TelemetryFrame {
  id: string;
  latitude: number;
  longitude: number;
  speed: number;
  accuracy: number;
  accelerationMagnitude: number;
  isHardBraking: boolean;
  timestamp: number;
}

export interface DeviceOrientationQuaternion {
  qx: number;
  qy: number;
  qz: number;
  qw: number;
}
```

#### Sensor Ring Buffer & Anomaly Detector (`src/core/SensorFusionEngine.ts`)

Engine ini bertugas melakukan rolling calculation terhadap data accelerometer mentah tanpa menyebabkan GC spikes (zero unnecessary object allocations):

```typescript
import { SensorAxesData } from '../types/telematics';

export class SensorFusionEngine {
  private readonly G_GRAVITY = 9.80665;
  private readonly HARD_BRAKE_THRESHOLD_G = -0.45; // -0.45G deceleration
  private lastX = 0;
  private lastY = 0;
  private lastZ = 0;
  private alpha = 0.8; // Low-pass filter weight

  /**
   * Mengisolasi gravitasi bumi menggunakan Low-Pass Filter
   * dan mendeteksi linear acceleration menggunakan High-Pass Filter.
   */
  public processInertialFrame(raw: SensorAxesData): {
    linearAccelerationY: number;
    magnitude: number;
    isHardBraking: boolean;
  } {
    // 1. Low-Pass Filter: Ekstraksi komponen gravitasi konstan
    this.lastX = this.alpha * this.lastX + (1 - this.alpha) * raw.x;
    this.lastY = this.alpha * this.lastY + (1 - this.alpha) * raw.y;
    this.lastZ = this.alpha * this.lastZ + (1 - this.alpha) * raw.z;

    // 2. High-Pass Filter: Komponen akselerasi gerak murni (tanpa gravitasi)
    const linearY = raw.y - this.lastY;
    const linearX = raw.x - this.lastX;
    const linearZ = raw.z - this.lastZ;

    // Vektor Magnitude dalam satuan G-force
    const magnitude = Math.sqrt(
      linearX * linearX + linearY * linearY + linearZ * linearZ
    ) / this.G_GRAVITY;

    // Hitung apakah terjadi pengereman mendadak (asumsi sumbu Y adalah arah laju kendaraan)
    const normalizedDeceleration = linearY / this.G_GRAVITY;
    const isHardBraking = normalizedDeceleration <= this.HARD_BRAKE_THRESHOLD_G;

    return {
      linearAccelerationY: linearY,
      magnitude,
      isHardBraking,
    };
  }

  public reset(): void {
    this.lastX = 0;
    this.lastY = 0;
    this.lastZ = 0;
  }
}
```

#### Production Background Telematics Service (`src/services/TelematicsTracker.ts`)

Implementasi background tracking yang memadukan adaptive sampling, batched writes, dan native service resilience.

```typescript
import { Platform } from 'react-native';
import { SensorFusionEngine } from '../core/SensorFusionEngine';
import { TelemetryFrame, SensorAxesData } from '../types/telematics';

// Interface abstraksi hardware native controller
export interface NativeLocationSource {
  startLocationUpdates(config: {
    distanceFilter: number;
    desiredAccuracy: 'high' | 'balanced' | 'low';
    pausesLocationUpdatesAutomatically: boolean;
    showsBackgroundLocationIndicator: boolean;
  }): Promise<void>;
  stopLocationUpdates(): Promise<void>;
  onLocationUpdate(callback: (loc: any) => void): () => void;
}

export class TelematicsTracker {
  private static instance: TelematicsTracker;
  private fusionEngine: SensorFusionEngine;
  private frameBuffer: TelemetryFrame[] = [];
  private readonly BUFFER_FLUSH_THRESHOLD = 50;
  private isRunning = false;
  private unsubscribeLocation: (() => void) | null = null;

  private constructor(private nativeLocation: NativeLocationSource) {
    this.fusionEngine = new SensorFusionEngine();
  }

  public static getInstance(nativeSource: NativeLocationSource): TelematicsTracker {
    if (!TelematicsTracker.instance) {
      TelematicsTracker.instance = new TelematicsTracker(nativeSource);
    }
    return TelematicsTracker.instance;
  }

  public async startTrackingSession(): Promise<void> {
    if (this.isRunning) {
      return;
    }

    this.fusionEngine.reset();
    this.frameBuffer = [];

    // Konfigurasi level native OS untuk background resilience
    await this.nativeLocation.startLocationUpdates({
      distanceFilter: 5, // Metres: Minimalkan noise saat idle
      desiredAccuracy: 'high',
      pausesLocationUpdatesAutomatically: false, // Critical untuk delivery tracking!
      showsBackgroundLocationIndicator: true, // Wajib di iOS
    });

    this.unsubscribeLocation = this.nativeLocation.onLocationUpdate(
      (locationRaw) => this.handleNativeLocation(locationRaw)
    );

    this.isRunning = true;
  }

  private handleNativeLocation(rawLoc: any): void {
    // Simulasi integrasi data IMU native realtime
    const simulatedRawIMU: SensorAxesData = {
      x: 0.02,
      y: -4.8, // Menandakan deselerasi
      z: 9.78,
      timestamp: Date.now(),
    };

    const imuResult = this.fusionEngine.processInertialFrame(simulatedRawIMU);

    const frame: TelemetryFrame = {
      id: `${rawLoc.timestamp}-${Math.random().toString(36).substr(2, 9)}`,
      latitude: rawLoc.coords.latitude,
      longitude: rawLoc.coords.longitude,
      speed: rawLoc.coords.speed ?? 0,
      accuracy: rawLoc.coords.accuracy ?? 0,
      accelerationMagnitude: imuResult.magnitude,
      isHardBraking: imuResult.isHardBraking,
      timestamp: rawLoc.timestamp,
    };

    this.frameBuffer.push(frame);

    if (this.frameBuffer.length >= this.BUFFER_FLUSH_THRESHOLD) {
      this.flushBufferToStorage();
    }
  }

  private async flushBufferToStorage(): Promise<void> {
    if (this.frameBuffer.length === 0) return;

    const payload = [...this.frameBuffer];
    this.frameBuffer = [];

    try {
      // Async direct write ke storage layer (SQLite / MMKV via C++)
      await this.persistFrames(payload);
    } catch (error) {
      // Re-queue buffer jika operasi I/O gagal
      this.frameBuffer = [...payload, ...this.frameBuffer];
      console.error('[TelematicsTracker] Failed to flush frames:', error);
    }
  }

  private async persistFrames(frames: TelemetryFrame[]): Promise<void> {
    // Pipeline I/O batch processing terproteksi
    return new Promise((resolve) => setTimeout(resolve, 10));
  }

  public async stopTrackingSession(): Promise<void> {
    if (!this.isRunning) return;

    if (this.unsubscribeLocation) {
      this.unsubscribeLocation();
      this.unsubscribeLocation = null;
    }

    await this.nativeLocation.stopLocationUpdates();
    await this.flushBufferToStorage();
    this.isRunning = false;
  }
}
```

#### Hardware-Backed Key Derivation & Biometric Auth (`src/security/HardwareKeyManager.ts`)

```typescript
import { NativeModules, Platform } from 'react-native';

export interface BiometricAuthResult {
  success: boolean;
  signature?: string;
  errorCode?: 'USER_CANCELED' | 'LOCKOUT' | 'HARDWARE_UNAVAILABLE' | 'NOT_ENROLLED';
}

export class HardwareKeyManager {
  /**
   * Mengakses Keypair yang terisolasi di Secure Enclave (iOS)
   * atau KeyStore (Android StrongBox) untuk validasi cryptographically non-repudiation.
   */
  public static async signPayloadWithBiometrics(
    challengePayload: string
  ): Promise<BiometricAuthResult> {
    try {
      // Interface TurboModule langsung ke native layer
      const nativeSecurity = NativeModules.EnterpriseSecurityModule;

      if (!nativeSecurity) {
        throw new Error('EnterpriseSecurityModule TurboModule is not linked!');
      }

      const signature = await nativeSecurity.signWithDeviceKey(
        challengePayload,
        {
          biometricPrompt: 'Autentikasi untuk otorisasi akses sensor critical',
          fallbackToPasscode: false,
          userCancellationConfigurable: true,
        }
      );

      return {
        success: true,
        signature,
      };
    } catch (err: any) {
      return {
        success: false,
        errorCode: this.mapErrorCode(err.code),
      };
    }
  }

  private static mapErrorCode(code: string): BiometricAuthResult['errorCode'] {
    switch (code) {
      case '13': // Android BiometricConstants.ERROR_NEGATIVE_BUTTON
      case '10': // iOS LAErrorUserCancel
        return 'USER_CANCELED';
      case '7':  // Android BIOMETRIC_ERROR_LOCKOUT
      case '8':  // iOS LAErrorBiometryLockout
        return 'LOCKOUT';
      default:
        return 'HARDWARE_UNAVAILABLE';
    }
  }
}
```

---

## 8. Real-World Case Study (Enterprise Scale)

### Skenario: "SwiftRoute Logistik" (Armada 15.000 Truk Ekspedisi)

* **Masalah:** Aplikasi driver mengalami 4.2% daily crash rate karena High Memory Usage (OOM). Baterai perangkat driver habis dalam waktu 4 jam operasional. Tim compliance membutuhkan data telematika (GPS, deteksi tabrakan/rem mendadak) yang terverifikasi secara hukum (*tamper-proof*).
* **Akar Masalah (Root Cause Analysis):**
  1. Modul GPS pihak ketiga mengirimkan event via React Native bridge lama pada frekuensi 1Hz per detik tanpa adaptive throttling saat kendaraan macet/berhenti.
  2. Kamera OCR untuk auto-scan waybill menggunakan bridge-based base64 snapshot string (`capture({ base64: true })`), mengalokasikan ~15MB memory per capture frame pada V8/Hermes heap.
  3. Ketiadaan foreground service yang benar pada Android menyebabkan Android System membunuh process secara acak di latar belakang (*LowMemoryKiller / Background Restricted App Status*).
* **Solusi Arsitektur Produksi:**
  1. **Adaptive Sampling Engine:** Mengubah frekuensi GPS menjadi 0.05Hz saat akselerometer mendeteksi kendaraan statis ($v < 1 \text{ km/h}$), menghemat 64% konsumsi baterai harian.
  2. **VisionCamera JSI Frame Processors:** Mengganti snapshot base64 dengan C++ MLKit Worklet. Frame buffer diakses langsung di memori native tanpa bridging string base64. Crash rate drop ke 0.02%.
  3. **Foreground Service Android Terproteksi:** Implementasi Sticky Notification dengan channel berprioritas tinggi dan `START_STICKY` service flag.

---

## 9. Trade-offs

| Pendekatan / Teknologi | Keuntungan (Pros) | Biaya & Kompromi (Cons / Trade-offs) |
| :--- | :--- | :--- |
| **JSI Worklets Frame Processing** | Zero-copy access ke image buffer, frame rate 60 FPS konsisten, minimal memory footprints. | Kompleksitas tinggi (butuh tooling C++/Obj-C++/CMake), debugging stack trace jauh lebih sulit jika terjadi memory fault/segmentation fault. |
| **Continuous High-Accuracy GPS (`kCLLocationAccuracyBest`)** | Navigasi level meter, akurasi tinggi untuk deteksi lane kendaraan. | Konsumsi baterai masif (~25-35% per jam), thermal throttling perangkat cepat tercapai, memicu pembatasan background oleh OS. |
| **Pure JS In-Memory Filtering** | Portabel, tanpa native binding khusus, mudah di-test menggunakan Jest standar. | CPU contention di JS thread; jika JS thread sibuk me-render virtual list complex, sensor frame update akan *starve* dan menyebabkan false drift. |
| **Secure Enclave Signed Payload** | Anti-tamper kriptografis, legal non-repudiation, tidak dapat di-spoof oleh rooted/jailbroken devices. | Latensi native processing (~50-250ms), UI sistem biometrik native memotong alur pengguna (intrusive). |

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Kesalahan Fatal Arsitektur

1. **Unregistered Native Listeners:** Mengaktifkan event listener hardware (`DeviceEventEmitter` atau native emitter) di dalam custom hook tanpa cleanup function pada `useEffect`. Hasil: Pembacaan sensor tetap aktif di background, menghabiskan baterai pengguna secara senyap.
2. **JSON Serialization Over the Bridge:** Mengirim data sensor mentah (IMU 100Hz) sebagai JSON Array melalui native bridge lama. Menyebabkan Hermes GC engine meledak dan UI freeze.
3. **Android 14+ Foreground Service Crashing:** Memanggil `startForegroundService()` tanpa mendeklarasikan `android:foregroundServiceType` yang sesuai di `AndroidManifest.xml` dan runtime permission `FOREGROUND_SERVICE_LOCATION`. Aplikasi akan langsung mengalami `ForegroundServiceStartNotAllowedException` atau crash fatal.

### 10.2. Panduan Troubleshooting

* **Gejala: Memory Leak pada Streaming Sensor Terus-menerus**
  * *Investigasi:* Periksa Heap snapshot di Hermes debugger / Flipper. Jika retained size bertambah seiring waktu, pastikan Anda tidak menambahkan array frame mentah ke array state React tanpa rolling limitation.
  * *Solusi:* Terapkan static bounded Ring Buffer (misal: panjang konstan 100 element) menggunakan TypedArray (`Float32Array`).
* **Gejala: Lokasi Background Terhenti Setelah 15 Menit di Android**
  * *Investigasi:* Buka `adb logcat | grep "Doze"`. Periksa apakah perangkat masuk ke deep sleep Doze mode.
  * *Solusi:* Implementasikan integrasi `PowerManager.isDeviceIdleMode()` dan request ignoransi optimasi baterai (`ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`) jika aplikasi masuk kategori white-listed enterprise mission-critical.

---

## 11. Best Practices (Production Checklist)

### Native Permissions & Lifecycle
- [ ] Mengimplementasikan runtime request logic terpisah untuk `ACCESS_COARSE_LOCATION`, `ACCESS_FINE_LOCATION`, dan `ACCESS_BACKGROUND_LOCATION` (Android tidak mengizinkan request background location bersamaan dengan fine location di Android 11+).
- [ ] Memastikan `UIBackgroundModes` berisi `location` dan `processing` pada `Info.plist` (iOS).
- [ ] Menyediakan fallback logic ketika permission ditolak secara permanen (`Never Ask Again`), mengarahkan pengguna secara elegan ke `Linking.openSettings()`.

### Resource & Power Management
- [ ] Menggunakan Sensor Fusion complementary filter untuk meminimalkan ketergantungan pada hardware GPS continuous.
- [ ] Memastikan seluruh listener native di-deregister saat aplikasi masuk ke state `inactive`/`background`, kecuali jika fitur background eksplisit aktif.
- [ ] Mengatur `distanceFilter` minimal 5-10 meter untuk penggunaan outdoor automotive tracking.

### Security & Compliance
- [ ] Seluruh data sensor telematika di local storage dienkripsi menggunakan AES-256 GCM dengan key yang disimpan di Secure Enclave / Keystore.
- [ ] Sensor telematika tidak boleh mencatat identifier PII langsung di buffer mentah yang belum terenkripsi.

---

## 12. Hands-on Practice

Simpan seluruh file praktikum di direktori: `hands-on/m02/`

### Struktur File

```
hands-on/m02/
├── package.json
├── tsconfig.json
├── AndroidManifest.partial.xml
├── Info.partial.plist
└── src/
    ├── AdaptiveLocationService.ts
    └── RingBuffer.ts
```

### Langkah 1: Inisialisasi Typed Buffer (`src/RingBuffer.ts`)

```typescript
export class Float64RingBuffer {
  private buffer: Float64Array;
  private pointer = 0;
  private isFull = false;

  constructor(private readonly capacity: number) {
    this.buffer = new Float64Array(capacity);
  }

  public push(value: number): void {
    this.buffer[this.pointer] = value;
    this.pointer = (this.pointer + 1) % this.capacity;
    if (this.pointer === 0) {
      this.isFull = true;
    }
  }

  public getAverage(): number {
    const size = this.isFull ? this.capacity : this.pointer;
    if (size === 0) return 0;
    
    let sum = 0;
    for (let i = 0; i < size; i++) {
      sum += this.buffer[i];
    }
    return sum / size;
  }

  public clear(): void {
    this.pointer = 0;
    this.isFull = false;
    this.buffer.fill(0);
  }
}
```

### Langkah 2: Layanan Lokasi Adaptif (`src/AdaptiveLocationService.ts`)

```typescript
import { Float64RingBuffer } from './RingBuffer';

export type AccuracyMode = 'HIGH_PRECISION' | 'POWER_SAVER' | 'IDLE';

export interface LocationReading {
  latitude: number;
  longitude: number;
  speed: number;
  timestamp: number;
}

export class AdaptiveLocationService {
  private speedBuffer = new Float64RingBuffer(10);
  private currentMode: AccuracyMode = 'IDLE';

  public evaluateMotionState(speedKmh: number): AccuracyMode {
    this.speedBuffer.push(speedKmh);
    const avgSpeed = this.speedBuffer.getAverage();

    if (avgSpeed > 20) {
      this.currentMode = 'HIGH_PRECISION';
    } else if (avgSpeed > 3) {
      this.currentMode = 'POWER_SAVER';
    } else {
      this.currentMode = 'IDLE';
    }

    return this.currentMode;
  }

  public getSamplingConfiguration(mode: AccuracyMode) {
    switch (mode) {
      case 'HIGH_PRECISION':
        return { intervalMs: 1000, distanceFilterMetres: 2 };
      case 'POWER_SAVER':
        return { intervalMs: 5000, distanceFilterMetres: 15 };
      case 'IDLE':
        return { intervalMs: 30000, distanceFilterMetres: 50 };
    }
  }
}
```

### Langkah 3: Konfigurasi Manifest & Info.plist

#### `AndroidManifest.partial.xml`
```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
    <uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION" />
    <uses-permission android:name="android.permission.ACCESS_BACKGROUND_LOCATION" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_LOCATION" />
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />

    <application>
        <service 
            android:name="com.enterprise.telematics.ForegroundLocationService"
            android:foregroundServiceType="location"
            android:exported="false" />
    </application>
</manifest>
```

#### `Info.partial.plist`
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>NSLocationWhenInUseUsageDescription</key>
    <string>Aplikasi memerlukan lokasi untuk navigasi pengiriman barang.</string>
    <key>NSLocationAlwaysAndWhenInUseUsageDescription</key>
    <string>Telematika pengiriman butuh koordinat latar belakang untuk validasi rute.</string>
    <key>UIBackgroundModes</key>
    <array>
        <string>location</string>
        <string>processing</string>
    </array>
</dict>
</plist>
```

---

## 13. Exercises

### Level Easy
Tulis sebuah TypeScript pure function `calculateDistanceHaversine(lat1: number, lon1: number, lat2: number, lon2: number): number` yang menghitung jarak antara dua koordinat geografis dalam satuan meter. Pastikan tidak ada floating point precision breakdown pada input ekstrem.

### Level Medium
Buat custom React Hook `useHardwareStepCounter()` yang berlangganan pada native step counter sensor. Hook harus mengimplementasikan debouncing logic dan otomatis mematikan subscription native saat component di-unmount atau layar masuk ke unfocused state menggunakan React Navigation lifecycle.

### Level Hard
Rancang modul TypeScript `BiometricProtectedSessionToken` yang melakukan enkripsi token sesi pengguna menggunakan WebCrypto / Native Crypto. Key encryption harus di-derive langsung dari native hardware biometrics prompt. Jika user membatalkan prompt atau proteksi biometrik diubah di level settings OS (misal: sidik jari baru ditambahkan), token otomatis hangus (invalidated).

---

## 14. Challenge (Tantangan Kasus Kompleks)

**Studi Kasus:** "Cold-Chain Logistics Offline Telemetry Collector"  
Aplikasi terpasang pada tablet Android/iOS di dalam kontainer pendingin pengiriman vaksin lintas pulau dengan spesifikasi skenario:
1. Perangkat berada di laut lepas tanpa konektivitas seluler/internet selama 7 hari berturut-turut.
2. Modul harus mencatat koordinat GPS (eksternal Bluetooth GPS), suhu via BLE (Bluetooth Low Energy), dan akselerometer 3D (goncangan kontainer) secara serentak setiap 10 detik.
3. Total batas memori alokasi database offline tidak boleh melebihi 150MB.

**Instruksi Rekayasa:**
* Desain arsitektur penyimpanan ring buffer menggunakan SQLite / C++ MMKV.
* Terapkan algoritma kompresi delta (misal: Delta-of-Delta timestamp & coordinate packing) sebelum persistensi data mentah.
* Tulis dokumen arsitektur teknis dan diagram status flow penanganan memori kritis saat storage mencapai batas kuota 150MB tanpa menghilangkan data anomali goncangan ekstrem ($>2.5G$).

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Basic (Pilihan Ganda / Konseptual)

1. **Mengapa New Architecture (JSI) lebih unggul daripada Old Architecture Bridge untuk pengolahan sensor kontinu?**
   * A. Karena JSI mengubah JavaScript menjadi bahasa multi-thread secara otomatis.
   * B. Karena JSI meniadakan kebutuhan alokasi dan serialisasi JSON melalui direct C++ pointers.
   * C. Karena JSI menghapus ketergantungan pada native runtime Android dan iOS.
   * D. Karena JSI meningkatkan kapasitas daya tahan baterai hingga 100%.

2. **Attribute mandatory apa yang harus dideklarasikan di `AndroidManifest.xml` (API Level $\ge 34$) saat menjalankan Background Location Service?**
   * A. `android:serviceType="sensor"`
   * B. `android:foregroundServiceType="location"`
   * C. `android:backgroundExecution="allow"`
   * D. `android:priority="max"`

3. **Komponen apa di platform iOS yang bertugas menyimpan cryptographic key yang diisolasi secara hardware dari main application processor?**
   * A. CoreLocation Framework
   * B. Secure Enclave
   * C. NSUserDefaults
   * D. File Protection Complete

4. **Metode optimasi manakah yang paling efektif mencegah Garbage Collection (GC) churn saat streaming sensor data 60Hz ke UI?**
   * A. Menggunakan `useState` untuk setiap frame yang masuk.
   * B. Mengalokasikan object baru via `Object.assign` di setiap payload.
   * C. Menggunakan reusable static TypedArrays (seperti `Float64Array`) dan ring buffers.
   * D. Memanggil `global.gc()` secara manual setiap 1 detik.

5. **Apa fungsi utama dari High-Pass Filter pada pemrosesan sinyal data akselerometer mentah?**
   * A. Mengisolasi akselerasi linier dengan membuang gravitasi konstan bumi.
   * B. Menghilangkan pergerakan dinamis pengguna dan hanya menyisakan gravitasi.
   * C. Meningkatkan sampling rate frekuensi sensor secara artifisial.
   * D. Mengurangi konsumsi baterai hardware accelerometer.

---

### Bagian B: Intermediate (Analisis Arsitektur)

6. Jelaskan apa yang terjadi jika Anda memanggil fungsi native via JSI secara sinkronus (`synchronous execution`) pada operasi komputasi sensor yang berat (durasi eksekusi native: 40ms). Bagaimana dampaknya terhadap frame rate (FPS) layar React Native?
7. Pada iOS, mengapa property `showsBackgroundLocationIndicator = true` wajib diatur jika aplikasi Anda meminta izin `location` di background?
8. Bagaimana VisionCamera Frame Processors memanfaatkan arsitektur *Worklet* untuk mengeksekusi inferensi computer vision tanpa memblokir interaksi gestur pengguna pada layar utama?
9. Jelaskan perbedaan struktural antara LowMemoryKiller (LMK) di Android dan Jetsam Event di iOS saat aplikasi mobile melakukan background location streaming dengan memory footprint yang besar.
10. Mengapa data koordinat GPS yang diambil tepat setelah perangkat bergerak dari kondisi diam sering kali memiliki error radius (inaccuracy) yang tinggi, dan bagaimana Complementary Filter mengatasi hal ini?

---

### Bagian C: Skenario Kasus Produksi

11. **Skenario 1:** Sebuah aplikasi kurir logistik mengalami bug: Driver melaporkan bahwa rute pengiriman menjadi garis lurus putus-putus (*teleportation*) saat ponsel mereka diletakkan di dashboard mobil dengan layar terkunci selama 10 menit di perangkat Android modern. Analisis penyebab level kernel OS-nya dan berikan solusi arsitekturalnya!
12. **Skenario 2:** Crash report dari sentry menunjukkan error `LAErrorBiometryLockout` secara sporadis pada 3% userbase saat mencoba login menggunakan hardware biometrics. Jelaskan akar masalahnya dan bagaimana UX state machine aplikasi harus merespons skenario ini secara aman tanpa merusak alur transaksi.
13. **Skenario 3:** Tim Anda mengembangkan fitur scan barcode live video 60 FPS. Di perangkat Android flagship app berjalan mulus, namun di perangkat Android low-end (RAM 2GB, Go Edition), aplikasi langsung force close (Crash OOM) setelah 5 detik kamera menyala. Desain strategi mitigasi adaptif native frame processing untuk mengatasi disparitas spek hardware ini!

---

## 16. Summary

Implementasi native hardware features dan sensor integration pada skala enterprise menuntut pemahaman arsitektural di bawah lapisan abstraksi React Native:
* **Perpindahan Paradigma:** Dari Bridge berbasis serialisasi asinkronus JSON ke **JSI & Worklets**, yang memungkinkan integrasi memori zero-copy untuk streaming berkecepatan tinggi (Camera frames, IMU, GPS).
* **Efisiensi Sumber Daya:** Kunci keberhasilan background tracking jangka panjang terletak pada **Adaptive Sampling Engine** yang memanfaatkan kombinasi inertial filtering (Low-pass/High-pass filter) untuk mematikan hardware berdaya tinggi saat idle.
* **Resiliensi Platform:** Mematuhi batasan lifecycle kedua OS—menggunakan Foreground Services dengan manifest type yang tepat di Android, serta mengelola Background Capabilities dan CoreLocation states secara presisi di iOS.
* **Zero-Allocation Execution:** Mencegah Garbage Collector starvation dengan menerapkan TypedArray buffers, static reuse strategy, dan delegasi pemrosesan komputasi berat ke C++ runtime.