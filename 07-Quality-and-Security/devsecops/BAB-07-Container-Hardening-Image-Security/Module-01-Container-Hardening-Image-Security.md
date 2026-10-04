# Bab 07 Module 01: Container Hardening & Image Security

---

## 1. Identitas Modul

* **Track**: DevSecOps
* **Kategori**: 07-Quality-and-Security
* **Bab**: 07 - Container Hardening & Image Security
* **Tingkat Kesulitan**: Advanced
* **Prasyarat**: Pemahaman mendalam tentang Linux OS Internals (Namespaces, Cgroups, POSIX), dasar arsitektur Docker/OCI Runtime, CI/CD Pipeline automation, serta dasar protokol jaringan TCP/IP.
* **Estimasi Waktu**: 240 Menit (Teori mendalam, konfigurasi kode keamanan, dan hands-on lab).

---

## 2. Learning Objectives (LO)

Setelah menyelesaikan modul ini, peserta diharapkan mampu:

* **LO-01**: Mengarsitekturkan *Multi-stage Docker Builds* secara efisien untuk memisahkan kompilasi dependensi dari *runtime image* guna meminimalkan jejak biner.
* **LO-02**: Mengimplementasikan *Distroless Images* pada aplikasi produksi untuk menghilangkan vektor serangan berbasis *shell*, *package manager*, dan utilitas sistem operasi standar.
* **LO-03**: Menerapkan dan memvalidasi *Non-Root UID Enforcement* baik di level instruksi container engine maupun orkestrator guna mencegah eskalasi hak akses host.
* **LO-04**: Mengintegrasikan sistem *Vulnerability Scanning* dan *Software Bill of Materials* (SBOM) otomatis ke dalam pipeline CI/CD dengan *remediation policy gates*.
* **LO-05**: Mengonfigurasi dan membatasi *Linux Capabilities* menggunakan prinsip *least privilege* (`CAP_DROP=ALL`).
* **LO-06**: Merancang, menguji, dan menegakkan *Secure Computing Mode* (Seccomp) profiles untuk memfilter *system calls* (syscalls) berbahaya dari container.
* **LO-07**: Mengonstruksi profil *AppArmor* kustom untuk membatasi akses sistem berkas, jaringan, dan eksekusi biner di tingkat Linux Security Modules (LSM).
* **LO-08**: Mendiagnosis serta memitigasi anomali *runtime* dan kegagalan sistem sandboxing tanpa mengorbankan performa aplikasi.

---

## 3. Concept Map & Architecture Diagram

```
+----------------------------------------------------------------------------------------------------+
|                                    CI/CD BUILD & ARTIFACT PIPELINE                                 |
+----------------------------------------------------------------------------------------------------+
| [Source Code]                                                                                      |
|       |                                                                                            |
|       v                                                                                            |
| [Multi-Stage Build] ---> [Builder Stage: SDK, Compilers, Headers]                                  |
|       |                                                                                            |
|       +----------------> [Artifact Stripping: Static Binary, Minimal Libs]                         |
|                                     |                                                              |
|                                     v                                                              |
|                          [Distroless Base Image]                                                   |
|                                     |                                                              |
|                                     v                                                              |
|                          [Static Vulnerability Scan] ---> (CVE Detection & SBOM Generation)        |
|                                     |                     [Block if Critical/High CVE > 0]         |
|                                     v                                                              |
|                          [Secure Registry (Harbor)]                                                |
+----------------------------------------------------------------------------------------------------+
                                      |
                                      v Image Pull
+----------------------------------------------------------------------------------------------------+
|                                LINUX HOST RUNTIME (SANDBOXING LAYER)                               |
+----------------------------------------------------------------------------------------------------+
|  USER SPACE                                                                                        |
|  +-----------------------------------------------------------------------------------------------+ |
|  | Container Sandbox (OCI Runtime / runc)                                                        | |
|  | - Non-Root UID Enforcement (e.g., UID 65532: nonroot)                                         | |
|  | - Read-Only Root Filesystem (`--read-only`)                                                    | |
|  | - Isolated Namespaces: PID, MNT, NET, IPC, UTS, USER                                           | |
|  | - Cgroups v2 Resource Constraints: CPU, Memory, PIDs Limit                                    | |
|  +-----------------------------------------------------------------------------------------------+ |
|         |                                        |                                    |            |
|         v (Syscall Request)                      v (File/Net Access)                  v (Privilege)|
+---------|----------------------------------------|------------------------------------|------------+
|  KERNEL SPACE                                                                                      |
|  +------v-----------------+            +---------v------------+             +---------v----------+ |
|  |     SECCOMP-BPF        |            |   APPARMOR / LSM     |             | LINUX CAPABILITIES | |
|  | (Syscall Filter Engine)|            |  (Path-based MAC)    |             |  (Posix Privilege) | |
|  |                        |            |                      |             |                    | |
|  | Action:                |            | Rule:                |             | Drop: ALL          | |
|  | - SCMP_ACT_ALLOW       |            | - Deny /proc, /sys   |             | Add: NET_BIND_SRV  | |
|  | - SCMP_ACT_ERRNO(EPERM)|            | - Ro/Rw File Bounds  |             | Block root escal.  | |
|  +------------------------+            +----------------------+             +--------------------+ |
|                                      |                                                             |
|                                      v                                                             |
|                                [Linux Kernel Core]                                                 |
+----------------------------------------------------------------------------------------------------+
```

---

## 4. Mengapa Ini Penting (Why & Business / Security Impact)

Kontainerisasi memisahkan dependensi aplikasi pada tingkat pengguna (*user space*), namun kontainer berbagi *kernel* yang sama dengan *host operating system*. Kegagalan mengisolasi kontainer secara ketat menimbulkan risiko keamanan yang substansial:

1. **Host Compromise via Container Escape**: Ketika kontainer berjalan dengan hak akses *root* tanpa pembatasan *capabilities* atau penyaringan *syscall*, penyerang yang mengeksploitasi kerentanan pada level aplikasi (misalnya RCE melalui dependensi pihak ketiga) dapat mengeksekusi *system call* berbahaya untuk keluar dari batas *namespace* kontainer dan mengontrol *host* secara langsung.
2. **Supply Chain Poisoning**: Citra kontainer standar (*full OS images* seperti `ubuntu:latest` atau `centos:7`) membawa ratusan paket biner yang tidak digunakan oleh aplikasi (seperti `curl`, `wget`, `tar`, `apt`, `python`). Setiap paket memiliki siklus kerentanan (*Common Vulnerabilities and Exposures* / CVE). Keberadaan utilitas ini menyediakan *living-off-the-land binaries* (LOLBins) bagi penyerang untuk mengunduh muatan sekunder (*dropper*) dan melakukan eksfiltrasi data.
3. **Dampak Finansial dan Regulasi**: Pelanggaran isolasi lingkungan kontainer yang menyebabkan pencurian data dapat mengakibatkan sanksi regulasi berat (misalnya denda GDPR hingga €20 juta atau 4% dari omzet global, kegagalan audit PCI-DSS 4.0 Bab 6 & 8, serta penangguhan sertifikasi SOC 2 Type II).
4. **Denial of Service (DoS) pada Level Host**: Tanpa pembatasan *system call* dan kuota kernel, kontainer yang terkompromi dapat menghabiskan tabel PID kernel (*PID exhaustion* via fork-bomb) atau memanipulasi *network socket raw*, yang melumpuhkan seluruh beban kerja lain yang berjalan pada *node* yang sama.

---

## 5. Apa Itu Konsep (What & Definisi Formal Mendalam)

### Multi-stage Docker Builds
Mekanisme pembuatan citra OCI di mana proses build dibagi menjadi beberapa tahap independen (*stages*). Artefak kompilasi (misalnya biner terkompilasi, *node_modules* yang telah diminifikasi) disalin dari tahap kompilasi (*builder stage*) ke tahap akhir (*runtime stage*). Semua perangkat lunak SDK, pustaka pengembangan (*header files*), dan *tools* kompilasi ditinggalkan di tahap sebelumnya dan tidak dimasukkan ke dalam lapisan (*layer*) citra final.

### Distroless Images
Citra kontainer yang secara ketat hanya berisi aplikasi target beserta dependensi *runtime*-nya secara langsung. Citra ini **tidak menyertakan** *package manager* (`apt`, `apk`), *shell* (`/bin/sh`, `/bin/bash`), maupun utilitas core Linux standar (`ls`, `cat`, `ps`). Diciptakan oleh GoogleContainerTools, Distroless meminimalkan basis TCB (*Trusted Computing Base*) kontainer ke tingkat serendah mungkin.

### Non-Root UID Enforcement
Konfigurasi eksplisit pada metadata citra (`USER <UID>:<GID>`) dan konfigurasi *runtime* kontainer yang memaksa proses utama dijalankan menggunakan *User Identifier* (UID) non-zero (bukan UID 0/root). Di dalam Linux, jika pengguna di dalam kontainer adalah UID 0 dan isolasi *user namespace* tidak aktif pada level daemon host, maka pengguna tersebut memetakan langsung ke UID 0 pada kernel host.

### Container Image Registry Scanning & Vulnerability Remediation
Praktik otomatisasi statis (SAST/SCA khusus kontainer) yang memeriksa seluruh lapisan sistem berkas citra kontainer terhadap basis data kerentanan yang diketahui (CVE/NVD/Vendor Security Advisories). Remediasi berfokus pada pembaruan lapisan basis (*base image updates*), *patching* dependensi, dan penolakan otomatis citra kontainer yang memiliki tingkat keparahan *High* atau *Critical* melalui *admission control*.

### Linux Kernel Sandboxing
Tiga pilar kontrol akses kernel yang membatasi hak istimewa kontainer:
1. **Linux Capabilities**: Memecah hak istimewa monolitik *super-user* (UID 0) menjadi 40+ unit izin individual independen (misalnya: `CAP_NET_ADMIN`, `CAP_SYS_ADMIN`, `CAP_CHOWN`).
2. **Seccomp (Secure Computing Mode)**: Subsistem kernel yang memfilter *system calls* yang dapat dipanggil oleh proses kontainer menggunakan *Berkeley Packet Filter* (BPF) yang diprogram langsung ke dalam kernel.
3. **AppArmor**: Modul Keamanan Linux (*Linux Security Module* / LSM) berbasis label dan jalur berkas (*path-based MAC*) yang membatasi berkas mana yang dapat dibaca, ditulis, atau dieksekusi oleh kontainer, serta operasi jaringan mana yang diizinkan.

---

## 6. Bagaimana Cara Kerjanya (How & Mekanika Internal Arsitektur)

### Mekanika Eksekusi Syscall dan Seccomp BPF

```
[ Application Process in Container ]
                 |
                 | 1. Memanggil syscall (misal: ptrace, reboot, clone)
                 v
        [ C Library / glibc ]
                 |
                 | 2. CPU Trap / Interrupt (Syscall instruction)
                 v
   +-------------------------------+
   |      LINUX KERNEL ENTRY       |
   +-------------------------------+
                 |
                 v
   +-------------------------------+
   |   SECCOMP-BPF System Filter   | <--- Aturan dimuat saat inisialisasi kontainer
   +-------------------------------+
                 |
        +--------+--------+
        | Memeriksa Syscall Number & Argumen
        v
    [ Evaluasi Aturan ]
     |-- Match Deny? ----> Kembalikan Return Action (misal: EPERM / SIGSYS kill)
     |-- Match Allow? ---> Teruskan ke Eksekusi Kernel Subsystem
                                    |
                                    v
                           [ AppArmor LSM Hook ]
                                    |
                            [ Otorisasi Path / Socket ]
                                    |
                                    v
                           [ Eksekusi Perintah Kernel ]
```

1. **Inisialisasi Sandbox**: Saat *container runtime* (`runc`) menginisialisasi proses kontainer, ia memanggil syscall `prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, ...)` dan mengirimkan program biner filter BPF terkompilasi.
2. **Evaluasi Syscall**: Setiap kali proses kontainer meminta kernel melakukan operasi (membaca berkas, membuka soket, mengubah *routing table*), filter BPF mengevaluasi arsitektur sistem (`arch`), nomor syscall (`syscall_nr`), dan argumennya (`args`).
3. **Tindakan Seccomp**:
   * `SCMP_ACT_ALLOW`: Syscall diizinkan untuk dilanjutkan.
   * `SCMP_ACT_ERRNO`: Syscall dibatalkan seketika, dan nilai kesalahan POSIX tertentu (seperti `EPERM` - *Operation not permitted*) dikembalikan langsung ke aplikasi tanpa mengeksekusi kode kernel.
   * `SCMP_ACT_KILL_PROCESS`: Kernel langsung mematikan proses kontainer yang melakukan pelanggaran.

### Mekanisme Linux Capabilities

Kernel Linux memvalidasi izin operasi melalui struktur data internal `struct cred` yang melekat pada setiap *task* (proses):

$$\text{Effective} \subseteq \text{Permitted} \subseteq \text{Bounding}$$

* **Bounding Set ($X_B$)**: Batas absolut kemampuan yang dapat diperoleh oleh sebuah proses sepanjang siklus hidupnya.
* **Inheritable Set ($X_I$)**: Izin yang dilewatkan ke proses anak melalui pemanggilan `execve()`.
* **Permitted Set ($X_P$)**: Izin absolut yang dimiliki oleh proses untuk digunakan.
* **Effective Set ($X_E$)**: Izin yang sedang aktif digunakan oleh kernel untuk memvalidasi operasi spesifik saat ini.

Secara *default*, *root* di dalam kontainer Docker standar memiliki 14 kapabilitas aktif (termasuk `CAP_CHOWN`, `CAP_DAC_OVERRIDE`, `CAP_NET_RAW`). Dengan menerapkan `--cap-drop=ALL`, kernel mengosongkan seluruh bitmask kapabilitas proses tersebut, sehingga proses tidak dapat melakukan tindakan seperti memodifikasi pemilik berkas, melakukan *spoofing* paket ARP, atau mengubah konfigurasi jaringan, meskipun aplikasi tersebut dieksekusi dengan UID 0.

### Mekanisme Path-Based LSM (AppArmor)

AppArmor memeriksa operasi berkas pada tingkat *VFS (Virtual Filesystem Switch)*:
* Mengikat *security context* secara langsung ke nama *path* direktori, bukan ke *inode* berkas.
* Ketika proses mencoba melakukan operasi `open()`, kernel memeriksa apakah profil AppArmor yang terasosiasi berada dalam status `enforcing`.
* Jika target operasi melanggar deklarasi profil (misalnya mencoba membaca direktori `/proc/sysrq-trigger` yang diberi label `deny`), kernel memblokir operasi dan mencatat peristiwa audit ke *auditd* sistem (`/var/log/audit/audit.log`).

---

## 7. Perbandingan Paradigma / Taksonomi Matriks

| Karakteristik | Full OS Image (e.g., Ubuntu/Debian) | Minimal OS Image (e.g., Alpine Linux) | Distroless Image (Google Distroless) | Scratch Image (`FROM scratch`) |
| :--- | :--- | :--- | :--- | :--- |
| **Ukuran Citra Rata-rata** | 70 MB - 200 MB+ | 5 MB - 15 MB | 15 MB - 50 MB (termasuk runtime) | Ukuran biner statis murni (< 10 MB) |
| **Package Manager** | `apt`, `dpkg` | `apk` | **Tidak Ada** | **Tidak Ada** |
| **Shell Bawaan** | `/bin/bash`, `/bin/sh` | `/bin/ash`, `/bin/sh` | **Tidak Ada** (kecuali `:debug`) | **Tidak Ada** |
| **C Library** | GNU C Library (`glibc`) | `musl libc` | `glibc` atau `musl` (varian khusus) | Tidak ada (statically linked) |
| **Vektor Serangan Bawaan** | Sangat Luas (Banyak biner utilitas & CVE bawaan) | Rendah (Permukaan kecil, namun ada shell) | **Sangat Sempit** (Hanya runtime + aplikasi) | **Absolut Minimal** (Zero OS footprint) |
| **Kompatibilitas Aplikasi** | Sangat Tinggi (Out-of-the-box) | Sedang (Masalah kompatibilitas Musl/Glibc) | Tinggi (Menggunakan standard glibc) | Terbatas (Hanya biner fully static) |
| **Kebutuhan Debugging** | Langsung via `docker exec -it ... /bin/bash` | Langsung via `docker exec -it ... /bin/sh` | Memerlukan Ephemeral Debug Container | Memerlukan Ephemeral Debug Container |
| **Rata-rata Temuan CVE** | Tinggi (Puluhan s/d Ratusan di image lama) | Rendah (Umumnya single digit) | **Nol s/d Sangat Rendah** | **Nol Mutlak** (Kecuali dari app binary) |

---

## 8. Analisis Mendalam Attack Surface & Vector Matrix

| Vektor Serangan | Kerentanan Mendasar | Skenario Eksploitasi | Dampak Sistem | Mitigasi Spesifik |
| :--- | :--- | :--- | :--- | :--- |
| **Container Escape via Syscall Abuse** | Kernel host rentan (e.g., Dirty COW, Dirty Pipe) & Seccomp dimatikan | Penyerang menjalankan syscall yang tidak diizinkan atau menyalahgunakan argumen kernel untuk mengubah memori kernel host. | Pengambilalihan kendali penuh host OS (*Root Access*). | Custom Seccomp profile (Blokir `ptrace`, `unshare`, `clone` flags berbahaya) + Update Kernel Host. |
| **Host File Overwrite via Privileged Mount** | Kontainer berjalan sebagai UID 0 dan memiliki akses write ke *shared volume* host | Penyerang memanipulasi symlink pada mount volume untuk menimpa `/etc/shadow` atau `/etc/crontab` di host. | Arbitrary code execution pada host OS. | Enforce Non-Root UID, aktifkan `userns-remap`, gunakan `--read-only` root filesystem. |
| **Lateral Movement via Network Raw Sockets** | Kontainer memiliki kapabilitas `CAP_NET_RAW` secara default | Aplikasi yang terkompromi memicu serangan ARP Spoofing / DNS Spoofing di dalam bridge network kontainer. | *Man-in-the-Middle* (MitM) terhadap lalu lintas data kontainer lain. | Hapus kapabilitas dengan `--cap-drop=NET_RAW` atau `--cap-drop=ALL`. |
| **Arbitrary Binary Execution via Package Manager** | Citra berbasis OS lengkap menyertakan `curl`, `bash`, dan `apt` | Penyerang menggunakan injeksi perintah (Command Injection) untuk mengunduh biner eksploitasi eksternal dan menjalankannya. | Pemasangan *backdoor* persisten dan *crypto-miner*. | Migrasi ke Distroless Images (tanpa shell dan utilitas pengunduh). |
| **Core Dump & Process Memory Inspection** | Kontainer memiliki kapabilitas `CAP_SYS_PTRACE` | Proses mengeksploitasi syscall `process_vm_readv` atau `ptrace` untuk mencuri *secret* dan *token* dari proses lain. | Kebocoran rahasia / kredensial infrastruktur. | Drop `CAP_SYS_PTRACE`, batasi Seccomp, terapkan AppArmor deny ptrace. |

---

## 9. Code Example Sederhana (Minimal & Clear)

Contoh *Multi-stage Dockerfile* sederhana untuk aplikasi Go, mendemonstrasikan pemisahan tahap build dan penggunaan *Distroless* non-root dasar.

```dockerfile
# ---------------------------------------------------------
# Stage 1: Build Environment
# ---------------------------------------------------------
FROM golang:1.22-alpine AS builder

WORKDIR /src

# Salin definisi modul dan download dependensi
COPY go.mod go.sum ./
RUN go mod download

# Salin kode sumber
COPY . .

# Kompilasi aplikasi menjadi biner statis
# CGO_ENABLED=0 menonaktifkan binding pustaka C dinamis
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build \
    -ldflags="-w -s" \
    -o /bin/minimal-app .

# ---------------------------------------------------------
# Stage 2: Runtime Environment (Distroless Non-Root)
# ---------------------------------------------------------
FROM gcr.io/distroless/static-debian12:nonroot

WORKDIR /app

# Salin biner dari builder stage ke runtime stage
COPY --from=builder /bin/minimal-app /app/minimal-app

# Port yang diekspos
EXPOSE 8080

# Jalankan sebagai nonroot (UID 65532 sudah terdaftar di distroless:nonroot)
USER nonroot:nonroot

ENTRYPOINT ["/app/minimal-app"]
```

---

## 10. Code Example Lanjutan (Production-ready / Hardening / Exploit Analysis)

Berikut adalah rangkaian konfigurasi *defense-in-depth* tingkat lanjut untuk lingkungan produksi:

### 10.1 Production Multi-Stage Hardened Dockerfile (`Dockerfile.production`)

```dockerfile
# ==============================================================================
# STAGE 1: Dependency Analyzer & Builder
# ==============================================================================
FROM golang:1.22.2-bookworm AS builder

# Buat non-privileged build user
RUN groupadd -g 10001 appbuild && \
    useradd -u 10001 -g appbuild -m -s /bin/bash appbuild

WORKDIR /workspace
RUN chown -R appbuild:appbuild /workspace

USER appbuild:appbuild

# Copy manifests
COPY --chown=appbuild:appbuild go.mod go.sum ./
RUN go mod download && go mod verify

# Copy source code
COPY --chown=appbuild:appbuild . .

# Parameter kompilasi hardening:
# -trimpath: Hapus path file lokal pengembang dari biner
# -buildmode=pie: Aktifkan Position Independent Executable (ASLR support)
# -ldflags: -w (strip DWARF debug info), -s (strip symbol table)
ENV CGO_ENABLED=0 \
    GOOS=linux \
    GOARCH=amd64

RUN go build \
    -trimpath \
    -buildmode=pie \
    -ldflags="-w -s -extldflags '-static'" \
    -o /workspace/bin/secure-service ./cmd/api

# ==============================================================================
# STAGE 2: Base System Setup (Membuat Non-Root User & Group Minimal)
# ==============================================================================
FROM alpine:3.19.1 AS system-prep

# Setup UID & GID spesifik (UID 10002)
RUN addgroup -g 10002 appgroup && \
    adduser -D -u 10002 -G appgroup -s /sbin/nologin appuser && \
    mkdir -p /empty-dir && \
    mkdir -p /tmp-app && \
    chown -R 10002:10002 /tmp-app

# ==============================================================================
# STAGE 3: Final Production Distroless Runtime
# ==============================================================================
FROM gcr.io/distroless/static-debian12:latest

# Salin user/group databases dari stage persiapan
COPY --from=system-prep /etc/passwd /etc/passwd
COPY --from=system-prep /etc/group /etc/group

# Salin direktori writeable sementara yang aman jika aplikasi memerlukan temporary swap
COPY --from=system-prep --chown=10002:10002 /tmp-app /tmp

# Salin biner yang sudah di-harden
COPY --from=builder --chown=10002:10002 /workspace/bin/secure-service /usr/local/bin/secure-service

# Gunakan UID/GID eksplisit yang terdefinisi
USER 10002:10002

# Konfigurasi filesystem: aplikasi harus siap berjalan dengan root-fs read-only
WORKDIR /usr/local/bin

EXPOSE 8443

# Aktifkan signal termination handling
STOPSIGNAL SIGTERM

ENTRYPOINT ["/usr/local/bin/secure-service"]
```

### 10.2 Custom Seccomp Profile (`custom-seccomp.json`)

Profil Seccomp ketat dengan paradigma *default-deny* (mengembalikan `SCMP_ACT_ERRNO` / `EPERM` jika tidak masuk *whitelist*):

```json
{
  "defaultAction": "SCMP_ACT_ERRNO",
  "defaultErrnoRet": 1,
  "archMap": [
    {
      "architecture": "SCMP_ARCH_X86_64",
      "subArchitectures": [
        "SCMP_ARCH_X86",
        "SCMP_ARCH_X32"
      ]
    },
    {
      "architecture": "SCMP_ARCH_AARCH64"
    }
  ],
  "syscalls": [
    {
      "names": [
        "accept4",
        "access",
        "bind",
        "brk",
        "clock_gettime",
        "clone",
        "clone3",
        "close",
        "epoll_create1",
        "epoll_ctl",
        "epoll_pwait",
        "exit",
        "exit_group",
        "fcntl",
        "fstat",
        "fstatfs",
        "futex",
        "getcwd",
        "getdents64",
        "getpid",
        "getrandom",
        "listen",
        "madvise",
        "mmap",
        "mprotect",
        "munmap",
        "nanosleep",
        "newfstatat",
        "openat",
        "pipe2",
        "pselect6",
        "read",
        "readlinkat",
        "restart_syscall",
        "rseq",
        "rt_sigaction",
        "rt_sigprocmask",
        "rt_sigreturn",
        "sched_getaffinity",
        "sched_yield",
        "setsockopt",
        "socket",
        "stat",
        "tgkill",
        "write"
      ],
      "action": "SCMP_ACT_ALLOW",
      "args": []
    },
    {
      "names": [
        "ptrace",
        "process_vm_readv",
        "process_vm_writev",
        "sys_chroot",
        "reboot",
        "kexec_load",
        "init_module",
        "finit_module",
        "delete_module",
        "iopl",
        "ioperm",
        "swapon",
        "swapoff"
      ],
      "action": "SCMP_ACT_KILL_PROCESS"
    }
  ]
}
```

### 10.3 Custom AppArmor Profile (`apparmor-hardened-profile`)

Simpan di `/etc/apparmor.d/docker-secure-service`:

```ini
#include <tunables/global>

profile docker-secure-service flags=(attach_disconnected,mediate_deleted) {
  #include <abstractions/base>

  # Explicit deny to sensitive kernel and host virtual filesystems
  deny /sys/** mrwklx,
  deny /proc/sys/** mrwklx,
  deny /proc/sysrq-trigger rwklx,
  deny /proc/kcore rwklx,
  deny /proc/mem rwklx,

  # Deny accessing raw disks and devices
  deny /dev/sd* mrwklx,
  deny /dev/nvme* mrwklx,
  deny /dev/mem rwklx,
  deny /dev/kmem rwklx,

  # Restrict raw networking and mount operations
  deny mount,
  deny remount,
  deny umount,
  deny ptrace,
  deny capability sys_admin,
  deny capability sys_ptrace,
  deny capability sys_rawio,

  # Allow network operations for web API
  network inet tcp,
  network inet6 tcp,

  # Allow binary execution
  /usr/local/bin/secure-service mr,

  # Allow temporary writable operations strictly in /tmp
  /tmp/** rwkl,

  # Read-only configuration access
  /etc/passwd r,
  /etc/group r,
  /etc/ssl/certs/** r,
  /usr/share/ca-certificates/** r,
}
```

### 10.4 Vulnerability Scanning Automation Script (`ci-scan-pipeline.sh`)

```bash
#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG="internal-registry.corp/apps/secure-service:${CI_COMMIT_SHA:-latest}"
SBOM_OUTPUT="sbom.cdx.json"
SCAN_REPORT="trivy-results.json"

echo "[+] Step 1: Building container image via Docker BuildKit..."
DOCKER_BUILDKIT=1 docker build \
    --no-cache \
    --file Dockerfile.production \
    --tag "${IMAGE_TAG}" .

echo "[+] Step 2: Generating Software Bill of Materials (SBOM) using Syft..."
syft packages "${IMAGE_TAG}" -o cyclonedx-json > "${SBOM_OUTPUT}"

echo "[+] Step 3: Scanning Image for CVEs with Trivy..."
# Fail (exit status 1) jika ditemukan kerentanan CRITICAL atau HIGH
# Abaikan kerentanan yang belum memiliki patch resmi (--ignore-unfixed)
trivy image \
    --exit-code 1 \
    --severity HIGH,CRITICAL \
    --ignore-unfixed \
    --format json \
    --output "${SCAN_REPORT}" \
    "${IMAGE_TAG}" || SCAN_EXIT_CODE=$?

if [ "${SCAN_EXIT_CODE:-0}" -ne 0 ]; then
    echo "[!] SECURITY GATE FAILED: Kerentanan HIGH/CRITICAL terdeteksi pada citra."
    echo "[!] Laporan detail tersimpan di: ${SCAN_REPORT}"
    exit 1
fi

echo "[+] Security gate lolos. Mengirim citra ke Registry..."
docker push "${IMAGE_TAG}"
```

---

## 11. Diagram Alur Serangan & Mitigasi (ASCII Art)

```
====================================================================================================
                        SCENARIO: ATTEMPTED CONTAINER BREAKOUT / ESCAPE
====================================================================================================

Penyerang mendapatkan akses Remote Code Execution (RCE) pada Service di dalam Container.
                                     |
                                     v
+--------------------------------------------------------------------------------------------------+
| LAYER 1: MULTI-STAGE & DISTROLESS DEFENSE                                                        |
+--------------------------------------------------------------------------------------------------+
| Penyerang mencoba menjalankan: `sh`, `bash`, `curl`, `apt`, `wget`                              |
| -> KONDISI: Citra adalah Distroless (tidak ada shell dan binary eksternal).                      |
| [HASIL MITIGASI]: Eksekusi gagal (File Not Found / Exec Format Error).                            |
| Penyerang terpaksa menyuntikkan shellcode langsung via TCP socket.                                |
+--------------------------------------------------------------------------------------------------+
                                     |
                                     v (Shellcode lolos ke memory proses)
+--------------------------------------------------------------------------------------------------+
| LAYER 2: NON-ROOT & READ-ONLY FILESYSTEM                                                         |
+--------------------------------------------------------------------------------------------------+
| Penyerang mencoba:                                                                               |
| 1. Memodifikasi file sistem (`/etc/shadow`, `/usr/bin/secure-service`)                           |
| 2. Membuat file backdoor baru di `/var/spool/cron`                                               |
| -> KONDISI: Root-filesystem bersifat READ-ONLY (`--read-only`) dan berjalan sebagai UID 10002.   |
| [HASIL MITIGASI]: Operasi I/O dibatalkan kernel (EROFS: Read-only file system / EACCES).        |
+--------------------------------------------------------------------------------------------------+
                                     |
                                     v (Penyerang mencoba eskalasi ke Kernel Host)
+--------------------------------------------------------------------------------------------------+
| LAYER 3: LINUX CAPABILITIES DROP                                                                 |
+--------------------------------------------------------------------------------------------------+
| Penyerang mencoba: Menjalankan `setuid(0)` atau memanipulasi Raw Network (`CAP_NET_RAW`).        |
| -> KONDISI: Flag `--cap-drop=ALL` aktif. Bounding set kapabilitas proses adalah kosong (0x0).    |
| [HASIL MITIGASI]: Kernel mengembalikan status error (EPERM: Operation not permitted).            |
+--------------------------------------------------------------------------------------------------+
                                     |
                                     v (Penyerang mencoba mengeksploitasi Kernel Exploit via Syscall)
+--------------------------------------------------------------------------------------------------+
| LAYER 4: SECCOMP-BPF FILTERING                                                                   |
+--------------------------------------------------------------------------------------------------+
| Penyerang memanggil syscall: `ptrace()` untuk menginjeksi kode ke proses host, atau              |
| `unshare(CLONE_NEWUSER)` untuk memecah isolasi namespace.                                        |
| -> KONDISI: Custom Seccomp Profile menginstruksikan `SCMP_ACT_KILL_PROCESS` untuk `ptrace`.      |
| [HASIL MITIGASI]: Kernel BPF Engine langsung mematikan (SIGSYS/SIGKILL) proses penyerang.        |
| Kontainer mati seketika, serangan gagal total. Event dicatat di audit log.                       |
+--------------------------------------------------------------------------------------------------+
```

---

## 12. Trade-offs & Security vs Usability / Performance

### 1. Distroless vs Developer Troubleshooting
* **Keamanan**: Mengeliminasi 99% utilitas LOLBins dan library tak terpakai; mengurangi frekuensi CVE hingga ~90%.
* **Kompromi**: Perintah `docker exec` atau `kubectl exec` tidak dapat digunakan karena ketiadaan `/bin/sh`.
* **Solusi Operasional**: Manfaatkan fitur modern orkestrator seperti *Kubernetes Ephemeral Debug Containers* (`kubectl debug -it <pod> --image=busybox --target=<container>`) untuk memasang instrumen diagnostik tanpa merusak keamanan citra inti.

### 2. Seccomp-BPF Filtering vs Overhead Kinerja
* **Keamanan**: Memblokir ratusan syscall tidak esensial; mencegah eksploitasi kerentanan zero-day pada antarmuka kernel yang rentan.
* **Kompromi**: Setiap eksekusi syscall harus melalui instruksi filter BPF kernel.
* **Solusi Operasional**: Tempatkan syscall frekuensi tinggi (seperti `read`, `write`, `epoll_pwait`, `futex`) di posisi teratas daftar izin (*whitelist ordering*) guna mempercepat pencocokan register BPF. Penurunan performa I/O umumnya di bawah 1.5% pada beban kerja tinggi.

### 3. Non-Root UID vs Hak Akses Port Rendah (<1024)
* **Keamanan**: Mencegah proses mengambil alih *root context* jika terjadi *container breakout*.
* **Kompromi**: Secara historis, biner non-root Linux tidak diizinkan membuka port *privileged* (port < 1024, seperti 80 dan 443).
* **Solusi Operasional**: Standar industri saat ini mengarahkan kontainer berjalan pada port *unprivileged* (misalnya: 8080, 8443) kemudian dimetakan via ingress/proxy, atau memberikan kapabilitas tunggal `CAP_NET_BIND_SERVICE` secara eksplisit tanpa memberikan hak root penuh.

---

## 13. Edge Cases & Complex Failure Modes

### Dynamic Linking Mismatch (glibc vs musl libc)
* **Gejala**: Aplikasi yang dikompilasi menggunakan Ubuntu/Debian (`glibc`) gagal dieksekusi saat disalin ke citra minimal seperti Alpine atau Distroless static murni, memunculkan galat misterius: `standard_init_linux.go: exec user process caused: no such file or directory`.
* **Akar Masalah**: Pemuat tautan dinamis (*dynamic linker/loader*) ELF (misalnya `/lib64/ld-linux-x86-64.so.2`) tidak ditemukan di sistem berkas basis target.
* **Remediasi**: Selalu gunakan kompilasi statis (`CGO_ENABLED=0`) atau targetkan citra Distroless yang menyertakan glibc (`gcr.io/distroless/base-debian12`).

### Volume Mounting Permission Denied pada Non-Root Containers
* **Gejala**: Ketika kontainer dijalankan dengan `USER 10002:10002` dan memasang volume persisten (`docker run -v /host/data:/app/data`), aplikasi mogok dengan pesan `EACCES: permission denied`.
* **Akar Masalah**: Direktori pada *host* dimiliki oleh `root:root` (UID 0), sehingga kontainer non-root tidak memiliki hak tulis ke direktori tersebut.
* **Remediasi**: Siapkan permission direktori host sebelum runtime menggunakan init container (`chown -R 10002:10002 /host/data`) atau konfigurasi `fsGroup` pada Kubernetes SecurityContext.

### Architecture-Specific Syscall Number Mismatch pada Seccomp
* **Gejala**: Profil Seccomp berjalan normal pada mesin pengembang (x86_64), namun memicu penghentian instan proses (*crash* / SIGSYS) saat dijalankan pada infrastruktur ARM64 (misalnya AWS Graviton).
* **Akar Masalah**: Penomoran nomor syscall pada kernel Linux berbeda secara radikal antara arsitektur x86_64 dan AArch64 (misalnya syscall `clone` vs `clone3`, `open` vs `openat`).
* **Remediasi**: Tentukan nama syscall secara simbolis (*string literal*) dalam berkas definisi Seccomp, bukan menggunakan nomor syscall mentah, dan pastikan blok `archMap` mencakup `SCMP_ARCH_X86_64` serta `SCMP_ARCH_AARCH64`.

---

## 14. Anti-Patterns & Common Vulnerabilities

### Anti-Pattern 1: Menggunakan Flag `--privileged`
* **Praktik Buruk**: Menjalankan kontainer dengan `docker run --privileged` untuk mengatasi masalah izin I/O atau jaringan.
* **Bahaya Teknis**: Memberikan kontainer seluruh kapabilitas Linux (menonaktifkan Seccomp dan AppArmor), memetakan seluruh perangkat `/dev` host ke dalam kontainer, dan memungkinkan penyerang memasang drive host secara langsung menggunakan perintah `mount /dev/sda1 /mnt`.

### Anti-Pattern 2: Melakukan Bind-Mounting Docker Socket Host
* **Praktik Buruk**: Memasang `/var/run/docker.sock` ke dalam kontainer aplikasi untuk mengontrol daemon Docker dari dalam kontainer.
* **Bahaya Teknis**: Siapa pun yang memiliki akses ke socket Docker memiliki kontrol setara dengan root pada host. Penyerang dapat membuat kontainer baru yang memetakan seluruh root filesystem host (`-v /:/host`).

### Anti-Pattern 3: Eksekusi Berkas dengan Bit SUID/SGID di Lapisan Runtime
* **Praktik Buruk**: Meninggalkan biner berstatus SUID (`chmod u+s`) di dalam citra kontainer (misal: `/usr/bin/sudo`, `/bin/su`, `/usr/bin/passwd`).
* **Bahaya Teknis**: Jika pengguna non-root berhasil diakses oleh eksploit, biner SUID ini dapat disalahgunakan untuk eskalasi lokal (*Local Privilege Escalation*) di dalam kontainer.

### Anti-Pattern 4: Penggunaan Tag `:latest` Tanpa Verifikasi Digest
* **Praktik Buruk**: Menggunakan deklarasi `FROM node:latest` atau `FROM alpine:latest`.
* **Bahaya Teknis**: Citra dapat berubah kapan saja tanpa proses validasi keamanan formal, merusak determinisme build dan berisiko memasukkan regresi keamanan dari upstream.

---

## 15. Best Practices & Enterprise Remediation Guide

1. **Prinsip Imutabilitas Filesystem**:
   Jalankan kontainer dengan *read-only root filesystem* menggunakan parameter runtime `--read-only`. Berikan akses tulis hanya pada direktori volatil yang strictly dibutuhkan menggunakan flag `--tmpfs /tmp:rw,noexec,nosuid,size=64m`.
2. **Standardisasi UID Enterprise**:
   Tetapkan rentang UID/GID non-root standar di seluruh enterprise (misalnya: UID 10001 s/d 20000). Jangan pernah mengizinkan build Dockerfile yang berakhir tanpa deklarasi instruksi `USER <UID>`.
3. **Penerapan Multi-Stage Golden Images**:
   Pusatkan pemeliharaan base image melalui *Enterprise Platform Security Team*. Perbarui *base image* mingguan untuk memastikan patch sistem operasi upstream selalu diserap.
4. **Enforcement Shift-Left pada Registry**:
   Terapkan *Admission Webhook* (misalnya Kyverno atau OPA Gatekeeper di Kubernetes) yang secara otomatis menolak Pod jika:
   * Kontainer berjalan sebagai `runAsRoot: true`.
   * SecurityContext tidak menyertakan `drop: ["ALL"]` pada blok capabilities.
   * Citra ditarik dari *registry* eksternal yang belum terverifikasi atau tanpa tanda tangan kriptografis Cosign/Notary.
5. **Generasi SBOM dan Attestation**:
   Simpan SBOM format CycloneDX/SPDX untuk setiap artefak build dan pasang tanda tangan digital (*Cosign signature*) untuk memverifikasi integritas *supply chain*.

---

## 16. Hands-on Lab Step-by-Step

Lab ini memandu implementasi hardening menyeluruh pada host Linux berbasis Ubuntu 22.04/Debian 12 dengan Docker CE dan Trivy terpasang.

### Langkah 1: Persiapan Workspace & Aplikasi Target

Buat direktori kerja baru dan inisialisasi aplikasi Go sederhana:

```bash
mkdir -p ~/container-hardening-lab/app
cd ~/container-hardening-lab/app

cat << 'EOF' > main.go
package main

import (
	"fmt"
	"net/http"
	"os"
)

func handler(w http.ResponseWriter, r *http.Request) {
	fmt.Fprintf(w, "Sandboxed Service Running. PID: %d, UID: %d\n", os.Getpid(), os.Getuid())
}

func main() {
	http.HandleFunc("/", handler)
	fmt.Println("Server starting on port 8080...")
	if err := http.ListenAndServe(":8080", nil); err != nil {
		panic(err)
	}
}
EOF

cat << 'EOF' > go.mod
module secure-lab

go 1.22
EOF
```

### Langkah 2: Konstruksi Dockerfile Multi-Stage Hardened

Buat berkas Dockerfile dengan non-root distroless:

```bash
cat << 'EOF' > Dockerfile
FROM golang:1.22-bookworm AS builder
WORKDIR /src
COPY go.mod ./
COPY main.go ./
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -ldflags="-w -s" -o /bin/service main.go

FROM gcr.io/distroless/static-debian12:nonroot
WORKDIR /app
COPY --from=builder /bin/service /app/service
USER nonroot:nonroot
EXPOSE 8080
ENTRYPOINT ["/app/service"]
EOF
```

Bangun citra kontainer:

```bash
docker build -t local-hardened:v1 .
```

### Langkah 3: Vulnerability Scanning & SBOM Generation

Install Trivy jika belum tersedia, lalu pindai citra:

```bash
# Instalasi Trivy (Debian/Ubuntu)
if ! command -v trivy &> /dev/null; then
    sudo apt-get install wget apt-transport-https gnupg lsb-release -y
    wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | gpg --dearmor | sudo tee /usr/share/keyrings/trivy.gpg > /dev/null
    echo "deb [signed-by=/usr/share/keyrings/trivy.gpg] https://aquasecurity.github.io/trivy-repo/deb $(lsb_release -sc) main" | sudo tee -a /etc/apt/sources.list.d/trivy.list
    sudo apt-get update && sudo apt-get install trivy -y
fi

# Eksekusi scanning terhadap citra hardened
trivy image --severity HIGH,CRITICAL local-hardened:v1
```

*Verifikasi output*: Citra distroless harus menghasilkan `0 vulnerabilities` untuk tingkat keparahan High/Critical.

### Langkah 4: Penerapan Seccomp Custom Profile

Buat profil Seccomp yang memblokir instruksi sistem tidak esensial:

```bash
cat << 'EOF' > /tmp/deny-ptrace-seccomp.json
{
  "defaultAction": "SCMP_ACT_ALLOW",
  "syscalls": [
    {
      "names": [
        "ptrace",
        "process_vm_readv",
        "process_vm_writev"
      ],
      "action": "SCMP_ACT_ERRNO",
      "args": []
    }
  ]
}
EOF
```

### Langkah 5: Penerapan AppArmor Profile

Buat dan muat profil AppArmor ke dalam Linux Kernel:

```bash
sudo tee /etc/apparmor.d/containers-strict-profile << 'EOF'
#include <tunables/global>

profile containers-strict-profile flags=(attach_disconnected,mediate_deleted) {
  #include <abstractions/base>

  deny /proc/sysrq-trigger rwklx,
  deny /proc/kcore rwklx,
  deny /sys/** mrwklx,
  
  network inet tcp,
  
  /app/service mr,
  /tmp/** rwkl,
}
EOF

# Muat profil ke kernel
sudo apparmor_parser -r -W /etc/apparmor.d/containers-strict-profile

# Verifikasi profil telah aktif
sudo aa-status | grep containers-strict-profile
```

### Langkah 6: Eksekusi Kontainer dengan Hardening Menyeluruh

Jalankan kontainer dengan mengombinasikan seluruh instrumen keamanan:
* Non-Root UID (`--user 65532:65532`)
* Drop Capabilities (`--cap-drop=ALL`)
* Read-Only Root Filesystem (`--read-only`)
* Custom Seccomp (`--security-opt seccomp=/tmp/deny-ptrace-seccomp.json`)
* Custom AppArmor (`--security-opt apparmor=containers-strict-profile`)
* Tmpfs untuk direktori writeable volatil (`--tmpfs /tmp:rw,noexec,nosuid,size=16m`)

```bash
docker run -d \
  --name hardened-api-instance \
  -p 8080:8080 \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  --cap-drop=ALL \
  --security-opt seccomp=/tmp/deny-ptrace-seccomp.json \
  --security-opt apparmor=containers-strict-profile \
  local-hardened:v1
```

### Langkah 7: Pengujian & Validasi Keamanan Sandbox

1. **Uji Respons Layanan**:
```bash
curl -i http://localhost:8080/
```
Output validasi: `Sandboxed Service Running. PID: 1, UID: 65532` (Memvalidasi proses bukan root).

2. **Uji Ketiadaan Shell (Distroless Validation)**:
```bash
docker exec -it hardened-api-instance /bin/sh
```
Output yang diharapkan: `OCI runtime exec failed: exec failed: unable to start container process: exec: "/bin/sh": stat /bin/sh: no such file or directory`.

3. **Uji Status Isolasi Kernel (Inspect Process Status)**:
```bash
CONTAINER_PID=$(docker inspect --format '{{.State.Pid}}' hardened-api-instance)
grep "Cap" /proc/$CONTAINER_PID/status
```
Output yang diharapkan (seluruh bitmask capability bernilai nol):
```
CapInh: 0000000000000000
CapPrm: 0000000000000000
CapEff: 0000000000000000
CapBnd: 0000000000000000
CapAmb: 0000000000000000
```

4. **Pembersihan Lingkungan Lab**:
```bash
docker stop hardened-api-instance && docker rm hardened-api-instance
```

---

## 17. Real-world Case Study & Incident Analysis Enterprise

### Kasus: Insiden Cryptomining & Host Penetration pada Lembaga Keuangan Multinasional (2022)

* **Vektor Awal (Initial Access)**:
  Penyerang mengeksploitasi celah Remote Code Execution (RCE) pada pustaka pemrosesan gambar dalam aplikasi web *customer onboarding*. Aplikasi dikemas menggunakan citra Docker berbasis `ubuntu:20.04` standar.
* **Kelemahan Arsitektur**:
  1. Kontainer berjalan menggunakan akun bawaan: `USER root` (UID 0).
  2. Kontainer dijalankan tanpa membuang kapabilitas Linux (memiliki `CAP_NET_RAW`, `CAP_SYS_ADMIN`, `CAP_SYS_PTRACE`).
  3. Menggunakan profil Seccomp `unconfined` karena keluhan pengembang terkait pemblokiran syscall saat testing.
  4. Root filesystem bersifat *writable*.
* **Eskalasi Serangan**:
  Setelah RCE berhasil, penyerang memanfaatkan utilitas LOLBins (`curl` dan `apt`) yang tersedia pada citra Ubuntu untuk mengunduh biner eksploitasi kernel *host* (Dirty Pipe - CVE-2022-0847). Karena proses berjalan sebagai UID 0 dan memiliki akses syscall luas tanpa filter Seccomp, eksploit Dirty Pipe sukses menimpa cache halaman kernel Linux pada host OS. Penyerang menyuntikkan SSH Public Key mereka langsung ke file host `/etc/passwd`, keluar sepenuhnya dari isolasi kontainer (*container escape*), dan memperoleh sesi shell interaktif tingkat root pada *hypervisor node*.
* **Remediasi Pascainsiden**:
  1. Seluruh pipeline CI/CD diwajibkan menggunakan citra *Distroless* berbasis *Multi-stage Build*, memusnahkan utilitas pengunduh dan shell dari kontainer runtime.
  2. Penerapan OPA Gatekeeper untuk memblokir seluruh Pod yang tidak memiliki `runAsNonRoot: true`.
  3. Penegakan profil Seccomp *runtime-default* dan *custom profile* ketat pada seluruh kluster Kubernetes produksi.
  4. Pengaktifan *Read-Only Root Filesystem* secara global di seluruh layanan backend.

---

## 18. Quiz Pemahaman & Challenge

### Pertanyaan Evaluasi

1. Jelaskan mengapa menjalankan aplikasi kontainer sebagai `USER root` (UID 0) di dalam kontainer tanpa *user namespace remapping* berbahaya bagi keamanan host OS, meskipun kontainer memiliki *namespace* tersendiri!
2. Mengapa biner statis Go yang dikompilasi pada sistem operasi Debian standar dapat memunculkan galat `file not found` ketika dipindahkan ke citra minimalis `alpine` atau `scratch`, dan bagaimana parameter build yang tepat untuk menanggulanginya?
3. Sebutkan perbedaan fundamental antara fungsi pengamanan yang dijalankan oleh **Seccomp** dan **AppArmor** pada arsitektur Linux Kernel Sandbox!
4. Jika kontainer dideklarasikan dengan flag `--cap-drop=ALL`, tindakan spesifik apa yang diblokir oleh kernel terhadap proses kontainer meskipun proses tersebut diinisialisasi oleh UID 0?
5. Sebuah tim DevOps mengeluhkan bahwa setelah mengaktifkan `--read-only` root filesystem, aplikasi Java Spring Boot mereka tidak dapat berjalan karena memerlukan penyimpanan sementara (*temporary storage*) untuk *embedded Tomcat*. Bagaimana solusi arsitektural yang aman tanpa mematikan fitur `--read-only`?

### Kunci Jawaban & Analisis

1. **Jawaban**: Di dalam arsitektur kernel Linux tanpa *User Namespaces* (`userns`), UID 0 di dalam kontainer memetakan langsung ke struktur kredensial UID 0 pada kernel host. Jika penyerang menemukan kerentanan pada OCI runtime (misalnya `runc` CVE-2019-5736) atau kerentanan kernel host, kernel mengidentifikasi proses penyerang sebagai pemilik hak administratif tertinggi, sehingga kontainer breakout langsung memberikan kontrol mutlak atas mesin host.
2. **Jawaban**: Biner tersebut dikompilasi secara dinamis (*dynamic linking*) dan mengikat dependensi ke *glibc* (`/lib64/ld-linux-x86-64.so.2`). Alpine Linux menggunakan *musl libc*, sedangkan Scratch tidak memiliki sistem berkas pustaka apa pun. Solusinya adalah mengompilasi biner secara statis menggunakan perintah: `CGO_ENABLED=0 go build -ldflags="-w -s -extldflags '-static'"` yang menanamkan seluruh dependensi langsung ke dalam biner ELF.
3. **Jawaban**: **Seccomp** beroperasi pada lapisan penyaringan antarmuka *system call* (instruksi level proses) menggunakan program BPF untuk mengizinkan atau menolak syscall spesifik (misal: memblokir pemanggilan fungsi kernel `ptrace`). Sedangkan **AppArmor** adalah *Linux Security Module (LSM)* yang beroperasi pada lapisan deklarasi akses *objek* berbasis path sistem berkas, kapabilitas, dan soket jaringan (misal: mengizinkan syscall `open()`, namun membatasi agar path target hanya boleh berada di bawah direktori `/app`).
4. **Jawaban**: Proses akan kehilangan seluruh hak operasi administratif khusus kernel. Ini mencakup: ketidakmampuan mengubah kepemilikan file (`CAP_CHOWN`), ketidakmampuan mengabaikan izin baca/tulis berkas Linux DAC (`CAP_DAC_OVERRIDE`), larangan membuat raw network packets / ARP spoofing (`CAP_NET_RAW`), larangan memuat modul kernel (`CAP_SYS_MODULE`), dan larangan melacak memori proses lain (`CAP_SYS_PTRACE`).
5. **Jawaban**: Pasang volume berbasis memori sementara (*tmpfs*) berukuran terbatas secara eksplisit pada direktori yang diwajibkan oleh runtime Java, misalnya dengan menambahkan flag runtime: `--tmpfs /tmp:rw,noexec,nosuid,size=128m`. Hal ini menjaga seluruh integritas sistem berkas kontainer tetap *read-only* (mencegah modifikasi biner aplikasi) sembari memberikan ruang tulis volatil bagi Tomcat yang tidak akan bertahan jika kontainer di-restart.

### Advanced Architectural Challenge

**Skenario**: Anda adalah DevSecOps Architect pada sistem Core Banking. Aplikasi perbankan berbasis Node.js wajib berjalan pada kontainer dengan kriteria:
* Harus menggunakan citra Distroless.
* Sistem berkas wajib *read-only*.
* Menggunakan Non-Root UID dinamis.
* Tidak boleh memiliki akses shell sama sekali.
* Namun, aplikasi **membutuhkan sertifikat CA lokal privat** yang diinjeksi saat deployment dan rotasi kunci berkala tanpa memicu pembuatan image baru.

**Tugas Anda**:
Rancang strategi konfigurasi `Dockerfile`, pola volume mount, dan Kubernetes `SecurityContext` YAML yang memenuhi seluruh batas kepatuhan keamanan di atas tanpa melanggar batasan imutabilitas kontainer.

---

## 19. Summary & Key Takeaways

* **Pertahanan Berlapis (*Defense-in-Depth*)**: Keamanan kontainer tidak boleh bertumpu pada satu isolasi saja. Kombinasi *Multi-stage Minimal Build*, *Non-Root Execution*, *Capabilities Dropping*, *Seccomp Filtering*, dan *AppArmor LSM* adalah prasyarat mutlak untuk beban kerja produksi modern.
* **Minimalkan Attack Surface dengan Distroless**: Singkirkan shell (`/bin/sh`), package manager (`apk`, `apt`), dan compiler dari runtime image. Jika biner LOLBins tidak ada di dalam kontainer, rantai serangan eksploitasi pasca-kompromi terputus secara efektif.
* **Eliminasi Hak Root**: Kontainer seharusnya tidak pernah berjalan sebagai UID 0. Terapkan penegakan UID non-root pada level Dockerfile dan perkuat melalui *Admission Controller* di level orkestrasi orkestrator.
* **Kendalikan Komunikasi Kernel**: Syscall adalah gerbang antara kontainer dan kernel host. Terapkan default-drop pada Linux Capabilities (`--cap-drop=ALL`) dan filter antarmuka syscall menggunakan profil Seccomp ketat untuk memitigasi risiko *container escape*.
* **Imutabilitas File System**: Konfigurasi kontainer dengan status `--read-only` root filesystem. Layanan yang tidak dapat menulis ke sistem berkasnya sendiri secara drastis membatasi persistensi malware dan modifikasi konfigurasi secara ilegal.

---

## 20. Referensi Resmi & Standar Keamanan

* **NIST SP 800-190**: *Application Container Security Guide* (Pedoman komprehensif NIST untuk mitigasi risiko pada arsitektur kontainer di tingkat image, registry, orchestrator, dan host OS).
* **CIS Docker Benchmark v1.6.0**: Standar konsensus industri mengenai parameter konfigurasi hardening Docker Engine, Host Configuration, dan Container Images.
* **CIS Kubernetes Benchmark v1.8.0**: Rekomendasi keamanan terkait *Pod Security Standards* (PSS) dan *Security Context* penegakan non-root.
* **OWASP Container Security Verification Standard (CSVS)**: Kerangka kerja verifikasi keamanan teknis untuk aplikasi berbasis kontainer.
* **MITRE ATT&CK for Containers Matrix**: Taksonomi taktik dan teknik penyerang yang menargetkan lingkungan kontainerisasi (khususnya teknik *Escape to Host* [T1611]).
* **Linux Kernel Documentation - Seccomp BPF**: Dokumentasi resmi antarmuka kernel Linux untuk Secure Computing Mode (`https://www.kernel.org/doc/Documentation/prctl/seccomp_filter.txt`).
* **AppArmor Core Documentation**: Panduan teknis manajemen kontrol akses wajib berbasis path (`https://gitlab.com/apparmor/apparmor/-/wikis/Documentation`).