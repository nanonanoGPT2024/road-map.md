# BAB 01: Quiz, Challenge, & Knowledge Check
**Fondasi Modern PHP 8.x & Execution Model**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Zend Engine Pipeline Lifecycle:**  
   Jelaskan secara mendalam alur transformasi kode dari file mentah `.php` hingga dieksekusi sebagai instruksi CPU oleh Zend VM pada PHP 8.x (Tokenizing/Lexing, Abstract Syntax Tree/AST Parsing, Compilation to Opcodes, dan Execution via Virtual Machine). Bagaimana OPcache memotong siklus ini, dan pada tahap mana OPcache menyuntikkan hasil optimasinya?

2. **Filosofi Arsitektur "Shared-Nothing":**  
   PHP secara historis mengadopsi model *shared-nothing architecture* dalam konteks request lifecycle. Jelaskan secara teknis apa yang diisolasi antar-request (memori, state, superglobals, resource handles). Apa keuntungan fundamental arsitektur ini terhadap stabilitas aplikasi enterprise, dan apa konsekuensi trade-off-nya terhadap performa alokasi resource dan I/O latency?

3. **Mekanisme Memory Management (Reference Counting & Copy-on-Write):**  
   Jelaskan bagaimana Zend Memory Manager (ZMM) mengelola struktur data menggunakan `zval`, `refcount`, dan mekanisme *Copy-on-Write* (COW). Apa yang terjadi pada level pointer memori ketika sebuah array berukuran 50 MB di-*pass* ke dalam fungsi sebagai argumen nilai tanpa mutasi, dan apa yang memicu alokasi memori fisik baru saat elemen array tersebut dimutasi?

4. **Sematik Type Safety & Call-Site Enforcement:**  
   Mengapa deklarasi `declare(strict_types=1);` didesain untuk dievaluasi secara per-file dan ditegakkan pada tingkat *call-site* (tempat fungsi dipanggil), bukan pada tingkat *definition-site* (tempat fungsi dideklarasikan)? Analisis implikasi arsitekturalnya terhadap interoperabilitas kode warisan (*legacy code*) dengan pustaka modern berbasis PHP 8.x.

5. **OPcache vs Just-In-Time (JIT) Compilation:**  
   Bedakan secara fundamental peran dari OPcache standar dengan JIT compiler yang diperkenalkan sejak PHP 8.0. Mengapa aplikasi web tipikal (I/O-bound, berinteraksi dengan database/HTTP API) seringkali tidak mengalami peningkatan throughput yang signifikan saat JIT diaktifkan, sementara aplikasi CPU-bound (komputasi matematis, image processing, serialisasi biner) memperoleh performa berlipat ganda?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Garbage Collection Stop-the-World Analysis:**  
   Pada pemrosesan background worker (CLI) yang berjalan terus-menerus (*long-running process*), terjadi lonjakan CPU secara periodik yang membekukan eksekusi selama beberapa ratus milidetik. Analisis bagaimana Circular Reference Collector pada Zend Engine bekerja (struktur *Root Buffer*, threshold 10.000 elemen, algoritma penandaan ungu/abu-abu/hitam/putih). Kapan GC secara otomatis memicu proses pembersihan, dan bagaimana cara memitigasinya tanpa memicu *memory exhaustion*?

2. **Dinamika Tracing JIT vs Function JIT:**  
   Jelaskan perbedaan mekanis antara `Function JIT` dan `Tracing JIT` pada PHP 8.x. Bagaimana Tracing JIT mendeteksi *hot code paths* dan loop eksekusi? Kondisi spesifik apa saja yang menyebabkan Zend Engine melakukan *de-optimization* (de-opt) dan kembali mengeksekusi kode melalui interpreted VM bytecode?

3. **Type System Edge Cases: Type Juggling vs DNF Types:**  
   Diberikan definisi tipe Disjunctive Normal Form (DNF) pada PHP 8.2+: `(HasLogger&HasFormatter)|NullOutput`.  
   Bagaimana engine melakukan validasi tipe ini secara internal saat menerima instance objek? Bandingkan kompleksitas runtime check ini terhadap *scalar union types* (misal: `int|float|string`) ketika `strict_types=0` aktif, di mana engine harus melakukan *coercion prioritization*.

4. **Deep-Dive Arsitektur PHP-FPM Worker Pool:**  
   Dalam konfigurasi PHP-FPM, jelaskan perbedaan alokasi sumber daya sistem (RAM/CPU context switching) antara mode `pm = dynamic` dan `pm = static`. Mengapa pengaturan nilai `pm.max_requests` yang terlalu rendah pada sistem dengan konkurensi 10.000 RPS dapat menyebabkan degradasi performa (*thundering herd problem* dan *cold cache AST compilation*), sementara nilai `0` (unlimited) berisiko mematikan server?

5. **Internal Memory Layout `zval` pada Arsitektur 64-bit:**  
   Ukuran `zval` di PHP 7/8 telah diperkecil secara radikal menjadi 16 byte. Jelaskan bagaimana union `zend_value` dan byte flags (type, type_flags, u2) dikemas dalam representasi 16 byte tersebut. Jelaskan pula bagaimana flag `IS_TYPE_REFCOUNTED` dan `IS_TYPE_IMMUTABLE` membedakan string biasa dari *interned string* yang disimpan dalam memori bersama (*Shared Memory* / SHM) OPcache.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Bottleneck Produksi (OPcache Buffer Exhaustion & Cache Stampede)
Sebuah platform e-commerce monolitik berbasis PHP 8.2 mengalami insiden saat kampanye flash sale:
- **Gejala:** Latency p99 melonjak dari 45ms ke 3.200ms. CPU utilization pada cluster FPM mencapai 100%, sementara pemanfaatan database (RDS) berada di bawah 25%.
- **Observasi Metrik:**
  ```json
  {
    "opcache_enabled": true,
    "cache_full": true,
    "restart_pending": true,
    "restart_in_progress": true,
    "wasted_memory_percentage": 28.4
  }
  ```
- **Karakteristik Kode:** Aplikasi memiliki 45.000 file script PHP karena dependensi framework dan vendor packages yang masif.

**Pertanyaan Diagnostik:**
1. Identifikasi akar penyebab kegagalan berdasarkan observasi status OPcache di atas. Apa korelasi antara `restart_in_progress` dengan lonjakan CPU dan waktu respons?
2. Parameter `php.ini` spesifik apa saja yang harus dievaluasi ulang (sebutkan minimal 4 direktif OPcache krusial) beserta rekomendasi perhitungannya?
3. Bagaimana implementasi *OPcache Preloading* dapat menyelesaikan masalah ini secara permanen, dan apa risiko operasional yang harus diperhitungkan dalam alur deployment CI/CD?

---

### Skenario B: Race Condition & Data Corruption pada Runtimes Asinkron/Long-Running
Sebuah tim merefaktor aplikasi microservice dari PHP-FPM tradisional ke runtime *long-running* berbasis Swoole / RoadRunner untuk memangkas latensi alokasi memori. Dua minggu pasca rilis, audit keamanan menemukan anomali: **Data profil User A (alamat email, token pembayaran) secara acak terkirim ke User B pada respons API pembayaran.**

**Snippet Kode Tersangka:**
```php
class OrderService
{
    private static ?RequestContext $currentContext = null;
    private PaymentGateway $gateway;

    public function __construct(PaymentGateway $gateway) {
        $this->gateway = $gateway;
    }

    public function process(Request $request): Response {
        self::$currentContext = new RequestContext($request->getAuthUser());
        
        // Asynchronous/Concurrent I/O operation
        $paymentResult = $this->gateway->charge(self::$currentContext->getUserId(), $request->getAmount());

        return new Response([
            'user' => self::$currentContext->getUserData(),
            'status' => $paymentResult->status
        ]);
    }
}
```

**Pertanyaan Diagnostik:**
1. Analisis secara mekanis bagaimana arsitektur *long-running persistent worker* merusak asumsi *lifecycle* PHP-FPM standar pada kode di atas sehingga menyebabkan kebocoran data (*state leakage*).
2. Tunjukkan baris-baris kritis yang melanggar prinsip *concurrency safety* di lingkungan multi-fiber/coroutine runtime.
3. Desain solusi arsitektur untuk memperbaiki masalah ini: Bagaimana cara mengelola *per-request context* secara aman tanpa merusak pola *Dependency Injection* pada runtime long-running?

---

### Skenario C: Arsitektur & Trade-Off Sistem (FPM vs FrankenPHP/RoadRunner)
Sebagai Principal Architect, Anda diminta menentukan arsitektur execution runtime untuk sistem core banking generasi baru yang harus menangani 20.000 transaksi per detik (TPS) dengan toleransi downtime 0% (High Availability).

**Pilihan Pendekatan:**
- **Opsi 1:** Tradisional PHP-FPM dengan NGINX reverse proxy, OPcache tuning maksimal, dan Preloading.
- **Opsi 2:** Worker-based application server menggunakan FrankenPHP (Caddy server integration) atau RoadRunner (Go-based process manager) dengan stateful resident memory.

**Pertanyaan Diagnostik:**
1. Sajikan analisis perbandingan *trade-off* mendalam antar kedua pendekatan tersebut, mencakup matriks:
   - Alokasi & Kebocoran Memori (Memory Leaks blast radius).
   - Database Connection Management (Overhead koneksi TCP vs Persistent Connection / Connection Pooling).
   - Zero-Downtime Deployment & Graceful Reloading.
   - Developer Cognitive Load & Debugging Complexity.
2. Dalam skenario kegagalan fatal (*fatal error*, *unhandled exception*, atau `SIGSEGV` pada C-extension), bagaimana perilaku isolasi proses pada masing-masing opsi?
3. Berikan keputusan final arsitektur Anda dengan justifikasi mitigasi teknis jika memilih opsi dengan risiko stabilitas lebih tinggi.

---

## 4. Chapter Challenge

**Tantangan Praktis: Engine Internals Diagnostic Profiler & Memory Isolation Suite**

### Problem Statement
Banyak tim engineering mengalami memory leak tersembunyi (*slow creep memory leakage*) dan beban GC yang berlebihan pada pemrosesan batch data bervolume tinggi di CLI. Anda ditantang untuk membangun sebuah *Micro Diagnostic Engine Profiler* murni menggunakan PHP 8.x tanpa bantuan library/vendor eksternal yang mampu membuktikan cara kerja internal Zend Engine.

### Requirements
Bangun satu script standalone bernama `EngineProfiler.php` yang memenuhi fungsionalitas berikut:
1. **ZMM (Zend Memory Manager) Deep Tracker:**
   - Mengukur alokasi memori internal *real* (`memory_get_usage(true)`) versus alokasi memori yang diminta oleh script (`memory_get_usage(false)`).
   - Menghitung rasio fragmentasi memori ZMM sebelum dan sesudah eksekusi tugas.
2. **Circular Reference Detector & GC Impact Benchmark:**
   - Buat skenario buatan yang menginstansiasi 100.000 objek dengan referensi melingkar (*self-referencing graph*).
   - Ukur waktu eksekusi presisi mikrosekon ($\mu s$) dan konsumsi memori saat:
     - GC dimatikan secara manual (`gc_disable()`).
     - GC dibiarkan default.
     - GC dipicu secara deterministik menggunakan `gc_collect_cycles()`.
   - Cetak jumlah siklus (*cycles*) yang berhasil dibebaskan oleh Zend Engine.
3. **Copy-on-Write (COW) Verification Mechanism:**
   - Gunakan fungsi bawaan engine (`memory_get_usage`) untuk membuktikan fenomena Copy-on-Write secara empiris:
     - Tahap A: Buat array berukuran 100.000 elemen numerik.
     - Tahap B: Gandakan array tersebut ke variabel baru ($copy = $original). Tunjukkan bahwa alokasi memori tidak naik signifikan (pointer sharing).
     - Tahap C: Modifikasi indeks pertama dari array duplikat ($copy[0] = 9999). Tunjukkan lonjakan memori akibat duplikasi buffer fisik oleh ZMM.
4. **Output Structured Report:**
   - Output terminal harus diformat secara elegan (ANSI color-coded) atau terstruktur dalam bentuk tabel Markdown yang mencantumkan ringkasan metrik: Alokasi ZMM, Siklus GC, Deteksi COW, serta status OPcache runtime jika aktif.

### Constraints
- Wajib menggunakan fitur modern PHP 8.x: *Typed Properties, Readonly properties/classes, Match expressions, dan Named Arguments*.
- `declare(strict_types=1);` wajib diterapkan.
- Tidak boleh menggunakan ekstensi eksternal selain ekstensi core PHP (ekstensi seperti `xdebug` dilarang).
- Penggunaan memori puncak profiler sendiri harus seminimal mungkin agar tidak mengaburkan hasil benchmark.

### Expected Output
Terminal harus menampilkan visualisasi eksekusi serupa berikut:
```text
================================================================================
           ZEND ENGINE 8.x INTERNALS DIAGNOSTIC & BENCHMARK REPORT
================================================================================
[PHP Version]: 8.x.x | [SAPI]: cli | [Zend OPcache]: Active/Inactive | [JIT]: On/Off
--------------------------------------------------------------------------------
1. COPY-ON-WRITE (COW) PROOF:
   - Initial Array Allocation (100k items) : 4,096.12 KB
   - Shadow Copy Variable ($b = $a)        : +0.08 KB (Proof of reference sharing)
   - Mutation Induced ($b[0] = 999)        : +4,096.05 KB (Proof of buffer clone)
   => COW Verification: PASSED (ZMM delayed clone verified)

2. CIRCULAR REFERENCE GARBAGE COLLECTION PROFILING:
   - Uncollected Leaked Nodes              : 100,000 nodes
   - GC Disable Phase Memory               : XX,XXX KB
   - gc_collect_cycles() Harvested Cycles  : 100,000 cycles
   - GC Latency Cost                       : X.XXX ms (Stop-The-World Impact)

3. ZMM ALLOCATION VS SYSTEM BRK/MMAP:
   - Allocated to Script                   : X,XXX.XX KB
   - Reserved by Engine (Real)             : X,XXX.XX KB
   - Fragmentation Index                   : X.XX%
================================================================================
```

---

## 5. Knowledge Check & Checklist

Verifikasi kesiapan pemahaman Anda sebelum melangkah ke bab berikutnya. Berikan tanda centang jika Anda telah menguasai kompetensi di bawah ini secara konseptual dan praktis.

### Saya harus memahami:
- [ ] Siklus internal Zend Engine: Lexing $\rightarrow$ AST generation $\rightarrow$ Compilation $\rightarrow$ Opcode emission $\rightarrow$ VM Execution.
- [ ] Perbedaan fundamental arsitektur *Shared-Nothing* pada PHP-FPM dibandingkan model *Persistent Resident State* (Swoole, RoadRunner, FrankenPHP).
- [ ] Mekanisme alokasi memori `zval`, representasi internal 16-byte, Reference Counting, dan prinsip kerja Copy-on-Write (COW).
- [ ] Cara kerja Circular Garbage Collection (Buffer Root 10.000 siklus) dan strategi mengatasi *GC stop-the-world latency spikes*.
- [ ] Cara kerja OPcache dalam menyimpan Opcodes di Shared Memory (SHM) dan mekanisme Tracing JIT dalam mengompilasi hot bytecode ke native machine code via DynASM.
- [ ] Aturan resolusi Type System modern PHP 8.x: Strict Types Call-Site vs Definition-Site, Union Types, Intersection Types, dan Disjunctive Normal Form (DNF).

### Saya tidak perlu menghafal:
- [ ] Seluruh opcode number/C-macro definition dari Zend Engine (misal: konstanta ID biner `ZEND_ADD`, `ZEND_ECHO`).
- [ ] Syntax C internal untuk penulisan ekstensi Zend (`zend_parse_parameters`, `ZVAL_COPY_VALUE`) di luar arsitektur pemahaman teoritisnya.
- [ ] Nilai bitmask heksadesimal dari flag status internal `zval` (`IS_TYPE_REFCOUNTED`, `IS_TYPE_COPYABLE`). Cukup pahami semantik perilakunya.

### Saya harus bisa melakukan:
- [ ] Mendiagnosis dan mengonfigurasi optimal parameter produksi PHP-FPM (`pm`, `pm.max_children`, `pm.max_requests`, `pm.process_idle_timeout`) berbasis kapasitas core CPU dan RAM server.
- [ ] Menganalisis metrik `opcache_get_status()` dan `opcache_get_configuration()` untuk mencegah crash akibat memory buffer exhaustion dan cache invalidation storms.
- [ ] Menulis kode yang aman dari ancaman *state contamination* / *memory leakage* saat di-deploy ke environment runtime long-running (Swoole, RoadRunner, dsb.).
- [ ] Mengontrol alokasi memori CLI worker intensif dengan manipulasi `gc_enable()`, `gc_disable()`, dan penempatan strategis `gc_collect_cycles()`.
- [ ] Melakukan benchmark performa komputasi murni dengan dan tanpa JIT Compiler untuk membuktikan kelayakan implementasi fitur berbasis data empiris.