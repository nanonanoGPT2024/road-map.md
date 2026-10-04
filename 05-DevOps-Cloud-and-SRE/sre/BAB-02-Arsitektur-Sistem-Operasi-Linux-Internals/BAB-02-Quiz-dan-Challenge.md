# Evaluasi Bab 02: Arsitektur Sistem Operasi Tingkat Rendah & Linux Internals

Dokumen ini berisi rangkaian pengujian pemahaman teknis mulai dari tingkat dasar, menengah, hingga analisis studi kasus industri nyata dan tantangan arsitektur hands-on.

---

## 1. Basic Questions (5 Soal)

### Soal 1.1
Jelaskan perbedaan mendasar antara CPU privilege level **Ring 0** dan **Ring 3** pada arsitektur x86_64, serta sebutkan instruksi CPU yang digunakan untuk berpindah dari Ring 3 ke Ring 0!

<details>
<summary>Jawaban & Kunci Penilaian</summary>

- **Ring 0 (Supervisor/Kernel Mode)**: Tingkat privilese tertinggi di mana CPU memiliki akses tak terbatas ke seluruh instruksi perangkat keras fisik, seluruh register kontrol (seperti register kontrol MMU `CR0`, `CR3`), dan seluruh pemetaan memori fisik. Kode kernel Linux beroperasi di Ring 0.
- **Ring 3 (User Mode)**: Tingkat privilese terendah yang membatasi eksekusi instruksi: aplikasi tidak dapat mengakses I/O hardware secara langsung, memodifikasi page table, atau membaca ruang memori proses lain.
- **Instruksi Transisi**: Instruksi assembly `syscall` (atau `sysenter` pada arsitektur legacy x86 32-bit, dan `svc` pada ARM) mengeksekusi *software trap* yang secara hardware mengubah privilege level CPU dari Ring 3 ke Ring 0 dan mengalihkan *instruction pointer* (`%rip`) ke register kernel syscall entrypoint.
</details>

---

### Soal 1.2
Mengapa penggunaan `epoll` jauh lebih skalabel dan berkinerja tinggi dibandingkan `select` atau `poll` ketika mengelola ratusan ribu koneksi socket jaringan konkuren?

<details>
<summary>Jawaban & Kunci Penilaian</summary>

- **Kompleksitas Seleksi Event**:
  - `select()` dan `poll()` mengharuskan user-space menyalin seluruh list file descriptor (array/bitmask) ke kernel space pada setiap pemanggilan, lalu kernel melakukan iterasi pemindaian linier $\mathcal{O}(N)$ ke seluruh FD tersebut untuk mengecek ada tidaknya event.
  - `epoll` memisahkan pendaftaran event dari proses pengecekan. FD disimpan di kernel space dalam struktur **Red-Black Tree** ($\mathcal{O}(\log N)$ untuk mutasi).
- **Mekanisme Callback Ready List**:
  Driver jaringan kernel mendaftarkan callback interupsi hardware. Ketika paket tiba di socket, kernel secara otomatis memindahkan socket terkait ke dalam struktur **Ready List (Doubly Linked List)**. Syscall `epoll_wait()` hanya mengembalikan FD yang berstatus ready dari list tersebut dengan kompleksitas $\mathcal{O}(K)$ (di mana $K$ adalah jumlah event yang aktif). Tidak ada operasi penyalinan array FD secara berulang bolak-balik antara user-space dan kernel-space.
</details>

---

### Soal 1.3
Apa perbedaan teknis antara **Minor Page Fault** dan **Major Page Fault** pada sistem manajemen memori Linux?

<details>
<summary>Jawaban & Kunci Penilaian</summary>

- **Minor Page Fault (Soft Fault)**: Terjadi ketika halaman memori yang diminta oleh proses sudah berada di RAM fisik (misalnya: halaman dialokasikan melalui demand paging tetapi belum dipetakan ke Page Table Entry proses, atau halaman tersebut berada di shared memory Page Cache yang telah dimuat oleh proses lain), sehingga kernel hanya perlu memperbarui *Page Table Entry* (PTE) dan TLB tanpa melakukan pembacaan blok dari disk penyimpanan. Operasi ini berlangsung sangat cepat (orde nanodetik/mikrodetik).
- **Major Page Fault (Hard Fault)**: Terjadi ketika halaman memori yang dirujuk sama sekali belum ada di RAM fisik dan harus dibaca secara sinkron dari media penyimpanan sekunder (seperti membaca blok file dari SSD/NVMe atau membaca halaman anonymous memory yang sebelumnya terlempar ke Swap disk). Proses akan dipaksa beralih ke *sleep state* (`D-state`) menunggu I/O disk selesai, menimbulkan penalti latensi tinggi (orde milidetik).
</details>

---

### Soal 1.4
Apa fungsi dari kernel thread **`kswapd`** dan dalam kondisi apa proses aplikasi beralih fungsi menjalankan **Direct Reclaim**?

<details>
<summary>Jawaban & Kunci Penilaian</summary>

- **`kswapd` (Background Reclaim)**: Kernel daemon asinkron yang terbangun ketika kapasitas memori bebas pada zone memori turun menyentuh ambang batas **Watermark Low** (`WMARK_LOW`). `kswapd` membebaskan halaman memori (membersihkan dirty page cache dan memindahkan anonymous memory ke swap) di latar belakang hingga memori bebas kembali berada di atas ambang batas **Watermark High** (`WMARK_HIGH`). Selama fase ini, proses aplikasi user-space tidak diblokir.
- **Direct Reclaim**: Jika laju alokasi memori oleh aplikasi jauh melampaui kemampuan `kswapd` membebaskan halaman, dan memori bebas anjlok hingga menembus ambang batas **Watermark Min** (`WMARK_MIN`), kernel akan menghentikan alokasi aplikasi secara sinkron. Aplikasi peminta memori dipaksa langsung (*Direct Reclaim*) membersihkan memori sistem sendiri, menyebabkan aplikasi mengalami *latency stall* yang signifikan.
</details>

---

### Soal 1.5
Sebutkan satu kelemahan arsitektural utama dari **cgroups v1** yang akhirnya diselesaikan secara fundamental pada rancang bangun **cgroups v2**!

<details>
<summary>Jawaban & Kunci Penilaian</summary>

- Pada **cgroups v1**, setiap controller resource (seperti `memory`, `cpu`, `blkio`) memiliki hirarki direktori independen dan terpisah satu sama lain (*multi-hierarchy design*).
- **Dampaknya**: Terjadi ketidakmampuan mengoordinasikan interaksi antar-subkelompok resource. Contoh paling nyata: pengontrol `blkio` tidak dapat melacak proses mana yang memproduksi dirty pages pada controller `memory` saat dirty pages tersebut di-flush oleh kernel thread `kworker`. Akibatnya, I/O throttling pada cgroups v1 gagal berfungsi untuk operasi *buffered write*.
- **Solusi cgroups v2**: Menyediakan satu pohon hirarki tunggal (*unified hierarchy*), di mana resource memory dan block I/O saling terhubung erat sehingga kernel dapat melakukan tracking kepemilikan I/O writeback buffer hingga ke proses pembuat aslinya di cgroup yang bersangkutan.
</details>

---

## 2. Intermediate Questions (5 Soal)

### Soal 2.1
Perhatikan parameter sysctl kernel berikut:
```ini
vm.dirty_background_ratio = 5
vm.dirty_ratio = 20
```
Jelaskan secara presisi urutan kejadian di dalam kernel ketika sebuah proses melakukan operasi `write()` secara masif pada server dengan total RAM 64 GB!

<details>
<summary>Jawaban & Kunci Penilaian</summary>

1. **Fase Ingress Cepat**: Proses memanggil syscall `write()`. Data disalin dari buffer user-space ke Page Cache kernel di RAM fisik dan ditandai sebagai *dirty page*. Pemanggilan `write()` langsung mengembalikan status sukses tanpa menunggu data tertulis di storage fisik.
2. **Ambang Batas Background (`vm.dirty_background_ratio = 5%` $\rightarrow$ 3.2 GB)**:
   Ketika akumulasi dirty pages di Page Cache melampaui 3.2 GB, kernel secara asinkron membangunkan flusher threads (`kworker/flush`). Flusher thread mulai menulis blok kotor tersebut ke media disk di latar belakang. Proses aplikasi **tidak diblokir** dan tetap dapat menulis secara normal.
3. **Ambang Batas Kritis Blocking (`vm.dirty_ratio = 20%` $\rightarrow$ 12.8 GB)**:
   Jika kecepatan penulisan proses aplikasi melampaui kecepatan transfer fisik media storage, volume dirty page akan terus membengkak hingga menyentuh 12.8 GB. Pada titik ini, kernel mengaktifkan mekanisme proteksi *throttling*: proses aplikasi yang memanggil syscall `write()` **akan diblokir secara sinkron** (berpindah ke state `D`/uninterruptible sleep) dan dipaksa oleh scheduler kernel untuk ikut serta menulis dirty page ke disk sampai jumlah dirty memory menyusut kembali ke bawah 20%.
</details>

---

### Soal 2.2
Bagaimana cara kerja **`futex` (Fast Userspace Mutex)** saat mengoptimalkan operasi sinkronisasi thread pada kondisi *uncontended* (tidak ada perebutan) dibandingkan saat *contended* (terjadi perebutan)?

<details>
<summary>Jawaban & Kunci Penilaian</summary>

- **Uncontended Case (Jalur Cepat / User Space Only)**:
  Thread mencoba mengunci variabel integer atomic 32-bit di user space menggunakan instruksi CPU atomic berkemampuan memori (misalnya: `LOCK CMPXCHG` pada arsitektur x86). Karena tidak ada thread lain yang sedang memegang lock tersebut, operasi pertukaran nilai berhasil dalam 1 siklus CPU. Tidak ada transisi context switch, tidak ada trap handler, dan tidak ada syscall yang dieksekusi. Overhead performa mendekati nol.
- **Contended Case (Jalur Lambat / Kernel Space Involvement)**:
  Jika lock sedang dipegang oleh thread lain, instruksi atomic user space akan gagal. Thread peminta menyadari adanya tabrakan dan mengeksekusi syscall `futex(val_addr, FUTEX_WAIT, current_val, ...)`. Kernel akan memverifikasi apakah nilai pada alamat memori masih sama secara atomik; jika ya, kernel menempatkan thread tersebut ke dalam antrean tunggu (*kernel wait queue*) dan menidurkannya (`TASK_INTERRUPTIBLE`/`UNINTERRUPTIBLE`). Ketika thread pemilik lock selesai, ia memanggil syscall `futex(val_addr, FUTEX_WAKE, 1, ...)`, yang memerintahkan kernel membangunkan thread yang tertidur di antrean.
</details>

---

### Soal 2.3
Analisis baris output dari `/proc/<PID>/smaps` berikut ini:
```text
7f9200000000-7f9202000000 rw-p 00000000 00:00 0 
Size:              32768 kB
Rss:                8192 kB
Pss:                4096 kB
Shared_Clean:          0 kB
Shared_Dirty:       8192 kB
Private_Clean:         0 kB
Private_Dirty:         0 kB
Referenced:         8192 kB
Anonymous:          8192 kB
Swap:                  0 kB
```
Jelaskan arti metrik **Size**, **Rss**, dan **Pss**, serta mengapa nilai **Pss** bernilai persis setengah dari **Rss** pada segmen memori ini!

<details>
<summary>Jawaban & Kunci Penilaian</summary>

- **Size (32768 kB / 32 MB)**: Ukuran keseluruhan ruang alamat memori *virtual* (VMA) yang dialokasikan oleh proses pada rentang tersebut.
- **Rss (Resident Set Size - 8192 kB / 8 MB)**: Jumlah halaman memori fisik (RAM nyata) yang saat ini benar-benar dipetakan dan dipegang oleh segmen ini.
- **Pss (Proportional Set Size - 4096 kB / 4 MB)**: Representasi penggunaan memori fisik aktual proses dengan memperhitungkan pembagian beban secara proporsional jika suatu halaman memori di-share antar-proses.
- **Penyebab Pss bernilai setengah dari Rss**:
  Segmen ini memiliki `Shared_Dirty: 8192 kB` dan `Private_Dirty: 0 kB`. Ini menandakan bahwa seluruh 8 MB memori fisik tersebut sedang di-share secara bersamaan oleh **dua proses** yang berbeda (misalnya: master process dan 1 child worker process hasil pemanggilan `fork()` sebelum terjadinya Copy-On-Write). Rumus Pss adalah:
  $$\text{Pss} = \text{Private} + \sum \left(\frac{\text{Shared}}{N}\right)$$
  Karena halaman dibagi rata oleh $N = 2$ proses, maka:
  $$\text{Pss} = 0 + \frac{8192\text{ kB}}{2} = 4096\text{ kB}$$
</details>

---

### Soal 2.4
Pada konfigurasi cgroups v2, apa perbedaan mekanisme mendasar antara file kontrol **`memory.high`** dan **`memory.max`**, dan bagaimana Anda menggunakannya untuk mendesain arsitektur aplikasi yang *resilient*?

<details>
<summary>Jawaban & Kunci Penilaian</summary>

- **`memory.max` (Hard Ceiling)**:
  Batas absolut kapasitas memori. Jika penggunaan memori proses dalam cgroup menyentuh batas ini, dan kernel tidak mampu lagi membebaskan memori via reclaim, kernel **seketika mengaktifkan OOM Killer** untuk mematikan satu atau seluruh proses dalam cgroup tersebut.
- **`memory.high` (Soft Throttle Throttle)**:
  Batas proteksi dini. Jika penggunaan memori menembus nilai `memory.high`, kernel **tidak akan membunuh proses**. Sebagai gantinya, kernel akan:
  1. Menerapkan penalti penundaan (*throttling delay*) pada proses peminta alokasi saat kembali dari syscall alokasi memori.
  2. Memicu proses *asynchronous reclaim* yang sangat agresif di latar belakang untuk menekan volume memori kembali ke bawah ambang batas `memory.high`.
- **Desain Resilient**:
  Pasang nilai `memory.high` pada ~80-85% dari batas `memory.max`. Ini bertindak sebagai *early warning & self-healing zone*: sistem monitoring dapat mendeteksi metrik *throttle events* di `memory.events` dan mengirim alert kapasitas, sementara aplikasi secara fisik diperlambat secara terkendali tanpa mengalami *crash termination* akibat OOM Killer.
</details>

---

### Soal 2.5
Jelaskan arsitektur keamanan **eBPF In-Kernel Verifier**. Mengapa Verifier menolak kode C yang memiliki *unbounded loops* atau dereferensi pointer bebas?

<details>
<summary>Jawaban & Kunci Penilaian</summary>

- **Peran Verifier**:
  eBPF mengeksekusi instruksi kustom langsung di Ring 0 (kernel space). Jika program eBPF mengalami crash, membaca sembarang memori kernel, atau terkunci dalam infinite loop, seluruh sistem operasi akan mengalami *Kernel Panic* atau *System Freeze*. Verifier bertindak sebagai gerbang pembuktian formal (*formal verification gate*) sebelum bytecode diizinkan dikompilasi oleh JIT (*Just-In-Time Compiler*).
- **Penolakan Unbounded Loops**:
  Loop tanpa batas kepastian (*infinite loops*) akan membekukan thread kernel selamanya, merusak penjadwalan CPU (*CPU starvation*). Verifier memverifikasi *Directed Acyclic Graph* (DAG) dari seluruh alur instruksi untuk membuktikan bahwa program eBPF dijamin akan selesai (*guaranteed termination*) dalam batas instruksi instruksi yang telah ditetapkan.
- **Penolakan Dereferensi Pointer Bebas**:
  Program eBPF dilarang membaca atau menulis sembarang alamat pointer fisik tanpa melalui helper resmi (`bpf_probe_read_*` atau mekanisme BPF CO-RE) untuk mencegah kebocoran data rahasia kernel (*memory corruption*) atau eksploitasi eskalasi privilese sistem.
</details>

---

## 3. Scenario-Based Questions (3 Kasus Nyata)

### Skenario 3.1: "The Vanishing JVM Microservice"
**Konteks Masalah**:
Sebuah aplikasi Java Spring Boot berjalan di dalam container Docker pada node Kubernetes. Container disetel dengan limit resource:
```yaml
resources:
  limits:
    memory: "4Gi"
```
Flags JVM dikonfigurasi dengan:
`-Xms2g -Xmx2g` (Heap diatur 2 GB).

Namun, setiap 6 jam sekali pada saat traffic padat, Pod mendadak mati (*restarted*) dengan status exit code `137`. Saat log aplikasi diperiksa, **tidak ditemukan satupun jejak error `java.lang.OutOfMemoryError`**.

**Pertanyaan Analisis**:
1. Mengapa aplikasi Java mati tanpa melempar exception `OutOfMemoryError` di log aplikasi?
2. Bagaimana cara membuktikan secara pasti komponen internal mana yang mengonsumsi sisa memori 2 GB lainnya pada container tersebut?
3. Langkah mitigasi arsitektur apa yang harus diambil pada level runtime Java dan level Linux OS/Container?

<details>
<summary>Solusi & Panduan Investigasi</summary>

1. **Penyebab Kematian Tanpa Exception**:
   `java.lang.OutOfMemoryError` hanya dilempar oleh JVM runtime jika alokasi di dalam **JVM Heap Space** penuh dan lolos dari Garbage Collection. Exit code `137` adalah $128 + 9$ (`SIGKILL`). Ini membuktikan bahwa proses dimatikan secara paksa dari luar oleh **Linux Kernel OOM Killer** karena total penggunaan memori container melampaui 4 GB (`memory.max` cgroup breached).
2. **Investigasi Konsumsi Memori Off-Heap**:
   Sisa alokasi memori di luar heap 2 GB dikonsumsi oleh komponen internal JVM Non-Heap:
   - Metaspace (Class metadata).
   - Thread Stack (`-Xss`, misal: 1000 threads $\times$ 1MB = 1 GB).
   - JVM Internal (Garbage Collector data structures, Code Cache, JIT compilation).
   - Direct Byte Buffers / Netty off-heap buffer untuk I/O jaringan.
   *Langkah Pembuktian*:
   Aktifkan *Native Memory Tracking* (NMT) pada Java via opsi JVM:
   `-XX:NativeMemoryTracking=summary`
   Lalu lakukan dump via `jcmd <PID> VM.native_memory baseline` dan `jcmd <PID> VM.native_memory detail.diff`. Di sisi kernel, periksa log dmesg: `dmesg -T | grep -E '(killed process|oom_reaper)'`.
3. **Mitigasi Arsitektur**:
   - Di sisi Java: Batasi memori off-heap secara eksplisit menggunakan `-XX:MaxDirectMemorySize=512m`, batasi ukuran thread stack `-Xss256k` atau `-Xss512k`, dan batasi Metaspace `-XX:MaxMetaspaceSize=256m`.
   - Di sisi Container: Naikkan cgroup limit memory menjadi 5 GB untuk memberikan headroom aman bagi *native memory overhead*, atau turunkan `-Xmx` menjadi `1536m`.
</details>

---

### Skenario 3.2: "The Mystery of High System CPU and Lagging APIs"
**Konteks Masalah**:
Sebuah API gateway berbasis Go runtime yang menangani 30.000 RPS pada server bare-metal 64-core mengalami degradasi drastis: p99 latency melonjak dari 5ms ke 1.200ms. Hasil pengamatan metrik menunjukkan:
- CPU User Space (`%usr`): hanya 15%.
- CPU System Space (`%sys`): melonjak hingga 75%.
- Network ingress/egress masih jauh di bawah kapasitas bandwidth interface NIC.

**Pertanyaan Analisis**:
1. Apa indikasi utama di balik tingginya rasio `%sys` dibanding `%usr` pada arsitektur server Linux?
2. Bagaimana Anda menggunakan utilitas Linux Internals tingkat rendah untuk menemukan fungsi kernel spesifik yang memonopoli siklus CPU tersebut?
3. Sebutkan dua potensi bug internal sistem operasi / konfigurasi Go runtime yang paling sering memicu gejala ini!

<details>
<summary>Solusi & Panduan Investigasi</summary>

1. **Indikasi Teknis**:
   Rasio `%sys` yang mendominasi menunjukkan bahwa CPU menghabiskan sebagian besar siklus clock-nya untuk mengeksekusi instruksi di kernel space (Ring 0), bukan menjalankan logika kode aplikasi pengguna (Ring 3). Ini biasanya disebabkan oleh:
   - Terlalu tingginya frekuensi context switching antar thread.
   - Panggilan System Call yang tidak efisien dalam loop ketat.
   - Perebutan lock kernel tingkat rendah (*spinlocks*).
   - Page fault rate yang masif atau alokasi buffer kernel yang mengalami fragmentasi.
2. **Langkah Investigasi Presisi**:
   - Jalankan `perf top` langsung di server. Amati simbol teratas: jika didominasi oleh fungsi kernel seperti `native_queued_spin_lock_slowpath` atau `futex_*`, ini menandakan kontensi lock sinkronisasi. Jika didominasi oleh `page_fault` atau `copy_user_enhanced_fast_string`, masalah berada pada alokasi memori masif.
   - Analisis frekuensi syscall menggunakan eBPF tool `syscount`:
     `syscount -p $(pgrep gateway) -i 1`
   - Periksa context switch via `pidstat -w -p $(pgrep gateway) 1` (bandingkan `cswch/s` voluntary vs `nvcswch/s` involuntary).
3. **Penyebab Klasik Masalah Ini**:
   - **GOMAXPROCS Mismatch**: Go runtime secara default mengatur scheduler goroutine sesuai jumlah core fisik mesin (`GOMAXPROCS=64`). Jika gateway berjalan di dalam container dengan CPU quota kecil (misal: 2 core) namun runtime Go mendeteksi 64 core mesin host, puluhan scheduler OS thread (`M` di Go runtime) akan terus bersaing memperebutkan lock kernel via `futex()`.
   - **Connection Pool Exhaustion / Excessive Epoll Re-registration**: Kode gateway membuat koneksi HTTP baru untuk setiap request upstream tanpa pooling (memicu badai syscall `socket()`, `connect()`, `epoll_ctl()`, dan `close()` puluhan ribu kali per detik).
</details>

---

### Skenario 3.3: "The Silent Storage Lockup"
**Konteks Masalah**:
Sebuah cluster database PostgreSQL beroperasi di atas volume penyimpanan NVMe berkemampuan tinggi. Tiba-tiba seluruh query database mengalami *freeze* total selama rentang 15 hingga 20 detik tanpa ada query yang selesai. Ketika engineer mengecek metrik Prometheus, CPU utilization turun ke 1%, namun parameter Load Average melonjak drastis dari 4.0 menjadi 85.0.

Pengecekan process list via `ps aux` menunjukkan sebagian besar worker database berada dalam status `D`.

**Pertanyaan Analisis**:
1. Mengapa metrik Load Average dapat melonjak drastis sementara CPU Usage justru menurun mendekati 0%?
2. Bagaimana cara mengetahui titik ketersendatan (*bottleneck*) di dalam kernel Linux yang menyebabkan seluruh proses worker tertidur di status `D`?
3. Apa tindakan mitigasi yang harus dieksekusi pada konfigurasi virtual memory Linux?

<details>
<summary>Solusi & Panduan Investigasi</summary>

1. **Mekanisme Load Average di Linux**:
   Berbeda dengan OS Unix tradisional yang hanya menghitung proses runnable di CPU (`TASK_RUNNING`), metrik Linux Load Average memasukkan proses yang berada dalam status **`TASK_UNINTERRUPTIBLE` (`D-state`)**. Proses dalam status `D` sedang tidur menunggu event hardware (biasanya I/O storage) dan tidak dapat diinterupsi bahkan oleh `kill -9`. Akibatnya, jika puluhan worker database terhenti menunggu antrean I/O disk, CPU menjadi menganggur (CPU usage anjlok), namun Load Average melonjak drastis.
2. **Diagnostik Kernel Trace**:
   Periksa kernel call-trace dari salah satu PID yang tersangkut:
   `cat /proc/<PID_WORKER>/stack`
   Jika trace menunjukkan:
   `io_schedule` $\rightarrow$ `wait_on_page_writeback` $\rightarrow$ `balance_dirty_pages`
   Maka terbukti secara definitif bahwa kernel sedang mencegat worker tersebut di fungsi `balance_dirty_pages()` karena buffer dirty pages di RAM telah melewati ambang `vm.dirty_ratio`, memaksa worker mem-flush data kotor ke disk secara sinkron.
3. **Tindakan Mitigasi**:
   Turunkan batas dirty memory ke batas aman absolut pada `/etc/sysctl.conf`:
   ```ini
   vm.dirty_background_bytes = 134217728 # 128 MB (Mulai flush di latar belakang lebih awal)
   vm.dirty_bytes = 536870912            # 512 MB (Batas mutlak sebelum memblokir aplikasi)
   ```
   Lakukan apply langsung via `sysctl -p`.
</details>

---

## 4. Practical Chapter Challenge: "The Low-Latency Sandboxed Worker"

### Deskripsi Masalah Arsitektur
Anda diminta merancang arsitektur eksekusi lingkungan (*execution runtime*) untuk worker multi-tenant pemroses data finansial sensitif pada server Linux modern (kernel 5.15+).

### Persyaratan Teknis
1. **Isolasi Hierarki cgroups v2**:
   Buat otomasi skrip bash yang mengonfigurasi hirarki cgroup `/sys/fs/cgroup/fintech_worker`:
   - Batas hard memori: 1 GB (`memory.max`).
   - Batas soft throttling memori: 800 MB (`memory.high`).
   - Batas CPU: Maksimal 2 core penuh (`200000 100000` pada `cpu.max`).
   - Isolasi I/O disk: Batasi write rate maksimal ke hard drive root/storage menjadi 10 MB/s (`io.max`).
2. **Mitigasi OOM Deterministik**:
   Aktifkan opsi agar jika ada satu child proses worker yang memicu OOM Killer di dalam cgroup ini, **seluruh proses worker lain dalam cgroup tersebut harus dimatikan secara serentak** (`memory.oom.group`) untuk mencegah fragmentasi data finansial setengah jalan.
3. **Observabilitas Zero-Overhead**: