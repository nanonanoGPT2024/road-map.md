---
[⬅️ Module 02: Kompilasi, JIT, GC, & Profiling](./Module-02-Kompilasi-JIT-Garbage-Collection-dan-Profiling.md) | [📋 Silabus Induk](../README.md) | [BAB 03 Module 01: Desain RESTful API & Idempotency ➡️](../BAB-03-Arsitektur-API-REST-GraphQL-gRPC/Module-01-Desain-RESTful-API-Richardson-Maturity-Idempotency.md)
---

# BAB 02: Bahasa Pemrograman Backend & Runtime Execution — Quiz & Chapter Challenge

Dokumen ini berisi pengujian pemahaman konseptual, analisis skenario alokasi memori dan konkurensi runtime, serta tantangan implementasi sistematis untuk BAB 02.

---

## Bagian 1: Quiz Konseptual Dasar (5 Soal)

### Soal 1
Manakah karakteristik yang benar mengenai alokasi memori pada **Stack** dibandingkan dengan **Heap**?
- A. Stack dikelola oleh Garbage Collector dan ukurannya fleksibel tanpa batas.
- B. Stack beroperasi menggunakan model LIFO (*Last-In, First-Out*), alokasinya sangat cepat (hanya menggeser register pointer CPU), dan otomatis dibersihkan saat stack frame fungsi selesai.
- C. Stack digunakan khusus untuk menyimpan objek JSON yang kompleks.
- D. Heap memiliki kecepatan akses 10x lebih cepat daripada Stack.

### Soal 2
Dalam model konkurensi Single-Threaded Event Loop (seperti pada Node.js), apa yang akan terjadi jika sebuah handler mengeksekusi perulangan kalkulasi CPU-intensif selama 10 detik tanpa jeda?
- A. Node.js otomatis memecah perulangan tersebut ke 8 thread baru secara diam-diam.
- B. Event Loop utama akan terblokir (*blocked*), menyebabkan seluruh pengguna lain di server tidak dapat menerima respon apapun (*server freeze*) hingga kalkulasi tersebut selesai.
- C. Browser client akan otomatis me-restart Node.js server.
- D. Memori Heap akan langsung terformat ulang.

### Soal 3
Bagaimana algoritma **Work-Stealing** pada scheduler Go (M:N Scheduler) mengoptimalkan utilisasi CPU multi-core?
- A. Menghapus Goroutine yang memakan memori lebih dari 2KB.
- B. Jika antrean lokal tugas sebuah Processor ($P$) kosong, Processor tersebut akan mencuri separuh tugas dari antrean lokal Processor lain yang sedang sibuk, menjaga seluruh thread CPU tetap aktif bekerja.
- C. Memaksa sistem operasi mematikan kernel thread lain di luar Go.
- D. Mengubah kode Go menjadi instruksi Python saat runtime.

### Soal 4
Apa dasar ilmiah dari **Weak Generational Hypothesis** yang menjadi pondasi arsitektur Generational Garbage Collection (seperti pada JVM dan V8)?
- A. Semua objek di dalam komputer memiliki umur yang sama persis.
- B. Sebagian besar objek (95%+) memiliki masa hidup yang sangat singkat (*die young*) sesaat setelah dialokasikan (misal variabel lokal per request HTTP), sehingga pembersihan memori Young Generation menghasilkan efisiensi tertinggi.
- C. Objek lama selalu lebih mudah dihapus daripada objek baru.
- D. Garbage Collector hanya boleh dijalankan di malam hari.

### Soal 5
Apa yang dimaksud dengan fenomena **JIT Deoptimization (Bailout)** pada runtime seperti Node.js V8 atau Java HotSpot?
- A. Proses di mana JIT compiler membatalkan kode mesin assembly native yang telah dioptimasi dan beralih kembali ke bytecode interpreter lambat karena asumsi tipe data input tiba-tiba dilanggar (*type mismatch*).
- B. Kegagalan koneksi jaringan TCP saat mengunduh package npm.
- C. Memory leak yang diakibatkan oleh pointer null.
- D. Kompilasi otomatis saat server dimatikan.

---

## Bagian 2: Quiz Skenario & Troubleshooting Tingkat Menengah (5 Soal)

### Soal 6
Sebuah fungsi di Go memiliki kode berikut:
```go
func getAccount() *Account {
    acc := Account{ID: 101, Name: "Budi"}
    return &acc
}
```
Berdasarkan mekanisme **Escape Analysis**, di manakah variabel `acc` akan dialokasikan oleh compiler Go?
- A. Di Stack, karena dideklarasikan di dalam fungsi lokal.
- B. Di Heap (*escapes to heap*), karena fungsi mengembalikan pointer (`&acc`) yang masa hidupnya masih dibutuhkan di luar stack frame fungsi tersebut.
- C. Di ROM (Read-Only Memory).
- D. Di dalam cache CoreDNS.

### Soal 7
Aplikasi e-commerce Anda mengalami bug di mana total stok barang di database menjadi minus saat flash sale, padahal kode Anda memiliki pemeriksaan `if (stock > 0) stock = stock - 1`. Bug konkurensi apakah ini dan bagaimana memperbaikinya di level kode aplikasi backend?
- A. Deadlock; mitigasi: gunakan recursive loop.
- B. Race Condition (Data Race); mitigasi: lindungi blok baca-tulis kritis menggunakan Mutex Lock atau operasi database tingkat atomik (*Atomic UPDATE / SELECT FOR UPDATE*).
- C. Buffer Overflow; mitigasi: gunakan IPv6.
- D. Out of Memory; mitigasi: kurangi ukuran RAM.

### Soal 8
Pada event loop Node.js, jika sebuah `Promise.resolve().then(...)` (Microtask) dan `setTimeout(..., 0)` (Macrotask) dijadwalkan secara bersamaan, callback manakah yang akan dieksekusi terlebih dahulu oleh engine saat Call Stack kosong?
- A. Callback `setTimeout` karena waktu delay-nya 0.
- B. Callback `Promise.then` (Microtask Queue) selalu diproses dengan prioritas tertinggi hingga bersih sebelum Event Loop berpindah mengeksekusi Macrotask.
- C. Keduanya dieksekusi bersamaan di 2 thread terpisah.
- D. Bergantung pada sistem operasi Windows atau Linux.

### Soal 9
Aplikasi microservice Node.js Anda mengalami peningkatan penggunaan RAM secara konstan dari 200MB menjadi 1.4GB selama 24 jam hingga akhirnya crash dengan pesan:
`FATAL ERROR: Ineffective mark-compacts near heap limit Allocation failed - JavaScript heap out of memory`.
Setelah memeriksa Heap Snapshot di Chrome DevTools, Anda menemukan 500.000 objek tersimpan di sebuah array. Apa akar penyebab yang paling sering terjadi?
- A. Garbage collector dinonaktifkan oleh cloud provider.
- B. Array global digunakan sebagai in-memory cache tanpa batasan ukuran (*unbounded cache*), sehingga objek-objek tersebut tetap terikat pada GC Roots dan tidak pernah dibersihkan.
- C. Ukuran hard disk server penuh.
- D. Port 3000 terkena blokir firewall.

### Soal 10
Pada grafik **CPU Flame Graph** dari sebuah aplikasi Go, fungsi `json.Unmarshal` terlihat membentuk balok datar yang sangat lebar (mencakup 75% dari total lebar horizontal grafik). Apa makna dari visualisasi tersebut bagi seorang backend engineer?
- A. Fungsi `json.Unmarshal` berjalan sangat cepat tanpa memakan resource.
- B. Fungsi `json.Unmarshal` menghabiskan 75% dari total waktu CPU seluruh server dan menjadi bottleneck utama performa yang harus dioptimasi (misal mengganti JSON dengan Protobuf atau streaming parser).
- C. Terjadi deadlock di dalam kernel sistem operasi.
- D. Aplikasi mengalami kebocoran memori di fungsi tersebut.

---

## Bagian 3: Skenario Kasus Arsitektur Tingkat Lanjut (3 Soal)

### Skenario 1: Mitigasi Stop-The-World Latency Spike pada High-Throughput Service
Sebuah payment gateway memproses transaksi dengan SLA latensi p99 di bawah 50ms. Aplikasi ditulis menggunakan Java. Setiap 15 menit, terjadi jeda GC Stop-The-World (STW) selama 300ms yang melanggar SLA dan memicu komplain dari merchant.
Rancang langkah-langkah evaluasi dan mitigasi sistematis:
1. Pemilihan collector modern (G1GC vs ZGC vs Shenandoah).
2. Tuning parameter memori (rasio Young vs Tenured Generation).
3. Pola pemrograman backend untuk meminimalkan alokasi objek temporer di dalam loop transaksi (*Object Pooling*).

### Skenario 2: Arsitektur Worker Concurrency I/O-Bound vs CPU-Bound
Perusahaan Anda membangun platform analitik media:
- Tugas A: Mengunduh 100.000 artikel berita dari internet setiap hari (*I/O-Bound*).
- Tugas B: Menjalankan ekstraksi entitas NLP dan enkripsi dokumen (*CPU-Bound*).
Jelaskan bahasa pemrograman dan model konkurensi (Node.js Event Loop, Go Goroutines, atau Python Worker Pool) yang paling tepat untuk masing-masing tugas tersebut, dan berikan argumen arsitektur teknis yang mendasarinya!

### Skenario 3: Investigasi dan Mitigasi Goroutine Leaks di Produksi
Di sebuah cluster microservice Go, penggunaan RAM terus menanjak tajam setelah rilis fitur notifikasi baru. Metrik pprof menunjukkan jumlah Goroutine aktif melonjak dari 500 menjadi 85.000 Goroutine.
Jelaskan:
- Bagaimana pola kode (seperti unbuffered channel atau HTTP client tanpa timeout) dapat memicu Goroutine Leak.
- Cara menggunakan `go tool pprof` untuk melacak stack trace dari 85.000 goroutine yang macet tersebut.
- Pola perbaikan menggunakan `context.Context` dengan batas timeout pembatalan.

---

## Bagian 4: Chapter Challenge — Building a Zero-Allocation Object Pool & Concurrency Engine

### Deskripsi Tantangan
Anda diminta membangun sistem pemrosesan transaksi berkinerja tinggi di Go atau Node.js yang memproses **200.000 transaksi bersamaan**:
1. **Concurrency Control**:
   - Bangun worker pool konkuren dengan kapasitas maksimal 20 worker simultan.
   - Gunakan Mutex atau Channel atomik untuk menjamin pembaruan saldo akun bersama bebas dari *Race Condition*.
2. **Memory Optimization (Zero-Allocation Pooling)**:
   - Gunakan teknik *Object Pooling* (`sync.Pool` di Go atau custom pool di Node.js) untuk mendaur ulang objek payload transaksi tanpa memicu alokasi baru di Heap pada setiap request.
3. **Benchmarking & Heap Verification**:
   - Bandingkan konsumsi memori dan throughput (ops/detik) antara implementasi standar (alokasi objek baru terus-menerus) vs implementasi berbasis Object Pool.
   - Buktikan bahwa alokasi Heap berkurang minimal 70%!

---

## Bagian 5: Knowledge Check & Checklist

### Saya Harus Memahami:
- [ ] Perbedaan Stack (cepat, LIFO, frame lokal) vs Heap (dinamis, pointer, alokasi fleksibel).
- [ ] Konsep Escape Analysis pada compiler modern.
- [ ] Cara kerja Single-Threaded Event Loop (Call Stack, Microtask vs Macrotask Queue).
- [ ] Model M:N Scheduler pada Go (GMP model) dan algoritma Work-Stealing.
- [ ] Mekanisme JIT Compilation: Hot-Spot profiling, Inline Caching, dan Bailout.
- [ ] Algoritma Tracing Garbage Collection (Mark-and-Sweep) dan Generational Hypothesis.
- [ ] Penyebab terjadinya jeda Stop-The-World (STW) dan cara mitigasinya.
- [ ] Cara membaca CPU Flame Graph untuk menemukan bottleneck kode.

### Saya Tidak Perlu Menghafal:
- [ ] Kode heksadesimal opcode biner V8 bytecode (Star0, LdaNamedProperty).
- [ ] Struktur internal C++ kernel Linux untuk struktur data `task_struct`.

### Saya Harus Bisa Melakukan:
- [ ] Mencegah dan memperbaiki bug Race Condition menggunakan Mutex atau Channel.
- [ ] Mendiagnosa dan memecahkan masalah Memory Leak menggunakan Heap Snapshot inspector.
- [ ] Menjalankan profiler CPU dan menganalisis visualisasi Flame Graph.
- [ ] Memisahkan tugas I/O-Bound dan CPU-Bound pada arsitektur Event Loop.
- [ ] Mengonfigurasi batas memori runtime untuk mencegah crash tidak terkontrol.

---
[⬅️ Module 02: Kompilasi, JIT, GC, & Profiling](./Module-02-Kompilasi-JIT-Garbage-Collection-dan-Profiling.md) | [📋 Silabus Induk](../README.md) | [BAB 03 Module 01: Desain RESTful API & Idempotency ➡️](../BAB-03-Arsitektur-API-REST-GraphQL-gRPC/Module-01-Desain-RESTful-API-Richardson-Maturity-Idempotency.md)
---
