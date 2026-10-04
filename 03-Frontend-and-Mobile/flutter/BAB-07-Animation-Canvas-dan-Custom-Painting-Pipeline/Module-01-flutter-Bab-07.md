# Bab 07 Module 01: Animation, Canvas, & Custom Painting Pipeline

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** 03-Frontend-and-Mobile
*   **Mata Pelajaran:** Advanced Flutter Engine Internals, Rendering, & Graphics
*   **Modul:** 07.01 — *Animation, Canvas, & Custom Painting Pipeline*
*   **Tingkat Kesulitan:** Advanced / Staff Engineer Level
*   **Prasyarat:** Pemahaman mendalam terkait Flutter Rendering Tree (`RenderObject`, `LayerTree`), Lifecycle `StatefulWidget`, Dart Event Loop, serta dasar-dasar geometri vector 2D.
*   **Estimasi Waktu Penyelesaian:** 180 - 240 Menit

---

## SEKSI 02 — LEARNING OBJECTIVES

Pada akhir modul ini, peserta didik mampu:

1.  **Membongkar Fase Render Pipeline:** Membedah siklus hidup frame Flutter (*Animate, Build, Layout, Compositing Bits, Paint, Composite, Rasterize*) dan mengidentifikasi overhead komputasi pada masing-masing tahapan.
2.  **Menguasai Subsistem Animasi Flutter:** Mengimplementasikan orkestrasi `AnimationController`, `TickerProvider`, `CurvedAnimation`, serta `Animatable/Tween` dengan pemisahan dependensi build tree untuk mencegah kebocoran pemanggilan `build()`.
3.  **Mengoperasikan `CustomPainter` & Native Engine Canvas:** Mengeksekusi API tingkat rendah `dart:ui.Canvas` dan Skia/Impeller recording context secara deterministik, serta menerapkan strategi caching off-screen menggunakan `PictureRecorder`.
4.  **Mencegah Frame Drops & Jitter:** Mengimplementasikan layer isolation melalui `RepaintBoundary`, memangkas raster cache thrashing, serta mengevaluasi performa menggunakan DevTools CPU/Raster Profiler.
5.  **Membangun Komponen Finansial Real-Time:** Merancang dan mengimplementasikan visualisasi data interaktif 60/120 FPS (*High-Frequency Live Order Book Chart*) yang mampu menerima ratusan update per detik tanpa penurunan performa rendering.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Mental Model: Canvas Sebagai Rekaman Perintah, Bukan Array Piksel

Banyak developer mengasumsikan bahwa pemanggilan metode seperti `canvas.drawRect()` langsung mewarnai piksel pada layar perangkat (seperti manipulasi `ImageData` pada web raster). **Mental model ini keliru.**

Dalam arsitektur Flutter (baik menggunakan backend Skia maupun Impeller), `Canvas` adalah sebuah *command recorder*. Saat Anda mengeksekusi metode pada `Canvas`, Anda tidak memodifikasi frame buffer, melainkan mencatat urutan operasi rendering ke dalam objek `ui.Picture`. Objek ini dikonversi menjadi Display List / Command Buffer yang dikirimkan ke Engine (C++) untuk dikompilasi, dioptimasi (culling, batching), dan dieksekusi oleh GPU pada tahap Rasterization.

```
[Kode Dart: canvas.drawCircle()]
       │
       ▼
[Recording Phase: ui.PictureRecorder menghasilkan Display List]
       │
       ▼
[Compositing Phase: Penggabungan Layer Tree di Render Pipeline]
       │
       ▼
[Rasterization Phase: Impeller/Skia mengirim GPU Commands via Vulkan/Metal]
       │
       ▼
[Frame Buffer: Piksel Muncul di Layar Hardware]
```

### Paradigma: "Paint Invalidation Boundary"

Jika Anda memanggil `setState()` di dalam widget yang berisi `CustomPaint`, Anda berisiko memaksa Flutter mengevaluasi ulang fase **Build**, **Layout**, dan **Paint** untuk seluruh sub-tree widget tersebut.

Prinsip performa tinggi: **Isolasi siklus cat.** Animasi murni adalah mutasi visual tanpa alterasi struktur geometris (*Layout*). Maka, perubahan state animasi idealnya **hanya memicu fase Paint**, melewati fase Build dan Layout secara keseluruhan melalui `ListenableBuilder` / `AnimatedBuilder` yang diisolasi di balik `RepaintBoundary`.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Siklus Frame Rendering Engine Flutter

Diagram berikut mengilustrasikan transmisi VSYNC dari display hardware hingga penerbitan draw call ke GPU driver:

```
+-----------------------------------------------------------------------------+
|                          HARDWARE DISPLAY SUBSYSTEM                         |
+-----------------------------------------------------------------------------+
                                       │
                               VSYNC Pulse (60Hz / 120Hz)
                                       │
                                       ▼
+-----------------------------------------------------------------------------+
|                                ENGINE (C++)                                 |
|                                                                             |
|  1. Platform Configuration & Message Loop Routing                           |
|  2. Schedule Frame Callback Dispatch                                        |
+-----------------------------------------------------------------------------+
                                       │
                         Engine -> Framework Binding
                                       │
                                       ▼
+-----------------------------------------------------------------------------+
|                              FRAMEWORK (DART)                               |
|                                                                             |
|  [PHASE 1: ANIMATION]                                                       |
|  Ticker triggers AnimationController ticks                                  |
|  Tweens evaluate values -> Listeners notified                               |
|                                      │                                      |
|                                      ▼                                      |
|  [PHASE 2: BUILD]                                                           |
|  Dirty Elements re-run build() (Targeted widgets ONLY)                      |
|                                      │                                      |
|                                      ▼                                      |
|  [PHASE 3: LAYOUT]                                                          |
|  RenderObjects calculate constraints & sizes (performLayout)                |
|                                      │                                      |
|                                      ▼                                      |
|  [PHASE 4: COMPOSITING BITS]                                                |
|  Mark subtrees that need separate compositing layers                        |
|                                      │                                      |
|                                      ▼                                      |
|  [PHASE 5: PAINT]                                                           |
|  RenderObject.paint() & CustomPainter.paint() record to ui.Canvas           |
|  Output: Layer Tree containing ui.Picture objects                           |
|                                      │                                      |
|                                      ▼                                      |
|  [PHASE 6: COMPOSITING]                                                     |
|  Framework converts Layer Tree into Scene via ui.SceneBuilder               |
+-----------------------------------------------------------------------------+
                                       │
                      window.render(Scene) -> C++ Engine
                                       │
                                       ▼
+-----------------------------------------------------------------------------+
|                          RASTER THREAD / GPU ENGINE                         |
|                                                                             |
|  [PHASE 7: RASTERIZATION]                                                   |
|  Backend (Impeller / Skia) translates Display List to Draw Calls            |
|  Vulkan (Android) / Metal (iOS) pipelines execute shaders                   |
|                                      │                                      |
|                                      ▼                                      |
|                             DISPLAY FRAME BUFFER                            |
+-----------------------------------------------------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. `Ticker` dan `SchedulerBinding`

Animasi tidak digerakkan oleh `Timer.periodic`. `Timer` berbasis software interrupt dan tidak memiliki sinkronisasi fase dengan refresh rate hardware layar. Menggunakan `Timer` menyebabkan fenomena *tearing* dan *stuttering*.

Flutter menggunakan `Ticker`:
*   `Ticker` mendaftarkan callback ke `SchedulerBinding.instance.scheduleFrameCallback()`.
*   Callback dieksekusi tepat saat sinyal hardware **VSYNC** (Vertical Synchronization) dipancarkan oleh kernel display driver.
*   Objek `TickerProvider` (misal: via mixin `SingleTickerProviderStateMixin`) memastikan `Ticker` dinonaktifkan ketika widget dilepas (`muted`/unmounted), mencegah kebocoran memori siklus rendering.

### 2. Dekonstruksi `CustomPainter`

Ketika `CustomPaint` widget dimasukkan ke dalam widget tree, ia menginstansiasi sebuah `RenderCustomPaint` (turunan dari `RenderBox`).

```
CustomPaint (Widget) ──instantiates──> RenderCustomPaint (RenderBox)
                                                │
                          ┌─────────────────────┴─────────────────────┐
                          ▼                                           ▼
                 paint(PaintingContext, Offset)              hitTestChildren(...)
                          │
            PaintingContext.canvas
                          │
          CustomPainter.paint(Canvas, Size)
```

Alur kerja `RenderCustomPaint.paint(PaintingContext context, Offset offset)`:
1.  Mengecek apakah `painter` atau `foregroundPainter` bernilai non-null.
2.  Mengeksekusi `painter.paint(context.canvas, size)`. Canvas yang diberikan diikat ke `PaintingContext` yang sedang aktif.
3.  Memanggil delegasi child jika widget memiliki child: `context.paintChild(child!, offset)`.
4.  Mengeksekusi `foregroundPainter.paint(context.canvas, size)` di atas render buffer child.

### 3. Kontrak `shouldRepaint`

Metode `shouldRepaint(covariant CustomPainter oldDelegate)` adalah gerbang performa deterministik.
*   Engine memanggil metode ini setiap kali instance baru dari `CustomPainter` dilewatkan ke `RenderCustomPaint`.
*   Jika mengembalikan `false`, Flutter tidak akan memanggil ulang `paint()`, melainkan menggunakan kembali rekaman `Picture` dari frame sebelumnya (jika layout tidak berubah).
*   Jika mengembalikan `true`, rekaman sebelumnya dibuang, dan `paint()` dieksekusi ulang secara penuh.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Pipeline Skia vs Impeller

Flutter kini beralih secara default dari Skia ke **Impeller** pada platform modern (iOS dan Android bertahap). Perbedaan fundamental arsitektur ini berdampak pada eksekusi Canvas:

*   **Skia:** Mengompilasi shader secara *just-in-time* (JIT) pada runtime saat suatu instruksi visual (seperti path kompleks dengan gradient tertentu) pertama kali dieksekusi. Ini menjadi sumber utama fenomena "Jank Frame Pertama" (*Shader Compilation Jank*).
*   **Impeller:** Mengompilasi seluruh shader secara *ahead-of-time* (AOT) saat build engine time. Semua operasi `Canvas` dipetakan ke stage pipeline pipeline GPU yang sudah ditentukan sebelumnya. Impeller mengonsumsi Display List dari Dart framework dan mengonversinya langsung menjadi GPU Command Buffers tanpa proses kompilasi shader runtime.

### Mekanisme `RepaintBoundary`

Setiap `RenderObject` memiliki properti `isRepaintBoundary`. Secara default bernilai `false`.
Ketika disetel ke `true` (seperti saat Anda membungkus widget dengan `RepaintBoundary`):

1.  `RenderObject` tersebut memisahkan diri dari painting context parent-nya dan membuat `OffsetLayer` baru.
2.  Semua operasi paint dari child subtree dicatat ke layer tersendiri.
3.  Jika subtree di dalam boundary perlu di-repaint, parent **tidak** perlu ikut di-repaint.
4.  Sebaliknya, jika parent di-repaint, engine dapat langsung mengomposisikan ulang layer anak yang sudah di-cache tanpa mengeksekusi ulang kode `paint()` miliknya.

```
                  Root RenderView
                        │
                  RenderPadding
                        │
              RenderRepaintBoundary ───> [Layer A: Cached Texture]
                        │
                RenderCustomPaint   ───> (Renders into Layer A only)
```

> **Hukum Konservasi Memori:** Jangan membungkus semua elemen dengan `RepaintBoundary`. Setiap boundary mengalokasikan backing store layer tersendiri di memori GPU. Penggunaan membabi buta akan menyebabkan *memory bloating* dan meningkatkan beban *compositor*.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah demonstrasi implementasi custom animation controller terpisah, kurva Bézier kustom, dan CustomPainter yang mengisolasi render pass tanpa overhead rebuilding widget.

```dart
import 'dart:math' as math;
import 'package:flutter/material.dart';

void main() {
  runApp(const MaterialApp(home: RadialProgressEngineMastery()));
}

class RadialProgressEngineMastery extends StatefulWidget {
  const RadialProgressEngineMastery({super.key});

  @override
  State<RadialProgressEngineMastery> createState() =>
      _RadialProgressEngineMasteryState();
}

class _RadialProgressEngineMasteryState extends State<RadialProgressEngineMastery>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<double> _curvedAnimation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2000),
    )..repeat(reverse: true);

    _curvedAnimation = CurvedAnimation(
      parent: _controller,
      curve: Curves.easeInOutCubic,
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F172A),
      body: Center(
        child: RepaintBoundary(
          child: AnimatedBuilder(
            animation: _curvedAnimation,
            builder: (context, child) {
              return CustomPaint(
                size: const Size(220, 220),
                painter: EngineMetricPainter(
                  progress: _curvedAnimation.value,
                ),
              );
            },
          ),
        ),
      ),
    );
  }
}

class EngineMetricPainter extends CustomPainter {
  final double progress;

  EngineMetricPainter({required this.progress});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = math.min(size.width, size.height) / 2 - 16;

    // Background Track Paint
    final trackPaint = Paint()
      ..color = const Color(0xFF1E293B)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 14.0
      ..strokeCap = StrokeCap.round;

    canvas.drawCircle(center, radius, trackPaint);

    // Dynamic Gradient Arc Paint
    final rect = Rect.fromCircle(center: center, radius: radius);
    final sweepGradient = SweepGradient(
      startAngle: 0.0,
      endAngle: math.pi * 2,
      colors: const [
        Color(0xFF38BDF8),
        Color(0xFF818CF8),
        Color(0xFFC084FC),
        Color(0xFF38BDF8),
      ],
      transform: GradientRotation(-math.pi / 2),
    );

    final activePaint = Paint()
      ..shader = sweepGradient.createShader(rect)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 14.0
      ..strokeCap = StrokeCap.round;

    final sweepAngle = 2 * math.pi * progress;
    
    // Draw Dynamic Arc
    canvas.drawArc(
      rect,
      -math.pi / 2, // Mulai dari arah jam 12 (-90 derajat)
      sweepAngle,
      false,
      activePaint,
    );

    // Indicator Glow Tip
    final tipAngle = (-math.pi / 2) + sweepAngle;
    final tipX = center.dx + radius * math.cos(tipAngle);
    final tipY = center.dy + radius * math.sin(tipAngle);

    final tipGlowPaint = Paint()
      ..color = const Color(0xFFC084FC).withValues(alpha: 0.6)
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 8);

    canvas.drawCircle(Offset(tipX, tipY), 8.0, tipGlowPaint);

    final tipCorePaint = Paint()..color = Colors.white;
    canvas.drawCircle(Offset(tipX, tipY), 4.0, tipCorePaint);
  }

  @override
  bool shouldRepaint(covariant EngineMetricPainter oldDelegate) {
    return oldDelegate.progress != progress;
  }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Telaah Kode `RadialProgressEngineMastery`

*   **Baris 19-20 (`with SingleTickerProviderStateMixin`):**
    Mengikat state widget dengan subsistem timing engine. Mixin ini memfasilitasi pembuatan instance `Ticker` tunggal dan otomatis mengatur registrasi muting via `didChangeDependencies` ketika rute aplikasi tidak aktif.
*   **Baris 27-35 (`AnimationController` & `CurvedAnimation`):**
    `_controller` mengelola domain linear waktu $t \in [0.0, 1.0]$. `CurvedAnimation` memetakan domain linear $t$ ke kurva kubik non-linear $f(t)$ tanpa memicu rebuild layout.
*   **Baris 50 (`RepaintBoundary`):**
    Memaksa `CustomPaint` membuat render subtree di layer kompositor mandiri. Ketika arc berputar/berkembang, repaint context diisolasi penuh; `Scaffold` dan canvas dasarnya tidak digambar ulang.
*   **Baris 51-54 (`AnimatedBuilder`):**
    Menangkap notifikasi perubahan tick dari `_curvedAnimation`. Perhatikan bahwa parameter `child` dapat dimanfaatkan jika terdapat sub-widget statis yang tidak perlu di-instansiasi ulang setiap tick.
*   **Baris 73-81 (`trackPaint` setup):**
    Instansiasi properti rendering. Style diatur ke `PaintingStyle.stroke` agar engine hanya menggambar lintasan garis luar dari lingkaran, bukan mengisi bagian tengahnya.
*   **Baris 85-98 (`SweepGradient.createShader`):**
    Membuat native engine shader. Rect yang dikirimkan mendefinisikan domain kalkulasi matriks warna gradient Skia/Impeller.
*   **Baris 103-109 (`canvas.drawArc`):**
    Menerbitkan instruksi arc ke Display List recorder. Parameter `useCenter: false` menginstruksikan Skia untuk tidak menutup path kembali ke titik tengah (tidak membentuk irisan pai/wedge).
*   **Baris 117-119 (`MaskFilter.blur`):**
    Menerapkan GPU fragment blur stage pada skalar radius yang ditentukan secara efisien sebelum koordinat inti lingkaran dieksekusi.
*   **Baris 125-128 (`shouldRepaint`):**
    Implementasi guard check optimal. Jika nilai properti `progress` sama persis dengan snapshot sebelumnya, pipeline paint dilewati seketika.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: Real-Time Financial Depth Chart & High-Frequency Order Book

**Konteks Perusahaan:** Platform Perdagangan Aset Kripto Global (FinTech Enterprise).

**Masalah:** 
Aplikasi harus menampilkan grafik *Order Book Depth Chart* yang memvisualisasikan akumulasi volume order Bid dan Ask secara real-time. Data streaming masuk via WebSocket dengan frekuensi rata-rata **40 hingga 100 paket per detik**. 

Implementasi awal menggunakan library charting berbasis widget generik standar menyebabkan:
1.  Penurunan frame rate drastis dari 120 FPS ke kisaran **18–25 FPS** pada perangkat flagship.
2.  Tingginya Garbage Collection (GC) pressure akibat instansiasi ribuan objek widget penampung garis data per detik.
3.  *UI Thread Choke:* Main thread kehabisan waktu kalkulasi per frame (< 8.3ms pada 120Hz), menghasilkan *frame drop severe warning* pada Android Systrace.

**Kebutuhan Solusi:**
1.  Pembangunan arsitektur custom paint berbasis zero-widget-rebuilding pipeline.
2.  Agregasi data berbasis ring buffer terisolasi.
3.  Optimasi path rendering vektor menggunakan algoritma *Path Pre-allocation & Point Projection* langsung di dalam canvas native buffer.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Di bawah ini adalah sistem rendering Depth Chart performa tinggi untuk data volume finansial berfrekuensi tinggi.

```dart
import 'dart:math' as math;
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

/// Representasi data point level kedalaman pasar.
@immutable
class DepthPoint {
  final double price;
  final double volume;

  const DepthPoint({required this.price, required this.volume});
}

/// Snapshot order book yang Immutable untuk konsistensi thread painting.
@immutable
class MarketDepthSnapshot {
  final List<DepthPoint> bids; // Order Beli (Harga Menurun)
  final List<DepthPoint> asks; // Order Jual (Harga Meningkat)

  const MarketDepthSnapshot({required this.bids, required this.asks});

  static const MarketDepthSnapshot empty =
      MarketDepthSnapshot(bids: [], asks: []);
}

/// Notifier berperforma tinggi khusus mutasi data pasar tanpa re-render pohon widget global.
class MarketDepthNotifier extends ChangeNotifier {
  MarketDepthSnapshot _snapshot = MarketDepthSnapshot.empty;

  MarketDepthSnapshot get snapshot => _snapshot;

  void updateData(List<DepthPoint> newBids, List<DepthPoint> newAsks) {
    _snapshot = MarketDepthSnapshot(bids: newBids, asks: newAsks);
    notifyListeners();
  }
}

class HighFrequencyDepthChart extends StatefulWidget {
  final MarketDepthNotifier notifier;

  const HighFrequencyDepthChart({
    super.key,
    required this.notifier,
  });

  @override
  State<HighFrequencyDepthChart> createState() =>
      _HighFrequencyDepthChartState();
}

class _HighFrequencyDepthChartState extends State<HighFrequencyDepthChart> {
  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      height: 320,
      color: const Color(0xFF0B0E14),
      child: RepaintBoundary(
        child: CustomPaint(
          painter: _DepthChartPainter(
            depthListenable: widget.notifier,
          ),
        ),
      ),
    );
  }
}

class _DepthChartPainter extends CustomPainter {
  final ValueListenable<MarketDepthSnapshot> _listenable;
  MarketDepthSnapshot _lastSnapshot;

  _DepthChartPainter({
    required MarketDepthNotifier depthListenable,
  })  : _listenable = depthListenable,
        _lastSnapshot = depthListenable.snapshot,
        super(repaint: depthListenable);

  // Instansiasi Paint di luar paint method loop untuk amortisasi biaya GC
  final Paint _bidLinePaint = Paint()
    ..color = const Color(0xFF00C087)
    ..style = PaintingStyle.stroke
    ..strokeWidth = 2.0;

  final Paint _askLinePaint = Paint()
    ..color = const Color(0xFFFF3B30)
    ..style = PaintingStyle.stroke
    ..strokeWidth = 2.0;

  final Paint _bidAreaPaint = Paint()
    ..color = const Color(0x2200C087)
    ..style = PaintingStyle.fill;

  final Paint _askAreaPaint = Paint()
    ..color = const Color(0x22FF3B30)
    ..style = PaintingStyle.fill;

  @override
  void paint(Canvas canvas, Size size) {
    final snapshot = _listenable.value;
    _lastSnapshot = snapshot;

    if (snapshot.bids.isEmpty && snapshot.asks.isEmpty) {
      return;
    }

    final double width = size.width;
    final double height = size.height;

    // Kalkulasi domain nilai maksimum untuk penskalaan normalisasi canvas
    double maxVolume = 0.0;
    for (var i = 0; i < snapshot.bids.length; i++) {
      if (snapshot.bids[i].volume > maxVolume) {
        maxVolume = snapshot.bids[i].volume;
      }
    }
    for (var i = 0; i < snapshot.asks.length; i++) {
      if (snapshot.asks[i].volume > maxVolume) {
        maxVolume = snapshot.asks[i].volume;
      }
    }

    if (maxVolume == 0.0) return;

    final double halfWidth = width / 2.0;

    // ==========================================
    // 1. GENERATE BID PATH (SISI KIRI: HIJAU)
    // ==========================================
    if (snapshot.bids.isNotEmpty) {
      final Path bidPath = Path();
      final Path bidAreaPath = Path();

      final int bidCount = snapshot.bids.length;
      final double xStep = halfWidth / (math.max(bidCount - 1, 1));

      // Titik Awal (Sisi Paling Kiri)
      double firstY = height - (snapshot.bids.first.volume / maxVolume * (height - 20));
      bidPath.moveTo(0, firstY);
      bidAreaPath.moveTo(0, height);
      bidAreaPath.lineTo(0, firstY);

      for (int i = 1; i < bidCount; i++) {
        final double x = i * xStep;
        final double y = height - (snapshot.bids[i].volume / maxVolume * (height - 20));
        
        // Garis bertangga vertikal-horizontal (Step line khas Depth Chart)
        final double prevX = (i - 1) * xStep;
        bidPath.lineTo(x, firstY); 
        bidPath.lineTo(x, y);

        bidAreaPath.lineTo(x, firstY);
        bidAreaPath.lineTo(x, y);

        firstY = y;
      }

      // Menutup path area untuk shader fill
      bidAreaPath.lineTo(halfWidth, height);
      bidAreaPath.close();

      canvas.drawPath(bidAreaPath, _bidAreaPaint);
      canvas.drawPath(bidPath, _bidLinePaint);
    }

    // ==========================================
    // 2. GENERATE ASK PATH (SISI KANAN: MERAH)
    // ==========================================
    if (snapshot.asks.isNotEmpty) {
      final Path askPath = Path();
      final Path askAreaPath = Path();

      final int askCount = snapshot.asks.length;
      final double xStep = halfWidth / (math.max(askCount - 1, 1));

      // Titik Awal Ask (Tengah Canvas)
      double currentY = height - (snapshot.asks.first.volume / maxVolume * (height - 20));
      askPath.moveTo(halfWidth, currentY);
      askAreaPath.moveTo(halfWidth, height);
      askAreaPath.lineTo(halfWidth, currentY);

      for (int i = 1; i < askCount; i++) {
        final double x = halfWidth + (i * xStep);
        final double y = height - (snapshot.asks[i].volume / maxVolume * (height - 20));

        // Step-line ask
        askPath.lineTo(x, currentY);
        askPath.lineTo(x, y);

        askAreaPath.lineTo(x, currentY);
        askAreaPath.lineTo(x, y);

        currentY = y;
      }

      askAreaPath.lineTo(width, height);
      askAreaPath.close();

      canvas.drawPath(askAreaPath, _askAreaPaint);
      canvas.drawPath(askPath, _askLinePaint);
    }

    // ==========================================
    // 3. MID-MARKET DIVIDER
    // ==========================================
    final Paint dividerPaint = Paint()
      ..color = const Color(0xFF334155)
      ..strokeWidth = 1.0;
    canvas.drawLine(
      Offset(halfWidth, 0),
      Offset(halfWidth, height),
      dividerPaint,
    );
  }

  @override
  bool shouldRepaint(covariant _DepthChartPainter oldDelegate) {
    // Hindari alokasi repaint jika referensi data snapshot identik
    return !identical(oldDelegate._lastSnapshot, _listenable.value);
  }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Fitur / Parameter | CustomPainter murni | Composited Layer Tree (`SceneBuilder`) | CanvasKit / WebGL Proxy | AnimatedWidget / Flutter Built-in |
| :--- | :--- | :--- | :--- | :--- |
| **Abstraksi Level** | Menengah (Engine Canvas API) | Sangat Rendah (Raw Layer Manipulation) | Tinggi (DOM Canvas Translation) | Tinggi (Declarative Widget Composition) |
| **Kompleksitas Kode** | Sedang (Perlu perhitungan manual matriks/trigonometri) | Ekstrem (Manual retain and prune composited layer) | Rendah (Gaya standard Canvas HTML5) | Sangat Rendah (Deklaratif standar) |
| **Overhead Memori** | Minimal (Display list dikompilasi langsung ke native C++) | Sangat Rendah (GPU texture handle retention) | Tinggi (Marshalling JS-Dart Bridge overhead) | Signifikan (Setiap elemen grafis adalah widget instance) |
| **Beban CPU Pipeline** | Melewati Fase Build & Layout secara total | Melewati Build, Layout, & Paint (Hanya fase Composite) | Bergantung pada Browser JavaScript Engine | Mengeksekusi Build, Layout, dan Paint berulang kali |
| **Kasus Penggunaan Optimal** | Chart finansial, efek partikel, game 2D ringan, waveform visualizer | Virtual display windowing, video surface composition | Cross-platform web fallback | Animasi UI transisi dasar (Fade, Scale, Slide dialog) |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Zero Size Geometry Constraints
*   **Kondisi Gagal:** Ketika parent widget memberikan batas unconstrained (`constraints.maxWidth == double.infinity`) atau ukuran `Size(0, 0)` saat layout awal inisialisasi.
*   **Gejala:** Operasi seperti `SweepGradient.createShader(rect)` atau pembagian titik koordinat menghasilkan nilai `NaN` atau `Infinity`, memicu crash fatal unhandled engine exception: `Float64List contains NaN`.
*   **Mitigasi:** Pasang *guard clause* di awal metode `paint`:
    ```dart
    if (size.width <= 0 || size.height <= 0 || size.isEmpty) {
      return;
    }
    ```

### 2. Path Allocation di Frame Loop
*   **Kondisi Gagal:** Melakukan mutasi atau instansiasi path jutaan segmen tanpa memanggil `path.reset()`, atau membuat instance objek kompleks berulang kali di dalam loop `paint()`.
*   **Gejala:** GC Pressure melonjak tajam (*GC Churn*), menyebabkan drop frame periodik (Jank setiap 2–3 detik) akibat thread execution dihentikan sementara oleh Garbage Collector.
*   **Mitigasi:** Gunakan objek path lokal secara terukur atau gunakan static object caches; hindari pembuatan collection baru (List, Map) di dalam tubuh fungsi `paint(Canvas, Size)`.

### 3. Matriks Transformasi Canvas yang Tidak Di-reset
*   **Kondisi Gagal:** Melakukan rotasi atau translasi koordinat (`canvas.translate()`, `canvas.rotate()`) tanpa menyimpannya ke dalam stack isolasi.
*   **Gejala:** Seluruh widget berikutnya yang digambar pada canvas context yang sama akan terdistorsi posisinya secara acak.
*   **Mitigasi:** Wajib membungkus transformasi koordinat dengan `canvas.save()` dan `canvas.restore()`:
    ```dart
    canvas.save();
    try {
      canvas.translate(centerX, centerY);
      canvas.rotate(angle);
      // Operasi cat di sini...
    } finally {
      canvas.restore();
    }
    ```

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Mistake 1: Menggunakan `setState()` untuk Menggerakkan `CustomPainter`

```dart
// ANTI-PATTERN: Menyebabkan seluruh pohon widget di-rebuild setiap 8ms (120FPS)
void _initAnimation() {
  _controller.addListener(() {
    setState(() {}); // FATAL: Rebuild layout & tree overhead!
  });
}
```

**Solusi Arsitektural:** Berikan controller atau listenable ke parameter `repaint` milik konstruktor `CustomPainter`:

```dart
// POLA BENAR: Framework hanya menjalankan ulang fase paint!
class OptimizedPainter extends CustomPainter {
  OptimizedPainter(AnimationController controller) : super(repaint: controller);

  @override
  void paint(Canvas canvas, Size size) {
    // Nilai diambil langsung saat paint pass
  }
}
```

---

### Mistake 2: Hardcoding Instansiasi Objek `Paint` di Dalam Loop `paint()`

```dart
// ANTI-PATTERN: Mengalokasikan puluhan ribu instance Paint per detik
@override
void paint(Canvas canvas, Size size) {
  for (int i = 0; i < points.length; i++) {
    final paint = Paint()..color = Colors.blue..strokeWidth = 2; // Instansiasi baru tiap iterasi!
    canvas.drawCircle(points[i], 2, paint);
  }
}
```

**Solusi Arsitektural:** Buat instance objek `Paint` sebagai *field/member variable* dari kelas `CustomPainter`, lalu mutasi propertinya jika diperlukan:

```dart
// POLA BENAR: 0 Alokasi Objek di siklus rendering loop
class OptimizedPainter extends CustomPainter {
  final Paint _pointPaint = Paint()
    ..style = PaintingStyle.fill
    ..strokeWidth = 2;

  @override
  void paint(Canvas canvas, Size size) {
    _pointPaint.color = Colors.blue;
    for (int i = 0; i < points.length; i++) {
      canvas.drawCircle(points[i], 2, _pointPaint);
    }
  }
}
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Strict Anti-Aliasing Control:** Properti `Paint.isAntiAlias` secara default bernilai `true`. Nonaktifkan anti-aliasing (`isAntiAlias = false`) jika Anda menggambar garis ortogonal vertikal/horizontal sempurna (seperti grid background). Hal ini menghemat operasi fragment shader GPU secara masif.
2.  **Pemisahan Layer Interaktivitas:** Pisahkan visual pasif (seperti grid latar belakang) dari grafik dinamis aktif. Bungkus grid dalam `CustomPaint` statis di balik `RepaintBoundary`, dan letakkan grafik dinamis di layer `CustomPaint` atasnya.
3.  **Path Topology Optimization:** Manfaatkan `drawPoints()` dengan `PointMode.polygon` atau `PointMode.lines` daripada membangun struktur `Path` manual yang dipenuhi ribuan instruksi `.lineTo()` individual jika Anda hanya membutuhkan serial garis terhubung tanpa isi *fill*.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### 1. Offscreen Buffer Raster