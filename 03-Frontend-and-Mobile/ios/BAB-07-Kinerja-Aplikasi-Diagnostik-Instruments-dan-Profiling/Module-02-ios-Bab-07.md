# BAB-07 Kinerja Aplikasi, Diagnostik, Instruments, dan Profiling
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Mengidentifikasi, mengisolasi, dan memitigasi degradasi performa mikro (*micro-stutters*, *frame hitches*) dan makro (*memory thrashing*, *thermal throttling*) pada tingkat arsitektur sistem iOS.
- Menguasai instrumentasi diagnostik tingkat lanjut menggunakan kombinasi Apple Instruments (Time Profiler, Allocations, Leaks, System Trace, Core Animation FPS) dan instrumentasi runtime berbasis `os_signpost` / `OSSignposter`.
- Merancang dan mengimplementasikan telemetri performa sisi klien (*client-side APM*) secara non-intrusif menggunakan `MetricKit` yang terintegrasi dengan pipeline analitik terdistribusi.
- Menganalisis topologi memori iOS (Mach kernel memory subsystems: *Clean*, *Dirty*, *Compressed memory*) dan mekanisme *Jetsam* guna mencegah crash berbasis *OOM (Out Of Memory)*.
- Mengotomatisasi validasi performa (Hitch Rate, Launch Time, Allocations) ke dalam pipeline *Continuous Integration* (CI/CD) menggunakan `XCTest` Metric APIs.

---

### 2. Prerequisite
Untuk memahami materi ini secara optimal, Anda wajib menguasai:
- **Swift Concurrency & Threading Low-Level**: `Task`, `Actor`, GCD (`DispatchQueue`), `os_unfair_lock`, serta model eksekusi *Mach thread* dan *RunLoop*.
- **ARC (Automatic Reference Counting) Internals**: Representasi *Reference Count* di *Side Table* vs *Inline Pointer*, *Strong Reference Cycles*, `unowned`, `weak`, dan *Capture Lists*.
- **Konsep Dasar Modul 01**: Penggunaan dasar Xcode Profiler, Instruments template standar, dan navigasi antarmuka Instruments.
- **Sistem Operasi Fundamental**: Virtual Memory Management, Paging, Page Faults, CPU Scheduling, State Machine Thread.

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Arsitektur Memori Mach Kernel & Mekanisme Jetsam
iOS tidak memiliki mekanisme swap file sekunder konvensional (disk paging) seperti macOS. Ketika kapasitas memori fisik (RAM) terbatas, kernel Mach menggunakan pendekatan terstruktur:

```
[Total Physical RAM]
 ├── Clean Memory      : Halaman read-only (binary text segment, dylib static data, mmap file read-only)
 │                       -> Dapat di-purge oleh kernel kapan saja dan di-reload dari storage.
 ├── Compressed Memory : Halaman dirty yang dikompresi oleh VM compressor saat idle.
 └── Dirty Memory       : Alokasi heap objek (malloc), decoded bitmaps, dynamic structures.
                         -> TIDAK BISA di-purge tanpa menghentikan proses.
```

Total Footprint Formula yang digunakan iOS Memory Monitor:
$$\text{Memory Footprint} = \text{Dirty Memory} + \text{Compressed Memory}$$

Jika total memory footprint melewati batas kuota proses (*high-water mark*), kernel Mach mengirim sinyal memory warning (`OSMemoryNotificationEvent`). Jika footprint terus meningkat, subsistem **Jetsam** (bagian dari `memorystatus`) mengeksekusi *kill signal* (`EXC_RESOURCE` atau `SIGKILL` dengan kode terminasi `0x8badf00d` atau `0xdead10cc` / Jetsam event reason) pada proses dengan prioritas paling rendah via algoritma `memorystatus_sort_by_high_bandwidth()`.

#### B. Pipeline Core Animation & Anatomi Frame Hitch
UI iOS dirender pada refresh rate 60Hz (16.67ms per frame) atau 120Hz ProMotion (8.33ms per frame).

```
[ App Process: Main RunLoop ]
  Layout -> Display -> Prepare Subviews -> Commit Transaction
                                              │
                                              ▼ (IPC via Mach Port)
[ Render Server (backboardd / WindowServer) ]
  Decode -> Render Pipeline Setup -> Draw Commands
                                              │
                                              ▼ (Metal Pipeline)
[ GPU Processing & Display Engine ]
  V-Sync Signal Trigger Frame Swap
```

1. **Commit Phase (Main Thread)**: Pembaruan layer hierarchy, layout autolayout calculations (`layoutSubviews`), dan visual snapshot preparation.
2. **Render Server Phase**: Backboardd menerima tree transaction, mendekomposisikan layer tree menjadi primitive draw calls menggunakan GPU Metal pipeline.
3. **Execution Phase**: GPU mengeksekusi rasterization dan swap buffer ke display controller saat sinyal *V-Sync* diterima.

Sebuah **Hitch** terjadi apabila *frame interval delta* ($T_{\text{display}} - T_{\text{target}}$) $> 0$. Apple mendefinisikannya menjadi dua kategori:
- **Commit Hitch**: Main thread app terblokir lebih lama dari frame budget ($>8.33\text{ms}$ / $>16.67\text{ms}$), menunda pengiriman transaksi ke Render Server.
- **Render Hitch**: Render Server atau GPU kehabisan waktu untuk merender frame yang telah di-commit sebelum siklus V-Sync berikutnya.

Metric standar industri:
$$\text{Hitch Time Ratio} = \frac{\sum \text{Durasi Hitch (ms)}}{\sum \text{Durasi Presentasi UI (s)}}$$

#### C. Mekanisme Low-Overhead Tracing: `os_signpost`
Berbeda dengan print statement atau logging berbasis network HTTP yang memakan I/O dan alokasi heap masif, `os_signpost` memanfaatkan subsistem **Unified Logging Platform (ULP)**.
- Data ditulis langsung ke ring-buffer di kernel memory.
- Zero-heap allocation path untuk string format statis.
- Argumen dinamis diserialisasi menggunakan byte-copy berukuran minimum.
- Hanya di-decode menjadi representasi string manusia jika Instruments disambungkan atau via konsol log streaming.

---

### 4. Why & What

| Dimensi | Mengapa Dibutuhkan (Why) | Apa yang Diterapkan (What) |
| :--- | :--- | :--- |
| **User Experience (Retention)** | Penurunan 10% hitch rate berkorelasi langsung dengan peningkatan engagement dan penurunan churn rate pada transaksi checkout. | Eliminasi main thread I/O, downsampling bitmap rendering di background thread, dan layout caching. |
| **System Health (Crash Rate)** | Terminasi OOM Jetsam tidak meninggalkan Apple Crash Report standar (`.ips`), membuat crash rate seolah rendah padahal pengguna mengalami *silent drops*. | Monitoring `os_proc_available_memory()`, MetricKit `MXCrashDiagnostic`, dan pereduksian agresif Dirty Memory. |
| **Battery Life & Thermals** | CPU spikes yang konstan memicu *Thermal State: Critical*, yang menyebabkan CPU throttling OS dan degradasi frame rate sistemik. | Thread affinity stabilization, coalescing async dispatch, dan eliminasi lock contention. |
| **Continuous Verification** | Regresi performa sering kali tidak terdeteksi via Unit Test standar dan lolos hingga production release. | Integrasi `XCTMetric` (OSSignpostMetric, MemoryMetric, CPUProfileMetric) ke pipeline CI/CD. |

---

### 5. How (Workflow Detail)

Berikut adalah alur diagnostik menyeluruh yang diterapkan di lingkungan enterprise:

```
[Phase 1: Detection]
   ├── MetricKit APM Telemetry (Production Payload Aggregate)
   └── XCTest Performance Regression Failure (CI Level)
             │
             ▼
[Phase 2: Isolation & Reproducibility]
   ├── Local Profiling (Release/Profiling Build Configuration)
   ├── Lock CPU Frequency & Thermal State via Instruments
   └── Instrument Selection:
         ├── Time Profiler (Main RunLoop Stalls & CPU Cycles)
         ├── Allocations & Leaks (Dirty Memory Accumulation)
         └── System Trace (Thread Scheduling & Syscall Blocks)
             │
             ▼
[Phase 3: Root Cause Analysis]
   ├── Time Profiler: Invert Call Tree, Hide System Libraries
   ├── Allocations: Generation Analysis (Mark Generation before/after flow)
   └── System Trace: Virtual Memory Page Faults & Mutex Lock Contention
             │
             ▼
[Phase 4: Remediation & Proof]
   ├── Architectural decoupling (Offload from main thread, memory footprint optimization)
   └── Comparative trace analysis before vs after remediation
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Arsitektur Restoran Bintang Lima

Bayangkan sebuah restoran berbintang:
- **Main Thread (Head Chef)**: Bertugas menaruh garnish akhir dan menyajikan hidangan ke meja pelayan (Display/Render Server). Jika Head Chef dipaksa mencuci piring (parsing JSON) atau memotong bawang mentah (decode JPEG berukuran besar), antrean makanan terhenti (*Frame Hitch*).
- **Background Threads (Prep Cooks)**: Memotong daging, merebus kaldu, dan menyiapkan bahan dasar di dapur belakang (offloading data processing).
- **Jetsam (Inspektur Kebakaran / Fire Marshall)**: Dapur memiliki batas kapasitas beban ruang (*Dirty Memory Limit*). Jika koki membawa terlalu banyak tumpukan kardus bahan mentah ke lorong dapur, Inspektur tidak memberi peringatan kedua; ia langsung membunyikan alarm dan menutup restoran secara paksa (*Jetsam Termination*).

#### Diagram Transisi Eksekusi RunLoop & Hitch Point

```
V-Sync Timeline:
|--------------- 16.67ms ---------------|--------------- 16.67ms ---------------|
[Frame N: Commit] -> [Render Server]   [Frame N+1: Commit] -> [Render Server]
=================================================================================
KASUS A: Smooth Pipeline
Main Thread: |--Layout--|--Draw--|--Idle--| |--Layout--|--Draw--|--Idle--|
Display    : [Frame N-1 Presenting        ] [Frame N Presenting          ]

KASUS B: Frame Hitch (Main Thread Stall / Long Commit)
Main Thread: |--Layout--|----Heavy JSON Parsing & Sync Lock----|-> STALL -> Commit
Display    : [Frame N-1 Presenting        ] [Frame N-1 DUPLICATED DURATION (HITCH)]
                                            ^
                                            Frame N+1 terlambat dikirim ke GPU!
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Menggunakan `OSSignposter` untuk Mengukur Sub-Sistem
Mengukur durasi operasi asinkron spesifik tanpa overhead alokasi memori.

```swift
import Foundation
import OSLog

final class ImageProcessingPipeline {
    private static let subsystem = Bundle.main.bundleIdentifier ?? "com.enterprise.app"
    private let logger = Logger(subsystem: subsystem, category: "ImagePipeline")
    private let signposter = OSSignposter(subsystem: subsystem, category: "ImagePipeline")

    func processImage(data: Data) async throws -> CGImage {
        let signpostID = signposter.makeSignpostID()
        let state = signposter.beginInterval("ProcessImageData", id: signpostID, "Payload bytes: %{public}d", data.count)
        
        defer {
            signposter.endInterval("ProcessImageData", state, "Status: Complete")
        }

        // Simulating memory footprint-sensitive transformation
        return try await withCheckedThrowingContinuation { continuation in
            DispatchQueue.global(qos: .userInitiated).async {
                guard let provider = CGDataProvider(data: data as CFData),
                      let imageSource = CGImageSourceCreateWithData(data as CFData, nil),
                      let cgImage = CGImageSourceCreateImageAtIndex(imageSource, 0, nil) else {
                    continuation.resume(throwing: CocoaError(.fileReadCorruptFile))
                    return
                }
                continuation.resume(returning: cgImage)
            }
        }
    }
}
```

#### Practical Example: Arsitektur Produksi Telemetri Performa Terdistribusi (MetricKit + Low-Memory Watchdog)

```swift
import Foundation
import MetricKit
import OSLog

// MARK: - Memory Footprint Inspection Utility
public struct ProcessMemoryInfo {
    public static func currentUsageBytes() -> UInt64 {
        var info = mach_task_basic_info()
        var count = mach_msg_type_number_t(MemoryLayout<mach_task_basic_info>.size / MemoryLayout<natural_t>.size)
        let kerr: kern_return_t = withUnsafeMutablePointer(to: &info) {
            $0.withMemoryRebound(to: integer_t.self, capacity: Int(count)) {
                task_info(mach_task_self_, task_flavor_t(MACH_TASK_BASIC_INFO), $0, &count)
            }
        }
        return kerr == KERN_SUCCESS ? UInt64(info.resident_size) : 0
    }
}

// MARK: - Enterprise MetricKit Subscriber Pipeline
public final class PerformanceTelemetryManager: NSObject, MXMetricManagerSubscriber {
    public static let shared = PerformanceTelemetryManager()
    
    private let logger = Logger(subsystem: "com.enterprise.telemetry", category: "APM")
    private let isolationQueue = DispatchQueue(label: "com.enterprise.telemetry.queue", qos: .utility)
    
    private override init() {
        super.init()
    }
    
    public func startMonitoring() {
        MXMetricManager.shared.add(self)
        registerThermalNotification()
    }
    
    public func stopMonitoring() {
        MXMetricManager.shared.remove(self)
        NotificationCenter.default.removeObserver(self)
    }
    
    // MARK: - MXMetricManagerSubscriber Protocol
    public func didReceive(_ payloads: [MXMetricPayload]) {
        isolationQueue.async { [weak self] in
            guard let self = self else { return }
            for payload in payloads {
                self.processMetricPayload(payload)
            }
        }
    }
    
    public func didReceive(_ payloads: [MXDiagnosticPayload]) {
        isolationQueue.async { [weak self] in
            guard let self = self else { return }
            for payload in payloads {
                self.processDiagnosticPayload(payload)
            }
        }
    }
    
    // MARK: - Internal Processors
    private func processMetricPayload(_ payload: MXMetricPayload) {
        if let displayMetrics = payload.displayMetrics {
            logger.info("Display Hitch Ratio Reported: \(displayMetrics.averagePixelThroughput?.description ?? "N/A")")
        }
        
        if let memoryMetrics = payload.memoryMetrics {
            let peakMemory = memoryMetrics.peakMemoryUsage.value
            let averageMemory = memoryMetrics.averageSuspendedMemory.averageMeasurement.value
            logger.info("Memory Profile: Peak=\(peakMemory) bytes, Suspended Avg=\(averageMemory) bytes")
            
            // Evaluasi batas Dirty Memory
            if peakMemory > (400 * 1024 * 1024) { // 400 MB threshold
                self.dispatchMemoryAlertToBackend(peakBytes: peakMemory)
            }
        }
    }
    
    private func processDiagnosticPayload(_ payload: MXDiagnosticPayload) {
        if let crashDiagnostics = payload.crashDiagnostics {
            for crash in crashDiagnostics {
                let callStack = crash.callStackTree
                let signal = crash.exceptionCode ?? 0
                logger.error("MetricKit Crash captured! Code: \(signal), CallStack: \(callStack.jsonRepresentation())")
            }
        }
        
        if let hangDiagnostics = payload.hangDiagnostics {
            for hang in hangDiagnostics {
                logger.warning("Main thread Hang captured. Duration: \(hang.hangDuration.value) ms")
            }
        }
    }
    
    private func registerThermalNotification() {
        NotificationCenter.default.addObserver(
            forName: ProcessInfo.thermalStateDidChangeNotification,
            object: nil,
            queue: .main
        ) { _ in
            let state = ProcessInfo.processInfo.thermalState
            switch state {
            case .critical, .serious:
                // Kurangi concurrency level, hentikan expensive background task segera!
                NotificationCenter.default.post(name: .reduceMemoryBudgetForThermalEvent, object: state)
            default:
                break
            }
        }
    }
    
    private func dispatchMemoryAlertToBackend(peakBytes: Double) {
        // Enqueue telemetry payload via non-blocking background network path
    }
}

public extension Notification.Name {
    static let reduceMemoryBudgetForThermalEvent = Notification.Name("reduceMemoryBudgetForThermalEvent")
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: SuperApp E-Commerce (15+ Juta Monthly Active Users)
**Symptom**: Pengguna iPhone tipe reguler (iPhone 11 & 12, RAM 4GB) mengalami lonjakan terminasi mendadak (*silent app termination*) ketika melakukan *endless scroll* pada katalog produk "Mega Sale" yang memiliki format UI majemuk (Video Player + Carousel Gambar Beresolusi Tinggi + Chat Widget Floating). Metric crash standard (`EXC_BAD_ACCESS`) tidak muncul di Firebase Crashlytics.

**Investigasi**:
1. **Profiling Menggunakan Instruments (Allocations + Leaks)**:
   - Menjalankan skenario *Generation Analysis*. Mark Generation 1 sebelum scroll, Mark Generation 2 setelah scroll 100 cell.
   - Hasil: Alokasi `CGImageRef` dan `CALayer` meningkat secara linier sebesar 450 MB dalam kurun waktu 30 detik.
   - Analisis pointer: Image caching layer menyimpan instance `UIImage` hasil decode asli (resolusi kamera 4032x3024) secara penuh di dalam heap memory berformat decompressed ARGB8888 ($4032 \times 3024 \times 4 \text{ bytes} \approx 48.7 \text{ MB per image}$), meskipun display view hanya berukuran $120 \times 120$ point.
2. **System Trace Identification**:
   - Terdeteksi page fault badai (*high-rate minor/major page faults*) saat RunLoop mencoba meregister subview baru.
   - Mach kernel VM mengirim status memory pressure level `.critical`, lalu mengeksekusi sinyal **Jetsam Kill** (kode terminasi: `0xdead10cc` / Memory Pressure Exit).

**Solusi & Remediasi Arsitektur**:
1. **Image Downsampling Streaming**: Membaca file source langsung menggunakan Image I/O tanpa mendekompresi keseluruhan file ke RAM menggunakan opsi `kCGImageSourceCreateThumbnailWithImageMaxPixelSize`.
2. **Auto-Purging Memory Cache**: Mengganti native dictionary dengan `NSCache` yang mereferensikan disk cache berbasis LRU (*Least Recently Used*), serta memicu explicit eviction ketika `UIApplication.didReceiveMemoryWarningNotification` di-broadcast.
3. **Decoupled View Recycling**: Menghapus background video playback context saat cell keluar dari visible screen area.

**Dampak**:
- Total Dirty Memory menurun dari 650 MB menjadi 110 MB saat scrolling kontinu.
- Crash Jetsam OOM turun 94% pada perangkat RAM 3GB-4GB.
- Hitch Rate menurun dari 18.2 ms/s ke 2.1 ms/s.

---

### 9. Trade-offs (Performance, Latency, Scalability, Cost)

| Keputusan Arsitektur | Keuntungan | Kerugian & Konsekuensi | Mitigasi |
| :--- | :--- | :--- | :--- |
| **Agresif Downsampling via CoreGraphics (Image I/O)** | Memory Dirty footprint turun drastis (hingga 80%). Mengeliminasi resiko OOM Jetsam. | Penggunaan siklus CPU bertambah sedikit saat kalkulasi downsampling on-the-fly. | Pindahkan komputasi downsampling ke background actor pool berprioritas `.utility`. |
| **Comprehensive Unified Logging (`os_signpost`)** | Visibilitas observabilitas granular di Instruments tanpa network bandwidth overhead. | Ukuran biner kompilasi sedikit membesar; disk write kecil jika persistensi debug diaktifkan. | Bungkus eksekusi signpost dalam compiler condition `#if DEBUG` atau environment flags dinamis. |
| **MetricKit In-App Telemetry Pipeline** | Menangkap crash diagnostik asli Jetsam OOM dan metric latensi riil pengguna (*field data*). | Payload hanya dikirim oleh sistem sekali per 24 jam secara batch (tidak *real-time*). | Kombinasikan MetricKit untuk analitik makro harian dengan custom breadcrumbs logging untuk tracing cepat. |
| **Offscreen Rendering Flattening (`shouldRasterize = true`)** | Menghindari re-komputasi bayangan (*shadows*) dan *corner radius* berulang pada static views. | Memakan video memory (VRAM) offscreen buffer cache; jika view dinamis, performa justru anjlok drastis. | Hanya terapkan pada static complex views dan selalu tentukan `rasterizationScale = UIScreen.main.scale`. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum (Anti-Patterns):
1. **Menggunakan `UIImage(named:)` untuk Asset Dinamis Skala Besar**: `UIImage(named:)` otomatis menempatkan gambar di system cache internal Apple yang tidak transparan dan tidak dapat dikontrol pengosongannya oleh developer, memicu pembengkakan Dirty Memory.
2. **Capture `self` secara Implisit dalam Task Concurrency Tanpa Memory Boundary**:
   ```swift
   // SALAH: Strong reference cycle via context retention
   Task {
       self.performHeavyComputation()
   }
   
   // BENAR:
   Task { [weak self] in
       guard let self = self else { return }
       self.performHeavyComputation()
   }
   ```
3. **Mengabaikan Offscreen Rendering**: Menggunakan `.cornerRadius` digabungkan dengan `masksToBounds = true` dan `shadowPath` yang nilainya tidak dispesifikasikan secara eksplisit memicu Core Animation membuat *Offscreen Render Pass* tambahan di GPU untuk setiap frame cycle.

#### Troubleshooting Matrix:
- **Gejala: Time Profiler menunjukkan spike pada `objc_msgSend`**.
  *Solusi*: Kurangi dynamic dispatch yang tidak perlu; gunakan keyword `final`, tandai method internal dengan `private`, dan implementasikan WMO (*Whole Module Optimization*).
- **Gejala: Leaks instrument mendeteksi leak tapi tidak ada retain cycle di kode Swift**.
  *Solusi*: Periksa interop C/C++ (Core Foundation, Core Graphics). Pastikan objek seperti `CGPath`, `CGContext`, atau `CVPixelBuffer` dilepas secara manual menggunakan fungsi CFRelease jika tidak dikelola oleh automatic bridging ARC.
- **Gejala: RunLoop Hang dilaporkan oleh MetricKit sebesar >250ms**.
  *Solusi*: Periksa akses disk database (Core Data / Realm / SQLite) atau deserialisasi JSON berukuran besar (`JSONDecoder`) yang berjalan secara sinkron pada main thread.

---

### 11. Best Practices (Production Checklist)

#### Pre-Release Performance Audit Checklist
- [ ] **No Unbounded Memory**: Pastikan proses alokasi data memori tidak bertumbuh secara linear tanpa batas saat scrolling daftar elemen tak terhingga (*unbounded lists*).
- [ ] **Hitch Rate Baseline**: Hitung Hitch Time Ratio pada target perangkat terendah (minimum supported device); pastikan Hitch Rate $< 5\text{ ms/s}$ (Target 60/120 FPS).
- [ ] **Image Optimization**: Tidak ada decoding raw bitmap pada Main Thread. Semua image presentation views menggunakan downsampling proporsional.
- [ ] **Shadow Path Definition**: Setiap layer yang menggunakan drop shadow wajib mendefinisikan `layer.shadowPath = UIBezierPath(...).cgPath`.
- [ ] **Lock Free Main Thread**: Pastikan main thread tidak pernah memanggil `DispatchQueue.sync`, `os_unfair_lock_lock`, atau semaphore wait yang dapat ditahan oleh background thread berprioritas rendah (*Priority Inversion*).
- [ ] **Memory Footprint Quota**: Uji batas memory footprint di bawah limit Jetsam profil perangkat terendah (misal: $<250\text{ MB}$ pada iPhone model legacy).

---

### 12. Hands-on Practice

Buat struktur direktori berikut di workspace lokal Anda:
`hands-on/m02/PerformanceLab/`

#### Langkah 1: Implementasi Downsampling Engine Efisien
Buat file `hands-on/m02/PerformanceLab/ImageDownsampler.swift`:

```swift
import UIKit
import ImageIO

public enum ImageDownsampler {
    public static func downsample(
        imageAt imageURL: URL,
        to pointSize: CGSize,
        scale: CGFloat = UIScreen.main.scale
    ) -> UIImage? {
        let maxDimensionInPixels = max(pointSize.width, pointSize.height) * scale
        let imageSourceOptions = [kCGImageSourceShouldCache: false] as CFDictionary
        
        guard let imageSource = CGImageSourceCreateWithURL(imageURL as CFURL, imageSourceOptions) else {
            return nil
        }
        
        let downsampleOptions = [
            kCGImageSourceCreateThumbnailFromImageAlways: true,
            kCGImageSourceShouldCacheImmediately: true,
            kCGImageSourceCreateThumbnailWithImageMaxPixelSize: maxDimensionInPixels
        ] as [CFString : Any] as CFDictionary
        
        guard let downsampledImage = CGImageSourceCreateThumbnailAtIndex(imageSource, 0, downsampleOptions) else {
            return nil
        }
        
        return UIImage(cgImage: downsampledImage)
    }
}
```

#### Langkah 2: Otomasi Pengujian Regresi Menggunakan `XCTest`
Buat file `hands-on/m02/PerformanceLab/PerformanceRegressionTests.swift`:

```swift
import XCTest

final class PerformanceRegressionTests: XCTestCase {
    
    func testScrollingPerformanceAndHitchRate() throws {
        let app = XCUIApplication()
        app.launchArguments.append("--uitesting-performance-mode")
        app.launch()
        
        let listTable = app.tables["CatalogTableView"]
        XCTAssertTrue(listTable.waitForExistence(timeout: 5.0))
        
        let metricOptions = XCTMeasureOptions()
        metricOptions.iterationCount = 5
        
        measure(
            metrics: [
                XCTOSSignpostMetric.scrollDecelerationMetric,
                XCTMemoryMetric(application: app),
                XCTCPUMetric(application: app)
            ],
            options: metricOptions
        ) {
            listTable.swipeUp(velocity: .fast)
            listTable.swipeDown(velocity: .fast)
        }
    }
}
```

#### Langkah 3: Profiling Menggunakan Command-Line Instruments
Jalankan kompilasi profil dan rekam trace memory tanpa antarmuka grafis untuk integrasi CI:
```bash
# 1. Build aplikasi untuk profiling
xcodebuild -workspace PerformanceLab.xcworkspace \
           -scheme PerformanceLab \
           -configuration Release \
           -sdk iphonesimulator \
           -destination 'platform=iOS Simulator,name=iPhone 15 Pro' \
           clean build

# 2. Record trace menggunakan xctrace tool
xcrun xctrace record \
      --template 'Allocations' \
      --device 'iPhone 15 Pro' \
      --all-processes \
      --time-limit 15s \
      --output ./hands-on/m02/TraceResults.trace
```

---

### 13. Exercise

#### Level Easy
Ubah implementasi layout berikut agar tidak memicu *Offscreen Rendering*:
```swift
// Kode Awal:
customView.layer.cornerRadius = 12.0
customView.layer.masksToBounds = true
customView.layer.shadowColor = UIColor.black.cgColor
customView.layer.shadowOpacity = 0.5
customView.layer.shadowOffset = CGSize(width: 0, height: 4)
```
*Tugas*: Dekomposisikan styling ini menggunakan layer struktur yang benar (`shadowPath` & background container view) tanpa memotong bayangan secara salah.

#### Level Medium
Sebuah sistem melakukan parsing file JSON seukuran 80MB secara berkala saat menerima WebSocket sync event. Ketika diuji pada perangkat, UI mengalami freeze selama 650ms.
*Tugas*: Rancang modul sinkronisasi berbasis Swift 6 Actor yang memotong JSON payload menjadi chunk stream (`AsyncThrowingStream`), memparsing model per segmen di background queue berprioritas rendah, dan memperbarui persistent container secara periodik tanpa memblokir RunLoop thread utama.

#### Level Hard
Deteksi dead-lock atau high lock contention secara dinamis pada level runtime.
*Tugas*: Rancang sebuah `LockContentionMonitor` menggunakan API POSIX thread (`pthread_introspection_hook_install`) atau `os_unfair_lock` wrapper yang mengukur waktu blokir thread saat mencoba mengakuisisi lock. Jika lock acquisition memakan waktu $> 16\text{ ms}$ pada thread utama, rekam stack trace lengkap thread tersebut dan simpan ke file crash disk lokal.

---

### 14. Challenge

**Studi Kasus Arsitektur Real-Time Financial Trading Terminal**:
Aplikasi Anda menampilkan buku pesanan (*Order Book*) bursa saham dengan update data via TCP socket mencapai 120 pesan per detik. Setiap pesan memperbarui tabel harga bid/ask dengan animasi visual.
- **Kondisi**:
  1. Main thread mengalami saturasi $100\%$ CPU, memicu frame rate anjlok ke 18 FPS.
  2. Suhu perangkat mencapai *Thermal State: Critical* dalam 3 menit penggunaan, memicu thermal throttling hingga frekuensi prosesor ditekan ke tingkat minimal.
  3. Dirty Memory terus meningkat akibat pembuatan ribuan objek struct/class formatting per detik.

**Misi Anda**:
Rancang dokumen arsitektur dan blue print kode lengkap yang mencakup:
- Mekanisme **Batching Engine** (*Time-Coalesced Throttling*) yang memadatkan update paket bursa tanpa kehilangan data audit.
- Model representasi memori flat (*Zero-Allocation Byte Parsing*) tanpa overhead Swift dynamic heap allocation.
- Sistem adaptasi rendering yang menyesuaikan refresh-rate target display secara dinamis berdasarkan `ProcessInfo.thermalState`.
*Catatan: Solusi tidak disediakan secara instan; selesaikan problem ini dengan prinsip-prinsip low-level yang telah dijabarkan.*

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Konsep Dasar (Basic)
1. Apa perbedaan mendasar antara *Clean Memory* dan *Dirty Memory* dalam arsitektur virtual memory Mach kernel iOS?
2. Mengapa sinyal terminasi akibat *Out-Of-Memory (OOM) Jetsam* sering kali tidak menghasilkan laporan crash di layanan crash reporting pihak ketiga konvensional?
3. Sebutkan perbedaan karakteristik antara *Commit Hitch* dan *Render Hitch*!
4. Mengapa method `UIImage(named:)` berisiko menyebabkan memory warning jika digunakan untuk memuat ribuan foto berukuran besar dari disk?
5. Apa keunggulan arsitektural penggunaan `os_signpost` dibandingkan pencatatan log tradisional berbasis runtime strings (`print` / `NSLog`)?

#### Bagian B: Analisis Lanjutan (Intermediate)
6. Bagaimana cara kerja algoritma *VM Compressor* pada iOS ketika sistem mengalami tekanan alokasi memori sebelum memicu terminasi Jetsam?
7. Mengapa operasi `layoutIfNeeded()` yang dipanggil berulang kali di dalam loop animasi dapat memicu *Layout Thrashing* dan *Frame Hitch*?
8. Bagaimana Anda memanfaatkan template *System Trace* di Instruments untuk mendeteksi *Priority Inversion* pada thread execution pool?
9. Mengapa opsi `kCGImageSourceShouldCacheImmediately` disetel ke `true` saat melakukan downsampling via Image I/O framework?
10. Bagaimana `MetricKit` menghemat konsumsi baterai perangkat saat mengumpulkan telemetri performa diagnostik aplikasi?

#### Bagian C: Skenario Kasus Produksi (Enterprise Scenario)
11. **Skenario 1**: Dashboard APM MetricKit Anda melaporkan bahwa *Launch Time (Resume from Suspended)* aplikasi melonjak dari median 400ms menjadi 1850ms setelah pembaruan versi rilis terbaru. Parameter apa yang pertama kali harus Anda telusuri di Instruments Time Profiler, dan kesalahan apa yang umumnya terjadi pada `didBecomeActive` state?
12. **Skenario 2**: Dalam sebuah feed aplikasi media sosial berbasis `UICollectionViewCompositionalLayout`, Instruments Core Animation menunjukkan *Hitch Rate* sebesar 24ms/s hanya pada perangkat ProMotion 120Hz (iPhone 13 Pro ke atas), sedangkan pada perangkat 60Hz feed berjalan mulus tanpa keluhan. Analisis mengapa hitch rate lebih rentan terlihat pada ProMotion display!
13. **Skenario 3**: Tim QA melaporkan terjadinya silent crash saat aplikasi diuji coba di background selama lebih dari 30 detik pada kondisi low battery mode. Tidak ada crash log di Xcode Organizer. Bagaimana Anda mendiagnosis bahwa ini merupakan pembunuhan proses oleh watchdog atau Jetsam, dan langkah mitigasi kode apa yang harus diterapkan?

---

### 16. Summary

Optimalisasi kinerja pada platform iOS bukan sekadar proses perbaikan reaktif (*bug fixing*), melainkan fondasi arsitektur sistem perangkat lunak modern. Memahami interaksi antara **Mach Kernel Memory Subsystems**, **Core Animation Frame Pipelines**, dan **RunLoop Thread Scheduling** memungkinkan *Senior Engineer* mendeteksi bottleneck sebelum mencapai lingkungan produksi.

Penggunaan instrumen presisi tinggi seperti Apple Instruments (Time Profiler, Allocations, System Trace), instrumentasi non-intrusif menggunakan `os_signpost`, dan pengumpulan telemetri lapangan agregat via `MetricKit` memastikan aplikasi berskala enterprise tetap responsif, efisien dalam penggunaan daya, dan tahan terhadap terminasi mendadak sistemik (*Jetsam OOM*). Otomasi audit performa ke dalam Continuous Integration pipeline menjamin standar kualitas aplikasi tidak mengalami regresi seiring bertambahnya kompleksitas codebase.