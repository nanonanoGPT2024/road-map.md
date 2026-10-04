# SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: `SWIFTUI-MOD-06-01`
* **Kategori**: `02-Programming-Languages`
* **Mata Pelajaran**: Arsitektur & Rekayasa Antarmuka SwiftUI Lanjutan
* **Judul Modul**: Graphics, Metal, & Advanced Animations
* **Tingkat Kesulitan**: Advanced / Expert
* **Target Platform**: iOS 17.0+, macOS 14.0+, iPadOS 17.0+
* **Tooling Minimal**: Xcode 15.0+, Swift 5.9+, Metal 3.1
* **Prasyarat**:
  * Penguasaan mendalam siklus hidup View SwiftUI (`body`, Identity, Lifetime, Dependencies).
  * Pemahaman dasar arsitektur GPU: Alur Pipeline Grafis (Rasterization, Shaders, Framebuffer).
  * Pengetahuan kalkulus dasar & aljabar linier (Vektor, Matriks Transformasi, Trigonometri).
  * Familiaritas sintaks C++ dasar untuk membaca *Metal Shading Language* (MSL).

---

# SEKSI 02 — LEARNING OBJECTIVES

1. **Menganalisis dan Mengimplementasikan Pipeline Grafis SwiftUI Tingkat Rendah**: Memahami bagaimana `RenderServer` Core Animation mendelegasikan beban komputasi grafis ke GPU melalui integrasi `Canvas`, `Path`, dan layer Metal backing.
2. **Menguasai Protokol `Animatable` dan `VectorArithmetic`**: Mengabstraksi dan menginterpolasi state kustom non-trivial melalui manipulasi `animatableData` dan struktur data hierarki `AnimatablePair`.
3. **Mengintegrasikan Metal Shading Language (MSL) dengan SwiftUI**: Menulis, mengompilasi, dan menghubungkan stitchable shaders (`colorEffect`, `distortionEffect`, dan `layerEffect`) menggunakan runtime `ShaderLibrary`.
4. **Membangun Sistem Animasi Multi-Fase Deklaratif**: Mengimplementasikan `PhaseAnimator` dan `KeyframeAnimator` untuk koreografi animasi berbasis kurva spline kompleks tanpa bergantung pada mutasi state imperatif eksternal.
5. **Mendiagnosis dan Mengoptimalkan Frame Budgeting**: Melakukan profiling dropped frames, offscreen rendering, shader invocation overhead, dan GPU memory bandwidth menggunakan Xcode Instruments (Core Animation & Metal System Trace).

---

# SEKSI 03 — MINDSET & MENTAL MODEL

Dalam paradigma SwiftUI standar, pengembang beroperasi di ranah deklaratif tingkat tinggi: deklarasikan *state*, SwiftUI memetakan ke pohon ketergantungan tampilan, dan *diffing engine* memutuskan bagian mana yang dimutasi. 

Namun, saat memasuki domain **Graphics & Advanced Animations**, mental model ini harus diperluas menjadi pemahaman berbasis hardware:

```
[State Mutation] 
      │
      ▼
[Layout & Frame Calculation] (Main Thread / CPU)
      │
      ▼
[Display Tree / Layer Hierarchy Generation] (Render Server / CPU)
      │
      ▼
[Vertex Processing & Rasterization] (GPU Pipeline)
      │
      ▼
[Fragment Processing / Metal Shaders] (GPU Execution Units)
      │
      ▼
[Framebuffer / Screen Output at 120Hz (8.33ms Budget)]
```

### Konsep Mental Esensial:
1. **CPU vs. GPU Duality**: Main Thread (CPU) bertanggung jawab terhadap kalkulasi koordinat, layout, dan evaluasi *spring curves*. GPU bertanggung jawab memproses jutaan piksel (fragment) secara paralel. Hambatan (*bottleneck*) animasi 90% berasal dari mutasi layout berulang di CPU atau kompilasi offscreen pass di GPU.
2. **Rasterization vs. Vector Primitives**: `Path` dan `Shape` didefinisikan secara matematis. `Canvas` adalah medium *immediate-mode drawing context* yang dirender secara deferred ke dalam raster buffer. Memahami kapan harus mempertahankan representasi vektor vs membekukan tampilan ke dalam rasterized layer adalah kunci performa 120 fps.
3. **Interpolasi Sebagai Fungsi Kontinu**: Animasi bukan sekadar perubahan dari nilai A ke B. Animasi adalah fungsi diferensial dari waktu $f(t) \to \mathbb{R}^n$, di mana $t \in [0, 1]$. Protokol `Animatable` memaksa pengembang berpikir secara matematis: objek apa pun dapat dianimasikan selama memenuhi ruang vektor (*vector space*).

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Integrasi antara SwiftUI, Core Animation, Metal, dan GPU Display Server beroperasi melalui alur hierarki berikut:

```
+-------------------------------------------------------------------------+
|                              SWIFTUI LAYER                              |
|  - View Hierarchy / Body Evaluation                                    |
|  - Custom Shapes / Path Generators                                     |
|  - PhaseAnimator / KeyframeAnimator                                    |
+------------------------------------+------------------------------------+
                                     |
                                     | Evaluates to Native Primitives
                                     v
+------------------------------------+------------------------------------+
|                         CORE ANIMATION / RENDER SERVER                  |
|  - CAContext & Commit Transaction                                      |
|  - Layer Tree Construction (CALayer, CAMetalLayer)                     |
|  - CA::Render Engine Encoding                                          |
+------------------------------------+------------------------------------+
                                     |
                                     | Translates via Metal Backing
                                     v
+-------------------------------------------------------------------------+
|                           METAL GRAPHICS PIPELINE                       |
|                                                                         |
|   +-----------------------+     +----------------------------------+    |
|   | SwiftUI Shaders (MSL) |     | Geometry & Vertex Shading        |    |
|   | - distortionEffect()  |     | - Triangle Meshes from Paths     |    |
|   | - layerEffect()       |     | - Coordinate Space UV Transform  |    |
|   | - colorEffect()       |     |                                  |    |
|   +-----------+-----------+     +----------------+-----------------+    |
|               |                                  |                      |
|               +----------------+-----------------+                      |
|                                |                                        |
|                                v                                        |
|             +--------------------------------------+                    |
|             | Fragment / Pixel Processing Engine   |                    |
|             +------------------+-------------------+                    |
+--------------------------------|----------------------------------------+
                                 |
                                 | Direct Blit
                                 v
+-------------------------------------------------------------------------+
|                        DISPLAY HARDWARE (ProMotion)                     |
|   Display Pipeline (8.33ms budget for 120fps / 16.66ms for 60fps)      |
+-------------------------------------------------------------------------+
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Mekanisme `Animatable` dan `VectorArithmetic`
Ketika sebuah view dianimasikan dengan interpolasi kustom, SwiftUI tidak melakukan snapshotting terhadap frame intermediary di CPU. Sebaliknya:
* SwiftUI membaca properti `animatableData`.
* Properti ini harus mengadopsi `VectorArithmetic`, yang mendefinisikan operasi dasar aljabar vektor: penambahan (`+`), pengurangan (`-`), dan penskalaan skalar (`scale(by:)`).
* Core Animation Render Server menghitung delta nilai pada setiap tick display link ($t$), menghitung nilai interpolasi $V(t) = V_{start} + (V_{end} - V_{start}) \cdot f(t)$, dan menginjeksikannya kembali ke accessor `animatableData`.
* `body` dari Shape atau modifier dievaluasi ulang dengan nilai $V(t)$ tersebut tanpa memicu invalidasi view pohon induk.

### 2. Arsitektur Metal Shader Interop (iOS 17+)
Mulai iOS 17, SwiftUI memperkenalkan API shader berbasis runtime (`ShaderLibrary`) yang mengeksekusi kode MSL langsung di dalam render pass SwiftUI:
* **`colorEffect`**: Menerima koordinat fragmen dan warna fragmen saat ini (`half4`). Menghasilkan nilai warna baru tanpa mengubah koordinat fisik piksel. Operasi ini berjalan isolated pada fragment processor.
* **`distortionEffect`**: Menerima posisi fragmen target (`float2`) dan mengembalikan posisi sumber yang harus disampel. Metal memetakan UV sampler secara non-linear tanpa menghasilkan representasi mesh baru.
* **`layerEffect`**: Mentransformasi seluruh representasi sub-tree tampilan sebagai raster texture buffer (`SwiftUI::Layer`). Memungkinkan operasi convolution, spatial multi-pass blurring, atau fluid displacement.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Ruang Vektor Animasi Lanjutan: Multi-Dimensi via `AnimatablePair`
Bila sebuah komponen grafis memiliki lebih dari satu parameter animasi (misalnya: radius poligon, deformasi kurva, dan offset sudut), tipe skalar tunggal seperti `Double` atau `CGFloat` tidak lagi memadai. Kita harus menyusun *composite vector space* menggunakan `AnimatablePair`.

```swift
AnimatablePair<CGFloat, AnimatablePair<CGFloat, CGFloat>>
```

Struktur ini merepresentasikan vektor berdimensi 3: $\mathbf{x} = \begin{bmatrix} x_1 \\ x_2 \\ x_3 \end{bmatrix} \in \mathbb{R}^3$. Operasi skalar didistribusikan secara rekursif melalui operator aljabar:
$$\alpha \mathbf{x} = \begin{bmatrix} \alpha x_1 \\ \alpha x_2 \\ \alpha x_3 \end{bmatrix}$$

### 2. Metal Shading Language (MSL) Bridge
Fungsi Metal stitchable diwajibkan menggunakan atribut atributifikasi `[[stitchable]]`. Atribut ini memberitahu Metal compiler untuk menghasilkan metadata binding signature yang dapat dipanggil secara dinamis oleh SwiftUI runtime:

```metal
#include <metal_stdlib>
#include <SwiftUI/SwiftUI_Metal.h>
using namespace metal;

[[stitchable]] half4 calculateChroma(float2 position, half4 currentColor, float time);
```

Secara internal:
1. File `.metal` di bundle aplikasi dikompilasi oleh Xcode menjadi `default.metallib`.
2. Saat aplikasi dieksekusi, `ShaderLibrary` memetakan simbol `calculateChroma` menggunakan symbol table yang tersimpan di `default.metallib`.
3. Parameter yang dikirim dari Swift (seperti `Float`, `SIMD2<Float>`, `Color`) dikonversi ke representasi tipe C++/MSL standar (`float`, `float2`, `half4`) menggunakan memory layout alignment yang kompatibel (standar std140 / Metal alignment rules).

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi poligon reguler adaptif yang mampu mengubah jumlah sisi (*sides*) dan faktor pembulatan kurva (*smoothness*) secara mulus (*morphing*) menggunakan integrasi `AnimatablePair` dan `Path`.

```swift
import SwiftUI

// MARK: - 1. Shape Implementation
public struct MorphingRegularPolygon: Shape {
    private var sides: Double
    private var smoothness: Double

    // Properti animasi gabungan: AnimatablePair merepresentasikan (sides, smoothness)
    public var animatableData: AnimatablePair<Double, Double> {
        get {
            AnimatablePair(sides, smoothness)
        }
        set {
            sides = newValue.first
            smoothness = newValue.second
        }
    }

    public init(sides: Double, smoothness: Double = 0.0) {
        self.sides = max(3.0, sides)
        self.smoothness = min(max(0.0, smoothness), 1.0)
    }

    public func path(in rect: CGRect) -> Path {
        var path = Path()
        let center = CGPoint(x: rect.midX, y: rect.midY)
        let radius = min(rect.width, rect.height) / 2.0
        
        let integerSides = Int(floor(sides))
        let fractionalPart = sides - Double(integerSides)
        let totalVertices = fractionalPart > 0.001 ? integerSides + 1 : integerSides
        
        guard totalVertices >= 3 else { return path }

        var rawPoints: [CGPoint] = []
        let angleStep = (2.0 * .pi) / Double(sides)

        for i in 0..<totalVertices {
            let currentAngle = angleStep * Double(i) - (.pi / 2.0)
            let point = CGPoint(
                x: center.x + radius * cos(currentAngle),
                y: center.y + radius * sin(currentAngle)
            )
            rawPoints.append(point)
        }

        // Algoritma konstruksi path dengan kontrol kelengkungan (Bezier Cubic Splines)
        path.move(to: computeMidpoint(rawPoints[0], rawPoints[1]))

        for i in 0..<rawPoints.count {
            let current = rawPoints[i]
            let nextIndex = (i + 1) % rawPoints.count
            let next = rawPoints[nextIndex]
            
            let mid = computeMidpoint(current, next)
            
            if smoothness > 0.0 {
                // Interpolasi kontrol kurva berbasis faktor smoothness
                path.addQuadCurve(to: mid, control: current)
            } else {
                path.addLine(to: current)
                path.addLine(to: mid)
            }
        }
        path.closeSubpath()
        return path
    }

    private func computeMidpoint(_ p1: CGPoint, _ p2: CGPoint) -> CGPoint {
        CGPoint(x: (p1.x + p2.x) * 0.5, y: (p1.y + p2.y) * 0.5)
    }
}

// MARK: - 2. Interactive Harness View
public struct MorphingPolygonShowcase: View {
    @State private var sideCount: Double = 3.0
    @State private var cornerSmoothness: Double = 0.0

    public var body: some View {
        VStack(spacing: 40) {
            MorphingRegularPolygon(sides: sideCount, smoothness: cornerSmoothness)
                .fill(
                    LinearGradient(
                        colors: [.indigo, .cyan],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .frame(width: 250, height: 250)
                .shadow(color: .indigo.opacity(0.4), radius: 20, x: 0, y: 10)

            VStack(spacing: 20) {
                Text("Jumlah Sisi: \(sideCount, specifier: "%.2f")")
                    .font(.system(.body, design: .monospaced))

                HStack {
                    Button("-1 Sisi") {
                        withAnimation(.spring(response: 0.6, dampingFraction: 0.7)) {
                            sideCount = max(3.0, sideCount - 1.0)
                        }
                    }
                    .buttonStyle(.bordered)

                    Button("+1 Sisi") {
                        withAnimation(.spring(response: 0.6, dampingFraction: 0.7)) {
                            sideCount += 1.0
                        }
                    }
                    .buttonStyle(.borderedProminent)
                }

                Toggle("Smooth Edges", isOn: Binding(
                    get: { cornerSmoothness > 0.5 },
                    set: { isSmooth in
                        withAnimation(.easeInOut(duration: 0.4)) {
                            cornerSmoothness = isSmooth ? 1.0 : 0.0
                        }
                    }
                ))
                .frame(maxWidth: 200)
            }
            .padding()
        }
    }
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Evaluasi Logika Inti `MorphingRegularPolygon`:

* **Baris 5-6**: `sides` dan `smoothness` disimpan sebagai `Double`. Tipe data primitif ini mendasari kemampuan interpolasi non-diskrit (misal: transisi mulus dari segitiga ke segi-empat melewati 3.42 sisi).
* **Baris 9-18**: 
  ```swift
  public var animatableData: AnimatablePair<Double, Double> {
      get { AnimatablePair(sides, smoothness) }
      set {
          sides = newValue.first
          smoothness = newValue.second
      }
  }
  ```
  Implementasi protokol `Animatable`. Tanpa blok ini, mutasi nilai `sides` dari 3 ke 4 akan menyebabkan lompatan instan (*discrete jump*). Dengan mengekspos `AnimatablePair`, Core Animation mendelegasikan interpolasi nilai desimal berkelanjutan ke layout thread pada interval display refresh rate.
* **Baris 30-32**:
  ```swift
  let integerSides = Int(floor(sides))
  let fractionalPart = sides - Double(integerSides)
  let totalVertices = fractionalPart > 0.001 ? integerSides + 1 : integerSides
  ```
  Menangani morphing fraksional. Saat nilai bernilai $3.5$, algoritma mengalokasikan vertex ke-4 di posisi sudut parsial sehingga transisi geometri tidak mengalami diskontinuitas visual (*visual popping*).
* **Baris 48-60**:
  ```swift
  if smoothness > 0.0 {
      path.addQuadCurve(to: mid, control: current)
  } else {
      path.addLine(to: current)
      path.addLine(to: mid)
  }
  ```
  Pemetaan kurva kuadratik (*Quadratic Bezier*). Dengan mengarahkan `control` ke titik sudut riil dan mendarat di titik tengah garis (*midpoint*), kita mencapai kelengkungan $C^1$ continuity yang membulatkan sudut secara dinamis berdasarkan parameter `smoothness`.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Interactive Dynamic Audio Visualizer with Metal Shader Distortion
Aplikasi streaming musik profesional memerlukan komponen *Dynamic Organic Waveform Visualizer*. Persyaratan produksi meliputi:
1. Visualizer harus merespons fluktuasi amplitudo audio real-time (60–120 data updates per detik).
2. Tampilan grafis harus mengalami efek distorsi fluida (*fluid wave refraction*) tanpa membebani CPU.
3. Menghindari alokasi objek memory terus menerus di dalam method render untuk mencegah lonjakan Garbage Collection / ARC overhead.
4. Rendering harus mempertahankan frame rate stabil 120 FPS pada display ProMotion iOS.

### Solusi Arsitektural:
* Menggunakan **`Canvas`** untuk menggambar basis visualisasi spektrum frekuensi audio secara *immediate-mode*.
* Menggunakan **`TimelineView`** untuk memicu siklus rendering terikat display cadence.
* Mengintegrasikan **Metal Stitchable Distortion Shader** untuk mengeksekusi perhitungan trigonometri refraksi fluida langsung di fragment pipeline GPU.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

### 1. Metal Shader Source: `AudioShaders.metal`
Letakkan file ini pada target Xcode proyek Anda.

```metal
#include <metal_stdlib>
#include <SwiftUI/SwiftUI_Metal.h>
using namespace metal;

[[stitchable]] float2 audioWaveDistortion(
    float2 position,
    float2 size,
    float time,
    float intensity
) {
    // Normalisasi koordinat UV ke rentang [0.0, 1.0]
    float2 uv = position / size;
    
    // Perhitungan osilasi gelombang sinus ganda
    float waveX = sin((uv.y * 12.0) + (time * 4.0)) * (8.0 * intensity);
    float waveY = cos((uv.x * 16.0) + (time * 3.5)) * (12.0 * intensity);
    
    // Kembalikan koordinat fragmen sumber yang telah terdistorsi
    return position + float2(waveX, waveY);
}
```

### 2. SwiftUI Production Engine: `AudioVisualizerView.swift`

```swift
import SwiftUI

// Model data performa tinggi menggunakan unmanaged contiguous buffers
public final class AudioBufferState: ObservableObject {
    public static let sampleCount: Int = 32
    @Published public var spectrumSamples: [Float]

    public init() {
        self.spectrumSamples = Array(repeating: 0.1, count: Self.sampleCount)
    }

    // Simulasi ingestion data dari audio tapping node (CoreAudio/AVFoundation)
    public func updateSamplesDirectly(_ newSamples: [Float]) {
        guard newSamples.count == Self.sampleCount else { return }
        self.spectrumSamples = newSamples
    }
}

public struct MetalAudioVisualizer: View {
    @ObservedObject var audioState: AudioBufferState
    @State private var visualizerScale: CGFloat = 1.0
    private let startTime = Date()

    public init(audioState: AudioBufferState) {
        self.audioState = audioState
    }

    public var body: some View {
        TimelineView(.animation(minimumInterval: 1.0 / 120.0, paused: false)) { context in
            let elapsedTime = Float(context.date.timeIntervalSince(startTime))
            let maxIntensity = Float(audioState.spectrumSamples.max() ?? 0.1)

            GeometryReader { proxy in
                Canvas(rendersAsynchronously: true) { canvasContext, size in
                    let barWidth = size.width / CGFloat(AudioBufferState.sampleCount)
                    let baseCenterY = size.height / 2.0

                    for i in 0..<AudioBufferState.sampleCount {
                        let amplitude = CGFloat(audioState.spectrumSamples[i])
                        let barHeight = (size.height * 0.4) * amplitude
                        
                        let xPosition = CGFloat(i) * barWidth
                        let rect = CGRect(
                            x: xPosition + 1.0,
                            y: baseCenterY - (barHeight / 2.0),
                            width: max(1.0, barWidth - 2.0),
                            height: barHeight
                        )

                        // Rendering bar spektrum
                        let roundedPath = Path(roundedRect: rect, cornerRadius: 4.0)
                        let gradientColor = Color(
                            hue: Double(i) / Double(AudioBufferState.sampleCount),
                            saturation: 0.8,
                            brightness: 0.95
                        )
                        
                        canvasContext.fill(roundedPath, with: .color(gradientColor))
                    }
                }
                .distortionEffect(
                    ShaderLibrary.audioWaveDistortion(
                        .float2(proxy.size.width, proxy.size.height),
                        .float(elapsedTime),
                        .float(maxIntensity)
                    ),
                    maxSampleOffset: CGSize(width: 30, height: 30)
                )
                .scaleEffect(visualizerScale)
            }
        }
        .drawingGroup() // Force offscreen raster cache layer via Core Graphics / Metal
        .onAppear {
            // Menerapkan Advanced Keyframe / Phase animation pulse
            withAnimation(.easeInOut(duration: 1.2).repeatForever(autoreverses: true)) {
                visualizerScale = 1.05
            }
        }
    }
}

// MARK: - Preview Harness with Live Audio Mock Generator
#Preview("Production Audio Visualizer") {
    struct MockContainer: View {
        @StateObject private var bufferState = AudioBufferState()
        let timer = Timer.publish(every: 0.05, on: .main, in: .common).autoconnect()

        var body: some View {
            ZStack {
                Color.black.ignoresSafeArea()
                
                VStack(spacing: 40) {
                    MetalAudioVisualizer(audioState: bufferState)
                        .frame(height: 250)
                        .padding(.horizontal, 20)

                    Text("Metal GPU Native Distortion Active")
                        .font(.caption)
                        .fontWeight(.bold)
                        .foregroundColor(.green)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 8)
                        .background(Color.green.opacity(0.15))
                        .cornerRadius(20)
                }
            }
            .onReceive(timer) { _ in
                // Menghasilkan fake harmonic data
                var newValues: [Float] = []
                for idx in 0..<AudioBufferState.sampleCount {
                    let pseudoRandom = Float.random(in: 0.15...0.95)
                    let envelope = sin(Float(idx) / Float(AudioBufferState.sampleCount) * .pi)
                    newValues.append(pseudoRandom * envelope)
                }
                bufferState.updateSamplesDirectly(newValues)
            }
        }
    }

    return MockContainer()
}
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Kriteria Penilaian | SwiftUI Standard Shapes (`Path`) | SwiftUI `Canvas` (Immediate API) | SwiftUI + Metal Shaders (`ShaderLibrary`) | Native UIKit/MetalKit (`MTKView`) |
| :--- | :--- | :--- | :--- | :--- |
| **Tingkat Abstraksi** | Sangat Tinggi (Deklaratif murni) | Menengah (Command-based 2D) | Menengah (Hybrid Swift-MSL) | Rendah (Imperatif C++/Metal) |
| **Beban CPU vs GPU** | CPU bound saat path generation | Seimbang, CPU memproses context | GPU Bound (Fragment Shaders) | GPU Direct Encoding |
| **Performa pada 10.000 Node**| Sangat Buruk (Tree Explosion) | Sangat Tinggi (Single context pass) | Tinggi (Piksel distorsi dinamis) | Ekstrem (Draw call instancing) |
| **Kemudahan Pemeliharaan** | Ekstrem Sederhana | Sederhana, isolasi grafis | Menengah (Butuh pemahaman UV) | Rumit (Setup pipeline, buffer, swapchain) |
| **Dukungan Dynamic Type/A11y**| Native terintegrasi otomatis | Memerlukan manual parsing accessibility | Inherited dari sub-view tree | Terpisah sepenuhnya dari antarmuka |
| **Konsumsi Alokasi Memori**| Tinggi jika Shape di-generate ulang | Rendah jika context dioptimasi | Tergantung batas `maxSampleOffset` | Sangat rendah, dikontrol eksplisit via pool |

---

# SEKSI 12 — EDGE CASES & PITFALLS

1. **`maxSampleOffset` Bounds Clipping**: Pada `distortionEffect`, parameter `maxSampleOffset` menentukan alokasi margin padding rendering buffer oleh SwiftUI. Jika shader Anda memindahkan piksel sebesar 50pt tetapi Anda menetapkan `maxSampleOffset: CGSize(width: 10, height: 10)`, hasil render akan terpotong secara tajam (*clipping visual artifact*) di luar bounding box asli.
2. **NaN/Infinite Values Propagation pada MSL**: Jika persamaan matematika dalam Metal Shader membagi nilai dengan $0$ atau melakukan `log()` pada bilangan negatif, fragment processor akan mengembalikan nilai NaN. SwiftUI akan merender seluruh layer yang terkena dampak sebagai **hitam pekat (blackout screen)** atau **transparan seketika**. Selalu gunakan fungsi penjagaan: `clamp()` atau `max(0.0001f, val)`.
3. **Precision Overflow pada AnimatableData**: Menggunakan struktur data yang terlalu besar di `AnimatablePair` bertingkat lebih dari 4 level (`AnimatablePair<A, AnimatablePair<B, AnimatablePair<...>>>`) dapat memicu degradasi memori dan penurunan *stack evaluation speed* pada Core Animation, menyebabkan *dropped frames* parah saat inisiasi gestur.
4. **Color Space Inconsistency**: Metal shader beroperasi secara default pada **Linear sRGB Space** atau **Extended Linear Display P3**. SwiftUI colors secara default berada pada format Gamma-corrected sRGB/P3. Melewatkan warna dari Swift ke Metal via `.colorEffect` memerlukan kesadaran bahwa operasi aritmatika linear dapat tampak *washed out* (memudar) jika inverse gamma correction tidak diperhitungkan.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Anti-Pattern 1: Mengalokasikan Objek / Collection di dalam Scope `Canvas` Draw Pass
```swift
// BURUK: Alokasi memori berulang dieksekusi 120 kali per detik
Canvas { context, size in
    let points = (0..<1000).map { CGPoint(...) } // ALOKASI MASSAL TIAP FRAME!
    context.stroke(...)
}
```
**Perbaikan**: Alokasikan cache buffer di luar context atau gunakan primitive iterasi instan tanpa array allocation intermediet:
```swift
// BENAR: Menggambar secara streaming tanpa alokasi memori
Canvas { context, size in
    for i in 0..<1000 {
        let pt = CGPoint(...)
        // Operasi direct draw
    }
}
```

### Anti-Pattern 2: Menggunakan Shaders Tanpa Guarding Device Capabilities
Mengeksekusi `ShaderLibrary` di simulator lama atau perangkat sebelum chip A12 Bionic tanpa memverifikasi ketersediaan driver dapat menyebabkan visual fallback error.
**Solusi**: Pastikan selalu melakukan fallback dekoratif menggunakan conditional compiler checks dan platform runtime availability.

### Anti-Pattern 3: Animasi State Berulang Menggunakan `DispatchQueue.main.asyncAfter`
Menggunakan loop `asyncAfter` untuk membuat loop animasi berkelanjutan. Pola ini memicu desinkronisasi clock dan memory retention cycle.
**Perbaikan**: Gunakan `PhaseAnimator` deklaratif atau `TimelineView(schedule: .animation, ...)`.

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Modularisasi Kode Metal (`.metal` isolation)**: Simpan seluruh fungsi MSL pada folder terdedikasi `Shaders/`. Jangan mencampur shader SwiftUI dengan Compute Shaders atau pipeline rendering Metal murni kecuali diperlukan modular targets.
2. **Kompilasi Ahead-Of-Time (AOT)**: Gunakan flag build setting Xcode `METAL_ENABLE_DEBUG_INFO = NO` pada release mode untuk memangkas ukuran `default.metallib`.
3. **Immutability pada Input Shader**: Semua parameter yang diinjeksikan ke `ShaderLibrary` harus bersifat stateless per-frame. Jangan mengandalkan shader state caching internal di Metal untuk SwiftUI effects.
4. **Adaptive Cadence Scaling**: Batasi kecepatan pembaruan animasi jika perangkat mengaktifkan *Low Power Mode*. Gunakan environment variable `@Environment(\.accessibilityReduceMotion)` untuk mematikan shader distorsi non-esensial bagi pengguna yang rentan terhadap motion sickness.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Frame Budgeting Matrix (Display Rate Mechanics)
* **60 Hz Standard Display**: Jendela eksekusi CPU + GPU maksimal adalah **16.66 milidetik**.
* **120 Hz ProMotion Display**: Jendela eksekusi CPU + GPU maksimal adalah **8.33 milidetik**.

Untuk menjamin alokasi rendering stabil di bawah 8.33ms:
* **Offscreen Render Pass Minimization**: Hindari penggunaan `.cornerRadius()` bersamaan dengan `.shadow()` pada hierarki yang memiliki Metal shader aktif. Kombinasi ini memaksa GPU membuat alokasi *intermediate offscreen texture*, menggandakan konsumsi bandwidth memori.
* **`drawingGroup()` Strategy**: Aktifkan modifier `.drawingGroup(opaque: true, colorMode: .nonLinear)` pada tree grafis yang kompleks. Ini memerintahkan SwiftUI menggabungkan hierarki subview menjadi satu CALayer berbasis Metal framebuffer, memangkas tree composition overhead dari Core Animation Render Server.

---

# SEKSI 16 — KEAMANAN & HARDENING

1. **Buffer Overread Prevention pada Custom Metal Shading**: Di Metal MSL, shader berbasis `distortionEffect` menerima sampling argument berupa `position`. Selalu pastikan koordinat yang dihitung tidak merujuk memory di luar rentang texture bounds dengan memanfaatkan fungsi intrinsik Metal:
   ```metal
   float2 boundedUV = clamp(targetUV, float2(0.0f), float2(1.0f));
   ```
2. **Input Sanitization dari External Vectors**: Ketika shader mengonsumsi data dari luar (misal: amplitude data via jaringan/Bluetooth/Audio Device), sanitasi nilai skalar di level Swift menggunakan `.isFinite`:
   ```swift
   let sanitizedIntensity = input.isFinite ? max(0.0, min(input, 10.0)) : 0.0
   ```
   Menyuntikkan nilai `Float.infinity` ke Metal shader menyebabkan instabilitas driver GPU (*kernel panic / system UI freeze*).

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### Tooling Profiling Metal & SwiftUI:
1. **Xcode Instruments -> Core Animation Pipeline Tool**:
   * Amati metrik **"Frame Lifetimes"**.
   * Identifikasi fase yang mengalami lonjakan durasi: *App Commit*, *Render Server*, atau *Display Driver*.
2. **Instruments -> Metal System Trace**:
   * Melacak *Vertex & Fragment Execution Time*.
   * Memeriksa keberadaan GPU memory pipeline stalls yang disebabkan oleh pemanggilan tekstur berukuran raksasa.
3. **Debug Flags Khusus Core Animation**:
   Aktifkan pada environment skema run:
   * `CA_DEBUG_TRANSACTIONS=1` : Mencatat setiap mutasi transaksi implicit Core Animation di konsol debug.
   * `CA_COLOR_OPAQUE=1` : Mewarnai layer non-opaque menjadi merah untuk mendeteksi alpha compositing berlebih di layar.

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

```swift
// 1. Morphing Shape Data Structure
struct CustomShape: Shape {
    var animatableData: Double // Mengadopsi VectorArithmetic
    func path(in rect: CGRect) -> Path { ... }
}

// 2. SwiftUI to Metal Shader Invocations (iOS 17+)
// File: Operations.metal -> [[stitchable]] half4 tint(float2 pos, half4 col, float factor);
view.colorEffect(ShaderLibrary.tint(.float(0.5)))

// File: Operations.metal -> [[stitchable]] float2 wave(float2 pos, float time);
view.distortionEffect(ShaderLibrary.wave(.float(time)), maxSampleOffset: .zero)

// 3. Multi-Phase Declarative Animation
view.phaseAnimator([0.0, 10.0, -10.0], trigger: triggerState) { content, phase in
    content.offset(y: phase)
} animation: { phase in
    .spring(response: 0.3, dampingFraction: 0.6)
}

// 4. Rasterization Opt-in
view.drawingGroup() // Alihkan layer stack ke GPU backing store tunggal
```

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)
1. **Apa fungsi dari protokol `VectorArithmetic` pada framework SwiftUI?**
   * *Jawaban*: Menyediakan operasi matematika dasar (penambahan, pengurangan, dan penskalaan skalar) yang dibutuhkan mesin animasi SwiftUI untuk menghitung interpolasi antar dua nilai secara kontinu.
2. **Kapan Anda harus menggunakan `Canvas` alih-alih menyusun kombinasi `ZStack` dari banyak elemen `Shape`?**
   * *Jawaban*: Ketika Anda perlu menggambar ratusan atau ribuan elemen dinamis per frame. `Canvas` menggunakan context drawing immediate-mode yang meminimalkan overhead alokasi node view tree.
3. **Apa fungsi atribut `[[stitchable]]` pada fungsi Metal Shading Language (MSL)?**
   * *Jawaban*: Memberitahu Metal compiler untuk membuat ABI metadata binding yang memungkinkan runtime SwiftUI (`ShaderLibrary`) memanggil fungsi shader tersebut secara dinamis.
4. **Apa batasan utama dari modifier `.colorEffect()`?**
   * *Jawaban*: `.colorEffect()` hanya dapat mengubah nilai warna (RGBA) dari fragmen/piksel yang sedang diproses; efek ini tidak dapat mengubah atau memindahkan koordinat spasial piksel tersebut.
5. **Mengapa nilai `maxSampleOffset` pada `.distortionEffect()` harus diisi secara akurat dan tidak boleh bernilai sembarangan?**
   * *Jawaban*: Nilai tersebut mendefinisikan margin padding alokasi buffer rendering oleh SwiftUI. Jika terlalu kecil, distorsi akan terpotong secara visual (*clipped*); jika terlalu besar, alokasi memori tekstur offscreen akan terbuang percuma.

### Soal Tingkat Menengah/Lanjutan (Intermediate)
6. **Bagaimana cara mengabstraksikan struktur state yang memiliki 3 parameter grafis berbeda agar dapat dianimasikan secara simultan dalam satu Shape?**
   * *Jawaban*: Menggunakan sarang (*nested*) `AnimatablePair`, misalnya `AnimatablePair<CGFloat, AnimatablePair<CGFloat, CGFloat>>`, yang secara rekursif mengadopsi protokol `VectorArithmetic`.
7. **Jelaskan perbedaan mendasar antara `.colorEffect` dan `.layerEffect`!**
   * *Jawaban*: `.colorEffect` beroperasi secara terisolasi per fragmen tanpa mengetahui piksel tetangga. `.layerEffect` menerima argumen berupa representasi tekstur layer utuh (`SwiftUI::Layer`), memungkinkan sampling spasial bebas (misalnya untuk filter Gaussian Blur atau convolutional filtering).
8. **Apa yang terjadi di layar jika Metal Shader Anda menghasilkan evaluasi numerik NaN (Not a Number)?**
   * *Jawaban*: Area rendering yang terkena dampak akan menampilkan artefak visual parah, biasanya menjadi area hitam pekat (*blackout*) atau transparan seketika karena driver grafis membatalkan evaluasi fragmen yang tidak valid.
9. **Mengapa penggunaan `.drawingGroup()` tidak selalu disarankan untuk semua hierarki SwiftUI?**
   * *Jawaban*: Karena `.drawingGroup()` memaksa proses rendering offscreen ke buffer Metal/Core Graphics. Jika diterapkan pada antarmuka teks/UI standar beresolusi rendah, alokasi dan swap texture layer justru menambah latency dan mematikan optimasi render engine native Core Animation.
10. **Bagaimana `TimelineView` berkoordinasi dengan ProMotion Display (120Hz) pada perangkat Apple?**
    * *Jawaban*: Melalui engine `.animation(minimumInterval:paused:)`, `TimelineView` mendaftarkan callback ke Core Animation CADisplayLink internal, menerima pulsa sinkronisasi refresh rate perangkat secara adaptif (misal: 120Hz saat interaksi aktif, melambat ke 24Hz/30Hz saat statis).

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek: "Interactive Liquid Metal Glass Morphism Engine"

### Spesifikasi Kebutuhan Proyek:
Rancang dan bangun sebuah modul antarmuka komponen kartu (*Card Component*) yang mengimplementasikan efek kaca fluida interaktif (*Liquid Glass Distortion*):

1. **Metal Component**:
   * Tulis file `LiquidGlass.metal` dengan shader `layerEffect`.
   * Shader harus menerima input koordinat gestur sentuhan pengguna (`float2 touchPosition`), waktu (`float time`), dan intensitas viskositas cairan (`float viscosity`).
   * Shader harus menghasilkan efek pembiasan cahaya (refraksi) berbasis hukum Snellius sederhana atau distorsi gelombang sirkular teredam (*damped circular ripples*) yang memancar keluar dari posisi sentuhan.

2. **SwiftUI Layer**:
   * Bangun view `LiquidCardView` yang menampilkan konten teks, ikon, dan background gradien kompleks.
   * Hubungkan gestur sentuhan `DragGesture(minimumDistance: 0)` untuk memperbarui state koordinat yang diinjeksikan secara real-time ke shader Metal.
   * Gunakan `KeyframeAnimator` untuk menggerakkan pantulan bias cahaya (*specular highlight*) secara otomatis saat kartu tidak disentuh.

3. **Kriteria Penilaian Keberhasilan**:
   * Frame rate tidak boleh turun di bawah 118 FPS pada iPhone ProMotion saat gestur drag aktif (verifikasi melalui Profile Core Animation di Instruments).
   * Alokasi alokasi ARC Heap memory harus konstan (flatline memory graph, tanpa akumulasi memory leak).
   * Teks di dalam kartu tetap tajam dan dapat dibaca dengan jelas meskipun distorsi aktif di sekeliling permukaannya.
   * Komponen harus mendukung fallback dinamis jika dijalankan pada simulator atau OS yang tidak mendukung MSL Stitchable APIs.