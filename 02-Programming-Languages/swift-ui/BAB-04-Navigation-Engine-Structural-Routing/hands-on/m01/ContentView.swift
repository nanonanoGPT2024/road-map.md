import SwiftUI
import OSLog

// MARK: - 1. DOMAIN ROUTES (SERIALIZABLE)

enum AppRoute: Codable, Hashable {
    case dashboard
    case accountDetail(accountId: String)
    case transferInput(sourceAccountId: String)
    case transferConfirmation(transactionId: String, amount: Double)
    case systemSettings
}

// MARK: - 2. CENTRALIZED NAVIGATION ENGINE / ROUTER

@Observable
final class NavigationRouter {
    private let logger = Logger(subsystem: "com.fintech.app", category: "NavigationRouter")
    
    // Core data stack
    var path: [AppRoute] = [] {
        didSet {
            logger.debug("Stack Mutated. Depth: \(self.path.count), Head: \(String(describing: self.path.last))")
        }
    }
    
    // Sheet presentation router
    var presentedSheet: AppSheet?
    
    enum AppSheet: Identifiable, Hashable {
        case biometricAuth
        case errorAlert(message: String)
        
        var id: String {
            switch self {
            case .biometricAuth: return "biometricAuth"
            case .errorAlert(let msg): return "error_\(msg)"
            }
        }
    }

    // MARK: Actions
    func navigate(to route: AppRoute) {
        path.append(route)
    }
    
    func pop() {
        guard !path.isEmpty else { return }
        path.removeLast()
    }
    
    func popToRoot() {
        path.removeAll()
    }
    
    // MARK: Deep Link Parsing Engine
    func handleDeepLink(url: URL) -> Bool {
        logger.info("Parsing Deep Link: \(url.absoluteString)")
        guard url.scheme == "bankapp" else { return false }
        
        // Format: bankapp://transfer/confirm?txId=TX9901&amount=500000
        guard let host = url.host else { return false }
        
        switch host {
        case "account":
            if let accountId = url.queryParameters?["id"] {
                popToRoot()
                navigate(to: .accountDetail(accountId: accountId))
                return true
            }
        case "transfer":
            if url.path == "/confirm",
               let txId = url.queryParameters?["txId"],
               let amountStr = url.queryParameters?["amount"],
               let amount = Double(amountStr) {
                popToRoot()
                navigate(to: .transferConfirmation(transactionId: txId, amount: amount))
                return true
            }
        default:
            break
        }
        return false
    }
    
    // MARK: State Persistence Engine
    func exportStateRepresentation() -> Data? {
        do {
            let encoder = JSONEncoder()
            return try encoder.encode(path)
        } catch {
            logger.error("Gagal serialisasi navigation stack: \(error.localizedDescription)")
            return nil
        }
    }
    
    func restoreState(from data: Data) {
        do {
            let decoder = JSONDecoder()
            let decodedPath = try decoder.decode([AppRoute].self, from: data)
            self.path = decodedPath
            logger.info("Stack state berhasil dipulihkan. Total node: \(decodedPath.count)")
        } catch {
            logger.error("Gagal memulihkan state dari data: \(error.localizedDescription)")
        }
    }
}

// Helper parsing URL query parameters
extension URL {
    var queryParameters: [String: String]? {
        guard let components = URLComponents(url: self, resolvingAgainstBaseURL: true),
              let queryItems = components.queryItems else { return nil }
        return queryItems.reduce(into: [String: String]()) { result, item in
            result[item.name] = item.value
        }
    }
}

// MARK: - 3. ROOT CONTAINER VIEW

struct ProductionRootView: View {
    @State private var router = NavigationRouter()
    @SceneStorage("navigation_state_cache") private var savedNavigationData: Data?

    var body: some View {
        NavigationStack(path: $router.path) {
            DashboardScreen()
                .navigationDestination(for: AppRoute.self) { route in
                    DestinationFactory.view(for: route)
                }
        }
        .environment(router)
        .sheet(item: $router.presentedSheet) { sheet in
            switch sheet {
            case .biometricAuth:
                Text("Autentikasi Biometrik Diperlukan")
                    .presentationDetents([.medium])
            case .errorAlert(let msg):
                Text("Error: \(msg)")
                    .presentationDetents([.fraction(0.3)])
            }
        }
        .onAppear {
            // Restore state saat launch
            if let savedNavigationData {
                router.restoreState(from: savedNavigationData)
            }
        }
        .onChange(of: router.path) { _, _ in
            // Save state saat path termutasi
            savedNavigationData = router.exportStateRepresentation()
        }
        .onOpenURL { url in
            _ = router.handleDeepLink(url: url)
        }
    }
}

// MARK: - 4. VIEW FACTORY (DECOUPLING INVERSION)

enum DestinationFactory {
    @ViewBuilder
    static func view(for route: AppRoute) -> some View {
        switch route {
        case .dashboard:
            DashboardScreen()
        case .accountDetail(let accountId):
            AccountDetailScreen(accountId: accountId)
        case .transferInput(let sourceId):
            TransferInputScreen(sourceAccountId: sourceId)
        case .transferConfirmation(let txId, let amount):
            TransferConfirmationScreen(transactionId: txId, amount: amount)
        case .systemSettings:
            SettingsScreen()
        }
    }
}

// MARK: - 5. SCREENS (ISOLATED COMPONENTS)

struct DashboardScreen: View {
    @Environment(NavigationRouter.self) private var router

    var body: some View {
        List {
            Section("Rekening Anda") {
                Button("Rekening Tabungan Utama") {
                    router.navigate(to: .accountDetail(accountId: "ACC-001928"))
                }
            }
            
            Section("Aksi Cepat") {
                Button("Transfer Dana") {
                    router.navigate(to: .transferInput(sourceAccountId: "ACC-001928"))
                }
            }
        }
        .navigationTitle("Dashboard FinTech")
        .toolbar {
            Button("Settings") {
                router.navigate(to: .systemSettings)
            }
        }
    }
}

struct AccountDetailScreen: View {
    let accountId: String
    @Environment(NavigationRouter.self) private var router

    var body: some View {
        VStack(spacing: 20) {
            Text("Detail Rekening: \(accountId)")
                .font(.headline)
            
            Button("Mulai Transfer dari Akun Ini") {
                router.navigate(to: .transferInput(sourceAccountId: accountId))
            }
        }
        .navigationTitle("Detail Akun")
    }
}

struct TransferInputScreen: View {
    let sourceAccountId: String
    @Environment(NavigationRouter.self) private var router

    var body: some View {
        VStack(spacing: 20) {
            Text("Transfer dari: \(sourceAccountId)")
            
            Button("Kirim Rp 500.000") {
                let generatedTxId = "TX-" + UUID().uuidString.prefix(6)
                router.navigate(to: .transferConfirmation(transactionId: String(generatedTxId), amount: 500_000))
            }
        }
        .navigationTitle("Pilih Nominal")
    }
}

struct TransferConfirmationScreen: View {
    let transactionId: String
    let amount: Double
    @Environment(NavigationRouter.self) private var router

    var body: some View {
        VStack(spacing: 24) {
            Image(systemName: "checkmark.circle.fill")
                .foregroundColor(.green)
                .font(.system(size: 64))
            
            Text("Transaksi Berhasil!")
                .font(.title2)
            
            Text("ID Transaksi: \(transactionId)")
            Text("Nominal: Rp \(Int(amount))")
            
            Button("Kembali ke Dashboard Utama") {
                router.popToRoot()
            }
            .buttonStyle(.borderedProminent)
        }
        .navigationTitle("Konfirmasi")
        .navigationBarBackButtonHidden(true) // Cegah kembali ke flow input
    }
}

struct SettingsScreen: View {
    @Environment(NavigationRouter.self) private var router

    var body: some View {
        VStack {
            Text("Pengaturan Aplikasi")
            Button("Trigger Sheet Error") {
                router.presentedSheet = .errorAlert(message: "Koneksi Terputus")
            }
        }
        .navigationTitle("Settings")
    }
}
