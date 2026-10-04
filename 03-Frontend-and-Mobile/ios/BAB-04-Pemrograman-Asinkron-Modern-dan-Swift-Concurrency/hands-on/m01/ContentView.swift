import Foundation

// MARK: - Domain Models
public struct TransactionOrder: Identifiable, Sendable, Codable {
    public let id: UUID
    public let symbol: String
    public let amount: Double
    public let timestamp: Date
}

public enum OrderProcessingError: Error, Sendable {
    case networkTimeout
    case insufficientLiquidity
    case cancelledByUser
}

// MARK: - Actor State Manager: Ledger Store
public actor PortfolioLedgerActor {
    private var totalBalance: Double
    private var executedOrders: [UUID: TransactionOrder] = [:]

    public init(initialBalance: Double) {
        self.totalBalance = initialBalance
    }

    public func debit(amount: Double, for order: TransactionOrder) throws {
        guard totalBalance >= amount else {
            throw OrderProcessingError.insufficientLiquidity
        }
        totalBalance -= amount
        executedOrders[order.id] = order
    }

    public func currentBalance() -> Double {
        return totalBalance
    }
}

// MARK: - Production Engine with AsyncStream & Bounded TaskGroup
public final class ResilientOrderProcessingEngine: Sendable {
    private let ledger: PortfolioLedgerActor

    public init(ledger: PortfolioLedgerActor) {
        self.ledger = ledger
    }

    /// Menghasilkan stream transaksional yang aman dari buffer overflow (Backpressure Control)
    public func createLiveOrderStream() -> (AsyncStream<TransactionOrder>, AsyncStream<TransactionOrder>.Continuation) {
        var continuationRef: AsyncStream<TransactionOrder>.Continuation?
        let stream = AsyncStream<TransactionOrder>(bufferingPolicy: .bufferingNewest(100)) { continuation in
            continuationRef = continuation
        }
        // Force unwrap aman di sini karena closure AsyncStream dieksekusi secara sinkronis pada inisialisasi
        return (stream, continuationRef!)
    }

    /// Memproses batch order menggunakan Pola Concurrency Limiting (Mencegah Resource Exhaustion)
    public func processBatchOrdersConcurrently(
        orders: [TransactionOrder], 
        maxConcurrentTasks: Int
    ) async throws -> [UUID] {
        guard !orders.isEmpty else { return [] }

        return try await withThrowingTaskGroup(of: UUID.self) { group in
            var processedOrderIDs: [UUID] = []
            processedOrderIDs.reserveCapacity(orders.count)

            var currentIndex = 0
            let total = orders.count

            // Batch initial filling: Hanya alokasikan sejumlah slot konkurensi aman
            let initialBatchLimit = min(maxConcurrentTasks, total)
            for _ in 0..<initialBatchLimit {
                let order = orders[currentIndex]
                currentIndex += 1
                group.addTask {
                    return try await self.executeInternalOrderTransaction(order)
                }
            }

            // Pool Sliding Window: Saat satu task selesai, masukkan task berikutnya
            for try await completedOrderID in group {
                processedOrderIDs.append(completedOrderID)
                
                // Cek status pembatalan parent
                try Task.checkCancellation()

                if currentIndex < total {
                    let nextOrder = orders[currentIndex]
                    currentIndex += 1
                    group.addTask {
                        return try await self.executeInternalOrderTransaction(nextOrder)
                    }
                }
            }

            return processedOrderIDs
        }
    }

    private func executeInternalOrderTransaction(_ order: TransactionOrder) async throws -> UUID {
        // Periksa kooperatif pembatalan sebelum operasi intensif
        try Task.checkCancellation()

        // Simulasi latensi RPC / Enkripsi payload
        try await Task.sleep(nanoseconds: 50_000_000) // 50ms

        // Crossing boundary ke Actor: Melindungi data balance mutasi
        try await ledger.debit(amount: order.amount, for: order)

        return order.id
    }
}

// MARK: - UI Coordinator (MainActor Presentation Binding)
@MainActor
public final class OrderProcessingViewModel {
    private let engine: ResilientOrderProcessingEngine
    private let ledger: PortfolioLedgerActor
    
    public private(set) var displayBalance: Double = 0.0
    public private(set) var isProcessing: Bool = false
    private var streamProcessingTask: Task<Void, Never>?

    public init(engine: ResilientOrderProcessingEngine, ledger: PortfolioLedgerActor) {
        self.engine = engine
        self.ledger = ledger
    }

    public func startListeningToLiveOrders(stream: AsyncStream<TransactionOrder>) {
        streamProcessingTask?.cancel() // Batalkan task listener lama jika aktif
        
        streamProcessingTask = Task { [weak self] in
            for await order in stream {
                guard let self = self else { return }
                do {
                    _ = try await self.engine.processBatchOrdersConcurrently(orders: [order], maxConcurrentTasks: 1)
                    // Mutasi state MainActor dilakukan secara otomatis di thread utama
                    self.displayBalance = await self.ledger.currentBalance()
                } catch {
                    // Logging terpusat dan graceful degradation
                    print("Gagal mengeksekusi order: \(order.id), Error: \(error)")
                }
            }
        }
    }

    public func teardown() {
        streamProcessingTask?.cancel()
        streamProcessingTask = nil
    }
}
