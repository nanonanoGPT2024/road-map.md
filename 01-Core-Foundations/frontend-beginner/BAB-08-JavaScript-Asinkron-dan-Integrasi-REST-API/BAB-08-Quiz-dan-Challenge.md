# BAB 08: Quiz, Challenge, & Knowledge Check
**JavaScript Asinkron, Web API & Integrasi REST**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Single-Threaded Concurrency Model
JavaScript di lingkungan browser dieksekusi secara *single-threaded* pada *main thread*. Jelaskan secara arsitektural bagaimana JavaScript mampu menangani operasi *I/O-bound* yang membutuhkan waktu lama (seperti network request melalui `fetch`) tanpa menyebabkan *blocking* pada antarmuka pengguna (UI render thread). Uraikan interaksi spesifik antara **Call Stack**, **Web APIs**, **Task Queue (Macrotask)**, dan **Event Loop**.

### Soal 1.2: Siklus Hidup dan Immutability Promise
Objek `Promise` merepresentasikan nilai yang mungkin tersedia saat ini, di masa depan, atau tidak pernah sama sekali. 
1. Sebutkan dan jelaskan 3 status (*state*) mutlak dari sebuah `Promise`.
2. Jelaskan konsep *immutability* setelah sebuah Promise berada dalam kondisi *settled*. Mengapa pemanggilan `resolve()` atau `reject()` berkali-kali di dalam fungsi *executor* yang sama tidak akan mengubah status atau payload dari Promise tersebut?

### Soal 1.3: Microtask Queue vs. Macrotask Queue
Diberikan urutan eksekusi berikut:
```javascript
console.log('1');
setTimeout(() => console.log('2'), 0);
Promise.resolve().then(() => console.log('3'));
queueMicrotask(() => console.log('4'));
console.log('5');
```
Jelaskan urutan output konsol yang benar secara tepat, dan bedah aturan prioritas pemrosesan antara **Microtask Queue** (`Promise.then`, `queueMicrotask`, `MutationObserver`) dan **Macrotask Queue** (`setTimeout`, `setInterval`, I/O) dalam satu siklus (*tick*) Event Loop.

### Soal 1.4: Dekonstruksi `async/await`
Keyword `async/await` sering disebut sebagai *syntactic sugar* di atas `Promise` dan *generator/coroutine*. Jelaskan apa yang sebenarnya terjadi pada Call Stack ketika eksekutor JavaScript menemui ekspresi `await`. Apa status fungsi tersebut di memori, dan bagaimana eksekusi fungsi dilanjutkan kembali setelah Promise yang di-*await* berstatus *fulfilled*?

### Soal 1.5: Mekanika Kegagalan pada Fetch API
Banyak engineer pemula berasumsi bahwa Fetch API akan melempar error (*reject*) jika server merespons dengan HTTP Status Code `404 Not Found` atau `500 Internal Server Error`.
1. Mengapa arsitektur Fetch API didesain untuk **tidak** menolak (*reject*) Promise pada respons HTTP 4xx dan 5xx?
2. Kondisi teknis apa saja yang secara spesifik membuat `fetch()` menghasilkan *rejected Promise*?
3. Tuliskan pola standar (*idiomatic guard clause*) untuk memvalidasi keberhasilan respons jaringan menggunakan properti `response.ok`.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Microtask Starvation & Event Loop Freezing
Perhatikan potongan kode berikut:
```javascript
function recursiveSchedule() {
  Promise.resolve().then(() => {
    recursiveSchedule();
  });
}
recursiveSchedule();
```
Jelaskan dampak eksekusi kode di atas terhadap browser:
1. Mengapa kode di atas membekukan antarmuka (UI freeze) sepenuhnya, padahal tidak ada *synchronous infinite loop* (seperti `while(true)`) pada Call Stack awal?
2. Bagaimana perilaku di atas berbeda secara fundamental jika implementasi diganti menggunakan `setTimeout(recursiveSchedule, 0)`?

### Soal 2.2: Evaluasi Kritis Kombinator Promise
Sistem backend Anda menyediakan tiga microservice terpisah untuk merender dasbor pengguna: `fetchUserProfile()`, `fetchUserOrders()`, dan `fetchUserNotifications()`.
1. Bandingkan karakteristik penanganan kegagalan (*failure handling*) dan alokasi konkurensi antara `Promise.all()`, `Promise.allSettled()`, `Promise.race()`, dan `Promise.any()`.
2. Jika kegagalan `fetchUserNotifications()` tidak boleh menggagalkan rendering profil dan order, kombinator mana yang wajib digunakan? Justifikasi arsitektur Anda dengan menyertakan mitigasi dampak *fail-fast*.

### Soal 2.3: Lifecycle & Resource Leak pada AbortController
Saat menggunakan `AbortController` untuk membatalkan *in-flight HTTP request*:
1. Jelaskan bagaimana sinyal pembatalan (`AbortSignal`) dipropagasikan dari kontroler ke level socket jaringan di tingkat platform browser.
2. Identifikasi potensi *memory leak* jika `AbortController` diinisialisasi dan dihubungkan ke event listener `abort` tanpa mekanisme pembersihan (*cleanup*) ketika operasi berhasil diselesaikan lebih cepat daripada pembatalan.

### Soal 2.4: Pola Retry dengan Exponential Backoff & Jitter
Implementasi *naive retry* (misal: mencoba ulang secara statis tiap 1 detik saat menerima HTTP 503) dapat memicu fenomena **Thundering Herd Problem** pada infrastruktur server.
1. Jelaskan secara matematis dan konseptual bagaimana penambahan *exponential backoff* ($2^n \times \text{delay}$) memitigasi kelebihan beban pada server.
2. Mengapa penambahan faktor acak (*Full Jitter*) mutlak diwajibkan dalam sistem terdistribusi, bukan sekadar backoff eksponensial deterministik?

### Soal 2.5: Kebocoran Memori (Memory Leak) Akibat Asynchronous Closures
Jelaskan mekanisme terjadinya kebocoran memori ketika sebuah Promise yang tertahan lama (*long-lived* atau *unresolved Promise*) membungkus variabel berukuran besar di dalam *lexical closure*-nya:
```javascript
function processHeavyData() {
  const hugePayload = new Array(10000000).fill('leak');
  return eventEmitter.waitForEvent('data-ready').then(() => {
    console.log(hugePayload[0]);
  });
}
```
Jika event `'data-ready'` tidak pernah dipicu, mengapa Garbage Collector (V8 Engine) dilarang mereklamasi array `hugePayload` dari heap memory? Bagaimana cara refaktor kode di atas agar aman dari kebocoran memori?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: UI Freezing Akibat JSON Parsing Berukuran Masif
* **Konteks:** Sebuah sistem analitik internal memuat dataset historis transaksi logistik sebesar 180 MB dalam satu HTTP GET endpoint. Kode aplikasi:
  ```javascript
  const response = await fetch('/api/v1/massive-logs');
  const data = await response.json(); // Titik freeze
  renderChart(data);
  ```
* **Masalah:** Segera setelah data selesai diunduh dari jaringan, UI browser terkunci (*freeze*) selama 3 hingga 5 detik. Indikator loading berhenti berputar (*jank*), dan event klik pengguna diabaikan oleh browser sebelum grafik akhirnya dirender.
* **Pertanyaan Diagnostik & Solusi:**
  1. Identifikasi akar penyebab pemblokiran UI: apakah proses unduh jaringan (*network stream*), pemanggilan `response.json()`, atau manipulasi DOM yang memblokir main thread?
  2. Rancang arsitektur data fetching alternatif menggunakan kombinasi **Streams API** (`response.body.getReader()`), **Web Worker**, atau manipulasi *chunked processing* agar UI tetap responsif 60 FPS selama proses dekomposisi data berlangsung.

---

### Skenario B: Race Condition pada Search-as-You-Type (Typeahead)
* **Konteks:** Pengguna mengetik kata kunci pada kotak pencarian produk. Sistem mengirimkan request secara dinamis pada tiap penekanan tombol (*keystroke*). Pengguna mengetik `"macb"`, berhenti sebentar, lalu dengan cepat menyempurnakan menjadi `"macbook"`.
* **Masalah:** Input UI menunjukkan teks `"macbook"`, tetapi hasil pencarian yang tampil di layar menampilkan produk untuk kata kunci `"macb"`. Investigasi network panel menunjukkan request untuk `"macb"` membutuhkan waktu 1200ms (karena variasi latency server), sedangkan request untuk `"macbook"` selesai dalam 300ms.
* **Pertanyaan Diagnostik & Solusi:**
  1. Jelaskan mengapa *debounce* saja tidak sepenuhnya mengeliminasi potensi race condition jaringan pada latensi yang fluktuatif.
  2. Implementasikan solusi teknis yang sepenuhnya *bulletproof* menggunakan `AbortController` untuk membatalkan request sebelumnya yang masih *in-flight*.
  3. Alternatif lain: bagaimana cara mengatasi masalah ini tanpa membatalkan koneksi HTTP, melainkan menggunakan mekanisme *Request Sequence Token / Generation Counter*? Bandingkan kelebihan dan kekurangannya.

---

### Skenario C: Cascading Failure Akibat Respon HTTP 429 (Rate Limiting)
* **Konteks:** Aplikasi kasir web (Point-of-Sale) offline-first melakukan sinkronisasi massal atas 200 item transaksi ke server backend via integrasi REST API saat koneksi internet kembali aktif.
* **Masalah:** Tim frontend menggunakan `Promise.all(transactions.map(syncTransaction))` yang menembak 200 HTTP POST sekaligus secara konkuren. Server API gateway langsung merespons dengan HTTP Status `429 Too Many Requests` dan header `Retry-After: 5`. Akibat penanganan error yang tidak terisolasi, seluruh sinkronisasi digagalkan, data transaksi lokal terancam tidak terunggah, dan server gateway mengalami lonjakan beban (*spike CPU*).
* **Pertanyaan Diagnostik & Solusi:**
  1. Identifikasi dua kelemahan fatal pada arsitektur eksekusi `Promise.all` di atas dalam konteks integrasi jaringan enterprise.
  2. Rancang arsitektur client-side concurrency control: Bagaimana cara membatasi pemanggilan paralel agar maksimal hanya ada $N$ request (misal: konkurensi = 4) yang berjalan secara simultan (*worker pool pattern*)?
  3. Bagaimana strategi integrasi parsing header `Retry-After` secara otomatis ke dalam pipeline antrean (*queue*) client-side untuk mematuhi regulasi rate limit server?

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise-Grade Resilient HTTP Client Orchestrator
Bangun sebuah utilitas klien jaringan `ApiClient` *zero-dependency* murni (Vanilla JavaScript/ESNext) yang dapat menangani degradasi jaringan, pembatalan request, deduplikasi transaksi, dan pembatasan beban secara deterministik.

#### Problem Statement
Aplikasi web modern sering kali rentan terhadap kegagalan jaringan sporadis (*network flakiness*), duplikasi pemanggilan data identik (*duplicate requests*), dan pembebanan server berlebih tanpa kontrol antrean. Fetch API bawaan terlalu *low-level* untuk langsung digunakan pada skala produksi tanpa abstraksi yang tangguh.

#### Requirements
Anda diwajibkan menulis sebuah class/modul `ResilientHttpClient` yang memenuhi spesifikasi fungsional berikut:

1. **Concurrency Pool Limiter**: Klien memiliki batas maksimal pemanggilan konkuren global (misal: maksimum 3 koneksi aktif bersamaan). Request selebihnya harus ditahan di dalam antrean internal bergaya FIFO (*First-In, First-Out*).
2. **Exponential Backoff with Full Jitter**:
   - Jika endpoint merespons dengan status `5xx` atau mengalami network error, lakukan retry otomatis hingga maksimal $M$ kali (default: 3 kali).
   - Interval jeda retry harus mengikuti kalkulasi: $\text{Delay} = \text{random}(0, \, \min(\text{MaxDelay}, \, \text{BaseDelay} \times 2^{\text{attempt}}))$.
3. **In-Flight Request Deduplication**:
   - Jika aplikasi memicu pemanggilan HTTP GET ke endpoint yang sama (URL + parameter query identik) sementara request sebelumnya untuk URL tersebut masih berjalan (*in-flight*), klien dilarang membuka koneksi HTTP baru.
   - Klien harus mengembalikan *Promise* yang sama kepada seluruh pemanggil (*consumer*) tersebut.
4. **Unified Abort Handling**:
   - Menerima opsi `timeout` (dalam milidetik). Jika waktu terlampaui, request otomatis dibatalkan via `AbortController` internal.
   - Mampu menerima `signal` eksternal dari caller, sehingga pembatalan oleh komponen UI tetap mematikan siklus retry dan menghapus antrean seketika.
5. **Strict Response Extraction**:
   - Melakukan parsing otomatis untuk payload JSON.
   - Melempar (*throw*) Custom Error Class `HttpError` yang membawa informasi: `status`, `statusText`, `headers`, dan data parsed body jika respons `!response.ok`.

#### Constraints
* **Runtime:** Zero-dependency (Dilarang mengimpor library luar seperti Axios, p-limit, p-retry, lodash, dsb).
* **Environment:** Standar browser modern (ES2022+).
* **Memory Safety:** Pastikan seluruh referensi Promise yang telah selesai dihapus dari cache deduplikasi (*settled cache pruning*) untuk mencegah memory leak.

#### Expected Output
1. File modul implementasi: `ResilientHttpClient.js`.
2. Blok kode verifikasi/simulasi pengujian yang mendemonstrasikan:
   - 10 pemanggilan request sekaligus dengan batas konkurensi 2.
   - Pengecekan retry saat disimulasikan error 500 via mock server / dummy endpoint.
   - Pembatalan via timeout global.
   - Bukti konsol bahwa 2 pemanggilan identik dalam jeda 10ms hanya menghasilkan 1 HTTP traffic di network layer.

---

## 5. Knowledge Check & Checklist

Tandai kotak centang berikut setelah menyelesaikan seluruh pembelajaran dan tantangan di atas untuk memvalidasi kesiapan kompetensi Anda:

### Saya harus memahami:
- [ ] Arsitektur internal JavaScript Event Loop: interaksi Call Stack, Web APIs, Microtask Queue, dan Macrotask (Task) Queue.
- [ ] Aturan deterministik pemrosesan Microtask yang mengosongkan antreannya sebelum render step berikutnya dieksekusi oleh browser.
- [ ] Mekanisme status objek `Promise` (`pending`, `fulfilled`, `rejected`) serta sifat permanen (*settled state immutability*).
- [ ] Transformasi internal sintaks `async/await` dan bagaimana Call Stack melepaskan kendali thread saat ekspresi `await` dievaluasi.
- [ ] Perbedaan fundamental antara error jaringan tingkat protokol (koneksi terputus, DNS failure) dan status respons aplikasi HTTP (4xx, 5xx) pada Fetch API.
- [ ] Karakteristik, komparasi performa, dan kegunaan taktis dari `Promise.all`, `Promise.allSettled`, `Promise.race`, dan `Promise.any`.
- [ ] Dampak arsitektural dari *Thundering Herd Problem* dan formulasi matematika mitigasinya menggunakan *Exponential Backoff with Full Jitter*.
- [ ] Bagaimana siklus hidup `AbortController` beroperasi dan memutus aliran data I/O level rendah (*stream cancellation*).

### Saya tidak perlu menghafal:
- [ ] Daftar lengkap seluruh HTTP Status Code RFC (cukup memahami klasifikasi umum: 1xx, 2xx, 3xx, 4xx, 5xx serta kode kritis seperti 200, 201, 204, 400, 401, 403, 404, 429, 500, 502, 503).
- [ ] Struktur byte internal implementasi engine V8 untuk PromiseReaction records.
- [ ] Semua konfigurasi header usang XMLHttpRequest (XHR) warisan legacy.

### Saya harus bisa melakukan:
- [ ] Melakukan debugging urutan eksekusi asynchronous yang kompleks tanpa menjalankan kode (*mental modeling / trace analysis*).
- [ ] Menulis modul pembungkus Fetch API standar industri yang memiliki parsing respons terpadu, transformasi error, dan validasi `response.ok`.
- [ ] Mengimplementasikan pembatalan request dinamis menggunakan `AbortController` untuk mengeliminasi *race condition* pada komponen UI interaktif (Typeahead/Search/Tab switching).
- [ ] Merancang dan mengeksekusi arsitektur *Concurrent Queue / Worker Pool* Vanilla JavaScript untuk membatasi lonjakan request paralel.
- [ ] Menangani integrasi rate-limiting backend secara elegan melalui pembacaan header `Retry-After`.
- [ ] Mengidentifikasi dan memperbaiki potensi kebocoran memori (*memory leaks*) yang disebabkan oleh *long-lived asynchronous closures* dan event listener tak terlepas.