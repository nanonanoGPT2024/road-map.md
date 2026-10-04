# SEKSI 01 — IDENTITAS MODUL

*   **Modul ID:** RUBY-SYS-0401
*   **Track:** Core & Systems Ruby Programming
*   **Kategori:** 02-Programming-Languages
*   **Judul Modul:** Bab 04 Module 01: Resource Management & Low-Level I/O
*   **Tingkat Kesulitan:** Advanced / Systems-Level
*   **Prasyarat:** Pemahaman mendalam tentang Object-Oriented Ruby, Blok/Proc/Lambda, penanganan Exception (`begin/rescue/ensure`), serta dasar-dasar sistem operasi UNIX/POSIX (File System, Proses, Syscall).
*   **Estimasi Durasi Belajar:** 6 - 8 Jam (Teori, Eksplorasi Kode C-Extension Ruby, Hands-on Lab)
*   **Stack & Tools:** 
    *   Ruby 3.2+ (CRuby / MRI)
    *   Linux OS (Ubuntu 22.04 LTS / Debian 12 / Arch Linux) atau macOS
    *   POSIX CLI Tools: `strace` (Linux) / `dtruss` (macOS), `lsof`, `procfs` (`/proc/$PID/fd`)

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, software engineer mampu:

1.  **Menganalisis (C4)** perbedaan fundamental antara *Buffered I/O* (userspace) dan *Unbuffered/Low-Level System Calls* pada CRuby (`read` vs `sysread`, `write` vs `syswrite`).
2.  **Mendiagnosis (C4)** risiko kebocoran *File Descriptor* (FD leak) yang diakibatkan oleh ketergantungan keliru pada Garbage Collector MRI, serta merancang arsitektur manajemen siklus hidup sumber daya yang deterministik.
3.  **Mengimplementasikan (C3)** operasi I/O asinkron dan non-blocking primitif (`read_nonblock`, `write_nonblock`) dengan penanganan exception level kernel (`IO::WaitReadable`, `IO::WaitWritable`).
4.  **Mengevaluasi (C5)** strategi konkurensi berkas menggunakan mekanisme *Advisory File Locking* (`flock`) dan *Atomic Operations* guna mencegah *race condition* antar-proses OS.
5.  **Mengoptimasi (C5)** *throughput* transfer data dengan memanfaatkan teknik *Buffer Reuse* (zero-allocation loops) dan *Kernel-level Zero-Copy* via `IO.copy_stream`.
6.  **Membangun (C6)** subsistem *Write-Ahead Logging* (WAL) atau *Persistence Engine* berkinerja tinggi yang aman terhadap *kernel panic* / *power loss* dengan primitif sinkronisasi disk (`fsync`, `fdatasync`).

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Mental Model 1: File Descriptor Adalah Indeks Array Kernel
Di level sistem operasi (POSIX), *file* bukan sekadar berkas di disk, melainkan abstraksi stream *byte*. Ketika proses Ruby membuka file, socket, atau pipe, kernel mengalokasikan entri di *file table* dan mengembalikan integer non-negatif bernama **File Descriptor (FD)**. Ruby `IO` object hanyalah representasi *userspace wrapper* di atas integer FD tersebut. Menutup objek Ruby tidak serta-merta menutup FD di kernel secara deterministik kecuali diperintahkan secara eksplisit.

```
Ruby VM Heap               Linux Kernel Space
┌───────────────┐          ┌───────────────────────────────────┐
│ File Object   │          │ Process File Descriptor Table     │
│  (Ruby alloc) │          │ Index 0 -> stdin                  │
│   ├── @path   │          │ Index 1 -> stdout                 │
│   └── @fileno ┼─────────►│ Index 2 -> stderr                 │
└───────────────┘          │ Index 3 -> /var/log/app.log (FD)  │
                           └─────────────────┬─────────────────┘
                                             │
                                             ▼
                                     ┌───────────────┐
                                     │ Kernel VFS &  │
                                     │ Page Cache    │
                                     └───────────────┘
```

### Mental Model 2: The Two-Tier Buffer (Userspace vs Kernelspace)
Operasi baca-tulis standar di Ruby memiliki dua lapisan penampung:
1.  **Ruby Userspace Buffer (`stdio` / CRuby Internal Buffer):** Mengumpulkan fragmen byte kecil di memori Ruby VM untuk meminimalkan *context-switch* ke kernel.
2.  **Kernel Page Cache:** Memori RAM kernel yang menampung *dirty pages* sebelum benar-benar di-*flush* oleh subsistem I/O ke media penyimpanan fisik.

Memanggil `sysread` atau `syswrite` berarti **memotong jalur Userspace Buffer**, berbicara langsung dengan Kernel Interface melalui System Call (`read(2)` / `write(2)`).

```
[ Ruby Code ]
      │
      ├───────────────────────┐
      │ (High-Level IO#write) │ (Low-Level IO#syswrite)
      ▼                       │
[ CRuby Internal Buffer ]     │
      │ (Flush saat penuh/LF) │
      ▼                       ▼
════════════════════════════════════════════════════ User / Kernel Boundary
      │ (write(2) Syscall)    │ (write(2) Syscall)
      └───────────────────────►
                              ▼
                  [ OS Kernel Page Cache ]
                              │ (pdflush / dirty writeback / fsync)
                              ▼
                  [ Physical Hardware (NVMe/SSD) ]
```

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Diagram 1: Alur Sinkronisasi Data dan Flush Mechanism

Berikut adalah visualisasi bagaimana data bergerak dari level aplikasi Ruby hingga mencapai lapisan magnetik/semikonduktor storage fisik:

```
+-------------------------------------------------------------------------+
|                              RUBY USERSPACE                             |
|                                                                         |
|  data = "PAYLOAD_DATA"                                                  |
|  io.write(data) ──────> [ Ruby IO Write Buffer (rb_io_t) ]              |
|                                     │                                   |
|                                 io.flush                                |
+─────────────────────────────────────┼───────────────────────────────────+
                                      │ syscall: write(2)
                                      ▼
+-------------------------------------------------------------------------+
|                            LINUX KERNEL SPACE                           |
|                                                                         |
|                        [ Page Cache / Dirty Pages ]                     |
|                                     │                                   |
|                              io.fdatasync /                             |
|                                 io.fsync                                |
|                                     │ syscall: fsync(2)                 |
+─────────────────────────────────────┼───────────────────────────────────+
                                      │ Storage Controller Command
                                      ▼
+-------------------------------------------------------------------------+
|                             HARDWARE LAYER                              |
|                                                                         |
|                       [ On-disk Drive Cache / DRAM ]                    |
|                                     │                                   |
|                          Storage Controller Flush                       |
|                                     ▼                                   |
|                     [ Non-Volatile Flash Media (NAND) ]                 |
+-------------------------------------------------------------------------+
```

### Diagram 2: Finite State Machine Transisi Status Non-Blocking I/O

Saat mengoperasikan I/O dalam mode non-blocking (`sysread` / `read_nonblock`), alur eksekusi aplikasi dikontrol oleh kesiapan resource kernel:

```
                  +-----------------------------------+
                  |           MULAI BACA              |
                  |     io.read_nonblock(maxlen)      |
                  +-----------------+-----------------+
                                    |
                                    v
                     /-----------------------------\
                    /   Data Tersedia di Socket/    \
                   <        Kernel Pipe Buffer?      >
                    \                               /
                     \-----------------------------/
                               /           \
                       TIDAK  /             \  YA
                             v               v
           +-------------------------+   +-------------------------+
           | Raise Exception:        |   | Kembalikan Data Buffer  |
           | IO::WaitReadable        |   | (Return String)         |
           | (Kernel errno: EAGAIN)  |   +-------------------------+
           +------------+------------+
                        |
                        v
           +-------------------------+
           | Suspensi Thread / Loop: |
           | IO.select([io],nil,nil) |
           +------------+------------+
                        |
                        v
           +-------------------------+
           | Kernel Memberi Notifikasi|
           | Socket Siap Dibaca      |
           +-------------------------+
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Struktur Internal CRuby: `rb_io_t`
Di dalam source code CRuby (`io.c`), objek `IO` dipetakan ke struktur C bernama `rb_io_t`. Struktur ini mengelola status FD dan buffer mandiri di level proses:

```c
// Representasi konseptual dari rb_io_t di MRI C-Core
typedef struct rb_io_t {
    int fd;                     // OS File Descriptor primitif
    FILE *stdio_file;           // Handle stdio opsional (jika di-wrap)
    int mode;                   // Mode bitmask (Read, Write, Append, Nonblock)
    rb_io_buffer_t read_buffered;  // Userspace buffer untuk IO#read / IO#gets
    rb_io_buffer_t write_buffered; // Userspace buffer untuk IO#write / IO#puts
    rb_pid_t pid;               // PID proses jika dibuat via IO.popen
    int lineno;                 // Tracking nomor baris
    // ... metadata internal lainnya
} rb_io_t;
```

### 2. Kegagalan Garbage Collector Mengelola File Descriptor
Garbage Collector (GC) Ruby hanya memantau alokasi memori heap Ruby VM. FD dialokasikan oleh kernel di luar batas heap Ruby VM:
*   GC terpicu oleh saturasi alokasi heap object (`ruby_malloc`), **bukan** oleh menipisnya sisa limit FD sistem (`ulimit -n`).
*   Jika Anda membuka ribuan instance `File.new` dalam perulangan cepat tanpa menutupnya, sistem operasi akan melempar error `Errno::EMFILE` (Too many open files) jauh sebelum Ruby VM memutuskan untuk menjalankan GC sweep.
*   Finalizer pada object `IO` (yang memanggil `close(2)`) bersifat **non-deterministik**. Jangan pernah bergantung pada GC untuk membebaskan native OS resources.

### 3. File Descriptor Flags & Inheritance (`FD_CLOEXEC`)
Secara default sejak Ruby 2.0, semua FD yang dibuka oleh Ruby secara internal diberi atribut bit `FD_CLOEXEC` (Close-on-Exec) via `fcntl(2)`. Ini mencegah terjadinya *FD leak* ke child process yang di-spawn melalui `fork(2)` / `execve(2)`.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. High-Level I/O vs Low-Level I/O (Syscalls)
CRuby membagi layer I/O menjadi dua:

| Karakteristik | High-Level (`IO#read`, `IO#write`) | Low-Level (`IO#sysread`, `IO#syswrite`) |
| :--- | :--- | :--- |
| **Buffering** | Menggunakan userspace buffer (default 8KB - 16KB). | Zero userspace buffering. Langsung ke kernel. |
| **System Calls** | Diamortisasi (banyak operasi write kecil = 1 syscall). | Rasio 1:1 (Satu kali panggil = Satu syscall `read(2)` / `write(2)`). |
| **Overhead Context-Switch** | Sangat Rendah untuk operasi berulang. | Tinggi jika digunakan untuk menulis/membaca data kecil. |
| **Partial Execution** | Ruby mengulang internal read/write hingga buffer tuntas. | Dapat terjadi *partial write* (mengembalikan jumlah byte nyata yang masuk). |
| **Mixing Hazard** | **BAHAYA:** Menggabungkan `read` dan `sysread` pada stream yang sama akan merusak pointer pembacaan data. |

### 2. Durabilitas Penyimpanan Data: `fsync` vs `fdatasync`
Ketika `IO#syswrite` atau `IO#write` selesai, kernel hanya menjamin byte telah disalin ke *OS Page Cache*. Jika server mati mendadak (kernel panic/power cut), data di RAM tersebut hilang.
*   `IO#fsync`: Memaksa kernel menulis seluruh data dirty pages **dan** metadata berkas (waktu modifikasi, ukuran, permission) ke media fisik. Memerlukan setidaknya 2 I/O operations pada storage controller.
*   `IO#fdatasync`: Hanya menulis data *payload* berkas. Metadata hanya ditulis jika esensial untuk menemukan berkas tersebut (misalnya penambahan ukuran file). Ini menghemat rotasi head HDD atau operasi flash write amplifier pada SSD.

### 3. Non-Blocking I/O & Multiplexing
Operasi synchronous I/O akan memblokir thread eksekusi jika storage pipe, socket, atau character device belum siap menerima/mengirim data. 
*   Dengan mode non-blocking, jika buffer OS kosong saat dipanggil `read_nonblock`, OS tidak menidurkan proses, melainkan mengembalikan error code `EAGAIN` / `EWOULDBLOCK`.
*   Ruby membungkus ini dalam exception `IO::WaitReadable` atau `IO::WaitWritable`.
*   Pemanggilan `IO.select([readable_io], [writable_io], nil, timeout)` memanfaatkan kernel syscall multiplexer (`select(2)`, `poll(2)`, atau di-wrap oleh reactor seperti `epoll`/`kqueue`) untuk menidurkan thread Ruby hingga kernel menandakan descriptor siap.

### 4. File Locking Semantics: Advisory vs Mandatory
Ruby mengimplementasikan *Advisory Locking* melalui POSIX syscall `flock(2)` via `File#flock`:
*   **Advisory:** Kernel tidak membatasi proses nakal membaca/menulis berkas jika proses tersebut tidak mengecek lock. Semua proses yang berpartisipasi harus sepakat secara sukarela mengeksekusi `flock` sebelum memanipulasi berkas.
*   Konstanta Operasi:
    *   `File::LOCK_EX` (Exclusive Lock): Akses tulis eksklusif (hanya satu proses).
    *   `File::LOCK_SH` (Shared Lock): Akses baca bersama (banyak pembaca paralel, nol penulis).
    *   `File::LOCK_UN` (Unlock): Membebaskan lock.
    *   `File::LOCK_NB` (Non-blocking): Kombinasi bitwise (`File::LOCK_EX | File::LOCK_NB`) agar tidak blocking jika lock sedang dipegang proses lain.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi fundamental penanganan File Descriptor tingkat rendah secara aman, mendemonstrasikan unbuffered read/write, zero-allocation buffers, flag level OS, dan proteksi concurrency:

```ruby
# frozen_string_literal: true

require 'fcntl'

module LowLevelIOFundamentals
  TARGET_FILE = "low_level_demo.bin"

  def self.run_demo
    # 1. Buka Low-Level File Descriptor via POSIX sysopen
    # Menghindari abstraksi tinggi, flags langsung ke Kernel
    flags = File::Constants::O_RDWR | 
            File::Constants::O_CREAT | 
            File::Constants::O_TRUNC
    mode  = 0640 # rw-r-----
    
    raw_fd = IO.sysopen(TARGET_FILE, flags, mode)
    # Membungkus File Descriptor integer ke Ruby IO instance
    io = IO.new(raw_fd, flags)

    puts "[+] File Descriptor dibuka: #{io.fileno}"

    begin
      # 2. Advisory Locking: Mengunci file secara eksklusif dan non-blocking
      puts "[+] Meminta Exclusive Lock..."
      lock_status = io.flock(File::LOCK_EX | File::LOCK_NB)
      if lock_status == false
        raise "Gagal mendapatkan lock: File sedang digunakan oleh proses lain."
      end
      puts "[+] Lock didapatkan."

      # 3. Unbuffered Low-Level Write (Bypass Ruby Userspace Buffer)
      payload = "INITIAL_RAW_DATA_PAYLOAD_CHUNK\n"
      bytes_written = 0
      
      # Handle partial writes secara manual
      while bytes_written < payload.bytesize
        chunk = payload.byteslice(bytes_written..-1)
        written = io.syswrite(chunk)
        bytes_written += written
      end
      puts "[+] Sukses menulis #{bytes_written} bytes melalui syswrite."

      # 4. Flush dirty pages dari OS Page Cache ke disk fisik (Durability Guarantee)
      io.fdatasync
      puts "[+] fdatasync berhasil: Data mendarat di storage controller."

      # 5. Low-Level Seek (Ubah cursor langsung di Kernel VFS)
      io.sysseek(0, IO::SEEK_SET)

      # 6. Low-Level Read dengan Non-Allocating Memory Buffer
      # Re-use string object untuk mencegah garbage collection pressure
      read_buffer = String.new(capacity: 64)
      bytes_to_read = 15

      io.sysread(bytes_to_read, read_buffer)
      puts "[+] Buffer hasil sysread: #{read_buffer.inspect}"

      # Peringatan: Membaca sisa berkas menggunakan high-level IO#gets 
      # setelah sysread berisiko merusak pointer bila tidak di-handle hati-hati!
      rest = io.read # High-level buffer sekarang disinkronisasi ulang
      puts "[+] Sisa data via high-level read: #{rest.inspect}"

    ensure
      # 7. Pembersihan Deterministik Sumber Daya
      if io && !io.closed?
        puts "[+] Membebaskan lock dan menutup file descriptor..."
        io.flock(File::LOCK_UN) rescue nil
        io.close # Otomatis mengeksekusi close(2) pada kernel
      end
      
      # Bersihkan artefak disk
      File.unlink(TARGET_FILE) if File.exist?(TARGET_FILE)
    end
  end
end

LowLevelIOFundamentals.run_demo if __FILE__ == $PROGRAM_NAME
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut bedah teknis dari kode di **SEKSI 07**:

*   **Baris 11-16 (`IO.sysopen`)**: Memanggil langsung syscall `open(2)`. Flags bitwise `O_RDWR | O_CREAT | O_TRUNC` menginstruksikan kernel: buka mode baca-tulis, buat file jika belum ada, dan kosongkan ukuran file menjadi 0 bytes. `0640` mengikat permission POSIX saat pembuatan berkas.
*   **Baris 17 (`IO.new(raw_fd, flags)`)**: Mengikat primitif FD kernel (integer) ke dalam struktur Ruby VM `rb_io_t`. Ruby tidak membuka file baru, melainkan mengadopsi FD yang sudah terbuka.
*   **Baris 19 (`io.fileno`)**: Mengambil integer native file descriptor (misal: 3, 4, 11). Menunjukkan referensi slot pada proses table kernel.
*   **Baris 24 (`io.flock(File::LOCK_EX | File::LOCK_NB)`)**: Menjalankan syscall `flock(2)`. Bitwise `LOCK_NB` memastikan jika proses lain sedang mengunci berkas, Ruby tidak terhenti (*deadlock/block*), melainkan segera melempar nilai false atau error `Errno::EWOULDBLOCK`.
*   **Baris 33-37 (`while bytes_written < payload.bytesize`)**: Kontrak sistem operasi pada `write(2)` tidak menjamin seluruh byte terkirim dalam satu pemanggilan (terutama pada pipes/sockets/slow storage). Pola loop `syswrite` wajib menangani *partial write* secara manual.
*   **Baris 42 (`io.fdatasync`)**: Mengirim syscall `fdatasync(2)`. Berbeda dari `IO#flush` yang hanya memindahkan data dari buffer Ruby VM ke Kernel RAM, `fdatasync` menahan eksekusi proses hingga physical drive controller mengonfirmasi bahwa data payload telah diamankan ke flash storage.
*   **Baris 46 (`io.sysseek(0, IO::SEEK_SET)`)**: Mengirim syscall `lseek(2)`. Menggeser pointer pembacaan kernel kembali ke byte indeks 0 tanpa memengaruhi buffer userspace yang sedang tersimpan.
*   **Baris 50-52 (`io.sysread(bytes_to_read, read_buffer)`)**: Pola performa tinggi. Parameter kedua (`read_buffer`) menampung byte langsung ke pointer memori string yang telah dialokasikan sebelumnya. Mencegah alokasi memori Ruby String baru setiap kali I/O loop berjalan.
*   **Baris 61-63 (`ensure` block)**: Menggaransi integritas sistem operasi. Lock dilepas (`File::LOCK_UN`), kemudian `io.close` dipanggil. Metode `close` memutus kaitan native FD, mengembalikan integer FD tersebut ke OS pool agar tidak terjadi situasi *Descriptor Exhaustion*.

---

# SEKSI 09 — STUDI KASUS NYATA (Real-World Production Scenario)

### Kasus: High-Throughput Write-Ahead Logging (WAL) Engine
Pada platform database transaksional (seperti PostgreSQL/SQLite engine mini), sebuah subsistem harus mencatat seluruh mutasi status ke dalam format berkas Append-Only Log (*Write-Ahead Log*) sebelum perubahan diterapkan ke basis data utama.

**Tantangan Sistemik:**
1.  **Multiple Worker Processes:** Aplikasi di-deploy menggunakan webserver multi-proses (seperti Puma / Unicorn cluster). Banyak worker mencoba menulis log secara bersamaan ke shared file yang sama.
2.  **Crash Resilience:** Jika terjadi *power outage*, log tidak boleh corrupt atau mengalami *partial entry write*.
3.  **Tear-free / No Race Conditions:** Garis log dari Worker A tidak boleh bercampur di tengah-tengah garis log Worker B (*data interleaving*).
4.  **Resource Contention:** Penggunaan locks konvensional yang buruk memicu CPU spinning atau thread starvation.
5.  **Garbage Collection Impact:** Jutaan penulisan per menit tidak boleh memicu GC pauses panjang akibat alokasi objek buffer temporer.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi subsistem WAL Engine enterprise-grade yang mengombinasikan *Low-Level Unbuffered I/O*, *Atomic Lock-and-Append*, *Durability Guarantees*, dan *Zero-Allocation Buffer Pools*.

```ruby
# frozen_string_literal: true

require 'fcntl'
require 'zlib'

class ResilientWALEngine
  # Header: 4 bytes Magic Number, 4 bytes Length, 4 bytes CRC32
  HEADER_SIZE = 12
  MAGIC = 0x57414C31 # "WAL1"

  WALError = Class.new(StandardError)
  LockTimeoutError = Class.new(WALError)
  CorruptedEntryError = Class.new(WALError)

  def initialize(log_path)
    @log_path = log_path
    # Buka dengan flags tingkat rendah:
    # O_RDWR   : Baca dan tulis
    # O_CREAT  : Buat jika tidak ada
    # O_APPEND : Kernel level atomic pointer seek to the end on writes
    @flags = File::Constants::O_RDWR | 
             File::Constants::O_CREAT | 
             File::Constants::O_APPEND
             
    @fd = IO.sysopen(@log_path, @flags, 0600)
    @io = IO.new(@fd, @flags)
    
    # Pre-allocate buffer untuk serialisasi biner tanpa alokasi GC
    @header_scratch = String.new(capacity: HEADER_SIZE, encoding: Encoding::BINARY)
  end

  # Menulis entry log secara atomik dan persisten
  def append_entry(payload_str)
    raise ArgumentError, "Payload must be String" unless payload_str.is_a?(String)

    binary_data = payload_str.b
    payload_size = binary_data.bytesize
    checksum = Zlib.crc32(binary_data)

    # Susun header biner: Magic (uint32), Size (uint32), Checksum (uint32)
    # Network byte order (Big Endian)
    header = [MAGIC, payload_size, checksum].pack("NNN")

    acquire_lock do
      # Lakukan low-level atomic write
      # O_APPEND menjamin penulisan selalu terjadi di akhir berkas
      write_raw_chunk(header)
      write_raw_chunk(binary_data)

      # Pastikan data mencapai piringan penyimpanan
      @io.fdatasync
    end

    true
  end

  # Membaca seluruh entri log untuk proses crash recovery
  def recover_entries
    records = []
    
    # Buka FD terpisah untuk pembacaan agar pointer cursor terisolasi
    read_fd = IO.sysopen(@log_path, File::Constants::O_RDONLY, 0600)
    read_io = IO.new(read_fd, File::Constants::O_RDONLY)

    begin
      header_buf = String.new(capacity: HEADER_SIZE, encoding: Encoding::BINARY)
      
      loop do
        header_buf.clear
        
        # Baca Header
        begin
          read_exact(read_io, HEADER_SIZE, header_buf)
        rescue EOFError
          break # Mencapai akhir berkas secara bersih
        end

        magic, size, expected_checksum = header_buf.unpack("NNN")
        
        if magic != MAGIC
          raise CorruptedEntryError, "Invalid WAL magic byte signature: #{magic.to_s(16)}"
        end

        # Baca Payload berdasarkan panjang di header
        payload_buf = String.new(capacity: size, encoding: Encoding::BINARY)
        read_exact(read_io, size, payload_buf)

        # Verifikasi Integritas Data via Checksum
        calculated_checksum = Zlib.crc32(payload_buf)
        if calculated_checksum != expected_checksum
          raise CorruptedEntryError, "Integrity fault: CRC32 mismatch. Data corrupted on disk."
        end

        records << payload_buf.freeze
      end
    ensure
      read_io.close unless read_io.closed?
    end

    records
  end

  def close
    return if @io.closed?

    # Flush sisa dan tutup descriptor
    @io.fdatasync rescue nil
    @io.close
  end

  private

  # Mengunci berkas menggunakan flock dengan mekanisme retry limit
  def acquire_lock(timeout_seconds: 5.0)
    start_time = Process.clock_gettime(Process::CLOCK_MONOTONIC)

    loop do
      # Coba non-blocking exclusive lock
      if @io.flock(File::LOCK_EX | File::LOCK_NB)
        break
      end

      # Cek limit timeout
      elapsed = Process.clock_gettime(Process::CLOCK_MONOTONIC) - start_time
      if elapsed >= timeout_seconds
        raise LockTimeoutError, "Gagal mengunci WAL dalam #{timeout_seconds} detik."
      end

      # Yield CPU time sebelum retry (5 milliseconds)
      sleep 0.005
    end

    begin
      yield
    ensure
      # Selalu lepaskan lock dalam blok ensure
      @io.flock(File::LOCK_UN) rescue nil
    end
  end

  # Menangani low-level writes terhadap risiko partial write
  def write_raw_chunk(data_str)
    bytes_to_write = data_str.bytesize
    total_written = 0

    while total_written < bytes_to_write
      chunk = data_str.byteslice(total_written..-1)
      written = @io.syswrite(chunk)
      total_written += written
    end
  end

  # Membaca tepat N bytes tanpa alokasi String berulang
  def read_exact(io_handle, total_bytes, out_buffer)
    out_buffer.clear
    bytes_read = 0

    while bytes_read < total_bytes
      remaining = total_bytes - bytes_read
      chunk = io_handle.sysread(remaining)
      out_buffer << chunk
      bytes_read += chunk.bytesize
    end

    out_buffer
  end
end

# Demo Pengujian Reliabilitas WAL Engine
if __FILE__ == $PROGRAM_NAME
  log_file = "production_audit.wal"
  File.unlink(log_file) if File.exist?(log_file)

  wal = ResilientWALEngine.new(log_file)

  puts "[*] Menulis 1,000 Transaksi Audit ke WAL Engine..."
  t_start = Process.clock_gettime(Process::CLOCK_MONOTONIC)

  100.times do |i|
    wal.append_entry("TRANSACTION_ID=#{1000 + i};STATUS=COMMITTED;AMOUNT=#{rand(10..500) * 100}")
  end

  t_end = Process.clock_gettime(Process::CLOCK_MONOTONIC)
  puts format("[+] Selesai menulis 100 transaksi ter-sinkronisasi dalam %.4f detik", (t_end - t_start))

  # Verifikasi Integritas Data
  puts "[*] Memulai Crash Recovery & Validasi Checksum..."
  recovered = wal.recover_entries
  puts "[+] Sukses memulihkan #{recovered.size} transaksi tanpa inkonsistensi."
  puts "[+] Bukti Data Terakhir: #{recovered.last}"

  wal.close
  File.unlink(log_file) if File.exist?(log_file)
end
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Memilih pendekatan I/O yang tepat membutuhkan pemahaman komparatif antara fleksibilitas abstraksi dan determinisme performa:

```
    Abstraksi Tinggi                                               Abstraksi Rendah
    (Developer Experience)                                    (Performa Maksimal)
          │                                                            │
          ▼                                                            ▼
┌──────────────────┐         ┌───────────────────┐         ┌──────────────────────┐
│ File.open(block) │ <=====> │ IO#sysread/write  │ <=====> │ Kernel Direct Syscall│
│   (Buffered IO)  │         │  (Low-Level IO)   │         │ (IO.sysopen + flags) │
└──────────────────┘         └───────────────────┘         └──────────────────────┘
  - Auto-buffered              - Unbuffered                  - Bypass userspace
  - Slower on raw sys          - No GC heap churn            - Manual buffer pool
  - High risk of desync        - Explicit syscall            - Explicit fdatasync
```

| Matriks Kriteria | High-Level (`IO#read` / `IO#write`) | Low-Level (`IO#sysread` / `IO#syswrite`) | Zero-Copy (`IO.copy_stream`) |
| :--- | :--- | :--- | :--- |
| **Userspace Buffering** | Ya (Ruby VM Heap) | Tidak (Bypass langsung ke C/Kernel) | Tidak (Kernel-space buffer forwarding) |
| **GC Allocation Rate** | Tinggi (Membuat objek String baru tiap pemanggilan tanpa argumen buffer) | Sangat Rendah (Mendukung in-place buffer mutation) | Nol (Alokasi objek payload 0 di Ruby VM) |
| **Throughput (File to File)**| Sedang (~200 - 400 MB/s) | Tinggi (~500 - 800 MB/s) | Ekstrem (> 1.5 GB/s via `sendfile(2)`) |
| **Kompleksitas Kode** | Sangat Rendah (Simpel, Idiomatis) | Menengah (Harus tangani loop *partial writes*) | Rendah (Untuk operasi transfer langsung) |
| **Kesesuaian Penggunaan** | File teks parsing biasa, JSON files, template rendering. | WAL Engines, Socket Parsers, Protocols, Binary IPC. | File download streaming, file proxying, backup dump. |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Interleaving Buffering Trap
Jika Anda menggabungkan `IO#read` dan `IO#sysread` pada *instance* berkas yang sama:
```ruby
file = File.open("data.txt", "r")
first_char = file.read(1)      # CRuby membaca 8192 bytes ke Userspace Buffer!
second_char = file.sysread(1)  # KERNEL membaca byte indeks 8193! Byte 2..8192 terlompati!
```
*Akar Masalah:* `IO#read(1)` secara diam-diam menyedot ribuan byte ke dalam `rb_io_t->read_buffered`. Ketika `sysread` dipanggil, ia menanyakan kernel pointer yang posisinya sudah berada di byte 8192. Byte 2 hingga 8191 di userspace hilang dari aliran `sysread`.

### 2. Partial Writes pada Pipes dan Sockets
`IO#syswrite` tidak dijamin menulis seluruh string. Jika buffer socket kernel penuh, `syswrite` dapat mengembalikan angka lebih kecil dari panjang string yang diberikan:
```ruby
# SALAH: Asumsi seluruh byte ditulis
io.syswrite(huge_payload)

# BENAR: Penanganan partial write
written = 0
while written < huge_payload.bytesize
  written += io.syswrite(huge_payload.byteslice(written..-1))
end
```

### 3. File Descriptor Leak via Forks
Jika Anda membuka berkas sebelum melakukan `fork`, dan anak proses mewarisi FD tersebut tanpa sinkronisasi:
*   Keduanya berbagi OS cursor position yang sama.
*   Jika Worker A melakukan write, kursor Worker B bergeser tanpa disadari.
*   *Mitigasi:* Selalu buka File Descriptor **setelah** proses melakukan `fork`, atau terapkan flag `O_CLOEXEC` pada subprocess creation.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan Fatal 1: Mengabaikan Penutupan Handle dalam Block Form
```ruby
# BURUK: Bergantung pada Garbage Collector untuk menutup file
def read_config(path)
  file = File.open(path, "r")
  file.read
  # Lupa file.close! FD tetap menggantung di OS Table!
end

# BENAR: Gunakan Idiomatic Block Scope (Deterministik)
def read_config(path)
  File.open(path, "r") do |file|
    file.read
  end # Ruby VM mengeksekusi close(2) otomatis begitu blok selesai
end
```

### Kesalahan Fatal 2: Mengira `IO#flush` Menyimpan Data ke Storage Fisik
```ruby
# BURUK: Menganggap flush aman terhadap crash hardware
file.write(critical_payment_record)
file.flush # HANYA memindahkan data dari Ruby VM ke Kernel RAM! Server mati = Data lenyap!

# BENAR: Panggil fsync atau fdatasync
file.write(critical_payment_record)
file.flush
file.fdatasync # Data secara fisik dikonfirmasi mendarat pada disk
```

### Kesalahan Fatal 3: Deadlock pada Advisory Locking
Memanggil `flock` blocking tanpa batas waktu dapat membekukan aplikasi jika proses lain mati tanpa sempat melepaskan lock.
```ruby
# BURUK: Blocking lock tanpa proteksi timeout
file.flock(File::LOCK_EX) # Thread hang tanpa batas jika pemilik lock freeze

# BENAR: Gunakan File::LOCK_NB dengan loop timeout dan backoff
start = Process.clock_gettime(Process::CLOCK_MONOTONIC)
locked = false
while Process.clock_gettime(Process::CLOCK_MONOTONIC) - start < 3.0
  if file.flock(File::LOCK_EX | File::LOCK_NB)
    locked = true
    break
  end
  sleep 0.01
end
raise "Lock Timeout!" unless locked
```

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Strict Resource Cleanup Guards:** Selalu gunakan idiom `begin ... ensure file.close end` jika tidak memungkinkan memakai block syntax standar `File.open(...) do`.
2.  **Explicit Binary Encoding:** Ketika memanipulasi low-level I/O, selalu tandai buffer dengan `Encoding::BINARY` (ASCII-8BIT). Mencegah Ruby VM menghabiskan siklus CPU melakukan kalkulasi konversi UTF-8 character boundaries.
3.  **Terapkan Least-Privilege Flags:** Jangan gunakan `IO::RDWR` jika hanya memerlukan `IO::RDONLY`. Gunakan mask `0600` (User-only Read/Write) untuk berkas sensitif atau WAL logs.
4.  **Zero-Allocation Buffers untuk Hot Loops:** Alokasikan String buffer sekali di luar perulangan (`buf = String.new(capacity: 16384)`), lalu teruskan variabel tersebut ke `sysread(size, buf)`. Ini menekan GC Pause Time hingga 0% pada I/O loops intensif.
5.  **Gunakan `IO.copy_stream` untuk Transfer Berkas:** Jangan membaca file ke dalam memori aplikasi hanya untuk menuliskannya kembali ke file lain atau socket. `IO.copy_stream(src, dest)` mengeksekusi kernel-level optimizations (`sendfile(2)` atau `splice(2)` pada Linux).

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Benchmark: Manual Read-Write Loop vs Zero-Allocation vs `IO.copy_stream`

Berikut adalah kode pengujian untuk mengukur perbedaan latensi, alokasi memori, dan GC overhead antar pendekatan I/O:

```ruby
# frozen_string_literal: true

require 'benchmark/ips'
require 'tempfile'

source = Tempfile.new('benchmark_source')
source.write("A" * 1024 * 1024 * 10) # 10 MB Dummy Data
source.flush

dest_path = "benchmark_dest.bin"

Benchmark.ips do |x|
  x.config(time: 5, warmup: 2)

  # Skenario 1: Naive High-Level Chunked Read (Heap Heavy)
  x.report("High-Level IO#read (Allocating)") do
    src = File.open(source.path, "rb")
    dst = File.open(dest_path, "wb")
    while (chunk = src.read(16384))
      dst.write(chunk)
    end
    src.close; dst.close
  end

  # Skenario 2: Low-Level sysread dengan In-Place Mutation Buffer
  x.report("Low-Level sysread (Zero-Alloc)") do
    src = File.open(source.path, "rb")
    dst = File.open(dest_path, "wb")
    buffer = String.new(capacity: 16384, encoding: Encoding::BINARY)
    begin
      loop do
        src.sysread(16384, buffer)
        dst.syswrite(buffer)
      end
    rescue EOFError
      # End of file reached
    ensure
      src.close; dst.close
    end
  end

  # Skenario 3: Zero-Copy Kernel Offload
  x.report("IO.copy_stream (Kernel-Level Zero-Copy)") do
    src = File.open(source.path, "rb")
    dst = File.open(dest_path, "wb")
    IO.copy_stream(src, dst)
    src.close; dst.close
  end

  x.compare!
end

# Cleanup
File.unlink(dest_path) if File.exist?(dest_path)
source.close!
```

### Hasil Analisis Tipikal (Linux x86_64, NVMe):
1.  **`IO.copy_stream`** secara konsisten mendominasi: Menghilangkan peralihan *Kernel-Space -> User-Space -> Kernel-Space*. Memory cost di Ruby Heap adalah 0 Bytes.
2.  **`Low-Level sysread (Zero-Alloc)`**: Memberikan peningkatan kecepatan 30-45% dibanding High-Level Chunked Read standar, dengan zero object churn pada Garbage Collector.

---

# SEKSI 16 — KEAMANAN & HARDENING

### 1. Mencegah TOCTOU (Time-Of-Check to Time-Of-Use) Vulnerabilities
Hindari mengecek kondisi berkas menggunakan `File.exist?` sebelum membukanya:
```ruby
# SANGAT RENTAN: Attacker dapat menyisipkan Symlink di antara pemanggilan exist? dan open
if File.exist?(user_path)
  # Jendela waktu bagi symlink race attack
  File.open(user_path, "w") { |f| f.write(data) }
end

# AMAN (Hardened): Buka atomik menggunakan O_CREAT | O_EXCL
begin
  flags = File::Constants::O_WRONLY | 
          File::Constants::O_CREAT | 
          File::Constants::O_EXCL |
          File::Constants::O_NOFOLLOW # Gagalkan jika file berupa Symlink!
  fd = IO.sysopen(user_path, flags, 0600)
  File.open(fd, "w") do |f|
    f.write(data)
  end
rescue Errno::EEXIST
  # File sudah ada, batalkan aksi eksploitasi
  raise "Security Alert: Race condition dideteksi atau file sudah ada!"
end
```

### 2. POSIX File Permission Masking (Umask Hardening)
Saat membuat file yang memuat data rahasia (kunci token, data user), jangan bergantung pada default umask sistem:
```ruby
# Selalu set umask eksplisit pada proses sebelum membuat berkas sensitif
old_umask = File.umask(0077) # Hanya pemilik yang punya akses rwx------
begin
  File.open("secret.key", "w", 0600) { |f| f.write(master_key) }
ensure
  File.umask(old_umask) # Pulihkan umask sistem
end
```

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Untuk melacak kebocoran File Descriptor atau deadlock lock I/O di production environment, gunakan instrumentasi internal dan inspeksi kernel berikut:

### 1. Inspeksi File Descriptor Runtime di Ruby
```ruby
module FDIssueTracker
  # Mendapatkan list seluruh FD yang terbuka di proses saat ini (Linux Only)
  def self.open_fds
    Dir.glob("/proc/#{Process.pid}/fd/*").map do |fd_path|
      target = File.readlink(fd_path) rescue "Unknown"
      [File.basename(fd_path).to_i, target]
    end.to_h
  end

  def self.print_fd_audit
    fds = open_fds
    puts "[FD AUDIT] Total Open FDs: #{fds.size}"
    fds.each do |fd_num, target|
      puts "  -> FD #{fd_num} => #{target}"
    end
  end
end
```

### 2. CLI Debugging Tools
*   **Mendeteksi Leaks via `lsof`:**
    ```bash
    # Lacak file yang dibuka oleh proses Ruby tertentu
    lsof -p <PID_RUBY>
    # Hitung jumlah open descriptor
    lsof -p <PID_RUBY> | wc -l
    ```
*   **Tracing System Calls via `strace` (Linux):**
    ```bash
    # Monitor eksekusi read/write/fsync/close secara real-time
    strace -e trace=openat,read,write,close,fsync,fdatasync,flock -p <PID_RUBY>
    ```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

| Operasi | High-Level Ruby API | Low-Level POSIX Ruby API | Syscall Terkait | Keterangan Perilaku |
| :--- | :--- | :--- | :--- | :--- |
| **Open** | `File.open(path)` | `IO.sysopen(path, flags, mode)` | `open(2)` / `openat(2)` | Mengembalikan File Descriptor integer mentah. |
| **Close** | `io.close` | `io.close` | `close(2)` | Melepas entri pada OS Descriptor Table. |
| **Read** | `io.read(len)` | `io.sysread(len[, buf])` | `read(2)` | `sysread` melewati Ruby buffer; optimal pakai buffer target. |
| **Write**| `io.write(data)`| `io.syswrite(data)` | `write(2)` | `syswrite` dapat menghasilkan *partial writes*. |
| **Seek** | `io.seek(offset)`| `io.sysseek(offset, whence)` | `lseek(2)` | Menggeser pointer pembacaan kernel secara langsung. |
| **Flush**| `io.flush` | *N/A* | None | Hanya memindahkan buffer Userspace Ruby ke Kernel RAM. |
| **Sync** | *N/A* | `io.fsync` / `io.fdatasync` | `fsync(2)` / `fdatasync(2)`| Memaksa persistence controller menulis ke flash storage fisik. |
| **Lock** | `file.flock(flags)` | `file.flock(flags)` | `flock(2)` | Advisory locking: `LOCK_EX`, `LOCK_SH`, `LOCK_NB`, `LOCK_UN`. |

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

Pilihlah jawaban yang paling tepat serta analisis rasionalnya:

### Soal Tingkat Basic (1 - 5)

**1. Apa perbedaan mendasar antara memanggil `io.flush` dengan memanggil `io.fsync`?**
*   A. `flush` mematikan child process, `fsync` menyinkronkan thread Ruby.
*   B. `flush` mengosongkan userspace buffer Ruby ke OS kernel page cache, sedangkan `fsync` memaksa kernel memindahkan data dirty pages ke media penyimpanan fisik.
*   C. `flush` hanya berfungsi untuk console stdout, sedangkan `fsync` hanya untuk socket.
*   D. Keduanya identik, `flush` adalah alias sintaktis dari `fsync`.
*   *Jawaban Rasional:* **B**. `flush` hanya mengosongkan internal Ruby `rb_io_t` buffer menuju kernel space. Tanpa `fsync`, data masih rentan hilang jika operating system mengalami crash mendadak saat data masih di RAM kernel cache.

**2. Mengapa bergantung pada Garbage Collection untuk menutup objek `File` atau `IO` dianggap sebagai anti-pattern berbahaya pada Ruby?**
*   A. Karena GC Ruby tidak memiliki method `close`.
*   B. Karena GC hanya terpicu oleh tekanan konsumsi heap memori Ruby, bukan batas limit file descriptor OS (`ulimit -n`), sehingga aplikasi dapat kehabisan FD sebelum GC berjalan.
*   C. Karena memanggil `close` dari finalizer akan mematikan proses utama Ruby.
*   D. Karena GC Ruby berjalan secara synchronous dan memblokir I/O execution.
*   *Jawaban Rasional:* **B**. Kernel membatasi jumlah open file descriptor per proses. Garbage collector Ruby hanya memantau alokasi objek Ruby di heap. Alokasi FD yang cepat tanpa penutupan eksplisit akan memicu `Errno::EMFILE`.

**3. Manakah flag mode yang harus digabungkan jika Anda ingin membuat file baru, membuka akses baca-tulis, dan gagal jika file tersebut ternyata sudah ada (untuk mencegah race condition)?**
*   A. `File::Constants::O_RDWR | File::Constants::O_CREAT | File::Constants::O_EXCL`
*   B. `File::Constants::O_RDWR | File::Constants::O_TRUNC`
*   C. `File::Constants::O_APPEND | File::Constants::O_CREAT`
*   D. `File::Constants::O_WRONLY | File::Constants::O_BINARY`
*   *Jawaban Rasional:* **A**. Kombinasi `O_CREAT | O_EXCL` adalah standar POSIX untuk pembukaan file secara eksklusif-atomik; kernel menjamin operasi gagal melempar exception `Errno::EEXIST` jika file sudah ada.

**4. Apa yang dimaksud dengan sifat "Advisory" pada metode `File#flock` di sistem POSIX?**
*   A. Kernel secara ketat menolak operasi `read` atau `write` dari proses manapun jika lock sedang aktif.
*   B. Lock hanya berlaku untuk thread di dalam satu proses Ruby yang sama.
*   C. Kernel tidak membatasi proses lain mengakses berkas secara fisik kecuali proses tersebut juga secara sukarela mengecek dan meminta lock via `flock`.
*   D. Lock otomatis terhapus setelah 30 detik.
*   *Jawaban Rasional:* **C**. Advisory locking bergantung pada kepatuhan kooperatif dari semua proses yang memanipulasi berkas untuk memanggil `flock` sebelum operasi I/O.

**5. Mengapa teknik passing buffer `io.sysread(1024, buffer)` lebih diutamakan dalam loop performa tinggi dibandingkan `buffer = io.sysread(1024)`?**
*   A. Karena syntax tersebut otomatis meng-enkripsi buffer.
*   B. Mengurangi beban alokasi memori GC (Zero Garbage Collection Pressure) dengan memutasi memori string yang telah dialokasikan sebelumnya.
*   C. Mempercepat koneksi internet pada socket.
*   D. Mencegah kernel mengalami segment fault.
*   *Jawaban Rasional:* **B**. Melewatkan buffer yang sudah ada (`in-place buffer mutation`) menghindari pembuatan ribuan objek `String` baru per detik di heap Ruby, menekan terjadinya siklus *Major GC Pause*.

---

### Soal Tingkat Intermediate (6 - 10)

**6. Apa dampak buruk mencampur penggunaan `IO#read` dan `IO#sysread` pada stream IO instance yang sama?**
*   A. Aplikasi langsung mengalami `Segfault (Signal 11)`.
*   B. Desinkronisasi data kursor pembacaan; `IO#read` membaca sekumpulan blok data ke dalam userspace buffer, menyebabkan pemanggilan `IO#sysread` berikutnya melompati byte data tersebut di tingkat kernel.
*   C. File otomatis terhapus dari hard disk.
*   D. Tidak berdampak apapun, Ruby secara otomatis mengosongkan internal buffer sebelum `sysread` dipanggil.
*   *Jawaban Rasional:* **B**. `IO#read` bersifat buffered (membaca melebihi batas yang diminta ke userspace buffer). `IO#sysread` bypass userspace buffer dan memajukan cursor kernel, sehingga data yang sudah terlanjur tersedot ke buffer userspace `IO#read` akan terlewati.

**7. Ketika mengeksekusi `io.syswrite(payload)`, apa arti dari nilai kembalian bilangan bulat (integer) yang dihasilkan?**
*   A. Kode status error POSIX (0 menandakan sukses).
*   B. Jumlah byte riil yang berhasil disalin ke kernel buffer pada pemanggilan tersebut (bisa terjadi partial write).
*   C. Sisa ruang kosong yang tersedia pada disk.
*   D. Nomor File Descriptor dari target file.
*   *Jawaban Rasional:* **B**. `syswrite` memetakan langsung syscall `write(2)` yang mengembalikan jumlah byte yang nyata disalin. Angka ini bisa lebih kecil dari ukuran payload asli (*partial write*), mengharuskan program menangani sisa byte melalui loop.

**8. Mengapa `IO.copy_stream` jauh lebih hemat sumber daya CPU dan RAM dibandingkan manual buffer copy loop untuk transfer file ukuran gigabyte?**
*   A. `IO.copy_stream` mengompresi data dengan gzip secara otomatis.
*   B. `IO.copy_stream` dapat memanfaatkan optimasi kernel Zero-Copy (seperti syscall `sendfile(2)`), memindahkan data langsung antar-file descriptor di dalam kernel-space tanpa mengalirkan data ke Ruby heap.
*   C. `IO.copy_stream` menggunakan C++ multithreading tersembunyi.
*   D. `IO.copy_stream` mengabaikan proteksi file permissions.
*   *Jawaban Rasional:* **B**. `IO.copy_stream` memotong context switching dan alokasi memory user space dengan mendelegasikan transfer data sepenuhnya ke subsistem kernel (menggunakan `sendfile`, `splice`, atau buffer internal C berukuran optimal).

**9. Sebuah thread Ruby mengeksekusi operasi baca non-blocking `io.read_nonblock(1024)` pada socket dan menangkap exception `IO::WaitReadable`. Langkah penanganan apa yang paling efisien dilakukan selanjutnya?**
*   A. Mengulang pemanggilan `read_nonblock` dalam tight loop tanpa jeda (`busy-waiting`).
*   B. Menutup socket dan menganggap koneksi terputus.
*   C. Memanggil `IO.select([io], nil, nil, timeout)` untuk menidurkan thread Ruby hingga kernel memberitahukan bahwa data telah siap di socket buffer.
*   D. Melakukan `Thread.kill` pada thread tersebut.
*   *Jawaban Rasional:* **C**. Melakukan *busy waiting* akan memicu konsumsi CPU 100%. `IO.select` menangguhkan eksekusi thread secara efisien menggunakan I/O multiplexer OS sampai socket descriptor berstatus readable.

**10. Apa kegunaan utama dari flag `File::Constants::O_NOFOLLOW` saat membuka File Descriptor di lingkungan aplikasi dengan multi-tenant / user-uploaded directory?**
*   A. Menginstruksikan kernel agar tidak mengikuti symlink, menggagalkan operasi jika path yang dituju adalah symbolic link untuk mencegah eksploitasi symlink race arbitrer.
*   B. Menonaktifkan pelacakan git pada file tersebut.
*   C. Mencegah kernel melakukan caching pada file tersebut.
*   D. Menolak file jika ukurannya melebihi 2 Gigabyte.
*   *Jawaban Rasional:* **A**. `O_NOFOLLOW` adalah primitif keamanan esensial untuk mencegah *Symlink Traversal / TOCTOU vulnerability*, memastikan penyerang tidak dapat memanipulasi symlink yang mengarah ke file sistem sensitif (misal `/etc/passwd`).

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek: "The Multi-Process Concurrent Ring-Buffer Audit Logger"

### Deskripsi Masalah:
Bangun sebuah pustaka sistem logging Ruby (`ProcessSafeAuditLogger`) yang mampu menerima entri log terstruktur dari beberapa proses Ruby yang berjalan independen secara bersamaan (misal simulasi 4 worker proses via `fork`) dan menuliskannya ke dalam berkas log tunggal tanpa ada teks yang terpotong/bercampur (*tear-free*). Log engine harus tahan banting: jika terjadi error tak terduga, integritas berkas harus terjaga.

### Spesifikasi Teknis:
1.  **Format Log Biner:** Setiap baris diawali dengan Timestamp Unix 64-bit Big-Endian, diikuti oleh 2 bytes panjang payload string, dilanjutkan dengan Payload String UTF-8 itu sendiri.
2.  **Concurrency Control:** Manfaatkan kombinasi `File::Constants::O_APPEND` dan `File#flock(File::LOCK_EX)` dengan mekanisme retry/backoff cerdas (maksimal 500ms timeout sebelum melempar error).
3.  **Low-Level System Calls:** Dilarang menggunakan `File.write`, `puts`, atau `IO#<<`. Seluruh penulisan wajib melalui `IO.sysopen` dan `IO#syswrite` dengan perlindungan terhadap *partial writes*.
4.  **Resource Cleanup:** Pastikan setiap worker child process membersihkan dan menutup *File Descriptor* secara deterministik menggunakan blok `ensure`.
5.  **Durability:** Lakukan `io.fdatasync` setiap 100 entri log dituliskan untuk menjamin ketahanan terhadap crash.
6.  **Verification Script:** Sediakan method `verify_integrity!` yang membaca file tersebut dari awal hingga akhir menggunakan `IO#sysread`, memvalidasi panjang byte, dan memverifikasi tidak ada karakter yang corrupt akibat race condition antar worker.

### Checklist Penyelesaian:
*   [ ] Mengalokasikan file descriptor mentah via `IO.sysopen` dengan permissions `0640`.
*   [ ] Menangani *partial writes* dalam sebuah loop `syswrite` terisolasi.
*   [ ] Mengimplementasikan *exponential backoff* sederhana saat gagal mendapatkan `LOCK_NB`.
*   [ ] Melakukan spawning 4 proses anak menggunakan `Process.fork`. Masing-masing anak menuliskan 500 baris log.
*   [ ] Menjalankan recovery scan membaca total 2.000 log record secara utuh dan valid tanpa ada header mismatch.
*   [ ] Menutup seluruh handle FD secara deterministik pada master dan worker process.