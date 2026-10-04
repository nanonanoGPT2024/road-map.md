# BAB 01: Quiz, Challenge, & Knowledge Check
**Bab 01**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Pipeline Kompilasi C++ End-to-End**
   Jelaskan secara mendalam empat tahapan utama dalam transformasi kode sumber C++ menjadi executable biner (*Preprocessing*, *Compilation*, *Assembly*, *Linking*). Analisis artifak/representasi intermediate apa yang dihasilkan pada setiap fase, dan jelaskan pada fase mana tipe data (*type system*) diverifikasi serta kapan resolusi alamat simbolik dilakukan.

2. **One Definition Rule (ODR) & Translation Units (TU)**
   Definisikan apa yang dimaksud dengan *Translation Unit* (TU) dan jelaskan prinsip fundamental *One Definition Rule* (ODR). Bedakan batasan ODR di dalam satu TU tunggal (*single TU*) dibandingkan dengan batasan ODR lintas TU (*cross-TU*) untuk:
   - Fungsi non-inline dan variabel global.
   - Definisi `class`/`struct` dan `inline function`.
   Apa konsekuensi arsitektural jika pelanggaran ODR lolos dari deteksi compiler?

3. **Storage Duration vs. Segmen Memori Biner (ELF/PE)**
   C++ mendefinisikan empat jenis *storage duration*: *automatic*, *static*, *thread*, dan *dynamic*. Petakan masing-masing storage duration tersebut ke segmen memori biner tingkat rendah (*Stack*, *Heap*, `.data`, `.bss`, `.text`, `.tbss`/`.tdata`). Jelaskan siklus hidup (*lifetime*) dan mekanisme inisialisasi dari variabel `static` lokal di dalam sebuah fungsi (termasuk implikasi *thread-safety* pasca C++11).

4. **Internal Linkage vs. External Linkage**
   Bandingkan mekanisme *internal linkage* (penggunaan `static` pada file-scope atau *unnamed/anonymous namespace*) dengan *external linkage* (variabel global non-static atau fungsi standar). Bagaimana linker OS memperlakukan simbol-simbol ini pada tabel simbol (*symbol table*) file objek (`.o`/`.obj`), dan bagaimana dampaknya terhadap *binary size* serta *symbol collision* pada proyek skala enterprise?

5. **Mekanisme Inisialisasi & Most Vexing Parse**
   Jelaskan hierarki dan perbedaan semantik antara *Zero-Initialization*, *Default-Initialization*, *Value-Initialization*, dan *Direct-List-Initialization* (menggunakan kurung kurawal `{}`). Tunjukkan bagaimana *Direct-List-Initialization* mencegah *narrowing conversion* dan bagaimana sintaks ini menyelesaikan ambiguitas parsing historis C++ yang dikenal sebagai *Most Vexing Parse*.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Semantik `inline` Modern & Multiple Definition Stripping**
   Dalam C++ modern (C++17/20), kata kunci `inline` tidak lagi sekadar menjadi petunjuk (*compiler hint*) untuk ekspansi kode in-place. Jelaskan fungsi formal `inline` terhadap ODR dan tabel simbol linker. Bagaimana linker menangani multiple identical weak symbols dari header yang disertakan di belasan TU berbeda tanpa menghasilkan galat *duplicate symbol*?

2. **Static Initialization Order Fiasco (SIOF) & Mitigasinya**
   Jelaskan apa itu *Static Initialization Order Fiasco* (SIOF), mengapa standar C++ tidak menjamin urutan inisialisasi objek global/static lintas translation unit yang berbeda, dan bagaimana skenario ini memicu *Undefined Behavior* (akses memori sebelum diinisialisasi). Uraikan secara teknis implementasi idiom *Construct On First Use* (Meyers' Singleton) untuk meniadakan race condition inisialisasi ini.

3. **Undefined Behavior (UB), Optimasi Kompiler, & Time-Travel Debugging**
   Jelaskan perbedaan mendasar antara *Undefined Behavior* (UB), *Unspecified Behavior*, dan *Implementation-Defined Behavior*. Berikan contoh bagaimana *Aggressive Dead-Code Elimination* atau *Loop Optimization* oleh optimizer (Clang/GCC dengan flag `-O3`) dapat mengeksploitasi asumsi ketiadaan UB (misalnya pada kasus *signed integer overflow* atau *null-pointer dereference*) sehingga mengubah alur logika program secara radikal.

4. **Name Mangling, ABI Compatibility, & Interoperabilitas `extern "C"`**
   Mengapa C++ memerlukan *Name Mangling* sedangkan C murni tidak? Jelaskan informasi struktural apa saja yang di-encode oleh compiler ke dalam mangled name suatu fungsi. Jelaskan peran direktif `extern "C"` dalam menonaktifkan mangling ini, konsekuensinya terhadap fitur *function overloading*, serta implikasinya terhadap stabilitas *Application Binary Interface* (ABI) pada shared library (`.so`/`.dll`).

5. **Diagnostik Segfault: Stack Corruption vs. Dangling Stack Reference**
   Diberikan skenario di mana aplikasi mengalami crash dengan sinyal `SIGSEGV` saat runtime:
   - Kasus 1: Melewati batas alokasi stack (*stack overflow* akibat rekursi tak terbatas).
   - Kasus 2: Mengakses referensi/pointer ke objek lokal yang frame stack-nya telah di-*unwind* (*dangling pointer/use-after-return*).
   Jelaskan bagaimana compiler menyusun frame stack (register `RBP`/`RSP`, *return address*), mengapa Kasus 2 sering kali tidak langsung crash saat dereferensi pertama (*silent corruption*), dan bagaimana flags `-fstack-protector-all` serta AddressSanitizer (`-fsanitize=address`) mendeteksi kedua anomali ini.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Waktu Build Monolitik & Dependency Bloat (45 Menit Bottleneck)
Sebuah sistem core-banking dengan basis kode C++20 monolitik mengalami eskalasi durasi kompilasi dari 6 menit menjadi 52 menit per build di pipeline CI/CD setelah integrasi modul analitik baru. Pemeriksaan awal menunjukkan bahwa file header inti (`CoreContext.hpp`) secara transitif meng-`#include` hampir 80% header dependensi lain, termasuk template meta-programming utilities dan library eksternal berukuran masif. 

*Pertanyaan Diagnostik:*
1. Bagaimana Anda mengukur dan memetakan kontribusi waktu kompilasi dari masing-masing Translation Unit menggunakan fitur diagnostik compiler (misalnya `-ftime-trace` pada Clang atau `-ftime-report` pada GCC)?
2. Rancang strategi restrukturisasi dependensi untuk mereduksi *blast radius* rekompilasi. Bandingkan efektivitas implementasi *Forward Declarations*, teknik *PIMPL Idiom* (Pointer to Implementation), dan migrasi parsial ke *C++20 Modules* (`import` vs `#include`).

---

### Skenario B: Silent Memory Corruption akibat Pelanggaran ODR Lintas Build Target
Sistem High-Frequency Trading (HFT) mengalami *undefined behavior* acak: beberapa order trading tereksekusi dengan nilai quantity yang terdistorsi secara sporadis di lingkungan staging, namun tidak pernah dapat direproduksi di unit test lokal. Hasil dump memori menunjukkan bahwa struct `OrderBookEntry` memiliki ukuran memori 64 byte di TU `MarketDataReceiver.cpp`, namun berukuran 72 byte di TU `RiskEngine.cpp`. Perbedaan ini dipicu oleh compile-time macro flag (`-DENABLE_EXTENDED_METRICS`) yang hanya diaktifkan pada build target modul `RiskEngine`.

*Pertanyaan Diagnostik:*
1. Mengapa compiler dan linker klasik sering kali gagal mendeteksi ketidakcocokan layout memori struct antar-TU ini (*silent pass* di tahap link)?
2. Bagaimana mekanisme AddressSanitizer/UndefinedBehaviorSanitizer (ASan/UBSan) atau Link-Time Optimization (`-flto`) membantu mengidentifikasi pelanggaran ODR spesifik ini?
3. Rancang arsitektur pencegahan pada level build system (CMake/Bazel) dan code-level architecture untuk memastikan integritas single-definition pada tipe data kritis.

---

### Skenario C: Trade-off Arsitektur Sistem Embedded/Kernel-Bypass: Zero-Allocation vs. Binary Footprint
Anda ditunjuk sebagai Principal Architect untuk merancang platform telemetri zero-copy ultra-low-latency yang berjalan pada embedded target dengan constraint memori RAM fisik ketat (hanya 32 MB). Sistem menuntut determinisme absolut (jitter < 1 mikrodetik). Tim memperdebatkan dua pendekatan arsitektur penyimpanan status global:
- **Pendekatan 1:** Menggunakan *Zero Dynamic Allocation* murni dengan pre-allocated static arenas di segmen `.bss`/`.data`.
- **Pendekatan 2:** Menggunakan *Custom Memory Pool* terisolasi yang dialokasikan di awal runtime (`mmap`/`malloc`) dengan segmentasi modular berbasis smart pointers kustom.

*Pertanyaan Diagnostik:*
1. Analisis konsekuensi pendekatan 1 terhadap ukuran file biner (*flash footprint*), waktu loading OS (ELF loader overhead), serta potensi resiko SIOF saat *startup*.
2. Analisis konsekuensi pendekatan 2 terhadap fragmentasi memori, *cache locality* (L1/L2 hits vs misses), dan *page fault latencies*.
3. Apa keputusan teknis yang Anda rekomendasikan jika sistem tersebut wajib lolos uji keselamatan deterministik (hard real-time)? Berikan rasionalisasi berbasis arsitektur memori C++.

---

## 4. Chapter Challenge

**Tantangan Praktis: Rekonstruksi ELF/Mach-O Symbol Inspection & Custom ODR Violation Detector Tool**

### Deskripsi Masalah:
Dalam proyek enterprise multi-repo, pelanggaran ODR dan polusi simbol global sering kali merusak stabilitas runtime tanpa peringatan compiler. Anda diminta membangun sebuah tool utilitas baris perintah (*CLI diagnostic tool*) sederhana dalam C++ modern (C++20) atau script diagnostik berbasis binary tools yang mampu menganalisis file objek (`.o`/`.obj`) hasil kompilasi, membaca tabel simbol, dan mendeteksi potensi duplikasi simbol, kebocoran *internal linkage*, atau mismatch ukuran data.

### Requirements:
1. **Source Generator:**
   - Buat minimal dua Translation Unit (`module_a.cpp` dan `module_b.cpp`) yang secara sengaja mengintroduksi:
     - Satu pelanggaran ODR layout struct (definisi field berbeda di bawah kondisi conditional compilation yang tidak sinkron).
     - Satu pelanggaran SIOF (objek global A di TU 1 mengakses objek global B di TU 2 pada saat inisialisasi).
     - Satu penggunaan variabel dengan *internal linkage* (`static`) di dalam header file yang disertakan oleh kedua TU.
2. **Analysis Pipeline:**
   - Kompilasi file objek secara terpisah menggunakan flag compiler standar (`-c -Wall -Wextra`).
   - Buat skrip otomatisasi atau binary tool C++ yang mem-parsing tabel simbol (menggunakan `nm`, `readelf`, atau `objdump` secara terprogram, atau parsing langsung ELF header) untuk:
     - Mengidentifikasi simbol yang terduplikasi di segmen BSS/Data.
     - Mendeteksi ukuran simbol struct yang tidak identik antar file objek sebelum linker dijalankan.
     - Melaporkan apakah simbol masuk kategori Weak (`W`/`V`), Global (`T`/`D`/`B`), atau Local (`t`/`d`/`b`).
3. **Remediasi:**
   - Refaktor kode sumber yang salah menggunakan modern idioms (`inline constexpr`, `std::unique_ptr` dengan PIMPL, anonymous namespaces yang terisolasi, dan *Construct On First Use* pattern).

### Constraints:
- Kode C++ wajib kompatibel minimal dengan standar C++20.
- Tidak boleh menggunakan *dynamic memory allocation* (`new`/`delete` eksplisit); gunakan modern memory safety patterns.
- Wajib menyertakan parameter kompilasi `-Wall -Wextra -Werror -pedantic` tanpa menghasilkan warning apa pun pada kode hasil refaktor.

### Expected Output:
1. Log eksekusi CLI tool yang memvalidasi deteksi sebelum refaktor:
   ```text
   [WARNING] Potential ODR Mismatch detected for symbol 'ConfigPayload':
     - module_a.o: size = 64 bytes, linkage = GLOBAL
     - module_b.o: size = 72 bytes, linkage = GLOBAL
   [ALERT] Duplicate internal linkage pollution detected from header: 'shared_counter'
   ```
2. Hasil verifikasi AddressSanitizer (`-fsanitize=address,undefined`) yang membuktikan runtime bersih (0 memory leaks, 0 SIOF errors) pasca refaktor.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Alur transformasi detail: Preprocessing (`#include`, macro expansion) $\rightarrow$ Compilation (AST, Type Checking, Intermediate Representation) $\rightarrow$ Assembly (Instruksi Mesin/Opcode) $\rightarrow$ Linking (Resolusi Simbol, Address Relocation).
- [ ] Aturan ketat *One Definition Rule* (ODR) untuk variabel, fungsi biasa, `inline` functions, template, dan tipe kelas lintas Translation Unit.
- [ ] Pemetaan memori biner C++: Perbedaan mendasar antara Stack, Heap, Data (`.data`), BSS (`.bss`), Text (`.text`), dan segmen Read-Only Data (`.rodata`).
- [ ] Dampak visibilitas simbol: Perbedaan teknis `static` pada file-scope, anonymous namespace, dan `extern`.
- [ ] Risiko fatal *Static Initialization Order Fiasco* (SIOF) serta implementasi idiom *Construct On First Use*.
- [ ] Perbedaan kategori perilaku: *Well-defined*, *Implementation-defined*, *Unspecified*, dan *Undefined Behavior* (UB).
- [ ] Implikasi ABI, *Name Mangling*, dan kegunaan blok `extern "C"` untuk foreign function interface.

### Saya tidak perlu menghafal:
- [ ] Spesifikasi byte-by-byte struktur header format file binary biner (seperti ELF Header offsets atau PE/COFF magic numbers).
- [ ] Algoritma encoding karakter spesifik dari ABI Name Mangling compiler tertentu (misalnya Itanium ABI vs Microsoft Visual C++ ABI mangling rules).
- [ ] Nilai hex spesifik untuk setiap assembly opcode arsitektur x86_64 atau ARM.

### Saya harus bisa melakukan:
- [ ] Menginspeksi tabel simbol biner file objek dan shared object menggunakan command-line tools (`nm`, `readelf -s`, `objdump -t`, `c++filt`).
- [ ] Menggunakan flags diagnostik compiler (`-E` untuk output preprocessor, `-S` untuk assembly, `-ftime-trace` untuk profiling waktu build).
- [ ] Menulis dan mengeksekusi pipeline kompilasi multi-file secara manual tanpa IDE menggunakan GCC/Clang via terminal.
- [ ] Menjalankan sanitizers (`-fsanitize=address,undefined`) untuk menangkap memory error dan pelanggaran ODR saat eksekusi pengujian.
- [ ] Mencegah inisialisasi ganda dan *Most Vexing Parse* secara konsisten menggunakan *Uniform List Initialization* (`{}`).