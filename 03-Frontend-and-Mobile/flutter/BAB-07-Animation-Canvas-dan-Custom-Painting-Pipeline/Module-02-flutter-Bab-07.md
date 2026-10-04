# Kurikulum Rekayasa Perangkat Lunak Enterprise: Flutter Engine & Rendering Pipeline

## Topik: 03-Frontend-and-Mobile
## Bab 07: Animation, Canvas, dan Custom Painting Pipeline
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
*   **Menganalisis (Analyze)** siklus hidup rendering frame Flutter dari fase `Animate`, `Build`, `Layout`, `Paint`, hingga `Composite` dan `Rasterize` pada engine Skia dan Impeller.
*   **Mengevaluasi (Evaluate)** dampak arsitektural penggunaan `CustomPainter` versus direct subclassing `RenderObject` (`RenderBox`) terhadap throughput GPU dan pemanfaatan frame budget (16.67ms pada 60Hz, 8.33ms pada 120Hz).
*   **Merancang (Create)** sistem visualisasi data berkecepatan tinggi (*high-frequency streaming*) yang menerapkan isolasi layer render via `RepaintBoundary`, meminimalisasi *raster cache thrashing*, dan mengeliminasi alokasi memori pada fase `paint()`.
*   **Mendiagnosis dan Memitigasi (Troubleshoot)** masalah performa grafis seperti shader compilation jank, layer explosion, overdraw, serta memory leak pada objek `ui.Picture` dan `ui.Image`.

---

### 2. Prerequisites
Sebelum mempelajari modul ini, engineer wajib menguasai:
*   **Internal Dasar Flutter**: Pohon Widget, Element, dan RenderObject (Modul 01).
*   **Matematika Grafis Vektor**: Vektor 2D, transformasi matriks affine 4x4 (`Matrix4`), koordinat Kartesius, interpolasi Bézier (Cubic & Quadratic).
*   **Dasar Concurrency Dart**: Event loop, Microtasks, Streams, dan Isolates.
*   **Profiling Tools**: Flutter DevTools (CPU Profiler, Memory Profiler, dan Performance Overlay/Timeline).

---

### 3. Concept & Internal Architecture

#### Flutter Rendering Pipeline Phases
Proses rendering dalam Flutter Engine diorkestrasi oleh `SchedulerBinding` dan `PipelineOwner`. Setiap *vsync signal* dari sistem operasi memicu eksekusi tahapan pipeline berurutan:

```
[VSYNC Event]
      │
      ▼
1. VSYNC Phase (SchedulerBinding.handleBeginFrame)
      │  └── Tickers firing, AnimationController transitions
      ▼
2. Microtasks Execution
      ▼
3. Build Phase (BuildOwner.buildScope)
      │  └── Widget.build() -> Element tree dirty nodes rebuild
      ▼
4. Layout Phase (PipelineOwner.flushLayout)
      │  └── Constraints go down, Sizes go up (BoxConstraints -> Size)
      ▼
5. Compositing Bits Phase (PipelineOwner.flushCompositingBits)
      │  └── Mark RenderObjects requiring Layer updates
      ▼
6. Paint Phase (PipelineOwner.flushPaint)
      │  └── PaintingContext records Display Lists (ui.Picture)
      ▼
7. Composition Phase (PipelineOwner.flushCompositeFrame)
      │  └── SceneBuilder constructs Layer Tree -> ui.Scene
      ▼
8. Raster Phase (Engine: Impeller / Skia)
      │  └── GPU command execution (Vulkan/Metal/OpenGL)
      ▼
[Pixels on Display]
```

#### PaintingContext & Layer Tree Mechanics
`CustomPainter` tidak menggambar piksel secara langsung ke GPU framebuffer. Sebaliknya, ia beroperasi pada `PaintingContext` yang mengekspos `ui.Canvas`.
*   `ui.Canvas` bertindak sebagai *recorder interface* yang didukung oleh `ui.PictureRecorder`. Operasi seperti `drawLine`, `drawPath`, dan `drawRRect` dikompilasi menjadi representasi biner serial dari instruksi grafis yang disebut **Display List**.
*   Ketika `CustomPainter` menggambar, instruksi tersebut ditampung dalam sebuah `PictureLayer`.
*   Jika suatu sub-pohon `RenderObject` ditandai dengan `isRepaintBoundary = true`, Flutter Engine memutus propagasi pengecatan ke node *parent* dan mengalokasikan `OffsetLayer` tersendiri. Ini mencegah *dirty paint* merambat ke seluruh layer tree.

#### Backend Rendering: Skia vs. Impeller
*   **Skia**: Bergantung pada kompilasi shader saat *runtime* (Just-in-Time / JIT). Masalah klasik Skia adalah **Shader Compilation Jank**, di mana kompilasi driver GPU untuk efek grafis baru (misal: path clipping kompleks dengan blur) memakan waktu lebih dari 16ms pada frame pertama kemunculannya.
*   **Impeller (Modern Engine)**: Mengeliminasi runtime shader compilation dengan melakukan *Ahead-Of-Time* (AOT) compilation pada seluruh pipeline state objects (PSO) selama proses build aplikasi. Impeller melakukan dekonstruksi kurva dan poligon melalui algoritma *tessellation* langsung pada GPU compute/vertex stage, memotong latensi rasterisasi secara deterministik.

---

### 4. Why & What

#### Mengapa Standard Widgets Tidak Cukup?
Widget pohon standar (`Container`, `Row`, `Stack`, `Transform`) dibuat untuk fleksibilitas komposisi UI declaratif. Namun, untuk kasus penggunaan seperti visualisasi chart trading finansial real-time (60-120 ticks per detik) atau rendering audio spectrum:
*   Biaya re-konstruksi Element tree dan reconciliasi layout (`flushLayout`) menimbulkan *overhead CPU* yang besar.
*   Peningkatan jumlah node `RenderObject` secara eksponensial memperlambat traversal layout/paint.
*   Keterbatasan ekspresi visual: manipulasi raw canvas pixel, shader masking, komposit blend modes kompleks, dan transformasi mesh 2D kustom mustahil dilakukan hanya dengan komposisi widget bawaan.

#### Apa Solusinya?
*   Menggunakan `CustomPainter` dengan optimasi ketat (`shouldRepaint` granularity, canvas save/restore isolation).
*   Membangun kustom `RenderBox` ketika visualisasi membutuhkan kontrol terpadu atas protokol layout dan paint sekaligus tanpa perantara widget wrapper berlebih.
*   Pemanfaatan `RepaintBoundary` untuk mempartisi beban kerja antara UI statis dan kanvas dinamis berfrekuensi tinggi.

---

### 5. How (Workflow Detail)

Berikut adalah siklus operasional dalam mengimplementasikan custom render pipeline:

1.  **State Invalidation Strategy**: Jangan panggil `setState()` pada parent widget jika hanya kanvas yang berubah. Gunakan `Listenable` (seperti `ValueNotifier` atau `AnimationController`) yang dioper langsung ke konstruktor `super(repaint: listenable)` milik `CustomPainter`.
2.  **Paint Isolation**:
    *   Evaluasi ukuran kanvas via parameter `Size size`.
    *   Bungkus manipulasi kanvas dengan `canvas.save()` dan `canvas.restore()` jika melakukan mutasi koordinat (`canvas.translate()`, `canvas.rotate()`, `canvas.clipRect()`).
3.  **Eliminasi Alokasi Objek di `paint()`**:
    *   DILARANG keras menginisialisasi `Paint()`, `Path()`, `TextStyle()`, atau kalkulasi koleksi baru di dalam method `paint()`. Method ini dapat terpanggil hingga 120 kali per detik.
    *   Instansiasi objek-objek tersebut di level class/field, lalu lakukan *mutation/reset* (`path.reset()`, `paint.color = ...`).
4.  **Optimalisasi `shouldRepaint`**:
    *   Validasi dependensi data: bandingkan instance atau *sequence token* data lama (`oldDelegate`) dengan data baru. Kembalikan `false` jika data identik untuk memutus siklus paint.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sutradara Teater vs. Rekaman Video (RepaintBoundary)
Bayangkan panggung teater dengan dua aktor: seorang pembawa berita yang diam di podium (statis) dan seorang penari latar yang bergerak dinamis (60 FPS).
*   **Tanpa Boundary**: Setiap kali penari bergerak 1 milimeter, seluruh panggung teater (termasuk latar kayu dan pembawa berita) harus digambar ulang dari nol oleh pelukis.
*   **Dengan RepaintBoundary**: Sutradara menaruh kamera digital khusus di depan penari latar. Rekaman penari dialokasikan pada layer terpisah. Pelukis hanya menggambar ulang frame penari tersebut, lalu menempelkannya (komposisi) di atas panggung statis.

```
SCENE / LAYER TREE ARCHITECTURE:

[TransformLayer: Root Scene]
       │
       ├── [PictureLayer: UI Statis (AppBar, Background, Legend)] ──> Cache GPU OK
       │
       └── [OffsetLayer: RepaintBoundary] ── (Diisolasi dari Render Tree Utama)
                 │
                 └── [PictureLayer: Kanvas Dinamis Real-Time]
                           │
                           ├── Frame N   : DisplayList [Clear, DrawPath, Flush]
                           ├── Frame N+1 : DisplayList [Clear, DrawPath, Flush]
                           └── Overhead CPU/GPU terbatas HANYA pada sub-tree ini
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Menggambar Dial/Arc dengan Animasi Bezier
Contoh sederhana implementasi `CustomPainter` yang benar dengan isolasi `repaint`.

```dart
import 'dart:math' as math;
import 'package:flutter/material.dart';

class ProgressDialPainter extends CustomPainter {
  final double progress; // 0.0 to 1.0
  final Paint _backgroundPaint;
  final Paint _progressPaint;

  ProgressDialPainter({required this.progress})
      : _backgroundPaint = Paint()
          ..color = Colors.grey.shade300
          ..style = PaintingStyle.stroke
          ..strokeWidth = 12,
        _progressPaint = Paint()
          ..color = Colors.blueAccent
          ..style = PaintingStyle.stroke
          ..strokeCap = StrokeCap.round
          ..strokeWidth = 12;

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = math.min(size.width, size.height) / 2 - (_progressPaint.strokeWidth / 2);

    // Draw background track
    canvas.drawCircle(center, radius, _backgroundPaint);

    // Draw animated arc
    final sweepAngle = 2 * math.pi * progress;
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      -math.pi / 2, // Start at top
      sweepAngle,
      false,
      _progressPaint,
    );
  }

  @override
  bool shouldRepaint(covariant ProgressDialPainter oldDelegate) {
    return oldDelegate.progress != progress;
  }
}
```

#### Practical Example: High-Throughput Real-Time Sparkline Canvas
Implementasi industri: Chart gelombang data stream tanpa alokasi di `paint()`, digerakkan oleh `ChangeNotifier`, dan diisolasi dengan `RepaintBoundary`.

```dart
import 'dart:math' as math;
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

class TelemetryDataModel extends ChangeNotifier {
  final List<double> _points = [];
  List<double> get points => _points;

  void appendSample(double value) {
    if (_points.length > 500) {
      _points.removeAt(0);
    }
    _points.add(value);
    notifyListeners();
  }
}

class HighPerformanceWaveformPainter extends CustomPainter {
  final TelemetryDataModel telemetryModel;
  final Paint _linePaint;
  final Path _renderPath;

  HighPerformanceWaveformPainter({required this.telemetryModel})
      : _linePaint = Paint()
          ..color = const Color(0xFF00E676)
          ..strokeWidth = 2.0
          ..style = PaintingStyle.stroke
          ..isAntiAlias = true,
        _renderPath = Path(),
        super(repaint: telemetryModel);

  @override
  void paint(Canvas canvas, Size size) {
    final data = telemetryModel.points;
    if (data.isEmpty) return;

    _renderPath.reset();

    final double stepX = size.width / (data.length - 1 <= 0 ? 1 : data.length - 1);
    final double midY = size.height / 2;
    final double maxY = size.height / 2;

    for (int i = 0; i < data.length; i++) {
      final double x = i * stepX;
      // Normalisasi amplitude [-1.0, 1.0] ke rentang view size
      final double y = midY - (data[i].clamp(-1.0, 1.0) * maxY);

      if (i == 0) {
        _renderPath.moveTo(x, y);
      } else {
        _renderPath.lineTo(x, y);
      }
    }

    canvas.drawPath(_renderPath, _linePaint);
  }

  @override
  bool shouldRepaint(covariant HighPerformanceWaveformPainter oldDelegate) {
    return oldDelegate.telemetryModel != telemetryModel;
  }
}

class TelemetryDashboardView extends StatefulWidget {
  const TelemetryDashboardView({super.key});

  @override
  State<TelemetryDashboardView> createState() => _TelemetryDashboardViewState();
}

class _TelemetryDashboardViewState extends State<TelemetryDashboardView>
    with SingleTickerProviderStateMixin {
  late final TelemetryDataModel _dataModel;
  late final Ticker _ticker;
  double _phase = 0.0;

  @override
  void initState() {
    super.initState();
    _dataModel = TelemetryDataModel();
    // Mensimulasikan data stream 60hz via Ticker
    _ticker = createTicker((Duration elapsed) {
      _phase += 0.05;
      final sample = math.sin(_phase) * 0.7 + (math.Random().nextDouble() - 0.5) * 0.3;
      _dataModel.appendSample(sample);
    })..start();
  }

  @override
  void dispose() {
    _ticker.dispose();
    _dataModel.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF121212),
      appBar: AppBar(title: const Text('Real-Time Engine Visualizer')),
      body: Center(
        child: RepaintBoundary(
          child: Container(
            width: double.infinity,
            height: 250,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: CustomPaint(
              painter: HighPerformanceWaveformPainter(telemetryModel: _dataModel),
              child: const SizedBox.expand(),
            ),
          ),
        ),
      ),
    );
  }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario: L2 Depth Chart / Financial Order Book Engine
Sebuah crypto-exchange enterprise membutuhkan visualisasi Order-Book (kedalaman pasar bid/ask) yang mampu menangani *market burst* hingga 200 payload data delta per detik dari WebSocket.

#### Masalah Produksi
1.  **UI Jank**: Implementasi awal menggunakan standard layout `CustomMultiChildLayout` dan widget primitives menyebabkan *dropped frames* parah (frame rate anjlok ke 22 FPS).
2.  **Memory Churn**: Pembuatan list `Path` baru pada setiap kalkulasi *Market Depth Cumulative Fill* men-trigger Garbage Collector (GC) `Scavenge` setiap 1.5 detik.

#### Solusi Rekayasa
1.  **Double Buffering Memory Strategy**:
    *   Buat `Float32List` statis berukuran tetap untuk representasi array koordinat X/Y.
    *   Hilangkan serialisasi Objek Dart: Data dari worker isolate langsung dipetakan ke typed data buffers menggunakan `transferableByteBuffer`.
2.  **RenderBox Subclassing**:
    Mengganti `CustomPainter` dengan kustom `RenderBox` untuk menggabungkan kalkulasi geometri langsung pada fase layout Flutter, mengeliminasi layout pass ganda.
3.  **Canvas Drawing Optimizations**:
    Gunakan `canvas.drawVertices()` dengan `VertexMode.triangleStrip` alih-alih kurva Bézier `drawPath()` yang kompleks. `drawVertices` memotong overhead tessellation pada engine dan langsung memetakan vertex buffers ke API grafis dasar (Metal/Vulkan).

```
[WebSocket Isolate] ──(TransferableTypedData)──> [UI Isolate]
                                                       │
                                          [Ring Buffer / Float32List]
                                                       │
                                                       ▼
                                          [Custom RenderBox Pipeline]
                                          - computeDryLayout()
                                          - paint() -> canvas.drawVertices()
                                                       │
                                                       ▼
                                             [GPU Hardware Raster]
```

---

### 9. Trade-offs

| Pendekatan | CPU Cost | GPU Memory Footprint | Kompleksitas Kode | Kasus Penggunaan Optimal |
| :--- | :--- | :--- | :--- | :--- |
| **Widget Trees Composition** | Tinggi (Layout & Element Diffing) | Sangat Rendah | Sangat Rendah | Antarmuka standar berbasis form dan list. |
| **Standard CustomPainter** | Rendah-Sedang | Rendah | Sedang | Visualisasi diagram, gauge, custom toggle, animasi transisi visual. |
| **RepaintBoundary Caching** | Sangat Rendah (di frame berulang) | Tinggi (Mengalokasikan GPU texture bitmap terpisah) | Rendah | Konten kompleks yang jarang berubah namun bergerak bersama (e.g. Map layers). |
| **Custom RenderBox** | Minimal (Zero framework overhead) | Terkontrol | Tinggi | Engine visualisasi performa ekstrim, Custom layout + paint fusion. |
| **Canvas `drawVertices`** | Rendah | Sangat Efisien | Sangat Tinggi (Manual Mesh & UV Mapping) | Rendering ribuan partikel simultan, visualisasi 3D/2.5D kustom. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Instansiasi Objek di Siklus `paint()`
*   *Bad*:
    ```dart
    void paint(Canvas canvas, Size size) {
      final paint = Paint()..color = Colors.red; // BAD: Alokasi memory per frame!
      final path = Path(); // BAD: Trigger GC thrashing
      ...
    }
    ```
*   *Fix*: Definisikan sebagai class member instance, bersihkan (`path.reset()`) dan gunakan kembali objek yang sama.

#### 2. Implementasi `shouldRepaint` yang Ceroboh
*   *Bad*: Selalu mengembalikan `true` (`bool shouldRepaint(...) => true;`). Ini membatalkan optimasi display-list reuse milik Flutter Engine, memicu rasterisasi berulang meskipun data tidak berubah.
*   *Fix*: Lakukan pengecekan identitas atau kesamaan field secara deterministik.

#### 3. Over-use `RepaintBoundary`
*   Menempatkan `RepaintBoundary` pada setiap item di dalam `ListView` panjang akan memicu **Layer Explosion**. Setiap boundary mengalokasikan backing store GPU texture. Hal ini menghabiskan VRAM perangkat seluler dan memicu crash *Out of Memory* (OOM).

#### 4. Shader Compilation Jank pada Path Clipping
*   *Gejala*: Aplikasi terasa *freeze* singkat saat dialog atau shape kustom dengan clipping muncul pertama kali di perangkat Android (engine Skia).
*   *Mitigasi*:
    1.  Upgrade ke Flutter 3.x+ dengan Impeller aktif (default pada iOS dan Android modern).
    2.  Hindari pemanggilan `canvas.clipPath()` jika efek visual dapat dicapai dengan menggambar geometri terbalik (alpha masking via `BlendMode.clear` atau `BlendMode.dstOut`).

---

### 11. Best Practices (Production Checklist)

*   [ ] **Zero-Allocation Paint**: Tidak ada pemanggilan constructor objek apapun (`new`, factories, `Color()`) di dalam tubuh method `paint()`.
*   [ ] **Correct Listeners Binding**: `CustomPainter` mengikat instance `Listenable` pada konstruktor `super(repaint: ...)` alih-alih me-rebuild widget tree menggunakan `setState()`.
*   [ ] **Strict Matrix Isolation**: Operasi kanvas `save()`, `translate()`, `scale()`, `rotate()`, `restore()` selalu dibungkus secara simetris dalam blok `try ... finally` jika ada logic bercabang.
*   [ ] **Canvas Boundary Checks**: Memvalidasi kondisi batas (`size.width <= 0 || size.height <= 0`) sebelum menjalankan instruksi visual untuk mencegah rendering artifacts.
*   [ ] **Optimal Layer Separation**: Menambahkan `RepaintBoundary` hanya pada area kanvas yang memiliki frekuensi render berbeda dari widget di sekitarnya.
*   [ ] **Text Layout Caching**: Jika mengecat teks pada Canvas, instansiasi `TextPainter` di-cache dan hanya memanggil `layout()` ulang jika constraints ukuran atau string teks bermutasi.
*   [ ] **Anti-Aliasing Management**: Matikan anti-aliasing (`paint.isAntiAlias = false`) untuk garis lurus vertikal/horizontal tepat pada piksel grid demi menghemat fill-rate GPU.

---

### 12. Hands-on Practice

Buat dan simpan implementasi berikut di direktori target modul: `hands-on/m02/`

#### File: `hands-on/m02/radar_chart_render_box.dart`
Terapkan kustom `RenderBox` murni yang merender visualisasi radar multi-axis interaktif tanpa menggunakan framework layer `CustomPainter`.

```dart
import 'dart:math' as math;
import 'package:flutter/rendering.dart';

class RenderRadarChart extends RenderBox {
  RenderRadarChart({
    required List<double> values,
    required Color chartColor,
  })  : _values = values,
        _chartColor = chartColor {
    _polygonPaint = Paint()
      ..color = _chartColor.withOpacity(0.4)
      ..style = PaintingStyle.fill;

    _strokePaint = Paint()
      ..color = _chartColor
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.0;

    _gridPaint = Paint()
      ..color = const Color(0xFF616161)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 0.8;
  }

  List<double> _values;
  Color _chartColor;

  late Paint _polygonPaint;
  late Paint _strokePaint;
  late Paint _gridPaint;
  final Path _polygonPath = Path();

  set values(List<double> newValues) {
    if (_values == newValues) return;
    _values = newValues;
    markNeedsPaint(); // Hanya paint yang kotor, ukuran tidak berubah
  }

  set chartColor(Color newColor) {
    if (_chartColor == newColor) return;
    _chartColor = newColor;
    _polygonPaint.color = _chartColor.withOpacity(0.4);
    _strokePaint.color = _chartColor;
    markNeedsPaint();
  }

  @override
  bool get sizedByParent => true;

  @override
  Size computeDryLayout(BoxConstraints constraints) {
    // Memaksa canvas berbentuk bujur sangkar optimal berdasarkan batasan parent
    final double desiredSize = math.min(constraints.maxWidth, constraints.maxHeight);
    return constraints.constrain(Size(desiredSize, desiredSize));
  }

  @override
  void paint(PaintingContext context, Offset offset) {
    if (size.isEmpty || _values.isEmpty) return;

    final Canvas canvas = context.canvas;
    canvas.save();
    canvas.translate(offset.dx, offset.dy);

    final double center = size.width / 2;
    final double radius = center * 0.85;
    final int sides = _values.length;
    final double angleStep = (2 * math.pi) / sides;

    // 1. Gambar Web Grid Konsentris
    for (double step = 0.25; step <= 1.0; step += 0.25) {
      final double r = radius * step;
      for (int i = 0; i < sides; i++) {
        final double a1 = i * angleStep - (math.pi / 2);
        final double a2 = ((i + 1) % sides) * angleStep - (math.pi / 2);
        canvas.drawLine(
          Offset(center + r * math.cos(a1), center + r * math.sin(a1)),
          Offset(center + r * math.cos(a2), center + r * math.sin(a2)),
          _gridPaint,
        );
      }
    }

    // 2. Plot Value Polygon
    _polygonPath.reset();
    for (int i = 0; i < sides; i++) {
      final double val = _values[i].clamp(0.0, 1.0);
      final double r = radius * val;
      final double angle = i * angleStep - (math.pi / 2);
      final double x = center + r * math.cos(angle);
      final double y = center + r * math.sin(angle);

      if (i == 0) {
        _polygonPath.moveTo(x, y);
      } else {
        _polygonPath.lineTo(x, y);
      }
    }
    _polygonPath.close();

    // 3. Eksekusi Raster Draw Calls
    canvas.drawPath(_polygonPath, _polygonPaint);
    canvas.drawPath(_polygonPath, _strokePaint);

    canvas.restore();
  }
}
```

---

### 13. Exercise

#### Level: Easy
1. Modifikasi file practical example agar setiap titik data pada gelombang menampilkan marker lingkaran kecil (`canvas.drawCircle`) hanya jika nilainya berada di atas ambang batas `0.5`. Pastikan tidak ada alokasi `Paint` baru di dalam loop.

#### Level: Medium
1. Buat custom widget `SymmetricWaveformProgress` yang menerima parameter `double audioLevel` (0.0 to 1.0) dan menggambar spektrum suara simetris (cermin atas-bawah). 
2. Tambahkan shader linear gradient (`ui.Gradient.linear`) pada `Paint` stroke yang bereaksi terhadap ukuran canvas tanpa mengalokasikan ulang shader jika ukuran frame tidak berubah.

#### Level: Hard
1. Buat custom `RenderObject` bernama `RenderParticleBurst` yang mengelola 10.000 partikel independen secara realtime.
2. Gunakan `canvas.drawRawAtlas()` atau `canvas.drawVertices()` untuk merender seluruh 10.000 partikel dalam tepat **1 draw call**.
3. Buktikan melalui DevTools CPU Profiler bahwa frametime rendering berada di bawah **8ms (120 FPS)** pada target device platform.

---

### 14. Challenge

#### Deskripsi Tantangan Sistem
Rancang sistem visualisasi **High-Frequency ECG/EKG Trace Monitor** untuk aplikasi medis enterprise.

#### Parameter Kebutuhan:
1.  **Throughput**: 500 sampel sensor baru masuk setiap detik via Stream tanpa henti.
2.  **Visual Buffer Requirement**: Layar harus menampilkan jendela geser 5 detik terakhir (total 2.500 titik data aktif di layar pada satu waktu).
3.  **Sweep-Bar Mode**: Pola gambar tidak boleh menggeser chart ke kiri (mengurangi beban scrolling), melainkan menggunakan efek jarum penghapus radar (*phosphor sweep line*): data baru menghapus dan menggantikan data lama dari kiri ke kanan lalu melakukan wrap-around ke awal.
4.  **Hardware Constraints**: Harus berjalan stabil tanpa *jank frame* pada perangkat embedded/low-end Android TV dan tablet POS kelas bawah (RAM 2GB, chipset ARM Cortex-A53).
5.  **Technical Constraints**: 
    *   Nol alokasi di `paint()`.
    *   Wajib menggunakan custom `LeafRenderObjectWidget` dan `RenderBox`.
    *   Sediakan profiling budget audit: Layout Time < 0.2ms, Paint Time < 1.8ms.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic Level (5 Soal)
1. **Fase apa yang terjadi tepat di antara Layout Phase dan Paint Phase pada Flutter Engine Pipeline?**
   * A. Build Phase
   * B. Compositing Bits Phase
   * C. Raster Phase
   * D. Vsync Phase
   * *Jawaban yang benar: B. Compositing Bits Phase menandai RenderObjects yang memerlukan pembaharuan layer sebelum pengecatan.*

2. **Mengapa alokasi objek baru (e.g., `Paint()`, `Path()`) di dalam method `paint()` dianggap sebagai antipattern performa parah?**
   * A. Karena akan menyebabkan crash segmentasi memory pada C++ engine.
   * B. Karena instansiasi tersebut langsung mengunci GPU driver thread.
   * C. Karena frekuensi pemanggilan method (hingga 120Hz) membanjiri Dart Garbage Collector (`Young Gen Scavenge`), memicu micro-stutters/jank.
   * D. Karena Skia tidak dapat membaca objek yang diinstansiasi di thread UI.
   * *Jawaban yang benar: C.*

3. **Apa kegunaan utama parameter `shouldRepaint(covariant CustomPainter oldDelegate)`?**
   * A. Memberi tahu layout engine apakah child widget perlu diukur ulang.
   * B. Menghapus memory texture GPU secara paksa.
   * C. Mengevaluasi apakah display list yang tersimpan perlu dibuang dan dicat ulang atau dapat menggunakan cache yang ada.
   * D. Memvalidasi thread isolator WebSocket.
   * *Jawaban yang benar: C.*

4. **Kapan Anda sebaiknya membungkus widget `CustomPaint` dengan `RepaintBoundary`?**
   * A. Pada setiap widget yang ada di layar tanpa terkecuali.
   * B. Ketika sub-pohon `CustomPaint` dicat ulang secara berkala pada frekuensi tinggi, sedangkan widget di sekitarnya bersifat statis.
   * C. Hanya jika menggunakan backend Impeller engine.
   * D. Ketika widget membutuhkan animasi rotasi 3D.
   * *Jawaban yang benar: B.*

5. **Apa fungsi dari `canvas.save()` dan `canvas.restore()`?**
   * A. Menyimpan bitmap ke hard drive perangkat dan membacanya kembali.
   * B. Memindahkan eksekusi kode dari Dart VM ke GPU pipeline.
   * C. Mendorong dan memulihkan kondisi matriks transformasi dan clipping stack saat ini pada canvas stack.
   * D. Mengamankan kode kanvas dari memory corruption.
   * *Jawaban yang benar: C.*

#### Intermediate Level (5 Soal)
6. **Perbedaan arsitektural mendasar apa yang membedakan Impeller dari Skia terkait pipeline rendering?**
   * A. Impeller mengandalkan JIT shader compilation pada runtime, sementara Skia tidak menggunakan shader.
   * B. Impeller tidak mendukung operasi vektor kurva Bézier.
   * C. Impeller melakukan kompilasi AOT untuk semua pipeline state objects dan shader, mengeliminasi shader compilation jank saat runtime.
   * D. Impeller sepenuhnya dieksekusi di CPU tanpa memerlukan akselerasi GPU.
   * *Jawaban yang benar: C.*

7. **Jika custom render box Anda memiliki ukuran yang sepenuhnya tergantung pada constraints parent (tidak terpengaruh oleh child apapun), optimasi apa yang harus diterapkan?**
   * A. Mengembalikan `sizedByParent = true` dan mengimplementasikan `computeDryLayout()`.
   * B. Memanggil `markNeedsLayout()` di dalam method `paint()`.
   * C. Menambahkan `RepaintBoundary` di root RenderView.
   * D. Menyetel `isRepaintBoundary = false` secara permanen.
   * *Jawaban yang benar: A.*

8. **Mengapa pemanggilan `setState()` di dalam listener `AnimationController` sering kali merusak performa animasi custom canvas?**
   * A. Karena animasi tidak akan berjalan di frame berikutnya.
   * B. Karena memicu `build()` pass pada seluruh widget tree scope tersebut, alih-alih langsung melompat ke paint phase via super(repaint).
   * C. Karena mengubah nilai controller dari floating point menjadi integer.
   * D. Karena mendestruksi canvas bitmap buffer.
   * *Jawaban yang benar: B.*

9. **Apa dampak arsitektural dari memasang terlalu banyak `RepaintBoundary` (misal pada seluruh item grid berkonten dinamis)?**
   * A. Layer explosion: Mengakibatkan pemborosan GPU VRAM untuk alokasi offscreen buffer dan memicu OOM (Out Of Memory).
   * B. CPU Throttling: Menurunkan frekuensi clock CPU secara permanen.
   * C. UI menjadi hitam putih karena raster cache rusak.
   * D. Skia Engine mematikan proses anti-aliasing secara otomatis.
   * *Jawaban yang benar: A.*

10. **Metode drawing mana pada `ui.Canvas` yang paling efisien untuk merender 5.000 poligon partikel independen secara simultan ke GPU?**
    * A. Melakukan loop 5.000 kali dan memanggil `canvas.drawPath()`.
    * B. Melakukan loop 5.000 kali dan memanggil `canvas.drawRect()`.
    * C. Menggunakan `canvas.drawVertices()` tunggal dengan vertex buffer array yang dipetakan.
    * D. Membungkus setiap partikel ke dalam custom `RenderObjectWidget`.
    * *Jawaban yang benar: C.*

#### Production Scenarios (3 Soal Kasus)
11. **Skenario 1**:
    Tim Anda menemukan bahwa aplikasi Android e-commerce mengalami frame drop (jank hingga 40ms) hanya saat pengguna membuka lembar *signature pad* kustom untuk pertama kali. Setelah coretan pertama berhasil dibuat, stroke berikutnya berjalan mulus di 60 FPS. Engine yang digunakan adalah Skia.
    *Diagnosa akar masalah dan tentukan tindakan korektif yang paling tepat:*
    * A. Akar masalah adalah memory leak pada path storage; solusinya panggil `System.gc()`.
    * B. Akar masalah adalah Shader Compilation Jank saat Skia mengompilasi shader GPU untuk antialiased path drawing; solusinya aktifkan Impeller backend atau lakukan shader warmup pada saat bootstrap aplikasi.
    * C. Akar masalah adalah ukuran canvas terlalu besar; solusinya kecilkan resolusi canvas ke 50%.
    * D. Akar masalah adalah ketiadaan `TickerProvider`; solusinya ubah state menjadi `SingleTickerProviderStateMixin`.
    * *Jawaban yang benar: B.*

12. **Skenario 2**:
    Sebuah aplikasi pemantau seismik menampilkan pergerakan tremor secara live. Komponen chart dibungkus dalam `CustomPaint` dengan `super(repaint: seismicStreamController)`. Namun, saat dicek via Timeline Flutter DevTools, fase `Layout` selalu terpanggil (durasi 8ms) pada setiap update titik getaran, membuang frame budget.
    *Apa penyebab utama arsitektural dan bagaimana cara memperbaikinya?*
    * A. Objek `RenderCustomPaint` tidak memiliki bounded constraint; solusinya bungkus `CustomPaint` dalam widget `SizedBox` dengan ukuran eksplisit atau terapkan `sizedByParent = true` di custom RenderBox.
    * B. Stream mengalir terlalu cepat; solusinya turunkan polling rate stream ke 10Hz.
    * C. DevTools Timeline memberikan metrik yang salah; abaikan saja hasil profiler tersebut.
    * D. `CustomPaint` harus diubah menjadi `Container` dengan background color dinamis.
    * *Jawaban yang benar: A.*

13. **Skenario 3**:
    Pada dashboard analitik finansial, terdapat grafik garis kompleks yang terdiri dari 10.000 data point statis historis, dan satu garis penunjuk waktu vertikal (cursor scrubber) yang dapat digeser-geser oleh jari pengguna secara interaktif. Ketika scrubber digeser, interaksi terasa patah-patah (lag parah).
    *Bagaimana arsitektur rendering harus direstrukturisasi untuk mencapai interaksi 120 FPS tanpa lag?*
    * A. Ubah 10.000 data point menjadi gambar resolusi rendah (JPEG).
    * B. Satukan kedua elemen dalam satu `CustomPainter` tunggal dengan loop drawing terpadu.
    * C. Pisahkan kanvas menjadi dua layer: Layer bawah statis untuk 10.000 data point (dibungkus `RepaintBoundary` agar dicache sebagai bitmap di GPU), dan Layer atas transparan terisolasi hanya untuk menggambar scrubber line yang dinamis.
    * D. Pindahkan operasi rendering chart historis ke Web Worker via platform channels.
    * *Jawaban yang benar: C.*

---

### 16. Summary

1.  **Eksekusi Pipeline**: Flutter mengonversi pohon widget menjadi display list melalui orkestrasi `Animate -> Build -> Layout -> Paint -> Composite -> Rasterize`. Efisiensi grafis diperoleh dengan memotong loop pada fase serendah mungkin (Paint alih-alih Build/Layout).
2.  **Display List Recording**: `CustomPainter` merekam instruksi grafis ke `ui.Picture` via `ui.Canvas`. Engine merender ulang instruksi ini pada GPU backend (Impeller/Skia) secara asinkronus.
3.  **Boundary Isolation**: `RepaintBoundary` adalah mekanisme isolasi komposit. Ia menghentikan propagasi dirty-paint pada pohon render dengan mengorbankan memori VRAM GPU untuk tekstur bitmap layer.
4.  **Zero-Allocation Rule**: Method `paint()` harus bebas dari alokasi memori heap. Objek `Paint`, `Path`, dan kalkulasi array wajib di-cache dan di-reuse untuk mencegah runtime garbage collector stuttering.
5.  **Direct Engine Access**: Untuk sistem visualisasi berkecepatan tinggi ekstrem, melompati abstraction layer `CustomPainter` dengan mengimplementasikan `RenderBox` secara langsung dan memanfaatkan primitive calls (`drawVertices`) adalah arsitektur baku tingkat enterprise.