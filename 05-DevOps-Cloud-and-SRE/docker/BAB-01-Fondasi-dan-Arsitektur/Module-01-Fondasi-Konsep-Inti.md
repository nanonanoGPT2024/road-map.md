# Bab 01: Fundamental Containerization & Docker Engine Architecture
## Module 01: Pengenalan Containerization, Isolasi Linux Kernel, dan Anatomi Docker Engine

---

### 01. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis (C4)** perbedaan fundamental antara virtualisasi berbasis hypervisor (Hardware-level Virtualization) dan containerization (OS-level Virtualization) berdasarkan alokasi resource dan struktur eksekusi kernel.
- **Mendekonstruksi (C4)** primitif Linux Kernel yang mendasari containerization: 7 Linux Namespaces, Control Groups (cgroups v1/v2), dan Union File System (OverlayFS).
- **Mengartikulasikan (C3)** arsitektur modular Docker Engine (Docker CLI, Docker Daemon/`dockerd`, `containerd`, `shim`, dan `runc` berdasarkan Open Container Initiative / OCI spec).
- **Mengimplementasikan (C3)** isolasi container manual dari baris perintah menggunakan abstraksi primitif OS untuk memahami lifecycle proses container.
- **Mendiagnosis (C4)** anomali eksekusi container seperti *PID 1 zombie reaping*, *Out-Of-Memory (OOM) Killer triggers*, dan *I/O latency overhead*.

---

### 02. Introduction & High-Level Concept
Secara historis, deployment aplikasi bergantung pada server fisik monolitik atau Virtual Machine (VM). Pendekatan VM menyertakan Guest Operating System (Guest OS) lengkap beserta kernel, driver, dan virtual hardware abstraction di atas Hypervisor (Type 1 atau Type 2). Hal ini menghasilkan overhead memori yang masif, ukuran artifact gigabyte-scale, serta waktu boot yang memakan hitungan menit.

```
+-------------------------------------------------------------+
|                          ANALOGI                            |
|                                                             |
|   VIRTUAL MACHINE                  CONTAINER                |
|   (Apartemen Independen)           (Bilik Kantor / Cubicle) |
|   +-----------------------+        +---------------------+  |
|   | Dapur Sendiri         |        | Meja Kerja Pribadi  |  |
|   | Saluran Air Sendiri   |        | Listrik Terisolasi  |  |
|   | Listrik Sendiri       |        | AC & Pondasi Bersama|  |
|   | Pondasi Mandiri       |        | (Kernel OS Host)    |  |
|   +-----------------------+        +---------------------+  |
|   -> Berat, boros ruang.           -> Ringan, efisien.      |
+-------------------------------------------------------------+
```

Docker mempopulerkan **OS-level virtualization**. Container bukan merupakan sebuah mesin virtual, melainkan **sebuah proses reguler di host Linux yang dibatasi ruang pandangnya (isolation) dan dikontrol konsumsi sumber dayanya (resource limitation)**. Container berbagi (share) Linux Kernel dengan host OS. Container engine seperti Docker membungkus dependensi aplikasi, runtime, library, dan konfigurasi ke dalam satu kesatuan immutable image yang dapat dijalankan secara konsisten di lingkungan komputasi mana pun yang kompatibel dengan kernel tersebut.

---

### 03. Why It Matters
Sebelum era containerization, industri menghadapi masalah kronis: *"It works on my machine, but breaks in production"*. Masalah ini dipicu oleh environmental drift (perbedaan versi libc, path dependencies, permission level, runtime flags, dan konfigurasi kernel).

| Aspek | Virtual Machine (VM) | Container (Docker) |
| :--- | :--- | :--- |
| **Arsitektur Abstraksi** | Hardware Level (Hypervisor) | OS Level (Kernel sharing) |
| **Guest OS** | Wajib ada OS mandiri per VM | Tidak ada (menggunakan Kernel Host) |
| **Startup Time** | Menit (booting full OS) | Milidetik hingga detik (instant process fork) |
| **Resource Footprint** | Gigabytes RAM/Disk per instance | Megabytes RAM/Disk (overhead minimal) |
| **Performance (I/O & CPU)** | Terkena hypervisor translation penalty | Bare-metal performance (native syscalls) |
| **Portabilitas Skala** | Lambat di-scale horizontal | Sangat cepat diorkestrasi (Kubernetes/Swarm) |

Containerization memotong biaya infrastruktur secara drastis melalui densitas komputasi yang tinggi: sebuah server bare-metal yang biasanya hanya mampu menjalankan 10 VM dapat mengonsolidasi ratusan container tanpa degradasi performa akibat redundansi kernel.

---

### 04. What It Is (and What It Isn't)

#### What It Is:
- **Process Isolation Mechanism:** Pemanfaatan fitur keamanan dan isolasi native Linux Kernel (`namespaces`, `cgroups`, `capabilities`, `seccomp`).
- **Packaging Format:** Standar distribusi perangkat lunak (OCI Image Format) yang menyatukan binaries, file konfigurasi, dan shared libraries ke dalam rootfs (root filesystem) berlapis (*layered filesystem*).
- **Ecosystem Runtime:** Docker Engine menyediakan tooling end-to-end untuk build, ship, dan run container melalui standardisasi API.

#### What It Isn't:
- **Bukan Hypervisor:** Docker tidak mengemulasikan CPU, RAM bus, controller disk, atau PCI peripherals.
- **Bukan Sandbox Sempurna secara Default:** Berbagi kernel host berarti kerentanan kernel (*kernel exploit* atau *kernel panic*) pada satu container yang tidak di-hardening secara teoritis dapat merusak seluruh host node.
- **Bukan Emulator Multi-Architecture:** Container x86-64 tidak dapat langsung berjalan di CPU ARM64 tanpa layer emulasi instruksi (seperti QEMU binfmt_misc), karena binary container dieksekusi langsung oleh CPU host.

---

### 05. How It Works (Deep Dive)
Docker bekerja dengan mengorkestrasi tiga pilar fundamental Linux Kernel:

```
+-------------------------------------------------------------------------+
|                              LINUX KERNEL                               |
|                                                                         |
|  +--------------------+  +----------------------+  +-----------------+  |
|  |     NAMESPACES     |  |       CGROUPS        |  |   OVERLAYFS     |  |
|  |    (Apa yang bisa  |  |    (Berapa banyak    |  |  (Layered File  |  |
|  |     proses LIHAT)  |  |    yang bisa DIPAKAI)|  |    System)      |  |
|  +--------------------+  +----------------------+  +-----------------+  |
+-------------------------------------------------------------------------+
```

#### 1. Linux Namespaces (Isolasi Visibilitas)
Namespaces membatasi apa yang dapat *dilihat* oleh suatu proses. Linux menyediakan 7 namespace utama untuk isolasi container:
- **PID (Process ID):** Memberikan penomoran tree proses independen. Proses di dalam container menjadi PID 1 di namespacenya sendiri, meskipun memiliki PID arbitrer (misal: PID 10452) di host namespace.
- **NET (Networking):** Menyediakan virtual network stack independen: routing tables, IP addresses, port binding, iptables rules, dan network interfaces (`eth0`, `veth`).
- **MNT (Mount):** Mengisolasi titik mount filesystem. Container memiliki root mount directory tersendiri (`/`) yang terpisah dari root host.
- **IPC (Inter-Process Communication):** Mengisolasi shared memory segments, message queues, dan semaphores.
- **UTS (UNIX Timesharing System):** Mengizinkan container memiliki hostname dan domain name sendiri tanpa mempengaruhi host.
- **USER (User IDs):** Memetakan UID/GID di dalam container ke UID/GID berbeda di host (misal: user `root` di dalam container dipetakan ke UID non-privilese `10001` di host untuk mitigasi privilege escalation).
- **CGROUP Namespace:** Mengisolasi visibilitas konfigurasi cgroup view milik proses.

#### 2. Control Groups / cgroups (Batasan Alokasi Sumber Daya)
Jika namespaces membatasi visibilitas proses, cgroups membatasi *seberapa banyak resource yang dapat dikonsumsi*:
- **CPU:** Menetapkan quota dan period (melalui CFS - Completely Fair Scheduler), serta pinned CPU cores (`cpuset`).
- **Memory:** Mengontrol limit resident memory, swap space, dan mendeteksi kondisi out-of-memory untuk menembakkan sinyal `SIGKILL` via Linux OOM Killer.
- **Block I/O (blkio):** Mengontrol read/write throughput dan IOPS ke storage devices.
- **PIDs:** Membatasi jumlah maksimum proses yang dapat di-fork di dalam cgroup untuk mencegah *fork-bomb attacks*.

#### 3. Union File System (OverlayFS)
Docker menggunakan OverlayFS untuk efisiensi penyimpanan disk. Image terdiri dari sekumpulan layer *Read-Only* (LowerDir). Ketika container diinstansiasi, Docker menambahkan layer tipis *Read-Write* di atasnya (UpperDir).
Proses sistem operasi melihat layer-layer ini terintegrasi sebagai kesatuan tunggal (MergedDir). Operasi mutasi berkas menggunakan mekanisme **Copy-on-Write (CoW)**: berkas dari layer bawah disalin ke layer atas hanya saat proses memodifikasi berkas tersebut.

#### 4. The Docker Architecture Stack
Arsitektur modular Docker modern dibangun di atas OCI standard:
- **Docker CLI (`docker`):** Client interface biner untuk menerima input developer dan mengirimkan REST API calls melalui UNIX socket `/var/run/docker.sock`.
- **Dockerd:** Daemon yang mengelola Docker images, networks, volumes, build systems, dan API router.
- **containerd:** Daemon runtime container level-tinggi (high-level runtime) yang bertugas mendownload image, memanajemen lifecycle container, dan push/pull images.
- **containerd-shim:** Proses independen yang menjadi parent dari container runtime. Shim menjaga stdin/stdout/stderr tetap terbuka jika daemon crash/restart, dan mengembalikan exit status container ke containerd.
- **runc:** Implementasi referensi biner OCI (low-level runtime). `runc` berinteraksi langsung dengan Linux syscalls (`clone`, `unshare`, `setns`, `pivot_root`) untuk menyusun namespaces/cgroups, menjalankan proses, lalu langsung exit setelah proses container diserahkan ke `shim`.

---

### 06. Architecture Diagram

```
+-----------------------------------------------------------------------+
| USER SPACE (Host OS)                                                  |
|                                                                       |
|  +------------------+                                                 |
|  |    Docker CLI    |                                                 |
|  |     (docker)     |                                                 |
|  +--------+---------+                                                 |
|           | (HTTP REST API via /var/run/docker.sock)                  |
|           v                                                           |
|  +------------------+                                                 |
|  |  Docker Daemon   |                                                 |
|  |     (dockerd)    |                                                 |
|  +--------+---------+                                                 |
|           | (gRPC via /run/containerd/containerd.sock)                |
|           v                                                           |
|  +------------------+                                                 |
|  |    containerd    |                                                 |
|  +--------+---------+                                                 |
|           |                                                           |
|           +-----------------------+                                   |
|           | (spawns runtime)      | (supervises)                      |
|           v                       v                                   |
|  +------------------+    +-------------------+                        |
|  |      runc        |--->|  containerd-shim  |                        |
|  | (OCI low-level)  |    +---------+---------+                        |
|  +--------+---------+              |                                  |
|           | (clone/unshare/setns)  | (attaches stdin/out/err)         |
+-----------|------------------------|----------------------------------+
| KERNEL SPACE                       |                                  |
|           v                        v                                  |
|  +-------------------------------------------+                        |
|  | Linux Process Container Context           |                        |
|  |                                           |                        |
|  |  +-------------------------------------+  |                        |
|  |  | PID 1 (Inside NS): App Process      |  |                        |
|  |  +-------------------------------------+  |                        |
|  |  [Namespaces] [Cgroups] [OverlayFS RootFS]|                        |
|  +-------------------------------------------+                        |
+-----------------------------------------------------------------------+
```

---

### 07. Minimal Reproducible Example
Mari jalankan container pertama dan verifikasi bahwa proses tersebut merupakan proses Linux native yang dapat dilacak dari host OS.

#### Langkah 1: Eksekusi Container Alpine
```bash
docker run -d --name test-container alpine sleep 1000
```

#### Langkah 2: Inspeksi PID Container dari Sisi Host
Dapatkan process ID container tersebut di host OS:
```bash
CONTAINER_PID=$(docker inspect --format '{{.State.Pid}}' test-container)
echo "Container Process ID on Host: ${CONTAINER_PID}"
```

#### Langkah 3: Verifikasi Namespace & Cgroup Proses dari Host Linux
Periksa namespace yang dialokasikan kernel host untuk proses ini:
```bash
ls -la /proc/${CONTAINER_PID}/ns
```
*Output menampilkan link ke inode unik untuk namespaces seperti `net`, `mnt`, `pid`, dll.*

Periksa proses langsung melalui tools `ps` host:
```bash
ps aux | grep "[s]leep 1000"
```
Anda akan melihat proses `sleep 1000` berjalan langsung pada table proses host kernel dengan PID Host `${CONTAINER_PID}`, namun jika Anda masuk ke dalam container:
```bash
docker exec test-container ps aux
```
Output di dalam container menunjukkan `sleep 1000` berjalan sebagai **PID 1**. Ini membuktikan secara langsung cara kerja PID Namespace.

#### Cleanup
```bash
docker rm -f test-container
```

---

### 08. Production-Grade Practical Implementation
Implementasi containerization modern mengharuskan kita mematuhi prinsip minimal attack surface, non-root execution, serta deterministic lifecycle. Di bawah ini adalah contoh arsitektur build container Go-based production-ready menggunakan multistage build.

#### Project Layout
```
├── Dockerfile
├── entrypoint.sh
└── main.go
```

#### File: `main.go`
```go
package main

import (
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
)

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("OK"))
	})

	server := &http.Server{
		Addr:         ":8080",
		Handler:      mux,
		ReadTimeout:  5 * time.Second,
		WriteTimeout: 10 * time.Second,
	}

	// Channel intercept graceful shutdown
	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGTERM, syscall.SIGINT)

	go func() {
		fmt.Println("Server running on port :8080")
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			fmt.Printf("Listen error: %s\n", err)
			os.Exit(1)
		}
	}()

	<-stop
	fmt.Println("Shutting down gracefully...")
	os.Exit(0)
}
```

#### File: `entrypoint.sh`
```bash
#!/bin/sh
set -eu

# Validasi environment sebelum eksekusi
echo "Executing init sequence inside container..."

# Exec menggantikan PID shell script dengan binary target agar menerima direct signal (SIGTERM)
exec "$@"
```

#### File: `Dockerfile` (Production Hardened)
```dockerfile
# Stage 1: Build stage
FROM golang:1.22-alpine AS builder

WORKDIR /src

# Caching dependencies
COPY go.* ./
# RUN go mod download (uncomment jika memiliki external modules)

COPY . .

# Build statically compiled binary, stripping debugging symbols (-ldflags="-s -w")
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build \
    -ldflags="-s -w" \
    -o /bin/app main.go

# Stage 2: Final Minimal Runtime Stage
FROM alpine:3.19

# Security: Buat non-root user dan group spesifik
RUN addgroup -S -g 10001 appgroup && \
    adduser -S -u 10001 -G appgroup appuser

WORKDIR /app

# Ambil binary dari builder stage
COPY --from=builder /bin/app /app/app
COPY entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh && \
    chown -R appuser:appgroup /app

# Pindah konteks ke unprivileged user
USER 10001:10001

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:8080/healthz || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["/app/app"]
```

#### Build dan Jalankan
```bash
docker build -t production-microservice:1.0 .
docker run -d --name microservice -p 8080:8080 --memory="128m" --cpus="0.5" production-microservice:1.0
```

---

### 09. Trade-offs & Alternatives

```
+--------------------------------------------------------------------------+
|                        ISOLATION vs OVERHEAD SPECTRUM                    |
|                                                                          |
| Bare Metal        Docker Containers      Kata Containers /      Full VM  |
|                                          Firecracker                     |
| <----------------------------------------------------------------------> |
| Max Performance                         Max Isolation (Hardware Virtual) |
| Min Security Boundary                   High Resource & Boot Penalty     |
+--------------------------------------------------------------------------+
```

| Teknologi | Kelebihan Utama | Kelemahan Utama | Kasus Penggunaan Ideal |
| :--- | :--- | :--- | :--- |
| **Traditional VM (KVM/ESXi)** | Isolasi hardware penuh; independent kernel; support legacy OS. | Overhead RAM/Disk besar; startup lambat; densitas rendah. | Multi-tenant untrusted workloads; OS heterogen (Windows di Linux). |
| **Standard Container (Docker/runc)** | Performa mendekati native; startup instan; utilitas CI/CD standar industri. | Berbagi kernel; risiko *kernel exploit privilege escalation*. | Internal enterprise microservices; environments terkontrol. |
| **MicroVM (Firecracker/Kata)** | Isolasi hardware per-container dengan overhead jauh lebih kecil dari VM tradisional. | Memerlukan hardware acceleration (VT-x/AMD-V); konfigurasi networking kompleks. | Multi-tenant serverless execution (misal: AWS Lambda, Fly.io). |
| **WebAssembly (Wasm/WASI)** | Footprint ultra-ringan (kilobytes); startup sub-milidetik; platform-agnostic. | Ekosistem API belum selengkap POSIX; adopsi library C-binding terbatas. | Edge computing; plugin architecture; function execution. |

---

### 10. Best Practices & Design Patterns
- **Prinsip Immutability:** Jangan pernah memperbarui dependensi secara langsung di dalam running container via SSH/exec. Lakukan update pada base image, build image baru, dan redeploy.
- **Single Responsibility Principle per Container:** Satu container idealnya hanya mengelola satu domain proses (misal: jangan bundling Nginx dan Node.js/PHP-FPM ke dalam satu container). Gunakan network compose jika membutuhkan kolaborasi service.
- **Enforce Non-Root Users:** Definisikan direktif `USER <UID>` di Dockerfile untuk membatasi akses privilege. Jika container tereksploitasi, attacker terkunci dalam restricted user namespace.
- **Manfaatkan `.dockerignore`:** Pastikan folder `.git`, local build artifacts, logs, dan secrets (`.env`) tidak masuk ke build context:
  ```
  .git
  .env
  node_modules
  bin/
  *.log
  ```
- **Opt-in Multi-Stage Builds:** Pisahkan build-time tools (compiler, SDK) dari runtime environment untuk mereduksi surface attack dan ukuran image.

---

### 11. Edge Cases & Failure Modes

#### 1. PID 1 Zombie Reaping Problem
Dalam Linux, proses dengan PID 1 bertugas sebagai init process. Dua tanggung jawab intinya:
- Mengadopsi proses "yatim piatu" (*orphaned processes*) saat parent aslinya mati.
- Mereap (membersihkan) exit status anak proses (`waitpid()`). Jika PID 1 gagal melakukan reaping, proses yang sudah mati berubah menjadi **Zombie Process (`[defunct]`)**. Zombie process menghabiskan alokasi PID table host.
*Solusi:* Gunakan flag `--init` pada `docker run` atau binary init ringan seperti `tini`.

#### 2. OOM Killer Triggers & Cgroup Enforcements
Jika aplikasi dalam container meminta alokasi memori melebihi batas `--memory`:
- Kernel tidak me-restart aplikasi secara graceful; Linux Kernel OOM killer langsung mengirimkan sinyal tidak terinterupsi `SIGKILL` (Exit Code 137).
- Pada Java VM versi lama (< Java 8u131), JVM tidak menyadari batas cgroup dan mengalokasikan heap berdasarkan total RAM host fisik, menyebabkan crash instan akibat OOM Killer.

#### 3. Cgroups v1 vs v2 Unified Hierarchy
Migrasi arsitektur dari Docker lama ke modern seringkali terbentur cgroup v2:
- Cgroup v1 memisahkan kontroler (`/sys/fs/cgroup/memory`, `/sys/fs/cgroup/cpu`).
- Cgroup v2 menyatukan hierarki (*unified hierarchy*) di bawah `/sys/fs/cgroup`.
Jika Anda memiliki monitoring agent lama di dalam container yang membaca path cgroups v1 secara hardcoded, agent tersebut akan menghasilkan silent metric loss atau runtime error.

---

### 12. Anti-patterns

#### 1. "Fat Container" / Treating Containers as VMs
Menjalankan init systems seperti `systemd`, SSH daemon, syslog, dan database bersamaan dalam satu container menggunakan supervisord tanpa arsitektur microservices terukur.
*Dampak:* Kesulitan logging stdout/stderr, health check tidak akurat, lifecycle container tidak deterministik.

#### 2. Hardcoding Secrets ke Image Layer
```dockerfile
# SANGAT BERBAHAYA
ENV DB_PASSWORD="SuperSecretPassword123"
COPY id_rsa /root/.ssh/id_rsa
```
*Dampak:* Sekalipun file dihapus pada layer berikutnya (`RUN rm -f /root/.ssh/id_rsa`), file tersebut tetap berada di history layer sebelumnya dan dapat diekstrak oleh siapapun yang memiliki akses read ke registry image.

#### 3. Menggunakan Tag `:latest` di Production
```dockerfile
# TIDAK DETERMINISTIK
FROM node:latest
```
*Dampak:* Deploy di hari yang berbeda dapat mengunduh versi compiler/libc yang berbeda secara mendadak, menghancurkan prinsip deterministik build. Gunakan immutable digest atau pinned semantic tags (misal: `node:20.11.1-alpine3.19`).

---

### 13. Security Considerations
- **Eksploitasi `/var/run/docker.sock`:** Me-mount Docker socket ke dalam container tanpa proteksi sama artinya dengan memberikan hak akses `root` penuh pada host OS. Attacker dapat memanggil Docker daemon API untuk membuat privileged container yang memetakan root host `/` ke container.
- **Docker Daemon Attack Surface:** Default Docker daemon berjalan sebagai user `root`. Implementasikan **Rootless Docker** jika arsitektur lingkungan mengizinkan, agar `dockerd` dieksekusi di user namespace non-root.
- **Linux Capabilities (`--cap-drop` & `--cap-add`):**
  Secara default Docker mempertahankan subset kemampuan kernel (capabilities). Sangat disarankan men-drop seluruh capabilities default dan menambahkan hanya yang dibutuhkan:
  ```bash
  docker run --cap-drop=ALL --cap-add=NET_BIND_SERVICE ...
  ```
- **Seccomp (Secure Computing Mode):** Pastikan default Docker seccomp profile tetap aktif. Fitur ini memblokir ratusan syscalls berbahaya (seperti `reboot`, `sys_ptrace`, atau manipulasi kernel modules `init_module`) agar tidak dapat dipanggil dari dalam container.

---

### 14. Performance & Resource Implications

#### CPU Scheduling Overhead
Container mengeksekusi syscall langsung ke host kernel. Tidak ada overhead CPU emulasi/virtualisasi (0% hypervisor translation cost). Namun, penggunaan cgroup CFS Quota (`--cpus="1.0"`) yang tidak tepat dapat menyebabkan proses mengalami **CPU Throttling** meskipun utilisasi host masih rendah. Metrik throttling harus dipantau via `/sys/fs/cgroup/cpu.stat`.

#### Storage Drivers (Overlay2) vs Native FS
Overlay2 menambahkan layer indirection minimal melalui lookup virtual directory. Operasi I/O berat pertama kali pada file besar di layer bawah akan memicu overhead saat CoW (Copy-on-Write) menduplikasi seluruh file ke UpperDir. 
*Aturan Performa:* Untuk I/O throughput tinggi (misal: PostgreSQL, MySQL, Redis append-only file), **selalu bypass storage driver** dengan menggunakan **Docker Volumes**. Volumes langsung me-mount direktori host ke container filesystem secara native.

#### Memory Management
Memory container tidak di-prealokasi seperti VM. Jika host memiliki 64GB RAM dan Anda menjalankan 10 container tanpa batas `--memory`, satu container yang mengalami memory-leak dapat mengonsumsi sisa RAM fisik dan menyebabkan host membunuh proses-proses sistem yang krusial.

---

### 15. Testing, Verification & Observability

#### Validasi Resource Limit Container
Jalankan stress-test untuk memverifikasi apakah batas cgroups bekerja sesuai ekspektasi.

```bash
# 1. Jalankan container dengan batas memori ketat (64MB)
docker run -d --name mem-test --memory="64m" progrium/stress --vm 1 --vm-bytes 50M

# 2. Observasi penggunaan resource realtime
docker stats --no-stream mem-test

# 3. Uji OOM scenario dengan melebihi batas alokasi (100MB)
docker run -d --name oom-test --memory="64m" progrium/stress --vm 1 --vm-bytes 100M

# 4. Verifikasi status exit
docker ps -a --filter "name=oom-test" --format "table {{.Names}}\t{{.Status}}"
# Output harus mengindikasikan Exited (137) atau OOMKilled
docker inspect oom-test --format '{{.State.OOMKilled}}'
# Output bernilai: true
```

#### Diagnostic Commands
- **Tracing Syscalls:** `docker run --security-opt seccomp=unconfined strace -p <PID>`
- **Live Event Feed:** `docker events --filter 'type=container'`
- **Verify Direct Cgroup Constraints:**
  ```bash
  cat /sys/fs/cgroup/system.slice/docker-<CONTAINER_ID>.scope/memory.max
  ```

---

### 16. Real-World Scenario
**Konteks Masalah:**
Sebuah cluster production backend Node.js mengalami crash beruntun setiap jam 03.00 pagi. Log host menampilkan alert:
`kernel: [78213.120] Out of memory: Kill process 12431 (node) score 950 or sacrifice child`.
Status Docker menampilkan container mati dengan code `137`.

**Investigasi:**
Setelah dilakukan penelusuran arsitektur:
1. Container dideploy tanpa limitasi memory (`--memory` tidak diset).
2. Setiap jam 03.00, cron job menghasilkan heavy data export yang memuat ratusan ribu record langsung ke heap RAM Node.js.
3. Node.js melahap memori hingga 98% kapasitas host OS, mengancam kestabilan kernel host, sehingga kernel memicu OOM Killer dan mengeksekusi `SIGKILL` pada proses dengan skor OOM tertinggi (aplikasi backend).

**Solusi Arsitektur:**
1. Isolasi limit memori container pada level cgroups:
   ```bash
   --memory="2g" --memory-swap="2g"
   ```
2. Set heap limit internal runtime agar Node.js melakukan Garbage Collection agresif sebelum menyentuh batas cgroup Linux:
   `node --max-old-space-size=1800 index.js`
3. Konfigurasi restart policy:
   `--restart=on-failure:5`
4. Hasil: Heap crash dicegah via internal GC; jikapun lonjakan memory ekstrem terjadi, OOM Killer hanya menghentikan container tersebut tanpa mengganggu proses lain di host.

---

### 17. Troubleshooting Runbook

```
                         [ CONTAINER CRASH / ANOMALI ]
                                       |
                         Eksekusi: docker ps -a
                                       |
                   +-------------------+-------------------+
                   |                                       |
          Exit Code: 137                          Exit Code: 127/1
                   |                                       |
            OOM Killer Alert?                       Entrypoint Failure?
                   |                                       |
         +---------+---------+                     +-------+-------+
         |                   |                     |               |
     OOMKilled:         Host OOM?              Missing         Incorrect
       true                  |                Libraries/     Interpreter/
         |           Inspeksi Host           Executables?      Syntax?
    Naikkan limit     /var/log/messages            |               |
    --memory          atau dmesg              Cek Alpine      Periksa shebang
                                              libc/musl       (#!/bin/sh)
```

| Kode / Error | Kemungkinan Root Cause | Prosedur Resolusi |
| :--- | :--- | :--- |
| **Exit Code 137** | Container dibunuh paksa oleh `SIGKILL` (128 + sinyal 9). Dominan diakibatkan OOM Killer. | Jalankan `docker inspect <container> --format '{{.State.OOMKilled}}'`. Jika true, naikkan `--memory` atau cari memory leak di aplikasi. |
| **Exit Code 127** | Command tidak ditemukan (Container cannot find executable binary). | Periksa direktif `ENTRYPOINT` atau `CMD`. Sering terjadi pada image Alpine karena library `glibc` tidak ada (gunakan Alpine yang kompatibel atau build static binary). |
| **Exit Code 1** | Application error runtime. | Periksa output error log: `docker logs --tail 100 <container>`. Pastikan variabel environment lengkap. |
| **"Cannot connect to the Docker daemon..."** | Dockerd tidak berjalan atau permission socket salah. | Pastikan systemd unit aktif: `sudo systemctl status docker`. Jika non-root user, pastikan user telah masuk group docker: `sudo usermod -aG docker $USER`. |
| **Container stuck in `RemovalInProcess`** | Deadlock pada driver storage OverlayFS atau proses I/O hanging di kernel (State `D`). | Periksa proses D di host via `ps aux \| awk '$8 ~ /D/'`. Lepaskan mountpoint nyangkut di `/var/lib/docker/overlay2` secara hati-hati atau reboot host jika kernel lockup. |

---

### 18. Tooling, Extensions & Ecosystem
- **Runtimes:**
  - `runc`: Low-level OCI reference runtime.
  - `crun`: Alternatif implementasi `runc` berbasis C murni, jauh lebih cepat dan hemat memori.
  - `containerd`: Standard industry core container runtime engine.
- **Alternative Build & Run Tools:**
  - `Podman`: Container engine tanpa daemon (daemonless) dan natively rootless (drop-in replacement untuk Docker CLI).
  - `Buildah`: Tooling spesialis untuk memproduksi OCI container images tanpa membutuhkan Docker daemon.
  - `Skopeo`: Utilitas inspeksi image langsung di remote registry tanpa perlu pull seluruh layers.
- **Security & Inspection Tools:**
  - `Trivy`: Scanner kerentanan CVE pada image layers.
  - `Dive`: TUI tool untuk mengeksplorasi layer image dan mendeteksi berkas redundan yang memboroskan size disk.

---

### 19. Self-Assessment & Hands-On Exercises

#### Skenario 1: Verifikasi File System Layering CoW
Eksekusi container Ubuntu. Buat sebuah file sebesar 100MB di dalam container pada direktori `/root`. Temukan lokasi pasti di host filesystem (`/var/lib/docker/overlay2/.../diff`) di mana file 100MB tersebut tersimpan secara fisik.
*Kriteria Sukses:* Mengidentifikasi file baru di UpperDir host tanpa membuka shell container.

#### Skenario 2: Mengatasi Zombie Process Isolation
Tulis Dockerfile dengan script bash yang secara sengaja me-launch multiple background processes (`sleep 300 &`) dan keluar tanpa menunggu (`wait`). Jalankan container dengan dan tanpa flag `--init`.
*Kriteria Sukses:* Menganalisis table proses melalui `docker exec <container> ps aux` dan melihat bagaimana zombie processes (`<defunct>`) hilang saat mode `--init` aktif.

#### Skenario 3: Hardening Container User Privileges
Diberikan aplikasi berbasis Node.js yang membaca port 80. Lakukan konfigurasi agar container berjalan sebagai user UID 1000 tanpa hak akses root, namun tetap bisa mendengarkan traffic network yang diarahkan kepadanya.
*Kriteria Sukses:* Verifikasi melalui `docker exec <container> id` menghasilkan UID non-zero dan aplikasi tetap running stabil.

#### Skenario 4: Rekonstruksi Failure Exit Code 137
Konfigurasikan sebuah container Python yang mengalokasikan array string masif ke RAM secara eksponensial. Set limit memory container sebesar `32m`.
*Kriteria Sukses:* Observasi `docker logs` dan buktikan exit code yang dihasilkan bernilai tepat 137 menggunakan template `docker inspect`.

#### Skenario 5: Namespace Dismantling
Gunakan tool Linux native `unshare` di environment host Linux Anda untuk membuat process isolasi mandiri (PID dan Mount) tanpa melibatkan Docker sama sekali.
*Kriteria Sukses:* Menjalankan `/bin/sh` di mana proses tersebut hanya melihat dirinya sendiri sebagai PID 1 tanpa bantuan Docker Engine daemon.

---

### 20. References & Further Deep Dive
- **Spesifikasi Formal:**
  - Open Container Initiative (OCI) Runtime Specification: `https://github.com/opencontainers/runtime-spec`
  - OCI Image Format Specification: `https://github.com/opencontainers/image-spec`
- **Linux Kernel Documentation:**
  - Linux Namespaces Reference: `man 7 namespaces`
  - Linux Control Groups Reference: `man 7 cgroups`
  - Overlay Filesystem Architecture: `https://www.kernel.org/doc/Documentation/filesystems/overlayfs.txt`
- **Buku Rujukan Rekomendasi:**
  - *Docker Deep Dive* oleh Nigel Poulton.
  - *Linux Kernel Development* (3rd Edition) oleh Robert Love.
  - *Container Security: Fundamental Technology Concepts that Protect Containerized Applications* oleh Liz Rice.