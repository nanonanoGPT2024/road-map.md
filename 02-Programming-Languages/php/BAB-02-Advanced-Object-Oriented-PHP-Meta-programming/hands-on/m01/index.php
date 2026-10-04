<?php

declare(strict_types=1);

namespace App\Infrastructure\Engine;

use Attribute;
use ReflectionClass;
use ReflectionMethod;
use ReflectionProperty;
use ReflectionNamedType;
use PDO;
use Closure;
use Exception;
use RuntimeException;
use InvalidArgumentException;

// ============================================================================
// 1. DOMAIN DECLARATIVE METADATA (ATTRIBUTES)
// ============================================================================

#[Attribute(Attribute::TARGET_CLASS)]
final readonly class Table
{
    public function __construct(public string $name) {}
}

#[Attribute(Attribute::TARGET_PROPERTY)]
final readonly class Column
{
    public function __construct(
        public string $name,
        public bool $isPrimary = false,
        public bool $encrypted = false
    ) {}
}

#[Attribute(Attribute::TARGET_METHOD)]
final readonly class Transactional {}

// ============================================================================
// 2. DOMAIN ENTITY (PURE DOMAIN LOGIC, ZERO EXTERNAL DEPENDENCY)
// ============================================================================

#[Table(name: 'bank_customers')]
final class Customer
{
    #[Column(name: 'id', isPrimary: true)]
    private ?int $id = null;

    #[Column(name: 'full_name')]
    private string $name;

    #[Column(name: 'tax_number', encrypted: true)]
    private string $taxNumber;

    #[Column(name: 'account_balance')]
    private float $balance;

    public function __construct(string $name, string $taxNumber, float $balance, ?int $id = null)
    {
        $this->name = $name;
        $this->taxNumber = $taxNumber;
        $this->balance = $balance;
        $this->id = $id;
    }

    public function getId(): ?int { return $this->id; }
    public function getName(): string { return $this->name; }
    public function getTaxNumber(): string { return $this->taxNumber; }
    public function getBalance(): float { return $this->balance; }

    public function credit(float $amount): void
    {
        if ($amount <= 0) {
            throw new InvalidArgumentException("Nominal kredit harus positif.");
        }
        $this->balance += $amount;
    }
}

// ============================================================================
// 3. ENTERPRISE ENCRYPTION SERVICE
// ============================================================================

interface EncryptionServiceInterface
{
    public function encrypt(string $plain): string;
    public function decrypt(string $cipher): string;
}

final class SodiumEncryptionService implements EncryptionServiceInterface
{
    private string $key;

    public function __construct(string $hexKey)
    {
        $this->key = sodium_hex2bin($hexKey);
    }

    public function encrypt(string $plain): string
    {
        $nonce = random_bytes(SODIUM_CRYPTO_SECRETBOX_NONCEBYTES);
        $cipher = sodium_crypto_secretbox($plain, $nonce, $this->key);
        return sodium_bin2hex($nonce . $cipher);
    }

    public function decrypt(string $cipher): string
    {
        $raw = sodium_hex2bin($cipher);
        $nonce = substr($raw, 0, SODIUM_CRYPTO_SECRETBOX_NONCEBYTES);
        $ciphertext = substr($raw, SODIUM_CRYPTO_SECRETBOX_NONCEBYTES);
        
        $plain = sodium_crypto_secretbox_open($ciphertext, $nonce, $this->key);
        if ($plain === false) {
            throw new RuntimeException("Gagal melakukan dekripsi data!");
        }
        return $plain;
    }
}

// ============================================================================
// 4. METADATA COMPILER & COMPILED HYDRATOR (HOT-PATH OPTIMIZATION)
// ============================================================================

final class EntityMetadata
{
    /**
     * @param array<string, array{column: string, encrypted: bool, property: string}> $columns
     */
    public function __construct(
        public string $tableName,
        public string $primaryKeyProperty,
        public string $primaryKeyColumn,
        public array $columns,
        public Closure $hydrator,
        public Closure $extractor
    ) {}
}

final class MetadataRegistry
{
    /** @var array<class-string, EntityMetadata> */
    private static array $cache = [];

    public static function get(string $class, EncryptionServiceInterface $crypto): EntityMetadata
    {
        if (isset(self::$cache[$class])) {
            return self::$cache[$class];
        }

        $refClass = new ReflectionClass($class);

        // Ambil Nama Tabel
        $tableAttrs = $refClass->getAttributes(Table::class);
        if (empty($tableAttrs)) {
            throw new RuntimeException("Kelas {$class} tidak memiliki atribut Table.");
        }
        $tableName = $tableAttrs[0]->newInstance()->name;

        $pkProperty = '';
        $pkColumn = '';
        $columns = [];
        $propertyNames = [];

        foreach ($refClass->getProperties() as $prop) {
            $colAttrs = $prop->getAttributes(Column::class);
            if (empty($colAttrs)) {
                continue;
            }

            /** @var Column $colMeta */
            $colMeta = $colAttrs[0]->newInstance();
            $propName = $prop->getName();
            $propertyNames[] = $propName;

            $columns[$propName] = [
                'column' => $colMeta->name,
                'encrypted' => $colMeta->encrypted,
                'property' => $propName
            ];

            if ($colMeta->isPrimary) {
                $pkProperty = $propName;
                $pkColumn = $colMeta->name;
            }
        }

        // COMPILED CLOSURES UNTUK MENJAMIN PERFORMA TINGGI (MEMOTONG REFLEKSI PADA RUNTIME)
        
        // 1. Fast Hydrator (Database Array -> Uninitialized Object)
        $hydrator = function (array $data, object $instance) use ($columns, $crypto): object {
            foreach ($columns as $prop => $conf) {
                if (!array_key_exists($conf['column'], $data)) {
                    continue;
                }

                $rawVal = $data[$conf['column']];
                if ($rawVal !== null && $conf['encrypted']) {
                    $rawVal = $crypto->decrypt((string)$rawVal);
                }

                // Injeksi state langsung menembus private visibility
                $this->{$prop} = $rawVal;
            }
            return $instance;
        };

        // 2. Fast Extractor (Object -> Database Array)
        $extractor = function (object $instance) use ($columns, $crypto): array {
            $output = [];
            foreach ($columns as $prop => $conf) {
                $val = $this->{$prop} ?? null;
                if ($val !== null && $conf['encrypted']) {
                    $val = $crypto->encrypt((string)$val);
                }
                $output[$conf['column']] = $val;
            }
            return $output;
        };

        return self::$cache[$class] = new EntityMetadata(
            tableName: $tableName,
            primaryKeyProperty: $pkProperty,
            primaryKeyColumn: $pkColumn,
            columns: $columns,
            hydrator: $hydrator->bindTo(null, $class),
            extractor: $extractor->bindTo(null, $class)
        );
    }
}

// ============================================================================
// 5. DATA MAPPER REPOSITORY
// ============================================================================

final class AdvancedDataMapper
{
    public function __construct(
        private PDO $pdo,
        private EncryptionServiceInterface $crypto
    ) {}

    /**
     * @template T of object
     * @param class-string<T> $class
     * @return T|null
     */
    public function find(string $class, int|string $id): ?object
    {
        $meta = MetadataRegistry::get($class, $this->crypto);
        
        $sql = sprintf(
            'SELECT * FROM %s WHERE %s = :id LIMIT 1',
            $meta->tableName,
            $meta->primaryKeyColumn
        );

        $stmt = $this->pdo->prepare($sql);
        $stmt->execute(['id' => $id]);
        $row = $stmt->fetch(PDO::FETCH_ASSOC);

        if (!$row) {
            return null;
        }

        // Bikin instance kosong tanpa memanggil constructor (Bypass Constructor Arguments)
        $refClass = new ReflectionClass($class);
        $instance = $refClass->newInstanceWithoutConstructor();

        // Hydrate data via compiled pre-bound closure
        ($meta->hydrator)($row, $instance);

        return $instance;
    }

    public function save(object $entity): void
    {
        $class = $entity::class;
        $meta = MetadataRegistry::get($class, $this->crypto);

        // Ekstraksi data private melalui closure
        $data = ($meta->extractor)($entity);
        $pkValue = $data[$meta->primaryKeyColumn] ?? null;

        if ($pkValue === null) {
            // INSERT
            unset($data[$meta->primaryKeyColumn]);
            $columns = implode(', ', array_keys($data));
            $placeholders = ':' . implode(', :', array_keys($data));
            
            $sql = sprintf('INSERT INTO %s (%s) VALUES (%s)', $meta->tableName, $columns, $placeholders);
            $stmt = $this->pdo->prepare($sql);
            $stmt->execute($data);

            // Set Primary Key kembali ke instance
            $lastId = (int)$this->pdo->lastInsertId();
            $setter = function (string $pk, int $val) {
                $this->{$pk} = $val;
            };
            $setter->bindTo($entity, $class)($meta->primaryKeyProperty, $lastId);
        } else {
            // UPDATE
            $fields = [];
            foreach ($data as $col => $val) {
                if ($col === $meta->primaryKeyColumn) continue;
                $fields[] = "{$col} = :{$col}";
            }
            $sql = sprintf('UPDATE %s SET %s WHERE %s = :pk', $meta->tableName, implode(', ', $fields), $meta->primaryKeyColumn);
            $data['pk'] = $pkValue;
            $stmt = $this->pdo->prepare($sql);
            $stmt->execute($data);
        }
    }
}

// ============================================================================
// 6. ASPECT-ORIENTED TRANSACTION INTERCEPTOR (DYNAMIC PROXY FACTORY)
// ============================================================================

final class TransactionProxyFactory
{
    /**
     * Membungkus service domain dengan Proxy Dynamic Interceptor untuk transaksi database ACID
     *
     * @template T of object
     * @param T $service
     * @return T
     */
    public static function create(object $service, PDO $pdo): object
    {
        $targetClass = new ReflectionClass($service);

        // Memanfaatkan anonymous class untuk membangun proxy struktural dinamis
        return new class($service, $pdo, $targetClass) {
            public function __construct(
                private readonly object $targetInstance,
                private readonly PDO $pdo,
                private readonly ReflectionClass $reflectedTarget
            ) {}

            public function __call(string $name, array $arguments): mixed
            {
                if (!$this->reflectedTarget->hasMethod($name)) {
                    throw new RuntimeException("Metode {$name} tidak ditemukan pada target.");
                }

                $method = $this->reflectedTarget->getMethod($name);
                $isTransactional = !empty($method->getAttributes(Transactional::class));

                if (!$isTransactional) {
                    return $method->invokeArgs($this->targetInstance, $arguments);
                }

                // Jalankan dalam proteksi transaksi ACID
                $this->pdo->beginTransaction();
                try {
                    $result = $method->invokeArgs($this->targetInstance, $arguments);
                    $this->pdo->commit();
                    return $result;
                } catch (Exception $e) {
                    $this->pdo->rollBack();
                    throw new RuntimeException(
                        "Transaksi dibatalkan karena kegagalan internal: " . $e->getMessage(),
                        (int)$e->getCode(),
                        $e
                    );
                }
            }
        };
    }
}

// ============================================================================
// 7. APLIKASI LAYANAN DOMAIN
// ============================================================================

class BankingService
{
    public function __construct(private AdvancedDataMapper $mapper) {}

    #[Transactional]
    public function executeTransfer(int $customerId, float $amount): void
    {
        /** @var Customer|null $customer */
        $customer = $this->mapper->find(Customer::class, $customerId);
        if (!$customer) {
            throw new RuntimeException("Nasabah dengan ID {$customerId} tidak ditemukan.");
        }

        $customer->credit($amount);
        $this->mapper->save($customer);
    }
}

// ============================================================================
// 8. TESTING & PIPELINE DEMONSTRASI (SQLITE IN-MEMORY)
// ============================================================================

// A. Siapkan Database dan Mock Key
$pdo = new PDO('sqlite::memory:', options: [
    PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION
]);

$pdo->exec("
    CREATE TABLE bank_customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        tax_number TEXT NOT NULL,
        account_balance REAL NOT NULL
    )
");

// 256-bit Key acak (32 byte -> 64 karakter hex)
$hexKey = sodium_bin2hex(sodium_crypto_secretbox_keygen());
$crypto = new SodiumEncryptionService($hexKey);
$mapper = new AdvancedDataMapper($pdo, $crypto);

// B. Simpan Customer Baru Melalui DataMapper (Enkripsi Transparan)
$alice = new Customer("Alice Springs", "NPWP-88192-X", 1500000.00);
$mapper->save($alice);
$aliceId = $alice->getId();

echo "--- 1. DATA TERSIMPAN DI DATABASE SECARA FISIK RAW ---\n";
$stmt = $pdo->query("SELECT * FROM bank_customers WHERE id = {$aliceId}");
$rawRow = $stmt->fetch(PDO::FETCH_ASSOC);
print_r($rawRow);

echo "\n--- 2. HYDRATION OBJECT POPO MELALUI COMPILED CLOSURES ---\n";
/** @var Customer $retrievedAlice */
$retrievedAlice = $mapper->find(Customer::class, $aliceId);
echo "Nama           : " . $retrievedAlice->getName() . "\n";
echo "Tax Number Dec : " . $retrievedAlice->getTaxNumber() . "\n";
echo "Saldo Awal     : " . $retrievedAlice->getBalance() . "\n";

echo "\n--- 3. EKSEKUSI AOP DYNAMIC PROXY TRANSACTION INTERCEPTOR ---\n";
$pureService = new BankingService($mapper);

/** @var BankingService $proxyService */
$proxyService = TransactionProxyFactory::create($pureService, $pdo);

// Eksekusi mutasi melalui proxy
$proxyService->executeTransfer($aliceId, 750000.00);

/** @var Customer $updatedAlice */
$updatedAlice = $mapper->find(Customer::class, $aliceId);
echo "Saldo Akhir    : " . $updatedAlice->getBalance() . "\n";
