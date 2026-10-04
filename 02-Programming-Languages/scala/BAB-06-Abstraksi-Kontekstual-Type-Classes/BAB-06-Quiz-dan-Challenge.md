# BAB 06: Quiz, Challenge, & Knowledge Check
**Abstraksi Kontekstual & Type Classes (Scala 3)**

Dokumen ini dirancang untuk menguji, memvalidasi, dan mengukur kompetensi teknis tingkat lanjut mengenai paradigma abstraksi kontekstual (*Contextual Abstractions*) dan implementasi *Type Classes* di Scala 3. Seluruh materi mengacu pada standar rekayasa perangkat lunak enterprise berbasis *type-level safety*, determinisme kompilasi, dan efisiensi runtime.

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Evolusi Paradigma Implisit
Jelaskan perbedaan mendasar secara filosofis, semantik sintaksis, dan resolusi scope antara mekanisme `implicit` pada Scala 2 dengan kombinasi `given` / `using` pada Scala 3! Mengapa Scala 3 memisahkan *intent* (pemberian data contextual vs konversi tipe implisit)?

### Soal 1.2: Anatomi dan Mekanisme Type Class
Uraikan 4 komponen utama yang menyusun pola *Type Class* murni di Scala 3 (Definisi Interface, *Given Instances*, *Syntax Extensions*, dan *Summoner Method*). Jelaskan keunggulan *Type Class* dibandingkan polimorfisme klasik berbasis *subtyping* (*object-oriented subtyping*) dalam konteks *ad-hoc polymorphism* dan prinsip *Open-Closed Principle*!

### Soal 1.3: Desugaring Context Bounds
Diberikan penulisan signature method berikut:
```scala
def serializePipeline[T: Serializer: Logger](data: T): Array[Byte]
```
Jelaskan bagaimana Scala 3 compiler mendesugar (*desugaring process*) potongan kode di atas menjadi bentuk kanonikal `using` parameters! Bagaimana cara mengakses instance dari *type class* `Logger` di dalam tubuh method tanpa memberikan identifier eksplisit pada parameter?

### Soal 1.4: Semantik dan Arsitektur Context Functions
Scala 3 memperkenalkan tipe *Context Function* (`?=>`). Jelaskan secara matematis dan implementatif apa perbedaan antara fungsi biasa `A => B` dengan `A ?=> B`! Bagaimana compiler mengevaluasi dependensi kontekstual ketika sebuah context function dipassing melintasi batas pemanggilan (*execution boundary*)?

### Soal 1.5: Isolasi Resolusi Scope melalui Import Given
Pada Scala 2, `import mypackage._` mengimpor semua anggota package, termasuk nilai implisit, yang kerap memicu *namespace pollution* dan *implicit conflict*. Bagaimana mekanisme `import mypackage.given` dan `import mypackage.{given TypeClass[?]}` pada Scala 3 mengatasi masalah ini pada tingkat compiler symbol table?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Algoritma Resolusi Ambiguitas dan Specificity Rules
Ketika terdapat dua atau lebih `given` instance yang bertipe kompatibel dalam scope resolusi yang sama, bagaimana compiler menentukan instance mana yang menang (*most specific rule*)? Parameter apa saja yang dievaluasi compiler (misal: relasi subtyping pada tipe target, relasi kelas pembungkus, tipe argumen) sebelum akhirnya melempar error `Ambiguous Given Instances`?

### Soal 2.2: Deteksi dan Mitigasi Diverging Implicit Expansion
Perhatikan kasus pembuatan recursive type class generator (misal: JSON serializer untuk nested case class atau struktur data rekursif seperti linked list / generic trees). Apa akar penyebab compiler melempar error `diverging implicit expansion for type...`? Jelaskan cara compiler mendeteksi siklus resolusi infinite, dan strategi apa yang harus diterapkan untuk memutus rekursi tersebut secara deterministik!

### Soal 2.3: Name Clashes & Precedence pada Extension Methods
Jika sebuah tipe data primitif atau domain class memiliki method anggota instansiasi asli bernama `validate(): Boolean`, dan pada saat yang sama diimport sebuah extension method:
```scala
extension (entity: Order) def validate(): Either[DomainError, Unit]
```
Jelaskan aturan resolusi lookup compiler Scala 3 ketika memanggil `order.validate()`! Bagaimana jika terdapat dua extension method identik yang berasal dari dua trait berbeda yang di-summon ke scope yang sama?

### Soal 2.4: JVM Bytecode Footprint & Erasure Analysis
Secara runtime di JVM:
1. Bagaimana representasi compiled code dari sebuah `given` instance bertipe `given Show[User]`?
2. Bagaimana representasi pemanggilan method `extension (u: User) def audit()` di level bytecode? Apakah alokasi objek pembungkus (*wrapper instance*) terjadi pada runtime heap, ataukah method tersebut dikompilasi menjadi static invocation? Buktikan dampaknya terhadap garbage collection pada throughput ultra-tinggi!

### Soal 2.5: Orphan Instances, Coherence, dan Binary Compatibility
Definisikan konsep *Type Class Coherence* vs *Orphan Instances*. Jika Anda mengembangkan modul core library dan mengizinkan konsumen library mendeklarasikan `given` instance di luar modul tipe domain dan di luar companion object type class, risiko apa yang dihadapi sistem pada runtime saat beberapa modul dependensi menggabungkan graf dependensinya (*diamond dependency problem*)?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Compile-Time Explosion pada Microservice Monorepo
Sebuah sistem pemrosesan transaksi keuangan berbasis Scala 3 menggunakan monorepo dengan 650.000 baris kode. Tim platform mendeteksi bahwa waktu kompilasi CI/CD melonjak drastis dari 8 menit menjadi 57 menit setelah tim produk menambahkan library pemetaan DTO berbasis *automatic derivation* (menggunakan macro `Mirror.ProductOf` dan derivation type class nested untuk 250 case class hierarkis berukuran besar). Selain itu, sesekali proses kompilasi mati akibat `java.lang.OutOfMemoryError: Metaspace / GC overhead limit exceeded`.

*Pertanyaan Diagnostik & Solusi:*
1. Mengapa generic derivation berbasis compile-time mirror rekursif dapat menyebabkan degradasi performa kompilasi eksponensial pada skala tipe yang masif?
2. Langkah rekayasa apa yang harus diambil untuk menghentikan derivation otomatis yang *unbounded* tersebut dan menggantinya dengan pendekatan *semi-automatic derivation* berbasis caching given instance?
3. Tooling atau compiler flag Scala 3 apa yang dapat Anda aktifkan untuk menganalisis jejak pohon ekspansi given (*trace implicit search tree*) guna menemukan bottleneck kompilasi secara presisi?

### Skenario B: Contextual Leakage & Thread-Boundary Desynchronization
Arsitektur transaksi enterprise menggunakan `RequestContext` yang menyimpan data audit (`traceId`, `tenantId`, `userId`). Tim merancang pipeline asinkronus menggunakan Cats Effect / ZIO / standard Scala `Future`, dengan API domain yang memanfaatkan context functions:
```scala
type Authenticated[T] = RequestContext ?=> T
def executeTransfer(from: AccountId, to: AccountId, amount: BigDecimal): Authenticated[Future[TxReceipt]]
```
Di level produksi, ditemukan anomali audit fatal: saat load tinggi, `TxReceipt` dari Tenant-A tercatat memiliki `traceId` dan `tenantId` dari Tenant-B pada Kafka transaction log downstream.

*Pertanyaan Diagnostik & Solusi:*
1. Analisis mekanisme passing context pada kode di atas: mengapa `RequestContext ?=> Future[TxReceipt]` rentan terhadap masalah *contextual capture* saat thread context beralih (*thread hopping*) di asynchronous execution boundaries?
2. Identifikasi titik kegagalan integrasi antara static contextual abstraction Scala 3 dengan runtime asynchronous context propagation!
3. Rekonstruksi rancangan API di atas agar context propagation bersifat referentially transparent, aman melintasi asynchronous boundaries, dan menjamin isolasi tenant secara mutlak tanpa kebocoran memori atau kondisi balapan (*race condition*)!

### Skenario C: Multi-Tenant Zero-Downtime Dynamic Database Routing
Perusahaan SaaS skala global mewajibkan isolasi data level fisik: setiap query SQL harus dieksekusi pada basis data tenant yang bersangkutan. Tim arsitektur ingin memanfaatkan abstraksi kontekstual Scala 3 agar developer aplikasi tidak perlu menyuntikkan parameter koneksi database secara manual di setiap method repositori domain. Namun, sistem juga memiliki background daemon process (seperti batch invoicing) yang mengeksekusi multi-tenant iteration dalam satu proses JVM yang sama secara paralel.

*Pertanyaan Diagnostik & Solusi:*
1. Bagaimana Anda merancang Type Class `DatabaseRoute[T]` dan model eksekusi berbasis Context Function sehingga developer menulis kode murni domain seperti `def fetchUser(id: UserId): Transactional[User]` tanpa menyentuh logic routing?
2. Bandingkan trade-off performa, safety, dan testability antara pendekatan Contextual Abstraction murni Scala 3 vs pendekatan runtime `ThreadLocal` / MDC (Mapped Diagnostic Context) dalam skenario eksekusi paralel multi-tenant di atas!
3. Bagaimana Anda membuktikan bahwa implementasi type class routing Anda tidak dapat di-bypass saat compile-time (menghindari runtime failure akibat missing route)?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Zero-Allocation Type-Safe Serialization & Masking Engine

#### Problem Description
Di sektor industri perbankan (Fintech Core), setiap data payload transaksi finansial wajib diserialisasi ke format JSON dan binary audit payload. Namun, beberapa field data sensitif (misal: `panCardNumber`, `cvv`, `balance`) wajib dimasking (*data obfuscation*) sebelum ditulis ke log platform atau didistribusikan ke analytics. 

Anda ditugaskan merancang *High-Performance Type-Safe Masking & Serialization Framework* dari awal (*scratch*) memanfaatkan seluruh kapabilitas abstraksi kontekstual Scala 3, **tanpa** menggunakan runtime reflection (*no `scala.reflect`* atau Java reflection), **tanpa** dependensi library serialisasi pihak ketiga, dan **meminimalkan alokasi objek** pada JVM heap.

#### Requirements
1. **Core Type Classes:**
   - Bangun type class `Masker[T]` dengan signature `def mask(value: T): String`.
   - Bangun type class `DataEncoder[T]` dengan signature `def encode(value: T): Array[Byte]`.
2. **Context-Driven Auditing:**
   - Definisikan tipe `AuditContext` yang membawa informasi `actor: String`, `ipAddress: String`, dan `correlationId: UUID`.
   - Buat Context Function type alias: `type Auditable[T] = AuditContext ?=> T`.
3. **Syntax Extensions & Ergonomics:**
   - Sediakan extension method `.toMaskedString` yang hanya dapat dipanggil jika dan hanya jika instance `Masker[T]` tersedia dalam context scope.
   - Sediakan extension method `.toAuditedPayload` yang mengeksekusi encoding dengan menyisipkan metadata `AuditContext` di awal payload tanpa merusak struktur data payload asli.
4. **Conditional & Derived Instances:**
   - Sediakan default generic derivation untuk tipe-tipe opsional (`Option[T]`), list (`List[T]`), dan key-value collections jika tipe elemen dasarnya memiliki instance `Masker[T]`.
   - Definisikan low-priority vs high-priority given instances: jika sebuah tipe primitif (misal `String`) tidak didefinisikan aturan masking eksplisitnya, fallback given instance harus memvalidasi agar field disamarkan seluruhnya (default safe fallback: `***REDACTED***`).
5. **No Reflection Guarantee:**
   - Semua evaluasi struktur data domain wajib diverifikasi saat compile-time. Gunakan Scala 3 *derivation* via `scala.deriving.Mirror.ProductOf` untuk meng-auto-derive instance `Masker` bagi case class sederhana.

#### Constraints
* **Scala Version:** Scala 3.3.x LTS atau lebih baru.
* **Strict Safety:** Dilarang keras menggunakan `asInstanceOf`, `isInstanceOf`, Java Reflection API, atau library external seperti Jackson, Circe, Upickle, Cats, atau ZIO.
* **Coherence:** Seluruh given instances default harus ditempatkan pada companion objects terkait untuk mencegah orphan instances.
* **Zero Overhead:** Extension methods tidak boleh mengalokasikan wrapper instances baru pada invocation site (manfaatkan inline methods atau value class conventions jika relevan).

#### Expected Output Test Case
Tulis sebuah test verification script yang membuktikan:
```scala
case class CardPayment(cardNumber: String, cvv: String, amount: Double)

// Demonstrasikan:
// 1. Pemanggilan .toMaskedString pada CardPayment menghasilkan masking selektif:
//    CardPayment(cardNumber=4111********1111, cvv=***, amount=1500.50)
// 2. Pemanggilan .toAuditedPayload di dalam blok 'given AuditContext'
//    menghasilkan byte stream yang diawali oleh metadata [Actor: ..., CorrelationId: ...]
// 3. Kompilasi GAGAL jika tipe target tidak memiliki type class derivation yang valid.
```

---

## 5. Knowledge Check & Checklist

Pastikan Anda menguasai seluruh indikator berikut sebelum melanjutkan ke bab berikutnya. Berikan tanda centang `[x]` pada capaian yang telah Anda kuasai.

### Saya harus memahami:
- [ ] Perbedaan fundamental antara `given` vs `implicit val/def` serta `using` vs `implicit parameter`.
- [ ] Aturan resolusi scope implicits/givens: Local Scope, Enclosing Class, Static Scope, dan Companion Scope (*Associated Types*).
- [ ] Algoritma specificity compiler dalam menentukan pemenang instance given ketika terjadi *candidate overlap*.
- [ ] Mekanisme Context Bound `[T: TypeClass]` dan proses desugaring-nya oleh compiler.
- [ ] Cara kerja Context Functions (`?=>`) dan implementasi internalnya sebagai pemetaan `ContextFunctionN`.
- [ ] Alasan mengapa *orphan instances* merusak *type class coherence* dan integritas binary compatibility.
- [ ] Konsep compile-time type class derivation menggunakan `scala.deriving.Mirror`.
- [ ] Strategi compiler dalam melakukan inlining extension methods untuk memangkas alokasi heap JVM.

### Saya tidak perlu menghafal:
- [ ] Penamaan sintaksis desugared synthetic identifier internal yang digenerate oleh compiler Scala 3 (misal: `evidence$1`, `$anon$1`).
- [ ] Daftar keseluruhan method spesifik dari internal macro API Scala 3 (`scala.quoted.Quotes`) di luar interface `Mirror` standar.
- [ ] Penomoran spesifik dari compiler warning/error code internal di compiler `dotc`.

### Saya harus bisa melakukan:
- [ ] Merancang arsitektur type class murni dari nol dengan segregasi interface, default instance, dan syntax extensions.
- [ ] Mengimplementasikan *type-safe fallback priority* menggunakan trait subtyping hierarchy untuk memisahkan High-Priority vs Low-Priority Givens.
- [ ] Menulis extension methods yang efisien, tanpa overhead alokasi objek runtime, memanfaatkan kata kunci `inline`.
- [ ] Men-debug error `Ambiguous Given Instances` dan `diverging implicit expansion` secara analitis menggunakan compiler options seperti `-Vprint:typer` atau `-explain`.
- [ ] Menerapkan context function untuk mengeliminasi parameter boilerplate (*plumbing parameters*) pada aplikasi berarsitektur enterprise.
- [ ] Mengonversi legacy codebase Scala 2 berbasis `implicit` menjadi pola modern `given`/`using` Scala 3 secara idiomatik dan zero-regression.