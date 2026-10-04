# BAB 06: Quiz, Challenge, & Knowledge Check
**Concurrency & Parallelism: GIL, Threads & Multiprocessing**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Mekanisme Evaluasi Bytecode dan Global Interpreter Lock (GIL)
Jelaskan bagaimana CPython mengeksekusi instruksi pada loop evaluasi bytecode (`ceval.c`). Mengapa CPython mengimplementasikan Global Interpreter Lock (GIL) pada tingkat interpreter, dan apa konsekuensi mekanis dari keberadaan mutex ini terhadap eksekusi multi-threaded pada beban kerja *CPU-bound* di mesin multi-core?

### Soal 1.2: Perbedaan Fundamental Concurrency vs Parallelism pada OS & CPython
Bedakan antara *Concurrency* dan *Parallelism* jika ditinjau dari sudut pandang *OS Kernel Scheduler* (POSIX threads / `pthreads`) dan CPython runtime. Mengapa menjalankan dua thread *CPU-bound* secara konkuren di CPython sering kali menghasilkan *execution wall-time* yang lebih lambat secara signifikan dibandingkan mengeksekusinya secara sekuensial (*single-threaded*)?

### Soal 1.3: Atomisitas Bytecode vs Thread-Safety pada Level Logika Bisnis
Operasi mutasi pada tipe data bawaan CPython seperti `list.append(x)` atau pembaruan kamus `dict[k] = v` sering disebut "bersifat atomik". Jelaskan mengapa atomisitas pada tingkat instruksi tunggal bytecode CPython tidak menjamin kode aplikasi bebas dari *race condition* pada level logika bisnis (misalnya operasi `counter += 1`). Tunjukkan urutan dekompilasi bytecode (`dis`) yang membuktikan argumen Anda.

### Soal 1.4: Spektrum Inter-Process Communication (IPC): Serialization vs Shared Memory
Dalam modul `multiprocessing`, evaluasi perbedaan arsitektural dan penalti performa antara pertukaran data menggunakan `multiprocessing.Queue` (berbasis OS pipe dan serialisasi `pickle`) dibandingkan dengan `multiprocessing.shared_memory.SharedMemory`. Kapan penalti latensi serialisasi `pickle` mendominasi waktu eksekusi total, dan kapan *shared memory* wajib digunakan?

### Soal 1.5: Siklus Hidup dan Risiko Arsitektural Daemon Threads
Jelaskan perbedaan mendasar antara *daemon thread* dan *non-daemon thread* saat *main thread* menyelesaikan seluruh instruksinya. Mengapa penggunaan *daemon thread* sangat berbahaya apabila thread tersebut bertugas menangani penulisan ke sistem berkas (*file I/O*), transaksi basis data, atau mengakuisisi *lock/system resource* dalam *context manager*?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Pelepasan GIL pada Operasi Eksternal dan C-Extensions
Bagaimana CPython menangani pelepasan dan perebutan kembali GIL saat sebuah thread melakukan pemanggilan sistem (*system call*) seperti *socket read/write* atau saat mengeksekusi pustaka C pihak ketiga (misalnya operasi matriks BLAS/LAPACK di NumPy)? Apa yang terjadi pada level OS thread jika fungsi ekstensi C memanggil Python C-API tanpa terlebih dahulu mengeksekusi makro `PyGILState_Ensure()`?

### Soal 2.2: GIL Switch Interval dan Fenomena Convoy Effect
Sejak Python 3.2, mekanisme pergantian thread berbasis jumlah instruksi (*ticker*) digantikan oleh *time-based GIL interval* (`sys.getswitchinterval()`, default 5ms). Jelaskan cara kerja variabel kondisi (*condition variable*) internal yang mengatur pergantian ini. Bagaimana interaksi antara satu thread *CPU-bound* murni dan satu thread *I/O-bound* responsif dapat memicu latensi ekstrim (*thread starvation*) pada thread *I/O-bound* akibat *convoy effect*?

### Soal 2.3: Komparasi Start Method: `fork`, `spawn`, dan `forkserver`
Bandingkan mekanisme internal `fork`, `spawn`, dan `forkserver` pada modul `multiprocessing` di sistem operasi Linux. Jelaskan skenario fatal di mana penggunaan metode `fork` memicu *deadlock* instan pada *child process* jika *parent process* telah menjalankan thread lain yang sedang memegang mutex (misalnya alokasi memori internal via `malloc` atau logging handler lock).

### Soal 2.4: Deadlock Tersembunyi pada `multiprocessing.Queue` dan Batasan Pipe OS
Ditinjau dari implementasi internal `multiprocessing.Queue`, sebuah *feeder thread* bertugas mengalirkan data yang di-*pickle* ke dalam OS pipe. Mengapa memanggil `process.join()` sebelum seluruh data dalam antrean dikonsumsi atau sebelum buffer OS pipe dikosongkan dapat menyebabkan aplikasi membeku (*deadlock*) secara permanen jika data yang dikirim melebihi kapasitas buffer OS pipe (misalnya >64KB di Linux)?

### Soal 2.5: Crash Recovery dan Orphan Process pada `ProcessPoolExecutor`
Ketika sebuah worker process di dalam `concurrent.futures.ProcessPoolExecutor` dimatikan secara paksa oleh sistem operasi melalui sinyal `SIGKILL` (misalnya dipicu oleh Linux Out-Of-Memory / OOM Killer), bagaimana executor mendeteksi kondisi tersebut? Mengapa exception `BrokenProcessPool` dilempar ke thread pemanggil, dan bagaimana strategi arsitektur untuk memulihkan (*recover*) task yang sedang berjalan tanpa mematikan proses utama (*parent process*)?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck CPU Pod Kubernetes pada Pipeline Pemrosesan Citra
Sebuah *microservice* berbasis FastAPI di-deploy pada Kubernetes pod dengan kuota resource 8 vCPU dan 16GB RAM. Service ini bertugas menerima unggahan gambar beresolusi tinggi, melakukan decoding, cropping, dan kalkulasi histogram warna secara intensif. 

Implementasi awal menggunakan `ThreadPoolExecutor(max_workers=8)` untuk memproses batch gambar secara paralel. Namun, hasil observasi via Prometheus dan Grafana menunjukkan:
* Metrik CPU utilization pod tidak pernah melampaui rentang 115% - 130% (hanya setara ~1 core aktif dari total 8 core).
* Latensi response melonjak drastis saat request concurrency meningkat dari 10 RPS ke 50 RPS.
* Analisis non-intrusif menggunakan `py-spy` mengindikasikan bahwa sebagian besar thread menghabiskan >85% waktu siklusnya dalam status `GIL wait/contention`.

**Tugas Diagnostik:**
1. Bedah secara mekanis mengapa penambahan jumlah worker pada `ThreadPoolExecutor` di skenario ini sama sekali tidak meningkatkan throughput pemrosesan.
2. Rancang arsitektur baru menggunakan `ProcessPoolExecutor` atau modul `multiprocessing`. Bagaimana Anda mengelola *worker lifecycle* agar tidak memicu memory footprint berlebih saat menangani citra berukuran besar?
3. Jika pipeline tersebut melibatkan NumPy atau OpenCV, identifikasikan strategi pelepasan GIL di dalam pustaka tersebut dan tentukan konfigurasi kombinasi antara *thread-level parallelism* (OpenMP/MKL) dengan *process-level parallelism* agar tidak terjadi *oversubscription* CPU core.

---

### Skenario B: Heisenbug Race Condition pada In-Memory Financial Ledger
Sebuah mesin pencatatan transaksi finansial *in-memory* berkinerja tinggi menangani ribuan mutasi saldo dompet per detik menggunakan Python 3.11. Setiap mutasi dieksekusi oleh worker thread di dalam pool:

```python
# Komponen state in-memory
accounts_balance = {"ID_USER_001": 1_000_000}

def execute_transfer(account_id: str, amount: int):
    # Validasi saldo
    if accounts_balance[account_id] >= amount:
        # Simulasi sedikit network call logging
        time.sleep(0.00001) 
        accounts_balance[account_id] -= amount
        return True
    return False
```

Dalam unit test sekuensial, kode berjalan 100% sempurna. Namun pada load testing dengan 100 thread paralel yang melakukan penarikan saldo simultan sebesar 10.000, ditemukan bahwa saldo akhir bernilai negatif (misalnya -80.000) dan total mutasi yang berhasil melebihi limit validasi yang diizinkan. 

**Tugas Diagnostik:**
1. Bedah titik kerentanan *race condition* (khususnya *Time-of-Check to Time-of-Use* / TOCTOU) pada cuplikan kode di atas dengan menjabarkan kemungkinan alur *context switching* antar-thread yang terjadi.
2. Tunjukkan bagaimana GIL gagal melindungi integritas variabel `accounts_balance` meskipun `time.sleep()` dihilangkan (misalnya operasi mutasi matematika murni di bawah beban ekstrim).
3. Rancang dua solusi perbaikan kelas produksi:
   - **Solusi 1 (Pessimistic Locking):** Menggunakan primitive synchronization (`threading.Lock` atau `threading.RLock`) yang *exception-safe* dan meminimalkan area *critical section*.
   - **Solusi 2 (Lock-Free / Queue-Based):** Mengubah paradigma mutasi menjadi arsitektur berbasis *Single-Threaded Event Loop / Actor Pattern* menggunakan thread-safe queues. Evaluasi kelebihan dan kekurangan kedua pendekatan tersebut.

---

### Skenario C: Trade-off Desain Sistem Ekstraksi Data Dokumen Skala Besar
Sebuah platform analitik dokumen legal harus mengolah 100.000 dokumen PDF terenkripsi setiap hari. Alur kerja setiap dokumen terdiri dari tiga fase:
1. **Fase I (I/O-Bound):** Mengunduh dokumen terenkripsi dari S3 storage (latensi network bervariasi).
2. **Fase II (CPU-Bound murni):** Dekripsi PDF, Optical Character Recognition (OCR), dan parsing struktur token dokumen (sangat intensif CPU dan alokasi memori).
3. **Fase III (I/O-Bound):** Mengunggah representasi JSON hasil parsing kembali ke S3 dan mengindeks metadata ke PostgreSQL.

Tim engineering terbagi menjadi dua kubu:
* *Kubu A* ingin menggunakan satu `ProcessPoolExecutor` besar (misalnya 32 worker) untuk mengeksekusi ketiga fase tersebut sekaligus dalam satu fungsi worker per dokumen.
* *Kubu B* ingin memisahkan arsitektur menjadi *hybrid pipeline*: `ThreadPoolExecutor` (atau `asyncio`) untuk Fase I & III, dan `ProcessPoolExecutor` khusus untuk Fase II, yang dihubungkan melalui *bounded queue*.

**Tugas Diagnostik:**
1. Evaluasi kelemahan kritis dari pendekatan *Kubu A*, terutama terkait pemborosan *CPU allocation*, memory starvation akibat *resident set size* (RSS) proses worker, dan inefisiensi worker saat menunggu I/O network.
2. Analisis implikasi penggunaan pendekatan *Kubu B*. Bagaimana Anda menangani mekanisme *backpressure* agar Fase I tidak membanjiri memori RAM dengan dokumen mentah sebelum Fase II sempat memprosesnya?
3. Tentukan estimasi dimensi sizing pool (jumlah thread I/O vs jumlah process CPU) jika sistem berjalan di server *bare-metal* dengan spesifikasi 16 Physical Cores (32 Hardware Threads) dan 64GB RAM. Berikan justifikasi berbasis *Amdahl's Law* dan *resource constraints*.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Zero-Copy Parallel Matrix Cruncher with Crash-Resilient Shared Memory

#### Deskripsi Masalah
Dalam komputasi numerik skala enterprise, memproses dataset besar secara paralel menggunakan modul `multiprocessing` sering kali terhambat oleh *IPC bottleneck*. Jika sebuah dataset matriks berukuran multi-gigabyte dikirimkan melalui `multiprocessing.Queue` atau argumen fungsi `pool.map()`, CPython akan menduplikasi dataset tersebut melalui serialisasi `pickle` untuk setiap proses anak. Hal ini menyebabkan lonjakan memori (*memory ballooning*), memicu Linux OOM-killer, dan menurunkan performa komputasi secara masif.

Anda ditantang untuk membangun sebuah *Zero-Copy Parallel Processing Engine* yang mampu mendistribusikan beban kalkulasi numerik ke seluruh CPU core yang tersedia tanpa overhead serialisasi data input, menggunakan memori bersama terproteksi (*POSIX Shared Memory* via Python), serta memiliki ketahanan terhadap kegagalan mendadak (*crash resilience*).

#### Spesifikasi Fungsional & Teknis

1. **Shared Memory Allocation & Mapping:**
   - Alokasikan blok memori menggunakan `multiprocessing.shared_memory.SharedMemory`.
   - Inisialisasi matriks sintetis berdimensi $N \times M$ bertipe `float64` (minimal berukuran 1GB hingga 2GB di RAM) langsung pada blok memori tersebut menggunakan `numpy.ndarray(..., buffer=shm.buf)`.

2. **Zero-Copy Parallel Execution:**
   - Bangun pool worker menggunakan `ProcessPoolExecutor` atau `multiprocessing.Process` murni dengan start method `'spawn'` (atau `'forkserver'`) untuk menjamin keamanan isolasi state OS.
   - Bagikan referensi shared memory hanya menggunakan *string identifier* nama blok (`shm.name`), bukan me-pass instance objek array NumPy ke argumen worker.
   - Setiap worker harus me-mount blok memori bersama tersebut, mengambil irisan (*slice*) segment baris tertentu secara independen, dan melakukan operasi matematika intensif (misalnya transformasi Fourier 1D, normalisasi skalar non-linear, atau perkalian matriks lokal).
   - Seluruh hasil mutasi harus ditulis langsung ke *output shared memory buffer* yang terpisah (*zero-copy in-place write*).

3. **Graceful Destruction & Resource Cleanup:**
   - Gunakan blok penanganan resource (`try...finally` atau *custom context manager*) yang menjamin pemanggilan `.close()` dan `.unlink()` pada objek `SharedMemory`. Pastikan tidak ada kebocoran blok memori POSIX (`/dev/shm`) yang tertinggal di sistem operasi, bahkan jika aplikasi menerima interupsi keyboard (`SIGINT` / Ctrl+C) atau unhandled exception.

4. **Fault Tolerance & Poison Pill Simulation:**
   - Rancang mekanisme pendeteksian di mana salah satu worker process secara sengaja dimatikan paksa menggunakan `os.kill(os.getpid(), signal.SIGKILL)` di tengah kalkulasi untuk mereplikasi kondisi fatal Out-Of-Memory (OOM).
   - Parent process harus mampu mendeteksi kematian worker tersebut, mengidentifikasi segmen data mana yang gagal diolah, menginisialisasi ulang worker pengganti, dan mengkalkulasi ulang segmen yang terputus tanpa mengulang komputasi segmen lain yang telah selesai (*fault recovery*).

#### Batasan Implementasi (Constraints)
* Dilarang menggunakan serialisasi `pickle` untuk data matriks utama (argumen worker hanya boleh berupa primitif: metadata nama shared memory, offset indeks baris awal, offset indeks baris akhir, dan tipe data).
* Total alokasi memori fisik (RSS) seluruh proses tidak boleh melampaui $1.2 \times$ dari ukuran matriks asli (menandakan zero-copy berhasil dan tidak terjadi duplikasi memori antar-proses).
* Utilisasi seluruh core CPU yang dialokasikan wajib mencapai >90% secara linear selama komputasi berlangsung (verifikasi via profiling CPU time vs wall time).

#### Expected Output
1. Skrip Python mandiri (`matrix_cruncher.py`) yang mematuhi *type hinting* ketat (PEP 484), bebas *global state leak*, dan memiliki error-handling berstandar industri.
2. Log konsol terstruktur yang menampilkan:
   - Metadata matriks (dimensi, tipe data, total bytes di `/dev/shm`).
   - Verifikasi isolasi alamat memori fisik pada tiap PID worker.
   - Benchmark perbandingan waktu eksekusi: Pendekatan Standar (Pickle/IPC Queue) vs Zero-Copy Shared Memory.
   - Bukti eksekusi skenario *Worker Crash & Auto-Recovery*.
   - Verifikasi pembersihan total blok `/dev/shm` setelah eksekusi selesai.

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk memvalidasi kesiapan arsitektural dan pemahaman teknis Anda sebelum beralih ke materi asynchronous programming atau deployment tingkat lanjut:

### Saya harus memahami:
- [ ] Mekanisme loop evaluasi bytecode (`ceval.c`) di CPython dan implikasi struktural GIL terhadap single-core thread serialization.
- [ ] Perbedaan implementasi kernel-level threading (1:1 model POSIX threads) dengan interpreter-level lock constraints di Python.
- [ ] Batasan atomisitas operasi built-in CPython dan mengapa race condition tetap dapat terjadi tanpa adanya explicit locking.
- [ ] Perbedaan mendalam mekanisme start method process: `fork` vs `spawn` vs `forkserver`, beserta implikasi keamanan memory footprint dan OS-level thread safety-nya.
- [ ] Penalti performa serialisasi `pickle` pada IPC standar dan cara kerja POSIX shared memory (`multiprocessing.shared_memory`).
- [ ] Algoritma GIL time-slice release (`sys.getswitchinterval()`), serta fenomena GIL contention dan convoy effect pada campuran workload CPU dan I/O.
- [ ] Kondisi deadlock pada OS pipe buffer limit ketika memanipulasi `multiprocessing.Queue` dan proses joining.

### Saya tidak perlu menghafal:
- [ ] Kode heksadesimal representasi opcode CPython internal di level compiler C.
- [ ] Implementasi assembly spesifik dari spin-lock atau OS-level primitive mutex di kernel Linux/Darwin.
- [ ] Setiap parameter konfigurasi mikro dari C-API Python internals (`PyThreadState`, dsb.) di luar cakupan interaksi umum C-extensions.

### Saya harus bisa melakukan:
- [ ] Mendiagnosis thread contention dan GIL bottleneck pada aplikasi produksi menggunakan continuous profiler non-intrusif (seperti `py-spy` atau `perf`).
- [ ] Mengimplementasikan *synchronization primitives* (`threading.Lock`, `RLock`, `Semaphore`, `Event`, `Condition`) secara tepat tanpa menimbulkan bahaya *deadlock* atau *livelock*.
- [ ] Menentukan kapan harus menggunakan `threading`, `multiprocessing`, atau kombinasi hybrid berdasarkan profil resource (I/O-Bound vs CPU-Bound).
- [ ] Membangun pipeline pemrosesan data paralel berkecepatan tinggi dengan *zero-copy memory sharing* menggunakan `multiprocessing.shared_memory` dan `numpy`.
- [ ] Mengonfigurasi dan mengamankan siklus hidup worker pool (`concurrent.futures.ProcessPoolExecutor`) terhadap crash proses tak terduga (OOM/SIGKILL) dan memory leak.