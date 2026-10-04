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
