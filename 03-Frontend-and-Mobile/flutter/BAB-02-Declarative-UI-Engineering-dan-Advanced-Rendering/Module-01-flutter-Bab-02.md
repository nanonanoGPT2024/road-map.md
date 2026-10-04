# Bab 02 Module 01: Declarative UI Engineering & Advanced Rendering

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum**: 03-Frontend-and-Mobile
*   **Modul**: Bab 02 Module 01
*   **Topik**: Declarative UI Engineering & Advanced Rendering
*   **Tingkat Kesulitan**: Advanced / Staff Engineer Level
*   **Prasyarat**: Pemahaman mendalam tentang Dart OOP, Async Programming (Streams, Isolates), dan Lifecycle Dasar Flutter Widgets.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1.  **Membongkar Paradigma Deklaratif**: Mengisolasi dan membedakan siklus komputasi UI imperatif vs. deklaratif pada level engine ($UI = f(State)$).
2.  **Menganalisis Internal Tri-Tree Architecture**: Menjelaskan siklus hidup sinkronisasi antara *Widget Tree*, *Element Tree*, dan *RenderObject Tree*.
3.  **Menguasai Rendering Pipeline Engine**: Memetah tahapan frame Flutter dari *VSync Tick*, *Animate*, *Build*, *Layout (BoxConstraints down, Size up)*, *Paint*, hingga *Composite/Rasterize*.
4.  **Mengimplementasikan Low-Level Layouting**: Membangun custom layout logic menggunakan `MultiChildRenderObjectWidget` dan memanipulasi `RenderBox` secara langsung tanpa abstraksi framework dasar.
5.  **Mendiagnosis dan Mengeliminasi Bottleneck Rendering**: Mengidentifikasi jank, unneeded relayout/repaint boundaries, dan degradasi pipeline menggunakan Flutter DevTools & Dart Timeline Events.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam paradigma imperatif tradisional (Android View, iOS UIKit), pengembang memanipulasi referensi mutabel instans UI secara langsung:

```
// Mental Model Imperatif: Manipulasi State & View Terpisah
Button btn = findViewById(R.id.btn);
btn.setText("Clicked");
btn.setBackgroundColor(Color.RED);
```

Model mental deklaratif mentransformasikan komponen antarmuka menjadi **proyeksi matematis murni tanpa efek samping (*pure projection*)**:

$$\text{UI} = f(\text{State})$$

Di mana:
*   $\text{State}$ adalah representasi kebenaran tunggal (*Single Source of Truth*) pada waktu $t$.
*   $f$ adalah fungsi deterministik pohon build Flutter.
*   $\text{UI}$ adalah deskripsi blueprint struktural yang bersifat immutabel.

```
                  ┌──────────────────────┐
                  │     State Mutasi     │
                  └──────────┬───────────┘
                             │ Notifikasi Modifikasi
                             ▼
                  ┌──────────────────────┐
                  │    Engine Re-eval    │
                  │   UI = f(State)      │
                  └──────────┬───────────┘
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
┌───────────────────────┐         ┌───────────────────────┐
│     Old Blueprint     │         │     New Blueprint     │
│   (Immutable Widget)  │         │   (Immutable Widget)  │
└───────────┬───────────┘         └───────────┬───────────┘
            │                             │
            └──────────────┬──────────────┘
                           │ Diffing / Reconciliation
                           ▼
              ┌────────────────────────┐
              │ State Retaining Element│ (Mutable Identity)
              └────────────┬───────────┘
                           │ Perubahan Struktural / Geometri
                           ▼
              ┌────────────────────────┐
              │   RenderObject Tree    │ (Expensive Layout/Paint)
              └────────────────────────┘
```

**Kunci Mental Model Staff Engineer**:
*Widget bukanlah representasi visual nyata pada layar.* Widget hanyalah konfigurasi struktural sementara (*disposable lightweight blueprint*). *Element* adalah node manajerial struktural yang mempertahankan identitas pohon. *RenderObject* adalah entitas komputasi berat yang menghitung geometri, hit testing, dan instruksi rasterisasi GPU.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Alur hidup frame dari VSync platform thread hingga rasterisasi pada GPU dijalankan melalui pipeline 10 tahap:

```
[ Platform VSync Signal ]
           │
           ▼
┌────────────────────────────────────────────────────────┐
│ 1. Engine Phase: VSync Received                        │
└──────────┬─────────────────────────────────────────────┘
           ▼
┌────────────────────────────────────────────────────────┐
│ 2. Transient Callbacks: Ticker & Animation Tick        │
└──────────┬─────────────────────────────────────────────┘
           ▼
┌────────────────────────────────────────────────────────┐
│ 3. Persistent Callbacks: Build Phase                   │
│    - Rebuild dirty Elements                            │
│    - Diffing Widget Tree vs Element Tree               │
│    - Element.update() or Element.inflateWidget()       │
└──────────┬─────────────────────────────────────────────┘
           ▼
┌────────────────────────────────────────────────────────┐
│ 4. Layout Phase (PipelineOwner.flushLayout)            │
│    - Relayout Boundary traversal                       │
│    - Constraints go DOWN (min/max width & height)      │
│    - Geometry Sizes go UP (Size)                       │
└──────────┬─────────────────────────────────────────────┘
           ▼
┌────────────────────────────────────────────────────────┐
│ 5. Compositing Bits (PipelineOwner.flushCompositing)   │
│    - Update needsCompositing markers                   │
└──────────┬─────────────────────────────────────────────┘
           ▼
┌────────────────────────────────────────────────────────┐
│ 6. Paint Phase (PipelineOwner.flushPaint)              │
│    - Repaint Boundary isolation                        │
│    - Canvas draw commands recording                    │
│    - DisplayList generation                            │
└──────────┬─────────────────────────────────────────────┘
           ▼
┌────────────────────────────────────────────────────────┐
│ 7. Semantics Phase (PipelineOwner.flushSemantics)      │
│    - Accessibility tree updates                        │
└──────────┬─────────────────────────────────────────────┘
           ▼
┌────────────────────────────────────────────────────────┐
│ 8. Compositing Phase (RendererBinding.compositeFrame)  │
│    - SceneBuilder generates Scene                      │
└──────────┬─────────────────────────────────────────────┘
           ▼
┌────────────────────────────────────────────────────────┐
│ 9. Engine Send: window.render(Scene)                   │
└──────────┬─────────────────────────────────────────────┘
           ▼
┌────────────────────────────────────────────────────────┐
│ 10. Raster Thread: Impeller / Skia                     │
│    - GPU Command Buffer Encoding                       │
│    - Frame Buffer swap onto physical display           │
└────────────────────────────────────────────────────────┘
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### Tri-Tree Synchronization & Diffing Algorithm

Ketika `setState()` atau mutasi state terpicu, `Element` ditandai sebagai *dirty*. Algoritma rekonsiliasi mengeksekusi pemeriksaan identitas:

```dart
static bool canUpdate(Widget oldWidget, Widget newWidget) {
  return oldWidget.runtimeType == newWidget.runtimeType
      && oldWidget.key == newWidget.key;
}
```

```
[ Widget Tree (Rebuilt) ]          [ Element Tree (Retained) ]          [ RenderObject Tree ]
Container(Color: Red)              ComponentElement                     RenderDecoratedBox
        │                                  │                                     │
        ▼ (canUpdate == true)              ▼                                     ▼
Update: Container(Color: Blue) ──> element.update(newWidget) ────> renderObject.color = Blue
                                                                   (Marked Paint Dirty)
```

Jika `canUpdate` bernilai:
1.  **`true`**: Instans `Element` dipertahankan. Elemen memanggil `RenderObject.update...` untuk menyinkronkan parameter baru. *Zero reallocation of memory-heavy instances.*
2.  **`false`**: `Element` lama di-*unmount*, dibuang dari tree, `RenderObject` di-*dispose*, dan `Element` baru di-*inflate* dari widget baru bersama dengan alokasi `RenderObject` baru.

### Constraint Propagation: The Sacred Law of Layout

Layout Flutter tunduk pada satu aturan absolut:
*   **Constraints go Down**: Induk memberikan batasan (*Min Width, Max Width, Min Height, Max Height*) ke anak.
*   **Sizes go Up**: Anak menentukan dimensinya sendiri secara deterministik berdasarkan batasan tersebut, lalu melaporkannya kembali ke induk.
*   **Parent Sets Position**: Induk menentukan posisi koordinat ($x, y$) anak di dalam sistem koordinat lokalnya.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Relayout Boundaries

Relayout boundary membatasi propagasi layout pass. Tanpa relayout boundary, pemanggilan `markNeedsLayout()` pada suatu node anak akan menggelembung (*bubble up*) secara rekursif ke `rootElement`, memaksa *seluruh* pohon aplikasi menghitung ulang layout-nya.

Suatu `RenderObject` otomatis menjadi **Relayout Boundary** jika salah satu kondisi berikut terpenuhi pada layout pass-nya:
1.  `constraints.isTight`: Lebar dan tinggi minimum bernilai sama persis dengan lebar dan tinggi maksimum.
2.  `parentUsesSize == false`: Induk tidak menggunakan dimensi anak untuk menentukan ukuran dirinya sendiri.
3.  `sizedByParent == true`: Dimensi node ditentukan sepenuhnya oleh batasan induknya lewat `performResize()`.
4.  Parent bukan merupakan `RenderObject` (misal root RenderView).

```
   Parent RenderObject
          │
          ▼
   Relayout Boundary ─── [ markNeedsLayout() di sini terisolasi ]
          │
   Child RenderObject
          │
   Sub-child RenderObject (markNeedsLayout() DIPANGGIL)
   -> Mutasi layout merambat HANYA sampai boundary ini, berhenti, tidak mencapai Root!
```

### Repaint Boundaries

Serupa dengan relayout, operasi `markNeedsPaint()` akan menandai parent untuk digambar ulang hingga mencapai `isRepaintBoundary == true`. Repaint boundary mengisolasi subtree ke dalam layer tersendiri (`OffsetLayer`). GPU meng-cache hasil raster subtree tersebut; jika subtree di luar boundary digambar ulang, subtree di dalam boundary tidak perlu dieksekusi ulang di level instruksi canvas (`DisplayList`).

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut implementasi custom low-level layout engine menggunakan `MultiChildRenderObjectWidget`, mendemonstrasikan protokol manual layout pass, penentuan relayout boundary, dan penempatan anak (*positioning*) tanpa ketergantungan pada `Row`, `Column`, atau `Stack`.

Nama Komponen: **`CascadeFlowLayout`** (Menyusun elemen anak secara diagonal menurun dengan evaluasi constraint manual).

```dart
import 'package:flutter/widgets.dart';
import 'dart:math' as math;

// 1. ParentData: Menyimpan metadata posisi & status kustom tiap anak
class CascadeParentData extends ContainerBoxParentData<RenderBox> {
  double customScale = 1.0;
}

// 2. Widget Layer: Deklarasi Immutable
class CascadeFlowLayout extends MultiChildRenderObjectWidget {
  final double horizontalStep;
  final double verticalStep;

  const CascadeFlowLayout({
    super.key,
    this.horizontalStep = 32.0,
    this.verticalStep = 24.0,
    super.children,
  });

  @override
  RenderCascadeFlow createRenderObject(BuildContext context) {
    return RenderCascadeFlow(
      horizontalStep: horizontalStep,
      verticalStep: verticalStep,
    );
  }

  @override
  void updateRenderObject(BuildContext context, RenderCascadeFlow renderObject) {
    renderObject
      ..horizontalStep = horizontalStep
      ..verticalStep = verticalStep;
  }
}

// 3. RenderObject Layer: Mesin Komputasi Geometri
class RenderCascadeFlow extends RenderBox
    with
        ContainerRenderObjectMixin<RenderBox, CascadeParentData>,
        RenderBoxContainerDefaultsMixin<RenderBox, CascadeParentData> {
  
  double _horizontalStep;
  double _verticalStep;

  RenderCascadeFlow({
    required double horizontalStep,
    required double verticalStep,
  })  : _horizontalStep = horizontalStep,
        _verticalStep = verticalStep;

  double get horizontalStep => _horizontalStep;
  set horizontalStep(double value) {
    if (_horizontalStep == value) return;
    _horizontalStep = value;
    markNeedsLayout();
  }

  double get verticalStep => _verticalStep;
  set verticalStep(double value) {
    if (_verticalStep == value) return;
    _verticalStep = value;
    markNeedsLayout();
  }

  @override
  void setupParentData(RenderBox child) {
    if (child.parentData is! CascadeParentData) {
      child.parentData = CascadeParentData();
    }
  }

  @override
  void performLayout() {
    final BoxConstraints constraints = this.constraints;
    
    if (firstChild == null) {
      size = constraints.smallest;
      return;
    }

    double currentX = 0.0;
    double currentY = 0.0;
    double maxChildWidth = 0.0;
    double maxChildHeight = 0.0;

    RenderBox? child = firstChild;
    
    // Protokol Downward Constraint: Berikan batasan longgar (loose) ke setiap anak
    final BoxConstraints childConstraints = constraints.loosen();

    while (child != null) {
      final CascadeParentData childParentData = child.parentData! as CascadeParentData;
      
      // Layout anak, parentUsesSize: true karena layout induk bergantung ukuran anak
      child.layout(childConstraints, parentUsesSize: true);
      
      // Tentukan posisi anak (Parent sets position)
      childParentData.offset = Offset(currentX, currentY);

      maxChildWidth = math.max(maxChildWidth, currentX + child.size.width);
      maxChildHeight = math.max(maxChildHeight, currentY + child.size.height);

      currentX += _horizontalStep;
      currentY += _verticalStep;

      child = childParentData.nextSibling;
    }

    // Hitung ukuran akhir dari RenderBox ini, di-clamp ke constraints yang diberikan induk
    size = constraints.constrain(Size(maxChildWidth, maxChildHeight));
  }

  @override
  void paint(PaintingContext context, Offset offset) {
    // Protokol Paint: Gambar anak-anak berurutan sesuai posisinya
    defaultPaint(context, offset);
  }

  @override
  bool hitTestChildren(BoxHitTestResult result, {required Offset position}) {
    // Protokol Hit Testing dari anak paling atas (terakhir) ke paling bawah (pertama)
    return defaultHitTestChildren(result, position: position);
  }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

*   **Baris 5**: `class CascadeParentData extends ContainerBoxParentData<RenderBox>`: Mengalokasikan node data struktural. `ContainerBoxParentData` menyediakan referensi linked-list (`nextSibling`, `previousSibling`) untuk traversal performa tinggi tanpa alokasi array baru.
*   **Baris 10**: `class CascadeFlowLayout extends MultiChildRenderObjectWidget`: Entry point deklaratif ke dalam widget tree.
*   **Baris 20-25**: `createRenderObject`: Factory instansiasi `RenderCascadeFlow` yang dieksekusi saat `Element` di-*mount*.
*   **Baris 28-34**: `updateRenderObject`: Sinkronisasi properti dari widget baru ke `RenderObject` eksisting saat diffing algoritma bernilai `canUpdate == true`.
*   **Baris 38-40**: Mixin `ContainerRenderObjectMixin` & `RenderBoxContainerDefaultsMixin`: Menyediakan implementasi standar manajemen doubly-linked-list untuk anak-anak `RenderBox`.
*   **Baris 51-54**: Setter `horizontalStep`: Melakukan proteksi equality check (`_horizontalStep == value`). Bila ada perubahan, memanggil `markNeedsLayout()` secara eksplisit untuk menjadwalkan ulang layout pass pada pipeline berikutnya.
*   **Baris 63-67**: `setupParentData(RenderBox child)`: Hook inisialisasi ParentData ketika anak baru digabungkan ke tree.
*   **Baris 70**: `void performLayout()`: Jantung layout engine. Fungsi ini bertanggung jawab memenuhi kontrak Constraints Down, Sizes Up.
*   **Baris 87**: `child.layout(childConstraints, parentUsesSize: true)`: Memaksa anak menghitung layout dirinya. Argumen `parentUsesSize: true` memberi tahu Flutter bahwa perubahan ukuran anak wajib memicu relayout pada parent ini (memutus relayout boundary otomatis).
*   **Baris 90**: `childParentData.offset = Offset(currentX, currentY)`: Parent secara definitif menetapkan koordinat spatial lokal untuk anak.
*   **Baris 100**: `size = constraints.constrain(...)`: Menjamin ukuran `RenderCascadeFlow` tidak melanggar batasan `BoxConstraints` dari induknya.
*   **Baris 104**: `defaultPaint(context, offset)`: Menggambar seluruh anak dari firstChild ke lastChild menggunakan offset yang telah dihitung.

---

## SEKSI 09 — STUDI KASUS NYATA

### Enterprise Scenario: Virtualized Time-Series Financial Canvas

**Permasalahan**:
Sebuah platform broker valuta asing (FX Trading) memproses update data order-book dan grafik candlestick via WebSocket pada frekuensi 60 updates per detik (60Hz).
Jika UI dibangun menggunakan kombinasi standard declarative widget (`Column`, `Row`, `CustomPaint` di dalam `AnimatedBuilder` tanpa isolasi layer), sistem mengalami frame drop masif (<22 FPS) dan memori melonjak karena rekonsiliasi jutaan objek Widget dan Element per detik.

```
[ WebSocket Data Ingestion (60 updates/sec) ]
                     │
                     ▼
 [ Standard Flutter Widget Tree (Naive Approach) ]
      └── AnimatedBuilder / setState
           └── Re-eval seluruh Tree
                └── Canvas CustomPaint repaint SEMUA elemen
                     └── CRITICAL JANK: UI Thread > 16.6ms!
```

**Solusi Arsitektural**:
1.  Bypass widget reconciliation loop untuk render tick.
2.  Membangun custom `RenderBox` terisolasi dengan layer `RepaintBoundary` paksa (`isRepaintBoundary = true`).
3.  Memisahkan chart static grid layer dan dynamic tick lines ke dalam dua layer terpisah menggunakan `DisplayList` caching.
4.  Mengalirkan data langsung ke `RenderObject` melalui direct reference mutable buffer tanpa alokasi objek Widget baru pada setiap tick data.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

```dart
import 'dart:ui' as ui;
import 'package:flutter/foundation.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/widgets.dart';

// Model Finansial Immutabel
@immutable
class PricePoint {
  final double timestamp;
  final double price;

  const PricePoint({required this.timestamp, required this.price});
}

// Controller penyedia stream langsung ke RenderObject tanpa setState
class FastQuoteController extends ChangeNotifier {
  final List<PricePoint> _buffer = [];
  List<PricePoint> get buffer => List.unmodifiable(_buffer);

  void addPoint(PricePoint point) {
    _buffer.add(point);
    if (_buffer.length > 500) {
      _buffer.removeAt(0); // Batasi ukuran window rendering
    }
    notifyListeners();
  }
}

// Low-Level Leaf Widget
class FastOrderBookCanvas extends LeafRenderObjectWidget {
  final FastQuoteController controller;
  final Color chartColor;

  const FastOrderBookCanvas({
    super.key,
    required this.controller,
    required this.chartColor,
  });

  @override
  RenderFastOrderBook createRenderObject(BuildContext context) {
    return RenderFastOrderBook(
      controller: controller,
      chartColor: chartColor,
    );
  }

  @override
  void updateRenderObject(BuildContext context, RenderFastOrderBook renderObject) {
    renderObject
      ..controller = controller
      ..chartColor = chartColor;
  }
}

// High-Performance Engine-Level RenderBox
class RenderFastOrderBook extends RenderBox {
  FastQuoteController _controller;
  Color _chartColor;

  RenderFastOrderBook({
    required FastQuoteController controller,
    required Color chartColor,
  })  : _controller = controller,
        _chartColor = chartColor {
    _controller.addListener(_handleDataTick);
  }

  FastQuoteController get controller => _controller;
  set controller(FastQuoteController value) {
    if (_controller == value) return;
    _controller.removeListener(_handleDataTick);
    _controller = value;
    _controller.addListener(_handleDataTick);
    markNeedsPaint();
  }

  Color get chartColor => _chartColor;
  set chartColor(Color value) {
    if (_chartColor == value) return;
    _chartColor = value;
    markNeedsPaint();
  }

  void _handleDataTick() {
    // Meminta frame rendering berikutnya HANYA untuk paint, bypass layout pass
    markNeedsPaint();
  }

  @override
  void detach() {
    _controller.removeListener(_handleDataTick);
    super.detach();
  }

  // MENGUNCI LAYER: Mencegah canvas ini memicu paint ulang parent/sibling
  @override
  bool get isRepaintBoundary => true;

  @override
  bool get sizedByParent => true;

  @override
  Size computeDryLayout(BoxConstraints constraints) {
    // Komputasi layout tanpa efek samping
    return constraints.biggest;
  }

  @override
  void performResize() {
    // Mengambil seluruh ruang yang dialokasikan oleh parent
    size = constraints.biggest;
  }

  @override
  void paint(PaintingContext context, Offset offset) {
    final Canvas canvas = context.canvas;
    final Rect bounds = offset & size;

    // Clip rendering boundary agar tidak bocor keluar geometri
    canvas.save();
    canvas.clipRect(bounds);

    // Background Render
    final Paint bgPaint = Paint()..color = const Color(0xFF0F172A);
    canvas.drawRect(bounds, bgPaint);

    final points = _controller.buffer;
    if (points.length < 2) {
      canvas.restore();
      return;
    }

    final double minPrice = points.map((e) => e.price).reduce((a, b) => a < b ? a : b);
    final double maxPrice = points.map((e) => e.price).reduce((a, b) => a > b ? a : b);
    final double priceRange = (maxPrice - minPrice) == 0 ? 1.0 : (maxPrice - minPrice);

    final Path path = Path();
    final double dxStep = size.width / (points.length - 1);

    for (int i = 0; i < points.length; i++) {
      final double x = offset.dx + (i * dxStep);
      final double normalizedY = (points[i].price - minPrice) / priceRange;
      // Inversi Y karena koordinat Canvas 0,0 berada di kiri-atas
      final double y = offset.dy + size.height - (normalizedY * size.height);

      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }

    final Paint linePaint = Paint()
      ..color = _chartColor
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.0
      ..strokeCap = StrokeCap.round
      ..isAntiAlias = true;

    canvas.drawPath(path, linePaint);
    canvas.restore();
  }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Aspek Arsitektur | Standar Declarative Widget (`StatefulWidget`) | `CustomPainter` (`Canvas`) | Custom `RenderObject` (`RenderBox`) |
| :--- | :--- | :--- | :--- |
| **Abstraksi** | Sangat Tinggi (Composability tinggi) | Menengah (Functional canvas API) | Rendah (Engine Pipeline Integration) |
| **Alokasi Memori** | Tinggi (Widget instansiasi per-rebuild) | Menengah (Objek Painter dibuat ulang) | Terendah (Instans ditahan di tree) |
| **Biaya Layout** | Rekursif ke seluruh sub-tree | Tetap (Ditentukan oleh widget pembungkus) | Presisi Manual (Layout-pass kustom) |
| **Relayout Boundary Isolation** | Tergantung properti `Key` & parent constraints | Ditentukan oleh widget induk | Kontrol penuh via `sizedByParent = true` |
| **Repaint Boundary Isolation** | Manual (`RepaintBoundary` widget) | Manual (`RepaintBoundary` widget) | Terintegrasi via `isRepaintBoundary = true` |
| **Hit Testing Engine** | Otomatis via Widget tree | Terbatas (`hitTest` bool function) | Kontrol manual per-pixel koordinat |
| **Kompleksitas Perawatan** | Sangat Rendah | Sedang | Sangat Tinggi (Raw low-level Dart) |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The "Unbounded Constraints" Crash (RenderFlex / Custom RenderBox)
*   **Kasus**: Sebuah RenderObject menerima `BoxConstraints(0.0 <= w <= Infinity, 0.0 <= h <= Infinity)`. Terjadi saat ditempatkan di dalam `ListView` atau `SingleChildScrollView` tanpa batasan tinggi eksplisit.
*   **Failure Mode**: `AssertionError: BoxConstraints forces an infinite height` atau crash memori seketika jika mencoba mengalokasikan canvas berdasarkan `constraints.maxHeight`.
*   **Mitigasi**: Selalu sediakan *fallback dimension* atau lakukan pengecekan eksplisit di `performLayout`:
    ```dart
    final double targetHeight = constraints.hasBoundedHeight 
        ? constraints.maxHeight 
        : kDefaultComponentHeight;
    ```

### 2. Violating the Single-Pass Layout Rule
*   **Kasus**: Mencoba memanggil `child.layout()` lebih dari satu kali dalam satu frame `performLayout()` dengan argumen constraints yang berbeda untuk melakukan "coba-coba" pengukuran.
*   **Failure Mode**: Crash: `'!_debugMutationsLocked': is not true`. Desain Flutter adalah $O(N)$ single-pass rendering. Layout berulang memicu kompleksitas layout eksponensial $O(2^N)$.
*   **Mitigasi**: Gunakan sistem **Intrinsic Dimensions** (`computeMinIntrinsicWidth`, `computeMaxIntrinsicHeight`) untuk negosiasi ukuran sebelum layout pass aktual, atau definisikan protokol layout multi-pass kustom terisolasi secara internal.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Memanggil Operasi Berat di Dalam Metode `build()`
*   **Kesalahan Fatal**:
    ```dart
    @override
    Widget build(BuildContext context) {
      final formatter = DateFormat('yyyy-MM-dd'); // Alokasi CPU berulang
      return Text(formatter.format(DateTime.now()));
    }
    ```
*   **Dampak**: Menghancurkan performa 60/120 FPS. Metode `build()` dapat dipanggil setiap 8ms.
*   **Solusi**: Pindahkan inisialisasi parser/formatter ke lifecycle `initState()`, constructor konstan, atau static class cache.

### 2. Mengabaikan Boundary Check pada Setter `RenderObject`
*   **Kesalahan Fatal**:
    ```dart
    set dynamicWidth(double val) {
      _dynamicWidth = val;
      markNeedsLayout(); // Memaksa layout ulang bahkan jika valuenya SAMA!
    }
    ```
*   **Solusi**:
    ```dart
    set dynamicWidth(double val) {
      if (_dynamicWidth == val) return; // Wajib: Nilai sama = abort pipeline
      _dynamicWidth = val;
      markNeedsLayout();
    }
    ```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Ekstrak Leaf Widgets**: Jika widget tidak memiliki anak (*zero children*), selalu inherit dari `LeafRenderObjectWidget`, bukan `RenderObjectWidget` generik.
2.  **Deklarasikan `const` Constructor**: Selalu gunakan konstruktor konstan pada level widget tree untuk memungkinkan canonicalization memori Dart dan *short-circuiting* rekonsiliasi oleh element tree.
3.  **Terapkan `sizedByParent = true` Jika Memungkinkan**: Jika dimensi `RenderObject` sepenuhnya ditentukan oleh `constraints` induk (misal: selalu meregang memenuhi layar), setel `sizedByParent = true` dan lakukan perhitungan ukuran di `performResize()`. Ini mengisolasi tahap Layout dan memotong overhead propagasi layout anak.
4.  **Audit Render Tree Menggunakan Flag Debug**:
    ```dart
    void main() {
      debugProfileBuildsEnabled = true;
      debugPaintLayerBordersEnabled = true; // Visualisasi Repaint Boundaries
      runApp(const ProductionApp());
    }
    ```

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### DisplayList and Layer Caching
Setiap kali canvas digambar, framework merekam perintah grafis ke dalam `DisplayList`. Jika operasi rendering Anda melibatkan ratusan komputasi trigonometri (seperti chart), pastikan `RenderBox` dilindungi oleh Repaint Boundary:

```dart
@override
bool get isRepaintBoundary => true;
```

Ini menginstruksikan `Compositor` untuk mengalokasikan physical surface layer di GPU memory. Pada frame berikutnya, jika data tidak bermutasi, GPU hanya melakukan compositing tekstur yang sudah di-cache tanpa mengeksekusi ulang loop rendering CPU.

### Menghindari SaveLayer Overhead
Hindari pemanggilan eksplisit `canvas.saveLayer()`. Operasi ini memaksa GPU membuat offscreen render target terpisah, merender subtree ke dalamnya, lalu menggabungkannya kembali ke frame buffer utama (*offscreen switch*), menyebabkan degradasi drastis pada GPU fill-rate. Gunakan clipping standar atau fragment shader jika membutuhkan blending kompleks.

---

## SEKSI 16 — KEAMANAN & HARDENING

Pada arsitektur rendering kustom, kerentanan utama berpusat pada **DoS via Resource Exhaustion (Canvas Out-Of-Memory / Buffer Overflow)**:

1.  **Strict Coordinate Boundary Sanitization**:
    Data eksternal (misal koordinat dari WebSocket atau file GeoJSON) harus divalidasi dari nilai `double.nan`, `double.infinity`, dan nilai ekstrem di luar batas layar sebelum dioperasikan ke API Canvas:
    ```dart
    void safeDrawPoint(Canvas canvas, double x, double y) {
      if (x.isNaN || y.isNaN || x.isInfinite || y.isInfinite) {
        // Laporkan anomali ke internal log, putuskan rendering frame
        return;
      }
      canvas.drawCircle(Offset(x, y), 2.0, _paint);
    }
    ```
2.  **Path Sanitization & Complexity Limits**:
    Mencegah penyerang mengirim ribuan path vectors yang dapat membekukan GPU driver (TDR - Timeout Detection and Recovery crash). Batasi panjang node kalkulasi `Path` maksimal $N$ item per RenderBox execution pass.

---

## SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

### Pelacakan Custom Timeline Menggunakan `dart:developer`

Gunakan marker performa native untuk menganalisis durasi eksekusi layout dan paint kustom pada DevTools Profiler:

```dart
import 'dart:developer' as developer;

@override
void performLayout() {
  developer.Timeline.startSync('CustomLayout:OrderBook');
  try {
    // Layout logic execution
  } finally {
    developer.Timeline.finishSync();
  }
}

@override
void paint(PaintingContext context, Offset offset) {
  developer.Timeline.startSync('CustomPaint:OrderBook');
  try {
    // Painting operations
  } finally {
    developer.Timeline.finishSync();
  }
}
```

### Deteksi Jank Menggunakan Frame Timing Callback
Implementasikan observabilitas pipeline rendering pada level enterprise untuk mengirim telemetri ke observability backend (misal: Datadog, Sentry):

```dart
void setupRenderTelemetry() {
  WidgetsBinding.instance.addTimingsCallback((List<FrameTiming> timings) {
    for (final timing in timings) {
      final buildDuration = timing.buildDuration.inMilliseconds;
      final rasterDuration = timing.rasterDuration.inMilliseconds;
      
      if (buildDuration + rasterDuration > 16) {
        // Frame Drop Detected (> 16.6ms)
        telemetryClient.sendMetric('ui.frame_drop', {
          'build_ms': buildDuration,
          'raster_ms': rasterDuration,
        });
      }
    }
  });
}
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

*   **$UI = f(State)$**: Widget adalah konfigurasi immutabel; mutasi visual dikelola oleh reconciler Element dan engine RenderObject.
*   **Tri-Tree Roles**:
    *   *Widget*: Blueprint konfigurasi ringan ($O(1)$ allocation).
    *   *Element*: Pengelola siklus hidup, graph node, dan penyimpan state struktural.
    *   *RenderObject*: Engine kalkulasi ukuran geometris, penataan posisi, hit-test, dan pemanggilan canvas paint.
*   **Single-Pass Layout**:
    *   Constraints Down: Parent memberikan batasan minimum/maksimum.
    *   Sizes Up: Child menentukan ukurannya sendiri dalam batasan tersebut.
    *   Parent Sets Position: Child tidak pernah menentukan posisinya sendiri; Parent yang menulis `parentData.offset`.
*   **Pipeline Optimizations**:
    *   `markNeedsLayout()`: Menjadwalkan recalculation geometri.
    *   `markNeedsPaint()`: Menjadwalkan pengasramaan ulang layer canvas (bypass layout).
    *   `isRepaintBoundary = true`: Mengisolasi display-list ke layer terpisah di level GPU.
    *   `sizedByParent = true`: Memisahkan kalkulasi ukuran ke `performResize()` sehingga layout anak tidak memicu layout parent.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal 1
Kondisi manakah yang secara otomatis menjadikan sebuah `RenderObject` bertindak sebagai **Relayout Boundary**?
*   A. `isRepaintBoundary` bernilai `true`.
*   B. `constraints.isTight` bernilai `true`.
*   C. `parentUsesSize` bernilai `true`.
*   D. Mengimplementasikan `ContainerRenderObjectMixin`.

### Soal 2
Apa yang terjadi pada `Element Tree` jika sebuah widget lama digantikan oleh widget baru yang memiliki `runtimeType` berbeda tetapi memiliki `Key` yang sama?
*   A. Element dipertahankan dan fungsi `update()` dipanggil.
*   B. Framework membuang (unmount) Element lama beserta sub-treenya dan meng-inflate Element baru.
*   C. Terjadi error assertion pada saat kompilasi.
*   D. State dari Element lama disalin secara otomatis ke Element baru melalui reflection