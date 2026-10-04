# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 04: Resource Management & Low-Level I/O**
**Kategori: 02-Programming-Languages (Ruby)**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Menganalisis struktur internal I/O Ruby MRI (`rb_io_t`, buffer C runtime, dan interaksi dengan *Giant VM Lock* / GVL).
- Mengimplementasikan pola I/O non-blocking tingkat rendah menggunakan `read_nonblock`, `write_nonblock`, dan I/O multiplexing (`IO.select`, Fiber Scheduler) tanpa alokasi memori yang redundan.
- Membangun arsitektur *zero-copy data pipeline* di Linux menggunakan `IO.copy_stream` (yang memetakan ke `sendfile(2)`) dan memory mapping (`mmap`) untuk beban kerja throughput tinggi.
- Mendiagnosis dan memitigasi anomali sistemik seperti file descriptor leak, buffer bloat, serta CPU spinning akibat *busy-wait* pada event loop.
- Merancang subsistem penanganan resource yang deterministik dan aman terhadap kegagalan konkurensi (thread-safe dan fiber-safe).

---

## 2. Prerequisite

Sebelum mempelajari modul ini, Anda harus menguasai:
- Konsep dasar UNIX/Linux System Calls: `open(2)`, `read(2)`, `write(2)`, `close(2)`, `fcntl(2)`, `epoll(7)`.
- Pemahaman siklus hidup memori Ruby (Ruby Heap, ObjectSpace, Garbage Collection, GC Compaction).
- Pengetahuan dasar konkurensi Ruby: Thread, Fiber, Ractor, dan karakteristik GVL.
- Penggunaan CLI diagnostik Linux: `strace`, `lsof`, `vmstat`, dan `/proc/<pid>/fd`.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Struktur Internal I/O Ruby MRI (`rb_io_t`)

Di balik kelas `IO` pada Ruby (MRI/CRuby), terdapat abstraksi C tingkat rendah yang didefinisikan dalam struktur `rb_io_t` (didefinisikan di `include/ruby/io.h` atau internal header MRI):

```c
// Representasi konseptual rb_io_t pada MRI
typedef struct rb_io_t {
    int fd;                     // Underlying OS File Descriptor
    FILE *stdio_file;           // C stdio pointer (jika menggunakan buffered I/O standard)
    int mode;                   // Mode flag (FMODE_READABLE, FMODE_WRITABLE, dll.)
    rb_pid_t pid;               // PID proses anak jika IO dibuka via pipe/popen
    struct rb_io_buffer_t rbuf; // Buffer baca internal level user-space
    struct rb_io_buffer_t wbuf; // Buffer tulis internal level user-space
    VALUE pathv;                // Path file asli untuk debugging
    void *scheduler;            // Hook Fiber Scheduler (Ruby 3+)
    // ... metadata internal lainnya
} rb_io_t;
```

Ketika operasi `IO#read` atau `IO#write` dieksekusi:
1. Ruby memeriksa apakah data sudah tersedia di buffer internal user-space (`rbuf`).
2. Jika tidak ada, Ruby melepaskan GVL via fungsi internal `rb_thread_call_without_gvl()` sebelum memanggil syscall `read(2)` blocking. Hal ini memungkinkan Ruby thread lain tetap mengeksekusi bytecode Ruby.
3. Setelah kernel menyalin data dari *kernel page cache* ke buffer user-space Ruby, GVL diakuisisi kembali oleh thread tersebut sebelum membungkus data ke dalam objek `String`.

```
+-------------------------------------------------------------------------+
|                              Ruby User Space                            |
|                                                                         |
|  +--------------------+                                                 |
|  |     Ruby Code      |  IO#readpartial(16384, reusable_buffer)         |
|  +---------+----------+                                                 |
|            |                                                            |
|            v                                                            |
|  +--------------------+   (rb_io_t)                                     |
|  |    Ruby MRI VM     |   Allocates String or writes to outbuf          |
|  |                    |   Releases GVL -> Calls OS syscall              |
|  +---------+----------+                                                 |
+------------|------------------------------------------------------------+
             | System Call Boundary: read(2) / write(2) / sendfile(2)
+------------|------------------------------------------------------------+
|            v                 Kernel Space                               |
|  +--------------------+                                                 |
|  |     VFS Layer      |                                                 |
|  +---------+----------+                                                 |
|            |                                                            |
|            +-------------------------------+                            |
|            |                               |                            |
|            v                               v                            |
|  +--------------------+         +--------------------+                  |
|  |    Page Cache      |         | Socket Buffer (SKB)|                  |
|  +---------+----------+         +----------+---------+                  |
|            |                               |                            |
|            v                               v                            |
|    [ Block Storage ]                [ NIC Driver ]                      |
+-------------------------------------------------------------------------+
```

### 3.2 Non-Blocking I/O dan State Machine

Pada mode blocking, syscall `read(2)` menahan eksekusi thread sampai kernel menerima byte data. Sebaliknya, non-blocking I/O mengubah deskriptor file melalui flag `O_NONBLOCK`.

Ketika operasi I/O dilakukan pada deskriptor non-blocking dan kernel buffer kosong, kernel mengembalikan error code `EAGAIN` atau `EWOULDBLOCK`. Pada Ruby:
- Metode bawaan seperti `read_nonblock(maxlen)` secara default akan melempar exception `IO::WaitReadable`.
- Alokasi exception di Ruby membutuhkan alokasi frame stack trace dan memori heap yang sangat mahal.
- Ruby menyediakan flag `exception: false`. Jika flag ini disetel, alih-alih melempar exception, metode ini mengembalikan simbol khusus `:wait_readable` atau `:wait_writable`.

### 3.3 Ruby 3+ Fiber Scheduler Interception

Sejak Ruby 3.0, Ruby memperkenalkan arsitektur antarmuka *Fiber Scheduler* (`Fiber.set_scheduler`). Ketika *scheduler* terpasang:
1. Operasi I/O standar seperti `io.read` tidak lagi memblokir native thread OS.
2. Ruby mendeteksi keberadaan scheduler dan memanggil hook scheduler (misalnya `scheduler.io_read(io, buffer, length, offset)`).
3. Fiber yang sedang aktif akan di-*suspend* (`Fiber.yield`), dan underlying deskriptor didaftarkan ke event loop backend (misalnya `epoll` di Linux atau `kqueue` di macOS / BSD).
4. Native OS thread bebas menjalankan Fiber lain tanpa perlu mengubah kode blocking synchronous menjadi callback atau async/await.

---

## 4. Why & What

| Dimensi | High-Level I/O Abstraction (`File.read`, `Net::HTTP`) | Low-Level I/O (`IO#readpartial`, `sendfile`, Non-blocking) |
| :--- | :--- | :--- |
| **Alokasi Memori** | Mengalokasikan string baru secara agregat di Ruby Heap. Rawan memicu OOM pada payload gigabyte. | Menggunakan reusable heap-buffer atau menghindari user-space allocations sepenuhnya (*Zero-Copy*). |
| **Kontrol Backpressure**| Nyaris tidak ada; sistem membaca semua data ke memori tanpa memperhatikan kapasitas receiver. | Granular; pembacaan dan penulisan dikontrol per-chunk berdasarkan ketersediaan buffer socket (`EAGAIN`). |
| **Throughput & Concurrency** | Terbatas oleh memory footprint dan alokasi thread OS yang masif. | Mendukung arsitektur *event-driven* C10K/C100K melalui single thread / small thread pool. |
| **Abstraksi Error** | Error dibungkus menjadi standard errors, detail state soket TCP tingkat rendah tersembunyi. | Menangani langsung status kernel: `ECONNRESET`, `EPIPE`, `ETIMEDOUT`, `EAGAIN`. |

Mengapa drop-down ke Low-Level I/O di Enterprise:
1. **Predictable Tail Latency (p99/p99.9)**: Mencegah *stop-the-world GC pause* yang disebabkan oleh pembuatan jutaan string sementara (garbage) per detik.
2. **Resource Saturation Guard**: Menjamin batas penggunaan *file descriptor* dan memori virtual (VIRT/RES) tetap konstan di bawah beban puncak.
3. **Hardware Maximization**: Memanfaatkan kapabilitas transfer zero-copy perangkat keras jaringan dan media penyimpanan NVMe secara native.

---

## 5. How (Workflow Detail)

Alur kerja implementasi stream pemrosesan I/O non-blocking berbasis reusability buffer dan multiplexing:

```
[ Inisialisasi ]
       │
       ▼
[ Buat / Ambil IO FD ] ───► [ Set O_NONBLOCK ]
       │
       ▼
┌────────────────────────────────────────────────────────┐
│  Loop Pemrosesan                                       │
│                                                        │
│  1. Panggil read_nonblock(CHUNK, buf, exception: false)│
│                                                        │
│  2. Evaluasi Hasil:                                    │
│     ├──> String data      : Proses chunk data          │
│     ├──> :wait_readable   : IO.select([fd], nil, nil)  │
│     │                       (Suspend hingga ready)     │
│     ├──> nil (EOF)        : Tutup koneksi / Berhenti   │
│     └──> Exception        : Tangani Error Jaringan     │
└────────────────────────────────────────────────────────┘
       │
       ▼
[ Deterministic Cleanup: Ensure close & Deregister FD ]
```

1. **Konfigurasi Flag**: Modifikasi status socket menggunakan `fcntl(F_SETFL, O_NONBLOCK)` atau lewat interface Ruby `io.nonblock = true`.
2. **Buffer Pre-Allocation**: Alokasikan string penyangga satu kali di luar loop: `buf = String.new(capacity: 64.kilobytes)`.
3. **Non-blocking Consumption**: Gunakan `io.read_nonblock(size, buf, exception: false)`. Pola ini menginstruksikan VM untuk mengisi kembali `buf` yang sama tanpa merealokasi slot objek baru di Ruby Heap.
4. **Kernel Polling**: Jika membaca mengembalikan simbol `:wait_readable`, masukkan deskriptor ke multiplexer I/O (`IO.select` atau Fiber Scheduler) untuk menunggu interrupt kernel.
5. **Backpressure Propagation**: Jangan membaca dari source jika downstream destination mengembalikan `:wait_writable`. Terapkan jeda penyerapan data hingga socket buffer tujuan mengosongkan antriannya.
6. **Graceful Teardown**: Tutup deskriptor dalam blok `ensure` deterministik. Jangan mengandalkan Garbage Collector finalizer untuk menutup socket atau file.

---

## 6. Analogy & Diagram ASCII

### Analogi Logistik: *Forklift vs Pipeline Pneumatik*
- **Standard I/O (`File.read`)**: Seperti mempekerjakan kurir yang memuat seluruh isi gudang ke dalam kotak-kotak karton kecil (Ruby String objects) dan menumpuknya di lobi utama. Gudang cepat kehabisan ruang (*Out of Memory*), dan petugas kebersihan (*Garbage Collector*) harus menyapu ribuan kotak kosong setelah barang diambil.
- **Zero-Copy / Low-Level Buffer (`IO.copy_stream` / `readpartial(size, buf)`)**: Seperti pipa pneumatik tertutup antara ruang penyimpanan dan dermaga pengiriman. Data dipompa langsung di tingkat kernel tanpa pernah diletakkan di lantai gudang aplikasi, menggunakan kontainer logam yang sama berulang kali.

### Arsitektur Aliran Data: Zero-Copy vs Standard User-Space Copy

```
========================= 1. STANDARD DATA PATH =========================
Disk Read -> Kernel Page Cache -> User-space Ruby String -> Kernel Socket Buffer -> NIC
[Disk] ──────► [Page Cache] ──────► [Ruby Heap] ──────► [Socket Buf] ──────► [NIC]
 (DMA Transfer)            (CPU Copy)          (CPU Copy)           (DMA Transfer)
               * Membutuhkan 2 Context Switch & 2 Alokasi CPU Copy *

=========================== 2. ZERO-COPY PATH ===========================
Disk Read -> Kernel Page Cache ────────────────────────► Kernel Socket Buffer ──► NIC
                                   (Kernel-Level Copy /
                                  Splice / sendfile(2))
[Disk] ──────► [Page Cache] ───────────────────────────► [Socket Buf] ──────► [NIC]
 (DMA Transfer)                                                     (DMA Transfer)
               * 0 CPU Copy ke User Space, 0 Ruby Heap Allocation *
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Non-blocking TCP Read Menggunakan Pre-allocated Buffer

Contoh ini menunjukkan cara membaca data socket tanpa memicu alokasi heap berlebih dan tanpa melempar exception overhead.

```ruby
# frozen_string_literal: true
require 'socket'

server = TCPServer.new('127.0.0.1', 9001)
puts "[INFO] Server listening on port 9001..."

client = server.accept
client.nonblock = true

# Pra-alokasi buffer tunggal (32 KiB)
buffer = String.new(capacity: 32 * 1024)

begin
  loop do
    # exception: false mencegah pembuatan exception object IO::WaitReadable
    case result = client.read_nonblock(32 * 1024, buffer, exception: false)
    when :wait_readable
      # Menunggu kernel socket buffer memiliki data
      IO.select([client], nil, nil, 5.0)
    when nil
      puts "[INFO] Client menutup koneksi (EOF)."
      break
    else
      # 'result' merujuk ke instance 'buffer' yang sama
      puts "[DATA RECEIVED] #{result.bytesize} bytes (Buffer Object ID: #{buffer.object_id})"
      # Kirim balik respons echo
      client.write_nonblock("ACK: #{result.bytesize}\n", exception: false)
    end
  end
rescue Errno::ECONNRESET, Errno::EPIPE => e
  warn "[ERROR] Koneksi putus abnormal: #{e.message}"
ensure
  client&.close unless client&.closed?
  server.close unless server.closed?
end
```

### 7.2 Practical Example: High-Throughput Streaming File Server Menggunakan Zero-Copy

Implementasi server HTTP streaming chunked/file enterprise yang memanfaatkan socket flag `TCP_CORK` (di Linux) dan `IO.copy_stream` untuk memicu syscall `sendfile(2)`.

```ruby
# frozen_string_literal: true
require 'socket'

class ZeroCopyFileServer
  CHUNK_SIZE = 64 * 1024 # 64 KB

  def initialize(host, port, root_dir)
    @server = TCPServer.new(host, port)
    @root_dir = File.expand_path(root_dir)
    configure_socket_options(@server)
  end

  def start
    puts "[INFO] ZeroCopyFileServer running on #{@server.local_address.ip_port}..."
    loop do
      client = @server.accept
      Thread.new(client) { |conn| handle_connection(conn) }
    end
  rescue Interrupt
    puts "\n[INFO] Gracefully shutting down..."
  ensure
    @server.close unless @server.closed?
  end

  private

  def configure_socket_options(socket)
    # Reuse address & port untuk zero-downtime reload
    socket.setsockopt(Socket::SOL_SOCKET, Socket::SO_REUSEADDR, true)
    socket.setsockopt(Socket::SOL_SOCKET, Socket::SO_REUSEPORT, true) rescue nil
  end

  def handle_connection(client)
    # Optimasi TCP: Mengirim header dan payload dalam segmen jaringan minimal
    enable_tcp_cork(client)

    request_line = client.gets
    return if request_line.nil?

    parts = request_line.split(' ')
    target_path = parts[1]

    file_path = File.join(@root_dir, File.basename(target_path))

    unless File.file?(file_path)
      send_not_found(client)
      return
    end

    file_size = File.size(file_path)

    # 1. Tulis HTTP Headers
    headers = "HTTP/1.1 200 OK\r\n" \
              "Content-Type: application/octet-stream\r\n" \
              "Content-Length: #{file_size}\r\n" \
              "Connection: close\r\n" \
              "\r\n"
    client.write(headers)

    # 2. Transfer Data menggunakan IO.copy_stream (Zero-Copy sendfile)
    File.open(file_path, 'rb') do |file_io|
      bytes_sent = IO.copy_stream(file_io, client)
      puts "[SUCCESS] Streamed #{bytes_sent} bytes via Kernel Zero-Copy."
    end
  rescue Errno::ECONNRESET, Errno::EPIPE
    # Client disconnect mendadak, abaikan untuk stabilitas server
  ensure
    disable_tcp_cork(client)
    client.close unless client.closed?
  end

  def send_not_found(client)
    body = "404 Not Found\r\n"
    client.write "HTTP/1.1 404 NOT FOUND\r\nContent-Length: #{body.bytesize}\r\n\r\n#{body}"
  end

  # TCP_CORK (Linux) atau TCP_NOPUSH (BSD/macOS) menahan paket sampai flush
  def enable_tcp_cork(socket)
    if defined?(Socket::TCP_CORK)
      socket.setsockopt(Socket::IPPROTO_TCP, Socket::TCP_CORK, 1)
    elsif defined?(Socket::TCP_NOPUSH)
      socket.setsockopt(Socket::IPPROTO_TCP, Socket::TCP_NOPUSH, 1)
    end
  rescue StandardError => e
    # Log fallback jika kernel tidak mendukung
  end

  def disable_tcp_cork(socket)
    return if socket.closed?
    if defined?(Socket::TCP_CORK)
      socket.setsockopt(Socket::IPPROTO_TCP, Socket::TCP_CORK, 0) rescue nil
    elsif defined?(Socket::TCP_NOPUSH)
      socket.setsockopt(Socket::IPPROTO_TCP, Socket::TCP_NOPUSH, 0) rescue nil
    end
  end
end

# Eksekusi server jika dijalankan langsung
if __FILE__ == $0
  Dir.mktmpdir do |dir|
    test_file = File.join(dir, "large_asset.bin")
    File.write(test_file, SecureRandom.random_bytes(10 * 1024 * 1024)) # 10MB Mock Data
    
    server = ZeroCopyFileServer.new('127.0.0.1', 8080, dir)
    trap('INT') { exit }
    server.start
  end
end
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Pipeline Ingesti Telemetri & Log Multi-Gigabyte (Fintech Payment Gateway)

#### Konteks & Masalah
Sebuah platform pemrosesan pembayaran memproses 200 juta transaksi harian. Microservice berbasis Ruby memvalidasi dan mem-parsing log audit biner sebesar ~8 TB per hari. 
Implementasi awal menggunakan:
```ruby
# Anti-pattern: High-memory footprint
File.readlines(log_file).each do |line|
  process_audit(line)
end
```
**Dampak Sistemik:**
1. **OOM Kills**: Worker Ruby mengalami crashing berulang kali akibat penggunaan memori menembus batas kontainer Kubernetes (8 GB limit).
2. **GC Pause Bloat**: Waktu henti proses (*Stop-the-world GC latency*) mencapai 1.800 ms per siklus major, menyebabkan timeout pada downstream API gateway.
3. **Disk Trashing**: Sistem terus-menerus melakukan page swapping.

#### Solusi Arsitektural: Memory-Mapped Ring-Buffer Reader
Tim arsitek merekayasa ulang komponen ingestor dengan:
1. Mengganti string-parsing agregat dengan `mmap` native (menggunakan antarmuka kernel `mmap(2)` via interface C-extension atau block reading).
2. Menghindari alokasi baris menggunakan fixed-size pointer scanning langsung pada memory-mapped page cache.
3. Mengaplikasikan `posix_fadvise(2)` dengan hint `POSIX_FADV_SEQUENTIAL` dan `POSIX_FADV_WILLNEED` untuk mengoptimalkan readahead kernel disk scheduler.

```ruby
# frozen_string_literal: true
# Abstraksi Engine Pemroses File Skala Enterprise
class EnterpriseLogScanner
  READ_AHEAD_SIZE = 128 * 1024 # 128 KB chunks

  def initialize(file_path)
    @file_path = file_path
    @fd = IO.sysopen(file_path, Fcntl::O_RDONLY)
    @io = IO.new(@fd, 'r')
    optimize_kernel_caching
  end

  def process_records
    buffer = String.new(capacity: READ_AHEAD_SIZE)
    residual = String.new(capacity: 4096)

    # Membaca per-blok tanpa mengalokasikan string array
    while @io.readpartial(READ_AHEAD_SIZE, buffer)
      combined = residual.empty? ? buffer : (residual + buffer)
      residual.clear

      last_newline_idx = combined.rindex("\n")

      if last_newline_idx.nil?
        residual.replace(combined)
        next
      end

      # Segmentasi data siap proses
      process_chunk(combined[0..last_newline_idx])

      # Simpan potongan sisa batas chunk untuk iterasi berikutnya
      if last_newline_idx + 1 < combined.bytesize
        residual.replace(combined[(last_newline_idx + 1)..-1])
      end
    end
  rescue EOFError
    process_chunk(residual) unless residual.empty?
  ensure
    cleanup
  end

  private

  def optimize_kernel_caching
    # 2 = POSIX_FADV_SEQUENTIAL pada Linux
    # Hint ke OS bahwa file akan dibaca berurutan dari awal ke akhir
    if File.constants.include?(:Constants) && File::Constants.constants.include?(:FADV_SEQUENTIAL)
      @io.advise(:sequential)
    end
  rescue StandardError => e
    warn "[WARN] Kernel advise tidak didukung: #{e.message}"
  end

  def process_chunk(chunk)
    # Logika ekstraksi bitwise / binary deserialization
    # Melakukan parse data in-place
  end

  def cleanup
    @io.close unless @io.closed?
  end
end
```

#### Hasil Benchmark Pasca-Implementasi:
- **Alokasi Heap (Puncak)**: Turun dari **7.4 GB** menjadi konstan di **~45 MB**.
- **GC Latency (p99)**: Turun dari **1.800 ms** menjadi **< 12 ms**.
- **Throughput**: Meningkat **410%** (dari 24.000 log/detik menjadi 122.400 log/detik per instance worker).

---

## 9. Trade-offs

| Parameter Arsitektur | Low-Level Manual I/O (`readpartial`, nonblock, syscalls) | High-Level I/O Abstraction (`File.read`, Buffered IO) |
| :--- | :--- | :--- |
| **Throughput** | **Sangat Tinggi**: Mampu saturasi bandwidth hardware (10Gbps+). | **Sedang**: Terhambat bottleneck alokasi Ruby VM object heap. |
| **Latency Consistency (p99)** | **Optimal**: Nyaris zero-GC overhead. Variansi response time sangat rendah. | **Buruk**: Latensi melonjak secara periodik ketika Major GC aktif. |
| **Memory Footprint** | **Datar / Terprediksi**: Ukuran memori ditentukan di awal (pre-allocated buffer pool). | **Volatil**: Berfluktuasi proporsional terhadap ukuran file/data stream. |
| **Complexity & Maintainability** | **Tinggi**: Developer harus mengelola fragmentasi buffer, partial write, dan error code OS manual. | **Rendah**: Kode deklaratif, sederhana, minim potensi bug *dangling socket*. |
| **Portabilitas OS** | **Tergantung Kernel**: Flag seperti `TCP_CORK` atau `sendfile` bervariasi antara Linux, FreeBSD, dan macOS. | **Sangat Tinggi**: Terabstraksi secara seragam di seluruh OS yang didukung Ruby. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 File Descriptor Leaks (FD Starvation)
- **Gejala**: Aplikasi crash setelah berjalan beberapa jam/hari dengan pesan `Errno::EMFILE: Too many open files`.
- **Akar Masalah**: Membuka soket atau file tanpa blok `begin ... ensure ... close` yang ketat, atau exception terjadi sebelum objek ditutup, sementara GC belum berjalan untuk memicu finalizer C.
- **Pencegahan**:
  ```ruby
  # SALAH: Objek IO bergantung pada siklus GC non-deterministik
  def write_log(payload)
    file = File.open('/var/log/audit.log', 'a')
    file.write(payload)
    # Tidak di-close secara eksplisit jika terjadi throw/return lebih awal
  end

  # BENAR: Deterministic block auto-close pattern
  def write_log(payload)
    File.open('/var/log/audit.log', 'a') do |file|
      file.write(payload)
    end # Otomatis close di level kernel meskipun terjadi exception
  end
  ```

### 10.2 CPU 100% Spin pada Non-blocking Socket Loop
- **Gejala**: Worker memanfaatkan 100% core CPU padahal tidak ada trafik signifikan.
- **Akar Masalah**: Polling loop `read_nonblock(exception: false)` langsung melakukan looping ulang tanpa menunggu kesiapan I/O saat menerima status `:wait_readable`.
- **Solusi**: Integrasikan I/O multiplexer seperti `IO.select` dengan timeout terukur atau event loop berbasis Fiber.

### 10.3 Buffer Mutation Corruption
- **Gejala**: Data yang dikirim ke socket tujuan rusak, berisi sisa payload dari transmisi sebelumnya.
- **Akar Masalah**: Menggunakan `buffer` yang sama tanpa memperhatikan nilai balik panjang byte aktual yang dibaca oleh `readpartial` atau `read_nonblock`.
- **Solusi**: Selalu lakukan slice index atau gunakan referensi byte yang dikembalikan:
  ```ruby
  bytes_read = io.readpartial(CHUNK_SIZE, buffer)
  # JANGAN asumsikan buffer.bytesize == CHUNK_SIZE!
  # Gunakan data persis sepanjang bytes_read
  process(buffer) # Ruby otomatis mengecilkan buffer.bytesize sesuai bytes_read
  ```

### 10.4 Matrix Panduan Troubleshooting

| Gejala Sistem | Perintah Investigasi Terminal | Aksi Remediasi |
| :--- | :--- | :--- |
| `Errno::EMFILE` | `lsof -p <PID> \| wc -l` | Periksa koneksi tak tertutup; naikkan limit via `ulimit -n <limit>`. |
| High CPU + I/O Wait | `pidstat -d -p <PID> 1` | Pastikan buffer read rate tidak terlalu kecil (misal: 1 byte reads). |
| Excessive Memory Swapping | `strace -c -p <PID>` | Cek apakah alokasi string heap memicu syscall `brk`/`mmap` berlebihan. |
| Socket Half-Open Hanging | `ss -t -a -p \| grep <PID>` | Pasang `SO_KEEPALIVE` atau dead-man-timeout di layer I/O loop. |

---

## 11. Best Practices (Production Checklist)

- [ ] **Alokasikan Ulang Buffer (Buffer Reuse)**: Gunakan parameter `outbuf` pada `IO#readpartial` atau `IO#read_nonblock` untuk stream berkapasitas besar.
- [ ] **Deterministic Resource Release**: Tutup seluruh socket/file dalam blok `ensure` atau gunakan block-style context manager (`File.open(...) do |f|`).
- [ ] **Hindari Exception di Hot-Path**: Gunakan parameter `exception: false` pada `read_nonblock` dan `write_nonblock`.
- [ ] **Konfigurasi Kernel Limits**: Pastikan file descriptor limit pada host produksi diatur optimal di `/etc/security/limits.conf` (`nofile >= 65536`).
- [ ] **Atur Socket Buffers**: Tentukan ukuran send/receive buffer (`SO_SNDBUF`, `SO_RCVBUF`) secara manual untuk koneksi high-throughput cross-datacenter (BDP tuning).
- [ ] **Gunakan Socket Keepalive**: Konfigurasi `Socket::SO_KEEPALIVE` untuk mendeteksi *dead peers* secara transparan pada pool koneksi jangka panjang.
- [ ] **Zero-Copy untuk Transfer Statis**: Gunakan `IO.copy_stream(src, dst)` saat memindahkan file ke socket tanpa manipulasi isi data di user-space.
- [ ] **Atomic File Writes**: Jangan menulis langsung ke file target di produksi; tulis ke file temporer pada filesystem yang sama dan lakukan `File.rename` (`rename(2)` atomik).

---

## 12. Hands-on Practice

Buat dan eksekusi skrip praktikum berikut untuk mengamati perilaku buffer allocation dan streaming zero-copy secara langsung.

### Struktur Direktori:
```text
hands-on/m02/
├── 01_buffer_allocation_test.rb
├── 02_nonblocking_echo.rb
└── 03_zerocopy_benchmark.rb
```

### Langkah Praktikum 1: Monitoring Alokasi Buffer Heap
Simpan skrip berikut di `hands-on/m02/01_buffer_allocation_test.rb`:

```ruby
# frozen_string_literal: true
require 'objspace'

puts "=== LAB 1: Memverifikasi Alokasi Memori Ruby Heap ==="

# Buat dummy payload file 50MB
dummy_path = "/tmp/dummy_50mb.dat"
File.open(dummy_path, "wb") { |f| f.write("X" * (50 * 1024 * 1024)) }

# Metode A: Naive File.read
GC.start
mem_before = ObjectSpace.memsize_of_all
naive_data = File.read(dummy_path)
mem_after = ObjectSpace.memsize_of_all
puts "Naive File.read Delta Memori : #{((mem_after - mem_before) / 1024.0 / 1024.0).round(2)} MB"
naive_data = nil

# Metode B: Reusable Buffer Read
GC.start
mem_before = ObjectSpace.memsize_of_all
buf = String.new(capacity: 64 * 1024)
bytes_processed = 0

File.open(dummy_path, 'rb') do |io|
  while io.readpartial(64 * 1024, buf)
    bytes_processed += buf.bytesize
    # Buffer digunakan ulang, tidak ada alokasi baru
  end
end

mem_after = ObjectSpace.memsize_of_all
puts "Buffer Reuse Delta Memori   : #{((mem_after - mem_before) / 1024.0 / 1024.0).round(2)} MB"
puts "Total Bytes Diproses        : #{bytes_processed} bytes"

File.delete(dummy_path)
```

Jalankan:
```bash
ruby hands-on/m02/01_buffer_allocation_test.rb
```
*Perhatikan bahwa Delta Memori pada Metode B mendekati 0 MB di Ruby VM Heap.*

---

## 13. Exercise

### Level Easy
Modifikasi implementasi socket client agar menangani skenario non-blocking write. Buat fungsi `safe_nonblocking_write(socket, data)` yang menjamin seluruh data terkirim meskipun kernel socket buffer penuh (`:wait_writable`) tanpa crash.

### Level Medium
Bangun reverse-proxy TCP multiplexer satu-utas (*single-threaded*) sederhana menggunakan `IO.select`. Server harus menerima koneksi dari client port `8888` dan mem-forward seluruh lalu lintas bolak-balik ke upstream service port `9999` secara non-blocking tanpa thread alokasi baru.

### Level Hard
Implementasikan sebuah library mini storage engine biner berformat Append-Only Log (AOL) yang memiliki karakteristik:
1. Thread-safe writing menggunakan locking tingkat kernel (`flock`).
2. Pembacaan catatan telemetri menggunakan chunked buffer processing tanpa memicu pemanggilan GC saat membaca file 1 GB.
3. Memastikan integritas data melalui penulisan checksum CRC32 pada setiap frame byte yang dialirkan.

---

## 14. Challenge

### Studi Kasus Produksi: "The Thundering Herd & Backpressure Proxy"

**Deskripsi Masalah:**
Anda ditugaskan mendesain subsistem streaming biner berkecepatan tinggi yang menjembatani streaming output dari sensor IoT industri ke sebuah broker analitik.
Tantangan teknis:
1. **Slow Consumer Bottleneck**: Jika upstream broker mengalami degradasi performa I/O (jaringan lambat), buffer di memory Ruby tidak boleh membengkak (*unbounded memory growth*).
2. **Backpressure Propagation**: Saat buffer internal lokal mencapai limit 16 MB, server harus segera menangguhkan (`pause/stop reading`) socket dari sensor IoT di level TCP flow control (jangan membaca dari client socket agar kernel mengirim window advertisement size 0).
3. **No Garbage Overhead**: Pemrosesan harus mempertahankan konsumsi alokasi Ruby Heap tetap < 100 objek per 10.000 request.
4. **Resilience**: Harus mampu menangani kondisi koneksi putus mendadak (*broken pipe / ECONNRESET*) tanpa menghentikan streaming klien sensor lainnya.

**Instruksi Deliverable:**
Rancang arsitektur kelas berbasis Fiber Scheduler atau IO non-blocking loop murni di Ruby, sertakan simulasi skrip *fast producer* dan *slow consumer*, serta laporkan metrik footprint memori melalui visualisasi log `ObjectSpace`.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Pemahaman Konseptual (Basic)
1. Apa fungsi flag `exception: false` pada pemanggilan metode `IO#read_nonblock` di Ruby MRI?
2. Bagaimana representasi internal dari sebuah file descriptor pada struktur data C `rb_io_t`?
3. Mengapa pemanggilan `File.readlines` dianggap anti-pattern arsitektur pada sistem data throughput tinggi?
4. Apa perbedaan mekanisme OS antara `IO.copy_stream` dan perulangan `read`/`write` konvensional di Linux?
5. Mengapa blocking system call pada Ruby MRI tidak menyebabkan seluruh thread Ruby berhenti berjalan?

### Bagian B: Analisis Arsitektur (Intermediate)
1. Jelaskan bagaimana alur transisi status I/O ketika sebuah socket mengembalikan simbol `:wait_writable` pada saat penulisan data payload besar!
2. Mengapa exception `Errno::EPIPE` terjadi di tingkat socket dan bagaimana kernel memberitahukan hal ini kepada proses Ruby?
3. Bagaimana Ruby 3 Fiber Scheduler mengubah pola I/O blocking lama tanpa perlu memodifikasi sintaksis synchronous dari kode yang telah ditulis?
4. Mengapa penting menggunakan opsi socket `TCP_NODELAY` (algoritma Nagle) pada komunikasi microservices dengan payload kecil?
5. Mengapa penutupan resource IO di Ruby sebaiknya tidak dipasrahkan kepada `ObjectSpace.define_finalizer`?

### Bagian C: Skenario Kasus Produksi
1. **Skenario 1**: Sebuah background worker Ruby melaporkan error `Errno::EMFILE (Too many open files)` padahal trafik jaringan sedang normal. Saat dilakukan inspeksi `lsof`, terdapat ribuan socket dalam status `CLOSE_WAIT`. Apa yang salah pada implementasi Ruby I/O Anda?
2. **Skenario 2**: Sistem proxy Ruby Anda mengalami lonjakan memori resident (RSS) yang tidak pernah turun kembali ke OS setelah memindahkan file 5 GB, meskipun file tersebut telah berhasil ditutup. Analisis apa yang terjadi pada memory allocator (glibc malloc) dan struktur heap Ruby!
3. **Skenario 3**: Sebuah aplikasi streaming audio real-time berbasis Ruby mengalami *jitter* latensi audio setiap 30 detik sekali. Profiling menunjukkan CPU spike berkorelasi dengan pemanggilan `GC.start`. Bagaimana Anda mengubah strategi I/O buffer untuk menghilangkan jitter ini?

---

## 16. Summary

- Abstraksi I/O Ruby menyembunyikan kompleksitas interaksi C-level kernel, tetapi pada skala enterprise, pemahaman mendalam tentang `rb_io_t`, buffer boundaries, dan context-switch mutlak diperlukan.
- **Allocation-Free I/O** adalah kunci performa latensi deterministik. Memanfaatkan parameter `outbuf` pada operasi pembacaan mencegah thrashing memori dan memangkas waktu kerja Garbage Collector.
- Pemanfaatan fitur kernel seperti **Zero-Copy (`IO.copy_stream` / `sendfile`)** dan flag socket tingkat rendah (`TCP_CORK`, `O_NONBLOCK`) memungkinkan aplikasi berbasis Ruby bersaing dalam metrik throughput dengan bahasa sistem seperti Go atau Rust.
- Arsitektur I/O modern Ruby 3+ dengan antarmuka **Fiber Scheduler** menjembatani kesederhanaan kode sinkron dengan skalabilitas tinggi sistem operasi event-driven (`epoll`/`kqueue`).