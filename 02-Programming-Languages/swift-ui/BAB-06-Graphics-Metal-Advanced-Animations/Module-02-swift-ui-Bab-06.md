# BAB-06: Graphics, Metal & Advanced Animations
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Mengonstruksi arsitektur rendering grafis performa tinggi pada SwiftUI dengan memanfaatkan Metal Shading Language (MSL) dan API Metal FX bawaan iOS 17+.
- Menganalisis dan mengeliminasi *off-screen rendering*, *frame drop*, dan *render pipeline hitches* pada tampilan berkecepatan 120 FPS (ProMotion).
- Mengintegrasikan komputasi shader custom (`colorEffect`, `distortionEffect`, dan `layerEffect`) ke dalam *render tree* Core Animation tanpa memicu alokasi memori berlebih pada thread UI.
- Mengimplementasikan state-driven animation kompleks berbasis `KeyframeAnimator`, `PhaseAnimator`, serta custom `VectorArithmetic` dengan sinkronisasi frame presisi mikrodetik.
- Mendiagnosis degradasi termal dan konsumsi daya GPU menggunakan Xcode Instruments (Metal System Trace dan Core Animation FPS analysis).

---

### 2. Prerequisite
Sebelum mendalami modul ini, Anda wajib menguasai:
- **Swift Core**: Swift 6 *Strict Concurrency*, memory layout struct/class, Unsafe Pointers, dan SIMD types (`SIMD2<Float>`, `SIMD4<Float>`).
- **SwiftUI Internals**: Siklus hidup layout SwiftUI, deklarasi `Animatable`, `Transaction`, dan `TimelineView`.
- **Dasar Grafis & GPU**: Konsep dasar rasterisasi, fragment shading, UV coordinates, normalized device coordinates (NDC), dan pipeline komputasi GPU Apple Silicon (Unified Memory Architecture).

---

### 3. Concept & Internal Architecture

#### Pipeline Core Animation Render Server vs. Metal
Secara arsitektural, antarmuka SwiftUI tidak langsung digambar ke GPU dari proses aplikasi (*client process*). SwiftUI membangun sebuah *render tree* deklaratif, yang kemudian dikompilasi menjadi representasi Core Animation layer. 

```
+-----------------------------------------------------------------------+
| App Process (Client)                                                  |
|  [ SwiftUI View Hierarchy ] -> [ AttributeGraph ]                     |
|                                       |                               |
|                         [ CA::Transaction Commit ]                    |
+---------------------------------------|-------------------------------+
                                        | (IPC / Mach Port)
+---------------------------------------v-------------------------------+
| Core Animation Render Server (backboardd / render server process)     |
|  [ Layer Tree Deserialization ] -> [ Render Tree Flattening ]         |
|                                       |                               |
|                          [ GPU Command Encoder ]                      |
+---------------------------------------|-------------------------------+
                                        |
+---------------------------------------v-------------------------------+
| Apple Silicon GPU (Unified Memory Architecture - UMA)                 |
|  [ Vertex Processing ] -> [ Tiler ] -> [ Fragment/Metal Shaders ]     |
|                                       |                               |
|                              [ Framebuffer ]                          |
+---------------------------------------|-------------------------------+
                                        | (V-Sync Signal: 60/120Hz)
                                  [ Display Engine ]
```

1. **Commit Phase (App Process)**: AttributeGraph mengalkulasi pergeseran layout. Core Animation membungkus perubahan dalam paket transaksi (`CA::Transaction`) dan mengirimkannya melalui IPC (Inter-Process Communication via Mach Ports) ke *Render Server*.
2. **Render Server Phase**: *Render Server* mendeserialisasi hierarki layer dan menjadwalkan instruksi penggambaran GPU menggunakan Metal pipeline.
3. **Execution Phase (GPU)**: GPU mengeksekusi primitive assembly, tiling (arsitektur Tile-Based Deferred Rendering / TBDR milik Apple Silicon), dan fragment shading.
4. **Display Phase**: Hasil rasterisasi dimasukkan ke *framebuffer* dan dibaca oleh kontroler display sinkron dengan sinyal V-Sync.

#### Integrasi Metal Shader pada SwiftUI (iOS 17+)
Mulai iOS 17, SwiftUI memperkenalkan namespace `ShaderLibrary` yang menjembatani MSL langsung ke dalam *render passes* SwiftUI tanpa harus keluar ke representasi UIKit via `MTKView`. Terdapat tiga fungsi utama:
- `colorEffect`: Memanipulasi nilai `half4` warna per-fragment tanpa mengubah lokasi koordinat pixel.
- `distortionEffect`: Melakukan *remap* terhadap koordinat sampling `float2 position`, memungkinkan pemanjangan, refraksi, dan distorsi geometris.
- `layerEffect`: Mengakses keseluruhan representasi layer sebagai tekstur sampler (`SwiftUI::Layer`), memungkinkan efek raster multipass seperti dynamic blur, konvolusi kernel, dan color matrix kompleks.

---

### 4. Why & What

| Pendekatan | Mekanisme Eksekusi | Kelebihan | Kelemahan |
| :--- | :--- | :--- | :--- |
| **Pure SwiftUI Modifiers** (misal `.blur`, `.opacity`) | Core Animation layer caching / Render Server primitives | Efisien untuk UI standar, zero custom code, native dark mode | Terbatas pada efek standar OS; modifikasi dinamis kompleks memicu off-screen pass tak terkontrol |
| **`drawingGroup()`** | Mereduksi view tree menjadi satu off-screen Metal context (`MTLTexture`) | Mengurangi draw calls untuk grafik vektor kompleks (Ribuan Path) | Memutus integrasi teks UIKit natively; boros bandwidth VRAM jika tekstur sering diperbarui; tidak interaktif |
| **SwiftUI + MSL Shaders** | Inline GPU fragment program langsung dieksekusi oleh TBDR pipeline | Kecepatan penuh 120 FPS; manipulasi matematis tingkat fragment; interaktif penuh | Membutuhkan debugging Metal khusus; kesalahan pada shader memicu crash GPU; kompilasi runtime awal |

#### Mengapa Perlu Arsitektur Shader Enterprise?
Pada aplikasi enterprise skala masif (seperti grafik finansial real-time, canvas analitik, atau media editor), kalkulasi jutaan titik data pada CPU thread UI akan memicu *Core Animation Hitch*. Dengan memindahkan kalkulasi matematis (seperti interpolasi, distorsi gelombang, dan mapping deviasi) langsung ke Metal Fragment Shader, kita menghemat siklus CPU dan menyerahkan operasi matriks paralel secara native ke ratusan compute core GPU Apple Silicon.

---

### 5. How (Workflow Detail)

Untuk mengimplementasikan Metal Shader ke dalam SwiftUI tingkat produksi:

```
[Buat File .metal] -> [Tulis Fungsi C++ Metal] -> [Build System mengompilasi ke default.metallib]
         |
         v
[Definisikan Interface Swift] -> [Ambil Function via ShaderLibrary] -> [Terapkan via View Modifier]
         |
         v
[Hubungkan ke Dynamic Driver (TimelineView / KeyframeAnimator / DragGesture)]
```

1. **Konstruksi Metal Function**: Definisikan fungsi shading dengan signature yang kompatibel dengan protokol SwiftUI (`SwiftUI::Layer`, `float2 position`, dan argumen kustom).
2. **Kompilasi Metal**: Build system Xcode mengompilasi file `.metal` menjadi format intermediate AIR (Apple Intermediate Representation) dan menggabungkannya ke `default.metallib`.
3. **Bridge Swift**: Akses shader melalui `ShaderLibrary.default.nama_fungsi(args...)`.
4. **Bind View Modifier**: Terapkan modifier target (`.distortionEffect`, `.colorEffect`, atau `.layerEffect`).
5. **Frame Pacing**: Hubungkan variabel dinamis (misalnya waktu elaps atau titik kordinat interaksi) via `TimelineView(.animation)` atau `AnimatableModifier` untuk menjamin sinkronisasi rendering 120 FPS tanpa alokasi heap berulang pada runloop.

---

### 6. Analogy & Diagram ASCII

Bayangkan proses rendering konvensional CPU seperti **Seorang Arsitek (CPU)** yang menggambar denah manual garis per garis, lalu mengirim kurir ke **Pabrik (GPU)** untuk mencetak tiap frame. Jika denah berubah 120 kali per detik, arsitek kelelahan (*CPU Hitch*).

Integrasi Metal Shader seperti **Arsitek hanya memberikan Rumus Geometri ke Pabrik**. Pabrik memiliki 10.000 buruh (*GPU SIMD execution units*). Tiap buruh langsung mewarnai dan mendistorsi pikselnya masing-masing secara serentak berdasarkan formula instan tanpa perlu menunggu instruksi langkah-demi-langkah arsitek.

```
CPU Model (Konvensional):
[State Change] -> [CPU: Kalkulasi Math] -> [CPU: Rasterisasi Path] -> [GPU: Tampilkan]
(Tergantung beban main-thread; rentan frame-drop jika GC/JSON parsing jalan)

GPU Shader Model (Modern SwiftUI):
[State Change] ------------------ Uniform Data (16 bytes) -----------------> [GPU Core]
                                                                                |
                                     [Setiap piksel dihitung mandiri via Metal Shaders]
                                                                                |
                                                                           [Display]
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Ripple Distortion Shader
Di bawah ini adalah implementasi dasar distorsi riak air interaktif menggunakan MSL dan SwiftUI.

**WaveDistortion.metal**
```metal
#include <metal_stdlib>
#include <SwiftUI/SwiftUI_Metal.h>
using namespace metal;

[[ stitchable ]] float2 waterRipple(
    float2 position, 
    float2 origin, 
    float time, 
    float frequency, 
    float amplitude, 
    float decay
) {
    float distance = length(position - origin);
    float delay = distance * frequency - time;
    
    // Eksponensial decay untuk meredam riak seiring jarak
    float factor = exp(-distance * decay);
    float offset = sin(delay) * amplitude * factor;
    
    // Normalisasi vektor arah
    float2 direction = (distance > 0.0) ? (position - origin) / distance : float2(0.0);
    
    return position + direction * offset;
}
```

**WaveDistortionView.swift**
```swift
import SwiftUI

public struct WaveDistortionView: View {
    @State private var touchOrigin: CGPoint = .zero
    @State private var animationTime: Float = 0.0
    @State private var isActive: Bool = false
    
    public var body: some View {
        TimelineView(.animation(minimumInterval: 1.0 / 120.0, paused: !isActive)) { timeline in
            CanvasContent()
                .distortionEffect(
                    ShaderLibrary.waterRipple(
                        .float2(touchOrigin),
                        .float(animationTime),
                        .float(0.05),  // frequency
                        .float(15.0),  // amplitude
                        .float(0.008)  // decay
                    ),
                    maxSampleOffset: CGSize(width: 20, height: 20)
                )
                .onChange(of: timeline.date) { _, _ in
                    if isActive {
                        animationTime += 0.08
                        if animationTime > 30.0 {
                            isActive = false
                            animationTime = 0.0
                        }
                    }
                }
        }
        .onTapGesture { location in
            touchOrigin = location
            animationTime = 0.0
            isActive = true
        }
    }
}

private struct CanvasContent: View {
    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: "cellularbars")
                .font(.system(size: 80))
                .foregroundStyle(.tint)
            Text("High-Throughput Node")
                .font(.title2.bold())
            Text("Tap to trigger localized GPU surface disruption")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .frame(width: 320, height: 220)
        .background(Material.regular, in: RoundedRectangle(cornerRadius: 24))
        .overlay(
            RoundedRectangle(cornerRadius: 24)
                .stroke(Color.primary.opacity(0.1), lineWidth: 1)
        )
    }
}
```

---

#### B. Practical Example: Enterprise Real-Time Biometric Heatmap Canvas
Contoh implementasi industri: Komponen sensor biometrik/fintech visualizer berbasis real-time audio/telemetry streams. Menggunakan multi-pass `layerEffect`, *vector arithmetic-driven spring animations*, dan proteksi terhadap alokasi memori berlebih.

**BiometricPass.metal**
```metal
#include <metal_stdlib>
#include <SwiftUI/SwiftUI_Metal.h>
using namespace metal;

[[ stitchable ]] half4 biometricHeatmap(
    float2 position, 
    SwiftUI::Layer layer, 
    float4 viewport,     // x, y, width, height
    float intensity, 
    float time,
    float thermalNoise
) {
    // 1. Sample warna asli dari texture buffer
    half4 originalColor = layer.sample(position);
    
    // 2. Normalisasi UV coordinates [0.0, 1.0]
    float2 uv = (position - viewport.xy) / viewport.zw;
    
    // 3. Sintesis noise algoritmik (Simulated Perlin/Turbulence)
    float waveA = sin(uv.x * 12.0 + time * 2.5);
    float waveB = cos(uv.y * 16.0 - time * 1.8);
    float dynamicPattern = (waveA + waveB) * 0.5;
    
    // 4. Hitung gradien radial dari titik tengah
    float2 center = float2(0.5, 0.5);
    float distFromCenter = distance(uv, center);
    
    // 5. Campur layer warna termal (Spectral shift: Blue -> Green -> Red -> White)
    float thermalFactor = saturate((1.0 - distFromCenter) * intensity + dynamicPattern * thermalNoise);
    
    half3 cold = half3(0.05, 0.2, 0.8);
    half3 medium = half3(0.1, 0.9, 0.3);
    half3 hot = half3(1.0, 0.1, 0.05);
    half3 peak = half3(1.0, 1.0, 0.9);
    
    half3 heatColor;
    if (thermalFactor < 0.33) {
        heatColor = mix(cold, medium, half(thermalFactor * 3.0));
    } else if (thermalFactor < 0.66) {
        heatColor = mix(medium, hot, half((thermalFactor - 0.33) * 3.0));
    } else {
        heatColor = mix(hot, peak, half((thermalFactor - 0.66) * 3.0));
    }
    
    // Terapkan overlay dengan preservasi transparansi alpha mask
    half3 blendedOutput = mix(originalColor.rgb, heatColor, half(intensity * 0.75));
    return half4(blendedOutput * originalColor.a, originalColor.a);
}
```

**BiometricThermalVisualizer.swift**
```swift
import SwiftUI

public struct BiometricTelemetryData: Equatable {
    public var coreLoad: Double       // 0.0 to 1.0
    public var signalTurbulence: Double // 0.0 to 1.0
}

public struct BiometricThermalVisualizer: View {
    public let telemetry: BiometricTelemetryData
    
    @State private var referenceDate: Date = .now
    
    public init(telemetry: BiometricTelemetryData) {
        self.telemetry = telemetry
    }
    
    public var body: some View {
        GeometryReader { proxy in
            let frame = proxy.frame(in: .local)
            let viewportVector = simd_float4(
                Float(frame.origin.x),
                Float(frame.origin.y),
                Float(frame.size.width),
                Float(frame.size.height)
            )
            
            TimelineView(.animation(minimumInterval: 1.0 / 120.0)) { timeline in
                let elapsedTime = Float(timeline.date.timeIntervalSince(referenceDate))
                
                ContentSurface()
                    .layerEffect(
                        ShaderLibrary.biometricHeatmap(
                            .float4(viewportVector),
                            .float(Float(telemetry.coreLoad)),
                            .float(elapsedTime),
                            .float(Float(telemetry.signalTurbulence * 0.35))
                        ),
                        maxSampleOffset: .zero
                    )
            }
        }
        .aspectRatio(1.0, contentMode: .fit)
        .clipShape(RoundedRectangle(cornerRadius: 32, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 32, style: .continuous)
                .stroke(
                    LinearGradient(
                        colors: [.white.opacity(0.4), .clear],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    ),
                    lineWidth: 1.5
                )
        )
    }
}

private struct ContentSurface: View {
    var body: some View {
        ZStack {
            Color.black
            
            // Grid background struktural
            GridLinePattern()
                .stroke(Color.white.opacity(0.12), lineWidth: 1)
            
            VStack(spacing: 8) {
                Image(systemName: "waveform.path.ecg.rectangle")
                    .symbolRenderingMode(.hierarchical)
                    .font(.system(size: 64, weight: .light))
                    .foregroundStyle(.white)
                
                Text("SECURE CORE INTERFACE")
                    .font(.system(size: 14, weight: .black, design: .monospaced))
                    .foregroundStyle(.white.opacity(0.8))
                    .tracking(2.0)
            }
        }
    }
}

private struct GridLinePattern: Shape {
    func path(in rect: CGRect) -> Path {
        var path = Path()
        let step: CGFloat = 24.0
        
        var x = rect.minX
        while x <= rect.maxX {
            path.move(to: CGPoint(x: x, y: rect.minY))
            path.addLine(to: CGPoint(x: x, y: rect.maxY))
            x += step
        }
        
        var y = rect.minY
        while y <= rect.maxY {
            path.move(to: CGPoint(rect.minX, y: y))
            path.addLine(to: CGPoint(rect.maxX, y: y))
            y += step
        }
        return path
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario Kasus Produksi:
Sebuah platform perdagangan valuta asing tingkat institusional mengalami penurunan kinerja (*render server hitch rate* melonjak ke 18.4%) pada modul *real-time depth chart*. Chart tersebut menampilkan dinamika likuiditas pasar dengan 60 perbaruan per detik via gRPC stream pada layar ProMotion 120Hz iPad Pro.

#### Analisis Masalah (Bottleneck Profiling):
1. **CPU Path Reconstruction**: Menggunakan shape SwiftUI native yang digambar ulang setiap kali tick data baru datang melalui `Path.addLine()`.
2. **IPC Overload**: Setiap pembaruan frame memicu re-evaluasi `AttributeGraph` dan mengunggah ribuan poligon via Core Animation IPC transaction.
3. **Off-screen Blurs**: Efek glow pada batas likuiditas menggunakan modifikator `.shadow(color:radius:...)` dan `.blur(radius:)` berlapis, memaksa GPU melakukan setidaknya 4 off-screen pass per frame, memicu memory bandwidth starvation (>9.8 GB/s).

#### Solusi Arsitektur Sistem:
- **Transformasi Data**: Reduksi transmisi titik data mentah dari CPU. CPU hanya mengunggah matriks harga dan intensitas terkonsolidasi via `SIMD4<Float>` uniform buffer.
- **Metal Offload**: Pindahkan kurva ekstrapolasi dan visualisasi glow ke `layerEffect` dan `distortionEffect` shader tunggal.
- **Single Render Pass Elimination**: Mengganti `.shadow` berantai dengan fungsi shader *signed distance field* (SDF) langsung di dalam pipeline shader fragment native, menghindari pembuatan layer perantara Core Animation.

#### Hasil Metrik:
- **Core Animation Hitch Rate**: Turun dari **18.4%** menjadi **0.12%**.
- **CPU Time / Frame**: Turun dari **11.2 ms** menjadi **1.1 ms** (penghematan 90%).
- **GPU Thermal State**: Tetap berada pada status `Nominal` selama 45 menit pengujian terus-menerus, mengeliminasi throttling perangkat.

---

### 9. Trade-offs

```
                  FLEKSIBILITAS & FITUR UI NATIVE
                               ▲
                              / \
                             /   \
                            /     \
    SwiftUI Native Pipeline       Metal Shaders (iOS 17+)
             /                             \
            /                               \
           ▼                                 ▼
   KONSUMSI MEMORI RENDAH <------------> EKSTRIM GPU THROUGHPUT
```

1. **Kompleksitas vs. Kecepatan (Performance)**:
   - SwiftUI Native Modifiers: Mengembangkan fitur memakan waktu cepat, auto-resolving warna sistem, namun kapabilitas rendering terikat batasan Core Graphics.
   - Metal Shaders: Membutuhkan pengetahuan mendalam tentang kalkulasi vektor SIMD dan fragment arithmetic, tetapi memberikan kestabilan 120 FPS konstan.

2. **Unified Memory Bandwidth (Bandwidth vs. Arithmetic Intensity)**:
   - Penggunaan `layerEffect` memerlukan alokasi tekstur off-screen implisit untuk layer yang sedang ditransformasi. Jika resolusi layer mencakup full-screen 4K iPad Pro, pembacaan sampler terus-menerus pada 120 FPS akan menguras bandwidth bus memori SoC.
   - Alternatif: Gunakan `colorEffect` atau kalkulasi procedur analitik murni jika tidak memerlukan koordinat tetangga piksel, untuk memangkas *texture fetch cycle*.

3. **Kompatibilitas Backward**:
   - `ShaderLibrary` dan integrasi modern hanya tersedia di iOS 17+, macOS 14+, visionOS 1+.
   - Untuk iOS 16 ke bawah, arsitektur harus mundur (*fallback*) ke `UIViewRepresentable<MTKView>`, yang memperkenalkan kompleksitas koordinasi lifecyle SwiftUI-Metal context secara manual.

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan Fatal: Alokasi Memory di Dalam Blok Render
*Kesalahan*: Menginisialisasi struct atau memanggil alokasi heap (seperti Array initialization atau format string) di dalam closure `TimelineView` atau deklarasi `ShaderLibrary`.
```swift
// BURUK: Alokasi heap terjadi 120 kali/detik
TimelineView(.animation) { context in
    let _ = String(format: "Debug %f", context.date.timeIntervalSince1970)
    MyView().distortionEffect(...)
}
```
*Solusi*: Pindahkan seluruh state mutable dan variabel non-primitif ke luar render loop. Lewatkan hanya tipe data bernilai skalar primitif (`Float`, `Double`, `SIMD`).

#### 2. Sampling di Luar Batas Tekstur (Out-of-Bounds Sampling)
*Kesalahan*: Menggunakan `.distortionEffect` dengan offset displacement besar tanpa mendeklarasikan `maxSampleOffset`.
```swift
// Hasil grafis akan terpotong secara kasar pada batas frame layer
.distortionEffect(ShaderLibrary.waterRipple(...), maxSampleOffset: .zero) 
```
*Solusi*: Definisikan `maxSampleOffset` secara presisi sesuai dengan amplitude maksimum pergeseran piksel yang dihasilkan oleh fungsi MSL.

#### 3. Infinite Recursion pada SwiftUI Layer Buffers
*Kesalahan*: Menerapkan `.layerEffect` pada hierarki view yang membungkus *nested* rasterized view berulang kali tanpa stabilisasi frame, memicu stack overflow pada pipeline tiling GPU.

#### 4. Panduan Diagnostik Xcode Instruments:
- Buka **Instruments -> Core Animation FPS**: Cek nilai *Hitch Time Ratio*. Jika > 5 ms/s, analisis kategori hitch: *Commit Hitch* (CPU bottleneck) atau *Render Hitch* (GPU overload).
- Buka **Instruments -> Metal System Trace**: Pantau metrik *Encoder Execution Time*. Jika blok fragment shader melebihi 6.5 ms, sederhanakan percabangan non-uniform (*divergent branching*) di dalam loop kode MSL.

---

### 11. Best Practices (Production Checklist)

- [ ] **Stitchable Signature Valid**: Pastikan fungsi di `.metal` diawali dengan atribut `[[ stitchable ]]` dan berada dalam namespace `using namespace metal;`.
- [ ] **Precision Selection**: Gunakan `half` untuk warna dan representasi grafis low-dynamic-range; gunakan `float` hanya untuk kalkulasi UV coordinates, posisi spasial, dan akurasi waktu.
- [ ] **Branch Divergence Elimination**: Hindari penggunaan `if-else` kompleks di dalam fragment shader MSL. Gunakan fungsi intrinsik GPU seperti `step()`, `smoothstep()`, `mix()`, dan `saturate()`.
- [ ] **Vectorization**: Kelompokkan uniform float ke dalam vektor `simd_float4` atau `SIMD2<Float>` untuk mempercepat transfer data dari CPU ke constant registers GPU.
- [ ] **Layer Geometry Clamping**: Selalu bungkus view penerima shader dengan `.clipped()` atau `.clipShape()` untuk mencegah render server melakukan rasterisasi tak perlu di luar batas tampilan layar.
- [ ] **Thermal Throttling Fallback**: Sediakan fallback otomatis yang menurunkan frekuensi pembaruan `TimelineView` (misalnya dari 120Hz ke 60Hz atau 30Hz) saat sistem mendeteksi `ProcessInfo.processInfo.thermalState == .serious`.

---

### 12. Hands-on Practice
Simpan seluruh artefak praktikum ini di direktori: `hands-on/m02/`

#### Langkah-langkah Implementasi:
1. Buat direktori struktur baru di repo lokal Anda:
   ```bash
   mkdir -p hands-on/m02/Shaders hands-on/m02/Views
   ```
2. Buat file `hands-on/m02/Shaders/ProductionShaders.metal` dan salin kode shader di bawah.
3. Buat file `hands-on/m02/Views/AdvancedFluidCard.swift` dan bangun integrasi view.
4. Hubungkan ke target Xcode dan jalankan pada Real Device (iPhone dengan layar ProMotion direkomendasikan).

**hands-on/m02/Shaders/ProductionShaders.metal**
```metal
#include <metal_stdlib>
#include <SwiftUI/SwiftUI_Metal.h>
using namespace metal;

[[ stitchable ]] half4 chromaticAberration(
    float2 position, 
    SwiftUI::Layer layer, 
    float2 direction, 
    float intensity
) {
    float2 offset = direction * intensity;
    
    // Sample channel RGB secara terpisah dengan offset spasial
    half r = layer.sample(position + offset).r;
    half g = layer.sample(position).g;
    half b = layer.sample(position - offset).b;
    half a = layer.sample(position).a;
    
    return half4(r, g, b, a);
}
```

**hands-on/m02/Views/AdvancedFluidCard.swift**
```swift
import SwiftUI

public struct AdvancedFluidCard: View {
    @State private var dragOffset: CGSize = .zero
    @State private var isDragging: Bool = false
    
    public init() {}
    
    public var body: some View {
        let displacementIntensity = Float(
            min(hypot(dragOffset.width, dragOffset.height) / 10.0, 15.0)
        )
        let normalizedDirection = simd_float2(
            dragOffset.width == 0 ? 0 : Float(dragOffset.width / hypot(dragOffset.width, dragOffset.height)),
            dragOffset.height == 0 ? 0 : Float(dragOffset.height / hypot(dragOffset.width, dragOffset.height))
        )
        
        ZStack {
            Color(.systemGroupedBackground).ignoresSafeArea()
            
            VStack(alignment: .leading, spacing: 16) {
                HStack {
                    Circle()
                        .fill(Color.green)
                        .frame(width: 12, height: 12)
                    Text("ACTIVE GPU PIPELINE")
                        .font(.caption.weight(.bold))
                        .foregroundStyle(.secondary)
                }
                
                Text("Enterprise Asset Vault")
                    .font(.title.bold())
                
                Text("Drag surface to execute real-time multi-channel chromatic dispersion.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                
                Spacer()
                
                HStack {
                    Spacer()
                    Image(systemName: "lock.shield.fill")
                        .font(.system(size: 48))
                        .foregroundStyle(.tint)
                }
            }
            .padding(24)
            .frame(width: 320, height: 240)
            .background(Color(.secondarySystemGroupedBackground))
            .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
            .shadow(color: .black.opacity(0.08), radius: 12, x: 0, y: 6)
            .layerEffect(
                ShaderLibrary.chromaticAberration(
                    .float2(normalizedDirection),
                    .float(displacementIntensity)
                ),
                maxSampleOffset: CGSize(width: 30, height: 30)
            )
            .offset(dragOffset)
            .gesture(
                DragGesture()
                    .onChanged { value in
                        dragOffset = value.translation
                        isDragging = true
                    }
                    .onEnded { _ in
                        withAnimation(.spring(response: 0.45, dampingFraction: 0.65)) {
                            dragOffset = .zero
                            isDragging = false
                        }
                    }
            )
        }
    }
}
```

---

### 13. Exercise

#### Level: Easy
Implementasikan fungsi `.colorEffect` Metal sederhana yang mengubah kontras dan saturasi UI view secara dinamis menggunakan penggeser (*Slider*). 
- *Spesifikasi*: Shader mengalikan color channels dengan faktor scalar, mengonversi nilai RGB ke greyscale secara native melalui dot product `dot(color.rgb, half3(0.2126, 0.7152, 0.0722))`, dan melakukan interpolasi linier (`mix`).

#### Level: Medium
Rancang animasi interaktif menggunakan `KeyframeAnimator` yang mengombinasikan *spring physics* rotasi 3D native dengan `.distortionEffect` gelombang kejut (*shockwave*) Metal yang dipicu setiap kali nilai state tertentu berganti.
- *Spesifikasi*: Durasi shockwave 0.8 detik, menghilang secara cosinusoidal decay, dengan sampling offset maksimal 25 piksel.

#### Level: Hard
Bangun rendering multi-pass custom yang menggabungkan:
1. `.distortionEffect` untuk mensimulasikan refraksi lensa cembung (*magnifying glass effect*) yang mengikuti sentuhan user (`DragGesture`).
2. `.layerEffect` di lapisan berikutnya untuk menerapkan filter Gaussian blur modular 2-pass (horizontal & vertical passes) manual di dalam MSL tanpa memanggil `.blur()` SwiftUI.

---

### 14. Challenge
**Studi Kasus Arsitektural**: Rancang subsistem render untuk aplikasi finansial bertransaksi tinggi: **Real-Time Level-2 Order Book Liquidity Depth Canvas**.

- **Batasan Skala**:
  - 10.000 pesanan masuk per detik yang dialirkan melalui WebSockets/gRPC.
  - Tampilan visual harus merender depth chart dinamis (Bid/Ask wall) dengan visualisasi gradien termal volumetrik.
  - Kebutuhan Frame Rate: Lock 120 FPS tanpa kompromi pada iPhone 15/16 Pro.
  - Batasan CPU: Penggunaan Main Thread CPU untuk visualisasi grafis tidak boleh melebihi **4.0%**.
- **Kebutuhan Teknis**:
  - Rancang ring-buffer data structure thread-safe untuk menampung tick data.
  - Hindari re-layout SwiftUI; transformasi seluruh kalkulasi matriks menjadi tekstur 1D atau uniform buffer array yang diteruskan ke Metal fragment shader.
  - Implementasikan pencegahan crash otomatis jika Metal compiler runtime mengalami failure (*shader recovery mechanism*).

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Apa fungsi dari atribut `[[ stitchable ]]` pada deklarasi fungsi di Metal Shading Language?
2. Apa perbedaan fungsional utama antara modifikator `.colorEffect` dan `.distortionEffect`?
3. Mengapa variabel `maxSampleOffset` sangat krusial pada penggunaan `.distortionEffect` dan `.layerEffect`?
4. Jalur IPC apa yang digunakan SwiftUI untuk mengirimkan transaksi layer dari aplikasi ke Core Animation Render Server?
5. Mengapa tipe data `half` lebih disukai dibandingkan `float` untuk manipulasi warna di dalam chip Apple Silicon?

#### B. Pertanyaan Intermediate
6. Bagaimana cara kerja arsitektur *Tile-Based Deferred Rendering* (TBDR) pada Apple Silicon menguntungkan eksekusi fragment shader SwiftUI dibandingkan arsitektur GPU desktop tradisional?
7. Jelaskan konsekuensi performa terhadap pemanggilan `TimelineView(.animation)` tanpa membatasi minimum interval frame pada layar perangkat ProMotion!
8. Apa yang menyebabkan fenomena *Commit Hitch* pada pipeline grafis Core Animation, dan bagaimana cara membedakannya dengan *Render Hitch*?
9. Mengapa penggunaan `.drawingGroup()` tidak selalu meningkatkan performa dan justru dapat memperburuk konsumsi memori pada hierarki view yang sering berubah?
10. Bagaimana representasi memori dari `SwiftUI::Layer` saat dilewatkan ke dalam fungsi MSL `layerEffect`?

#### C. Skenario Kasus Produksi
11. **Skenario 1**: Aplikasi produksi Anda menerima laporan crash dari analytics dengan log `GPUEvents: Command Buffer Execution Failed: Page Fault Exception`. Crash ini terjadi sporadis hanya saat pengguna melakukan zoom pada chart yang menggunakan `.distortionEffect`. Di mana letak potensi cacat kode shader dan bagaimana cara mengatasinya?
12. **Skenario 2**: Anda mengintegrasikan `.layerEffect` kompleks pada kartu interaktif di dalam `LazyVStack`. Saat pengguna melakukan *fast scrolling*, UI mengalami stuttering parah (frame drop dari 120 FPS ke 35 FPS). Apa akar masalah arsitektural rendering ini, dan bagaimana strategi mitigasinya?
13. **Skenario 3**: Sebuah modul visualisasi audio menggunakan `TimelineView` dan Metal Shader mengalami degradasi frekuensi render bertahap dari 120 FPS ke 60 FPS lalu ke 30 FPS setelah dijalankan selama 10 menit pada iPhone, disertai peningkatan panas fisik perangkat. Langkah diagnosa sistematis apa yang harus Anda lakukan menggunakan Instruments untuk memecahkan masalah degradasi termal ini?

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Basic
1. Atribut `[[ stitchable ]]` menandai fungsi MSL agar dapat dikompilasi ke dalam pipeline dinamis SwiftUI dan dipanggil langsung oleh runtime `ShaderLibrary` Core Animation.
2. `.colorEffect` hanya memodifikasi nilai warna tanpa mengubah posisi piksel (koordinat sampling tetap), sedangkan `.distortionEffect` mengubah posisi koordinat sampling piksel tanpa memodifikasi representasi warnanya secara langsung.
3. Menentukan area *bounding box* tambahan bagi GPU untuk melakukan sampling di luar batas asli frame view. Jika tidak ditentukan atau terlalu kecil, efek grafis yang meluas akan terpotong secara visual (*clipping artifacts*).
4. Core Animation menggunakan antarmuka IPC berbasis Mach Ports (XPC kernel abstractions) untuk mengirim transaksi layer dari proses klien ke proses `render server` (`backboardd`).
5. `half` (16-bit floating point) diproses dengan throughput dua kali lipat lebih cepat pada Apple Silicon GPU SIMD lanes dan mengonsumsi setengah bandwidth register/memori dibanding `float` (32-bit).

#### Intermediate
6. TBDR membagi layar menjadi tile-tile kecil (misal 16x16 piksel) yang seluruhnya disimpan di dalam On-Chip SRAM berkecepatan tinggi. Shading dilakukan hanya pada piksel yang benar-benar terlihat (*Hidden Surface Removal*), memangkas konsumsi daya dan bandwidth DRAM eksternal secara drastis saat memproses shader berlapis.
7. Tanpa pembatasan minimum interval, `TimelineView` akan dievaluasi pada kecepatan refresh display tertinggi (120 FPS / 8.33 ms per frame pada ProMotion). Jika thread UI memiliki pekerjaan lain, alokasi konstan setiap frame akan membebani thread allocator dan memicu frame pacing instability.
8. *Commit Hitch*: Waktu terbuang pada proses aplikasi utama (CPU) dalam mempersiapkan transaksi layer (layout, hierarchy resolution, IPC send) sebelum mencapai render server. *Render Hitch*: Waktu terbuang saat render server memproses frame atau GPU kewalahan merasterisasi instruksi grafis sehingga frame terlambat ditampilkan ke display controller.
9. `.drawingGroup()` memaksa rendering pohon view ke tekstur off-screen Metal independen sebelum ditampilkan kembali. Jika pohon view berubah setiap frame, CPU harus terus mengalokasikan dan meng-copy buffer tekstur baru, menghilangkan keuntungan caching dan menghabiskan bandwidth bus memori.
10. `SwiftUI::Layer` direpresentasikan sebagai tekstur sampler 2D terabstraksi (`texture2d<half>`) yang menyediakan metode `.sample(float2 position)` dengan hardware filtering terintegrasi.

#### Skenario Kasus Produksi
11. **Akar Masalah**: Fungsi shader mencoba membaca koordinat piksel di luar memori tekstur yang valid akibat formula distorsi menghasilkan nilai NaN (*Not a Number*) atau infinitas (misalnya pembagian dengan nol saat jarak radius bernilai 0: `position / distance`). 
    **Solusi**: Tambahkan penanganan batas eksplisit pada MSL: `float safeDistance = max(distance, 0.0001);` dan lakukan pengecekan `isnan()` atau `isinf()` sebelum mengembalikan koordinat baru.
12. **Akar Masalah**: View recycling pada `LazyVStack` menghancurkan dan membuat ulang Metal render contexts secara berulang-ulang, memaksa Metal menginisialisasi tekstur intermediate baru setiap frame scroll.
    **Solusi**: Hindari penggunaan `.layerEffect` langsung di dalam baris *lazy collection*. Flatten rendering kartu menggunakan `.drawingGroup()` statis, atau batasi rendering shader hanya pada kartu yang sedang aktif/berhenti bergulir.
13. **Langkah Diagnosa**:
    - Buka *Instruments -> Metal System Trace*.
    - Periksa trace *Thermal State Changed Notification* untuk memastikan titik waktu pelambatan dipicu oleh Thermal Throttling OS.
    - Cek *ALU vs Texture Fetch utilization* pada track GPU. Jika ALU mendekati 100%, optimalkan kode MSL (ganti operasi transcendental `sin`/`cos` berat dengan lookup table atau aproksimasi polynomial).
    - Cek alokasi memori di *Allocations Instrument*: Pastikan tidak ada capture context SwiftUI yang bocor (*retain cycle*) pada closure `TimelineView`.

---

### 16. Summary
- Integrasi **SwiftUI dan Metal Shading Language** via `ShaderLibrary` memindahkan beban rendering dari CPU Main Thread langsung ke GPU SIMD units Apple Silicon secara efisien.
- Tiga modifier kunci: **`colorEffect`** (manipulasi piksel mandiri), **`distortionEffect`** (spasial/koordinat piksel), dan **`layerEffect`** (multi-pass rasterisasi kontekstual).
- Menguasai pipeline rendering internal Core Animation (Client App -> Mach Port IPC -> CA Render Server -> TBDR GPU Execution) adalah prasyarat fundamental untuk mengeliminasi **Commit Hitches** dan **Render Hitches** demi mengunci kestabilan **120 FPS ProMotion**.
- Selalu prioritaskan tipe data presisi **`half`**, hindari alokasi heap di dalam execution block `TimelineView`, dan gunakan alat profil industri seperti **Xcode Instruments (Core Animation & Metal System Trace)** untuk memvalidasi efisiensi termal dan konsumsi daya aplikasi skala enterprise.