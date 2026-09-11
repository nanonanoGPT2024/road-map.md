---
[⬅️ Module 01: Memory & Concurrency Models](./Module-01-Manajemen-Memori-dan-Concurrency-Models.md) | [📋 Silabus Induk](../README.md) | [BAB 02 Quiz & Challenge ➡️](./BAB-02-Quiz-dan-Challenge.md)
---

# Module 02: Kompilasi, Just-In-Time (JIT), Garbage Collection, & Profiling

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Membedakan tiga paradigma eksekusi bahasa backend: **Ahead-of-Time (AOT)**, **Interpreted murni**, dan **Hybrid Bytecode + Just-In-Time (JIT)**.
- Menjelaskan arsitektur mesin JIT (seperti V8 pada Node.js atau HotSpot pada Java JVM): *Interpreter (Ignition)* $\rightarrow$ *Profiler / Hot Spot Detection* $\rightarrow$ *Optimizing Compiler (TurboFan)* $\rightarrow$ *Deoptimization (Bailout)*.
- Menguasai algoritma **Garbage Collection (GC)**: *Reference Counting*, *Mark-and-Sweep*, *Mark-Compact*, dan **Generational Hypothesis** (Eden, Survivor, Tenured/Old Generation).
- Memahami strategi mitigasi jeda **Stop-The-World (STW)** pada low-latency collector modern (Go Tri-Color Concurrent Collector, Java ZGC).
- Mengidentifikasi pola-pola kebocoran memori (*Memory Leaks*) di bahasa ber-GC dan memecahkannya menggunakan analisis **Heap Snapshot** dan **CPU Flame Graphs**.

---

## 2. Prerequisite
- Memahami alokasi Stack vs Heap (Modul 01).
- Pemahaman dasar tentang siklus instruksi CPU (Fetch, Decode, Execute) dan register CPU.
- Pengalaman menggunakan terminal dan profiling tools.

---

## 3. Concept
Ketika Anda menulis kode backend:
```javascript
function calculateTotal(items) {
    return items.reduce((acc, item) => acc + item.price, 0);
}
```
Prosesor fisik (Intel x86_64 atau Apple ARM64) tidak mengerti teks bahasa pemrograman tingkat tinggi tersebut. CPU hanya memahami deretan instruksi biner mesin (`01010100`).

Bagaimana kode tersebut diubah menjadi instruksi mesin sangat menentukan efisiensi, kecepatan startup, dan konsumsi memori server Anda:
1. **AOT (Ahead-of-Time)**: Kode langsung dikonversi menjadi biner mesin sebelum aplikasi dijalankan (Go, Rust, C++). Startup instan, performa mentah maksimal, footprint memori minimal.
2. **Interpreted**: Kode dieksekusi baris-demi-baris oleh program interpreter saat runtime (Python standar CPython). Portabel dan fleksibel, namun kecepatan eksekusi lambat (10x - 50x lebih lambat dari AOT).
3. **Bytecode + JIT (Hybrid)**: Kode dikompilasi menjadi representasi perantara (*Bytecode*), lalu dieksekusi oleh Virtual Machine (JVM, V8, .NET CLR). Ketika VM mendeteksi sebuah fungsi sering dipanggil (*Hot Spot*), mesin **Just-In-Time (JIT)** mengompilasi fungsi tersebut menjadi instruksi mesin asli secara real-time saat aplikasi sedang berjalan.

```
+-----------------------------------------------------------------------------------+
|                        THE JIT COMPILATION PIPELINE (V8 / JVM)                    |
|                                                                                   |
|  [ Source Code (JS / Java) ]                                                      |
|            |                                                                      |
|            v (Parser & AST)                                                       |
|  [ Bytecode Generator ]                                                           |
|            |                                                                      |
|            v (Generates Platform-Independent Bytecode)                            |
|  [ Fast Interpreter (Ignition / JVM Interpreter) ] ---> Starts executing FAST!    |
|            |                                                                      |
|            v (Collects Profiling Type Feedback)                                   |
|  [ Profiler: "Is function X called 10,000 times? (HOT SPOT!)" ]                   |
|            |                                                                      |
|            v (YES: Trigger JIT Optimization)                                      |
|  [ Optimizing Compiler (TurboFan / C2 Compiler) ]                                 |
|  - Inline Caching (Assume types won't change)                                     |
|  - Loop Unrolling & Dead Code Elimination                                         |
|            |                                                                      |
|            v                                                                      |
|  [ Highly Optimized Native Machine Code (Assembly x86_64/ARM64) ]                 |
|            |                                                                      |
|            | (If type assumption fails: e.g. Number suddenly becomes String!)     |
|            v                                                                      |
|  [ DEOPTIMIZATION / BAILOUT ] ---> Drops back to slow Interpreter!                |
+-----------------------------------------------------------------------------------+
```

---

## 4. Why?
Mengapa pemahaman kompilasi, JIT, dan Garbage Collector sangat penting?
1. **Menghindari Perangkap JIT Deoptimization**: Perubahan tipe data dinamis pada *hot functions* di Node.js/Python dapat memicu *JIT Bailout*, membuat throughput API anjlok 80% secara mendadak.
2. **Menghilangkan Latency Spikes (Stop-The-World GC)**: Pada aplikasi perbankan atau pembayaran, jeda Garbage Collector selama 200ms dapat memicu timeout pada payment gateway downstream dan membatalkan ribuan transaksi.
3. **Mendiagnosa Memory Leak Secara Ilmiah**: Mengetahui cara membaca *Heap Dump* dan *Flame Graphs* memungkinkan Anda menemukan akar kebocoran memori dalam 15 menit, bukan berhari-hari menebak-nebak kode.

---

## 5. What?

### A. JIT Optimizations: Inline Caching & Monomorphism
Mesin JIT bekerja dengan asumsi bahwa kode yang sering dipanggil biasanya beroperasi pada tipe data yang sama (*Monomorphic*).
- **Inline Caching**: Jika fungsi `add(a, b)` selalu dipanggil dengan integer, JIT menghilangkan pemeriksaan tipe data dan langsung menggantinya dengan instruksi CPU tunggal `ADD EAX, EBX`.
- **Megamorphic Hazard**: Jika `add(a, b)` tiba-tiba dipanggil dengan string, array, atau objek berbeda-beda tipe, JIT menyerah (*Polymorphic/Megamorphic*), membatalkan optimasi native (*Deoptimization*), dan kembali ke interpreter yang lambat.

### B. Algoritma Garbage Collection (GC)

#### 1. Reference Counting (Legacy / Python)
- Setiap objek memiliki pencatat jumlah referensi (*reference count*).
- Setiap ada variabel baru yang menunjuk ke objek, count bertambah 1. Jika pointer dihapus, count berkurang 1. Saat count = 0, objek langsung dihapus.
- **Kelemahan Fatal**: **Circular References (Referensi Melingkar)**! Jika Objek A menunjuk ke Objek B, dan Objek B menunjuk ke Objek A, keduanya tidak akan pernah dihapus meskipun tidak lagi dapat dijangkau oleh aplikasi, menghasilkan memory leak permanen.

#### 2. Tracing Garbage Collection (Mark-and-Sweep)
Digunakan oleh Go, Node.js V8, Java, dan browser modern:
1. **Fase Mark**: GC mulai dari **GC Roots** (variabel global, stack pointer aktif, register CPU). GC menelusuri seluruh pointer yang terhubung dan menandai (*mark*) semua objek yang masih terjangkau (*reachable*) sebagai `ALIVE`.
2. **Fase Sweep**: GC memindai seluruh memori Heap; semua objek yang tidak ditandai sebagai `ALIVE` dianggap sampah (*dead object*) dan dikembalikan ke pool memori bebas.
3. **Fase Compact (Opsional)**: Menggeser objek yang tersisa agar berdampingan, menghilangkan fragmentasi memori.

#### 3. Weak Generational Hypothesis
Berdasarkan riset empiris ilmu komputer:
> *"Sebagian besar objek (95%+) mati sangat muda sesaat setelah dibuat (seperti variabel lokal dalam request HTTP)."*

Atas dasar ini, memori Heap dibagi menjadi dua generasi:
- **Young Generation (Eden Space & Survivor Spaces)**: Tempat objek baru lahir. Dibersihkan sangat sering melalui **Minor GC** (hanya butuh 1-3 milidetik).
- **Old / Tenured Generation**: Objek yang berhasil bertahan melewati beberapa siklus Minor GC dipindahkan ke sini. Dibersihkan jarang melalui **Major / Full GC** (membutuhkan waktu lebih lama).

---

## 6. How?

### Mendeteksi Memory Leak Menggunakan Node.js Heap Profiling
Kebocoran memori pada bahasa ber-GC terjadi ketika objek yang sudah tidak terpakai **masih tetap terhubung ke GC Roots** (misal tersimpan di array global atau event listener yang lupa di-remove).

```javascript
// CONTOH KASUS MEMORY LEAK NYATA
const express = require('express');
const app = express();

// ANTI-PATTERN: Array global yang tidak pernah dibersihkan!
const requestAuditLog = [];

app.get('/api/pay', (req, res) => {
  const transaction = {
    id: Math.random(),
    payload: Buffer.alloc(1024 * 1024), // Alokasi 1MB Heap
    timestamp: new Date()
  };

  // Objek tersangkut di GC Roots (requestAuditLog global)!
  // Garbage Collector TIDAK AKAN PERNAH bisa menghapus objek ini!
  requestAuditLog.push(transaction);

  res.json({ status: "success" });
});

app.listen(3000);
```

*Langkah Diagnosa Profiling*:
1. Jalankan aplikasi dengan flag inspector: `node --inspect server.js`.
2. Buka browser Chrome, akses `chrome://inspect`.
3. Rekam **Heap Snapshot 1** saat aplikasi baru menyala.
4. Jalankan load testing (1.000 request).
5. Rekam **Heap Snapshot 2** dan bandingkan (*Comparison View*).
6. Identifikasi objek `Buffer` atau `Array` yang jumlahnya bertambah pesat dan periksa rantai referensinya (*Retainer Tree*) untuk menemukan variabel `requestAuditLog`.

---

## 7. Analogy
Bayangkan **Pengelolaan Sampah di Kota Metropolitan**:
- **AOT Compilation**: Membangun pabrik dengan robot mekanik khusus yang sudah dirakit mati untuk satu fungsi tertentu. Sangat cepat, presisi, tanpa jeda.
- **JIT Compilation**: Mempekerjakan staf magang (*Interpreter*) untuk mencatat pekerjaan apa yang paling sering diulang (*Hot Spot*). Begitu ada pekerjaan yang diulang 1.000 kali, staf ahli teknik langsung merakit mesin otomatis (*JIT Machine Code*) untuk tugas tersebut. Namun jika bahan baku tiba-tiba berubah bentuk (*Type Mismatch*), mesin otomatis mogok (*Bailout*) dan pekerjaan diserahkan kembali ke staf magang.
- **Generational GC**:
  - **Tong Sampah Meja Dapur (Young Generation / Eden)**: Dibuang setiap jam sekali secara kilat (Minor GC). Mayoritas tisu dan kulit bawang langsung dibuang di sini.
  - **Gudang Penyimpanan Barang Antik (Tenured / Old Generation)**: Barang-barang yang bertahan bertahun-tahun di rumah (seperti lukisan atau sertifikat). Hanya dibersihkan setahun sekali saat pembersihan massal (*Full GC*).

---

## 8. Diagram: Memory Leak Retainer Tree & CPU Flame Graph

```
+---------------------------------------------------------------------------------+
|                       HEAP RETENTION & FLAME GRAPH CONCEPT                      |
+---------------------------------------------------------------------------------+

1. GC ROOT RETAINER GRAPH (Mengapa objek tidak terhapus GC):
   [ Global Object (window / globalThis) ] <--- GC ROOT (Root Pointer)
                |
                v holds reference
   [ globalCache = [] (Array) ]
                |
                v holds reference
   [ Leaked Object { buffer: 10MB } ] <--- GC menganggap objek ini ALIVE!

-----------------------------------------------------------------------------------

2. CPU FLAME GRAPH (Membaca Profiler Performa):
   +-------------------------------------------------------------+
   |                  calculateTax() (Lebar = 80% CPU Time!)     | <--- BOTTLENECK!
   +-------------------------------------------------------------+
   |                  processPayment()                           |
   +-------------------------------------------------------------+
   |                  httpHandler()                              |
   +-------------------------------------------------------------+
   Setiap balok merepresentasikan fungsi. Semakin LEBAR balok pada Flame Graph,
   semakin banyak waktu CPU yang dihabiskan fungsi tersebut!
```

---

## 9. Simple Example: Monomorphic vs Megamorphic JIT Benchmark

Menunjukkan bagaimana konsistensi tipe data memengaruhi optimasi JIT:

```javascript
// Monomorphic Function: JIT mengoptimalkan ini ke instruksi mesin assembly super cepat
function addMonomorphic(a, b) {
  return a + b;
}

// Uji 10 juta kali dengan tipe konsisten (Integer)
console.time("Monomorphic (Fast JIT)");
for (let i = 0; i < 10000000; i++) {
  addMonomorphic(i, 2);
}
console.timeEnd("Monomorphic (Fast JIT)");

// Megamorphic: JIT mengalami bailout karena tipe berganti-ganti secara liar
console.time("Megamorphic (Bailout)");
for (let i = 0; i < 10000000; i++) {
  if (i % 2 === 0) addMonomorphic(i, 2);
  else addMonomorphic("str_" + i, "suffix"); // Tipe berganti menjadi String!
}
console.timeEnd("Megamorphic (Bailout)");
```

---

## 10. Practical Example: CPU Profiling dengan Go pprof

Go memiliki profiler kelas dunia yang tertanam langsung di runtime standarnya:

```go
package main

import (
    "net/http"
    _ "net/http/pprof" // Mendaftarkan endpoint /debug/pprof otomatis!
    "time"
)

func heavyTask() {
    for {
        // Simulasi komputasi CPU intensif
        data := make([]byte, 1024*1024)
        _ = data
        time.Sleep(10 * time.Millisecond)
    }
}

func main() {
    go heavyTask()
    
    // Server pprof berjalan di port 6060
    http.ListenAndServe(":6060", nil)
}
```

*Cara Menganalisis CPU Flame Graph*:
```bash
# 1. Ambil profil CPU selama 30 detik
go tool pprof -http=:8081 http://localhost:6060/debug/pprof/profile?seconds=30

# 2. Browser otomatis terbuka di http://localhost:8081 menampilkan visualisasi Flame Graph interaktif!
```

---

## 11. Real World Example: JVM Garbage Collector Tuning di Platform Finansial
Sebuah bank digital di Asia Tenggara memproses 15.000 transaksi per detik menggunakan aplikasi berbasis Java Spring Boot.
- Masalah: Setiap 10 menit, aplikasi mengalami jeda *Stop-The-World Full GC* selama **450 milidetik** menggunakan collector default G1GC. Jeda ini menyebabkan latensi p99 melonjak, memicu error timeout pada integrasi QRIS dan BI-FAST.
- Solusi Arsitektur: Tim Platform Engineering beralih ke **ZGC (Z Garbage Collector)** dengan flag JVM:
  `-XX:+UseZGC -XX:+ZGenerational`
- Hasil: ZGC mengeksekusi penandaan dan pemadatan memori secara konkuren bersamaan dengan thread aplikasi yang sedang berjalan (*concurrent phase*). Jeda Stop-The-World terpangkas dari **450ms menjadi di bawah 1 milidetik (< 1ms)** pada heap memori 32GB!

---

## 12. Trade-offs

| Pendekatan Eksekusi | Keuntungan | Kerugian |
|---|---|---|
| **AOT (Go, Rust)** | Performa langsung optimal, konsumsi RAM sangat rendah, waktu booting instan (< 10ms) | Waktu kompilasi lebih lama, biner platform-dependent |
| **JIT (JVM, V8)** | Optimasi runtime berbasis profil nyata (profiling feedback), fleksibilitas tinggi | *Warm-up time* lambat (butuh waktu sebelum mencapai performa puncak), konsumsi RAM tinggi |
| **Manual Memory (Rust/C)** | Zero GC pause, deterministik mutlak | Kompleksitas kode tinggi (Borrow checker / risiko pointer bug) |
| **Automatic GC (Go/Java/Node)**| Produktivitas developer tinggi, aman dari buffer overflow | Resiko GC pauses, konsumsi memori tambahan (*memory footprint overhead*) |

---

## 13. When To Use
- Gunakan bahasa **AOT (Go / Rust)** untuk aplikasi cloud microservice yang sering mengalami autoscaling (scale up/down cepat via Karpenter/HPA) karena waktu *cold-start* instan.
- Gunakan bahasa **JIT (Java JVM / C# .NET)** untuk aplikasi enterprise monolitik berumur panjang (*long-running processes*) di mana JIT compiler dapat melakukan optimasi komputasi mendalam setelah fase warm-up.
- Selalu lakukan **CPU Profiling** sebelum melakukan optimasi kode untuk memastikan Anda menyelesaikan bottleneck nyata (*Measure first, optimize second*).

---

## 14. When NOT To Use
- **JANGAN** menggunakan variabel global sebagai penampung cache (*in-memory global cache*) tanpa batas maksimal (*unbounded cache*), karena ini adalah penyebab nomor satu memory leak di Node.js, Go, dan Java. Gunakan Redis atau LRU cache berukuran tetap.
- Jangan menjalankan profiler CPU dengan durasi terlalu lama di lingkungan produksi ber-traffic puncak tanpa membatasi sampling rate, karena profiler dapat menambahkan overhead 5-10% pada CPU.

---

## 15. Common Mistakes
1. **Lupa Melepas Event Listeners**: Menambahkan `emitter.on('event', callback)` di dalam scope request HTTP tanpa pernah memanggil `removeListener()`. Setiap request meninggalkan closure function di memori hingga server crash OOM.
2. **Menutup Koneksi Database Secara Manual di Setiap Request**: Membuka dan menutup koneksi database alih-alih menggunakan **Connection Pool**, membebani Garbage Collector dengan jutaan objek socket yang cepat lahir dan mati.
3. **Mengabaikan Closure Memory Retention**: Fungsi bersarang (*nested closure*) yang mempertahankan referensi ke objek induk besar secara tidak sengaja menahan seluruh objek induk di Heap.

---

## 16. Best Practices
- **Must Have**: Pasang batas alokasi memori maksimal pada runtime (`--max-old-space-size` di Node.js, `-Xmx` di Java) agar proses crash dan di-restart secara terkontrol sebelum mengorbankan stabilitas seluruh node Linux.
- **Recommended**: Hindari membuat objek sementara di dalam loop berfrekuensi tinggi (*tight loops*); daur ulang objek jika memungkinkan (*object pooling*).
- **Advanced**: Pantau metrik GC pauses (durasi STW dan frekuensi GC per menit) di dashboard Prometheus/Grafana sebagai indikator kesehatan degradasi aplikasi.
- **Avoid**: Menjalankan fungsi pembersihan memori manual (`global.gc()` di Node.js atau `System.gc()` di Java) di kode produksi.

---

## 17. Troubleshooting Guide
```
Masalah: Aplikasi Node.js crash dengan pesan "FATAL ERROR: Ineffective mark-compacts near heap limit Allocation failed - JavaScript heap out of memory".
Penyebab : Memori Heap melampaui batas maksimal (--max-old-space-size default ~1.4GB) akibat kebocoran memori.
Diagnosa : Ambil heap dump sebelum crash: node --max-old-space-size=2048 --heapsnapshot-near-heap-limit=3 server.js
Solusi   : Buka file .heapsnapshot di Chrome DevTools, identifikasi objek dengan 'Retained Size' terbesar, dan putus rantai referensi GC root-nya.

Masalah: Latensi API sesekali melonjak drastis (p99 spike) setiap beberapa menit.
Penyebab : Siklus Major/Full Garbage Collection yang memicu jeda Stop-The-World panjang.
Diagnosa : Aktifkan logging GC: node --trace-gc server.js atau java -Xlog:gc* ...
Solusi   : Naikkan memori Young Generation, kurangi alokasi objek temporer, atau ganti collector ke low-latency collector (ZGC / Go runtime).
```

---

## 18. Exercise
1. Tulis skrip Node.js atau Go yang sengaja memicu memory leak menggunakan closure atau unbounded map.
2. Pantau grafik penggunaan RAM proses menggunakan Task Manager atau `top`/`htop`.
3. Gunakan profiler (Node.js Heap Snapshot atau Go `pprof`) untuk menemukan baris kode yang menyebabkan retensi memori tersebut.

---

## 19. Challenge
Rancang arsitektur pemrosesan data real-time berkecepatan tinggi (**100.000 events/detik**) di Go atau Java:
1. Hitung alokasi memori objek per detik dan buktikan bagaimana teknik **Object Pooling** (`sync.Pool`) dapat memangkas alokasi Heap hingga 90%.
2. Tunjukkan perbandingan performa latensi p99 sebelum dan sesudah eliminasi alokasi Heap melalui pembacaan grafik CPU & Memory profiler!

---

## 20. Summary
Pemahaman mendalam tentang cara kerja kompilasi AOT, optimasi Just-In-Time (JIT), siklus penelusuran Garbage Collection, dan pembacaan Flame Graphs profiler melengkapi seorang backend engineer dengan kemampuan diagnostik tingkat lanjut. Fondasi ini memastikan bahwa kode backend yang ditulis tidak hanya berfungsi secara logika, tetapi juga berjalan dengan efisiensi memori dan latensi kelas satu.

---
[⬅️ Module 01: Memory & Concurrency Models](./Module-01-Manajemen-Memori-dan-Concurrency-Models.md) | [📋 Silabus Induk](../README.md) | [BAB 02 Quiz & Challenge ➡️](./BAB-02-Quiz-dan-Challenge.md)
---
