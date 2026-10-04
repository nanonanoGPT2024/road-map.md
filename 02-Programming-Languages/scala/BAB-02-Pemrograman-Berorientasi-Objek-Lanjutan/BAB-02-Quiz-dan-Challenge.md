# BAB 02: Quiz, Challenge, & Knowledge Check
**Pemrograman Berorientasi Objek Lanjutan**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Algoritma Linearization dan Resolusi Diamond Problem
Jelaskan secara mendalam bagaimana compiler Scala menyelesaikan *Diamond Problem* pada *multiple trait inheritance* menggunakan algoritma **Trait Linearization**. 
* Diberikan relasi: `class D extends A with B with C`. Bagaimanakah urutan evaluasi pemanggilan `super`? 
* Mengapa algoritma ini bersifat deterministik dibandingkan dengan *multiple inheritance* tradisional pada C++?

### Soal 1.2: Mekanika Variance Annotations dan Type Bounds
Pada sistem tipe Scala, jelaskan perbedaan mendasar antara **Covariance (`+T`)**, **Contravariance (`-T`)**, dan **Invariance (`T`)**.
* Mengapa sebuah tipe parameter kovarian tidak diizinkan berada pada posisi parameter metode (*contravariant position*)?
* Bagaimana teknik **Lower Type Bound (`[U >: T]`)** menyelesaikan pembatasan tersebut secara elegan tanpa melanggar prinsip *Liskov Substitution Principle (LSP)*?

### Soal 1.3: Self-Type Annotations vs. Subtyping Inheritance
Jelaskan perbedaan semantik, siklus kompilasi, dan arsitektural antara:
```scala
trait ComponentB { this: ComponentA => ... }
```
dengan:
```scala
trait ComponentB extends ComponentA { ... }
```
Kapan seorang Software Architect harus memilih *Self-Type* dibanding *Subclassing*, khususnya dalam kaitannya dengan siklus hidup dependensi (*circular dependency*) dan kebocoran API surface (*leaky abstraction*)?

### Soal 1.4: Semantik dan Batasan Universal Traits serta Value Classes
Scala menyediakan optimasi alokasi heap via `extends AnyVal` (*Value Classes*). 
* Jelaskan bagaimana compiler merepresentasikan *Value Class* pada level Java Bytecode untuk menghindari alokasi memori heap.
* Sebutkan 3 skenario mutlak di mana compiler Scala terpaksa melakukan proses *boxing* (mengalokasikan objek baru pada heap) meskipun tipe tersebut didefinisikan sebagai *Value Class*!

### Soal 1.5: Desain Aljabar Data: Sealed Hierarchies vs. Scala 3 Enums
Bandingkan arsitektur `sealed trait` + `case object/class` pada Scala 2 dengan konstruksi `enum` pada Scala 3.
* Bagaimana compiler mengimplementasikan validasi kelengkapan (*exhaustiveness checking*) saat *pattern matching* dilakukan?
* Apa perbedaan representasi *bytecode* yang dihasilkan oleh keduanya, dan bagaimana implikasinya terhadap *binary compatibility* serta *class loading overhead*?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Debugging Inisialisasi State Trait dan Order-of-Initialization NullPointer
Perhatikan cuplikan kode Scala berikut yang melempar `NullPointerException` saat runtime:

```scala
trait BaseMetrics {
  val serviceName: String
  val metricKey: String = s"metrics.$serviceName"
}

class PaymentService extends BaseMetrics {
  val serviceName: String = "payment-gateway"
}

// Runtime Execution:
// val service = new PaymentService
// println(service.metricKey) // Output: metrics.null
```

* Jelaskan secara teknis urutan inisialisasi *bytecode* JVM yang menyebabkan `service.metricKey` bernilai `"metrics.null"`.
* Bandingkan 3 strategi untuk memitigasi isu ini: penggunaan `lazy val`, `def`, dan pendekatan Scala 3 *Trait Parameters*.

### Soal 2.2: JVM Call-Site Inlining dan Megamorphism pada Linearized Traits
Bagaimana struktur hierarki *trait* yang sangat dalam (misalnya: pewarisan berlapis 7 tingkat dengan `super.execute()` chaining) mempengaruhi kinerja JVM Just-In-Time (JIT) Compiler?
* Jelaskan dampaknya terhadap *monomorphic*, *bimorphic*, dan *megamorphic call-site inline caching*.
* Kapan penggunaan *deep trait composition* berubah dari pola desain modular menjadi *bottleneck throughput* pada aplikasi berlatensi rendah (*low-latency*)?

### Soal 2.3: Isolasi Konteks dengan Path-Dependent Types
Diberikan kode arsitektur enkapsulasi berikut:

```scala
class DatabaseEngine {
  trait Session { def execute(sql: String): Unit }
  def createSession(): Session = new Session { def execute(sql: String) = () }
  def runMigration(session: Session): Unit = session.execute("MIGRATE")
}

val primaryDb = new DatabaseEngine
val replicaDb = new DatabaseEngine
val primarySession = primaryDb.createSession()
```

* Mengapa ekspresi `replicaDb.runMigration(primarySession)` gagal dikompilasi oleh compiler Scala?
* Jelaskan bagaimana *Path-Dependent Types* menjamin *compile-time safety* terhadap kebocoran referensi antar-entitas dan bagaimana memintasnya secara legal menggunakan *type projection* (`DatabaseEngine#Session`) jika integrasi cross-instance diperlukan.

### Soal 2.4: Broken Equality Contract pada Pewarisan State
Dalam implementasi POJO/OO konvensional, penambahan field pada subkelas sering merusak kontrak simetris `equals` (`a.equals(b) == b.equals(a)`).
* Bagaimana method `canEqual` dari trait `scala.Equals` menyelesaikan anomali transitivitas dan simetri saat membandingkan instans dari kelas induk dan subkelas?
* Buatlah skema diagnosa kode jika terjadi *infinite recursion* (*StackOverflowError*) pada implementasi kustom `canEqual`, `equals`, dan `hashCode`.

### Soal 2.5: Array Invariance vs. Covariance Safety
Bahasa Java mengizinkan array kovarian (`String[]` adalah subtipe dari `Object[]`), yang membuka peluang runtime `ArrayStoreException`. 
* Bagaimana Scala mengoreksi hal ini pada level *type-checker*?
* Jelaskan peran modul `scala.reflect.ClassTag` dalam mengatasi batasan *type erasure* JVM saat mengalokasikan array bertipe generik `Array[T]`.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck GC Akibat Boxing pada Hot-Path Pipeline FinTech
* **Latar Belakang:** Sebuah microservice pemrosesan transaksi berkecepatan tinggi (*high-frequency trading engine*) memproses 120.000 transaksi/detik. Sistem menggunakan arsitektur *Value Class* untuk membungkus identifier:
  ```scala
  case class AccountId(value: Long) extends AnyVal
  case class TransactionId(value: Long) extends AnyVal
  ```
* **Masalah:** Tim *Infrastructure* mendeteksi peningkatan drastis pada frekuensi *Minor GC* dan lonjakan latensi p99 dari 2ms melonjak ke 45ms. Setelah dianalisis menggunakan *Java Flight Recorder (JFR)*, jutaan alokasi instans `AccountId` terdeteksi di memori heap, padahal tipe tersebut adalah *Value Class*.
* **Pertanyaan Diagnostik:**
  1. Identifikasi 3 konstruksi kode idiomatik Scala yang memicu JVM melakukan *boxing* instans `AnyVal` ke heap tanpa peringatan compiler (*silent performance degradation*), khususnya dalam operasi koleksi standar atau generic interfaces.
  2. Bagaimana Anda merefaktor kode domain ini menggunakan fitur **Opaque Type Aliases** (Scala 3) untuk menjamin alokasi zero-overhead secara mutlak tanpa resiko boxing di level runtime?

### Skenario B: Race Condition dan Deadlock pada Lazy Val Initialization
* **Latar Belakang:** Sebuah sistem distributed orchestration berbasis Akka/Pekko memuat konfigurasi dependensi modul menggunakan pola *Cake Pattern / Complex Trait Mixing* yang memanfaatkan `lazy val` singleton:
  ```scala
  trait SecurityModule { lazy val tokenValidator = new HeavyValidator() }
  trait DatabaseModule { lazy val connectionPool = new HeavyPool() }
  object SystemContext extends SecurityModule with DatabaseModule
  ```
* **Masalah:** Saat deployment ke multi-core production server (64 vCPU), sistem mengalami *hang* total saat proses *cold start*. Analisis *thread dump* menunjukkan kondisi deadlock di antara dua thread internal JVM:
  * Thread-1: `waiting to lock <0x...SystemContext$> at SecurityModule.$init$`
  * Thread-2: `waiting to lock <0x...SystemContext$> at DatabaseModule.$init$`
* **Pertanyaan Diagnostik:**
  1. Bedah mekanisme sinkronisasi internal (*locking mechanism*) yang di-generate oleh compiler Scala untuk inisialisasi `lazy val` pada Scala 2.x vs Scala 3.x (*thread-safe lazy initialization map* vs *SIP-20*).
  2. Bagaimana rekonstruksi arsitektural yang harus diterapkan untuk menghilangkan *circular initialization dependency* ini tanpa mengorbankan keamanan inisialisasi *thread-safe*?

### Skenario C: Trade-off Arsitektural Framework Enterprise Event-Sourcing
* **Latar Belakang:** Anda bertindak sebagai *Principal Enterprise Architect* yang sedang merancang framework *Event-Sourcing core* yang digunakan oleh puluhan tim produk di seluruh organisasi. Terdapat perdebatan teknis antara dua paradigma arsitektur untuk *Domain Event Processing*:
  * **Pendekatan 1 (Pure OOP/Subtyping):** Hierarki *Sealed Traits* berbasis kelas, variance bounds, inheritance-driven pipeline (`trait EventHandler[-E <: Event]`).
  * **Pendekatan 2 (Functional / Type Class Pattern):** Invariant traits berparameter konteks implisit (`trait EventHandler[E]`).
* **Pertanyaan Diagnostik:**
  1. Analisis *trade-off* mendalam dari kedua pendekatan tersebut ditinjau dari:
     * *Binary Compatibility* (kemudahan modifikasi model tanpa memecah konsumen framework).
     * *Extensibility* (kemudahan developer pihak ketiga menambahkan *Event Handler* baru secara modular).
     * Efisiensi memori runtime dan kemudahan *debugging* stack trace bagi tim support.
  2. Berikan rekomendasi arsitektur final Anda berserta justifikasi teknis yang paling aplikatif untuk kebutuhan skala enterprise.

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise Multi-Tenant Event Dispatching Core
Bangun sebuah sistem modul pemrosesan data event (*Core Event Bus Pipeline*) multi-tenant strictly-typed dengan performa tinggi yang memanfaatkan konsep-konsep OOP Lanjutan Scala: **Trait Linearization, Contravariance, Self-Type Annotations, dan Path-Dependent Types**.

#### 1. Problem Statement
Sistem perbankan modular membutuhkan *Event Dispatcher Engine* yang aman pada level kompilasi (*compile-time safety*). Dispatcher harus memastikan bahwa:
- Handler event akun bisnis tidak dapat secara tidak sengaja memproses event akun personal (pencegahan kontaminasi lintas tenant).
- Pemrosesan event melewati pipeline standar: *Audit Logging*, *Security Enforcement*, dan *Metrics Tracking* menggunakan trait composition yang tertib dan deterministik.
- Handler yang dideklarasikan untuk menangani event induk (misal: `AuditEvent`) dapat menangani turunan event yang lebih spesifik (misal: `SecurityAuditEvent`) secara otomatis melalui mekanisme *Contravariance*.

#### 2. Functional & Technical Requirements
1. **Tenant Context Isolation (Path-Dependent Types):**
   * Buat class `TenantContext(val tenantId: String)`.
   * Di dalam class ini, definisikan tipe abstrak atau kelas untuk `TenantEvent`. Sebuah event dari tenant `TenantContext("CorpA")` harus berstatus *incompatible type* dengan tenant `TenantContext("CorpB")` pada saat kompilasi.
2. **Contravariant Event Handler:**
   * Definisikan abstraksi `EventHandler[-E]` yang bersifat kontravarian. Tunjukkan bahwa instance `EventHandler[GeneralTenantEvent]` dapat disubstitusikan ke tempat yang membutuhkan `EventHandler[SpecificTenantEvent]`.
3. **Pluggable Pipeline (Trait Linearization & Super-Chaining):**
   * Buat trait dasar `PipelineStage` dengan method `handle(event: String): Unit`.
   * Buat trait interseptor: `MetricsInterceptor`, `AuditLogInterceptor`, dan `SecurityValidationInterceptor`.
   * Susun urutan eksekusi secara deterministik menggunakan pemanggilan `super.handle(...)`.
4. **Dependency Enforcement (Self-Types):**
   * Implementasikan komponen audit database `AuditRepositoryComponent` yang tidak mewarisi (*does not extend*) modul enkripsi, melainkan menuntut keberadaannya melalui *Self-Type* annotation (`this: EncryptionComponent =>`).

#### 3. Constraints
* Bahasa: Scala (Scala 2.13.x atau Scala 3.x).
* Bebas dari alokasi *reflection* (`scala.reflect.*` runtime mirrors dilarang).
* Zero-warning kompilasi dengan flag fatal warnings diaktifkan (`-Xfatal-warnings`).
* Tidak boleh menggunakan library third-party (hanya gunakan Scala Standard Library).

#### 4. Expected Output & Demonstration
Sediakan demonstrasi kode tunggal yang dapat dieksekusi (*runnable script / object main*) yang membuktikan:
* Kode gagal dikompilasi jika *cross-tenant event passing* dicoba (sertakan bukti berupa komentar baris error kompilasi).
* Bukti eksekusi *linearization sequence* pada terminal yang mencerminkan pemanggilan urutan interceptor secara presisi: `Security -> Metrics -> Audit -> Processing`.
* Bukti substitusi kontravarian berhasil dieksekusi tanpa *casting* runtime (`asInstanceOf`).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Aturan resolusi Diamond Problem menggunakan Trait Linearization (kalkulasi topologi dari kanan ke kiri, pembalikan urutan evaluasi).
- [ ] Aturan kompilasi tipe parameter Variance: Mengapa `+T` hanya boleh pada posisi output (*covariant/return position*) dan `-T` hanya pada posisi input (*contravariant/argument position*).
- [ ] Solusi Lower Bound (`[U >: T]`) untuk mempertahankan kovariansi pada struktur data immutabel (seperti method `prepend` pada immutable List).
- [ ] Mekanisme internal *Self-Type Annotations* sebagai teknik *Static Dependency Injection* dan pencegah *circular class-subtyping*.
- [ ] Arsitektur internal Value Classes (`AnyVal`), kondisi eliminasi alokasi heap oleh JVM, dan skenario pemicu runtime boxing.
- [ ] Perbedaan jaminan *Compile-Time Path-Dependent Types* terhadap tipe berbasis dependensi instance objek.
- [ ] Pola implementasi `scala.Equals` dan method `canEqual` untuk mematuhi kontrak relasional simetris dan transitif pada JVM.

### Saya tidak perlu menghafal:
- [ ] Struktur eksak dari *hash seed algorithm* yang digunakan oleh `scala.util.hashing.MurmurHash3` di balik `case class`.
- [ ] Bytecode label offsets dan mnemonic instruction indeks dari JVM saat mengeksekusi invokeinterface/invokevirtual.
- [ ] Urutan flag biner spesifik kompiler untuk aktivasi SIP compiler plugins lama.

### Saya harus bisa melakukan:
- [ ] Mentransformasi class hierarchy yang rentan NPE saat inisialisasi menjadi hierarki yang aman (*thread-safe & deterministic lifecycle*).
- [ ] Mengimplementasikan *Type-Safe Domain Modeling* menggunakan gabungan *Sealed Hierarchies*, *Value Classes / Opaque Types*, dan *Path-Dependent Types*.
- [ ] Melakukan troubleshooting dan profiling memori untuk mendeteksi alokasi heap tak terduga (*hidden boxing allocations*) yang diakibatkan oleh kesalahan representasi tipe generik.
- [ ] Mendesain arsitektur plugin modular perusahaan berbasis *Stacked Trait Pattern* dengan eksekusi `super` chaining yang dapat diprediksi secara matematis.
- [ ] Memperbaiki anomali kompilasi *"covariant type T occurs in contravariant position"* dengan mengaplikasikan *type bounds* yang tepat tanpa mengorbankan integritas abstraksi domain.