# Kurikulum Teknis Enterprise: Flutter Multi-Platform Architecture

---

## SEKSI 01 — IDENTITAS MODUL

* **Domain Kategori:** `03-Frontend-and-Mobile`
* **Kurikulum:** Flutter Advanced Enterprise Engineering
* **Kode Modul:** `FLT-ARCH-0301`
* **Bab:** 03 — Multi-Platform Architecture & System Design
* **Modul:** 01 — Multi-Platform Adaptive & Responsive Architecture
* **Tingkat Kesulitan:** Advanced / Staff Engineer Level
* **Prasyarat:** Pemahaman mendalam tentang RenderObject pipeline Flutter, InheritedWidget mechanics, Dart sound null-safety, serta dasar-dasar platform channels.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1. **Membedakan Paradigma Responsif vs Adaptif:** Mengartikulasikan perbedaan mendasar antara transformasi layout berbasis dimensi geometris (*responsiveness*) dan penyesuaian fungsional, interaksional, serta heuristik sistem operasi (*adaptiveness*).
2. **Menguasai Render Tree Layout Constraints:** Menganalisis bagaimana `BoxConstraints` mengalir ke bawah (*downward*) dan dimensi geometris mengalir ke atas (*upward*) dalam multi-platform engine, serta mencegah layout thrashing.
3. **Membangun Dynamic Device Class Breakpoint Engine:** Mengimplementasikan mesin breakpoints deterministik yang terisolasi dari UI layer dan mendukung *hot-reloading* serta penyesuaian dinamis (multi-windowing, foldables, display density shifts).
4. **Menerapkan Abstraksi Input Modality:** Membangun antarmuka pengguna yang secara mulus menangani transisi antara Pointer events (Mouse, Trackpad), Touch gestural events, dan Hardware Keyboards tanpa kebocoran state logic.
5. **Mendesain Canonical Multi-Platform Layouts:** Mengimplementasikan pola arsitektur layout enterprise seperti List-Detail, Supporting Pane, dan Feed-Split View yang stabil di platform Web, Desktop (macOS, Windows, Linux), dan Mobile (Android, iOS).
6. **Mencegah Anti-Pattern & Performance Degeneracy:** Menghindari penggunaan `MediaQuery` yang memicu rebuild subtree yang tidak perlu (*broad-brush rebuilds*), race conditions pada inisialisasi context, serta kegagalan rendering pada foldable devices.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### 1. Dualitas Responsif vs Adaptif
Mental model yang keliru menganggap bahwa membuat aplikasi multi-platform hanyalah perihal *resizing UI* agar muat di layar besar. 

```
                                  MULTI-PLATFORM UI
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 ▼                                               ▼
         RESPONSIVE ENGINE                                ADAPTIVE ENGINE
     (Spatial & Geometric)                            (Behavioral & Systemic)
                 │                                               │
   • Screen real estate (Width/Height)             • Input Modality (Touch vs Hover/Click)
   • Breakpoints (Compact, Medium, Expanded)       • Platform Conventions (Cupertino vs Material)
   • Flexible/Fluid Typography                     • File System & Window Management
   • Multi-Pane Structural Morphing                • Context Menus, Right-Click, Keystrokes
```

* **Responsif:** Menyelesaikan masalah **ruang (Space)**. Bagaimana elemen UI mengatur posisinya sendiri ketika ukuran viewport bertransformasi secara fluid (misalnya: mengubah 1 kolom vertikal menjadi 3 kolom grid).
* **Adaptif:** Menyelesaikan masalah **konteks (Context)**. Bagaimana sistem berinteraksi dengan pengguna berdasarkan kapabilitas lingkungan perangkat (misalnya: scroll-wheel physics vs finger-fling, tooltip on hover vs long-press bottom sheet, hardware back-button vs swipe-to-pop).

### 2. Aturan Emas Constraints Flutter
> **"Constraints go down. Sizes go up. Parent sets position."**

Dalam perancangan multi-platform, aturan ini menjadi absolut. Viewport Desktop OS memberikan parent constraint berupa *loose constraints* (misal: `minWidth: 0, maxWidth: 1920`), sedangkan perangkat Mobile sering kali memberikan *tight constraints* (misal: `minWidth: 390, maxWidth: 390`). Menulis layout multi-platform tanpa memahami propagation constraint akan langsung berujung pada bug fatal: `RenderFlex overflowed` atau `A RenderFlex with unbounded height`.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Arsitektur layout adaptif-responsif enterprise harus memisahkan penentuan form-factor dari rendering layer menggunakan token design dan unidirectional data-flow:

```
+-------------------------------------------------------------------------------+
|                             PLATFORM / HARDWARE LAYER                         |
|  [Display Density (DPI)]   [Raw Pixels (W x H)]   [Pointer / Stylus / Touch]  |
+-------------------------------------------------------------------------------+
                                        │
                                        ▼ (Window Metrics Update)
+-------------------------------------------------------------------------------+
|                       FLUTTER ENGINE EMBEDDER (C++)                           |
|  - PlatformDispatcher.onMetricsChanged                                        |
|  - ViewConfiguration (Physical size to Logical Pixel conversion)              |
+-------------------------------------------------------------------------------+
                                        │
                                        ▼
+-------------------------------------------------------------------------------+
|                         DESIGN SYSTEM INGRESS LAYER                           |
|  +-------------------------------------------------------------------------+  |
|  | WindowSizeClassResolver (Material 3 / Custom Breakpoint System)         |  |
|  | - Compact:   Width < 600dp   (Mobile Portrait)                          |  |
|  | - Medium:    600dp <= W < 840dp (Foldable unfolded, Tablet Portrait)   |  |
|  | - Expanded:  840dp <= W < 1200dp (Tablet Landscape, Small Desktop)      |  |
|  | - Large:     1200dp <= W < 1600dp (Desktop Monitor)                     |  |
|  | - ExtraLarge: Width >= 1600dp (Ultra-wide Desktop / 4K)                 |  |
|  +-------------------------------------------------------------------------+  |
+-------------------------------------------------------------------------------+
                                        │
                                        ▼
+-------------------------------------------------------------------------------+
|                   ADAPTIVE CAPABILITY PROVIDER (Inherited)                    |
|  - WindowClassToken                                                           |
|  - InputMode (Touch, Cursor, Stylus, Gamepad)                                 |
|  - PlatformFeatures (Fold State, Physical Hinge Sensor bounds)                |
+-------------------------------------------------------------------------------+
                                        │
             ┌──────────────────────────┴──────────────────────────┐
             ▼                                                     ▼
+----------------------------------------+ +------------------------------------+
|       STRUCTURAL ADAPTER ENGINE        | |       SURFACE ADAPTER ENGINE       |
|  (Pola Makro Tata Letak)               | |  (Pola Mikro Interaksi Komponen)   |
|                                        | |                                    |
|  - Breakpoint < Compact:               | |  - Touch: 48dp target, no tooltip  |
|      Scaffold (BottomNavigationBar)    | |  - Desktop: 32dp dense target,     |
|      + Single Pane Navigation Stack    | |      hover states, custom cursors  |
|  - Breakpoint >= Expanded:             | |  - macOS: ContextMenu Cupertino    |
|      Scaffold (NavigationRail / Drawer)| |  - Windows: Fluent ContextMenu     |
|      + Multi-Pane (List + Detail Pane) | |  - Web: URL-hash synced navigation |
+----------------------------------------+ +------------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Perbedaan Mekanisme: `MediaQuery` vs `LayoutBuilder`

| Parameter | `MediaQuery.of(context)` / `MediaQuery.sizeOf(context)` | `LayoutBuilder` |
| :--- | :--- | :--- |
| **Sumber Data** | `InheritedWidget` yang merefleksikan seluruh *window* (`FlutterView`). | Parent `RenderObject` constraints selama fasa layout. |
| **Waktu Evaluasi** | Fasa Build widget tree (`Element.build()`). | Fasa Layout render tree (`RenderObject.layout()`). |
| **Cakupan Pengukuran** | Global (Layar/Jendela aplikasi secara keseluruhan). | Lokal (Berapa luas area yang dialokasikan parent untuk widget ini). |
| **Sensitivitas Rebuild** | Jika menggunakan `MediaQuery.of`, widget rebuild pada *setiap* perubahan keyboard, padding inset, orientation. | Hanya rebuild jika parent constraints berubah melewati batas logika `LayoutBuilder`. |
| **Target Penggunaan** | Keputusan rute makro (misal: Apakah Scaffold menampilkan Navigation Rail atau Bottom Nav). | Komponen modular independen (misal: Apakah card item menampilkan layout horizontal atau vertikal). |

### 2. Mekanisme Internal Layout Constraints Flutter
Mekanisme passing constraints terjadi pada `RenderBox.layout()`:

```dart
void layout(Constraints constraints, { bool parentUsesSize = false })
```

* Jika `parentUsesSize = false`, parent tidak peduli berapa size final dari child. Perubahan ukuran child tidak memicu parent untuk relayout (Optimasi *Relayout Boundary*).
* Jika `parentUsesSize = true`, parent bergantung pada hasil ukuran child. Child menandai parent sebagai dirty jika ukurannya berubah.
* `LayoutBuilder` bekerja dengan cara menyuntikkan `RenderConstrainedLayoutBuilder` ke dalam render tree. Callback builder-nya dipanggil **selama fasa layout**, bukan fasa build biasa. Menggunakan `setState` atau memodifikasi tree lain di dalam callback `LayoutBuilder` dapat memicu crash: `"setState() or markNeedsBuild() called during layout"`.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### 1. Klasifikasi Form-Factor Standar Industri
Industri perangkat modern menuntut standarisasi ukuran minimum, terinspirasi oleh *Material 3 Adaptive Breakpoints*:
* **Compact (< 600 dp):** Portrait smartphone. Ruang layar horizontal sangat terbatas. Komposisi data linear (1 dimensi).
* **Medium (600 - 839 dp):** Tablet portrait, smartphone lipat unfolded, atau window desktop berukuran kecil.
* **Expanded (840 - 1199 dp):** Tablet landscape, desktop standar. Dapat menampung panel navigasi persisten dan konten 2 kolom.
* **Large (1200 - 1599 dp):** Desktop resolusi menengah/tinggi. Mampu menampung 3 kolom data (Navigasi + List Master + Detail View).
* **Extra Large (≥ 1600 dp):** Ultra-wide display. Perlu membatasi lebar konten maksimal (*max-content-width constrain*) agar readability mata pengguna tidak menurun drastis akibat scanning teks terlalu lebar.

### 2. Input Modality Engine
Aplikasi multi-platform tidak boleh mengasumsikan input method dari ukuran layar:
* Banyak laptop touch-screen berukuran 14 inci (> 1200 dp) memiliki input sentuh sekaligus mouse trackpad.
* Banyak tablet menggunakan external keyboard dan Apple Pencil / mouse pointer.
* **Solusi Arsitektural:** Tangani *input modality* sebagai stream status runtime independen menggunakan `Listener`, `MouseRegion`, dan `FocusTraversalGroup`, bukan branching statis berdasarkan `Platform.isAndroid` atau `Platform.isMacOS`.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut implementasi fondasi breakpoint engine terpusat tanpa layout thrashing:

```dart
// lib/core/responsive/breakpoint_tokens.dart
import 'package:flutter/material.dart';

enum DeviceWindowSizeClass {
  compact,
  medium,
  expanded,
  large,
  extraLarge;

  static DeviceWindowSizeClass fromWidth(double width) {
    if (width < 600.0) return DeviceWindowSizeClass.compact;
    if (width < 840.0) return DeviceWindowSizeClass.medium;
    if (width < 1200.0) return DeviceWindowSizeClass.expanded;
    if (width < 1600.0) return DeviceWindowSizeClass.large;
    return DeviceWindowSizeClass.extraLarge;
  }
}

class WindowSizeScope extends InheritedWidget {
  final DeviceWindowSizeClass sizeClass;
  final Size rawSize;

  const WindowSizeScope({
    super.key,
    required this.sizeClass,
    required this.rawSize,
    required super.child,
  });

  static DeviceWindowSizeClass of(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<WindowSizeScope>();
    assert(scope != null, 'No WindowSizeScope found in the current widget context.');
    return scope!.sizeClass;
  }

  static DeviceWindowSizeClass? maybeOf(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<WindowSizeScope>();
    return scope?.sizeClass;
  }

  @override
  bool updateShouldNotify(covariant WindowSizeScope oldWidget) {
    return sizeClass != oldWidget.sizeClass || rawSize != oldWidget.rawSize;
  }
}
```

```dart
// lib/core/responsive/adaptive_root_builder.dart
import 'package:flutter/material.dart';
import 'breakpoint_tokens.dart';

class AdaptiveRootBuilder extends StatelessWidget {
  final Widget Function(BuildContext context, DeviceWindowSizeClass sizeClass) builder;

  const AdaptiveRootBuilder({
    super.key,
    required this.builder,
  });

  @override
  Widget build(BuildContext context) {
    // Menggunakan MediaQuery.sizeOf(context) untuk efisiensi rebuild spesifik size
    final Size size = MediaQuery.sizeOf(context);
    final DeviceWindowSizeClass currentClass = DeviceWindowSizeClass.fromWidth(size.width);

    return WindowSizeScope(
      sizeClass: currentClass,
      rawSize: size,
      child: Builder(
        builder: (innerContext) => builder(innerContext, currentClass),
      ),
    );
  }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis File `breakpoint_tokens.dart`
* **Baris 4–10:** `enum DeviceWindowSizeClass`: Mendefinisikan kontrak domain yang stabil untuk seluruh aplikasi. Menghilangkan ketergantungan widget daun (*leaf widget*) pada angka mentah pixel (`600`, `1200`).
* **Baris 12–18:** `static DeviceWindowSizeClass fromWidth(double width)`: Algoritma deterministik satu arah (*pure function*). Sangat mudah diuji (*unit-testable*) tanpa perlu me-render widget Flutter.
* **Baris 21–30:** `class WindowSizeScope extends InheritedWidget`: Menyediakan penyebaran state global dengan performa $O(1)$ tree lookups, menghindari propagasi manual melalui constructor parameters (*prop drilling*).
* **Baris 39–41:** `updateShouldNotify`: Menghentikan gelombang rebuild jika dimensi pixel berubah sedikit namun masih dalam satu kategori `sizeClass` yang sama.

### Analisis File `adaptive_root_builder.dart`
* **Baris 15:** `MediaQuery.sizeOf(context)`: **Krusial untuk performa!** Sejak Flutter 3.10+, API granular ini mencegah rebuild seluruh aplikasi saat atribut non-dimensi (seperti `MediaQueryData.viewInsets` saat keyboard virtual muncul) mengalami mutasi.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Enterprise: Global Asset Portfolio & Trading Terminal
* **Tantangan:** Perusahaan perbankan digital membangun aplikasi portofolio multi-platform ("Apex Asset").
* **Target Platform:** iOS, Android (termasuk Galaxy Z Fold), Web (Chrome/Safari), macOS, dan Windows 11.
* **Kebutuhan Bisnis:**
  * Di Mobile Portrait (Compact): Tampilan hanya boleh berupa Master List of Assets. Mengetuk aset memicu navigasi route baru ke halaman Detail.
  * Di Foldable Unfolded & Tablet Portrait (Medium): Layout berubah menjadi Split List dengan summary compact di bawahnya.
  * Di Desktop/Web (Expanded/Large): Mengadopsi **Canonical List-Detail Architecture**. List Aset di sebelah kiri (350dp), Chart & Trading Book di panel tengah, dan Real-time Order Action di panel kanan (Supporting Pane).
  * **Interaksi:** Hover pada baris data menampilkan aksi cepat (Desktop). Right-click memunculkan native context menu. Mobile mengandalkan swipe action dan tap sheet.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi arsitektur multi-platform production-grade yang menangani List-Detail, adaptasi input modal, dan hover behavior secara holistik.

```dart
// lib/features/portfolio/presentation/widgets/adaptive_portfolio_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

// --- DOMAIN ENUMS & ENTITIES ---
class AssetEntity {
  final String id;
  final String symbol;
  final String name;
  final double price;
  final double changePercentage;

  const AssetEntity({
    required this.id,
    required this.symbol,
    required this.name,
    required this.price,
    required this.changePercentage,
  });
}

// --- REPOSITORY MOCK ---
final List<AssetEntity> kSampleAssets = List.generate(
  50,
  (i) => AssetEntity(
    id: 'asset_$i',
    symbol: 'SYM$i',
    name: 'Enterprise Asset Token $i',
    price: 100.0 + (i * 12.5),
    changePercentage: (i % 2 == 0 ? 1 : -1) * (i * 0.42),
  ),
);

// --- MAIN ADAPTIVE SHELL ---
class AdaptivePortfolioScreen extends StatefulWidget {
  const AdaptivePortfolioScreen({super.key});

  @override
  State<AdaptivePortfolioScreen> createState() => _AdaptivePortfolioScreenState();
}

class _AdaptivePortfolioScreenState extends State<AdaptivePortfolioScreen> {
  AssetEntity? _selectedAsset;

  @override
  void initState() {
    super.initState();
    // Default seleksi untuk skenario layar lebar
    _selectedAsset = kSampleAssets.first;
  }

  void _onAssetSelected(AssetEntity asset, bool isCompact) {
    if (isCompact) {
      // Pada Mobile, dorong route navigasi penuh
      Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (context) => AssetDetailMobileScaffold(asset: asset),
        ),
      );
    } else {
      // Pada Desktop/Tablet, ubah in-place state untuk detail pane
      setState(() {
        _selectedAsset = asset;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final double width = constraints.maxWidth;
        final bool isCompact = width < 720.0;
        final bool isTriplePane = width >= 1200.0;

        return Scaffold(
          appBar: AppBar(
            title: const Text('Apex Portfolio Engine'),
            elevation: 0,
            backgroundColor: Theme.of(context).colorScheme.inversePrimary,
          ),
          body: Row(
            children: [
              // PANEL 1: LIST / MASTER VIEW
              SizedBox(
                width: isCompact ? width : (isTriplePane ? 380.0 : 320.0),
                child: AssetMasterList(
                  assets: kSampleAssets,
                  selectedAsset: isCompact ? null : _selectedAsset,
                  onSelect: (asset) => _onAssetSelected(asset, isCompact),
                ),
              ),

              // SEPARATOR JIKA LAYAR LEBAR
              if (!isCompact)
                const VerticalDivider(width: 1, thickness: 1, color: Colors.black12),

              // PANEL 2: DETAIL PRIMARY VIEW (Hanya dirender jika bukan layar compact)
              if (!isCompact)
                Expanded(
                  flex: 3,
                  child: _selectedAsset != null
                      ? AssetDetailPane(asset: _selectedAsset!)
                      : const Center(child: Text('Pilih aset untuk melihat performa')),
                ),

              // PANEL 3: SUPPORTING ACTIONS PANE (Hanya di layar Desktop Large)
              if (isTriplePane) ...[
                const VerticalDivider(width: 1, thickness: 1, color: Colors.black12),
                SizedBox(
                  width: 320.0,
                  child: SupportingExecutionPane(asset: _selectedAsset),
                ),
              ],
            ],
          ),
        );
      },
    );
  }
}

// --- WIDGET: MASTER LIST DENGAN VIRTUALISASI MEMORI ---
class AssetMasterList extends StatelessWidget {
  final List<AssetEntity> assets;
  final AssetEntity? selectedAsset;
  final ValueChanged<AssetEntity> onSelect;

  const AssetMasterList({
    super.key,
    required this.assets,
    required this.selectedAsset,
    required this.onSelect,
  });

  @override
  Widget build(BuildContext context) {
    return ListView.builder(
      itemCount: assets.length,
      itemBuilder: (context, index) {
        final asset = assets[index];
        final bool isSelected = selectedAsset?.id == asset.id;

        return AssetRowItem(
          asset: asset,
          isSelected: isSelected,
          onTap: () => onSelect(asset),
        );
      },
    );
  }
}

// --- WIDGET: ASSET ROW DENGAN HOVER & CONTEXT-MENU NATIVE/DESKTOP CAPABILITIES ---
class AssetRowItem extends StatefulWidget {
  final AssetEntity asset;
  final bool isSelected;
  final VoidCallback onTap;

  const AssetRowItem({
    super.key,
    required this.asset,
    required this.isSelected,
    required this.onTap,
  });

  @override
  State<AssetRowItem> createState() => _AssetRowItemState();
}

class _AssetRowItemState extends State<AssetRowItem> {
  bool _isHovered = false;

  void _showContextMenu(BuildContext context, Offset globalPosition) {
    final RenderBox overlay = Overlay.of(context).context.findRenderObject()! as RenderBox;

    showMenu<String>(
      context: context,
      position: RelativeRect.fromRect(
        globalPosition & const Size(40, 40),
        Offset.zero & overlay.size,
      ),
      items: [
        PopupMenuItem(
          value: 'copy',
          child: const Text('Salin Simbol Asset'),
          onTap: () {
            Clipboard.setData(ClipboardData(text: widget.asset.symbol));
          },
        ),
        const PopupMenuItem(
          value: 'watchlist',
          child: Text('Tambahkan ke Watchlist'),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isNegative = widget.asset.changePercentage < 0;

    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _isHovered = true),
      onExit: (_) => setState(() => _isHovered = false),
      child: GestureDetector(
        onSecondaryTapUp: (details) => _showContextMenu(context, details.globalPosition),
        onTap: widget.onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 150),
          curve: Curves.easeInOut,
          padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 12.0),
          decoration: BoxDecoration(
            color: widget.isSelected
                ? theme.colorScheme.primaryContainer.withAlpha(128)
                : (_isHovered ? theme.colorScheme.surfaceContainerHighest.withAlpha(80) : Colors.transparent),
            border: Border(
              bottom: BorderSide(color: theme.dividerColor.withAlpha(40)),
            ),
          ),
          child: Row(
            children: [
              CircleAvatar(
                radius: 18,
                backgroundColor: theme.colorScheme.secondaryContainer,
                child: Text(
                  widget.asset.symbol.substring(0, 2),
                  style: theme.textTheme.labelMedium?.copyWith(fontWeight: FontWeight.bold),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      widget.asset.symbol,
                      style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
                    ),
                    Text(
                      widget.asset.name,
                      style: theme.textTheme.bodySmall?.copyWith(color: theme.hintColor),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    '\$${widget.asset.price.toStringAsFixed(2)}',
                    style: theme.textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.bold),
                  ),
                  Text(
                    '${isNegative ? "" : "+"}${widget.asset.changePercentage.toStringAsFixed(2)}%',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: isNegative ? Colors.redAccent : Colors.green,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// --- WIDGET: DETAIL PRIMARY VIEW ---
class AssetDetailPane extends StatelessWidget {
  final AssetEntity asset;

  const AssetDetailPane({super.key, required this.asset});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.all(24.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(asset.name, style: theme.textTheme.headlineMedium),
                  Text(asset.symbol, style: theme.textTheme.titleMedium?.copyWith(color: theme.hintColor)),
                ],
              ),
              Text(
                '\$${asset.price.toStringAsFixed(2)}',
                style: theme.textTheme.headlineLarge?.copyWith(fontWeight: FontWeight.bold),
              ),
            ],
          ),
          const SizedBox(height: 24),
          // Chart Simulation Box
          Expanded(
            child: Container(
              width: double.infinity,
              decoration: BoxDecoration(
                color: theme.colorScheme.surfaceContainerHighest.withAlpha(50),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: theme.dividerColor),
              ),
              child: const Center(
                child: Text('Interactive Canvas Vector Engine Placeholder'),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// --- WIDGET: THIRD PANE (EXECUTION / ORDERING PANE) ---
class SupportingExecutionPane extends StatelessWidget {
  final AssetEntity? asset;

  const SupportingExecutionPane({super.key, required this.asset});

  @override
  Widget build(BuildContext context) {
    if (asset == null) return const SizedBox.shrink();

    return Padding(
      padding: const EdgeInsets.all(16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Eksekusi Order', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 16),
          TextFormField(
            decoration: const InputDecoration(
              labelText: 'Volume Transaksi',
              border: OutlineInputBorder(),
            ),
            keyboardType: TextInputType.number,
          ),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: () {},
            style: FilledButton.styleFrom(
              minimumSize: const Size(double.infinity, 48),
            ),
            child: Text('Beli ${asset!.symbol}'),
          ),
        ],
      ),
    );
  }
}

// --- SCAFFOLD KHUSUS MOBILE UNTUK NAVIGASI STANDAR PUSH/POP ---
class AssetDetailMobileScaffold extends StatelessWidget {
  final AssetEntity asset;

  const AssetDetailMobileScaffold({super.key, required this.asset});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(asset.symbol),
      ),
      body: AssetDetailPane(asset: asset),
    );
  }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Pendekatan Arsitektur | Keunggulan (*Pros*) | Kelemahan (*Cons*) | Skenario Penggunaan Optimal |
| :--- | :--- | :--- | :--- |
| **Monolithic Adaptive Scaffolds** (Logika kondisional terpusat dalam 1 widget via `LayoutBuilder`) | Kode ringkas, state internal layar mudah dibagi antar varian tampilan (tidak perlu state store terpisah). | File widget membesar (*bloated*); risiko tight-coupling antara mobile view dan desktop view. | Tampilan sederhana hingga menengah di mana state master dan detail terikat erat. |
| **Separate Platform View Tree** (Membagi file: `screen_mobile.dart`, `screen_desktop.dart`) | Pemisahan tanggung jawab tegas (*Separation of Concerns*); kode tiap form-factor sangat bersih dan mudah dimodifikasi tanpa efek samping. | Duplikasi binding presenter/bloc/controller; overhead sinkronisasi perubahan state antar file. | Aplikasi level Enterprise dengan arsitektur UX yang sangat berbeda radikal antara Desktop dan Mobile. |
| **Pure Micro-Layout Component Driven** (Setiap widget daun memutuskan strukturnya sendiri via `LayoutBuilder`) | Reusabilitas komponen sangat tinggi; komponen dapat diletakkan di container apa pun tanpa peduli ukuran layar. | Layout overhead yang tinggi; Render tree menjadi dalam (*deep tree*); sulit mengatur kohesi ritme ritmis visual halaman global. | Design System Component Library (DS Core UIKit). |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Foldable & Dual-Screen Display Discontinuity
* **Failure Mode:** Saat perangkat lipat (*foldable*) dibuka dari posisi cover screen (compact) ke wide screen (unfolded), sistem memicu runtime configuration change mendadak. Posisi engsel (*hinge*) fisik berada tepat di tengah-tengah konten teks atau tombol kritis.
* **Mitigasi:** Gunakan API `DisplayFeatureSubScreen` atau query langsung:
```dart
final displayFeatures = MediaQuery.displayFeaturesOf(context);
// Identifikasi DisplayFeatureType.hinge atau fold dan tambahkan safe bounds padding.
```

### 2. Desktop Window Sizing Instability (Zero-Width Glitch)
* **Failure Mode:** Pada Windows OS, saat aplikasi dijalankan via *minimized startup* atau digeser ke monitor sekunder, `maxWidth` dan `maxHeight` sesaat bernilai `0.0`. Hal ini memicu exception tak tertangani: `BoxConstraints forces an empty or negative size`.
* **Mitigasi:** Selalu sertakan assertion dan guard-clause:
```dart
if (constraints.maxWidth <= 0 || constraints.maxHeight <= 0) {
  return const SizedBox.shrink();
}
```

### 3. Keyboard Inset Contamination pada Web & Desktop
* **Failure Mode:** `MediaQuery.of(context).viewInsets.bottom` di Desktop OS dapat secara tiba-tiba mengirimkan nilai aneh saat berinteraksi dengan Virtual Keyboard/IME input, menyebabkan layout melompat (*jumping artifacts*).
* **Mitigasi:** Isolasi evaluasi soft-keyboard hanya pada environment target touch atau mobile OS (`defaultTargetPlatform == TargetPlatform.android || defaultTargetPlatform == TargetPlatform.iOS`).

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan Fatal 1: Menggunakan `Platform.isAndroid` / `Platform.isIOS` untuk Layout Responsif
* **Mengapa Bahaya:** `dart:io` Platform checks mengidentifikasi **OS engine**, bukan **ukuran layar/konteks**. Menjalankan aplikasi Android pada tablet 12 inci atau mode desktop Samsung DeX akan menghasilkan UI ponsel berukuran raksasa yang membentang aneh jika dicek via `Platform.isAndroid`.
* **Solusi Benar:** Gunakan `MediaQuery.sizeOf(context)` atau `BoxConstraints` untuk menentukan bentuk UI (layout geometris), bukan platform OS.

### Kesalahan Fatal 2: Broad `MediaQuery.of(context)` Dependency
* **Anti-Pattern:**
```dart
Widget build(BuildContext context) {
  // SALAH: Widget akan rebuild saat MediaQueryData apapun berubah (orientation, insets, brightness, textScale)
  final size = MediaQuery.of(context).size;
  return Container(width: size.width > 600 ? 500 : 300);
}
```
* **Solusi Benar:**
```dart
Widget build(BuildContext context) {
  // BENAR: Rebuild HANYA terjadi saat properti 'size' bermutasi
  final size = MediaQuery.sizeOf(context);
  return Container(width: size.width > 600 ? 500 : 300);
}
```

### Kesalahan Fatal 3: Menggunakan Fixed Height/Width Hardcoded
* **Anti-Pattern:** `Container(width: 375)` (Hardcoded berdasarkan ukuran iPhone 13 canvas Figma).
* **Solusi Benar:** Gunakan `Flexible`, `Expanded`, atau batasi dengan `ConstrainedBox(constraints: BoxConstraints(maxWidth: 375))` agar tidak overflow di device berlayar lebih sempit (misal: iPhone SE 320dp).

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Standardize Target Touch Sizes:**
   * Mobile: Target sentuh interaktif minimum adalah **$48 \times 48\text{ dp}$** (Material Design Spec) atau **$44 \times 44\text{ pt}$** (Apple HIG).
   * Desktop Pointer: Target sentuh dapat dirapatkan (*denser*) menjadi **$32 \times 32\text{ dp}$** atau **$28 \times 28\text{ dp}$** karena akurasi mouse kursor jauh melampaui jari manusia.
2. **Strict Keyboard Navigation Support:**
   * Setiap komponen interaktif di Desktop/Web WAJIB memiliki visual focus indicator (`FocusNode`, `FocusRing`). Tombol `Tab` harus memindahkan fokus secara linier terprediksi via `FocusTraversalGroup`.
3. **Cursor Styling:**
   * Semua area klik Desktop harus membungkus komponen interaktif dengan `MouseRegion(cursor: SystemMouseCursors.click)`.
4. **Content Max-Width Clamping:**
   * Bungkus area teks membaca utama (artikel, deskripsi panjang) dengan batasan lebar:
     `Center(