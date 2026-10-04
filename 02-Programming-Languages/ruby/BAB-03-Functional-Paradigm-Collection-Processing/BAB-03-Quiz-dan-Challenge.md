# BAB 03: Quiz, Challenge, & Knowledge Check
**Functional Paradigm & Collection Processing**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Semantik Kontrol Alur & Penegakan Arity: `Proc` vs `lambda`**
   Jelaskan secara mendalam perbedaan arsitektural antara objek `Proc` standar (`Proc.new` / `proc`) dan `lambda` (`->() {}` / `lambda`) dalam Ruby, khususnya terkait:
   - Perilaku keyword `return` terhadap call-stack dan *lexical enclosing scope*.
   - Mekanisme validasi argumen (*arity checking*) saat jumlah parameter formal tidak sesuai dengan parameter aktual.

2. **Protokol Kontrak `Enumerable` & Primitif `#each`**
   Modul `Enumerable` menyediakan lusinan method fungsional tingkat tinggi (`map`, `select`, `reduce`, `any?`, dll.). Jelaskan kontrak minimal yang harus dipenuhi oleh sebuah class agar dapat meng-include `Enumerable` secara valid, dan bagaimana modul tersebut memanfaatkan single-entry point `#each` untuk menurunkan (*derive*) seluruh algoritma pemrosesan koleksi secara deterministik.

3. **Mekanisme Coercion Operator `&` dan Protokol `#to_proc`**
   Ketika kita menulis ekspresi idiomatis `users.map(&:name)`, jelaskan langkah demi langkah yang dieksekusi oleh runtime Ruby pada level VM:
   - Bagaimana operator unari `&` memicu protokol `#to_proc` pada instance `Symbol`.
   - Bentuk representasi internal objek closure yang dihasilkan dan bagaimana argumen pertama di-dispatch ke method tujuan.

4. **Purity vs In-Place Mutation pada Reduksi Koleksi**
   Evaluasi method `#reduce` (alias `#inject`). Mengapa penggunaan mutasi in-place (seperti `acc << item` atau `acc.merge!(item)`) di dalam blok `#reduce` sering kali dianggap sebagai antipattern fungsional sekaligus sumber bug konkurensi tersembunyi, meskipun menawarkan efisiensi alokasi memori dibanding `acc + [item]` atau `acc.merge(item)`?

5. **Higher-Order Functions dan Aplikasi Parsial via `Proc#curry`**
   Definisikan konsep *Higher-Order Function* (HOF) dalam konteks Ruby di mana fungsi bukanlah *first-class citizen* murni melainkan direpresentasikan via objek `Method` atau `Proc`. Jelaskan bagaimana `Proc#curry` bekerja secara internal dalam memecah fungsi bervalensi multi-argumen ($n$-arity) menjadi rantai pemanggilan fungsi unari ($1$-arity).

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Trade-off Kinerja Internal: `Enumerator::Lazy` vs Standard Eager Evaluation**
   Secara teoritis, `Enumerator::Lazy` mengeliminasi alokasi intermediate array pada pipeline pemrosesan data panjang (`array.lazy.map{}.select{}.to_a`). Namun, pada dataset berukuran kecil hingga menengah ($N < 10.000$), eksekusi rantai `lazy` justru terbukti lebih lambat secara signifikan daripada evaluasi eager standar. Analisis penyebab fenomena ini dari perspektif *overhead alokasi objek enumerator wrapper*, *fiber/block yield dispatch latency*, dan optimasi JIT/CRuby VM.

2. **Closure Retention & Memory Leak via `Binding` Object**
   Perhatikan cuplikan kode berikut:
   ```ruby
   def generate_multiplier(factor)
     heavy_payload = SecureRandom.bytes(50 * 1024 * 1024) # 50 MB
     ->(x) { x * factor }
   end

   multiplier = generate_multiplier(10)
   ```
   Meskipun variabel `heavy_payload` tidak dipanggil di dalam tubuh lambda, objek byte array tersebut tetap tidak dapat dibersihkan oleh Garbage Collector (GC) selama lambda `multiplier` masih hidup. Jelaskan mengapa *binding environment* Ruby mempertahankan seluruh *lexical scope frame* dan bagaimana cara mengisolasi closure agar tidak menahan referensi memori yang tidak terpakai.

3. **Allocation Churn: Analisis Memory Footprint pada `flat_map` vs `map.flatten(1)`**
   Jelaskan perbedaan alokasi memori internal antara `collection.flat_map { |x| transform(x) }` dan `collection.map { |x| transform(x) }.flatten(1)`. Mengapa `flat_map` meminimalkan tekanan pada *GC minor mark-and-sweep* dan kapan `flat_map` tetap menghasilkan alokasi perantara jika transformator mengembalikan enumerator alih-alih array konkret?

4. **Optimasi YJIT terhadap `Symbol#to_proc` vs Block Literal Eksplisit**
   Dalam versi Ruby modern yang dilengkapi YJIT (Yet Another Ruby JIT), bandingkan efisiensi eksekusi antara pemanggilan block eksplisit:
   ```ruby
   records.map { |r| r.id }
   ```
   dengan implicit coercion:
   ```ruby
   records.map(&:id)
   ```
   Bagaimana YJIT mengoptimalkan *invalidation check* dan *method inline caching* pada kedua pendekatan tersebut?

5. **Shallow Freeze vs Deep Immutability & Persistent Data Structures**
   Method `#freeze` pada Ruby standar hanya melakukan *shallow freezing* pada pointer array/hash terluar. 
   - Buktikan bagaimana integritas data tetap dapat terkompromi pada nested collection yang di-freeze secara konvensional.
   - Analisis trade-off performa (*CPU cycle* vs *memory allocation*) dari implementasi deep copy rekursif fungsional (`dup`/`clone`) versus adopsi library struktur data persisten struktural berbasis *Hash Array Mapped Tries* (HAMT).

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Worker Background OOM pada Streaming Data Skala Besar
Sebuah background job worker (Sidekiq) yang berjalan pada container berkapasitas RAM ketat (512 MB) mengalami insiden crash berkala akibat *Out of Memory* (OOMKilled). Worker tersebut bertugas memvalidasi, mentransformasi, dan memfilter rekonsiliasi data transaksi dari file NDJSON (Newline Delimited JSON) harian berukuran 4.2 GB dengan rata-rata 15 juta baris. 

Kode eksisting yang ditulis oleh engineer terdahulu:
```ruby
def process_reconciliation(file_path)
  File.readlines(file_path)
    .map { |line| JSON.parse(line, symbolize_names: true) }
    .select { |txn| txn[:status] == "SETTLED" }
    .map { |txn| normalize_transaction(txn) }
    .each_slice(1000) { |batch| DatabaseUpserter.bulk_insert(batch) }
end
```
**Pertanyaan Diagnostik:**
1. Bedah secara runut mengapa metode `File.readlines` yang dikombinasikan dengan chaining array standard langsung menyebabkan memory explosion seketika.
2. Rekonstruksi arsitektur pipeline fungsional di atas menggunakan `File.open`, `Enumerator`, dan `Enumerator::Lazy` (atau streaming chunking) agar footprint memori konstan berada di bawah 64 MB heap consumption sepanjang proses berlangsung.
3. Bagaimana Anda menguji dan membuktikan bahwa implementasi baru bersifat zero-array-allocation pada tahap read-and-parse sebelum chunking?

---

### Skenario B: Race Condition & Silent Mutation pada Multi-threaded Web Server
Sebuah aplikasi web berbasis Puma running dalam mode clustered + multi-threaded (5 worker processes, 16 threads per worker) menyajikan dashboard analytics. Terdapat modul agregasi yang menggunakan data cache bersama (in-memory process cache):

```ruby
class MetricsAggregator
  # Data di-cache dalam proses memori worker Puma
  SHARED_DATA = [
    { id: 1, region: "APAC", values: [100, 200, 300] },
    { id: 2, region: "EMEA", values: [400, 500] },
    { id: 3, region: "US",   values: [600, 700, 800] }
  ].freeze

  def self.summarize_for_region(target_region, modifier_factor)
    dataset = SHARED_DATA.select { |item| item[:region] == target_region }
    
    dataset.each do |record|
      # Modifikasi metrik temporer untuk kalkulasi dashboard
      record[:values].map! { |v| v * modifier_factor }
    end

    total = dataset.flat_map { |record| record[:values] }.sum
    { region: target_region, total: total }
  end
end
```

Setelah beberapa jam di production, metrik yang dihasilkan dashboard melenceng secara eksponensial dan tidak konsisten antar request concurrent.

**Pertanyaan Diagnostik:**
1. Tunjukkan letak bug mutasi tersembunyi yang menyebabkan terjadinya *data corruption* antar-thread, meskipun konstanta `SHARED_DATA` telah di-`freeze`.
2. Jelaskan mengapa *Global VM Lock* (GVL) pada CRuby tidak melindungi aplikasi dari inkonsistensi state pada kasus mutasi koleksi di atas.
3. Desain ulang method `summarize_for_region` menggunakan pendekatan pure functional pipeline (tanpa mutasi in-place dan tanpa dependensi thread-locking eksplisit) sehingga aman dieksekusi secara konkuren (*thread-safe*).

---

### Skenario C: Refactoring Service Object Monolitik ke Composable Pipeline
Aplikasi Core Banking Anda memiliki Service Object monolitik sepanjang 400 baris untuk *Loan Application Approval*. Kode tersebut penuh dengan deep nesting conditional (`if-else`), mutation flag (`application.approved = true; application.score += 10`), serta penyebaran error handling yang tidak konsisten.

Arsitektur sistem baru menuntut penerapan pola **Railway-Oriented Programming (ROP)** / Monadic Data Flow murni menggunakan Ruby standard primitives (tanpa external gem seperti `dry-monads`).

**Pertanyaan Diagnostik:**
1. Bagaimana Anda merancang kelas atau representasi fungsional `Result` (`Success(value)` dan `Failure(error)`) yang mengimplementasikan method `#bind` (atau `#flat_map`) dan `#map` untuk memfasilitasi *monadic chaining*?
2. Demonstrasikan bagaimana Anda merefaktor 3 tahapan pemrosesan berikut:
   - `validate_identity(input)`
   - `calculate_credit_score(validated_input)`
   - `disburse_loan(scored_input)`
   menjadi sebuah pipeline komposable di mana kegagalan pada satu tahap langsung membypass tahap berikutnya dan mengembalikan error context secara murni tanpa melempar exception (`raise`).
3. Bandingkan trade-off arsitektural pendekatan monadic ini terhadap *idiomatic Ruby exception handling* (`rescue`) dalam aspek: kemudahan debugging (stack trace), CPU performance cost, dan testability.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance, Zero-Mutation Streaming Pipeline Engine
Bangun sebuah generic transformation engine bernama `StreamPipeline` yang memanfaatkan prinsip-prinsip murni fungsional Ruby, beroperasi di atas custom lazy enumerators, dan menjamin nol mutasi pada input data.

#### Problem
Anda diminta memproses stream data audit event berskala jutaan record. Data masuk dalam bentuk string terstruktur tidak beraturan (raw log lines). Engine harus mampu membersihkan data, menerapkan aturan filtering composable, memperkaya record dengan kalkulasi metrik, serta mendistribusikan data ke target multi-sink (misal: valid metrics vs quarantine log) secara streaming tanpa menimbun data di memori.

#### Requirements
1. **Composable Transformations via Currying & Closures**:
   - Engine harus menerima rantai operator fungsional independen. Setiap operator harus berupa `Proc` atau callable object yang menerima format seragam dan mengembalikan hasil baru (*immutable transformation*).
   - Wajib memanfaatkan partial application/currying untuk mendefinisikan operator reusable, misalnya:
     ```ruby
     filter_by_severity = PipelineOperators.filter_eq.curry[:severity]
     # filter_by_severity.call("ERROR") -> menghasilkan callable baru
     ```
2. **Backpressure-Safe Lazy Evaluation**:
   - Engine tidak boleh mengonsumsi memori sebanding dengan ukuran total input stream ($O(1)$ space complexity terhadap panjang stream input).
   - Seluruh pipeline harus berbasis `Enumerator::Lazy` atau custom `Enumerator` yang mengimplementasikan protokol `#each`.
3. **Partitioning Stream Murni**:
   - Sediakan mekanisme untuk memecah stream menjadi dua path tanpa membaca ulang source: path data valid dan path data anomali (*quarantine*), menggunakan iterator fungsional.
4. **Zero-Mutation Enforcement**:
   - Setiap modifikasi record pada pipeline harus menghasilkan representasi objek baru. Jika ditemukan mutasi objek input (misal via destruktif `gsub!`, `merge!`, atau `delete`), pipeline harus menggagalkan eksekusi secara deterministik.

#### Constraints
- **Strictly Ruby Standard Library**: Tidak diperbolehkan menggunakan external gems sama sekali.
- **Memory Consumption**: Peak memory usage harus stabil dan tidak boleh melampaui **50 MB heap allocation**, diuji terhadap input stream minimum 500.000 log lines.
- **Ruby Version**: Kompatibel penuh dengan Ruby 3.x (mendukung optimasi pattern matching).

#### Expected Output
1. File implementasi engine fungsional (`stream_pipeline.rb`).
2. Script benchmarking dan profiling memori menggunakan `ObjectSpace.memsize_of` atau alokasi retain object count yang membuktikan memory footprint stabil.
3. Unit test mandiri (menggunakan `Minitest` bawaan stdlib) yang memverifikasi:
   - Immutability input (verifikasi bahwa object ID input tidak mengalami mutasi state internal).
   - Ketepatan eksekusi currying dan monadic functional composition.
   - Skenario backpressure: verifikasi proses pemrosesan stream tak terbatas (*infinite sequence*) dapat dihentikan secara aman dengan operator seperti `.take(n)` tanpa memicu infinite loop.

---

## 5. Knowledge Check & Checklist

Gunakan checklist evaluasi mandiri ini untuk mengonfirmasi penguasaan materi Bab 03 sebelum melangkah ke Bab 04:

### Saya harus memahami:
- [ ] Perbedaan fundamental antara `Proc` dan `lambda` terkait penanganan keyword `return` (local jump vs method return) dan validasi arity.
- [ ] Mekanisme kerja modul `Enumerable` dan ketergantungannya secara absolut pada implementasi method `#each` pada class host.
- [ ] Cara kerja operator `&` dalam konteks method call dan bagaimana protokol `#to_proc` dieksekusi oleh runtime Ruby.
- [ ] Mekanisme closure binding pada Ruby dan implikasi *scope retention* terhadap siklus hidup Garbage Collector (GC).
- [ ] Trade-off internal antara eager evaluation (`Array#map`, `select`) dan lazy evaluation (`Enumerator::Lazy`) dalam konteks alokasi intermediate arrays vs overhead VM dispatch.
- [ ] Keterbatasan `#freeze` bawaan Ruby (shallow immutability) dan konsekuensinya terhadap multi-threaded safety.
- [ ] Konsep partial application dan currying (`Proc#curry`) serta penerapannya dalam membangun higher-order functions yang composable.

### Saya tidak perlu menghafal:
- [ ] Seluruh daftar method di dalam modul `Enumerable` secara alfabetis (cukup pahami kategori fungsinya: filtering, transformation, reduction, boolean checks).
- [ ] Nilai spesifik representasi numerik bitwise dari arity suatu `Method` atau `Proc` via `#arity` (cukup pahami perbedaan nilai positif, nol, dan negatif).
- [ ] Algoritma internal C-implementation dari quicksort/timsort yang digunakan oleh `Enumerable#sort`.

### Saya harus bisa melakukan:
- [ ] Menganalisis dan men-debug memory bottleneck yang disebabkan oleh pemrosesan array berukuran besar menggunakan lazy streaming pipeline.
- [ ] Menulis pipeline pemrosesan koleksi data yang bebas dari efek samping (side effects) dan mutasi in-place.
- [ ] Mengonversi sekumpulan procedural conditional branching yang kompleks menjadi fungsional pipeline menggunakan higher-order functions atau monadic patterns.
- [ ] Menulis custom class yang mengikutsertakan `Enumerable` dan mengimplementasikan protokol `#each` secara benar termasuk handling tanpa block yang mengembalikan `Enumerator`.
- [ ] Mengisolasi shared state yang rentan race condition pada multi-threaded Ruby server dengan menerapkan struktur data immutable.