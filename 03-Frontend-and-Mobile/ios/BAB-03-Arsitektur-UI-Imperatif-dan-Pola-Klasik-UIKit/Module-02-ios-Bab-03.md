# Kurikulum Enterprise iOS Engineering
## Kategori: 03-Frontend-and-Mobile
### BAB-03: Arsitektur UI Imperatif dan Pola Klasik UIKit
#### Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, engineer diharapkan memiliki kompetensi tingkat lanjut untuk:
- Menganalisis siklus internal *iOS Render Loop* dan algoritma *Cassowary Linear Constraint Solver* untuk mengeliminasi *layout thrashing* dan mencapai konsistensi 120 FPS (*ProMotion*).
- Merancang dan mengimplementasikan arsitektur modular decoupling berbasis *VIPER* atau *Clean Swift* yang terintegrasi secara *type-safe* dengan pola *Coordinator Pattern*.
- Menguasai teknik manipulasi `CALayer`, *off-screen rendering mitigation*, dan asinkronisasi kalkulasi layout untuk menangani *high-frequency UI updates*.
- Mengimplementasikan *custom interactive UIViewController transitions* dan *adaptive presentation controllers* berbasis arsitektur *gesture-driven state machine*.
- Melakukan profil memori, deteksi *retain cycles*, dan *memory leaks* menggunakan *Instruments (Leaks, Allocations, Time Profiler)* pada aplikasi skala enterprise.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, engineer wajib menguasai:
- **Swift Core**: *Automatic Reference Counting* (ARC), *capture lists* (`[weak self]`, `[unowned self]`), *generics*, *protocols & associated types*.
- **Dasar UIKit**: `UIViewController` *lifecycle*, hierarki view dasar (`UIView`, `UIWindow`), dan dasar AutoLayout via NSLayoutConstraint/VFL.
- **Multithreading**: Grand Central Dispatch (GCD), *Main RunLoop*, eksekusi serial vs *concurrent*, serta isolasi `@MainActor` pada Swift Concurrency.

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Internal Render Loop & Cassowary Constraint Solver
UIKit tidak langsung merender view ke layar saat properti visual (seperti `frame`, `bounds`, atau constraint) berubah. UIKit bekerja di atas *RunLoop* yang memproses perubahan ini melalui fase terstruktur:

```
[Touch/Event Phase] -> [Update Constraints Phase] -> [Layout Subviews Phase] -> [Display/Draw Phase] -> [Commit Transaction to Render Server]
```

1. **Update Constraints Phase (`updateConstraints`)**: Dipicu oleh pemanggilan `setNeedsUpdateConstraints()`. Cassowary solver menyelesaikan relasi linear persamaan $Ax \le b$ atau $Ax = b$ dalam kompleksitas ruang dan waktu $O(N^3)$ pada skenario terburuk jika hierarki tidak optimal.
2. **Layout Phase (`layoutSubviews`)**: Dipicu oleh `setNeedsLayout()`. Nilai kalkulasi posisi dari Cassowary dikonversi menjadi nilai konkret: `center` dan `bounds` untuk setiap `UIView` (yang memetakan ke `position` dan `bounds` pada `CALayer`).
3. **Display Phase (`drawRect` / `draw(_:)`)**: Core Animation menyiapkan *backing store* bitmap jika view meng-override fungsi `draw(_:)`. Jika tidak, UIKit menggunakan bitmap yang di-cache di GPU memory buffer.
4. **Render Server Phase**: Proses `render server` independen dari thread aplikasi (`SpringBoard`/`backboardd`). Core Animation men-serialize layer tree via IPC (Inter-Process Communication), mem-parsing drawing commands via OpenGL/Metal, dan mengirimkannya ke GPU framebuffer.

#### B. Off-Screen Rendering & GPU Pipeline Cost
*Off-Screen Rendering* terjadi ketika GPU tidak dapat langsung merender konten ke *Frame Buffer* di layar, melainkan harus mengalokasikan buffer memori sekunder di *VRAM* (disebut *Offscreen Buffer*) dan melakukan multi-pass rendering.

Pemicu utama di UIKit:
- Penggunaan `layer.cornerRadius` bersamaan dengan `layer.masksToBounds = true`.
- Layer shadow tanpa penetapan eksplisit `layer.shadowPath`.
- Aplikasi `layer.mask` (alpha mask).
- `layer.allowsGroupOpacity = true` dengan nilai `layer.opacity < 1.0`.

Biaya performa: Konteks switching berulang antara *On-Screen* dan *Off-Screen* buffer menyebabkan penurunan drastis pada *texture cache throughput* GPU, yang langsung memicu *dropped frames* di bawah 60/120 Hz.

#### C. Arsitektur Decoupling: Coordinator + Clean Swift (VIP)
Untuk mencegah *Massive View Controller* (MVC), produksi enterprise memisahkan tanggung jawab secara absolut:

```
+-----------------------------------------------------------+
|                        Coordinator                        |
+-----------------------------------------------------------+
             | instantiates & routes
             v
+------------------+       requests       +-------------------+
|                  | -------------------> |                   |
|  ViewController  |                      |    Interactor     |
|      (View)      | <------------------- |  (Business Logic) |
+------------------+     passes Model     +-------------------+
        ^                                           |
        | displays ViewModel                        | passes Response
        |                                           v
+-----------------------------------------------------+
|                     Presenter                       |
|               (Presentation Logic)                  |
+-----------------------------------------------------+
```

- **ViewController**: Hanya mengurus siklus hidup UIKit, rendering data dari ViewModel, dan meneruskan *UI Events* ke Interactor. Tidak boleh mengimpor modul navigasi atau logika bisnis.
- **Interactor**: Mengimplementasikan *Use Case*. Murni menggunakan Swift murni (tanpa dependensi `UIKit`), berinteraksi dengan *Worker/Repository*, dan mengembalikan *Response Model*.
- **Presenter**: Menerima *Response Model*, mentransformasikannya menjadi representasi string/UI (*ViewModel*), dan mengirimkannya kembali ke ViewController.
- **Coordinator**: Memegang kendali mutlak atas alur navigasi (`UINavigationController`, presenting modally, deep linking).

---

### 4. Why & What

| Dimensi | Mengapa Digunakan (Enterprise Context) | Apa Risikonya jika Salah Desain |
| :--- | :--- | :--- |
| **UIKit Imperatif** | Memberikan determinisme tinggi, performa absolut untuk custom canvas rendering, dan backward compatibility hingga iOS lawas tanpa bug state-loss SwiftUI. | Terjadi *Massive View Controller* (MVC), *memory leaks* akibat closure retain cycles, dan arsitektur sulit diuji unit test. |
| **Manual Frame/Pure Code Layout** | Menghilangkan overhead komputasi Cassowary solver pada daftar data berdensitas tinggi (e.g., dynamic high-frequency order book). | Menulis kode kalkulasi bounding box matematika manual yang rentan terhadap bug saat terjadi perubahan orientasi atau dynamic type scaling. |
| **Coordinator Pattern** | Memungkinkan View Controller digunakan kembali (*reusable*) di modul berbeda tanpa ketergantungan erat (*tight coupling*) pada parent navigator. | Jika hierarki child-coordinator tidak dikelola secara eksplisit, terjadi *zombie coordinators* di memori RAM. |

---

### 5. How (Workflow Detail)

Alur kerja eksekusi UI imperatif berkinerja tinggi:

```
[Event Trigger] 
       │
       ▼
[State Mutation di Interactor] 
       │
       ▼
[Presenter memformat ViewModel]
       │
       ▼
[ViewController update UI via Main Thread]
       │
       ├─► Diffable DataSource memproses Snapshot via Background Queue
       │
       ├─► Main Queue menerapkan Snapshot animasi secara atomik
       │
       └─► CALayer menghindari Off-Screen Pass (ShadowPath & Rasterization diaktifkan)
             │
             ▼
      [GPU Frame Swap: 120 FPS Match]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Kontraktor Bangunan dan Blueprint
- **Cassowary Solver (AutoLayout)**: Arsitek yang terus-menerus mengukur ulang blueprint tiap kali dinding bergeser 1 mm. Sangat presisi namun memakan waktu komputasi besar.
- **Manual Frame Layout (`layoutSubviews`)**: Tukang kayu profesional yang memotong balok kayu langsung dengan ukuran pasti yang sudah dihitung sebelumnya.
- **Off-Screen Rendering**: Kontraktor yang harus mengecat papan di gudang belakang terlebih dahulu, mengeringkannya, baru membawanya kembali ke lokasi proyek utama, alih-alih mengecat langsung di dinding terpasang.

#### Diagram: VIPER / VIP Navigation Pipeline
```
               DEEP LINK / USER ACTION
                         │
                         ▼
             ┌─────────────────────────┐
             │     App Coordinator     │
             └───────────┬─────────────┘
                         │ spawns
                         ▼
             ┌─────────────────────────┐
             │    Trade Coordinator    │
             └───────────┬─────────────┘
                         │ pushes
                         ▼
        ┌───────────────────────────────────┐
        │       TradeViewController         │
        │  (UIKit lifecycle, subviews)     │
        └───┬───────────────────────────▲───┘
            │ User taps "BUY"           │ display(viewModel)
            ▼                           │
        ┌─────────────────────────┐     │
        │      TradeInteractor    │     │
        │  (Execute order worker) │     │
        └───┬─────────────────────┘     │
            │ returns TradeResponse     │
            ▼                           │
        ┌─────────────────────────┐     │
        │     TradePresenter      │─────┘
        │ (Formats Currency, Date)│
        └─────────────────────────┘
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Zero-Offscreen-Rendering Rounded Card with Manual Optimization
Contoh penerapan `UIView` kustom dengan optimasi shadow, clipping, dan rendering border tanpa memicu offscreen pass.

```swift
import UIKit

final class OptimizedCardView: UIView {
    private let titleLabel = UILabel()

    override init(frame: CGRect) {
        super.init(frame: frame)
        setupView()
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    private func setupView() {
        backgroundColor = .secondarySystemBackground
        layer.cornerRadius = 12.0
        // Hindari masksToBounds = true bersamaan dengan shadow
        layer.masksToBounds = false 
        
        layer.shadowColor = UIColor.black.cgColor
        layer.shadowOpacity = 0.15
        layer.shadowRadius = 8.0
        layer.shadowOffset = CGSize(width: 0, height: 4)

        titleLabel.translatesAutoresizingMaskIntoConstraints = false
        titleLabel.font = .preferredFont(forTextStyle: .headline)
        addSubview(titleLabel)

        NSLayoutConstraint.activate([
            titleLabel.topAnchor.constraint(equalTo: topAnchor, constant: 16),
            titleLabel.leadingAnchor.constraint(equalTo: leadingAnchor, constant: 16),
            titleLabel.trailingAnchor.constraint(equalTo: trailingAnchor, constant: -16),
            titleLabel.bottomAnchor.constraint(equalTo: bottomAnchor, constant: -16)
        ])
    }

    override func layoutSubviews() {
        super.layoutSubviews()
        // KUNCI: Tentukan shadowPath secara eksplisit untuk mencegah GPU Off-Screen Pass
        layer.shadowPath = UIBezierPath(roundedRect: bounds, cornerRadius: layer.cornerRadius).cgPath
    }

    func configure(title: String) {
        titleLabel.text = title
    }
}
```

#### B. Practical Enterprise Example: Asynchronous Prefetched Dynamic Feed with Clean Swift VIP & Custom Transitions

##### 1. Protocols & Contract (VIP)
```swift
import UIKit

// MARK: - Models
enum FeedModel {
    struct Request {
        let page: Int
    }
    struct Response {
        let items: [FeedItem]
    }
    struct ViewModel {
        struct DisplayedItem: Hashable {
            let id: String
            let formattedTitle: String
            let formattedAmount: String
            let statusColor: UIColor
        }
        let displayedItems: [DisplayedItem]
    }
}

struct FeedItem {
    let id: String
    let name: String
    let amount: Decimal
    let isSettled: Bool
}

// MARK: - VIP Protocols
protocol FeedBusinessLogic: AnyObject {
    func fetchFeed(request: FeedModel.Request)
}

protocol FeedPresentationLogic: AnyObject {
    func presentFeed(response: FeedModel.Response)
}

protocol FeedDisplayLogic: AnyObject {
    func displayFeed(viewModel: FeedModel.ViewModel)
}

protocol FeedRoutingLogic: AnyObject {
    func navigateToDetail(id: String)
}
```

##### 2. Interactor & Presenter
```swift
import Foundation
import UIKit

final class FeedInteractor: FeedBusinessLogic {
    var presenter: FeedPresentationLogic?
    private var worker = FeedWorker()

    func fetchFeed(request: FeedModel.Request) {
        // Simulasi background execution via Task / Dispatch
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self = self else { return }
            let items = self.worker.fetchItems(page: request.page)
            let response = FeedModel.Response(items: items)
            
            DispatchQueue.main.async {
                self.presenter?.presentFeed(response: response)
            }
        }
    }
}

final class FeedWorker {
    func fetchItems(page: Int) -> [FeedItem] {
        return (0..<20).map { index in
            FeedItem(
                id: UUID().uuidString,
                name: "Transaction #\(page * 20 + index)",
                amount: Decimal(Double.random(in: 100...5000)),
                isSettled: Bool.random()
            )
        }
    }
}

final class FeedPresenter: FeedPresentationLogic {
    weak var viewController: FeedDisplayLogic?
    
    private let currencyFormatter: NumberFormatter = {
        let formatter = NumberFormatter()
        formatter.numberStyle = .currency
        formatter.currencyCode = "USD"
        return formatter
    }()

    func presentFeed(response: FeedModel.Response) {
        let displayed = response.items.map { item -> FeedModel.ViewModel.DisplayedItem in
            let amountString = currencyFormatter.string(from: item.amount as NSDecimalNumber) ?? "$0.00"
            return FeedModel.ViewModel.DisplayedItem(
                id: item.id,
                formattedTitle: item.name.uppercased(),
                formattedAmount: amountString,
                statusColor: item.isSettled ? .systemGreen : .systemOrange
            )
        }
        
        let viewModel = FeedModel.ViewModel(displayedItems: displayed)
        viewController?.displayFeed(viewModel: viewModel)
    }
}
```

##### 3. High Performance Cell with Custom Manual Layout
```swift
final class TransactionCell: UICollectionViewCell {
    static let reuseIdentifier = "TransactionCell"
    
    private let titleLabel = UILabel()
    private let amountLabel = UILabel()
    private let statusIndicator = UIView()
    
    override init(frame: CGRect) {
        super.init(frame: frame)
        setupHierarchy()
    }
    
    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }
    
    private func setupHierarchy() {
        contentView.addSubview(statusIndicator)
        contentView.addSubview(titleLabel)
        contentView.addSubview(amountLabel)
        
        titleLabel.font = .systemFont(ofSize: 16, weight: .semibold)
        amountLabel.font = .monospacedDigitSystemFont(ofSize: 15, weight: .medium)
        statusIndicator.layer.cornerRadius = 4.0
    }
    
    // Bypass Cassowary AutoLayout solver for ultra-performance list scrolling
    override func layoutSubviews() {
        super.layoutSubviews()
        let bounds = contentView.bounds
        let padding: CGFloat = 16.0
        
        statusIndicator.frame = CGRect(
            x: padding,
            y: (bounds.height - 8) / 2,
            width: 8,
            height: 8
        )
        
        let amountWidth: CGFloat = 100.0
        amountLabel.frame = CGRect(
            x: bounds.width - padding - amountWidth,
            y: 0,
            width: amountWidth,
            height: bounds.height
        )
        amountLabel.textAlignment = .right
        
        let titleOriginX = statusIndicator.frame.maxX + 12.0
        titleLabel.frame = CGRect(
            x: titleOriginX,
            y: 0,
            width: amountLabel.frame.minX - titleOriginX - 8.0,
            height: bounds.height
        )
    }
    
    func render(item: FeedModel.ViewModel.DisplayedItem) {
        titleLabel.text = item.formattedTitle
        amountLabel.text = item.formattedAmount
        statusIndicator.backgroundColor = item.statusColor
    }
    
    override func prepareForReuse() {
        super.prepareForReuse()
        titleLabel.text = nil
        amountLabel.text = nil
        statusIndicator.backgroundColor = nil
    }
}
```

##### 4. UIViewController with Diffable DataSource & Coordinator Hooks
```swift
final class FeedViewController: UIViewController, FeedDisplayLogic {
    var interactor: FeedBusinessLogic?
    weak var coordinator: FeedRoutingLogic?

    private var collectionView: UICollectionView!
    private var dataSource: UICollectionViewDiffableDataSource<Int, FeedModel.ViewModel.DisplayedItem>!

    override func loadView() {
        let layout = UICollectionViewCompositionalLayout { _, layoutEnvironment in
            var config = UICollectionLayoutListConfiguration(appearance: .plain)
            config.showsSeparators = true
            return NSCollectionLayoutSection.list(using: config, layoutEnvironment: layoutEnvironment)
        }
        collectionView = UICollectionView(frame: .zero, collectionViewLayout: layout)
        self.view = collectionView
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        title = "Enterprise Feed"
        setupCollectionView()
        configureDataSource()
        
        interactor?.fetchFeed(request: FeedModel.Request(page: 1))
    }

    private func setupCollectionView() {
        collectionView.delegate = self
        collectionView.register(TransactionCell.self, forCellWithReuseIdentifier: TransactionCell.reuseIdentifier)
    }

    private func configureDataSource() {
        dataSource = UICollectionViewDiffableDataSource<Int, FeedModel.ViewModel.DisplayedItem>(
            collectionView: collectionView
        ) { collectionView, indexPath, itemIdentifier in
            guard let cell = collectionView.dequeueReusableCell(
                withReuseIdentifier: TransactionCell.reuseIdentifier,
                for: indexPath
            ) as? TransactionCell else {
                return UICollectionViewCell()
            }
            cell.render(item: itemIdentifier)
            return cell
        }
    }

    func displayFeed(viewModel: FeedModel.ViewModel) {
        var snapshot = NSDiffableDataSourceSnapshot<Int, FeedModel.ViewModel.DisplayedItem>()
        snapshot.appendSections([0])
        snapshot.appendItems(viewModel.displayedItems)
        dataSource.apply(snapshot, animatingDifferences: true)
    }
}

extension FeedViewController: UICollectionViewDelegate {
    func collectionView(_ collectionView: UICollectionView, didSelectItemAt indexPath: IndexPath) {
        guard let item = dataSource.itemIdentifier(for: indexPath) else { return }
        coordinator?.navigateToDetail(id: item.id)
    }
}
```

##### 5. Navigation Coordinator Pattern
```swift
protocol Coordinator: AnyObject {
    var childCoordinators: [Coordinator] { get set }
    var navigationController: UINavigationController { get set }
    func start()
}

final class MainFeedCoordinator: Coordinator, FeedRoutingLogic {
    var childCoordinators = [Coordinator]()
    var navigationController: UINavigationController

    init(navigationController: UINavigationController) {
        self.navigationController = navigationController
    }

    func start() {
        let feedVC = FeedViewController()
        let interactor = FeedInteractor()
        let presenter = FeedPresenter()
        
        feedVC.interactor = interactor
        feedVC.coordinator = self
        interactor.presenter = presenter
        presenter.viewController = feedVC
        
        navigationController.setViewControllers([feedVC], animated: false)
    }

    func navigateToDetail(id: String) {
        let detailVC = UIViewController()
        detailVC.view.backgroundColor = .systemBackground
        detailVC.title = "Detail ID: \(id.prefix(8))"
        navigationController.pushViewController(detailVC, animated: true)
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: SuperApp FinTech Real-Time Multi-Asset Feed
- **Skala**: Aplikasi dengan 10 juta pengguna aktif harian (*DAU*). Data pasar (*stock ticker*, *crypto*, dan rekening saldo) di-push melalui WebSocket dengan frekuensi 15-30 *payloads* per detik.
- **Problem Statement**:
  - Main thread mengalami *stall* hingga 200 ms (UI *frozen*, *frame drop* dari 120 FPS ke 14 FPS).
  - Konsumsi memori melonjak hingga >800MB dalam 15 menit pemakaian, memicu terminasi oleh sistem karena `EXC_RESOURCE -> MEMORY EXCEPTION` (OOM).
  - Terdapat AutoLayout *constraint churning* akibat pemanggilan `view.layoutIfNeeded()` berulang pada subviews feed saat *stream* data masuk.
- **Root Cause Analysis (RCA)**:
  1. Parsing JSON WebSocket dijalankan pada background, tetapi data langsung mentah-mentah dioper ke Main Thread untuk memicu `reloadData()` pada `UICollectionView`.
  2. Seluruh cell menggunakan autolayout dengan 20+ constraint per sel, memaksa Cassowary solver memecahkan $N \times 20$ sistem matriks secara bersamaan pada Main Thread.
  3. Cell image menggunakan corner radius dinamis dengan `clipsToBounds = true` tanpa spesifikasi path, menyebabkan multi-pass GPU off-screen rendering.
- **Solusi Arsitektural & Engineering**:
  1. **Throttling & Batching**: Menggunakan Combine/AsyncChannel buffer untuk membatasi UI update ke snapshot 60Hz.
  2. **Diffable Data Source Background Apply**: Perhitungan diff hash dijalankan pada background queue sebelum commit ke main thread:
     ```swift
     DispatchQueue.global(qos: .userInteractive).async {
         var snapshot = self.dataSource.snapshot()
         snapshot.reconfigureItems(updatedIdentifiers)
         self.dataSource.apply(snapshot, animatingDifferences: false)
     }
     ```
  3. **Layout Pre-calculation**: Mengganti AutoLayout pada `UICollectionViewCell` berdensitas tinggi dengan perhitungan manual bounds via `layoutSubviews()` atau caching layout atribut.
  4. **GPU Optimization**: Mengubah profiling layer:
     ```swift
     layer.shadowPath = UIBezierPath(rect: bounds).cgPath
     layer.shouldRasterize = true
     layer.rasterizationScale = UIScreen.main.scale
     ```
- **Hasil**:
  - Frame rate stabil di 118-120 FPS pada iPhone Pro Promotion displays.
  - Alokasi memori rata-rata turun dari 800MB ke 145MB konstan (kebocoran memori teratasi 100%).
  - Main Thread Time Profiler CPU usage turun dari 94% ke 12%.

---

### 9. Trade-offs

| Pendekatan | Keuntungan | Kerugian & Batasan | Mitigasi |
| :--- | :--- | :--- | :--- |
| **AutoLayout (Cassowary)** | Sangat deklaratif, mudah beradaptasi dengan Dynamic Type dan orientasi layar. | Kompleksitas kalkulasi $O(N^3)$, CPU overhead tinggi pada scroll berkecepatan tinggi dengan sel kompleks. | Gunakan AutoLayout hanya pada view statis; alihkan ke manual frame untuk cell list berulang. |
| **Manual Layout (`layoutSubviews`)** | Eksekusi instan $O(1)$, zero solver overhead, konsumsi baterai & CPU terendah. | Kode perhitungan matematis verbose, rawan human-error, harus menangani RTL (*Right-to-Left*) secara manual. | Buat helper utility layout internal (seperti micro-engine PinLayout/LayoutKit). |
| **Coordinator VIP / VIPER** | *Single Responsibility Principle* terpenuhi, testability 100%, navigasi terisolasi sempurna. | *Boilerplate* tinggi, kurva belajar tim terjal, file overhead bertambah signifikan. | Gunakan code generation tools (seperti SwiftGen atau Xcode Templates kustom). |
| **Layer Rasterization (`shouldRasterize`)** | GPU me-render layer kompleks ke dalam bitmap cache sekali saja, scrolling sangat mulus. | Memakan VRAM tambahan; jika layer berubah dinamis (*dirty*), GPU akan me-render ulang setiap frame (membuat lag makin parah). | Terapkan HANYA pada view statis yang isinya tidak berubah selama scrolling. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Retain Cycle pada Coordinator & Router Closures
- **Gejala**: Memori tidak turun saat menekan tombol back/dismiss pada View Controller.
- **Penyebab**: Child coordinator mereferensikan closure atau delegate tanpa `weak`.
- **Solusi Debugging**: Gunakan Xcode Memory Graph Debugger. Cari `UIViewController` yang masih eksis padahal sudah tidak ada di navigation stack.
  ```swift
  // SALAH
  coordinator.onFinish = {
      self.dismissChild()
  }
  
  // BENAR
  coordinator.onFinish = { [weak self] in
      self?.dismissChild()
  }
  ```

#### 2. Layout Thrashing (Recursive `layoutSubviews`)
- **Gejala**: CPU usage mencapai 100%, UI macet total tanpa crash log (*hang*).
- **Penyebab**: Memanggil `view.setNeedsLayout()` atau mengubah constraint di dalam fungsi `layoutSubviews()` tanpa kondisi guard.
- **Solusi**: Jangan pernah melakukan mutasi hierarki constraint atau memanggil method invalidate layout di dalam `layoutSubviews()`. Gunakan flag boolean pengecekan mutasi state:
  ```swift
  override func layoutSubviews() {
      super.layoutSubviews()
      // JANGAN LAKUKAN INI:
      // setNeedsLayout()
      // heightConstraint.constant = 50 
  }
  ```

#### 3. Off-Screen Rendering Akibat Dynamic Masks
- **Gejala**: Scroll stutters saat list memuat sel dengan gambar profil bulat.
- **Penyebab**: Memotong gambar dengan `imageView.layer.cornerRadius = w / 2` dan `imageView.clipsToBounds = true` langsung pada sel yang di-scroll cepat.
- **Solusi**: Potong *UIImage* menjadi lingkaran langsung di background thread via `UIGraphicsImageRenderer` sebelum diumpankan ke UIImageView, sehingga layer tidak perlu melakukan clipping mask saat render loop.

---

### 11. Best Practices (Production Checklist)

1. [ ] **Constraint Sanity**: Pastikan tidak ada pesan error `Unable to simultaneously satisfy constraints` pada console log aplikasi.
2. [ ] **Deinit Verification**: Pastikan setiap `UIViewController`, `Coordinator`, dan `Presenter` mencetak log dealloc saat di-pop:
   ```swift
   #if DEBUG
   deinit { print("DEALLOCATED: \(String(describing: self))") }
   #endif
   ```
3. [ ] **Main Thread Guard**: Eksekusi semua mutasi snapshot Diffable Data Source atau UIKit properties hanya dari Thread Utama:
   ```swift
   assert(Thread.isMainThread, "Must be dispatched to Main Thread")
   ```
4. [ ] **Shadow Path Definition**: Selalu tentukan `layer.shadowPath = UIBezierPath(...).cgPath` setiap kali mengaktifkan layer shadow.
5. [ ] **Reusable Cell Cleanup**: Kembalikan state awal sel di `prepareForReuse()`, termasuk membatalkan network task (`URLSessionTask.cancel()`).
6. [ ] **Instruments Profiling Checklist**:
   - Jalankan **Time Profiler**: Pastikan *no inverted call tree exceeds 16ms per tick*.
   - Jalankan **Core Animation Instrument**: Pastikan *Color Offscreen-Rendered Yellow* tidak menyala di area feed aktif.
   - Jalankan **Leaks**: Pastikan zero leaks setelah bolak-balik navigasi 10 kali.

---

### 12. Hands-on Practice

Target implementasi: Buat modul `CustomInteractiveTransition` yang mengelola navigasi kustom berbasis gesture pan di folder `hands-on/m02/`.

#### Struktur Folder:
```
hands-on/m02/
├── AppDelegate.swift
├── SceneDelegate.swift
├── Presentation/
│   ├── CustomTransitionAnimator.swift
│   ├── InteractionController.swift
│   ├── RootViewController.swift
│   └── DetailViewController.swift
└── Info.plist
```

#### Langkah Pengerjaan:

##### 1. Buat File `CustomTransitionAnimator.swift`
```swift
import UIKit

final class CustomTransitionAnimator: NSObject, UIViewControllerAnimatedTransitioning {
    let isPresenting: Bool
    let duration: TimeInterval = 0.35

    init(isPresenting: Bool) {
        self.isPresenting = isPresenting
        super.init()
    }

    func transitionDuration(using transitionContext: UIViewControllerContextTransitioning?) -> TimeInterval {
        return duration
    }

    func animateTransition(using transitionContext: UIViewControllerContextTransitioning) {
        let containerView = transitionContext.containerView

        if isPresenting {
            guard let toView = transitionContext.view(forKey: .to) else {
                transitionContext.completeTransition(false)
                return
            }
            containerView.addSubview(toView)
            toView.transform = CGAffineTransform(translationX: 0, y: containerView.bounds.height)
            
            UIView.animate(
                withDuration: duration,
                delay: 0,
                options: [.curveEaseOut],
                animations: {
                    toView.transform = .identity
                },
                completion: { finished in
                    transitionContext.completeTransition(finished && !transitionContext.transitionWasCancelled)
                }
            )
        } else {
            guard let fromView = transitionContext.view(forKey: .from) else {
                transitionContext.completeTransition(false)
                return
            }
            
            UIView.animate(
                withDuration: duration,
                delay: 0,
                options: [.curveEaseIn],
                animations: {
                    fromView.transform = CGAffineTransform(translationX: 0, y: containerView.bounds.height)
                },
                completion: { finished in
                    if !transitionContext.transitionWasCancelled {
                        fromView.removeFromSuperview()
                    }
                    transitionContext.completeTransition(finished && !transitionContext.transitionWasCancelled)
                }
            )
        }
    }
}
```

##### 2. Buat File `InteractionController.swift`
```swift
import UIKit

final class InteractionController: UIPercentDrivenInteractiveTransition {
    var interactionInProgress = false
    private weak var viewController: UIViewController?
    private var shouldCompleteTransition = false

    init(viewController: UIViewController) {
        self.viewController = viewController
        super.init()
        setupGestureRecognizer(in: viewController.view)
    }

    private func setupGestureRecognizer(in view: UIView) {
        let panGesture = UIPanGestureRecognizer(target: self, action: #selector(handlePanGesture(_:)))
        view.addGestureRecognizer(panGesture)
    }

    @objc private func handlePanGesture(_ gestureRecognizer: UIPanGestureRecognizer) {
        guard let view = gestureRecognizer.view, let window = view.window else { return }
        let translation = gestureRecognizer.translation(in: window)
        let verticalMovement = translation.y / window.bounds.height

        switch gestureRecognizer.state {
        case .began:
            interactionInProgress = true
            viewController?.dismiss(animated: true, completion: nil)
        case .changed:
            let progress = max(0.0, min(1.0, verticalMovement))
            shouldCompleteTransition = progress > 0.35
            update(progress)
        case .cancelled:
            interactionInProgress = false
            cancel()
        case .ended:
            interactionInProgress = false
            if shouldCompleteTransition {
                finish()
            } else {
                cancel()
            }
        default:
            break
        }
    }
}
```

##### 3. Hubungkan di `DetailViewController.swift`
```swift
import UIKit

final class DetailViewController: UIViewController, UIViewControllerTransitioningDelegate {
    private var interactionController: InteractionController?

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .systemTeal
        
        transitioningDelegate = self
        modalPresentationStyle = .custom
        
        interactionController = InteractionController(viewController: self)
    }

    func animationController(
        forPresented presented: UIViewController,
        presenting: UIViewController,
        source: UIViewController
    ) -> UIViewControllerAnimatedTransitioning? {
        return CustomTransitionAnimator(isPresenting: true)
    }

    func animationController(
        forDismissed dismissed: UIViewController
    ) -> UIViewControllerAnimatedTransitioning? {
        return CustomTransitionAnimator(isPresenting: false)
    }

    func interactionControllerForDismissal(
        using animator: UIViewControllerAnimatedTransitioning
    ) -> UIViewControllerInteractiveTransitioning? {
        guard let interactionController = interactionController, interactionController.interactionInProgress else {
            return nil
        }
        return interactionController
    }
}
```

---

### 13. Exercise

#### Level Easy
Ubah implementasi `UICollectionView` konvensional menjadi `UICollectionViewDiffableDataSource` dengan snapshot statis 3 elemen. Pastikan tidak ada pemanggilan `reloadData()`.
- **Kriteria Penerimaan**: Tidak menggunakan method delegate `cellForItemAt`, data ditransaksikan menggunakan generic snapshot.

#### Level Medium
Buat sebuah custom view `SlidingHeaderView` yang mewarisi `UIView`. View ini harus mengimplementasikan fungsi paralaks di mana ketinggian frame menyusut secara matematis saat di-scroll via `UIScrollViewDelegate` (`scrollViewDidScroll`), dari tinggi `300pt` ke minimum `80pt`, dengan mengubah font size secara proporsional menggunakan transformasi manual (tanpa merusak AutoLayout constraint).
- **Kriteria Penerimaan**: 0 AutoLayout conflict errors, frame tracking bekerja mulus pada 60/120 FPS.

#### Level Hard
Buat implementasi custom container view controller (`DockContainerViewController`) yang menampung 2 child view controller secara vertikal (Master and Detail Pane). 
- Container harus mengizinkan resizing ukuran pane via *drag handle divider*.
- Handle divider harus mengirimkan callback perubahan safeAreaInsets ke child controllers via custom layout guides (`additionalSafeAreaInsets`).
- Jika ditarik melampaui ambang 70% layar, child controller bawah harus mengembang memenuhi seluruh layar (*snap animation*) menggunakan `UIViewPropertyAnimator` yang interaktif dan dapat dibatalkan (*reversible*).
- **Kriteria Penerimaan**: Memory cleanup sempurna saat child di-remove (`willMove(toParent: nil)`, `removeFromParent()`), transisi interaktif fluid tanpa glitch layout frame.

---

### 14. Challenge

**Skenario**: Anda ditugaskan merekonstruksi dynamic layout engine untuk modul **Trading Terminal Orderbook** pada sistem perdagangan aset kripto berkecepatan tinggi.
- **Batasan Sistem**:
  - Main thread hanya diberikan budget maksimal **3.5 ms** per render pass untuk komputasi layout UI guna mencegah frame drop pada ProMotion display (120Hz = total frame budget 8.3ms).
  - Data buku pesanan (*bids* dan *asks*) berubah setiap 50 milidetik via push WebSocket (masing-masing 50 tingkat harga).
  - Setiap sel harus menampilkan bar depth horizontal (persentase volume), label harga, label kuantitas, dan waktu eksekusi.
- **Tugas Arsitektur**:
  1. Rancang arsitektur komponen rendering layout yang tidak menggunakan `NSLayoutConstraint` sama sekali.
  2. Implementasikan teknik *Text Pre-rendering/CoreText sizing* atau *background bounding-box calculation* sebelum data di-dispatch ke main thread.
  3. Hindari alokasi memory baru pada *hot-path* frame render dengan menerapkan *Object Pool* pattern untuk cell / data layer buffers.
  4. Sediakan bukti arsitektural (berupa skema pseudocode terperinci) bahwa sistem bebas dari GPU Off-Screen rendering dan aman dari data race concurrency.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic (5 Soal)
1. **Pada fase apakah dalam RunLoop UIKit memproses nilai persamaan matematika yang ditentukan oleh AutoLayout?**
   - A. `drawRect`
   - B. `updateConstraints`
   - C. `layoutSubviews`
   - D. `displayLayer`
   *Jawaban*: B. Pada fase `updateConstraints`, Cassowary solver menghitung nilai koordinat berdasarkan rule constraints.

2. **Properti apa yang wajib diisi saat mengatur `layer.shadowRadius` dan `layer.shadowOpacity` untuk mencegah kalkulasi off-screen pass oleh GPU?**
   - A. `layer.masksToBounds`
   - B. `layer.shadowPath`
   - C. `layer.isOpaque`
   - D. `layer.cornerRadius`
   *Jawaban*: B. `layer.shadowPath` memberi tahu GPU bentuk pasti shadow tanpa harus menganalisis alpha channel view layer off-screen.

3. **Mengapa deklarasi delegate protocol pada UIKit pattern hampir selalu wajib mewarisi `AnyObject`?**
   - A. Agar delegate bisa memiliki method opsional.
   - B. Agar compiler mengizinkan delegate disimpan dengan modifier `weak` guna mencegah retain cycle.
   - C. Agar method delegate berjalan di background thread.
   - D. Agar delegate dapat dikonversi menjadi struct.
   *Jawaban*: B. Modifier `weak` hanya dapat diaplikasikan pada reference types (`class`), yang ditandai dengan konstrain `AnyObject`.

4. **Kapan method `prepareForReuse()` pada `UITableViewCell` atau `UICollectionViewCell` dipanggil oleh sistem?**
   - A. Sesaat sebelum sel dibuat pertama kali di memori.
   - B. Tepat sebelum sel dikembalikan dari queue `dequeueReusableCell`.
   - C. Ketika user menghapus sel dari layar menggunakan gesture swipe.
   - D. Ketika view controller mengalami `deinit`.
   *Jawaban*: B. Dipanggil tepat sebelum sel yang di-recycle dikembalikan oleh method dequeue reuse identifier.

5. **Apa fungsi utama dari protokol `UIViewControllerContextTransitioning` dalam custom view controller transitions?**
   - A. Memastikan animasi dijalankan menggunakan Core Video.
   - B. Menyediakan akses ke context environment transisi termasuk container view, from/to controllers, dan handling status pembatalan transisi.
   - C. Mengubah resolusi layar secara dinamis selama presentasi modal.
   - D. Menggantikan peran `UINavigationController`.
   *Jawaban*: B. Protokol ini membungkus state dan metadata container views yang terlibat dalam custom animation.

#### B. Pertanyaan Intermediate (5 Soal)
6. **Perhatikan kode berikut:**
   ```swift
   override func layoutSubviews() {
       super.layoutSubviews()
       titleLabel.frame = CGRect(x: 0, y: 0, width: bounds.width, height: 40)
       customButton.frame = CGRect(x: 0, y: titleLabel.frame.maxY, width: bounds.width, height: 50)
       setNeedsLayout()
   }
   ```
   **Apa konsekuensi eksekusi kode di atas di runtime iOS?**
   - A. Button tidak akan pernah muncul.
   - B. Terjadi infinite layout loop yang memicu Main Thread freeze (CPU 100%).
   - C. Crash dengan pesan `Fatal error: Index out of range`.
   - D. Tampilan akan bergeser 50pt ke bawah setiap frame.
   *Jawaban*: B. Memanggil `setNeedsLayout()` di dalam `layoutSubviews()` memicu request layout ulang secara rekursif tak terhingga pada runloop yang sama.

7. **Apa perbedaan mendasar antara method `layoutIfNeeded()` dan `setNeedsLayout()` pada `UIView`?**
   - A. `layoutIfNeeded()` bersifat asynchronous, sedangkan `setNeedsLayout()` synchronous.
   - B. `setNeedsLayout()` menandai view dirty untuk diproses pada runloop berikutnya, sedangkan `layoutIfNeeded()` memaksa layouting saat itu juga jika dirty.
   - C. `layoutIfNeeded()` hanya bekerja pada AutoLayout, sedangkan `setNeedsLayout()` khusus untuk manual frame.
   - D. Keduanya memiliki implementasi internal yang identik.
   *Jawaban*: B. `setNeedsLayout()` menaruh flag invalidasi, sedangkan `layoutIfNeeded()` langsung mengeksekusi update frame seketika jika flag invalidasi aktif.

8. **Mengapa Diffable Data Source mengeliminasi crash `NSInternalInconsistencyException: Invalid number of items` yang sering terjadi pada `UICollectionView` konvensional?**
   - A. Diffable Data Source menonaktifkan seluruh animasi penghapusan cell.
   - B. Diffable Data Source selalu menjalankan `reloadData()` di balik layar.
   - C. Penentuan perbedaan state dilakukan secara deterministik via hashing data model unik sebelum mengaplikasikan mutasi linear atomik ke UI.
   - D. Diffable Data Source mengabaikan delegate data source.
   *Jawaban*: C. Bug klasik inconsistency terjadi karena divergensi index path antara data array dan collection view state; hashing model diffing menjamin sinkronisasi mutasi state secara mutlak.

9. **Di dalam arsitektur VIP (Clean Swift), manakah jalur komunikasi data yang benar untuk mempertahankan unidirectional data flow?**
   - A. ViewController -> Presenter -> Interactor -> ViewController
   - B. ViewController -> Interactor -> Presenter -> ViewController
   - C. Presenter -> Interactor -> ViewController -> Coordinator
   - D. Interactor -> ViewController -> Presenter -> Interactor
   *Jawaban*: B. View Controller memanggil Interactor (Business Logic), Interactor mengoper response ke Presenter (Formatting Logic), dan Presenter mengirim ViewModel ke View Controller.

10. **Apa implikasi penggunaan `layer.shouldRasterize = true` pada cell yang berisi dynamic ticker numbers yang berubah tiap 100ms?**
    - A. Performa render meningkat secara signifikan karena disimpan di CPU cache.
    - B. Frame rate anjlok drastis karena GPU dipaksa membuang dan merekonstruksi texture bitmap cache secara berulang setiap kali konten berubah.
    - C. Warna label akan pudar secara otomatis akibat downsampling GPU.
    - D. Memori heap aplikasi langsung habis (OOM) seketika.
    - *Jawaban*: B. Rasterization hanya efisien untuk view statis. Merasterisasi view dinamis yang sering berubah (*dirty*) justru membebani GPU dengan *cache thrashing*.

#### C. Skenario Kasus Produksi (3 Soal)
11. **Skenario 1**: Aplikasi Core Banking Anda menerima komplain bahwa pengguna iPhone lawas mengalami crash saat membuka screen riwayat transaksi yang memiliki puluhan ribu data. Setelah dianalisis dengan Xcode Instruments, terjadi memory spike yang sangat tajam tepat saat View Controller di-load, meskipun Anda sudah menggunakan `UICollectionView`.
    **Apa akar masalah teknis yang paling mungkin dan bagaimana tindakan arsitektural yang tepat?**
    *Solusi Analitis*:
    - **Penyebab**: Seluruh puluhan ribu data di-instansiasi sekaligus ke dalam memory snapshot array pada memori heap dan/atau cell size dihitung menggunakan AutoLayout secara simultan untuk seluruh index path.
    - **Tindakan**: Implementasikan teknik *Windowed Data Pagination* / *Data Chunking* (misal memuat 50 record per fetch), manfaatkan protocol `UICollectionViewDataSourcePrefetching` untuk memuat data secara eager hanya mendekati viewport batas bawah, dan lepas retain reference snapshot lama sebelum appending snapshot baru.

12. **Skenario 2**: Dalam sebuah audit performa menggunakan Instruments (Core Animation), engineer melihat area feed aplikasi Anda menyala dengan warna merah dan kuning terang saat opsi *Color Hits Green and Misses Red* dan *Color Offscreen-Rendered Yellow* diaktifkan. Pengguna melaporkan UI *laggy* saat scrolling cepat.
    **Langkah eliminasi konkret apa yang harus Anda lakukan pada layer rendering views tersebut?**
    *Solusi Analitis*:
    - Warna kuning (*Offscreen-Rendered*) mengindikasikan GPU multi-pass rendering: Identifikasi komponen dengan shadow atau rounded corner. Ganti pemotongan layer dinamis dengan `UIBezierPath(roundedRect: ...)` eksplisit pada `shadowPath`, atau render rounded corner langsung pada aset gambar via bitmap rendering background.
    - Warna merah (*Misses Red*) mengindikasikan cache rasterisasi terus-menerus gagal (*miss*): Nonaktifkan `layer.shouldRasterize = false` pada elemen sel dinamis yang teksnya atau posisinya beranimasi secara aktif.

13. **Skenario 3**: Anda memimpin tim enterprise yang sedang memigrasi arsitektur monolith ke modular framework. Tiba-tiba terjadi bug di mana View Controller detail berhasil ditampilkan, namun saat user menekan back button, View Controller tertutup tetapi memory RAM tidak pernah berkurang, dan presenter background polling tetap berjalan tanpa henti.
    **Jelaskan urutan tindakan diagnosa teknis dan arsitektural untuk mendeteksi serta menyelesaikan bug ini secara permanen.**
    *Solusi Analitis*:
    - **Diagnosa**: Buka Xcode Memory Graph Debugger. Temukan instance `DetailViewController` dan cari node graf yang memiliki garis panah tebal (strong reference). Umumnya ditemukan pada: (1) Interactor memegang closure worker yang menahan `self` secara kuat, (2) Presenter memegang ViewController tanpa `weak`, atau (3) Coordinator memegang child coordinator di dalam array induk tanpa pernah menghapusnya saat alur navigasi berakhir (`navigationController(_:didShow:)`).
    - **Solusi**: 
      1. Tetapkan reference presenter ke view controller sebagai `weak var viewController: DetailDisplayLogic?`.
      2. Gunakan delegate `UINavigationControllerDelegate` pada coordinator untuk mendeteksi event pop manual dan menghapus child coordinator dari array `childCoordinators`.
      3. Batalkan polling task pada siklus hidup `viewWillDisappear` atau di dalam blok `deinit`.

---

### 16. Summary

Menguasai arsitektur imperatif UIKit tingkat lanjut menuntut pemahaman mendalam tentang siklus eksekusi di balik abstraksi framework. Performa UI optimal bukan sekadar menggunakan AutoLayout, melainkan memahami kapan AutoLayout harus dihindari demi efisiensi algoritma Cassowary $O(1)$ melalui kalkulasi manual `layoutSubviews`. 

Kunci stabilitas enterprise UIKit terletak pada:
1. **Pemisahan Peran Deterministik**: Mencegah MVC dengan memisahkan Presenter, Interactor, dan Coordinator.
2. **Pembersihan GPU Pipeline**: Mengeliminasi off-screen rendering via deklarasi `shadowPath` eksplisit dan isolasi pemotongan gambar.
3. **Disiplin Manajemen Memori**: Menghindari retain cycles pada setiap escaping closure dan relasi coordinator child-parent.
4. **Main Thread Preservation**: Menjalankan diffing, deserialisasi data, dan pre-sizing teks di background thread sehingga frame rate 120 FPS ProMotion tetap terjaga secara konsisten.