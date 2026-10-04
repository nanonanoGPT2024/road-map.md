# BAB 03: Quiz, Challenge, & Knowledge Check
**Fondasi Pemrograman Fungsional**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Referential Transparency & The Substitution Model
Jelaskan definisi formal dari *Referential Transparency* (RT) dan bagaimana *Substitution Model of Evaluation* bekerja untuk membuktikannya. Mengapa pemanggilan fungsi yang melibatkan `scala.util.Random.nextInt()` atau `println()` secara fundamental merusak *Referential Transparency*? Berikan contoh matematis/kode yang mendemonstrasikan kegagalan substitusi (*substitution failure*) pada ekspresi yang tidak referentially transparent.

### Soal 1.2: Mekanika Tail Call Optimization (TCO) pada JVM
Java Virtual Machine (JVM) secara native tidak memiliki instruksi bytecode untuk eliminasi *tail call* umum. Jelaskan bagaimana compiler Scala menyiasati limitasi ini saat memproses anotasi `@tailrec`! Apa perbedaan representasi bytecode yang dihasilkan antara rekursi biasa (*linear recursion*) dan rekursi ekor (*tail-recursive*)? Sebutkan tiga kondisi spesifik di mana compiler Scala akan menolak anotasi `@tailrec` dan melempar *compilation error*.

### Soal 1.3: Aljabar Data: Sum Types vs Product Types
Dalam paradigma Algebraic Data Types (ADT), model data dibangun menggunakan *Sum Types* (disjoint union) dan *Product Types* (cartesian product). 
1. Tunjukkan bagaimana cara merepresentasikan *Sum Type* dan *Product Type* secara idiomatik pada Scala 2 (`sealed trait` + `case class`) versus Scala 3 (`enum`).
2. Dari perspektif teori tipe (*type theory*), berapa jumlah status (*cardinality*) yang mungkin dimiliki oleh tipe data:
   `sealed trait ConnectionState` (memiliki 3 varian singleton) dikombinasikan dalam sebuah Product Type dengan tuple `(Boolean, Boolean)`?
3. Mengapa *exhaustiveness checking* oleh compiler hanya dapat dijamin apabila tipe dasar dinyatakan sebagai `sealed`?

### Soal 1.4: Perbedaan Semantik Antara Method (`def`) dan Function Value (`val`)
Pada Scala, method (`def`) dan function value (`val foo: A => B`) bukanlah konstruksi yang sama di level bytecode. 
Jelaskan perbedaan mendasar keduanya terkait:
1. Alokasi heap dan representasi runtime object (`scala.FunctionN`).
2. Proses *Eta-Expansion* (konversi method menjadi function value).
3. Kemampuan menerima parameter polimorfik / *type parameters* (generics). Kapan Anda harus mendefinisikan logika sebagai `def` versus menyimpannya sebagai `val` yang memegang fungsi tingkat tinggi (*Higher-Order Function*)?

### Soal 1.5: Total Functions, Partial Functions, dan `PartialFunction[A, B]`
Jelaskan perbedaan mendasar antara:
1. *Partial Function* dalam definisi matematika murni.
2. *Total Function* dalam sistem tipe Scala.
3. Tipe data `scala.PartialFunction[-A, +B]`.
Bagaimana method `isDefinedAt` dan `lift` bekerja pada `PartialFunction[A, B]`? Berikan contoh di mana sebuah blok pattern matching `{ case ... }` diperlakukan oleh compiler sebagai instansiasi dari `PartialFunction`, bukan `Function1`.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Memory Footprint dan Boxing Overhead pada Higher-Order Functions
Diberikan cuplikan kode transformasi performa tinggi berikut:
```scala
def processMetrics(data: Array[Int], f: Int => Int): Array[Int] = {
  val result = new Array[Int](data.length)
  var i = 0
  while (i < data.length) {
    result(i) = f(data(i))
    i += 1
  }
  result
}
```
Ketika fungsi ini dieksekusi dengan mem-passing lambda literal primitif seperti `processMetrics(arr, x => x * 2)`:
1. Mengapa alokasi memori dan *boxing/unboxing overhead* tetap dapat terjadi pada argumen `f` di level runtime JVM?
2. Bagaimana signature bytecode dari `scala.Function1` menangani tipe primitif tanpa optimasi?
3. Strategi apa yang disediakan oleh ekosistem Scala (misalnya `@specialized` pada Scala 2 atau *specialized functional interfaces*) untuk mengeliminasi alokasi wrapper `java.lang.Integer`?

### Soal 2.2: Memory Leak Melalui Unintended Closure Scope Capture
Perhatikan skenario kebocoran memori (*memory leak*) berikut:
```scala
class EventProcessor(val serviceName: String, largeMetadataCache: Array[Byte]) {
  def createFilter(): String => Boolean = {
    val prefix = serviceName.take(3)
    (event: String) => event.startsWith(prefix)
  }
}
```
Meskipun lambda di atas hanya membutuhkan variabel `prefix`, objek instansiasi `EventProcessor` (beserta `largeMetadataCache` sebesar ratusan megabyte) gagal dibersihkan oleh Garbage Collector selama referensi fungsi hasil kembalian `createFilter()` masih dipegang oleh komponen lain.
1. Bedah mekanisme internal JVM closure generation yang menyebabkan instans `EventProcessor.this` tertangkap secara implisit dalam closure tersebut.
2. Tuliskan refaktorisasi konkret untuk memutuskan retensi siklus hidup instans `EventProcessor` dari closure tersebut tanpa mengubah kontrak fungsi `String => Boolean`.

### Soal 2.3: Decompilation Pattern Matching: Guard Clauses & Bytecode Branching
Diberikan ADT dan evaluasi pattern matching berikut:
```scala
sealed trait Command
case class Transfer(amount: Long, targetAccount: String) extends Command
case class Audit(reason: String) extends Command
case object Shutdown extends Command

def execute(cmd: Command): Unit = cmd match {
  case Transfer(amt, _) if amt > 1000000L => notifyRegulator()
  case Transfer(amt, target)              => processTransfer(amt, target)
  case Audit(reason)                      => logAudit(reason)
  case Shutdown                           => haltSystem()
}
```
1. Jelaskan bagaimana compiler mentranslasikan konstruksi pattern matching di atas ke dalam instruksi JVM bytecode (`TABLESWITCH`, `LOOKUPSWITCH`, atau serangkaian `INSTANCEOF` / conditional jumps).
2. Mengapa penambahan *guard clause* (`if amt > 1000000L`) pada kasus pertama mematikan kemampuan compiler untuk melakukan optimasi jump table tertentu, dan bagaimana pengaruhnya terhadap pemenuhan *exhaustiveness check* jika klausa fallback `Transfer` tidak disediakan?

### Soal 2.4: Eager vs Lazy Evaluation Chaining & JVM Garbage Collector Thrashing
Sebuah microservice memproses data file transaksi harian:
```scala
val rawTransactions: List[Transaction] = loadFromFile() // Berisi 2.000.000 records

val suspiciousAmounts = rawTransactions
  .filter(_.country == "ID")
  .map(_.amount)
  .filter(_ > 500000000L)
  .take(10)
```
1. Analisis alokasi objek heap sementara (*intermediate collections*) yang diciptakan oleh operasi rantai (*chained transformations*) di atas. Mengapa pendekatan ini dapat memicu GC pause yang tinggi (*GC thrashing*)?
2. Bandingkan karakteristik komputasi dan konsumsi memori dari solusi di atas jika diubah menggunakan:
   - `rawTransactions.view` (Scala `View`)
   - `rawTransactions.iterator`
   Kapan evaluasi elemen sebenarnya terjadi pada masing-masing alternatif tersebut?

### Soal 2.5: Mutual Recursion, Trampolining, dan Call-Stack Management
Compiler Scala tidak dapat mengoptimasi rekursi mutual (*mutual recursion*) secara otomatis menggunakan `@tailrec`:
```scala
def isEven(n: Int): Boolean = if (n == 0) true else isOdd(n - 1)
def isOdd(n: Int): Boolean  = if (n == 0) false else isEven(n - 1)
```
Jika `isEven(1000000)` dipanggil, eksekusi akan melempar `java.lang.StackOverflowError`.
1. Jelaskan mengapa rekursi mutual gagal dioptimasi oleh compiler Scala standar ke dalam bentuk iterasi lokal loop tunggal.
2. Jelaskan konsep arsitektur dari pattern **Trampoline** (`scala.util.control.TailCalls._`). Bagaimana tipe data `TailRec[A]` mengubah alokasi stack frame JVM menjadi representasi alokasi data di heap, sehingga mencegah overflow?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Latency Spike & GC Pressure pada Real-Time Telemetry Pipeline
Sebuah sistem pipeline analitik menerima 120.000 *telemetry payloads* per detik. Engine dibangun menggunakan fungsional murni di mana setiap batch data dikonversi secara immutabel:

```scala
case class Metric(sensorId: String, value: Double, timestamp: Long)

def aggregateMetrics(raw: List[Metric]): Map[String, Double] = {
  raw.groupBy(_.sensorId)
     .map { case (id, metrics) => 
       id -> (metrics.map(_.value).sum / metrics.size)
     }
}
```

**Kondisi Produksi:**
Setelah berjalan stabil selama 15 menit, aplikasi mengalami degradasi throughput parah. Monitoring APM menunjukkan metrik CPU 100%, dan JVM Garbage Collector melakukan *Stop-the-World (STW)* pauses setiap 30 detik selama rata-rata 1.8 detik. Profiler (JFR) mengidentifikasi bahwa 85% alokasi memori berasal dari pembuatan objek sementara: `Tuple2`, `List`, `Vector`, dan instans `Map$Node` internal yang dibuat berulang kali selama pipeline `groupBy` dan `map`.

**Pertanyaan Diagnostik:**
1. Bedah secara mekanis mengapa pemanggilan `groupBy` yang diikuti oleh `map` dan `sum` pada collection fungsional standar JVM menciptakan *garbage churn* yang masif.
2. Tulis ulang fungsi `aggregateMetrics` menggunakan pendekatan fungsional yang *zero-garbage* atau *minimal-allocation* (misalnya memanfaatkan rekursi ekor `@tailrec` dengan struktur data yang tepat, atau akumulator mutabel yang **terisolasi ketat secara lokal di dalam batas fungsi/local scope** tanpa membocorkan efek ke luar). Jelaskan mengapa mutabilitas lokal tersebut tetap aman secara semantik FP (*purity*).

---

### Skenario B: Race Condition Menggunakan Shared Mutable State dalam Rantai Monadik `Future`
Sebuah sistem e-commerce mengorkestrasi pembayaran dan pembaruan inventaris menggunakan abstraksi fungsional paralel. Developer menulis kode berikut untuk memproses multi-item checkout:

```scala
import scala.concurrent.{Future, ExecutionContext}
import ExecutionContext.Implicits.global

class CheckoutService(inventoryService: InventoryService) {
  def processItems(items: List[Item]): Future[Int] = {
    var successfullyReserved = 0
    val reservationFutures: List[Future[Unit]] = items.map { item =>
      inventoryService.reserve(item).map { _ =>
        // Mutasi variabel lokal dari thread worker pool berbeda
        successfullyReserved += 1
      }
    }
    
    Future.sequence(reservationFutures).map(_ => successfullyReserved)
  }
}
```

**Kondisi Produksi:**
Saat beban pesanan melonjak, customer melaporkan bahwa keranjang belanja berisi 10 barang hanya mencatat `successfullyReserved` sebanyak 6 atau 7 barang, meskipun pada log database sistem inventaris, seluruh 10 reservasi berhasil dilakukan. Terjadi data inconsistency parah pada ringkasan transaksi.

**Pertanyaan Diagnostik:**
1. Lacak akar masalah kegagalan konkurensi di atas pada level JVM memory model (*visibility*, *instruction reordering*, dan operasi *non-atomic read-modify-write* pada shared mutable variable `var`).
2. Tuliskan implementasi fungsional murni untuk menyelesaikan masalah ini tanpa menggunakan `var`, tanpa primitive lock (`synchronized`), dan tanpa `AtomicInteger`. Operasi harus mengumpulkan hasil reservasi dan menghitung jumlah total sukses secara murni memanfaatkan aljabar kombinator fungsional (seperti `Future.foldLeft`, `traverse`, atau rekursi immutabel).

---

### Skenario C: Model Domain Core Banking: Exception Throwing vs Typed Error Handling
Tim arsitektur sedang me-refactor core module transfer dana antarbank. Implementasi legacy saat ini mengandalkan pelemparan exception (`throw new InsufficientFundsException()`, `throw new AccountLockedException()`) yang menyebabkan alur eksekusi bersifat implisit dan mahal secara runtime performance akibat penangkapan stack trace JVM (`Throwable.fillInStackTrace()`).

Junior engineer mengusulkan untuk mengganti semua return type menjadi `Option[TransactionReceipt]`, sedangkan Senior FP Advocate menuntut penggunaan `Either[DomainFailure, TransactionReceipt]`. Tim Business Compliance menuntut bahwa jika terjadi kegagalan validasi, sistem tidak hanya mengembalikan kesalahan pertama (*fail-fast*), melainkan mampu mengumpulkan (*accumulate*) semua alasan kegagalan input (misal: "Saldo tidak cukup" DAN "Nomor rekening tujuan tidak valid" DAN "Batas limit harian terlampaui").

**Pertanyaan Diagnostik:**
1. Mengapa `Option[TransactionReceipt]` merupakan pemodelan domain yang cacat untuk skenario kegagalan enterprise?
2. Definisikan hierarki error domain komprehensif menggunakan Scala 3 `enum` atau Scala 2 `sealed trait` (ADT) yang memodelkan varian-varian kegagalan perbankan di atas beserta data kontekstualnya.
3. Analisis mengapa monad `Either` standar gagal memenuhi kebutuhan bisnis untuk *Error Accumulation* (pengumpulan daftar error), dan jelaskan konsep aljabar tipe data yang dibutuhkan untuk mengakomodasi akumulasi tersebut (seperti tipe data `Validated` pada ekosistem fungsional Scala / Cats) dibandingkan perilaku `monadic short-circuiting`.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance, Purely Functional Order Matching Engine

#### Problem Statement
Anda diminta untuk membangun komponen inti (*core matching engine*) bursa perdagangan aset kripto untuk pasangan instrumen `BTC/USDT`. Komponen ini harus murni fungsional: **bebas efek samping (no I/O, no mutation outside isolated functions, no exceptions)**. Seluruh status order book dan log transaksi harus diproses sebagai transisi status deterministik (*pure state transitions*).

#### Requirements:
1. **Domain Modeling (ADTs):**
   - Bangun model domain lengkap menggunakan ADT:
     - `Side` (`Buy`, `Sell`)
     - `OrderType` (`Limit`, `Market`)
     - `Order(id: OrderId, side: Side, orderType: OrderType, price: BigDecimal, quantity: BigDecimal, timestamp: Long)`
     - `Trade(buyerOrderId: OrderId, sellerOrderId: OrderId, price: BigDecimal, quantity: BigDecimal, timestamp: Long)`
     - `OrderBook(bids: List[Order], asks: List[Order])` (bids terurut menurun/descending, asks terurut menaik/ascending berdasarkan harga dan FIFO timestamp).
   - Definisikan tipe kesalahan domain `EngineError` (e.g., `InvalidQuantity`, `InvalidPrice`, `OrderNotFound`) menggunakan Sum Type.

2. **Matching Engine Logic:**
   - Implementasikan fungsi inti dengan *pure signature*:
     ```scala
     def processOrder(book: OrderBook, incoming: Order): Either[EngineError, (OrderBook, List[Trade])]
     ```
   - Aturan pencocokan (*Matching Rules*):
     - Order `Limit Buy` akan mencocokkan *Ask* yang memiliki `price <= buy.price`.
     - Order `Limit Sell` akan mencocokkan *Bid* yang memiliki `price >= sell.price`.
     - Eksekusi harus menangani *partial fills* (sisa volume tetap berada di dalam book) dan *full fills* (order diangkat dari book).
     - Jika order baru tidak habis tercocokkan, sisa kuantitasnya harus dimasukkan ke sisi book yang sesuai dengan mempertahankan aturan sorting prioritas: Harga terbaik -> Waktu paling awal.

3. **Constraints:**
   - **Zero Side-Effects:** Dilarang menggunakan `var` global/instance, dilarang melempar exception (`throw`), dilarang memanggil `println`, `System.currentTimeMillis` (timestamp harus di-inject via parameter order), atau operasi I/O.
   - **Stack Safety:** Semua algoritma matching yang memproses antrean order book harus menggunakan rekursi ekor beranotasi `@tailrec`. Tidak boleh ada risiko `StackOverflowError` berapapun kedalaman buku order.
   - **Purity & Determinism:** Diberikan `OrderBook` awal yang sama dan urutan order yang identik, output akhir harus menghasilkan nilai byte-identical.

#### Expected Output
Dokumentasikan implementasi lengkap dalam satu file Scala mandiri (dapat dikompilasi menggunakan `scalac` Scala 2.13 atau Scala 3) yang menyertakan:
1. Definisi ADT.
2. Implementasi algoritma matching `@tailrec`.
3. Test harness berbasis pemanggilan murni (bukan testing framework eksternal, cukup via fungsi `main`) yang mendemonstrasikan kasus:
   - Order masuk mencocokkan sebagian (*partial match*).
   - Order masuk mencocokkan multi-order di seberang antrean (*multi-fill*).
   - Order ditolak karena validasi domain (menghasilkan `Left(EngineError)`).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Definisi presisi dari *Referential Transparency*, *Pure Function*, dan konsekuensi dari *Substitution Model*.
- [ ] Mengapa functional programming memandang exception handling konvensional (`throw / try / catch`) sebagai *goto statement* yang merusak referential transparency dan type safety.
- [ ] Batasan arsitektural JVM terkait *Tail Call Optimization* dan cara kerja compiler Scala mentransformasi fungsi rekursif `@tailrec` menjadi iterasi level bytecode.
- [ ] Struktur dan klasifikasi *Algebraic Data Types* (Sum Types, Product Types) beserta peran *pattern matching exhaustiveness check* pada fase kompilasi.
- [ ] Perbedaan antara method invocation (`invokevirtual` / `invokestatic`) dan dynamic function invocation melalui objek instance turunan `scala.FunctionN`.
- [ ] Bahaya memori akibat *unintended closure scope capture* saat fungsi anonim memegang referensi ke outer class.
- [ ] Implikasi performa heap memory (*garbage collector thrashing*) dari manipulasi immutable collection berantai tanpa abstraksi lazy (`View` / `Iterator`).
- [ ] Pemodelan penanganan error berbasis aljabar monadik: Kapan menggunakan `Option`, kapan `Either`, dan kapan membutuhkan *applicative error accumulation*.

### Saya tidak perlu menghafal:
- [ ] Penamaan bytecode offset spesifik atau opcode number numerik JVM (seperti `0xb6` untuk `invokevirtual`).
- [ ] Setiap implementasi method internal pada hirarki collection Scala (`c.s.c.immutable.VectorPointer`, dll).
- [ ] Notasi matematika kategori teori formal (seperti detail representasi *Cartesian Closed Categories* atau hukum *Kleisli composition*) selama Anda menguasai semantik operasionalnya pada kode Scala.

### Saya harus bisa melakukan:
- [ ] Mengonversi loop imperatif berbasis `var`, `while`, dan mutable collection menjadi fungsi fungsional murni berbasis `@tailrec` tanpa mengorbankan keamanan alokasi heap.
- [ ] Mendiagnosis dan mengisolasi insiden *memory leak* di level production yang dipicu oleh retensi state di dalam closure function value.
- [ ] Mengonstruksi model domain sistem enterprise yang kompleks dengan ADT yang menjamin *invalid states become unrepresentable* (kondisi tidak valid tidak dapat dikompilasi).
- [ ] Menulis unit testing deterministik untuk logika fungsional tanpa memerlukan mock framework, semata-mata memanfaatkan substitusi nilai murni.
- [ ] Melakukan refaktorisasi arsitektur dari sistem berbasis throwing exception ke arah sistem *Typed Functional Error Handling* berbasis `Either`/ADT secara idiomatik.