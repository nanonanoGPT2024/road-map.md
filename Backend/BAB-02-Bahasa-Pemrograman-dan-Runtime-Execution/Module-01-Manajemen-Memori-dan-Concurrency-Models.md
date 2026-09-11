---
[⬅️ BAB 01 Quiz & Challenge](../BAB-01-Fondasi-Internet-dan-Protokol/BAB-01-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Kompilasi, JIT, GC, & Profiling ➡️](./Module-02-Kompilasi-JIT-Garbage-Collection-dan-Profiling.md)
---

# Module 01: Manajemen Memori (Stack vs Heap) & Concurrency Models Backend

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Mengartikulasikan perbedaan fundamental manajemen memori tingkat rendah: **Stack Allocation** (LIFO, deterministik, cepat) vs **Heap Allocation** (dinamis, alokasi pointer, fragmentasi memori).
- Menganalisis 4 paradigma konkurensi backend:
  1. **Multi-Threading / Multi-Processing** (OS Threads, Thread Pool, Context Switching Overhead).
  2. **Single-Threaded Event Loop dengan Non-Blocking I/O** (Node.js `libuv`, Linux `epoll`, Event Demultiplexer).
  3. **Coroutines / Lightweight Green Threads** (Go Goroutines, M:N Scheduler, Work-Stealing Algorithm, Saluran Komunikasi CSP).
  4. **Actor Model** (Erlang/Elixir, Akka, Message Mailbox, Zero Shared State).
- Mengidentifikasi dan memitigasi bahaya konkurensi kritis: *Race Conditions*, *Deadlocks*, *Livelocks*, dan *Thread Starvation*.
- Memilih model konkurensi yang paling efisien berdasarkan karakteristik beban kerja (**I/O-Bound** vs **CPU-Bound**).

---

## 2. Prerequisite
- Memahami konsep dasar proses sistem operasi (PID, Memory Virtual, Threads).
- Pengalaman menulis kode backend dalam salah satu bahasa: JavaScript/TypeScript, Go, Python, Java, atau C#.
- Konsep dasar struktur data antrean (Queue) dan tumpukan (Stack).

---

## 3. Concept
Setiap program backend yang menerima request dari ribuan client secara simultan harus memecahkan dua tantangan komputasi paling mendasar:
1. **Di mana data disimpan di dalam memori RAM?** (Apakah di **Stack** yang otomatis musnah saat fungsi selesai, atau di **Heap** yang membutuhkan alokasi dinamis dan manajemen siklus hidup?).
2. **Bagaimana server mengeksekusi banyak request secara serentak tanpa saling menunggu?** (Apakah menggunakan banyak thread sistem operasi, antrean event loop tunggal, atau jutaan *lightweight green threads*?).

Pilihan arsitektur bahasa dan runtime backend (apakah Anda menggunakan Go, Node.js, Java, atau Rust) sangat ditentukan oleh bagaimana runtime tersebut menangani memori dan model konkurensinya.

```
+-----------------------------------------------------------------------------------+
|                        PROCESS MEMORY LAYOUT IN LINUX                             |
|                                                                                   |
|  [ High Memory Address: 0xFFFFFFFF ]                                              |
|  +-----------------------------------------------------------------------------+  |
|  | KERNEL SPACE (Restricted OS Privileges)                                     |  |
|  +-----------------------------------------------------------------------------+  |
|  | USER STACK (Fast, Local Variables, Grows DOWNWARD |  |                      |  |
|  |             Stack Frame funcB()                    v  v                      |  |
|  |             Stack Frame funcA()                                             |  |
|  +-----------------------------------------------------------------------------+  |
|  |                          | (Free Unallocated Space)                         |  |
|  +-----------------------------------------------------------------------------+  |
|  | HEAP (Dynamic Objects, Pointers, Arrays, Grows UPWARD ^  ^)                 |  |
|  |       Managed by malloc/free or Garbage Collector                           |  |
|  +-----------------------------------------------------------------------------+  |
|  | BSS & DATA SEGMENT (Global & Static Variables)                              |  |
|  +-----------------------------------------------------------------------------+  |
|  | TEXT / CODE SEGMENT (Compiled Binary Instructions: Read-Only)               |  |
|  +-----------------------------------------------------------------------------+  |
|  [ Low Memory Address: 0x00000000 ]                                               |
+-----------------------------------------------------------------------------------+
```

---

## 4. Why?
Mengapa pemahaman Stack vs Heap dan Concurrency Models sangat menentukan kesuksesan backend?
1. **Mencegah Kebocoran Memori (Memory Leaks & Out-of-Memory Crashes)**: Kesalahan mempertahankan referensi objek di Heap dapat mengakibatkan RAM server membengkak dari 500MB menjadi 16GB dan memicu crash OOMKilled di production.
2. **Efisiensi Skalabilitas Skala Tinggi (High-Throughput Concurrency)**: Model multi-thread tradisional (seperti Apache Web Server atau Ruby Puma) mengalokasikan 1MB - 2MB RAM per OS Thread. 10.000 koneksi bersamaan membutuhkan 20GB RAM hanya untuk thread stack! Sebaliknya, Go Goroutine hanya membutuhkan ~2KB per koneksi, memungkinkan 100.000 koneksi di server dengan RAM 1GB.
3. **Pemberantasan Bug Concurrency yang Sulit Dilacak (Heisenbugs)**: Bug *Race Condition* seringkali tidak muncul di laptop pengembang, namun meledak di produksi saat ribuan nasabah melakukan transaksi di waktu yang bersamaan.

---

## 5. What?

### A. Stack vs Heap Memory Allocation
- **Stack Memory**:
  - Alokasi berbasis struktur data LIFO (*Last-In, First-Out*).
  - Menyimpan *primitive values* (integer, boolean, float) dan *pointer references* lokal di dalam cakupan fungsi (*Stack Frame*).
  - **Sangat Cepat**: Alokasi dan dealokasi hanya berupa instruksi CPU yang menggeser *Stack Pointer Register* (`RSP`).
  - Ukuran tetap (*fixed size*). Jika terjadi rekursi tanpa henti, memori akan melebihi batas batas stack $\rightarrow$ **Stack Overflow**.
- **Heap Memory**:
  - Alokasi dinamis untuk objek kompleks (struktur data berukuran fleksibel, string panjang, maps/dictionaries, slice/array).
  - Alokasi membutuhkan pencarian blok memori bebas (*malloc*) yang memicu overhead CPU dan fragmentasi memori.
  - Siklus hidup objek tidak terikat pada satu fungsi; objek diakses melalui alamat penunjuk (*pointer/reference*).
  - Harus dibersihkan secara manual (C/C++ `free()`, Rust borrow checker) atau otomatis via **Garbage Collector (GC)** (Go, Java, Node.js).

### B. Empat Model Konkurensi Backend

#### 1. Multi-Threading Tradisional (Thread-per-Request)
- Setiap request HTTP baru dilayani oleh satu Kernel Thread tersendiri (contoh: Java Spring Boot dengan Tomcat thread pool, Ruby on Rails).
- **Kelemahan**: OS Context Switching memakan siklus CPU (menyimpan dan memuat register CPU, TLB cache flush). Terbatas pada kapasitas thread pool (misal 200 thread).

#### 2. Single-Threaded Event Loop (Non-Blocking Reactive I/O)
- Menggunakan 1 thread komputasi utama untuk mengeksekusi kode JavaScript/Python (contoh: Node.js, Python FastAPI/Asyncio, NGINX).
- Memanfaatkan panggilan sistem kernel Linux yang sangat efisien (**`epoll`** di Linux, `kqueue` di macOS) via pustaka **`libuv`**.
- Saat melakukan operasi I/O (membaca database atau disk), thread tidak diam menunggu (*non-blocking*). Thread langsung beralih melayani request lain, dan ketika data I/O siap, event dimasukkan ke *Callback Queue*.
- **Kelemahan**: Jika ada satu fungsi CPU-intensive (misal: enkripsi gambar besar atau kalkulasi Fibonacci panjang), seluruh server akan macet (*event loop blocked*).

#### 3. Coroutines / Green Threads (Go Goroutines & Erlang)
- Model **M:N Scheduler**: Memetakan ribuan *Green Threads* (N) ke sejumlah kecil *OS Kernel Threads* (M, biasanya sama dengan jumlah CPU Core fisik).
- **Go Scheduler (GMP Model)**:
  - `G`: Goroutine (stack awal super ringan, ~2KB, dapat tumbuh dinamis).
  - `M`: Machine (OS Kernel Thread).
  - `P`: Processor (Konteks logis pemroses dengan antrean lokal Run Queue).
  - Menggunakan algoritma **Work-Stealing**: Jika prosesor $P_1$ kehabisan tugas, $P_1$ akan mencuri separuh antrean tugas dari prosesor $P_2$, menjaga seluruh core CPU bekerja 100% tanpa henti.

#### 4. Actor Model
- Tidak ada *Shared Memory* sama sekali (*Share Nothing Architecture*).
- Setiap entitas adalah **Actor** independen yang memiliki *Mailbox* (antrean pesan privat).
- Komunikasi antar aktor hanya dilakukan melalui pengiriman pesan asinkron (*Message Passing*). Sempurna untuk sistem chat dan game online (contoh: Erlang/OTP, Elixir).

---

## 6. How?

### Memahami Escape Analysis (Go Runtime Contoh Nyata)
Kompiler modern (seperti Go dan Java JIT) menjalankan **Escape Analysis** saat kompilasi untuk menentukan apakah sebuah variabel boleh dialokasikan di Stack (murah) atau terpaksa "kabur" (*escape*) ke Heap (mahal).

```go
package main

type Transaction struct {
    ID     int
    Amount float64
}

// Kasus 1: Tidak kabur -> Dialokasikan di STACK!
func processLocal() float64 {
    t := Transaction{ID: 1, Amount: 50000.0}
    return t.Amount // Mengembalikan nilai primitif (copy value). Memori t langsung musnah saat fungsi return.
}

// Kasus 2: Kabur ke HEAP!
func createTransaction() *Transaction {
    t := Transaction{ID: 2, Amount: 75000.0}
    return &t // Mengembalikan POINTER! Karena t masih dibutuhkan oleh pemanggil di luar fungsi,
              // compiler Go memindahkan alokasi t ke HEAP!
}
```

*Verifikasi via Compiler Flag*:
```bash
go build -gcflags="-m" main.go
# Output:
# ./main.go:14:9: &t escapes to heap
# ./main.go:13:2: moved to heap: t
```

---

## 7. Analogy
Bayangkan **Operasional Dapur Restoran**:
- **Stack Memory**: Piring dan talenan kecil milik koki pribadi. Digunakan untuk memotong bawang, langsung dicuci dan diletakkan kembali begitu selesai memasak satu porsi (*instan dan bersih*).
- **Heap Memory**: Meja buffet tengah bersama berukuran besar. Bahan makanan disimpan di sana untuk digunakan bersama oleh semua koki. Harus ada petugas kebersihan (**Garbage Collector**) yang membersihkan sisa makanan basi agar meja tidak penuh sampah.
- **Multi-Threading**: Menyewa 1 koki khusus untuk setiap tamu yang datang. Jika ada 1.000 tamu, restoran bangkrut karena dapur penuh sesak oleh 1.000 koki (**Context Switch Overhead**).
- **Single-Threaded Event Loop**: 1 koki jenius super cepat (**Node.js**). Begitu pesanan masuk, dia menaruh panci di atas kompor (Non-blocking I/O), lalu langsung melayani pesanan tamu berikutnya. Begitu alarm kompor berbunyi (**Event Callback**), dia mengangkat panci tersebut.
- **Goroutines (M:N Work-Stealing)**: 4 koki kepala (**M Threads**) mengelola 10.000 pesanan mini (**Goroutines**). Jika Koki A selesai mengerjakan pesanannya, dia segera mengambil pesanan dari meja Koki B (**Work-Stealing**) agar dapur beroperasi dengan efisiensi maksimal.

---

## 8. Diagram: Node.js Event Loop vs Go M:N Scheduler

```
+---------------------------------------------------------------------------------+
|               CONCURRENCY ARCHITECTURES: NODE.JS VS GO RUNTIME                  |
+---------------------------------------------------------------------------------+

1. NODE.JS EVENT LOOP (libuv):
   Call Stack (V8 Engine - 1 Thread)
       |
       v (I/O calls: DB query, file read)
   libuv Event Demultiplexer (epoll / OS Kernel)
       |
       v (When I/O completes)
   Microtask Queue (Promise.then, queueMicrotask) -> PRIORITAS TERTINGGI!
       |
       v
   Macrotask Callback Queue (setTimeout, I/O events, setImmediate)

-----------------------------------------------------------------------------------

2. GO M:N WORK-STEALING SCHEDULER:
   OS Threads (M1, M2)  <---- Mapped dynamically to Physical Cores
         |          |
   Logical Contexts:
       [ P1 ]     [ P2 ]
         |          |
   Local RunQueue:
     [ G1, G2 ]   [ G3, G4 ]  <--- Goroutines (Lightweight ~2KB stacks)
         ^          |
         | steals   |
         +----------+ (If P1 RunQueue is empty, it STEALS half of P2's Goroutines!)
```

---

## 9. Simple Example: Demonstrasi Race Condition & Mutex

Dua thread/goroutine mencoba menambah saldo akun bersama secara bersamaan tanpa proteksi:

```go
package main

import (
    "fmt"
    "sync"
)

var balance int = 1000
var mu sync.Mutex // Mutex untuk mencegah Race Condition

func deposit(amount int, wg *sync.WaitGroup) {
    defer wg.Done()
    
    // CRITICAL SECTION (Dilindungi Mutex)
    mu.Lock()
    current := balance
    // Simulasikan delay operasi jaringan/database
    balance = current + amount
    mu.Unlock()
}

func main() {
    var wg sync.WaitGroup
    for i := 0; i < 1000; i++ {
        wg.Add(1)
        go deposit(10, &wg)
    }
    wg.Wait()
    fmt.Printf("Saldo Akhir: %d (Harus tepat 11000)\n", balance)
}
```

*Deteksi Race Condition bawaan Go*:
```bash
go run -race main.go
```

---

## 10. Practical Example: Event Loop Blocking Pitfall di Node.js

Salah satu kesalahan paling fatal pengembang backend pemula adalah mengeksekusi operasi CPU-intensif di dalam event loop utama, yang menyebabkan seluruh user lain mengalami timeout:

```javascript
const http = require('http');

http.createServer((req, res) => {
  if (req.url === '/fast') {
    // Endpoint non-blocking cepat
    return res.end("Respons instan!");
  }

  if (req.url === '/heavy-cpu-bug') {
    // ANTI-PATTERN FATAL: Menghitung loop 5 miliar iterasi secara synchronous!
    // Selama fungsi ini berjalan (misal 5 detik), TIDAK ADA USER LAIN
    // yang bisa mengakses endpoint /fast sekalipun! SELURUH SERVER FREEZE!
    let sum = 0;
    for (let i = 0; i < 5000000000; i++) {
      sum += i;
    }
    return res.end(`Hasil: ${sum}`);
  }
}).listen(3000);

// SOLUSI:
// Alihkan pekerjaan berat CPU ke:
// 1. Worker Threads (worker_threads module)
// 2. Child Processes
// 3. Background Job Queue terpisah (BullMQ / RabbitMQ / Kafka)
```

---

## 11. Real World Example: Migrasi Discord dari Python/Go ke Rust untuk Efisiensi Memori
Discord menangani jutaan pesan teks dan voice status setiap detik. Awalnya layanan *Read States* mereka dibangun menggunakan **Go**.
- Masalah yang dialami: Meskipun Go sangat cepat dan memiliki model goroutine yang hebat, **Garbage Collector (GC)** Go secara periodik (setiap 2 menit) memindai jutaan pointer di Heap memory.
- Pemindaian ini memicu *CPU spikes* dan lonjakan latensi (*latency p99 spikes*) yang membuat antarmuka Discord lag.
- Discord memutuskan menulis ulang layanan tersebut dalam bahasa **Rust**. Rust tidak memiliki Garbage Collector sama sekali; memori dikelola menggunakan sistem kepemilikan kompilasi (*Compile-time Ownership & Borrow Checker*).
- Hasil: Latensi p99 turun dari 300ms menjadi 11ms, penggunaan CPU rata-rata turun drastis, dan penggunaan RAM stabil konstan tanpa lonjakan GC.

---

## 12. Trade-offs

| Model Konkurensi | Bahasa Tipikal | Keunggulan Utama | Risiko / Batasan |
|---|---|---|---|
| **Single-Thread Event Loop** | JavaScript (Node.js), Python (Asyncio) | Sangat hemat RAM, bebas race condition memori thread | Tidak cocok untuk komputasi CPU berat (mudah freeze) |
| **M:N Green Threads** | Go (Goroutines), Elixir (BEAM) | Efisiensi skala masif, work-stealing otomatis, sintaks sinkron | Butuh runtime khusus, tuning alokasi stack |
| **OS Thread Pool** | Java, C++, C# | Mampu memanfaatkan multi-core CPU untuk komputasi berat | Konsumsi RAM per thread tinggi (~1MB), overhead context switch |
| **Actor Model** | Elixir/Erlang, Akka | Isolasi kegagalan sempurna (*Let it crash*), bebas shared-memory lock | Overhead serialisasi pesan antar aktor |

---

## 13. When To Use
- Gunakan **Single-Threaded Event Loop (Node.js/FastAPI)** untuk backend yang dominan melayani operasi **I/O-Bound**: CRUD REST API, streaming gateway, integrasi database, atau proxy perantara.
- Gunakan **M:N Coroutines (Go)** untuk microservice berkinerja tinggi, sistem jaringan skala masif, streaming pipeline, atau alat infrastruktur sistem (Kubernetes, Docker, Terraform semuanya ditulis dalam Go).
- Gunakan **Rust/C++** untuk sistem yang mewajibkan latensi ultra-rendah dan prediktif tanpa interupsi Garbage Collector (financial high-frequency trading, game engines, embedded devices).

---

## 14. When NOT To Use
- **JANGAN** menggunakan Node.js atau Python async untuk pemrosesan gambar, transcoding video, atau pelatihan machine learning di dalam thread utama web server.
- Jangan berbagi memori global (*shared global state*) lintas thread tanpa mekanisme penguncian (*mutex/semaphore*) atau saluran atomik (*atomic operations*).

---

## 15. Common Mistakes
1. **Goroutine Leak**: Memulai goroutine yang menunggu pesan dari channel yang tidak pernah dikirimkan atau tidak memiliki buffer, menyebabkan goroutine tertahan di memori selamanya dan menghabiskan RAM secara perlahan.
2. **Deadlock Karena Urutan Penguncian Mutex yang Berbeda**: Thread 1 mengunci Mutex A lalu menunggu Mutex B, sementara Thread 2 mengunci Mutex B lalu menunggu Mutex A. Kedua thread terkunci selamanya.
3. **Membaca/Menulis Slice/Map Bersamaan Tanpa Lock**: Di Go dan Node.js, struktur data bawaan tidak *thread-safe*. Menulis ke `map` dari dua goroutine secara bersamaan akan langsung memicu `fatal error: concurrent map writes` dan mematikan aplikasi seketika.

---

## 16. Best Practices
- **Must Have**: Jalankan alat deteksi race condition (`go test -race` atau ThreadSanitizer) pada seluruh pipeline pengujian otomatis CI/CD.
- **Recommended**: Minimalisir alokasi Heap pada jalur kritis (*hot path*) aplikasi; gunakan objek pooling (`sync.Pool` di Go) untuk mendaur ulang alokasi buffer byte.
- **Advanced**: Terapkan prinsip komunikasi CSP: *"Do not communicate by sharing memory; instead, share memory by communicating"* (gunakan Channel daripada Mutex jika memungkinkan).
- **Avoid**: Menggunakan `sync/atomic` secara berlebihan jika logika dapat diselesaikan dengan struktur data yang terisolasi.

---

## 17. Troubleshooting Guide
```
Masalah: Aplikasi crash dengan pesan "fatal error: concurrent map read and map write".
Penyebab : Beberapa goroutine mengakses struktur data Go map yang sama tanpa sinkronisasi mutex.
Diagnosa : go run -race main.go
Solusi   : Bungkus akses map dengan sync.RWMutex (Lock/Unlock untuk tulis, RLock/RUnlock untuk baca), atau gunakan 'sync.Map'.

Masalah: Event loop Node.js mengalami lag parah, latensi API melonjak dari 5ms menjadi 4000ms.
Penyebab : Ada blocking synchronous call (seperti fs.readFileSync, crypto.pbkdf2Sync, atau parsing JSON raksasa 50MB).
Diagnosa : Gunakan library 'blocked-at' atau runtime inspector: node --inspect app.js
Solusi   : Ganti seluruh pemanggilan biner sync dengan asynchronous async/await version, atau pindahkan parsing JSON besar ke worker_threads.
```

---

## 18. Exercise
1. Tulis program sederhana di bahasa pilihan Anda yang mendemonstrasikan alokasi Stack vs Heap.
2. Buat skenario di mana dua thread/goroutine mencoba memodifikasi counter integer bersama sebanyak 100.000 kali.
3. Buktikan terjadinya inkonsistensi data (nilai akhir bukan 200.000) tanpa menggunakan lock, lalu perbaiki program tersebut menggunakan Mutex atau Channel.

---

## 19. Challenge
Rancang arsitektur worker pool konkuren di Go atau Node.js yang mampu memproses **500.000 item pekerjaan** per menit dengan batasan:
1. Jumlah worker dibatasi maksimal 50 worker simultan untuk melindungi koneksi pool database.
2. Menerapkan pola *Graceful Shutdown* menggunakan `context.WithTimeout` (menunggu seluruh worker yang sedang aktif selesai bekerja sebelum proses exit).
3. Mengukur efisiensi memori (memastikan penggunaan RAM stabil di bawah 100MB). Tulis kode implementasinya secara lengkap!

---

## 20. Summary
Manajemen memori (Stack vs Heap) dan model konkurensi (Event Loop, Threads, Coroutines) adalah dua pilar terpenting dalam arsitektur software backend. Pemilihan model yang selaras dengan profil beban kerja aplikasi akan menjamin efisiensi alokasi sumber daya perangkat keras, responsivitas latensi, serta ketahanan sistem dalam menghadapi beban komputasi masif.

---
[⬅️ BAB 01 Quiz & Challenge](../BAB-01-Fondasi-Internet-dan-Protokol/BAB-01-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Kompilasi, JIT, GC, & Profiling ➡️](./Module-02-Kompilasi-JIT-Garbage-Collection-dan-Profiling.md)
---
