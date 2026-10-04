# BAB 10: Quiz, Challenge, & Knowledge Check
**Enterprise Security Hardening & Production System Design**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Prototype Pollution & V8 Internal Property Lookup
Jelaskan secara komprehensif bagaimana kerentanan *Prototype Pollution* dieksploitasi dalam runtime V8 JavaScript pada operasi rekursif penggabungan objek (*recursive deep merge* atau *object path assignment*). Bagaimana manipulasi pada `Object.prototype` dapat memicu *Remote Code Execution* (RCE) atau *Denial of Service* (DoS), dan mengapa pembekuan objek menggunakan `Object.freeze()` saja belum tentu menjadi solusi universal jika diterapkan secara parsial dalam skala enterprise?

### Soal 1.2: Event Loop Starvation & Catastrophic Backtracking (ReDoS)
Uraikan secara mekanistik bagaimana mesin Nondeterministic Finite Automaton (NFA) dalam *engine* regex JavaScript (V8 Irregexp) memproses pola yang memiliki ambiguitas kuantifikasi bersarang (*nested quantifiers*). Apa dampak langsung dari *catastrophic backtracking* terhadap *libuv thread pool* dan *Event Loop phase execution* pada Node.js, serta mengapa offloading komputasi regex berat ke *Worker Threads* bukan substitusi permanen untuk mitigasi ReDoS di tingkat arsitektur?

### Soal 1.3: Defense-in-Depth Web Security: SOP, CORS, dan CSP
Bedakan secara fundamental model ancaman (*threat models*) yang ditangani oleh *Same-Origin Policy* (SOP), *Cross-Origin Resource Sharing* (CORS), dan *Content Security Policy* (CSP). Jelaskan mengapa miskonfigurasi `Access-Control-Allow-Origin: *` pada endpoint mutasi data (POST/PUT/DELETE) yang memvalidasi sesi via cookie `SameSite=None` membuka celah Cross-Site Request Forgery (CSRF), meskipun SOP secara teoritis membatasi pembacaan respons (*read access*) antar-origin.

### Soal 1.4: V8 Memory Lifecycles & Garbage Collection Bottlenecks
Jelaskan siklus hidup alokasi memori pada V8 (New Space/Scavenger semi-spaces vs. Old Space/Mark-Sweep-Compact). Dalam konteks Node.js API bervolume tinggi, bagaimana akumulasi closure berumur panjang (*long-lived closures*) dan event listener yang tidak di-*dereference* (*dangling listeners*) memicu peningkatan frekuensi *Major GC* (Stop-the-World pauses)? Bagaimana metrik *Heap Used*, *Heap Total*, dan *External Memory* (Buffer allocation) harus diinterpretasikan untuk mendeteksi memory leak sebelum memicu *OOM (Out-of-Memory) crash*?

### Soal 1.5: Zero-Downtime Deployment & POSIX Signal Handling
Gambarkan alur penanganan sinyal terminasi OS (`SIGTERM` dan `SIGINT`) dalam arsitektur server Node.js terisolasi (misalnya di dalam Kubernetes Pod). Mengapa aplikasi dilarang langsung memanggil `process.exit(0)` saat sinyal diterima? Rincikan langkah-langkah transisi status dari *readiness probe failure*, penutupan *keep-alive connections*, *in-flight requests draining*, hingga pemutusan koneksi *connection pool* database secara deterministik.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Side-Channel Timing Attacks pada Verifikasi Kriptografi
Perhatikan potongan kode autentikasi berikut:
```javascript
function verifyToken(userInputToken, secretToken) {
  if (userInputToken.length !== secretToken.length) return false;
  for (let i = 0; i < userInputToken.length; i++) {
    if (userInputToken[i] !== secretToken[i]) return false;
  }
  return true;
}
```
Jelaskan kelemahan keamanan tingkat rendah pada kode di atas terkait *timing side-channel attacks*. Bagaimana penyerang dapat mengeksploitasi perbedaan waktu eksekusi CPU cycle untuk merekonstruksi token karakter per karakter? Tunjukkan bagaimana modul bawaan `node:crypto` melalui fungsi `timingSafeEqual` mengeliminasi celah ini dan apa prasyarat mutlak alokasi memori (Buffer sizing) sebelum fungsi tersebut dapat dieksekusi dengan aman tanpa melempar eksepsi *RangeError*.

### Soal 2.2: Memory Leak Forensics via V8 Heap Snapshot
Dalam investigasi insiden produksi, ditemukan bahwa pemakaian RSS (*Resident Set Size*) sebuah mikroservis Node.js terus meningkat linear hingga 1.4 GB dalam kurun waktu 48 jam. Saat menganalisis *Heap Snapshot* menggunakan Chrome DevTools:
1. Apa arti representasi metrik **Shallow Size** versus **Retained Size**?
2. Bagaimana Anda memanfaatkan konsep **Dominator Tree** dan **Retainer Path** untuk membuktikan bahwa sebuah `Map` global bertindak sebagai akar penahan (*retaining root*) yang mencegah ribuan instans konteks HTTP request dideallokasi oleh V8 garbage collector?

### Soal 2.3: Server-Side Request Forgery (SSRF) & DNS Rebinding Exploitation
Sebuah aplikasi Node.js menyediakan fitur webhook tester yang menerima URL eksternal dari pengguna dan melakukan HTTP fetch:
```javascript
async function sendWebhook(targetUrl) {
  const parsed = new URL(targetUrl);
  if (['127.0.0.1', 'localhost', '169.254.169.254'].includes(parsed.hostname)) {
    throw new Error('Forbidden host');
  }
  return await fetch(targetUrl);
}
```
Uraikan secara presisi bagaimana proteksi berbasis blacklist string/hostname di atas dapat ditembus menggunakan teknik **DNS Rebinding Attack** atau resolusi IPv6 (misalnya `::1` atau IPv4-mapped IPv6 `::ffff:127.0.0.1`). Rancang mekanisme validasi tingkat jaringan menggunakan custom HTTP Agent yang memvalidasi resolved IP address sebelum koneksi TCP (*socket connect*) diinisiasi.

### Soal 2.4: Deep Immutability, Proxy Traps, dan Performance Penalty
Implementasi defensive programming sering memanfaatkan `Object.freeze()` secara rekursif atau membungkus objek konfigurasi/keadaan dengan `Proxy` ber-trap `set` dan `defineProperty`. Jelaskan secara mendalam:
1. Mengapa `Object.freeze()` gagal mencegah mutasi pada properti yang mereferensikan tipe non-primitif (seperti `Date`, `Set`, atau `Map`)?
2. Bagaimana dampak penggunaan runtime `Proxy` yang ekstensif terhadap optimasi *Hidden Classes* dan *Inline Caches* (IC) pada V8 TurboFan compiler? Kapan proteksi runtime berbasis Proxy harus dihindari di *hot path* pemrosesan data?

### Soal 2.5: Concurrency Safety: SharedArrayBuffer, Atomics, dan Race Conditions
Ketika mengeksekusi komputasi paralel menggunakan Node.js `worker_threads` yang berbagi memori melalui `SharedArrayBuffer`:
1. Mengapa mutasi langsung non-atomik (misalnya `view[0]++`) menyebabkan *data races* dan inkonsistensi memori lintas thread?
2. Jelaskan bagaimana instruksi `Atomics.compareExchange` dan `Atomics.wait`/`Atomics.notify` bekerja di tingkat instruksi prosesor untuk mengimplementasikan *lock-free synchronization primitives* tanpa memblokir *Main Event Loop thread*.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: The Event Loop Lag & Cascading Failure Domino Effect
**Konteks Produksi:**
Sebuah kluster e-commerce berbasis Node.js mengalami insiden kritis saat *Flash Sale*. Metrik APM menunjukkan throughput request melonjak dari 2.000 RPS menjadi 15.000 RPS. Secara tiba-tiba, metrik **Event Loop Delay (ELD)** melonjak dari 2ms ke 4.500ms. Kubernetes Liveness Probe (konfigurasi: HTTP GET `/healthz`, timeout: 1s, failureThreshold: 3) mulai gagal secara masif. Kubernetes mengidentifikasi pod tidak responsif dan melakukan restart serentak (*mass eviction/restart*). Hal ini menyebabkan beban terdistribusi ke sisa pod yang masih hidup, memicu kegagalan berantai (*thundering herd & cascading collapse*). 

CPU utilisasi berada di angka 95%, namun profiling menunjukkan penggunaan waktu komputasi terbanyak bukan pada I/O jaringan, melainkan pada eksekusi JavaScript synchronous: deserialisasi JSON berukuran 5MB dari Redis cache dan operasi enkripsi token JWT yang tidak dioptimalkan.

**Pertanyaan Diagnostik:**
1. Mengapa penempatan *Health Check probe* pada Event Loop yang sama dengan thread aplikasi bisnis merupakan anti-pattern arsitektur dalam skenario latensi tinggi?
2. Apa strategi perbaikan arsitektural untuk memisahkan lifecycle health checking dari processing queue?
3. Rancang formula degradasi beban (*graceful degradation / shed load*) menggunakan metrik Event Loop Delay: bagaimana sistem menolak request baru (HTTP 503) di layer Node.js middleware sebelum server kehabisan memori atau gagal merespons liveness probe?

---

### Skenario B: Distributed Async Concurrency Hazard pada Ledger Saldo
**Konteks Produksi:**
Sebuah platform fintech memproses pencairan dana (*withdrawal*) secara asinkron menggunakan arsitektur Node.js microservices. Skema pemrosesan saldo pengguna pada database relasional menggunakan pola:
1. `GET /balance` dari database via query `SELECT balance FROM accounts WHERE id = ?`.
2. Validasi bisnis di layer JavaScript: `if (balance >= withdrawAmount) { ... }`.
3. Komputasi sisa saldo: `const newBalance = balance - withdrawAmount;`.
4. Delay asinkron terjadi karena pemanggilan API Fraud Detection eksternal via `await verifyFraudRisk(userId)`.
5. Eksekusi mutasi saldo: `UPDATE accounts SET balance = ? WHERE id = ?`.

Penyerang mengirimkan 10 HTTP POST request pencairan dana sebesar Rp 1.000.000 secara serentak (konkurensi tinggi dalam rentang waktu 5 milidetik) pada akun yang hanya memiliki saldo Rp 1.000.000. Hasil audit menunjukkan penyerang berhasil mencairkan total Rp 10.000.000, menyebabkan saldo akun akhir menjadi Rp 0 (bukan negatif, tetapi terjadi *double/multiple spending* masif).

**Pertanyaan Diagnostik:**
1. Identifikasi secara tepat letak celah *Time-of-Check to Time-of-Use* (TOCTOU) race condition dalam pipeline asinkron JavaScript tersebut. Mengapa model *single-threaded* JavaScript sama sekali tidak melindungi aplikasi dari *distributed concurrency hazard* semacam ini?
2. Berikan 2 pendekatan mitigasi konkret:
   - Solusi di tingkat database layer (Pessimistic vs. Optimistic Locking / Atomic Conditional Updates).
   - Solusi di tingkat arsitektur Node.js terdistribusi (Distributed Lock via Redis Redlock atau Queued Serialization). Tuliskan pseudocode atau query SQL yang benar-benar kebal terhadap serangan konkurensi ini.

---

### Skenario C: Trade-off Arsitektur Token Security: Asymmetric Stateless JWT vs. Opaque Token Introspection
**Konteks Produksi:**
Perusahaan perbankan skala enterprise sedang merancang arsitektur autentikasi untuk 40 microservices backend yang saling berkomunikasi melalui Internal API Gateway. Tim arsitektur terbelah menjadi dua kubu:
*   **Kubu A (Stateless JWT):** Mengusung EdDSA/RS256 signed JWT. Gateway memvalidasi signature menggunakan public key (JWKS) yang di-*cache*. Token membawa klaim otorisasi penuh (*roles, permissions, scopes*). Tidak ada *state* tersimpan di database/cache backend. Validitas token: 1 jam.
*   **Kubu B (Stateful Opaque Token):** Gateway menerima string acak terenkripsi (Opaque Reference Token). Gateway harus melakukan *introspection call* via high-performance distributed Redis cache atau memanggil Auth Service untuk mengecek keabsahan token dan *revocation status* pada setiap request yang masuk.

**Studi Kasus Insiden:**
Salah satu hak akses pengguna level admin dicabut seketika (*instant privilege revocation*) karena perangkatnya teridentifikasi malware. Selain itu, sebuah token valid berhasil diekspos melalui log error pihak ketiga.

**Pertanyaan Diagnostik:**
1. Bedakan konsekuensi fatal penggunaan *Stateless JWT* dalam skenario pembatalan akses seketika (*instant revocation*) di atas. Mengapa mekanisme *short-lived token + refresh token* seringkali masih menyisakan *security gap window* yang tidak dapat diterima pada sistem berisiko tinggi?
2. Bagaimana trade-off performa, kompleksitas infrastruktur, dan latensi jaringan (*network overhead*) antara Kubu A dan Kubu B saat sistem menangani 50.000 RPS?
3. Rancang arsitektur hibrida (*Hybrid Architecture*) yang mempertahankan performa verifikasi lokal asinkron dari JWT, namun tetap memiliki kemampuan *real-time revocation* tanpa membebani database utama pada setiap incoming HTTP request.

---

## 4. Chapter Challenge

### Tantangan Praktis: Hardened Zero-Trust Webhook Ingestion Engine with Distributed Backpressure & Resiliency Defense

#### 1. Deskripsi Masalah
Anda diminta membangun modul enterprise ingestion gateway berkinerja tinggi menggunakan Node.js murni (*native HTTP/crypto*) atau framework minimalis, yang bertugas menerima webhook sensitif (seperti notifikasi transaksi pembayaran perbankan) dari penyedia pihak ketiga. Modul ini menjadi pintu masuk utama sistem yang rentan terhadap serangan ReDoS, JSON Bomb (Denial of Service via parsing payload besar), Timing Attack, Replay Attack, serta ancaman Event Loop Lag akibat banjir traffic.

#### 2. Kebutuhan Teknis (Functional & Security Requirements)
1. **Cryptographic Signature Verification:**
   - Webhook dikirimkan bersama header `X-Signature-SHA256` dan `X-Timestamp` (format ISO-8601).
   - Validasi signature dilakukan menggunakan HMAC-SHA256 atas kombinasi payload: `${timestamp}.${rawBody}`.
   - Komparasi signature wajib menggunakan teknik **constant-time string comparison** (`crypto.timingSafeEqual`) untuk menangkal side-channel timing attack.
2. **Replay Attack Mitigation:**
   - Request dengan nilai `X-Timestamp` yang berselisih lebih dari 5 menit (toleransi clock skew: 300 detik) dari waktu sistem server lokal harus di-*reject* secara deterministik sebelum komputasi kriptografi dilakukan.
3. **Payload Sanitization & Resource Limiting:**
   - Membatasi ukuran payload mentah (*raw body streaming*) maksimal 64 KB. Jika client mengirim data melebihi batas tersebut, koneksi harus dihentikan secara agresif (*destroy socket*) guna mencegah memory exhaustion.
   - Mengimplementasikan parsing JSON yang aman terhadap *Prototype Pollution* (menolak payload yang mengandung kunci `__proto__`, `constructor`, atau `prototype`).
4. **Adaptive Backpressure & Event Loop Health Gate:**
   - Pantau metrik *Event Loop Delay* menggunakan `perf_hooks.monitorEventLoopDelay`.
   - Jika nilai percentile ke-99 ($p_{99}$) dari Event Loop Delay melampaui ambang batas 100ms, gateway secara otomatis memasuki mode **Shed Load**: tolak request baru yang masuk dengan status code `HTTP 503 Service Unavailable` dan header `Retry-After: 30`.

#### 3. Batasan Teknis (Constraints)
- Tidak diperbolehkan menggunakan library pihak ketiga tingkat tinggi (seperti Express, Fastify, Lodash, atau Body-Parser). Gunakan modul bawaan Node.js: `node:http`, `node:crypto`, `node:perf_hooks`, `node:buffer`.
- Kode harus ditulis dalam format clean JavaScript modern (ESM) atau TypeScript yang kompatibel dengan runtime Node.js LTS (v20+).
- Penanganan asynchronous I/O wajib menggunakan pola `async/await` yang bersih, tanpa *unhandled promise rejections* atau kebocoran resource stream.

#### 4. Kriteria Keberhasilan & Expected Output
- File script mandiri (misal: `webhook-server.js` atau `webhook-server.ts`).
- Server harus lolos pengujian terhadap vektor serangan berikut:
  1. *Payload Tampering:* Perubahan 1 bit pada body request menghasilkan `HTTP 401 Unauthorized`.
  2. *Replay Attempt:* Pengiriman request yang sama dengan timestamp 6 menit yang lalu menghasilkan `HTTP 400 Bad Request`.
  3. *Oversized Buffer:* Pengiriman stream payload sebesar 10 MB langsung diputus pada transmisi 64 KB pertama dengan `HTTP 413 Payload Too Large`.
  4. *Prototype Injection:* Pengiriman payload valid JSON `{"__proto__": {"admin": true}}` di-reject dengan status `HTTP 422 Unprocessable Content`.
  5. *High-Load Starvation:* Di bawah injeksi loop CPU intensif, server mempertahankan responsivitas endpoint health check atau mengembalikan 503 secara deterministik tanpa crash akibat `OutOfMemory`.

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk mengukur kesiapan teknis Anda dalam mendesain sistem produksi JavaScript/Node.js berskala besar dan berstandar enterprise.

### Saya harus memahami:
- [ ] Vektor serangan Prototype Pollution pada mesin V8 dan cara runtime mengeksekusi lookup properti melalui prototype chain.
- [ ] Mekanisme kerja V8 Garbage Collection (Scavenge, Mark-Sweep, Compact) dan bagaimana memory leak di Old Generation memicu Event Loop latency spikes.
- [ ] Algoritma backtracking regex pada V8 Irregexp engine dan karakteristik pola ekspresi reguler yang rentan terhadap ReDoS ($O(2^n)$ atau $O(n^k)$ complexity).
- [ ] Anatomi timing attack pada verifikasi byte buffer dan implementasi low-level dari `crypto.timingSafeEqual`.
- [ ] Batasan Same-Origin Policy (SOP) dan bagaimana CORS preflight (`OPTIONS`), CSP directives, serta atribut Cookie (`SameSite`, `HttpOnly`, `Secure`) membentuk pertahanan berlapis.
- [ ] Konsep Time-of-Check to Time-of-Use (TOCTOU) dalam operasi asynchronous JavaScript yang melibatkan external state storage (Database/Redis).
- [ ] Dinamika POSIX signals (`SIGTERM`, `SIGINT`) dan fase-fase graceful shutdown koneksi TCP/HTTP pada runtime Node.js.
- [ ] Perbedaan model memori antara Single-Threaded Event Loop, Worker Threads (`SharedArrayBuffer`, `MessageChannel`), dan Multi-Process Clustering.

### Saya tidak perlu menghafal:
- [ ] Sintaks mikro regex engine internal atau bytecode assembly internal V8 (cukup pahami kompleksitas algoritma dan cara audit pola regex).
- [ ] Seluruh tabel kode status HTTP RFC 9110 secara berurutan (cukup pahami semantik status error esensial: 400, 401, 403, 409, 413, 422, 429, 503).
- [ ] Struktur byte internal penulisan sertifikat X.509 atau representasi biner ASN.1 (cukup pahami cara kerja validasi TLS dan Public Key Infrastructure).
- [ ] Detail algoritma kompresi zlib/gzip internal (cukup pahami dampak kompresi terhadap kerentanan keamanan seperti CRIME/BREACH dan alokasi CPU-nya).

### Saya harus bisa melakukan:
- [ ] Mengambil, membaca, dan menganalisis V8 Heap Snapshot menggunakan Chrome DevTools untuk menemukan retaining paths dari memory leak di lingkungan produksi.
- [ ] Memasang instrumentasi APM untuk mengukur Event Loop Delay ($p_{50}, p_{95}, p_{99}$) secara real-time dan mengonfigurasinya sebagai health metric pod.
- [ ] Membangun custom JSON parser validator atau reviver function untuk menolak payload yang terkontaminasi unsafe keys (`__proto__`, `constructor`).
- [ ] Menulis arsitektur HTTP graceful shutdown di Node.js yang mengosongkan in-flight request pool sebelum menutup database client connections.
- [ ] Mengamankan interaksi database terdistribusi dari race condition asinkron menggunakan transaksi terisolasi atau atomic updates.
- [ ] Merancang policy CORS dan CSP berbasis Nonce/Hash yang ketat untuk mencegah eksekusi unauthorized inline scripts dan data exfiltration.