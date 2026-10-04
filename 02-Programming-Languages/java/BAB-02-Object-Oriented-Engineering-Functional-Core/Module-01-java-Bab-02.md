# Bab 02 Module 01: Object-Oriented Engineering & Functional Core

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: `MOD-JAVA-02-01`
* **Jalur Kurikulum**: `02-Programming-Languages / java`
* **Tingkat Kemahiran**: Advanced / Senior Software Engineer
* **Prasyarat Pengetahuan**:
  * Sintaks dasar Java (Java 17/21 LTS).
  * Prinsip Object-Oriented Programming (OOP) konvensional: Abstraksi, Enkapsulasi, Pewarisan, Polimorfisme.
  * Pemahaman Java Collections Framework dan Generics.
  * Pengetahuan dasar memori JVM (Stack vs Heap).
* **Target Stack**: Java 21 LTS, OpenJDK HotSpot VM, Build tool (Maven/Gradle).
* **Deskripsi Singkat**: Modul ini membahas paradigma modern rekayasa perangkat lunak Java yang mengawinkan kekuatan enkapsulasi *Domain-Driven Object-Oriented Design* dengan prediktabilitas matematis dari *Functional Core*. Fokus utama mencakup perancangan domain model tanpa efek samping (*pure domain models*), pemanfaatan *Algebraic Data Types* (ADT) menggunakan `sealed interface` dan `record`, eliminasi mutabilitas tak terkendali, serta penerapan arsitektur *Functional Core, Imperative Shell* pada aplikasi kelas industri.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik mampu:

1. **Menganalisis dan Membongkar Anemic Domain Model**: Mengidentifikasi kelemahan model mutabel berbasis JavaBean konvensional dan merekonstruksinya menjadi *Rich Domain Model* yang kebal terhadap mutasi liar.
2. **Merancang Algebraic Data Types (ADT)**: Mengimplementasikan *Sum Types* dan *Product Types* secara formal di Java 21 memanfaatkan `sealed interface`, `permits`, dan `record`.
3. **Menguasai Pattern Matching & Exhaustiveness**: Mengoperasikan *Pattern Matching for switch* dan *Record Patterns* (deconstruction) untuk mengeksekusi logika bisnis tanpa *casting* manual serta menjamin keabsahan seluruh percabangan (*exhaustive check*) di tingkat kompilasi.
4. **Menerapkan Paradigma Functional Core, Imperative Shell**: Mengisolasi kalkulasi murni, validasi domain, dan transisi *state* dari operasi *I/O*, mutasi basis data, dan panggilan jaringan.
5. **Mengendalikan Efek Samping Menggunakan Konstruk Fungsional**: Mengeliminasi penggunaan `null` dan *runtime exception* tak terkendali di dalam domain core menggunakan struktur representasi eksplisit seperti `Optional`, `Result/Either`, atau *Domain Event Records*.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Dari "Stateful OOP" ke "Functional Core, Imperative Shell"

Selama dua dekade, rekayasa Java didominasi oleh pola *Anemic Domain Model*: objek entitas hanyalah sekantong data mutabel (kumpulan *getter* dan *setter* tanpa logika), sementara seluruh logika bisnis dieksekusi di dalam *Service Layer* yang sarat dengan efek samping (*stateful side effects*).

```
Paradigma Usang (Anemic Service Layer):
[Database] <--- [Service (Business Logic + Side Effects campur aduk)] ---> [Entity Mutabel (Data Bag)]
                * Sukar diuji unit tanpa mock berat.
                * State dapat dimutasi dari mana saja (hilang integritas data).

Paradigma Modern (Functional Core, Imperative Shell):
[Imperative Shell: Controller/Repo] 
       | (Mengambil Data I/O)
       v
[Functional Core: Pure Model & ADT] ---> Menghasilkan State Baru & Domain Events
       ^ (Kalkulasi Deterministik, 100% Bebas Side Effects, Zero Mocks Needed)
       |
[Imperative Shell: Mengeksekusi Efek Samping Berdasarkan Hasil Domain Core]
```

### Model Mental Utama

1. **Objek sebagai Agen Penjaga Invarian, Bukan Sekadar Penyimpan Data**:
   Objek domain tidak boleh berada dalam kondisi (*state*) yang tidak valid barang satu nanodetik pun. Jika suatu objek berhasil diinstansiasi, objek tersebut dijamin 100% valid secara matematis dan bisnis.

2. **Immutability by Default**:
   Alih-alih mengubah *state* internal objek yang ada (`order.setStatus("PAID")`), metode domain mengembalikan instansiasi baru yang merepresentasikan transisi tersebut (`Order paidOrder = order.markAsPaid(...)`).

3. **Data sebagai Aljabar**:
   Domain bisnis adalah kombinasi diskrit antara komposisi data (*Product Types*: data A **dan** data B, misal `record User(String name, Email email)`) atau alternatif status (*Sum Types*: data X **atau** data Y, misal `sealed interface PaymentStatus permits Pending, Completed, Failed`).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Arsitektur *Functional Core, Imperative Shell* memisahkan sistem menjadi dua lapisan tegas:
* **The Imperative Shell (Outer Ring)**: Bertanggung jawab atas semua I/O, transaksi DB, panggilan HTTP, orkestrasi *framework*, dan mutasi state eksternal. Lapisan ini tipis, tidak memiliki percabangan logika bisnis yang rumit.
* **The Functional Core (Inner Core)**: Kumpulan fungsi murni (*pure functions*), *records*, dan *sealed hierarchies*. Tidak mengetahui keberadaan basis data, jaringan, atau framework eksternal. Selalu deterministik: input yang sama menghasilkan output yang sama tanpa mutasi state luar.

```
+---------------------------------------------------------------------------------+
|                                IMPERATIVE SHELL                                 |
|                                                                                 |
|   +-----------------------+                    +----------------------------+   |
|   |  HTTP Web Controller  |                    |  RDBMS / Kafka Publisher   |   |
|   +-----------+-----------+                    +--------------^-------------+   |
|               | (1) Read DTO                                  | (6) Commit Side |
|               v                                               |     Effects     |
|   +-----------------------+                    +--------------+-------------+   |
|   | Repository (Fetch DB) |                    |  Event Dispatcher Engine   |   |
|   +-----------+-----------+                    +--------------^-------------+   |
|               | (2) Load Entities                             |                 |
|               v                                               |                 |
|      +--------------------------------------------------------+---------+       |
|      |                  FUNCTIONAL CORE (PURE)                          |       |
|      |                                                                  |       |
|      |   (3) Feed Current State + Domain Command                        |       |
|      |       ----------------------------------------------------->     |       |
|      |                                                                  |       |
|      |   +---------------------+        +---------------------------+   |       |
|      |   |  Record / Immutable | =====> | Sealed Hierarchy Transits |   |       |
|      |   |  Domain Model       |        | (Pure State Transitions)  |   |       |
|      |   +---------------------+        +---------------------------+   |       |
|      |                                                |                 |       |
|      |   (4) Compute Invariants Deterministically     v                 |       |
|      |   (5) Return New State + Domain Events Records ----------------> |       |
|      +------------------------------------------------------------------+       |
+---------------------------------------------------------------------------------+
```

### Siklus Eksekusi Pemrosesan Transaksi

```
Shell: Terima Request HTTP POST /orders/123/pay
  │
  ├─► Shell: Ambil state saat ini dari DB (Immutable Order Snapshot)
  │
  ├─► CORE: Order.processPayment(PaymentDetails) ◄── [PURE FUNCTION]
  │     │
  │     ├── Evaluasi Invarian (Apakah status membolehkan pembayaran?)
  │     ├── Hitung Diskon/Pajak secara deterministik
  │     └── Return: Result.Success(OrderState.Paid, List<OrderPaidEvent>)
  │
  ├─► Shell: Evaluasi Hasil Result (Pattern Matching)
  │     │
  │     ├─► Case Failure: Rollback/Kirim HTTP 400 Bad Request
  │     │
  │     └─► Case Success:
  │           ├─ Simpan OrderState.Paid ke DB (I/O Mutation)
  │           ├─ Terbitkan OrderPaidEvent ke Broker Pesan (I/O Mutation)
  │           └─ Kirim HTTP 200 OK ke Client
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Struktur Memori Record vs Regular Class di HotSpot JVM

Secara mendasar, `record` diperkenalkan pada Java 14-16 (JEP 395) sebagai *Product Type* transparan. Di tingkat bytecode dan JVM runtime, terdapat perbedaan struktural antara `class` biasa dan `record`.

```
Standard Java Class Layout (HotSpot 64-bit with Compressed OOPs)
+---------------------------------------------------------------+
| Mark Word (64 bits / 8 bytes)                                 |
+---------------------------------------------------------------+
| Klass Word (32 bits / 4 bytes via +UseCompressedClassPointers)|
+---------------------------------------------------------------+
| Field: id (4 bytes reference)                                 |
+---------------------------------------------------------------+
| Field: balance (8 bytes double / long)                        |
+---------------------------------------------------------------+
| Alignment / Padding (Variabel, kelipatan 8 bytes)             |
+---------------------------------------------------------------+
* Dapat dimutasi sewaktu-waktu jika field tidak eksplisit 'final'.
* Memerlukan bytecode getter boilerplate dan berisiko polymorphic inline-cache miss
  jika subclassing tidak dibatasi.
```

Pada `record`:
* Semua field secara internal bertindak sebagai `private final`.
* Kelas ditandai secara final (`final class RecordName extends java.lang.Record`).
* JVM HotSpot mengoptimasi alokasi record melalui **Escape Analysis**. Jika record dibuat di dalam metode fungsional tertutup dan tidak lolos (*does not escape*) ke heap luar thread, compiler C2 Hotspot dapat melakukan **Scalar Replacement**: mengeliminasi alokasi heap sama sekali dan memecah field record langsung ke register CPU atau frame Stack.

### 2. Bytecode Level: Invokedynamic pada Compact Constructor & Deconstruction

Saat kita mendefinisikan record:
```java
public record Money(java.math.BigDecimal amount, String currency) {
    public Money { // Compact constructor
        java.util.Objects.requireNonNull(amount, "Amount cannot be null");
        java.util.Objects.requireNonNull(currency, "Currency cannot be null");
        if (amount.compareTo(java.math.BigDecimal.ZERO) < 0) {
            throw new IllegalArgumentException("Amount must be non-negative");
        }
    }
}
```

Kompiler `javac` menghasilkan bytecode khusus:
1. `compact constructor` digabungkan secara otomatis sebelum assignment field `this.amount = amount;`. Tidak ada celah di mana instance ada tanpa inisialisasi tuntas.
2. Method `equals()`, `hashCode()`, dan `toString()` tidak di-generate sebagai kode raksasa statis, melainkan memanfaatkan instruksi `invokedynamic` yang terhubung ke `java.lang.runtime.ObjectMethods::bootstrap`. Hal ini menghemat ukuran footprint bytecode `.class`.

### 3. Sealed Interface & Permitted Subclasses Mechanism

Pada deklarasi:
```java
public sealed interface OrderState permits DraftOrder, PlacedOrder, ShippedOrder {}
```

Di level class file (`javap -v`):
* Kompiler menyisipkan atribut `PermittedSubclasses`:
  ```text
  PermittedSubclasses:
    com.engine.domain.DraftOrder
    com.engine.domain.PlacedOrder
    com.engine.domain.ShippedOrder
  ```
* Saat `switch` pattern matching dievaluasi:
  ```java
  return switch (orderState) {
      case DraftOrder d -> ...;
      case PlacedOrder p -> ...;
      case ShippedOrder s -> ...;
  };
  ```
  Kompiler tidak lagi membutuhkan blok `default`. JVM dan `javac` memvalidasi exhaustiveness secara formal. Jika engineer menambahkan subclass baru tanpa mengupdate seluruh blok `switch`, kompilasi akan gagal seketika (*Compile-Time Exhaustiveness Guarantee*).

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Algebraic Data Types (ADT): Product Types vs Sum Types

Teori tipe data mendasari representasi fungsional di Java modern:

* **Product Type ($A \times B$)**: Menggabungkan dua atau lebih tipe data sekaligus. Instansiasi dari tipe ini membutuhkan nilai $A$ **dan** $nilai $B$. Di Java, Product Types diwujudkan secara sempurna oleh `record`.
  $$\text{Ukuran Kemungkinan State} = |A| \times |B|$$
* **Sum Type ($A + B$)**: Menggabungkan dua atau lebih varian tipe yang mutually exclusive. Sebuah nilai hanya bisa berupa $A$ **atau** $B$. Di Java, Sum Types diwujudkan oleh `sealed interface` yang membatasi turunannya.
  $$\text{Ukuran Kemungkinan State} = |A| + |B|$$

Mengapa ini krusial? Desain OOP konvensional sering kali menciptakan model dengan "Illegal States Representable". Contoh:
```java
// BURUK: Desain Anemic OOP
public class Order {
    private String status; // "DRAFT", "PENDING", "PAID", "CANCELLED"
    private Instant paidAt; // null jika DRAFT? Bagaimana jika status PAID tapi paidAt null?
    private String cancellationReason; // null jika PAID? Bagaimana jika keduanya terisi?
}
```
Formula di atas menciptakan jutaan kemungkinan kombinasi state yang tidak valid, memaksa pengecekan defensif `if (order.getPaidAt() != null)` bertebaran di seluruh codebase.

Dengan ADT di Java modern:
```java
// BENAR: Domain Modeling via ADT
public sealed interface OrderState {
    record Draft(Instant createdAt) implements OrderState {}
    record Paid(Instant createdAt, Instant paidAt, String paymentRef) implements OrderState {}
    record Cancelled(Instant createdAt, String reason) implements OrderState {}
}
```
State yang tidak valid secara matematis **mustahil untuk direpresentasikan**. `reason` tidak akan pernah ada di dalam status `Paid`.

### 2. Referential Transparency pada Domain Entity

Sebuah ekspresi atau metode dikatakan *referentially transparent* jika kita dapat mengganti pemanggilan metode tersebut dengan nilai kembaliannya tanpa mengubah perilaku program.

```java
// Referentially Transparent Domain Logic:
// Nilai balance tidak berubah, metode mengembalikan instansiasi baru.
public Account withdraw(Money amount) {
    if (this.balance.isLessThan(amount)) {
        throw new InsufficientFundsException();
    }
    return new Account(this.id, this.balance.subtract(amount));
}
```
Karakteristik ini membuat domain logic:
1. **Thread-safe secara alami**: Tidak membutuhkan sinkronisasi (`synchronized`, `ReentrantLock`) pada domain layer karena data tidak pernah dimutasi di tempat (*in-place*).
2. **Deterministically Testable**: Pengujian unit tidak memerlukan framework *mocking* seperti Mockito untuk menguji domain core.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah perbandingan evolusi: dari domain mutabel usang menuju *Modern Functional Core* menggunakan Record, Sealed Interface, dan Pattern Matching.

### Berkas 1: Rekayasa Usang (Mutable & Bug-Prone)
```java
// Mutable, Nullable, State Invariants mudah dilanggar
package com.fundamental.legacy;

import java.math.BigDecimal;

public class LegacyBankAccount {
    private String accountNumber;
    private BigDecimal balance;
    private boolean isFrozen;

    public LegacyBankAccount(String accountNumber, BigDecimal balance) {
        this.accountNumber = accountNumber;
        this.balance = balance;
        this.isFrozen = false;
    }

    public void withdraw(BigDecimal amount) {
        // Bug: Kurang validasi invarian null
        if (!isFrozen && this.balance.compareTo(amount) >= 0) {
            this.balance = this.balance.subtract(amount); // In-place mutation
        } else {
            throw new RuntimeException("Gagal withdraw"); // Generic exception
        }
    }

    // Getters and Setters exposing internal state
    public BigDecimal getBalance() { return balance; }
    public void setBalance(BigDecimal balance) { this.balance = balance; } // Bahaya!
}
```

### Berkas 2: Rekayasa Modern (Functional Core & ADT)
```java
package com.fundamental.modern;

import java.math.BigDecimal;
import java.util.Objects;

// 1. Value Object Immutable dengan validasi mutlak
public record Money(BigDecimal amount, String currency) {
    public static final String DEFAULT_CURRENCY = "IDR";

    public Money {
        Objects.requireNonNull(amount, "Amount tidak boleh null");
        Objects.requireNonNull(currency, "Currency tidak boleh null");
        if (amount.compareTo(BigDecimal.ZERO) < 0) {
            throw new IllegalArgumentException("Nilai uang tidak boleh negatif: " + amount);
        }
    }

    public static Money of(long amount) {
        return new Money(BigDecimal.valueOf(amount), DEFAULT_CURRENCY);
    }

    public Money subtract(Money other) {
        validateSameCurrency(other);
        if (this.amount.compareTo(other.amount) < 0) {
            throw new IllegalStateException("Saldo tidak mencukupi untuk pengurangan");
        }
        return new Money(this.amount.subtract(other.amount), this.currency);
    }

    public Money add(Money other) {
        validateSameCurrency(other);
        return new Money(this.amount.add(other.amount), this.currency);
    }

    private void validateSameCurrency(Money other) {
        if (!this.currency.equals(other.currency)) {
            throw new IllegalArgumentException("Mata uang tidak cocok: " + this.currency + " vs " + other.currency);
        }
    }
}
```

```java
package com.fundamental.modern;

import java.time.Instant;
import java.util.Objects;

// 2. Sum Type untuk State Mesin Akun Bank
public sealed interface AccountState {
    record Active(Instant activatedAt) implements AccountState {}
    record Frozen(Instant frozenAt, String reason) implements AccountState {}
    record Closed(Instant closedAt) implements AccountState {}
}
```

```java
package com.fundamental.modern;

import java.time.Instant;
import java.util.Objects;

// 3. Rich Domain Entity: Functional Transitions
public record BankAccount(String accountNumber, Money balance, AccountState state) {

    public BankAccount {
        Objects.requireNonNull(accountNumber, "Account number tidak boleh null");
        Objects.requireNonNull(balance, "Balance tidak boleh null");
        Objects.requireNonNull(state, "State tidak boleh null");
    }

    // Pure Function: Mengembalikan instansiasi baru, tidak memutasi `this`
    public BankAccount withdraw(Money amount) {
        return switch (this.state) {
            case AccountState.Active a -> {
                Money newBalance = this.balance.subtract(amount);
                yield new BankAccount(this.accountNumber, newBalance, this.state);
            }
            case AccountState.Frozen f -> 
                throw new IllegalStateException("Akun dibekukan karena: " + f.reason());
            case AccountState.Closed c -> 
                throw new IllegalStateException("Akun telah ditutup permanen pada: " + c.closedAt());
        };
    }

    public BankAccount freeze(String reason, Instant timestamp) {
        return switch (this.state) {
            case AccountState.Active a -> 
                new BankAccount(this.accountNumber, this.balance, new AccountState.Frozen(timestamp, reason));
            case AccountState.Frozen f -> this; // Idempotent
            case AccountState.Closed c -> 
                throw new IllegalStateException("Tidak dapat membekukan akun yang sudah ditutup");
        };
    }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Membedah implementasi fungsional di Seksi 07:

1. `public record Money(BigDecimal amount, String currency)`:
   * Mengumumkan tipe nilai (*Value Object*) dengan kesetaraan struktural (*structural equality*). Dua instance `Money(100, "IDR")` adalah setara, mematuhi hukum simetri dan transitif tanpa menulis `equals` manual.
2. `public Money { ... }` (Compact Constructor):
   * Fitur Java Record yang mengizinkan eksekusi kode validasi *sebelum* parameter diikat ke field internal. Jika terdapat data `null` atau `amount < 0`, JVM membatalkan alokasi objek dengan melempar exception secara instan.
3. `public sealed interface AccountState permits ...`:
   * Mendefinisikan Sum Type eksplisit. Hanya class atau record yang terdaftar di dalam kluster ini yang diizinkan mewarisi `AccountState`. Tidak ada pihak luar yang dapat menyusupkan subclass sembarangan di kemudian hari.
4. `return switch (this.state) { ... }`:
   * Menggunakan *Pattern Matching for switch* sebagai ekspresi (*expression*, bukan *statement*). Karena `AccountState` adalah `sealed`, kompiler memverifikasi bahwa kasus `Active`, `Frozen`, dan `Closed` tertangani.
5. `yield new BankAccount(...)`:
   * Kata kunci `yield` digunakan untuk mengembalikan nilai dari blok multi-baris di dalam ekspresi switch, mempertahankan referential transparency.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: Mesin Rekonsiliasi & Settlement Transaksi Pembayaran Skala Tinggi

**Konteks**: Sebuah Payment Gateway memproses transaksi dengan tingkat konkurensi ribuan *requests per second*. Setiap transaksi memiliki alur:
1. Permintaan otorisasi pembayaran masuk dari Merchant.
2. Domain Core harus mengevaluasi risiko, memotong saldo/limit, memproses fee potongan merchant secara matematis, dan bertransisi status:
   * `Authorized` $\to$ `Captured` $\to$ `Settled`
   * Atau `Authorized` $\to$ `Voided` / `Refunded`.

**Tantangan Lapangan**:
* Terjadinya *race condition* jika entity dimutasi di memori aplikasi.
* Audit trail harus bersifat absolut: setiap transisi harus menerbitkan *immutable domain event* yang akan disimpan di Event Store (Append-Only Log).
* Tidak boleh ada dependency injection (Spring `@Autowired`, DB EntityManager) di dalam logika inti settlement.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi skala produksi untuk modul settlement pembayaran, memisahkan secara tegas antara **Core Domain (Fungsional)** dan **Imperative Orchestrator (Shell)**.

```java
// ==========================================
// FILE: com/payment/domain/DomainResult.java
// ==========================================
package com.payment.domain;

import java.util.Objects;
import java.util.function.Function;

/**
 * Monadic Result Pattern untuk mengeliminasi throwing runtime exceptions di Core Logic.
 */
public sealed interface DomainResult<S, F> {
    record Success<S, F>(S value) implements DomainResult<S, F> {}
    record Failure<S, F>(F error) implements DomainResult<S, F> {}

    static <S, F> DomainResult<S, F> success(S value) {
        return new Success<>(Objects.requireNonNull(value));
    }

    static <S, F> DomainResult<S, F> failure(F error) {
        return new Failure<>(Objects.requireNonNull(error));
    }

    default boolean isSuccess() {
        return this instanceof Success;
    }

    default <T> DomainResult<T, F> map(Function<S, T> mapper) {
        return switch (this) {
            case Success<S, F>(var val) -> DomainResult.success(mapper.apply(val));
            case Failure<S, F>(var err) -> DomainResult.failure(err);
        };
    }
}
```

```java
// ==========================================
// FILE: com/payment/domain/PaymentModels.java
// ==========================================
package com.payment.domain;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Instant;
import java.util.List;
import java.util.Objects;
import java.util.UUID;

// --- Value Objects ---
public final class PaymentModels {
    private PaymentModels() {}

    public record TransactionId(UUID value) {
        public TransactionId {
            Objects.requireNonNull(value, "TransactionId cannot be null");
        }
        public static TransactionId generate() {
            return new TransactionId(UUID.randomUUID());
        }
    }

    public record Money(BigDecimal amount, String currency) {
        public Money {
            Objects.requireNonNull(amount, "Amount cannot be null");
            Objects.requireNonNull(currency, "Currency cannot be null");
            if (amount.scale() > 2) {
                amount = amount.setScale(2, RoundingMode.HALF_EVEN);
            }
        }

        public static Money of(String amount, String currency) {
            return new Money(new BigDecimal(amount), currency);
        }

        public Money applyFeePercentage(BigDecimal percentage) {
            BigDecimal feeAmount = this.amount.multiply(percentage)
                    .divide(BigDecimal.valueOf(100), 2, RoundingMode.HALF_EVEN);
            return new Money(feeAmount, this.currency);
        }

        public Money subtract(Money other) {
            if (!this.currency.equals(other.currency)) {
                throw new IllegalArgumentException("Mismatched currency");
            }
            return new Money(this.amount.subtract(other.amount), this.currency);
        }
    }

    // --- Domain Events ---
    public sealed interface PaymentEvent {
        TransactionId transactionId();
        Instant occurredAt();

        record PaymentAuthorized(TransactionId transactionId, Money amount, Instant occurredAt) implements PaymentEvent {}
        record PaymentCaptured(TransactionId transactionId, Money netAmount, Money feeApplied, Instant occurredAt) implements PaymentEvent {}
        record PaymentVoided(TransactionId transactionId, String reason, Instant occurredAt) implements PaymentEvent {}
    }

    // --- Algebraic State Machine (Sum Types) ---
    public sealed interface PaymentState {
        record Authorized(Money grossAmount, Instant authorizedAt) implements PaymentState {}
        record Captured(Money grossAmount, Money fee, Money netAmount, Instant capturedAt) implements PaymentState {}
        record Voided(String reason, Instant voidedAt) implements PaymentState {}
    }

    // --- Domain Error Representations ---
    public sealed interface SettlementError {
        record InvalidStateTransition(String message) implements SettlementError {}
        record CurrencyMismatch(String expected, String actual) implements SettlementError {}
        record ExcessiveFee(String message) implements SettlementError {}
    }

    // --- Functional Entity Container ---
    public record PaymentAggregate(
            TransactionId id,
            PaymentState state,
            long version
    ) {
        public PaymentAggregate {
            Objects.requireNonNull(id);
            Objects.requireNonNull(state);
        }

        // Pure factory method
        public static PaymentAggregate initialize(TransactionId id, Money amount, Instant timestamp) {
            return new PaymentAggregate(id, new PaymentState.Authorized(amount, timestamp), 1L);
        }

        // Pure State Transition: Mengembalikan state baru beserta Domain Event
        public DomainResult<TransitionResult, SettlementError> capture(BigDecimal feePercentage, Instant timestamp) {
            return switch (this.state) {
                case PaymentState.Authorized auth -> {
                    if (feePercentage.compareTo(BigDecimal.valueOf(50)) > 0) {
                        yield DomainResult.failure(new SettlementError.ExcessiveFee("Fee cannot exceed 50%"));
                    }
                    Money fee = auth.grossAmount().applyFeePercentage(feePercentage);
                    Money net = auth.grossAmount().subtract(fee);

                    PaymentState newState = new PaymentState.Captured(auth.grossAmount(), fee, net, timestamp);
                    PaymentAggregate newAggregate = new PaymentAggregate(this.id, newState, this.version + 1);
                    PaymentEvent event = new PaymentEvent.PaymentCaptured(this.id, net, fee, timestamp);

                    yield DomainResult.success(new TransitionResult(newAggregate, List.of(event)));
                }
                case PaymentState.Captured c ->
                    DomainResult.failure(new SettlementError.InvalidStateTransition("Transaction already captured at " + c.capturedAt()));
                case PaymentState.Voided v ->
                    DomainResult.failure(new SettlementError.InvalidStateTransition("Cannot capture voided transaction: " + v.reason()));
            };
        }

        public DomainResult<TransitionResult, SettlementError> voidTransaction(String reason, Instant timestamp) {
            return switch (this.state) {
                case PaymentState.Authorized auth -> {
                    PaymentState newState = new PaymentState.Voided(reason, timestamp);
                    PaymentAggregate newAggregate = new PaymentAggregate(this.id, newState, this.version + 1);
                    PaymentEvent event = new PaymentEvent.PaymentVoided(this.id, reason, timestamp);
                    yield DomainResult.success(new TransitionResult(newAggregate, List.of(event)));
                }
                case PaymentState.Captured c ->
                    DomainResult.failure(new SettlementError.InvalidStateTransition("Cannot void an already captured transaction"));
                case PaymentState.Voided v ->
                    DomainResult.failure(new SettlementError.InvalidStateTransition("Transaction is already voided"));
            };
        }
    }

    public record TransitionResult(PaymentAggregate aggregate, List<PaymentEvent> events) {}
}
```

```java
// ===============================================================
// FILE: com/payment/shell/SettlementServiceImperativeShell.java
// ===============================================================
package com.payment.shell;

import com.payment.domain.DomainResult;
import com.payment.domain.PaymentModels.*;

import java.math.BigDecimal;
import java.time.Clock;
import java.time.Instant;
import java.util.Optional;
import java.util.logging.Logger;

/**
 * IMPERATIVE SHELL:
 * Bertanggung jawab terhadap I/O, database, side-effects, dan penanganan Result.
 */
public class SettlementServiceImperativeShell {
    private static final Logger log = Logger.getLogger(SettlementServiceImperativeShell.class.getName());

    // Ports / Dependencies
    private final PaymentPersistencePort persistencePort;
    private final EventPublisherPort eventPublisher;
    private final Clock clock;

    public SettlementServiceImperativeShell(
            PaymentPersistencePort persistencePort,
            EventPublisherPort eventPublisher,
            Clock clock
    ) {
        this.persistencePort = persistencePort;
        this.eventPublisher = eventPublisher;
        this.clock = clock;
    }

    public void processCapture(TransactionId txId, BigDecimal feePercent) {
        log.info(() -> "Memulai proses capture untuk txId: " + txId.value());

        // 1. I/O: Ambil aggregate dari storage
        Optional<PaymentAggregate> optionalAggregate = persistencePort.load(txId);
        if (optionalAggregate.isEmpty()) {
            log.warning("Transaksi tidak ditemukan di database: " + txId.value());
            return;
        }

        PaymentAggregate currentAggregate = optionalAggregate.get();
        Instant executionTime = clock.instant();

        // 2. Invocation to PURE FUNCTIONAL CORE
        DomainResult<TransitionResult, SettlementError> result = 
                currentAggregate.capture(feePercent, executionTime);

        // 3. I/O: Evaluasi hasil dan terapkan efek samping (Imperative Actions)
        switch (result) {
            case DomainResult.Success<TransitionResult, SettlementError>(var transition) -> {
                // Simpan state baru (Optimistic locking via versioning)
                persistencePort.save(transition.aggregate());
                
                // Terbitkan events ke Message Broker
                for (PaymentEvent event : transition.events()) {
                    eventPublisher.publish(event);
                }
                log.info(() -> "Berhasil capture transaksi. Version baru: " + transition.aggregate().version());
            }
            case DomainResult.Failure<TransitionResult, SettlementError>(var error) -> {
                handleDomainFailure(txId, error);
            }
        }
    }

    private void handleDomainFailure(TransactionId txId, SettlementError error) {
        switch (error) {
            case SettlementError.InvalidStateTransition err ->
                log.warning("Pelanggaran alur state pada txId: " + txId.value() + " - Info: " + err.message());
            case SettlementError.ExcessiveFee err ->
                log.severe("Penolakan fee berlebih: " + err.message());
            case SettlementError.CurrencyMismatch err ->
                log.severe("Mata uang konflik: Diharapkan " + err.expected() + ", tetapi didapat " + err.actual());
        }
    }

    // --- Ports / Interfaces ---
    public interface PaymentPersistencePort {
        Optional<PaymentAggregate> load(TransactionId id);
        void save(PaymentAggregate aggregate);
    }

    public interface EventPublisherPort {
        void publish(PaymentEvent event);
    }
}
```

```java
// ==========================================
// FILE: com/payment/Main.java (Driver App)
// ==========================================
package com.payment;

import com.payment.domain.PaymentModels.*;
import com.payment.shell.SettlementServiceImperativeShell;

import java.math.BigDecimal;
import java.time.Clock;
import java.time.Instant;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

public class Main {
    public static void main(String[] args) {
        // Simulasi In-Memory Shell Storage & Event Bus
        Map<TransactionId, PaymentAggregate> database = new HashMap<>();
        
        SettlementServiceImperativeShell.PaymentPersistencePort dbPort = 
            new SettlementServiceImperativeShell.PaymentPersistencePort() {
                public Optional<PaymentAggregate> load(TransactionId id) { return Optional.ofNullable(database.get(id)); }
                public void save(PaymentAggregate aggregate) { database.put(aggregate.id(), aggregate); }
            };

        SettlementServiceImperativeShell.EventPublisherPort busPort = 
            event -> System.out.println("[KAFKA BROKER SIMULASI] Dispatching Event: " + event);

        Clock clock = Clock.systemUTC();
        SettlementServiceImperativeShell shell = new SettlementServiceImperativeShell(dbPort, busPort, clock);

        // 1. Setup Initial State
        TransactionId txId = TransactionId.generate();
        PaymentAggregate initialAggregate = PaymentAggregate.initialize(
                txId, 
                Money.of("500000.00", "IDR"), 
                Instant.now()
        );
        database.put(txId, initialAggregate);

        System.out.println("--- MENJALANKAN CAPTURE PERTAMA (VALID) ---");
        shell.processCapture(txId, new BigDecimal("2.5")); // Valid: Fee 2.5%

        System.out.println("\n--- MENJALANKAN CAPTURE KEDUA (INVALID STATE TRANSITION) ---");
        shell.processCapture(txId, new BigDecimal("2.5")); // Gagal: State sudah Captured
    }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Memahami konsekuensi teknik rekayasa yang dipilih:

| Parameter Evaluasi | Anemic OOP + Service Layer | Pure OOP (Domain Driven) | Functional Core + Imperative Shell |
| :--- | :--- | :--- | :--- |
| **Mutabilitas Data** | Sangat Tinggi (Setter ada di mana-mana). | Terkendali (Encapsulated Mutation). | Nol pada domain layer (Strict Immutability). |
| **Kemudahan Pengujian** | Sulit. Membutuhkan Mocking framework yang rumit. | Cukup. Bergantung pada pemisahan state & I/O. | **Sangat Sederhana**. Unit test 100% pure function, zero mocks. |
| **Beban Alokasi GC** | Rendah (Objek dimutasi *in-place*). | Rendah hingga Sedang. | Sedang. Membuat objek baru pada setiap transisi state. |
| **Pencegahan Bug State**| Lemah. Banyak kondisi runtime race condition. | Baik. Dilindungi method boundaries. | **Ekselen**. Tipe data aljabar menjamin invalid state tak bisa dikompilasi. |
| **Learning Curve Tim** | Sangat Rendah (Pola umum industri). | Sedang (Paham DDD, Invariants). | Tinggi (Membutuhkan pemahaman ADT, Pattern Matching, Purity). |

---

## SEKSI 12 — EDGE CASES & PITFALLS

1. **Shallow Immutability pada Java Record**:
   Secara default, komponen record bersifat `final`. Namun, jika komponen tersebut adalah objek referensi yang mutabel (misalnya `java.util.List` atau `java.util.Date`), data internal di dalam komponen tersebut **tetap dapat dimutasi**.
   * *Mitigasi*: Lakukan *defensive copy* pada compact constructor menggunakan `List.copyOf()`, atau gunakan struktur data murni seperti persistent collections.
2. **Rekursi Tanpa Tail-Call Optimization (TCO)**:
   JVM HotSpot tidak mendukung eliminasi rekursi ekor (*tail-call optimization*). Jika domain logic Anda mengeksekusi transisi state berulang-ulang menggunakan rekursi fungsional murni alih-alih perulangan imperatif, Anda berisiko memicu `StackOverflowError`.
3. **Over-Allocation & GC Pressure**:
   Pembuatan record baru pada pemrosesan throughput sangat ekstrem (misal 500.000 tx/detik) dapat memicu peningkatan alokasi pada Young Generation (Eden Space).
   * *Mitigasi*: Manfaatkan profil Escape Analysis via JVM flag `-XX:+DoEscapeAnalysis` untuk membiarkan HotSpot mengalokasikan objek temporer di register/stack.
4. **Serialization Pitfalls**:
   Record memiliki mekanisme serialisasi yang jauh lebih aman daripada class biasa karena proses deserialisasi wajib melewati kanonisasi *canonical constructor*. Namun, jika Anda menggunakan library eksternal (Jackson lama atau Gson lama), library tersebut mungkin memotong validasi via `Unsafe`. Selalu gunakan Jackson 2.15+ dengan modul `jackson-module-blackbird` atau `ParameterNamesModule`.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Membocorkan Referensi Mutabel pada Record

```java
// SALAH: List dapat dimodifikasi dari luar!
public record Order(String id, List<String> itemIds) {}

// PERBAIKAN: Gunakan Unmodifiable Defensive Copy di Compact Constructor
public record Order(String id, List<String> itemIds) {
    public Order {
        Objects.requireNonNull(itemIds);
        itemIds = List.copyOf(itemIds); // Mengembalikan UnmodifiableList yang kebal mutasi
    }
}
```

### 2. Melempar Side-Effecting Database Calls dari dalam Rich Domain Entity

```java
// SALAH: Domain Core memanggil I/O (Tercemar!)
public record Account(String id, Money balance) {
    public Account withdraw(Money amount, AccountRepository repo) {
        Account updated = new Account(this.id, this.balance.subtract(amount));
        repo.save(updated); // Rusak! Core tidak boleh mengendalikan I/O shell.
        return updated;
    }
}

// PERBAIKAN: Core hanya mengembalikan data perubahan, Shell yang mengeksekusi I/O.
public record Account(String id, Money balance) {
    public Account withdraw(Money amount) {
        return new Account(this.id, this.balance.subtract(amount));
    }
}
```

### 3. Menggunakan Tipe Primitif untuk Invarian Kritis (Primitive Obsession)

```java
// SALAH: Parameter mudah tertukar karena tipe sama (String)
public void registerUser(String email, String phoneNumber, String username) { ... }
registerUser(phoneNumber, email, username); // Lolos kompilasi, fatal saat runtime!

// PERBAIKAN: Lindungi dengan Strongly-Typed Single-Value Records
public record Email(String value) { ... }
public record PhoneNumber(String value) { ... }
public record Username(String value) { ... }

public void registerUser(Email email, PhoneNumber phoneNumber, Username username) { ... }
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Jadikan Compact Constructor Sebagai Penjaga Gerbang Invarian**:
   Validasi keberadaan data (non-null), batas nilai numerik, format teks, dan batas logika harus selalu berada di dalam compact constructor record. Jangan biarkan objek cacat terlahir ke heap.
2. **Gunakan Exhaustive Pattern Matching Tanpa Default Branch**:
   Saat mengevaluasi `sealed interface`, hindari menulis `default -> ...`. Biarkan kompiler memandu Anda. Jika suatu saat varian baru ditambahkan ke `sealed interface`, ketiadaan `default` memaksa kompiler melempar *compile error* pada switch yang belum meng-handle tipe tersebut.
3. **Mata Uang dan Presisi**:
   Jangan pernah menggunakan `double` atau `float` untuk urusan finansial. Selalu gunakan `BigDecimal` dengan konfigurasi pembulatan eksplisit (`RoundingMode.HALF_EVEN` / Banker's Rounding) dan scale terdefinisi.
4. **Pisahkan Event dari State**:
   State merepresentasikan *fakta saat ini*, sedangkan Event merepresentasikan *fakta di masa lalu* (bersifat append-only). Namai Event dengan kalimat lampau: `OrderPlaced`, `PaymentAuthorized`, `InventoryDeducted`.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Pemanfaatan Escape Analysis dan Scalar Replacement

Compiler Just-In-Time (JIT) HotSpot (C2) sangat agresif dalam mengoptimasi objek kecil yang bersifat immutable. 

```java
// Menguji Escape Analysis
public Money calculateTotal(List<Item> items) {
    Money total = Money.of(0);
    for (Item item : items) {
        // total.add() membuat instance Money baru di tiap iterasi.
        // C2 Compiler mendeteksi instance Money tidak escape keluar metode ini.
        // Objek Money di-scalar-replace langsung ke CPU Register (RAX, RBX, dsb).
        total = total.add(item.price());
    }
    return total; // Hanya objek akhir ini yang dialokasikan ke Heap!
}
```

### JVM Tuning Flags yang Relevan

Untuk aplikasi berkecepatan tinggi yang mengeksekusi arsitektur *Functional Core*:
* `-XX:+EliminateAllocations`: Memaksa JIT melakukan optimasi pelepasan alokasi heap via scalar replacement.
* `-XX:+UseZGC` atau `-XX:+UseShenandoahGC`: Mengeliminasi jeda *Stop-The-World* yang timbul dari alokasi objek temporer berumur pendek dalam fungsional core.
* `-XX:+OptimizeStringConcat`: Meningkatkan efisiensi interpolasi string pada serialisasi event.

---

## SEKSI 16 — KEAMANAN & HARDENING

1. **Kebal Terhadap Serangan Deserialisasi (Deserialization Vulnerability)**:
   Berdasarkan spesifikasi Java, proses deserialisasi standar Java (`ObjectInputStream`) mengabaikan pemanggilan konstruktor pada kelas biasa, mengizinkan penyerang mengisi *private fields* dengan memori mentah yang melanggar invarian.
   * **Pertahanan**: Record tidak bisa dieksploitasi dengan cara ini. Deserialisasi Record **wajib** mengeksekusi *canonical constructor*, sehingga validasi invariant pada compact constructor tidak dapat dilewati oleh *payload exploit*.
2. **Immutability Mencegah Time-of-Check to Time-of-Use (TOCTOU) Flaws**:
   Pada arsitektur multithreaded, sebuah thread dapat memvalidasi data objek, lalu thread lain memutasi data tersebut tepat sebelum data itu diproses. Dengan *Functional Core* yang immutable, serangan TOCTOU menjadi mustahil karena objek tidak dapat diubah oleh thread lain setelah fase validasi.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

1. **Logging Fungsional Tanpa Polusi Data**:
   Jangan pernah menempatkan perintah `log.info()` di dalam *Pure Functional Core*. Logging adalah efek samping (*side effect*). Lakukan logging di *Imperative Shell* berdasarkan *Domain Events* yang dikembalikan oleh Core.
2. **Audit Trails Berbasis Domain Events**:
   Setiap mutasi pada functional core harus menghasilkan struktur event:
   ```java
   log.info("Domain Event Produced: " + event.getClass().getSimpleName() + " Payload: " + event);
   ```
   Karena record secara otomatis menghasilkan representasi teks terstruktur yang mencakup nama field dan nilainya, Anda mendapatkan format log JSON-friendly tanpa perlu konfigurasi refleksi yang membebani kinerja.
3. **Debugging Deterministik**:
   Jika terjadi bug logika di sistem produksi, Anda tidak perlu mengkloning seluruh database atau lingkungan eksternal. Cukup salin representasi snapshot record aggregate yang rusak, masukkan ke unit test lokal sebagai input parameter fungsi murni, dan jalankan debugging. Perilaku bug akan ter-reproduksi 100% identik.

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

| Konsep | Sintaks Java 21 | Tujuan Arsitektur |
| :--- | :--- | :--- |
| **Product Type** | `public record Name(Type1 a, Type2 b) {}` | Memodelkan kombinasi data immutable dengan kesetaraan nilai. |
| **Sum Type** | `public sealed interface S permits A, B {}` | Memodelkan alternatif kondisi yang saling eksklusif (State Machine). |
| **Guarded Pattern** | `case Type t when t.val() > 100 -> ...` | Evaluasi kondisi percabangan logika langsung pada deklarasi dekonstruksi. |
| **Exhaustiveness** | `switch (sealedType) { case A -> ...; case B -> ...; }` | Verifikasi seluruh cabang state tertangani di tingkat kompilasi tanpa `default`. |
| **Invariance Enforcer**| `public RecordName { Objects.requireNonNull(...); }` | Menolak eksistensi objek cacat di memori JVM sejak milidetik pertama. |

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

Ujilah pemahaman konseptual dan teknis Anda terhadap materi modul ini.

### Bagian A: Tingkat Dasar (Basic)

1. **Mengapa penambahan blok `default` pada switch pattern matching terhadap `sealed interface` justru dianggap *code smell* dalam perancangan Domain ADT?**
   * *Jawaban*: Karena blok `default` akan membungkam kompiler jika di masa depan ada subclass/varian baru yang ditambahkan ke dalam `sealed interface`. Tanpa `default`, kompiler akan melempar *compile error* dan memaksa developer menangani varian baru tersebut secara eksplisit di seluruh sistem.

2. **Apakah field pada sebuah `record` di Java dapat di-reassign nilainya secara langsung?**
   * *Jawaban*: Tidak. Semua field yang didefinisikan pada deklarasi komponen header record secara implisit bertindak sebagai `private final`.

3. **Di manakah kode validasi invariant harus diletakkan pada sebuah record?**
   * *Jawaban*: Di dalam *Compact Constructor*, yaitu konstruktor tanpa tanda kurung parameter di mana assignasi ke field internal belum dilakukan secara formal.

4. **Sebutkan dua komponen utama dalam arsitektur "Functional Core, Imperative Shell"!**
   * *Jawaban*: (1) *Functional Core*, lapisan kalkulasi murni bebas efek samping berbasis immutable models dan pure functions; dan (2) *Imperative Shell*, lapisan luar yang menangani I/O, transaksi DB, panggilan jaringan, dan orkestrasi efek samping.

5. **Apa yang terjadi secara internal di JVM jika sebuah record tidak pernah keluar (*escape*) dari konteks metode pengeksekusinya?**
   * *Jawaban*: JIT Hotspot akan menerapkan optimasi *Escape Analysis* dan *Scalar Replacement*, mengeliminasi alokasi record di heap dan memetakan field-nya langsung ke dalam CPU register atau frame stack.

---

### Bagian B: Tingkat Menengah (Intermediate)

6. **Diberikan kode berikut:**
   ```java
   public record UserGroup(String groupName, List<String> members) {}
   ```
   **Jelaskan mengapa record di atas melanggar prinsip immutability mutlak dan bagaimana cara memperbaikinya!**
   * *Jawaban*: Komponen `List<String> members` adalah referensi mutabel. Pihak luar masih dapat memanggil `userGroup.members().add("hacker")` dan merusak data internal. Perbaikannya adalah menerapkan *defensive copying* di compact constructor: `this.members = List.copyOf(members);`.

7. **Jelaskan perbedaan mendasar antara representasi error berbasis `throw new RuntimeException()` dengan tipe monadic `DomainResult<Success, Failure>` pada Functional Core!**
   * *Jawaban*: Melempar exception memutus alur kendali eksekusi secara non-lokal (*side-effecting stack unwinding*) dan menyembunyikan kemungkinan kegagalan dari signature tipe metode. `DomainResult` memodelkan kegagalan secara eksplisit di level sistem tipe (*type-safe*), memaksa pemanggil menangani kedua kemungkinan cabang tanpa overhead pembuatan exception stack trace.

8. **Bagaimana cara kerja deconstruction pattern pada Java 21 Record Pattern di dalam blok switch?**
   * *Jawaban*: Kompiler mengekstrak langsung komponen data di dalam record tanpa pemanggilan getter manual. Contoh: `case PaymentCaptured(var txId, var net, var fee, var time) -> ...` mendekomposisi record langsung menjadi variabel-variabel lokal individual secara instan dan type-safe.

9. **Mengapa kelas turunan dari `sealed interface` harus berada di modul atau package yang sama?**
   * *Jawaban*: Untuk memastikan integritas exhaustiveness check saat kompilasi. Kompiler Java harus dapat memindai seluruh subtipe yang diizinkan untuk memvalidasi bahwa daftar pewaris bersifat tertutup (*closed-world assumption*).

10. **Bagaimana arsitektur Functional Core menyelesaikan masalah konkurensi (Concurrency Race Conditions) tanpa menggunakan keyword `synchronized` pada domain logic?**
    * *Jawaban*: Karena functional core beroperasi pada objek immutable, pembacaan dan kalkulasi data antar thread bersifat *thread-safe* secara alami tanpa race condition di memori. Resolusi konkurensi dipindahkan sepenuhnya ke Imperative Shell melalui teknik *Atomic Operations*, *Optimistic Locking* (via kolom versi pada basis data), atau *Actor Model*.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek: "High-Precision Dynamic Ride-Sharing Fare & Dispatch Core"

#### Deskripsi Permasalahan
Anda diminta membangun mesin inti (Core Engine) untuk kalkulasi tarif dan dispatch penjemputan armada transportasi online. Modul ini dilarang keras memiliki dependensi ke framework web (Spring, Quarkus, Micronaut) dan basis data manapun. Semua kalkulasi harus murni fungsional.

#### Aturan Bisnis & Spesifikasi Domain:
1. **Model Domain State**:
   Implementasikan lifecycle trip menggunakan `sealed interface RideTrip`:
   * `Requested`: Memuat koordinat awal, koordinat tujuan, ID Penumpang, waktu request.
   * `Matched`: Memuat data `Requested` ditambah Driver ID, waktu alokasi penjemputan, tarif estimasi.
   * `Active`: Memuat waktu aktual pickup, waktu estimasi tiba.
   * `Completed`: Memuat waktu drop-off, jarak aktual tempuh, rincian komponen final tarif (Base, Distance, Surge Multiplier, Discount).
   * `Cancelled`: Memuat siapa pembatalnya (Driver vs Passenger), denda pembatalan (jika ada), dan alasan.
2. **Kalkulasi Dynamic Fare (Tarif Dinamis)**:
   Buat pure function:
   $$\text{Final Fare} = (\text{Base Fare} + (\text{Distance (km)} \times \text{Per-Km Rate})) \times \text{Surge Multiplier} - \text{Promo Discount}$$
   * Jika pembatalan dilakukan oleh Penumpang saat status sudah `Matched` dan lewat dari 3 menit sejak matching: kenakan penalti flat Rp 10.000.
   * Jika pembatalan dilakukan Driver: penalti pembatalan Rp 0, dan sistem otomatis menerbitkan event `DriverSanctionCandidate`.
3. **Karakteristik Teknis Wajib**:
   * Seluruh entity harus dibangun menggunakan `record`.
   * Tidak boleh ada method `setter` atau field mutabel.
   * Seluruh percabangan alur status divalidasi via *Exhaustive Pattern Matching*.
   * Menggunakan pola `DomainResult<Success, DomainError>` untuk seluruh kemungkinan validasi invariant yang gagal.
   * Buat kelas `ImperativeSimulator` yang menguji siklus hidup perjalanan secara menyeluruh dari status `Requested` sampai `Completed` beserta emisi domain event-nya.

#### Kriteria Keberhasilan:
* Kode bersih dari peringatan compiler (`0 compiler warnings`).
* Seluruh test case berjalan sukses dengan pengujian pure unit test tanpa menggunakan `@Mock` sama sekali.
* File struktur memisahkan paket `domain` (Functional Core) dan `simulator` (Imperative Shell).