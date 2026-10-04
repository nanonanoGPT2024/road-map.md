# BAB 02: Quiz, Challenge, & Knowledge Check
**Object-Oriented Engineering & Functional Core**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Virtual Method Dispatch vs Static Binding
Jelaskan secara mendalam perbedaan mekanisme eksekusi pada level JVM bytecode antara pemanggilan metode melalui instruksi `invokevirtual`, `invokeinterface`, `invokestatic`, dan `invokespecial`. Bagaimana JVM memanfaatkan *vtable* (Virtual Method Table) dan *itable* (Interface Table) dalam memetakan target metode secara dinamis saat *polymorphism* terjadi pada saat runtime?

### Soal 1.2: Semantik dan Batasan Rekayasa Java Records
Mengapa Java `record` didesain secara arsitektural sebagai representasi *transparent carrier for immutable data*? Analisis mengapa spesifikasi Java secara ketat melarang `record` untuk memperluas (*extends*) kelas lain dan tidak mengizinkan penambahan *instance fields* non-komponen, serta bagaimana hal ini menjamin invariant *state-driven equality* (kontrak `equals`, `hashCode`, dan `toString`).

### Soal 1.3: Algebraic Data Types (ADT) via Sealed Types dan Pattern Matching
Bandingkan pendekatan pemodelan domain tertutup (*closed domain modeling*) menggunakan *GoF Visitor Pattern* klasik dengan kombinasi *Sealed Interfaces/Classes* dan *Pattern Matching for switch* pada Java modern (Java 17/21). Mengapa *exhaustiveness checking* oleh kompilator pada sealed hierarchies mengeliminasi kebutuhan penanganan `default` branch atau lemparan `IllegalArgumentException` pada runtime?

### Soal 1.4: Mekanisme Desugaring Lambdas dan `invokedynamic`
Berbeda dengan *Anonymous Inner Classes* yang menghasilkan file `.class` terpisah untuk setiap instansiasi, bagaimana JVM mengeksekusi Lambda Expressions menggunakan instruksi `invokedynamic` dan bootstrap method `LambdaMetafactory`? Apa keuntungan arsitektural pendekatan ini terhadap jejak memori (*metaspace memory footprint*) dan optimasi runtime JIT?

### Soal 1.5: Desain Monadik dan Anti-Pattern `Optional<T>`
Jelaskan filosofi perancangan tipe `Optional<T>` dalam ekosistem Java. Analisis 3 (tiga) skenario anti-pattern penggunaan `Optional` yang sering ditemui di lingkungan *enterprise* (misalnya: parameter metode, field pada entitas persistent, atau pembungkus koleksi) dan jelaskan dampaknya terhadap alokasi memori heap, fragmentasi memori, serta serialisasi.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Generics Type Erasure, Heap Pollution, dan Synthetic Bridge Methods
Perhatikan kode berikut:
```java
public interface Producer<T> {
    T produce();
}
public class StringProducer implements Producer<String> {
    @Override
    public String produce() {
        return "payload";
    }
}
```
Ketika dikompilasi, bytecode menghasilkan *synthetic bridge method* `public Object produce()`.
1. Mengapa kompilator harus membangkitkan *bridge method* tersebut?
2. Bagaimana mekanisme JVM menjaga integritas *subtyping polymorphism* saat pemanggilan polimorfis dilakukan melalui referensi `Producer` mentah?
3. Jelaskan bagaimana skenario *heap pollution* dapat terjadi saat memadukan generic type dengan varargs (`@SafeVarargs`).

### Soal 2.2: Contention pada `ForkJoinPool.commonPool()` via Parallel Streams
Jelaskan bahaya arsitektural penggunaan `.parallelStream()` untuk operasi yang mengeksekusi *blocking I/O* (seperti HTTP call atau query database). Bagaimana `ForkJoinPool.commonPool()` menangani thread starvation, mengapa *work-stealing algorithm* menjadi tidak efektif dalam skenario blocking, dan bagaimana cara yang benar mengisolasi pemrosesan paralel fungsional di luar pool default aplikasi?

### Soal 2.3: Spliterator Anatomy dan Pipeline Fusion
Bagaimana Stream pipeline mengoptimalkan operasi melalui *horizontal loop fusion*? Jelaskan fungsi metodologis dari karakteristik `Spliterator` (seperti `ORDERED`, `SIZED`, `SUBSIZED`, `NONNULL`, `IMMUTABLE`, dan `CONCURRENT`) dalam menentukan apakah runtime Stream akan mengeksekusi pipeline secara lazy, melakukan short-circuiting, atau mengoptimalkan alokasi memori internal buffer (misalnya pada operasi `.distinct()` atau `.sorted()`).

### Soal 2.4: Mutasi State Objek sebagai Key pada Hashing Collections
Sebuah objek domain `UserSession` memiliki field mutable `status`. Objek ini dimasukkan ke dalam `java.util.HashSet<UserSession>`. Beberapa saat kemudian, `status` diubah dari `PENDING` menjadi `ACTIVE`. Ketika dieksekusi `set.contains(session)`, sistem mengembalikan nilai `false`, meskipun objek tersebut secara fisik masih berada di dalam koleksi. 
Jelaskan anomali ini berdasarkan mekanisme internal hashing (perhitungan `bucketIndex`, `hashCode()`, dan transversal linked list/red-black tree) serta mitigasi desain berbasis immutability murni.

### Soal 2.5: Object Memory Layout dan Compressed OOPs
Pada arsitektur 64-bit JVM dengan *Compressed OOPs* (*Ordinary Object Pointers*) aktif:
1. Hitung perkiraan konsumsi memori heap untuk sebuah objek `java.lang.Integer` dibandingkan dengan tipe primitif `int`.
2. Uraikan komponen-komponen *Object Header* (Mark Word, Klass Word), data payload, dan *alignment padding*.
3. Mengapa pemrosesan stream koleksi wrapper numerik (`Stream<Long>`) menimbulkan degradasi throughput drastis dibandingkan specialized stream (`LongStream`) akibat fenomena *cache locality* dan *pointer chasing*?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Thread Exhaustion Akibat Parallel Stream pada Core Payment Gateway
* **Kasus:**
  Sebuah microservice payment gateway berbasis Spring Boot mengalami lonjakan drastis pada *P99 latency* (dari 80ms menjadi 18.000ms), diikuti dengan penolakan request (`503 Service Unavailable`). Profiling menggunakan JFR (Java Flight Recorder) menunjukkan puluhan thread HTTP worker Tomcat beralih ke state `TIMED_WAITING` atau `WAITING`.
  Setelah dilakukan *thread dump analysis*, ditemukan cuplikan kode pada modul verifikasi transaksi:
  ```java
  public List<FraudCheckResult> evaluateTransactions(List<Transaction> transactions) {
      return transactions.parallelStream()
              .map(tx -> thirdPartyFraudClient.verify(tx)) // Pemanggilan REST API eksternal (Ramping 150-300ms)
              .toList();
  }
  ```
* **Pertanyaan Diagnostik:**
  1. Identifikasi akar masalah (*root cause*) kegagalan sistemik di atas dan hubungannya dengan arsitektur threading runtime JVM. Mengapa HTTP server worker thread ikut terdampak padahal kode tersebut hanya memproses batch internal?
  2. Rancang refactoring arsitektur kode tersebut menggunakan pendekatan *ExecutorService* terisolasi atau *Virtual Threads* (Java 21) dengan tetap mempertahankan prinsip pemrosesan terkelola (*structured concurrency* atau *bounded concurrency*).

---

### Skenario B: Race Condition dan State Mutation Akibat Stream Side-Effects
* **Kasus:**
  Sebuah modul *billing aggregation* bulanan menghasilkan laporan total piutang yang tidak konsisten saat dijalankan pada dataset produksi berskala 5.000.000 records. Nilai kalkulasi akhir berubah-ubah setiap kali job batch dieksekusi. 
  Pemeriksaan kode sumber memperlihatkan implementasi berikut:
  ```java
  public BillingSummary calculateSummary(List<Invoice> invoices) {
      List<Invoice> processedInvoices = new ArrayList<>();
      BigDecimal totalAmount = BigDecimal.ZERO;
      
      invoices.parallelStream().forEach(inv -> {
          if (inv.getStatus() == InvoiceStatus.APPROVED) {
              processedInvoices.add(inv);
              totalAmount.add(inv.getAmount()); // Mutasi lokal
          }
      });
      return new BillingSummary(processedInvoices.size(), totalAmount);
  }
  ```
* **Pertanyaan Diagnostik:**
  1. Analisis 2 (dua) kesalahan fatal terkait *concurrency*, *thread-safety*, dan karakteristik operasi `BigDecimal` dalam kode di atas.
  2. Jelaskan bahaya *thread interference* dan *memory visibility* pada `ArrayList` saat diakses bersamaan tanpa sinkronisasi.
  3. Tuliskan kembali solusi tersebut secara fungsional murni (*pure functional reduction*) menggunakan Stream API standard tanpa *side-effects*, memanfaatkan `Collector` kustom atau reduksi paralel bawaan yang *thread-safe* dan deterministik.

---

### Skenario C: The Fragile Base Class Dilemma dan Refactoring Domain Core
* **Kasus:**
  Sebuah sistem ERP logistik memiliki hierarki inheritance warisan (*legacy*) sedalam 6 tingkat:
  `Object` $\rightarrow$ `BaseEntity` $\rightarrow$ `AuditableDomain` $\rightarrow$ `ShipmentItem` $\rightarrow$ `PerishableShipmentItem` $\rightarrow$ `ColdChainPerishableItem`.
  Tim teknik menghadapi masalah:
  - Setiap perubahan pada konstruktor `BaseEntity` atau metode validasi di `AuditableDomain` merusak puluhan unit test pada sub-kelas.
  - Sub-kelas `ColdChainPerishableItem` mewarisi properti yang tidak lagi relevan akibat regulasi baru, namun metode override dipaksa melempar `UnsupportedOperationException`.
  - Terjadi masalah circular dependency saat serialisasi JSON karena relasi dua arah tersembunyi di dalam kelas induk.
* **Pertanyaan Diagnostik:**
  1. Berdasarkan prinsip OOP modern (*Composition over Inheritance* dan *Liskov Substitution Principle*), analisislah mengapa hierarki warisan dalam skala tersebut dianggap sebagai *architectural smell*.
  2. Rancang strategi refactoring komprehensif untuk membongkar hierarki tersebut menjadi model berorientasi komponen (*composition-based*) menggunakan fitur Java modern: gabungan *Record*, *Sealed Interfaces*, dan delegasi dependensi via interface kecil (*role interfaces*).

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Financial Ledger Pipeline Engine
Implementasikan sebuah mesin pemrosesan buku besar (*financial ledger engine*) dalam format mini-framework (pure Java 21+, tanpa third-party library) yang memadukan keunggulan **Object-Oriented Domain Modeling** yang kuat dan **Functional Core Pipeline**.

#### 1. Problem Statement
Sistem harus memproses aliran transaksi keuangan dengan tipe transaksi yang beragam. Setiap transaksi harus divalidasi, dikenakan serangkaian aturan bisnis (pajak, fee, limit saldo), dan diagregasikan ke dalam status akun akhir (*account balance state*) secara thread-safe, immutable, dan berkinerja tinggi.

#### 2. Functional Requirements
* **Domain Modeling (OOP/ADT):**
  Definisikan domain model menggunakan *Sealed Interface* `Transaction` yang hanya boleh diturunkan oleh record tipe berikut:
  * `Deposit(UUID id, String accountId, BigDecimal amount, Instant timestamp)`
  * `Withdrawal(UUID id, String accountId, BigDecimal amount, Instant timestamp)`
  * `Transfer(UUID id, String sourceAccountId, String targetAccountId, BigDecimal amount, Instant timestamp)`
  * `FeeDeduction(UUID id, String accountId, BigDecimal feeAmount, FeeType type, Instant timestamp)`
* **Business Rule Validation:**
  Buat rantai validasi fungsional menggunakan representasi *Higher-Order Functions* (misal: `Function<Transaction, ValidationResult>` atau *Combinator Pattern*) yang dapat dikomposisikan secara dinamis:
  * Amount harus bernilai positif (> 0).
  * Akun tidak boleh berstatus *frozen* (gunakan model konteks akun immutable).
  * Batas penarikan tunggal maksimal tidak melebihi aturan bisnis.
* **State Processing Pipeline (Functional Core):**
  Rancang engine yang mengonsumsi `Stream<Transaction>` dan memproses perubahan saldo menggunakan implementasi kustom:
  * Terapkan pattern matching switch untuk mengekstrak mutasi saldo per akun.
  * Hasilkan agregasi data akhir berupa `LedgerReport` yang bersifat immutable (Record), mencakup: total turnover, total volume transaksi per tipe, dan saldo akhir tiap akun.
  * Hindari penggunaan locking primitif (`synchronized`) dan shared-mutable variable.

#### 3. Constraints
* **Immutability Mutlak:** Seluruh kelas domain dan representasi state akumulasi dilarang memiliki setter atau field non-final.
* **No Side-Effects in Lambdas:** Lambda expression yang digunakan dalam pipeline Stream tidak boleh memodifikasi referensi di luar cakupan eksekusinya.
* **Memory & Performance Awareness:** Operasi agregasi tidak boleh mengumpulkan jutaan objek interim ke dalam koleksi intermediate jika tidak dibutuhkan; gunakan pendekatan *single-pass stream reduction* (Custom `Collector`).

#### 4. Expected Output & Verification
Buat sebuah kelas eksekutor `LedgerPipelineTest` yang menyimulasikan pemrosesan 500.000 transaksi acak, dengan validasi:
1. Tidak ada `NullPointerException` atau unchecked exceptions yang lolos tak tertangani.
2. Konsistensi saldo neraca: `Total Deposit == Saldo Akhir Semua Akun + Total Withdrawal + Total Fee`.
3. Demonstrasi penanganan invalid transactions yang terisolasi ke dalam *dead-letter collection* fungsional tanpa memutus jalannya pipeline.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan esensial virtual dispatch vs static dispatch pada level bytecode (`invokevirtual`, `invokestatic`, `invokespecial`, `invokeinterface`).
- [ ] Siklus hidup memori objek di HotSpot JVM, struktur Object Header (Mark Word & Klass Pointer), serta efek Compressed OOPs terhadap memori footprint.
- [ ] Arsitektur evaluasi *lazy* Stream API, mekanisme *intermediate loop fusion*, dan implementasi `Spliterator`.
- [ ] Bahaya penggunaan `ForkJoinPool.commonPool()` untuk beban kerja Blocking I/O pada paralel stream.
- [ ] Desugaring lambda expression via `invokedynamic` dan perbedaannya secara struktural terhadap anonymous inner classes.
- [ ] Filosofi Algebraic Data Types (ADT) pada Java menggunakan kombinasi *Sealed Types* dan *Records*.
- [ ] Batasan kontrak kesetaraan (`equals` & `hashCode`) serta anomali mutasi state pada hashing data structure.
- [ ] Aturan PECS (*Producer Extends, Consumer Super*) pada Generics wildcard dan mekanisme *Bridge Methods*.

### Saya tidak perlu menghafal:
- [ ] Nilai bit exact dari Mark Word bitmask pada status locking JVM (biased, thin lock, fat lock).
- [ ] Konstanta numerik opcode bytecode internal JVM untuk setiap instruksi stack machine.
- [ ] Seluruh signature metode bawaan dari package `java.util.function` (cukup pahami pola intinya: `Supplier`, `Consumer`, `Function`, `Predicate`, `UnaryOperator`).
- [ ] Nama algoritma pengurutan internal JVM (Timsort/Dual-Pivot Quicksort) baris per baris.

### Saya harus bisa melakukan:
- [ ] Mengonversi hierarki OOP kompleks yang rapuh (*deep inheritance tree*) menjadi arsitektur fungsional terkomposisi berbasis *Record* dan *Sealed Hierarchies*.
- [ ] Mengimplementasikan custom `java.util.stream.Collector` yang thread-safe, efisien, dan mendukung eksekusi paralel murni (*accumulate, combine, finish*).
- [ ] Memecahkan masalah konkurensi data race yang timbul akibat side-effects mutasi data pada Stream pipeline.
- [ ] Menganalisis Java Flight Recorder (JFR) atau Thread Dump untuk mengidentifikasi bottleneck starvation akibat penggunaan `parallelStream()` yang salah.
- [ ] Merancang API monadik yang aman dan bersih menggunakan `Optional<T>` hanya pada boundary batas domain/metode tanpa mencemari state internal objek.