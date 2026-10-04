# BAB 01: Quiz, Challenge, & Knowledge Check
**Fondasi dan Arsitektur Docker Engine**

---

## 1. Basic Questions (5 Soal Fundamental & Konseptual)

### Soal 1.1: Virtualisasi Hypervisor (Hardware-Level) vs. Containerization (OS-Level)
Virtualisasi tradisional mengandalkan Hypervisor (Type 1 bare-metal atau Type 2 hosted) untuk mengemulasikan perangkat keras fisik, sedangkan containerization memanfaatkan isolasi pada tingkat sistem operasi.
* Jelaskan perbedaan struktural eksekusi instruksi antara aplikasi yang berjalan di dalam Virtual Machine (VM) dengan aplikasi di dalam Linux Container terkait interaksi terhadap CPU host dan kernel Linux!
* Mengapa container tidak memerlukan proses booting Guest OS tersendiri, dan apa konsekuensinya terhadap kompatibilitas lintas sistem operasi (misalnya menjalankan container biner ELF Linux native di atas kernel Windows atau macOS secara langsung tanpa virtualisasi perantara)?

### Soal 1.2: Anatomi dan Taksonomi Linux Namespaces
Container pada dasarnya adalah proses Linux standar yang dibatasi ruang pandangnya (*visibility isolation*) menggunakan primitif kernel yang disebut **Linux Namespaces**.
* Uraikan fungsi isolasi spesifik yang disediakan oleh 7 subsistem Linux Namespaces berikut:
  1. `PID (Process ID)`
  2. `NET (Network)`
  3. `MNT (Mount)`
  4. `IPC (Inter-Process Communication)`
  5. `UTS (UNIX Timesharing System)`
  6. `USER (User IDs and Group IDs)`
  7. `TIME (Time Namespace)`
* Apa *system call* kernel (`clone`, `unshare`, `setns`) yang dipanggil saat container baru diinisialisasi untuk memisahkan struktur namespace dari proses induk (*parent process*) di host?

### Soal 1.3: Mekanisme Kontrol Sumber Daya: cgroups v1 vs. cgroups v2
Jika namespaces mengisolasi **apa yang dapat dilihat** oleh suatu proses, maka Control Groups (cgroups) membatasi **berapa banyak sumber daya yang dapat dikonsumsi** oleh proses tersebut.
* Jelaskan perbedaan arsitektural antara cgroups v1 (*multi-hierarchy per-controller*) dan cgroups v2 (*unified single-hierarchy tree*) yang berpusat di `/sys/fs/cgroup`!
* Sebutkan file kontrol cgroups v2 yang bertanggung jawab mengatur:
  1. Batas maksimum memori fisik (*hard limit*).
  2. Alokasi kuota CPU (*CPU quota and period*).
  3. Prioritas penulisan/pembacaan blok I/O disk (*I/O weight/throttling*).

### Soal 1.4: Arsitektur Storage Driver: OverlayFS dan Prinsip Copy-on-Write (CoW)
Docker mengandalkan Union File System (UnionFS), khususnya driver penyimpanan `OverlayFS`, untuk menyusun image berlapis-lapis (*layered image*) secara efisien.
* Jelaskan peran dan karakteristik dari 4 direktori struktural pada mount OverlayFS:
  1. `lowerdir` (Read-Only layers)
  2. `upperdir` (Container Read-Write layer)
  3. `workdir` (Atomic storage staging area)
  4. `merged` (Unified VFS mount point)
* Bagaimana mekanisme **Copy-on-Write (CoW)** bekerja saat sebuah proses di dalam container memodifikasi file berukuran besar yang berasal dari `lowerdir`? Apa yang dimaksud dengan *whiteout file* (`char device 0,0`) ketika proses menghapus file yang ada di layer image dasar?

### Soal 1.5: Dekonstruksi Arsitektur OCI Runtime Stack
Docker modern tidak lagi berbentuk monolit raksasa, melainkan arsitektur berlapis yang mematuhi standar Open Container Initiative (OCI).
* Petakan alur eksekusi saat pengguna mengetik perintah `docker run -d --name web nginx`:
  1. Peran `Docker CLI` dalam mengirimkan *payload request*.
  2. Peran Docker Daemon (`dockerd`) dan komunikasinya via UNIX Socket `/var/run/docker.sock`.
  3. Peran `containerd` sebagai container supervisor.
  4. Peran `containerd-shim-v2` dalam lifecycle manajemen proses.
  5. Peran `runc` sebagai referensi implementasi OCI runtime tingkat rendah (*low-level runtime*).

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Hardening)

### Soal 2.1: Lifecycle Eksekusi OCI & Peran containerd-shim-v2
Pada arsitektur Docker terdahulu, apabila daemon Docker mengalami crash atau di-restart, seluruh container yang berjalan akan ikut mati (*hard crash*).
* Jelaskan mengapa proses `runc` langsung melakukan terminasi (`exit`) segera setelah proses aplikasi utama container berhasil di-fork dan di-exec!
* Apa fungsi kritis dari `containerd-shim-v2` yang tetap berjalan mendampingi container? Mengapa keberadaannya memungkinkan fitur **Live Restore** (kemampuan me-restart `dockerd`/`containerd` tanpa memutus koneksi stdin/stdout/stderr maupun mematikan proses container)?

### Soal 2.2: Fenomena PID 1 Zombie Reaping & Penanganan Sinyal POSIX
Di dalam Linux namespace, proses pertama yang dijalankan menjadi **PID 1** di dalam container tersebut.
* Mengapa proses yang berjalan sebagai PID 1 di dalam namespace memiliki perlakuan kernel khusus terhadap sinyal POSIX (`SIGTERM` dan `SIGINT`) dibandingkan proses biasa?
* Apa yang terjadi apabila proses PID 1 di container berupa aplikasi runtime (seperti Node.js atau Python tanpa supervisor) yang men-spawn banyak proses anak (*child processes*), lalu proses anak tersebut mati mendahului induknya? Jelaskan konsep **Zombie Process Reaping** dan peran init system ringan seperti `tini` atau flag `--init` pada Docker!

### Soal 2.3: User Namespace Remapping & Komparasi Rootless Container
Secara default, user `root (UID 0)` di dalam container memiliki identitas numerik yang identik dengan user `root (UID 0)` pada host kernel, dibatasi hanya oleh Linux Capabilities dan Seccomp.
* Bagaimana fitur **User Namespace Remapping (`userns-remap`)** memetakan rentang UID/GID container ke rentang non-privileged UID/GID host menggunakan konfigurasi `/etc/subuid` dan `/etc/subgid`?
* Apa perbedaan arsitektural antara Docker dalam mode `userns-remap` dengan **Rootless Docker** (menjalankan daemon `dockerd` sepenuhnya tanpa akses root di host)? Sebutkan dua keterbatasan teknis dari eksekusi Rootless Docker (misal: binding port < 1024 dan pembatasan driver cgroups/network)!

### Soal 2.4: Linux Capabilities & Profiling Seccomp (Security Boundary)
Menjalankan container dengan flag `--privileged` merupakan anti-pattern berbahaya yang menonaktifkan seluruh mekanisme pertahanan kernel.
* Mengapa Linux Capabilities memecah hak akses superuser `root` menjadi potongan-potongan privilege granular? Berikan analisis risiko jika container memiliki capability `CAP_SYS_ADMIN` atau `CAP_NET_RAW`!
* Mengapa konfigurasi enterprise mewajibkan flag `--cap-drop=ALL` yang dipadukan dengan `--cap-add` selektif (misal: `CAP_NET_BIND_SERVICE`)? Apa peran **Seccomp (Secure Computing Mode)** default profile pada Docker dalam memblokir *system calls* berbahaya (~44 syscalls diblokir secara default) meskipun container berjalan sebagai root?

### Soal 2.5: Deep Dive OOM Killer Kernel: memory.max, Anonymous Memory, vs. Page Cache
Ketika konsumsi memori container melonjak mendekati batas yang ditentukan pada cgroups v2 (`memory.max`):
* Bagaimana kernel Linux membedakan antara alokasi **Anonymous Memory** (heap, stack, data runtime) dan **Page Cache** (file-backed cache) saat mengevaluasi tekanan memori (*memory pressure*)?
* Apa yang terjadi jika kernel tidak lagi dapat mereklamasi (*reclaim*) Page Cache yang kotor (*dirty pages*) dan konsumsi Anonymous Memory menembus limit `memory.max`?
* Jelaskan bagaimana kernel menghitung `oom_score` dan bagaimana nilai `oom_score_adj` digunakan oleh container runtime untuk menentukan proses mana yang akan dimatikan terlebih dahulu (`kill -9`, Exit Code 137)!

---

## 3. Scenario-Based Questions (3 Skenario Kasus Nyata Produksi)

### Skenario A: Latensi I/O Ekstrem Akibat Copy-Up Overhead pada Database PostgreSQL
**Konteks Insiden:**
Sebuah tim data engineer menjalankan instance database PostgreSQL 16 di dalam container Docker pada server bare-metal produksi. Karena kelalaian konfigurasi, direktori data database `/var/lib/postgresql/data` tidak di-mount ke *Named Volume* maupun *Bind Mount*, melainkan dibiarkan berada di atas layer read-write container bawaan (`OverlayFS`).

Database tersebut telah memuat tabel master transaksi dengan ukuran data berkisar 35 GB. Ketika sistem menerima batch transaksi update bertubi-tubi pada jam sibuk, metrik pemantauan mencatat fenomena anomali kritis:
- Utilisasi Disk I/O Wait (%iowait) pada host melonjak ke angka **98%**.
- Latensi query meningkat secara eksponensial dari **3 milidetik menjadi lebih dari 4.500 milidetik**.
- Kapasitas disk host berkurang drastis sebesar 35 GB seketika dalam hitungan detik.

**Pertanyaan Diagnostik & Solusi:**
1. Bedah secara mekanistis apa yang terjadi pada layer internal OverlayFS (`lowerdir` vs `upperdir`) ketika PostgreSQL melakukan modifikasi penulisan pertama kali (*in-place write*) pada file data berukuran gigabyte yang berada di layer image! Jelaskan istilah **Copy-Up Performance Penalty**!
2. Mengapa penggunaan *Named Volume* atau *Bind Mount* meniadakan degradasi latensi tersebut secara total? Jelaskan jalur eksekusi Virtual Filesystem (VFS) Linux ketika proses mengakses direktori volume dibandingkan dengan layer OverlayFS!
3. Susun perintah Docker CLI atau konfigurasi Docker Compose yang memigrasikan database tersebut ke arsitektur penyimpanan persistent berstandar performa tinggi (*high-throughput direct I/O*).

---

### Skenario B: OOM Killer Kaskade & Java JVM Heap Inconsistency pada Container Multi-Core
**Konteks Insiden:**
Sebuah microservice mission-critical berbasis Spring Boot (Java 11) di-deploy ke cluster host Linux berkapasitas 64 CPU Cores dan 256 GB RAM. Container dijalankan dengan alokasi batas cgroups:
`docker run -d --name payment-service --cpus="2" --memory="2g" payment-service:1.0`

Pada saat peak traffic event promo kilat (*flash sale*):
- Container sering kali mengalami terminasi mendadak (*silent crash*) dengan kode keluar `Exit Code 137` setiap 10-15 menit sekali.
- Dashboard APM (Application Performance Monitoring) internal aplikasi menunjukkan bahwa pemakaian JVM Heap hanya berada pada kisaran **60% (sekitar 1.2 GB)** tepat sebelum crash terjadi.
- File log aplikasi tidak mencatat satupun pesan `java.lang.OutOfMemoryError`.

**Pertanyaan Diagnostik & Solusi:**
1. Mengapa aplikasi Java mati tanpa melempar pengecualian `java.lang.OutOfMemoryError`, dan mengapa *Exit Code 137* mengindikasikan terminasi oleh kernel Linux (*Host OOM Killer*)?
2. Bagaimana cara membuktikan secara forensik bahwa container tersebut dimatikan oleh cgroups OOM Killer menggunakan perintah CLI host Linux (`dmesg`, `/var/log/messages`, dan file cgroups v2 `/sys/fs/cgroup/.../memory.events`)?
3. Analisis mengapa alokasi memori total container dapat menembus limit 2 GB padahal JVM Heap baru terpakai 1.2 GB! Pertimbangkan faktor: Metaspace, Thread Stacks (alokasi thread pool default pada host 64 Cores), Native Memory, Direct Byte Buffers, serta Page Cache.
4. Tuliskan konfigurasi JVM flags modern (`-XX:+UseContainerSupport`, `-XX:MaxRAMPercentage`, `-XX:ActiveProcessorCount`) dan optimasi parameter Docker yang menstabilkan service tersebut dari ancaman OOM Killer kaskade!

---

### Skenario C: Host Takeover & Privilege Escalation via Docker Daemon Socket Mount
**Konteks Insiden:**
Sebuah tim CI/CD membangun pipeline otomatisasi runner menggunakan containerized agent. Untuk memungkinkan runner membangun (*build*) image Docker di dalam pipeline, engineer mem-mount socket daemon host ke dalam container runner menggunakan opsi berikut:
`docker run -d --name gitlab-runner -v /var/run/docker.sock:/var/run/docker.sock gitlab-runner:latest`

Sebuah commit eksternal pada repositori open-source berhasil mengeksploitasi celah keamanan remote code execution (RCE) pada dependensi runner, memberikan akses shell interaktif kepada penyerang di dalam container `gitlab-runner`.

Dalam kurun waktu kurang dari 5 menit, penyerang berhasil membobol sistem operasi host utama, membaca file sensitif `/etc/shadow`, menanamkan backdoor binary berstatus SUID root pada host `/usr/local/bin`, dan mengambil kendali penuh atas cluster infrastruktur.

**Pertanyaan Diagnostik & Solusi:**
1. Jelaskan mengapa memberikan akses mount `/var/run/docker.sock` setara secara efektif dengan memberikan hak akses `root` penuh pada host OS tanpa batasan (*root equivalent*)!
2. Rekonstruksi taktik penyerang (*attack vector*): Perintah Docker apa yang dieksekusi oleh penyerang dari dalam container runner untuk melepaskan diri dari isolasi container (*container breakout*) dan memetakan root filesystem host (`/`) ke namespace eksternal?
3. Rancang 3 arsitektur alternatif yang aman untuk kebutuhan build image di dalam pipeline CI/CD tanpa mengekspos socket Docker host (misal: Docker-in-Docker / DinD terisolasi, Daemonless image builders seperti Kaniko atau Buildah, serta Container Sandbox berbasis microVM seperti gVisor atau Kata Containers)!

---

## 4. Chapter Challenge

### Tantangan Praktis: The Bare-Metal Linux Container Engine & Production Hardened OCI Container

#### Problem Description
Untuk menguasai esensi terdalam containerization, Anda tidak boleh hanya memandang Docker sebagai kotak hitam (*black box*). Tantangan ini terbagi menjadi dua bagian:
1. **Part 1 (Low-Level Kernel Isolation):** Membangun lingkungan container terisolasi secara manual langsung menggunakan *Linux primitives* (`unshare`, `cgroups v2`, `pivot_root`/`chroot`, dan virtual interface) tanpa bantuan binary `docker` ataupun `containerd`.
2. **Part 2 (Enterprise Hardening Dockerfile & Runtime):** Mengemas microservice ke dalam OCI Image berstandar keamanan militer (*zero-trust distroless, non-root, capability-stripped, read-only rootfs*).

---

#### Specifications & Requirements

#### Bagian 1: Native Linux Container Construction (Shell Scripting)
Buat sebuah script shell otomatisasi bernama `build_native_container.sh` yang menjalankan tahapan berikut pada Linux kernel modern (Ubuntu 22.04+ / Kernel 5.15+ dengan cgroups v2 aktif):

1. **Root Filesystem Preparation:**
   * Unduh rootfs mini Alpine Linux terkini ke direktori `/tmp/my_container_rootfs`.
2. **cgroups v2 Resource Constraining:**
   * Buat node cgroups v2 baru di `/sys/fs/cgroup/custom_box`.
   * Konfigurasikan batas keras memori sebesar **100 MB** (`memory.max = 104857600`).
   * Konfigurasikan batas CPU sebesar **0.5 core** (`cpu.max = 50000 100000`).
3. **Namespace Isolation & Execution:**
   * Gunakan utilitas `unshare` untuk mengisolasi 5 namespace: PID, Mount, UTS, IPC, dan Network (`--pid --mount --uts --ipc --net --fork`).
   * Ubah hostname di dalam UTS namespace menjadi `isolated-box`.
   * Pindahkan PID script ke dalam cgroup node `/sys/fs/cgroup/custom_box/cgroup.procs`.
   * Lakukan isolasi mount rootfs menggunakan `chroot` (atau `pivot_root`) dan mount direktori `/proc` baru yang terisolasi (`mount -t proc none /proc`).
   * Jalankan shell `/bin/sh` di dalam container tersebut.
4. **Verifikasi Isolasi:**
   * Jalankan `ps aux` di dalam container: output **hanya boleh** menampilkan proses container sendiri (PID 1 adalah `/bin/sh`), tanpa melihat proses host.
   * Jalankan script pengujian konsumsi memori di dalam container untuk memvalidasi bahwa cgroups mematikan proses ketika melewati batas 100 MB (`Killed / OOMKilled`).

---

#### Bagian 2: Enterprise Production Dockerfile & Runtime Hardening
Rancang sebuah project microservice Go/Node.js dengan struktur artefak berikut:
1. **`Dockerfile.hardened` (Multi-Stage Build):**
   * **Stage 1 (Builder):** Meng-compile source code menjadi biner statis mandiri.
   * **Stage 2 (Runtime):** Menggunakan base image `gcr.io/distroless/static-debian12:nonroot` atau `scratch`.
   * Tidak boleh ada package manager, shell (`/bin/sh`, `/bin/bash`), compiler, maupun utilitas debugging pada image runtime.
   * Konfigurasikan user non-root eksplisit: `USER 65532:65532`.
   * Tentukan instruksi `HEALTHCHECK` native tanpa dependensi `curl`/`wget`.
2. **Docker Run Security Flags (Zero-Trust Profile):**
   * Tuliskan script eksekusi `run_hardened.sh` yang menerapkan flags keamanan wajib:
     ```bash
     docker run -d \
       --name secure-app \
       --read-only \
       --tmpfs /tmp:rw,noexec,nosuid,size=64m \
       --cap-drop=ALL \
       --security-opt=no-new-privileges:true \
       --pids-limit 100 \
       --memory="256m" \
       --cpus="1.0" \
       -p 8080:8080 \
       secure-app:latest
     ```
3. **Automated Verification Script (`verify_security.sh`):**
   * Script harus memverifikasi bahwa:
     - Root filesystem berstatus read-only (mencoba menulis file ke `/` menghasilkan error `Read-only file system`).
     - Direktori `/tmp` dapat ditulisi namun flag `noexec` mencegah eksekusi biner.
     - Container tidak memiliki capabilities apa pun (`CapEff: 0000000000000000` pada `/proc/1/status`).
     - Tidak ada proses zombie yang tertinggal saat child proses dihentikan.

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk memverifikasi kesiapan arsitektural Anda sebelum melanjutkan ke bab berikutnya.

### Saya harus memahami:
- [ ] Batasan formal antara isolasi berbasis perangkat keras (Hypervisor) dengan isolasi berbasis kernel sistem operasi (Container).
- [ ] Peran fundamental 7 Linux Namespaces (`PID`, `NET`, `MNT`, `IPC`, `UTS`, `USER`, `TIME`) dalam mengabstraksikan pandangan proses.
- [ ] Perbedaan mendasar struktur hierarki cgroups v1 vs cgroups v2, dan lokasi direktori kontrol terpadu di `/sys/fs/cgroup`.
- [ ] Prinsip operasi driver OverlayFS: hierarki `lowerdir`, `upperdir`, `workdir`, `merged`, dan penalti I/O copy-up.
- [ ] Runtimes execution flow OCI: Pemisahan peran Docker CLI $\to$ `dockerd` $\to$ `containerd` $\to$ `containerd-shim-v2` $\to$ `runc`.
- [ ] Mengapa proses `runc` langsung exit setelah container dibuat, dan bagaimana `containerd-shim-v2` menjaga kestabilan file descriptor proses.
- [ ] Bahaya proses zombie dan kegagalan forwarding sinyal POSIX (`SIGTERM`/`SIGINT`) pada aplikasi non-supervisor yang bertindak sebagai PID 1.
- [ ] Cara kerja pemetaan UID/GID melalui User Namespaces (`userns-remap`) dan keunggulan arsitektural Rootless Docker.
- [ ] Prinsip keamanan *Least Privilege* menggunakan reduksi Linux Capabilities (`--cap-drop=ALL`) dan filter Seccomp.
- [ ] Cara kerja kernel Linux OOM Killer, perbedaan Anonymous Memory vs Page Cache, serta interpretasi *Exit Code 137*.

### Saya tidak perlu menghafal:
- [ ] Nilai bitmask heksadesimal dari seluruh Linux Capabilities (misal: nilai biner bitmask numerik `0x0000003fffffffff`).
- [ ] Struktur data C internal kernel Linux untuk `struct task_struct` atau implementasi driver VFS OverlayFS baris-per-baris.
- [ ] Seluruh nomor syscall Linux x86_64 (~350+ syscalls) yang tercatat dalam tabel seccomp.
- [ ] Sintaks JSON mentah spesifikasi OCI `config.json` yang di-generate otomatis oleh `containerd`.
- [ ] Algoritma internal hashing SHA-256 untuk layer blob tar OCI Image manifest.

### Saya harus bisa melakukan:
- [ ] Mendiagnosis penyebab container exit mendadak akibat OOMKilled menggunakan `docker inspect`, `dmesg`, dan metrik cgroup v2.
- [ ] Menemukan dan menanggulangi kebocoran proses zombie di dalam container dengan menyematkan init daemon ringan (`--init` / `tini`).
- [ ] Menghilangkan copy-up latency penalty pada aplikasi database/I/O intensif dengan merancang persistensi melalui *Named Volumes*.
- [ ] Menulis Dockerfile multi-stage production-grade dengan base image distroless dan eksekusi non-root UID.
- [ ] Mengamankan runtime container menggunakan kombinasi flag security: `--read-only`, `--tmpfs`, `--cap-drop=ALL`, dan `--security-opt=no-new-privileges`.
- [ ] Memeriksa struktur namespace dan cgroups proses container secara langsung dari host filesystem (`/proc/<PID>/ns/` dan `/proc/<PID>/cgroup`).
- [ ] Menjelaskan dan memitigasi celah eksploitasi keamanan socket daemon Docker (`/var/run/docker.sock`) pada pipeline CI/CD modern.

---
*Ketik **LANJUT** untuk melangkah ke Bab berikutnya: Container Image Engineering, Layer Optimization, & Multi-Stage Builds.*
