# MODUL PEMBELAJARAN TEKNIS: IOS ADVANCED ARCHITECTURE

---

## SEKSI 01 — IDENTITAS MODUL

* **Jalur Kurikulum:** 03-Frontend-and-Mobile
* **Teknologi:** iOS (Swift, SwiftUI/UIKit, Metal Pipeline, Darwin Kernel)
* **Bab:** 07 — Kinerja Sistem, Diagnostik, & Telemetri Tingkat Rendah
* **Modul:** 01 — Kinerja Aplikasi, Diagnostik Instruments, & Profiling
* **Prasyarat Pengetahuan:** ARC (*Automatic Reference Counting*), GCD (*Grand Central Dispatch*), Swift Concurrency (`async`/`await`, Actors), Runtime Objective-C/Swift, Siklus Hidup Render Core Animation, Memory Layout (Stack vs Heap).

---

## SEKSI 02 — LEARNING OBJECTIVES

Pada akhir modul ini, Anda diharapkan mampu:

1. **Mengisolasi dan Mendiagnosis UI Hangs:** Mengidentifikasi latensi thread utama (*Main Thread Blocks*) menggunakan Time Profiler dan MetricKit, serta memetakan eksekusi ke batas anggaran frame 120Hz/60Hz (8.33ms / 16.67ms).
2. **Menganalisis Alokasi Memori Tingkat Rendah:** Membedakan jejak memori *Clean*, *Dirty*, dan *Compressed Memory*, serta merekonstruksi siklus referensi (*retain cycles*) dan memory leaks menggunakan Allocations & Leaks Instruments serta Graph Execution Memory.
3. **Mengoperasikan Diagnostic Instruments:** Menguasai profiling berbasis *Time Profiler*, *System Trace*, *Allocations*, *Leaks*, dan *Core Animation Display Pipeline* untuk melacak bottlenecks CPU/GPU.
4. **Menerapkan Telemetri Kinerja Produksi:** Mengintegrasikan framework `MetricKit` dan API `OSSignpost` / Unified Logging (`os_log`) guna mengalirkan data analitik performa *real-time* tanpa mengorbankan overhead runtime aplikasi.
5. **Mengatasi Masalah Off-Screen Rendering & Core Animation Drops:** Mengoptimalkan kompilasi view tree hierarkis, masking, visual effects, dan layout updates berlebih agar GPU rendering pipeline beroperasi optimal.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Mental Model: Anggaran Waktu Frame (Frame Budget Invariance)
Layar perangkat iOS ProMotion beroperasi pada frekuensi adaptif hingga 120Hz. Artinya, sistem operasi memiliki batas mutlak rendering sebesar **8.33 milidetik** per frame (atau **16.67 milidetik** pada 60Hz).

$$\text{Toleransi Frame (120Hz)} = \frac{1000\text{ ms}}{120} \approx 8.333\text{ ms}$$

Ketika eksekusi pada thread utama melampaui jendela waktu tersebut—akibat layout pass yang tidak efisien, decoding payload JSON masif, dekompresi gambar, atau pemblokiran I/O—Display Pipeline Core Animation gagal menyajikan *framebuffer* baru ke hardware display. Hasilnya adalah **Hangs (Janks)**. Profiling bukanlah langkah perbaikan reaktif pasca-rilis; ini adalah verifikasi deterministik terhadap alokasi waktu komputasi per frame.

### Mental Model: Topologi Memori iOS (The OOM Reality)
iOS **tidak menyediakan swap space virtual memory konvensional berbasis disk**. Arsitektur memori iOS mengandalkan *Compressed Memory Store*.

```
[Total System RAM]
   ├── Clean Memory (Dapat dibuang kapan saja oleh Kernel: Frameworks binary, mmap read-only files)
   └── Dirty Memory (Alokasi Heap dinamis: Objek Swift, Dekompresi Bitmap, Unsafe Pointers)
         └── Compressed Memory (Halaman Dirty yang dikompresi oleh Darwin Kernel saat tekanan naik)
```

Ketika *Dirty + Compressed Memory* melampaui batas yang diizinkan (*High Watermark Memory Footprint*), Darwin Kernel mengirimkan sinyal tekanan memori (`OSMemoryNotificationMask`). Jika aplikasi gagal membebaskan alokasi secara cepat, daemon `jetsam` mengeksekusi terminasi paksa: **EXC_RESOURCE RESOURCE_TYPE_MEMORY (OOM Crash)** tanpa peringatan stack trace.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### A. Core Animation Rendering Pipeline Cycle
Siklus per-frame dari aplikasi hingga hardware display:

```
+-----------------------------------------------------------------------------------+
| 1. APPLICATION (Main Thread)                                                      |
|    - Update Layout Constraints -> Data Source Updates -> Display Layer Tree       |
|    - Commit Transaction: CATransaction.commit()                                   |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼ [IPC / Mach Port]
+-----------------------------------------------------------------------------------+
| 2. RENDER SERVER (render server process)                                          |
|    - Deserialisasi Tree Structure                                                 |
|    - Decode Draw Commands (Draw Lists)                                            |
|    - GPU Pipeline Setup (Tessellation, Vertex & Fragment Shaders)                 |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
| 3. GRAPHICS PROCESSOR (GPU Hardware)                                              |
|    - Rasterization Buffer                                                         |
|    - Offscreen Passes (Shadows, Corner Radius Clips, Visual Blurs)               |
|    - Menulis Frame Buffer akhir                                                   |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
| 4. DISPLAY HARDWARE (V-Sync Sync Pulse)                                           |
|    - Pindah Frame Buffer ke Layar Panel OLED/Mini-LED (8.33ms / 16.67ms tick)      |
+-----------------------------------------------------------------------------------+
```

### B. Time Profiler vs System Trace Sampling Pipeline

```
Thread Execution: [---Task A---]       [--Task B--]       [---Task C---]
                      |                     |                  |
Time Profiler Sampling:
Interval (1ms)   *    *    *    *    *    *    *    *    *    *    *
Sample Taken:   [A]  [A]  [Idle] [Idle] [B]  [B]  [Idle] [C]  [C]  [C]
                      │
                      ▼
Aggregation: Stack Trace Unwinding -> Inferred Call Tree Generation

System Trace Context Switches:
Darwin Kernel:  [Thread 1: Running] -> [Blocked: Mutex] -> [Thread 2: Context Switch]
                      │
                      ▼
Visualisasi Thread State: Running, Blocked, Waiting, Interrupt
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Instrument Sampling Engine & Stack Unwinding
Time Profiler mengandalkan interupsi kernel berbasis *hardware performance counters* atau *timer interrupt* yang dikonfigurasi secara berkala (default: per 1 ms). Ketika timer terpicu:
* Darwin Kernel memicu interupsi pada CPU Core target.
* Register instruksi CPU (`$PC` - Program Counter) dan register frame pointer (`$FP`) diakses.
* Stack frames ditelusuri ke belakang (*Stack Unwinding*). 
* Data diekspor ke buffer sirkular milik Daemon DTrace/Instruments tanpa alokasi memori heap baru guna menjaga keaslian profil eksekusi aplikasi (*heisenbug mitigation*).

### 2. Jetsam Memory Subsystem
Jetsam adalah bagian dari Darwin kernel yang bertugas mengelola tekanan alokasi RAM:
* Setiap proses memiliki skor prioritas (`memcheck priority` / `active background status`).
* Saat physical footprint meningkat, kernel menugaskan kswapd-like worker untuk memindahkan dirty pages ke *Compressed Memory*.
* Jika alokasi tetap menembus ambang batas hardware (misal: 1.4GB pada iPhone 15 Pro Max saat memori bebas tipis), kernel membaca tabel alokasi Jetsam dan langsung mengirim sinyal `SIGKILL` (diberi flag `0x8badf00d` atau `0xdeadfa11`). Memory leak pada akhirnya akan berujung pada Jetsam event, bukan classic user-space exception.

### 3. Off-Screen Rendering Mechanics
Secara natural, GPU melakukan rendering direct-to-framebuffer (*On-Screen Rendering*). Namun, apabila suatu layer memiliki atribut yang mengharuskan layer digabungkan sebelum tampil (seperti `layer.masksToBounds = true` dikombinasikan dengan `layer.cornerRadius`, atau `layer.shadowPath == nil`), GPU terpaksa:
* Menghentikan pipeline rendering normal.
* Mengalokasikan off-screen buffer sementara di VRAM.
* Melakukan context switch antara frame buffer dan off-screen buffer.
* Menulis seluruh konten anak, melakukan clipping/masking, kemudian menyalin kembali hasilnya ke frame buffer. Context switch pada GPU ini memicu lonjakan thermal throttling dan frame drop drastis.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### MetricKit Under the Hood
`MetricKit` mengabstraksi telemetri runtime dengan agregasi lokal yang sangat hemat daya. Alih-alih melakukan *polling* konstan yang menguras baterai, kernel mencatat metrik ke dalam subsistem tracing internal. Sekali dalam 24 jam (atau saat simulasi debug melalui API), `MetricKit` memaketkan data telemetri historis (akumulasi konsumsi energi, waktu hang, terminasi OOM, disk write overhead) dan mendistribusikannya via callback `MXMetricManagerSubscriber`.

### Unified Logging and Custom Tracing via OSSignpost
`os_signpost` adalah implementasi tracing dengan latensi rendah (< 1 mikrosekon per emisi data). Ketika aplikasi menulis signpost:
* Nilai tidak langsung diformat menjadi string secara instan.
* Pointer string statis dan argumen dinamis ditulis ke dalam *lock-free ring buffer* pada kernel.
* Instruments membaca ring buffer ini dan mengekstrak segmen interval (`begin` ke `end`) untuk diproyeksikan langsung pada timeline visual Time Profiler/System Trace.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut implementasi instrumentasi manual menggunakan `OSSignpost` dan integrasi listener `MetricKit`:

```swift
import Foundation
import MetricKit
import OSLog

// MARK: - Telemetry & Signpost Interface
public final class PerformanceTelemetryManager: NSObject {
    public static let shared = PerformanceTelemetryManager()
    
    // Subsystem Log khusus untuk profiling berkinerja tinggi
    private let logger = Logger(subsystem: "com.enterprise.app.performance", category: "DataProcessing")
    private let signpostLog = OSLog(subsystem: "com.enterprise.app.performance", category: "CriticalPath")
    
    private override init() {
        super.init()
        // Mendaftarkan subscriber ke MetricKit Engine
        MXMetricManager.shared.add(self)
    }
    
    deinit {
        MXMetricManager.shared.remove(self)
    }
    
    /// Menjalankan blok eksekusi yang dipetakan langsung ke Instruments Timeline
    public func traceScope<T>(name: StaticString, execute: () throws -> T) rethrows -> T {
        let signpostID = OSSignpostID(log: signpostLog)
        
        os_signpost(.begin, log: signpostLog, name: name, signpostID: signpostID)
        defer {
            os_signpost(.end, log: signpostLog, name: name, signpostID: signpostID)
        }
        
        return try execute()
    }
}

// MARK: - MetricKit Subscriber Implementation
extension PerformanceTelemetryManager: MXMetricManagerSubscriber {
    public func didReceive(_ payloads: [MXMetricPayload]) {
        for payload in payloads {
            // Evaluasi Hang Time dari komputasi Main Thread
            if let hangMetrics = payload.applicationTimeMetrics {
                let cumulativeHangTime = hangMetrics.cumulativeHangTime
                print("Aggregated Cumulative Hang Time: \(cumulativeHangTime)")
            }
            
            // Evaluasi Memory Metrics
            if let memoryMetrics = payload.memoryMetrics {
                let peakMemoryFootprint = memoryMetrics.peakMemoryUsage
                print("Reported Peak Memory Footprint: \(peakMemoryFootprint)")
            }
        }
    }
    
    public func didReceive(_ payloads: [MXDiagnosticPayload]) {
        for diagnostic in payloads {
            // Menganalisis CPU Exception Diagnostics (Crash akibat Infinite Loop / Runaway CPU)
            if let cpuExceptions = diagnostic.cpuExceptionDiagnostics {
                for exception in cpuExceptions {
                    print("Crash Call Stack: \(exception.callStackTree)")
                }
            }
            
            // Menganalisis Disk Write Exhaustion
            if let diskWrites = diagnostic.diskWriteExceptionDiagnostics {
                print("Excessive Disk Writes: \(diskWrites)")
            }
        }
    }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

* **Baris 8-9:** Deklarasi instance `Logger` dan `OSLog`. Menggunakan string statis pada `subsystem` dan `category` sangat penting agar Instruments dapat melakukan kategorisasi filter tanpa overhead dynamic memory allocation.
* **Baris 14:** `MXMetricManager.shared.add(self)` mendaftarkan kelas ke engine kernel MetricKit. Sistem akan mengumpulkan seluruh telemetri agregat harian perangkat dan mengirimkannya lewat mekanisme delegate ini.
* **Baris 24:** `let signpostID = OSSignpostID(log: signpostLog)` membuat identifier 64-bit unik. Hal ini memungkinkan pelacakan paralel jika fungsi yang sama berjalan secara bersamaan di berbagai background thread tanpa tumpang tindih visualisasi trace di Instruments.
* **Baris 26:** `os_signpost(.begin, ...)` menginstruksikan kernel untuk mencatat timestamp awal dari segmen trace.
* **Baris 27-29:** `defer { os_signpost(.end, ...) }` memastikan pemanggilan end-marker bersifat deterministik, bahkan jika operasi di dalam blok melempar exception (`throws`).
* **Baris 36:** Callback `didReceive(_ payloads: [MXMetricPayload])` dieksekusi secara periodik oleh daemon sistem untuk memasok metrik agregat produksi nyata.
* **Baris 39:** `payload.applicationTimeMetrics?.cumulativeHangTime` mengekstrak metrik waktu hang kumulatif, mengukur total waktu ketika main thread tidak responsif terhadap run-loop ticks.
* **Baris 51:** `didReceive(_ payloads: [MXDiagnosticPayload])` mendengarkan kegagalan fatal performa, termasuk crash stack trace yang diurai langsung oleh sistem tanpa memakan alokasi proses aplikasi.

---

## SEKSI 09 — STUDI KASUS NYATA (ENTERPRISE SCENARIO)

### Masalah
Sebuah platform media streaming dan e-commerce berskala enterprise mengalami peningkatan churn rate pengguna pada iPhone berlayar ProMotion (120Hz). Tim produk menerima feedback bahwa aplikasi mengalami "patah-patah parah" (micro-stuttering) saat scrolling pada halaman Feed Katalog Utama yang berisi gambar resolusi tinggi, feed video preview, serta kartu produk dinamis. Selain itu, crash analytics menunjukkan lonjakan terminasi mendadak (*0x00000000deadfa11* - Jetsam OOM) pada perangkat lama (iPhone 11 dan SE generasi ke-2) setelah 3-5 menit pemakaian terus-menerus.

### Hipotesis Investigasi Menggunakan Instruments
1. **Time Profiler & Core Animation:** Mengidentifikasi bahwa main thread terblokir oleh pemrosesan gambar (decoding inline) dan autolayout recalculation yang berulang. Selain itu, layer memiliki rounded corners dengan masking dinamis yang memicu Off-Screen Rendering massal.
2. **Allocations & Leaks:** Menemukan bahwa gambar hasil unduhan didekompresi menjadi buffer bitmap raw di memori tanpa ukuran tampilan target (*downsampling failure*), menggelembungkan *Dirty Memory* dari 150MB ke 1.8GB, yang memicu intervensi OOM killer (Jetsam).

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & PRODUCTION CODE

Di bawah ini adalah implementasi komponen pemrosesan gambar dan layout katalog yang telah diamankan dari alokasi memori berlebih via *image downsampling on IO/background queue*, serta penghapusan off-screen rendering pada rendering layer:

```swift
import UIKit
import CoreGraphics
import ImageIO
import OSLog

// MARK: - Thread-Safe Downsampler Cache Engine
public actor OptimizedImagePipeline {
    public static let shared = OptimizedImagePipeline()
    private let signpostLog = OSLog(subsystem: "com.enterprise.media", category: "ImagePipeline")
    
    // In-memory cache yang dibatasi kuota alokasi memori aktual
    private let memoryCache: NSCache<NSURL, UIImage> = {
        let cache = NSCache<NSURL, UIImage>()
        cache.totalCostLimit = 100 * 1024 * 1024 // Batas ketat: 100 Megabytes
        return cache
    }()
    
    private init() {}
    
    /// Melakukan decoding & downsampling gambar secara hemat tanpa memuat full bitmap ke Heap
    public func downsample(
        imageAt sourceURL: URL,
        to targetSize: CGSize,
        scale: CGFloat
    ) async throws -> UIImage {
        let nsURL = sourceURL as NSURL
        if let cached = memoryCache.object(forKey: nsURL) {
            return cached
        }
        
        let signpostID = OSSignpostID(log: signpostLog)
        os_signpost(.begin, log: signpostLog, name: "DownsampleTask", signpostID: signpostID, "URL: %{public}@", sourceURL.lastPathComponent)
        
        defer {
            os_signpost(.end, log: signpostLog, name: "DownsampleTask", signpostID: signpostID)
        }
        
        return try await withCheckedThrowingContinuation { continuation in
            DispatchQueue.global(qos: .userInitiated).async {
                let imageSourceOptions = [kCGImageSourceShouldCache: false] as CFDictionary
                guard let imageSource = CGImageSourceCreateWithURL(sourceURL as CFURL, imageSourceOptions) else {
                    continuation.resume(throwing: URLError(.cannotDecodeContentData))
                    return
                }
                
                // Menentukan dimensi target berdasarkan densitas layar hardware
                let maxDimensionInPixels = max(targetSize.width, targetSize.height) * scale
                
                let downsampleOptions = [
                    kCGImageSourceCreateThumbnailFromImageAlways: true,
                    kCGImageSourceShouldCacheImmediately: true, // Dekompresi terjadi di sini (Background)
                    kCGImageSourceCreateThumbnailWithTransform: true,
                    kCGImageSourceThumbnailMaxPixelSize: maxDimensionInPixels
                ] as CFDictionary
                
                guard let downsampledImage = CGImageSourceCreateThumbnailAtIndex(imageSource, 0, downsampleOptions) else {
                    continuation.resume(throwing: URLError(.cannotDecodeContentData))
                    return
                }
                
                let finalImage = UIImage(cgImage: downsampledImage)
                
                // Kalkulasi perkiraan cost byte: lebar * tinggi * 4 (RGBA 8-bit)
                let cost = Int(targetSize.width * scale * targetSize.height * scale * 4)
                Task { [weak self] in
                    await self?.cacheImage(finalImage, for: nsURL, cost: cost)
                }
                
                continuation.resume(returning: finalImage)
            }
        }
    }
    
    private func cacheImage(_ image: UIImage, for url: NSURL, cost: Int) {
        memoryCache.setObject(image, forKey: url, cost: cost)
    }
}

// MARK: - Zero Off-Screen Rendering Custom View Cell
public final class HighPerformanceCatalogCell: UICollectionViewCell {
    public static let reuseIdentifier = "HighPerformanceCatalogCell"
    
    private let thumbnailImageView: UIImageView = {
        let iv = UIImageView()
        iv.translatesAutoresizingMaskIntoConstraints = false
        iv.contentMode = .scaleAspectFill
        // PENTING: Menghindari Off-Screen Render Masking
        // Menggunakan direct corner radius tanpa shadow/clip kombinasi
        iv.layer.cornerRadius = 8.0
        iv.layer.masksToBounds = true
        return iv
    }()
    
    private var currentTask: Task<Void, Never>?
    
    public override init(frame: CGRect) {
        super.init(frame: frame)
        setupViews()
    }
    
    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }
    
    private func setupViews() {
        contentView.addSubview(thumbnailImageView)
        NSLayoutConstraint.activate([
            thumbnailImageView.topAnchor.constraint(equalTo: contentView.topAnchor),
            thumbnailImageView.leadingAnchor.constraint(equalTo: contentView.leadingAnchor),
            thumbnailImageView.trailingAnchor.constraint(equalTo: contentView.trailingAnchor),
            thumbnailImageView.bottomAnchor.constraint(equalTo: contentView.bottomAnchor)
        ])
        
        // Optimasi Layer Drawing Pipeline
        layer.drawsAsynchronously = true // Offload drawing composition ke background render thread
    }
    
    public func configure(with imageURL: URL) {
        currentTask?.cancel()
        
        let screenScale = UIScreen.main.scale
        let targetSize = bounds.size == .zero ? CGSize(width: 120, height: 120) : bounds.size
        
        currentTask = Task {
            do {
                let optimizedImage = try await OptimizedImagePipeline.shared.downsample(
                    imageAt: imageURL,
                    to: targetSize,
                    scale: screenScale
                )
                
                if !Task.isCancelled {
                    self.thumbnailImageView.image = optimizedImage
                }
            } catch {
                // Tangani error secara silent atau fallback image
                if !Task.isCancelled {
                    self.thumbnailImageView.image = nil
                }
            }
        }
    }
    
    public override func prepareForReuse() {
        super.prepareForReuse()
        currentTask?.cancel()
        currentTask = nil
        thumbnailImageView.image = nil
    }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS KOMPARATIF

| Pendekatan / Pola | Keuntungan (*Pros*) | Kerugian / Risiko (*Cons*) | Memory Footprint | CPU Cost | Kasus Penggunaan Optimal |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Direct UIImage(contentsOfFile:)** | Kode minimalis, tidak butuh boiler plate. | Membaca seluruh file ke memori, dekompresi sinkronis di main thread saat render. Memicu hang. | **Ekstrem Tinggi** (Ukuran raw bitmap penuh). | Lonjakan tajam di Main Thread. | Thumbnail aset lokal ukuran sangat kecil (<50KB). |
| **ImageIO Thumbnail Downsampling** | Memotong dekompresi bitmap langsung ke dimensi tampilan, hemat RAM >90%. | Memerlukan C-based CoreGraphics APIs (`CFDictionary`, `CGImageSource`). | **Sangat Rendah** (Proporsional dengan frame pixel target). | Terbagi merata pada Background Thread. | Feed media, galeri dinamis, e-commerce catalog. |
| **`layer.drawsAsynchronously = true`** | Context rendering diproses pada background CoreAnimation threads, frame rate naik. | Menambah latensi 1-2 frame untuk rendering pertama, alokasi memori ganda sementara. | **Moderat** (Double buffer alokasi pendek). | Mengurangi beban CoreAnimation Render Server. | Teks rendering kompleks, drawRect kustom berat. |
| **Instruments: Time Profiler** | Overhead pengujian rendah (~1-3%), visibilitas sampling call-tree sangat baik. | Berbasis sampling statistik; eksekusi fungsi sangat pendek dapat terlewat (*sample skipping*). | **Nol Overhead** pada alokasi aplikasi. | Rendah. | Diagnostik CPU spike, lock contention, UI Hangs. |
| **Instruments: Allocations Track** | Melacak setiap alokasi heap malloc/free secara deterministik 100%. | Overhead tinggi, aplikasi berjalan lebih lambat, jejak memori profiling besar di host Mac. | **Tinggi** pada buffer tracking kernel host. | Menengah ke Tinggi. | Investigasi Retain Cycles, Dirty Memory spikes. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

1. **Deadlock Tersembunyi via DispatchGroup/Semaphores di Swift Concurrency:** Memanggil `semaphore.wait()` atau `DispatchGroup.wait()` di dalam blok Swift Concurrency (`Task`) yang menunggu MainActor akan menyebabkan sistem thread injection kehabisan thread pool (*Thread Starvation*), yang berakhir pada pembekuan aplikasi total dan hang diagnostics permanen.
2. **Time-Of-Flight Decompression Glitch:** Jika downsampling dilakukan terlalu agresif pada background thread saat sel digulirkan cepat, sel mungkin muncul kosong beberapa milidetik (*flash/flicker*) sebelum gambar masuk. Ini harus dimitigasi dengan caching bertingkat.
3. **Ghost References via Memory Graphs:** Ketika mendeteksi Retain Cycle pada Swift Closures, berhati-hatilah dengan capture `self` implisit di struct yang menyimpan reference context secara tidak sengaja (misal: nested closures dalam escaping parameter).

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan Fatal 1: Menjalankan Profiling pada Modus 'Debug'
* **Penyebab:** Modus Debug menyertakan metadata simbolik ekstensif, menghilangkan optimasi kompilator Swift (`-O`), dan mematikan *inlining*. Profiling CPU di mode Debug menghasilkan metrik performa yang salah.
* **Solusi:** Selalu jalankan profiling pada konfigurasi skema **Release** (Product > Profile di Xcode) dengan opsi *DWARF with dSYM File* aktif untuk symbolication.

### Kesalahan Fatal 2: Menyelesaikan Masking Menggunakan `view.clipsToBounds = true` + Shadow
* **Penyebab:** Menyetel `layer.cornerRadius` dengan `masksToBounds = true` bersamaan dengan `layer.shadowOpacity > 0` memaksa Core Animation melakukan render dua kali via GPU Off-screen Pass karena batas bayangan tidak dapat ditentukan sebelum konten di-mask.
* **Solusi:** Sediakan explicit shadow path: `layer.shadowPath = UIBezierPath(roundedRect: bounds, cornerRadius: 8).cgPath`, atau buat layer bayangan terpisah di belakang view kontainer.

### Kesalahan Fatal 3: Blocking Main Thread Menggunakan Operasi JSON Serialisasi
* **Penyebab:** Mengeksekusi `JSONDecoder().decode(LargePayload.self, from: data)` di dalam closure respons jaringan yang kembali ke `DispatchQueue.main`.
* **Solusi:** Jalankan serialisasi model data secara eksplisit di dalam cooperative background task (`Task.detached(priority: .userInitiated)`) sebelum melempar hasilnya ke UI binding layer.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Batas Latensi Run-Loop (Zero Main-Thread IO):** Tidak boleh ada pemanggilan file I/O (`Data(contentsOf:)`), IPC sinkron, atau CoreData request tanpa batching di Thread Utama. Ambang batas toleransi hang adalah **0 milidetik** untuk blocking I/O.
2. **Kompilasi Auto-Layout yang Statis:** Hindari penghapusan dan penambahan constraint layout dinamis berulang-ulang di dalam method `layoutSubviews()`. Gunakan aktivasi constraint kolektif: `NSLayoutConstraint.activate(...)` satu kali pada saat inisialisasi, kemudian ubah nilai `constant` jika perlu animasi.
3. **Gunakan Signpost Metadata yang Dinamis:** Tambahkan metadata kontekstual pada `os_signpost` (misalnya identifier item atau resolusi) untuk mempercepat pelacakan anomali di Instruments.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### Formula Perhitungan Dirty Memory Bitmap:
Untuk mengukur dampak memori gambar yang tidak di-downsample:

$$\text{Memory (Bytes)} = \text{Pixel Width} \times \text{Pixel Height} \times 4\text{ Bytes (RGBA)}$$

Kamera iPhone 48MP menghasilkan resolusi sebesar $8064 \times 6048$ piksel.
$$\text{Memory} = 8064 \times 6048 \times 4 = 195,084,288\text{ Bytes} \approx 186\text{ MB}$$

Memuat satu gambar mentah ke dalam UIImageView berukuran $100 \times 100$ point (@3x = $300 \times 300$ piksel) mengonsumsi **186 MB RAM**, padahal yang dibutuhkan hanyalah:
$$\text{Target Memory} = 300 \times 300 \times 4 = 360,000\text{ Bytes} \approx 0.34\text{ MB}$$
Melalui teknik downsampling ImageIO di Seksi 10, kita menghemat efisiensi memori sebesar **99.8%**.

---

## SEKSI 16 — KEAMANAN & HARDENING

Saat mengumpulkan data telemetri produksi, perhatikan aspek privasi dan keamanan:
1. **Redaksi Data Sensitif (Data Redaction):** Apple Logging System (`os_log`, `Logger`) secara default mengabstraksi variabel dinamis menjadi `<private>` pada perangkat non-jailbreak/rilis retail demi melindungi PII (*Personally Identifiable Information*).
2. **Eksplisit Publikasi Metadata:** Hanya gunakan penanda interpolasi `%{public}@` untuk konstanta operasional non-sensitif (contoh: ID error internal, UUID non-user, nama endpoint). Jangan pernah menandai nama pengguna, token otentikasi, atau geolokasi sebagai `public`.
3. **Penyimpanan Metrik:** File dump dari MetricKit yang disimpan secara lokal sebelum dikirimkan ke backend harus diletakkan pada direktori yang diproteksi enkripsi file sistem (`NSFileProtectionComplete`).

---

## SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

Langkah-langkah merekam jejak diagnostik Instruments secara terprogram via Command-Line Interface (CI/CD Automated Profiling):

```bash
# 1. Jalankan Time Profiler Headless pada Perangkat Target / Simulator
xcrun xctrace record \
  --template 'Time Profiler' \
  --device 'iPhone 15 Pro' \
  --attach 'com.enterprise.app' \
  --output './ProfilingResults/MainApp_Performance.trace' \
  --time-limit 30s

# 2. Ekspor Hasil Trace Menjadi Format Readable (XML) untuk Divalidasi oleh Runner CI
xcrun xctrace export \
  --input './ProfilingResults/MainApp_Performance.trace' \
  --xpath '/trace-toc/run[@number="1"]/data/table[@schema="time-profile"]' \
  --output './ProfilingResults/trace_summary.xml'
```

Melalui pipeline ini, tim engineer dapat memverifikasi batas ambang toleransi regresi performa (misalnya CPU usage > 80% selama lebih dari 300ms) secara otomatis sebelum kode digabungkan (*merged*) ke cabang produksi.

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

* **UI Hang Target:** Eksekusi per frame wajib tuntas $\le 8.33$ ms (120Hz) atau $\le 16.67$ ms (60Hz).
* **Instrument Matrix:**
  * **Time Profiler:** Menemukan fungsi lambat berbasis statistik interupsi CPU.
  * **Allocations:** Mengukur *Dirty Memory* dan melacak alokasi heap via `malloc`.
  * **Leaks:** Menemukan *retained memory cycles* yang tidak lagi memiliki pointer aktif.
  * **Core Animation:** Menganalisis *Off-Screen Rendering*, *Color Blended Layers*, dan FPS drop.
* **Dirty vs Clean:** Clean memory dapat dieliminasi kernel; Dirty memory wajib ditangani manual atau aplikasi dimatikan oleh Jetsam.
* **ImageIO:** Selalu gunakan thumbnail downsampling sebelum memindahkan file gambar besar ke `UIImageView`.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal 1
Mengapa eksekusi profiling aplikasi yang dijalankan di Xcode menggunakan skema 'Debug' memberikan kesimpulan diagnostik yang tidak valid untuk performa di dunia nyata?
* A. Kernel Darwin melarang alokasi memori heap lebih dari 500MB dalam mode Debug.
* B. Kompilator menonaktifkan optimasi kode (`-Onone`), fungsi tidak di-inline, dan runtime dibebani oleh instrumen sanitasi data.
* C. Display ProMotion 120Hz dikunci secara otomatis pada 30Hz saat koneksi debugger LLDB aktif.
* D. Instruments tidak dapat membaca register CPU `$PC` jika binary tidak diproteksi oleh dSYM.

### Soal 2
Perhatikan potongan kode berikut:
```swift
func renderProfileImage(url: URL) {
    let data = try! Data(contentsOf: url)
    let rawImage = UIImage(data: data)!
    self.avatarImageView.image = rawImage
    self.avatarImageView.layer.cornerRadius = 20
    self.avatarImageView.layer.masksToBounds = true
    self.avatarImageView.layer.shadowRadius = 4
    self.avatarImageView.layer.shadowOpacity = 0.8
}
```
Berapa banyak titik kegagalan performa (*performance flaws*) mendasar yang terjadi di main thread?
* A. 1 Flaw: Hanya crash akibat `try!`.
* B. 2 Flaws: Penggunaan `Data(contentsOf:)` dan ketiadaan thread scaling.
* C. 3 Flaws: Blocking synchronous I/O, alokasi memori bitmap tak ter-downsample, dan Off-Screen Rendering akibat kombinasi masksToBounds dan shadow.
* D. Tidak ada masalah performa jika ukuran file gambar di bawah 2MB.

### Soal 3
Apa peran utama dari daemon `jetsam` di Darwin OS?
* A. Mengompilasi bytecode Swift ke instruksi mesin Native saat proses runtime.
* B. Mematikan proses aplikasi secara deterministik saat jejak Dirty Memory melampaui batas batas hardware via physical footprint threshold.
* C. Membagi alokasi beban grafis antara CPU hardware threads dan Metal compute pipelines.
* D. Melakukan dekompresi file asset catalog saat aplikasi pertama kali di-launch.

### Soal 4
Bagaimana cara paling efektif mendeteksi retain cycle tanpa harus menjalankan aplikasi di Instruments secara manual?
* A. Menambahkan log print di method `viewDidLoad`.
* B. Memeriksa alokasi heap via Debug Memory Graph di Xcode dan mengaktifkan build warning untuk unowned/weak closure rules.
* C. Menghitung jumlah alokasi struct di stack frame.
* D. Mengurangi resolusi display simulator iOS.

### Soal 5
Saat melakukan profiling rendering Core Animation, indikator "Color Offscreen-Rendered Yellow" menandakan bahwa:
* A. GPU melakukan rasterisasi langsung ke framebuffer layar secara efisien.
* B. Main thread kehabisan cooperative background execution pool.
* C. GPU terpaksa mengalokasikan temporary context buffer sekunder untuk memproses efek visual layer sebelum memindahkannya ke layar.
* D. Aset gambar tidak memiliki color profile sRGB standar.

---

### Kunci Jawaban & Analisis

* **Soal 1: Jawaban B.** Modus Debug mengompilasi kode tanpa optimasi compiler (-Onone), menjaga call-site tidak