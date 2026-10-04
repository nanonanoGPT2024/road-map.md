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
