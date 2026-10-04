# Kurikulum Rekayasa Perangkat Lunak Enterprise: Java Core
## Bab 02: Object-Oriented Engineering & Functional Core
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, *software engineer* diharapkan mampu:
- Menganalisis dan mengoptimalkan mekanisme internal JVM terkait alokasi objek, *polymorphic dispatch* (vtable/itable), *escape analysis*, dan *inlining*.
- Mengimplementasikan paradigma **Functional Core, Imperative Shell (FCIS)** menggunakan konstruksi modern Java 21+ (*Records*, *Sealed Types*, *Pattern Matching*).
- Menghilangkan *defensive copying overhead* dan *unintended side-effects* melalui penegakan *strict immutability* pada pemodelan domain kritis.
- Mengidentifikasi degradasi performa pada tingkat *bytecode* dan JIT compilation, seperti *megamorphic call sites* dan *boxing/unboxing overhead* pada *functional pipelines*.
- Merancang subsistem transaksi skala enterprise dengan latensi rendah (<5ms p99) yang aman secara *thread-safety* serta kompatibel penuh dengan Java Virtual Threads (Project Loom).

---

### 2. Prerequisite
Sebelum mendalami modul ini, praktisi diwajibkan telah menguasai:
- **OOP Fundamentals**: Polimorfisme, enkapsulasi, pewarisan, dan abstraksi.
- **Java Basics**: Sintaks dasar Java 17+, generics, exception handling standar.
- **Concurrency Basics**: Thread lifecycle, memori model dasar (heap vs. stack).
- **Tooling**: Terbiasa menggunakan Maven/Gradle dan minimal Java Development Kit (JDK) 21 LTS.

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. JVM Object Layout & Memory Density
Pada HotSpot JVM 64-bit, setiap instansiasi objek membawa metadata *overhead*:
- **Mark Word** (8 bytes): Menyimpan status *identity hash code*, bias/lock status (meskipun biased locking didiskualifikasi di JDK modern), dan *age bits* untuk Generational GC.
- **Klass Word** (8 bytes, atau 4 bytes jika `-XX:+UseCompressedClassPointers` aktif): Penunjuk ke representasi metadata kelas di Metaspace.
- **Data Payload**: Nilai primitif atau referensi objek lain (32-bit jika `-XX:+UseCompressedOops` aktif pada heap < 32GB).
- **Padding**: Pelengkap byte agar ukuran total objek merupakan kelipatan 8 bytes (64-bit word alignment).

```
+-------------------------------------------------------------+
|                     JVM Object Layout                       |
+------------------------------+------------------------------+
| Mark Word (64-bit / 8 bytes) | Klass Pointer (32/64-bit)    |
+------------------------------+------------------------------+
| Fields / Array Length (variadic based on primitives/oops)   |
+-------------------------------------------------------------+
| Alignment Padding (0 to 7 bytes to align to 8-byte boundary)|
+-------------------------------------------------------------+
```

Penggunaan **Record** tidak mengubah skema header ini, tetapi karena `Record` menjamin *shallow immutability* dan membuang kebutuhan *getter-setter boilerplate*, JIT compiler (`C2`) dapat melakukan optimasi ekstrim melalui **Escape Analysis**. Objek record yang tidak "bocor" (escaped) ke luar thread lokal dapat dipecah menjadi variabel primitif langsung di register CPU atau stack frame (*Scalar Replacement*), mengeliminasi alokasi pada Java Heap secara total.

#### B. Dynamic Dispatch: Vtable, Itable, dan Inline Caching
Eksekusi method polymorphism di Java tidak terjadi secara gratis:
1. **Invokevirtual & Vtable**: Class-based polymorphism menggunakan *Virtual Method Table* (vtable). Index offset method dihitung saat *class loading*. Resolusi pemanggilan hanya membutuhkan dereferensi array pointer tunggal.
2. **Invokeinterface & Itable**: Interface polymorphism lebih kompleks karena kelas dapat mengimplementasikan multi-interface dengan offset yang berbeda. JVM menggunakan *Interface Method Table* (itable) dengan overhead resolusi lookup lebih tinggi.
3. **Monomorphic vs Bimorphic vs Megamorphic Call Sites**:
   - *Monomorphic* (1 tipe target konkret): JIT melakukan *direct inlining*. Instruksi pemanggilan diganti dengan kode method target itu sendiri.
   - *Bimorphic* (2 tipe target): JIT menggunakan conditional guard (`if (type == A) ... else if (type == B) ...`).
   - *Megamorphic* (>= 3 tipe target berbeda pada call-site yang sama): JIT menyerah melakukan inlining. Program terpaksa melakukan fallback ke *table lookup* runtime secara konstan, memicu *branch mispredictions* di level CPU L1 instruction cache.

```
Monomorphic Call Site (Fastest):
Caller ---> JIT Inlined Assembly directly into execution block

Megamorphic Call Site (Slowest):
Caller ---> Runtime Itable Stub Lookup ---> Hash/Linear Search Table ---> Target Method Address
```

#### C. Functional Core, Imperative Shell (FCIS) Architecture
Paradigma FCIS memisahkan:
- **Functional Core**: Logika domain murni (*pure functions*, *referential transparency*). Mengambil state dan event, lalu menghasilkan state baru tanpa mutasi atau I/O (tanpa database, HTTP, atau disk write). Dibangun sepenuhnya dengan `Sealed Interface`, `Record`, dan fungsi evaluasi berbasis *Pattern Matching*.
- **Imperative Shell**: Lapisan luar penanganan *side-effects*. Bertanggung jawab membaca request HTTP/Kafka, query database, memvalidasi dependensi I/O, memberikan snapshot domain ke *Functional Core*, lalu menyimpan mutasi dan memancarkan efek (events/notifications).

---

### 4. Why & What
- **Why**: Arsitektur enterprise klasik kerap mencampur logika bisnis ke dalam *Spring Service layer* yang penuh dependensi mutabel (`@Autowired` di mana-mana). Hal ini memicu *race condition*, sulit di-*unit test* tanpa mocking masif, memicu alokasi memori liar, dan menghambat migrasi ke *concurrency* modern (*Virtual Threads* rentan mengalami masalah jika terjadi *pinning* atau sinkronisasi mutabel yang buruk).
- **What**: Modul ini mengajarkan rekonstruksi inti domain menggunakan prinsip *algebraic data types* (ADT) via `sealed interface` (sum types) dan `record` (product types), digabungkan dengan alur eksekusi deterministik yang terisolasi dari I/O.

---

### 5. How (Workflow Detail)
Tahapan eksekusi arsitektur domain fungsional:
1. **Ingress**: Controller/Consumer menerima payload tidak terstruktur (*untrusted boundary*).
2. **Sanitization & Mapping**: Mengonversi JSON/Avro ke tipe data domain yang divalidasi secara struktural (*Parse, don't validate*).
3. **Hydration (Imperative Shell)**: Membaca current state dari database/storage (e.g., PostgreSQL / Redis) ke dalam *immutable domain model*.
4. **Execution (Functional Core)**: Memanggil pure function dengan signature: `(CurrentState, Command) -> Result<NewState, DomainFailure>`. Seluruh evaluasi dilarang keras melakukan network/disk call.
5. **Persist & Emit (Imperative Shell)**: Transaksi ACID menyimpan `NewState` dan meneruskan Domain Event ke message broker.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Arloji Mekanikal vs. Tampilan Digital IoT
- **Functional Core (Roda Gigi Mekanikal)**: Roda gigi tidak peduli dari mana sumber daya listrik berasal atau apakah cuaca sedang hujan. Ketika roda A berputar 10 derajat, roda B pasti berputar 5 derajat. Sepenuhnya deterministik, terisolasi, matematis.
- **Imperative Shell (Casing Kedap Air & Sensor Baterai)**: Mengambil data dari satelit GPS, membaca voltase baterai, dan memutar kenop pemutar mekanikal. Jika satelit hilang sinyal (I/O failure), roda gigi di dalam tetap berfungsi secara akurat tanpa *crash*.

```
+---------------------------------------------------------------------------------+
|                        IMPERATIVE SHELL (I/O, Side Effects)                     |
|                                                                                 |
|  [REST API / Kafka] ---> Fetch Current Domain State via JDBC                   |
|                                     |                                           |
|                                     v                                           |
|             +-----------------------------------------------+                   |
|             |      FUNCTIONAL CORE (Pure & Deterministic)   |                   |
|             |                                               |                   |
|             |  Input: State + Command                       |                   |
|             |  Output: NewState + DomainEvent               |                   |
|             |  Rule: No I/O, No Mutations, Immutable Data   |                   |
|             +-----------------------------------------------+                   |
|                                     |                                           |
|                                     v                                           |
|  [DB Transaction] <--- Persist New State & Publish Event to Outbox Table        |
+---------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Mengganti State Mutation dengan Immutability & Pattern Matching
```java
package com.enterprise.core.simple;

// Sealed hierarchy bertindak sebagai algebraic data type (Sum Type)
public sealed interface OrderStatus {
    record Draft() implements OrderStatus {}
    record Submitted(long timestampEpochMs) implements OrderStatus {}
    record Shipped(String trackingNumber) implements OrderStatus {}
    record Cancelled(String reason) implements OrderStatus {}
}

// Pure function evaluation
class OrderWorkflow {
    public static OrderStatus transition(OrderStatus current, String action, String tracking) {
        return switch (current) {
            case OrderStatus.Draft() when "SUBMIT".equals(action) -> 
                new OrderStatus.Submitted(System.currentTimeMillis());
            case OrderStatus.Submitted(_) when "SHIP".equals(action) && tracking != null -> 
                new OrderStatus.Shipped(tracking);
            case OrderStatus.Draft(), OrderStatus.Submitted(_) when "CANCEL".equals(action) -> 
                new OrderStatus.Cancelled("User cancelled");
            default -> throw new IllegalStateException("Transisi tidak valid dari state: " + current);
        };
    }
}
```

#### Practical Example: High-Throughput Financial Account Settlement
Kode standar perbankan untuk mutasi rekening secara *thread-safe* dan fungsional murni.

```java
package com.enterprise.banking.domain;

import java.math.BigDecimal;
import java.util.Objects;
import java.util.UUID;

// 1. Immutable Domain Primitives via Records
public record AccountId(UUID value) {
    public AccountId {
        Objects.requireNonNull(value, "AccountId tidak boleh bernilai null");
    }
}

public record Money(BigDecimal amount, String currency) {
    public Money {
        Objects.requireNonNull(amount, "Amount mandatory");
        Objects.requireNonNull(currency, "Currency mandatory");
        if (amount.scale() > 4) {
            throw new IllegalArgumentException("Presisi maksimal adalah 4 digit desimal");
        }
    }

    public Money add(Money other) {
        validateCurrency(other);
        return new Money(this.amount.add(other.amount), this.currency);
    }

    public Money subtract(Money other) {
        validateCurrency(other);
        return new Money(this.amount.subtract(other.amount), this.currency);
    }

    public boolean isGreaterThanOrEqual(Money other) {
        validateCurrency(other);
        return this.amount.compareTo(other.amount) >= 0;
    }

    private void validateCurrency(Money other) {
        if (!this.currency.equals(other.currency)) {
            throw new IllegalArgumentException("Mismatched currency: " + this.currency + " vs " + other.currency);
        }
    }
}

// 2. Algebraic Data Types for Ledger Commands
public sealed interface LedgerCommand {
    record Deposit(AccountId target, Money amount, String referenceId) implements LedgerCommand {}
    record Withdraw(AccountId source, Money amount, String referenceId) implements LedgerCommand {}
    record Hold(AccountId source, Money amount, String holdReason) implements LedgerCommand {}
}

// 3. Algebraic Data Types for Ledger Events
public sealed interface LedgerEvent {
    record Deposited(AccountId target, Money amount, String ref) implements LedgerEvent {}
    record Withdrawn(AccountId source, Money amount, String ref) implements LedgerEvent {}
    record InsufficientFundsAttempted(AccountId source, Money requested, Money currentBalance) implements LedgerEvent {}
}

// 4. Pure Domain Entity (State)
public record Account(AccountId id, Money balance, boolean isFrozen) {
    public Account {
        Objects.requireNonNull(id);
        Objects.requireNonNull(balance);
    }
}

// 5. Functional Core (Evaluator murni, tidak ada I/O, deterministik)
public final class AccountOperations {
    
    private AccountOperations() {} // Prevent direct instantiation

    public record ExecutionResult(Account updatedAccount, LedgerEvent event) {}

    public static Result<ExecutionResult, String> process(Account current, LedgerCommand command) {
        if (current.isFrozen()) {
            return Result.failure("Rekening dibekukan, operasi ditolak");
        }

        return switch (command) {
            case LedgerCommand.Deposit dep -> {
                Account mutated = new Account(current.id(), current.balance().add(dep.amount()), false);
                yield Result.success(new ExecutionResult(mutated, new LedgerEvent.Deposited(dep.target(), dep.amount(), dep.referenceId())));
            }
            case LedgerCommand.Withdraw wth -> {
                if (!current.balance().isGreaterThanOrEqual(wth.amount())) {
                    yield Result.success(new ExecutionResult(current, 
                        new LedgerEvent.InsufficientFundsAttempted(current.id(), wth.amount(), current.balance())));
                }
                Account mutated = new Account(current.id(), current.balance().subtract(wth.amount()), false);
                yield Result.success(new ExecutionResult(mutated, new LedgerEvent.Withdrawn(wth.source(), wth.amount(), wth.referenceId())));
            }
            case LedgerCommand.Hold _ -> Result.failure("Operasi Hold belum diimplementasikan pada Core ini");
        };
    }
}

// 6. Generic Functional Result monad
public sealed interface Result<T, E> {
    record Success<T, E>(T value) implements Result<T, E> {}
    record Failure<T, E>(E error) implements Result<T, E> {}

    static <T, E> Result<T, E> success(T value) { return new Success<>(value); }
    static <T, E> Result<T, E> failure(E error) { return new Failure<>(error); }
}
```

---

### 8. Real World Case Study (Enterprise Scale)
**Skenario**: Core Banking Clearing Engine memproses 50.000 transaksi settlement antarbank per detik (*Real-Time Gross Settlement*). 

- **Problem Statement**:
  Implementasi lama menggunakan Hibernate `@Entity` dengan mutasi *setter* langsung pada entity account. Saat 20 virtual threads mencoba memperbarui rekening bank sentral yang sama secara bersamaan, terjadi *OptimisticLockException* secara masif (>40% transaksi gagal dan retry), memicu GC pauses selama 4 detik karena pembuatan ribuan *detached object graphs* yang dibuang ke Eden space.

- **Solution Architecture**:
  1. Refactoring model persistensi menggunakan model *Event Sourcing snapshot* dengan Java `record`.
  2. Implementasi **Single-Writer Loop Pattern** menggunakan RingBuffer (LMAX Disruptor): thread tunggal mengeksekusi *Functional Core* `AccountOperations.process()`.
  3. Menghapus locking dan alokasi state transien. Pemrosesan state murni terjadi di CPU L1/L2 cache register.

- **Production Metric Improvements**:
  - Latensi p99 drop dari 1.200ms ke 1.8ms.
  - Alokasi memori berkurang dari 800 MB/detik menjadi 12 MB/detik (Scalar replacement aktif karena zero-escaping immutable records).
  - CPU usage turun dari 85% menjadi 24% pada volume 50.000 TPS.

---

### 9. Trade-offs (Analisis Arsitektur)

| Aspek | Pendekatan Mutable OOP Tradisional | Pendekatan Functional Core (Records/ADT) |
|---|---|---|
| **Memory Allocation** | Sedikit lebih rendah di awal jika meng-overwrite memori eksisting in-place. | Menghasilkan instansiasi record baru saat transisi state, namun mudah di-*scalar replace* oleh JIT jika lifecycle-nya lokal. |
| **CPU Cache Locality** | Buruk karena pointer chasing antar objek reference yang tersebar di heap. | Sangat tinggi; struktur flattened record memfasilitasi serial sequential reading di L1/L2 cache CPU. |
| **Concurrency Safety** | Butuh sinkronisasi manual (`ReentrantLock`, `synchronized`), rawan deadlocks & memory barriers. | Bebas thread contention (*lock-free*) karena state lama tidak pernah termutasi (*side-effect free*). |
| **Debugging Complexity** | Sulit; state suatu objek bisa diubah oleh method mana saja di thread mana saja (*temporal coupling*). | Sangat mudah; murni matematis, cukup periksa input `(State, Command)` untuk mereproduksi bug. |
| **Refactoring Cost** | Ringan di awal, eksponensial di akhir saat basis kode membesar. | Ketat di awal; menuntut disiplin *type-system*, namun biaya pemeliharaan flat saat sistem membesar. |

---

### 10. Common Mistakes & Troubleshooting

#### Kasus 1: Megamorphic Call Sites di Dynamic Rule Engine
- **Gejala**: CPU profil menunjukkan penggunaan waktu yang sangat tinggi pada pemanggilan interface method (`invokeinterface`) meskipun logika di dalam method sangat pendek.
- **Penyebab**: Lebih dari 2 kelas implementasi konkret melewati interface call site yang sama di loop fungsional. JIT compiler mendonasi status call-site ke *Megamorphic*, menghentikan *inlining*.
- **Solusi**: Ubah polymorphism polymorphic dispatch dinamis menjadi `sealed interface` dengan `switch` expression (Pattern Matching). Pola switch dievaluasi menggunakan bytecode `tableswitch` atau `lookupswitch` berkecepatan tinggi yang dapat dioptimasi oleh JIT secara deterministik.

#### Kasus 2: Shallow Immutability Leakage
- **Gejala**: Data pada record tiba-tiba berubah tanpa melalui logic transitions.
- **Penyebab**: Record hanya menjamin referensi immutable (*shallow*). Menyimpan `List` atau `Date` mutabel di dalam komponen record memungkinkan modifikasi via referensi luar:
```java
// KESALAHAN FATAL:
public record BadPayload(List<String> items) {} 
// Solusi:
public record GoodPayload(List<String> items) {
    public GoodPayload {
        items = List.copyOf(items); // Defensive unmodifiable copy
    }
}
```

#### Kasus 3: Boxing Overhead di Stream Pipelines
- **Gejala**: GC CPU time meningkat drastis saat memproses aggregation array numerik.
- **Penyebab**: Menggunakan `Stream<Long>` alih-alih `LongStream`. Setiap angka 64-bit di-box ke objek `java.lang.Long` berukuran 24 bytes, memboroskan bandwidth memory bus.
- **Solusi**: Gunakan Primitive Streams (`IntStream`, `LongStream`, `DoubleStream`) atau arrays primitif di hot-path fungsional.

---

### 11. Best Practices (Production Checklist)

- [ ] **Desain ADT**: Selalu buat interface domain sebagai `sealed` dan definisikan implementasi konkretnya (`permits`) secara eksplisit.
- [ ] **Validasi Kompak**: Manfaatkan *Compact Constructor* pada record untuk memastikan validitas invarian bisnis (*fail-fast* saat inisialisasi).
- [ ] **Larangan I/O di Core**: Pastikan tidak ada dependensi terhadap database client, HTTP client, `Clock.systemUTC()`, atau `UUID.randomUUID()` di dalam *functional core*. Operan temporal dan identifier harus disuplai dari *Imperative Shell*.
- [ ] **No Hidden Allocations**: Hindari pemanggilan `.stream()` di dalam *inner loops* yang dieksekusi lebih dari 10.000 kali per detik; ganti dengan perulangan indeks array standar untuk mengeliminasi alokasi iterator.
- [ ] **Virtual Thread Friendly**: Pastikan kode tidak menggunakan blok `synchronized` yang melingkupi I/O pada Imperative Shell untuk menghindari *Virtual Thread Pinning* (gunakan `ReentrantLock` jika mutasi kritis diperlukan).

---

### 12. Hands-on Practice
Simpan seluruh file berikut di dalam folder: `hands-on/m02/`

#### Langkah 1: Siapkan Struktur Direktori
```bash
mkdir -p hands-on/m02/src/main/java/com/enterprise/fcis
mkdir -p hands-on/m02/src/test/java/com/enterprise/fcis
```

#### Langkah 2: Buat File `DomainEngine.java`
Path: `hands-on/m02/src/main/java/com/enterprise/fcis/DomainEngine.java`

```java
package com.enterprise.fcis;

import java.util.List;
import java.util.Objects;

public class DomainEngine {

    public sealed interface LoanState {
        record Applied(String applicantId, long amount) implements LoanState {}
        record Underwritten(String applicantId, long amount, int creditScore) implements LoanState {}
        record Approved(String applicantId, long amount, double interestRate) implements LoanState {}
        record Rejected(String applicantId, String reason) implements LoanState {}
    }

    public sealed interface DecisionCommand {
        record Underwrite(int creditScore) implements DecisionCommand {}
        record Approve() implements DecisionCommand {}
        record Reject(String reason) implements DecisionCommand {}
    }

    public static LoanState process(LoanState state, DecisionCommand cmd) {
        Objects.requireNonNull(state, "State tidak boleh null");
        Objects.requireNonNull(cmd, "Command tidak boleh null");

        return switch (state) {
            case LoanState.Applied a when cmd instanceof DecisionCommand.Underwrite u -> {
                if (u.creditScore() < 300 || u.creditScore() > 850) {
                    throw new IllegalArgumentException("Credit score invalid");
                }
                yield new LoanState.Underwritten(a.applicantId(), a.amount(), u.creditScore());
            }
            case LoanState.Underwritten u when cmd instanceof DecisionCommand.Approve -> {
                if (u.creditScore() < 650) {
                    yield new LoanState.Rejected(u.applicantId(), "Credit score di bawah ambang batas minimal");
                }
                double rate = (u.creditScore() >= 750) ? 0.05 : 0.085;
                yield new LoanState.Approved(u.applicantId(), u.amount(), rate);
            }
            case LoanState.Underwritten u when cmd instanceof DecisionCommand.Reject r -> 
                new LoanState.Rejected(u.applicantId(), r.reason());
            case LoanState.Applied a when cmd instanceof DecisionCommand.Reject r ->
                new LoanState.Rejected(a.applicantId(), r.reason());
            default -> throw new IllegalStateException("Transisi ilegal: State [" 
                + state.getClass().getSimpleName() + "] tidak menerima command [" 
                + cmd.getClass().getSimpleName() + "]");
        };
    }
}
```

#### Langkah 3: Eksekusi Unit Test Verifikasi Deterministik
Path: `hands-on/m02/src/test/java/com/enterprise/fcis/DomainEngineTest.java`

```java
package com.enterprise.fcis;

import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import static com.enterprise.fcis.DomainEngine.*;

public class DomainEngineTest {

    @Test
    public void testSuccessfulLoanFlow() {
        LoanState initial = new LoanState.Applied("CUST-990", 500_000_000L);
        
        LoanState underwritten = DomainEngine.process(initial, new DecisionCommand.Underwrite(780));
        Assertions.assertInstanceOf(LoanState.Underwritten.class, underwritten);

        LoanState approved = DomainEngine.process(underwritten, new DecisionCommand.Approve());
        Assertions.assertInstanceOf(LoanState.Approved.class, approved);
        
        LoanState.Approved app = (LoanState.Approved) approved;
        Assertions.assertEquals(0.05, app.interestRate(), 0.0001);
    }

    @Test
    public void testUnderwriteRejectionFlow() {
        LoanState initial = new LoanState.Applied("CUST-102", 100_000_000L);
        LoanState underwritten = DomainEngine.process(initial, new DecisionCommand.Underwrite(550));
        LoanState finalState = DomainEngine.process(underwritten, new DecisionCommand.Approve());

        Assertions.assertInstanceOf(LoanState.Rejected.class, finalState);
        Assertions.assertTrue(((LoanState.Rejected) finalState).reason().contains("ambang batas"));
    }
}
```

---

### 13. Exercise

#### Level: Easy
- **Tugas**: Tambahkan state `Disbursed` pada `LoanState` dan command `Disburse(long timestamp)` pada `DecisionCommand`. Pastikan state `Disbursed` hanya bisa ditransisikan dari state `Approved`.
- **Kriteria**: Jika command `Disburse` dicoba dieksekusi saat state masih `Underwritten`, lempar `IllegalStateException`.

#### Level: Medium
- **Tugas**: Buat generic monad `ValidationResult<T>` yang mampu mengumpulkan (*accumulate*) lebih dari satu pesan error (bukan langsung *fail-fast* pada exception pertama) menggunakan immutable collections, lalu bungkus fungsi parsing identitas applicant di Imperative Shell sebelum menyentuh `LoanState`.

#### Level: Hard
- **Tugas**: Implementasikan high-performance in-memory ledger reconciler yang memproses `List<TransactionRecord>` berjumlah 1.000.000 baris. Reconciler dilarang memicu alokasi heap baru di inner loop (reuse record wrapper melalui *Flyweight* pattern atau unbox flattening array primitif `long[] accounts, long[] amounts`) dan laporkan execution latency p99.9 harus berada di bawah 15 milidetik.

---

### 14. Challenge
**Tantangan Sistem E-Commerce Settlement Engine (Zero-Allocation Core)**:
Rancang arsitektur modul *Order Clearing* yang mampu menerima aliran multi-item orders dengan diskon dinamis bertingkat.
- **Constraint 1**: Tidak boleh menggunakan framework eksternal apa pun (Pure Java 21 SDK).
- **Constraint 2**: State domain *Cart* dan *Coupon* harus dimodelkan menggunakan `sealed hierarchy` dan `record`.
- **Constraint 3**: Sediakan *Imperative Shell* virtual-thread-based yang memvalidasi stok ke database palsu (mock I/O berlatensi buatan 10ms via `Thread.sleep()`), mengeksekusi *Functional Core*, dan menuliskan event logs. 
- **Target Uji Beban**: Sistem harus stabil pada 10.000 concurrent virtual threads tanpa mengalami thread starvation, memory leak, atau polymorphic call site degradation.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Mengapa sebuah `record` di Java bersifat `final` secara implisit dan tidak dapat memperluas (extends) kelas lain?
2. Bagaimana mekanisme kerja *Compact Constructor* pada Java Record dan apa bedanya dengan canonical constructor?
3. Sebutkan ukuran byte overhead metadata dasar (Mark Word + Klass Word) dari instansiasi objek Java pada 64-bit JVM tanpa compressed OOPs!
4. Apa fungsi klausa `permits` pada sebuah `sealed interface` dan kapan klausa tersebut opsional untuk dituliskan?
5. Mengapa pure functions mempermudah proses concurrent programming?

#### B. Pertanyaan Intermediate
6. Jelaskan bagaimana JIT Compiler (C2) memanfaatkan *Escape Analysis* untuk melakukan *Scalar Replacement* pada objek `record`!
7. Terangkan perbedaan mendasar antara *vtable dispatch* (`invokevirtual`) dan *itable dispatch* (`invokeinterface`) dalam konteks konsumsi siklus CPU.
8. Apa yang menyebabkan suatu call site berubah status menjadi *Megamorphic* dan apa dampak fatalnya terhadap performa hot-path aplikasi?
9. Bagaimana Anda mendesain sebuah record yang berisi field `java.util.Map` agar karakteristik immutability-nya tidak bocor (*breached*) ke client luar?
10. Dalam paradigma FCIS, mengapa `System.currentTimeMillis()` atau `UUID.randomUUID()` dilarang dipanggil di dalam Functional Core?

#### C. Skenario Kasus Produksi
11. **Skenario 1**: Sebuah microservice sistem trading mengalami lonjakan GC Pause (Stop-The-World) hingga 800ms setiap kali volume order meningkat drastis. Profiler menunjukkan jutaan objek `java.util.Optional` dan lambdas dialokasikan per detik pada functional stream pipeline pemrosesan harga. Solusi struktural apa yang harus diterapkan pada kode core engine?
12. **Skenario 2**: Anda mendesain payment gateway engine. Tim Anda menggunakan arsitektur OOP warisan (inheritance) di mana `CreditCardPayment` mewarisi `BasePayment`. Setiap jenis pembayaran memiliki 15 subclass berbeda. Pemanggilan method `payment.authorize()` pada loop transaksi utama berjalan lambat secara konsisten. Bagaimana merekayasa ulang arsitektur ini dengan modern Java primitives agar performa eksekusi melonjak?
13. **Skenario 3**: Sebuah bank mengeluhkan terjadinya deadlock saat dua transaksi transfer antar rekening A dan Rekening B dieksekusi bersamaan di Imperative Shell (Thread 1: A -> B, Thread 2: B -> A). Bagaimana arsitektur *Functional Core, Imperative Shell* menyelesaikan masalah concurrency hazard semacam ini secara tuntas?

---

### 16. Summary
- **Mekanika JVM**: Efisiensi sistem Java enterprise dibangun di atas pemahaman layout memori objek, pencegahan *megamorphic dispatch*, dan penciptaan struktur data lokal yang memfasilitasi optimasi *Escape Analysis* JIT compiler.
- **Arsitektur FCIS**: Memisahkan kode menjadi *Functional Core* yang deterministik dan *Imperative Shell* yang mengisolasi I/O menghasilkan sistem enterprise yang sangat mudah diuji (*testable*), tahan terhadap concurrency bugs, dan scalable.
- **Modern Java Primitives**: Perpaduan antara `record`, `sealed interface`, dan *Pattern Matching* menyediakan sarana pemodelan *Algebraic Data Types* (ADT) yang sangat ekspresif, aman secara tipe (*compile-time exhaustive check*), dan efisien dari sisi alokasi memori. Menguasai pemisahan ini adalah fondasi mutlak seorang Enterprise Software Architect.