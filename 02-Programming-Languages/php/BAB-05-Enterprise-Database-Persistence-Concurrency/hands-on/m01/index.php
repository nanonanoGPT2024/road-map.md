<?php

declare(strict_types=1);

namespace Enterprise\Ledger;

use PDO;
use PDOException;
use RuntimeException;
use InvalidArgumentException;
use DateTimeImmutable;

// -----------------------------------------------------------------------------
// DOMAIN MODELS & VALUE OBJECTS
// -----------------------------------------------------------------------------

final readonly class Money
{
    public function __construct(public int $amountInCents)
    {
        if ($this->amountInCents < 0) {
            throw new InvalidArgumentException("Amount cannot be negative.");
        }
    }

    public function add(Money $other): self
    {
        return new self($this->amountInCents + $other->amountInCents);
    }

    public function subtract(Money $other): self
    {
        if ($other->amountInCents > $this->amountInCents) {
            throw new RuntimeException("Insufficient funds for subtraction.");
        }
        return new self($this->amountInCents - $other->amountInCents);
    }
}

final class Account
{
    public function __construct(
        public readonly int $id,
        public readonly string $accountNumber,
        private Money $balance,
        private int $version
    ) {}

    public function getBalance(): Money
    {
        return $this->balance;
    }

    public function getVersion(): int
    {
        return $this->version;
    }

    public function debit(Money $amount): void
    {
        $this->balance = $this->balance->subtract($amount);
    }

    public function credit(Money $amount): void
    {
        $this->balance = $this->balance->add($amount);
    }

    public function incrementVersion(): void
    {
        $this->version++;
    }
}

final class ProductInventory
{
    public function __construct(
        public readonly int $id,
        public readonly string $sku,
        private int $availableStock,
        private int $version
    ) {
        if ($this->availableStock < 0) {
            throw new InvalidArgumentException("Stock cannot be initialized to negative value.");
        }
    }

    public function getAvailableStock(): int
    {
        return $this->availableStock;
    }

    public function getVersion(): int
    {
        return $this->version;
    }

    public function reserve(int $quantity): void
    {
        if ($quantity <= 0) {
            throw new InvalidArgumentException("Quantity must be greater than zero.");
        }
        if ($this->availableStock < $quantity) {
            throw new RuntimeException("Insufficient stock for product SKU: {$this->sku}.");
        }
        $this->availableStock -= $quantity;
    }
}

// -----------------------------------------------------------------------------
// IDENTITY MAP PATTERN
// -----------------------------------------------------------------------------

final class IdentityMap
{
    /** @var array<string, object> */
    private array $map = [];

    public function get(string $class, int $id): ?object
    {
        $key = $this->buildKey($class, $id);
        return $this->map[$key] ?? null;
    }

    public function set(int $id, object $entity): void
    {
        $key = $this->buildKey($entity::class, $id);
        $this->map[$key] = $entity;
    }

    public function clear(): void
    {
        $this->map = [];
    }

    private function buildKey(string $class, int $id): string
    {
        return "{$class}:{$id}";
    }
}

// -----------------------------------------------------------------------------
// REPOSITORY LAYER WITH CONCURRENCY LOCKING
// -----------------------------------------------------------------------------

final class AccountRepository
{
    public function __construct(
        private readonly PDO $pdo,
        private readonly IdentityMap $identityMap
    ) {}

    /**
     * Mengambil account dengan Pessimistic Exclusive Lock (FOR UPDATE).
     */
    public function findByIdForUpdate(int $id): Account
    {
        // Tetap eksekusi query lock ke database untuk menjamin row-level locking fisik
        $stmt = $this->pdo->prepare(
            "SELECT id, account_number, balance_cents, version 
             FROM accounts 
             WHERE id = :id 
             FOR UPDATE"
        );
        $stmt->execute(['id' => $id]);
        $row = $stmt->fetch(PDO::FETCH_ASSOC);

        if (!$row) {
            throw new RuntimeException("Account with ID {$id} not found.");
        }

        $account = new Account(
            id: (int)$row['id'],
            accountNumber: (string)$row['account_number'],
            balance: new Money((int)$row['balance_cents']),
            version: (int)$row['version']
        );

        $this->identityMap->set($account->id, $account);
        return $account;
    }

    public function update(Account $account): void
    {
        $stmt = $this->pdo->prepare(
            "UPDATE accounts 
             SET balance_cents = :balance, version = version + 1 
             WHERE id = :id"
        );

        $stmt->execute([
            'balance' => $account->getBalance()->amountInCents,
            'id' => $account->id,
        ]);

        $account->incrementVersion();
    }
}

final class InventoryRepository
{
    public function __construct(
        private readonly PDO $pdo,
        private readonly IdentityMap $identityMap
    ) {}

    public function findByIdForUpdate(int $id): ProductInventory
    {
        $stmt = $this->pdo->prepare(
            "SELECT id, sku, available_stock, version 
             FROM product_inventory 
             WHERE id = :id 
             FOR UPDATE"
        );
        $stmt->execute(['id' => $id]);
        $row = $stmt->fetch(PDO::FETCH_ASSOC);

        if (!$row) {
            throw new RuntimeException("Inventory for product ID {$id} not found.");
        }

        $inventory = new ProductInventory(
            id: (int)$row['id'],
            sku: (string)$row['sku'],
            availableStock: (int)$row['available_stock'],
            version: (int)$row['version']
        );

        $this->identityMap->set($inventory->id, $inventory);
        return $inventory;
    }

    public function update(ProductInventory $inventory): void
    {
        $stmt = $this->pdo->prepare(
            "UPDATE product_inventory 
             SET available_stock = :stock, version = version + 1 
             WHERE id = :id"
        );

        $stmt->execute([
            'stock' => $inventory->getAvailableStock(),
            'id' => $inventory->id,
        ]);
    }
}

// -----------------------------------------------------------------------------
// CORE SETTLEMENT SERVICE WITH DEADLOCK PREVENTION VIA DETERMINISTIC ORDERING
// -----------------------------------------------------------------------------

final class FlashSaleOrderProcessor
{
    public function __construct(
        private readonly PDO $pdo,
        private readonly AccountRepository $accountRepo,
        private readonly InventoryRepository $inventoryRepo,
        private readonly IdentityMap $identityMap
    ) {}

    /**
     * Memproses pesanan Flash Sale:
     * 1. Mengunci inventaris produk.
     * 2. Mengunci akun sumber dan target secara DETERMINISTIK (Sorting ID) guna mencegah Deadlock 2PL.
     * 3. Membuat Ledger Record (Double-Entry Bookkeeping).
     * 4. Memperbarui seluruh state secara atomik.
     */
    public function processOrder(
        int $buyerAccountId,
        int $merchantAccountId,
        int $productId,
        int $quantity,
        Money $totalPrice
    ): void {
        $this->identityMap->clear();

        // 1. Kunci resource Inventory terlebih dahulu
        $inventory = $this->inventoryRepo->findByIdForUpdate($productId);
        $inventory->reserve($quantity);

        // 2. Deadlock Prevention Strategy: Deterministic Locking Order
        // Selalu kunci akun dengan ID terkecil terlebih dahulu, baru ID yang lebih besar!
        $accountIds = [$buyerAccountId, $merchantAccountId];
        sort($accountIds, SORT_NUMERIC);

        /** @var array<int, Account> $lockedAccounts */
        $lockedAccounts = [];
        foreach ($accountIds as $id) {
            $lockedAccounts[$id] = $this->accountRepo->findByIdForUpdate($id);
        }

        $buyerAccount = $lockedAccounts[$buyerAccountId];
        $merchantAccount = $lockedAccounts[$merchantAccountId];

        // 3. Mutasi State Domain
        $buyerAccount->debit($totalPrice);
        $merchantAccount->credit($totalPrice);

        // 4. Double-Entry Ledger Entry Insertion
        $this->recordLedgerEntry(
            debitAccountId: $buyerAccount->id,
            creditAccountId: $merchantAccount->id,
            amount: $totalPrice,
            referenceType: 'FLASH_SALE_PURCHASE',
            referenceId: "PRD-{$productId}"
        );

        // 5. Persist State Changes
        $this->inventoryRepo->update($inventory);
        $this->accountRepo->update($buyerAccount);
        $this->accountRepo->update($merchantAccount);
    }

    private function recordLedgerEntry(
        int $debitAccountId,
        int $creditAccountId,
        Money $amount,
        string $referenceType,
        string $referenceId
    ): void {
        $stmt = $this->pdo->prepare(
            "INSERT INTO financial_ledger 
             (debit_account_id, credit_account_id, amount_cents, reference_type, reference_id, created_at) 
             VALUES (:debit_id, :credit_id, :amount, :ref_type, :ref_id, :created_at)"
        );

        $now = (new DateTimeImmutable())->format('Y-m-d H:i:s');

        $stmt->execute([
            'debit_id' => $debitAccountId,
            'credit_id' => $creditAccountId,
            'amount' => $amount->amountInCents,
            'ref_type' => $referenceType,
            'ref_id' => $referenceId,
            'created_at' => $now,
        ]);
    }
}

// -----------------------------------------------------------------------------
// INTEGRATION TEST & RUNNER
// -----------------------------------------------------------------------------

// Inisialisasi koneksi Database SQLite in-memory untuk verifikasi fungsionalitas
$pdo = new PDO('sqlite::memory:');
$pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

// Setup Schema
$pdo->exec("
    CREATE TABLE accounts (
        id INTEGER PRIMARY KEY,
        account_number TEXT NOT NULL,
        balance_cents INTEGER NOT NULL,
        version INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE product_inventory (
        id INTEGER PRIMARY KEY,
        sku TEXT NOT NULL,
        available_stock INTEGER NOT NULL,
        version INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE financial_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        debit_account_id INTEGER NOT NULL,
        credit_account_id INTEGER NOT NULL,
        amount_cents INTEGER NOT NULL,
        reference_type TEXT NOT NULL,
        reference_id TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
");

// Fixture Data
$pdo->exec("INSERT INTO accounts (id, account_number, balance_cents, version) VALUES (1, 'ACC-BUYER-01', 500000, 1)"); // Saldo 5.000,00
$pdo->exec("INSERT INTO accounts (id, account_number, balance_cents, version) VALUES (2, 'ACC-MERCHANT-01', 100000, 1)"); // Saldo 1.000,00
$pdo->exec("INSERT INTO product_inventory (id, sku, available_stock, version) VALUES (100, 'PHONE-FLAGSHIP-01', 50, 1)"); // Stok 50

$identityMap = new IdentityMap();
$accountRepo = new AccountRepository($pdo, $identityMap);
$inventoryRepo = new InventoryRepository($pdo, $identityMap);
$processor = new FlashSaleOrderProcessor($pdo, $accountRepo, $inventoryRepo, $identityMap);

// Eksekusi Pesanan
$pdo->beginTransaction();
try {
    $processor->processOrder(
        buyerAccountId: 1,
        merchantAccountId: 2,
        productId: 100,
        quantity: 2,
        totalPrice: new Money(200000) // Harga 2.000,00
    );
    $pdo->commit();
    echo "TRANSAKSI SUKSES DIVERIFIKASI SECARA ATOMIK.\n";
} catch (Throwable $e) {
    $pdo->rollBack();
    echo "TRANSAKSI GAGAL: " . $e->getMessage() . "\n";
}

// Verifikasi State Akhir
$buyer = $accountRepo->findByIdForUpdate(1);
$merchant = $accountRepo->findByIdForUpdate(2);
$product = $inventoryRepo->findByIdForUpdate(100);

echo "Sisa Saldo Pembeli  : " . $buyer->getBalance()->amountInCents . " cents (Ekspektasi: 300000)\n";
echo "Sisa Saldo Merchant : " . $merchant->getBalance()->amountInCents . " cents (Ekspektasi: 300000)\n";
echo "Sisa Stok Produk    : " . $product->getAvailableStock() . " unit (Ekspektasi: 48)\n";
