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
