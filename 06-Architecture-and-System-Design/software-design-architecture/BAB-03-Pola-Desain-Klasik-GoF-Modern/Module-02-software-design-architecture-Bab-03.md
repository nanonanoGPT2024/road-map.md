# Kurikulum Enterprise Software Architecture
## Topik: 06-Architecture-and-System-Design / BAB-03-Pola-Desain-Klasik-GoF-Modern
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis Overhead Runtime GoF Klasik:** Membedakan biaya komputasi *dynamic dispatch* (*vtable resolution*), *pointer indirection*, dan *cache miss* dari implementasi GoF klasik terhadap modern *monomorphization* dan *data-oriented design*.
- **Mengimplementasikan Pola Desain Berbasis Concurrency & Non-blocking:** Mengembangkan variasi pola *State*, *Observer*, dan *Chain of Responsibility* yang aman terhadap konkurensi (*thread-safe*, *lock-free*, atau *backpressure-aware*) pada throughput tinggi (>50.000 RPS).
- **Mentransformasi Pola Klasik ke Idiom Modern:** Mengganti *boilerplate class hierarchy* klasik menggunakan fitur bahasa modern seperti *Sealed Interfaces*, *Pattern Matching*, *First-Class Functions*, dan *Generics*.
- **Mendiagnosis Kegagalan Produksi Pola GoF:** Mengidentifikasi dan memitigasi *memory leak* pada *Observer/Listener*, *circular dependency* pada *Mediator/DI*, serta *contention bottlenecks* pada *Object Pool* dan *Singleton*.
- **Merancang Arsitektur Pipeline Transaksional Enterprise:** Menggabungkan pola *Abstract Factory*, *Pipeline/Interceptor (Decorator)*, dan *Hierarchical State Machine* untuk sistem pemrosesan finansial dengan latensi sub-milidetik.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, peserta harus menguasai:
- **Prinsip SOLID & GoF Dasar:** Memahami intent dasar dari 23 pola Gang of Four (GoF).
- **Sistem Tipe & Memori:** Memahami perbedaan *Stack* vs *Heap allocation*, *Escape Analysis*, dan mekanisme *Virtual Method Table (vtable)*.
- **Konkurensi Tingkat Menengah:** Memahami primitif sinkronisasi (*Mutex*, *Read-Write Lock*, *CAS/Atomic operations*, dan *Memory Barriers*).
- **Bahasa Pemrograman Modern:** Pemahaman membaca sintaksis modern (misal: Java 21+, Go 1.21+, atau Rust) yang mendukung generics, closures, dan tipe aljabar (*Algebraic Data Types*).

---

### 3. Concept & Internal Architecture (Mendalam)

Implementasi pola GoF di lingkungan enterprise modern menuntut kompromi antara abstraksi modular dan efisiensi level mesin (*hardware sympathy*). 

#### 3.1. Anatomi Polymorphic Dispatch & Overhead VTable
Pada GoF klasik, polimorfisme dicapai melalui pewarisan (*inheritance*) dan antarmuka dinamis. Secara internal:

```
+--------------------------------------------------------+
| Object Memory Layout in Heap                           |
|  +--------------------+------------------------------+ |
|  | *vptr (8 bytes)    | Instance Fields (Data) ...   | |
|  +---------+----------+------------------------------+ |
+------------|-------------------------------------------+
             |
             v
+-------------------------------+
| Virtual Method Table (VTable) |
|  +--------------------------+ |
|  | &Method1() Function Pointer |
|  +--------------------------+ |
|  | &Method2() Function Pointer |
|  +--------------------------+ |
+-------------------------------+
```

1. **Pointer Indirection:** CPU harus membaca alamat *vptr* dari *object header*, melompat ke memori *VTable*, membaca pointer fungsi, baru melompat ke instruksi biner fungsi tersebut.
2. **Branch Misprediction:** Kompiler dan CPU kesulitan melakukan spekulasi eksekusi (*branch prediction*) karena target pemanggilan bersifat dinamis pada saat *runtime*.
3. **Inlining Barrier:** Fungsi yang dipanggil via *vtable* secara umum tidak dapat di-*inline* secara langsung oleh kompiler (kecuali dioptimalkan oleh JIT via *Monomorphic Inline Caching*), menghilangkan peluang optimasi *dead code elimination* dan *loop vectorization*.

#### 3.2. Modern Alternative: Tipe Data Aljabar & Monomorfisasi
Sistem modern mengganti polimorfisme berbasis kelas dengan *Sum Types* (*Sealed Interfaces* / *Tagged Unions*) yang dievaluasi menggunakan *Pattern Matching*:
- **Monomorphization / Static Dispatch:** Pada bahasa yang dikompilasi (Go/Rust/C++), penggunaan generic dievaluasi pada saat kompilasi (*compile-time substitution*), menghasilkan kode biner terdedikasi tanpa *vtable indirection*.
- **Sealed Hierarchies (Java/Kotlin):** Kompiler mengetahui seluruh kemungkinan implementasi dari sebuah *interface*, memungkinkan optimasi *jump table* deterministik di tingkat instruksi perakitan (*assembly*).

#### 3.3. Memory Locality & Cache Lines
Pola GoF klasik (seperti *Composite* atau *State*) sering kali menghasilkan struktur pointer-chasing:
$$\text{L1/L2 Cache Miss Latency} \approx 200 \times \text{CPU Register Cycle}$$
Ketika objek dialokasikan secara terpencar di heap, traversal hierarki menyebabkan *CPU cache thrashing*. Arsitektur modern mengadopsi representasi array terpadu (*Struct of Arrays* atau *Flat Buffer Pools*) di balik antarmuka pola desain tersebut.

---

### 4. Why & What

| Dimensi | Pendekatan GoF Klasik (Tahun 1994) | Pendekatan Enterprise Modern |
| :--- | :--- | :--- |
| **Gaya Pemrograman** | Object-Oriented kaku, deep class hierarchies. | Hybrid Functional-OOP, Composition over Inheritance. |
| **Abstraksi Perilaku** | Kelas konkret mengimplementasikan interface untuk 1 method. | *First-class functions*, *Lambdas*, *Higher-Order Functions*. |
| **Manajemen State** | *Mutable in-place state modification* dengan lock. | *Immutable data structures*, Event Sourcing, CAS-driven state transitions. |
| **Kopling Komponen** | Direct pointer reference, raw Observer/Subject. | Reactive Streams (Flow/Rx), In-Memory Ring Buffer, Channel-based pub-sub. |
| **Lifecycle & Scope** | Mengandalkan *Singleton* global dan manual instantiation. | Inversion of Control (IoC) Container terkelola, Context-bound lifecycles. |

#### Mengapa Perlu Berubah?
1. **Multi-Core Scaling:** Pola GoF klasik didesain pada era *single-core CPU*. Pola yang mengandalkan mutable state terbagi (seperti naive Singleton atau naive Observer) memicu *severe lock contention* pada server 64-core modern.
2. **GC Pressure:** Instansiasi objek kecil berumur pendek yang berlebihan (akibat naive *Command* atau *Strategy* object allocations) membebani garbage collector, memicu lonjakan latensi p99 (*stop-the-world pauses*).

---

### 5. How (Workflow Detail)

Alur kerja arsitektur pemrosesan transaksi enterprise yang memodernisasi pola *Factory*, *Decorator (Pipeline)*, *Strategy*, dan *State*:

```
[Inbound Request]
       |
       v
[Step 1: Dynamic Factory / Registry]
       |---> Resolusi tipe transaksi secara static/compile-time safe
       v
[Step 2: Interceptor Pipeline (Modern Decorator)]
       |---> Auth Verification (Non-allocating)
       |---> Metrics Tracing (Context Propagation)
       |---> Rate Limiting (Token Bucket / Lock-free)
       v
[Step 3: Strategy Selection via Pattern Matching]
       |---> Evaluasi aturan bisnis (Zero-allocation execution)
       v
[Step 4: Atomic State Transition]
       |---> CAS / Actor Mailbox / FSM Validation
       v
[Step 5: Event Notification (Decoupled Observer)]
       |---> Non-blocking Ring Buffer / Disruptor / Event Bus
       v
[Outbound Response]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Rel Kereta Logistik Otomatis vs Kurir Manual
* **GoF Klasik:** Seperti memesan kurir manual untuk setiap paket kecil. Kurir datang ke kantor pusat, bertanya ke meja resepsionis (*vtable lookup*), mengambil dokumen, berjalan ke gedung lain, menandatangani buku tamu yang dikunci satu orang (*mutex lock*), lalu mengubah status barang di papan tulis.
* **GoF Modern:** Seperti sistem ban berjalan terpadu (*conveyor belt*) dengan sensor optik. Paket diproses secara kontigu di memori (*cache-line friendly*). Ketika tipe barang terdeteksi melalui kode batang (*pattern matching*), aktuator hidrolik langsung membelokkan jalur secara deterministik tanpa perlu interogasi manual bertingkat.

#### Diagram Arsitektur Komponen: Non-Blocking Execution Pipeline

```
+-----------------------------------------------------------------------------------+
| TRANSACTION PROCESSING PIPELINE                                                   |
+-----------------------------------------------------------------------------------+
                                                                                     
  Incoming Data                                                                     
        |                                                                           
        v                                                                           
  +------------------+      Resolves       +--------------------------------------+ 
  | Transaction      | ------------------> | Sealed Transaction Type              | 
  | Factory Registry |                     | [Deposit | Withdraw | Transfer]      | 
  +------------------+                     +--------------------------------------+ 
        |                                                     |                     
        v                                                     v                     
  +-------------------------------------------------------------------------------+ 
  | Interceptor Chain (Decorator Pipeline)                                        | 
  |                                                                               | 
  |  +--------------------+   +--------------------+   +-----------------------+  | 
  |  | SecurityValidator  |-->| RateLimiterFilter  |-->| TelemetryContextFilter|  | 
  |  +--------------------+   +--------------------+   +-----------------------+  | 
  +-------------------------------------------------------------------------------+ 
        |                                                                           
        v                                                                           
  +-------------------------------------------------------------------------------+ 
  | High-Performance Strategy Evaluator (Pattern Matching & Pure Functions)      | 
  |                                                                               | 
  |  switch (transaction) {                                                       | 
  |    case Deposit d  -> PureFinancialEngine::applyDeposit;                      | 
  |    case Withdraw w -> PureFinancialEngine::applyWithdraw;                     | 
  |    case Transfer t -> PureFinancialEngine::applyTransfer;                     | 
  |  }                                                                            | 
  +-------------------------------------------------------------------------------+ 
        |                                                                           
        v                                                                           
  +-------------------------------------------------------------------------------+ 
  | Lock-Free State Machine (Atomic Reference / CAS Loop)                         | 
  |                                                                               | 
  |  Current: [Pending] ===== CAS Success =====> Next: [Authorized]              | 
  |                 ^                                                              | 
  |                 |---- CAS Conflict Retry (Exponential Backoff)                | 
  +-------------------------------------------------------------------------------+ 
        |                                                                           
        v                                                                           
  +-------------------------------------------------------------------------------+ 
  | Observer System: High-Throughput Event Multiplexer                            | 
  |                                                                               | 
  |  +-------------------------------------------------------------------------+  | 
  |  | Circular Ring Buffer / LMAX-style Queue (Zero GC Pressure)              |  | 
  |  +-------------------------------------------------------------------------+  | 
  |          |                                   |                                  
  |          v                                   v                                  
  |  [Audit Ledger Worker]            [WebSocket Client Pusher]                     
  +-------------------------------------------------------------------------------+ 
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Evolusi Strategy Pattern (Java 21+)

##### Pendekatan GoF Klasik (Verbose, Heap Allocating, Boilerplate)
```java
// Klasik: Membutuhkan hierarki interface dan banyak kelas implementasi
public interface DiscountStrategy {
    double applyDiscount(double amount);
}

public class BlackFridayDiscountStrategy implements DiscountStrategy {
    @Override
    public double applyDiscount(double amount) {
        return amount * 0.70;
    }
}

public class OrderContext {
    private DiscountStrategy strategy;
    public OrderContext(DiscountStrategy strategy) { this.strategy = strategy; }
    public double execute(double val) { return strategy.applyDiscount(val); }
}
```

##### Pendekatan Modern (Functional, Stateless, Zero-Boilerplate)
```java
package enterprise.design.modern;

import java.util.Map;
import java.util.function.DoubleUnaryOperator;

public final class ModernStrategy {
    // Strategy didefinisikan sebagai fungsi murni (stateless & reusable)
    public static final DoubleUnaryOperator NO_DISCOUNT = amount -> amount;
    public static final DoubleUnaryOperator BLACK_FRIDAY = amount -> amount * 0.70;
    public static final DoubleUnaryOperator VIP_CUSTOMER = amount -> amount * 0.85;

    // Registry Strategy berbasis compile-time map / enum dispatch
    public enum Tier {
        REGULAR(NO_DISCOUNT),
        SEASONAL(BLACK_FRIDAY),
        VIP(VIP_CUSTOMER);

        private final DoubleUnaryOperator discountLogic;
        Tier(DoubleUnaryOperator discountLogic) {
            this.discountLogic = discountLogic;
        }

        public double calculate(double amount) {
            return this.discountLogic.applyAsDouble(amount);
        }
    }
}
```

---

#### 7.2. Practical Example: Enterprise Order Execution Engine (Java 21)
Implementasi produksi menggabungkan:
1. **Sealed Types** untuk isolasi varian perintah (Modern *Factory/Strategy*).
2. **Lock-Free State Machine** (*State Pattern* menggunakan `VarHandle`/Atomic updates).
3. **Composable Functional Interceptors** (*Chain of Responsibility / Decorator*).

```java
package enterprise.engine;

import java.lang.invoke.MethodHandles;
import java.lang.invoke.VarHandle;
import java.util.Objects;
import java.util.concurrent.CompletableFuture;
import java.util.function.Function;

// ============================================================================
// 1. DATA MODELS: Sealed Types (Algebraic Data Types)
// ============================================================================
public final class Domain {
    public sealed interface OrderCommand permits CreateOrder, CancelOrder, SettleOrder {}
    public record CreateOrder(String orderId, double amount, String assetId) implements OrderCommand {}
    public record CancelOrder(String orderId, String reason) implements OrderCommand {}
    public record SettleOrder(String orderId, long executionTimestamp) implements OrderCommand {}

    public enum OrderState {
        NEW, PENDING, SETTLED, CANCELLED
    }
}

// ============================================================================
// 2. STATE MACHINE: Modern Lock-Free State Pattern via CAS
// ============================================================================
final class OrderAggregate {
    private final String orderId;
    private final double amount;
    private volatile Domain.OrderState currentState;

    private static final VarHandle STATE_HANDLE;
    static {
        try {
            STATE_HANDLE = MethodHandles.lookup().findVarHandle(
                OrderAggregate.class, "currentState", Domain.OrderState.class
            );
        } catch (ReflectiveOperationException e) {
            throw new ExceptionInInitializerError(e);
        }
    }

    public OrderAggregate(String orderId, double amount) {
        this.orderId = orderId;
        this.amount = amount;
        this.currentState = Domain.OrderState.NEW;
    }

    public boolean transitionTo(Domain.OrderState expected, Domain.OrderState target) {
        return STATE_HANDLE.compareAndSet(this, expected, target);
    }

    public Domain.OrderState getCurrentState() {
        return currentState;
    }

    public String getOrderId() { return orderId; }
    public double getAmount() { return amount; }
}

// ============================================================================
// 3. MODERN PIPELINE (Chain of Responsibility / Decorator via Functional Composition)
// ============================================================================
@FunctionalInterface
interface PipelineContext<T, R> {
    R execute(T context);

    default <V> PipelineContext<T, V> andThen(Function<R, V> after) {
        Objects.requireNonNull(after);
        return context -> after.apply(execute(context));
    }
}

final class ValidationStep {
    public static OrderAggregate validateLimits(OrderAggregate order) {
        if (order.getAmount() <= 0) {
            throw new IllegalArgumentException("Nilai order harus lebih dari nol");
        }
        if (order.getAmount() > 1_000_000.0) {
            throw new IllegalArgumentException("Melebihi single execution limit");
        }
        return order;
    }

    public static OrderAggregate auditLogging(OrderAggregate order) {
        // High-performance direct system telemetry logging (Zero-allocation)
        System.out.printf("[AUDIT] Processing Order=%s, State=%s%n", 
            order.getOrderId(), order.getCurrentState());
        return order;
    }
}

// ============================================================================
// 4. STRATEGY EVALUATOR VIA PATTERN MATCHING
// ============================================================================
final class OrderExecutionService {

    public Domain.OrderState processCommand(Domain.OrderCommand cmd, OrderAggregate aggregate) {
        // Pattern matching modern Java untuk evaluasi strategi
        return switch (cmd) {
            case Domain.CreateOrder create -> {
                if (aggregate.transitionTo(Domain.OrderState.NEW, Domain.OrderState.PENDING)) {
                    yield Domain.OrderState.PENDING;
                }
                throw new IllegalStateException("Gagal transisi NEW -> PENDING");
            }
            case Domain.SettleOrder settle -> {
                if (aggregate.transitionTo(Domain.OrderState.PENDING, Domain.OrderState.SETTLED)) {
                    yield Domain.OrderState.SETTLED;
                }
                throw new IllegalStateException("Gagal transisi PENDING -> SETTLED");
            }
            case Domain.CancelOrder cancel -> {
                // Bisa cancel dari NEW atau PENDING
                while (true) {
                    Domain.OrderState current = aggregate.getCurrentState();
                    if (current == Domain.OrderState.SETTLED || current == Domain.OrderState.CANCELLED) {
                        throw new IllegalStateException("Tidak bisa membatalkan order yang sudah final: " + current);
                    }
                    if (aggregate.transitionTo(current, Domain.OrderState.CANCELLED)) {
                        yield Domain.OrderState.CANCELLED;
                    }
                    // CAS retry spin loop
                    Thread.onSpinWait();
                }
            }
        };
    }
}

// ============================================================================
// 5. PRODUCTION INTEGRATION SUITE
// ============================================================================
public class ProductionEngineDemo {
    public static void main(String[] args) {
        OrderAggregate order = new OrderAggregate("ORD-99021", 50_000.0);

        // Komposisi Interceptor Pipeline
        Function<OrderAggregate, OrderAggregate> executionPipeline = 
            ((Function<OrderAggregate, OrderAggregate>) ValidationStep::validateLimits)
                .andThen(ValidationStep::auditLogging);

        // Eksekusi Pipeline
        OrderAggregate validatedOrder = executionPipeline.apply(order);

        OrderExecutionService service = new OrderExecutionService();

        // 1. Eksekusi Create
        Domain.OrderState s1 = service.processCommand(
            new Domain.CreateOrder(validatedOrder.getOrderId(), 50000.0, "BTC-USD"), 
            validatedOrder
        );
        System.out.println("Hasil Transisi 1: " + s1);

        // 2. Eksekusi Settle
        Domain.OrderState s2 = service.processCommand(
            new Domain.SettleOrder(validatedOrder.getOrderId(), System.currentTimeMillis()), 
            validatedOrder
        );
        System.out.println("Hasil Transisi 2: " + s2);
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Refactoring Core Ledger & Settlement Engine pada FinTech Tier-1
* **Latar Belakang:** FinTech unicorn memproses lebih dari 120.000 transaksi pembayaran per detik pada jam puncak (*peak hour*). Implementasi awal menggunakan arsitektur GoF klasik berbasis Spring Beans:
  * Pola *State* dibuat menggunakan kelas polimorfik tersimpan di database via ORM Hibernate/JPA.
  * Pola *Chain of Responsibility* diimplementasikan dengan mendaftarkan puluhan Spring `@Component` interceptor yang dialokasikan di heap pada setiap request.
  * Pola *Observer* menggunakan pemanggilan sinkron bertingkat via event publisher internal framework.
* **Gejala Masalah di Produksi:**
  1. *GC Pause Times* mencapai 450ms setiap 15 detik karena pembentukan jutaan objek perantara (*FilterContext*, *StateWrapper*, *EventPayload*).
  2. Latensi p99 membengkak hingga 1.800ms.
  3. Terjadi deadlock fatal ketika dua thread mencoba mengubah state transaksi yang sama secara bersamaan melalui transaction lock database (`SELECT ... FOR UPDATE`).
* **Solusi Arsitektur Modern:**
  1. **Transformasi State Pattern:** Mengganti ORM Entity-based State Pattern menjadi In-Memory Lock-Free FSM berbasis *CAS (Compare-And-Swap)* primitives dan snapshotting secara asinkron.
  2. **Pipeline Unrolling:** Menggabungkan rantai Decorator/Interceptor menjadi single compiled bytecode pipeline menggunakan Java Functional Interfaces tanpa alokasi objek per request.
  3. **Zero-Alloc Strategy Dispatch:** Menggantikan Dynamic Polymorphic Lookup dengan *Sealed Types* dan *Type-switch Pattern Matching*, memungkinkan compiler melakukan *Monomorphic Inlining*.
  4. **Ring Buffer Observer:** Pola Observer digantikan oleh single non-blocking Circular Ring Buffer (arsitektur LMAX Disruptor) dengan thread-pinning untuk I/O dan Audit Writer.
* **Hasil:**
  * Throughput meningkat dari **18.000 RPS** menjadi **135.000 RPS** per node.
  * Latensi p99 terpangkas dari **1.800ms** menjadi **1.2ms**.
  * Penggunaan memori JVM Heap turun sebesar 72%, mengeliminasi *Stop-the-World pauses*.

---

### 9. Trade-offs

| Pendekatan Desain | Keuntungan | Kerugian & Batasan | Mitigasi Arsitektur |
| :--- | :--- | :--- | :--- |
| **GoF Klasik (Full Polymorphic Hierarchy)** | Fleksibilitas tinggi; *Open-Closed Principle* murni tanpa memodifikasi class caller; sangat mudah di-mock dalam testing. | High pointer indirection; GC pressure masif; vtable overhead; potensi branch misprediction. | Batasi penggunaannya hanya pada *application-boundary* / orchestration layer dengan throughput rendah. |
| **Data-Oriented / Algebraic GoF (Sealed Types)** | Ekstrem cepat; monomorphic optimization; type-safety exhaustiveness di level kompilasi; zero-allocation. | Melanggar OCP kaku (menambah tipe baru mengharuskan recompilation / perubahan kode pemanggil). | Gunakan pada core domain logic yang membutuhkan audit ketat dan set varian domain yang relatif stabil. |
| **Lock-Free State Machine** | Latensi minimal; skalabilitas linier pada sistem multi-core; tidak ada resiko deadlock. | Rentan terhadap *CAS retry storm* / CPU starvation jika tingkat kontensi pada single key luar biasa tinggi. | Tambahkan *exponential backoff* dan *contention ring queues* jika kontensi tinggi. |
| **Ring-Buffer Event Decoupling** | Memisahkan produsen dan konsumen dengan zero-lock dan zero-GC; latensi ultra-deterministik. | Kompleksitas tinggi dalam implementasi; debugging stack trace menjadi asinkron dan sulit. | Lengkapi dengan *distributed tracing context* yang ditempelkan ke fixed pre-allocated payload. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Memory Leak pada Implementasi Pola Observer/Listener
* **Masalah:** Subjek (*Publisher*) menahan referensi kuat (*Strong Reference*) ke objek *Observer*. Saat lifecycle Observer harusnya selesai (misal request/session berakhir), objek tidak bisa di-garbage collect.
* **Deteksi:** OOM (*OutOfMemoryError*) setelah service berjalan beberapa hari. Heap dump analyzer menunjukkan jutaan instans listener tertahan di collection internal subjek.
* **Mitigasi:**
  * Gunakan `WeakReference` atau mekanisme cleanup eksplisit berbasis lifecycle event (*AutoCloseable*).
  * Di lingkungan modern, gantikan static observer dengan struktur *backpressure reactive streams* yang memiliki lifecycle completion jelas (`onComplete()`).

#### 10.2. Context Leak & Thread-Safety pada Interceptor Pipeline (Decorator)
* **Masalah:** Developer menyimpan data spesifik request di dalam field stateful dari singleton Decorator/Filter, memicu *race condition* antar request pengguna lain.
* **Deteksi:** Data pengguna A bocor ke pengguna B di bawah beban konkurensi tinggi.
* **Mitigasi:** Pastikan semua node pipeline berstatus **murni stateless**. Kirimkan seluruh state kontekstual melalui parameter method secara eksplisit, hindari *shared mutable fields*.

#### 10.3. Livelock pada State CAS Loop
* **Masalah:** Multiple worker berebut mengupdate State Machine objek yang sama secara bersamaan menggunakan `compareAndSet`, menyebabkan CPU 100% karena thread terus-menerus gagal dan berputar di `while(true)`.
* **Deteksi:** CPU utilization melonjak ke 100% tanpa kenaikan throughput (throughput justru jatuh ke mendekati nol).
* **Mitigasi:** Terapkan pembatasan retry maksimal, gunakan `Thread.onSpinWait()` untuk memberi sinyal optimasi pipeline CPU, dan implementasikan *jittered backoff*.

---

### 11. Best Practices (Production Checklist)

- [ ] **Immutability by Default:** Semua representasi command, event, dan domain value objects wajib diimplementasikan sebagai tipe immutable (misal: Java `record`, Kotlin `data class`, Rust `struct`).
- [ ] **Exhaustive Pattern Matching:** Pastikan tidak ada fallback `default:` liar tanpa semantic handling saat mengevaluasi sealed interface types untuk mendeteksi penambahan state baru sejak waktu kompilasi.
- [ ] **Thread-Safety Proof:** Jika menggunakan Singleton atau Factory Registry, inisialisasi wajib bersifat *eager* atau menggunakan idiom thread-safe lazily terverifikasi (misal: *Holder Class Idiom* atau *Double-Checked Locking* dengan penanda `volatile`).
- [ ] **Zero Escape Allocations on Hot Paths:** Pastikan profiling JIT / Kompiler menunjukkan bahwa pipeline Strategy dan State tidak mengalokasikan objek baru di memori Heap di dalam loop pemrosesan utama.
- [ ] **Decoupled Observability:** Metrics, logging, dan audit tracing pada pipeline tidak boleh memblokir thread eksekusi transaksional (gunakan decoupled logging / async appenders).
- [ ] **No Infinite Retries:** Semua implementasi retry berbasis CAS pada state transitions harus dibatasi oleh *max attempts* dan fallback failure handler.

---

### 12. Hands-on Practice

Buat dan uji implementasi transaksi finansial modern pada environment Anda.

#### 12.1. Struktur Direktori Proyek
```bash
hands-on/m02/
├── pom.xml (atau build.gradle)
└── src/
    ├── main/
    │   └── java/
    │       └── enterprise/
    │           └── architecture/
    │               ├── domain/
    │               │   ├── AccountTransaction.java
    │               │   └── TransactionType.java
    │               ├── pipeline/
    │               │   ├── PipelineStep.java
    │               │   └── TransactionPipeline.java
    │               └── state/
    │                   └── ConcurrentLedgerEntry.java
    └── test/
        └── java/
            └── enterprise/
                └── architecture/
                    └── EngineStressTest.java
```

#### 12.2. Langkah Praktikum

##### Langkah 1: Setup Proyek (Java 21+)
Pastikan JDK 21 terpasang:
```bash
java --version
# Output harus menunjukkan OpenJDK/Oracle JDK versi 21 atau lebih tinggi
```

##### Langkah 2: Buat PipelineStep Generic (`PipelineStep.java`)
```java
package enterprise.architecture.pipeline;

@FunctionalInterface
public interface PipelineStep<T> {
    T process(T input);

    default PipelineStep<T> linkWith(PipelineStep<T> next) {
        return input -> next.process(this.process(input));
    }
}
```

##### Langkah 3: Implementasi Test Stres Konkurensi (`EngineStressTest.java`)
Buat pengujian konkurensi tinggi untuk memvalidasi thread-safety:
```java
package enterprise.architecture;

import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

public class EngineStressTest {
    public static void main(String[] args) throws InterruptedException {
        int threadCount = 32;
        int operationsPerThread = 10_000;
        ExecutorService pool = Executors.newFixedThreadPool(threadCount);
        CountDownLatch latch = new CountDownLatch(threadCount);
        AtomicInteger successTransitions = new AtomicInteger(0);
        AtomicInteger rejectedTransitions = new AtomicInteger(0);

        // Target pengujian: Satu entry yang sama diakses ribuan thread bersamaan
        enterprise.engine.OrderAggregate testOrder = 
            new enterprise.engine.OrderAggregate("STRESS-01", 100.0);

        long start = System.nanoTime();
        for (int i = 0; i < threadCount; i++) {
            pool.submit(() -> {
                try {
                    for (int j = 0; j < operationsPerThread; j++) {
                        // Coba transisikan NEW -> PENDING
                        if (testOrder.transitionTo(
                                enterprise.engine.Domain.OrderState.NEW, 
                                enterprise.engine.Domain.OrderState.PENDING)) {
                            successTransitions.incrementAndGet();
                        } else {
                            rejectedTransitions.incrementAndGet();
                        }
                    }
                } finally {
                    latch.countDown();
                }
            });
        }

        latch.await();
        long duration = System.nanoTime() - start;
        pool.shutdown();

        System.out.printf("Selesai dalam: %.2f ms%n", duration / 1_000_000.0);
        System.out.println("Transisi Berhasil (Harus Tepat 1): " + successTransitions.get());
        System.out.println("Transisi Ditolak (Harus " + (threadCount * operationsPerThread - 1) + "): " 
            + rejectedTransitions.get());

        if (successTransitions.get() != 1) {
            System.err.println("TEST GAGAL: Terjadi Race Condition!");
            System.exit(1);
        } else {
            System.out.println("TEST SUKSES: Thread safety terbukti aman.");
        }
    }
}
```

##### Langkah 4: Eksekusi Test
```bash
javac -d bin $(find src -name "*.java")
java -cp bin enterprise.architecture.EngineStressTest
```

---

### 13. Exercise

#### Level Easy
Tuliskan refactoring pola **Singleton** klasik berikut menggunakan Java modern yang aman dari *reflection attack* dan *serialization breach*:
```java
// KODE YANG HARUS DIREFACTOR (Naive Singleton):
public class ClassicConfig {
    private static ClassicConfig instance;
    private ClassicConfig() {}
    public static ClassicConfig getInstance() {
        if (instance == null) { instance = new ClassicConfig(); }
        return instance;
    }
}
```
*Kriteria Penerimaan:* Thread-safe tanpa explicit synchronization block, kebal terhadap double-instantiation via reflection, dan kebal deserialization duplicate.

#### Level Medium
Implementasikan pola **Composite** modern menggunakan *Java Sealed Interfaces* dan *Records* untuk merepresentasikan pohon ekspresi aritmatika (`Add`, `Multiply`, `Constant`). Buat fungsi evaluasi rekursif murni (*pure function*) yang menghitung nilai akhir dari pohon tanpa meletakkan method `evaluate()` di dalam class node tersebut.  
*Kriteria Penerimaan:* Menggunakan pattern matching Java 21, zero mutable state, compiler memvalidasi seluruh varian ekspresi.

#### Level Hard
Rancang dan implementasikan pola **Observer/Event Bus** berkinerja tinggi yang mampu menangani 1.000.000 events/detik tanpa garbage collection pressure:
* Tidak boleh mengalokasikan memori baru di heap saat mem-publish event.
* Menggunakan antrian sirkular fixed-capacity (*Ring Buffer*).
* Menyediakan jaminan pemrosesan non-blocking untuk publisher (*drop* atau *backpressure signal* jika buffer penuh).  
*Kriteria Penerimaan:* Lulus stress-test konkurensi 16 thread publisher tanpa memicu *OutOfMemoryError* dan memory footprint konstan di VisualVM / JConsole.

---

### 14. Challenge

**Skenario Sistem:**
Anda adalah Principal Architect pada bursa aset digital. Sistem Matching Engine Anda menerima perintah transaksi via FIX Protocol dengan SLA: **p99 latency < 250 microsecond** pada beban **200.000 orders/sec**.

**Kebutuhan:**
1. Rancang arsitektur integrasi pola GoF teroptimasi yang memproses validasi margin (*Strategy*), penerapan biaya transaksi bertingkat (*Decorator/Chain*), transisi lifecycle order (*State*), dan notifikasi ke broadcast orderbook stream (*Observer*).
2. **Batasan Keras (Hard Constraints):**
   * **Zero Heap Allocation:** Di hot path (`OrderInbound` -> `Engine` -> `MatchResult`), alokasi objek baru di heap bernilai 0 bytes (Gunakan *Flyweight Object Pools* atau *Struct of Primitives*).
   * **No Blocking Locks:** Dilarang menggunakan `synchronized`, `ReentrantLock`, atau primitif pemblokir thread lainnya.
   * **Fault Isolation:** Kegagalan salah satu node observer (misal audit logging lambat) tidak boleh menyebabkan latensi spike pada pemrosesan order utama.

**Deliverables:**
* Diagram arsitektur memori mendalam (ASCII).
* Cetak biru desain teknis (*Architecture Specification Doc*) yang mencakup pemilihan primitif konkurensi, mitigasi *false sharing* CPU cache line, dan strategi garbage collection tuning.

---

### 15. Quiz Evaluasi Pemahaman

#### 15.1. Pertanyaan Basic

##### Q1: Mengapa pemanggilan metode virtual (*polymorphic dispatch*) pada GoF klasik memiliki overhead performa dibandingkan pemanggilan metode statis?
*A:* Karena pemanggilan metode virtual membutuhkan operasi *pointer indirection* melalui *Virtual Method Table (vtable)* yang berada di memori, sehingga mencegah optimasi *inlining* oleh kompiler dan berpotensi memicu *CPU branch misprediction* serta *cache miss*.

##### Q2: Apa bahaya utama dari implementasi pola *Double-Checked Locking* pada Singleton tanpa menggunakan kata kunci `volatile` pada lingkungan Java/C++?
*A:* Terjadinya fenomena *Instruction Reordering* oleh CPU/Kompiler. Thread lain dapat melihat referensi objek yang sudah dialokasikan di memori tetapi konstruktor objek tersebut belum selesai dieksekusi secara utuh (*partially initialized object*).

##### Q3: Bagaimana fitur *First-Class Functions* pada bahasa modern menyederhanakan pola desain *Strategy*?
*A:* Pola *Strategy* tidak lagi membutuhkan pembuatan interface terdedikasi beserta puluhan kelas konkret implementasi yang memperbesar ukuran metadata aplikasi; strategi dapat langsung dioperasikan sebagai lambda, function pointer, atau method reference yang stateless.

##### Q4: Apa perbedaan prinsip antara pola *Decorator* dan pola *Adapter*?
*A:* *Decorator* menambahkan perilaku baru ke objek yang sudah ada tanpa mengubah antarmukanya (*interface identical*), sedangkan *Adapter* mengubah atau mengkonversi antarmuka suatu objek menjadi antarmuka lain yang diharapkan oleh klien.

##### Q5: Mengapa pola *Flyweight* sangat kritikal dalam arsitektur berorientasi penghematan memori?
*A:* Karena *Flyweight* memisahkan state internal (*intrinsic/immutable state* yang dapat dipakai bersama) dari state eksternal (*extrinsic/contextual state*), secara masif memangkas duplikasi objek yang serupa di heap.

---

#### 15.2. Pertanyaan Intermediate

##### Q6: Pada implementasi pola *State*, bagaimana cara memastikan transisi antar state aman secara konkuren tanpa mengunci (*lock*) seluruh instance objek?
*A:* Menggunakan primitif atomik seperti *Compare-And-Swap (CAS)* melalui `AtomicReference` atau `VarHandle`. Transisi dilakukan hanya jika state saat ini sesuai dengan state yang diharapkan (`expected`), dan melakukan backoff atau retry loop jika terjadi tabrakan antar thread.

##### Q7: Mengapa pendekatan *Sealed Interfaces* dengan *Pattern Matching* sering dianggap melanggar prinsip *Open-Closed Principle (OCP)* klasik, namun justru lebih disukai dalam domain engine modern?
*A:* Sealed interfaces membatasi penambahan varian tipe baru di luar package/modul yang telah ditentukan (*closed for extension*), sehingga melanggar OCP murni. Namun, pendekatan ini menjamin *type exhaustiveness* di tingkat kompilasi, mengeliminasi runtime type check error, dan memungkinkan optimasi jump table monomorfik yang jauh lebih efisien.

##### Q8: Bagaimana cara mengatasi masalah *Backpressure* yang terjadi pada pola *Observer* klasik ketika Publisher memproduksi data jauh lebih cepat daripada kemampuan Consumer?
*A:* Mengganti Observer pasif dengan Reactive Streams protocol (spesifikasi Flow API) yang menyertakan mekanisme sinyal *request(n)* dari Subscriber ke Publisher, atau menggunakan *Bounded Ring Buffer* dengan kebijakan drop terdefinisi (misal: *drop oldest* atau *drop latest*).

##### Q9: Apa dampak dari fenomena *False Sharing* pada aplikasi multi-threaded yang mengimplementasikan shared State Machine, dan bagaimana solusinya?
*A:* *False sharing* terjadi ketika variabel independen yang dimodifikasi oleh core CPU yang berbeda berada di dalam *CPU Cache Line* yang sama (biasanya 64 bytes), memaksa cache invalidation terus menerus. Solusinya adalah dengan menerapkan *cache-line padding* (misal via `@jdk.internal.vm.annotation.Contended` di Java) agar state variabel menempati cache line terisolasi.

##### Q10: Bagaimana pola *Chain of Responsibility* modern dapat diimplementasikan tanpa menimbulkan alokasi memori objek konteks request pada setiap rantai?
*A:* Menggunakan komposisi fungsi murni fungsional (`Function.andThen()`) di mana konteks dilewatkan sebagai reference primitive atau mutable struct terpadu yang telah dialokasikan sebelumnya (*pre-allocated thread-local scratchpad*), alih-alih membuat wrapper object baru di setiap interceptor step.

---

#### 15.3. Skenario Kasus Produksi

##### Skenario A: Deadlock Transaksional Rekursif pada Payment Orchestrator
Sebuah sistem agregator pembayaran menggunakan pola *Mediator* untuk mengoordinasikan pola *State* dari akun pengguna dan akun merchant. Setiap transaksi membungkus mutasi dengan `synchronized(userAccount)` lalu `synchronized(merchantAccount)`. Di bawah beban tinggi, terjadi *thread starvation* dan sistem membeku total (*deadlock*).
* **Pertanyaan:** Mengapa arsitektur ini memicu deadlock dan bagaimana rekayasa ulang pola desain untuk mengeliminasinya secara permanen?
* **Analisis & Solusi:**
  1. *Akar Masalah:* Terjadi *lock acquisition ordering inverted*. Ketika Transaksi 1 mengunci Akun A lalu mencoba mengunci Akun B, secara bersamaan Transaksi 2 (reverse flow seperti refund/transfer balik) mengunci Akun B lalu mencoba mengunci Akun A.
  2. *Solusi Desain:*
     * Terapkan **Deterministic Resource Ordering**: Urutkan akun berdasarkan identifier unik secara leksikografis sebelum mengambil lock (selalu kunci akun dengan ID lebih kecil terlebih dahulu).
     * Atau ganti sepenuhnya dengan **Actor Pattern / Single-Threaded Event Loop per Account Partition** menggunakan antrean pesan, sehingga tidak ada lock yang saling bersilangan antar thread (*Share nothing architecture*).

##### Skenario B: Latensi Spike p99 Akibat Naive Object Pooling
Sebuah gateway microservice memproses jutaan pesan JSON berukuran 2KB. Untuk "mengurangi alokasi memori", arsitek menerapkan pola *Object Pool (GoF)* menggunakan library pool thread-safe generik untuk buffer penampung byte data. Namun, metrik profiling menunjukkan latensi p99 justru melonjak drastis saat beban request naik dari 10.000 RPS ke 80.000 RPS.
* **Pertanyaan:** Apa yang menyebabkan penurunan performa akibat penggunaan Object Pool tersebut, dan bagaimana arsitektur yang benar untuk kasus ini?
* **Analisis & Solusi:**
  1. *Akar Masalah:* Object Pool generik mengandalkan synchronization lock atau shared CAS queue internal untuk operasi peminjaman (`borrow`) dan pengembalian (`return`). Pada beban 80.000 RPS, ratusan thread berebut memperebutkan lock internal pool yang sama (*lock contention*), menyebabkan biaya thread descheduling dan context switching jauh lebih mahal daripada alokasi objek kecil di heap modern JVM TLAB (*Thread-Local Allocation Buffer*).
  2. *Solusi Desain:*
     * Hapus Object Pool untuk objek-objek kecil berumur pendek; biarkan mekanisme TLAB pada modern garbage collector (ZGC/Shenandoah) bekerja secara optimal.
     * Jika buffer pooling mutlak dibutuhkan (misal *Direct Byte Buffers* untuk I/O off-heap), gunakan **Thread-Local Pooling** di mana setiap thread memiliki pool eksklusif tanpa kebutuhan sinkronisasi antar-thread sama sekali.

##### Skenario C: Audit Logging Merusak Throughput Pipeline
Sebuah sistem transaksi core banking mengimplementasikan pola *Decorator* untuk menyuntikkan audit logging ke penyimpanan database pada setiap panggilan method `executeTransaction()`. Ketika database audit mengalami lonjakan latensi (dari 2ms ke 200ms), kapasitas seluruh core banking system langsung kolaps dan memicu timeout masif pada klien.
* **Pertanyaan:** Pelanggaran prinsip arsitektur apa yang terjadi di sini, dan bagaimana mengubah implementasi pola Decorator agar kebal terhadap degradasi performa eksternal?
* **Analisis & Solusi:**
  1. *Akar Masalah:* Pola Decorator diimplementasikan secara **sinkron di dalam synchronous hot-path execution**. Kegagalan atau perlambatan pada salah satu lapisan interceptor mendegradasi seluruh rantai (*Failure Cascading*).
  2. *Solusi Desain:*
     * Pisahkan pipeline transaksional inti dari audit pipeline dengan pola **Observer Asinkron berbasis Ring Buffer (Disruptor)**.
     * Interceptor Decorator hanya bertugas meletakkan payload event audit ke memori circular queue lock-free secara instan (nanodetik).
     * Thread worker independen (*I/O Consumer Worker*) membaca dari buffer tersebut dan mem-batch data ke database audit secara asinkron. Jika database audit down, buffer mengaplikasikan strategi isolasi fail-safe (misal *spillover to disk log*) tanpa menghentikan pemrosesan transaksi utama.

---

### 16. Summary

1. **Modern GoF Architecture** menuntut pergeseran dari sekadar kepatuhan hierarki OOP menjadi keselarasan terhadap performa arsitektur perangkat keras modern (*Hardware Sympathy*).
2. Overhead GoF klasik berakar dari *Dynamic Dispatch (vtable indirection)*, fragmentasi memori heap, dan *lock contention* pada shared mutable states.
3. Fitur bahasa modern—termasuk *Sealed Interfaces*, *Pattern Matching*, *Pure Functions*, dan *Primitive Records*—memungkinkan implementasi pola GoF klasik secara lebih ringkas, aman pada saat kompilasi, dan memiliki alokasi memori mendekati nol (*zero-allocation hot path*).
4. Penanganan concurrency tingkat lanjut pada pola *State*, *Observer*, dan *Pipeline* harus meninggalkan *blocking locks* konvensional dan beralih ke struktur *CAS-driven lock-free*, *Thread-Confined State*, atau *Asynchronous Non-Blocking Ring Buffers*.
5. Kematangan seorang System Architect terbukti dari kemampuannya menimbang *trade-offs*: kapan harus mempertahankan fleksibilitas extensible ala GoF klasik, dan kapan harus mengorbankan OCP kaku demi mencapai determinisme latensi sub-milidetik di sistem produksi berkapasitas tinggi.