# BAB 08: Quiz, Challenge, & Knowledge Check
**Pengujian Perangkat Lunak Komprehensif (XCTest & UI Testing)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Siklus Hidup Eksekusi `XCTestCase` dan Alokasi Memori Instans
Jelaskan siklus hidup (*lifecycle*) eksekusi satu *test suite* yang berisi beberapa fungsi uji dalam `XCTestCase`. Mengapa Apple mendesain `XCTest` untuk menginisiasi ulang instans `XCTestCase` pada setiap pemanggilan *test method*, dan apa implikasi arsitekturalnya terhadap penggunaan properti instans versus pembersihan pada `tearDownWithError()`?

<details>
<summary>Jawaban & Analisis Teknis</summary>

**Analisis Siklus Hidup:**
Ketika *test runner* mengeksekusi kelas turunan `XCTestCase`, alur yang terjadi adalah:
1. `+ (void)setUp` / `class func setUp()` (Level Kelas): Dipanggil satu kali sebelum ada *test method* yang dijalankan dalam *class* tersebut.
2. Untuk setiap *test method* (misal: `testA()`, `testB()`):
   - Instans baru dari `XCTestCase` dialokasikan di memori (*instantiation*).
   - `setUpWithError()` / `setUp()` dipanggil pada instans tersebut.
   - Fungsi pengujian (`testA()`) dieksekusi.
   - `tearDownWithError()` / `tearDown()` dipanggil pada instans tersebut.
   - Blok yang didaftarkan melalui `addTeardownBlock {}` dieksekusi dalam urutan LIFO (*Last-In, First-Out*).
3. `+ (void)tearDown` / `class func tearDown()` (Level Kelas): Dipanggil satu kali setelah seluruh *test method* selesai dieksekusi.

**Tujuan Desain Instansiasi Ulang:**
Desain ini bertujuan untuk menjamin **Isolasi Mutlak (Hermetic State)** antar-pengujian. Dengan membuat *instance* baru untuk setiap metode uji, XCTest berupaya meminimalisasi kebocoran *state* lokal (misalnya properti non-statis) dari `testA` ke `testB`.

**Implikasi Arsitektural dan Kebocoran Memori (Memory Bloat):**
Meskipun instans baru dibuat untuk setiap tes, *test runner* XCTest tetap mempertahankan referensi ke seluruh instans `XCTestCase` yang telah selesai dieksekusi hingga seluruh rangkaian *suite* tuntas demi kebutuhan pelaporan (*test reporting*). 

Jika seorang *engineer* menginisialisasi properti instans yang memakan memori besar (misal: *sut* / *System Under Test* berupa database in-memory, view hierarchy, atau image buffer) di dalam `setUpWithError()` tanpa melepaskannya (*nil-out*) di `tearDownWithError()`, objek-objek tersebut akan tetap tertahan di memori (akumulasi *retained memory*). Oleh karena itu, praktik wajib pada pengujian enterprise adalah:
```swift
override func tearDownWithError() throws {
    sut = nil
    dependency = nil
    try super.tearDownWithError()
}
```
</details>

---

### Soal 1.2: Taksonomi Test Doubles Berdasarkan Standar Gerard Meszaros pada Ekosistem Swift
Definisikan dan bedakan secara presisi kelima varian *Test Double* (Dummy, Stub, Spy, Mock, Fake) dalam konteks bahasa Swift yang berbasis *strong static typing* dan *Protocol-Oriented Programming (POP)*. Berikan satu contoh struktural singkat untuk membedakan antara **Spy** dan **Mock**.

<details>
<summary>Jawaban & Analisis Teknis</summary>

**Taksonomi Test Doubles:**
1. **Dummy:** Objek yang dioper ke dalam sistem tetapi tidak pernah digunakan atau dieksekusi sama sekali. Biasanya hanya digunakan untuk memenuhi parameter tanda tangan fungsi (misal: konfigurasi dummy, token kosong).
2. **Stub:** Objek yang menyediakan respons terprogram (*canned answers*) terhadap panggilan metode yang dilakukan selama pengujian. Stub tidak memverifikasi apakah panggilan tersebut benar-benar terjadi; ia hanya memfasilitasi jalur eksekusi SUT.
3. **Spy:** Objek yang membungkus fungsi Stub tetapi secara aktif merekam informasi/metadata tentang cara pemanggilannya (misal: frekuensi eksekusi, argumen yang dioper, urutan eksekusi) untuk kemudian diasersikan di akhir pengujian.
4. **Mock:** Objek yang diprogram sebelumnya dengan *ekspektasi* perilaku spesifik (aturan asserting terdefinisi di awal). Mock memverifikasi interaksi secara ketat; pengujian akan otomatis gagal jika interaksi yang diekspektasikan tidak terjadi sesuai spesifikasi.
5. **Fake:** Objek yang memiliki implementasi kerja fungsional yang valid namun disederhanakan sehingga tidak cocok untuk lingkungan produksi (misalnya: `InMemoryUserRepository` yang menggunakan `Dictionary` lokal alih-alih koneksi SQLite/CoreData).

**Perbedaan Struktural Spy vs Mock dalam Swift:**

```swift
// Target Protocol
protocol PaymentGateway {
    func processPayment(amount: Decimal) async throws -> Bool
}

// SPY: Merekam interaksi, asersi dilakukan manual pasca-eksekusi (State/Behavior Verification via Inspection)
final class PaymentGatewaySpy: PaymentGateway {
    private(set) var processPaymentCallCount = 0
    private(set) var capturedAmounts: [Decimal] = []
    var stubbedResult: Result<Bool, Error> = .success(true)

    func processPayment(amount: Decimal) async throws -> Bool {
        processPaymentCallCount += 1
        capturedAmounts.append(amount)
        return try stubbedResult.get()
    }
}
// Di Test Method (Spy):
// sut.checkout()
// XCTAssertEqual(spy.processPaymentCallCount, 1)
// XCTAssertEqual(spy.capturedAmounts.first, 100.0)

// MOCK: Memiliki ekspektasi internal yang memvalidasi dirinya sendiri (Direct Behavior Verification)
final class PaymentGatewayMock: PaymentGateway {
    var expectedAmount: Decimal?
    var expectationFulfilled = false

    func expectProcessPayment(amount: Decimal) {
        self.expectedAmount = amount
    }

    func processPayment(amount: Decimal) async throws -> Bool {
        if let expected = expectedAmount, expected == amount {
            expectationFulfilled = true
            return true
        }
        XCTFail("Unexpected interaction: Processed \(amount), expected \(String(describing: expectedAmount))")
        return false
    }

    func verify() {
        XCTAssertTrue(expectationFulfilled, "Expected processPayment was not called with \(String(describing: expectedAmount))")
    }
}
// Di Test Method (Mock):
// mock.expectProcessPayment(amount: 100.0)
// sut.checkout()
// mock.verify()
```
</details>

---

### Soal 1.3: Asynchronous Testing: Primitive `XCTestExpectation` vs Modern Swift Concurrency (`async/await`)
Bandingkan mekanisme internal pengujian asinkron menggunakan *traditional blocking expectations* (`XCTestExpectation`, `wait(for:timeout:)`) dengan pengujian *first-class concurrency* (`async/await` dalam *test methods*). Kapan penggunaan `XCTestExpectation` tetap menjadi pilihan wajib di era modern Swift?

<details>
<summary>Jawaban & Analisis Teknis</summary>

**Perbandingan Mekanisme Internal:**
- **Traditional Expectations (`wait(for:timeout:)`):**
  Menggunakan mekanisme *blocking* pada *thread/runloop* saat ini. Pemanggilan `wait` menghentikan alur pengujian dengan memutar `CFRunLoop` secara berulang (*polling/spinning*) sampai flag `isFulfilled` bernilai `true` atau batas *timeout* tercapai. Jika thread utama terblokir oleh operasi lain secara sinkron, mekanisme ini dapat memicu *deadlock*.
- **Modern Concurrency (`testMethod() async throws`):**
  Dieksekusi langsung di atas *Cooperative Thread Pool* Swift Concurrency. Tidak ada pemblokiran RunLoop; pengujian menangguhkan (*suspends*) eksekusinya menggunakan titik suspensi non-blocking via instruksi `await`. Kode pengujian berperilaku seperti *asynchronous task* biasa, menjaga integritas penjadwalan *actor-isolated code*.

**Kasus di Mana `XCTestExpectation` Tetap Wajib Digunakan:**
1. **Inverted Expectations (Pengujian Negatif):**
   Memverifikasi bahwa suatu *event* **tidak boleh terjadi** dalam batas waktu tertentu (misal: delegasi tidak boleh dipanggil saat token tidak valid):
   ```swift
   let invertedExp = expectation(description: "Delegate must not be invoked")
   invertedExp.isInverted = true
   ```
2. **Kuantitas Panggilan Tertentu (*Fulfillment Count*):**
   Memvalidasi bahwa suatu *callback* atau *notification* dieksekusi tepat $N$ kali (misal: data sinkronisasi menembakkan sinyal progress sebanyak 5 kali):
   ```swift
   expectation.expectedFulfillmentCount = 5
   ```
3. **Pemberitahuan Asinkron Multicast / NSNotificationCenter / Combine:**
   Ketika menguji sistem yang memancarkan *event* melalui `NotificationCenter` atau Combine publisher multi-emisi yang belum/tidak diubah menjadi `AsyncSequence`, menggunakan `expectation(forNotification:object:notificationCenter:)` jauh lebih bersih daripada mengonversi manual dengan kontinuation.
</details>

---

### Soal 1.4: Arsitektur Eksekusi UI Testing (`XCUIApplication`) dan Komunikasi Out-of-Process
Bagaimana arsitektur *under-the-hood* dari Apple XCUITest beroperasi? Mengapa *target* UI Test dibangun dalam proses terpisah (*out-of-process*) dari aplikasi utama, dan bagaimana proses pengujian berinteraksi dengan antarmuka aplikasi target?

<details>
<summary>Jawaban & Analisis Teknis</summary>

**Arsitektur Out-of-Process:**
Eksekusi XCUITest melibatkan tiga komponen utama:
1. **Target Application Process:** Proses aplikasi utama iOS yang sedang diuji.
2. **Test Runner Process (`<AppName>UITests-Runner`):** Aplikasi *driver* independen yang memuat bundel pengujian kita.
3. **Accessibility Daemon (`com.apple.Accessibility` / `AXRuntime`):** Layanan sistem iOS yang mengelola pohon aksesibilitas.

```
+-----------------------------------------------------------+
|                   Test Runner Process                     |
|  (XCUIApplication, XCUIElementQuery, XCTAssert, XCTest)   |
+-----------------------------+-----------------------------+
                              |
                     IPC (XPC Interface)
                              |
+-----------------------------v-----------------------------+
|               macOS/iOS Accessibility Core                |
|                    (Daemon / AXRuntime)                   |
+-----------------------------+-----------------------------+
                              |
                     IPC (XPC Interface)
                              |
+-----------------------------v-----------------------------+
|                 Target Application Process                |
|         (UIWindow, UIView / SwiftUI Render Tree)          |
+-----------------------------------------------------------+
```

**Alasan Desain Out-of-Process:**
- **Integritas Isolasi:** Jika aplikasi target mengalami *crash* atau *unhandled exception*, *test runner* tidak ikut mati (*abort*). Runner dapat mendeteksi crash aplikasi secara akurat, mencatat call stack, dan melaporkan kegagalan dengan tepat.
- **Simulasi Pengguna Nyata:** Pengujian tidak boleh memanipulasi *state* internal *in-memory* secara langsung (seperti memodifikasi variabel `viewModel.state = .success`). Runner harus berinteraksi layaknya pengguna fisik eksternal melalui simulasi sentuhan dan *event synthesis* (melalui IOHIDEvent via daemon sistem).

**Mekanisme Interaksi:**
Ketika `XCUIApplication().buttons["Login"].tap()` dipanggil:
1. *Runner* mengirim kueri melalui *Inter-Process Communication* (IPC / XPC) ke subsistem Accessibility sistem operasi.
2. Subsistem mengekstrak pohon representasi UI (*Accessibility Snapshot*) dari aplikasi target.
3. Elemen dicocokkan berdasarkan `accessibilityIdentifier`, `accessibilityLabel`, atau tipe *traits*.
4. Sistem menghitung koordinat titik layar dan menginjeksi perintah sentuhan *hardware level* (*touch event dispatch*) langsung ke aplikasi target.
</details>

---

### Soal 1.5: Kode Metrik vs Kualitas Nyata: Batasan Line Coverage
Mengapa pencapaian 100% *Line Coverage* tidak menjamin keandalan sistem (*correctness*) dalam produksi, dan apa perbedaan konsepnya dengan *Branch Coverage* serta *Condition/Decision Coverage* (MCDC)?

<details>
<summary>Jawaban & Analisis Teknis</summary>

**Kelemahan Fundamental Line Coverage:**
*Line Coverage* hanya mengukur apakah baris kode tertentu pernah dieksekusi satu kali oleh instruksi pointer selama fase pengetesan. Metrik ini sepenuhnya mengabaikan:
1. Kualitas asersi (baris kode bisa dieksekusi 100% tanpa adanya `XCTAssert`).
2. Kombinasi *state*, variasi data input, dan *side-effects*.
3. Penanganan kondisi batas (*boundary conditions*, integer overflow, nil coalescing).

**Perbedaan Taksonomi Coverage:**
- **Line/Statement Coverage:** Mengukur persentase instruksi baris yang tersentuh.
- **Branch (Decision) Coverage:** Mengukur apakah setiap cabang dari struktur kendali logika (setiap jalur `if/else`, `guard`, `switch-case`, `ternary operator`) telah dievaluasi pada kondisi *true* dan *false*.
- **Condition/Decision Coverage (C/DC) & MCDC (Modified Condition/Decision Coverage):** Menguji setiap sub-kondisi boolean independen di dalam suatu ekspresi majemuk (misal: `if A && (B || C)`). MCDC menuntut bahwa setiap parameter (`A`, `B`, `C`) terbukti dapat mengubah hasil keputusan secara independen tanpa dipengaruhi variabel lain.

**Studi Kasus Kegagalan Line Coverage:**
```swift
func calculateDiscount(price: Double, isMember: Bool, couponValid: Bool) -> Double {
    var discount = 0.0
    if isMember || couponValid { // Line tersentuh jika isMember = true
        discount = price * 0.1
    }
    return price - discount
}
```
*Dengan 100% Line Coverage via satu pengujian tunggal (`isMember: true, couponValid: false`), logika cacat pada validitas kupon (`couponValid`) tidak akan pernah teruji.*
</details>

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Race Conditions pada Unstructured Task dalam Asynchronous Test Suites
Perhatikan potongan kode pengujian berikut:

```swift
final class OrderViewModelTests: XCTestCase {
    var sut: OrderViewModel!
    var analyticsSpy: AnalyticsServiceSpy!

    override func setUpWithError() throws {
        analyticsSpy = AnalyticsServiceSpy()
        sut = OrderViewModel(analytics: analyticsSpy)
    }

    func test_submitOrder_logsAnalyticsEvent() {
        sut.submitOrder()
        XCTAssertEqual(analyticsSpy.loggedEvents.count, 1) // Terkadang gagal (Flaky) di CI!
    }
}
```
Jika `sut.submitOrder()` memicu operasi menggunakan `Task { ... }` (*unstructured concurrency*), jelaskan secara mendalam akar penyebab ketidakstabilan (*flakiness*) pengujian ini pada mesin CI, dan berikan solusi arsitektural berbasis *deterministic testing* tanpa menggunakan `Thread.sleep` atau `Task.sleep`.

<details>
<summary>Jawaban & Analisis Teknis</summary>

**Akar Penyebab (*Root Cause*):**
`Task { ... }` membuat sebuah *unstructured concurrent task* yang dijadwalkan secara asinkron di atas *global cooperative thread pool*. Tidak ada hubungan hierarkis (*no structured lifecycle*) antara `Task` tersebut dengan konteks pemanggil sinkron di `test_submitOrder_logsAnalyticsEvent()`. 

Ketika `sut.submitOrder()` kembali (*returns*), instruksi pengetesan langsung melompat ke baris `XCTAssertEqual`. Terjadi *race condition* antara penjadwalan `Task` di background worker threads dengan eksekusi asersi di main thread. Pada mesin CI dengan beban CPU tinggi atau jumlah core terbatas, eksekusi `Task` sering kali belum sempat berjalan sebelum asersi dievaluasi, memicu *intermittent failure* (*flaky*).

**Solusi Arsitektural Tanpa Sleep (Inversion of Control via Synchronous Engine / Concurrency Injection):**

*Pendekatan 1: Menghindari Unstructured Task di Domain Model dengan mengekspos tanda tangan `async`.*
Jadikan `submitOrder()` sebagai fungsi `async`:
```swift
func test_submitOrder_logsAnalyticsEvent() async {
    await sut.submitOrder()
    XCTAssertEqual(analyticsSpy.loggedEvents.count, 1)
}
```

*Pendekatan 2: Structured Suspend via Yield/Continuation Injection pada Spy.*
Jika `submitOrder()` mutlak harus sinkron dari kacamata UI framework, Spy harus memiliki kapabilitas sinkronisasi via `AsyncStream` atau `CheckedContinuation`:

```swift
final class AnalyticsServiceSpy: AnalyticsService {
    private var continuation: CheckedContinuation<Void, Never>?
    private(set) var loggedEvents: [Event] = []

    func log(event: Event) {
        loggedEvents.append(event)
        continuation?.resume()
        continuation = nil
    }

    func waitForEvent() async {
        if !loggedEvents.isEmpty { return }
        await withCheckedContinuation { cont in
            self.continuation = cont
        }
    }
}

// Di dalam Unit Test:
func test_submitOrder_logsAnalyticsEvent() async {
    sut.submitOrder()
    await analyticsSpy.waitForEvent()
    XCTAssertEqual(analyticsSpy.loggedEvents.count, 1)
}
```
</details>

---

### Soal 2.2: Intersepsi Jaringan Tingkat Rendah dengan Custom `URLProtocol`
Bagaimana cara kerja internal `URLProtocol` dalam mengintersepsi *network traffic* pada level `URLSession` selama Unit Testing? Jelaskan potensi jebakan (*pitfalls*) terkait konkurensi, mutasi state global, dan penanganan HTTP Body Stream yang sering merusak eksekusi paralel pengujian!

<details>
<summary>Jawaban & Analisis Teknis</summary>

**Mekanisme Internal `URLProtocol`:**
`URLProtocol` adalah kelas abstrak dari Foundation yang berfungsi memperluas atau mengkustomisasi protokol komunikasi URL (seperti HTTP/HTTPS). 
1. Saat suatu request dimulai via `URLSession`, session memeriksa array `protocolClasses` pada konfigurasi konfigurasinya (`URLSessionConfiguration`).
2. Sistem mengeksekusi metode statis `canInit(with:)` secara berantai pada seluruh protocol yang terdaftar.
3. Protocol pertama yang mengembalikan nilai `true` akan bertanggung jawab penuh mengelola siklus hidup request tersebut (`startLoading()`, `stopLoading()`).
4. Custom implementation mengirimkan respons sintetis kembali ke `client` (`URLProtocolClient`) melalui pemanggilan `urlProtocol(_:didReceive:redirectionPolicy:)`, `urlProtocol(_:didLoad:)`, dan `urlProtocolDidFinishLoading(_:)`.

**Jebakan Konkurensi & Mutasi Global State:**
1. **Pencemaran Lingkungan Global (`URLProtocol.registerClass`):**
   Mendaftarkan custom protocol secara global melalui `URLProtocol.registerClass(MockURLProtocol.self)` berdampak pada `URLSession.shared` di seluruh thread. Ini menyebabkan *test pollution* ketika unit test dijalankan secara paralel (*parallel execution enabled*). 
   *Solusi:* Hindari `registerClass` global; gunakan selalu instansiasi eksplisit:
   ```swift
   let config = URLSessionConfiguration.ephemeral
   config.protocolClasses = [MockURLProtocol.self]
   let session = URLSession(configuration: config)
   ```
2. **Kondisi Balapan (*Race Conditions*) pada Shared Stub Handler:**
   Jika `MockURLProtocol` menyimpan mapping URL ke stub response menggunakan `static var stubs: [URL: Data]`, penulisan dan pembacaan paralel dari beberapa test case akan memicu `EXC_BAD_ACCESS` (data race).
   *Solusi:* Isolasi storage stub menggunakan thread-safe serial queue atau Actor:
   ```swift
   final class MockURLProtocol: URLProtocol {
       private static let lock = NSLock()
       private static var _requestHandler: ((URLRequest) throws -> (HTTPURLResponse, Data))?
       
       static var requestHandler: ((URLRequest) throws -> (HTTPURLResponse, Data))? {
           get { lock.withLock { _requestHandler } }
           set { lock.withLock { _requestHandler = newValue } }
       }
   }
   ```
3. **HTTPBody Hilang pada Body Streams:**
   Pada arsitektur NSURLSession modern, properti `request.httpBody` sering kali bernilai `nil` karena data dialihkan ke dalam bentuk input stream (`request.httpBodyStream`). Jika pengujian bergantung pada inspeksi payload request POST/PUT tanpa membaca `httpBodyStream`, validasi payload akan gagal.
</details>

---

### Soal 2.3: Pendeteksian Kebocoran Memori (Retain Cycle) Secara Otomatis dalam Unit Test
Buatlah fungsi pembantu (*test helper*) generik dalam `XCTestCase` yang memverifikasi bahwa suatu objek dilepaskan (*deallocated*) dari memori secara semestinya setelah siklus uji berakhir. Jelaskan mekanisme kerja instruksi dan peran `addTeardownBlock` dalam pola ini.

<details>
<summary>Jawaban & Analisis Teknis</summary>

**Implementasi Test Helper:**

```swift
extension XCTestCase {
    /// Melacak objek untuk memastikan objek didealloc setelah test method selesai dieksekusi.
    /// Jika objek masih bertahan di memori, test akan memicu kegagalan (Memory Leak).
    func trackForMemoryLeaks(
        _ instance: AnyObject,
        file: StaticString = #filePath,
        line: UInt = #line
    ) {
        // 1. Tangkap objek via weak pointer untuk memecah retain count
        weak var weakInstance = instance
        
        // 2. Daftarkan blok teardown yang akan dieksekusi setelah metode pengujian tuntas
        addTeardownBlock { [weak weakInstance] in
            // 3. Verifikasi apakah objek masih eksis di memori
            XCTAssertNil(
                weakInstance,
                "Instance target mengalami memory leak (retain cycle terdeteksi)! Objek tidak dideallokasi.",
                file: file,
                line: line
            )
        }
    }
}
```

**Mekanisme Kerja dan Peran `addTeardownBlock`:**
1. **Weak Reference Pointer:**
   Dengan menangkap instans target secara `weak` (`weak var weakInstance = instance`), reference counter ARC pada objek tersebut tidak bertambah.
2. **Timing Eksekusi `addTeardownBlock`:**
   Blok yang didaftarkan ke `addTeardownBlock` memiliki sifat LIFO dan dieksekusi **tepat setelah** fungsi pengujian lokal selesai dan seluruh variabel lokal di *stack frame* pengujian keluar dari cakupan (*out of scope*).
3. **Penyelidikan Evaluasi:**
   Jika arsitektur kode bersih (misal tidak ada *strong retain cycle* antara ViewModel dan Coordinator/Closure), pelepasan referensi lokal di akhir metode tes akan menyebabkan `retain count` turun ke angka 0, sehingga objek dihapus dan `weakInstance` otomatis bermutasi menjadi `nil`. Jika terjadi retain cycle, pointer tetap hidup, `weakInstance` tidak bernilai `nil`, dan `XCTAssertNil` gagal mencatat error tepat di baris konfigurasi SUT.
</details>

---

### Soal 2.4: Deep Dive Performa: Metrik `measure(metrics:options:block:)` dan Pengukuran Statis
Bagaimana cara kerja pengukuran performa pada `XCTest` menggunakan `measure(metrics:options:block:)`? Analisis perbedaan metrik antara `XCTClockMetric`, `XCTCPUMetric`, `XCTMemoryMetric`, dan `XCTOSSignpostMetric`, serta strategi mengatasi *high standard deviation* pada lingkungan eksekusi CI/CD!

<details>
<summary>Jawaban & Analisis Teknis</summary>

**Karakteristik Metrik:**
- **`XCTClockMetric`:** Mengukur waktu dinding riil (*wall-clock time*) yang berlalu dari titik awal hingga akhir eksekusi blok. Rentan terhadap fluktuasi *context switching* CPU dan *background thread stealing*.
- **`XCTCPUMetric`:** Mengukur waktu CPU murni yang dihabiskan oleh proses saat mengeksekusi instruksi, termasuk instruksi per siklus dan utilisasi core. Metrik ini mengeliminasi deviasi akibat penundaan I/O (*I/O wait time*).
- **`XCTMemoryMetric`:** Melacak jejak penggunaan memori fisik (khususnya *Peak Physical Memory Use* / *Resident Set Size*). Sangat krusial untuk mencegah degradasi alokasi pada pemrosesan citra atau deserialisasi berkas raksasa.
- **`XCTOSSignpostMetric`:** Mengukur rentang waktu interval tertentu yang dipancarkan secara terprogram melalui `os_signpost` / `OSSignposter` di dalam kode domain, memungkinkan isolasi pengukuran pada sub-sistem internal spesifik tanpa mengukur overhead pengujian.

**Mekanisme Pengukuran dan Kalibrasi:**
XCTest secara default mengulang blok uji sebanyak 10 kali (iterasi 1 sering kali merupakan *warm-up iteration*). Sistem menghitung rata-rata dan deviasi standar (*standard deviation*). Baseline disimpan dalam file `.xctestconfiguration` target.

**Strategi Mengatasi High Standard Deviation di Mesin CI/CD:**
1. **Isolasi Mesin CI (Noisy Neighbor Elimination):** Jangan menjalankan pengujian performa di shared container/virtual machine yang memiliki pembagian CPU secara elastis (misal: burstable AWS instances). Gunakan dedicated bare-metal runner (misal: Mac Studio / Mac Mini on-premise).
2. **Pra-pemanasan Cache & RunLoop:** Inisialisasi dependensi global sebelum masuk ke blok `measure`. Hindari inisialisasi *first-time disk I/O* di dalam blok loop pengujian.
3. **Kombinasi Pengaturan `XCTMeasureOptions`:**
   ```swift
   let options = XCTMeasureOptions()
   options.iterationCount = 15 // Tingkatkan sampel statistik
   measure(metrics: [XCTCPUMetric()], options: options) {
       // Operasi deterministic
   }
   ```
4. **Relaksasi Toleransi Baseline:** Tetapkan ambang batas deviasi yang realistis di Scheme Settings (misal: toleransi 10%-15% alih-alih nilai ketat 2.5% default Xcode).
</details>

---

### Soal 2.5: Optimasi Query Traversing pada `XCUIElementQuery`
Perhatikan pemanggilan UI testing berikut yang memicu *test timeout*:

```swift
let label = app.descendants(matching: .any)
               .element(matching: .staticText, identifier: "transaction_status_label")
label.tap()
```
Jelaskan mengapa pendekatan kueri di atas menghancurkan efisiensi pengujian (*performance penalty*) dari sudut pandang *accessibility tree traversal*, dan bagaimana cara memperbaikinya dengan memanfaatkan predikat langsung dan `.firstMatch`.

<details>
<summary>Jawaban & Analisis Teknis</summary>

**Analisis Traversal dan Kemacetan Performa (*Performance Penalty*):**
1. **Eksplorasi Pohon Secara Eksponensial:**
   `app.descendants(matching: .any)` memaksa XCTest melakukan traversal rekursif mendalam (*depth-first search*) ke **seluruh** simpul pohon aksesibilitas aplikasi target, mengumpulkan ribuan elemen individual terlepas dari jenisnya (UIWindow, UIView, UITableViewCell, Icon, dll.) menjadi representasi snapshot IPC raksasa.
2. **Evaluasi Tertunda yang Berulang (*Uncached Lazy Evaluation*):**
   `XCUIElementQuery` bersifat lazy. Pemanggilan rantai kueri di atas tidak langsung mengembalikan elemen, melainkan membangun *query chain AST*. Saat `.tap()` dieksekusi, XCTest mengevaluasi seluruh query tree dari awal. Jika elemen UI mengalami animasi atau re-render sekilas, query akan mengulang parsing seluruh pohon XML aksesibilitas tersebut berkali-kali.
3. **Ketiadaan Limitasi Pencarian:**
   Secara default, `element(...)` mencoba memastikan elemen unik dan mengevaluasi seluruh sisa dokumen untuk mengidentifikasi potensi ambiguitas (*multiple matches check*).

**Solusi Optimal Menggunakan `.firstMatch` dan Typed Direct Query:**

```swift
// OPTIMASI: Resolusi Instan
let label = app.staticTexts["transaction_status_label"].firstMatch
label.tap()
```

**Alasan Peningkatan Performa:**
- **Penyempitan Domain:** `app.staticTexts` hanya menyaring simpul bertipe `UIAccessibilityTraitStaticText` / label, memangkas lebih dari 80% simpul yang tidak relevan di awal.
- **Pemanfaatan Direct Keyed Subscript:** Sintaks `["identifier"]` langsung memetakan lookup ke dictionary `accessibilityIdentifier` pada level platform API.
- **`.firstMatch` Short-circuiting:** Memberitahu test runner untuk **segera menghentikan** traversal traversal pohon aksesibilitas begitu elemen valid pertama yang cocok ditemukan, menghilangkan kalkulasi sisa pohon DOM UI.
</details>

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Pipeline CI/CD: Meledaknya Execution Time & Test Suite Freeze
Sebuah aplikasi SuperApp perbankan memiliki 1.200 Unit Test dan 150 UI Test. Setelah migrasi ke mesin CI baru, durasi build & test pipeline membengkak secara anomali dari 12 menit menjadi 1 jam 15 menit, bahkan sering kali mengalami *hard timeout (freeze)* secara acak pada tahapan UI testing.

```
[CI Log Snapshot]
10:14:02  Executed 1200 unit tests, with 0 failures in 45.2 seconds.
10:14:48  Starting UI tests...
10:22:15  t =    45.12s Find: Descendants matching type Any
10:35:40  t =   850.21s Assertion Failure: Waiting for element to appear timed out...
10:48:00  [FATAL ERROR] CI Runner killed process due to exceeding 60-minute execution cap.
```

#### Pertanyaan Diagnostik & Solusi Skenario A:
1. Analisis faktor apa saja yang menyebabkan fenomena *freeze* dan degradasi performa UI Test hingga 10x lipat pada lingkungan CI simulator!
2. Rancang strategi arsitektural komprehensif untuk mereduksi waktu eksekusi UI Test tersebut kembali di bawah 15 menit tanpa memangkas jumlah cakupan skenario pengujian!

<details>
<summary>Solusi Teknis Lengkap</summary>

**1. Analisis Faktor Penyebab (*Root Causes*):**
- **Overhead Animasi UI:** Simulator CI merender seluruh animasi CoreAnimation secara penuh (default duration). Loading spinners, transition screen, dan pulse animations memaksa `XCUIApplication` menunggu proses diam (*idle wait*) sebelum mencoba berinteraksi, membuang waktu ratusan detik.
- **Simulator Audio/Video & Logging Saturation:** Mesin CI tanpa akselerasi grafis GPU (headless software rendering) tercekik saat memproses render layout dan I/O logging aksesibilitas sistem.
- **Kueri Tidak Efisien (Deep Tree Scanning):** Log `Descendants matching type Any` menandakan adanya kueri buruk (seperti yang dibahas di soal 2.5) yang memindai seluruh pohon aksesibilitas ribuan kali.
- **Sequential Execution Single Simulator:** 150 skenario UI test dijalankan secara sekuensial pada satu simulator tanpa paralelisasi tingkat proses.

**2. Rencana Remediasi Arsitektural:**

*A. Eliminasi Animasi Sistemik (App Launch Injection)*
Suntikkan flag via Launch Arguments untuk mematikan seluruh animasi layer pada aplikasi target selama fase test:
```swift
// Di dalam Base UITest Case
let app = XCUIApplication()
app.launchArguments.append("-UITests_DisableAnimations")
app.launch()

// Di dalam AppDelegate / SceneDelegate Aplikasi
if CommandLine.arguments.contains("-UITests_DisableAnimations") {
    UIView.setAnimationsEnabled(false)
    UIApplication.shared.keyWindow?.layer.speed = 100.0 // Fast-forward layer transitions
}
```

*B. Implementasi Test Sharding dan Simulator Parallelization*
Ubah skema CI untuk mengeksekusi pengujian secara paralel menggunakan `xcodebuild`:
```bash
xcodebuild test-without-building \
  -workspace SuperApp.xcworkspace \
  -scheme SuperAppUITests \
  -destination 'platform=iOS Simulator,name=iPhone 15,OS=latest' \
  -parallel-testing-enabled YES \
  -maximum-concurrent-test-simulator-destinations 4
```
Ini membagi 150 UI Test ke dalam 4 klon simulator independen (*Simulator Clones*) secara simultan.

*C. Migrasi dari Real Screen Flow ke Deep Linking Test Targets*
Hindari menguji skenario fitur dalam (misal: "Transfer Sukses") dengan memulai flow dari Splash Screen $\to$ Login $\to$ OTP $\to$ Dashboard $\to$ Transfer. Gunakan custom internal URL Schemes / Deep Links via `app.open(url)` untuk langsung membuka screen target dengan state ter-mock.
</details>

---

### Skenario B: Race Condition & Data Corruption pada CoreData / SwiftData Parallel Testing
Setelah mengaktifkan fitur *Execute in Parallel* pada skema Unit Test Xcode untuk mempercepat proses pengujian, tim backend-frontend mendapati pengujian modul sinkronisasi database (`DatabaseSyncTests`) sering mengalami `EXC_BAD_ACCESS` atau kegagalan asersi data acak (*flaky data assertions*). 

```
[Stack Trace Crash Log]
Thread 7 Crashed:
0   CoreData   0x00000001a18209c8 _execute + 124
1   CoreData   0x00000001a1835bc4 -[NSManagedObjectContext executeFetchRequest:error:] + 580
2   SuperApp   0x0000000104a32b00 specialized SyncWorker.merge(records:) (SyncWorker.swift:84)
3   SuperAppTests 0x0000000106b20c12 DatabaseSyncTests.test_sync_insertsUniqueRecords() (DatabaseSyncTests.swift:42)
```

#### Pertanyaan Diagnostik & Solusi Skenario B:
1. Mengapa eksekusi paralel memicu kegagalan fatal pada CoreData/SwiftData meskipun pengujian menggunakan *In-Memory Store*?
2. Bagaimana cara mengisolasi *Storage Layer Dependency Injection* agar setiap unit test method dapat dieksekusi secara fully parallel, thread-safe, dan deterministik tanpa polusi data antar *worker threads*?

<details>
<summary>Solusi Teknis Lengkap</summary>

**1. Akar Masalah (*Root Cause*):**
- **Shared Persistent Container (Singleton Pollution):** Modul pengujian menggunakan instance bersama (`PersistentContainer.shared` atau `DataStore.shared`). Ketika dua worker thread paralel mengeksekusi dua test method berbeda, keduanya membaca dan menulis ke container yang sama.
- **Konkurensi Konteks (Thread Confinement Violation):** `NSManagedObjectContext` (khususnya tipe default `.mainQueueConcurrencyType`) tidak bersifat *thread-safe*. Paralelisasi XCTest menjalankan thread pengujian pada *worker pool* yang berbeda. Memanggil `executeFetchRequest` atau `save()` dari thread sembarang tanpa membungkusnya dalam `perform` atau `performAndWait` akan langsung memicu *concurrency violation crash* (`EXC_BAD_ACCESS`).
- **Disk I/O Collisions pada /dev/null:** Menetapkan konfigurasi In-Memory melalui URL `/dev/null` pada persistent store terkadang tetap membuat file lock temporal di direktori shared cache sistem jika nama store identifier-nya identik antar-proses.

**2. Remediasi Arsitektur: Isolated Stack Factory per Test:**

```swift
// Test-Specific Persistent Factory
final class TestCoreDataStackFactory {
    static func createCleanInMemoryStack() -> NSPersistentContainer {
        let model = NSManagedObjectModel.mergedModel(from: [Bundle.main])!
        let container = NSPersistentContainer(name: "TestSuperAppModel", managedObjectModel: model)
        
        let description = NSPersistentStoreDescription()
        description.type = NSInMemoryStoreType
        // Gunakan UUID unik agar antar instance test tidak pernah bertabrakan di level CoreData memory cache
        description.url = URL(fileURLWithPath: "/dev/null/\(UUID().uuidString)")
        
        container.persistentStoreDescriptions = [description]
        
        container.loadPersistentStores { description, error in
            if let error = error {
                fatalError("Gagal inisialisasi In-Memory Store: \(error)")
            }
        }
        return container
    }
}

// Di Dalam Test Case
final class DatabaseSyncTests: XCTestCase {
    private var container: NSPersistentContainer!
    private var context: NSManagedObjectContext!
    private var sut: SyncWorker!

    override func setUpWithError() throws {
        try super.setUpWithError()
        // Buat instance STACK BARU yang terisolasi mutlak untuk setiap test method
        container = TestCoreDataStackFactory.createCleanInMemoryStack()
        context = container.newBackgroundContext()
        context.automaticallyMergesChangesFromParent = true
        
        sut = SyncWorker(context: context)
    }

    override func tearDownWithError() throws {
        sut = nil
        context = nil
        container = nil
        try super.tearDownWithError()
    }

    func test_sync_insertsUniqueRecords() async throws {
        let payload = [RecordDTO(id: 1), RecordDTO(id: 2)]
        
        // Eksekusi thread-safe via context actor / background runner
        try await context.perform {
            try self.sut.merge(records: payload)
            let fetch: NSFetchRequest<RecordMO> = RecordMO.fetchRequest()
            let count = try self.context.count(for: fetch)
            XCTAssertEqual(count, 2)
        }
    }
}
```
</details>

---

### Skenario C: UI Testing Mengalami Kegagalan Masif Akibat Dinamika Remote API & Image Caching
Dalam rangkaian regression test harian, 60% UI Test pada fitur E-Commerce Checkout gagal serempak. Investigasi menunjukkan bahwa kegagalan terjadi karena:
1. API Staging sedang mengalami *maintenance downtime*, sehingga aplikasi menampilkan alert *Network Error*.
2. Gambar produk yang diunduh secara asinkron dari CDN pihak ketiga membutuhkan waktu render 3 detik lebih lama dari biasanya, menyebabkan `XCUIElement.waitForExistence(timeout:)` terlampaui.
3. Sebagian pengujian mencoba melakukan transaksi nyata (*sandbox payment*) yang bergantung pada ketersediaan balance akun demo tertentu yang saldonya telah habis.

```
[UI Test Failure Report]
Failed: test_userCanCompleteCheckout()
Reason: Element 'Payment Confirmation Screen' not found within 10.0s.
Screen Hierarchy: [UIAlertController: "Network Timeout - Unable to reach staging-api.bank.com"]
```

#### Pertanyaan Diagnostik & Solusi Skenario C:
1. Bandingkan secara arsitektural efektivitas dan kerentanan antara:
   - Menjalankan UI Test dengan koneksi ke Server Staging asli.
   - Menjalankan UI Test dengan Embedded Local Mock HTTP Server (misal: Swifter/Criollo) di dalam runner.
   - Menjalankan UI Test menggunakan IPC Mock Injection / App Launch Arguments.
2. Rancang pola implementasi *Page Object Model* (POM) yang diperkuat dengan *State Mocking Strategy* untuk memutus total ketergantungan UI Test dari jaringan eksternal!

<details>
<summary>Solusi Teknis Lengkap</summary>

**1. Analisis Perbandingan Strategi:**

| Kriteria | Real Staging Server | Embedded Mock Server (Localhost) | App Launch Environment Injection |
| :--- | :--- | :--- | :--- |
| **Determinisme** | **Sangat Rendah** (Rentan downtime, data berubah, kuota habis) | **Tinggi** (Mengontrol respons HTTP secara lokal di port 8080) | **Tertinggi** (Mengganti Network Client dengan Fake in-memory) |
| **Kecepatan** | Lambat (tergantung latency jaringan riil) | Cepat (loopback network latency $\approx 1-2$ ms) | Instan (0 ms latency jaringan, memotong layer socket) |
| **Isolasi UI** | Buruk (bukan pengujian murni UI melainkan E2E Integration) | Baik (tetap menguji integrasi layer HTTP networking app) | Sangat Baik (UI berinteraksi murni dengan ViewState siap saji) |
| **Kompleksitas** | Setup awal rendah, pemeliharaan sangat tinggi | Memerlukan dependensi pihak ketiga/port binding management | Memerlukan *code hooks* terpisah dalam arsitektur aplikasi |

**2. Rancangan Solusi: Robust Page Object Model (POM) + Mock Environment Injection**

*A. Pendekatan App Launch Environment Injection:*
Alih-alih menembak HTTP rute luar, arahkan target aplikasi untuk memotong *transport layer* saat mendeteksi flag UI Test:

```swift
// Target App: NetworkFactory.swift
enum NetworkFactory {
    static func createSession() -> URLSession {
        if ProcessInfo.processInfo.arguments.contains("-MockNetworkMode") {
            let config = URLSessionConfiguration.ephemeral
            config.protocolClasses = [LocalFileSystemStubProtocol.self]
            return URLSession(configuration: config)
        }
        return URLSession.shared
    }
}
```

*B. Implementasi Page Object Model (POM):*

```swift
// BASE PAGE OBJECT
class BasePage {
    let app: XCUIApplication
    
    init(app: XCUIApplication) {
        self.app = app
    }
}

// CHECKOUT PAGE OBJECT
final class CheckoutPage: BasePage {
    private var payButton: XCUIElement {
        app.buttons["checkout_pay_button"].firstMatch
    }
    
    private var confirmationModal: XCUIElement {
        app.otherElements["payment_confirmation_modal"].firstMatch
    }
    
    @discardableResult
    func tapPayButton() -> Self {
        XCTAssertTrue(payButton.waitForExistence(timeout: 5.0), "Pay button tidak ditemukan.")
        payButton.tap()
        return self
    }
    
    func verifyPaymentSuccess() {
        XCTAssertTrue(
            confirmationModal.waitForExistence(timeout: 5.0),
            "Payment Confirmation Modal gagal muncul dalam threshold waktu aman."
        )
    }
}

// IMPLEMENTASI TEST CASE
final class CheckoutUITests: XCTestCase {
    private var app: XCUIApplication!

    override func setUpWithError() throws {
        try super.setUpWithError()
        continueAfterFailure = false
        
        app = XCUIApplication()
        // Injeksi state terisolasi
        app.launchArguments = [
            "-UITests_DisableAnimations",
            "-MockNetworkMode",
            "-InitialBalance_1000000" // Seed saldo virtual aman
        ]
        app.launch()
    }

    func test_userCanCompleteCheckout() {
        CheckoutPage(app: app)
            .tapPayButton()
            .verifyPaymentSuccess()
    }
}
```
</details>

---

## 4. Chapter Challenge

### Tantangan Praktis: Membangun Engine Pengujian Mandiri Berstandar Enterprise (Mock Engine, Retain Cycle Detector, & Optimized UI POM)

#### Deskripsi Permasalahan
Anda ditunjuk sebagai Lead Mobile Test Architect di sebuah startup Decacorn Fintech. Tim sering mengeluhkan pengujian unit yang lambat, kebocoran memori tersembunyi yang lolos ke produksi (*OOM Crashes*), serta kegagalan acak pengujian UI. Anda ditugaskan membangun infrastruktur fondasi pengujian internal standar (*zero external library dependencies*).

#### Spesifikasi Kebutuhan & Fitur
1. **Zero-Dependency Network Stubbing Engine (`MockNetworkEngine`):**
   - Bangun implementasi khusus dari `URLProtocol` yang mampu memetakan pasangan `URLRequest` ke HTTP status code, data response, atau error.
   - Harus memiliki mekanisme proteksi *thread-safe* mutlak (mendukung eksekusi *parallel test* Swift 6 Concurrency strict mode).
2. **Automated Memory Leak Assertion Framework:**
   - Bangun utility pembungkus SUT yang mendeteksi apakah instance ViewModel/Coordinator melepaskan diri dari siklus hidup ARC tanpa meninggalkan retain cycle.
3. **Optimized Screen Page Object:**
   - Buat satu skenario UI Test lengkap untuk proses "Transfer Dana" menggunakan pola Page Object Model. Wajib menerapkan optimasi `.firstMatch`, zero sleep, dan asersi deterministik berbasis state snapshot.

#### Batasan Arsitektural (Constraints)
- Tidak boleh menggunakan library pihak ketiga (*Zero 3rd party pod/SPM seperti Nimble, Quick, Mockingjay, atau Swifter*). Murni menggunakan `XCTest`, `Foundation`, dan API resmi Apple.
- Kompatibel penuh dengan Swift 6 Concurrency (`@Sendable`, `actor-safe`, tidak ada mutable static state tanpa proteksi sinkronisasi).

---

### Kode Solusi Komprehensif (Architecture Blueprint)

```swift
import XCTest
import Foundation

// =============================================================================
// KOMPONEN 1: THREAD-SAFE ZERO-DEPENDENCY NETWORK STUB ENGINE
// =============================================================================

public final class MockNetworkEngine: URLProtocol, @unchecked Sendable {
    public struct StubResponse: Sendable {
        let statusCode: Int
        let data: Data
        let headers: [String: String]?
        let error: Error?

        public init(statusCode: Int = 200, data: Data = Data(), headers: [String: String]? = nil, error: Error? = nil) {
            self.statusCode = statusCode
            self.data = data
            self.headers = headers
            self.error = error
        }
    }

    // Thread-Safe State Store menggunakan NSLock
    private static let lock = NSLock()
    private static var stubs: [URL: StubResponse] = [:]
    private static var wildcardHandler: (@Sendable (URLRequest) -> StubResponse?)?

    public static func registerStub(url: URL, response: StubResponse) {
        lock.withLock {
            stubs[url] = response
        }
    }

    public static func registerWildcardHandler(_ handler: @escaping @Sendable (URLRequest) -> StubResponse?) {
        lock.withLock {
            wildcardHandler = handler
        }
    }

    public static func reset() {
        lock.withLock {
            stubs.removeAll()
            wildcardHandler = nil
        }
    }

    public override class func canInit(with request: URLRequest) -> Bool {
        return true // Intersepsi seluruh traffic pada session yang terkonfigurasi
    }

    public override class func canonicalRequest(for request: URLRequest) -> URLRequest {
        return request
    }

    public override func startLoading() {
        MockNetworkEngine.lock.lock()
        let targetURL = request.url
        let stub = targetURL.flatMap { MockNetworkEngine.stubs[$0] } ?? MockNetworkEngine.wildcardHandler?(request)
        MockNetworkEngine.lock.unlock()

        guard let responseData = stub else {
            let error = NSError(domain: "MockNetworkEngine", code: -1004, userInfo: [NSLocalizedDescriptionKey: "Stub tidak terdaftar untuk URL: \(String(describing: targetURL))"])
            client?.urlProtocol(self, didFailWithError: error)
            return
        }

        if let error = responseData.error {
            client?.urlProtocol(self, didFailWithError: error)
            return
        }

        let response = HTTPURLResponse(
            url: request.url ?? URL(string: "https://localhost")!,
            statusCode: responseData.statusCode,
            httpVersion: "HTTP/1.1",
            headerFields: responseData.headers
        )!

        client?.urlProtocol(self, didReceive: response, redirectionPolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: responseData.data)
        client?.urlProtocolDidFinishLoading(self)
    }

    public override func stopLoading() {
        // Cleanup jika connection dibatalkan
    }
}

// Factory Helper untuk Testing
public enum TestURLSessionFactory {
    public static func makeSession() -> URLSession {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [MockNetworkEngine.self]
        return URLSession(configuration: configuration)
    }
}

// =============================================================================
// KOMPONEN 2: SYSTEM UNDER TEST (SUT) & DOMAIN DUMMY
// =============================================================================

public final class TransferCoordinator {
    public var onTransferCompleted: (() -> Void)?
    
    // Potensi Retain Cycle jika closure memegang reference coordinator
    public func complete() {
        onTransferCompleted?()
    }
}

public final class TransferViewModel {
    private let session: URLSession
    public private(set) var isProcessing = false
    public var coordinator: TransferCoordinator?

    public init(session: URLSession = .shared, coordinator: TransferCoordinator? = nil) {
        self.session = session
        self.coordinator = coordinator
    }

    public func executeTransfer(amount: Decimal, recipientID: String) async throws -> Bool {
        isProcessing = true
        defer { isProcessing = false }

        let url = URL(string: "https://api.fintech.com/v1/transfer")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        
        let (data, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            return false
        }
        
        let success = (try? JSONSerialization.jsonObject(with: data) as? [String: Any])?["success"] as? Bool ?? false
        if success {
            coordinator?.complete()
        }
        return success
    }
}

// =============================================================================
// KOMPONEN 3: UNIT TEST ENGINE WITH MEMORY LEAK TRACKER
// =============================================================================

final class TransferViewModelTests: XCTestCase {
    private var sut: TransferViewModel!
    private var session: URLSession!
    private var coordinator: TransferCoordinator!

    override func setUpWithError() throws {
        try super.setUpWithError()
        MockNetworkEngine.reset()
        session = TestURLSessionFactory.makeSession()
        coordinator = TransferCoordinator()
        sut = TransferViewModel(session: session, coordinator: coordinator)
    }

    override func tearDownWithError() throws {
        sut = nil
        coordinator = nil
        session = nil
        MockNetworkEngine.reset()
        try super.tearDownWithError()
    }

    func test_transferSuccess_triggersCoordinator_andFreesMemory() async throws {
        // 1. Memory Leak Tracking Guard
        trackForMemoryLeaks(sut)
        trackForMemoryLeaks(coordinator)

        // 2. Setup Deterministic Stub Response
        let targetURL = URL(string: "https://api.fintech.com/v1/transfer")!
        let jsonResponse = """
        {"success": true, "transaction_id": "TX_9901"}
        """.data(using: .utf8)!
        
        MockNetworkEngine.registerStub(url: targetURL, response: .init(statusCode: 200, data: jsonResponse))

        // 3. Setup Callback Expectation
        let coordinatorExpectation = expectation(description: "Coordinator transfer completion must be triggered")
        coordinator.onTransferCompleted = { [weak self] in
            // Menggunakan weak self di dalam closure menghindari retain cycle
            _ = self
            coordinatorExpectation.fulfill()
        }

        // 4. Execution
        let isSuccess = try await sut.executeTransfer(amount: 500_000, recipientID: "REC_008")

        // 5. Asersi Logika
        XCTAssertTrue(isSuccess, "Transfer harus berhasil berdasarkan stub respons.")
        XCTAssertFalse(sut.isProcessing, "State processing harus di-reset ke false.")
        await fulfillment(of: [coordinatorExpectation], timeout: 1.0)
    }
}

// Helper Memory Leak Extractor
extension XCTestCase {
    func trackForMemoryLeaks(_ instance: AnyObject, file: StaticString = #filePath, line: UInt = #line) {
        weak var weakInstance = instance
        addTeardownBlock { [weak weakInstance] in
            XCTAssertNil(
                weakInstance,
                "MEMORy LEAK: Objek [\(String(describing: weakInstance))] masih dialokasikan di heap memory. Periksa strong reference cycle.",
                file: file,
                line: line
            )
        }
    }
}

// =============================================================================
// KOMPONEN 4: OPTIMIZED UI TEST (PAGE OBJECT MODEL WITH FAST SHORT-CIRCUIT)
// =============================================================================

public final class TransferScreenPageObject {
    private let app: XCUIApplication

    public init(app: XCUIApplication) {
        self.app = app
    }

    // Direct Traversing Optimizations
    private var recipientInputField: XCUIElement {
        app.textFields["transfer_input_recipient"].firstMatch
    }

    private var amountInputField: XCUIElement {
        app.textFields["transfer_input_amount"].firstMatch
    }

    private var sendButton: XCUIElement {
        app.buttons["transfer_button_submit"].firstMatch
    }

    private var successBanner: XCUIElement {
        app.otherElements["transfer_success_indicator"].firstMatch
    }

    @discardableResult
    public func enterRecipient(_ id: String) -> Self {
        XCTAssertTrue(recipientInputField.waitForExistence(timeout: 2.0), "Field penerima tidak ditemukan")
        recipientInputField.tap()
        recipientInputField.typeText(id)
        return self
    }

    @discardableResult
    public func enterAmount(_ amount: String) -> Self {
        XCTAssertTrue(amountInputField.waitForExistence(timeout: 2.0), "Field nominal tidak ditemukan")
        amountInputField.tap()
        amountInputField.typeText(amount)
        return self
    }

    @discardableResult
    public func submitTransfer() -> Self {
        XCTAssertTrue(sendButton.waitForExistence(timeout: 2.0), "Tombol kirim tidak aktif")
        sendButton.tap()
        return self
    }

    public func assertTransferSuccessDisplayed() {
        XCTAssertTrue(
            successBanner.waitForExistence(timeout: 3.0),
            "Banner sukses tidak muncul dalam batas waktu aman"
        )
    }
}

final class TransferFlowUITests: XCTestCase {
    private var app: XCUIApplication!

    override func setUpWithError() throws {
        try super.setUpWithError()
        continueAfterFailure = false
        
        app = XCUIApplication()
        // Fast UI Configurations
        app.launchArguments = [
            "-UITests_DisableAnimations",
            "-MockNetworkMode",
            "-DirectScreen_Transfer"
        ]
        app.launch()
    }

    func test_completeTransferFlow_deterministicExecution() {
        TransferScreenPageObject(app: app)
            .enterRecipient("REC_99212")
            .enterAmount("150000")
            .submitTransfer()
            .assertTransferSuccessDisplayed()
    }
}
```

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Bahwa instans `XCTestCase` dialokasikan ulang untuk setiap *test method*, namun referensinya tetap disimpan hingga seluruh *suite* selesai sehingga pembersihan di `tearDownWithError()` mutlak diperlukan untuk mencegah *memory bloat*.
- [ ] Perbedaan fundamental antara Dummy, Stub, Spy, Mock, dan Fake, serta implementasi *Protocol-Oriented Testing* tanpa memerlukan dynamic runtime mock injection.
- [ ] Mekanisme kerja `XCTestExpectation` vs penangguhan non-blocking `async/await` dalam menguji aliran konkurensi Swift 6.
- [ ] Arsitektur Out-of-Process `XCUIApplication` yang berkomunikasi via IPC/XPC dengan Accessibility Daemon sistem operasi.
- [ ] Bahwa 100% *Line Coverage* tidak menjamin kebebasan aplikasi dari *runtime bugs*, dan mengapa pengujian wajib mengukur *Decision/Condition Coverage* (MCDC).
- [ ] Mekanisme kerja `URLProtocol` sebagai *transport interception layer* serta resiko *state leakage* dalam eksekusi pengujian secara paralel.
- [ ] Penggunaan `addTeardownBlock` dan `weak reference assertions` untuk mengaudit *retain cycle* pada ViewModel/Coordinator secara otomatis.

### Saya tidak perlu menghafal:
- [ ] Seluruh daftar konstanta string raw API Accessibility Traits iOS (`UIAccessibilityTraits`). Cukup memahami representasi abstraksi query di XCTest.
- [ ] Nilai eksak internal konfigurasi metrik performa `XCTMeasureOptions` default. Konfigurasi ini dapat disesuaikan per target sistem di Scheme Xcode.
- [ ] Implementasi internal method forwarding Objective-C runtime yang digunakan mock framework lama (seperti OCMock). Pola modern berbasis protokol murni Swift jauh lebih aman dan direkomendasikan.

### Saya harus bisa melakukan:
- [ ] Mengonfigurasi skema pengujian untuk eksekusi paralel (*Parallel Testing*) dengan aman tanpa memicu *data race* atau tabrakan storage in-memory.
- [ ] Mematikan seluruh animasi aplikasi secara terprogram (*App Launch Injection*) guna memangkas durasi pengujian UI di pipeline CI/CD.
- [ ] Menulis arsitektur UI Testing berbasis *Page Object Model* (POM) dengan pemanfaatan `.firstMatch` dan spesifikasi traversal presisi untuk mengeliminasi *flaky tests*.
- [ ] Mengisolasi *Network Layer* secara total menggunakan Custom `URLProtocol` tanpa ketergantungan pada library pihak ketiga.
- [ ] Menganalisis *crash log* dan *diagnostic snapshot* pengujian untuk membedakan antara kerusakan murni kode domain (*assertion failure*) dan kegagalan lingkungan uji (*timeout / thread starvation*).