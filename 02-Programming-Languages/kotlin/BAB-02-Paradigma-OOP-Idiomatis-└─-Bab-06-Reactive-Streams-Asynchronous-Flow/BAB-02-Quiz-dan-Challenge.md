# BAB 02: Quiz, Challenge, & Knowledge Check
**Paradigma OOP Idiomatis di Kotlin**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Backing Field vs Backing Property
Jelaskan secara mendalam perbedaan antara *Backing Field* (penggunaan identifier `field`) dan *Backing Property* (pola konvensi private/public property seperti `_data` dan `data`). Dalam kondisi bytecode seperti apa compiler Kotlin memutuskan untuk **tidak** meng-generate backing field fisik untuk sebuah `val` atau `var`, dan apa implikasi memorinya?

### Soal 1.2: Siklus Eksekusi Inisialisasi Objek
Analisis urutan eksekusi konstruksi objek berikut: *primary constructor parameter evaluation*, *property initializer*, *`init` block*, dan *secondary constructor body*. Jika sebuah kelas induk (`open class Base`) memiliki `init` block dan kelas turunan (`class Derived : Base()`) juga memiliki `init` block serta *secondary constructor*, jelaskan urutan deterministik eksekusinya dari perspektif JVM runtime.

### Soal 1.3: Class Delegation vs Interface Inheritance
Kotlin menyediakan native class delegation via keyword `by` (misal: `class Service(db: Database) : Database by db`). Bagaimana compiler Kotlin mengompilasi konstruksi ini ke dalam bytecode JVM? Jelaskan keunggulan arsitektural mekanisme ini dibandingkan pendekatan pewarisan kelas konvensional (*subclassing*) dalam kaitannya dengan prinsip *Composition over Inheritance* dan isu *fragile base class*.

### Soal 1.4: Semantik Struktural dan Batasan Data Class
Data class meng-generate `equals()`, `hashCode()`, `toString()`, `componentN()`, dan `copy()`. 
1. Mengapa compiler melarang deklarasi `open`, `abstract`, `sealed`, atau `inner` pada sebuah `data class`?
2. Bagaimana implementasi generated `equals()` dan `hashCode()` menangani property bertipe `Array<T>` dibanding `List<T>`, dan mengapa penggunaan `Array` di primary constructor data class dianggap sebagai code smell fatal?

### Soal 1.5: Object Declaration, Companion Object, dan Thread Safety
Jelaskan bagaimana JVM menginisialisasi `object` (singleton) dan `companion object` di Kotlin. Kapankah inisialisasi tersebut terjadi (eager vs lazy), bagaimana garansi *thread safety* dipenuhi tanpa keyword `synchronized` eksplisit pada deklarasi kelas, dan apa dampak penggunaan anotasi `@JvmStatic` serta `@JvmField` terhadap bytecode yang dihasilkan?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Memory Footprint & Escape Analysis pada `@JvmInline value class`
Diberikan deklarasi:
```kotlin
@JvmInline value class AccountId(val raw: Long)
```
Identifikasi 4 (empat) kondisi di mana runtime JVM terpaksa melakukan *boxing* (mengalokasikan objek baru pada managed heap) terhadap instance `AccountId` tersebut alih-alih mempertahankan representasi primitif `long`. Bagaimana *escape analysis* dan batasan generic type erasure di JVM memicu overhead ini?

### Soal 2.2: The Leaking `this` Initialization Trap
Perhatikan kode berikut:
```kotlin
open class BaseProcessor {
    open val bufferSize: Int = 1024
    init {
        allocateBuffer(bufferSize)
    }
    open fun allocateBuffer(size: Int) {
        println("Base allocating: $size")
    }
}

class CustomProcessor(override val bufferSize: Int = 4096) : BaseProcessor() {
    override fun allocateBuffer(size: Int) {
        println("Custom allocating: $size, verify property: $bufferSize")
    }
}
```
Ketika `CustomProcessor()` diinstansiasi:
1. Mengapa output mencetak `verify property: 0` dan bukan `4096` atau `1024`?
2. Bedah eksekusi bytecode yang menyebabkan *memory uninitialized state* ini, dan jelaskan mengapa compiler Kotlin mengeluarkan peringatan terhadap pemanggilan *overridable member* di dalam `init` block.

### Soal 2.3: Resolusi Ambigu Diamond Problem pada Multi-Interface Implementation
Sebuah kelas mengimplementasikan dua interface dengan method signature identik:
```kotlin
interface Reader {
    fun close(): Unit = println("Closing Reader")
}

interface Channel {
    fun close(): Unit = println("Closing Channel")
}

class BytePipe : Reader, Channel {
    override fun close() {
        // Explicit resolution
    }
}
```
Tuliskan sintaks idiomatik Kotlin untuk mengeksekusi kedua implementasi default tersebut di dalam `BytePipe.close()`. Jelaskan bagaimana *invokespecial* dan *default method* metadata di level JVM bytecode (`InterfaceName.DefaultImpls` vs Java 8+ interface default methods) menyelesaikan ambiguitas dispatch ini.

### Soal 2.4: Property Delegation Lifecycle & Overhead Metadata
Pada custom property delegate:
```kotlin
class MonitoredState<T>(private var value: T) : ReadWriteProperty<Any?, T> {
    override fun getValue(thisRef: Any?, property: KProperty<*>): T = value
    override fun setValue(thisRef: Any?, property: KProperty<*>, value: T) {
        this.value = value
    }
}
```
1. Objek apa yang di-generate compiler di belakang layar untuk parameter `property: KProperty<*>`?
2. Dalam sistem dengan ribuan instansiasi kelas per detik, dampak memory overhead apa yang ditimbulkan oleh static/instance backing metadata reflection tersebut (`KProperty` array allocation)?
3. Bagaimana Kotlin mengoptimalkan ini pada kasus delegated properties lokal (*local delegated properties*)?

### Soal 2.5: Sealed Class/Interface vs Enum State Exhaustiveness Bytecode
Bandingkan implementasi antara `enum class State` dengan `sealed interface State`:
1. Bagaimana compiler Kotlin memetakan statement `when (state)` yang exhaustif ke dalam bytecode? Bedakan penggunaan instruksi `TABLESWITCH` / `LOOKUPSWITCH` vs cascading `instanceof` (`checkcast`).
2. Kapan penggunaan `sealed interface` memberikan keunggulan performa garbage collection (GC) dibandingkan `sealed class` konvensional?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Degradasi Throughput & GC Pressure Akibat Immutability Anti-Pattern
* **Latar Belakang Kasus:**
  Sebuah microservice analitik finansial memproses event stream Kafka dengan throughput 80.000 events/detik. Sistem menggunakan event-sourcing berbasis immutable data class:
  ```kotlin
  data class OrderBookSnapshot(
      val orderId: String,
      val asks: Map<BigDecimal, Volume>,
      val bids: Map<BigDecimal, Volume>,
      val lastAuditTimestamp: Instant
  )
  ```
  Setiap pembaruan harga mengeksekusi method `.copy()` pada `OrderBookSnapshot` untuk memperbarui salah satu entri map.
* **Gejala / Insiden:**
  JVM mengalami *latency spike* periodic sebesar 2.5 detik (Stop-The-World Young Generation GC pauses). Monitoring heap profiler menunjukkanjutaan instansiasi `OrderBookSnapshot` dan entry map sementara per detik, yang dengan cepat memicu *early object tenuring* ke Old Gen.
* **Pertanyaan Diagnostik:**
  1. Identifikasi secara struktural mengapa paradigma immutability naïf via `data class.copy()` pada struktur data kompleks (seperti nested map) menjadi anti-pattern dalam konteks high-frequency mutations.
  2. Rancang ulang arsitektur OOP domain ini menggunakan kombinasi idiomatis Kotlin (misalnya: *persistent data structures*, *encapsulated mutable backing properties with read-only views*, atau *structural sharing*) tanpa mengorbankan integritas encapsulasi state dan thread safety.

---

### Skenario B: Race Condition pada Concurrency State via Custom Getter Non-Idempotent
* **Latar Belakang Kasus:**
  Sebuah modul otorisasi core banking memiliki representasi entitas pengguna:
  ```kotlin
  class SecuritySession(private val tokenStore: TokenStore) {
      val isSessionActive: Boolean
          get() = tokenStore.fetchToken()?.let { !it.isExpired() && !it.isRevoked() } ?: false
  }
  ```
  Modul transaksi memvalidasi sesi dan kemudian mengeksekusi operasi finansial:
  ```kotlin
  if (session.isSessionActive) {
      // Thread context-switch terjadi di sini
      paymentGateway.charge(session.tokenStore.getCurrentTokenId(), amount)
  }
  ```
* **Gejala / Insiden:**
  Terjadi insiden fraud di mana transaksi bernilai tinggi berhasil diproses meskipun token telah di-revoke 2 millisecond sebelumnya di thread lain. Audit log menunjukkan bahwa `tokenStore.getCurrentTokenId()` melempar `NullPointerException` atau mengembalikan token id invalid yang lolos dari validasi awal. Developer mengira bahwa `isSessionActive` adalah `val` yang menyimpan state statis, bukan sebuah dynamic computed getter.
* **Pertanyaan Diagnostik:**
  1. Mengapa sintaks `val` pada custom getter di Kotlin memberikan ilusi *immutability* yang menipu (*semantic pitfall*), dan bagaimana compiler memperlakukan `val` dengan custom getter di level JVM byte code?
  2. Rekonstruksi arsitektur kelas ini agar mengikuti prinsip *Parse, Don't Validate* menggunakan Kotlin *Sealed Hierarchies* atau *Atomic State Snapshots*, sehingga race condition TOCTOU (*Time-of-Check to Time-of-Use*) tereliminasi secara struktural di compile-time.

---

### Skenario C: Arsitektur Migrasi dari Deep Java Inheritance ke Idiomatic Kotlin Composition
* **Latar Belakang Kasus:**
  Sebuah sistem ERP enterprise warisan Java memiliki arsitektur hierarki inheritance 6 level untuk proses transaksi gudang:
  `Object -> BaseEntity -> AuditableEntity -> Document -> FinancialDocument -> InventoryTransferDocument`.
  Setiap level mewarisi puluhan field mutable dan mengeksekusi method `super.save()`, `super.validate()`, dan `super.calculateTax()`.
  Ketika kode dikonversi secara mekanis oleh Java-to-Kotlin converter (J2K), muncul ratusan baris kode dengan `open class`, mutabilitas berlebih (`var`), nullable properties akibat inisialisasi bertahap, dan dependensi sirkular pada lifecycle hook.
* **Pertanyaan Diagnostik:**
  1. Uraikan analisis Anda mengenai kelemahan arsitektural dari hierarki deep inheritance di atas dalam konteks *maintainability*, *testability*, dan *cognitive load*.
  2. Transformasikan model domain tersebut ke dalam Kotlin idiomatis enterprise menggunakan prinsip:
     * **Sealed Interface** untuk state lifecycle document (`Draft`, `Approved`, `Transferred`, `Cancelled`).
     * **Class Delegation (`by`)** untuk auditing dan financial ledger persistence capabilities.
     * **Inline Value Classes** untuk id entity type-safety (`DocumentId`, `WarehouseId`).
  3. Jelaskan trade-off performa runtime JVM dan fleksibilitas arsitektur antara arsitektur Java legacy vs arsitektur Kotlin idiomatis yang Anda usulkan.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Domain-Driven Event Ledger Engine
**Domain:** Financial Core Banking Transaction Processor  
**Objective:** Mengembangkan domain model core banking yang 100% type-safe, immutably secure, zero-allocation di hot-path transaksi, dan menerapkan seluruh paradigma idiomatis Kotlin OOP (Value Classes, Sealed Interfaces, Delegation, Custom Property Delegate, dan Structural Encapsulation).

#### Deskripsi Masalah
Anda diminta membangun mesin pemrosesan mutasi akun (*Account Ledger Engine*). Mesin ini bertugas memvalidasi, menerapkan transaksi debit/kredit, mencatat jejak audit secara otomatis, dan mendeteksi anomali mutasi tanpa menggunakan framework eksternal (pure Kotlin SE).

#### Kebutuhan Fungsional & OOP Requirements
1. **Type-Safe Primitives (Zero-Boxing Constraint):**
   * Gunakan `@JvmInline value class` untuk `AccountId` (berbasis `String`), `TransactionId` (berbasis `UUID`), dan `MonetaryAmount` (berbasis `Long`, merepresentasikan unit cent/sen untuk menghindari floating point issues).
2. **State Modeling via Sealed Hierarchies:**
   * Representasikan siklus hidup akun (`AccountStatus`) menggunakan `sealed interface`:
     * `Unverified`
     * `Active(val creditLimit: MonetaryAmount)`
     * `Frozen(val reason: String, val frozenAt: Instant)`
     * `Closed`
   * Representasikan tipe transaksi (`TransactionType`) menggunakan `sealed class`:
     * `Deposit`
     * `Withdrawal`
     * `Transfer(val targetAccount: AccountId)`
3. **Class Delegation untuk Auditability:**
   * Definisikan interface `Auditable`:
     ```kotlin
     interface Auditable {
         fun recordEvent(event: String)
         fun getAuditHistory(): List<String>
     }
     ```
   * Buat implementasi konkrit `InMemoryAuditTrail : Auditable`.
   * Kelas domain `Account` harus mengimplementasikan `Auditable` **bukan** lewat subclassing, melainkan melalui **Class Delegation** (`by`).
4. **Custom Property Delegation (State Change Observer):**
   * Implementasikan property delegate `VetoableState<T>` yang memverifikasi apakah status akun valid untuk transisi state tertentu (misal: dilarang berpindah dari `Closed` ke `Active`). Jika tidak valid, throw exception domain `IllegalStateTransitionException`.
5. **Backing Properties & Deep Encapsulation:**
   * Mutasi ledger akun disimpan dalam list internal privat `_transactions: MutableList<Transaction>`.
   * Ekspos mutasi tersebut ke publik hanya sebagai immutable read-only view: `val transactions: List<Transaction>`.
6. **Polymorphic Exhaustive Business Rule Enforcement:**
   * Buat sebuah fungsi dispatch transaksi idiomatis:
     ```kotlin
     fun applyTransaction(account: Account, tx: Transaction): Account
     ```
   * Wajib memanfaatkan compiler check exhaustive `when` tanpa klausul `else`.

#### Constraints Teknis
* **Zero Reflection:** Tidak boleh menggunakan `kotlin.reflect.*` runtime calls untuk auditing atau clone objek.
* **No Leaking Mutability:** Tidak boleh ada internal state yang dapat dimutasi dari luar batas enkapsulasi kelas.
* **Boxing Elimination:** Operasi verifikasi saldo dan debit/kredit pada `MonetaryAmount` di dalam domain logic hot-path tidak boleh menyebabkan boxing (pastikan method `plus`, `minus`, `compareTo` diimplementasikan secara optimal pada value class).

#### Expected Output
Dokumentasi kode lengkap dalam satu berkas terstruktur rapi yang berisi:
1. Deklarasi Value Classes lengkap dengan operator functions (`+`, `-`, perbandingan).
2. Deklarasi hirarki Sealed Interface/Class.
3. Implementasi Custom Property Delegate `VetoableState`.
4. Implementasi kelas `Account` yang mengintegrasikan delegasi `Auditable` dan backing properties.
5. Fungsi eksekusi transaksi yang menangani exhaustive branch logic.
6. Test driver class (dalam method `main()`) yang membuktikan eksekusi:
   * Berhasil memproses Deposit dan Withdrawal.
   * Gagal saat mencoba menarik dana melebihi credit limit (Domain rejection).
   * Gagal saat mencoba memutasikan akun yang berada dalam state `Frozen`.
   * Cetak histori audit yang membuktikan fungsi delegasi berjalan secara transparan.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Mekanisme exact bagaimana compiler mentranslasi primary constructor, secondary constructor, default arguments, dan `init` blocks ke dalam satu atau beberapa overloading bytecode constructors `<init>`.
- [ ] Perbedaan internal backing field bytecode vs non-backing field properties (computed getters).
- [ ] Bagaimana Kotlin mengimplementasikan Class Delegation via internal synthetic bridge fields dan dampaknya terhadap memori serta performa dispatch method.
- [ ] Kenapa `equals()` dan `hashCode()` pada `data class` hanya mengevaluasi properties yang dideklarasikan di *primary constructor*, serta bahaya menyertakan mutable reference di dalamnya.
- [ ] Batasan konseptual dan runtime JVM terhadap `@JvmInline value class` (type-erasure, boxing triggers saat cast ke interface/Any, batasan init blocks).
- [ ] Struktur compiler mapping `sealed class` dan `sealed interface` pada JVM (seperti metadata `PermittedSubclasses` pada Java 15/17+ target bytecode).
- [ ] Pola inisialisasi `companion object` dan `object` deklarasi di level class-loader JVM (Thread-safe singleton via static initialization block `<clinit>`).

### Saya tidak perlu menghafal:
- [ ] Nama synthetic methods spesifik compiler yang berubah antar-versi (misal: penamaan exact `$default` method flags untuk default parameters).
- [ ] Bytecode offsets / opcode numerical values hexadesimal dari instruksi JVM (`invokevirtual` vs `invokeinterface`).
- [ ] Implementasi internal string hashing library untuk property name resolution pada `KProperty` generation.

### Saya harus bisa melakukan:
- [ ] Mengaudit kode Kotlin untuk mendeteksi *initialization leakage* (mengakses open property/function dari constructor parent).
- [ ] Mendesain hierarki domain state yang exhaustive menggunakan `sealed interface` sehingga mengeliminasi defensive code (`else -> unreachable()`).
- [ ] Mengganti struktur pewarisan inheritance klasik yang rapuh (*fragile base class*) menjadi modular composable components menggunakan class delegation `by`.
- [ ] Mengonfigurasi dan mengimplementasikan custom property delegates (`ReadOnlyProperty` / `ReadWriteProperty`) yang aman terhadap thread concurrency dan memory-leak free.
- [ ] Menginspeksi decompiled Java/bytecode dari Kotlin via IntelliJ IDEA untuk memverifikasi apakah `@JvmInline value class` benar-benar ter-inlined secara unboxed di CPU stack memory.
- [ ] Mengamankan enkapsulasi data dengan pola explicit backing properties (`_items` mutable vs `items` immutable collection view).