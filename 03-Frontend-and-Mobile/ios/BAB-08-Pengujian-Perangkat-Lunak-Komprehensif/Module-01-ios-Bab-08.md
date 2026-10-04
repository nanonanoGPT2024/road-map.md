# MODUL 08: TESTING & QUALITY ASSURANCE
## Unit 01: Pengujian Perangkat Lunak Komprehensif (XCTest & UI Testing)

---

### SEKSI 01 — IDENTITAS MODUL
* **Kategori:** 03-Frontend-and-Mobile
* **Jalur Kurikulum:** iOS Engineering (Advanced Level)
* **Topik Utama:** Pengujian Perangkat Lunak Komprehensif (XCTest, Asynchronous Testing, UI Testing, & Mocking Engine)
* **Prasyarat Pengetahuan:** Swift 5.9+, Concurrency (`async/await`, Actor model), Clean Architecture (VIPER/MVVM-C), Dependency Injection, Protocol-Oriented Programming (POP).
* **Target Kompetensi:** Mampu merancang, mengimplementasikan, dan mengotomatisasi suite pengujian deterministik berstandar *enterprise* yang mencakup Unit Test, Integration Test, UI Test dengan *accessibility identifiers*, serta mengisolasi subsistem jaringan menggunakan protokol dan *custom URLProtocol*.

---

### SEKSI 02 — LEARNING OBJECTIVES
1. **Menguasai Siklus Hidup XCTest:** Mengonfigurasi *test harness*, mengelola alokasi dan dealokasi state antar *test case*, serta memahami eksekusi internal `setUpWithError()` dan `tearDownWithError()`.
2. **Menguji Kode Asinkron Determinik:** Mengimplementasikan pengujian berbasis *structured concurrency* Swift modern (`async/await`) dan `XCTestExpectation` tanpa memicu *flakiness* atau *race condition*.
3. **Membangun Arsitektur Test Double:** Merancang *Mocks*, *Stubs*, *Spies*, dan *Fakes* berbasis protokol serta menerapkan *intercepting network layer* menggunakan `URLProtocol`.
4. **Otomatisasi UI Testing Berbasis Page Object Pattern (POP):** Menulis UI Tests yang resilient dengan memanfaatkan `XCUIElement`, `XCUIApplication`, dan *Accessibility Identifiers* tanpa *hardcoded sleep*.
5. **Mengevaluasi & Mengoptimalkan Code Coverage:** Mengidentifikasi metrik *branch coverage*, menghapus dependensi implisit (*side-effects*), dan mengeliminasi *flaky tests* pada pipeline CI/CD.

---

### SEKSI 03 — MINDSET & MENTAL MODEL
Pengujian perangkat lunak di iOS bukan sekadar memvalidasi fungsi yang mengembalikan nilai benar; ini adalah **kontrak arsitektural**. 

```
+-------------------------------------------------------------------------+
|                              MENTAL MODEL                               |
|                                                                         |
|   Kode Produksi (System Under Test / SUT)  <--->  Test Double Injection |
|                     |                                                   |
|                     v                                                   |
|             State Mutation / I/O Output                                 |
|                     |                                                   |
|                     v                                                   |
|        Assertion Verification (XCTAssert...)                            |
+-------------------------------------------------------------------------+
```

1. **State Isolation:** Setiap unit test harus dijalankan di dalam *sandbox* absolut. Tidak boleh ada status yang bocor (*leaked state*) dari tes A ke tes B.
2. **Inversion of Control for Testability:** Jika sebuah kode sulit diuji, kesalahan hampir selalu berada pada arsitekturnya, bukan pada framework pengujian. Ketergantungan erat (*tight coupling*) pada singleton sistem (`URLSession.shared`, `NotificationCenter.default`, `UserDefaults.standard`) harus dipecah menjadi dependensi berbasis protokol.
3. **Flakiness Zero-Tolerance:** Tes yang gagal sesekali (*flaky test*) lebih berbahaya daripada ketiadaan tes sama sekali. Tes harus deterministik: input $X$ pada kondisi $Y$ harus **selalu** menghasilkan output $Z$, tanpa terpengaruh kondisi jaringan fisik, latensi prosesor, atau zona waktu sistem.

---

### SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Diagram berikut mengilustrasikan interaksi arsitektur antara pengujian unit (Unit Test Harness) terhadap *System Under Test* (SUT), penggunaan *Mock Network Engine* berbasis `URLProtocol`, serta mekanisme koordinasi pengujian UI (*Out-of-Process UI Testing*).

```
+---------------------------------------------------------------------------------------+
|                                    XCTest Framework                                   |
+---------------------------------------------------------------------------------------+
                                           |
                 +-------------------------+-------------------------+
                 |                                                   |
                 v                                                   v
   [ IN-PROCESS UNIT TESTING ]                         [ OUT-OF-PROCESS UI TESTING ]
+------------------------------------+              +-----------------------------------+
|  XCTestCase Runner                 |              |  Target Test Runner Process       |
|  - Lifecycle Management            |              |  - XCUIApplication Proxy          |
|  - Assertion Evaluation            |              |  - IPC / XPC Communication        |
+-----------------+------------------+              +-----------------+-----------------+
                  |                                                   |
                  v                                                   v (Accessibility API)
+------------------------------------+              +-----------------------------------+
|  System Under Test (SUT)           |              |  Target Application Process       |
|  - ViewModels / UseCases / Domains |              |  - Springboard Accessibility Tree |
|  - Injected Dependencies           |              |  - Rendered Views Hierarchy       |
+-----------------+------------------+              +-----------------------------------+
                  |
                  v (Network Abstraction Layer)
+------------------------------------+
|  URLSession (Custom Configuration) |
|  +------------------------------+  |
|  | Interceptor: MockURLProtocol |  |
|  +------------------------------+  |
|                 |                  |
|                 v                  |
|     [ In-Memory Stub Response ]    |
+------------------------------------+
```

---

### SEKSI 05 — ANATOMI & MEKANISME INTERNAL

#### Siklus Hidup `XCTestCase`
`XCTestCase` mengisolasi setiap fungsi tes dengan membuat instance baru dari kelas pengujian untuk setiap metode yang diawali dengan kata `test`.

```
                    +------------------------------------+
                    |       Class Allocation (Init)      |
                    +-----------------+------------------+
                                      |
                                      v
                    +------------------------------------+
                    |        setUpWithError()            |
                    |  (Alokasi SUT & Mock Environment)  |
                    +-----------------+------------------+
                                      |
                                      v
                    +------------------------------------+
                    |         testMethodExecution()      |
                    |    (Arrange -> Act -> Assert)      |
                    +-----------------+------------------+
                                      |
                                      v
                    +------------------------------------+
                    |       tearDownWithError()          |
                    |   (Deallokasi SUT / Reset State)   |
                    +-----------------+------------------+
                                      |
                                      v
                    +------------------------------------+
                    |      Class Deallocation (Deinit)   |
                    +------------------------------------+
```

* **XCTest Runner Execution Plan:** XCTest menginspeksi runtime Objective-C/Swift via refleksi untuk menemukan pemanggilan fungsi bersignature `test*() -> Void` atau `test*() async throws -> Void`.
* **Asynchronous Wait Loops:** Ketika memanggil `fulfillment(of:timeout:)` atau `await`, XCTest memutar run loop saat ini (`CFRunLoopRunInMode`) untuk menangani event sembari memblokir kelanjutan sekuensial fungsi tes hingga timeout atau pemenuhan predikat tercapai.
* **UI Testing Inter-Process Communication (IPC):** `XCUIApplication` berjalan pada proses terpisah dari aplikasi iOS utama. Komunikasi terjadi melalui antarmuka aksesibilitas privat OS (*XPC Framework*). Apple Accessibility Engine mengekspos representasi pohon visual aplikasi dalam bentuk snapshot elemen antarmuka (`XCUIElementQuery`).

---

### SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

#### 1. Tipologi Test Doubles (Gerard Meszaros Taxonomy)
Dalam pengembangan berstandar industri, istilah "Mock" sering disalahartikan. Secara akademis dan teknis, test doubles terbagi menjadi:
* **Dummy:** Objek yang diteruskan tetapi tidak pernah digunakan (hanya untuk mengisi parameter fungsi).
* **Stub:** Objek yang menyediakan jawaban siap saji (*hardcoded response*) untuk pemanggilan fungsi selama pengujian.
* **Spy:** Objek yang mencatat informasi pemanggilan (berapa kali fungsi dipanggil, argumen apa yang diteruskan) untuk kemudian diverifikasi.
* **Mock:** Objek yang dikonfigurasi secara deklaratif dengan ekspektasi spesifik yang harus dipenuhi; gagal secara otomatis jika ekspektasi meleset.
* **Fake:** Implementasi fungsional nyata namun disederhanakan dan tidak cocok untuk produksi (misalnya, *In-Memory Database* berbasis dictionary).

#### 2. Isolation Network Menggunakan `URLProtocol`
Pengujian unit tidak boleh melakukan koneksi socket TCP/IP fisik ke server backend asli. Menggunakan `URLProtocol` memungkinkan pengujian mengintersepsi semua alur data `URLSessionConfiguration` pada level paling bawah di Network Core Foundation layer tanpa perlu merusak struktur kode produksi.

#### 3. Determinisme UI Testing Melalui Accessibility
`XCUIElementQuery` mengevaluasi pohon elemen secara *lazy*. Kueri tidak dieksekusi saat didefinisikan, melainkan saat aksi (seperti `.tap()`) atau pembacaan properti (seperti `.exists`) dipanggil. Memahami traversal pohon UI ini krusial untuk mencegah UI Test hang atau crash akibat *stale elements*.

---

### SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi fundamental pengujian unit sinkron dan asinkron menggunakan protokol dependensi dan assertion native.

```swift
import XCTest

// MARK: - Production Contracts & Domain Logic
protocol BankAccountManaging: AnyObject {
    var balance: Decimal { get }
    func deposit(amount: Decimal) throws
    func withdraw(amount: Decimal) throws
    func fetchRemoteConversionRate(for currency: String) async throws -> Decimal
}

enum AccountError: Error, Equatable {
    case invalidAmount
    case insufficientFunds(available: Decimal, required: Decimal)
    case networkFailure
}

final class BankAccount: BankAccountManaging {
    private(set) var balance: Decimal
    private let networkSession: URLSession

    init(initialBalance: Decimal = 0.0, session: URLSession = .shared) {
        self.balance = initialBalance
        self.networkSession = session
    }

    func deposit(amount: Decimal) throws {
        guard amount > 0 else { throw AccountError.invalidAmount }
        balance += amount
    }

    func withdraw(amount: Decimal) throws {
        guard amount > 0 else { throw AccountError.invalidAmount }
        guard balance >= amount else {
            throw AccountError.insufficientFunds(available: balance, required: amount)
        }
        balance -= amount
    }

    func fetchRemoteConversionRate(for currency: String) async throws -> Decimal {
        guard let url = URL(string: "https://api.bank.internal/rates/\(currency)") else {
            throw AccountError.networkFailure
        }
        
        do {
            let (data, response) = try await networkSession.data(from: url)
            guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
                throw AccountError.networkFailure
            }
            guard let rateString = String(data: data, encoding: .utf8),
                  let rate = Decimal(string: rateString) else {
                throw AccountError.networkFailure
            }
            return rate
        } catch {
            throw AccountError.networkFailure
        }
    }
}

// MARK: - Unit Test Harness
final class BankAccountTests: XCTestCase {
    private var sut: BankAccount!

    override func setUpWithError() throws {
        try super.setUpWithError()
        // Diinisialisasi ulang sebelum setiap test method berjalan
        sut = BankAccount(initialBalance: 100.0)
    }

    override func tearDownWithError() throws {
        // Melakukan pembersihan state secara eksplisit untuk mencegah memory leaks antar suite
        sut = nil
        try super.tearDownWithError()
    }

    func test_deposit_withValidAmount_shouldIncreaseBalance() throws {
        // Arrange
        let depositAmount: Decimal = 50.0
        let expectedBalance: Decimal = 150.0

        // Act
        try sut.deposit(amount: depositAmount)

        // Assert
        XCTAssertEqual(sut.balance, expectedBalance, "Saldo akhir tidak sesuai dengan nominal deposit.")
    }

    func test_withdraw_withAmountExceedingBalance_shouldThrowInsufficientFunds() {
        // Arrange
        let withdrawAmount: Decimal = 200.0
        let expectedError = AccountError.insufficientFunds(available: 100.0, required: 200.0)

        // Act & Assert
        XCTAssertThrowsError(try sut.withdraw(amount: withdrawAmount)) { error in
            guard let accountError = error as? AccountError else {
                XCTFail("Tipe error yang dilempar tidak sesuai ekspektasi: \(error)")
                return
            }
            XCTAssertEqual(accountError, expectedError, "Detail status insufficient funds tidak valid.")
        }
    }
}
```

---

### SEKSI 08 — ANALISIS BARIS DEMI BARIS

* **Baris 4–9:** `protocol BankAccountManaging` mendeklarasikan kontrak antarmuka domain. Menggunakan protokol memungkinkan kita mengganti implementasi nyata dengan *Test Doubles* secara mulus tanpa mengubah arsitektur level atas.
* **Baris 11–15:** `enum AccountError: Error, Equatable`. Mengadopsi protokol `Equatable` sangat penting agar assertion `XCTAssertEqual` dapat membandingkan nilai error secara komprehensif, termasuk *associated value*-nya.
* **Baris 54–64:** `setUpWithError()` dan `tearDownWithError()`. Menggantikan versi legacy non-error throwing. Jika proses inisialisasi pada setup melempar error, runtime XCTest langsung menandai tes sebagai *Failed* dan menghentikan eksekusi tanpa memicu *Fatal Crash*. Menyetel `sut = nil` pada teardown memastikan instance dibersihkan dari memori (mencegah *retained memory leaks*).
* **Baris 66–76:** Menjalankan pendekatan *AAA Pattern (Arrange, Act, Assert)*. Ini merupakan standar tata kelola tes terstruktur.
* **Baris 78–90:** `XCTAssertThrowsError(try sut.withdraw(...))` mengevaluasi kegagalan kontrol alur program. *Trailing closure* menerima objek `Error` yang kemudian di-*downcast* secara eksplisit untuk memverifikasi apakah tipe dan konteks error sesuai dengan parameter batasan logika bisnis.

---

### SEKSI 09 — STUDI KASUS NYATA
**Skenario Produksi:** Sebuah aplikasi perbankan digital *FinTech* skala besar memiliki modul otentikasi login kritis. Login melibatkan:
1. Memvalidasi format kredensial.
2. Mengirim request enkripsi ke backend via API Gateway.
3. Menyimpan securely *AccessToken* ke dalam Keychain.
4. Menavigasi user ke Dashboard UI jika berhasil, atau menampilkan dialog alert jika gagal.

**Tantangan Teknis:**
* Suite tes tidak boleh melakukan *network hit* ke server *staging/production* selama CI berjalan.
* Pengujian UI harus tahan terhadap latensi animasi antarmuka dan tidak boleh menggunakan `sleep(seconds)`.
* Komponen pengujian harus memverifikasi bahwa *Keychain* benar-benar menerima payload tanpa merusak data *Keychain* lingkungan simulator lokal pengembang.

---

### SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

#### 1. Interseptor Jaringan Tingkat Rendah (`MockURLProtocol`)
```swift
import Foundation

final class MockURLProtocol: URLProtocol {
    private static let queue = DispatchQueue(label: "com.engine.MockURLProtocol.queue")
    private static var mockHandlers: [URL: (URLRequest) throws -> (HTTPURLResponse, Data)] = [:]

    static func setHandler(for url: URL, handler: @escaping (URLRequest) throws -> (HTTPURLResponse, Data)) {
        queue.sync { mockHandlers[url] = handler }
    }

    static func resetHandlers() {
        queue.sync { mockHandlers.removeAll() }
    }

    override class func canInit(with request: URLRequest) -> Bool {
        guard let url = request.url else { return false }
        return queue.sync { mockHandlers[url] != nil }
    }

    override class func canonicalRequest(for request: URLRequest) -> URLRequest {
        return request
    }

    override func startLoading() {
        guard let url = request.url else {
            client?.urlProtocol(self, didFailWithError: URLError(.badURL))
            return
        }

        let handler: ((URLRequest) throws -> (HTTPURLResponse, Data))? = Self.queue.sync {
            Self.mockHandlers[url]
        }

        guard let currentHandler = handler else {
            client?.urlProtocol(self, didFailWithError: URLError(.unsupportedURL))
            return
        }

        do {
            let (response, data) = try currentHandler(request)
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: data)
            client?.urlProtocolDidFinishLoading(self)
        } catch {
            client?.urlProtocol(self, didFailWithError: error)
        }
    }

    override func stopLoading() {}
}
```

#### 2. Service & ViewModel Layer Produksi
```swift
import Foundation

struct UserCredentials {
    let email: String
    let token: String
}

protocol AuthenticationKeychianManaging {
    func saveToken(_ token: String) -> Bool
}

final class AuthenticationViewModel {
    private let session: URLSession
    private let keychainManager: AuthenticationKeychianManaging
    
    enum State: Equatable {
        case idle
        case authenticating
        case authenticated(userToken: String)
        case error(String)
    }

    private(set) var state: State = .idle

    init(session: URLSession, keychainManager: AuthenticationKeychianManaging) {
        self.session = session
        self.keychainManager = keychainManager
    }

    func login(email: String) async {
        state = .authenticating
        guard email.contains("@") else {
            state = .error("Format email tidak valid.")
            return
        }

        let endpoint = URL(string: "https://auth.fintech.internal/v1/authenticate")!
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.httpBody = try? JSONSerialization.data(withJSONObject: ["email": email])

        do {
            let (data, response) = try await session.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
                state = .error("Gagal otentikasi: Server menolak.")
                return
            }

            guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let token = json["token"] as? String else {
                state = .error("Payload data server korup.")
                return
            }

            let isSaved = keychainManager.saveToken(token)
            if isSaved {
                state = .authenticated(userToken: token)
            } else {
                state = .error("Penyimpanan token lokal gagal.")
            }
        } catch {
            state = .error(error.localizedDescription)
        }
    }
}
```

#### 3. Enterprise Unit Test Suite Menggunakan Test Doubles
```swift
import XCTest

final class KeychainManagerSpy: AuthenticationKeychianManaging {
    private(set) var saveTokenCallCount = 0
    private(set) var capturedTokens: [String] = []
    var stubbedSuccess: Bool = true

    func saveToken(_ token: String) -> Bool {
        saveTokenCallCount += 1
        capturedTokens.append(token)
        return stubbedSuccess
    }
}

final class AuthenticationViewModelTests: XCTestCase {
    private var sut: AuthenticationViewModel!
    private var keychainSpy: KeychainManagerSpy!
    private var customSession: URLSession!
    private let targetAuthURL = URL(string: "https://auth.fintech.internal/v1/authenticate")!

    override func setUpWithError() throws {
        try super.setUpWithError()
        
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [MockURLProtocol.self]
        customSession = URLSession(configuration: config)
        
        keychainSpy = KeychainManagerSpy()
        sut = AuthenticationViewModel(session: customSession, keychainManager: keychainSpy)
    }

    override func tearDownWithError() throws {
        MockURLProtocol.resetHandlers()
        customSession = nil
        keychainSpy = nil
        sut = nil
        try super.tearDownWithError()
    }

    func test_login_whenRemoteServiceReturnsSuccess_shouldSaveTokenAndMutateState() async throws {
        // Arrange
        let expectedToken = "JWT-SECURE-TOKEN-XYZ-12345"
        let successPayload = """
        {"token": "\(expectedToken)"}
        """.data(using: .utf8)!

        MockURLProtocol.setHandler(for: targetAuthURL) { request in
            let response = HTTPURLResponse(
                url: self.targetAuthURL,
                statusCode: 200,
                httpVersion: nil,
                headerFields: ["Content-Type": "application/json"]
            )!
            return (response, successPayload)
        }

        // Act
        await sut.login(email: "staff.engineer@fintech.internal")

        // Assert
        XCTAssertEqual(keychainSpy.saveTokenCallCount, 1, "Keychain harus dipanggil tepat satu kali.")
        XCTAssertEqual(keychainSpy.capturedTokens.first, expectedToken, "Token yang disimpan tidak identik.")
        XCTAssertEqual(sut.state, .authenticated(userToken: expectedToken), "State mesin ViewModel harus authenticated.")
    }

    func test_login_whenInvalidEmailProvided_shouldTransitionToErrorStateWithoutNetworkHit() async {
        // Arrange
        let invalidEmail = "invalid-email-format"

        // Act
        await sut.login(email: invalidEmail)

        // Assert
        XCTAssertEqual(keychainSpy.saveTokenCallCount, 0, "Keychain tidak boleh dipanggil jika validasi gagal di awal.")
        XCTAssertEqual(sut.state, .error("Format email tidak valid."))
    }
}
```

#### 4. UI Testing Berstandar Enterprise (Page Object Pattern)
Berikut adalah implementasi UI Test yang menguji alur Login end-to-end secara aman dan deterministik.

```swift
// MARK: - Page Object Implementation
import XCTest

struct LoginPageObject {
    private let app: XCUIApplication

    init(app: XCUIApplication) {
        self.app = app
    }

    // Accessibility Elements Identifiers
    private var emailTextField: XCUIElement {
        app.textFields["UI_TEST_LOGIN_EMAIL_FIELD"]
    }

    private var loginButton: XCUIElement {
        app.buttons["UI_TEST_LOGIN_SUBMIT_BUTTON"]
    }

    private var dashboardHeader: XCUIElement {
        app.staticTexts["UI_TEST_DASHBOARD_TITLE"]
    }

    @discardableResult
    func typeEmail(_ email: String) -> LoginPageObject {
        XCTAssertTrue(emailTextField.waitForExistence(timeout: 5.0), "Email Textfield tidak muncul pada UI.")
        emailTextField.tap()
        emailTextField.typeText(email)
        return self
    }

    @discardableResult
    func tapSubmit() -> LoginPageObject {
        XCTAssertTrue(loginButton.waitForExistence(timeout: 2.0), "Submit button tidak interaktif.")
        loginButton.tap()
        return self
    }

    func verifyNavigatedToDashboard() {
        XCTAssertTrue(dashboardHeader.waitForExistence(timeout: 7.0), "Gagal berpindah ke halaman Dashboard.")
    }
}

// MARK: - UI Test Runner Execution
final class AuthenticationUITests: XCTestCase {
    private var app: XCUIApplication!

    override func setUpWithError() throws {
        try super.setUpWithError()
        continueAfterFailure = false // Menghentikan pengujian jika step pertama sudah gagal total
        app = XCUIApplication()
        
        // Pass launch environment parameters to bypass production authenticators during testing
        app.launchArguments = ["--ui-testing", "--mock-network"]
        app.launchEnvironment = ["MOCK_SERVER_MODE": "SUCCESS"]
        app.launch()
    }

    override func tearDownWithError() throws {
        app = nil
        try super.tearDownWithError()
    }

    func test_completeLoginFlow_successfullyNavigatesToDashboard() {
        let loginPage = LoginPageObject(app: app)

        loginPage
            .typeEmail("admin@bank.internal")
            .tapSubmit()
            .verifyNavigatedToDashboard()
    }
}
```

---

### SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter Evaluasi | Unit Testing (`XCTest`) | Integration Testing | UI Testing (`XCUIElement`) |
| :--- | :--- | :--- | :--- |
| **Eksekusi Waktu (Execution Time)** | Sangat Cepat (< 1-10 ms per test) | Sedang (50 - 500 ms per test) | Lambat (2 - 30 detik per skenario) |
| **Tingkat Flakiness** | Nol (jika pure isolated) | Rendah hingga Sedang | Cenderung Tinggi (Render, Animasi) |
| **Biaya Pemeliharaan (Maintenance)** | Rendah | Sedang | Sangat Tinggi (Perubahan UI konstan) |
| **Fokus Deteksi Bug** | Algoritma, State Logic, Edge Cases | Interaksi antar layer modul | User Workflow & Inter-process render |
| **Isolasi Masalah** | Sangat Presisi (Nama baris & fungsi) | Tingkat Modul | Sulit (UI Hierarchy crash, visual block) |
| **Konstruksi Mock/Stub** | Wajib untuk *all external I/O* | Sebagian (komunikasi antar layer) | Tidak menggunakan in-memory mocks secara langsung |

---

### SEKSI 12 — EDGE CASES & PITFALLS

1. **Race Conditions pada Asynchronous Expectations:** 
   * *Problem:* Memanggil `expectation.fulfill()` lebih dari satu kali secara paralel memicu fatal runtime crash pada `XCTest`.
   * *Mitigation:* Gunakan flag proteksi konkurensi atau `async/await` modern native tanpa explicit callback blocks jika memungkinkan.
2. **Main Thread Deadlock:** 
   * *Problem:* Memanggil sinkronisasi blocking `.wait()` pada antrean utama saat menunggu callback yang dijalankan di `DispatchQueue.main`.
   * *Mitigation:* Hindari penggunaan `DispatchSemaphore.wait()` di dalam pengujian unit; manfaatkan `await fulfillment(of: [expectation], timeout: 5.0)`.
3. **Penyimpanan State Sistem (Global Leakage):**
   * *Problem:* Mengubah nilai pada `UserDefaults.standard` atau `Keychain` fisik saat unit test berlangsung meninggalkan jejak yang merusak status tes berikutnya.
   * *Mitigation:* Bungkus *Keychain* dan *UserDefaults* dalam abstraksi protokol. Selalu inject memory-backed fake atau hapus keys suite secara tuntas pada `tearDownWithError()`.

---

### SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

* **Anti-Pattern 1: Penggunaan `sleep(UInt32)` pada UI Testing:**
  ```swift
  // SALAH: Menahan UI Thread secara acak, memperlambat CI, dan tetap rentan gagal jika server lambat.
  loginButton.tap()
  sleep(5)
  XCTAssertTrue(dashboard.exists)

  // BENAR: Menggunakan predicate expectations yang dinamis.
  loginButton.tap()
  XCTAssertTrue(dashboard.waitForExistence(timeout: 5.0), "Dashboard tidak muncul dalam batas waktu.")
  ```

* **Anti-Pattern 2: Melupakan `continueAfterFailure = false`:**
  Jika konfigurasi ini tidak diatur pada UI Testing, tes akan terus memaksa mengeksekusi assertion berikutnya meskipun komponen dasar layar belum muncul. Hal ini menyebabkan ratusan *cascade error logs* palsu di log CI/CD Anda.

* **Anti-Pattern 3: Testing Implementation Details Bukannya Behavior:**
  Memverifikasi apakah variabel internal privat bernilai tertentu merupakan kesalahan fatal. Ujilah **input yang masuk** dan **output/perubahan behavior publik yang dihasilkan**. Menguji detail privat membuat refactor kode mustahil dilakukan tanpa merusak suite tes.

---

### SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Struktur Penamaan Tes yang Standar (GIVEN-WHEN-THEN Style):**
   Gunakan struktur deklaratif: `test_[TargetMethod]_[Condition/State]_[ExpectedOutcome]()`.
   *Contoh:* `test_withdraw_whenBalanceIsZero_shouldThrowInsufficientFundsError()`.
2. **First Class Citizen Accessibility Identifiers:** 
   Jangan mencari elemen UI berdasarkan teks visual yang dapat dilokalisasi (`label: "Masuk"`). Gunakan `.accessibilityIdentifier = "UI_AUTH_SUBMIT_BUTTON"` yang stabil dan tidak terpengaruh oleh lokalisasi multibahasa (*i18n*).
3. **Pemisahan Test Schemes pada CI:** 
   Pisahkan scheme Unit Test (harus dieksekusi pada setiap *Commit / Pull Request*) dan UI Test (dieksekusi terjadwal pada nightly build atau sebelum deploy staging release) guna mempertahankan *feedback loop* developer yang cepat.

---

### SEKSI 15 — OPTIMASI KINERJA & EFISIENSI

1. **Parallel Execution Isolation:** Aktifkan **Execute in parallel** pada skema *Test Action* di Xcode. Untuk mencegah tabrakan data, pastikan tidak ada kode yang menggunakan folder file path lokal hardcoded (`/tmp/cache.json`). Selalu gunakan `FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)`.
2. **Ephemeral URLSession Configurations:** Gunakan konfigurasi `URLSessionConfiguration.ephemeral` alih-alih `URLSessionConfiguration.default`. Ephemeral tidak pernah menulis cookie, disk cache, atau credential store ke flash storage simulator, memangkas I/O overhead hingga ~40%.
3. **Disable Heavy Animations during UI Tests:** Tambahkan argumen peluncuran pada `XCUIApplication` untuk mematikan rendering animasi layer UIView:
   ```swift
   UIView.setAnimationsEnabled(false) // Dieksekusi pada AppDelegate/App Lifecycle saat flag UI Test aktif.
   ```

---

### SEKSI 16 — KEAMANAN & HARDENING

1. **Sanitasi Kredensial Nyata dari Source Code Testing:** Jangan pernah memasukkan private keys, password staging, atau token pengguna aktual ke dalam file *Test Fixtures* atau git repository. Semua data uji harus berupa payload tiruan (*dummy payloads*).
2. **Isolasi Simulator Keychain:** Saat menguji implementasi integrasi Keychain, gunakan access group acak sementara atau mock layer. Jangan mengotori shared access groups simulator yang digunakan oleh developer tools lain.
3. **Deteksi Kebocoran Data (Mock Enforcement):** Konfigurasikan Mocking Framework (`MockURLProtocol`) agar melempar exception atau *assert failure* jika kode produksi mencoba mengirim HTTP call ke domain luar yang tidak terdaftar dalam routing handler test.

---

### SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

1. **Pemanfaatan `XCTAttachment`:**
   Saat UI Test gagal, manfaatkan `XCTAttachment` untuk menyimpan screenshot hierarki visual dan dump string accessibility hierarchy secara otomatis ke Xcode Test Report:
   ```swift
   override func tearDownWithError() throws {
       if let testRun = self.testRun, testRun.failureCount > 0 {
           let screenshot = XCUIScreen.main.screenshot()
           let attachment = XCTAttachment(screenshot: screenshot)
           attachment.lifetime = .deleteOnSuccess
           attachment.name = "CRASH_SCREENSHOT_\(self.name)"
           add(attachment)
       }
       try super.tearDownWithError()
   }
   ```
2. **Diagnostic Activity Tracking:**
   Bungkus langkah UI Test yang rumit menggunakan `XCTContext.runActivity(named:block:)` untuk menghasilkan log hierarkis terstruktur di dashboard Xcode CI:
   ```swift
   XCTContext.runActivity(named: "Memproses Pembayaran Checkout") { _ in
       checkoutButton.tap()
   }
   ```

---

### SEKSI 18 — RINGKASAN & CHEAT SHEET

* `setUpWithError()`: Inisialisasi dependensi SUT.
* `tearDownWithError()`: Dealokasi memori; set instance SUT ke `nil`.
* `XCTAssertEqual(a, b)`: Menilai kesetaraan nilai dua objek berprotokol `Equatable`.
* `XCTAssertNil(a)`: Memastikan objek tidak teralokasi di memori.
* `XCTAssertThrowsError(try ...)`: Memverifikasi pemanggilan fungsi melempar error domain yang valid.
* `expectation(description:)`: Menahan alur kontrol sebelum `fulfillment(of:timeout:)` kedaluwarsa.
* `XCUIApplication().launchArguments`: Mengirim metadata konfigurasi diagnostik ke proses aplikasi host.
* `waitForExistence(timeout:)`: Assertion dinamis untuk memastikan visibilitas UI tanpa menghentikan thread dengan `sleep`.

---

### SEKSI 19 — KUIS EVALUASI PEMAHAMAN

#### 1. Mengapa instansiasi System Under Test (SUT) harus disetel ulang menjadi `nil` pada metode `tearDownWithError()`?
A. Agar kompiler Swift tidak menampilkan warning pembacaan variabel.  
B. Menghapus kebocoran alokasi objek antar eksekusi metode tes, memastikan isolasi lifecycle dan memori pengujian.  
C. Untuk mematikan koneksi internet secara otomatis dari simulator.  
D. Karena runtime Objective-C melarang penggunaan kembali memori yang sama.  

#### 2. Apa konsekuensi arsitektural jika Anda menggunakan `URLSession.shared` langsung di dalam baris kode fungsional ViewModel tanpa Dependency Injection?
A. Kode menjadi tidak bisa dikompilasi oleh Swift Modern Toolchain.  
B. Kecepatan transfer data HTTP meningkat secara dramatis.  
C. Pengujian unit menjadi dependen pada koneksi jaringan eksternal dan tidak dapat diuji secara deterministik menggunakan `MockURLProtocol`.  
D. Keamanan aplikasi akan turun dari TLS 1.3 menjadi plaintext secara otomatis.  

#### 3. Mengapa penggunaan `sleep(4)` dikategorikan sebagai anti-pattern berat di UI Testing?
A. Karena fungsi tersebut membatalkan instruksi thread Apple Silicon CPU.  
B. `sleep` membuang waktu eksekusi CI/CD dan tidak menjamin elemen target sudah ter-render, menimbulkan false-failures (*flakiness*).  
C. `sleep` menyebabkan App Store menolak aplikasi secara instan.  
D. `sleep` hanya dapat dipanggil di Objective-C, bukan di Swift.  

#### 4. Apa perbedaan mendasar antara "Mock" dan "Spy" menurut standar arsitektur test doubles?
A. Mock tidak memiliki assertions internal; Spy selalu melempar error jaringan.  
B. Spy mencatat interaksi pemanggilan untuk diverifikasi nanti; Mock mendefinisikan ekspektasi kontrak langsung yang diverifikasi secara strictly.  
C. Spy hanya digunakan pada antarmuka SwiftUI; Mock hanya digunakan pada UIKit.  
D. Mock tidak dapat disuntikkan via initializers;