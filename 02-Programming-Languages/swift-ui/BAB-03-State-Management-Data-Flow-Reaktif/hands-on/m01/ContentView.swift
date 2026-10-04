import SwiftUI
import Observation

// MARK: - Domain Models & Enums
enum PaymentMethod: String, CaseIterable, Identifiable {
    case bankTransfer = "Virtual Account"
    case creditCard = "Kartu Kredit"
    case eWallet = "E-Wallet Instant"
    
    var id: String { rawValue }
}

enum CheckoutStep {
    case cartReview
    case paymentSelection
    case processing
    case success(orderID: String)
    case failure(reason: String)
}

struct CartItem: Identifiable, Equatable {
    let id: UUID = UUID()
    let name: String
    let price: Decimal
    var quantity: Int
}

// MARK: - Domain Logic Error
enum CheckoutError: LocalizedError {
    case emptyCart
    case invalidPaymentMethod
    case paymentFailed(String)
    
    var errorDescription: String? {
        switch self {
        case .emptyCart: return "Keranjang belanja tidak boleh kosong."
        case .invalidPaymentMethod: return "Metode pembayaran tidak valid."
        case .paymentFailed(let reason): return "Pembayaran gagal: \(reason)"
        }
    }
}

// MARK: - State Management Model (Modern Observation)
@Observable
final class CheckoutCoordinator {
    // Public Read-Only State Projection
    private(set) var currentStep: CheckoutStep = .cartReview
    private(set) var items: [CartItem] = []
    private(set) var discountPercentage: Decimal = 0
    private(set) var isProcessing: Bool = false
    
    // Read-Write State untuk Binding Form
    var selectedPaymentMethod: PaymentMethod?
    var couponCode: String = ""
    var isCouponApplied: Bool = false

    // Derived State Computations
    var subtotal: Decimal {
        items.reduce(Decimal.zero) { $0 + ($1.price * Decimal($1.quantity)) }
    }
    
    var total: Decimal {
        let discount = subtotal * (discountPercentage / 100)
        return max(Decimal.zero, subtotal - discount)
    }

    init(seedItems: [CartItem]) {
        self.items = seedItems
    }

    // Intents / Actions
    @MainActor
    func applyCoupon() async {
        guard !couponCode.trimmingCharacters(in: .whitespaces).isEmpty else { return }
        isProcessing = true
        
        // Simulasi latensi verifikasi jaringan
        try? await Task.sleep(nanoseconds: 800_000_000)
        
        if couponCode.uppercased() == "PROMOHEMAT" {
            discountPercentage = 20
            isCouponApplied = true
        } else {
            discountPercentage = 0
            isCouponApplied = false
        }
        isProcessing = false
    }

    @MainActor
    func proceedToPayment() {
        guard !items.isEmpty else { return }
        currentStep = .paymentSelection
    }

    @MainActor
    func processOrder() async {
        guard let _ = selectedPaymentMethod else { return }
        isProcessing = true
        currentStep = .processing
        
        do {
            // Simulasi panggilan endpoint pembayaran gateway
            try await Task.sleep(nanoseconds: 1_500_000_000)
            
            // Evaluasi logika mock gateway
            if Bool.random() == true || total > 50000000 {
                let generatedID = "TRX-" + UUID().uuidString.prefix(8).uppercased()
                currentStep = .success(orderID: String(generatedID))
                items.removeAll()
            } else {
                throw CheckoutError.paymentFailed("Limit transaksi harian terlampaui.")
            }
        } catch {
            currentStep = .failure(reason: error.localizedDescription)
        }
        isProcessing = false
    }

    @MainActor
    func reset() {
        currentStep = .cartReview
        selectedPaymentMethod = nil
        couponCode = ""
        discountPercentage = 0
        isCouponApplied = false
    }
}

// MARK: - Root View Container
struct CheckoutContainerView: View {
    // Instansiasi Coordinator sebagai State yang mengendalikan siklus hidup hirarki ini
    @State private var coordinator: CheckoutCoordinator

    init(initialCart: [CartItem]) {
        _coordinator = State(wrappedValue: CheckoutCoordinator(seedItems: initialCart))
    }

    var body: some View {
        NavigationStack {
            VStack {
                switch coordinator.currentStep {
                case .cartReview:
                    CartReviewView(coordinator: coordinator)
                case .paymentSelection:
                    PaymentSelectionView(coordinator: coordinator)
                case .processing:
                    ProgressView("Mengotorisasi Pembayaran...")
                        .progressViewStyle(.circular)
                        .scaleEffect(1.2)
                case .success(let orderID):
                    SuccessView(orderID: orderID, onFinish: { coordinator.reset() })
                case .failure(let reason):
                    FailureView(reason: reason, onRetry: { coordinator.proceedToPayment() })
                }
            }
            .animation(.easeInOut(duration: 0.25), value: coordinator.currentStep == .cartReview)
            .navigationTitle("Checkout")
        }
    }
}

// MARK: - Sub-View: Cart Review
struct CartReviewView: View {
    // Menggunakan referensi langsung ke observable class (bukan @ObservedObject)
    @Bindable var coordinator: CheckoutCoordinator

    var body: some View {
        VStack(spacing: 0) {
            List(coordinator.items) { item in
                HStack {
                    VStack(alignment: .leading) {
                        Text(item.name).font(.headline)
                        Text("Jumlah: \(item.quantity)").font(.subheadline).foregroundColor(.secondary)
                    }
                    Spacer()
                    Text("Rp \(NSDecimalNumber(decimal: item.price * Decimal(item.quantity)).intValue)")
                        .fontWeight(.semibold)
                }
            }
            .listStyle(.plain)

            Divider()

            VStack(spacing: 12) {
                HStack {
                    TextField("Kode Kupon", text: $coordinator.couponCode)
                        .textFieldStyle(.roundedBorder)
                        .textInputAutocapitalization(.characters)
                        .disabled(coordinator.isCouponApplied || coordinator.isProcessing)

                    Button("Gunakan") {
                        Task { await coordinator.applyCoupon() }
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(coordinator.couponCode.isEmpty || coordinator.isCouponApplied || coordinator.isProcessing)
                }

                if coordinator.isCouponApplied {
                    HStack {
                        Label("Kupon Berhasil Diterapkan (-20%)", systemImage: "tag.fill")
                            .font(.caption)
                            .foregroundColor(.green)
                        Spacer()
                    }
                }

                HStack {
                    Text("Total Tagihan")
                        .font(.headline)
                    Spacer()
                    Text("Rp \(NSDecimalNumber(decimal: coordinator.total).intValue)")
                        .font(.title3)
                        .fontWeight(.bold)
                        .foregroundColor(.blue)
                }
                .padding(.top, 4)

                Button(action: { coordinator.proceedToPayment() }) {
                    Text("Lanjut ke Pembayaran")
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 8)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .disabled(coordinator.items.isEmpty)
            }
            .padding()
            .background(Color(uiColor: .secondarySystemBackground))
        }
    }
}

// MARK: - Sub-View: Payment Selection
struct PaymentSelectionView: View {
    @Bindable var coordinator: CheckoutCoordinator

    var body: some View {
        VStack(spacing: 20) {
            List(PaymentMethod.allCases, selection: $coordinator.selectedPaymentMethod) { method in
                HStack {
                    Text(method.rawValue)
                    Spacer()
                    if coordinator.selectedPaymentMethod == method {
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundColor(.blue)
                    }
                }
                .contentShape(Rectangle())
                .onTapGesture {
                    coordinator.selectedPaymentMethod = method
                }
            }
            .listStyle(.insetGrouped)

            Button(action: {
                Task { await coordinator.processOrder() }
            }) {
                Text("Bayar Sekarang")
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 8)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .padding(.horizontal)
            .disabled(coordinator.selectedPaymentMethod == nil || coordinator.isProcessing)

            Spacer()
        }
    }
}

// MARK: - Supporting Outcome Views
struct SuccessView: View {
    let orderID: String
    let onFinish: () -> Void

    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "checkmark.seal.fill")
                .font(.system(size: 72))
                .foregroundColor(.green)
            Text("Pembayaran Berhasil!").font(.title.bold())
            Text("ID Pesanan: \(orderID)").font(.subheadline).foregroundColor(.secondary)
            Button("Selesai Belanja", action: onFinish)
                .buttonStyle(.bordered)
                .padding(.top, 10)
        }
        .padding()
    }
}

struct FailureView: View {
    let reason: String
    let onRetry: () -> Void

    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "xmark.octagon.fill")
                .font(.system(size: 72))
                .foregroundColor(.red)
            Text("Transaksi Gagal").font(.title.bold())
            Text(reason).font(.body).multilineTextAlignment(.center).foregroundColor(.secondary)
            Button("Coba Lagi", action: onRetry)
                .buttonStyle(.borderedProminent)
                .padding(.top, 10)
        }
        .padding()
    }
}
