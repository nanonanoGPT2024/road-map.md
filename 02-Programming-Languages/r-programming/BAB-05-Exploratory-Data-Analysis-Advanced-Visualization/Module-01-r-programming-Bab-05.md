# Bab 05 Module 01: Arsitektur Memori R & Sistem Reference Semantics: Membedah SEXP, Copy-on-Modify, dan R6 Class Architecture

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, software engineer mampu:
* Mendiagnosis dan mengukur fenomena *Copy-on-Modify* (CoM) menggunakan *low-level memory profiling* (`tracemem`, `lobstr::ref`, `pryr`) pada C-level S-Expression (`SEXP`).
* Mengidentifikasi siklus hidup alokasi memori internal R engine, mencakup representasi `REFCNT`, *in-place modification*, dan pemicu alokasi redundan $O(N)$.
* Merancang dan mengimplementasikan arsitektur berorientasi objek berbasis *Reference Semantics* menggunakan `R6Class` untuk mengelola *stateful service* (seperti *connection pool*, *transaction manager*, dan *cache engine*).
* Mengeliminasi *memory overhead* dan lonjakan latensi *Garbage Collection* (GC) pada pemrosesan data volume tinggi dengan memilih struktur semantik mutasi yang tepat.
* Menerapkan pola *encapsulation*, *active bindings*, *deep cloning*, dan *deterministic finalization* untuk mencegah *resource leak* pada lingkungan produksi.

---

### 2. Prerequisite
Untuk memahami materi ini secara komprehensif, Anda wajib memiliki pemahaman mendalam tentang:
1. **Dasar Struktur Data R**: Vektor atomik, *generic vectors* (`list`), dan atribut R base.
2. **Lexical Scoping & Environments**: Mekanisme pembentukan *frame* eksekusi fungsi, *parent environments*, serta pointer *scoping lookup*.
3. **Konsep Dasar Pointer/Reference**: Pemahaman tingkat sistem mengenai alokasi memori (*heap* vs *stack*), referensi memori, dan konsep dasar *Garbage Collection* (*tracing/mark-and-sweep*).

---

### 3. Concept
R secara fundamental dirancang sebagai bahasa fungsional dengan semantik pass-by-value. Di balik antarmuka R, semua objek direpresentasikan pada level C oleh struktur pointer tunggal yang disebut **`SEXP`** (*S-Expression pointer*).

Setiap `SEXP` membungkus sebuah *header* metadata 64-bit yang berisi:
* **`TYPE`**: Tipe dasar objek (vektor real, list, environment, dll.).
* **`GC Info`**: Bit penanda untuk *generational garbage collector*.
* **`REFCNT` / Reference Count**: Menghitung berapa banyak *binding* simbol yang saat ini menunjuk ke alamat memori fisik `SEXP` yang sama.

```
+-------------------------------------------------------------+
|                        SEXP Header                          |
|  - Type Identifier (INTSXP, REALSXP, VECSXP, ENVSXP, dll.)  |
|  - Generational GC Mark Bits (Gen 0, 1, 2)                  |
|  - REFCNT (Reference Count: 0, 1, 2, ...)                   |
+-------------------------------------------------------------+
|                        Data Payload                         |
|  - Actual Values / Pointers Array                           |
+-------------------------------------------------------------+
```

#### Copy-on-Modify (CoM)
Saat objek R ditugaskan (*assigned*) ke variabel baru (`y <- x`), R engine tidak menyalin payload data. Kedua simbol (`x` dan `y`) menunjuk ke alamat memori fisik (`SEXP`) yang identik, dan `REFCNT` dinaikkan menjadi `2` (atau flag `NAMED = 2` pada sistem R legacy). 

Ketika salah satu variabel diubah nilainya (`y[1] <- 42`), sistem memeriksa `REFCNT`:
* Jika `REFCNT <= 1`, R melakukan **modifikasi langsung di tempat** (*in-place modification / modify-in-place*).
* Jika `REFCNT > 1`, R mengalokasikan blok memori heap baru, menduplikasi seluruh payload dari objek awal, mengalihkan pointer variabel `y` ke alamat baru, menurunkan referensi objek lama, lalu mengeksekusi mutasi.

#### Reference Semantics (Environments & R6)
Berbeda dengan tipe data vektor atau S3 (yang membungkus tipe data dasar dan tunduk pada aturan CoM), objek bertipe **`ENVSXP`** (*environment*) tidak menerapkan Copy-on-Modify. Setiap manipulasi variabel dalam environment atau pengiriman environment ke dalam fungsi dilakukan secara **Pass-by-Reference**.

Framework **R6** mengeksploitasi arsitektur `ENVSXP` ini untuk menyediakan sistem *Encapsulated Object-Oriented Programming*. Instance R6 adalah environment yang memiliki *class attribute*, memungkinkan mutasi internal objek (*state change*) secara deterministik tanpa menduplikasi alokasi memori payload data.

---

### 4. Why
Dalam rekayasa perangkat lunak skala produksi:

1. **Efisiensi Siklus CPU & Latensi GC**: Jika sistem enterprise memanipulasi *state* (misal: antrean transaksi, status koneksi basis data, atau bobot model *machine learning*) menggunakan sistem S3/list, setiap pembaruan elemen memicu alokasi memori penuh sebesar $O(N)$. Pada objek berukuran multi-gigabyte, hal ini mengakibatkan pemborosan siklus CPU untuk *memcpy* dan memicu *Garbage Collection pause* yang mematikan *throughput* sistem.
2. **Kebutuhan Singleton & Shared State**: Sistem seperti *connection pooling* ke database (misal: PostgreSQL/Snowflake) membutuhkan satu instance terpusat yang status koneksinya (terbuka, sibuk, tertutup) dapat diakses dan diubah secara konsisten oleh seluruh sub-modul tanpa khawatir instance tersebut "terfotokopi" secara tidak sengaja.
3. **Enkapsulasi & Proteksi State**: Tanpa enkapsulasi (yang tidak dimiliki oleh S3), atribut kritis dapat dimutasi secara ilegal dari luar modul tanpa validasi data, merusak integritas *runtime*.

---

### 5. What
Komponen kunci arsitektur memori dan sistem R6:

* **SEXP (S-Expression)**: Tipe pointer fundamental pada runtime R.
* **REFCNT (`0`, `1`, `>1`)**: Counter referensi internal yang menentukan apakah duplikasi memori wajib dilakukan saat penulisan data.
* **Modify-in-Place**: Optimasi R engine untuk langsung memanipulasi nilai pada pointer memori yang sama jika hanya ada 1 simbol penunjuk.
* **Environment (`ENVSXP`)**: Wadah simbol berbentuk hash map yang beroperasi menggunakan pointer reference semantics murni.
* **R6Class Generator**: Pabrik (*factory*) pembuat blueprint objek yang membungkus *public methods*, *private attributes*, *active bindings*, dan fungsi *finalizer*.
* **Active Bindings**: Fungsi yang dievaluasi dinamis saat properti diakses atau dimodifikasi, bertindak seperti getter/setter native.
* **Finalizer**: Prosedur pembersihan (*cleanup hook*) yang dieksekusi otomatis oleh *Garbage Collector* ketika instance objek dihapus dari alokasi memori.

---

### 6. How
Alur operasional transisi memori dari Copy-on-Modify menuju Reference Semantics:

```
[Inisialisasi Objek: x <- c(1, 2, 3)]
                 │
                 ▼
       Alamat: SEXP 0x001 (REFCNT = 1)
                 │
                 ├──────────────────────────────┐
                 │                              │
[Assignment: y <- x]                 [Assignment: env <- new.env()]
                 │                   [env$data <- c(1, 2, 3)]
                 ▼                              │
       Alamat: SEXP 0x001                       ▼
         (REFCNT = 2)                   Alamat: ENVSXP 0x999
        (Shared Pointer)                        │
                 │                              ├──────────────────────────────┐
                 ▼                              │                              │
[Mutasi Nilai: y[1] <- 9]            [Mutasi: env2 <- env]             [R6 Instance Mutation]
                 │                   [env2$data[1] <- 9]              [obj$mutate_state()]
                 ▼                              │                              │
Cek REFCNT > 1? -> TRUE                         ▼                              ▼
Duplikasi Memori!                    TETAP Alamat: ENVSXP 0x999       TETAP Alamat: ENVSXP 0xAAA
y -> Alamat: SEXP 0x002 (REFCNT=1)   Modifikasi langsung in-place     Modifikasi langsung in-place
x -> Alamat: SEXP 0x001 (REFCNT=1)   env$data ikut berubah!           Tanpa overhead CoM!
```

1. **Alokasi Nilai**: Variabel disimpan pada heap memory melalui konstruksi SEXP.
2. **Evaluasi Assignment**: Penugasan pointer baru menambah REFCNT.
3. **Pemberlakuan Copying**: Jika operasi penulisan dipanggil pada objek bersubsistem CoM dengan REFCNT > 1, alokasi memori baru terjadi via C-level `duplicate()`.
4. **Bypass via R6/Environment**: Ketika encapsulating class R6 digunakan, seluruh method memanipulasi atribut di dalam *enclosing environment* instance itu sendiri (`self`), menjaga REFCNT environment tetap pada konteks eksekusi, sehingga data diubah tanpa duplikasi payload.

---

### 7. Analogy
* **Copy-on-Modify (S3/Base Object)**: Seperti mengirim salinan cetak fisik formulir kertas kepada seorang rekan kerja. Jika rekan Anda ingin mencoret atau mengubah satu baris jawaban, ia harus menyalin seluruh lembar formulir tersebut ke kertas baru terlebih dahulu, menulis modifikasinya, dan menyimpan lembar baru miliknya sendiri. Anda tetap memegang kertas asli yang tidak berubah sama sekali. Jika proses ini dilakukan 10.000 kali, meja kerja Anda akan penuh dengan 10.000 tumpukan kertas.
* **Reference Semantics (R6 Object)**: Seperti membagikan tautan dokumen kolaboratif digital (*Google Docs*). Rekan Anda, sistem audit, dan Anda sendiri menunjuk ke tautan yang sama persis. Siapa pun yang memperbarui nilai di dalam dokumen tersebut, perubahannya langsung terlihat oleh pihak lain secara instan, tanpa ada kertas tambahan yang perlu dicetak ulang.

---

### 8. Diagram
Perbedaan mendalam mutasi S3 (Value Semantics) vs R6 (Reference Semantics) di dalam memori:

```
========================================================================================
S3 / LIST MUTATION (Copy-on-Modify Overhead)
========================================================================================
Langkah 1: Binding Awal
Symbol 'state_s3' ───> [ 0xAA01 : VECSXP (data=100MB, REFCNT=1) ]

Langkah 2: Pemanggilan Fungsi modify_s3(state_s3)
Symbol 'arg_obj'  ───> [ 0xAA01 : VECSXP (data=100MB, REFCNT=2) ]

Langkah 3: Mutasi arg_obj$val <- 200
  1. REFCNT > 1 terdeteksi
  2. Alokasi memori baru 0xAA02 (memcpy 100MB payload)
Symbol 'state_s3' ───> [ 0xAA01 : VECSXP (data=100MB, val=100) ]
Symbol 'arg_obj'  ───> [ 0xAA02 : VECSXP (data=100MB, val=200) ] (MEMORI BENGKAK 200MB)

========================================================================================
R6 MUTATION (Pure Reference Modification)
========================================================================================
Langkah 1: Binding Awal
Symbol 'state_r6' ───> [ 0xBB01 : ENVSXP (Pointer ke frame instance) ]
                            │
                            └───> [ Data Payload 100MB ]

Langkah 2: Pemanggilan Fungsi modify_r6(state_r6)
Symbol 'arg_obj'  ───> [ 0xBB01 : ENVSXP ] (Menunjuk ke alamat fisik yang sama persis)

Langkah 3: Mutasi arg_obj$update_val(200)
  1. Operasi dieksekusi di dalam lingkup 0xBB01
  2. Modifikasi payload in-place
Symbol 'state_r6' ───┐
                     ├───> [ 0xBB01 : ENVSXP (val=200, TOTAL MEMORI TETAP 100MB) ]
Symbol 'arg_obj'  ───┘
========================================================================================
```

---

### 9. Simple Example
Skrip minimal berikut membuktikan mekanisme Copy-on-Modify vs In-Place Mutation menggunakan package `lobstr`.

```r
# Pastikan library terpasang
if (!requireNamespace("lobstr", quietly = TRUE)) install.packages("lobstr")
if (!requireNamespace("R6", quietly = TRUE)) install.packages("R6")

library(lobstr)
library(R6)

# --- SKENARIO 1: Verifikasi Copy-on-Modify (Atomic Vector / Base R) ---
cat("=== SKENARIO 1: BASE R COPY-ON-MODIFY ===\n")
vec_a <- c(1L, 2L, 3L)
cat("Alamat awal vec_a       :", obj_addr(vec_a), "\n")

vec_b <- vec_a
cat("Alamat vec_b (copy ref) :", obj_addr(vec_b), "\n") # Alamat sama!

vec_b[1] <- 99L
cat("Alamat vec_b pasca-mutasi:", obj_addr(vec_b), "\n") # Alamat BERUBAH!
cat("Alamat vec_a tetap      :", obj_addr(vec_a), "\n")
cat("Nilai vec_a:", vec_a, "\n")
cat("Nilai vec_b:", vec_b, "\n\n")

# --- SKENARIO 2: Verifikasi Reference Semantics (R6) ---
cat("=== SKENARIO 2: R6 REFERENCE SEMANTICS ===\n")
SimpleNode <- R6Class("SimpleNode",
  public = list(
    value = NULL,
    initialize = function(val) self$value <- val,
    set_value = function(val) self$value <- val
  )
)

node_a <- SimpleNode$new(100L)
cat("Alamat instans node_a       :", obj_addr(node_a), "\n")

node_b <- node_a
cat("Alamat instans node_b       :", obj_addr(node_b), "\n") # Alamat identik

node_b$set_value(999L)
cat("Alamat node_b pasca-mutasi  :", obj_addr(node_b), "\n") # Alamat TETAP SAMA!
cat("Nilai node_a$value          :", node_a$value, "\n")     # Berubah menjadi 999L
cat("Nilai node_b$value          :", node_b$value, "\n")
```

---

### 10. Practical Example
Berikut adalah implementasi sistem **Database Connection Pool Manager** standar industri dengan enkapsulasi kredensial privat, pelacakan metrik latensi, active bindings, dan *destructor finalizer* untuk membebaskan koneksi secara deterministik.

```r
library(R6)

ConnectionPool <- R6Class("ConnectionPool",
  # -------------------------------------------------------------
  # PRIVATE BINDINGS: State terlindungi dari akses langsung luar
  # -------------------------------------------------------------
  private = list(
    ..conn_string   = character(0),
    ..max_conns     = integer(0),
    ..active_pool   = list(),
    ..leased_conns  = list(),
    ..total_queries = integer(0),

    # Internal generator untuk mock driver socket C
    create_raw_socket = function(conn_id) {
      return(structure(
        list(
          id = conn_id, 
          created_at = Sys.time(),
          is_open = TRUE
        ),
        class = "mock_c_socket"
      ))
    },

    close_raw_socket = function(sock) {
      if (sock$is_open) {
        sock$is_open <- FALSE
        message(sprintf("[CLEANUP] Socket ID '%s' diputus dengan aman.", sock$id))
      }
    }
  ),

  # -------------------------------------------------------------
  # PUBLIC INTERFACE: API resmi untuk interaksi modul produksi
  # -------------------------------------------------------------
  public = list(
    initialize = function(conn_string, max_conns = 5L) {
      stopifnot(is.character(conn_string), length(conn_string) == 1)
      stopifnot(is.integer(max_conns), max_conns > 0L)

      private$..conn_string   <- conn_string
      private$..max_conns     <- max_conns
      private$..total_queries <- 0L

      # Pre-warm pool
      for (i in seq_len(max_conns)) {
        id <- paste0("CONN_00", i)
        private$..active_pool[[id]] <- private$create_raw_socket(id)
      }
      message(sprintf("[POOL] Siap dengan %d koneksi terdaftar.", max_conns))
    },

    acquire = function() {
      if (length(private$..active_pool) == 0) {
        stop("FATAL: ExhaustedConnectionPool - Tidak ada koneksi yang menganggur.")
      }

      conn_name <- names(private$..active_pool)[1]
      conn <- private$..active_pool[[conn_name]]

      # Re-pointer allocation tanpa Copy-on-Modify
      private$..active_pool[[conn_name]] <- NULL
      private$..leased_conns[[conn_name]] <- conn

      return(conn)
    },

    release = function(conn) {
      stopifnot(inherits(conn, "mock_c_socket"))
      id <- conn$id

      if (!id %in% names(private$..leased_conns)) {
        stop(sprintf("Peringatan: Socket '%s' bukan bagian dari leased pool.", id))
      }

      private$..leased_conns[[id]] <- NULL
      private$..active_pool[[id]]  <- conn
      return(invisible(TRUE))
    },

    execute_query = function(query) {
      stopifnot(is.character(query))
      conn <- self$acquire()
      on.exit(self$release(conn), add = TRUE) # Deterministic release

      # Simulasi kerja IO
      private$..total_queries <- private$..total_queries + 1L
      return(data.frame(
        query_executed = query, 
        conn_used = conn$id, 
        timestamp = Sys.time()
      ))
    }
  ),

  # -------------------------------------------------------------
  # ACTIVE BINDINGS: Read-only Virtual Fields & Getters/Setters
  # -------------------------------------------------------------
  active = list(
    available_connections = function() {
      return(length(private$..active_pool))
    },
    metrics = function() {
      return(list(
        total_queries = private$..total_queries,
        active_leases = length(private$..leased_conns),
        idle_in_pool  = length(private$..active_pool)
      ))
    }
  )
)

# Integrasi Finalizer: Mencegah Socket Zombie pada level C jika GC berjalan
ConnectionPool$set("public", "finalize", function() {
  message("[GARBAGE COLLECTOR TRIGGERED] Finalizing ConnectionPool...")
  all_sockets <- c(private$..active_pool, private$..leased_conns)
  for (sock in all_sockets) {
    private$close_raw_socket(sock)
  }
})

# --- RUNTIME PIPELINE ---
pool <- ConnectionPool$new(conn_string = "pgsql://prod.db:5432/core", max_conns = 2L)
print(pool$metrics)

# Eksekusi Query
res1 <- pool$execute_query("SELECT * FROM transaction_ledger LIMIT 10")
print(res1)
print(pool$metrics)

# Simulasi Destruksi Objek (Finalizer Test)
rm(pool)
invisible(gc()) # Memaksa GC mengeksekusi destructor
```

---

### 11. Real World Example
**Studi Kasus: High-Frequency Limit Order Book (LOB) di Perusahaan Kuantitatif**

Sebuah hedge fund berfrekuensi tinggi memproses ~50.000 pembaharuan *bids* dan *asks* per detik dalam pipeline backtesting R.
* **Permasalahan**: Pipeline awal didesain menggunakan modul S3 standar dengan skema `book <- update_book(book, new_tick)`. Karena objek order book berukuran ~150 MB (berisi level kedalaman harga dan snapshot historis microsecond), setiap mutasi memicu evaluasi CoM. R menduplikasi 150 MB sebanyak 50.000 kali setiap detik. Hal ini menghasilkan alokasi sementara sebesar 7,5 TB/detik, menyebabkan R Engine terkunci dalam siklus `gc()` konstan (*GC Pause Thrashing*), membuat latensi backtesting melonjak dari hitungan menit menjadi berjam-jam.
* **Solusi Arsitektural**: Order book direkayasa ulang menggunakan objek `R6Class`. State internal disimpan dalam *hash-environment* berstruktur array flat fixed-size. Mutasi harga dan kuantitas order dieksekusi secara in-place via referensi internal `self$orders[[id]] <- new_val`.
* **Dampak**: 
  1. *Memory footprint* konstan di angka 152 MB (zero allocation spike).
  2. Latensi per tick berkurang dari $18.4\text{ ms}$ menjadi $14.1\ \mu\text{s}$ (peningkatan kecepatan ~1300x).
  3. Siklus GC dieliminasi sepenuhnya selama durasi pengetesan backtest.

---

### 12. Trade-offs
Tabel perbandingan teknis: **Value Semantics (S3 / Functional Data)** vs **Reference Semantics (R6 / Environments)**.

| Dimensi Rekayasa | Value Semantics (Base R / S3) | Reference Semantics (R6) |
| :--- | :--- | :--- |
| **Karakter Paradigma** | Fungsional murni, Imutabel (*side-effect free*). | Berorientasi Objek (*stateful*, *side-effects intentional*). |
| **Alokasi Memori** | Menggandakan data via Copy-on-Modify jika $REFCNT > 1$. | $O(1)$ in-place update tanpa menyalin payload memori. |
| **Efisiensi Modifikasi** | $O(N)$ terhadap total ukuran data payload. | $O(1)$ untuk pengubahan field tunggal. |
| **Debugging Complexity** | Rendah: Deterministik, tidak ada perubahan state di luar cakupan fungsi. | Tinggi: Perubahan objek di dalam fungsi berdampak global ke pointer pemanggil. |
| **Parallelization** | Aman secara inheren (thread-safe/process-safe via fork/copy). | Rentan *race conditions* jika memory di-share antar worker threading (C++ layer). |
| **Integrasi Ekosistem** | Standar de-facto (`tidyverse`, `base::plot`, modeling `lm/glm`). | Spesifik domain infrastruktur (API client, database pool, shiny backend). |

---

### 13. When To Use
Gunakan arsitektur **Reference Semantics / R6** ketika:
1. **Membangun Stateful Services**: Mengelola status stateful seperti *WebSocket connection*, *database connection pool*, atau *hardware telemetry client*.
2. **Resource-Constrained Memory**: Berhadapan dengan data structures in-memory yang masif yang harus terus dimutasi (misal: node/edge pada analisis grafik jaringan, state pohon catur/MCTS).
3. **Mencegah Side-Channel Duplication**: Memerlukan jaminan bahwa data kredensial atau *cryptographic key* hanya hidup di satu alamat memori dan dapat dihapus deterministik melalui finalizer.
4. **Active UI Component**: Membangun backend logika aplikasi web (Shiny Session Module) di mana *state* komponen harus sinkron lintas modul reaktif tanpa memicu duplikasi data reaktif.

---

### 14. When NOT To Use
Hindari arsitektur **R6** dan tetap gunakan **Functional S3 / Data Frame** ketika:
1. **Analisis Data Fungsional & Transformasi Tabular**: Pipeline ETL dan data cleaning. Gunakan `dplyr` atau `data.table` (yang mengimplementasikan reference semantics C-level sendiri secara aman).
2. **Mathematical / Statistical Modeling**: Fungsi pemodelan seperti `y ~ x` harus deterministik. Menggunakan reference semantics menghilangkan sifat *reproducibility* matematika fungsional.
3. **Tugas Paralelisme Sederhana (`mclapply`, `future`)**: Objek berorientasi referensi sering kali gagal dikirim dengan aman melintasi batas serialisasi IPC (*Inter-Process Communication*) karena pointer memori fisik tidak valid di memori worker process yang berbeda.

---

### 15. Common Mistakes
Kesalahan fatal implementasi yang kerap ditemui di level production:

1. **Shallow Clone Trap**: 
   ```r
   # SALAH: Mengira clone() menyalin referensi di dalam field privat
   inst_a <- R6Class("A", public = list(child = NULL))$new()
   inst_a$child <- R6Class("B", public = list(val = 1))$new()
   
   inst_b <- inst_a$clone() # Default shallow copy!
   inst_b$child$val <- 999  # inst_a$child$val IKUT BERUBAH!
   
   # BENAR: Gunakan Deep Cloning
   inst_b <- inst_a$clone(deep = TRUE)
   ```
2. **Memory Leaks Akibat Circular References**:
   Objek `Parent` menyimpan referensi ke `Child`, dan `Child` menyimpan referensi ke `Parent`. Algoritma *Garbage Collector* R engine dapat gagal mendeteksi deallokasi jika siklus referensi mengunci environment, menyebabkan memori heap tidak pernah dibebaskan.
3. **Mengabaikan Finalizer pada Unhandled Exceptions**:
   Mengandalkan finalizer untuk menutup koneksi file atau socket, namun kode C pendukung memicu *segfault* sebelum R GC sempat menjadwalkan siklus *mark-and-sweep*.

---

### 16. Best Practices
Checklist produksi sebelum men-deploy modul berorientasi objek:

* [ ] **Gunakan Active Bindings untuk Validasi Input**: Jangan pernah mengekspos atribut publik mentah jika atribut tersebut memiliki batasan tipe (*type invariance*). Lindungi di private area, akses melalui active bindings.
* [ ] **Implementasi Metode `deep_clone` Kustom**: Jika kelas R6 mengandung kelas R6 lain atau environment internal, wajib implementasikan private method `deep_clone(name, value)` untuk memastikan replikasi memori penuh saat method `$clone(deep=TRUE)` dipanggil.
* [ ] **Defensive Finalization**: Method `$finalize()` harus idempoten (dapat dieksekusi berulang kali tanpa melempar error) dan tidak boleh melempar exception (`tryCatch` internal adalah kewajiban).
* [ ] **Audit Alokasi Memori dengan Profiler**: Lakukan audit mutasi periodik menggunakan `lobstr::ref()` atau `bench::mark()` untuk membuktikan bahwa tidak ada fungsi yang secara tidak sengaja memicu *shallow duplication*.
* [ ] **Explicit Variable Cleanup**: Pastikan untuk selalu meregistrasikan `on.exit(..., add = TRUE)` saat meminjam objek stateful dari pool untuk menjamin *graceful return* sekalipun program crash di tengah jalan.

---

### 17. Troubleshooting
Panduan diagnosis masalah alokasi dan referensi:

| Gejala Masalah | Investigasi Teknis | Solusi Rekayasa |
| :--- | :--- | :--- |
| **Memori server terus meningkat padahal objek telah di-`rm()`** | Sisa referensi tertahan di *global environment* atau terkunci dalam *enclosing frame* fungsi (*closure memory leak*). | Gunakan `lobstr::obj_sizes()` untuk melacak lingkungan penahan. Putus referensi sirkular secara eksplisit (`self$parent <- NULL`) sebelum dereferencing. |
| **Objek A termutasi ketika Objek B diubah** | Terjadi *implicit aliasing* karena assignment langsung (`obj_b <- obj_a`) pada objek R6. | Gunakan metode `obj_b <- obj_a$clone(deep = TRUE)` untuk memisahkan instance secara utuh. |
| **Lonjakan pemakaian RAM $2\times$ lipat saat modifikasi list besar** | Pemicu Copy-on-Modify akibat *multi-referencing* (`REFCNT > 1`). | Bungkus array/list di dalam `environment` terisolasi atau migrasikan penyimpanan vektor ke paket memory-mapped seperti `bigstatsr` atau `arrow`. |

---

### 18. Exercise
**Instruksi Pengerjaan**:

1. Buat class generator R6 bernama `TransactionalBuffer`.
2. Class tersebut harus memiliki:
   * Private list `..buffer` yang menyimpan item data.
   * Private integer `..max_capacity` (misal 100 elemen).
   * Public method `$push(item)`: Menambahkan item ke buffer. Jika buffer mencapai kapasitas maksimum, lempar error bahwa buffer penuh.
   * Public method `$flush()`: Mengembalikan seluruh data buffer saat ini dalam format list murni, lalu mengosongkan isi buffer internal secara in-place.
   * Active binding `$fill_percentage`: Menghitung persentase kepenuhan buffer secara *read-only*.
3. Lakukan benchmark menggunakan `bench::mark()` atau ukur menggunakan `lobstr::obj_addr()` untuk membuktikan bahwa pemanggilan `$push()` berturut-turut sebanyak 100 kali tidak mengubah alamat memori instans buffer tersebut.

---

### 19. Challenge
**Rancang dan Bangun: Thread-Safe LRU (Least Recently Used) In-Memory Cache Engine**

**Spesifikasi Persyaratan Teknis**:
1. Buat class `LRUCache` menggunakan `R6Class`.
2. **Kapasitas Terbatas**: Cache menerima parameter `capacity` (integer positif) pada saat konstruksi (`initialize`).
3. **Kompleksitas Waktu**: 
   * Operasi `$get(key)` harus beroperasi dalam rata-rata $O(1)$.
   * Operasi `$set(key, value)` harus beroperasi dalam rata-rata $O(1)$.
4. **Logika Eviksi**: Ketika cache mencapai batas `capacity` dan sebuah kunci baru dimasukkan via `$set()`, item yang paling lama tidak diakses (baik melalui `$get` maupun `$set`) harus dieliminasi dari memori.
5. **Struktur Data Under-the-Hood**: Anda dilarang melakukan pencarian linear $O(N)$ di dalam vector/list untuk menemukan item tertua. Rancang kombinasi antara R *environment* (sebagai Hash Map $O(1)$) dan implementasi struktur data *Doubly Linked List* (yang dibangun dari node-node R6 dengan pointer `prev` dan `next`) untuk melacak urutan pemakaian elemen.
6. **Deep Cloning Handling**: Pastikan metode `$clone(deep = TRUE)` merekonstruksi pointer seluruh rantai node *doubly linked list* tanpa merusak urutan cache atau memicu infinite loop rekursif.

---

### 20. Summary
* **Mesin R Menggunakan Representasi C-level `SEXP`**: Semua objek R dibungkus dalam tipe data C terpadu dengan metadata header yang memuat counter referensi objek (`REFCNT`).
* **Copy-on-Modify (CoM) Menjamin Imutabilitas**: CoM adalah mekanisme proteksi fungsional dasar di mana penyalinan alokasi payload data fisik ditunda hingga modifikasi data dipicu pada saat `REFCNT > 1`.
* **Environment (`ENVSXP`) Kebal Terhadap CoM**: Modifikasi simbol di dalam environment selalu dilakukan secara langsung di tempat (*modify-in-place*), menjadikannya landasan ideal untuk *Reference Semantics*.
* **R6 Membawa OOP Berstandar Industri ke R**: Memanfaatkan keunggulan environment, `R6Class` menyediakan arsitektur berorientasi objek yang efisien secara memori, dilengkapi enkapsulasi privat/publik sejati, *active bindings*, dan mekanisme *finalizer*.
* **Manajemen State Skala Enterprise Wajib Berhati-hati**: Pemanfaatan *reference semantics* harus diisolasi pada lapisan infrastruktur sistem (koneksi, buffer, cache) untuk menghindari hilangnya transparansi referensial fungsional yang menjadi kekuatan utama analitik bahasa R.