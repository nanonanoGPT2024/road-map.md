# BAB 03 / MODULE 01: FONDASI PEMROGRAMAN FUNGSIONAL

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** `02-Programming-Languages / Scala`
*   **Modul:** `Bab 03 / Modul 01: Fondasi Pemrograman Fungsional`
*   **Prasyarat:** Pemahaman sintaks dasar Scala (deklarasi variabel, kontrol alur, object-oriented basics), instalasi JVM (Java Virtual Machine) 17+ LTS, dan sbt (Scala Build Tool) 1.9+.
*   **Tech Stack:** Scala 3.3+ LTS, JDK 17/21, sbt.
*   **Tingkat Kesulitan:** Intermediate.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1.  **Mendefinisikan dan Membuktikan** *Referential Transparency* dan *Purity* pada fungsi secara matematis dan implementatif dalam Scala 3.
2.  **Menganalisis dan Membedakan** mekanisme alokasi memori antara struktur data *mutable* versus *persistent immutable data structures* berbasis *structural sharing*.
3.  **Mengimplementasikan** *Higher-Order Functions* (HOFs), teknik *currying*, serta *partial application* untuk menyusun logika abstraksi data yang modular.
4.  **Menulis dan Mengoptimalkan** algoritma rekursif menggunakan tail recursion (`@tailrec`) untuk mengeliminasi risiko `StackOverflowError` pada JVM.
5.  **Menerapkan** paradigma *Expression-Oriented Programming* guna mengeliminasi mutasi state global dan memitigasi *side-effects* tak terprediksi dalam skala produksi.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Mesin von Neumann ke Kalkulus Lambda

Pemrograman imperatif berakar langsung pada arsitektur mesin von Neumann: program dipandang sebagai serangkaian instruksi yang memodifikasi sel-sel memori fisik register dan RAM (*state mutation*) secara berurutan. Pendekatan ini menuntut *developer* melacak *state* yang terus berubah seiring berjalannya waktu ($State(t_0) \to State(t_1) \to \dots$).

Sebaliknya, **Pemrograman Fungsional (FP)** berakar pada *Lambda Calculus* (Alonzo Church). Mental model FP memandang komputasi bukan sebagai aksi modifikasi memori, melainkan sebagai **evaluasi ekspresi matematika**.

```
Mental Model Imperatif:
[Input] -> [Langkah 1: Ubah Memori] -> [Langkah 2: Timpa Register] -> [Output]

Mental Model Fungsional:
[Input] -> [Transformasi F(x)] -> [Transformasi G(F(x))] -> [Output Baru]
           (Data lama tetap utuh, tidak pernah bermutasi)
```

### Analogi: Resep Dapur vs Rumus Aljabar

*   **Imperatif (Resep Dapur):** "Ambil mangkuk A, masukkan telur, kocok hingga mengembang (mangkuk A berubah bentuk fisik), tambahkan terigu ke mangkuk A." Jika proses gagal di tengah jalan, kondisi mangkuk A rusak dan tidak dapat dikembalikan dengan mudah.
*   **Fungsional (Rumus Aljabar):** Diberikan $y = f(x) = x^2 + 2x + 1$. Evaluasi terhadap $f(3)$ akan selalu menghasilkan $16$. Angka $3$ tidak bermutasi menjadi $16$. Kapan pun dan di mana pun $f(3)$ dipanggil, nilainya dapat langsung disubstitusikan dengan $16$ tanpa mengubah konteks dunia luar.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### 1. Model Substitusi (*Equational Reasoning*)

Ketika sebuah fungsi bersifat murni (*pure*), pemanggilan fungsi dapat ditukar secara langsung dengan nilainya tanpa memengaruhi perilaku program.

```
Ekspresi Awal:
val z = add(2, 3) * add(2, 3)

Langkah 1 (Evaluasi Pure Function):
add(2, 3) => 5

Langkah 2 (Substitusi Nilai):
val z = 5 * 5

Langkah 3 (Hasil Akhir):
val z = 25
```

Jika `add` memiliki *side-effect* (misalnya mencetak log atau mengubah variabel global), substitusi di atas menjadi cacat dan melanggar prinsip substitutabilitas.

### 2. Structural Sharing pada Persistent Data Structures

Data *immutable* tidak disalin seluruhnya (*deep copy*) saat dimodifikasi. Scala memanfaatkan *structural sharing* melalui pointer:

```
List Asli: xs = List(2, 3, 4)
Memori: [Node: 2] ---> [Node: 3] ---> [Node: 4] ---> Nil

Operasi Penambahan Elemen: ys = 1 :: xs
Memori Baru:
[Node: 1] 
    |
    v
[Node: 2] ---> [Node: 3] ---> [Node: 4] ---> Nil
   ^
   |
(xs tetap menunjuk ke sini tanpa modifikasi!)
```

### 3. Stack Frame: Rekursi Standar vs Tail Recursion (TCO)

```
Rekursi Biasa (Non-Tail Recursive):
stack-frame 3: fact(1) -> 1
stack-frame 2: fact(2) -> 2 * fact(1)    [Tertahan menunggu child frame]
stack-frame 1: fact(3) -> 3 * fact(2)    [Tertahan menunggu child frame]
stack-frame 0: main()
=> JVM mengalokasikan stack frame baru di setiap level: RISIKO StackOverflowError.

Tail Recursion (@tailrec):
Frame 0: factTail(3, acc = 1)
Frame 0: factTail(2, acc = 3)   [Stack frame ditimpa/di-reuse via instruksi GOTO]
Frame 0: factTail(1, acc = 6)
Frame 0: factTail(0, acc = 6) => Return 6
=> Konsumsi stack konstan: O(1) space.
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Representasi Internal Fungsi: Trait `scala.FunctionN`

Di balik layar, fungsi di Scala bukanlah konstruksi primitif JVM murni, melainkan sebuah *Object* yang mengimplementasikan trait `scala.FunctionN` (di mana $N$ adalah aritas fungsi dari 0 hingga 22 pada Scala 2, dan tak terbatas pada Scala 3 berkat sintaks fungsi baru).

```scala
// Kode Scala
val square: Int => Int = x => x * x
```

Diterjemahkan oleh *compiler* Scala menjadi padanan:

```java
// Representasi bytecode/Java runtime
public final class AnonSquare implements scala.Function1<Object, Object> {
    public int apply$mcII$sp(int x) {
        return x * x;
    }
    public Object apply(Object v1) {
        return BoxesRunTime.boxToInteger(apply$mcII$sp(BoxesRunTime.unboxToInt(v1)));
    }
}
```

Dalam Scala 3, pemanggilan fungsi `f(x)` selalu di-desugar menjadi pemanggilan metode internal: `f.apply(x)`.

### 2. Mekanisme Tail Call Optimization (TCO) di Level Bytecode

JVM secara *native* tidak memiliki instruksi formal untuk *Tail Call Optimization* (tidak ada instruksi `tailcall` universal seperti pada LLVM). Scala menjembatani limitasi ini pada fase kompilasi:

Ketika sebuah fungsi memenuhi syarat rekursi ekor (*tail-recursive*) dan ditandai dengan `@annotation.tailrec`, Scala compiler mengubah rekursi tersebut secara mekanis menjadi *bytecode jump* (`goto`), membuang kebutuhan membuat JVM Stack Frame baru.

*Bytecode Analysis:*
```
// Perintah rekursif yang belum dioptimasi menghasilkan:
INVOKEVIRTUAL MyClass.recursiveMethod (I)I

// Perintah @tailrec diubah compiler menjadi:
ILOAD 2
ISTORE 1
GOTO label_start
```

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Pure Functions & Side Effects

Sebuah fungsi $f: A \to B$ dikatakan **Pure** jika dan hanya jika:
1.  **Deterministik:** Untuk input $a \in A$ yang sama, fungsi selalu menghasilkan output $b \in B$ yang identik. Output semata-mata merupakan fungsi dari inputnya.
2.  **Bebas Efek Samping (*Free from Side-Effects*):** Tidak menyebabkan observasi perubahan kondisi di luar lingkup fungsi tersebut, seperti:
    *   Memodifikasi variabel luar (*shared mutable state*).
    *   Melakukan operasi I/O (membaca file, panggilan jaringan, mutasi database, atau mencetak teks ke layar/console).
    *   Melempar Exception secara eksplisit (`throw new RuntimeException()`).
    *   Membaca status global non-deterministik (`System.currentTimeMillis()`, `Random.nextInt()`).

### 2. Referential Transparency (RT)

Ekspresi $e$ bersifat *referentially transparent* jika dalam semua konteks di mana $e$ muncul, $e$ dapat digantikan dengan nilai hasil evaluasinya tanpa mengubah arti atau hasil akhir program.

*Formulasi Formal:*
Diberikan program $P$ dan ekspresi $e$. Jika semua kemunculan $e$ dalam $P$ dapat disubstitusi dengan $v$ (di mana $v$ adalah hasil dari `eval(e)`) tanpa mengubah perilaku eksekusi $P$, maka $e$ adalah *referentially transparent*.

### 3. First-Class & Higher-Order Functions (HOFs)

*First-class functions* berarti fungsi diperlakukan sebagai warga negara kelas satu (*first-class citizens*):
*   Dapat disimpan dalam variabel (`val f = (x: Int) => x + 1`).
*   Dapat diteruskan sebagai argumen ke fungsi lain.
*   Dapat dikembalikan sebagai nilai dari pemanggilan fungsi lain.

*Higher-Order Functions* (HOF) adalah fungsi yang menerima fungsi lain sebagai parameter, menghasilkan fungsi, atau keduanya. Fondasi HOFs menyediakan abstraksi universal terhadap perulangan data:
*   **Transformasi:** `map: (A => B) => List[B]`
*   **Penyaringan:** `filter: (A => Boolean) => List[A]`
*   **Akumulasi/Reduksi:** `foldLeft: (B) => ((B, A) => B) => B`

### 4. Currying dan Partial Application

*   **Currying:** Proses konversi sebuah fungsi dengan banyak parameter $f(A, B) \to C$ menjadi rantai fungsi-fungsi berargumen tunggal $g(A) \to (B \to C)$.
*   **Partial Application:** Tindakan menerapkan sebagian (bukan seluruh) argumen ke sebuah fungsi, menghasilkan fungsi baru dengan aritas (jumlah parameter) yang lebih rendah.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah serangkaian implementasi fungsional fundamental menggunakan Scala 3. Simpan dalam file bernama `FpFoundations.scala`.

```scala
package com.scaladev.foundations

import scala.annotation.tailrec

object FpFoundations:

  // 1. PURE VS IMPURE FUNCTION
  
  // Impure: Bergantung pada state global dan memutasi state luar
  private var globalTaxCounter = 0.0
  def calculateTaxImpure(amount: Double): Double =
    globalTaxCounter += amount * 0.1
    amount + globalTaxCounter

  // Pure: Deterministik, tanpa side-effect, referentially transparent
  def calculateTaxPure(amount: Double, taxRate: Double): Double =
    amount * (1.0 + taxRate)

  // 2. HIGHER-ORDER FUNCTION: Custom FoldLeft
  // Mengabstrak proses iterasi traversal koleksi secara immutabel
  @tailrec
  def customFoldLeft[A, B](list: List[A], accumulator: B)(combine: (B, A) => B): B =
    list match
      case Nil => accumulator
      case head :: tail => 
        val nextAcc = combine(accumulator, head)
        customFoldLeft(tail, nextAcc)(combine)

  // 3. CURRYING & PARTIAL APPLICATION
  def discountCalculator(discountType: String)(rate: Double)(price: Double): Double =
    discountType match
      case "VIP"      => price * (1.0 - (rate + 0.05))
      case "STANDARD" => price * (1.0 - rate)
      case _          => price

  // 4. TAIL-RECURSIVE REVERSE
  // Membalikkan urutan List dengan alokasi stack O(1)
  def reverseList[A](list: List[A]): List[A] =
    @tailrec
    def iterate(remaining: List[A], accumulated: List[A]): List[A] =
      remaining match
        case Nil => accumulated
        case head :: tail => iterate(tail, head :: accumulated)

    iterate(list, Nil)

  def main(args: Array[String]): Unit =
    println("=== Pembuktian Referential Transparency ===")
    val price = 100.0
    val taxRate = 0.11
    
    // Evaluasi 1
    val total1 = calculateTaxPure(price, taxRate) + calculateTaxPure(price, taxRate)
    // Evaluasi 2 (Substitusi nilai langsung)
    val total2 = 111.0 + 111.0
    println(s"Hasil Total1: $total1, Hasil Total2: $total2, Valid: ${total1 == total2}")

    println("\n=== Higher-Order Function (Custom FoldLeft) ===")
    val numbers = List(1, 2, 3, 4, 5)
    val sum = customFoldLeft(numbers, 0)((acc, elem) => acc + elem)
    val product = customFoldLeft(numbers, 1)(_ * _)
    println(s"Sum: $sum, Product: $product")

    println("\n=== Currying & Partial Application ===")
    // Memasang parameter pertama: discountType
    val vipDiscountConfig = discountCalculator("VIP")
    // Memasang parameter kedua: rate (menghasilkan fungsi parsial A => B)
    val tenPercentVipDiscount = vipDiscountConfig(0.10)
    
    // Aplikasi akhir pada data konkret
    val finalPrice = tenPercentVipDiscount(500.0)
    println(s"Final VIP Price (Diskon 10% + Bonus 5%): $finalPrice")

    println("\n=== Tail Recursion List Reversal ===")
    val originalList = List("A", "B", "C", "D")
    val reversed = reverseList(originalList)
    println(s"Original: $originalList")
    println(s"Reversed: $reversed")
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Konstruksi `customFoldLeft`
*   **Baris 20:** `@tailrec def customFoldLeft[A, B](list: List[A], accumulator: B)(combine: (B, A) => B): B`
    *   Menggunakan anotasi `@tailrec` untuk memaksa compiler memverifikasi optimasi tail call.
    *   Parameter tipe generik `[A, B]` memisahkan tipe elemen input (`A`) dan tipe hasil agregasi (`B`).
    *   Menggunakan multiple parameter list (currying) agar mempermudah type inference Scala pada parameter fungsi `combine`.
*   **Baris 22:** `list match`
    *   Pattern matching destruktif terhadap struktur aljabar `List`.
*   **Baris 23:** `case Nil => accumulator`
    *   *Base case*: Jika list kosong, kembalikan nilai akumulator saat ini. Tidak ada alokasi frame baru.
*   **Baris 24-26:** `case head :: tail => ... customFoldLeft(tail, nextAcc)(combine)`
    *   *Deconstruction*: `head` mengambil elemen pertama, `tail` mengambil sisa koleksi.
    *   Evaluasi ekspresi `combine(accumulator, head)` disimpan di variabel lokal `nextAcc`.
    *   Pemanggilan rekursif murni berada pada *tail position* (posisi absolut paling akhir dari cabang evaluasi). Tidak ada operasi tertunda setelah pemanggilan fungsi.

### Konstruksi `reverseList`
*   **Baris 35:** `@tailrec def iterate(remaining: List[A], accumulated: List[A]): List[A]`
    *   Helper function lokal dideklarasikan privat di dalam *scope* luar untuk menyembunyikan state akumulator dari konsumen API publik.
*   **Baris 38:** `case head :: tail => iterate(tail, head :: accumulated)`
    *   Operator `::` (*cons*) menempelkan `head` ke depan `accumulated` dalam waktu $O(1)$.
    *   Struktur *accumulated* yang baru dikirim ke panggilan `iterate` berikutnya tanpa memodifikasi `accumulated` lama.

---

## SEKSI 09 — STUDI KASUS NYATA

### Pipeline Pemrosesan Transaksi Finansial (Audit Engine)

**Domain Context:**
Sebuah payment gateway memproses puluhan ribu rekonsiliasi transaksi per detik. Komputasi harus:
1.  **Deterministic & Auditable:** Hasil rekonsiliasi histori mutasi rekening tidak boleh menghasilkan selisih akibat *race conditions* atau *dirty reads*.
2.  **Resilient against OutOfMemory / StackOverflow:** Riwayat mutasi suatu akun bisa mencapai $500.000$ transaksi. Rekursi yang ceroboh akan meruntuhkan node worker JVM akibat `StackOverflowError`.
3.  **Exception-Free:** Error sistemik (misal: saldo tidak cukup atau penipuan) tidak boleh melempar `java.lang.Exception`, melainkan harus dimodelkan sebagai representasi data murni (*Railway-Oriented Programming*).

**Solusi FP:**
Membangun sebuah *state machine engine* fungsional murni yang memproses *stream* transaksi secara berurutan (*batch*) menggunakan tail-recursive fold, menghasilkan ringkasan akun baru tanpa memutasi objek akun awal, dan mengembalikan penolakan secara terisolasi.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Simpan implementasi berikut di `src/main/scala/com/scaladev/ledger/TransactionEngine.scala`.

```scala
package com.scaladev.ledger

import scala.annotation.tailrec

// 1. DOMAIN MODELS (Immutable Case Classes & Sealed Types)
enum TransactionType:
  case Credit, Debit

case class Transaction(
    id: String,
    accountId: String,
    amount: BigDecimal,
    txType: TransactionType
)

case class AccountState(
    accountId: String,
    balance: BigDecimal,
    successfulTxCount: Int,
    failedTxCount: Int
)

enum TransactionResult:
  case Success(newState: AccountState, txId: String)
  case Rejected(currentState: AccountState, txId: String, reason: String)

case class LedgerReport(
    finalState: AccountState,
    rejectedTransactions: List[(String, String)] // Tuple: (TxId, Reason)
)

// 2. ENGINE LOGIC (Pure FP Engine)
object TransactionEngine:

  /**
   * Fungsi transisi status murni (State Transition Function)
   * f(State, Event) => State
   */
  def applyTransaction(
      state: AccountState,
      tx: Transaction
  ): TransactionResult =
    if tx.amount <= BigDecimal(0) then
      TransactionResult.Rejected(state, tx.id, "Nilai transaksi harus lebih besar dari nol")
    else
      tx.txType match
        case TransactionType.Credit =>
          val updated = state.copy(
            balance = state.balance + tx.amount,
            successfulTxCount = state.successfulTxCount + 1
          )
          TransactionResult.Success(updated, tx.id)

        case TransactionType.Debit =>
          if state.balance >= tx.amount then
            val updated = state.copy(
              balance = state.balance - tx.amount,
              successfulTxCount = state.successfulTxCount + 1
            )
            TransactionResult.Success(updated, tx.id)
          else
            TransactionResult.Rejected(state, tx.id, "Saldo tidak mencukupi untuk penarikan")

  /**
   * Memproses serangkaian transaksi menggunakan Tail Recursion
   * Memastikan O(1) stack space terlepas dari ukuran list.
   */
  def processLedger(
      initialState: AccountState,
      transactions: List[Transaction]
  ): LedgerReport =

    @tailrec
    def processLoop(
        remaining: List[Transaction],
        currentState: AccountState,
        rejectionsAcc: List[(String, String)]
    ): LedgerReport =
      remaining match
        case Nil =>
          // Pembalikan list rejections dilakukan sekali di akhir untuk menjaga konsistensi urutan
          LedgerReport(currentState, rejectionsAcc.reverse)

        case currentTx :: tail =>
          applyTransaction(currentState, currentTx) match
            case TransactionResult.Success(newState, _) =>
              processLoop(tail, newState, rejectionsAcc)

            case TransactionResult.Rejected(sameState, txId, reason) =>
              processLoop(tail, sameState, (txId, reason) :: rejectionsAcc)

    processLoop(transactions, initialState, Nil)

// 3. RUNNER VERIFICATION
object LedgerApp:
  def main(args: Array[String]): Unit =
    val account = AccountState(
      accountId = "ACC-ID-9921",
      balance = BigDecimal(1000.00),
      successfulTxCount = 0,
      failedTxCount = 0
    )

    // Simulasi Batch Transaksi
    val batch: List[Transaction] = List(
      Transaction("TX-001", "ACC-ID-9921", BigDecimal(250.00), TransactionType.Credit),
      Transaction("TX-002", "ACC-ID-9921", BigDecimal(1500.00), TransactionType.Debit), // Ditolak (Saldo: 1250)
      Transaction("TX-003", "ACC-ID-9921", BigDecimal(500.00), TransactionType.Debit),  // Berhasil (Saldo sisa: 750)
      Transaction("TX-004", "ACC-ID-9921", BigDecimal(-50.00), TransactionType.Credit)  // Ditolak (Amount invalid)
    )

    val report = TransactionEngine.processLedger(account, batch)

    println("=== HASIL PROSES LEDGER (AUDIT LOG) ===")
    println(s"Account ID        : ${report.finalState.accountId}")
    println(s"Final Balance     : $$${report.finalState.balance}")
    println(s"Sukses Terproses  : ${report.finalState.successfulTxCount}")
    println(s"Gagal Terproses   : ${report.rejectedTransactions.size}")
    
    println("\nRincian Penolakan:")
    report.rejectedTransactions.foreach { case (id, reason) =>
      println(s"- ID: $id | Alasan: $reason")
    }

    // Bukti Immutability Objek Awal
    println("\n=== INTEGRITAS DATA AWAL ===")
    println(s"Saldo Awal Objek Account: $$${account.balance}")
    assert(account.balance == BigDecimal(1000.00), "FATAL: Objek awal termutasi!")
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Dimensi Parameter | Pendekatan Imperatif / Mutasi State | Pemrograman Fungsional Murni (FP) |
| :--- | :--- | :--- |
| **Manajemen State** | *In-place mutation* (nilai di memori langsung ditimpa). | *State transformation* (menghasilkan salinan baru melalui *structural sharing*). |
| **Konkurensi & Paralelisme** | Sangat rentan *race-conditions*, butuh *locks*, *mutex*, atau `synchronized`. | Bebas *deadlock* dan *thread-safe* secara inheren karena data bersifat *read-only*. |
| **Alokasi Heap (Garbage Collector)** | Sangat rendah; objek dialokasikan sekali dan dimutasi berulang. | Lebih tinggi; terjadi instansiasi objek-objek pembungkus per iterasi. GC harus lebih aktif. |
| **Debugging & Traceability** | Sulit di-trace; nilai variabel bergantung pada histori mutasi waktu (*time-dependent*). | Sangat mudah; *Equational reasoning* memungkinkan fungsi diuji secara deterministik terisolasi. |
| **Call Stack Utilization** | Menggunakan loop primitif (`while`/`for`) dengan konsumsi stack $O(1)$. | Menggunakan rekursi; wajib memastikan TCO jika tidak ingin menabrak batasan memori stack. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Non-Tail-Recursive Frame Retention

Jika rekursi melakukan operasi matematika tambahan *setelah* pemanggilan fungsi anaknya, compiler membatalkan optimasi tail-call secara diam-diam (jika anotasi `@tailrec` diabaikan):

```scala
// BAHAYA: Bukan Tail Recursive! Operasi `+` dilakukan setelah recurse(tail) selesai.
def unsafeSum(list: List[Int]): Int = list match
  case Nil => 0
  case x :: xs => x + unsafeSum(xs) // Stack bertumpuk sebanyak panjang List
```

Solusi: Selalu gunakan anotasi `@tailrec` pada fungsi rekursif kustom. Compiler akan menolak mengompilasi program (*compile error*) jika fungsi gagal memenuhi kaidah TCO.

### 2. Evaluasi Lazy dan Eager pada Infinite Structure

Penggunaan fungsi pure pada infinite collection (`LazyList`) dapat menyebabkan kebocoran memori (*memory leak* / GC churn) jika pointer kepala (*head*) dipegang secara tidak sengaja oleh sebuah referensi `val`.

### 3. Purity yang Terkontaminasi oleh Exception

Melempar exception seperti `throw new IllegalArgumentException()` merusak *Referential Transparency*.

```scala
// Tidak Referentially Transparent:
def divide(a: Int, b: Int): Int = 
  if b == 0 then throw new ArithmeticException("Division by zero") else a / b
```

Jika fungsi ini digantikan dengan nilainya saat $b = 0$, runtime crash seketika terjadi di fase substitusi. Pendekatan fungsional yang benar adalah membungkus kemungkinan anomali dalam tipe aljabar: `Option[Int]` atau `Either[Error, Int]`.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Menggunakan `var` di Dalam Body Fungsi

```scala
// ANTI-PATTERN: Pemikiran Imperatif di Balut Fungsi
def calculateTotal(items: List[Double]): Double =
  var sum = 0.0
  for item <- items do
    sum += item
  sum
```

**Perbaikan:** Gunakan Higher-Order Function `foldLeft`:
```scala
// POLA FP IDIOMATIK
def calculateTotal(items: List[Double]): Double =
  items.foldLeft(0.0)(_ + _)
```

### Kesalahan 2: Menggunakan `List.apply(index)` untuk Akses Acak

Pemula sering mengira `list(5000)` setara efisiensinya dengan array `array[5000]`.
*   Struktur `List` di Scala adalah *Singly-Linked List*. Mengakses indeks ke-$N$ memerlukan transversal *pointer* sebesar $O(N)$.
*   Jika aplikasi butuh akses indeks acak yang intensif, gunakan `Vector` yang berbasis *32-way Radix Balanced Trie*, menyediakan akses dan update *effectively* $O(1)$ ($O(\log_{32} N)$).

### Kesalahan 3: Tidak Melakukan Reverse Akumulator pada Tail Recursion

Saat membangun list secara rekursif menggunakan cons `head :: acc`, data masuk dalam urutan terbalik (*LIFO*). Lupa mengeksekusi `.reverse` pada *base-case* akan menghasilkan *bug* inversi data di level produksi.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Total Functions Over Partial Functions:** Pastikan setiap fungsi fungsional mampu menangani seluruh spektrum domain input tanpa melempar crash. Jika input berada di luar rentang valid, kembalikan `Option` atau `Either`.
2.  **Enforce Immutability by Default:** 
    *   Haramkan kata kunci `var`.
    *   Gunakan hanya struktur koleksi dari package `scala.collection.immutable.*`.
    *   Gunakan `case class` untuk semua pemodelan data entitas (*domain entities*).
3.  **Compiler Warnings Enforcement:** Tambahkan konfigurasi berikut pada file `build.sbt` untuk memblokir kode kotor sejak tahapan kompilasi:
    ```scala
    scalacOptions ++= Seq(
      "-deprecation",
      "-feature",
      "-unchecked",
      "-Xfatal-warnings",
      "-Wnonunit-statement"
    )
    ```

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Primitive Boxing & Overhead

Generic types pada JVM (seperti `List[A]`) terikat pada tipe referensi `java.lang.Object`. Ketika memproses primitif numerik (`Int`, `Double`), JVM secara terpaksa melakukan proses *boxing/unboxing* yang membebani heap.

*Strategi Optimasi:*
*   Untuk pemrosesan numerik intensif berskala tinggi (*number crunching*), gunakan `Array` primitif lokal diisolasi di balik layer API murni, atau gunakan tipe struktur `IArray` (Scala 3 Zero-overhead Immutable Array).
*   Gunakan `opaque types` pada Scala 3 untuk membuat abstraksi domain murni (*Domain-Driven Design*) tanpa biaya alokasi memori tambahan runtime:
    ```scala
    opaque type AccountId = String
    object AccountId:
      def apply(raw: String): AccountId = raw
    ```

### 2. Memeriksa TCO Melalui Decompiler

Gunakan perkakas `javap` untuk memastikan compiler mengonversi pemanggilan rekursif menjadi instruksi iteratif `goto`:
```bash
javap -c target/scala-3.3.x/classes/com/scaladev/ledger/TransactionEngine$.class
```
Pastikan instruksi bytecode memuat label jump `goto` dan bukan `invokevirtual` rekursif berulang.

---

## SEKSI 16 — KEAMANAN & HARDENING

1.  **Immutability Menjamin Thread-Safety:** Kerentanan konkurensi (seperti *Race Condition TOCTOU - Time of Check to Time of Use*) hilang secara struktural karena thread worker tidak mampu memodifikasi nilai state yang sedang diinspeksi oleh thread validator.
2.  **Mitigasi Denial of Service (DoS) via Stack Exhaustion:** Serangan jaringan yang menyuntikkan payload bertingkat untuk memicu rekursi tak berujung (misal: JSON parsing bersarang) dinetralisir jika seluruh traversal dibangun di atas *Tail-Recursive Loops* atau struktur data terbatas.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Melakukan logging (`println` atau `logger.info`) di dalam *pure function* sejatinya adalah operasi I/O yang melanggar *Purity*. 

### Strategi Logging Tanpa Mengorbankan Purity

1.  **Pola Return Data Log (Writer Monad Principle):**
    Fungsi tidak mencetak ke *stdout*, melainkan mengembalikan *tuple* atau record yang menyertakan data hasil komputasi beserta catatan audit-nya (*telemetry data*):
    ```scala
    case class ExecutionLog(txId: String, durationMs: Long, message: String)
    case class ComputationResult[A](value: A, logs: List[ExecutionLog])
    ```
2.  **Tap/Wire Tap Pattern:**
    Gunakan titik intersepsi terisolasi pada batas tepi program (*boundary edge*) untuk logging, sehingga inti algoritma komputasi tetap murni:
    ```scala
    def tap[A](value: A)(sideEffect: A => Unit): A =
      sideEffect(value)
      value
    ```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

| Konsep | Definisi Singkat | Contoh Sintaks Scala 3 |
| :--- | :--- | :--- |
| **Pure Function** | Fungsi tanpa *side-effects*, deterministik. | `def add(a: Int, b: Int): Int = a + b` |
| **Referential Transparency** | Pemanggilan fungsi setara dengan nilainya. | Mengganti `add(2,3)` langsung dengan `5`. |
| **Higher-Order Function** | Fungsi yang menerima/mengembalikan fungsi. | `def exec(f: Int => String): String = f(42)` |
| **Currying** | Mengubah fungsi berparameter majemuk menjadi rantai fungsi tunggal. | `def f(x: Int)(y: Int): Int = x + y` |
| **Tail Recursion** | Rekursi yang dioptimasi compiler menjadi loop. | `@tailrec def loop(n: Int, acc: Int): Int` |
| **Cons Operator** | Menyambungkan elemen ke depan list ($O(1)$). | `val extended = head :: tail` |
| **FoldLeft** | Agregasi elemen koleksi dari arah kiri ke kanan. | `list.foldLeft(init)((acc, el) => acc + el)` |

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Basic

1.  **Pertanyaan:** Manakah di antara fungsi berikut yang melanggar prinsip *Referential Transparency*?
    *   A) `def multiply(a: Int, b: Int): Int = a * b`
    *   B) `def getGuid(seed: Long): Long = seed * 31L + 17L`
    *   C) `def fetchBalance(accId: String): Double = System.currentTimeMillis().toDouble`
    *   D) `def formatName(name: String): String = name.trim.toLowerCase`
    *   *Jawaban:* **C**
    *   *Penjelasan:* `System.currentTimeMillis()` bergantung pada clock internal CPU dan mengembalikan nilai yang selalu berubah setiap milidetik, menjadikannya non-deterministik.

2.  **Pertanyaan:** Mengapa anotasi `@tailrec` sangat disarankan saat menulis fungsi rekursif di Scala?
    *   A) Untuk mempercepat kompilasi bytecode.
    *   B) Agar Scala Compiler menghasilkan error jika fungsi tidak dapat dioptimasi menjadi loop berbasis flat stack.
    *   C) Agar memori heap di-garbage collect secara instan.
    *   D) Agar method tersebut dapat dieksekusi secara asynchronous di thread pool berbeda.
    *   *Jawaban:* **B**
    *   *Penjelasan:* `@tailrec` bertindak sebagai *compiler assertion*. Jika metode rekursif tidak berada pada posisi tail yang valid, proses kompilasi gagal, melindungi sistem dari potensi `StackOverflowError` runtime.

3.  **Pertanyaan:** Berapakah kompleksitas waktu untuk operasi *prepend* sebuah elemen pada immutable `List` di Scala (`x :: xs`)?
    *   A) $O(N)$
    *   B) $O(\log N)$
    *   C) $O(1)$
    *   D) $O(N^2)$
    *   *Jawaban:* **C**
    *   *Penjelasan:* Menggunakan *structural sharing*, node baru cukup menunjuk pointer *next*-nya ke node kepala list yang sudah ada. Tidak ada iterasi atau penyalinan elemen.

4.  **Pertanyaan:** Apa perbedaan fundamental antara *Currying* dan *Partial Application*?
    *   A) Currying hanya berlaku untuk fungsi dengan dua parameter.
    *   B) Currying mengubah bentuk fungsi menjadi rantai fungsi berparameter tunggal, sedangkan Partial Application menyediakan argumen nyata untuk sebagian parameter fungsi.
    *   C) Partial application hanya digunakan untuk fungsi `Unit`.
    *   D) Tidak ada perbedaan teknis; keduanya adalah istilah yang sama.
    *   *Jawaban:* **B**
    *   *Penjelasan:* Currying mentransformasi struktur penulisan aritas fungsi ($A \times B \to C \implies A \to (B \to C)$), sedangkan partial application mereduksi parameter dengan menyuplai argumen secara sebagian.

5.  **Pertanyaan:** Sifat utama dari koleksi *Immutable* saat terjadi manipulasi elemen adalah:
    *   A) Objek lama dimusnahkan secara paksa oleh runtime.
    *   B) Koleksi lama tetap utuh, dan dibuat koleksi baru yang berbagi node data yang relevan (*structural sharing*).
    *   C) Seluruh isi koleksi lama disalin ulang secara mendalam (*deep copy*).
    *   D) Memory JVM akan langsung terduplikasi secara penuh.
    *   *Jawaban:* **B**
    *   *Penjelasan:* Persistent data structures meminimalkan alokasi memori melalui *structural sharing*, di mana bagian data yang tidak berubah digunakan bersama oleh instansi baru dan instansi lama.

---

### Soal Intermediate

6.  **Pertanyaan:** Perhatikan potongan kode berikut:
    ```scala
    def calc(n: Int): Int =
      if n <= 1 then 1
      else n * calc(n - 1)
    ```
    Jika dipasang anotasi `@annotation.tailrec`, apa yang terjadi saat dikompilasi?
    *   A) Sukses terkompilasi dan berjalan cepat.
    *   B) Gagal kompilasi: *could not optimize @tailrec annotated method calc: it contains a recursive call not in tail position*.
    *   C) Gagal kompilasi: tipe kembalian salah.
    *   D) Program mengalami deadlock saat runtime.
    *   *Jawaban:* **B**
    *   *Penjelasan:* Operasi perkalian `n * ...` menandakan bahwa pemanggilan rekursif belum tuntas; JVM harus mempertahankan frame stack lokal untuk menunggu hasil `calc(n - 1)` sebelum dapat mengalikannya dengan `n`.

7.  **Pertanyaan:** Di balik layar, ekspresi lambda Scala `(x: Int, y: Int) => x + y` direpresentasikan pada tingkat runtime JVM sebagai:
    *   A) Method statis murni tanpa alokasi class.
    *   B) Objek turunan dari trait `scala.Function2[Int, Int, Int]`.
    *   C) Struktur array primitif `int[]`.
    *   D) Pointer C++ native.
    *   *Jawaban:* **B**
    *   *Penjelasan:* Fungsi dengan dua parameter dipetakan compiler ke instansi trait `scala.Function2`, dengan metode entry point `.apply(v1, v2)`.

8.  **Pertanyaan:** Apa implikasi performa dari penggunaan fungsi fungsional `map` dan `filter` secara berantai pada `List` yang besar tanpa menggunakan `.view`?
    *   A) StackOverflowError seketika.
    *   B) Terbentuknya koleksi data *intermediate* (sementara) di heap memori pada setiap langkah pipeline rantai.
    *   C) Otomatis dieksekusi secara paralel menggunakan seluruh core CPU.
    *   D) Tidak ada penalti memori apa pun.
    *   *Jawaban:* **B**
    *   *Penjelasan:* Pada strict collection seperti `List`, setiap pemanggilan HOF seperti `map` atau `filter` akan mengevaluasi seluruh elemen dan mengalokasikan List baru di memori sebelum rantai pemrosesan berikutnya dimulai.

9.  **Pertanyaan:** Manakah transformasi refactoring yang paling tepat agar fungsi rekursif faktorial menjadi valid di bawah optimasi `@tailrec`?
    *   A)
        ```scala
        @tailrec
        def fact(n: Int, acc: Int = 1): Int =
          if n <= 1 then acc else fact(n - 1, acc * n)
        ```
    *   B)
        ```scala
        @tailrec
        def fact(n: Int): Int =
          if n <= 1 then 1 else fact(n - 1) * n
        ```
    *   C) Mengganti `def` dengan `lazy val`.
    *   D) Menggunakan tipe data `Option[Int]`.
    *   *Jawaban:* **A**
    *   *Penjelasan:* Menggunakan akumulator `acc` memindahkan komputasi perkalian ke depan parameter pemanggilan rekursif, sehingga pemanggilan rekursif berada di posisi absolut tail (*tail-position*).

10. **Pertanyaan:** Bagaimana Functional Programming menangani operasi I/O (seperti pemanggilan database atau HTTP request) tanpa melanggar prinsip kebersihan kode (*purity*)?
    *   A) I/O dilarang secara absolut dalam bahasa Scala.
    *   B) Mengisolasi efek samping di layer terluar arsitektur (*edge of the system*) atau memodelkannya sebagai deskripsi nilai data komputasi (konsep *IO Monad*).
    *   C) Menggunakan keyword `volatile` pada semua variabel koneksi.
    *   D) Mengonversi seluruh operasi I/O menjadi tipe `String`.
    *   *Jawaban:* **B**
    *   *Penjelasan:* FP memisahkan secara tegas antara *deklarasi program* (murni) dan *eksekusi efek* (tidak murni). Kode domain tetap murni dan referentially transparent, sementara efek samping didorong ke tepi sistem (*boundaries*).

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Mini Project: In-Memory Pure FP Order Book Matching Engine

**Deskripsi Permasalahan:**
Bangun komponen inti mesin pencocokan order (*Order Book Matching Engine*) untuk perdagangan aset digital secara fungsional murni. Sistem bertugas mengantrekan order pembelian (*Buy*) dan penjualan (*Sell*), serta mencocokkan harga yang bersesuaian (*matching order*).

**Kebutuhan Spesifikasi Teknis:**
1.  **Immutability:** Tidak boleh menggunakan keyword `var` atau koleksi *mutable*.
2.  **Domain Entities:**
    *   `OrderType`: `Buy`, `Sell`
    *   `Order`: `id: String`, `traderId: String`, `orderType: OrderType`, `price: BigDecimal`, `quantity: Long`
    *   `Trade`: `buyOrderId: String`, `sellOrderId: String`, `matchedPrice: BigDecimal`, `matchedQuantity: Long`
    *   `OrderBook`: Berisi dua antrean: `bids: List[Order]` (pembelian, diurutkan dari harga tertinggi ke terendah) dan `asks: List[Order]` (penjualan, diurutkan dari harga terendah ke tertinggi).
3.  **Kebutuhan Algoritma Pure:**
    *   Fungsi `placeOrder(book: OrderBook, order: Order): (OrderBook, List[Trade])`
    *   Jika sebuah `Buy` order masuk dengan harga $\ge$ harga `Sell` terendah di antrean `asks`, lakukan eksekusi `Trade`.
    *   Eksekusi matching harus berbasis rekursif ekor (`@tailrec`). Order dapat terpenuhi sebagian (*partially filled*) atau terpenuhi penuh (*fully filled*).
    *   Jika order masih bersisa setelah seluruh lawan matching habis, sisa order dimasukkan ke antrean buku yang bersesuaian.

**Template Awal (Boilerplate):**
```scala
package com.scaladev.orderbook

import scala.annotation.tailrec

enum OrderType:
  case Buy, Sell

case class Order(
    id: String,
    traderId: String,
    orderType: OrderType,
    price: BigDecimal,
    quantity: Long
)

case class Trade(
    buyOrderId: String,
    sellOrderId: String,
    matchedPrice: BigDecimal,
    matchedQuantity: Long
)

case class OrderBook(
    bids: List[Order], // Disortir DESC berdasarkan price
    asks: List[Order]  // Disortir ASC berdasarkan price
)

object Engine:
  def emptyBook: OrderBook = OrderBook(Nil, Nil)

  def placeOrder(book: OrderBook, newOrder: Order): (OrderBook, List[Trade]) =
    // TODO: Implementasikan logika murni pencocokan orderbook di sini
    ???
```

**Rubrik Penilaian Pengujian:**
1.  **Purity Proof:** `placeOrder` tidak memodifikasi objek `book` lama.
2.  **TCO Verification:** Loop pencocokan transaksi dalam antrean berjalan di bawah method beranotasi `@tailrec`.
3.  **Edge Cases Check:**
    *   Order matched sempurna (kuantitas buy == sell).
    *   Order partially matched (kuantitas buy > sell dan sebaliknya).
    *   Order tidak match sama sekali (langsung masuk ke book).
    *   Nilai nominal transaksi bernilai nol atau negatif ditolak secara elegan.