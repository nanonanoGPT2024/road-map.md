# BAB 08: Quiz, Challenge, & Knowledge Check
**Network Programming & Rack Architecture**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Dekonstruksi Protokol Socket & Non-blocking I/O**
   Jelaskan perbedaan mendasar antara syscall `accept` blocking dan `accept_nonblock` pada objek `TCPServer` di Ruby. Bagaimana Ruby VM merepresentasikan transisi state koneksi TCP di level low-level OS, dan mengapa penanganan exception `IO::WaitReadable` secara deterministik krusial untuk mencegah *busy-waiting* (CPU starvation) pada arsitektur server single-threaded/event-loop?

2. **Anatomi Spesifikasi Antarmuka Rack**
   Spesifikasi Rack mewajibkan respons dari method `#call(env)` mengembalikan *array* 3 elemen: `[status, headers, body]`. 
   - Mengapa komponen `body` diwajibkan merespons terhadap method `#each` dan dilarang keras sekadar mengembalikan objek `String` primitif? 
   - Apa tanggung jawab server web terhadap pemanggilan method `#close` pada objek `body` tersebut, terutama terkait pelepasan *file descriptor* atau *stream buffering*?

3. **Mekanisme Eksekusi Middleware Pipeline (Onion Architecture)**
   Jelaskan alur perjalanan sebuah *request* dan *response* melewati rangkaian Rack Middleware yang dihubungkan secara serial. Jika Middleware B berada di antara Middleware A dan Middleware C (A -> B -> C -> End Application):
   - Bagaimana mutasi terhadap objek `env` hash di Middleware B memengaruhi downstream (C dan App)?
   - Bagaimana penanganan exception (misal: rescue error) di Middleware A dapat menginterupsi siklus respons yang belum diselesaikan oleh Middleware B atau C?

4. **I/O Multiplexing: `IO.select` vs Polling Primitif**
   Mengapa implementasi loop I/O jaringan di Ruby yang mengandalkan pengecekan manual (`sleep` + `read_nonblock`) dianggap sebagai *anti-pattern* performa, dan bagaimana abstraksi `IO.select` (yang membungkus syscall `select(2)` / `poll(2)`) bekerja sama dengan OS kernel untuk mengubah eksekusi *thread* Ruby dari state *running* menjadi *sleeping* hingga kernel buffer siap dibaca?

5. **Trade-off Arsitektur Web Server: Process-Based (Unicorn) vs Threaded (Puma)**
   Bandingkan arsitektur eksekusi web server berbasis *pre-forking multi-process* (Unicorn) dan *clustered multi-threaded* (Puma) dalam mengeksekusi aplikasi Rack di MRI (CRuby). Bagaimana keberadaan Global VM Lock (GVL) menentukan throughput komparatif dari kedua arsitektur tersebut saat melayani workload yang bersifat *I/O-bound* versus *CPU-bound*?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Socket Connection Hijacking (`rack.hijack`)**
   Jelaskan perbedaan mekanistis antara *Full Rack Hijacking* (`rack.hijack` dalam `env`) dan *Partial Hijacking* (`rack.hijack_io` pada response headers). Bagaimana web server modern seperti Puma melepaskan siklus hidup (*lifecycle*) pengelolaan file descriptor TCP socket ke lapisan aplikasi, dan apa konsekuensinya terhadap Thread Pool server jika socket tersebut tidak ditutup secara eksplisit oleh aplikasi WebSocket/SSE?

2. **Diagnostik Memory Leak pada Middleware via Body Wrapping**
   Diberikan sebuah custom middleware yang bertujuan mengompresi payload respons:
   ```ruby
   class CustomGzipMiddleware
     def initialize(app)
       @app = app
     end

     def call(env)
       status, headers, body = @app.call(env)
       new_body = []
       body.each { |chunk| new_body << compress(chunk) }
       [status, headers, new_body]
     end
   end
   ```
   Identifikasi dua cacat desain fatal pada implementasi di atas terkait alokasi memori untuk *large file streaming* dan kegagalan delegasi lifecycle resource! Bagaimana seharusnya `Rack::BodyProxy` digunakan untuk memperbaiki masalah ini?

3. **Penanganan TCP Backpressure dan Partial Writes**
   Ketika menulis response berukuran puluhan megabyte langsung ke socket TCP menggunakan `IO#write_nonblock`, Ruby dapat melemparkan exception `IO::WaitWritable`.
   - Mengapa exception ini muncul di tengah proses penulisan?
   - Rancang algoritma buffer management di tingkat Ruby socket handler untuk menangani parsial write tersebut tanpa memicu *high memory footprint* ataupun memblokir antrean event loop koneksi client lain!

4. **Implikasi Spesifikasi Rack 3 terhadap Mutabilitas Header dan Streaming**
   Rack 3 memperkenalkan pembaruan ketat dibanding Rack 2, di antaranya standardisasi header dengan huruf kecil (*lowercase keys*) dan penghapusan `rack.input` rewindability secara default, serta introduksi objek response streaming yang merespons terhadap `#call(stream)`. Apa dampak breaking changes ini terhadap middleware lama yang melakukan modifikasi header `Content-Length` atau melakukan pembacaan berulang (`rewind`) pada payload request?

5. **Mitigasi Slowloris Attack pada Arsitektur Layer 7 Ruby**
   Jelaskan secara teknis bagaimana serangan jenis *Slowloris* mengeksploitasi konkurensi web server Puma berbasis *thread-per-request* jika diletakkan langsung di internet publik tanpa *reverse proxy* (seperti NGINX atau Envoy). Mengapa konfigurasi `lowlevel_error_handler` atau tuning timeout di level Puma tidak sepenuhnya memadai untuk melindungi Ruby VM dari exhaust resource *thread pool* dan *file descriptors*?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Worker Starvation & Cascading Failure pada Cluster Puma
*Konteks*: Sebuah platform e-commerce dengan trafik tinggi menggunakan Puma (Clustered Mode: 4 workers, 16 threads per worker) yang berjalan di atas Kubernetes. Suatu hari, downstream Payment Gateway pihak ketiga mengalami degradasi performa, meningkatkan waktu respons HTTP dari 200ms menjadi 15 detik. Dalam 3 menit, seluruh Puma worker di semua pod mengalami saturasi 100% thread utilization, backlog queue TCP server membludak, Kubernetes Liveness Probe gagal merespons, dan cluster mengalami siklus *cascading restart* tiada henti (OOMKilled & Probe Timeout).

*Pertanyaan Diagnostik*:
1. Mengapa timeout HTTP client standard di dalam Rack application tidak cukup untuk menghentikan saturasi thread sebelum antrean TCP socket OS (`SOMAXCONN`) penuh?
2. Bagaimana cara mengonfigurasi dan memisahkan connection pool ActiveRecord terhadap thread allocation Puma agar saturasi downstream I/O tidak mengunci seluruh resource pool database?
3. Langkah mitigasi arsitektural apa yang harus diimplementasikan pada level Puma server metrics dan ingress controller untuk menerapkan *graceful degradation* (misal: shedding traffic / short-circuiting)?

### Skenario B: Cross-Tenant Data Contamination via Mutasi Thread-Unsafe Middleware
*Konteks*: Sistem SaaS multi-tenant berbasis Rails/Rack mendeteksi insiden keamanan di mana Tenant A sesekali melihat data sensitif (header profile dan data autentikasi) milik Tenant B. Investigasi awal menunjukkan bahwa bug ini muncul setelah penambahan middleware internal baru:
```ruby
class TenantContextMiddleware
  def initialize(app)
    @app = app
  end

  def call(env)
    @current_tenant = extract_tenant(env)
    Current.tenant = @current_tenant
    
    status, headers, body = @app.call(env)
    
    headers['X-Tenant-ID'] = @current_tenant.id.to_s
    [status, headers, body]
  end

  private

  def extract_tenant(env)
    # Parsing token & fetching tenant object
  end
end
```
*Pertanyaan Diagnostik*:
1. Jelaskan secara presisi letak kondisi *race condition* pada kode middleware di atas saat dijalankan di lingkungan Puma multi-threaded! Mengapa penggunaan instance variable (`@current_tenant`) pada objek middleware berakibat fatal?
2. Bagaimana siklus instansiasi middleware oleh `Rack::Builder` menentukan lifetime dari instance middleware tersebut dalam memori proses Ruby?
3. Tuliskan refaktor kode yang sepenuhnya *thread-safe* untuk kebutuhan di atas menggunakan isolasi berbasis `env` hash atau thread-local isolation (`Fiber.current.storage` / `ActiveSupport::CurrentAttributes`)!

### Skenario C: Dilema Arsitektur High-Throughput Streaming: Falcon (Fiber-based) vs Puma (Threaded)
*Konteks*: Tim infrastruktur sedang merancang microservice baru yang bertugas menyiarkan ribuan data feed keuangan secara *real-time* via Server-Sent Events (SSE). Durasi koneksi client rata-rata terbuka selama 45 menit. Beban diproyeksikan mencapai 25.000 koneksi simultan. Tim memperdebatkan apakah tetap menggunakan arsitektur tradisional Puma (multi-threaded) atau migrasi ke Falcon (arsitektur berbasis `Async` Gem dan Ruby Fiber).

*Pertanyaan Diagnostik*:
1. Hitung dan analisis perbandingan konsumsi memori dan OS Thread footprint antara 25.000 koneksi pada Puma (asumsi batas thread per process secara praktis di OS) vs Falcon (Fiber context switching di userspace).
2. Jika aplikasi tersebut membutuhkan querying data ke database PostgreSQL menggunakan gem C-extension standar (`pg`) yang bersifat *blocking syscall*, kendala fatal apa yang akan timbul pada server berbasis Fiber/Evented seperti Falcon, dan bagaimana cara mengatasinya?
3. Formulasikan matriks keputusan trade-off (keandalan, kompleksitas debugging/profiling, kompatibilitas ekosistem gem C-ext, dan throughput) untuk memilih antara Puma dan Falcon dalam kasus ini!

---

## 4. Chapter Challenge

### Tantangan Praktis: Membangun Minimalist HTTP/1.1 Web Server Berbasis Evented Socket dengan Dukungan Rack Protocol v3 & Middleware Pipeline

#### Problem Statement:
Sebagian besar engineer memahami Rack hanya sebagai "interface antara Rails dan Puma" tanpa memahami bagaimana byte data dari TCP stream diubah menjadi `env` hash dan diproses melalui rantai middleware. Tantangan Anda adalah membangun implementasi server HTTP/1.1 minimalis namun *production-grade conceptual* dari nol menggunakan pustaka murni Ruby `socket`, tanpa dependensi external gem apa pun.

#### Requirements:
1. **TCP Socket Server**:
   - Inisialisasi `TCPServer` pada host `127.0.0.1` dan port `9292`.
   - Gunakan pendekatan non-blocking I/O dengan event loop berbasis `IO.select` untuk memproses multiple incoming connections tanpa spawn 1 OS thread per request (single-thread evented core) atau gunakan fixed-size Worker Thread Pool dengan Thread-Safe Queue.
2. **HTTP/1.1 Parsing Engine**:
   - Baca stream masuk dan parsing Request Line (`METHOD`, `REQUEST_URI`, `HTTP_VERSION`).
   - Parsing HTTP Headers menjadi Hash key-value yang valid sesuai spesifikasi Rack (misal: `Content-Type` menjadi `CONTENT_TYPE`, header lain diawali `HTTP_`, semua uppercase).
   - Tangani parsing body sederhana untuk request ber-header `Content-Length`.
3. **Rack Interface Integration**:
   - Petakan hasil parsing ke objek `env` standar Rack v3:
     - `REQUEST_METHOD`, `PATH_INFO`, `QUERY_STRING`, `SERVER_NAME`, `SERVER_PORT`.
     - `rack.version` (`[3, 0]`), `rack.input` (objek `StringIO`), `rack.errors` (`$stderr`).
     - `rack.url_scheme` (`http`).
4. **Middleware Pipeline Execution**:
   - Implementasikan mini `Rack::Builder` sederhana untuk me-mount minimal 2 middleware:
     - *Middleware 1 (Request Logger)*: Mencatat method, path, HTTP status, dan waktu eksekusi request (benchmark).
     - *Middleware 2 (Custom Header Injector)*: Menambahkan header `X-Served-By: Handcrafted-Ruby-Server` pada array response headers.
   - Eksekusi Rack Application akhir yang mengembalikan status `200`, `content-type: text/plain`, dan body `["Hello from Baremetal Ruby Rack Server!"]`.
5. **Robust Response Writer**:
   - Tulis HTTP/1.1 response valid kembali ke socket TCP:
     - Status line (`HTTP/1.1 <STATUS> <REASON>`).
     - Response headers (termasuk auto-compute `Content-Length` jika tidak disediakan, dan `Connection: close`).
     - Iterasi seluruh chunk pada objek `body` via `#each` dan pastikan memanggil `body.close` jika objek merespons terhadap method tersebut.
   - Tutup client socket secara aman.

#### Constraints:
- **Zero External Gems**: Hanya diperbolehkan menggunakan Standard Library Ruby (`socket`, `stringio`, `uri`, `time`). Gem `rack` tidak boleh di-*require* secara langsung; Anda harus mengimplementasikan kontraknya secara independen!
- **Error Resilient**: Server tidak boleh *crash* jika menerima *malformed HTTP request* (harus mengembalikan response `400 Bad Request`).
- **Resource Cleanup**: Hindari *socket leak* (*file descriptor leak*) dengan memastikan penutupan socket di dalam blok `ensure`.

#### Expected Output:
Program Ruby executable (`server.rb`) yang saat dijalankan via terminal:
```bash
$ ruby server.rb
[INFO] Server running on http://127.0.0.1:9292
```
Dapat merespons request via `curl` secara sempurna:
```bash
$ curl -i http://127.0.0.1:9292/test?filter=active
HTTP/1.1 200 OK
Content-Type: text/plain
X-Served-By: Handcrafted-Ruby-Server
Content-Length: 40
Connection: close

Hello from Baremetal Ruby Rack Server!
```
Dan mencetak log terminal hasil eksekusi middleware:
```text
[LOG] GET /test?filter=active - 200 OK (0.42ms)
```

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Siklus hidup socket TCP pada sistem operasi Unix (`socket`, `bind`, `listen`, `accept`, `close`) dan pemetaannya pada kelas `Socket` & `TCPServer` di Ruby.
- [ ] Mekanisme kerja non-blocking socket I/O, error class `IO::WaitReadable` / `IO::WaitWritable`, serta penanganannya menggunakan multiplexer `IO.select`.
- [ ] Arsitektur internal Rack Specification (v2 dan v3): struktur `env` hash, tuple response `[status, headers, body]`, dan lifecycle streaming `body`.
- [ ] Paradigma Onion Architecture pada Rack Middleware: eksekusi serial, mutasi state down-stream, dan intercepting response up-stream.
- [ ] Mekanisme *Connection Hijacking* (`rack.hijack`) dan bagaimana protokol streaming (WebSocket, SSE) membajak ownership socket dari server.
- [ ] Perbedaan fundamental arsitektur konkuensi server web Ruby: Multi-Process Pre-forking (Unicorn), Hybrid Multi-Threaded (Puma), dan Fiber-based Evented (Falcon).
- [ ] Karakteristik performa eksekusi thread Ruby di MRI (CRuby) terkait GVL (Global VM Lock) untuk operasi I/O-bound vs CPU-bound.
- [ ] Bahaya state mutation dan race condition pada Middleware dalam eksekusi multi-threaded Puma.

### Saya tidak perlu menghafal:
- [ ] Seluruh daftar konstanta RFC HTTP Status Codes dan teks deskripsinya di luar status codes standar (200, 201, 301, 400, 401, 403, 404, 422, 500, 502, 503).
- [ ] Nilai numerik errno OS-level (seperti `Errno::ECONNRESET`, `Errno::EPIPE`, `Errno::EAGAIN`) selain mengerti kapan dan mengapa error tersebut terjadi.
- [ ] Struktur parsing spesifik dari puluhan environment keys non-standar yang disuntikkan oleh vendor cloud atau web server proprietary tertentu.

### Saya harus bisa melakukan:
- [ ] Membangun custom Rack Middleware yang thread-safe, efisien dalam alokasi memori, dan mengelola pembersihan resource secara deterministik via `Rack::BodyProxy`.
- [ ] Melakukan debugging dan profiling pada bottleneck performa server Puma menggunakan metrik worker saturation, thread allocation, dan socket backlog stats.
- [ ] Menulis program Ruby socket dasar yang mampu menangani koneksi concurrent tanpa memicu memory leak atau unhandled socket error exceptions.
- [ ] Mendiagnosis dan mengisolasi insiden *cross-tenant data leakage* yang bersumber dari thread-unsafe state di level middleware.
- [ ] Mengonfigurasi parameter Puma cluster (`workers`, `threads`, `preload_app!`) dan menyelaraskannya dengan *Database Connection Pool size* di lingkungan produksi skala besar.