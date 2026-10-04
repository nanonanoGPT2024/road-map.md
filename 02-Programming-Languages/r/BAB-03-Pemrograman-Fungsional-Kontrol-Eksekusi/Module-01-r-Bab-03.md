# Bab 03 Modul 01: Environments, Lexical Scoping, and Memory Binding Internals

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda akan mampu:
- Menganalisis topologi memori internal R (`ENVSXP`) dan arsitektur pointer antar-lingkungan (*environment hierarchy*).
- Mengimplementasikan pola *stateful functional programming* (closures) dengan kontrol siklus hidup memori tanpa mencemari *global namespace*.
- Melakukan isolasi dependensi runtime dan resolusi simbol dinamis menggunakan teknik manipulasi rantai *scoping* (*lexical scoping* & *active bindings*).
- Mendiagnosis dan memitigasi kebocoran memori (*memory leaks*) akibat retensi objek tak terpakai pada *enclosing environments* di aplikasi produksi skala besar (misalnya Plumber API atau Shiny Server).

---

### 2. Prerequisite
Sebelum mendalami modul ini, Anda wajib menguasai:
- **Arsitektur Data Primitif R**: Vektor atomik, *lists*, atribut objek, dan representasi C-level dari struktur R.
- **Mekanika Salin-Saat-Ubah (Copy-on-Modify)**: Konsep *reference counting* (`NAMED` / `REFCNT`) pada objek R.
- **Sintaksis Fungsi Tingkat Dasar**: Pembuatan fungsi, *anonymous functions*, dan evaluasi argumen standar (*lazy evaluation* / *promises*).

---

### 3. Concept
Secara arsitektural di level C (*R Core Runtime*), sebuah *environment* direpresentasikan oleh tipe struktur C `ENVSXP` (*environment S-expression*). Berbeda dengan *atomic vectors* atau *lists* yang mengadopsi semantik nilai (*value semantics*) dengan prinsip *copy-on-modify*, *environment* di R mengadopsi semantik referensi (*reference semantics*). Ketika sebuah *environment* dimodifikasi atau di-passing ke fungsi lain, ia tidak pernah diduplikasi secara implisit di memori; operasi dilakukan langsung pada blok memori yang sama.

Struktur internal `ENVSXP` terdiri dari tiga komponen fundamental:
1. **Frame**: Sebuah tabel hash (*hash table*) atau *pairlist* berpasangan nama-nilai yang mengikat (*binds*) sekumpulan simbol (nama variabel) ke pointer objek R tertentu di memori.
2. **Enclosing Environment (Parent)**: Pointer langsung yang menunjuk tepat ke satu *environment* lain di atasnya dalam hierarki. Setiap *environment* memiliki parent, kecuali satu: `emptyenv()`.
3. **Attributes**: Metadata tambahan (serupa dengan atribut objek R lainnya).

```
         +---------------------------------------------+
         |              ENVSXP Structure               |
         |                                             |
         |  +---------------------------------------+  |
         |  | Frame (Hash Table / Symbol Bindings)  |  |
         |  | "x" ---> Pointer to INTSXP [42]       |  |
         |  | "y" ---> Pointer to STRSXP ["prod"]   |  |
         |  +---------------------------------------+  |
         |                                             |
         |  Parent Pointer ---------------------------> To Enclosing ENV
         +---------------------------------------------+
```

R menggunakan aturan **Lexical Scoping** (pencarian leksikal), yang berarti penelusuran lokasi variabel ditentukan sepenuhnya oleh topologi struktur kode saat fungsi tersebut **didefinisikan**, bukan saat fungsi tersebut **dipanggil** (*dynamic scoping*). 

Rantai resolusi simbol beroperasi secara rekursif:
1. Cari simbol dalam frame saat ini (*current environment*).
2. Jika tidak ditemukan, dereferensi pointer parent untuk melangkah ke *enclosing environment*.
3. Ulangi proses hingga simbol ditemukan.
4. Jika pencarian mencapai `emptyenv()` tanpa menemukan simbol, runtime akan melemparkan kesalahan fatal: `object '<name>' not found`.

---

### 4. Why
Memahami internal *environment* dan *lexical scoping* adalah pembeda utama antara pengguna R tingkat pemula dan *Software/Data Infrastructure Engineer* tingkat lanjut. Di lingkungan produksi enterprise:

- **Kebocoran Memori (Memory Bloat)**: Sebuah fungsi yang me-return *closure* secara otomatis mempertahankan pointer ke seluruh *execution environment* tempat ia diciptakan. Jika *execution environment* tersebut memuat data frame sebesar 10 GB yang tidak lagi digunakan, data frame tersebut tidak akan pernah dibersihkan oleh *Garbage Collector* (GC) selama fungsi turunan tersebut masih aktif.
- **Konkurensi & Status Bersama (Shared State)**: API mikro (*microservices*) berbasis R (seperti `plumber`) atau visualisasi analitik interaktif (*Shiny*) bersifat multi-sesi atau berbasis *event loop*. Salah memahami referensi *global* versus *execution environment* dapat menyebabkan data nasabah bocor antar-sesi koneksi.
- **Determinisme Paket**: Menguasai *namespaces* (`<pkg>::<symbol>`, `imports`, `exports`) sangat bergantung pada cara R merangkai hierarki *enclosing environments* untuk menghindari tabrakan simbol runtime (*symbol masking*).

---

### 5. What
Komponen kunci dalam ekosistem *Environments* R meliputi:

| Komponen | Representasi Internal / Fungsi | Deskripsi Teknis |
| :--- | :--- | :--- |
| **Global Environment** | `globalenv()` / `.GlobalEnv` | Ruang kerja interaktif (*user workspace*). Tempat script berjalan secara default; parent-nya adalah paket terakhir yang di-*attach*. |
| **Empty Environment** | `emptyenv()` | Titik akhir (akar) dari seluruh hierarki lingkungan. Tidak memiliki parent (`parent.env(emptyenv())` mengembalikan *error*). |
| **Base Environment** | `baseenv()` | Lingkungan untuk paket fundamental `base`. Parent langsung dari `emptyenv()`. |
| **Execution Environment**| Ephemeral `ENVSXP` | Lingkungan yang dialokasikan secara dinamis saat sebuah fungsi dipanggil untuk menampung argumen dan variabel lokal. Dihancurkan otomatis setelah fungsi selesai, kecuali ditahan oleh *closure*. |
| **Enclosing Environment**| Atribut `environment(fn)` | Lingkungan tempat fungsi *diciptakan*. Menentukan ke mana penelusuran simbol diarahkan jika tidak ada di lokal. |
| **Binding Environment** | Lokasi simbol | Lingkungan tempat fungsi *diberi nama/diikat*. Sebuah fungsi bisa diikat di `globalenv()`, tetapi enclosing-nya berada di dalam *package namespace*. |

---

### 6. How
Alur kerja resolusi simbol dan *execution lifecycle* berlangsung dalam 4 fase:

```
[Definisi Fungsi]
       │
       ▼
[Penetapan Enclosing Environment: environment(f) <- current_env()]
       │
       ▼
[Pemanggilan Fungsi: f()]
       │
       ▼
[Alokasi Execution Frame (Parent diarahkan ke Enclosing Environment)]
       │
       ├── Argumen dievaluasi secara Lazy (Promises)
       ├── Eksekusi ekspresi dalam body(f)
       │     │
       │     ├── Simbol lokal? -> Ambil dari Execution Frame
       │     └── Simbol tidak ada? -> Telusuri rantai Enclosing Env
       │
       ▼
[Terminasi Fungsi]
       │
       ├── Ada Closure yang mempertahankan Execution Frame?
       │     ├── YA  --> Frame tetap berada di RAM (Heap)
       │     └── TIDAK --> Frame ditandai unreferenced -> Dibersihkan GC
       ▼
[Return Value kembali ke Caller Frame]
```

Langkah detail:
1. **Instansiasi Fungsi**: Saat parser mengevaluasi ekspresi `function(...)`, runtime mengalokasikan objek fungsi (`CLOSXP`) dan mengunci referensi lingkungan saat itu sebagai *enclosing environment*.
2. **Aktivasi Call Frame**: Pemanggilan fungsi memicu C-level `applypath` untuk membentuk konteks eksekusi baru.
3. **Penyelesaian Simbol Non-Lokal**: Jika variabel tidak diikat di frame lokal, runtime membaca pointer parent dan mencari variabel tersebut secara hierarkis (Lexical Scoping).
4. **Modifikasi Super-Assignment (`<<-`)**: Berbeda dengan operator assignment biasa (`<-`), operator super-assignment menolak memodifikasi frame lokal kecuali variabel sudah ada di sana. Operator ini menaiki hierarki *parent environments* dan mengubah nilai pada frame pertama yang memiliki simbol tersebut. Jika tidak ditemukan sampai ke `globalenv()`, ia membuat binding baru langsung di `globalenv()`.

---

### 7. Analogy
Bayangkan sebuah **Gedung Perusahaan Multinasional dengan Ruang Kerja Terisolasi**:
- Setiap ruangan adalah sebuah **Environment**.
- Meja kerja Anda di dalam ruangan adalah **Frame**, tempat Anda menyimpan dokumen bertuliskan nama-nama variabel.
- Pintu keluar ruangan memiliki tanda panah satu arah ke lorong utama: ini adalah **Parent Pointer**.
- Jika Anda membutuhkan dokumen bernama `Laporan_Keuangan`:
  - Anda pertama kali memeriksa meja Anda (**Execution Environment**).
  - Jika tidak ada, Anda keluar ke lorong departemen Anda (**Enclosing Environment**).
  - Jika tidak ada, Anda naik lift ke kantor pusat (**Global Environment** / **Package Environments**).
  - Jika hingga ke brankas pusat (**Empty Environment**) dokumen tidak ditemukan, Anda menyerah dan berteriak "Dokumen Tidak Ditemukan!" (*Runtime Error*).
- Anda **tidak pernah** bisa melihat ke dalam ruangan rekan kerja di departemen lain (*no dynamic scoping*), Anda hanya bisa melihat ke atas melalui jalur hierarki resmi tempat ruangan Anda dibangun (*lexical scoping*).

---

### 8. Diagram
Berikut adalah topologi rantai lingkungan (*search path*) tipikal dan siklus hidup eksekusi *closure*:

```
+-------------------------------------------------------------------------+
|                              SEARCH PATH                                |
+-------------------------------------------------------------------------+
                                                                           
   +------------------+      Parent      +--------------------+            
   |  R_GlobalEnv     | ---------------> | package:rlang      |            
   |  (Interactive)   |                  +--------------------+            
   +------------------+                            |                       
            ^                                      | Parent                
            |                                      v                       
            | Parent                     +--------------------+            
            |                            | package:base       |            
   +------------------+                  +--------------------+            
   | Execution Frame  |                            |                       
   | (Closure runtime)|                            | Parent                
   +------------------+                            v                       
     | "data" = [RAM]                    +--------------------+            
     | "x"    = 100                      | R_EmptyEnv         |            
     |                                   | (Terminal Root)    |            
     |                                   +--------------------+            
     |                                                                     
     |                                                                     
+----+--------------------------------------------------------------------+
| CLOSURE IN MEMORY                                                       |
+-------------------------------------------------------------------------+
|                                                                         |
|  my_closure <- function(val) { val + x }                                |
|                                                                         |
|  Object: CLOSXP                                                         |
|  ├── Formals: val                                                       |
|  ├── Body:    val + x                                                   |
|  └── Environment Pointer ───────────+                                   |
|                                     |                                   |
+-------------------------------------|-----------------------------------+
                                      |                                    
                                      v                                    
            Points to where it was CREATED (Execution Frame above)         
            Even if called from another context entirely!                  
```

---

### 9. Simple Example
Contoh berikut mendemonstrasikan mekanika pembuatan *environment*, penelusuran manual menggunakan R API native, dan bukti nyata sifat *reference semantics*.

```r
# 1. Pembuatan isolated environment tanpa parent kotor
sandbox_env <- new.env(parent = emptyenv())

# 2. Binding variabel ke dalam environment
sandbox_env$secret_key <- "0xDEADBEEF"
assign("max_retries", 5L, envir = sandbox_env)

# Verifikasi keberadaan binding
ls(sandbox_env)
# [1] "max_retries" "secret_key"

# 3. Bukti Reference Semantics (Tidak ada copy-on-modify)
env_alias <- sandbox_env
env_alias$secret_key <- "0xCAFEFEED"

# Nilai di sandbox_env ikut berubah secara in-place!
print(sandbox_env$secret_key)
# [1] "0xCAFEFEED"

# 4. Lexical Scoping Check: Enclosing vs Calling Environment
f_generator <- function(offset) {
  # Execution environment f_generator menjadi enclosing environment bagi inner_fn
  inner_fn <- function(x) {
    x + offset # 'offset' dicari di enclosing environment
  }
  return(inner_fn)
}

add_ten <- f_generator(10)
print(add_ten(5))
# [1] 15

# Inspeksi pointer lingkungan closure
closure_env <- environment(add_ten)
print(closure_env)
# <environment: 0x...> (Alamat memori execution frame f_generator)
print(ls(closure_env))
# [1] "inner_fn" "offset"
print(closure_env$offset)
# [1] 10
```

---

### 10. Practical Example
Pola tingkat produksi: **Thread-Safe In-Memory LRU-like TTL Cache Engine**. Menggunakan *environment* sebagai *hash map* O(1) dengan isolasi penuh, menghindari polusi memori global dan mencegah kebocoran referensi data.

```r
# Production-Grade In-Memory Storage Engine with Environment Encapsulation
create_cache_manager <- function(default_ttl_sec = 300) {
  # Storage frame terisolasi sepenuhnya dari globalenv()
  cache_storage <- new.env(hash = TRUE, parent = emptyenv())
  metadata_storage <- new.env(hash = TRUE, parent = emptyenv())
  
  # Return kumpulan closure API (Interface Segregation)
  list(
    set = function(key, value, ttl = default_ttl_sec) {
      stopifnot(is.character(key) && length(key) == 1)
      
      # Menghindari copy overhead: simpan langsung via pointer
      assign(key, value, envir = cache_storage)
      assign(key, Sys.time() + ttl, envir = metadata_storage)
      
      invisible(TRUE)
    },
    
    get = function(key) {
      stopifnot(is.character(key) && length(key) == 1)
      
      if (!exists(key, envir = cache_storage, inherits = FALSE)) {
        return(NULL)
      }
      
      # Evaluasi Time-To-Live (TTL)
      expiry <- get(key, envir = metadata_storage, inherits = FALSE)
      if (Sys.time() > expiry) {
        # Lazy Eviction
        rm(list = key, envir = cache_storage)
        rm(list = key, envir = metadata_storage)
        return(NULL)
      }
      
      get(key, envir = cache_storage, inherits = FALSE)
    },
    
    purge_expired = function() {
      keys <- ls(cache_storage, all.names = TRUE)
      now <- Sys.time()
      purged_count <- 0
      
      for (k in keys) {
        exp <- get(k, envir = metadata_storage, inherits = FALSE)
        if (now > exp) {
          rm(list = k, envir = cache_storage)
          rm(list = k, envir = metadata_storage)
          purged_count <- purged_count + 1
        }
      }
      purged_count
    },
    
    metrics = function() {
      list(
        total_keys = length(ls(cache_storage, all.names = TRUE)),
        memory_bytes = as.numeric(pryr::object_size(cache_storage))
      )
    }
  )
}

# --- Driver Verification Code ---
cache <- create_cache_manager(default_ttl_sec = 2)

# Simpan objek komputasi analitik
cache$set("model_alpha", list(weights = c(0.12, 0.98), converged = TRUE))

# Ambil data sebelum expiry
res1 <- cache$get("model_alpha")
cat("Nilai Berhasil Diambil:", !is.null(res1), "\n")

# Tunggu sampai TTL kedaluwarsa
Sys.sleep(2.1)

# Verifikasi pembersihan otomatis
res2 <- cache$get("model_alpha")
cat("Nilai Setelah TTL Habis:", is.null(res2), "\n")
```

---

### 11. Real World Example
**Studi Kasus: Kebocoran Memori Skala GB pada Engine Valuasi Risiko Finansial (Bank A)**.

#### Konteks:
Sebuah bank investasi menjalankan pipeline simulasi Monte Carlo untuk menghitung *Value-at-Risk* (VaR). Kode menggunakan *factory pattern* untuk menghasilkan fungsi diskon instrumen obligasi:

```r
# IMPLEMENTASI DEFEKTIF (Legacy Production)
create_discount_pricer_defective <- function(market_data_massive) {
  # market_data_massive berukuran 8 GB (tick-level quotes)
  zero_rates <- market_data_massive$zero_curve # Hanya butuh kurva bunga (~50 KB)
  
  # Return pricing closure
  function(cashflow, maturity_year) {
    rate <- zero_rates[maturity_year]
    cashflow / ((1 + rate) ^ maturity_year)
  }
}
```

#### Masalah:
Pipeline memproses 1.000 portofolio secara serial dalam worker container berkapasitas 32 GB RAM. Setiap kali `create_discount_pricer_defective` dipanggil dan fungsi hasilnya disimpan dalam daftar portofolio, memori container bertambah 8 GB. Pada portofolio ke-4, sistem terhenti secara mendadak akibat *Kernel OOM-Killer* (Out-Of-Memory).

#### Penyebab Akar (Root Cause):
Fungsi anak (*returned closure*) mengikat `market_data_massive` di dalam *enclosing execution frame*-nya. Meskipun `market_data_massive` tidak pernah lagi dipanggil di dalam *closure body*, R runtime tidak mendeteksi analisis *dead-code* otomatis untuk GC frame. Objek 8 GB tertahan permanen di RAM heap.

#### Solusi Arsitektural:
Sanitasi manual pada *execution environment* sebelum mengembalikan closure:

```r
# IMPLEMENTASI PERBAIKAN (Production Patch)
create_discount_pricer_hardened <- function(market_data_massive) {
  # 1. Ekstraksi data atomik minimal
  zero_rates <- market_data_massive$zero_curve
  
  # 2. Definisikan lingkungan terisolasi baru secara eksplisit
  fn_env <- new.env(parent = baseenv())
  fn_env$zero_rates <- zero_rates
  
  # 3. Rakit fungsi di lingkungan baru yang bebas dari pointer 8 GB
  pricer <- function(cashflow, maturity_year) {
    rate <- zero_rates[maturity_year]
    cashflow / ((1 + rate) ^ maturity_year)
  }
  
  # Mutasi enclosing environment fungsi
  environment(pricer) <- fn_env
  
  # 4. Hapus referensi parameter lokal secara eksplisit (Good Practice)
  rm(market_data_massive)
  
  return(pricer)
}
```
**Hasil**: Konsumsi RAM per *pricer instance* anjlok dari **8.000.054.210 byte** ke **51.240 byte** (penghematan >99.9%), container dapat memproses 100.000 simulasi dengan stabil pada footprint < 1.5 GB RAM.

---

### 12. Trade-offs

| Pendekatan | Keuntungan (*Advantages*) | Kerugian (*Disadvantages*) | Kompleksitas | Biaya (*Cost*) & Kinerja |
| :--- | :--- | :--- | :--- | :--- |
| **Environments (`ENVSXP`)** | Operasi in-place referensial; pencarian kunci O(1) berbasis hash; isolasi state tanpa *side-effects* global. | Mengabaikan fungsional murni; rentan terhadap memory leak tersembunyi; tidak bisa diserialisasi secara trivial. | Tinggi (Memerlukan pemahaman C pointer runtime). | CPU: Sangat Rendah (Pencarian cepat).<br>RAM: Rendah jika dikelola, bahaya jika bocor. |
| **Standard Lists (`VECSXP`)** | Mengikuti semantik fungsional R; aman dari race conditions; representasi data transparan; mudah di-*serialize*. | Perilaku *copy-on-modify* menyebabkan memory re-allocation besar saat manipulasi array besar. | Rendah (Pola idiomatis R standar). | CPU: Tinggi jika sering di-update.<br>RAM: Puncak utilisasi memori fluktuatif (duplikasi buffer). |
| **R6 Classes** | Enkapsulasi OOP penuh berbasis lingkungan; sintaksis publik/privat terstruktur; memiliki destructor (`finalize`). | Overhead inisialisasi lebih tinggi daripada bare environments; *boilerplate* kode lebih tebal. | Menengah-Tinggi (Berorientasi objek formal). | CPU: Sedang (Metode dispatch via overhead env).<br>RAM: Sedikit overhead per instance metadata. |

---

### 13. When To Use
Gunakan manipulasi *environment* secara eksplisit ketika:
- Membangun *in-memory cache*, *connection pools* database, atau *stateful singleton registry*.
- Merancang arsitektur paket (*package development*) yang membutuhkan persistensi konfigurasi selama siklus hidup sesi R pengguna.
- Membutuhkan performa lookup berbasis kunci teks pada volume data besar (ratusan ribu entri) yang tidak memerlukan komputasi vektor tabel.
- Mengimplementasikan abstraksi sistem kelas berbasis referensi mandiri (mirip implementasi internal R6).

---

### 14. When NOT To Use
Jangan gunakan *environment* jika:
- Anda hanya melakukan transformasi data tabular standar; gunakan `data.table` atau struktur `data.frame` teroptimasi / `arrow`.
- Anda memerlukan struktur data yang harus di-serialize dan dikirim melalui jaringan (misalnya MPI cluster worker standar yang bergantung pada serialisasi murni via `serialize()`), karena pointer parent environment dapat ikut terseret secara masif.
- Anda menulis kode fungsional murni di mana *immutability* dan sifat *deterministic/pure functions* diwajibkan untuk pengujian unit (*unit testing*).

---

### 15. Common Mistakes
1. **Penyalahgunaan Super-assignment (`<<-`)**:
   ```r
   # Anti-pattern: Polusi namespace global tanpa kontrol
   calculate_kpi <- function(val) {
     total_metric <<- total_metric + val # Mencari hingga globalenv!
   }
   ```
   *Dampak*: Kode tidak modular, memicu kegagalan acak (*random side effects*) saat dipanggil paralel atau dalam testing pipeline.

2. **Mengabaikan Parameter `inherits = FALSE` pada `exists()` dan `get()`**:
   ```r
   env_test <- new.env()
   exists("mean", envir = env_test) # RETURN TRUE!
   ```
   *Dampak*: R akan mencari menembus parent hingga ke `package:base`. Kegagalan logika jika Anda ingin memvalidasi eksklusivitas key dalam frame tersebut. Solusi: Gunakan selalu `exists("mean", envir = env_test, inherits = FALSE)`.

3. **Retensi Argumen Ukuran Masif pada Closures**:
   Menulis fungsi pembangkit (*factory*) tanpa membersihkan argumen lokal yang besar sebelum fungsi anak dikembalikan (seperti dibahas pada *Real World Example*).

---

### 16. Best Practices (Production Checklist)

- [ ] **Validasi Inheritansi**: Selalu gunakan `inherits = FALSE` pada `get()`, `exists()`, dan `assign()` saat berurusan dengan struktur data mirip dictionary.
- [ ] **Putus Rantai Parent Saat Isolasi**: Buat *custom storage environment* menggunakan parameter eksplisit `parent = emptyenv()` untuk menghindari interferensi penelusuran namespace global/base.
- [ ] **Purging Sisa Variabel Pabrik (*Factory Cleaning*)**: Jika mengembalikan closure, hapus objek data intermediate besar dengan `rm()` sebelum terminasi factory, atau gunakan lingkungan terisolasi baru yang hanya berisi dependensi minimal.
- [ ] **Pemberian Tipe Hash Eksplisit**: Inisialisasi environment via `new.env(hash = TRUE)` jika diproyeksikan menampung lebih dari 100 elemen unik untuk menjamin efisiensi O(1).
- [ ] **Hindari Penggunaan `eval(parse(...))`**: Untuk manipulasi binding simbolik, gunakan selalu fungsi terstruktur `as.symbol()`, `rlang::sym()`, atau primitif `assign()`.

---

### 17. Troubleshooting

#### Masalah 1: Deteksi Objek Tak Terduga Muncul (*Symbol Masking*)
- **Simptom**: Fungsi membaca nilai konfigurasi yang salah padahal frame lingkungan lokal tidak mendefinisikannya.
- **Root Cause**: Penelusuran *Lexical Scoping* menemukan simbol dengan nama yang identik pada *package namespace* atau *Global Environment*.
- **Investigasi**:
  ```r
  # Identifikasi rantai ancestor
  rlang::env_parents(environment())
  # Temukan di frame mana simbol berada
  pryr::where("nama_variabel")
  ```
- **Solusi**: Nyatakan referensi simbol secara absolut (`pkg::var`) atau pastikan frame tidak mewarisi (*isolated parent*).

#### Masalah 2: Kebocoran Memori pada Worker API Plumber
- **Simptom**: RSS Memory container melonjak seiring jumlah request HTTP masuk.
- **Root Cause**: Handler route me-return closure atau mengikat objek ke *environment* sesi yang tidak di-garbage collect.
- **Investigasi**:
  ```r
  # Lacak ukuran lingkungan fungsi mencurigakan
  lobstr::obj_size(environment(leaking_function))
  ```
- **Solusi**: Pindahkan penyimpanan *state* ke persistent cache eksternal (misal: Redis) atau terapkan decoupling *enclosing environment* fungsi ke `emptyenv()`.

---

### 18. Exercise
**Instruksi Praktik Mandiri**:
Rancang sebuah fungsi *factory* bernama `create_secure_vault(initial_balance, pin_code)` yang mengembalikan sebuah antarmuka (*list of functions*) untuk manipulasi rekening bank.

**Syarat Batasan**:
1. Saldo (`balance`) dan sandi (`pin`) **dilarang keras** dapat diakses secara langsung dari `.GlobalEnv` atau melalui atribut objek luar.
2. Sediakan tiga metode antarmuka:
   - `deposit(amount)`: Menambah balance.
   - `withdraw(amount, input_pin)`: Memvalidasi sandi, menolak transaksi jika salah; mengurangi balance jika pin valid dan balance mencukupi.
   - `get_balance(input_pin)`: Mengembalikan balance jika pin valid.
3. Objek saldo harus berada dalam lingkungan terenkapsulasi yang parent-nya diarahkan ke `emptyenv()` untuk menjamin keamanan dari penelusuran leksikal luar (hanya bawa dependensi yang dibutuhkan secara eksplisit).

---

### 19. Challenge
Analisis cuplikan kode sistem produksi bermasalah berikut:

```r
# BUGGY ARCHITECTURE: Model Training Dispatcher
train_batch_models <- function(dataset) {
  threshold <- dataset$config$threshold
  heavy_matrices <- dataset$raw_data # 5 GB
  
  models <- list()
  for (i in 1:10) {
    cutoff <- threshold * i
    # BUG: Closure creation inside loop
    models[[i]] <- function(new_sample) {
      if (sum(new_sample) > cutoff) {
        return(TRUE)
      }
      return(FALSE)
    }
  }
  return(models)
}
```

**Tugas Anda**:
1. Identifikasi secara tepat mengapa kode di atas menyebabkan pemborosan memori parah ketika objek `models` disimpan ke disk via `saveRDS()`.
2. Jelaskan bahaya *scoping* terkait variabel `cutoff` dalam loop tersebut di runtime R.
3. Tulis ulang implementasi arsitektur fungsi di atas secara penuh (*refactored version*) sehingga:
   - Nilai `cutoff` terikat secara tepat (tidak merujuk ke nilai iterasi loop terakhir).
   - `heavy_matrices` sama sekali tidak terseret ke dalam memori model yang disimpan.
   - Ukuran serialisasi file RDS berkurang hingga ke ukuran minimal (< 5 KB per model).

---

### 20. Summary
- **Sifat Referensial**: *Environment* di R adalah objek `ENVSXP` yang mematuhi *reference semantics*. Perubahan nilai frame bersifat lokal dan instan tanpa proses duplikasi *copy-on-modify*.
- **Determinisme Penelusuran Leksikal**: Lokasi penelusuran simbol ditentukan oleh tempat fungsi **didefinisikan** (*enclosing environment*), bukan tempat fungsi **dijalankan** (*calling environment*).
- **Anatomi Closure**: Objek fungsi membawa serta *enclosing environment*-nya ke mana pun ia dikirim. Ini memberikan kapabilitas *state preservation* yang kuat, namun membawa risiko retensi memori fatal jika objek data besar tidak dibersihkan dari frame tersebut.
- **Keamanan Skala Enterprise**: Gunakan `parent = emptyenv()` dan flag `inherits = FALSE` ketika membangun struktur data internal berkinerja tinggi guna menjamin ketiadaan interferensi dari simbol luar yang dapat merusak integritas aplikasi di tahap produksi.