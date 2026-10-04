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
