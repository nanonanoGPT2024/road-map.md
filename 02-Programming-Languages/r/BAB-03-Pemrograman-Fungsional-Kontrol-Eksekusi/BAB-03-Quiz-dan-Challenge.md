# BAB 03: Quiz, Challenge, & Knowledge Check
**Pemrograman Fungsional & Kontrol Eksekusi**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Anatomi *Promise* dan Mekanisme *Lazy Evaluation*
Jelaskan secara struktural bagaimana *runtime* R mengevaluasi argumen fungsi menggunakan *Promise Object*. Komponen internal apa saja yang menyusun sebuah *promise* (seperti *expression*, *environment*, dan *value*), kapan transisi status *unevaluated* ke *evaluated* terjadi, dan bagaimana mekanisme *caching* (memoization internal) mencegah evaluasi ganda terhadap ekspresi yang memiliki *side-effect*?

### Soal 1.2: Vektorisasi Sejati (*Idiomatic Vectorization*) vs. Iterasi Fungsional
Dalam ekosistem R, sering terjadi kerancuan antara fungsi tervektorisasi murni (*vectorized function*) dan *higher-order functions* seperti famili `apply` atau `purrr::map`. Uraikan perbedaan mendasar antara:
1. Vektorisasi tingkat rendah (*SIMD/C-level vector loops* seperti `+`, `exp()`, atau `ifelse()`).
2. Iterasi berbasis fungsional tingkat tinggi (*R-level loop abstraction* seperti `lapply`).
Jelaskan implikasinya terhadap *memory allocation*, *call-stack overhead*, dan utilisasi *instruction cache* pada CPU.

### Soal 1.3: *Lexical Scoping* dan Enkapsulasi Status Melalui *Closure*
Bagaimana R mengisolasi status (*state*) melalui *closure*? Jelaskan perbedaan mendasar antara *binding environment*, *enclosing environment*, *execution environment*, dan *calling environment*. Kapan operator *deep assignment* (`<<-`) sah digunakan dalam arsitektur fungsional, dan apa risiko degradasi integritas data jika digunakan secara tidak disiplin?

### Soal 1.4: Kontras Semantik: `tryCatch()` vs. `withCallingHandlers()`
Jelaskan perbedaan arsitektural penanganan kondisi (*condition handling*) antara `tryCatch()` dan `withCallingHandlers()`. Mengapa `tryCatch()` melakukan proses *stack unwinding* sebelum mengeksekusi handler, sedangkan `withCallingHandlers()` mengeksekusi handler langsung pada konteks titik sinyal dibangkitkan? Bagaimana perbedaan ini memengaruhi kemampuan *debugging* dan inspeksi *call-stack trace*?

### Soal 1.5: Purity, Referensial Transparansi, dan Mekanisme *Copy-on-Modify*
R mengadopsi paradigma fungsional namun mempertahankan struktur data yang tampak mutabel bagi pengguna. Jelaskan korelasi antara *referential transparency* dengan semantik *Copy-on-Modify* (CoM). Dalam kondisi apa manipulasi data dalam fungsi R memicu duplikasi memori penuh ($O(N)$), dan kapan *runtime* (melalui ALTREP dan pelacakan referensi internal/`NAMED` / reference counting) mampu melakukan optimasi modifikasi *in-place*?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: *The Leaky Index Closure Bug* dan Intervensi `force()`
Perhatikan cuplikan kode berikut:
```R
make_power_functions <- function(exponents) {
  funcs <- vector("list", length(exponents))
  for (i in seq_along(exponents)) {
    funcs[[i]] <- function(x) x ^ exponents[[i]]
  }
  return(funcs)
}

powers <- make_power_functions(1:3)
c(powers[[1]](2), powers[[2]](2), powers[[3]](2))
```
Kode di atas menghasilkan nilai `c(8, 8, 8)` alih-alih `c(2, 4, 8)`. 
1. Bedah anomali ini berdasarkan siklus hidup *promise* dan resolusi variabel dalam *lexical scoping*.
2. Jelaskan mengapa penambahan fungsi `force()` menyelesaikan masalah ini secara deterministik pada tingkat memori.

### Soal 2.2: Ketiadaan *Tail Call Optimization* (TCO) dan Batasan *C-Call Stack*
R engine secara *default* tidak mendukung *Tail Call Optimization* (TCO). 
1. Jelaskan apa yang terjadi pada *C-call stack* dan R *evaluation stack* (`sys.calls()`) ketika fungsi rekursif dieksekusi melampaui limit rekursi (`options("expressions")`).
2. Tunjukkan bagaimana Anda merefaktor algoritma rekursif murni (misal: *deep nested list flattener*) menjadi implementasi fungsional berbasis *Trampoline* atau reduksi berbasis iterasi (*fold/accumulate*) guna menjamin penggunaan memori stack $O(1)$.

### Soal 2.3: Degradasi Performa Akibat Pembuatan *Closure Overhead* pada Hot-Path
Mengapa mendefinisikan fungsi anonim di dalam loop atau di dalam pemanggilan iterasi frekuensi tinggi (misal: memanggil `lapply` berulang kali di dalam loop mikro-benchmark) dapat memicu peningkatan tajam pada aktivitas *Garbage Collector* (GC)? Bedah bagaimana *environment allocation* per evaluasi fungsi berdampak pada latensi sistem.

### Soal 2.4: Ambiguitas dan Penalti Evaluasi Dinamis pada Operator Dot-Dot-Dot (`...`)
Penggunaan argumen ellipsis (`...`) sangat fleksibel tetapi memiliki implikasi teknis.
1. Bagaimana R mengevaluasi *elements* di dalam `...`? Kapan ekspresi dalam `...` dievaluasi, dan apa bahayanya jika sebuah argumen dalam `...` diteruskan (*forwarded*) melalui beberapa lapis *higher-order functions* tanpa evaluasi awal?
2. Bagaimana mendeteksi jika terjadi salah ketik (*argument typo*) yang tertelan secara diam-diam oleh `...` tanpa menghasilkan *warning* atau *error*?

### Soal 2.5: Non-Local Jumps dan Restarts pada Sistem Sinyal Kondisi
Bagaimana mekanisme *restart* (seperti `invokeRestart()`, `withRestarts()`, `muffleWarning()`) bekerja dalam memisahkan logika deteksi kesalahan (*error detection*) dan strategi pemulihan (*error recovery*)? Berikan skema bagaimana sebuah proses pembacaan file batch korup dapat melanjutkan iterasi tanpa kehilangan status atau menghentikan keseluruhan *batch pipeline*.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Memory Thrashing pada Pipeline ETL Finansial
*Konteks*: Sebuah pipeline analitik memproses 50.000 file log transaksi harian menggunakan arsitektur pemrosesan paralel berbasis `mclapply` di lingkungan Linux R-Server. Tiap iterasi mengembalikan data frame dan digabungkan menggunakan pola:
```R
results <- vector("list", length(files))
# Di dalam loop / map:
aggregated <- do.call(rbind, results)
```
*Insiden*: Server mengalami *Kernel Out-of-Memory (OOM) Killer* meskipun total ukuran mentah data hanya 4 GB pada server berkapasitas RAM 64 GB. Pemantauan CPU menunjukkan utilisasi CPU anjlok ke level 5% dengan *I/O wait* dan *system time* (GC thrashing) mencapai 95%.
*Pertanyaan Diagnostik*:
1. Mengapa kombinasi `do.call(rbind, ...)` dengan ribuan partisi memicu alokasi memori berorde $O(N^2)$?
2. Bagaimana Anda mendesain ulang pola integrasi fungsional ini (misal menggunakan kombinasi `purrr`/`data.table::rbindlist`/`vctrs`) agar alokasi memori bersifat linier $O(N)$ dan mempertahankan kestabilan memori pekerja (*worker fork*)?

### Skenario B: *State Leakage* dan Segfault pada Paralelisasi Berbasis *Forking*
*Konteks*: Tim data engineer menjalankan proses *hyperparameter tuning* model machine learning secara paralel. Algoritma memanfaatkan objek *closure* untuk menyimpan matriks fitur dan sebuah *external pointer* ke pustaka C++ (melalui `Rcpp`).
*Insiden*: Pipeline yang berjalan menggunakan metode *fork-based clustering* (`parallel::mclapply`) menghasilkan prediksi yang bias (hasil worker 2 tertukar dengan worker 1) dan secara berkala mengalami *Segmentation Fault (core dumped)* tanpa *R stack trace*.
*Pertanyaan Diagnostik*:
1. Mengapa manipulasi status melalui *closure* yang menggunakan operator `<<-` di dalam fungsi yang diparalelkan via *forking* (`mclapply`) tidak persisten dan menyebabkan kondisi *race condition* semu (*copy-on-write divergence*)?
2. Mengapa *external pointer* (C++ raw address) rentan mengalami *dangling pointers* atau korupsi memori ketika proses R membagi memori melalui *forking*? Bagaimana arsitektur fungsional murni tanpa *shared-state mutation* menyelesaikan masalah ini?

### Skenario C: Desain Engine Validasi Data: OOP vs. Pure Functional Pipeline
*Konteks*: Anda bertindak sebagai Principal Architect yang harus merancang ulang modul validasi data ingestion berskala *terabyte*. Sistem harus memverifikasi ratusan aturan bisnis (kelengkapan, batasan numerik, integritas skema, deteksi anomali). Arsitek sebelumnya mengusulkan penggunaan sistem R6 (OOP) dengan kelas yang menyimpan *state* kegagalan validasi. Anda mengusulkan arsitektur *Pure Functional Composition* (berbasis fungsi monadic/kategori seperti pola `Result/Either`).
*Pertanyaan Diagnostik*:
1. Uraikan analisis *trade-off* performa, kemudahan *unit testing*, *thread-safety*, dan *idempotensi* antara pendekatan R6 OOP yang bersifat *stateful* versus pendekatan *Higher-Order Combinators* fungsional murni.
2. Rancang struktur komposisi fungsi menggunakan operator pipa fungsional murni (Base R `|>` atau `magrittr`) di mana setiap tahapan validasi menerima tuple `(data, status_log)` dan mengembalikan tuple baru tanpa melakukan mutasi global.

---

## 4. Chapter Challenge

### Tantangan Praktis: Pembangunan Resilient Resilient Execution Engine dengan Dynamic Backoff, Error Recovery, dan Call-Stack Preservation

#### Problem Statement
Dalam ekosistem mikroservis, pemanggilan API eksternal dan operasi I/O database sering mengalami degradasi transien (timeout, *rate limits*, koneksi terputus). Penggunaan *wrapper* sederhana berbasis `try()` atau `tryCatch()` primitif sering kali menghilangkan konteks *stack trace*, menyebabkan hilangnya visibilitas akar masalah (*root-cause analysis*), serta mengakibatkan konsumsi sumber daya berlebih karena tidak adanya jeda adaptif (*jittered exponential backoff*).

Anda ditantang membangun sebuah *Higher-Order Function Decorator* tingkat enterprise bernama `resilient_exec()` yang mentransformasikan fungsi biasa menjadi fungsi yang tangguh terhadap kegagalan operasional.

#### Functional Requirements
1. **Decorator Signature**:
   Fungsi harus menerima parameter:
   * `f`: Fungsi target yang akan dieksekusi.
   * `max_attempts`: Batas maksimal percobaan eksekusi (integer $\ge 1$).
   * `backoff_base`: Nilai dasar untuk kalkulasi eksponensial (detik).
   * `retry_on`: Vektor karakter atau predikat fungsi yang mendefinisikan kelas kondisi kegagalan mana yang *boleh* dicoba ulang (misal: `c("timeout_error", "connection_failure")`). Kesalahan fatal seperti `argument_missing` atau `type_error` harus langsung dihentikan (*abort immediately*).
2. **Context Preservation**:
   Jika seluruh upaya gagal, fungsi harus melemparkan sinyal *error* terstruktur (*custom S3 condition*) yang merangkum:
   * Pesan kesalahan asli dari setiap *attempt*.
   * Rekaman *call-stack trace* utuh dari percobaan terakhir.
   * Metadata durasi eksekusi dan jumlah *retry* yang telah dilakukan.
3. **Condition Handling Architecture**:
   Wajib menggunakan `withCallingHandlers()` untuk mendeteksi *warning* dan *error* pada saat kejadian (*point of origin*) guna merekam status stack trace sebelum stack tersebut di-*unwind* oleh sistem penanganan kesalahan.
4. **Pure Functional State Transformation**:
   Dilarang keras menggunakan variabel global atau memutasi objek di luar skop lokal (bebas efek samping pada *global environment*). Seluruh kalkulasi status percobaan harus dikelola melalui rekursi yang dikendalikan oleh *trampoline* ATAU fungsi akumulator fungsional murni.

#### Constraints
* **Ekosistem Dependensi**: Hanya boleh menggunakan Base R dan paket primitif fungsional/metaprogramming minimal (`rlang` diperbolehkan untuk inspeksi lingkungan/kondisi, tetapi diutamakan solusi mandiri).
* **Memory Safety**: Engine tidak boleh mempertahankan referensi data besar jika terjadi kegagalan eksekusi; *payload data* harus dibersihkan secara deterministik untuk mencegah kebocoran memori.
* **Deterministic Timing**: Logika jeda (*sleep*) harus mengimplementasikan variasi *Full Jitter* untuk mencegah sinkronisasi *retry storm*:
  $$\text{Sleep} = \text{runif}(1, 0, \text{backoff\_base} \times 2^{\text{attempt}-1})$$

#### Expected Output
1. Implementasi kode lengkap fungsi `resilient_exec()`.
2. Definisi *custom error condition class* yang dihasilkan jika terjadi kegagalan menyeluruh.
3. Contoh eksekusi uji (*test harness*) yang mensimulasikan pemanggilan fungsi flaky yang gagal dua kali berturut-turut karena transien error lalu berhasil pada percobaan ketiga.
4. Contoh eksekusi uji yang menunjukkan kegagalan fatal (non-retryable condition) yang dihentikan secara instan pada *attempt* ke-1 tanpa menjalankan retry.

---

## 5. Knowledge Check & Checklist

Verifikasi penguasaan materi fungsional dan eksekusi R Anda melalui checklist mandiri berikut:

### Saya harus memahami:
- [ ] Siklus hidup internal *Promise*: struktur memory C-level (`PRIMSXP`/`PROMSXP`), evaluasi tertunda, dan implikasi mutasi *environment* asal sebelum evaluasi terjadi.
- [ ] Model komputasi *Lexical Scoping*: 4 aturan scoping R (*name masking*, *functions vs variables*, *a fresh start*, *dynamic lookup*).
- [ ] Arsitektur *Condition Handling*: hierarki `condition`, `message`, `warning`, `error`, serta perbedaan teknis mekanisme *stack unwinding* pada `tryCatch` vs *in-place interception* pada `withCallingHandlers`.
- [ ] Mekanisme alokasi memori internal Base R: *Reference Counting*, implikasi *Copy-on-Modify* pada vektor, daftar, dan *environments*.
- [ ] Batasan eksekusi R: ketiadaan Tail Call Optimization (TCO), limit rekursi C-stack, serta risiko paralelisasi *forking* (`mclapply`) pada objek berstatus mutabel.

### Saya tidak perlu menghafal:
- [ ] Seluruh nama kode error internal atau nomor status numerik dari C API R Core.
- [ ] Rincian implementasi algoritma pengurutan internal di balik fungsi-fungsi primitif seperti `.Internal(radixsort(...))`.
- [ ] Seluruh variasi argumen antarmuka pada implementasi fungsi wrappers pihak ketiga jika prinsip *higher-order function*-nya sama.

### Saya harus bisa melakukan:
- [ ] Mencegah dan memperbaiki *binding bugs* pada *closures* dengan memanggil `force()` secara tepat pada argumen evaluasi malas.
- [ ] Mengonversi algoritma sekuensial prosedural berbasis for-loop berpotensi *memory-leak* menjadi pipeline fungsional murni berbasis *HOF* (`lapply`, `purrr::map`, `Reduce`) dengan alokasi memori yang stabil.
- [ ] Mengabstraksi logika *cross-cutting concerns* (pencatatan log, profiling waktu eksekusi, penanganan retry) ke dalam fungsi *decorator/wrapper* fungsional tingkat tinggi.
- [ ] Menulis sistem isolasi error tingkat lanjut yang mampu menangkap sinyal kesalahan, mengekstrak *call-stack trace* secara presisi, dan memulihkan eksekusi tanpa menghentikan pemrosesan batch data berskala besar.
- [ ] Mengidentifikasi dan membuktikan terjadinya modifikasi *in-place* vs duplikasi data memori ($O(N)$ CoM) menggunakan fungsi pelacak alamat memori (`tracemem()` atau `lobstr::ref()`).