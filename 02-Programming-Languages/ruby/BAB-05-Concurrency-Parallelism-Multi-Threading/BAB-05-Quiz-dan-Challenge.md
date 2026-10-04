# BAB 05: Quiz, Challenge, & Knowledge Check
**Concurrency, Parallelism, & Multi-Threading**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **GVL (Giant VM Lock / Global VM Lock) dan Model Eksekusi CRuby**  
   Jelaskan secara mendalam mengapa CRuby (MRI) mengimplementasikan GVL pada level VM. Bagaimana mekanisme pelepasan GVL (*GVL release*) bekerja ketika sebuah thread mengeksekusi operasi blocking I/O (misalnya: membaca file besar atau HTTP call) dibandingkan dengan CPU-bound execution?

2. **Diferensiasi Semantik: Thread, Fiber, dan Ractor**  
   Bandingkan model konkurensi antara `Thread`, `Fiber`, dan `Ractor` dalam konteks Ruby 3.x berdasarkan tiga parameter arsitektural:
   - Mekanisme penjadwalan (*preemptive* vs *cooperative*).
   - Penggunaan resource memori OS (native OS thread stack vs user-space stack).
   - Kemampuan mengeksekusi komputasi paralel sejati (*true multi-core CPU parallelism*).

3. **Fiber Scheduler dan Non-blocking Engine (Ruby 3+)**  
   Bagaimana arsitektur `Fiber::SchedulerInterface` mentransformasi eksekusi I/O pada Ruby? Jelaskan bagaimana operasi I/O standar seperti `TCPSocket#read` dapat berjalan asinkron tanpa mengubah kode prosedural menjadi model *callback/promise-based*.

4. **Exception Handling dan Lifecycle pada Thread**  
   Secara default, apa yang terjadi pada *main thread* ketika sebuah *worker thread* mengalami *unhandled exception*? Bandingkan perilaku ini dengan konfigurasi `Thread.abort_on_exception = true` dan `Thread#report_on_exception = true`, serta jelaskan dampaknya pada lingkungan produksi.

5. **Primitif Sinkronisasi: Mutex vs ConditionVariable**  
   Mengapa penggunaan `Mutex` saja sering kali tidak cukup untuk mengimplementasikan pola *producer-consumer*, sehingga memerlukan `ConditionVariable`? Jelaskan bahaya *busy-waiting* (polling loop) tanpa `ConditionVariable` terhadap utilitas CPU dan throughput thread lain di bawah GVL.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Ilusi Thread-Safety di Bawah GVL (*Atomicity vs Thread-Safety*)**  
   Banyak pengembang keliru mengasumsikan bahwa keberadaan GVL membuat operasi Ruby thread-safe secara otomatis. Perhatikan cuplikan kode berikut:
   ```ruby
   @counter = 0
   10.times.map do
     Thread.new do
       1_000.times { @counter += 1 }
     end
   end.each(&:join)
   ```
   Bedah mengapa nilai akhir `@counter` hampir selalu bernilai kurang dari `10_000` pada beban konkurensi tinggi. Uraikan instruksi YARV bytecode (`opt_plus`, `setinstancevariable`, `getinstancevariable`) untuk membuktikan titik terjadinya *race condition*.

2. **Deadlock Anatomi dan Siklus Akuisisi Lock**  
   Diberikan skenario transfer dana antar dua rekening:
   ```ruby
   def transfer(from_account, to_account, amount)
     from_account.mutex.synchronize do
       sleep 0.001 # Simulasi delay jaringan
       to_account.mutex.synchronize do
         from_account.balance -= amount
         to_account.balance += amount
       end
     end
   end
   ```
   Jelaskan secara teknis bagaimana kondisi *Circular Wait* dapat memicu `ThreadError: deadlock detected` ketika dua thread mengeksekusi transfer antar akun A dan B secara simultan dengan arah berlawanan. Bagaimana strategi deterministik (*resource ordering*) untuk memitigasinya?

3. **Ractor Isolation Model dan Batasan Mutabilitas**  
   Dalam Ractor, berbagi data mutable secara sembarangan dilarang (*shareable vs unshareable objects*). 
   - Apa kriteria eksak suatu objek diklasifikasikan sebagai *shareable object*?
   - Mengapa modul dan kelas secara default *shareable*, namun konstanta yang menunjuk pada *nested mutable object* (misal: `CONFIG = { timeout: 30 }`) memicu `Ractor::IsolationError` jika diakses lintas Ractor?
   - Jelaskan perbedaan semantik antara `Ractor.send(obj)` (copy) dan `Ractor.send(obj, move: true)` (move semantics).

4. **Koneksi Database dan Sizing Thread Pool Puma vs DB Pool**  
   Pada arsitektur aplikasi berbasis Puma (multithreaded mode) dengan `ActiveRecord`, jelaskan korelasi sistemik antara konfigurasi `RAILS_MAX_THREADS` (atau Puma threads) dengan `ActiveRecord::Base.connection_pool`. Apa symptom teknis spesifik yang terjadi di level kernel dan aplikasi jika Puma thread disetel ke 16, namun ukuran pool database dibatasi hanya 5?

5. **Copy-on-Write (CoW) Degradation pada Forking Worker**  
   Web server seperti Puma Clustered atau Unicorn menggunakan `fork(2)` untuk membuat worker processes guna mencapai paralelisasi di luar GVL. Namun, seiring waktu, memori fisik (RSS) masing-masing worker melonjak mendekati ukuran penuh aplikasi monolit. Jelaskan peran Ruby Generational Garbage Collector (RGenGC) dan *compaction* (`GC.compact`) terhadap degradasi Copy-on-Write pada memori OS.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck I/O Skala Masif & Thread Exhaustion
Sebuah microservice Ruby bertugas melakukan polling metrik performa ke 8.000 perangkat edge gateway setiap 60 detik melalui protokol HTTP/REST. Arsitektur saat ini menggunakan thread pool berbasis OS thread (`concurrent-ruby` ThreadPoolExecutor dengan batas 500 thread). 

**Insiden:**  
Ketika beberapa gateway mengalami degradasi jaringan dan memicu latensi tinggi (respons melambat dari 200ms ke 10-20 detik), utilisasi memori service langsung melonjak drastis hingga terkena Linux OOM Killer. CPU server justru berada di bawah 15%.
```
Metrics:
- OS Thread Count: 500+ (Maxed out)
- Memory (RSS): Spike dari 250MB ke 3.8GB
- System Calls: Ribuan context switches / sec
```
**Pertanyaan Diagnostik & Solusi:**
1. Mengapa alokasi OS thread dalam jumlah ratusan/ribuan untuk I/O latency tinggi memicu kegagalan memori dan *context switching overhead* di OS, meskipun GVL dilepas saat I/O?
2. Bagaimana Anda merancang ulang arsitektur sistem ini menggunakan Ruby 3.x Fiber / Gem `Async` (Ioquatix)? Jelaskan mengapa konsumsi memori dan overhead thread stack dapat berkurang hingga 80-90%.

---

### Skenario B: Race Condition dan Lost Updates pada Flash-Sale Checkout
Platform e-commerce mengalami diskrepansi inventaris serius saat *flash sale*. Item persediaan terbatas (stok: 50 unit) terjual sebanyak 68 kali. Backend menggunakan Puma dengan 8 worker dan masing-masing 5 thread, terhubung ke PostgreSQL.

Kode yang diidentifikasi bermasalah pada layer domain:
```ruby
class InventoryService
  def self.reserve_stock(product_id, quantity)
    product = Product.find(product_id) # Baris 1: Read state
    
    if product.available_stock >= quantity
      # Simulasi verifikasi eksternal / fraud check via REST API
      FraudCheckClient.verify!(product_id) # Memakan waktu ~80ms
      
      product.available_stock -= quantity
      product.save! # Baris 2: Write state
      true
    else
      false
    end
  end
end
```
**Pertanyaan Diagnostik & Solusi:**
1. Analisis mengapa keberadaan GVL tidak menghentikan terjadinya *overselling* ini, bahkan jika seluruh request dieksekusi dalam satu worker process yang sama.
2. Identifikasi kerentanan *Check-Then-Act (Time-of-check to time-of-use)* di atas.
3. Berikan solusi refaktorisasi arsitektur: Kapan Anda harus menggunakan In-Process Synchronization (`Mutex`), Database-Level Locking (Pessimistic vs Optimistic Locking), atau Distributed Locking (misal: Redis Redlock)? Sertakan implikasi skalabilitas horizontalnya.

---

### Skenario C: Data Processing Pipeline (CPU-Bound Tokenization + I/O Persistence)
Sebuah sistem NLP memproses dokumen teks berukuran total 20GB secara streaming. Setiap file harus melewati dua tahapan:
1. **Tahap 1 (CPU-Bound):** Tokenisasi teks kompleks, stopword removal, dan kalkulasi cosine similarity (berat komputasi).
2. **Tahap 2 (I/O-Bound):** Kompresi hasil token dan upload ke AWS S3 serta indexing metadata ke Elasticsearch.

Tim sebelumnya mencoba memproses ini menggunakan standar `Thread.new` sebanyak core CPU (8 core), namun mendapati bahwa utilisasi CPU total mesin tidak pernah melebihi ~120% (dari potensi 800% pada mesin 8-core), dan throughput pemrosesan sangat lambat.

**Pertanyaan Diagnostik & Solusi:**
1. Jelaskan mengapa pendekatan multi-threaded klasik gagal memanfaatkan 8-core CPU secara maksimal pada Tahap 1, dan bagaimana perilaku Tahap 2 berinteraksi dengan GVL.
2. Rancang arsitektur optimal berbasis Ruby modern: Bagaimana Anda memadukan **Ractor** (atau Process Forking/Parallel gem) untuk Tahap 1, dan **Fibers/Async** atau Thread I/O untuk Tahap 2? Jelaskan batas isolasi data (*zero-copy* atau *isolation rules*) antar layer komputasi dan layer I/O tersebut.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Thread-Safe Bounded Job Engine
Bangun sebuah library mini bernama `ResilientPipeline::Pool` menggunakan **murni Standard Library Ruby** (tanpa external gem seperti `concurrent-ruby`). Library ini harus memproses job secara paralel dan thread-safe dengan batasan resource yang ketat.

#### Requirements:
1. **Bounded Worker Pool:**  
   Implementasikan pool dengan ukuran worker thread yang statis/tetap (misal: $N$ worker threads).
2. **Bounded Task Queue & Backpressure:**  
   Gunakan antrean berkapasitas terbatas (*bounded buffer*, misal: kapasitas $M$). Jika queue penuh, thread produsen yang memanggil `#enqueue` tidak boleh membakar CPU (*no busy-wait*), melainkan harus diblokir (*blocking*) hingga ada slot kosong, atau memicu strategi reject jika timeout terlampaui.
3. **Deadlock-Free Coordination:**  
   Gunakan kombinasi `Mutex` dan `ConditionVariable` (atau `SizedQueue` internal standar) untuk mengelola sinkronisasi antara producer threads dan consumer worker threads.
4. **Graceful Shutdown & Drain:**  
   Implementasikan method `#shutdown(timeout:)` yang:
   - Menghentikan penerimaan task baru.
   - Mengizinkan worker threads menyelesaikan sisa task yang masih ada di antrean (*draining*).
   - Memaksa penghentian thread (`Thread#kill`) secara bersih jika batas `timeout` terlampaui.
5. **Thread Safety & Error Isolation:**  
   Exception yang muncul di dalam execution block task tidak boleh membunuh worker thread; exception harus ditangkap, dicatat (*error telemetry callback*), dan worker thread harus tetap hidup untuk memproses task berikutnya.

#### Constraints:
- Pure Ruby Core/Stdlib (Hanya boleh menggunakan `Thread`, `Mutex`, `ConditionVariable`, `Queue`/`SizedQueue`).
- Zero memory-leak: Tidak boleh menimbun referensi objek task yang telah selesai diproses.
- Harus lolos uji konkurensi: Menghindari deadlocks, starvation, dan silent thread crashes.

#### Expected Verification Script:
```ruby
pool = ResilientPipeline::Pool.new(workers: 4, max_queue: 10)

success_count = 0
mutex = Mutex.new

# Enqueue 50 tasks secara konkuren dari 5 thread producer yang berbeda
producers = 5.times.map do |p_id|
  Thread.new do
    10.times do |t_id|
      pool.enqueue do
        # Simulasi mixed CPU & IO work
        sleep(0.01)
        mutex.synchronize { success_count += 1 }
      end
    end
  end
end

producers.each(&:join)
pool.shutdown(timeout: 5)

puts "Processed #{success_count}/50 jobs successfully."
# Output harus tepat 50/50 tanpa deadlocks atau race conditions
```

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Batasan teknis eksak dari GVL pada CRuby dan implikasinya terhadap komputasi CPU-bound vs I/O-bound.
- [ ] Titik perpindahan konteks penjadwalan preemptive YARV (quantum timer / I/O syscall traps).
- [ ] Mengapa operasi compound seperti `+=`, `||=`, dan *check-then-act* pada Ruby murni tidak pernah thread-safe meskipun di bawah proteksi GVL.
- [ ] Perbedaan model memori antara Process Forking (CoW), Native Threading (Shared Memory + GVL), dan Ractor (Share-nothing Actor Model).
- [ ] Mekanisme kerja `ConditionVariable` dalam melepaskan dan mengakuisisi kembali `Mutex` secara atomik saat koordinasi thread.
- [ ] Arsitektur Ruby 3.x Fiber Scheduler dan integrasinya dengan event loop engine non-blocking (seperti `epoll` di Linux atau `kqueue` di macOS).
- [ ] Hubungan antara alokasi Thread OS, memory stack limits (`ulimit -s`), dan database connection pool saturation.

### Saya tidak perlu menghafal:
- [ ] Implementasi bahasa C internal dari file `thread_pthread.c` atau macro C spesifik untuk lock context switching pada VM MRI Ruby.
- [ ] Seluruh signature metode low-level pada `Fiber::SchedulerInterface` (cukup memahami lifecycle dan cara hook I/O dasarnya).
- [ ] Parameter assembly tingkat instruksi prosesor untuk memory barriers (*fence operations*), karena Ruby mengabstraksikannya di level VM.

### Saya harus bisa melakukan:
- [ ] Mengidentifikasi dan membuktikan keberadaan *race condition* pada kode multi-threaded menggunakan logging berbasis timestamp/thread-ID atau automated tests.
- [ ] Mengimplementasikan *locking pattern* deterministik (misal: pengurutan ID resource) untuk mencegah terjadinya distributed/in-process deadlocks.
- [ ] Mengkonfigurasi rasio concurrency server (Puma worker vs thread count) yang optimal berdasarkan karakteristik profil resource aplikasi (I/O heavy vs CPU heavy).
- [ ] Memanfaatkan primitif konkurensi bawaan Ruby (`Mutex`, `ConditionVariable`, `SizedQueue`) untuk membangun pipeline pemrosesan data konkuren yang bebas dari memory leak dan busy-waiting.
- [ ] Melakukan isolasi data mutabel dan mengeksekusi komputasi paralel sejati memanfaatkan `Ractor` pada Ruby 3+.