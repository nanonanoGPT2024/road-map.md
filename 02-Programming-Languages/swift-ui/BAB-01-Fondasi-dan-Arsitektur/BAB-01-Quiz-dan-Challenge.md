# BAB 01: Quiz, Challenge, & Knowledge Check
**Paradigma Deklaratif & Fondasi Runtime**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Ontologi Deklaratif vs Imperatif & Memory Layout
Jelaskan perbedaan mendasar antara representasi antarmuka pada UIKit (`UIView`/`UIViewController`) dan SwiftUI (`View`) ditinjau dari alokasi memori runtime (heap vs stack), siklus hidup instansiasi, dan dampaknya terhadap pencegahan *retain cycles* secara arsitektural. Mengapa desainer platform SwiftUI secara sengaja memilih `struct` (value type) alih-alih `class` (reference type)?

### Soal 1.2: Opaque Return Types & Static Type System
Dalam protokol `View`, properti `body` dideklarasikan dengan signature `var body: some View { get }`. 
1. Bedah secara mekanistis apa yang dilakukan kompilator Swift terhadap keyword `some` (*Opaque Return Type*) pada fase *type inference* dan *compile-time specialization*.
2. Apa konsekuensi arsitektural, performa (*layout engine optimization*), dan memori jika `some View` diganti secara universal menggunakan existential type `any View`?

### Soal 1.3: Dualisme Identitas: Structural vs Explicit Identity
SwiftUI mengandalkan dua mekanisme identitas untuk melacak representasi UI: *Structural Identity* dan *Explicit Identity*.
1. Jelaskan bagaimana runtime SwiftUI memanfaatkan *type tree* (seperti `_ConditionalContent<TrueContent, FalseContent>`) untuk memelihara *Structural Identity*.
2. Kapan Anda wajib menggunakan *Explicit Identity* (`.id(...)`), dan apa bahaya tersembunyi terhadap siklus hidup view (`@State` initialization, layout transitions, GPU rendering pipeline) jika modifier `.id()` di-inject dengan nilai dinamis yang berubah setiap siklus render?

### Soal 1.4: Fungsi Murni UI ($UI = f(State)$) dan Graph Invalidation
Paradigma deklaratif mendefinisikan UI sebagai fungsi deterministik dari state. Namun, deklarasi `var body: some View` dipanggil berulang kali sepanjang aplikasi berjalan.
1. Apakah eksekusi `body` setara dengan pembuatan ulang node visual grafika tingkat rendah (Metal/CoreAnimation layer)?
2. Jelaskan demarkasi antara *View Value Tree* (blueprint deklaratif sementara) dan *Backing Graph* (*AttributeGraph runtime*) yang persisten.

### Soal 1.5: Single Source of Truth & Dependency Invalidation Tracking
Bagaimana runtime SwiftUI mendeteksi bahwa sebuah `View` harus dievaluasi ulang ketika terjadi mutasi data? Jelaskan mekanisme *dynamic property registration* dan bagaimana koneksi dependency antara data source dan view node dibentuk saat runtime membaca nilai data di dalam scope eksekusi `body`.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Bedah Internal AttributeGraph Engine & Debugging via `_printChanges()`
SwiftUI menyembunyikan runtime mesin internal yang dikenal sebagai *AttributeGraph*.
1. Bagaimana cara kerja dependency tracking pada *AttributeGraph* dalam meminimalkan siklus rendering?
2. Ketika Anda memanggil metode internal `Self._printChanges()` di dalam blok `body`, informasi spesifik apa yang diekspos oleh compiler/runtime, dan bagaimana Anda menginterpretasikan output tersebut untuk mendiagnosis re-render yang tidak diinginkan (*spurious invalidations*)?

### Soal 2.2: The "Modifying State During View Update" Runtime Trap
Pertimbangkan skenario di mana seorang engineer menulis mutasi data `@State` secara tidak sengaja di dalam komputasi closure `body`, atau memanggil closure modifier yang mengeksekusi mutasi sebelum siklus layout selesai.
1. Secara internal, mengapa SwiftUI runtime langsung menghentikan eksekusi atau memicu peringatan ungu (*runtime warning*): *"Modifying state during view update, this will cause undefined behavior"*?
2. Bagaimana mekanisme siklus invalidasi memicu kondisi *infinite cycle loop* jika peringatan ini diabaikan?

### Soal 2.3: Type Erasure Penalty: Analisis Mikro-Arsitektur `AnyView`
Secara internal, `AnyView` membungkus concrete type ke dalam sebuah wrapper bertipe *existential container*.
1. Apa dampak `AnyView` terhadap alokasi memori (*heap boxing*) dan *vtable lookup/indirect dynamic dispatch*?
2. Mengapa penggunaan `AnyView` yang terlalu sering di level hierarki tinggi dapat melumpuhkan efisiensi algoritma *tree-diffing* SwiftUI runtime, dan memicu de-alokasi serta alokasi ulang komponen secara destruktif?

### Soal 2.4: Mekanisme Layout Pass, Layout Priority, dan Invalidation
Jelaskan algoritma negosiasi tata letak (*layout negotiation*) tiga langkah dalam siklus runtime SwiftUI:
1. *Parent proposes size*
2. *Child chooses its own size*
3. *Parent places the child in parent's coordinate space*
Bagaimana *Layout Neutrality*, *Hugging*, dan *Expansion Priority* bekerja pada container dasar (`VStack`, `HStack`, `ZStack`), serta apa implikasi komputasinya terhadap siklus frame rate (120 FPS / ProMotion) jika terdapat dependensi layout sirkular antar-anak komponen?

### Soal 2.5: Runtime Synchronization: `.task` vs `.onAppear` Lifecycle Desynchronization
Banyak pengembang menganggap modifier `.task` hanyalah alias untuk `.onAppear { Task { ... } }`.
1. Bedah siklus hidup *cooperative cancellation* pada modifier `.task` dan jelaskan bagaimana ia terikat langsung dengan *Structural Identity Lifetime* dari view terkait.
2. Identifikasi skenario edge-case pada virtualized containers (seperti `LazyVStack` di dalam `ScrollView`) di mana penggunaan `.onAppear` menyebabkan *memory leak* atau *race condition* eksekusi konkurensi saat pengguna melakukan *fast scrolling*.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: High-Frequency Ticker Jank pada Trading App
Sebuah aplikasi order-book crypto kelas institusional menerima payload data real-time via WebSocket dengan throughput 50 update per detik (setiap 20ms). Seluruh antarmuka layar transaksi dibangun menggunakan SwiftUI. 

Setelah implementasi, instrumen *Core Animation FPS* menunjukkan frame rate anjlok dari 120 FPS menjadi 18–25 FPS (*severe UI hanging*). Profiling menggunakan *Time Profiler* di Xcode Instruments menunjukkan bahwa thread utama (Main Thread) menghabiskan 78% waktu di pemanggilan fungsi internal `AG::Graph::UpdateValue` dan sub-rutin diffing runtime SwiftUI.

```swift
// Snippet representasi arsitektur bermasalah:
final class MarketDepthViewModel: ObservableObject {
    @Published var bids: [OrderBookEntry] = []
    @Published var asks: [OrderBookEntry] = []
    @Published var lastTradePrice: Double = 0.0
    @Published var volume24h: Double = 0.0
    // Dipanggil 50x per detik dari WebSocket background worker
    func didReceiveTick(depth: DepthPayload) {
        self.bids = depth.bids
        self.asks = depth.asks
        self.lastTradePrice = depth.lastPrice
        self.volume24h = depth.volume
    }
}

struct TradingDashboardView: View {
    @StateObject var viewModel: MarketDepthViewModel
    
    var body: some View {
        VStack {
            HeaderView(price: viewModel.lastTradePrice, volume: viewModel.volume24h)
            HStack {
                BidListView(bids: viewModel.bids)
                AskListView(asks: viewModel.asks)
            }
        }
    }
}
```

**Pertanyaan Diagnostik:**
1. Bedah akar penyebab struktural (*root cause*) mengapa pembaruan pada `lastTradePrice` memaksa runtime mengevaluasi ulang `BidListView` dan `AskListView` meskipun datanya tidak berubah.
2. Rancang arsitektur refactoring berbasis prinsip isolasi graf dependency untuk memitigasi bottleneck ini tanpa membatasi throughput WebSocket!

---

### Skenario B: Transient State Eviction pada Multi-Step Wizard Form
Sebuah aplikasi perbankan enterprise mengimplementasikan alur registrasi pembukaan rekening debit dengan sistem wizard multi-step. Setiap langkah memvalidasi identitas, input KYC, dan OTP. Pengembang mendesain alur navigasi menggunakan conditional branching sederhana pada root level view:

```swift
struct OnboardingContainerView: View {
    @State private var currentStep: WizardStep = .personalInfo
    
    var body: some View {
        VStack {
            switch currentStep {
            case .personalInfo:
                PersonalInfoStepView(onNext: { currentStep = .kycScan })
            case .kycScan:
                KYCStepView(onNext: { currentStep = .addressValidation })
            case .addressValidation:
                AddressStepView(onBack: { currentStep = .personalInfo }) // Bug terjadi di sini
            }
        }
    }
}

struct PersonalInfoStepView: View {
    let onNext: () -> Void
    @State private var fullName: String = ""
    @State private var idNumber: String = ""
    @FocusState private var isFieldFocused: Bool

    var body: some View {
        Form {
            TextField("Nama Lengkap", text: $fullName)
            TextField("Nomor KTP", text: $idNumber)
            Button("Lanjutkan", action: onNext)
        }
    }
}
```

**Insiden Produksi:**
Ketika nasabah berada di langkah `.addressValidation` dan menyentuh tombol "Kembali" ke `.personalInfo`, seluruh teks input yang sebelumnya diisi oleh pengguna hilang (*reset to blank*), keyboard interaktif tertutup secara glitchy, dan log analytics menandakan bahwa view instansiasi ulang terjadi secara destruktif.

**Pertanyaan Diagnostik:**
1. Mengapa transisi via `switch currentStep` menghancurkan `@State fullName` dan `@State idNumber` secara permanen? Jelaskan mekanisme internal *Structural Identity destruction* pada pohon view container.
2. Bagaimana Anda mendesain ulang skenario ini agar state formulir tetap persisten selama sesi navigasi berlangsung, namun tetap mempertahankan isolasi state lokal antarmuka secara elegan tanpa mengotori domain global?

---

### Skenario C: Desain Komponen Modular Design System & Trade-off "Dynamic Factory"
Sebuah tim arsitektur enterprise yang mengelola Core Design System ditugaskan membuat modul navigasi modular fleksibel. Salah satu Principal Engineer memajukan arsitektur "Dynamic Component Registry" di mana semua komponen UI diregistrasikan dan dikembalikan melalui generic factory pattern:

```swift
final class ComponentRegistry {
    static let shared = ComponentRegistry()
    private var builders: [String: (ComponentContext) -> AnyView] = [:]
    
    func register(type: String, builder: @escaping (ComponentContext) -> AnyView) {
        builders[type] = builder
    }
    
    func resolve(type: String, context: ComponentContext) -> AnyView {
        guard let builder = builders[type] else {
            return AnyView(EmptyView())
        }
        return builder(context)
    }
}

struct DynamicCardComponent: View {
    let componentType: String
    let context: ComponentContext
    
    var body: some View {
        ComponentRegistry.shared.resolve(type: componentType, context: context)
    }
}
```

Modul ini diintegrasikan ke dalam feed transaksi tak hingga (*infinite scroll list*) dengan variasi hingga 40 jenis sel kartu yang berbeda. Tak lama setelah peluncuran rilis staging, tim QA melaporkan *memory footprint* melonjak tajam (*steady leak-like pattern*), dan animasi ekspansi sel kartu mengalami *jitter* serta hilangnya animasi default fade/scale.

**Pertanyaan Diagnostik:**
1. Analisis kerugian komputasi dan arsitektural dari keputusan menggunakan `AnyView` di dalam generic factory untuk virtualized list view.
2. Rancang alternatif arsitektur berbasis *Compile-Time Type Preservation* (menggunakan *ViewBuilder*, *Generic Constraints*, atau protocol modular) yang memenuhi fleksibilitas register dinamis namun mempertahankan resolusi tipe konkret untuk runtime engine SwiftUI.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Diagnostic Profiler & Dynamic Identity Inspector

#### Deskripsi Masalah:
Dalam sistem berskala enterprise, tim sering kali tidak menyadari bahwa penulisan hierarki view yang buruk memicu evaluasi `body` yang eksesif. Anda ditugaskan membangun sebuah modul audit performa diagnostik zero-overhead berbasis compile-time wrapper yang mampu mendeteksi *identity churn* dan *re-render frequency* secara real-time langsung di atas kanvas perangkat.

#### Kebutuhan Fungsional (Requirements):
1. **Modifier Diagnostik Eksklusif Debug:**
   Bangun custom ViewModifier bernama `.diagnosticProfile(name: String, threshold: Int)` yang hanya aktif saat kompilasi `#if DEBUG`.
2. **Identity & Render Invalidation Counter:**
   - Melacak berapa kali properti `body` dari view sasaran dievaluasi ulang sejak instansiasi pertama.
   - Menginspeksi apakah identitas view tetap sama (*Structural Identity preservation*) atau telah dihancurkan/dibuat ulang (*Explicit/Destructive Re-creation*).
   - Memetakan properti apa yang menyebabkan invalidasi (mengintegrasikan kapabilitas inspeksi perubahan metadata state internal).
3. **Visual Frame HUD (Heads-Up Display):**
   - Render overlay garis tepi (border) tipis di sekeliling view:
     - **Hijau:** Render stabil (re-evaluation < threshold dalam interval 1 detik).
     - **Oranye:** Peringatan invalidasi tinggi (re-evaluation mencapai batas threshold).
     - **Merah Berkedip:** State cycle / Critical invalidation leak (render tak terbatas / identity reset).
   - Tampilkan badge numerik kecil di pojok kanan atas komponen yang mencantumkan total execution count dan status identitas.

#### Batasan Teknis (Constraints):
- **Zero Production Overhead:** Seluruh tracing infrastructure harus terhapus dari binary (*dead-code stripped*) pada release mode build tanpa meninggalkan runtime cost.
- **Pure Declarative Conformity:** Dilarang menggunakan UIKit fallback (`UIViewRepresentable`) untuk HUD overlay; semua harus diimplementasikan murni di atas SwiftUI engine runtime.
- **Strict Concurrency Safe:** Harus lolos analisis kompilasi Swift 6 Strict Concurrency (`CompleteChecking`), tanpa menimbulkan data races pada tracking counter.
- **Non-Destructive Invalidation:** Implementasi modifier tidak boleh mengotori (*dirtying*) atau memicu siklus invalidasi tambahan pada target view yang sedang diukur.

#### Expected Output:
Sebuah modul Swift terisolasi (`DiagnosticProfiler.swift`) yang siap diintegrasikan pada komponen target seperti contoh penggunaan berikut:

```swift
OrderBookRowView(entry: tradeEntry)
    .diagnosticProfile(name: "OrderBookRow", threshold: 10)
```

Sertakan arsitektur implementasi kode lengkap beserta penjelasan matematis bagaimana modifier Anda membaca identity footprint target tanpa merusak siklus hidup aslinya.

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk mengukur kesiapan pemahaman Anda sebelum melangkah ke Bab 02: Arsitektur Layout, Hierarki, & Negosiasi Dimensi.

### Saya harus memahami:
- [ ] Bahwa instans `View` pada SwiftUI adalah instruksi struktural alokasi stack sementara (*transient value type*), bukan komponen layar persisten.
- [ ] Cara kerja *AttributeGraph* sebagai mesin pelacak ketergantungan reaktif internal yang memelihara representasi visual aplikasi.
- [ ] Perbedaan deterministik antara *Structural Identity* (posisi hierarki tipe data) dan *Explicit Identity* (pengenal unik runtime via `.id()`).
- [ ] Mekanisme pemetaan kompilator Swift untuk *Opaque Return Types* (`some View`) dan bagaimana tipe komposit diekspresikan via `TupleView` atau `_ConditionalContent`.
- [ ] Bahwa operasi mutasi state di dalam body adalah pelanggaran arsitektur runtime deklaratif (*side-effect impurity*) yang menyebabkan siklus render tak terprediksi.
- [ ] Konsekuensi arsitektur dari *Type Erasure* via `AnyView` pada performa diffing algoritma SwiftUI dan siklus hidup representasi native backend.

### Saya tidak perlu menghafal:
- [ ] Nama-nama privat simbol C++ internal dari mesin *AttributeGraph* (`AG::Graph::...`).
- [ ] Seluruh variasi struktur internal privat yang dihasilkan compiler untuk kombinasi macro `@ViewBuilder`.
- [ ] Nilai bit-flag internal yang dialokasikan runtime Apple untuk penandaan render frame.

### Saya harus bisa melakukan:
- [ ] Mengidentifikasi dan menyelesaikan bottleneck UI Hangs menggunakan Xcode Instruments (*Time Profiler* & *SwiftUI View Body execution count*).
- [ ] Memecah arsitektur state yang terlalu terpusat (*monolithic state object*) menjadi granular state updates untuk mengisolasi invalidasi sub-tree.
- [ ] Menggunakan `Self._printChanges()` secara tepat untuk melacak property mana yang mengotori node grafika UI secara presisi.
- [ ] Menentukan kapan harus mempertahankan state input lokal melintasi navigasi dinamis tanpa memicu *identity eviction*.
- [ ] Melakukan refactoring dari penggunaan dinamis `AnyView` menjadi struktur generik berbasis tipe statis terkompilasi yang aman dan berperforma tinggi.