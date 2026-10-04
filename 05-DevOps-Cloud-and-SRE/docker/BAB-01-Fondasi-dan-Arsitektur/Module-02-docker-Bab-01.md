# Bab 01: Fondasi dan Arsitektur Docker
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, *Principal/Lead Systems Engineer* diharapkan mampu:

1. **Membedah Primitif Linux Kernel**: Mengartikulasikan cara kerja `cgroups v2`, sembilan subsistem `Linux Namespaces`, dan driver penyimpanan `OverlayFS` secara deterministik pada level kernel subsystem.
2. **Menganalisis Runtimes Execution Path**: Memetakan interaksi berurutan antara Docker CLI, Dockerd, Containerd, Containerd-Shim-v2, dan Runc sesuai dengan spesifikasi OCI (*Open Container Initiative*).
3. **Menerapkan Hardening Container Kelas Enterprise**: Membangun image berbasis *multi-stage distroless*, menjalankan mode *rootless container*, mengonfigurasi limitasi granular Linux *capabilities* (`cap-drop`), serta memitigasi isu PID 1 dan proses zombie.
4. **Mendiagnosis Masalah Produksi Kritis**: Mengidentifikasi dan menyelesaikan degradasi performa I/O (*storage engine copy-up overhead*), *Out-of-Memory (OOM) killer invocations*, serta kelelahan inode (*inode exhaustion*) pada kluster host berskala masif.

---

### 2. Prerequisite

Sebelum memulai modul ini, Anda wajib menguasai:
*   **Operating Systems Internals**: Memahami memori virtual, *system calls* (`clone()`, `unshare()`, `pivot_root()`, `mount()`), IPC (*Inter-Process Communication*), POSIX signals (`SIGTERM`, `SIGKILL`), dan alokasi ruang kernel vs *user space*.
*   **Networking L3/L4**: Memahami routing table, iptables/nftables, NAT (*Network Address Translation*), bridge interface, veth pairs, dan encapsulation.
*   **Sistem Berkas Linux**: Struktur file VFS, inode, superblock, dentry, dan driver CoW (*Copy-on-Write*).
*   **Modul 01**: Mengetahui sintaks dasar Docker, instalasi runtime standar, dan siklus hidup container dasar.

---

### 3. Concept & Internal Architecture

Container **bukanlah** virtual machine. Container adalah sebuah proses Linux biasa yang dibatasi (*isolated and resource-constrained process*) melalui fitur-fitur native kernel.

```
+-----------------------------------------------------------------------+
|                              USER SPACE                               |
|                                                                       |
|  +---------------------+                                              |
|  |     Docker CLI      |                                              |
|  +----------+----------+                                              |
|             | (UNIX Socket /var/run/docker.sock)                      |
|             v                                                         |
|  +---------------------+                                              |
|  |       dockerd       |                                              |
|  +----------+----------+                                              |
|             | (gRPC)                                                  |
|             v                                                         |
|  +---------------------+       +------------------------------------+ |
|  |     containerd      | ----> | containerd-shim-v2 (1 per pod/cnt) | |
|  +---------------------+       +-----------------+------------------+ |
|                                                  |                    |
|                                                  v                    |
|                                        +-------------------+          |
|                                        |  runc (OCI CLI)   |          |
|                                        +---------+---------+          |
+--------------------------------------------------|--------------------+
|                             KERNEL SPACE         |                    |
|                                                  v                    |
|  +-----------------------------------------------------------------+  |
|  | System Calls: clone(2), unshare(2), setns(2), pivot_root(2)     |  |
|  +-----------------------------------------------------------------+  |
|  |                           Namespaces                            |  |
|  | [pid] [net] [mnt] [ipc] [uts] [user] [cgroup] [time]            |  |
|  +-----------------------------------------------------------------+  |
|  |                           cgroups v2                            |  |
|  | [cpu.max] [memory.high/max] [io.weight] [pids.max]              |  |
|  +-----------------------------------------------------------------+  |
|  |                         Storage Driver                          |  |
|  | OverlayFS: [lowerdir (RO)] + [upperdir (RW)] = [merged (VFS)]   |  |
|  +-----------------------------------------------------------------+  |
+-----------------------------------------------------------------------+
```

#### 3.1. Linux Namespaces: Isolasi Eksekusi
Linux Kernel menyediakan isolasi melalui `syscall` `clone()` dengan bit flag tertentu:
*   `CLONE_NEWPID`: Menyediakan pohon PID independen. Proses di dalam container menjadi PID 1 bagi container tersebut, tetapi tetap memiliki PID riil pada host namespace.
*   `CLONE_NEWNET`: Memisahkan antarmuka jaringan, routing table, firewall rule (iptables/nftables), dan port allocation.
*   `CLONE_NEWMNT`: Mengisolasi hierarki mount point. Didukung oleh `pivot_root()` untuk mengganti root file system (`/`) container dari host.
*   `CLONE_NEWIPC`: Memisahkan System V IPC dan POSIX message queues.
*   `CLONE_NEWUTS`: Memisahkan Hostname dan domain NIS.
*   `CLONE_NEWUSER`: Memetakan UID dan GID container ke rentang non-privileged UID/GID pada host (krusial untuk keamanan).
*   `CLONE_NEWCGROUP`: Mengisolasi pandangan proses terhadap hirarki cgroup miliknya sendiri.
*   `CLONE_NEWTIME`: Mengisolasi jam sistem (`CLOCK_MONOTONIC` dan `CLOCK_BOOTTIME`).

#### 3.2. cgroups v2 (Control Groups): Regulasi Sumber Daya
Berbeda dari cgroups v1 yang memiliki hierarki terpisah untuk setiap controller (cpu, mem, io), **cgroups v2** menerapkan model hierarki tunggal (*unified hierarchy*) di bawah `/sys/fs/cgroup`.
*   **Memory Management**:
    *   `memory.min`: Hard memory protection (tidak akan terkena reclaim di bawah nilai ini).
    *   `memory.low`: Best-effort protection.
    *   `memory.high`: Throttling threshold. Jika terlampaui, alokasi memori proses diperlambat dan kernel melakukan reclaim agresif sebelum OOM Killer aktif.
    *   `memory.max`: Hard limit. Jika tembus dan reclaim gagal, OOM killer mengeksekusi proses dengan `oom_score_adj` tertinggi.
*   **CPU Throttling**:
    *   `cpu.max`: Mengatur kuota waktu CPU dalam periode tertentu (misal: `100000 100000` = 1 core penuh; `50000 100000` = 0.5 core).
*   **eBPF Integration**: cgroups v2 terintegrasi native dengan program BPF (misal `cgroup-bpf` untuk network filtering dan sys-call tracing langsung pada level grup).

#### 3.3. OverlayFS: Model Penyimpanan Copy-on-Write (CoW)
OverlayFS bekerja di atas virtual file system (VFS) dengan menggabungkan dua atau lebih direktori:
*   **Lowerdir**: Kumpulan layer image read-only (immutable).
*   **Upperdir**: Layer penulisan container read-write (ephemeral).
*   **Workdir**: Direktori internal kernel untuk menyiapkan atomic operations sebelum diekspos ke upperdir.
*   **Merged**: Mount point yang dilihat oleh container.

```
 Merged Directory (Container View: /)
 +-------------------------------------------------------+
 |  /etc/hosts (RW)  |  /app/bin (RO)  |  /var/log (RW)  |
 +-------------------------------------------------------+
               ^                       ^
               |                       |
 +-------------+--------+      +--------+----------------+
 | Upperdir (RW Layer)  |      | Workdir (Atomic Prep)   |
 | Modifikasi & File Baru|     | Temporary kernel state  |
 +----------------------+      +-------------------------+
               ^
               | (Read Fallthrough & Copy-Up Engine)
 +-------------+-----------------------------------------+
 | Lowerdir Layer N (Read-Only: Layer Aplikasi)          |
 +-------------------------------------------------------+
 | Lowerdir Layer 1..N-1 (Read-Only: Dependencies/BaseOS)|
 +-------------------------------------------------------+
```

*Mekanisme Copy-Up*: Saat container ingin memodifikasi file yang ada di `lowerdir`, kernel menyalin seluruh isi file tersebut dari `lowerdir` ke `upperdir` sebelum operasi tulis dijalankan. Operasi ini menyebabkan I/O amplification pada file berukuran besar.

#### 3.4. Runtime Chain: Docker ke Kernel
1.  **Docker CLI**: Mengirim HTTP REST Payload JSON ke daemon Docker.
2.  **Dockerd**: Mengautentikasi request, mengelola state jaringan (bridge), volume, dan mendelegasikan eksekusi kontainer ke `containerd` via gRPC interface.
3.  **Containerd**: Mengelola siklus hidup container secara utuh: distribusi image, snapshot storage management, dan eksekusi task.
4.  **Containerd-Shim-v2**: Menjadi parent process dari kontainer. Memungkinkan `runc` untuk exit setelah spawning kontainer, sehingga daemon engine dapat di-restart tanpa mematikan kontainer berjalan (*daemonless containers*), serta memegang file descriptor I/O (stdin/stdout/stderr).
5.  **Runc**: Implementasi referensi spesifikasi runtime OCI. Memanggil fungsi `clone()`, menerapkan cgroups, menyetel capabilities, memanggil `pivot_root()`, lalu memanggil `execve()` untuk menjalankan *entrypoint*.

---

### 4. Why & What

| Dimensi | Mengapa Relevan di Level Enterprise? | Apa yang Harus Diimplementasikan? |
| :--- | :--- | :--- |
| **Isolasi Keamanan** | Container breakout melalui shared kernel adalah ancaman fatal (*privilege escalation*). | Non-root runtime, User Namespaces mapping, drop dangerous capabilities (`CAP_SYS_ADMIN`, `CAP_NET_RAW`), seccomp filter profiles. |
| **Determinisme Resource** | *Noisy neighbor effect* dapat melumpuhkan layanan Tier-1 pada mesin yang sama. | Cgroups v2 throttling via `memory.high` & `cpu.max`, serta tuning IO scheduler limit. |
| **Build & Deploy Velocity** | Image yang besar (>1GB) memperlambat CI/CD runner dan menyita bandwidth registry. | Multi-stage build, base image *Distroless* atau *Alpine*, stripping debug symbols, dan minimalisasi layer. |
| **Observabilitas Host** | Kegagalan mendeteksi proses zombie menyebabkan kelelahan tabel PID Linux kernel (`PID exhaustion`). | Init processes integration (`tini`/`dumb-init`), penanganan POSIX Signals (`SIGTERM`, `SIGKILL`) yang deterministik. |

---

### 5. How (Workflow Detail)

Alur kerja implementasi sistem produksi berbasis Docker:

```
[ Developer Commit ] 
        |
        v
[ CI Pipeline: Multi-Stage Build Engine ]
        |-- Compile & Link Static Binaries
        |-- Strip Debug Symbols (strip -s)
        |-- Static Security Scan (Trivy/Grype)
        |-- Extract Artifact to Distroless/Scratch
        v
[ Image Registry (OCI Compliant) ]
        |-- Cosign Signature Verification
        v
[ Host Deployment via Orchestrator/Daemon ]
        |-- Pull Layer Snapshots via containerd
        |-- Create Network Namespace (veth-pair creation & IPAM)
        |-- Apply cgroups v2 Hierarchical Limits
        |-- Drop Capabilities & Apply Seccomp Profile
        |-- Shim-v2 Spawns Runc -> pivot_root -> execve
        v
[ Production Container Lifecycle ]
        |-- PID 1 Subreaper Management
        |-- Graceful Shutdown Handler (SIGTERM -> Flush -> SIGKILL)
```

1.  **Fase Kompilasi**: Jalankan builder container sementara dengan dependensi kompilasi lengkap.
2.  **Fase Assembling Artifact**: Salin hanya file biner terkompilasi dan file konfigurasi runtime ke base image minimal (scratch/distroless).
3.  **Fase Provisioning Host**: Host daemon mengeksekusi unpacking layer secara paralel menggunakan Content Addressable Storage (CAS).
4.  **Fase Hardening Runtime**: Shim mengeksekusi runc dengan file `config.json` terenkapsulasi: UID diset ke non-zero, isolasi seccomp diaktifkan, no-new-privileges di-flag true.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Apartemen Bertingkat (Container) vs Kompleks Perumahan Mandiri (VM)
*   **Virtual Machine (Kompleks Rumah Mandiri)**: Memiliki pondasi beton sendiri, sistem pemipaan mandiri, generator listrik sendiri, dan petugas pos sendiri (Guest OS, Kernel, Virtual Hardware). Sangat aman, tetapi butuh waktu lama untuk dibangun dan memakan banyak tempat.
*   **Container (Apartemen)**: Menggunakan satu pondasi bersama, pipa air utama bersama, dan gardu listrik terpusat milik gedung (Host Linux Kernel). Setiap unit apartemen dipasangi dinding kedap suara (Namespaces) dan meteran listrik/air per unit (cgroups). Jika satu unit membakar listrik berlebih, sekring unit tersebut akan putus sendiri tanpa mengganggu unit lain (cgroup limits).

#### Diagram Transisi Eksekusi Runc & Shim
```
Host System
+--------------------------------------------------------------------------+
| containerd                                                               |
|    |                                                                     |
|    | (Spawns)                                                            |
|    v                                                                     |
| containerd-shim-v2 (PID: 1042)                                           |
|    |                                                                     |
|    |--- fork/exec ---> runc create (PID: 1055)                           |
|    |                      |                                              |
|    |                      |-- clone(CLONE_NEWPID | CLONE_NEWNET ...)     |
|    |                      |-- pivot_root()                               |
|    |                      |-- setuid(65534)                              |
|    |                      v                                              |
|    |                   Container Process (PID: 1056 on host, PID: 1 in NS)
|    |                      |                                              |
|    |                   runc exits (1055 dead)                            |
|    |                                                                     |
|    | (Adopted)                                                           |
|    +-----------------> Container Process (PID: 1056)                     |
|                        (Streams Stdout/Stderr via Shim FIFO)             |
+--------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example (Anti-Pattern vs Pattern Dasar)
**Anti-Pattern**:
```dockerfile
# JANGAN GUNAKAN DI PRODUKSI
FROM ubuntu:latest
RUN apt-get update && apt-get install -y nodejs npm
COPY . /app
WORKDIR /app
RUN npm install
CMD node server.js
```
*Kelemahan*: Menjalankan aplikasi sebagai `root`, image berukuran >800MB, node_modules memuat compiler dependensi, sinyal POSIX tidak tertangkap karena menggunakan shell syntax (`CMD node server.js`).

#### 7.2. Practical Example (Production-Ready Architecture)
Berikut adalah implementasi microservice Go berbasis **Multi-stage distroless build**, **unprivileged user execution**, dan **explicit signal routing**.

**File: `Dockerfile`**
```dockerfile
# syntax=docker/dockerfile:1.4
# BUILD STAGE
FROM golang:1.22-bookworm AS builder

WORKDIR /src

# Caching dependency layer
COPY go.mod go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod \
    go mod download -x

COPY . .

# Compile target binary dengan flags optimasi & statis penuh
# -ldflags="-w -s": Menghapus DWARF debugging information dan symbol table
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build -trimpath -ldflags="-w -s -extldflags '-static'" -o /bin/api-server ./cmd/server

# RUNTIME STAGE (Scratch-based Distroless)
# Menggunakan base distroless static dari Google Container Tools
FROM gcr.io/distroless/static-debian12:nonroot

LABEL maintainer="infrastructure-team@enterprise.com"
LABEL security.hardened="true"

WORKDIR /app

# Copy binary dari stage builder
COPY --from=builder --chown=nonroot:nonroot /bin/api-server /app/api-server

# Gunakan dynamic port mapping non-privileged (UID: nonroot = 65532)
USER nonroot:nonroot

EXPOSE 8080

# Menggunakan format exec, bukan shell form, agar sinyal kernel diteruskan langsung
ENTRYPOINT ["/app/api-server"]
```

**File: `docker-compose.prod.yml` (Hardened Deployment Configuration)**
```yaml
version: '3.8'

services:
  payment-gateway:
    image: enterprise/payment-api:1.4.2
    build:
      context: .
      dockerfile: Dockerfile
    restart: always
    user: "65532:65532"
    read_only: true
    tmpfs:
      - /tmp:rw,noexec,nosuid,size=64m
    security_opt:
      - no-new-privileges:true
      - seccomp=./seccomp-profile.json
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 512M
          pids: 100
        reservations:
          cpus: '0.5'
          memory: 256M
    logging:
      driver: "json-file"
      options:
        max-size: "20m"
        max-file: "5"
    networks:
      - internal_backend

networks:
  internal_backend:
    driver: bridge
    internal: true
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
*   **Perusahaan**: Bank Digital Nasional (FinTech Tier-1).
*   **Volume**: 65.000 Request Per Second (RPS) pada microservice Payment Core Engine.
*   **Insiden**: Saat lonjakan beban akhir bulan, sejumlah node host tiba-tiba mengalami *unresponsive freeze* (I/O hang), dan puluhan container mendadak mengalami `CrashLoopBackOff` massal secara berantai.

#### Analisis Akar Masalah (Root Cause Analysis - RCA)
1.  **OverlayFS Inode & Copy-Up Overhead**: Layanan menulis temporary transaction logs langsung ke `/app/logs` yang berada pada root storage layer container (bukan volume/tmpfs). Setiap thread transaksi membuat copy-up dari file log berukuran ratusan megabyte di `lowerdir` ke `upperdir`, memicu disk write saturation pada disk SSD host.
2.  **Kelelahan Inode**: File log berukuran kecil yang tidak di-rotate menghabiskan struktur Inode pada host disk (`df -i` menunjukkan 100% inode utilization meskipun disk capacity tersisa 40%).
3.  **Zombie Process Proliferation**: Subproses audit yang dipanggil runtime container tidak di-reap oleh engine karena aplikasi Go tidak mengimplementasikan subreaper pattern dan berjalan langsung sebagai PID 1 tanpa init binary. Hal ini menyebabkan tabel PID Linux host (default: `/proc/sys/kernel/pid_max`) penuh.
4.  **Cgroup v1 Hard-kill**: Memory limit menyentuh hard cap dan seketika mengeksekusi `OOM-Kills` tanpa grace period.

#### Arsitektur Solusi & Resolusi
1.  **Refactoring Penyimpanan**: 
    *   Mengalihkan seluruh I/O sementara ke `tmpfs` RAM disk dengan batasan kuota eksplisit (`size=128m`).
    *   Mengalihkan log terstruktur secara eksklusif ke `stdout` yang ditangkap logging daemon async (Vector/FluentBit) yang membaca langsung dari UNIX socket containerd.
2.  **Sistem Inisialisasi Tini**:
    *   Mengintegrasikan `tini` binary sebagai PID 1 untuk meneruskan `SIGTERM` secara instan dan memanggil `waitpid()` untuk membersihkan proses anak yang mati (zombie cleaner).
3.  **Transisi ke cgroups v2**:
    *   Memperbarui Linux kernel host ke 6.1 LTS untuk mengaktifkan **cgroups v2 unified hierarchy**.
    *   Menerapkan parameter `memory.high` sebagai throttling warning sebelum memicu limit destruktif `memory.max`.
4.  **Audit Cap Drop**:
    *   Menghilangkan seluruh kapabilitas kernel host kecuali kapabilitas esensial jaringan melalui `cap_drop: [ALL]`.

```
SEBELUM:
[App (PID 1)] ---> fork() ---> [Audit CLI (Zombie)] (PID exhaustion)
[App File I/O] ---> [OverlayFS Upperdir] ---> [Direct Host Disk (I/O Freeze & Inode Out)]

SESUDAH:
[Tini (PID 1)] ---> [App (PID 2)] (Signal handling & Zombie reaping OK)
[App File I/O] ---> [tmpfs /tmp (RAM)] (No host storage impact)
[App Logs]     ---> [/dev/stdout] ---> [containerd FIFO] ---> [FluentBit Engine]
```

---

### 9. Trade-offs

| Pendekatan / Fitur | Keuntungan | Konsekuensi / Trade-off |
| :--- | :--- | :--- |
| **Scratch / Distroless Base** | Meminimalisir attack surface, zero CVE vulnerabilities, ukuran image < 20MB. | Ketiadaan tool debugging (`sh`, `bash`, `curl`, `lsof`). Membutuhkan implementasi *ephemeral debug containers* atau *chroot execution* untuk troubleshooting. |
| **Rootless Container Execution** | Container breakout tidak memberikan hak akses root pada OS host. Proteksi maksimal. | Keterbatasan integrasi jaringan (tidak bisa bind port di bawah 1024 tanpa network namespaces mapping/sysctl capabilities), isu mounting storage NFS/CIFS. |
| **OverlayFS CoW vs Direct Bind Volume** | Kemudahan deployment portabel, image bersifat hermetik dan independen. | Overhead latensi penulisan (write penalty) akibat mekanisme *copy-up*. Tidak cocok untuk throughput I/O intensif seperti DBMS atau Kafka. |
| **Granular Cgroups Limiting (CPU & RAM)** | Mencegah resource contention antar container, prediktabilitas SLA host. | Latensi komputasi meningkat jika setting CPU quota terlalu ketat (*CPU throttling*). Peningkatan frekuensi alokasi memori dapat memicu OOM Killer jika sizing salah. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Common Mistakes
1.  **Format Shell pada ENTRYPOINT/CMD**: Menggunakan `ENTRYPOINT /app/run` alih-alih `ENTRYPOINT ["/app/run"]`. Format shell menyebabkan `/bin/sh -c` menjadi PID 1. Shell tidak mem-forward sinyal POSIX (`SIGTERM`), akibatnya container mengalami latency shutdown selama 10 detik dan dimatikan paksa via `SIGKILL`.
2.  **Mengabaikan `.dockerignore`**: Menyertakan folder `.git`, `.env`, atau secret keys ke dalam image build context. Menambah ukuran transfer socket Docker engine dan membuka celah kebocoran rahasia.
3.  **Menjalankan Service Menggunakan Privilege Root**: Membiarkan default container run sebagai `root` (UID 0), memberikan akses kernel surface penuh jika terjadi escape vulnerability (contoh: CVE-2024-21626).
4.  **Pemberian `--privileged` Flag**: Menghapus seluruh batas isolasi kernel, mengekspos semua `/dev` perangkat host ke dalam container.

#### 10.2. Troubleshooting Framework

##### Kasus A: Debugging Zombie Processes
*Gejala*: Jumlah PID di sistem meningkat secara linear, kontainer menolak spawning proses baru (`fork: cannot allocate memory`).
*Tindakan Diagnostik*:
```bash
# Cek zombie processes pada namespace container
ps -ef | grep 'defunct'

# Telusuri parent PID
pstree -p -s <ZOMBIE_PID>
```
*Solusi*: Masukkan `tini` sebagai entrypoint proxy:
```dockerfile
ENTRYPOINT ["/sbin/tini", "--", "/app/my-binary"]
```

##### Kasus B: Mendiagnosis CPU Throttling yang Tidak Wajar
*Gejala*: Aplikasi terasa lambat meskipun penggunaan CPU host terpantau rendah.
*Tindakan Diagnostik*:
```bash
# Periksa metrik cgroups v2 throttled time (Ganti <CONTAINER_ID>)
cat /sys/fs/cgroup/system.slice/docker-<CONTAINER_ID>.scope/cpu.stat

# Output yang harus diperhatikan:
# nr_periods 12450
# nr_throttled 4320     <-- Jika angka ini tinggi, limit CPU terlalu ketat
# throttled_usec 245021234
```
*Solusi*: Tingkatkan kuota nilai `cpu.max` atau kurangi concurrency/thread pools di level bahasa pemrograman (misal: set `GOMAXPROCS` pada Go).

##### Kasus C: Container Crash Mendadak Tanpa Jejak Log
*Gejala*: Container tiba-tiba mati dengan Exit Code 137.
*Tindakan Diagnostik*:
```bash
# Konfirmasi penyebab kematian oleh kernel OOM Killer
dmesg -T | grep -E -i 'killed process|oom_reaper'

# Alternatif via docker inspect
docker inspect <CONTAINER_ID> --format '{{.State.OOMKilled}}'
```
*Solusi*: Evaluasi memory profiling heap allocators, naikkan limit memori, atau pasang threshold `memory.high` untuk throttling proaktif sebelum terminal eviction.

---

### 11. Best Practices (Production Checklist)

#### Security & Hardening
- [ ] Image tidak mengandung shell runtime di produksi (gunakan *Distroless* atau *Scratch*).
- [ ] Container dideklarasikan berjalan di user non-root (`USER 10001:10001`).
- [ ] Akses rootfs dibatasi menjadi read-only (`--read-only` flag diaktifkan).
- [ ] Seluruh kapabilitas kernel dimatikan via `cap-drop=ALL`; tambahkan hanya yang terbukti esensial.
- [ ] Flag `no-new-privileges:true` disetel untuk mencegah eksploitasi suid binaries.
- [ ] Base layer image dipindai secara kontinu terhadap CVE (Trivy/Clair/Snyk) di pipeline CI/CD.

#### Reliability & Resource Control
- [ ] Limit memori dan CPU disetel secara eksplisit (CPU Quota & Period, Memory Max & Reservation).
- [ ] PID limiter diterapkan (`--pids-limit`) guna mencegah serangan fork-bomb.
- [ ] Healthcheck internal didefinisikan menggunakan protokol non-exec jika memungkinkan (misal endpoint liveness L4/L7).
- [ ] Log dikirimkan murni ke stdout/stderr, dengan implementasi rotasi log terkonfigurasi pada host Docker daemon.
- [ ] Alokasi penyimpanan sementara yang intensif dialihkan ke mount memory `tmpfs`.

---

### 12. Hands-on Practice

Buat dan selesaikan latihan berikut di direktori target: `hands-on/m02/`.

#### Struktur Direktori Latihan
```bash
mkdir -p hands-on/m02/{src,config}
cd hands-on/m02/
```

#### Langkah 1: Buat Source Code Mock Microservice (Go)
Tulis file `src/main.go` yang mensimulasikan web service dengan listener signal handling graceful:

```go
// hands-on/m02/src/main.go
package main

import (
	"context"
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
		w.Write([]byte("HEALTHY\n"))
	})

	server := &http.Server{
		Addr:    ":8080",
		Handler: mux,
	}

	stopChan := make(chan os.Signal, 1)
	signal.Notify(stopChan, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		fmt.Println("[INIT] Server running on port 8080...")
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			fmt.Printf("[FATAL] Listen error: %v\n", err)
			os.Exit(1)
		}
	}()

	sig := <-stopChan
	fmt.Printf("[SHUTDOWN] Signal %v received. Performing atomic teardown...\n", sig)

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := server.Shutdown(ctx); err != nil {
		fmt.Printf("[ERROR] Graceful shutdown failed: %v\n", err)
		os.Exit(1)
	}

	fmt.Println("[EXIT] Clean server termination completed.")
}
```

#### Langkah 2: Buat Dockerfile Enterprise Multi-Stage
Tulis file `Dockerfile` pada direktori root praktikum:

```dockerfile
# hands-on/m02/Dockerfile
FROM golang:1.22-alpine AS build-env
WORKDIR /app
COPY src/main.go .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -o enterprise-svc main.go

FROM gcr.io/distroless/static-debian12:nonroot
WORKDIR /app
COPY --from=build-env --chown=nonroot:nonroot /app/enterprise-svc /app/
USER nonroot:nonroot
EXPOSE 8080
ENTRYPOINT ["/app/enterprise-svc"]
```

#### Langkah 3: Konfigurasi Deployment Compose dengan Cgroups & Hardening
Tulis file `docker-compose.yml`:

```yaml
# hands-on/m02/docker-compose.yml
version: '3.8'

services:
  secure-service:
    build: .
    ports:
      - "8080:8080"
    user: "65532:65532"
    read_only: true
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    deploy:
      resources:
        limits:
          cpus: '0.25'
          memory: 64M
          pids: 20
```

#### Langkah 4: Validasi dan Operasi Runtime
Jalankan runtutan instruksi berikut di terminal Anda:

```bash
# 1. Build image dan verifikasi ukuran akhir
docker compose build
docker images | grep hands-on-m02-secure-service

# 2. Jalankan container secara detached
docker compose up -d

# 3. Verifikasi ketiadaan hak privilege root dan proses
docker top hands-on-m02-secure-service-1 -o user,pid,comm

# 4. Uji Graceful Shutdown dan analisis streaming log time
time docker compose stop
```

Perhatikan bahwa output `time` saat melakukan `docker compose stop` selesai dalam rentang milidetik, bukan default timeout 10 detik. Ini memvalidasi sinyal `SIGTERM` berhasil dikirim dan ditangkap langsung oleh biner aplikasi.

---

### 13. Exercise

#### Level Easy
Buat `Dockerfile` yang membedakan proses build dan runtime untuk aplikasi NodeJS standar. Syarat: runtime stage wajib dieksekusi oleh user non-root default NodeJS (`node`), image akhir tidak boleh memuat compiler Python/C++ (yang sering dibutuhkan saat `npm rebuild`), dan working directory harus read-only.

#### Level Medium
Konfigurasikan container Nginx yang sepenuhnya mengisolasi sistem berkasnya (`--read-only`). Tangani seluruh direktori yang membutuhkan akses penulisan native Nginx (seperti `/var/cache/nginx`, `/var/run`, `/var/log/nginx`) menggunakan alokasi in-memory (`tmpfs`) tanpa menggunakan named volumes ataupun bind mounts fisik ke host disk.

#### Level Hard
Buat script Bash mandiri yang mensimulasikan container runtime mini tanpa engine Docker sama sekali. Script harus membuat network namespace baru, UTS namespace baru, mount namespace baru, menggunakan `chroot` (atau `pivot_root`) ke rootfs minimal (Alpine minirootfs), dan menerapkan alokasi limit memori maksimum 30MB menggunakan hierarki cgroups v2 (`/sys/fs/cgroup/`) langsung via kernel interface.

---

### 14. Challenge

**Studi Kasus Sistem**: Anda menjabat sebagai Principal Platform Engineer pada perusahaan SaaS FinTech. Sebuah microservice batch processing bernama `clearing-engine` mengalami restart intermiten setiap hari pada pukul 00:00 saat volume transaksi melonjak drastis. 

**Kondisi Lingkungan**:
*   Metrik APM NewRelic/Datadog tidak menangkap *stacktrace error* atau *panic exception*.
*   Container running di host Linux kernel 5.15 dengan Docker engine 24.x.
*   Container berjalan dengan flag alokasi: `--memory=4g --memory-swap=4g --cpus=4`.
*   Direktori `/data/recon` di-mount ke container menggunakan host bind mount dari storage pool NVMe.

**Tugas Anda**:
Rancang dokumen rencana investigasi post-mortem dan rekomendasi arsitektur perbaikan menyeluruh yang mencakup:
1.  Metodologi pelacakan sistem kernel untuk membuktikan apakah isu ini berakar pada *silent cgroup OOM killer*, *page-cache saturation lock*, atau *thread starvation* pada level kernel.
2.  Desain arsitektur penyimpanan alternatif guna mengeliminasi kemungkinan *filesystem lock contention* saat ribuan thread memproses file mutasi secara paralel.
3.  Desain implementasi konfigurasi cgroups v2 granular (termasuk metrik PSI - *Pressure Stall Information*) untuk memitigasi kegagalan serupa agar engine melakukan self-throttling, bukan mati mendadak.

*(Selesaikan tantangan ini murni melalui analisis sistem operasi internal dan runtime spec tanpa bergantung pada platform auto-recovery).*

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Pertanyaan)
1. Apa fungsi mendasar dari flag `CLONE_NEWPID` pada system call `clone()` Linux?
2. Mengapa format exec syntax (`ENTRYPOINT ["app"]`) lebih disarankan di lingkungan produksi dibandingkan shell syntax (`ENTRYPOINT app`)?
3. Sebutkan layer yang menyusun struktur filesystem OverlayFS dan jelaskan layer mana yang bersifat read-write.
4. Apa yang menyebabkan sebuah proses container berstatus `defunct` (Zombie), dan apa risiko sistemiknya terhadap host?
5. Mengapa image base *Distroless* lebih unggul secara postur keamanan dibandingkan image base *Ubuntu Minimal*?

#### Intermediate (5 Pertanyaan)
1. Jelaskan perbedaan arsitektur cgroups v1 vs cgroups v2, khususnya dalam cara kernel menangani batas alokasi memori gabungan dan I/O controller!
2. Bagaimana mekanisme interaksi antara `containerd-shim-v2` dan `runc` memungkinkan proses container tetap beroperasi tanpa downtime saat Docker Engine daemon (`dockerd`) di-restart?
3. Mengapa eksekusi container dengan flag `--cap-drop=ALL` ditambah `--cap-add=NET_BIND_SERVICE` jauh lebih aman daripada sekadar mengeksekusinya menggunakan regular UID non-root tanpa modifikasi capabilities?
4. Apa yang terjadi di level kernel (VFS & disk I/O) saat container pertama kali mencoba menambahkan baris baru ke file berukuran 5GB yang telah ada di `lowerdir` OverlayFS?
5. Bagaimana cara kerja flag `no-new-privileges:true` dalam memblokir eksploitasi celah keamanan yang melibatkan binary berlabel `setuid` (seperti `/bin/su` atau `/usr/bin/sudo`) di dalam container?

#### Skenario Kasus Produksi (3 Kasus)
1. **Kasus A**: Sebuah microservice Go yang berjalan di container dengan limit CPU `1.0` menunjukkan metrik penggunaan CPU host hanya 30%, namun latensi API P99 membengkak drastis dari 10ms menjadi 1200ms saat diuji beban concurency tinggi. Apa kemungkinan penyebabnya pada layer kernel cgroup, dan parameter metrik apa yang harus dianalisis?
2. **Kasus B**: Tim keamanan mendeteksi bahwa salah satu node host Docker mengalami crash global akibat kehabisan disk space, padahal perintah `df -h` menunjukkan sisa kapasitas disk masih 55%. Apa yang sebenarnya terjadi di level filesystem host, dan bagaimana cara memvalidasinya?
3. **Kasus C**: Aplikasi Node.js di dalam container dihentikan via pipeline deployment menggunakan perintah `docker stop <container_id>`. Tim mengamati bahwa pod selalu membutuhkan waktu tepat 10 detik untuk terminate. Jelaskan cascade kegagalan yang terjadi di dalam process tree container tersebut!

---

### 16. Summary

1.  **Fundamen Primitif**: Docker container bukanlah representasi virtualisasi hardware, melainkan proses Linux standar yang diisolasi oleh sembilan **Linux Namespaces** dan dibatasi secara ketat oleh **cgroups (v1/v2)**.
2.  **Runtime Decoupling**: Standarisasi **OCI** membagi arsitektur engine menjadi sub-komponen: `dockerd` (orkestrasi lokal), `containerd` (lifecycle management), `containerd-shim-v2` (daemonless container binding), dan `runc` (spawner container tingkat kernel via OCI runtime spec).
3.  **Efisiensi dan Bottleneck Storage**: Driver penyimpanan **OverlayFS** bekerja melalui penggabungan *lowerdir* dan *upperdir*. Operasi penulisan pertama pada file statis memicu overhead *copy-up* yang berpotensi membebani performa I/O jika arsitektur penyimpanan tidak didesain dengan benar.
4.  **Security Baseline Produksi**: Operasional enterprise mewajibkan container berjalan dengan paradigma non-root (`USER nonroot`), root filesystem bersifat read-only (`--read-only`), pembersihan seluruh privilege kernel (`cap-drop=ALL`), pengaktifan proteksi eksekusi privilese (`no-new-privileges`), serta pemanfaatan base image minimal (*Distroless/Scratch*).
5.  **Signal Propagation & Process Reaping**: Menggunakan format exec pada *entrypoint* dan memastikan adanya init system (seperti `tini`) adalah imperatif operasional untuk menjamin penanganan sinyal terminasi (`SIGTERM`) yang deterministik dan pembersihan proses zombie secara real-time.