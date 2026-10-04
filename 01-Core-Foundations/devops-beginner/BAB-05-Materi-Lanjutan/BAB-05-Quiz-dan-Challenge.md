# BAB 05: Quiz, Challenge, & Knowledge Check
**Kontainerisasi Aplikasi Modern Menggunakan Docker**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Primitif Isolasi Kernel Linux (Namespaces vs. Control Groups):**  
   Jelaskan secara mendalam bagaimana Linux Kernel menyediakan ilusi isolasi pada Docker container! Bedah perbedaan mendasar antara fungsi **Linux Namespaces** (sebutkan minimal 4 jenis namespace beserta apa yang diisolasinya) dan **Control Groups (cgroups v1/v2)** dalam membatasi serta memantau konsumsi sumber daya komputasi.

2. **Arsitektur Image, Layering, dan Storage Driver (OverlayFS):**  
   Bagaimana mekanisme *Copy-on-Write* (CoW) bekerja saat sebuah container aktif memodifikasi file yang berasal dari base image read-only? Jelaskan struktur layer pada Docker image (*lowerdir*, *upperdir*, *workdir*, dan *merged*) pada storage driver `overlay2`, serta jelaskan konsekuensi performa I/O jika container menulis data langsung ke layer writable dibandingkan menggunakan Docker Volume.

3. **Komparasi Fundamental: Hypervisor Virtualization vs. Containerization:**  
   Ditinjau dari perspektif *system call table*, *context switching overhead*, dan manajemen memori kernel: Mengapa container memiliki startup time dalam orde milidetik serta densitas beban kerja yang jauh lebih tinggi dibandingkan Type-1 maupun Type-2 Hypervisor? Apa trade-off keamanan terbesar dari pendekatan *shared-kernel* ini?

4. **Sintaksis Dockerfile: ENTRYPOINT vs. CMD dan Mekanisme Sinyal:**  
   Uraikan perbedaan fungsional antara instruksi `ENTRYPOINT` dan `CMD` saat digunakan dalam format *exec form* (`["executable", "param"]`) dibandingkan *shell form* (`executable param`). Mengapa penggunaan *shell form* dapat menyebabkan container mengabaikan sinyal penghentian (`SIGTERM`) dari Docker daemon, sehingga memicu *unclean shutdown* via `SIGKILL` setelah batas waktu *graceful timeout* terlewati?

5. **Arsitektur Jaringan Docker: Bridge Network Implementation:**  
   Ketika sebuah container dijalankan dengan driver jaringan default `--network bridge`, bagaimana Docker daemon merekayasa jaringan host menggunakan *virtual ethernet pairs* (`veth`), Linux Network Bridge (`docker0`), dan manipulasi aturan `iptables` (NAT/MASQUERADE)? Jelaskan alur paket TCP dari IP publik host hingga mencapai port internal container.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Masalah Zombie Reaping dan PID 1 Inisialisasi:**  
   Di sistem operasi Linux standar, proses PID 1 (`systemd`/`init`) bertugas mengadopsi dan membersihkan proses anak yang berstatus *zombie/defunct* (`wait()` syscall). Ketika aplikasi Node.js atau Python berjalan langsung sebagai PID 1 di dalam container tanpa init system (seperti `tini` atau `dumb-init`), kegagalan sistemik apa yang akan terjadi seiring berjalannya waktu jika aplikasi melakukan `fork()` child processes? Bagaimana cara mendeteksi dan mengatasinya?

2. **OOMKilled Triage (Exit Code 137) dan cgroup Memory Limits:**  
   Sebuah container backend Java (JVM) mati mendadak dengan status `Exit Code 137` (OOMKilled) meskipun alokasi memory limit container diatur ke 2GB dan parameter `-Xmx` diset ke 1.8GB. Jelaskan interaksi antara Linux OOM Killer dengan batas memori cgroup. Bagian memori JVM mana (*off-heap*, *metaspace*, *thread stack*) yang menjadi blind spot jika hanya mengandalkan flag `-Xmx`, dan bagaimana konfigurasi cgroup-aware JVM (`-XX:+UseContainerSupport`) memitigasi hal ini?

3. **Mekanisme Invalidation Build Cache dan Optimalisasi Ukuran Image:**  
   Diberikan potongan instruksi Dockerfile berikut:
   ```dockerfile
   FROM node:20-alpine
   WORKDIR /app
   COPY . .
   RUN npm install
   CMD ["node", "server.js"]
   ```
   Analisis mengapa struktur instruksi di atas sangat buruk ditinjau dari algoritma caching layer Docker. Bagaimana seharusnya urutan instruksi diubah untuk memaksimalkan layer reusability, dan teknik apa saja yang harus diterapkan untuk memangkas *attack surface* serta binary bloat (e.g., *Multi-Stage Builds*, `.dockerignore`, strip toolchains)?

4. **Debugging Network Packet Drop dan Port Forwarding Flaws:**  
   Container API Anda berjalan dan berstatus `Up (healthy)`, port mapping dideklarasikan `-p 8080:8080`, namun akses dari host via `curl http://localhost:8080` selalu menghasilkan error `Connection refused`. Namun, eksekusi `docker exec -it <container_id> curl http://localhost:8080` berhasil merespons 200 OK. Lakukan root cause analysis struktural terhadap konfigurasi binding IP interface aplikasi (0.0.0.0 vs 127.0.0.1) di dalam container!

5. **Container Security Posture: Privileged Mode vs. Granular Linux Capabilities:**  
   Mengapa menjalankan container dengan flag `--privileged` merupakan pelanggaran fatal dalam arsitektur keamanan *defense-in-depth*? Jelaskan bagaimana seorang penyerang dapat melakukan *container breakout* (ekspansi akses ke host filesystem) dari container `--privileged`. Alternatif apa yang disediakan oleh Docker untuk memberikan izin spesifik (misalnya: memanipulasi network route atau routing table) menggunakan `--cap-add` tanpa membuka seluruh kontrol kernel?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Disk Space Exhaustion Massal Akibat Logging Driver dan Layer Leak
* **Kasus:**  
  Di sebuah cluster produksi yang menjalankan 40 host Docker mandiri, 12 server mendadak mengalami *system lock-up* dengan alarm monitoring: `No space left on device` (Disk 100% full, inode exhaustion). Tim operasi tidak dapat melakukan deploy container baru, dan service database crash akibat kegagalan alokasi disk. Saat dicek via `df -h`, direktori `/var/lib/docker/overlay2` dan `/var/lib/docker/containers/` menyerap 95% dari volume SSD berkapasitas 1TB.
* **Pertanyaan Diagnostik:**
  1. Identifikasi dua faktor penyebab utama yang menyebabkan akumulasi data masif di kedua direktori tersebut! Mengapa konfigurasi default Docker (`json-file` tanpa rotasi) bertanggung jawab atas hal ini?
  2. Susun prosedur mitigasi darurat untuk membebaskan ruang disk tanpa mematikan container bisnis kritikal yang sedang berjalan!
  3. Rancang arsitektur preventif permanen di file `/etc/docker/daemon.json` untuk manajemen log (log-driver, max-size, max-file) serta policy pruning layer berbasis cron/automation agent.

### Skenario B: Race Condition dan File Lock Degradation pada Stateful Container via Shared Storage
* **Kasus:**  
  Sebuah sistem antrean transaksi finansial bermigrasi ke container. Untuk menjamin persistensi, developer menggunakan *bind mount* langsung dari direktori lokal host (`-v /mnt/nfs/shared-data:/app/data`) yang terhubung ke Network File System (NFS v4). Ketika beban transaksi mencapai puncak (5.000 req/sec terdistribusi ke 5 container identik pada host yang berbeda), data file index sqlite/leveldb mengalami korupsi parah (*malformed disk image*), dan latensi disk I/O melonjak hingga 4.000 ms.
* **Pertanyaan Diagnostik:**
  1. Dari sudut pandang atomic file-locking POSIX kernel (`flock`/`fcntl`) dan network latency overhead, mengapa penggunaan shared file-system (NFS) untuk file database internal stateful container sangat fatal?
  2. Jelaskan perbedaan isolasi I/O antara *Named Docker Volumes* lokal dengan driver `local` versus *Bind Mounts* dari network filesystem.
  3. Bagaimana rekomendasi arsitektur penyimpanan data yang seharusnya diimplementasikan untuk beban kerja transaksional stateful berkonsumsi I/O tinggi dalam container?

### Skenario C: Hardening Arsitektur Container untuk Aplikasi Perbankan Berstandar PCI-DSS
* **Kasus:**  
  Anda ditugaskan sebagai Lead Infrastructure Architect untuk merancang baseline standardisasi container image aplikasi pembayaran mikroservis berbasis Go dan Python yang harus lolos audit PCI-DSS v4.0. Hasil scan trivy/snyk pada image lama menunjukkan 450+ CVE (tingkat High/Critical), container berjalan dengan user `root` (UID 0), binary package manager (`apt`/`apk`) masih terpasang, serta container filesystem bersifat read-write penuh.
* **Pertanyaan Diagnostik:**
  1. Rancang blueprint Dockerfile berbasis *Distroless* atau *Scratch* untuk runtime Go, dan jelaskan mengapa ketiadaan package manager, shell (`/bin/sh`), dan utilitas OS dasar mematikan *kill-chain* peretas!
  2. Konfigurasi runtime security flag apa saja yang wajib ditambahkan pada perintah `docker run` atau spesifikasi compose (`read_only`, `user`, `no-new-privileges`, `drop-capabilities`) untuk mengunci filesystem serta privasi eksekusi proses?
  3. Bagaimana strategi penanganan secret runtime (API keys, database credentials) agar tidak pernah bocor ke dalam image layer metadata saat fase `docker build`?

---

## 4. Chapter Challenge

### Tantangan Praktis: Multi-Stage Enterprise Build, Hardening, & Resource-Constrained Stack
Anda diminta untuk membangun dan mengamankan deployment stack microservice lokal yang terdiri dari REST API berbasis Go, Worker background berbasis Node.js, dan Redis Cache dengan spesifikasi produksi enterprise tanpa celah keamanan mendasar.

#### 1. Problem Statement
Banyak tim engineering mendeploy image mentah (*fat images*) yang berisi compiler tools, berjalan sebagai root, dan tidak memiliki batasan memori sehingga rentan terhadap eksploitasi dan saling mematikan resource aplikasi lain saat terjadi *memory leak*.

#### 2. Requirements & Architecture
* **Komponen 1 (API Service - Go):**
  * Wajib menggunakan **Multi-Stage Build**. Stage builder menggunakan `golang:1.22-alpine` untuk kompilasi binary statis (CGO_ENABLED=0).
  * Stage runtime **wajib** menggunakan `gcr.io/distroless/static-debian12:nonroot` atau minimal image `scratch` dengan user non-root (UID 10001).
  * Ukuran image final tidak boleh melebihi **30 MB**.
* **Komponen 2 (Worker Service - Node.js):**
  * Menggunakan multi-stage build: builder menginstal dependency (termasuk devDependencies jika diperlukan transpilasi), sedangkan production stage hanya memuat `node_modules` production (`npm prune --production`).
  * Base image runtime: `node:20-alpine`.
  * Container tidak boleh berjalan sebagai UID 0; gunakan built-in user `node` (UID 1000).
  * Harus mengimplementasikan `tini` atau node native `--enable-source-maps` untuk penanganan sinyal PID 1 yang sempurna.
* **Komponen 3 (Data Store - Redis):**
  * Menggunakan image resmi `redis:7-alpine`.
  * Dikonfigurasi menggunakan volume bernama (*named volume*) untuk persistensi Append-Only File (AOF).
* **Komposisi Sistem (`docker-compose.yml`):**
  * Semua service terisolasi dalam *custom user-defined bridge network* dengan subnet privat eksplisit. Service Redis tidak boleh mengekspos port ke sistem host (`ports:` dilarang, hanya gunakan `expose:` internal).
  * Batasi sumber daya setiap service secara ketat:
    * Go API: CPU limit 0.5, Mem limit 128MB.
    * Node Worker: CPU limit 0.5, Mem limit 256MB.
    * Redis: CPU limit 0.25, Mem limit 128MB.
  * Tetapkan `healthcheck` native pada setiap service untuk mendeteksi kesiapan dan kesehatan aplikasi.
  * Terapkan logging driver bawaan dengan rotasi log: `max-size: 10m` dan `max-file: 3`.

#### 3. Constraints
* Dilarang keras menggunakan flag `privileged: true`.
* Root filesystem pada runtime container Go API dan Node Worker harus diatur ke kondisi **Read-Only** (`read_only: true`). Direktori temporer yang mutlak dibutuhkan untuk penulisan cache/log harus dialokasikan via in-memory storage (`tmpfs`).
* Seluruh deklarasi secret tidak boleh di-hardcode ke dalam Dockerfile maupun commit langsung di compose file; gunakan mechanism environment variables file (`.env`) yang ditandai gitignore.

#### 4. Expected Output
1. File `Dockerfile.api` dan `Dockerfile.worker` yang lolos uji linter (`hadolint`) tanpa warning kritikal.
2. File `docker-compose.yml` yang memenuhi seluruh kriteria isolasi, resource limit, dan network isolation.
3. Eksekusi `docker inspect` yang membuktikan bahwa container berjalan sebagai non-root, memori terikat sesuai spesifikasi, dan filesystem dalam kondisi read-only.
4. Uji simulasi terminasi: `docker compose stop` membuktikan bahwa seluruh kontainer menerima dan merespons `SIGTERM` secara graceful tanpa adanya paksaan kill timeout (Exit Code 0, bukan 137).

---

## 5. Knowledge Check & Checklist

Verifikasi kesiapan pemahaman materi kontainerisasi sebelum melanjutkan ke bab orkestrasi container (*Container Orchestration with Kubernetes*):

### Saya harus memahami:
- [ ] Peran dan perbedaan absolut antara Linux Namespaces (PID, Mount, Net, IPC, UTS, User) dan cgroups (v1 vs v2) dalam isolasi container.
- [ ] Cara kerja Copy-on-Write (CoW) pada driver penyimpanan OverlayFS (lowerdir, upperdir, merged).
- [ ] Anatomi sinyal Linux (khususnya `SIGTERM`, `SIGINT`, dan `SIGKILL`) serta mengapa PID 1 di container wajib mengelola signal propagation dan zombie process reaping.
- [ ] Mengapa kontainerisasi bukan virtualisasi perangkat keras (perbedaan shared kernel vs hypervisor hardware emulation).
- [ ] Dampak keamanan menjalankan proses di dalam container sebagai user `root` (UID 0) terhadap host kernel.
- [ ] Perbedaan fungsional antara Container Storage Types: Volume, Bind Mount, dan `tmpfs`.
- [ ] Cara Docker mengelola packet routing dan virtual interface (`veth`) via aturan kernel `iptables`.

### Saya tidak perlu menghafal:
- [ ] Seluruh flag CLI dari perintah `docker` (fokuslah pada memahami cara membaca output `docker inspect`, `docker logs`, `docker stats`, dan flag-flag core).
- [ ] Struktur byte internal tarball layer image OCI (Open Container Initiative).
- [ ] Algoritma internal sistem hash SHA-256 yang digunakan Docker untuk penamaan Content Addressable Storage (CAS).

### Saya harus bisa melakukan:
- [ ] Menulis Dockerfile dengan pola Multi-Stage Build untuk memisahkan stage kompilasi dari stage runtime.
- [ ] Mengurangi ukuran image seminimal mungkin menggunakan teknik image hardening (*distroless*, alpine, stripping binaries, `.dockerignore`).
- [ ] Mengonfigurasi dan mengamankan container runtime dengan parameter non-root user, dropped capabilities (`--cap-drop=ALL`), dan read-only root filesystems.
- [ ] Mengatur batasan CPU dan Memory pada container serta mendiagnosis error OOMKilled via Linux `dmesg` atau inspect status container.
- [ ] Menulis file `docker-compose.yml` yang memetakan user-defined bridge network, port exposure yang aman, resource limits, volume mounts, dan dependensi startup via `healthcheck`.
- [ ] Melakukan troubleshooting jaringan antar-container menggunakan container debugging utility (`curl`, `nslookup`, `tcpdump`) di dalam isolated namespaces.