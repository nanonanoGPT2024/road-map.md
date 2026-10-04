import SwiftUI
import Observation

// MARK: - Domain Models
public struct CryptoTick: Identifiable, Hashable, Sendable {
    public let id: UUID
    public let symbol: String
    public let price: Double
    public let timestamp: Date

    public init(symbol: String, price: Double) {
        self.id = UUID()
        self.symbol = symbol
        self.price = price
        self.timestamp = Date()
    }
}

// MARK: - Actor Data Pipeline (Ingestion & Buffering)
public actor MarketDataIngestor {
    private var isStreaming = false
    
    /// Mengonversi callback socket kontinu ke AsyncStream
    public func subscribeToStream(for symbol: String) -> AsyncStream<CryptoTick> {
        AsyncStream { continuation in
            let task = Task {
                var currentPrice = 50_000.0
                while !Task.isCancelled {
                    // Simulasi I/O latency frekuensi tinggi: 10ms - 50ms per paket
                    let deltaMs = UInt64.random(in: 10...50)
                    try? await Task.sleep(nanoseconds: deltaMs * 1_000_000)
                    
                    if Task.isCancelled { break }

                    // Simulasi fluktuasi acak
                    let change = Double.random(in: -25.0...25.0)
                    currentPrice += change
                    
                    let tick = CryptoTick(symbol: symbol, price: currentPrice)
                    
                    // Emisi tick ke consumer pipeline
                    let yieldResult = continuation.yield(tick)
                    if case .terminated = yieldResult {
                        break
                    }
                }
            }
            
            // Clean-up handler saat downstream consumer membatalkan stream
            continuation.onTermination = { @Sendable _ in
                task.cancel()
            }
        }
    }
}

// MARK: - View Model (Throttling & UI Orchestration)
@Observable
@MainActor
public final class MarketTickerViewModel {
    public private(set) var latestTick: CryptoTick?
    public private(set) var priceHistory: [CryptoTick] = []
    public private(set) var isConnected: Bool = false
    
    private let ingestor = MarketDataIngestor()
    private let maxHistoryEntries = 50

    public func startStreaming(for symbol: String) async {
        isConnected = true
        let tickStream = await ingestor.subscribeToStream(for: symbol)
        
        // Target: Render throttled stream tanpa membebani Main Thread
        // Mengumpulkan emisi dan batch update per window
        var lastRenderTime = CFAbsoluteTimeGetCurrent()
        let renderInterval: CFTimeInterval = 0.05 // Batas 20Hz update UI (~50ms)

        do {
            for await tick in tickStream {
                // Cooperative Cancellation Checkpoint
                try Task.checkCancellation()

                let currentTime = CFAbsoluteTimeGetCurrent()
                if currentTime - lastRenderTime >= renderInterval {
                    self.updateUIState(with: tick)
                    lastRenderTime = currentTime
                }
            }
        } catch {
            #if DEBUG
            print("Stream gracefully halted via cancellation.")
            #endif
        }
        
        isConnected = false
    }

    private func updateUIState(with tick: CryptoTick) {
        self.latestTick = tick
        self.priceHistory.append(tick)
        if self.priceHistory.count > maxHistoryEntries {
            self.priceHistory.removeFirst(self.priceHistory.count - maxHistoryEntries)
        }
    }
}

// MARK: - SwiftUI View Layer
public struct MarketTickerView: View {
    @State private var viewModel = MarketTickerViewModel()
    @State private var selectedSymbol: String = "BTC-USDT"
    
    public init() {}

    public var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                // Status Header
                HStack {
                    Circle()
                        .fill(viewModel.isConnected ? Color.green : Color.red)
                        .frame(width: 10, height: 10)
                    Text(viewModel.isConnected ? "LIVE FEED" : "DISCONNECTED")
                        .font(.caption)
                        .bold()
                        .foregroundColor(.secondary)
                    Spacer()
                    Picker("Asset", selection: $selectedSymbol) {
                        Text("BTC-USDT").tag("BTC-USDT")
                        Text("ETH-USDT").tag("ETH-USDT")
                        Text("SOL-USDT").tag("SOL-USDT")
                    }
                    .pickerStyle(.segmented)
                    .frame(maxWidth: 200)
                }
                .padding(.horizontal)

                // Current Price Display
                VStack(spacing: 4) {
                    Text(selectedSymbol)
                        .font(.headline)
                        .foregroundStyle(.secondary)
                    
                    if let tick = viewModel.latestTick {
                        Text(tick.price, format: .currency(code: "USD"))
                            .font(.system(size: 40, weight: .heavy, design: .monospaced))
                            .contentTransition(.numericText())
                    } else {
                        Text("Menerima Data...")
                            .font(.title2)
                            .foregroundStyle(.secondary)
                    }
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 20)
                .background(Color(.secondarySystemBackground))
                .clipShape(RoundedRectangle(cornerRadius: 16))
                .padding(.horizontal)

                // Streamed Price List
                List {
                    Section("Histori Perubahan Terakhir") {
                        ForEach(viewModel.priceHistory.reversed()) { tick in
                            HStack {
                                Text(tick.timestamp, format: .dateTime.hour().minute().second().secondFraction(.fractional(3)))
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                                Spacer()
                                Text(tick.price, format: .currency(code: "USD"))
                                    .font(.body)
                                    .monospacedDigit()
                            }
                        }
                    }
                }
                .listStyle(.insetGrouped)
            }
            .navigationTitle("High-Freq Ticker")
            // Pengikatan konkurensi siklus hidup ke parameter selectedSymbol
            .task(id: selectedSymbol) {
                await viewModel.startStreaming(for: selectedSymbol)
            }
        }
    }
}
