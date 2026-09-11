# Module 01: Arsitektur Container, Namespaces, Cgroups, & Docker Runtime

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar akan mampu:
1. Memahami perbedaan arsitektural mendasar antara Virtual Machine (Hypervisor-based) dan Linux Containers (OS-level virtualization).
2. Menguasai 6 fitur inti **Linux Namespaces** yang mengisolasi proses container (`PID`, `NET`, `MNT`, `IPC`, `UTS`, `USER`).
3. Mengonfigurasi **Control Groups (cgroups v1 & v2)** untuk membatasi kuota CPU, batas konsumsi Memory, dan Disk I/O.
4. Menganalisis ekosistem standar Open Container Initiative (OCI): Container Engine (Docker), Container Runtime (containerd, CRI-O), dan Low-level Runtime (`runc`).

---

## 2. Prerequisite
- Memahami konsep dasar proses Linux, PID, dan User Space dari [BAB 01 Module 01](file:///d:/explore/roadmap.sh%20materi/DevOps/BAB-01-Sistem-Operasi-dan-Linux-Automation/Module-01-Arsitektur-Kernel-Linux-Manajemen-Proses-dan-Konkurensi.md).
- Mengetahui cara kerja port dan interface jaringan dari [BAB 02 Module 01](file:///d:/explore/roadmap.sh%20materi/DevOps/BAB-02-Jaringan-Protokol-dan-Web-Servers/Module-01-Jaringan-Komputer-OSI-TCP-DNS-TLS.md).

---

## 3. Concept
Mitos umum yang sering disalahpahami: *"Container adalah virtual machine mini."*
Kenyataannya: **Container bukanlah Virtual Machine (VM)**.

Di dalam sistem Linux:
- Sebuah container **hanyalah proses Linux biasa** yang berjalan langsung di atas kernel host.
- Namun, proses tersebut dipasangi **kacamata kuda (Namespaces)** sehingga hanya bisa melihat resources miliknya sendiri, dan dipasangi **sabuk pengaman (Cgroups)** sehingga tidak bisa menghabiskan seluruh memori dan CPU host.

Docker tidak menciptakan isolasi ini dari nol; Docker mempopulerkan antarmuka developer yang elegan di atas fitur kernel Linux yang sudah ada:
1. **Linux Namespaces**: Memberikan ilusi isolasi (apa yang **dapat dilihat** oleh proses).
2. **Control Groups (cgroups)**: Memberikan pembatasan resource (berapa banyak yang **boleh digunakan** oleh proses).
3. **Union File System (OverlayFS)**: Mekanisme copy-on-write image layer yang membuat container ringan dan instan dinyalakan.

---

## 4. Why?
Mengapa pemahaman internal container penting bagi DevOps?
1. **Pencegahan Noisy Neighbor**: Tanpa cgroups, satu container yang mengalami memory leak dapat memicu OOM Killer kernel untuk mematikan database production di host yang sama.
2. **Keamanan Container Breakout**: Memahami user namespaces dan Linux capabilities (`cap-drop`) mencegah penyerang keluar dari container dan mengambil alih root host OS.
3. **Efisiensi Komputasi & Biaya Cloud**: Dibanding VM yang membutuhkan OS kernel terpisah (ukuran GB dan booting menit), ratusan container dapat berjalan di 1 host Linux dengan footprint MB dan startup dalam milidetik.

---

## 5. What?
Komponen arsitektur container:
- **6 Linux Namespaces Inti**:
  - `PID`: Mengisolasi pohon proses (proses di container melihat dirinya sebagai PID 1).
  - `NET`: Mengisolasi interface jaringan, routing table, dan port binding (tiap container punya IP `eth0` sendiri).
  - `MNT` (Mount): Mengisolasi filesystem mount point (chroot jail modern).
  - `IPC`: Mengisolasi shared memory dan message queues.
  - `UTS`: Mengisolasi hostname dan domain name.
  - `USER`: Memetakan UID/GID container ke user non-root di host.
- **Control Groups (cgroups)**:
  - `cpu.max` / `cpu.cfs_quota_us`: Membatasi throttled CPU cycles.
  - `memory.max`: Membatasi ambang batas RAM sebelum memicu OOM Killer.
- **OCI Container Stack**:
  - `Docker CLI` -> `dockerd` -> `containerd` -> `runc` (memanggil syscall `clone(CLONE_NEWPID|CLONE_NEWNET)`).

---

## 6. How?
Perbandingan Arsitektur VM vs Container:

```text
       [ VIRTUAL MACHINE ]                         [ DOCKER CONTAINER ]
+-------------------------------+           +-------------------------------+
| App A         | App B         |           | App A         | App B         |
| Bins / Libs   | Bins / Libs   |           | Bins / Libs   | Bins / Libs   |
+---------------+---------------+           +---------------+---------------+
| Guest OS (A)  | Guest OS (B)  |           | Namespaces & Cgroups Isolation|
| (Kernel RAM)  | (Kernel RAM)  |           +-------------------------------+
+---------------+---------------+           |        Docker Runtime (runc)  |
|       Hypervisor (KVM/ESXi)   |           +-------------------------------+
+-------------------------------+           |      HOST LINUX KERNEL        |
|       Host Hardware (CPU/RAM) |           |       Host Hardware (CPU/RAM) |
+-------------------------------+           +-------------------------------+
(Berat: GB, Booting: 1-3 Menit)             (Ringan: MB, Booting: < 1 Detik)
```

---

## 7. Analogy
Bayangkan **Virtual Machine vs Container** seperti **Membangun Rumah Tapak vs Menyewa Kamar Apartemen**:
- **Virtual Machine**: Anda membangun rumah tapak terpisah lengkap dengan tiang fondasi, atap genteng, dan generator listrik sendiri (Guest OS). Sangat terisolasi, tetapi mahal, berat, dan butuh waktu lama untuk dibangun.
- **Container**: Anda menyewa kamar unit di sebuah gedung apartemen modern (Host Kernel). Semua kamar berbagi saluran air dan listrik utama yang sama, tetapi masing-masing kamar memiliki pintu terkunci (Namespaces) dan meteran listrik dengan batas daya sekring maksimal (Cgroups).

---

## 8. Diagram
```text
Host Kernel: PID 45892 (Node.js Process)
                     │
                     ├─ Namespace PID: Proses melihat dirinya sebagai PID 1
                     ├─ Namespace NET: Memiliki IP virtual 172.17.0.2
                     ├─ Namespace MNT: Rootfs diisolasi di /var/lib/docker/overlay2/
                     │
                     ▼
+-------------------------------------------------------------+
|                     CGROUPS SUBSYSTEM                       |
|  - Memory Limit: 512 MB  (Jika > 512MB -> Kernel OOM Kill)  |
|  - CPU Quota   : 0.5 CPU (50.000us per 100.000us period)    |
|  - Disk BlkIO  : 10 MB/s read limit                         |
+-------------------------------------------------------------+
```

---

## 9. Simple Example
Membuat isolasi namespace Linux secara manual menggunakan utility `unshare`:

```bash
# 1. Menjalankan shell bash baru di dalam PID & Mount namespace terisolasi
sudo unshare --fork --pid --mount-proc /bin/bash

# Di dalam isolated shell, periksa daftar proses:
ps aux
# Output: Hanya melihat PID 1 (bash) dan ps itu sendiri!

# 2. Menguji cgroups memory limit di Linux
sudo mkdir /sys/fs/cgroup/sandbox_group
echo "100M" | sudo tee /sys/fs/cgroup/sandbox_group/memory.max

# Masukkan proses ke dalam grup pembatas
echo $$ | sudo tee /sys/fs/cgroup/sandbox_group/cgroup.procs
```

---

## 10. Practical Example
Perintah Docker esensial untuk memeriksa pembatasan resource:

```bash
# 1. Menjalankan container dengan limit memori 512MB dan 1 vCPU
docker run -d \
  --name web-app \
  --memory="512m" \
  --cpus="1.0" \
  --restart unless-stopped \
  -p 8080:80 \
  nginx:alpine

# 2. Memantau utilisasi resource container secara real-time
docker stats web-app

# 3. Menginspeksi metadata cgroup dan network namespace container
docker inspect web-app | grep -E "Memory|NanoCpus|IPAddress"
```

---

## 11. Real World Example
### Kasus: Insiden OOMKilled di Kubernetes Akibat Salah Mengatur Memory Request vs Limit
1. Developer mendefinisikan Pod manifest di Kubernetes:
   ```yaml
   resources:
     requests:
       memory: "256Mi"
     limits:
       memory: "512Mi"
   ```
2. Aplikasi Java Spring Boot di dalam container memiliki flag JVM `-Xmx1024m` (alokasi heap 1GB).
3. Saat traffic naik, JVM mengalokasikan RAM hingga 600MB.
4. Cgroups kernel Linux mendeteksi penggunaan memori melampaui `memory.max (512Mi)`.
5. Kernel seketika mengirimkan sinyal `SIGKILL (Exit Code 137)` ke container.
6. Container mati mendadak dengan status `OOMKilled`.
7. **Solusi SRE**: Selalu samakan batas heap JVM dengan cgroup limit (`-XX:MaxRAMPercentage=75.0`) dan sesuaikan resource limits di Kubernetes secara realistis.

---

## 12. Trade-offs
| Aspek | Virtual Machine (VM) | Linux Container (Docker) |
|---|---|---|
| **Keamanan Isolasi** | Sangat tinggi (Isolasi level hardware hypervisor) | Sedang (Berbagi kernel yang sama; rentan kernel exploit jika privilege leak) |
| **Kecepatan Startup** | 30 detik – 3 menit | < 1 detik (Instan) |
| **Konsumsi Resource** | Berat (membutuhkan duplikasi RAM untuk tiap OS) | Sangat hemat (hanya memakan memori proses aplikasi) |
| **Portabilitas** | Bergantung pada format hypervisor (OVA/VHDX) | Standar industri universal (OCI Image) |

---

## 13. When To Use
- Gunakan **Container**: Untuk microservices modern, aplikasi web stateless, batch processing jobs, dan pipeline build CI/CD.
- Gunakan **Virtual Machine**: Saat membutuhkan kernel OS yang berbeda (menjalankan Windows di atas host Linux), atau saat menjalankan beban kerja multi-tenant yang membutuhkan batas kepatuhan keamanan setingkat hardware (*hard multi-tenancy*).

---

## 14. When NOT To Use
- Jangan menggunakan container dengan flag `--privileged` di production tanpa alasan mendesak; flag ini mematikan seluruh isolasi namespace dan memberikan akses root host ke dalam container.

---

## 15. Common Mistakes
1. **Menjalankan Proses Container sebagai `root`**: Membiarkan user default container adalah root (UID 0). Jika ada celah RCE di aplikasi, penyerang memiliki privilege root di kernel host. Selalu definisikan `USER 1000:1000`.
2. **Tidak Memberikan Batas Resource (`--memory` dan `--cpus`)**: Menjalankan container tanpa batas resource memungkinkan 1 container menghabiskan seluruh RAM host (*fork bomb / leak*), menumbangkan server.
3. **Menyimpan Data Penting di Writable Container Layer**: Menaruh file database di writable layer container tanpa persistent volume. Saat container di-restart/upgrade, semua data hilang seketika.

---

## 16. Best Practices
### Must Have
- Selalu tetapkan batas memori dan CPU pada setiap container (`--memory` dan `--cpus`).
- Jalankan proses aplikasi menggunakan user non-root (`USER appuser` di Dockerfile).
- Pasang volume terpisah untuk data persisten (`-v /host/data:/app/data`).

### Recommended
- Gunakan base image minimal (seperti `alpine`, `distroless`, atau `scratch`) untuk memperkecil *attack surface* dan memangkas ukuran image hingga 90%.
- Gunakan `--read-only` rootfs untuk container yang tidak memerlukan modifikasi file lokal.

### Avoid / Overengineering
- Jangan menjalankan Docker-in-Docker (`dind`) dengan privilege root di runner CI jika dapat menggunakan tool daemonless seperti Kaniko atau Buildah.

---

## 17. Troubleshooting
| Gejala | Kemungkinan Penyebab | Solusi |
|---|---|---|
| Container exit dengan kode 137 | Dihabisi oleh OOM (Out of Memory) Killer kernel | Naikkan batas `--memory` atau optimasi memory leak di aplikasi |
| Container exit dengan kode 127 | Command atau binari di `ENTRYPOINT`/`CMD` tidak ditemukan di dalam image | Periksa path file binari dan dependency libc (terutama jika menggunakan Alpine musl) |
| Container tidak bisa resolve nama domain internet | Masalah network namespace DNS (`/etc/resolv.conf`) | Cek konfigurasi bridge docker0 atau berikan flag `--dns 8.8.8.8` |

---

## 18. Exercise
1. Jalankan container Alpine interaktif (`docker run -it alpine sh`), periksa pohon proses dengan `ps aux`, dan amati mengapa PID dimulai dari 1.
2. Bandingkan output `uname -r` di host Linux dan di dalam container untuk membuktikan bahwa keduanya berbagi kernel yang sama.

---

## 19. Challenge
Rancang arsitektur simulasi **Virtual Container Engine (Namespaces & Cgroups Sandbox)**:
- Buat runtime simulator yang memetakan Host PID ke Virtual Container PID.
- Terapkan alokasi Cgroups quota memory (misal 256MB).
- Jika alokasi memory melebihi quota, picu event simulasi `KERNEL OOM KILLER (Exit Code 137)` dan catat audit trace-nya.

---

## 20. Summary
- Container adalah proses Linux standar yang diisolasi menggunakan **Namespaces** (visibilitas) dan dibatasi oleh **Cgroups** (utilisasi).
- Standar OCI (Open Container Initiative) memastikan image container bersifat portabel dan dapat dijalankan di berbagai runtime (`runc`, `containerd`, `CRI-O`).
- Menjalankan container secara aman memerlukan penegakan user non-root dan pembatasan memori/CPU yang ketat.
- Modul praktikum lab dapat dijalankan langsung di [hands-on/m01/container_isolation_sim.js](file:///d:/explore/roadmap.sh%20materi/DevOps/BAB-03-Containerization-Docker/hands-on/m01/container_isolation_sim.js).
