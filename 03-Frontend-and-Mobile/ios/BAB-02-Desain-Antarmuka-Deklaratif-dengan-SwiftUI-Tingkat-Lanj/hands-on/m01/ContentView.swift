import SwiftUI

// MARK: - 1. Cache Storage Structure
public struct FlowLayoutCacheData: Sendable {
    var lineAllocations: [[LayoutSubview]] = []
    var lineHeights: [CGFloat] = []
    var totalComputedHeight: CGFloat = 0.0
    var maxWidthCached: CGFloat = 0.0
}

// MARK: - 2. Custom Layout Implementation
public struct AdaptiveFlowLayout: Layout {
    public struct AlignmentConfiguration: Sendable {
        public enum HorizontalAlignment: Sendable {
            case leading, center, trailing
        }
        public var horizontal: HorizontalAlignment
        public var horizontalSpacing: CGFloat
        public var verticalSpacing: CGFloat

        public init(horizontal: HorizontalAlignment = .leading, horizontalSpacing: CGFloat = 8, verticalSpacing: CGFloat = 8) {
            self.horizontal = horizontal
            self.horizontalSpacing = horizontalSpacing
            self.verticalSpacing = verticalSpacing
        }
    }

    private let config: AlignmentConfiguration

    public init(config: AlignmentConfiguration = .init()) {
        self.config = config
    }

    public func makeCache(subviews: Subviews) -> FlowLayoutCacheData {
        FlowLayoutCacheData()
    }

    public func updateCache(_ cache: inout FlowLayoutCacheData, subviews: Subviews) {
        // Cache akan diinvalidation otomatis saat subview collections berubah
        cache.lineAllocations.removeAll(keepingCapacity: true)
        cache.lineHeights.removeAll(keepingCapacity: true)
        cache.totalComputedHeight = 0
        cache.maxWidthCached = 0
    }

    public func sizeThatFits(
        proposal: ProposedViewSize,
        subviews: Subviews,
        cache: inout FlowLayoutCacheData
    ) -> CGSize {
        let containerWidth = proposal.width ?? .infinity
        computeRows(proposalWidth: containerWidth, subviews: subviews, cache: &cache)
        return CGSize(width: containerWidth.isInfinite ? cache.maxWidthCached : containerWidth, height: cache.totalComputedHeight)
    }

    public func placeSubviews(
        in bounds: CGRect,
        proposal: ProposedViewSize,
        subviews: Subviews,
        cache: inout FlowLayoutCacheData
    ) {
        computeRows(proposalWidth: bounds.width, subviews: subviews, cache: &cache)

        var currentY: CGFloat = bounds.minY

        for (rowIndex, rowSubviews) in cache.lineAllocations.enumerated() {
            let rowHeight = cache.lineHeights[rowIndex]
            let totalRowItemsWidth = rowSubviews.reduce(0.0) { sum, view in
                sum + view.sizeThatFits(.unspecified).width
            } + CGFloat(max(0, rowSubviews.count - 1)) * config.horizontalSpacing

            var currentX: CGFloat = bounds.minX

            switch config.horizontal {
            case .leading:
                currentX = bounds.minX
            case .center:
                currentX = bounds.minX + max(0, (bounds.width - totalRowItemsWidth) / 2)
            case .trailing:
                currentX = bounds.maxX - totalRowItemsWidth
            }

            for subview in rowSubviews {
                let itemSize = subview.sizeThatFits(.unspecified)
                let yOffset = currentY + (rowHeight - itemSize.height) / 2 // Align vertically centered within the row

                subview.place(
                    at: CGPoint(x: currentX, y: yOffset),
                    proposal: ProposedViewSize(itemSize)
                )

                currentX += itemSize.width + config.horizontalSpacing
            }

            currentY += rowHeight + config.verticalSpacing
        }
    }

    // MARK: - Core Allocation Algorithm
    private func computeRows(proposalWidth: CGFloat, subviews: Subviews, cache: inout FlowLayoutCacheData) {
        guard !subviews.isEmpty else {
            cache.totalComputedHeight = 0
            return
        }

        cache.lineAllocations.removeAll(keepingCapacity: true)
        cache.lineHeights.removeAll(keepingCapacity: true)

        var currentRow: [LayoutSubview] = []
        var currentLineWidth: CGFloat = 0.0
        var currentLineMaxHeight: CGFloat = 0.0
        var recordedMaxWidth: CGFloat = 0.0

        for subview in subviews {
            let itemSize = subview.sizeThatFits(.unspecified)
            
            // Check overflow
            if !currentRow.isEmpty && (currentLineWidth + config.horizontalSpacing + itemSize.width) > proposalWidth {
                cache.lineAllocations.append(currentRow)
                cache.lineHeights.append(currentLineMaxHeight)
                recordedMaxWidth = max(recordedMaxWidth, currentLineWidth)

                // Reset untuk baris berikutnya
                currentRow = [subview]
                currentLineWidth = itemSize.width
                currentLineMaxHeight = itemSize.height
            } else {
                currentRow.append(subview)
                currentLineWidth += (currentRow.count == 1 ? 0 : config.horizontalSpacing) + itemSize.width
                currentLineMaxHeight = max(currentLineMaxHeight, itemSize.height)
            }
        }

        if !currentRow.isEmpty {
            cache.lineAllocations.append(currentRow)
            cache.lineHeights.append(currentLineMaxHeight)
            recordedMaxWidth = max(recordedMaxWidth, currentLineWidth)
        }

        cache.maxWidthCached = recordedMaxWidth
        let totalSpacing = CGFloat(max(0, cache.lineAllocations.count - 1)) * config.verticalSpacing
        cache.totalComputedHeight = cache.lineHeights.reduce(0, +) + totalSpacing
    }
}
