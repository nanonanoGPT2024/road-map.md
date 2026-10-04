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
