# BAB 10: Quiz, Challenge, & Knowledge Check
**Containerization, Testing, & Enterprise Deployment**

---
## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Isolasi Linux Kernel vs Virtual Machine:**
   Jelaskan secara mendalam bagaimana Linux Kernel mengisolasi proses menggunakan *Namespaces* (sebutkan minimal 4 jenis namespace beserta fungsinya) dan *Control Groups* (cgroups v2). Mengapa kontainer Docker bukanlah sebuah "Virtual Machine ringan", dan apa implikasi keamanannya jika sebuah kontainer berjalan dengan flag `--privileged`?

2. **Anatomi Pyramida Pengujian & Determinisme:**
   Bandingkan karakteristik *Unit Test*, *Integration Test*, dan *End-to-End (E2E) Test* dalam konteks eksekusi sistem backend terdistribusi. Mengapa pengujian yang melibatkan database relasional riil sering kali menghasilkan *flaky tests*, dan bagaimana strategi isolasi status (*state isolation*) yang tepat untuk menjamin pengujian bersifat deterministik dan *idempotent*?

3. **Mekanisme Semantik Liveness vs Readiness Probe:**
   Pada orkestrasi kontainer (seperti Kubernetes atau AWS ECS), jelaskan perbedaan mendasar antara *Readiness Probe* dan *Liveness Probe*. Apa bencana arsitektural (*cascading failure*) yang akan terjadi jika sebuah *Liveness Probe* dikonfigurasi untuk mengecek ketersediaan database eksternal (*downstream dependency*)?

4. **Multi-Stage Docker Builds & Reduksi Attack Surface:**
   Bagaimana cara kerja mekanisme *layer caching* pada OCI (Open Container Initiative) image engine? Analisis bagaimana teknik *Multi-Stage Build* tidak hanya mereduksi ukuran artefak dari ratusan megabyte menjadi hitungan puluhan megabyte, tetapi juga memitigasi vektor serangan keamanan (*CVE surface reduction*) di lingkungan produksi.

5. **Siklus Hidup Graceful Shutdown:**
   Jelaskan urutan kejadian (*event sequence*) mikro ketika OS mengirimkan sinyal `SIGTERM` ke aplikasi backend di dalam kontainer hingga diterimanya sinyal `SIGKILL`. Mengapa mengabaikan penanganan `SIGTERM` secara eksplisit dapat menyebabkan *HTTP 502 Bad Gateway* atau data korup pada koneksi TCP yang sedang aktif?

---
## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Masalah PID 1 dan Sub-Process Reaping:**
   Ketika aplikasi dieksekusi di dalam kontainer tanpa *init system* (seperti `tini` atau `dumb-init`) dan berjalan langsung sebagai `PID 1`, jelaskan fenomena *Zombie Process Accumulation*. Mengapa *signal routing* (seperti `SIGINT` dan `SIGTERM`) sering kali gagal diterima oleh *child processes* yang di-spawn oleh runtime aplikasi Anda?

2. **Invalidasi Cache Dockerfile dan Layer Ordering Trap:**
   Diberikan struktur instruksi Dockerfile berikut:
   ```dockerfile
   FROM golang:1.22-alpine
   WORKDIR /app
   COPY . .
   RUN go mod download
   RUN go build -o main .
   CMD ["./main"]
   ```
   Bedah mengapa urutan instruksi di atas merupakan anti-pattern fatal dalam siklus CI/CD modern. Bagaimana Anda merekonstruksi tahapan *layering* tersebut agar proses download dependensi tidak dieksekusi ulang setiap kali terjadi perubahan kode bisnis mikro?

3. **Data Isolation Strategy: Transaction Rollback vs Ephemeral Containers:**
   Dalam pengujian integrasi database, beberapa tim memilih membungkus setiap pengujian dalam database transaction dan melakukan `ROLLBACK` di akhir pengujian, sementara tim lain memilih *Ephemeral Testcontainers* (kontainer database baru per *test suite*). Analisis batas kegagalan arsitektur dari pendekatan `ROLLBACK` ketika menguji sistem yang menggunakan *nested transactions*, *asynchronous background workers*, atau level isolasi *READ UNCOMMITTED*!

4. **Expand and Contract Pattern pada Database Migration:**
   Saat melakukan *Rolling Zero-Downtime Deployment*, aplikasi versi $N$ dan versi $N+1$ akan berjalan secara simultan dalam jangka waktu tertentu. Bagaimana cara mengaplikasikan pola arsitektur *Expand and Contract* (Parallel Run) ketika Anda harus mengganti nama kolom penting pada tabel dengan miliaran baris tanpa mengunci tabel (*table lock*) dan tanpa memicu *fatal error* pada aplikasi versi $N$?

5. **Container Networking, Ephemeral Ports, dan Conntrack Exhaustion:**
   Saat ratusan kontainer mikroservis berkomunikasi intensif melalui Docker Bridge Network menggunakan HTTP/1.1 tanpa *Connection Keep-Alive*, sistem tiba-tiba mengalami *latency spike* ekstrem dan kegagalan resolusi koneksi sementara CPU/Memory masih rendah. Jelaskan secara teknis apa yang terjadi pada *Linux conntrack table*, *TIME_WAIT sockets*, dan alokasi *ephemeral port*!

---
## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: The Cascading Death Loop (CrashLoopBackOff di Kubernetes)
Sebuah rilis baru dideploy menggunakan strategi *Rolling Update* di Kubernetes cluster. Aplikasi backend memiliki konkurensi tinggi. Tim DevOps mengonfigurasi *Liveness Probe* dengan endpoint `/healthz` yang melakukan query `SELECT 1` ke database PostgreSQL utama dengan `timeoutSeconds: 1` dan `failureThreshold: 3`. 

Pada jam sibuk, database mengalami kenaikan beban transaksional sesaat (*transient spike*) yang menyebabkan latensi query naik dari 10ms menjadi 1200ms. Seketika, satu per satu pod ditandai *unhealthy* dan di-*restart* paksa oleh Kubelet. Akibatnya, seluruh trafik beralih ke pod yang tersisa, membuat pod yang tersisa kelebihan beban dan gagal pada probe yang sama, hingga seluruh cluster mengalami pemadaman total (*total outage*).
*   **Pertanyaan Diagnostik:**
    1. Analisis mengapa konfigurasi probe tersebut melanggar prinsip desentralisasi kegagalan (*fault isolation*).
    2. Rancang ulang arsitektur endpoint pemeriksaan kesehatan: Bedakan secara spesifik apa yang harus diperiksa oleh `/livez`, `/readyz`, dan `/startupz` untuk mencegah terulangnya insiden ini!

### Skenario B: Race Condition & Data Corruption Pasca-Switchover Deployment
Sebuah platform *e-commerce* menerapkan *Blue/Green Deployment*. Versi aplikasi *Blue* (aktif) dan *Green* (kandidat) sama-sama membaca antrean *order processing* dari Apache Kafka yang sama dengan *Consumer Group ID* identik. 

Sebelum DNS router dialihkan dari Blue ke Green, *pipeline* CI/CD menyalakan kontainer Green secara penuh. Dalam kurun waktu 5 menit sebelum pengalihan trafik HTTP, sistem mencatat ribuan pesanan diproses dua kali, saldo pengguna terpotong ganda, dan terjadi *deserialization error* pada event schema baru yang belum di-commit secara permanen.
*   **Pertanyaan Diagnostik:**
    1. Identifikasi kegagalan fatal dalam manajemen dependensi *stateful/event-driven* pada strategi deployment tersebut.
    2. Bagaimana arsitektur *deployment pipeline* harus dirancang ketika sebuah backend bertindak sebagai *HTTP Web Server* sekaligus *Background Event Consumer* agar transisi Blue/Green berjalan tanpa duplikasi maupun kehilangan event?

### Skenario C: CI Pipeline Bottleneck: Mocking vs Testcontainers
Sebuah perusahaan SaaS memiliki lebih dari 80 *microservices*. Sebelumnya, unit test menggunakan *in-memory mock* berjalan sangat cepat (total pipeline CI: 3 menit), namun banyak *bug* lolos ke lingkungan *staging* karena perbedaan perilaku driver database SQLite (in-memory) dengan PostgreSQL produksi. 

Tim memutuskan beralih secara radikal mewajibkan *Testcontainers* (menyalakan Postgres, Redis, dan Kafka riil via Docker) untuk seluruh rangkaian pengujian di CI. Hasilnya, reliabilitas pengujian naik drastis, tetapi durasi eksekusi CI pipeline melonjak dari 3 menit menjadi 58 menit per *pull request*, memicu antrean antre panjang pada *runner* CI dan melumpuhkan produktivitas tim rekayasa perangkat lunak.
*   **Pertanyaan Diagnostik:**
    1. Lakukan *trade-off analysis* antara kecepatan umpan balik (*developer feedback loop*) versus tingkat keyakinan (*confidence level*) dalam konteks ini.
    2. Rekomendasikan arsitektur *testing pyramid* dan optimasi CI/CD terstruktur (meliputi teknik *parallelization*, *container reuse*, *caching*, dan *test stratification*) yang mampu memotong durasi kembali ke bawah 10 menit tanpa mengorbankan integritas pengujian PostgreSQL!

---
## 4. Chapter Challenge

### Tantangan Praktis: Production-Grade Containerization, Deterministic Integration Pipeline, & Zero-Downtime Deployment Lifecycle Engine

#### Problem:
Sebuah aplikasi backend monolitik berbasis HTTP REST API memiliki masalah reliabilitas: kontainer berjalan menggunakan user `root`, image berukuran 1.2 GB yang sarat *vulnerability*, sering *drop connection* saat proses restart/deployment, dan memiliki *integration test* yang tidak deterministik karena mengandalkan database lokal yang sudah terisi data kotor (*dirty state*).

#### Requirements:
1. **Hardened Multi-Stage Dockerfile:**
   - Gunakan pendekatan multi-stage build.
   - Stage kompilasi/build harus terpisah total dari stage runtime.
   - Runtime image berbasis `distroless` atau `alpine` minimal (target ukuran image final: < 50 MB untuk Go/Rust, atau < 150 MB untuk Node.js/JVM teroptimasi).
   - Eksekusi aplikasi wajib menggunakan non-root user eksplisit (misal `UID 10001`).
   - Terapkan alokasi cache layer yang optimal untuk package dependency manager.

2. **Deterministic Testcontainer-Based Integration Suite:**
   - Bangun skrip pengujian integrasi yang mengeksekusi *lifecycle* pengetesan menggunakan library ephemeral container (misal: *Testcontainers* atau custom Docker orchestration via test script).
   - Skrip harus:
     1. Menyalakan database container baru dari *clean state*.
     2. Menjalankan migrasi database otomatis (*schema migration*).
     3. Mengeksekusi pengetesan skenario CRUD secara paralel dengan isolasi data sempurna antar-test-case.
     4. Menjamin *teardown* dan pembersihan kontainer secara deterministik, bahkan jika skrip pengetesan mengalami *panic* atau *crash*.

3. **Production Graceful Lifecycle Engine:**
   - Implementasikan *signal handler* di aplikasi untuk menangani `SIGTERM` dan `SIGINT`.
   - Ketika sinyal diterima:
     1. Ubah status *Readiness Probe* internal menjadi *unhealthy* (agar orkestrator berhenti merutekan trafik baru).
     2. Berikan jeda toleransi (*grace period delay*, misal 5-10 detik) untuk mengakomodasi pembaruan tabel routing load balancer.
     3. Selesaikan semua request HTTP yang sedang berjalan (*in-flight requests*) dengan timeout ketat (misal 30 detik).
     4. Tutup pool koneksi database dan background worker secara berurutan (*clean termination*).
     5. Keluar (*exit*) dengan status code 0.

#### Constraints:
*   Tidak boleh menggunakan library pihak ketiga *magic framework* untuk graceful shutdown (tuliskan implementasi native menggunakan standar library bahasa pemrograman Anda).
*   Zero dropped connections: Simulasikan beban konstan (misal menggunakan tool benchmarking seperti `k6`, `hey`, atau `wrk`) saat proses shutdown/restart kontainer berlangsung; tidak boleh ada status return selain `2xx` (bebas dari `502 Bad Gateway` atau *connection reset by peer*).
*   Database migrasi tidak boleh dijalankan di dalam *entrypoint* runtime container utama pada skala produksi.

#### Expected Output:
1. File `Dockerfile` yang telah di-hardening dan teroptimasi.
2. File kode penanganan sinyal OS dan siklus *graceful shutdown* lengkap dengan log audit proses termination.
3. Test suite integrasi yang dapat dieksekusi secara terisolasi tanpa dependensi database eksternal yang sudah menyala sebelumnya.
4. Laporan hasil uji latensi dan error rate selama proses deployment kontainer di bawah beban traffic HTTP.

---
## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan fundamental antara isolasi Linux OS-level virtualization (cgroups, namespaces, seccomp) dan hardware-level virtualization (Hypervisor).
- [ ] Dampak arsitektural dari *Layer Caching* pada Dockerfile terhadap efisiensi storage registry dan kecepatan deployment pipeline.
- [ ] Bahaya keamanan menjalankan kontainer dengan user `root` serta prinsip least-privilege pada kontainer Linux.
- [ ] Perbedaan fungsional dan implikasi sistem dari *Liveness*, *Readiness*, dan *Startup Probes*.
- [ ] Konsep *Expand and Contract* (Parallel Run) dalam merancang evolusi skema database tanpa *downtime*.
- [ ] Urutan siklus hidup proses saat menerima `SIGTERM`, waktu drain koneksi, hingga eksekusi `SIGKILL`.
- [ ] Kelemahan dan batas toleransi pengujian menggunakan *mocking* dibandingkan dengan *ephemeral test environments*.

### Saya tidak perlu menghafal:
- [ ] Seluruh flag CLI sintaks baris perintah Docker atau Podman yang jarang digunakan (misal detail opsi `--device-write-bps`).
- [ ] Seluruh konfigurasi API Manifest Kubernetes secara verbatim di luar blok spesifikasi *probe* dan *lifecycle*.
- [ ] Seluruh kode internal implementasi driver Docker storage (seperti `overlay2`, `btrfs`, atau `vfs`).

### Saya harus bisa melakukan:
- [ ] Menulis *Multi-Stage Dockerfile* produksi yang aman, berukuran minimal, dan menggunakan non-root user.
- [ ] Mengonfigurasi layer Dockerfile secara presisi untuk memaksimalkan *cache hit* dependensi kode.
- [ ] Mengimplementasikan *Graceful Shutdown* native yang menutup koneksi database, HTTP server, dan background worker secara elegan tanpa *drop connection*.
- [ ] Menulis pengujian integrasi deterministik menggunakan *Testcontainers* atau database terisolasi tanpa kebocoran status data antar-pengujian.
- [ ] Menganalisis log kontainer dan *exit code* kernel (seperti `OOMKilled - Exit Code 137`) untuk melakukan troubleshooting crash pada container runtime.