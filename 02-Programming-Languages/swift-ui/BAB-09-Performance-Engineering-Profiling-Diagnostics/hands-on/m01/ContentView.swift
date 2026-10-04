import SwiftUI
import Observation
import OSLog

// MARK: - 1. DOMAIN MODEL DENGAN IDENTITAS STABIL
struct OrderBookEntry: Identifiable, Hashable, Sendable {
    let id: Double // Menggunakan harga unik sebagai stable explicit identity
    let price: Double
    var volume: Double
    let isAsk: Bool
}

// MARK: - 2. ACTOR BUFFERING ENGINE (OFF-MAIN THREAD)
actor OrderBookBufferEngine {
    private var pendingOrders: [Double: OrderBookEntry] = [:]
    
    func ingest(_ order: OrderBookEntry) {
        pendingOrders[order.id] = order
    }
    
    func flush() -> [OrderBookEntry] {
        defer { pendingOrders.removeAll(keepingCapacity: true) }
        return pendingOrders.values.sorted { $0.price > $1.price }
    }
}

// MARK: - 3. INSTRUMENTED VIEW MODEL
@Observable
@MainActor
final class OrderBookViewModel {
    private(set) var activeOrders: [OrderBookEntry] = []
    
    @ObservationIgnored
    private let logger = Logger(subsystem: "com.enterprise.orderbook", category: "Performance")
    @ObservationIgnored
    private let signposter = OSSignposter(subsystem: "com.enterprise.orderbook", category: "ViewRendering")
    @ObservationIgnored
    private let bufferEngine = OrderBookBufferEngine()
    @ObservationIgnored
    private var isStreaming = false
    
    func startReceivingTicks() {
        guard !isStreaming else { return }
        isStreaming = true
        
        // Background ingestion simulator
        Task.detached(priority: .userInitiated) { [bufferEngine = self.bufferEngine] in
            while true {
                try? await Task.sleep(nanoseconds: 5_000_000) // 200 pembaruan per detik (5ms)
                let dummyPrice = Double.random(in: 60000...61000).rounded()
                let entry = OrderBookEntry(
                    id: dummyPrice,
                    price: dummyPrice,
                    volume: Double.random(in: 0.1...5.0),
                    isAsk: Bool.random()
                )
                await bufferEngine.ingest(entry)
            }
        }
        
        // Display Synchronization Loop: Dibatasi pada 60 FPS (16.6ms) 
        // Mengurangi invalidasi AttributeGraph dari 200 Hz menjadi 60 Hz
        Task { @MainActor in
            while isStreaming {
                try? await Task.sleep(nanoseconds: 16_666_667)
                await self.drainBufferToUI()
            }
        }
    }
    
    private func drainBufferToUI() async {
        let state = signposter.beginInterval("FlushAndApplyState")
        let updates = await bufferEngine.flush()
        
        guard !updates.isEmpty else {
            signposter.endInterval("FlushAndApplyState", state)
            return
        }
        
        // Batch Mutation: Meminimalkan diskontinuitas State
        self.activeOrders = updates
        signposter.endInterval("FlushAndApplyState", state)
    }
}

// MARK: - 4. PERFORMANCE-OPTIMIZED VIEW HIERARCHY
struct HighSpeedOrderBookView: View {
    @State private var viewModel = OrderBookViewModel()
    
    var body: some View {
        VStack(spacing: 0) {
            HeaderMetricView()
            
            List {
                // List menggunakan UICollectionView di backend, 
                // efisien untuk cell reuse jika explicit identity konstan.
                ForEach(viewModel.activeOrders, id: \.id) { order in
                    OrderRowView(order: order)
                }
            }
            .listStyle(.plain)
            // Memaksa rendering CoreAnimation layer hardware caching
            .drawingGroup() 
        }
        .task {
            viewModel.startReceivingTicks()
        }
    }
}

struct HeaderMetricView: View {
    var body: some View {
        HStack {
            Text("Price (USD)").font(.caption).bold()
            Spacer()
            Text("Volume").font(.caption).bold()
        }
        .padding(.horizontal)
        .frame(height: 32)
        .background(Color(.secondarySystemBackground))
    }
}

// Subview Equatable murni untuk isolasi total
struct OrderRowView: View, Equatable {
    let order: OrderBookEntry
    
    // Equatable manual untuk memotong perbandingan diff yang tidak relevan
    static func == (lhs: OrderRowView, rhs: OrderRowView) -> Bool {
        lhs.order.id == rhs.order.id &&
        lhs.order.volume == rhs.order.volume
    }
    
    var body: some View {
        HStack {
            Text("\(order.price, specifier: "%.2f")")
                .font(.system(.body, design: .monospaced))
                .foregroundColor(order.isAsk ? .red : .green)
            Spacer()
            Text("\(order.volume, specifier: "%.4f")")
                .font(.system(.body, design: .monospaced))
        }
        .padding(.vertical, 2)
    }
}
