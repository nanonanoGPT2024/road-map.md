# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Kategori:** 03-Frontend-and-Mobile  
**Bab 03:** BAB-03-Multi-Platform-Adaptive-dan-Responsive-Architecture  
**Tingkat Kesulitan:** Advanced / Enterprise Grade

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Principal Engineer/Senior Mobile Architect diharapkan mampu:
- Menganalisis dan membedah internal engine Flutter terkait layout cycle: proses propagasi *Constraints go down, Sizes go up, Parent sets position*, serta dampaknya terhadap alokasi memori dan render pipeline.
- Merancang dan mengimplementasikan arsitektur *Adaptive & Responsive Design System* tingkat enterprise yang memisahkan abstraksi bisnis dari layout presentation layer di Desktop (macOS, Windows, Linux), Web, Tablet, Foldable, dan Mobile (Android, iOS).
- Mengisolasi *relayout boundaries* secara tepat untuk mencegah cascade reflow pada hierarki widget yang kompleks.
- Menangani form-factor unik seperti perangkat lipat (*foldables/dual-screen*) menggunakan `DisplayFeature` API dan engsel (*hinge*) geometry secara presisi.
- Mengintegrasikan modalitas input heterogen (pointer hover, scroll wheel, mouse right-click context menu, physical keyboard shortcuts, touch gestures) dalam satu basis kode tanpa degradasi performa frame rate (stabil di 60/120 FPS).

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
- **Flutter Framework Internals**: Memahami siklus hidup `Widget`, `Element`, dan `RenderObject`.
- **Tree Pipeline Engine**: Alur *Build -> Layout -> Compositing Bits -> Paint -> Semantics -> RenderDoc/Rasterization*.
- **State Management Terisolasi**: Implementasi state management berbasis streams/listenable (misalnya: BLoC/Cubit, Riverpod) yang mematuhi arsitektur terdesentralisasi (*unidirectional data flow*).
- **Dart Advanced Concepts**: Mixins, extension methods, dynamic invocations vs static dispatch, `Platform` check vs conditional imports compilation.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Layout Protocol Engine & Relayout Boundaries

Flutter tidak menggunakan HTML DOM reflow model berbasis flexbox CSS tradisional. Di engine C++ dan framework Dart, layout dijalankan dalam satu lintasan linear $O(N)$ melalui protokol layout ketat:

1. **Constraints Down**: Parent meneruskan `BoxConstraints` (minWidth, maxWidth, minHeight, maxHeight) ke Child.
2. **Sizes Up**: Child menghitung dan menentukan ukurannya sendiri (`Size(width, height)`) strictly di dalam rentang batas yang diberikan parent, lalu mengembalikannya ke Parent.
3. **Parent Sets Position**: Parent menentukan koordinat visual Child (`Offset(x, y)`) dalam render coordinates child tersebut melalui `parentData`.

```
[Parent RenderObject] 
      │
      │ 1. Passes BoxConstraints (minW, maxW, minH, maxH)
      ▼
[Child RenderObject]
      │
      │ 2. Calculates & Returns Size(width, height)
      ▼
[Parent RenderObject]
      │
      │ 3. Sets Child Offset(dx, dy) inside Child's ParentData
      ▼
[Compositing Layer Scene]
```

#### Relayout Boundary
Relayout boundary memutus propagasi rekursif pemanggilan `markNeedsLayout()` agar tidak merambat ke root node tree (`RenderView`). Sebuah `RenderObject` secara otomatis menjadi relayout boundary jika memenuhi salah satu dari empat predikat matematis berikut pada method `cleanRelayoutBoundary`:
- `sizedByParent == true`
- `constraints.isTight` (minWidth == maxWidth && minHeight == maxHeight)
- `!parentUsesSize` (Parent tidak membaca atau bergantung pada `child.size` saat parent mengeksekusi `performLayout()`)
- `parent is! RenderObject` (Root node)

Mengabaikan relayout boundaries pada layar adaptif yang dinamis (seperti resizing window desktop) akan memaksa relayout penuh pada ribuan render nodes, menyebabkan micro-stuttering dan drop frame (*jank*).

### 3.2 Platform-Adaptive Resolution vs Responsive Layout

Sering terjadi kerancuan antara *Responsiveness* dan *Adaptivity*:
- **Responsiveness**: Reaksi UI terhadap variasi dimensi visual viewport (lebar, tinggi, orientasi, aspect ratio, split-screen desktop tiling). Diukur secara metrik spasial.
- **Adaptivity**: Reaksi aplikasi terhadap karakteristik target platform execution:
  - Input device primitives (sentuhan, mouse kursor dengan pointer hover, physical keyboard navigation).
  - Platform UX idioms (Cupertino vs Material 3 tokens, NavigationRail vs BottomNavigationBar, App-bar behavior).
  - System Capabilities (Multi-window capability desktop, system tray, display cutouts, fold/hinge sensors).

### 3.3 Internal Injeksi MediaQuery dan DisplayFeature Engine

`MediaQuery` diinisialisasi pada level framework melalui `WidgetsBindingObserver.didChangeMetrics()`. Engine membaca data native platform via `PlatformDispatcher.instance.views` dan menyuntikkannya ke dalam pipeline rendering.

Pada perangkat lipat (*foldables*), data engsel fisik diekspos melalui `ViewConfiguration` sebagai instance dari `DisplayFeature`. `DisplayFeatureType.hinge` atau `DisplayFeatureType.fold` memberikan koordinat fisik engsel (*bounding box* `Rect`) serta status oklusi (`DisplayFeatureState`). 

Pengabaian deteksi sub-layar ini berisiko menempatkan tombol atau input field tepat di atas lipatan fisik layar, merusak fungsionalitas dan usability aplikasi secara fatal.

---

## 4. Why & What

| Paradigma Lama (Fragile/Naive) | Paradigma Modern (Production-Ready Architecture) |
|---|---|
| Menggunakan `MediaQuery.of(context).size.width` secara langsung di dalam puluhan build method UI. | Mengabstraksikan breakpoint menggunakan design tokens berbasis semantic window sizes (`Compact`, `Medium`, `Expanded`, `Large`, `ExtraLarge`). |
| Memvalidasi platform via `Platform.isAndroid` atau `Platform.isIOS` secara imperatif di runtime UI. | Menerapkan `AdaptiveStrategyFactory` / *Composition Pattern* yang memisahkan logic platform-specific ke layer infrastruktur. |
| Hardcoding `setState()` untuk mendeteksi event resize window. | Memanfaatkan `LayoutBuilder` secara selektif pada isolated subtree atau memanfaatkan dynamic breakpoint observer berbasis streams. |
| Satu arsitektur navigasi global dipaksa berjalan di Mobile dan Desktop. | Menerapkan *Dual-Pane Router Engine*: Switch dari hierarchical push-stack (Mobile) ke Master-Detail side-by-side view (Desktop/Tablet) secara deklaratif. |

---

## 5. How (Workflow Detail)

Alur perancangan arsitektur multi-platform yang resilient:

```
[Engine Window Metrics Updated]
               │
               ▼
[Root PlatformDispatcher / View.of(context)]
               │
               ▼
[ResponsiveBreakpointsProvider (InheritedModel)]
               │
               ├────────────────────────────────────────┐
               ▼                                        ▼
    [Width/Height Categorization]             [DisplayFeature Extraction]
    (Compact, Medium, Expanded)               (Hinge Rect, Posture State)
               │                                        │
               └───────────────────┬────────────────────┘
                                   │
                                   ▼
                   [AdaptiveFormFactorContext Token]
                                   │
               ┌───────────────────┴───────────────────┐
               ▼                                       ▼
     [Layout Strategy Selection]             [Input Modality Adapters]
   - SinglePaneStrategy (Compact)          - TouchGestures
   - MasterDetailStrategy (Expanded)       - MouseRegion (Hover / RightClick)
   - DualFoldStrategy (Separating Hinge)   - FocusableActionDetector (Shortcuts)
```

1. **Sinkronisasi Metrics Native**: Engine mendeteksi event perubahan ukuran window OS atau folding angle engsel via C++ embedder.
2. **Normalisasi Token Layout**: Framework mengabstraksi raw pixel dimensions menjadi Semantic Device Segments yang di-cache menggunakan `InheritedModel` (untuk menghindari rebuild widget yang hanya bergantung pada orientasi atau hinge).
3. **Seleksi Strategi Navigasi & Presentation**: Layout engine menentukan apakah layout menggunakan single canvas atau multi-pane canvas.
4. **Input Capability Binding**: Widget tree mengaktifkan interaksi mouse hover listener, shortcut controller keyboard, dan scroll wheel physics jika environment target bukan pointer sentuh murni.

---

## 6. Analogy & Diagram ASCII

Bayangkan sebuah kontainer kargo modular standar ISO (*BoxConstraints*).

- Kontainer kargo memiliki batas dimensi eksternal yang kaku yang ditetapkan oleh kapal pengangkut (*Parent*).
- Di dalam kontainer, produsen barang (*Child*) bebas menyusun rak penyimpanan selama dimensi rak tidak melebihi volume interior kontainer.
- Jika barang yang dimasukkan menuntut ruang lebih besar daripada volume kontainer fisik, kontainer tersebut akan jebol (*A RenderFlex overflowed by xxx pixels error*).
- Jika kapal kontainer berganti dari kapal sungai kecil (*Mobile*) menjadi kapal samudra raksasa (*Desktop Ultra-Wide*), kontainer tersebut tidak membesar secara elastis tak beraturan; sebaliknya, manajemen kapal mendistribusikan beberapa unit kontainer secara berdampingan (*Multi-Pane Architecture*).

```
                      DESKTOP VIEWPORT (> 1200dp)
┌────────────────────────────────────────────────────────────────────────┐
│ [ Navigation Rail ]  [ Master List Pane ]     [ Detail Content Pane ]  │
│ │ [Home]          │  │ ┌───────────────────┐ │ │ ┌───────────────────┐│ │
│ │ [Analytics]     │  │ │ Item #1 (Active)  │ │ │ │ Header Details    ││ │
│ │ [Settings]      │  │ └───────────────────┘ │ │ └───────────────────┘│ │
│ │                 │  │ ┌───────────────────┐ │ │ Content canvas with │ │
│ │                 │  │ │ Item #2           │ │ │ high-density data│ │
│ │                 │  │ └───────────────────┘ │ │ grids and metrics   │ │
│ └─────────────────┘  └─────────────────────┘ └────────────────────────┘│
└────────────────────────────────────────────────────────────────────────┘

              FOLDABLE VIEWPORT WITH PHYSICAL HINGE
┌──────────────────────────────┬───┬──────────────────────────────┐
│       Left Pane View         │ H │       Right Pane View        │
│                              │ I │                              │
│   List / Controller Pane     │ N │    Detail / Visualizer       │
│                              │ G │                              │
│                              │ E │                              │
└──────────────────────────────┴───┴──────────────────────────────┘

                   COMPACT MOBILE VIEWPORT (< 600dp)
┌────────────────────────────────┐
│ [ Top App Bar / Context Nav ]  │
├────────────────────────────────┤
│ ┌────────────────────────────┐ │
│ │ Item #1 (Tappable)         │ │
│ └────────────────────────────┘ │
│ ┌────────────────────────────┐ │
│ │ Item #2 (Tappable)         │ │
│ └────────────────────────────┘ │
├────────────────────────────────┤
│ [ Bottom Navigation Bar ]      │
└────────────────────────────────┘
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Relayout Boundary Isolation dengan LayoutBuilder

Contoh ini menunjukkan cara mengisolasi kalkulasi layout pada komponen dinamis agar tidak memicu re-layout pada parent tree:

```dart
import 'package:flutter/material.dart';

class IsolatedAdaptiveCard extends StatelessWidget {
  final Widget child;

  const IsolatedAdaptiveCard({super.key, required this.child});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: LayoutBuilder(
        builder: (BuildContext context, BoxConstraints constraints) {
          // Mengakses constraints tanpa memanggil MediaQuery global.
          // Mengisolasi layout rebuild di sub-tree ini secara efisien.
          final bool isCompact = constraints.maxWidth < 400.0;

          return Padding(
            padding: EdgeInsets.all(isCompact ? 8.0 : 24.0),
            child: isCompact 
                ? Column(mainAxisSize: MainAxisSize.min, children: [child])
                : Row(children: [Expanded(child: child)]),
          );
        },
      ),
    );
  }
}
```

### 7.2 Practical Example: Enterprise Production Adaptive Architecture

Sistem Token Window Klasifikasi, Hinge Separation Sub-System, dan Input Modality Support.

```dart
// lib/core/responsive/breakpoint_tokens.dart
import 'dart:ui' as ui;
import 'package:flutter/material.dart';

enum WindowClass { compact, medium, expanded, large, extraLarge }

@immutable
class WindowSizeClass {
  final WindowClass widthClass;
  final WindowClass heightClass;
  final Size rawSize;
  final Rect? hingeBounds;
  final bool hasSeparatingHinge;

  const WindowSizeClass._({
    required this.widthClass,
    required this.heightClass,
    required this.rawSize,
    this.hingeBounds,
    this.hasSeparatingHinge = false,
  });

  factory WindowSizeClass.fromContext(BuildContext context) {
    final MediaQueryData mediaQuery = MediaQuery.of(context);
    final Size size = mediaQuery.size;

    // Klasifikasi Standard Material 3 Design Window Size Specs
    final WindowClass widthClass = switch (size.width) {
      < 600.0 => WindowClass.compact,
      >= 600.0 && < 840.0 => WindowClass.medium,
      >= 840.0 && < 1200.0 => WindowClass.expanded,
      >= 1200.0 && < 1600.0 => WindowClass.large,
      _ => WindowClass.extraLarge,
    };

    final WindowClass heightClass = switch (size.height) {
      < 480.0 => WindowClass.compact,
      >= 480.0 && < 900.0 => WindowClass.medium,
      _ => WindowClass.expanded,
    };

    // Deteksi display feature (Foldable Hinge)
    Rect? hinge;
    bool separates = false;
    for (final ui.DisplayFeature feature in mediaQuery.displayFeatures) {
      if (feature.type == ui.DisplayFeatureType.hinge ||
          feature.type == ui.DisplayFeatureType.fold) {
        hinge = feature.bounds;
        separates = feature.state == ui.DisplayFeatureState.postureHalfOpened ||
            feature.bounds.width > 0;
        break;
      }
    }

    return WindowSizeClass._(
      widthClass: widthClass,
      heightClass: heightClass,
      rawSize: size,
      hingeBounds: hinge,
      hasSeparatingHinge: separates,
    );
  }
}

// lib/core/responsive/adaptive_scaffold.dart
class EnterpriseAdaptiveScaffold extends StatelessWidget {
  final Widget navigationBar;
  final Widget navigationRail;
  final Widget primaryBody;
  final Widget? secondaryBody;

  const EnterpriseAdaptiveScaffold({
    super.key,
    required this.navigationBar,
    required this.navigationRail,
    required this.primaryBody,
    this.secondaryBody,
  });

  @override
  Widget build(BuildContext context) {
    final WindowSizeClass windowMetrics = WindowSizeClass.fromContext(context);

    // KASUS 1: Perangkat Lipat (Foldable) dengan Engsel Pemisah Fisik Aktif
    if (windowMetrics.hasSeparatingHinge && windowMetrics.hingeBounds != null) {
      final double leftPaneWidth = windowMetrics.hingeBounds!.left;
      final double rightPaneWidth =
          windowMetrics.rawSize.width - windowMetrics.hingeBounds!.right;

      return Scaffold(
        body: Row(
          children: [
            SizedBox(
              width: leftPaneWidth,
              child: primaryBody,
            ),
            SizedBox(width: windowMetrics.hingeBounds!.width), // Spacer fisik engsel
            SizedBox(
              width: rightPaneWidth,
              child: secondaryBody ?? const SizedBox.shrink(),
            ),
          ],
        ),
      );
    }

    // KASUS 2: Desktop / Layar Lebar (Expanded, Large, ExtraLarge)
    if (windowMetrics.widthClass.index >= WindowClass.expanded.index) {
      return Scaffold(
        body: Row(
          children: [
            navigationRail,
            const VerticalDivider(width: 1, thickness: 1),
            Expanded(
              flex: 4,
              child: primaryBody,
            ),
            if (secondaryBody != null) ...[
              const VerticalDivider(width: 1, thickness: 1),
              Expanded(
                flex: 6,
                child: secondaryBody!,
              ),
            ],
          ],
        ),
      );
    }

    // KASUS 3: Tablet / Medium Size (Master Pane with Sliding/Stack behavior)
    if (windowMetrics.widthClass == WindowClass.medium) {
      return Scaffold(
        body: Row(
          children: [
            navigationRail,
            const VerticalDivider(width: 1, thickness: 1),
            Expanded(child: primaryBody),
          ],
        ),
      );
    }

    // KASUS 4: Compact Form Factor (Smartphones)
    return Scaffold(
      body: primaryBody,
      bottomNavigationBar: navigationBar,
    );
  }
}

// lib/core/responsive/desktop_interaction_wrapper.dart
class DesktopInteractiveContainer extends StatefulWidget {
  final Widget child;
  final VoidCallback onActivate;
  final ValueChanged<bool>? onHoverChange;

  const DesktopInteractiveContainer({
    super.key,
    required this.child,
    required this.onActivate,
    this.onHoverChange,
  });

  @override
  State<DesktopInteractiveContainer> createState() =>
      _DesktopInteractiveContainerState();
}

class _DesktopInteractiveContainerState
    extends State<DesktopInteractiveContainer> {
  bool _isHovered = false;

  @override
  Widget build(BuildContext context) {
    return FocusableActionDetector(
      mouseCursor: SystemMouseCursors.click,
      actions: <Type, Action<Intent>>{
        ActivateIntent: CallbackAction<ActivateIntent>(
          onInvoke: (_) => widget.onActivate(),
        ),
      },
      shortcuts: const <ShortcutActivator, Intent>{
        SingleActivator(LogicalKeyboardKey.enter): ActivateIntent(),
        SingleActivator(LogicalKeyboardKey.space): ActivateIntent(),
      },
      onShowHoverHighlight: (bool value) {
        setState(() => _isHovered = value);
        widget.onHoverChange?.call(value);
      },
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        curve: Curves.easeInOut,
        decoration: BoxDecoration(
          color: _isHovered
              ? Theme.of(context).colorScheme.surfaceContainerHighest
              : Colors.transparent,
          borderRadius: BorderRadius.circular(8.0),
        ),
        child: widget.child,
      ),
    );
  }
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Re-platforming Global Omni-channel ERP Terminal
*Global Supply Chain Logistics System* menggabungkan:
1. Smartphone Scanner Kurir (Android/iOS low-tier).
2. Ruggedized Handheld Tablet dengan Hinge/Dual Screen (Zebra & Galaxy Fold).
3. Stasiun Manajemen Logistik Desktop (Dual-monitor 4K macOS & Windows 11).

#### Kendala Arsitektural Awal:
- Menggunakan `MediaQuery.sizeOf(context)` di dalam controller pusat state; setiap kali keyboard virtual muncul pada mobile scanner, seluruh dashboard mengalami trigger build ulang dari root.
- Memory footprint pada runtime Desktop melonjak hingga 1.8GB karena rendering image grid list memicu instansiasi widget secara unbounded (*missing relayout & repaint boundary containment*).
- Pada perangkat lipat (Galaxy Fold), form inspeksi barcode terpotong di tengah display karena UI merender form field tepat di bawah area engsel.

#### Intervensi Solusi Principal Architect:
1. **Penerapan Subtree Invalidation dengan InheritedModel**: Menggantikan `MediaQuery.of(context)` dengan model terseleksi `WindowBreakpointProvider`. Event keyboard (yang hanya mengubah `viewInsets`) tidak lagi memicu update pada layout struktural navigasi.
2. **Implementasi Hinge-Aware Viewport Partitioning**: Penggunaan dynamic viewport divider dengan kalkulasi `DisplayFeature.bounds`. Jika posisi fold vertikal, view dipecah menjadi `Scanner Camera Feed (Kiri)` dan `Validated Cargo Tree View (Kanan)`.
3. **Hardware Acceleration Tuning Desktop**: Memasang `RepaintBoundary` eksplisit pada master navigation side rail dan detail visualizer, menurunkan draw call time dari 16.4ms menjadi 2.1ms pada monitor 144Hz.

---

## 9. Trade-offs (Performance, Latency, Scalability, Cost)

```
┌─────────────────────────────────┬───────────────────────────────────────────┐
│ Strategi Layout & Arsitektur    │ Keuntungan & Kerugian                     │
├─────────────────────────────────┼───────────────────────────────────────────┤
│ Universal Single Codebase       │ (+) Biaya pemeliharaan minimum (Cost Eff) │
│ Adaptive Components             │ (-) Kompleksitas logika percabangan tinggi│
│                                 │ (-) Risiko overhead render jika bloat code│
├─────────────────────────────────┼───────────────────────────────────────────┤
│ LayoutBuilder per Subtree       │ (+) Presisi tinggi pada ukuran lokal      │
│ (Granular Responsiveness)       │ (-) Micro-overhead ekstra pada build time │
│                                 │ (-) Memperdalam tree element nesting      │
├─────────────────────────────────┼───────────────────────────────────────────┤
│ MediaQuery Global Consumption   │ (+) Sangat mudah & cepat diimplementasi   │
│                                 │ (-) Memicu wide-invalidation performance  │
│                                 │     jank pada mobile resize/IME insets    │
├─────────────────────────────────┼───────────────────────────────────────────┤
│ Native Separate Layout Codebase │ (+) Performa platform 100% optimal        │
│ (Platform-specific binaries)    │ (-) Redundansi kode besar (High Dev Cost) │
│                                 │ (-) Divergensi implementasi fitur bisnis  │
└─────────────────────────────────┴───────────────────────────────────────────┘
```

- **Performance Trade-off**: Membungkus setiap container dengan `LayoutBuilder` memperkenalkan overhead alokasi memory layout pass Dart closure. Batasi `LayoutBuilder` hanya pada simpul layout struktural tingkat menengah.
- **Maintainability vs Flexibility**: Menggunakan adaptasi platform otomatis (seperti `flutter_platform_widgets`) memudahkan di awal, namun membatasi fleksibilitas kustomisasi saat designer menuntut UI styling Material 3 yang dikustomisasi total pada ekosistem macOS.

---

## 10. Common Mistakes & Troubleshooting

### Anti-Pattern 1: Mengabaikan Inherited Dependency Scope pada MediaQuery
**Problem**: Menggunakan `MediaQuery.of(context).size` pada root layout. Ketika keyboard muncul, `viewInsets.bottom` berubah, dan seluruh pohon layout di-rebuild, bukan hanya screen yang memiliki text field.  
**Solusi**:
```dart
// JANGAN LAKUKAN INI:
final double screenWidth = MediaQuery.of(context).size.width; 

// GUNAKAN METODE TARGETED (Flutter 3.7+):
final Size size = MediaQuery.sizeOf(context);
final double width = size.width;
// Ini mencegah rebuild jika hanya EdgeInsets (viewInsets/padding) yang berubah!
```

### Anti-Pattern 2: Unbounded Constraints Crash pada Multi-Pane Expanded Views
**Problem**: Meletakkan `ListView` secara langsung di dalam horizontal `Row` tanpa membungkusnya dengan bounded constraints:
`RenderFlex children have non-zero flex but incoming width constraints are unbounded.`  
**Solusi**:
```dart
// SALAH:
Row(
  children: [
    NavigationMenu(),
    ListView.builder(itemBuilder: ...), // CRASH: unbounded width
  ],
)

// BENAR:
Row(
  children: [
    const NavigationMenu(),
    Expanded(
      child: ListView.builder(itemBuilder: ...),
    ),
  ],
)
```

### Anti-Pattern 3: Pointer Device Ignorance pada Desktop Build
**Problem**: Aplikasi desktop terasa seperti "aplikasi mobile yang ditarik melebar" karena ketiadaan handling hover cursor, right-click, dan scroll wheel resolution.  
**Solusi**: Wajib membungkus item interaktif desktop dengan `MouseRegion` dan mengatur `ScrollBehavior` yang mengizinkan drag pointer devices yang tepat:
```dart
class DesktopScrollBehavior extends MaterialScrollBehavior {
  @override
  Set<PointerDeviceKind> get dragDevices => {
    PointerDeviceKind.touch,
    PointerDeviceKind.mouse,
    PointerDeviceKind.trackpad,
  };
}
```

---

## 11. Best Practices (Production Checklist)

- [ ] **Gunakan Targeted MediaQuery API**: Hanya konsumsi `MediaQuery.sizeOf(context)`, `MediaQuery.orientationOf(context)`, atau `MediaQuery.viewInsetsOf(context)`. Jangan pernah gunakan `MediaQuery.of(context)` telanjang.
- [ ] **Isolasi Relayout Boundary**: Pastikan list item dinamis yang kompleks dibungkus dengan constraint yang tight atau memanfaatkan `RepaintBoundary` jika memuat asset grafis berat / animasi.
- [ ] **Zero Magic Breakpoint Numbers**: Tidak boleh ada angka mentah seperti `if (width > 600)` yang tersebar di UI layer. Semua wajib merujuk ke immutable tokens seperti `WindowClass.medium`.
- [ ] **Dukungan Hinge Safe Zone**: Area kritis seperti form field, tombol konfirmasi pembayaran, dan modal aksi tidak boleh berada di koordinat `DisplayFeature.bounds`.
- [ ] **Multi-Input Modality Support**: Setiap komponen aksi harus mendukung event sentuhan, mouse hover highlight, serta keyboard shortcut bindings (`LogicalKeyboardKey.enter`, `escape`, dsb.).
- [ ] **Dynamic Title Bar Handling (Desktop)**: Gunakan plugin platform window (misal: `bitsdojo_window` / `window_manager`) untuk merender custom title bar yang adaptif terhadap frame window native macOS/Windows.

---

## 12. Hands-on Practice

Buat arsitektur adaptif modular pada path `hands-on/m02/`.

### Struktur Folder Proyek
```
hands-on/m02/
├── lib/
│   ├── core/
│   │   ├── responsive/
│   │   │   ├── breakpoint_provider.dart
│   │   │   ├── layout_engine.dart
│   │   │   └── input_adapter.dart
│   │   └── theme/
│   │       └── tokens.dart
│   ├── presentation/
│   │   ├── components/
│   │   │   ├── adaptive_navigation.dart
│   │   │   └── data_display_pane.dart
│   │   └── screens/
│   │       └── enterprise_dashboard_screen.dart
│   └── main.dart
└── test/
    └── layout_engine_test.dart
```

### Langkah Pelaksanaan
1. **Langkah 1**: Buat implementasi tokenisasi window pada `lib/core/responsive/breakpoint_provider.dart` memanfaatkan `InheritedModel` yang mendistribusikan class layout: Compact, Medium, Expanded.
2. **Langkah 2**: Pada `lib/presentation/components/adaptive_navigation.dart`, implementasikan auto-switching:
   - Lebar < 600: Bottom Navigation Bar.
   - 600 <= Lebar < 1200: Navigation Rail.
   - Lebar >= 1200: Extended Navigation Drawer permanen.
3. **Langkah 3**: Buat Dual-Pane visualizer pada `enterprise_dashboard_screen.dart`. Jika `WindowClass` adalah `Expanded`, render Master List dan Detail Pane berdampingan. Jika `Compact`, navigasikan ke sub-route terpisah menggunakan Navigator declarative (`Router` atau `GoRouter`).
4. **Langkah 4**: Pasang `MouseRegion` dan `FocusableActionDetector` pada item Master List. Verifikasi transisi visual saat di-hover dengan mouse dan saat tombol panah atas/bawah ditekan pada keyboard fisik desktop.

---

## 13. Exercise

### Level Easy
Ubah layout hardcoded berbasis orientasi (`MediaQuery.of(context).orientation == Orientation.portrait`) menjadi implementasi yang aman berbasis `MediaQuery.sizeOf(context).width < 600`, dan jelaskan mengapa pendekatan orientasi sering memicu layout bug pada desktop tiling dan tablet split-screen.

### Level Medium
Buat sebuah custom widget `AdaptiveActionSheet` yang secara otomatis menampilkan `CupertinoActionSheet` saat dijalankan di macOS/iOS dan menampilkan Material 3 `ModalBottomSheet` saat dijalankan di Android/Windows/Web, dengan API controller yang identik dan typesafe.

### Level Hard
Implementasikan sebuah Custom Multi-Child Layout RenderObject (`RenderHingeAwareLayout`) yang secara manual mengatur layout dua child RenderBox di sisi kiri dan kanan engsel foldable tanpa menggunakan bawaan `Row` atau `Column`. RenderObject harus mengukur ukuran display feature secara langsung via `BoxConstraints` dan memposisikan kedua children tersebut menggunakan kalkulasi manual `parentData.offset`.

---

## 14. Challenge

### Studi Kasus: Financial Command Terminal Multi-Window
Sebuah institusi perbankan investasi meminta Anda membangun *Cross-Platform Market Terminal* di Flutter yang berjalan di desktop (dengan kemampuan multi-window native: chart dapat dilepas (*undocked*) ke window terpisah di monitor lain) sekaligus berjalan di mobile dan perangkat lipat (Galaxy Fold) tanpa menulis ulang domain logic atau presentation view layer.

**Kebutuhan Teknis Arsitektural**:
1. Rancang arsitektur sinkronisasi state antara Main Window dan Child Undocked Windows (yang masing-masing memiliki `PlatformDispatcher` dan `FlutterView` berbeda di engine level).
2. Buat mekanisme deteksi posture layar lipat: Jika perangkat dilipat 90 derajat (*tabletop mode*), setengah layar atas otomatis berubah menjadi *Candlestick Graph Panel Canvas*, sedangkan setengah layar bawah menjadi *Order Execution Keypad Console*.
3. Sistem tidak boleh mengalami drop frame di bawah 60 FPS pada monitor 4K saat data WebSocket stream mengalir dengan frekuensi 50 updates per detik.

Tulis dokumen spesifikasi arsitektur teknis lengkap beserta diagram alur state & event, skema isolasi layout boundary, serta pseudocode inti rendering engine-nya.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Pertanyaan)

1. **Jelaskan siklus komunikasi ukuran dan layout constraint antara Parent dan Child RenderObject di Flutter!**
   - *Jawaban*: Parent mengirimkan batasan ukuran berupa `BoxConstraints` ke child (*Constraints go down*). Child menentukan ukurannya sendiri berdasarkan constraints tersebut dan mengembalikan nilainya ke parent (*Sizes go up*). Parent kemudian menetapkan posisi relatif child (`Offset`) di dalam koordinat parent melalui `parentData` (*Parent sets position*).

2. **Kapan sebuah RenderObject secara otomatis menjadi Relayout Boundary?**
   - *Jawaban*: Saat memenuhi salah satu dari empat kriteria: `sizedByParent == true`, `constraints.isTight` (lebar dan tinggi pasti), `!parentUsesSize` (parent tidak membaca ukuran child untuk layout dirinya sendiri), atau RenderObject tersebut tidak memiliki parent (`RenderView`).

3. **Mengapa pemanggilan `MediaQuery.of(context)` secara general dianggap sebagai anti-pattern performa pada layar berukuran besar/desktop?**
   - *Jawaban*: Karena `MediaQuery.of(context)` mendaftarkan widget sebagai dependent dari seluruh properti `MediaQueryData`. Perubahan sekecil apapun (seperti `viewInsets` akibat keyboard virtual muncul atau perubahan cursor inset) akan memaksa widget tersebut merender ulang (*rebuild*) meskipun ukuran spasial layar tidak berubah sama sekali.

4. **Sebutkan tiga jenis modalitas input desktop yang tidak ada secara native pada ekosistem mobile murni!**
   - *Jawaban*:
     1. Kursor mouse hover (deteksi pergerakan pointer tanpa klik).
     2. Event scroll wheel / smooth trackpad pan tanpa drag context.
     3. Tombol sekunder mouse (right-click) untuk pemanggilan context menu.

5. **Apa fungsi utama dari `DisplayFeature` API yang diperkenalkan pada Flutter multi-platform?**
   - *Jawaban*: Menyediakan data geometri fisik terkait anomali layar hardware yang membagi viewport, seperti engsel (*hinge*) fisik pada perangkat dual-screen/foldable, punch hole, atau notch, sehingga aplikasi dapat menata konten tanpa tertutup atau terpotong engsel.

---

### Bagian 2: Intermediate (5 Pertanyaan)

1. **Apa perbedaan teknis mendalam antara `LayoutBuilder` dan `MediaQuery.sizeOf(context)` dalam hal siklus build dan layout?**
   - *Jawaban*: `MediaQuery.sizeOf(context)` dieksekusi saat fase **Build Phase** berdasarkan data global layar yang disuntikkan root window. Sebaliknya, `LayoutBuilder` menunda build callback sub-tree hingga fase **Layout Phase**, di mana ia membaca constraints lokal yang diteruskan langsung dari parent render node-nya. Hal ini memungkinkan komponen responsif terhadap container pembungkusnya, bukan hanya terhadap viewport layar penuh.

2. **Bagaimana cara mencegah memory leak atau micro-jank ketika merender ribuan elemen list dalam tampilan desktop Ultra-Wide?**
   - *Jawaban*: Menggunakan lazy-loading slivers (`ListView.builder` / `SliverList`), memasang `RepaintBoundary` untuk memotong rasterisasi layer tree, membatasi flex layout dengan constraints ketat, dan mengatur `cacheExtent` secara terukur sesuai memory footprint.

3. **Dalam arsitektur navigasi responsif, jelaskan mengapa penggunaan Navigator 1.0 imperative push/pop rentan memicu state loss saat terjadi transisi layout Compact ke Expanded!**
   - *Jawaban*: Navigator 1.0 memperlakukan layar Master dan Detail sebagai rute independen di dalam call stack. Saat layar dilebarkan ke desktop, tampilan detail harus ditampilkan *side-by-side* bersama list. Jika navigasi bertumpu pada stack historis imperatif, me-mount kembali state detail widget ke dalam dual-pane canvas tanpa menghilangkan status stack rute akan menyebabkan duplikasi state atau hilangnya posisi scroll dan lifecycle controller. Solusinya adalah menggunakan declarative router (Navigator 2.0) berbasis model state terpadu.

4. **Bagaimana Flutter engine menangani text scaling dan density ketika aplikasi dipindahkan antar layar (misalnya dari laptop 1080p ke monitor eksternal 4K High-DPI)?**
   - *Jawaban*: OS mentransmisikan perubahan rasio kepadatan piksel via native embedder message ke `PlatformDispatcher.onMetricsChanged`. Flutter engine memperbarui properti `devicePixelRatio` pada window terkait, memicu `didChangeMetrics()` di framework. Framework kemudian menghitung ulang layout units (logical pixels = physical pixels / devicePixelRatio) dan memicu relayout boundary pohon widget secara terisolasi.

5. **Jelaskan peran `FocusableActionDetector` dalam merancang komponen antarmuka yang adaptif secara platform!**
   - *Jawaban*: `FocusableActionDetector` mengombinasikan fungsionalitas `Focus`, `Actions`, `Shortcuts`, dan `MouseRegion` ke dalam satu wrapper internal. Ini memungkinkan satu komponen menangani: (1) navigasi fokus via tombol Tab, (2) keyboard shortcuts (Enter/Space), dan (3) mouse cursor / hover state secara deklaratif tanpa boilerplate listener manual yang terpisah-pisah.

---

### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan Kompleks)

1. **Skenario Kasus Profiling Performa:**
   Sebuah aplikasi data-entry di-deploy ke browser Desktop dan tablet enterprise. Saat pengguna mengetik di `TextFormField` pada bagian bawah layar, CPU profile menunjukkan lonjakan 90% utilisasi pada UI Thread selama beberapa frame, memicu UI freezing. Hasil tracing Timeline menunjukkan event `markNeedsLayout` dipanggil hingga ke level root widget. Apa akar penyebab arsitekturalnya dan bagaimana perbaikan permanennya?
   - *Jawaban*: Akar penyebabnya adalah penggunaan `MediaQuery.of(context)` (atau membaca `viewInsets` secara non-isolated) di level root/scaffold utama aplikasi. Saat keyboard virtual atau IME input aktif, `viewInsets.bottom` berubah secara cepat per frame animasi keyboard. Karena root widget mendengarkan seluruh perubahan `MediaQuery`, seluruh hierarki widget dari puncak tree menandai layout dirinya *dirty*. Solusinya:
     1. Ubah konsumsi dimensi menjadi `MediaQuery.sizeOf(context)` pada layout scaffolding.
     2. Letakkan konsumsi `MediaQuery.viewInsetsOf(context)` hanya pada komponen textfield atau container formulir lokal.
     3. Pastikan scaffold memiliki flag `resizeToAvoidBottomInset: false` jika layout desktop ditargetkan, atau bungkus sub-view input formulir di dalam container dengan batasan layout kaku (*tight constraints*) yang berfungsi sebagai relayout boundary.

2. **Skenario Desain Dual-Screen / Foldable Failure:**
   Sebuah retail company menggunakan Galaxy Z Fold 5 untuk kasir point-of-sale. Ketika perangkat berada pada posisi unfolded (layar tablet penuh), aplikasi berjalan lancar dengan arsitektur 2-pane. Namun saat dilipat setengah (angle 90° - tabletop posture), tampilan detail transaksi terpotong secara visual tepat di garis engsel, dan touch target tombol "Proses Pembayaran" menjadi tidak responsif. Rancang solusi arsitekturnya!
   - *Jawaban*:
     1. Listen terhadap properti `displayFeatures` via `MediaQueryData.displayFeatures` pada layout tree.
     2. Validasi apakah salah satu display feature bertipe `DisplayFeatureType.hinge` atau `DisplayFeatureType.fold` dengan status `DisplayFeatureState.postureHalfOpened`.
     3. Ekstrak bounding box dari feature tersebut (`feature.bounds`).
     4. Terapkan arsitektur layout adaptif vertikal khusus posture setengah terbuka: Gunakan komponen pemisah struktural (misal: layout flex vertikal) dengan pembagian:
        - Canvas Atas: Mengisi constraint dari $Y = 0$ hingga $Y = feature.bounds.top$ (untuk tampilan item transaksi non-interaktif).
        - Canvas Tengah: SizedBox dengan tinggi $feature.bounds.height$ (area mati engsel yang di-skip dari layout tree).
        - Canvas Bawah: Mengisi constraint dari $Y = feature.bounds.bottom$ hingga batas bawah layar, mengalokasikan ruang interaksi penuh untuk Numeric Keypad dan Tombol Pembayaran. Tindakan ini mencegah penempatan elemen UI di area engsel dan memulihkan seluruh touch target secara presisi.

3. **Skenario Desktop Window Resizing Glitch:**
   Pada Flutter Desktop (macOS/Windows), pengguna dapat melakukan arbitrary window resize secara cepat dengan menarik sudut window. Laporan QA menunjukkan bahwa saat window di-resize secara agresif, terjadi flicker hitam (rendering artifact) dan crash fatal: `Assertion failed: !constraints.isNormalized`. Apa yang terjadi di balik layer engine C++ dan Dart layout phase, serta bagaimana mitigasinya?
   - *Jawaban*:
     - *Penyebab*: Flicker hitam dan assertion failure terjadi karena adanya *race condition* desinkronisasi antara native desktop window message loop OS (yang me-resize native window surface/DirectX/Metal swapchain) dengan asynchronous paint/raster cycle di engine Flutter. Ketika window dikecilkan secara sangat cepat ke ukuran mendekati 0 atau di luar ambang batas min-width/min-height, window manager OS mengirimkan event ukuran baru yang bernilai negatif atau zero sebelum frame layout sebelumnya selesai digambar, menghasilkan `BoxConstraints` tidak valid (`minWidth > maxWidth` atau `minHeight > maxHeight`).
     - *Mitigasi*:
       1. Tetapkan hard minimum window size di native level melalui C++ desktop embedder window configuration (`SetMinSize` pada Windows Win32 API / `minSize` pada `NSWindow` macOS) sehingga window OS secara fisik tidak bisa di-resize di bawah batas aman layout minimum Flutter (misal: minimum 360x480).
       2. Bungkus root navigation scaffolding dengan widget layout defensif:
          ```dart
          LayoutBuilder(
            builder: (context, constraints) {
              if (constraints.maxWidth <= 0 || constraints.maxHeight <= 0) {
                return const SizedBox.shrink(); // Hindari crash normalisasi pipeline
              }
              return SafeLayoutContainer(constraints: constraints);
            },
          )
          ```
       3. Terapkan throttle/debounce ringan pada level state management jika window resize memicu kalkulasi ulang business logic matrix data yang mahal.

---

## 16. Summary

- **Fondasi Engine**: Arsitektur multi-platform di Flutter bertumpu pada protokol layout satu lintasan (*One-Pass $O(N)$ Layout Protocol*). Pemahaman mendalam atas pembentukan *Relayout Boundaries* sangat krusial untuk mencegah degradasi performa pada layar beresolusi tinggi dan desktop environment.
- **Dua Pilar yang Berbeda**: *Responsiveness* berfokus pada variasi geometris viewport spasial, sedangkan *Adaptivity* berfokus pada kapabilitas ekosistem native, input device primitives, dan platform visual idioms.
- **Pola Produksi Modern**: Hindari pemanggilan global `MediaQuery.of(context)` yang rakus sumber daya. Gunakan granular selector API (`MediaQuery.sizeOf`, `viewInsetsOf`), abstraksikan ukuran fisik ke dalam semantic window tokens (`Compact`, `Medium`, `Expanded`), dan isolasi layout dinamis dengan `LayoutBuilder` pada subtree terisolasi.
- **Next-Gen Hardware Readiness**: Dukungan perangkat modern menuntut arsitektur yang sadar akan engsel perangkat lipat (`DisplayFeature`) dan integrasi input desktop tingkat lanjut (`FocusableActionDetector`, hover tracking, cursor handling, dan platform-aware navigation paradigms).