# BAB 05: Quiz, Challenge, & Knowledge Check
**Sistem Pengetikan Tingkat Lanjut (Advanced Type System)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Variance Positions & Liskov Substitution Principle (LSP)
Secara formal, jelaskan mengapa sebuah tipe kontainer kovarian `F[+A]` secara *default* dilarang oleh kompilator Scala untuk menerima tipe `A` sebagai parameter metode (`def add(item: A): F[A]`). Bagaimana kompilator mendeteksi pelanggaran posisi kontravarian (*contravariant position*) ini dari perspektif *Liskov Substitution Principle* (LSP), dan mengapa penambahan batasan bawah (*lower bound*) `[B >: A]` pada metode tersebut (`def add[B >: A](item: B): F[B]`) mampu memulihkan *soundness* dari sistem pengetikan?

### Soal 1.2: Path-Dependent Types dan Enkapsulasi Identitas
Diberikan dua *instance* objek terpisah: `val engineA = new DatabaseEngine` dan `val engineB = new DatabaseEngine`, di mana di dalam kelas `DatabaseEngine` didefinisikan sebuah kelas `class Session`. Mengapa kompilator Scala menganggap `engineA.Session` dan `engineB.Session` sebagai tipe yang sepenuhnya *disjoint* (tidak kompatibel satu sama lain)? Jelaskan fondasi teoretis *path-dependent types* dalam kalkulus $p$-calculus / DOT (*Dependent Object Types*) dan implikasi arsitekturalnya terhadap pencegahan kebocoran konteks (*context-leaking bug*).

### Soal 1.3: Abstraksi Tingkat Tinggi melalui Higher-Kinded Types (HKT)
Bedakan secara semantik dan dimensional antara *proper type* (tipe ber-kind `*` atau `Type`), *first-order type constructor* (tipe ber-kind `* -> *` atau `Type -> Type`), dan *higher-kinded type* (misalnya `(* -> *) -> *`). Mengapa konstruksi antarmuka seperti `Functor[F[_]]` menuntut `F` berstatus sebagai *type constructor* alih-alih tipe konkret? Jelaskan apa yang terjadi jika Anda memaksakan abstraksi tipe konkret pada pustaka pemrosesan aliran data generik (*generic streaming pipelines*).

### Soal 1.4: Generalized Type Constraints (`=:=` vs `<:<`)
Jelaskan perbedaan mendasar antara *subtyping upper bound* (`[A <: B]`) yang dievaluasi secara global pada level deklarasi kelas/metode dengan *generalized type constraint* (seperti `implicit ev: A =:= B` atau `ev: A <:< B`) yang dievaluasi pada situs pemanggilan (*call-site*). Dalam skenario apa pendefinisian metode koleksi generic (misalnya metode `flatten` pada `List[A]`) hanya dapat diimplementasikan menggunakan generalized type constraints tanpa merusak fleksibilitas *instantiation* kelas koleksi tersebut?

### Soal 1.5: Opaque Types vs Value Classes (`AnyVal`)
Pada Scala 3, diperkenalkan fitur `opaque type` untuk menggantikan idiom *Value Classes* (`extends AnyVal`). Jelaskan perbedaan arsitektur kompilasi dan representasi memori runtime JVM antara keduanya. Analisis kondisi di mana *Value Classes* masih berisiko memicu alokasi memori tak terduga (*runtime boxing*) pada heap, dan bagaimana *Opaque Types* mengeliminasi alokasi tersebut tanpa mengorbankan keamanan tipe (*type safety*).

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: JVM Type Erasure, Skolemization, dan TypeTest/ClassTag
Perhatikan potongan kode Scala berikut:
```scala
def processEntities[T](list: List[T]): Unit = list match {
  case strings: List[String] => println(s"Strings: ${strings.mkString}")
  case ints: List[Int]       => println(s"Sum: ${ints.sum}")
}
```
Kompilator mengeluarkan peringatan: *"non-variable type argument String in type pattern List[String] is unchecked since it is eliminated by type erasure"*. 
1. Bedah secara internal apa yang dilakukan JVM bytecode generator terhadap tipe generic `T` pada fase kompilasi *erasure*.
2. Mengapa *pattern matching* di atas akan selalu mengeksekusi cabang (*branch*) pertama terlepas dari argumen yang diberikan?
3. Jelaskan bagaimana Anda merekayasa ulang fungsi tersebut secara idiomatik menggunakan `TypeTest` (Scala 3) atau `ClassTag`/`TypeTag` (Scala 2) agar pembedaan tipe kontainer bersarang dapat berjalan deterministik saat runtime tanpa *blind casting*.

### Soal 2.2: The Aux Pattern vs Type Projection Soundness
Di Scala 2, teknik ekstraksi tipe *dependent* sering kali mengandalkan proyeksi tipe struktural arbitrary `F#Out`. Mengapa proyeksi tipe arbitrary ini dihapus pada Scala 3 karena dinilai *unsound* (dapat mematahkan konsistensi logis kompilator)? Jelaskan mekanisme internal dari *Aux Pattern* (misalnya `type Aux[A, B] = Foo[A] { type Out = B }`) dalam memindahkan resolusi tipe hasil (*result type*) dari posisi *type member* ke parameter tipe level ekspresi, dan bagaimana cara kerjanya mencegah instansiasi unsafe type pada fase *implicit search*.

### Soal 2.3: Phantom Types dan State Machine Invalidation
Anda mendesain *driver* koneksi jaringan menggunakan idiom *Phantom Types* untuk memastikan status transaksi (*Unauthenticated*, *Authenticated*, *Connected*, *Closed*) terisolasi pada level kompilasi tanpa *runtime overhead*. 
Jelaskan:
1. Mengapa tipe penanda (*phantom markers*) tidak memerlukan instansiasi objek konkret di JVM heap.
2. Analisis bagaimana kode berikut dapat dijebol integritas pengetikannya (*type-safety loophole*) jika pengembang ceroboh menggunakan *type coercion*, *variance mismatch*, atau downcasting implisit:
```scala
sealed trait State
trait Disconnected extends State
trait Connected extends State

class Connection[S <: State] private (val socket: Socket) {
  def send(data: Array[Byte])(implicit ev: S =:= Connected): Unit = ???
}
```
Bagaimana Anda menyusun enkapsulasi konstruktor private dan factory constructor untuk menjamin bahwa tidak ada status koneksi ilegal yang dapat dibuat secara sintetis oleh pemanggil API?

### Soal 2.4: Existential Types dan Skolemization Failures
Saat mengintegrasikan pustaka Java warisan (*legacy*) yang mengekspos *wildcard generic* (misalnya `Class<?>` atau `List<? extends Number>`), Scala memetakannya sebagai *existential type* atau *wildcard type argument* (`List[_ <: Number]`). 
Saat kompilator melakukan inferensi, ia menjalankan proses *skolemization* (membuat konstanta tipe internal unik/skolem constant `_$1`). 
Jelaskan mengapa kesalahan kompilasi berikut kerap terjadi saat mencoba memanipulasi struktur data tersebut:
```scala
def appendElement(list: List[_]): List[_] = list.head :: list
// Compile Error: type mismatch; found: Any, required: _$1
```
Bagaimana *pattern matching* atau *type parameter unpack pattern* (`def unpack[T](list: List[T]): List[T]`) bekerja secara formal di dalam typer engine kompilator untuk membuka (*open*) eksistensial skolem tersebut?

### Soal 2.5: Intersection Types (`&`) vs Structural/Refinement Types
Scala 3 menggantikan tipe *compound* (`A with B`) dengan *Intersection Types* (`A & B`).
1. Jelaskan perbedaan resolusi linearisasi (*linearization resolution*) antara `A with B` dan simetri komutatif pada `A & B`.
2. Jika tipe `A` mendefinisikan `def execute: Int` dan tipe `B` mendefinisikan `def execute: String`, jelaskan apa respons typer engine Scala 3 terhadap ekspresi bertipe `A & B`.
3. Bandingkan efisiensi runtime dispatch antara metode yang dipanggil melalui *Intersection Types* murni berbasis antarmuka statis dengan *Refinement/Structural Types* (`A { def execute: Int }`) yang menggunakan JVM dynamic reflection (*MethodHandle* / invokeDynamic overhead).

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Kompilasi OOM & Exponential Implicit Resolution Cycle
* **Konteks:** Sebuah sistem microservice berbasis Scala 3 menggunakan ekosistem *typelevel* (Cats, Circe, Tapir, Iron) untuk memvalidasi dan mendeserialisasi skema event streaming Kafka dengan 250+ model protobuf/JSON bersarang yang kompleks.
* **Gejala:** Pipeline CI/CD tiba-tiba mengalami *timeout*. Server build lokal mengalami *heap exhaustion* (`java.lang.OutOfMemoryError: Metaspace` atau JVM heap 16GB habis pada fase `typer` scalac). Analisis profil kompilasi (`-Vprofile` / `-Xmacro-settings:materialize-derivations`) menunjukkan kompilator terjebak dalam siklus pencarian implisit (*implicit search tree*) saat mencoba menderivasi encoder/decoder JSON untuk tipe-tipe yang memiliki generic derivation hierarkis.
* **Pertanyaan Diagnostik:**
  1. Bagaimana mekanisme kompilator Scala dalam mengevaluasi rekursi pengetikan (*divergent implicit expansion*)? Apa peran ambang batas (*threshold*) rekursi internal dan bagaimana siklus ini memakan memori kompilator secara eksponensial?
  2. Langkah mitigasi arsitektur apa yang harus diambil untuk menghentikan penurunan kinerja (*divergence*) kompilator ini? Evaluasi trade-off antara *automatic generic derivation* (shapeless/mirror derivation) vs *semi-automatic derivation* vs *manual explicit instances*.
  3. Bagaimana strategi isolasi boundary compilation unit (misalnya *separate compilation units* atau pre-compiled implicit cache interfaces) diterapkan pada struktur modul sbt multi-project?

### Skenario B: Kebocoran Data Multi-Tenant via Unsound Path-Dependent Types
* **Konteks:** Anda mengelola platform SaaS financial ledger yang mengimplementasikan sistem isolasi multitenansi berbasis tipe. Setiap tenant direpresentasikan oleh instansiasi objek tenant tersendiri:
```scala
class TenantContext(val tenantId: String) {
  sealed trait RecordId
  case class TransactionId(value: UUID) extends RecordId
  case class AccountId(value: UUID) extends RecordId
}
```
* **Insiden:** Pada sebuah batch processing pipeline multi-thread yang mengonsumsi ribuan transaksi, ditemukan bahwa `TransactionId` dari `Tenant A` diproses dan dieksekusi di dalam ledger `Tenant B`. Pemeriksaan awal menunjukkan bahwa *type checking* berhasil lolos tanpa peringatan (*zero compile warnings*).
* **Pertanyaan Diagnostik:**
  1. Identifikasi di mana letak kelemahan sistem tipe pada modul pipeline tersebut. Mengapa deserialisasi runtime (misalnya dari Akka/Pekko stream atau HTTP payload) yang mengonversi JSON payload kembali menjadi objek domain berisiko menghapus batasan *path-dependent* jika signature metodenya menerima abstraksi berbasis *erased structural type* atau `TenantContext#RecordId`?
  2. Rancang ulang antarmuka pipeline tersebut dengan menerapkan *generalized type constraints* dan *dependent method types* untuk memastikan kompilator secara kaku menolak transaksi apapun yang tidak memiliki dependensi eksplisit terhadap instansiasi *path* tenant yang bersangkutan:
     `def postTransaction(ctx: TenantContext)(id: ctx.TransactionId, amount: BigDecimal): Unit`
  3. Bagaimana Anda menangani *unification* saat memproses koleksi heterogen dari beberapa tenant (`List[TenantContext]`) tanpa mengekspos tipe ke `Any` atau memicu *skolem mismatch*?

### Skenario C: Dilema Arsitektur Type-Level State Machine vs Match Types
* **Konteks:** Tim Arsitektur Inti sedang merancang ulang modul orkestrasi *Order Execution Engine* untuk sistem perdagangan bursa berfrekuensi tinggi (low-latency, zero-GC pressure). Siklus hidup order mengikuti alur kaku:
  `New -> PendingNew -> (Rejected | Placed) -> (PartiallyFilled | Filled | Cancelled)`
* **Dilema:** Dua arsitek berselisih pandang:
  * **Arsitek 1:** Mengusulkan pemodelan menggunakan *Phantom Types* klasik dengan multi-parameter type class untuk transisi state guna menjamin keamanan tipe mutlak dan nol alokasi heap runtime.
  * **Arsitek 2:** Mengusulkan penggunaan *Scala 3 Match Types* yang direduksi pada compile-time untuk memodelkan fungsi transisi fungsional murni:
    `type Transition[S <: OrderState, E <: OrderEvent] <: OrderState = ...`
* **Pertanyaan Diagnostik:**
  1. Analisis performa emisi JVM bytecode antara kedua pendekatan tersebut. Apakah *Match Types* menyisakan jejak alokasi atau type-check casting tersembunyi saat dievaluasi di level hot-path?
  2. Bagaimana kemampuan kedua pendekatan tersebut dalam menangani *error handling compile-time*? Pendekatan mana yang mampu menyajikan pesan kompilasi humanis yang dapat dipahami teknisi biasa ketika transisi ilegal terjadi?
  3. Buat matriks keputusan arsitektur (meliputi: *Cognitive Overhead, Compile-time Performance, Binary Compatibility/Migration, GC Pressure*) dan berikan rekomendasi final berbasis fakta rekayasa perangkat lunak untuk skenario bursa berlatensi rendah ini.

---

## 4. Chapter Challenge

### Tantangan Praktis: Type-Safe Deterministic SQL Query Builder Engine

#### Deskripsi Masalah
Banyak pustaka basis data mengizinkan eksekusi query yang cacat secara runtime—misalnya memanggil `execute()` pada query `SELECT` tanpa klausa `FROM`, mendefinisikan klausa `WHERE` duplikat yang saling menimpa secara tidak sengaja, atau memetakan seleksi kolom yang tipe datanya tidak sesuai dengan tipe data pada model tabel. 

Anda ditugaskan membangun pustaka mini berkinerja tinggi bernama **`TypeSafeSQL`**. Query builder ini harus memanfaatkan sistem pengetikan tingkat lanjut Scala untuk memastikan bahwa query SQL **hanya dapat dikompilasi jika dan hanya jika** query tersebut lengkap secara gramatikal dan konsisten secara skema.

#### Persyaratan Teknis (Requirements)
1. **FSM Type-Level:** Buat state pengetikan statis menggunakan *Phantom Types* atau *Match Types* untuk menandai:
   * State Pemilihan: `NoSelect`, `HasSelect[Fields]`
   * State Sumber Data: `NoTable`, `HasTable[T]`
   * State Kesiapan: `Executable`
2. **Grammar Constraints:**
   * Metode `.select(...)` hanya boleh dipanggil dari state awal.
   * Metode `.from(...)` hanya boleh dipanggil setelah `.select(...)` dipanggil minimal satu kali.
   * Metode `.where(...)` opsional, namun hanya boleh dipanggil setelah `.from(...)`.
   * Metode `.build()` atau `.execute()` **hanya tersedia (terekspos)** jika query telah memiliki minimal satu kolom seleksi dan satu sumber tabel referensi. Jika query belum memenuhi syarat, pemanggilan `.build()` harus menghasilkan *compile-time error*.
3. **Pesan Kesalahan Compile-Time Khusus:**
   * Gunakan anotasi `@implicitNotFound` (Scala 2/3) atau *Scala 3 compile-time error assertion* (`scala.compiletime.error`) untuk menampilkan pesan error yang ramah dan presisi, contoh:
     `"Kompilasi Ditolak: Anda tidak dapat mengeksekusi Query tanpa mendefinisikan tabel sumber via klausa .from()!"`
4. **Schema Safety & Column Extraction:**
   * Buat representasi skema model (misal: `case class User(id: Long, name: String, age: Int)`).
   * Validasi kolom harus berbasis path-dependent atau tipe literal bertipe aman, mencegah developer memanggil nama kolom yang tidak ada pada tabel yang ditentukan di klausa `.from()`.

#### Batasan Arsitektural (Constraints)
* **Zero Allocation Runtime Overhead:** Builder tidak boleh mengalokasikan wrapper class baru di setiap transisi method call; gunakan *Opaque Types* atau *Value Classes* (`AnyVal`).
* **No Dynamic Reflection:** Dilarang keras menggunakan `scala.reflect.runtime` atau Java Reflection API. Semua metadata kolom harus di-resolve secara statis saat kompilasi.
* Target kompatibilitas: Scala 3.3+ LTS.

#### Contoh Verifikasi Implementasi
```scala
// Harus Berhasil Dikompilasi:
val validQuery = QueryBuilder
  .select[User](u => (u.id, u.name))
  .from("users")
  .where("age > 18")
  .build()

// HARUS GAGAL DIKOMPILASI dengan error deskriptif:
val invalidQuery1 = QueryBuilder
  .select[User](u => (u.id, u.name))
  .build() // ERROR: Tidak ada klausa .from()

val invalidQuery2 = QueryBuilder
  .from("users")
  .build() // ERROR: Tidak ada klausa .select()

val invalidQuery3 = QueryBuilder
  .select[User](u => u.nonExistentField) // ERROR: Field tidak terdefinisi pada model User
```

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk mengukur kesiapan teknis Anda sebelum melangkah ke bab implementasi arsitektur sistem berikutnya.

### Saya harus memahami:
- [ ] Aturan formal *Variance Annotations* (`+T`, `-T`, invariant) dan batasannya terhadap posisi kovarian, kontravarian, serta invarian dalam method definitions.
- [ ] Fondasi kalkulus DOT (*Dependent Object Types*) yang mendasari semantik pengetikan modern di Scala.
- [ ] Teori kategori dasar yang diterapkan pada Scala types: Kind, Type Constructors, dan abstraksi Higher-Kinded Types (`F[_]`).
- [ ] Dampak JVM Type Erasure terhadap generic types, mitigasi menggunakan bytecode evidence (`TypeTest`, `ClassTag`), dan batasannya.
- [ ] Mekanisme resolusi *Implicit Search* / *Given-Using Resolution*, batasan rekursi compiler, dan dampaknya terhadap throughput kompilasi.
- [ ] Semantik *Subtyping Bounds* (`<:`, `>:`) versus *Generalized Type Constraints* (`=:=`, `<:<`) dalam perancangan API fungsional.
- [ ] Perbedaan internal runtime antara *Opaque Types*, *Value Classes (`AnyVal`)*, dan *Primitive Boxed Types*.

### Saya tidak perlu menghafal:
- [ ] Algoritma internal *Type Linearization Order* untuk diamond inheritance berlapis (cukup pahami aturan: evaluasi kanan-ke-kiri, hirarki berbasis *depth-first search reverse post-order*).
- [ ] Setiap kode error desimal compiler `scalac` (cukup pahami cara membaca trace error pencarian tipe dan skolem mismatch).
- [ ] Kode internal translasi AST macros pada pemrosesan Shapeless Aux Pattern (cukup pahami konsep pengalihan *type member* ke parameter tipe).

### Saya harus bisa melakukan:
- [ ] Menulis antarmuka type-safe yang mencegah *state transition bug* menggunakan *Phantom Types* tanpa mengorbankan alokasi runtime memory heap.
- [ ] Mendiagnosis dan memperbaiki *compile-time performance bottleneck* yang disebabkan oleh ledakan implicit tree divergence di pipeline CI/CD.
- [ ] Merancang API berbasis *Path-Dependent Types* untuk memisahkan domain boundary dan menjamin isolasi data multi-tenant secara matematis saat kompilasi.
- [ ] Mengimplementasikan fungsionalitas abstraksi generik menggunakan *Higher-Kinded Types* yang dapat beroperasi mulus di atas berbagai jenis struktur data (`List`, `Vector`, `Future`, `IO`).
- [ ] Melakukan debugging terhadap error kompilasi *skolem type mismatch* dan merancang pattern matching unboxing yang valid secara *type safety*.