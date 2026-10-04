# BAB 06: Quiz, Challenge, & Knowledge Check
**Sistem Objek Enterprise (S3, S4, R6) & Metaprogramming**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Resolusi Dynamic Dispatch pada S3 vs S4
Jelaskan perbedaan mendasar antara mekanisme *single dispatch* pada S3 (`UseMethod()`) dan *multiple dispatch* pada S4 (`setGeneric()` / `setMethod()`). Bagaimana algoritma pencarian metode S4 mengatasi ambiguitas ketika dua argumen memiliki relasi pewarisan jamak (*multiple inheritance*), dibandingkan dengan mekanisme *fallback string concatenation* sederhana pada S3?

### Soal 1.2: Semantik Copy-on-Modify vs Reference Semantics
R secara default menerapkan paradigma fungsional dengan semantik *copy-on-modify*. 
1. Mengapa memutasi *slot* pada objek S4 atau elemen atribut pada objek S3 di dalam sebuah perulangan skala besar (e.g., 100.000 iterasi) menyebabkan *memory churn* eksponensial?
2. Bagaimana arsitektur memori internal R6 (yang berbasiskan R `environment`) memintas mekanisme *copy-on-modify* ini?

### Soal 1.3: Anatomi Kode R (AST: Call, Symbol, Pairlist, Literal)
Dalam metaprogramming R, setiap baris kode yang belum dievaluasi direpresentasikan sebagai *Abstract Syntax Tree* (AST). Uraikan empat tipe node fundamental dalam AST R (`symbol`/`name`, `call`, `constant`/`literal`, dan `pairlist`). Jelaskan apa yang dikembalikan oleh ekspresi `is.call(quote(x + 1))` dan mengapa elemen pertama dari objek *call* tersebut adalah simbol `+`.

### Soal 1.4: Tidy Evaluation: Base NSE vs Quosure
Pada implementasi *Non-Standard Evaluation* (NSE) tradisional basis R (seperti `substitute()` dan `eval()`), sering terjadi masalah *lexical scoping hygiene* (variabel tertukar antara *data mask* dan *calling environment*). Bagaimana konsep **Quosure** pada framework `rlang` menyelesaikan masalah ini secara deterministik dengan membungkus ekspresi (*expression*) beserta *lexical environment*-nya?

### Soal 1.5: Validitas Integritas Data S4 via `setValidity`
S4 dirancang untuk integritas data enterprise. Kapan tepatnya fungsi validator yang didefinisikan melalui `setValidity()` dieksekusi oleh R runtime? Mengapa mutasi langsung menggunakan operator `@<-` pada skrip internal dianggap berbahaya (*anti-pattern*) dan bagaimana mutasi tersebut dapat meloloskan data korup meskipun kelas memiliki validator yang ketat?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Memory Leak dan Garbage Collection pada R6 Circular References
Perhatikan skenario di mana dua kelas R6, `ParentNode` dan `ChildNode`, saling mereferensikan satu sama lain (`self$child <- child` dan `self$parent <- parent`).
* Mengapa *mark-and-sweep garbage collector* bawaan R gagal mereklamasi memori yang dialokasikan oleh kedua instance tersebut ketika variabel penampungnya di *global environment* dihapus via `rm()`?
* Rancang pola implementasi *weak reference* atau metode `finalize()` yang benar pada R6 untuk mencegah *memory leak* pada sistem yang berjalan kontinu (24/7).

### Soal 2.2: S3 Method Resolution Order & Name Collisions
Diberikan sebuah objek dengan hierarki kelas ganda: 
```R
x <- structure(list(), class = c("order.aggregate", "data.frame"))
```
Jika seorang insinyur membuat *generic function* bernama `order()` atau menggunakan generic bawaan, terjadi tabrakan penamaan (*name collision*) akibat pemisah titik (`.`) pada konvensi penamaan S3. 
* Analisis bagaimana `UseMethod()` mengurai nama metode untuk `order(x)` vs generic khusus `aggregate(x)`.
* Bagaimana peran `NextMethod()` di dalam rantai dispatch ini dan apa yang terjadi jika salah satu argumen diubah tipe strukturnya di tengah rantai pemanggilan?

### Soal 2.3: Metaprogramming AST Injection: `!!` (Bang-Bang) vs `!!!` (Splicing)
Jelaskan perbedaan mendalam pada level representasi memori antara operator unquote `!!` dan operator unquote-splice `!!!` di dalam `rlang::inject()`. Jika Anda ingin membangun fungsi analitik dinamis yang menerima vektor tak terbatas dari ekspresi agregasi (misalnya: `avg_val = mean(val), max_val = max(val)`), tunjukkan mengapa ekspresi tersebut harus di-expand menggunakan `!!!` ke dalam *call tree* target.

### Soal 2.4: Diagnostik Penurunan Performa pada S4 Method Caching
R runtime menggunakan internal cache untuk memetakan *dispatch signature* S4 guna menghindari kalkulasi jarak pewarisan graf (*class distance*) berulang kali. 
* Dalam kondisi arsitektur seperti apa cache S4 ini mengalami *cache invalidation* secara terus-menerus (*cache thrashing*)?
* Bagaimana cara menginspeksi status dispatch table menggunakan fungsi tingkat rendah dari *package* `methods` untuk mendeteksi bottleneck pemanggilan metode S4?

### Soal 2.5: Serialization Bug pada Closure dan NSE di Lingkungan Terdistribusi
Ketika mengirimkan ekspresi metaprogramming atau *quosure* ke *worker node* yang terdistribusi (misalnya melalui `future`, `parallel`, atau kluster Apache Spark/`sparklyr`), sering kali muncul galat `object of type 'closure' is not subsettable` atau `object not found`. 
* Jelaskan mengapa serialisasi ekspresi yang membawa *environment pointer* (`ENVSXP`) gagal mempertahankan integritas data di worker node terpisah.
* Bagaimana strategi sanitasi environment menggunakan `rlang::quo_squash()` atau pembersihan *enclosure* secara eksplisit sebelum serialisasi data dilakukan?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Memori pada Ingestion Mesin Finansial Skala Besar
Sebuah sistem *real-time automated trading* mengonsumsi pesan *tick data* pasar modal sebesar 50.000 events/detik. Arsitek sebelumnya mengimplementasikan setiap order transaksi sebagai objek **S4** dengan 20 *slot* (meliputi metadata, timestamp numerik, ID unik, status). 

Dalam pengujian beban (*load test*), sistem mengalami latensi lonjakan (*latency spikes*) hingga 4 detik setiap beberapa menit, yang diidentifikasi berasal dari aktivitas pembersihan memori (*Full Garbage Collection*). Profiler memori menunjukkan bahwa instansiasi kelas S4 berulang kali menghasilkan overhead alokasi metadata kelas yang sangat masif, dan mutasi status order melalui *accessor method* memicu duplikasi objek di memori (*copy-on-modify*).

**Pertanyaan Diagnostik & Solusi:**
1. Mengapa paradigma S4 (maupun S3 standar) tidak cocok untuk entitas mikro ber-throughput tinggi dengan mutasi status kontinu?
2. Bagaimana Anda mendesain ulang arsitektur entitas order ini menggunakan **R6 Class** atau struktur **Columnar Vectorized S3 (`vctrs`)**? Bandingkan trade-off latensi versus integritas tipe antara kedua pendekatan tersebut.
3. Rancang arsitektur alokasi objek dengan pola *Object Pooling* menggunakan R6 untuk membatasi frekuensi trigger Garbage Collector ke level minimum.

---

### Skenario B: Race Condition dan Mutasi State pada Model Training Paralel
Sebuah tim data science membangun framework AutoML internal. Mereka mendesain *Hyperparameter Tuning Engine* menggunakan **R6 Class** bernama `ExperimentTracker` untuk mengelola state metrik, log validasi silang, dan status model terbaik (*best model*). Proses evaluasi model didistribusikan ke 16 core prosesor lokal menggunakan eksekusi paralel multi-proses berbasis forking (`parallel::mclapply` di Linux).

Setelah pengujian 100 iterasi selesai, metrik pada `ExperimentTracker` yang berada di proses utama (*master process*) ternyata kosong atau tidak merefleksikan model terbaik dari iterasi yang dijalankan oleh sub-proses worker. Di skenario lain saat menggunakan kluster jaringan (*socket cluster*), sistem menghasilkan galat inkonsistensi data.

**Pertanyaan Diagnostik & Solusi:**
1. Analisis secara mendalam mengapa referensi memori R6 (yang berbasis *environment pointer*) tidak dapat menyinkronkan mutasi *state* lintas proses R yang independen (*inter-process memory isolation*).
2. Mengapa forking (`mclapply`) memberikan ilusi bahwa objek R6 dapat dibaca, namun mutasi di worker process gagal terpropagasi kembali ke master process (*Copy-on-Write behavior* pada level OS kernel)?
3. Rancang arsitektur baru untuk pelaporan metrik terdistribusi yang memisahkan antara *state mutation* dan agregasi data, dengan memanfaatkan IPC (*Inter-Process Communication*), database tertanam (seperti DuckDB/SQLite), atau pola pengembalian data fungsional murni.

---

### Skenario C: Architectural Trade-off Pembuatan Enterprise Query DSL
Perusahaan FinTech ingin membangun DSL (*Domain-Specific Language*) analitik data internal yang membungkus manipulasi data tabular kompleks. Pengguna sistem (analis keuangan) harus bisa menulis sintaks deklaratif seperti:
```R
Pipeline$new(data)$
  filter_rule(margin > 0.15, status == "ACTIVE")$
  aggregate_by(region, total_rev = sum(revenue))$
  execute()
```
Terdapat perdebatan teknis antara tiga Principal Engineer mengenai fondasi arsitektur yang digunakan:
* **Engineer 1:** Mengusulkan full **S4 OOP** dengan *method chaining* untuk memprioritaskan keamanan tipe mutlak dan validasi formal skema data finansial di setiap langkah transformasi.
* **Engineer 2:** Mengusulkan **R6 Class** yang membungkus ekspresi **Metaprogramming (Tidy Evaluation)** guna memberikan ergonomi sintaks fluid (*fluent API*) dan mutasi internal state yang efisien.
* **Engineer 3:** Menolak penggunaan OOP stateful dan mengusulkan pendekatan fungsional murni berbasis **S3 + package `vctrs`** yang dikombinasikan dengan macro ekspresi via `rlang`.

**Pertanyaan Diagnostik & Solusi:**
1. Bedah kelemahan fatal arsitektur Engineer 1 dalam hal ergonomi penulisan kode analitik dan *performance overhead* akibat evaluasi validasi S4 di setiap *chain step*.
2. Evaluasi risiko arsitektur Engineer 2 terkait *leakage* lingkungan eksekusi jika ekspresi `margin > 0.15` tidak di-quote dengan benar dan pengguna memanggil variabel global secara tidak sengaja.
3. Sebagai Senior Principal Engineer, tentukan arsitektur sistem gabungan terbaik (hybrid approach). Sajikan keputusan arsitektural yang menyeimbangkan *type safety*, performa eksekusi memori, dan kenyamanan sintaks bagi analis.

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise Metaprogramming & Validated Pipeline Engine

#### Deskripsi Masalah
Banyak implementasi DSL internal di industri gagal di tahap produksi karena dua hal: celah injeksi kode berbahaya (arbitrary code execution via `eval()`) dan kegagalan validasi tipe pada data pipeline berskala besar. Anda diminta membangun micro-framework modular bernama **`SafeQueryEngine`**.

#### Requirements Teknis
1. **Definisi Kontrak Formal (S4):**
   * Buat S4 class `ColumnContract` yang menyimpan metadata: `column_name` (character), `target_type` (character: "numeric", "character", "logical"), dan `allow_null` (logical).
   * Buat S4 class `TableSchema` yang memvalidasi kumpulan dari `ColumnContract`. Implementasikan `setValidity()` untuk mencegah adanya nama kolom duplikat atau tipe data di luar domain yang diizinkan.
2. **Mesin Eksekusi Stateful & Sandboxing (R6 & Metaprogramming):**
   * Buat R6 Class `PipelineExecutor` yang mengelola `data.frame` internal dan referensi `TableSchema`.
   * Implementasikan metode `add_filter()` yang menerima *unquoted expression* (NSE) dari pengguna via `rlang::enquo()`.
   * **Security AST Linting:** Sebelum dievaluasi, periksa *expression tree* secara rekursif. Batalkan proses (lempar `stop()`) jika ekspresi mengandung *dangerous primitives* seperti pemanggilan fungsi `system`, `eval`, `source`, `file`, atau operator assignment (`<-`, `<<-`, `=`).
   * Implementasikan metode `execute()` yang:
     1. Memvalidasi dataset masukan terhadap `TableSchema` S4.
     2. Menerapkan AST filter yang telah divalidasi ke dalam dataset menggunakan `rlang::eval_tidy()`.
     3. Mencatat metrik performa (*execution time*, *rows in*, *rows out*) secara in-place di dalam slot audit logging R6.

#### Constraints
* Tidak diperbolehkan menggunakan package framework query yang sudah jadi (misalnya: tidak boleh menggunakan `dplyr` atau `data.table` API internal). Manipulasi subsetting data harus menggunakan base R vector indexing yang dieksekusi di dalam tidy-eval environment.
* Dependensi eksternal yang diizinkan hanyalah: `methods` (bawaan R) dan `rlang`.
* Memory-leak free: Instance R6 tidak boleh menyimpan referensi sirkular yang tidak dapat di-garbage collect.

#### Expected Output
* File kode mandiri yang memuat definisi S4 (`ColumnContract`, `TableSchema`), kelas R6 (`PipelineExecutor`), dan fungsi traversal AST.
* Skrip demonstrasi eksekusi sukses: Menginisialisasi skema data, menginput dummy `data.frame`, mengeksekusi filter valid `add_filter(salary > 50000 & department == "Engineering")`, dan menampilkan output hasil filter beserta log audit internal.
* Skrip demonstrasi penanganan galat keamanan: Membuktikan bahwa pemanggilan injeksi seperti `add_filter(salary > 50000 | system("whoami"))` terdeteksi oleh *AST checker* dan membatalkan eksekusi sebelum evaluasi dijalankan.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan resolusi metode antara S3 (*naming convention* `generic.class`), S4 (*explicit signature table lookup*), dan R6 (*encapsulated method inside environment*).
- [ ] Mengapa S3 dan S4 bersifat *functional immutable* (berdasarkan semantik *copy-on-modify*), sedangkan R6 bersifat *reference mutable* (berdasarkan semantik memori R `environment`).
- [ ] Struktur hierarki AST R: Representasi simbol (`SYMSXP`), pemanggilan fungsi (`LANGSXP`/call), literal, dan ekspresi berpasangan (`pairlist`).
- [ ] Konsep higiene leksikal pada *Metaprogramming*: Perbedaan mendasar antara *Base NSE* (`eval(substitute(...))`) dan *Tidy Evaluation* (`enquo()`, `quosure`, *data masking*).
- [ ] Mekanisme injeksi kode menggunakan operator quasiquotation `rlang`: `!!` (*unquote* single node) vs `!!!` (*unquote-splice* multiple elements).
- [ ] Keterbatasan garbage collection R terhadap struktur data R6 yang memiliki referensi sirkular (*circular references*), serta cara kerja *destructor/finalizer*.
- [ ] Implikasi isolasi memori proses (*process isolation*) terhadap objek berbasis *reference semantics* pada eksekusi komputasi paralel dan terdistribusi.

### Saya tidak perlu menghafal:
- [ ] Kode C internal implementasi runtime dispatch S4 (`R_do_slot`, `R_dispatch_s4`).
- [ ] Seluruh variasi fungsi manipulasi *call* kuno di Base R (`bquote`, `substitute` tingkat dalam); prioritaskan penguasaan paradigma modern `rlang`.
- [ ] Algoritma internal C pencarian jarak matriks kelas S4 (*Manhattan distance dispatch resolving algorithm*).

### Saya harus bisa melakukan:
- [ ] Membangun kelas S4 dengan hierarki pewarisan yang kompleks lengkap dengan metode validasi skema formal (`setValidity()`).
- [ ] Merancang kelas R6 modular dengan kontrol akses publik/privat yang ketat, pencegahan *leakage state*, dan finalizer pembersihan memori.
- [ ] Menginspeksi dan membedah representasi pohon AST kode R menggunakan fungsi inspeksi seperti `lobstr::ast()` atau `rlang::call_inspect()`.
- [ ] Menulis fungsi analitik meta-programming berbasis *Tidy Evaluation* yang aman (*hygienic*) menggunakan `rlang::enquo()`, `rlang::eval_tidy()`, dan *data mask*.
- [ ] Mengimplementasikan traversal AST rekursif untuk melakukan sanitasi/audit kode kustom sebelum dievaluasi oleh sistem backend.
- [ ] Mendiagnosis degradasi performa pipeline analitik R yang disebabkan oleh alokasi memori berlebih akibat ketidaktahuan semantik *copy-on-modify*.