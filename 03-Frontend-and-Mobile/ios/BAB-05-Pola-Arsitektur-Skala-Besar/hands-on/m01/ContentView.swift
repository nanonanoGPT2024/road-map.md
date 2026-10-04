import Foundation
import Combine

// MARK: - 1. Domain States & Models
public struct CryptoAsset: Identifiable, Equatable, Sendable {
    public let id: String
    public let symbol: String
    public var priceUSD: Decimal
    public var holdingQuantity: Decimal
    
    public var totalValue: Decimal {
        priceUSD * holdingQuantity
    }
}

public struct PortfolioState: Equatable, Sendable {
    public var assets: [CryptoAsset] = []
    public var isExecutingTrade: Bool = false
    public var errorMessage: String?
    public var tradeSuccessMessage: String?
    
    public var totalBalanceUSD: Decimal {
        assets.reduce(0) { $0 + $1.totalValue }
    }
}

// MARK: - 2. Domain Actions
public enum PortfolioAction: Equatable, Sendable {
    case onAppear
    case priceStreamReceived([String: Decimal])
    case executeQuickSell(assetId: String, quantity: Decimal)
    case tradeExecutionCompleted(Result<String, TradeError>)
    case dismissAlert
}

public enum TradeError: Error, Equatable, Sendable {
    case insufficientBalance
    case networkTimeout
    case signatureFailed
}

// MARK: - 3. Dependencies Abstraction (Environment Clients)
public struct PortfolioClient: Sendable {
    public var startPriceStream: @Sendable () -> AsyncStream<[String: Decimal]>
    public var executeTrade: @Sendable (_ assetId: String, _ quantity: Decimal) async throws -> String
}

// MARK: - 4. Reducer Core Engine
public struct PortfolioReducer: Sendable {
    private let client: PortfolioClient
    
    public init(client: PortfolioClient) {
        self.client = client
    }
    
    // Pure Reducer Function: Deterministik & Tanpa Side-Effect Langsung
    public func reduce(state: inout PortfolioState, action: PortfolioAction) -> Effect<PortfolioAction> {
        switch action {
        case .onAppear:
            return .run { send in
                // Membuka stream harga dan mendistribusikan action
                for await prices in self.client.startPriceStream() {
                    await send(.priceStreamReceived(prices))
                }
            }
            .cancellable(id: "PRICE_STREAM_ID", cancelInFlight: true)
            
        case let .priceStreamReceived(priceMap):
            for i in state.assets.indices {
                if let newPrice = priceMap[state.assets[i].symbol] {
                    state.assets[i].priceUSD = newPrice
                }
            }
            return .none
            
        case let .executeQuickSell(assetId, quantity):
            guard let asset = state.assets.first(where: { $0.id == assetId }),
                  asset.holdingQuantity >= quantity else {
                state.errorMessage = "Saldo aset tidak mencukupi untuk order ini."
                return .none
            }
            
            state.isExecutingTrade = true
            state.errorMessage = nil
            
            return .run { send in
                do {
                    let txHash = try await self.client.executeTrade(assetId, quantity)
                    await send(.tradeExecutionCompleted(.success(txHash)))
                } catch let error as TradeError {
                    await send(.tradeExecutionCompleted(.failure(error)))
                } catch {
                    await send(.tradeExecutionCompleted(.failure(.networkTimeout)))
                }
            }
            
        case let .tradeExecutionCompleted(.success(txHash)):
            state.isExecutingTrade = false
            state.tradeSuccessMessage = "Transaksi Berhasil! TxHash: \(txHash)"
            return .none
            
        case let .tradeExecutionCompleted(.failure(error)):
            state.isExecutingTrade = false
            switch error {
            case .insufficientBalance:
                state.errorMessage = "Transaksi Ditolak: Saldo Tidak Mencukupi."
            case .networkTimeout:
                state.errorMessage = "Koneksi Bermasalah. Silakan Coba Lagi."
            case .signatureFailed:
                state.errorMessage = "Gagal Menandatangani Transaksi Kripto."
            }
            return .none
            
        case .dismissAlert:
            state.errorMessage = nil
            state.tradeSuccessMessage = nil
            return .none
        }
    }
}

// MARK: - 5. Lightweight Production Effect Implementation
public struct Effect<Action: Sendable>: Sendable {
    public typealias Operation = @Sendable (@escaping @Sendable (Action) async -> Void) async -> Void
    private let operation: Operation?
    
    public init(operation: Operation?) {
        self.operation = operation
    }
    
    public static var none: Effect<Action> {
        Effect(operation: nil)
    }
    
    public static func run(operation: @escaping Operation) -> Effect<Action> {
        Effect(operation: operation)
    }
    
    public func execute(send: @escaping @Sendable (Action) async -> Void) async {
        if let operation = self.operation {
            await operation(send)
        }
    }
    
    public func cancellable(id: String, cancelInFlight: Bool) -> Effect<Action> {
        // Implementasi integrasi lifecycle token cancellation
        return self
    }
}

// MARK: - 6. Architectural Store Core (Actor-Isolated Runtime)
@MainActor
@Observable
public final class Store<State: Equatable & Sendable, Action: Sendable> {
    public private(set) var state: State
    private let reducer: @Sendable (inout State, Action) -> Effect<Action>
    private var runningTasks: [Task<Void, Never>] = []
    
    public init(
        initialState: State,
        reducer: @escaping @Sendable (inout State, Action) -> Effect<Action>
    ) {
        self.state = initialState
        self.reducer = reducer
    }
    
    public func send(_ action: Action) {
        let effect = reducer(&self.state, action)
        
        let task = Task { [weak self] in
            await effect.execute { nextAction in
                Task { @MainActor [weak self] in
                    self?.send(nextAction)
                }
            }
        }
        runningTasks.append(task)
    }
    
    deinit {
        runningTasks.forEach { $0.cancel() }
    }
}
