import SwiftUI

// MARK: - Model Domain
public struct MetricData: Identifiable, Equatable, Sendable {
    public let id: UUID = UUID()
    public let title: String
    public let value: String
    public let changePercentage: Double
    
    public init(title: String, value: String, changePercentage: Double) {
        self.title = title
        self.value = value
        self.changePercentage = changePercentage
    }
}

// MARK: - Custom Flow Layout (Wrapping dynamic grid)
public struct AdaptiveFlowLayout: Layout {
    public var spacing: CGFloat

    public init(spacing: CGFloat = 12.0) {
        self.spacing = spacing
    }

    public struct CacheData {
        var rowOffsets: [CGFloat]
        var boundsSize: CGSize
    }

    public func makeCache(subviews: Subviews) -> CacheData {
        CacheData(rowOffsets: [], boundsSize: .zero)
    }

    public func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout CacheData) -> CGSize {
        let maxWidth = proposal.width ?? .infinity
        var totalHeight: CGFloat = 0
        var currentRowWidth: CGFloat = 0
        var currentRowHeight: CGFloat = 0

        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            if currentRowWidth + size.width > maxWidth {
                // Pindah ke baris baru
                totalHeight += currentRowHeight + spacing
                currentRowWidth = size.width + spacing
                currentRowHeight = size.height
            } else {
                currentRowWidth += size.width + spacing
                currentRowHeight = max(currentRowHeight, size.height)
            }
        }
        totalHeight += currentRowHeight
        let calculatedSize = CGSize(width: maxWidth == .infinity ? currentRowWidth : maxWidth, height: totalHeight)
        cache.boundsSize = calculatedSize
        return calculatedSize
    }

    public func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout CacheData) {
        var currentOrigin = CGPoint(x: bounds.minX, y: bounds.minY)
        var currentRowHeight: CGFloat = 0

        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            if currentOrigin.x + size.width > bounds.maxX {
                // Bungkus baris ke awal baris baru
                currentOrigin.x = bounds.minX
                currentOrigin.y += currentRowHeight + spacing
                currentRowHeight = 0
            }

            subview.place(
                at: currentOrigin,
                anchor: .topLeading,
                proposal: ProposedViewSize(size)
            )

            currentRowHeight = max(currentRowHeight, size.height)
            currentOrigin.x += size.width + spacing
        }
    }
}

// MARK: - Atomic Card Component
public struct MetricCardView: View {
    public let metric: MetricData

    public var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(metric.title)
                .font(.caption)
                .foregroundStyle(.secondary)
                .lineLimit(1)
            
            Text(metric.value)
                .font(.headline.weight(.semibold))
                .lineLimit(1)
                .minimumScaleFactor(0.8)

            HStack(spacing: 2) {
                Image(systemName: metric.changePercentage >= 0 ? "arrow.up.right" : "arrow.down.right")
                Text(String(format: "%.2f%%", abs(metric.changePercentage)))
            }
            .font(.caption2.bold())
            .foregroundStyle(metric.changePercentage >= 0 ? .green : .red)
        }
        .padding(12)
        .frame(minWidth: 140)
        .background(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .fill(Color(uiColor: .secondarySystemBackground))
        )
    }
}

// MARK: - Production Adaptive Container
public struct PortfolioDashboardView: View {
    public let metrics: [MetricData]
    
    public init(metrics: [MetricData]) {
        self.metrics = metrics
    }

    public var body: some View {
        ScrollView(.vertical, showsIndicators: true) {
            VStack(alignment: .leading, spacing: 16) {
                Text("Executive Financial Overview")
                    .font(.title2.bold())
                    .padding(.horizontal)

                // Layout Orchestration via ViewThatFits:
                // Engine mengevaluasi struktur visual terbaik dari urutan teratas ke bawah
                ViewThatFits(in: .horizontal) {
                    // Opsi 1: Multi-column horizontal row jika ruang melimpah (iPad / Landscape)
                    HStack(spacing: 12) {
                        ForEach(metrics) { metric in
                            MetricCardView(metric: metric)
                        }
                    }
                    .padding(.horizontal)

                    // Opsi 2: Dynamic Wrapping Layout jika opsi 1 overflow
                    AdaptiveFlowLayout(spacing: 12) {
                        ForEach(metrics) { metric in
                            MetricCardView(metric: metric)
                        }
                    }
                    .padding(.horizontal)

                    // Opsi 3: Vertical fallback stack jika layar terlampau sempit (iPhone SE)
                    VStack(spacing: 8) {
                        ForEach(metrics) { metric in
                            MetricCardView(metric: metric)
                                .frame(maxWidth: .infinity)
                        }
                    }
                    .padding(.horizontal)
                }
            }
            .padding(.vertical)
        }
    }
}
