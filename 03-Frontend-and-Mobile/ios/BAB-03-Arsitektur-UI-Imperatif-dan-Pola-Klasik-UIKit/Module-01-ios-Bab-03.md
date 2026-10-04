# Bab 03 Module 01: Arsitektur UI Imperatif & Pola Klasik UIKit

---

## SEKSI 01 — IDENTITAS MODUL

* **Kategori Kurikulum:** 03-Frontend-and-Mobile
* **Jalur Spesialisasi:** iOS Senior & Staff Software Engineer
* **Kode Modul:** IOS-UIK-0301
* **Topik/Judul:** Arsitektur UI Imperatif & Pola Klasik UIKit
* **Prasyarat Pengetahuan:** 
  * Advanced Swift (ARC, Retain Cycles, Closures, Protocols, Generics)
  * Pemahaman Concurrency Dasar (Grand Central Dispatch, Main Thread Execution)
  * Dasar OS (Run Loop, Rendering Pipeline, Event Handling)
* **Tingkat Kesulitan:** Tingkat Lanjut (Advanced)
* **Estimasi Waktu Selesai:** 6 - 8 Jam Pembelajaran Mandiri & Lab Koding

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1. **Mendekonstruksi Paradigma Imperatif:** Mengontrol mutasi state view secara granular dan deterministik melalui manipulasi hierarki `UIView` dan siklus hidup `UIViewController`.
2. **Menguasai Siklus Hidup Layar UIKit Secara Presisi:** Memetakan alur komputasi dari inisialisasi (`init`), alokasi tampilan (`loadView`), konfigurasi hierarki (`viewDidLoad`), mutasi visibilitas (`viewWillAppear`, `viewDidAppear`), hingga dealokasi (`deinit`) tanpa kebocoran memori.
3. **Mengimplementasikan View Hierarchies Secara Murni Berbasis Kode (Programmatic UI):** Membangun UI modular, performan, dan merge-conflict free menggunakan Auto Layout engine murni (`NSLayoutConstraint`, Layout Anchors) tanpa Interface Builder (Storyboard/XIB).
4. **Mengeksekusi Pola Klasik Delegation & Responder Chain:** Mengalirkan event UI, gestur, dan aksi responder secara decoupled dengan protokol delegate yang type-safe dan memory-safe (`weak ref`).
5. **Mendiagnosis Masalah Rendering & Thread Safety:** Mengidentifikasi dan memitigasi thread violation, hitching render pipeline (Core Animation commit), serta optimasi off-screen rendering pada aplikasi enterprise berskala besar.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam paradigma **deklaratif** (seperti SwiftUI atau React), developer mendefinisikan *apa* yang harus ditampilkan sebagai fungsi dari state ($UI = f(State)$), dan framework menangani mutasi struktural di balik layar via virtual tree reconciliation.

Sebaliknya, **UIKit adalah framework imperatif berbasis graf objek mutabel yang stateful**. Mental model UIKit dapat diibaratkan sebagai **mandor konstruksi fisik**:

```
+--------------------------------------------------------------------------+
|                        MENTAL MODEL: UIKIT                               |
|                                                                          |
|   [State Berubah] ---> [Developer Mengambil Objek Spesifik di Memori]   |
|                                  |                                       |
|                                  v                                       |
|                  [Mengeksekusi Perintah Mutasi]                          |
|                  (e.g., label.text = "X", view.addSubview(y))            |
|                                  |                                       |
|                                  v                                       |
|               [Meminta Relayout & Redraw Secara Eksplisit]               |
|               (setNeedsLayout(), layoutIfNeeded(), setNeedsDisplay())    |
+--------------------------------------------------------------------------+
```

1. **Objek Bertahan Lama (Long-lived Objects):** `UIView` dan `UIViewController` adalah instance kelas (tipe referensi / `class`) yang dialokasikan di heap dan tetap hidup sampai dilepaskan secara eksplisit dari hierarki atau kontainernya.
2. **Kepemilikan Eksplisit (Deterministic Mutability):** Anda bertanggung jawab penuh untuk menambahkan (`addSubview`), menghapus (`removeFromSuperview`), memperbarui frame, dan membersihkan event handler. Mutasi state yang terlewat tidak akan diperbaiki secara otomatis oleh runtime UIKit.
3. **Pemisahan Logika & Representasi:** `UIViewController` bertindak sebagai koordinator orkestrasi; `UIView` menangani komputasi layout dan input event parsing; sedangkan layer dasar (`CALayer`) menangani rendering grafis piksel aktual melalui GPU.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### 1. UIKit ViewController Lifecycle Pipeline

Siklus hidup internal `UIViewController` memetakan transformasi dari inisialisasi memori hingga terminasi visual.

```
       [ Instansiasi: init(nibName:bundle:) / init(coder:) / init(...) ]
                                      |
                                      v
                               [ loadView() ]
            (Membuat hierarki root view; fallback ke default jika kosong)
                                      |
                                      v
                             [ viewDidLoad() ]
        (View dialokasikan di RAM; inisialisasi setup statis & binding awal)
                                      |
                                      v
                         +---> [ viewWillAppear() ]
                         |  (Tampilan akan masuk ke window tree)
                         |            |
                         |            v
                         |   [ viewWillLayoutSubviews() ]
                         |            |
                         |            v
                         |    [ layoutSubviews() ]
                         |  (Auto Layout Engine menyelesaikan constraints)
                         |            |
                         |            v
                         |   [ viewDidLayoutSubviews() ]
                         |  (Frame final terbentuk, ukuran bounding box valid)
                         |            |
                         |            v
                         |    [ viewDidAppear() ]
                         |  (Layar aktif; animasi & telemetri dimulai)
                         |            |
                         |            +-----------------------+
                         |                                    |
                         | (Transisi Balik / Tampil Ulang)    | (Transisi Keluar / Dismiss)
                         |                                    v
                         |                           [ viewWillDisappear() ]
                         |                                    |
                         |                                    v
                         |                            [ viewDidDisappear() ]
                         +------------------------------------+
                                      |
                         (Dihapus permanen dari navigasi)
                                      v
                                  [ deinit ]
               (Dealokasi heap, invalidasi timer, pembersihan observer)
```

### 2. UI Event & Responder Chain Flow

Ketika interaksi fisik (sentuhan) terjadi pada layar kaca perangkat, subsistem kernel I/O Kit mengirimkan event ke SpringBoard, diteruskan ke thread aplikasi melalui port Mach, dan diproses oleh `UIApplication` menggunakan algoritma *Hit-Testing*.

```
   [ User Touch ]
         |
         v
   [ IOKit.framework ]  --->  [ SpringBoard ]  --->  [ Mach Port IPC ]
                                                            |
                                                            v
                                                   [ UIApplication ]
                                                            |
                                                            v
                                                    [ UIWindow ]
                                                            |
                                                 (hitTest:withEvent:)
                                                            |
                                                            v
      [ Root View ] ---> [ Container View ] ---> [ Leaf Subview (Button) ]
                                                            |
                                              (Hit Target Ditemukan!)
                                                            |
   <===================== Responder Chain Bubbling =========+
   | (Jika target tidak menangani UIEvent, oper ke parent / next responder)
   |
   +---> [ Leaf Subview ]
            |
            v (next)
         [ Container View ]
            |
            v (next)
         [ UIViewController ]
            |
            v (next)
         [ UIWindow ]
            |
            v (next)
         [ UIApplication ]
            |
            v (next)
         [ UIApplicationDelegate ] (Event dibuang jika tak tertangani)
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### Hubungan UIView, CALayer, dan Render Tree

Setiap `UIView` di UIKit memiliki satu layer pendukung (`CALayer`) yang dapat diakses melalui properti `.layer`. Pemisahan ini merupakan manifestasi arsitektural dari prinsip *Single Responsibility*:

* **`UIView` (Handling Logic & Layout):** Berada di namespace `UIKit`. Bertanggung jawab atas hit-testing, gesture recognition, integrasi Auto Layout, dan aksesibilitas. Beroperasi di Main Run Loop (`Thread 1`).
* **`CALayer` (Visual Content & Compositing):** Berada di namespace `QuartzCore` (Core Animation). Tidak memahami event touch responder. Menyimpan buffer piksel bitmap, geometri layer (`anchorPoint`, `position`, `transform3D`), masker visual, border, dan bayangan.

```
       UIView Layer Hierarchy                       Render Server Pipeline
  +-------------------------------+         +------------------------------------+
  |            UIView             |         |          Main Thread App           |
  |  - Auto Layout Engine         |         |  1. Layout (layoutSubviews)        |
  |  - UIResponder (Touch handling|         |  2. Display (drawRect/contents)    |
  |  - Accessibility Tree         |         |  3. Prepare (Image decode)         |
  +---------------+---------------+         |  4. Commit (Serialize tree state) |
                  | owns 1:1                +-----------------+------------------+
                  v                                           |
  +-------------------------------+                           | IPC (Mach Port)
  |            CALayer            |                           v
  |  - backing store (Bitmap)     |         +------------------------------------+
  |  - affine / 3D transform      |         |          Render Server             |
  |  - animations & shaders       | ======> |  - OpenGL ES / Metal Pipeline      |
  +-------------------------------+         |  - Layer Tree Rasterization        |
                                            +-----------------+------------------+
                                                              |
                                                              v
                                                    [ GPU Framebuffer ]
                                                              |
                                                              v
                                                    [ Physical Display ]
```

### Mekanisme Internal Layout Pass

Sistem Auto Layout bekerja dengan mesin pemecah pertidaksamaan linear bernama **Cassowary Algorithm**. Siklus update layout terdiri dari tiga fase terpisah:

1. **Constraints Updating (Update Pass):** Mesin berjalan bottom-up. Memanggil `updateConstraints()` dan `updateViewConstraints()`. Terjadi ketika nilai prioritas atau konstanta constraint berubah.
2. **Layout Engine Solution (Layout Pass):** Mesin berjalan top-down. Berdasarkan solusi Cassowary yang dihasilkan, sistem menghitung frame definitif (origin `(x, y)` dan size `(width, height)`) lalu mengaplikasikannya ke properti `bounds` dan `center` dari `CALayer`. Menembus siklus internal `layoutSubviews()`.
3. **Display Pass (Render Pass):** Jika ada view yang mengimplementasikan `draw(_ rect: CGRect)` atau memiliki dirty bitmap flag, sistem memanggil engine Core Graphics untuk me-rasterisasi konten ke memory buffer GPU.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### 1. `loadView()` vs `viewDidLoad()`

Salah satu miskonsepsi paling umum adalah instansiasi view kustom di dalam `viewDidLoad()`. 

* `loadView()`: Fungsi ini adalah tempat di mana properti `.view` dari `UIViewController` diciptakan. Jika Anda menggunakan pendekatan programmatic total tanpa Storyboard/XIB, **Anda wajib meng-override method ini** untuk menetapkan view kustom ke root view, tanpa memanggil `super.loadView()`.
* `viewDidLoad()`: Dipanggil tepat setelah instansiasi root view selesai dan dialokasikan ke memori. Pada titik ini, hierarki utama sudah stabil. Tempat ini dikhususkan untuk konfigurasi dependensi model, observer, dan fetching data jaringan awal.

### 2. Auto Layout Life Cycle: `setNeedsLayout()` vs `layoutIfNeeded()`

* `setNeedsLayout()`: Mengaktifkan flag *dirty* internal pada view. Method ini sangat murah secara komputasional (*asynchronous*). Sistem menandai bahwa view memerlukan pass layout ulang, yang akan diproses secara batch pada siklus Main Run Loop berikutnya.
* `layoutIfNeeded()`: Memaksa layout engine untuk mengeksekusi layout pass secara instan (*synchronous*) jika flag dirty aktif. Jika tidak ada perubahan constraint atau flag dirty tidak aktif, fungsi ini menghasilkan operasi nol. Teknik ini wajib dipanggil di dalam blok `UIView.animate` ketika menganimasikan constraint.

### 3. Hit-Testing Engine Algorithm

Algoritma hit-testing internal `UIView` mencari responder terdalam menggunakan teknik traversal *Depth-First Search (Pre-order)* terbalik:

```swift
// Representasi pseudocode algoritma internal UIKit:
func hitTest(_ point: CGPoint, with event: UIEvent?) -> UIView? {
    guard isUserInteractionEnabled, !isHidden, alpha > 0.01 else { return nil }
    guard self.point(inside: point, with: event) else { return nil }
    
    // Iterasi mundur dari subview paling depan (Z-Index tertinggi)
    for subview in subviews.reversed() {
        let convertedPoint = subview.convert(point, from: self)
        if let hitView = subview.hitTest(convertedPoint, with: event) {
            return hitView
        }
    }
    return self
}
```

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi programmatic UI murni tanpa interface builder yang mendemonstrasikan segregasi tanggung jawab: View kustom independen yang dihubungkan ke UIViewController via `loadView()`.

```swift
import UIKit

// MARK: - 1. Custom Programmatic View
final class ProfileSummaryView: UIView {
    
    // Komponen UI privat (Encapsulation)
    private let avatarImageView: UIImageView = {
        let imageView = UIImageView()
        imageView.translatesAutoresizingMaskIntoConstraints = false
        imageView.contentMode = .scaleAspectFill
        imageView.layer.cornerRadius = 40
        imageView.clipsToBounds = true
        imageView.backgroundColor = .systemGray5
        return imageView
    }()
    
    private let nameLabel: UILabel = {
        let label = UILabel()
        label.translatesAutoresizingMaskIntoConstraints = false
        label.font = UIFont.systemFont(ofSize: 18, weight: .bold)
        label.textColor = .label
        return label
    }()
    
    private let followButton: UIButton = {
        let button = UIButton(type: .system)
        button.translatesAutoresizingMaskIntoConstraints = false
        button.setTitle("Ikuti", for: .normal)
        button.titleLabel?.font = UIFont.systemFont(ofSize: 14, weight: .semibold)
        button.backgroundColor = .systemBlue
        button.setTitleColor(.white, for: .normal)
        button.layer.cornerRadius = 8
        return button
    }()
    
    // Callback event berbasis closure / delegation
    var onFollowButtonTapped: (() -> Void)?

    // Designated Initializer untuk pembuatan berbasis kode
    override init(frame: CGRect) {
        super.init(frame: frame)
        setupViewHierarchies()
        setupConstraints()
        setupEventActions()
    }

    // Required Initializer untuk NSCoding / Storyboard blocker
    @available(*, unavailable, message: "Inisialisasi via Storyboard/XIB tidak didukung.")
    required init?(coder: NSCoder) {
        fatalError("Gunakan init(frame:) untuk Programmatic UI.")
    }

    private func setupViewHierarchies() {
        backgroundColor = .systemBackground
        addSubview(avatarImageView)
        addSubview(nameLabel)
        addSubview(followButton)
    }

    private func setupConstraints() {
        NSLayoutConstraint.activate([
            // Layout Avatar Image
            avatarImageView.leadingAnchor.constraint(equalTo: leadingAnchor, constant: 16),
            avatarImageView.topAnchor.constraint(equalTo: safeAreaLayoutGuide.topAnchor, constant: 16),
            avatarImageView.widthAnchor.constraint(equalToConstant: 80),
            avatarImageView.heightAnchor.constraint(equalToConstant: 80),

            // Layout Name Label
            nameLabel.leadingAnchor.constraint(equalTo: avatarImageView.trailingAnchor, constant: 16),
            nameLabel.trailingAnchor.constraint(equalTo: trailingAnchor, constant: -16),
            nameLabel.topAnchor.constraint(equalTo: avatarImageView.topAnchor, constant: 8),

            // Layout Follow Button
            followButton.leadingAnchor.constraint(equalTo: nameLabel.leadingAnchor),
            followButton.widthAnchor.constraint(equalToConstant: 100),
            followButton.heightAnchor.constraint(equalToConstant: 36),
            followButton.topAnchor.constraint(equalTo: nameLabel.bottomAnchor, constant: 8)
        ])
    }
    
    private func setupEventActions() {
        followButton.addTarget(self, action: #selector(handleFollowTap), for: .touchUpInside)
    }
    
    @objc private func handleFollowTap() {
        onFollowButtonTapped?()
    }

    func configure(name: String, image: UIImage?) {
        nameLabel.text = name
        avatarImageView.image = image
    }
}

// MARK: - 2. UIViewController Implementation
final class ProfileSummaryViewController: UIViewController {
    
    private var customView: ProfileSummaryView {
        guard let view = view as? ProfileSummaryView else {
            fatalError("Root View harus bertipe ProfileSummaryView")
        }
        return view
    }

    // Overriding loadView() untuk menetapkan view programmatic sebagai Root View
    override func loadView() {
        self.view = ProfileSummaryView()
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        bindEvents()
        renderInitialData()
    }

    private func bindEvents() {
        customView.onFollowButtonTapped = { [weak self] in
            self?.processFollowAction()
        }
    }

    private func renderInitialData() {
        customView.configure(name: "Alexander Pratama", image: nil)
    }

    private func processFollowAction() {
        print("Tindakan follow diproses oleh ViewController.")
    }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis Kelas `ProfileSummaryView`

* **Baris 7–29:** Konstruksi closure instansiasi inline (`avatarImageView`, `nameLabel`, `followButton`).
  * `translatesAutoresizingMaskIntoConstraints = false`: **Krusial.** Menginstruksikan sistem untuk tidak mengonversi `UIView.autoresizingMask` (sistem springs and struts peninggalan lawas) menjadi Auto Layout constraints otomatis. Jika bernilai `true`, constraint sistem akan bentrok (*conflict crash*) dengan constraints kustom yang kita buat.
* **Baris 38–41:** `override init(frame: CGRect)` adalah designated initializer murni. Semua manipulasi hierarki dan penambahan constraint dijalankan di sini secara deterministik sebelum view disajikan.
* **Baris 44–46:** `@available(*, unavailable)` digabung dengan `fatalError` pada `init?(coder:)`. Praktik ini mencegah instansiasi ilegal dari storyboard, memastikan integritas *code-only approach*.
* **Baris 54–73:** `NSLayoutConstraint.activate([...])`: Mengompilasi dan mengaktifkan batch constraint secara atomik. Ini jauh lebih optimal dibanding mengeset `isActive = true` satu per satu, karena sistem internal Cassowary hanya perlu menyelesaikan persamaan constraint satu kali untuk seluruh batch array.
* **Baris 60:** `.safeAreaLayoutGuide.topAnchor`: Menjamin constraint merujuk pada area visibilitas layar di bawah notch/Dynamic Island dan status bar, bukan frame absolut perangkat.

### Analisis Kelas `ProfileSummaryViewController`

* **Baris 89–94:** Force-casting terselubung aman via computed property `customView`. Mengeliminasi kebutuhan `view.` casting berulang kali di seluruh controller.
* **Baris 97–99:** `override func loadView()`:
  * Tidak ada pemanggilan `super.loadView()`. Memanggil super akan membuat UIView default kosong dan membuang resource alokasi CPU secara percuma.
  * Inisialisasi eksplisit `self.view = ProfileSummaryView()`.
* **Baris 108:** `[weak self]` capture list pada closure callback: Mencegah *strong reference cycle* (retain cycle) antara `ViewController -> ProfileSummaryView -> Closure -> ViewController`.

---

## SEKSI 09 — STUDI KASUS NYATA

### Konteks Produksi Enterprise
Dalam aplikasi perbankan digital skala besar (Fintech), layar **Transfer & Validasi Transaksi** harus memenuhi kriteria non-fungsional yang ketat:
1. **Zero UI Glitch & Zero Storyboard:** Kinerja layout harus instan tanpa deserialisasi XML yang memakan I/O disk.
2. **Kepatuhan Form Validasi Realtime:** Setiap perubahan karakter pada input nominal harus menghitung ulang limit transfer, biaya admin, serta status aktifasi tombol konfirmasi.
3. **Decoupled Architecture:** Tampilan tidak boleh mengetahui logika jaringan atau parsing mata uang; seluruh aksi didelegasikan melalui kontrak protokol yang dapat diuji via mock unit-test.
4. **Resilient Memory Layout:** Penghancuran layar pasca-transaksi harus membersihkan seluruh pointer responder dari memori untuk mencegah kebocoran saldo/token otentikasi.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Arsitektur produksi: Penerapan pola **Classic Delegation & Pure Programmatic UI** pada modul transfer bank tingkat enterprise.

```swift
import UIKit

// MARK: - 1. Domain Protocols & Delegate Contracts
protocol TransactionInputDelegate: AnyObject {
    func transactionInputDidUpdate(amount: Decimal, isValid: Bool)
    func transactionDidTriggerExecution()
}

// MARK: - 2. Programmatic Production View
final class TransactionScreenView: UIView {
    
    weak var delegate: TransactionInputDelegate?
    private let transferLimit: Decimal = 50_000_000.00
    
    // UI Elements
    private let containerScrollView: UIScrollView = {
        let scrollView = UIScrollView()
        scrollView.translatesAutoresizingMaskIntoConstraints = false
        scrollView.keyboardDismissMode = .interactive
        scrollView.alwaysBounceVertical = true
        return scrollView
    }()
    
    private let contentView: UIView = {
        let view = UIView()
        view.translatesAutoresizingMaskIntoConstraints = false
        return view
    }()
    
    private let headerLabel: UILabel = {
        let label = UILabel()
        label.translatesAutoresizingMaskIntoConstraints = false
        label.text = "Nominal Transfer"
        label.font = UIFont.preferredFont(forTextStyle: .subheadline)
        label.textColor = .secondaryLabel
        return label
    }()
    
    private let amountTextField: UITextField = {
        let textField = UITextField()
        textField.translatesAutoresizingMaskIntoConstraints = false
        textField.font = UIFont.systemFont(ofSize: 32, weight: .bold)
        textField.keyboardType = .numberPad
        textField.placeholder = "0"
        textField.textColor = .label
        return textField
    }()
    
    private let errorLabel: UILabel = {
        let label = UILabel()
        label.translatesAutoresizingMaskIntoConstraints = false
        label.font = UIFont.preferredFont(forTextStyle: .caption1)
        label.textColor = .systemRed
        label.numberOfLines = 0
        label.isHidden = true
        return label
    }()
    
    private lazy var executeButton: UIButton = {
        var configuration = UIButton.Configuration.filled()
        configuration.baseBackgroundColor = .systemGreen
        configuration.title = "Konfirmasi Transfer"
        configuration.cornerStyle = .medium
        
        let button = UIButton(configuration: configuration)
        button.translatesAutoresizingMaskIntoConstraints = false
        button.isEnabled = false
        return button
    }()
    
    // MARK: - Lifecycle & Initialization
    override init(frame: CGRect) {
        super.init(frame: frame)
        setupHierarchy()
        setupConstraints()
        setupListeners()
    }
    
    @available(*, unavailable)
    required init?(coder: NSCoder) {
        fatalError("Inisialisasi IB tidak diizinkan.")
    }
    
    // MARK: - Subviews Setup
    private func setupHierarchy() {
        backgroundColor = .systemBackground
        addSubview(containerScrollView)
        containerScrollView.addSubview(contentView)
        
        contentView.addSubview(headerLabel)
        contentView.addSubview(amountTextField)
        contentView.addSubview(errorLabel)
        addSubview(executeButton) // Mengambang di safe area bawah
    }
    
    private func setupConstraints() {
        // Kontrak ScrollView dengan Content & Frame Guides
        let contentLayout = containerScrollView.contentLayoutGuide
        let frameLayout = containerScrollView.frameLayoutGuide
        
        NSLayoutConstraint.activate([
            // ScrollView Constraints
            containerScrollView.topAnchor.constraint(equalTo: safeAreaLayoutGuide.topAnchor),
            containerScrollView.leadingAnchor.constraint(equalTo: leadingAnchor),
            containerScrollView.trailingAnchor.constraint(equalTo: trailingAnchor),
            containerScrollView.bottomAnchor.constraint(equalTo: executeButton.topAnchor, constant: -16),
            
            // Frame Constraints: Memastikan content scroll memiliki lebar identik dengan frame
            contentView.topAnchor.constraint(equalTo: contentLayout.topAnchor),
            contentView.leadingAnchor.constraint(equalTo: contentLayout.leadingAnchor),
            contentView.trailingAnchor.constraint(equalTo: contentLayout.trailingAnchor),
            contentView.bottomAnchor.constraint(equalTo: contentLayout.bottomAnchor),
            contentView.widthAnchor.constraint(equalTo: frameLayout.widthAnchor),
            
            // Konten Form Internal
            headerLabel.topAnchor.constraint(equalTo: contentView.topAnchor, constant: 24),
            headerLabel.leadingAnchor.constraint(equalTo: contentView.leadingAnchor, constant: 20),
            headerLabel.trailingAnchor.constraint(equalTo: contentView.trailingAnchor, constant: -20),
            
            amountTextField.topAnchor.constraint(equalTo: headerLabel.bottomAnchor, constant: 8),
            amountTextField.leadingAnchor.constraint(equalTo: headerLabel.leadingAnchor),
            amountTextField.trailingAnchor.constraint(equalTo: headerLabel.trailingAnchor),
            amountTextField.heightAnchor.constraint(equalToConstant: 48),
            
            errorLabel.topAnchor.constraint(equalTo: amountTextField.bottomAnchor, constant: 6),
            errorLabel.leadingAnchor.constraint(equalTo: headerLabel.leadingAnchor),
            errorLabel.trailingAnchor.constraint(equalTo: headerLabel.trailingAnchor),
            errorLabel.bottomAnchor.constraint(equalTo: contentView.bottomAnchor, constant: -24),
            
            // Action Button Sticky Anchor
            executeButton.leadingAnchor.constraint(equalTo: leadingAnchor, constant: 20),
            executeButton.trailingAnchor.constraint(equalTo: trailingAnchor, constant: -20),
            executeButton.bottomAnchor.constraint(equalTo: keyboardLayoutGuide.topAnchor, constant: -16),
            executeButton.heightAnchor.constraint(equalToConstant: 50)
        ])
    }
    
    private func setupListeners() {
        amountTextField.addTarget(self, action: #selector(textDidChange), for: .editingChanged)
        executeButton.addTarget(self, action: #selector(executeButtonTapped), for: .touchUpInside)
    }
    
    @objc private func textDidChange() {
        let rawText = amountTextField.text ?? ""
        let numericValue = Decimal(string: rawText) ?? Decimal.zero
        
        let isValid = validateInput(amount: numericValue)
        delegate?.transactionInputDidUpdate(amount: numericValue, isValid: isValid)
    }
    
    private func validateInput(amount: Decimal) -> Bool {
        if amount <= 0 {
            hideError()
            executeButton.isEnabled = false
            return false
        }
        
        if amount > transferLimit {
            showError("Maksimal transfer harian Rp 50.000.000")
            executeButton.isEnabled = false
            return false
        }
        
        hideError()
        executeButton.isEnabled = true
        return true
    }
    
    private func showError(_ message: String) {
        errorLabel.text = message
        errorLabel.isHidden = false
    }
    
    private func hideError() {
        errorLabel.text = nil
        errorLabel.isHidden = true
    }
    
    @objc private func executeButtonTapped() {
        amountTextField.resignFirstResponder()
        delegate?.transactionDidTriggerExecution()
    }
}

// MARK: - 3. Production View Controller
final class TransactionViewController: UIViewController {
    
    private var transactionView: TransactionScreenView {
        guard let view = view as? TransactionScreenView else {
            fatalError("Sistem root view tidak valid.")
        }
        return view
    }
    
    private var currentAmount: Decimal = .zero
    
    override func loadView() {
        self.view = TransactionScreenView()
    }
    
    override func viewDidLoad() {
        super.viewDidLoad()
        setupNavigation()
        setupDelegation()
    }
    
    private func setupNavigation() {
        title = "Kirim Dana"
        navigationController?.navigationBar.prefersLargeTitles = false
    }
    
    private func setupDelegation() {
        transactionView.delegate = self
    }
}

// MARK: - 4. Delegate Protocol Conformance
extension TransactionViewController: TransactionInputDelegate {
    
    func transactionInputDidUpdate(amount: Decimal, isValid: Bool) {
        self.currentAmount = amount
    }
    
    func transactionDidTriggerExecution() {
        let alert = UIAlertController(
            title: "Verifikasi Transaksi",
            message: "Apakah Anda yakin mentransfer sejumlah Rp \(currentAmount)?",
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: "Batal", style: .cancel))
        alert.addAction(UIAlertAction(title: "Lanjutkan", style: .default, handler: { [weak self] _ in
            self?.submitToBackend()
        }))
        present(alert, animated: true)
    }
    
    private func submitToBackend() {
        // Implementasi integrasi network layer / Clean Architecture UseCase
        print("Mengirim payload transfer: \(currentAmount) ke API Gateway.")
    }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Aspek Komparasi | Pure Programmatic Auto Layout | Interface Builder (Storyboard/XIB) | SwiftUI (Modern Declarative) |
| :--- | :--- | :--- | :--- |
| **Penyelesaian Merge Conflicts** | **Sangat Baik.** Kode berupa Swift murni; diff Git terlihat jelas baris per baris. | **Buruk.** Dokumen XML monolitik yang mudah korup jika dimodifikasi concurrent. | **Sangat Baik.** Kode berupa Swift DSL deklaratif modular. |
| **Waktu Inisialisasi & Startup (TTI)** | **Paling Cepat.** Mengompilasi langsung ke native assembly tanpa parsing XML I/O. | **Lambat.** Overhead deserialisasi XML via runtime nib loader. | **Sangat Cepat.** Tipe value (struct) ultra-ringan dialokasikan di stack. |
| **Kompilasi & Type-Safety** | **Tinggi.** Kesalahan compiler terdeteksi seketika saat build time. | **Nol.** Crash runtime jika outlet/action terputus (`setValue:forUndefinedKey:`). | **Paling Tinggi.** Static typing mutlak pada state binding dan modifiers. |
| **Refactoring Agility** | **Tinggi.** Dukungan penuh terhadap engine refactoring Xcode (Rename, Extract Method). | **Sangat Rendah.** Perubahan nama kelas sering kali merusak relasi XIB. | **Tinggi.** Mudah diekstrak menjadi reusable subviews via View protocol. |
| **Inspeksi Visual & Preview** | **Sedang.** Bergantung pada memory canvas Canvas / injection tools eksternal. | **Tinggi.** Visual design canvas langsung di dalam Xcode. | **Paling Tinggi.** Real-time visual canvas interaktif melalui Swift Previews. |
| **Overhead Kurva Belajar** | **Tinggi.** Memerlukan visualisasi mental koordinat dan aturan constraint sistem. | **Rendah.** Ramah bagi developer pemula (Drag and drop visual). | **Menengah.** Paradigma fungsional & data-driven reactivity (Combine/Observation). |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The ScrollView Layout Ambiguity Edge Case
* **Pitfall:** `UIScrollView` memiliki dua pasang dimensi independen: ukuran viewport (`frameLayoutGuide`) dan ukuran area konten yang dapat digulir (`contentLayoutGuide`). Memasang constraint subview langsung ke `leading/trailing` ScrollView tanpa anchor guide modern menyebabkan sistem Auto Layout tidak dapat menentukan content size secara ambigu.
* **Mitigasi:** Gunakan `contentLayoutGuide` untuk menentukan batas scroll, dan kunci salah satu aksis dengan `frameLayoutGuide` (misal: `contentView.widthAnchor.constraint(equalTo: frameLayoutGuide.widthAnchor)` untuk mematikan scroll horizontal).

### 2. Auto Layout Unsatisfiable Constraints Churn
* **Pitfall:** Menambahkan constraints yang saling bertentangan secara matematis dengan prioritas `.required` (1000). Hal ini menyebabkan runtime melempar log konsol masif dan membuang constraint acak, yang merusak tampilan dan memicu CPU spike pada Cassowary engine.
* **Mitigasi:** Turunkan prioritas constraint fleksibel menjadi `.defaultHigh` (750) atau buat relasi ketidaksamaan (`greaterThanOrEqualTo`).

### 3. Asynchronous Image Binding Race Condition pada Subview
* **Pitfall:** Jika view kustom digunakan kembali (seperti dalam list atau recycled views), operasi pemuatan gambar asinkron dapat menetapkan bitmap lama ke layout yang baru.
* **Mitigasi:** Simpan token pembatalan (misal: `UUID` atau `URLSessionDataTask`) dan batalkan/reset task di dalam method `prepareForReuse()` atau sebelum binding baru dilakukan.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Lupa Mematikan `translatesAutoresizingMaskIntoConstraints`
```swift
// SALAH:
let button = UIButton()
view.addSubview(button)
button.leadingAnchor.constraint(equalTo: view.leadingAnchor).isActive = true
// Crash / Glitch: Autoresizing Mask otomatis bertabrakan dengan constraint eksplisit!

// BENAR:
let button = UIButton()
button.translatesAutoresizingMaskIntoConstraints = false
view.addSubview(button)
button.leadingAnchor.constraint(equalTo: view.leadingAnchor).isActive = true
```

### 2. Mengakses Properti `view` Terlalu Dini pada Inisialisasi Controller
```swift
// SALAH:
final class Coordinator {
    func start() {
        let vc = TransactionViewController()
        vc.view.backgroundColor = .white // MEMICU LOADVIEW() PREMATUR!
        // viewDidLoad() tereksekusi sebelum dependensi diinjeksi secara utuh.
    }
}

// BENAR:
final class Coordinator {
    func start() {
        let vc = TransactionViewController()
        // Biarkan lifecycle UIKit memicu loadView() saat controller disajikan (push/present).
        navigationController.pushViewController(vc, animated: true)
    }
}
```

### 3. Mengabaikan Strong Reference pada Protokol Delegate
```swift
// SALAH:
protocol TransactionInputDelegate { // Tidak restricted ke AnyObject/class
    func transactionDidTriggerExecution()
}
final class TransactionScreenView: UIView {
    var delegate: TransactionInputDelegate? // TIDAK BISA WEAK -> Memory Leak!
}

// BENAR:
protocol TransactionInputDelegate: AnyObject { // Class-bound protocol
    func transactionDidTriggerExecution()
}
final class TransactionScreenView: UIView {
    weak var delegate: Transaction