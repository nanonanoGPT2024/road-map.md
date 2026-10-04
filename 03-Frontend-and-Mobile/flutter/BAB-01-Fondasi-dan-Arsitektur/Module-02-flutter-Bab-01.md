# MODUL 02: DEEP DIVE, IMPLEMENTASI LANJUTAN & ARSITEKTUR PRODUKSI
**Kategori:** 03-Frontend-and-Mobile  
**Bab 01:** BAB-01-Fondasi-dan-Arsitektur  
**Tingkat Kesulitan:** Advanced / Enterprise-Grade

---

## 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
* **Menganalisis dan Membedah (Analyze & Deconstruct)** arsitektur internal Flutter Engine, mencakup interaksi Dart VM, Impeller/Skia graphic subsystem, dan Platform Channels pada tingkat native.
* **Menguasai Threading Model Flutter** dengan memetakan tugas komputasi secara tepat ke Platform Thread, UI Thread, Raster Thread, dan I/O Thread tanpa memicu UI drop-frame (jank).
* **Mengimplementasikan Custom RenderObject** dari nol dengan memanfaatkan siklus hidup mutasi tiga pohon (*Widget*, *Element*, *RenderObject*), kalkulasi constraints Box/Sliver, dan manipulasi canvas secara deterministik.
* **Merancang Arsitektur Skala Enterprise** berbasis Clean Architecture dan Reactive State Orchestration yang decouple, scalable, dan mematuhi batas isolasi domain core.
* **Melakukan Profiling dan Diagnosa Bottleneck** menggunakan DevTools (Timeline tracing, Memory allocation, GPU frame time) untuk memitigasi shader compilation jank dan over-invalidation tree.

---

## 2. Prerequisites
Sebelum mempelajari modul ini, peserta wajib memahami:
* Konsep OOP & Functional Programming lanjutan pada Dart (Generics, Mixins, Stream, Zone, Metadata, Concurrency dengan Isolates).
* Dasar Framework Flutter (Stateless/StatefulWidget, InheritedWidget, basic layouting `Column`, `Row`, `Stack`).
* Pengetahuan sistem operasi dasar: Thread scheduling, shared memory vs message passing, CPU/GPU pipeline, graphics context (OpenGL ES, Vulkan, Metal).

---

## 3. Concept & Internal Architecture

Arsitektur Flutter tidak mengandalkan WebView maupun native OEM widget wrappers (seperti React Native). Flutter memperlakukan kanvas sistem operasi sebagai kanvas gambar kosong (*blank canvas*) dan merender setiap piksel secara mandiri.

```
+-------------------------------------------------------------------+
|                        FRAMEWORK (Dart)                          |
|  Material / Cupertino -> Widgets -> Rendering -> Painting -> Core |
+-------------------------------------------------------------------+
|                         ENGINE (C/C++)                            |
|  Dart VM / Runtime | Impeller/Skia | Text (LibTxt/HarfBuzz)      |
+-------------------------------------------------------------------+
|                        EMBEDDER (Platform)                        |
|  Surface Setup | Thread Setup | Native Plugins (iOS/Android/macOS)|
+-------------------------------------------------------------------+
```

### 3.1 The 4-Thread Model
Flutter Engine beroperasi dengan empat thread primer yang saling terisolasi:

```
[Platform Thread]  <-- VSync Trigger, Lifecycle, Native Event Handling
        |
        v
   [UI Thread]     <-- Dart VM, Widget Tree, Build, Layout, Paint, Layer Tree
        |
        v (Layer Tree / Flow Engine)
 [Raster Thread]   <-- GPU Commands Generation (Impeller/Skia), Tessellation
        |
        v (Command Buffers)
      [GPU]        <-- Frame Buffer Scanout (Display)
        ^
        |
   [IO Thread]     <-- Image Decoding, Texture Upload, Asset Loading
```

1. **Platform Thread**: Thread utama host OS (misal: Android Main Thread / iOS UI Thread). Mengatur event OS, lifecycle, dan interaksi platform channel. UI tidak boleh di-render di sini secara langsung.
2. **UI Thread (Dart VM Thread)**: Menjalankan runtime Dart. Bertanggung jawab mengeksekusi kode aplikasi, membangun `Widget Tree`, mengompilasi `Element Tree`, menghitung kalkulasi layout, dan menghasilkan `Layer Tree`.
3. **Raster Thread (Sebelumnya GPU Thread)**: Mengambil `Layer Tree` yang diproduksi UI Thread, mengonversinya menjadi instruksi GPU (Draw calls), melakukan tessellation, dan mengirimkannya ke GPU pipeline.
4. **IO Thread**: Melakukan operasi I/O asinkron yang mahal seperti decoding gambar raster (PNG, JPEG) dan kompresi tekstur sebelum dipasok ke Raster Thread, mencegah UI Thread dan Raster Thread terhenti (*block*).

### 3.2 Sub-Sistem Rendering Engine: Impeller vs Skia
* **Skia**: Mengompilasi shader secara run-time (Just-In-Time compilation). Hal ini menyebabkan kompilasi shader bertepatan dengan frame render pertama, memicu fenomena **Shader Compilation Jank**.
* **Impeller (Default Engine Baru)**: Memindahkan kompilasi shader ke fase build aplikasi (**Ahead-Of-Time/AOT compilation**). Impeller menggunakan Vulkan (Android) dan Metal (iOS) pipelines secara langsung dengan arsitektur multi-pass tessellation, mengeliminasi kompilasi shader run-time secara total.

### 3.3 Anatomi 3 Pohon (The Three Trees)
Flutter mengelola 3 struktur data paralel untuk menampilkan antarmuka:

```
+------------------+      1:1 Relasi Spesifikasi      +-------------------+
|   Widget Tree    | -------------------------------> |   Element Tree    |
| (Immutable/Config|                                  | (Stateful/Identity|
+------------------+                                  +-------------------+
                                                                |
                                                      Instansiasi jika RenderObjectWidget
                                                                v
                                                      +-------------------+
                                                      | RenderObject Tree |
                                                      | (Geometry/Paint)  |
                                                      +-------------------+
```

1. **Widget Tree (Konfigurasi Deklaratif)**:
   * Bersifat *immutable* dan murah untuk dialokasikan serta dihancurkan.
   * Merupakan representasi hierarki konfigurasi blueprint visual.
2. **Element Tree (Struktur Manajemen Identitas & Lifecycle)**:
   * Mengatur referensi persisten antara `Widget` dan `RenderObject`.
   * Berfungsi sebagai *bridge* dan mengontrol rekonsiliasi state via algoritma diffing (`Widget.canUpdate`).
   * Terbagi menjadi `ComponentElement` (menampung widget komposisi) dan `RenderObjectElement` (menampung widget visual yang memetakan langsung ke `RenderObject`).
3. **RenderObject Tree (Geometri, Hit-Testing, Painting)**:
   * Mengelola komputasi geometris deterministik (`performLayout`), pembatasan ukuran (`Constraints`), dan output visual (`paint`).
   * Bersifat *mutable* dan sangat mahal (*heavyweight*). Dipertahankan selama struktur layout tidak berubah signifikan.

---

## 4. Why & What

### Mengapa Perlu Menyelami Engine dan Menghindari Sekadar Komposisi Widget?
Pada aplikasi enterprise dengan data throughput tinggi (seperti streaming charting bursa saham, peta interaktif, atau custom feed animasi), abstraksi widget deklaratif bawaan seperti `Container`, `Padding`, dan `CustomPaint` dapat memicu *overhead* berikut:
1. **Tree Allocation Overhead**: Terlalu banyak instansiasi objek `Widget` dan `Element` per frame pada update 120 FPS menekan Dart Garbage Collector (GC), memicu GC pauses (jank).
2. **Multi-pass Layout Redundancy**: Widget bawaan terkadang mengeksekusi intrinsic sizing passes ganda jika tidak dirancang efisien dalam flex layout.
3. **Canvas Overhead**: `CustomPainter` masih berada di bawah abstraksi `RenderCustomPaint`, membatasi kendali granular terhadap relayout boundary, hit-test caching, dan layer synthesis.

### Kapan Menggunakan Custom RenderObject?
Gunakan `RenderObject` ketika:
* Memerlukan kalkulasi layout khusus yang tidak efisien direpresentasikan oleh kombinasi `Row`, `Column`, `Stack`, atau `CustomMultiChildLayout`.
* Mengimplementasikan visualisasi data berperforma tinggi di mana mutasi visual tidak memerlukan mutasi structural tree layout.
* Memerlukan hit-testing kustom dengan bentuk non-geometris reguler (misal: polygon hit testing).

---

## 5. How: The Frame Pipeline Workflow

Siklus hidup satu frame Flutter (16.6ms untuk 60Hz, 8.3ms untuk 120Hz) dieksekusi melalui fase-fase berikut pada UI Thread dan Raster Thread:

```
[VSync Pulse Received]
         |
         v
1. [Animate]     : Memicu Tickers, mengupdate nilai AnimationController.
         |
         v
2. [Build]       : Menjalankan method build(), merekonsiliasi Element Tree.
         |
         v
3. [Layout]      : Top-down passing Constraints, Bottom-up passing Sizes.
         |
         v
4. [Compositing] : Membagi RenderObjects ke Layer terpisah (RepaintBoundary).
         |
         v
5. [Paint]       : Merekam instruksi visual ke dalam Picture via Skia/Impeller.
         |
         v
6. [Composition] : Mengompilasi Layer Tree menjadi frame visual final.
         |
         +-----> (Kirim Layer Tree ke Raster Thread)
                      |
                      v
         7. [Rasterize] : GPU backend mengeksekusi instruksi dan menggambar ke buffer.
```

### Algoritma Rekonsiliasi (Tree Diffing)
Flutter mengimplementasikan algoritma rekonsiliasi berbobot $O(N)$ pada fase **Build**:
Saat konfigurasi baru di-pass via `runApp` atau `setState`:
1. Framework memvalidasi `Widget.canUpdate(oldWidget, newWidget)`:
   ```dart
   static bool canUpdate(Widget oldWidget, Widget newWidget) {
     return oldWidget.runtimeType == newWidget.runtimeType
         && oldWidget.key == newWidget.key;
   }
   ```
2. Jika `true`: `Element` lama dipertahankan, properti `Element.widget` diperbarui dengan instansiasi baru, dan mutasi diteruskan ke `RenderObject` terkait via `updateRenderObject()`.
3. Jika `false`: `Element` lama dicabut (`unmount`), `RenderObject` dibuang dari tree (`dispose`), dan instansiasi `Element` baru diciptakan dari nol.

---

## 6. Analogy & Diagram ASCII

### Analogi: Perusahaan Konstruksi Teater
* **Widget Tree (Naskah Drama)**: Lembaran kertas instruksi. Sangat mudah dan murah untuk dicetak ulang setiap detik jika ada revisi teks.
* **Element Tree (Sutradara/Manajer Panggung)**: Mengingat siapa aktor yang memegang peran tertentu, mengarahkan apakah aktor perlu diganti atau hanya perlu membaca naskah baru.
* **RenderObject Tree (Aktor Fisik dan Properti Panggung)**: Membutuhkan waktu untuk berdandan, mengukur posisi panggung, dan bergerak secara fisik di panggung teater.
* **Raster Thread (Tim Tata Lampu & Rekaman Kamera)**: Merekam penampilan fisik aktor dan menyiarkannya ke layar bioskop penonton.

### Constraint Go Down, Sizes Go Up
```
Parent RenderBox
       |
       |  1. Downward: BoxConstraints (minWidth, maxWidth, minHeight, maxHeight)
       v
Child RenderBox
       |
       |  2. Process: Child menghitung dimensinya berdasarkan constraint parent
       v
Child RenderBox
       |
       |  3. Upward: Size (width, height) deterministik dikembalikan ke Parent
       v
Parent RenderBox
```

---

## 7. Implementation: Simple to Enterprise-Grade

### 7.1 Practical Example: Custom RenderObject
Berikut implementasi custom `RenderBox` yang merender diagram bar performa tinggi dengan layout constraints deterministik, memotong overhead widget tree standard.

```dart
import 'package:flutter/rendering.dart';
import 'package:flutter/widgets.dart';

// 1. LeafRenderObjectWidget: Penghubung Widget ke RenderObject Tree
class PerformanceBarWidget extends LeafRenderObjectWidget {
  final double fillPercentage; // Nilai 0.0 sampai 1.0
  final Color barColor;
  final Color backgroundColor;

  const PerformanceBarWidget({
    super.key,
    required this.fillPercentage,
    required this.barColor,
    required this.backgroundColor,
  }) : assert(fillPercentage >= 0.0 && fillPercentage <= 1.0);

  @override
  RenderPerformanceBar createRenderObject(BuildContext context) {
    return RenderPerformanceBar(
      fillPercentage: fillPercentage,
      barColor: barColor,
      backgroundColor: backgroundColor,
    );
  }

  @override
  void updateRenderObject(BuildContext context, RenderPerformanceBar renderObject) {
    renderObject
      ..fillPercentage = fillPercentage
      ..barColor = barColor
      ..backgroundColor = backgroundColor;
  }
}

// 2. Custom RenderBox: Pengendali Layout & Painting Murni
class RenderPerformanceBar extends RenderBox {
  double _fillPercentage;
  Color _barColor;
  Color _backgroundColor;

  RenderPerformanceBar({
    required double fillPercentage,
    required Color barColor,
    required Color backgroundColor,
  })  : _fillPercentage = fillPercentage,
        _barColor = barColor,
        _backgroundColor = backgroundColor;

  // Setter dengan Dirty Marking
  double get fillPercentage => _fillPercentage;
  set fillPercentage(double value) {
    if (_fillPercentage == value) return;
    _fillPercentage = value;
    markNeedsPaint(); // Tidak butuh relayout karena ukuran tidak berubah
  }

  Color get barColor => _barColor;
  set barColor(Color value) {
    if (_barColor == value) return;
    _barColor = value;
    markNeedsPaint();
  }

  Color get backgroundColor => _backgroundColor;
  set backgroundColor(Color value) {
    if (_backgroundColor == value) return;
    _backgroundColor = value;
    markNeedsPaint();
  }

  @override
  bool get sizedByParent => false;

  @override
  void performLayout() {
    // Mematuhi batas incoming constraints secara presisi
    final double desiredHeight = 24.0;
    final double width = constraints.hasBoundedWidth 
        ? constraints.maxWidth 
        : 100.0;
    final double height = constraints.constrainHeight(desiredHeight);

    size = Size(width, height);
  }

  @override
  void paint(PaintingContext context, Offset offset) {
    final Canvas canvas = context.canvas;
    final Rect baseRect = offset & size;

    // Background Paint
    final Paint bgPaint = Paint()..color = _backgroundColor;
    canvas.drawRRect(
      RRect.fromRectAndRadius(baseRect, const Radius.circular(4.0)),
      bgPaint,
    );

    // Active Bar Paint
    if (_fillPercentage > 0.0) {
      final Paint activePaint = Paint()..color = _barColor;
      final Rect activeRect = Rect.fromLTWH(
        offset.dx,
        offset.dy,
        size.width * _fillPercentage,
        size.height,
      );
      canvas.drawRRect(
        RRect.fromRectAndRadius(activeRect, const Radius.circular(4.0)),
        activePaint,
      );
    }
  }

  @override
  bool hitTestSelf(Offset position) => true; // Merespon gesture langsung jika dibutuhkan
}
```

### 7.2 Enterprise-Grade App Architecture Pattern
Penerapan arsitektur produksi berbasis Clean Architecture + Event-Driven Isolation.

```
lib/
├── core/
│   ├── network/
│   │   ├── api_client.dart
│   │   └── websocket_client.dart
│   └── error/
│       └── failures.dart
├── features/
│   └── market_depth/
│       ├── data/
│       │   ├── datasources/
│       │   │   └── market_remote_data_source.dart
│       │   ├── models/
│       │   │   └── order_book_model.dart
│       │   └── repositories/
│       │       └── market_repository_impl.dart
│       ├── domain/
│       │   ├── entities/
│       │   │   └── order_book_entity.dart
│       │   ├── repositories/
│       │   │   └── market_repository.dart
│       │   └── usecases/
│       │       └── stream_market_depth_usecase.dart
│       └── presentation/
│           ├── controllers/
│           │   └── market_depth_bloc.dart
│           └── views/
│               ├── market_depth_screen.dart
│               └── components/
│                   └── order_book_visualizer.dart
```

#### Enterprise Domain & Data Implementation

```dart
// domain/entities/order_book_entity.dart
import 'package:equatable/equatable.dart';

class OrderBookEntry extends Equatable {
  final double price;
  final double volume;

  const OrderBookEntry({required this.price, required this.volume});

  @override
  List<Object?> get props => [price, volume];
}

class OrderBookEntity extends Equatable {
  final List<OrderBookEntry> bids;
  final List<OrderBookEntry> asks;
  final DateTime timestamp;

  const OrderBookEntity({
    required this.bids,
    required this.asks,
    required this.timestamp,
  });

  @override
  List<Object?> get props => [bids, asks, timestamp];
}
```

```dart
// domain/usecases/stream_market_depth_usecase.dart
import 'dart:async';
import '../entities/order_book_entity.dart';
import '../repositories/market_repository.dart';

abstract class StreamMarketDepthUseCase {
  Stream<OrderBookEntity> execute(String symbol);
}

class StreamMarketDepthUseCaseImpl implements StreamMarketDepthUseCase {
  final MarketRepository _repository;

  StreamMarketDepthUseCaseImpl(this._repository);

  @override
  Stream<OrderBookEntity> execute(String symbol) {
    // Bisnis logic level domain: Memvalidasi filter anomali spread
    return _repository.subscribeOrderBook(symbol).transform(
      StreamTransformer<OrderBookEntity, OrderBookEntity>.fromHandlers(
        handleData: (data, sink) {
          if (data.bids.isNotEmpty && data.asks.isNotEmpty) {
            if (data.bids.first.price < data.asks.first.price) {
              sink.add(data); // Konsisten: Best Bid < Best Ask
            }
          }
        },
      ),
    );
  }
}
```

---

## 8. Real-World Case Study (Enterprise Scale)

### Skenario: High-Frequency Market Depth Engine (Fintech Exchange)
* **Konteks**: Aplikasi perdagangan kripto tier-1 menerima pembaruan Order Book melalui WebSocket hingga 200 frame snapshot per detik (`200 payload/sec`).
* **Masalah**: Implementasi standar menggunakan `StreamBuilder` dan `ListView.builder` konvensional menyebabkan UI Thread terhenti (*stutter*) dengan frame time melonjak ke 45ms (target: 8.3ms pada 120Hz). Dart VM menghabiskan 40% thread time untuk alokasi memori objek dan rekonsiliasi JSON parser pada main thread.
* **Solusi Arsitektur**:
  1. **Background Isolate Offloading**: Parsing protokol data binary (Protobuf/FlatBuffers) dialihkan secara mutlak ke dedicated Background Worker Isolate.
  2. **Throttling & Buffer Pooling**: State data di-buffer dan dikompresi menggunakan mekanisme *Lossless Throttling* pada interval sync display refresh rate OS (60/120Hz via `SchedulerBinding`).
  3. **Custom RenderObject Engine**: Mengganti pohon `Row`/`Container` untuk order-book bar rendering dengan satu `RenderBox` custom yang menggambar seluruh 50 depth levels dalam satu layer draw-call direct canvas.
  4. **Paint Containment**: Mengisolasi visual viewport menggunakan `RepaintBoundary` agar invalidasi frame orderbook tidak memicu repaint pada global navigation header dan chart canvas.

---

## 9. Trade-Off Analysis

| Aspek Arsitektur | Pilihan A: Standard Widget Composition | Pilihan B: Custom RenderObject | Justifikasi Arsitektur |
| :--- | :--- | :--- | :--- |
| **Development Velocity** | Sangat Cepat (declarative, component reuse). | Lambat (harus memetakan BoxConstraints, layout manual, dan low-level canvas painting). | Gunakan Widget Composition untuk 90% UI screen (form, dashboard CRUD, navigasi). |
| **Memory Footprint** | Tinggi ($3\times$ alokasi node: Widget, Element, RenderObject). | Minimal (Hanya satu node RenderObject yang dikendalikan secara mutlak). | Pilihan B mutlak untuk chart streaming, live canvas, dan high-density data visualizer. |
| **Frame Stability** | Rentan GC-induced jank pada throughput streaming data ekstrem. | Deterministik dan stabil pada refresh rate 120 FPS konstan. | GC Dart VM bekerja jauh lebih ringan saat tidak ada rebuild berulang-ulang pada structural tree. |
| **Maintainability** | Tinggi (mudah dibaca oleh seluruh level engineer). | Rendah (membutuhkan engineer yang paham geometri matematika dan rendering matrix). | Dokumentasikan secara ketat boundary dan invariant layer jika memilih Custom RenderObject. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Layout Exception: "A RenderFlex overflowed by X pixels"
* **Penyebab**: `RenderFlex` (`Row`/`Column`) menerima batasan unbounded (infinity) pada arah aksis utamanya namun anak-anaknya menuntut alokasi ruang tanpa pembatas.
* **Solusi**: Bungkus anak widget dengan `Expanded` atau `Flexible` untuk memasok bounded constraints, atau set `mainAxisSize: MainAxisSize.min`.

### 10.2 Anti-Pattern: Executing Business Logic / State Mutation in `build()`
```dart
// FATAL ANTI-PATTERN: Memicu infinite frame cycle crash
@override
Widget build(BuildContext context) {
  context.read<OrderBloc>().add(FetchOrdersEvent()); // JANGAN LAKUKAN INI
  return Container();
}
```
* **Solusi**: Pindahkan side-effects ke lifecycle hooks (`initState`, `didUpdateWidget`) atau orkestrasikan di luar presentation layer via event controllers/blocs.

### 10.3 Unnecessary Global Repaint Invalidation
* **Gejala**: Satu widget teks yang berkedip menyebabkan seluruh layar di-repaint ulang (terlihat via DevTools "Highlight Repaints").
* **Solusi**: Tempatkan `RepaintBoundary` di sekeliling sub-tree yang mengalami frekuensi pembaruan tinggi. Ini memotong sub-tree tersebut menjadi `DisplayList` terisolasi pada Raster Thread.

---

## 11. Best Practices (Production Checklist)

- [ ] **Const Constructor Enforcement**: Deklarasikan `const` pada seluruh widget yang bersifat stateless/konstan untuk memotong proses instansiasi dan rekonsiliasi diffing. Aktifkan linter rule: `prefer_const_constructors`.
- [ ] **Isolate Offloading**: Semua komputasi yang memakan waktu $\ge 8\text{ms}$ (JSON serialization besar, enkripsi, transformasi image) wajib dieksekusi di `Isolate.run()`.
- [ ] **Repaint Boundaries Optimization**: Sisipkan `RepaintBoundary` pada animasi looping dan high-frequency real-time update component.
- [ ] **Avoid SaveLayer**: Hindari penggunaan fitur visual yang memicu offscreen compositing pass implisit seperti `Opacity` dinamis (gunakan properti warna `withOpacity` daripada wrapping widget `Opacity`), atau `ShaderMask`, kecuali benar-benar diperlukan.
- [ ] **DevTools Continuous Profiling**: Lakukan profiling CPU Flame Chart dan Rasterizer Timeline pada perangkat low-end physical target (bukan simulator/emulator) pada target mode `--profile`.

---

## 12. Hands-on Practice: Implementasi Custom RenderObject & State Engine

Target Implementasi: `hands-on/m02/`

### Step 1: Inisialisasi Project Structure
```bash
mkdir -p hands-on/m02/lib/render_engine
cd hands-on/m02
```

### Step 2: Implementasi Custom RenderObject Matrix Grid
Buat file `lib/render_engine/matrix_visualizer.dart`:

```dart
import 'dart:math';
import 'package:flutter/rendering.dart';
import 'package:flutter/widgets.dart';

class MatrixVisualizer extends LeafRenderObjectWidget {
  final List<double> values;
  final Color baseColor;

  const MatrixVisualizer({
    super.key,
    required this.values,
    required this.baseColor,
  });

  @override
  RenderMatrixBox createRenderObject(BuildContext context) {
    return RenderMatrixBox(
      values: values,
      baseColor: baseColor,
    );
  }

  @override
  void updateRenderObject(BuildContext context, RenderMatrixBox renderObject) {
    renderObject
      ..values = values
      ..baseColor = baseColor;
  }
}

class RenderMatrixBox extends RenderBox {
  List<double> _values;
  Color _baseColor;

  RenderMatrixBox({
    required List<double> values,
    required Color baseColor,
  })  : _values = values,
        _baseColor = baseColor;

  List<double> get values => _values;
  set values(List<double> val) {
    _values = val;
    markNeedsPaint(); // Hanya invalidasi paint jika data array berubah
  }

  Color get baseColor => _baseColor;
  set baseColor(Color val) {
    if (_baseColor == val) return;
    _baseColor = val;
    markNeedsPaint();
  }

  @override
  void performLayout() {
    // Constraint handling deterministik: Ambil lebar maksimum, tentukan tinggi proporsional
    final double width = constraints.maxWidth.isFinite ? constraints.maxWidth : 300.0;
    final double height = constraints.maxHeight.isFinite ? constraints.maxHeight : 150.0;
    size = constraints.constrain(Size(width, height));
  }

  @override
  void paint(PaintingContext context, Offset offset) {
    if (_values.isEmpty) return;

    final Canvas canvas = context.canvas;
    final int count = _values.length;
    final double cellWidth = size.width / count;
    final double maxHeight = size.height;

    final Paint paint = Paint()..style = PaintingStyle.fill;

    for (int i = 0; i < count; i++) {
      final double normalizedVal = _values[i].clamp(0.0, 1.0);
      paint.color = _baseColor.withAlpha((normalizedVal * 255).toInt());

      final Rect rect = Rect.fromLTWH(
        offset.dx + (i * cellWidth),
        offset.dy + (maxHeight * (1.0 - normalizedVal)),
        maxCellWidth(cellWidth),
        maxHeight * normalizedVal,
      );

      canvas.drawRect(rect, paint);
    }
  }

  double maxCellWidth(double calculated) => max(0.0, calculated - 1.0);
}
```

### Step 3: Implementasi Test Application Screen
Buat file `lib/main.dart`:

```dart
import 'dart:async';
import 'dart:math';
import 'package:flutter/material.dart';
import 'render_engine/matrix_visualizer.dart';

void main() => runApp(const MaterialApp(home: EnterpriseDashboard()));

class EnterpriseDashboard extends StatefulWidget {
  const EnterpriseDashboard({super.key});

  @override
  State<EnterpriseDashboard> createState() => _EnterpriseDashboardState();
}

class _EnterpriseDashboardState extends State<EnterpriseDashboard> {
  late Timer _timer;
  List<double> _data = List.generate(50, (index) => 0.5);
  final Random _rng = Random();

  @override
  void initState() {
    super.initState();
    // High-frequency stream simulation: 60 updates per second
    _timer = Timer.periodic(const Duration(milliseconds: 16), (timer) {
      setState(() {
        _data = List.generate(50, (index) => _rng.nextDouble());
      });
    });
  }

  @override
  void dispose() {
    _timer.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('High-Throughput Render Pipeline')),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: RepaintBoundary(
            child: SizedBox(
              width: double.infinity,
              height: 200,
              child: MatrixVisualizer(
                values: _data,
                baseColor: Colors.cyanAccent,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
```

---

## 13. Exercises

### Level Easy
1. Ubah implementasi `RenderPerformanceBar` agar mendukung radius sudut (*border radius*) dinamis yang dapat dikonfigurasi melalui widget property, dengan tetap memastikan pemanggilan `markNeedsPaint` secara deterministik tanpa relayout.

### Level Medium
2. Implementasikan `RenderMultiColumnBar` yang menerima multi-series metrics (misal: 3 bar data berdampingan per entitas data) dan tangani skenario boundary constraint jika `maxWidth` bernilai `double.infinity`.

### Level Hard
3. Bangun custom `RenderObject` bertipe layout container (`RenderBox` yang menerapkan `ContainerRenderObjectMixin` dan `RenderBoxContainerDefaultsMixin`) yang mengatur layout anak-anaknya secara melingkar (*Radial/Circular Layout*) dengan kalkulasi trigonometri posisi anak secara manual di dalam `performLayout`.

---

## 14. Enterprise Challenge: Zero-Allocation Resilient Log Visualizer

### Skenario Bisnis
Sistem Telemetri IOT memancarkan log status frekuensi sangat tinggi (1.000 log events per detik) ke perangkat tablet teknisi lapangan. Tim UI dilarang keras menggunakan widget bawaan berbasis `ListView` maupun `CustomPainter` standar karena profiling memori mendeteksi alokasi $50\text{MB}$ memori per menit yang memicu freeze berkala dari Garbage Collector.

### Parameter & Kriteria Tantangan
1. **Zero Heap Allocation Loop**: Buat struktur custom `RenderBox` yang membaca buffer data dari circular memory ring buffer flat list (`Float64List`) tanpa membuat objek wrapper Dart baru pada setiap pembaruan frame.
2. **Layer Isolation**: Pastikan pembaruan kanvas terisolasi sepenuhnya dalam Layer Compositing mandiri tanpa memicu traversal layout pada parent tree.
3. **Target Benchmark**: Wajib berjalan pada **120 FPS konstan** di profile-mode Android/iOS low-tier device dengan Frame Time UI Thread $\le 3\text{ms}$ dan Raster Thread $\le 4\text{ms}$.
4. **Hit Test Support**: Implementasikan kalkulasi manual pada `hitTestChildren` / `hitTestSelf` untuk mendeteksi event klik pada log entry tertentu berdasarkan koordinat visual $Y$ pengguna.

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Pertanyaan Basic

#### Q1: Sebutkan 4 thread utama pada arsitektur Flutter Engine dan jelaskan peran singkat masing-masing!
* **Jawaban**: 
  1. *Platform Thread*: Mengelola native OS events, plugins, and lifecycle.
  2. *UI Thread*: Menjalankan Dart VM, mengeksekusi logika framework, membangun *Widget*, mengelola *Element*, dan kalkulasi *Layout* serta *Paint* untuk menghasilkan *Layer Tree*.
  3. *Raster Thread*: Mengonversi *Layer Tree* menjadi instruksi spesifik GPU (Draw Calls) melalui backend grafis (Impeller/Skia).
  4. *IO Thread*: Melakukan operasi I/O asinkron yang mahal seperti image decoding dan kompresi tekstur sebelum dipasok ke Raster Thread.

#### Q2: Apa fungsi utama dari algoritma rekonsiliasi `Widget.canUpdate`?
* **Jawaban**: Memeriksa apakah `Element` lama dapat menggunakan kembali instansiasi `Widget` baru berdasarkan kesamaan `runtimeType` dan `key`. Jika bernilai `true`, framework tidak akan membuang dan merekonstruksi ulang `Element` dan `RenderObject`, melainkan hanya memperbarui konfigurasi propertinya.

#### Q3: Mengapa widget bersifat immutable sedangkan `RenderObject` bersifat mutable?
* **Jawaban**: Widget bertindak sebagai deklarasi blueprint konfigurasi yang murah dialokasikan dan dihancurkan berulang kali saat UI berubah. Sebaliknya, `RenderObject` merepresentasikan alokasi memori mahal yang mempertahankan state geometri layout dan instruksi visual sistem grafis, sehingga dimutasi secara langsung (*in-place*) untuk mempertahankan efisiensi komputasi.

#### Q4: Kapan Anda harus memanggil `markNeedsLayout()` dibanding `markNeedsPaint()` pada sebuah custom `RenderObject`?
* **Jawaban**: Panggil `markNeedsPaint()` ketika mutasi data hanya mengubah tampilan visual tanpa memengaruhi dimensi atau batas geometris node (misal: perubahan warna). Panggil `markNeedsLayout()` ketika mutasi memengaruhi dimensi (*size*), margin, padding, atau constraint anak-anaknya yang mengharuskan eksekusi ulang kalkulasi `performLayout()`.

#### Q5: Masalah spesifik apa pada engine Skia yang diselesaikan oleh engine Impeller pada Flutter versi modern?
* **Jawaban**: Impeller menyelesaikan masalah **Shader Compilation Jank**. Skia mengompilasi shader secara runtime saat frame pertama dibutuhkan (JIT), menyebabkan animasi pertama tersendat. Impeller mengompilasi seluruh shader secara Ahead-Of-Time (AOT) saat proses build aplikasi berlangsung.

---

### 15.2 Pertanyaan Intermediate

#### Q6: Jelaskan aturan baku "Constraints go down, sizes go up, parent sets position"!
* **Jawaban**: Parent meneruskan batasan struktural (*BoxConstraints*: min/max width, min/max height) ke bawah (*downward*) ke anaknya. Anak menentukan dimensinya sendiri (*Size*) berdasarkan batasan tersebut dan mengembalikannya ke atas (*upward*) ke parent. Terakhir, parent menentukan titik koordinat posisi visual relatif (*Offset*) dari anak tersebut pada kanvasnya.

#### Q7: Apa fungsi spesifik dari widget `RepaintBoundary` di level Layer Tree?
* **Jawaban**: `RepaintBoundary` menginstruksikan rendering pipeline untuk menyisipkan node `OffsetLayer` baru ke dalam Layer Tree, mengisolasi sub-tree tersebut dari visual parent. Dengan demikian, jika sub-tree di dalamnya di-mark kotor (*dirty*), rendering engine hanya me-record ulang display list sub-tree tersebut tanpa memicu repaint pada elemen di luar batas isolasi tersebut.

#### Q8: Apa perbedaan mendasar antara `sizedByParent = true` dan `sizedByParent = false` pada `RenderBox`?
* **Jawaban**: Jika `sizedByParent = true`, ukuran `RenderBox` ditentukan murni oleh constraints yang diteruskan parent tanpa memperhitungkan kalkulasi dimensinya sendiri atau anak-anaknya, sehingga framework mengalihkan penentuan ukuran ke method `performResize()`. Jika `false`, ukuran node dihitung secara mandiri di dalam `performLayout()`.

#### Q9: Mengapa pemanggilan `setState()` pada root widget aplikasi enterprise dianggap sebagai critical design flaw?
* **Jawaban**: Karena memicu dirty marking pada root `Element`, yang memaksa rekonsiliasi $O(N)$ traversal tree ke seluruh cabang aplikasi di bawahnya. Meskipun algoritma diffing Flutter cepat, overhead pemanggilan ribuan fungsi `build()` dan evaluasi referensi objek pada UI Thread memicu frame drop.

#### Q10: Bagaimana mekanisme memory management Flutter menghindari kebocoran memori pada `ImageStream` decoder native?
* **Jawaban**: Framework menggunakan pola cache `ImageCache` terpusat yang diintegrasikan dengan referensi native handle engine. Engine me-retain pointer buffer di IO thread dan hanya menyuplai frame ter-decode ke Dart UI thread. Dart wrapper menggunakan `ImageInfo` yang mengimplementasikan pembersihan deterministik via `dispose()` manual untuk melepaskan retain count pada lapisan native C++.

---

### 15.3 Skenario Kasus Produksi

#### Skenario 1: Frame Jank Berkala pada List Animasi Kompleks
* **Kasus**: Tim QA melaporkan animasi scroll pada feed aplikasi e-commerce selalu mengalami stuttering/jank setiap kali produk baru dimuat, dengan DevTools menunjukkan lonjakan Raster Thread hingga 32ms. CPU flame chart menunjukkan aktivitas kompilasi `saveLayer` yang intensif.
* **Pertanyaan**: Apa akar masalah arsitektur grafis ini dan bagaimana langkah perbaikannya secara teknis?
* **Jawaban**:
  1. *Akar Masalah*: Penggunaan widget visual seperti `Opacity` dinamis, `ColorFiltered`, atau kliping kompleks (`ClipRRect` / `ClipPath`) di dalam kartu item feed memaksa Skia/Impeller memicu panggilan off-screen rendering via `Canvas.saveLayer()`. Operasi ini mengharuskan GPU mengalokasikan off-screen buffer sementara, me-render sub-tree ke tekstur tersebut, lalu me-render balik ke frame buffer utama, melipatgandakan waktu GPU pass.
  2. *Solusi Teknis*: 
     - Ganti widget `Opacity` dengan langsung mengatur alpha pada level warna kanvas/properti widget (misal: `color: Color.fromRGBO(..., alpha)`).
     - Hilangkan `ClipRRect` dinamis jika gambar dari backend dapat di-cache dan di-resize sesuai target resolusi dengan rounded corners yang sudah di-bake sejak awal oleh image provider.
     - Analisis menggunakan flag `checkerboardOffscreenLayers = true` untuk mendeteksi area layar yang memicu alokasi save layer.

#### Skenario 2: Memory Leak Tersembunyi pada Event Bus / Stream Architecture
* **Kasus**: Setelah beroperasi selama 30 menit, aplikasi enterprise mendadak terminated secara paksa oleh sistem operasi dengan indikasi Out-Of-Memory (OOM). Profiler memory merekam ratusan `_ControllerSubscription` dan instance `Element` yang tetap tertahan di heap meskipun halamannya sudah ditutup (*popped*).
* **Pertanyaan**: Analisis penyebab retensi referensi memori ini dan bagaimana standarisasi arsitektur daur hidup yang benar untuk mencegahnya?
* **Jawaban**:
  1. *Akar Masalah*: `Element` atau presentation controllers mendaftarkan callback listener ke stream global/singleton (EventBus/Global Repository) tanpa membatalkan subskripsi (`subscription.cancel()`) saat siklus hidup routing berakhir. Objek singleton memegang referensi kuat (*strong reference*) ke closures callback yang secara implisit menahan instansiasi state/element, mencegah Dart GC mengklaim memori tersebut.
  2. *Solusi Teknis*:
     - Terapkan pembersihan eksplisit pada lifecycle method: Batalkan seluruh `StreamSubscription` di method `dispose()`.
     - Gunakan auto-cancellation pattern seperti package `flutter_bloc` (via `BlocProvider` scoping) atau library lifecycle-aware binding yang otomatis menutup stream saat scope-nya unmount.
     - Lakukan audit dengan DevTools Memory view: Ambil Heap Snapshot, telusuri *Retainer Path* dari objek yang bocor hingga ke akarnya.

#### Skenario 3: Unbounded Constraints Exception pada Modul Checkout
* **Kasus**: Seorang engineer junior menambahkan komponen custom layout ke halaman Checkout, menghasilkan crash fatal runtime:  
  `Horizontal viewport was given unbounded height.`  
  Komponen tersebut berupa `ListView` horizontal yang dibungkus di dalam `Column`.
* **Pertanyaan**: Jelaskan secara matematis constraint propagation yang terjadi dan berikan 2 opsi solusi arsitektural yang elegan!
* **Jawaban**:
  1. *Analisis Propagasi*: `Column` memberikan batasan vertikal yang tidak terbatas (`maxHeight: double.infinity`) kepada anak-anaknya. Ketika `ListView` horizontal diletakkan di dalamnya, ia meminta anaknya untuk mengabarkan batasan intrinsik, namun `ListView` sendiri membutuhkan parent yang menetapkan ketinggian batas pasti (`bounded height`) untuk menentukan ukuran cross-axis viewportnya. Karena parent (`Column`) memasok infinity dan child (`ListView`) membutuhkan bound, terjadi tabrakan invariant layout.
  2. *Solusi Arsitektural*:
     - **Solusi A**: Bungkus `ListView` dengan widget `SizedBox(height: konstan)` jika ketinggian kartu item diketahui secara pasti, membatasi nilai `maxHeight` menjadi angka skalar definitif.
     - **Solusi B**: Gunakan `Expanded` atau `Flexible` JIKA `Column` tersebut berada di dalam konteks layar yang memiliki bounded height (seperti `Scaffold` body), sehingga memaksa `ListView` mengisi sisa ruang vertikal yang tersedia secara proporsional.

---

## 16. Summary

1. **Rendering Subsystem Direct Control**: Flutter tidak menjembatani komponen ke OEM platform widgets melainkan menggambar secara otonom via **Impeller/Skia**, digerakkan oleh **4-Thread Model** (Platform, UI, Raster, IO).
2. **Three-Tree Synchronization**: Rekonsiliasi antara **Widget** (immutable specs), **Element** (persistent identity), dan **RenderObject** (geometry, layout, paint) dioptimalkan dengan algoritma diffing $O(N)$ berbasis kesamaan Type dan Key.
3. **Determinisme Layout Pipeline**: Layout dijalankan dalam satu pass linear: *Constraints go down, sizes go up, parent sets position*. Mengabaikan aturan ini menyebabkan invariant layout crash seperti Unbounded Constraints.
4. **Low-Level Performance Supremacy**: Mengimplementasikan custom `RenderBox` dan mengisolasi sub-tree dinamis menggunakan `RepaintBoundary` merupakan strategi mutlak untuk skenario ultra-high throughput data guna memitigasi overhead alokasi memori Dart VM dan kompilasi paint tree berlebih.