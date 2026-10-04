# SEKSI 01 — IDENTITAS MODUL

* **Jalur Kurikulum:** Mobile Application Engineering
* **Kategori:** 02-Programming-Languages
* **Topik Utama:** SwiftUI Declarative UI Engine
* **Modul:** Bab 03 Module 01 — State Management & Data Flow Reaktif
* **Tingkat Kesulitan:** Intermediate to Advanced
* **Prasyarat:** Pemahaman mendalam tentang Swift Type System (Structs, Classes, Enums, Protocols), Closures, ARC (Automatic Reference Counting), Memory Layout dasar Swift, dan SwiftUI View Hierarchy fundamental.
* **Target Stack:** Swift 5.9+ / Swift 6, iOS 17+ (dengan referensi komparasi ke iOS 13–16 Combine-based architecture).

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis dan Membedakan** siklus hidup serta semantik memori dari mekanisme state SwiftUI (`@State`, `@Binding`, `@StateObject`, `@ObservedObject`, `@EnvironmentObject`, dan `@Observable` macro).
2. **Mengonstruksi** arsitektur *Unidirectional Data Flow* (UDF) yang deterministik dengan memisahkan *Single Source of Truth* (SSOT) dari *Derived State*.
3. **Mendiagnosis dan Mengeliminasi** *view invalidation thrashing* (re-render berlebih) menggunakan instrumen profil performa SwiftUI dan teknik scoping state granular.
4. **Menerapkan** mitigasi sistemik terhadap *race conditions*, mutasi state reentrant (*state mutation during view update*), dan siklus retensi memori pada alur asinkronus.
5. **Merancang** sistem state berskala enterprise yang aman (*thread-safe* dan *leak-free*) untuk skenario validasi data kompleks dan sinkronisasi status multi-layar.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Imperatif vs. Deklaratif

Dalam paradigma imperatif (UIKit), UI adalah kumpulan objek mutabel berumur panjang (*long-lived references*). Developer bertindak sebagai mandor yang secara manual memanipulasi properti visual setiap kali data berubah:

$$\text{Data Berubah} \longrightarrow \text{Controller Mengambil Objek} \longrightarrow \text{Ubah Properti (e.g., label.text = ...)}$$

Model mental ini rentan terhadap *state desynchronization*: jika ada satu cabang logika yang lupa memperbarui UI, antarmuka akan menampilkan data basi (*stale data*).

SwiftUI mengadopsi model mental fungsional murni:

$$\text{UI} = f(\text{State})$$

Antarmuka pengguna bukanlah kumpulan objek grafis yang disimpan di memori, melainkan **proyeksi langsung dari state pada titik waktu tertentu**. `View` dalam SwiftUI adalah sebuah `struct` yang bersifat *ephemeral* (berumur sangat pendek), murah untuk dialokasikan di stack, dan dapat dihancurkan serta dibuat ulang puluhan kali per detik tanpa penalti performa yang signifikan.

```
       [ Single Source of Truth ]
                   │
                   ▼ (Data Mengalir Turun)
       ┌────────────────────────┐
       │   View Graph / Struct  │
       └────────────────────────┘
                   │
                   ▲ (Aksi Mengalir Naik)
       [ Intent / User Action ]
```

### Prinsip Inti: Unidirectional Data Flow (UDF)
1. **Data Mengalir ke Bawah (Data Flows Down):** Induk meneruskan data ke anak baik dalam bentuk nilai baca-saja (*read-only value*) atau sebagai binding read-write dua arah.
2. **Aksi Mengalir ke Atas (Actions Flow Up):** Perubahan data tidak pernah dimutasi secara liar dari view anak. Anak mengirimkan *event/action* atau memutasi nilai lewat binding yang terikat langsung ke *Source of Truth* induk.
3. **Single Source of Truth (SSOT):** Setiap potongan data dinamis hanya boleh dimiliki secara definitif oleh satu entitas. Komponen lain hanya mengonsumsi referensi atau proyeksi dari data tersebut.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

SwiftUI mengelola representasi dependensi data menggunakan graf internal yang disebut **AttributeGraph**. Diagram berikut mengilustrasikan bagaimana mutasi State memicu siklus evaluasi ulang:

```
+-----------------------------------------------------------------------+
| SwiftUI Runtime Engine                                                |
|                                                                       |
|  [ User Tap / Network Event ]                                          |
|                │                                                      |
|                ▼                                                      |
|  +---------------------------+                                        |
|  | Mutasi State              |                                        |
|  | (@State / @Observable)    |                                        |
|  +-------------┬-------------+                                        |
|                │                                                      |
|                ▼                                                      |
|  +---------------------------+                                        |
|  | AttributeGraph            |                                        |
|  | Dependency Invalidation   |                                        |
|  +-------------┬-------------+                                        |
|                │ Menandai node "Dirty"                                |
|                ▼                                                      |
|  +---------------------------+                                        |
|  | Schedule View Render Loop |                                        |
|  +-------------┬-------------+                                        |
|                │                                                      |
|                ▼                                                      |
|  +---------------------------+      Diff Struct Hierarchy             |
|  | Re-evaluate body of View  | --------------------------------+      |
|  +---------------------------+                                 │      |
|                                                                ▼      |
|                                                  +------------------+ |
|                                                  | Structural Diff  | |
|                                                  | (Old vs New Tree)| |
|                                                  +---------┬--------+ |
|                                                            │          |
+------------------------------------------------------------│----------+
                                                             │ Compute minimal delta
                                                             ▼
                                             +-------------------------------+
                                             | Render Backend Engine         |
                                             | (CoreAnimation / Metal /      |
                                             |  RenderServer Transaction)    |
                                             +-------------------------------+
```

### Siklus Detail:
1. **Event Trigger:** Pengguna berinteraksi (misal menekan tombol) atau data asinkronus tiba via `Task`.
2. **Storage Mutation:** Nilai dalam backing storage `@State` atau properti bertanda `@Observable` berubah.
3. **Graph Invalidation:** `AttributeGraph` mendeteksi bahwa node data yang terikat pada View tertentu telah berubah, menandai node View tersebut sebagai *dirty*.
4. **Layout & Diffing:** Runtime mengeksekusi properti `body` dari View yang ditandai *dirty*. Outputnya adalah hirarki pohon struct baru.
5. **Platform Commit:** SwiftUI melakukan perbandingan (*diffing*) pohon struct baru terhadap pohon struct sebelumnya, lalu memetakan perubahan minimal ke layer CoreAnimation/RenderServer tanpa menyentuh node visual yang tidak berubah.

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### Protokol `DynamicProperty`

Bagaimana sebuah struct imutabel seperti `struct ContentView: View` dapat mempertahankan dan mengubah state? Kuncinya terletak pada protokol internal:

```swift
public protocol DynamicProperty {
    mutating func update()
}
```

Semua properti wrapper SwiftUI (`@State`, `@Binding`, `@Environment`, dll.) mengadopsi `DynamicProperty`. Ketika SwiftUI mengevaluasi `View`, framework memeriksa metadata layout dari struct View menggunakan *reflection metadata* dan menghubungkan setiap `DynamicProperty` ke penyimpanan runtime di luar struct itu sendiri.

### Anatomi `@State`

```swift
@frozen @propertyWrapper public struct State<Value>: DynamicProperty {
    // Pointer tidak langsung ke backing storage internal di memori heap SwiftUI
    internal var _location: AnyLocation<Value>

    public init(wrappedValue: Value) {
        _location = StoredLocation(value: wrappedValue)
    }

    public init(initialValue: Value) {
        self.init(wrappedValue: initialValue)
    }

    public var wrappedValue: Value {
        get { _location.value }
        nonmutating set { _location.value = newValue }
    }

    public var projectedValue: Binding<Value> {
        Binding(
            get: { self.wrappedValue },
            set: { self.wrappedValue = $0 }
        )
    }
}
```

* **Storage Eksternal:** `wrappedValue` tidak disimpan secara inline di dalam frame stack `struct View`. SwiftUI mengalokasikan slot penyimpanan persisten pada *graph node* yang dihubungkan dengan identitas struktural View tersebut.
* **`nonmutating set`:** Setter bersifat `nonmutating`. Ini memungkinkan kode di dalam `body` struct (yang *immutable*) memutasi nilai tanpa memerlukan penandaan `mutating func`.
* **Projected Value (`$` operator):** Menghasilkan tipe `Binding<Value>`, yang merupakan representasi *first-class reference* (closure get/set) menuju lokasi memori data asli.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Taksonomi Manajemen State

| Wrapper / Macro | Scope Lifetime | Tipe Data yang Didukung | Kebutuhan Observation Framework | Kasus Penggunaan Ideal |
| :--- | :--- | :--- | :--- | :--- |
| `@State` | Terikat siklus hidup View Graph | Value Types (Struct, Enum, Primitives) | Tidak | UI State lokal, transien (toggle, input teks, timer UI) |
| `@Binding` | Menunjuk ke Source of Truth eksternal | Value Types | Tidak | Komponen anak modular yang butuh memodifikasi state induk |
| `@StateObject` | Terikat siklus hidup View Graph | Reference Types (`ObservableObject`) | Ya (`Combine`) | Instansiasi ViewModel (Legacy iOS 14–16) |
| `@ObservedObject` | Dikelola di luar View (dapat ter-reset) | Reference Types (`ObservableObject`) | Ya (`Combine`) | Injeksi dependensi ViewModel dari luar (Legacy) |
| `@EnvironmentObject` | Bersifat global per sub-tree View | Reference Types (`ObservableObject`) | Ya (`Combine`) | Data bersama multi-layar (Auth, Theme) (Legacy) |
| `@Observable` (iOS 17+) | Fleksibel (Stack / Heap / Env) | Reference Types (Classes) | Observation Framework | Arsitektur modern; observasi tingkat properti |

### Paradigma Modern: Observation Framework vs. Combine-based `ObservableObject`

Pada arsitektur warisan (iOS 13–16), SwiftUI mengandalkan `Combine`:
```swift
// DEPRECATED / LEGACY MENTALITY
final class OldViewModel: ObservableObject {
    @Published var name: String = ""
    @Published var count: Int = 0
}
```
Kelemahan Combine di sini adalah: setiap kali properti `@Published` berubah, `objectWillChange` akan dipancarkan. Akibatnya, **setiap View** yang memegang referensi ke `OldViewModel` via `@ObservedObject` akan dievaluasi ulang `body`-nya, meskipun View tersebut hanya membaca properti `name` dan yang dimutasi adalah `count`.

#### Revolusi Macro `@Observable` (Swift 5.9+ / iOS 17+)
Macro `@Observable` secara otomatis menghasilkan instrumen pelacakan dependensi granular menggunakan `ObservationRegistrar`:

```swift
@Observable 
final class ModernViewModel {
    var name: String = ""
    var count: Int = 0
}
```

Ketika View membaca `viewModel.name` di dalam `body`, macro mencatat akses tersebut via `access(keyPath: \.name)`. Jika `viewModel.count` bermutasi, View tersebut **tidak akan di-render ulang**. Render ulang hanya terjadi jika keypath yang dibaca oleh View tersebut mengalami mutasi. Ini memangkas *unnecessary invalidation* tanpa konfigurasi manual.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi bertahap yang mendemonstrasikan `@State`, `@Binding`, dan pemisahan *Parent-Child* data flow:

```swift
import SwiftUI

// MARK: - Model Domain Sederhana
struct TaskItem: Identifiable, Equatable {
    let id: UUID = UUID()
    var title: String
    var isCompleted: Bool
}

// MARK: - Root Parent View (Source of Truth)
struct TaskManagerView: View {
    // Source of Truth tunggal untuk seluruh hirarki tampilan ini
    @State private var tasks: [TaskItem] = [
        TaskItem(title: "Rancang Desain Sistem", isCompleted: true),
        TaskItem(title: "Optimasi State AttributeGraph", isCompleted: false),
        TaskItem(title: "Implementasi Unit Test", isCompleted: false)
    ]
    
    @State private var newTaskTitle: String = ""

    var body: some View {
        NavigationStack {
            VStack(spacing: 16) {
                // Input Section
                HStack {
                    TextField("Tugas Baru...", text: $newTaskTitle)
                        .textFieldStyle(.roundedBorder)
                    
                    Button(action: addTask) {
                        Image(systemName: "plus.circle.fill")
                            .font(.title2)
                    }
                    .disabled(newTaskTitle.trimmingCharacters(in: .whitespaces).isEmpty)
                }
                .padding(.horizontal)

                // List Section via Binding
                List {
                    // Menggunakan Binding langsung ke elemen Array
                    ForEach($tasks) { $task in
                        TaskRowView(task: $task)
                    }
                    .onDelete(perform: deleteTask)
                }
                .listStyle(.plain)
            }
            .navigationTitle("Daftar Tugas")
        }
    }

    private func addTask() {
        let trimmed = newTaskTitle.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty else { return }
        tasks.append(TaskItem(title: trimmed, isCompleted: false))
        newTaskTitle = ""
    }

    private func deleteTask(at offsets: IndexSet) {
        tasks.remove(atOffsets: offsets)
    }
}

// MARK: - Child Component (Derived Binding Consumer)
struct TaskRowView: View {
    // Binding merujuk langsung ke Source of Truth di TaskManagerView
    @Binding var task: TaskItem

    var body: some View {
        HStack {
            Button(action: { task.isCompleted.toggle() }) {
                Image(systemName: task.isCompleted ? "checkmark.circle.fill" : "circle")
                    .foregroundColor(task.isCompleted ? .green : .gray)
                    .font(.title3)
            }
            .buttonStyle(.plain)

            TextField("Nama Tugas", text: $task.title)
                .strikethrough(task.isCompleted, color: .gray)
                .foregroundColor(task.isCompleted ? .gray : .primary)
        }
        .padding(.vertical, 4)
    }
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Evaluasi `TaskManagerView`
* **Baris 12:** `@State private var tasks: [TaskItem] = [...]`  
  Deklarasi ini memesan alokasi memori internal di luar struct `TaskManagerView`. Kata kunci `private` wajib digunakan karena data ini adalah *Single Source of Truth* absolut milik tampilan ini dan tidak boleh diakses langsung dari inisialisasi eksternal.
* **Baris 24:** `TextField("Tugas Baru...", text: $newTaskTitle)`  
  Operator `$` mengekspos `projectedValue` berupa `Binding<String>`. Komponen `TextField` dapat membaca dan menulis string ini secara dua arah tanpa memiliki state tersebut.
* **Baris 38:** `ForEach($tasks) { $task in ... }`  
  Sintaks ini menggunakan kemampuan Swift 5.5+ dynamic keypath collection binding. Nilai `$task` bertipe `Binding<TaskItem>`, bukan nilai biasa. Ini menghindari kesalahan klasik mencari index item manual (`tasks[index]`) yang berpotensi memicu crash *Out of Bounds* saat operasi penghapusan data berlangsung.

### Evaluasi `TaskRowView`
* **Baris 58:** `@Binding var task: TaskItem`  
  Komponen anak ini tidak memiliki state mandiri. Ketika tombol centang ditekan, mutasi `task.isCompleted.toggle()` berjalan melalui penunjuk referensial *get/set closure* yang langsung memodifikasi koleksi `tasks` pada `TaskManagerView`.
* **Baris 62:** `Image(...)` merespons mutasi data tersebut seketika karena `TaskManagerView` memicu perenderan ulang parsial pada baris yang terdampak.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Enterprise E-Commerce Checkout State Machine

Pada aplikasi skala besar, perancangan form transaksi checkout multi-langkah (*multi-step transaction*) rentan memicu kondisi berikut jika dikelola dengan buruk:
1. **Inkonsistensi State:** Metode pembayaran telah divalidasi, tetapi total nominal cart berubah di latar belakang tanpa membatalkan status validasi.
2. **Race Condition Jaringan:** Permintaan validasi kupon paralel menimpa status pesanan akhir.
3. **Memory Leaks & Task Desync:** View di-pop keluar dari hirarki navigasi saat panggilan API otorisasi pembayaran sedang berlangsung, memicu kebocoran alur kerja atau pembaruan UI pada view yang sudah mati.

### Solusi Arsitektural
Kita akan membangun alur checkout berbasis state machine deterministik menggunakan `@Observable` engine, memisahkan lapisan bisnis dan UI, serta mengamankan alur transaksi dari mutasi liar.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

```swift
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
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### Arsitektur Observasi State: Macro Modern vs. Legacy Stack

```
+------------------------------------+---------------------------------------+
| iOS 17+ (@Observable Engine)       | iOS 13-16 (Combine ObservableObject)  |
+------------------------------------+---------------------------------------+
|  [ ModernViewModel ]               |  [ LegacyViewModel ]                  |
|    var name: String                |    @Published var name: String        |
|    var age: Int                    |    @Published var age: Int            |
|                                    |                                       |
|         | Dependency Tracked       |          | Dispatches                 |
|         v                          |          v                            |
|  [ View reads .name ONLY ]         |  [ View reads .name ONLY ]            |
|  * Re-renders ONLY when name shifts|  * Re-renders on ANY @Published shift |
|  * Graph tracking via KeyPaths     |  * Coarse-grained invalidation        |
+------------------------------------+---------------------------------------+
```

### Matriks Perbandingan Komprehensif

| Dimensi Parameter | `@Observable` (Macro Swift 5.9+) | `ObservableObject` + `@Published` | Nilai Murni Value Types (`@State`) |
| :--- | :--- | :--- | :--- |
| **Granularitas Evaluasi** | Sangat granular (per-property keypath) | Kasar (seluruh object invalidasi) | Granular per property wrapper |
| **Alokasi Memori** | Heap (Class instances) | Heap (Class instances) | Managed Runtime Internal Graph |
| **Overhead Kode** | Minimal (cukup satu deklarasi macro) | Tinggi (`@Published`, Combine framework) | Minimal (native language feature) |
| **Kemudahan Pengujian Unit**| Sangat Tinggi (POJO/POCO Swift class) | Sedang (keterikatan Combine publishers)| Rendah (terikat siklus SwiftUI) |
| **Thread Safety Model** | Bebas, namun lazim diikat `@MainActor` | Wajib memancarkan di main thread | Terikat ke thread rendering internal |
| **Kompatibilitas Backward** | iOS 17+, macOS 14+ | iOS 13+, macOS 10.15+ | iOS 13+, macOS 10.15+ |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. Inisialisasi `@State` atau `@StateObject` Menggunakan Nilai Dynamic Parent
**Kasus:** Menuliskan `_state = State(initialValue: dynamicProperty)` di dalam inisialisasi kustom view anak.
* **Pitfall:** Inisialisasi properti wrapper hanya dieksekusi **satu kali** saat representasi node View pertama kali dimasukkan ke AttributeGraph. Jika nilai dynamic milik parent berubah di kemudian hari, child View **tidak akan** memperbarui nilai `@State` internalnya.
* **Solusi:** Jika data tersebut dinamis dari luar, gunakan `@Binding` atau sinkronisasikan via modifier `.onChange(of: dynamicValue)`.

### 2. State Mutation During View Update Loop
**Kasus:** Memodifikasi variabel `@State` secara sinkron langsung di dalam blok kalkulasi `var body: some View`.
* **Dampak:** Runtime Crash atau peringatan log: *"Modifying state during view update, this will cause undefined behavior"*.
* **Mekanisme Internal:** Evaluasi `body` harus bersifat fungsional murni tanpa *side-effects*. Mengubah state di dalam body menandai node tersebut sebagai *dirty* pada siklus render yang sedang aktif, memicu loop invalidasi rekursif tak berujung (*infinite loop*).

### 3. Structural Identity Loss
**Kasus:** Menggunakan modifier kondisional destruktif:
```swift
if isAlternate {
    MyCustomInputView().id("A")
} else {
    MyCustomInputView().id("B")
}
```
* **Dampak:** Seluruh tree internal dihancurkan dan dibuat ulang. Data form yang disimpan dalam `@State` lokal milik `MyCustomInputView` akan terhapus (*wiped out*), fokus keyboard hilang, dan animasi terpotong secara instan.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Anti-Pattern 1: Menggunakan `@ObservedObject` untuk Menginisialisasi State

```swift
// SALAH (ANTI-PATTERN)
struct BadParentView: View {
    var body: some View {
        // Setiap kali BadParentView di-render ulang oleh parent-nya,
        // instance ExpensiveViewModel AKAN DIBUAT ULANG DARI AWAL!
        BadChildView(viewModel: ExpensiveViewModel())
    }
}

struct BadChildView: View {
    @ObservedObject var viewModel: ExpensiveViewModel
    var body: some View { Text(viewModel.data) }
}
```

```swift
// BENAR (iOS 14-16)
struct GoodChildView: View {
    @StateObject var viewModel = ExpensiveViewModel()
    var body: some View { Text(viewModel.data) }
}

// BENAR (Modern iOS 17+)
struct ModernGoodChildView: View {
    @State private var viewModel = ModernExpensiveViewModel()
    var body: some View { Text(viewModel.data) }
}
```

---

### Anti-Pattern 2: Prop-Drilling State yang Berlebihan

```swift
// SALAH: Meneruskan 5 parameter binding melintasi 4 lapis hierarchy view
struct GrandParentView: View {
    @State private var themeColor: Color = .blue
    var body: some View {
        ParentView(themeColor: $themeColor)
    }
}
struct ParentView: View {
    @Binding var themeColor: Color
    var body: some View {
        ChildView(themeColor: $themeColor)
    }
}
```

```swift
// BENAR: Menggunakan Environment injection untuk state berskala tree
private struct ThemeColorKey: EnvironmentKey {
    static let defaultValue: Color = .blue
}

extension EnvironmentValues {
    var appThemeColor: Color {
        get { self[ThemeColorKey.self] }
        set { self[ThemeColorKey.self] = newValue }
    }
}

struct GrandParentView: View {
    @State private var themeColor: Color = .purple
    var body: some View {
        ChildView()
            .environment(\.appThemeColor, themeColor)
    }
}

struct ChildView: View {
    @Environment(\.appThemeColor) private var themeColor
    var body: some View {
        Text("Child View").foregroundColor(themeColor)
    }
}
```

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Akses Minimum (`private` by Default):** Seluruh properti `@State` wajib dideklarasikan dengan tingkat akses `private`. Properti tersebut tidak boleh dimodifikasi dari luar tanpa melalui antarmuka eksplisit.
2. **Isolasi Concurrency via `@MainActor`:** ViewModel atau koordinator state wajib dianotasi dengan `@MainActor` guna menjamin seluruh pembaruan atribut antarmuka dilakukan pada thread utama.
3. **Pemisahan State Model dan Business Service:** Hindari meletakkan logika panggilan HTTP/Database langsung di dalam controller state. Gunakan arsitektur berbasis service:
   $$\text{View} \longleftrightarrow \text{State Coordinator/ViewModel} \longleftrightarrow \text{Repository/Service API}$$
4. **Hindari Primitive Overuse:** Gabungkan state yang saling berelasi erat menjadi satu struct atau state machine enum. Mengelola 6 boolean terpisah (`isLoading`, `isError`, `isSuccess`, dll.) adalah sumber inkonsistensi utama.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Meminimalkan Cakupan Evaluasi `body` (Scoping Invalidation)

Perhatikan kode berikut:
```swift
struct InefficientDashboard: View {
    @State private var timerTicks: Int = 0
    @State private var heavyUserData: ComplexProfile = .load()

    var body: some View {
        VStack {
            Text("Ticks: \(timerTicks)") // Berubah tiap detik
            HeavyProfileCard(data: heavyUserData) // View sangat kompleks
        }
        .onReceive(timer) { _ in timerTicks += 1 }
    }
}
```
**Masalah:** Perubahan `timerTicks` setiap detik memaksa evaluasi ulang seluruh `VStack`, termasuk membandingkan struktur `HeavyProfileCard`.

**Solusi:** Ekstraksi komponen dinamis ke sub-view mandiri:
```swift
struct TickerView: View {
    @State private var timerTicks: Int = 0
    let timer = Timer.publish(every: 1, on: .main, in: .common).autoconnect()

    var body: some View {
        Text("Ticks: \(timerTicks)")
            .onReceive(timer) { _ in timerTicks += 1 }
    }
}

struct EfficientDashboard: View {
    @State private var heavyUserData: ComplexProfile = .load()

    var body: some View {
        VStack {
            TickerView() // Evaluasi terisolasi di dalam TickerView
            HeavyProfileCard(data: heavyUserData)
        }
    }
}
```

### 2. Memanfaatkan `EquatableView` pada Hirarki Statis Ekstrem
Jika struct view menerima data masukan berupa value type kompleks, implementasikan protokol `Equatable` pada View dan bungkus pemanggilan menggunakan modifier `.equatable()`. Ini memotong kalkulasi diffing jika input struct tidak mengalami perubahan bit-by-bit.

---

# SEKSI 16 — KEAMANAN & HARDENING

State pada aplikasi mobile sering kali menampung data sensitif (informasi identitas pribadi, token otentikasi, nomor kartu parsial). Kerentanan dapat terjadi apabila state ini tetap berada di memori saat aplikasi tidak aktif.

### 1. Pembersihan State Sensitif saat Lifecycle Perubahan Aplikasi

```swift
@Observable
final class SecureVaultCoordinator {
    var authenticationToken: String?
    var decryptedPII: String?

    @MainActor
    func flushSensitiveData() {
        authenticationToken = nil
        decryptedPII = nil
    }
}

struct SecureAppRootView: View {
    @State private var vault = SecureVaultCoordinator()
    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        ContentView()
            .environment(vault)
            .onChange(of: scenePhase) { _, newPhase in
                if newPhase == .background {
                    // Mencegah snapshot memori OS menyimpan plaintext rahasia
                    vault.flushSensitiveData()
                }
            }
    }
}
```

### 2. Pencegahan Injection via State Binding
Pastikan seluruh string yang diikat melalui `Binding<String>` pada field masukan teks disanitasi secara deterministik sebelum dialirkan ke lapisan komputasi domain atau penyimpanan lokal.

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

SwiftUI menyediakan instrumen debugging bawaan untuk melacak pemicu render ulang antarmuka:

### 1. `Self._printChanges()`

Sisipkan metode diagnosis internal ini di dalam blok `body` untuk mengidentifikasi penyebab invalidasi tampilan:

```swift
struct PerformanceDebugView: View {
    @Bindable var coordinator: CheckoutCoordinator

    var body: some View {
        #if DEBUG
        let _ = Self._printChanges()
        #endif

        VStack {
            Text("Total: \(coordinator.total.description)")
        }
    }
}
```
*Output pada Xcode Console:*
```text
PerformanceDebugView: _coordinator changed.
PerformanceDebugView: @self changed.
```

### 2. Structured Logging dengan OSLog

```swift
import OSLog

final class StateTelemetry {
    private static let logger = Logger(subsystem: "com.enterprise.app", category: "StateManagement")

    static func logMutation(property: String, from oldValue: Any, to newValue: Any) {
        logger.debug("Mutasi State [\(property)]: '\(String(describing: oldValue))' -> '\(String(describing: newValue))'")
    }
}
```

Gunakan instrument `SwiftUI View Body` di Apple Instruments untuk melacak *Frame Drops* (hitch rate) yang disebabkan oleh evaluasi body berlebih.

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

```
┌─────────────────────┬───────────────────┬───────────────────────────────────────────┐
│ Property Wrapper    │ Tipe Entitas      │ Karakteristik Siklus Hidup                │
├─────────────────────┼───────────────────┼───────────────────────────────────────────┤
│ @State              │ Value (Struct)    │ Terikat pada View Node. Single SSOT lokal.│
│ @Binding            │ Reference Value   │ Derived pointer. Membaca & menulis SSOT.  │
│ @StateObject        │ Reference (Class) │ Instansiasi pertama; persist saat re-eval.│
│ @ObservedObject     │ Reference (Class) │ Non-owning pointer; bisa ter-reset parent.│
│ @Environment        │ System Values     │ Global per context tree via EnvironmentKey│
│ @Observable (Macro) │ Reference (Class) │ iOS 17+. Lacak keypath tingkat properti.  │
└─────────────────────┴───────────────────┴───────────────────────────────────────────┘
```

* **Golden Rule 1:** Jangan pernah membuat instance kelas di dalam deklarasi `@ObservedObject`.
* **Golden Rule 2:** Pastikan properti `@State` selalu berstatus `private`.
* **Golden Rule 3:** Jika Anda hanya butuh membaca data, teruskan nilai murni (`let value: T`), bukan `Binding<T>`.

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Basic (1–5)

1. **Apa yang terjadi pada memori struct View ketika fungsi `body` selesai dievaluasi?**  
   *A.* Struct View tetap hidup di memori selamanya sebagai representasi visual.  
   *B.* Struct View dihancurkan; hanya data yang dikelola oleh `DynamicProperty` yang bertahan di graph runtime.  
   *C.* Terjadi memory leak jika tidak dibungkus dengan `weak`.  
   *D.* View diubah secara otomatis menjadi objek UIView.

2. **Mengapa modifikator `@State` diwajibkan menggunakan kata kunci `private` menurut standar konvensi Apple?**  
   *A.* Untuk mencegah SwiftUI runtime mengakses memori tersebut.  
   *B.* Mengurangi collision nama pada Swift module.  
   *C.* Menegakkan prinsip Single Source of Truth sehingga inisialisasi eksternal tidak sengaja mengaburkan ownership.  
   *D.* Agar struct dapat dikonversi menjadi Class secara otomatis.

3. **Operasi mana yang dihasilkan oleh operator `$` pada properti `@State private var count: Int = 0`?**  
   *A.* Mengembalikan pointer unsafe C.  
   *B.* Mengembalikan `Binding<Int>`.  
   *C.* Mengubah tipe data menjadi String.  
   *D.* Menghancurkan alokasi heap dari variabel count.

4. **Kapan sebuah `@Binding` harus digunakan alih-alih `@State`?**  
   *A.* Saat view anak perlu memiliki dan menyimpan data secara permanen.  
   *B.* Saat komponen memerlukan akses read/write terhadap state milik view induk tanpa menyalin ownership data.  
   *C.* Hanya saat bekerja dengan background threads.  
   *D.* Saat memproses request jaringan JSON.

5. **Apa efek samping utama dari arsitektur `ObservableObject` klasik (iOS 13–16) dibanding Macro `@Observable` modern?**  
   *A.* `ObservableObject` tidak dapat dikompilasi di Xcode 15.  
   *B.* `ObservableObject` memicu pembaruan pada seluruh view yang mengamati dirinya, terlepas dari apakah properti yang dibaca view tersebut berubah atau tidak.  
   *C.* `ObservableObject` hanya berjalan di atas Swift Concurrency murni.  
   *D.* Macro `@Observable` membutuhkan dependency pihak ketiga dari luar Apple SDK.

---

### Soal Intermediate (6–10)

6. **Diberikan skenario: Sebuah child view menerima data via initializer: `MyChildView(val: myState)`. Jika di dalam `MyChildView` dideklarasikan `@State private var internalVal: Int`, dan diisi lewat `init(val: Int) { _internalVal = State(initialValue: val) }`. Apa yang terjadi saat nilai `myState` di parent berubah?**  
   *A.* `internalVal` pada child otomatis terbarui mengikuti `myState`.  
   *B.* Terjadi compile error karena accessing `_internalVal` dilarang.  
   *C.* `internalVal` mengabaikan perubahan parent karena backing storage `@State` tidak diinisialisasi ulang setelah instalasi node awal.  
   *D.* Aplikasi langsung mengalami deadlock crash.

7. **Mengapa memanggil modifikasi state langsung di dalam blok `var body: some View` menghasilkan runtime warning atau infinite rendering loop?**  
   *A.* Karena body dieksekusi di background thread.  
   *B.* Karena mutasi memicu invalidasi node AttributeGraph saat evaluasi render tree belum selesai, menyebabkan loop dependensi sirkular.  
   *C.* Karena CoreAnimation tidak mengizinkan alokasi struct di dalam blok computed property.  
   *D.* Karena body bersifat immutable secara compiler type-check.

8. **Bagaimana Macro `@Observable` di Swift 5.9 melacak properti mana yang dikonsumsi oleh sebuah View?**  
   *A.* Menggunakan parsing teks string pada kode program saat runtime.  
   *B.* Melalui intervensi dynamic runtime `ObservationRegistrar` yang mencatat KeyPath properti ketika fungsi get dieksekusi di dalam body view.  
   *C.* Menggunakan timer pooling frekuensi tinggi untuk mendeteksi perubahan nilai.  
   *D.* Mengharuskan pengembang mendaftarkan setiap properti ke dalam notification center.

9. **Apa risiko arsitektur jika sebuah instance `@ObservedObject` diinisialisasi secara lokal langsung di dalam deklarasi struct View (`@ObservedObject var vm = MyVM()`)?**  
   *A.* Siklus referensi siklik yang tidak dapat dilepaskan oleh ARC.  
   *B.* Nilai VM akan diinstansiasi ulang secara liar setiap kali parent view memicu evaluasi ulang body, menghilangkan seluruh state transien pengguna.  
   *C.* Kompiler Swift akan menolak kode dengan pesan error sintaks.  
   *D.* Tidak ada risiko; pendekatan ini adalah best practice resmi Apple.

10. **Bagaimana cara yang paling benar untuk mengoptimalkan performa sebuah hirarki View besar yang mengalami penurunan frame rate akibat perubahan state frekuensi tinggi?**  
    *A.* Mengubah semua struct View menjadi subclass UIView.  
    *B.* Menempatkan seluruh state ke dalam satu global singleton.  
    *C.* Memecah antarmuka menjadi sub-view kecil sehingga mutasi state frekuensi tinggi terlokalisasi hanya pada node daun (*leaf node*) yang membutuhkan render ulang.  
    *D.* Menghilangkan semua animasi dari aplikasi.

---

### Kunci Jawaban & Pembahasan

1. **B** — View structs bersifat transien (hanya representasi konfigurasi). Memori stack struct dibersihkan segera setelah dievaluasi, sementara data persistennya disimpan di runtime storage eksternal yang dikelola SwiftUI.
2. **C** — `@State` dirancang sebagai SSOT lokal. Memberikannya visibilitas publik melanggar enkapsulasi dan memicu mutasi dari luar tanpa sinkronisasi graph.
3. **B** — Simbol `$` memanggil `projectedValue` dari Property Wrapper yang menghasilkan binding dua arah (`Binding<Value>`).
4. **B** — `@Binding` adalah referensi pointer transparan yang meneruskan mutasi kembali ke SSOT yang dimiliki oleh komponen induk.
5. **B** — Combine `ObservableObject` memancarkan sinyal `objectWillChange` global per-objek, memicu re-render pada seluruh pengamat tanpa memandang properti mana yang dimodifikasi.
6. **C** — Inisialisasi `@State` hanya dieksekusi saat View Node pertama kali dibuat. Perubahan parameter view berikutnya tidak akan merekonstruksi backing storage tersebut.
7. **B** — Body harus bersifat *pure function*. Memodifikasi state di dalamnya memicu siklus: Body dievaluasi $\to$ State berubah $\to$ View kotor $\to$ Body dievaluasi ulang (infinite loop).
8. **B** — Macro `@Observable` menyuntikkan `ObservationRegistrar` yang secara otomatis melacak pembacaan properti spesifik via KeyPath tracking.
9. **B** — View struct dapat dibuat ulang kapan saja oleh runtime. `@ObservedObject` tidak mempertahankan kepemilikan memori persisten di luar siklus struct, sehingga instance akan terbuat ulang terus-menerus. Gunakan `@StateObject` atau modern `@State` + `@Observable`.
10. **C** — Mengisolasi state ke sub-view independen mempersempit cakupan invalidasi AttributeGraph hanya ke elemen visual yang benar-benar memerlukan pembaruan.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek: Real-Time Algorithmic Trading Execution Desk

#### Deskripsi
Bangun antarmuka terminal trading portofolio multi-aset yang responsif menggunakan pola arsitektur **Unidirectional Data Flow (UDF)** berbasis Macro `@Observable`.

#### Persyaratan Fungsional:
1. **Ticker Engine Berkecepatan Tinggi:**
   * Simulasikan fluktuasi harga acak dari 3 instrumen (misal: AAPL, BTC, ETH) dengan pembaruan setiap 200–500 milidetik via `AsyncTimerSequence` atau background Task.
2. **Portofolio Aggregator:**
   * Tampilkan metrik portofolio global (Total Equity, Unrealized PnL).
   * **Aturan Kritis:** Perubahan harga pada instrumen BTC **tidak boleh** memicu render ulang (invalidation body) pada baris instrumen AAPL atau ETH.
3. **Komponen Eksekusi Order (Child View):**
   * Sediakan panel geser (*Sheet*) untuk mengeksekusi order Beli/Jual. Panel ini menerima data harga terkini via `@Binding` atau `@Observable` terisolasi.
4. **Audit Validasi Performa:**
   * Sisipkan `Self._printChanges()` pada baris list instrumen dan buktikan di konsol Xcode bahwa pembaruan harga terisolasi secara sempurna pada masing-masing komponen baris saja.

#### Kriteria Keberhasilan Teknis:
* Tidak ada peringatan pembaruan state di luar main thread (*Strict Concurrency Check: Complete* terpenuhi tanpa warning).
* Tidak ada memory leak saat navigasi bolak-balik antara Portofolio Screen dan Order Execution Sheet (verifikasi menggunakan Xcode Memory Graph Debugger).
* Kode bersih dari anti-pattern: Tidak ada manipulasi state di dalam body dan seluruh binding mengarah ke satu SSOT definitif.