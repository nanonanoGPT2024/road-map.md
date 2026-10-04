# Module 01: Container vs Virtual Machine, Standar OCI, containerd, runc, & Docker Daemon

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
- Membedakan secara mendalam arsitektur **Container** (isolasi tingkat OS) dengan **Virtual Machine** (virtualisasi perangkat keras penuh).
- Memahami peran **Open Container Initiative (OCI)** dalam standarisasi format image (`image-spec`) dan eksekusi runtime (`runtime-spec`).
- Menguraikan tumpukan arsitektur Docker: **Docker CLI**, **Docker Daemon (`dockerd`)**, **containerd**, **containerd-shim**, dan low-level runtime **runc**.
- Menjelaskan bagaimana container tetap berjalan (*daemonless containers*) meskipun Docker daemon di-restart atau di-upgrade melalui peran `containerd-shim`.
- Mengonfigurasi `/etc/docker/daemon.json` untuk tuning kinerja daemon di lingkungan produksi.

---

## 2. Prerequisite
- Memahami konsep dasar sistem operasi (Kernel vs User Space, System Calls).
- Mengetahui cara kerja terminal command line interface (CLI).
- Pemahaman dasar tentang siklus hidup proses komputer.

---

## 3. Concept
Sebelum container populer, isolasi aplikasi dilakukan menggunakan **Virtual Machine (VM)** melalui Hypervisor (KVM, VMware, Hyper-V). Setiap VM menjalankan kernel sistem operasinya sendiri secara penuh (Guest OS), memakan resource RAM gigabyte dan waktu booting hitungan menit.

**Container** adalah virtualisasi tingkat sistem operasi (*OS-level virtualization*). Container bukanlah mesin virtual; container pada hakikatnya adalah **proses Linux biasa** yang diisolasi menggunakan fitur bawaan kernel (Namespaces dan Cgroups) dan berbagi satu kernel host yang sama.

```
       VIRTUAL MACHINE (VM)                      CONTAINER (DOCKER)
 ┌───────────────────────────────┐       ┌───────────────────────────────┐
 │ App A  │ App B  │ App C       │       │ App A  │ App B  │ App C       │
 ├────────┼────────┼─────────────┤       ├────────┼────────┼─────────────┤
 │ Bins   │ Bins   │ Bins        │       │ Bins   │ Bins   │ Bins        │
 ├────────┼────────┼─────────────┤       ├───────────────────────────────┤
 │ Guest  │ Guest  │ Guest       │       │ Container Engine (containerd) │
 │ OS     │ OS     │ OS          │       ├───────────────────────────────┤
 ├───────────────────────────────┤       │ Host Operating System         │
 │ Hypervisor (Type 1 / 2)       │       ├───────────────────────────────┤
 ├───────────────────────────────┤       │ Shared Linux Kernel           │
 │ Host OS & Server Hardware     │       ├───────────────────────────────┤
 └───────────────────────────────┘       │ Server Hardware               │
                                         └───────────────────────────────┘
```

---

## 4. Why?
1. **Densitas & Efisiensi Resource**: Sebuah server fisik dengan 32GB RAM hanya mampu menjalankan 10-15 VM karena setiap VM memakan overhead OS 1-2GB. Server yang sama dapat menjalankan ratusan container secara bersamaan karena container tidak membuang memori untuk kernel terduplikasi.
2. **Kecepatan Booting Instan**: Memulai VM membutuhkan waktu 30-90 detik untuk inisialisasi BIOS, bootloader, dan init system (systemd). Memulai container hanya membutuhkan waktu beberapa milidetik karena hanya memanggil syscall `clone()` untuk menjalankan proses baru.
3. **Imutabilitas Lingkungan**: Menghilangkan masalah klasik *"It works on my machine!"*. Container mengemas kode aplikasi beserta seluruh dependensi library binary ke dalam satu unit portabel yang dijamin berjalan identik di laptop developer, staging, maupun multi-cloud.

---

## 5. What?
Komponen arsitektur modern Docker:
- **Docker CLI (`docker`)**: Perintah baris yang digunakan pengguna untuk berinteraksi dengan engine. Berkomunikasi dengan daemon melalui Unix domain socket (`/var/run/docker.sock`) atau REST API over mTLS.
- **Docker Daemon (`dockerd`)**: Layanan persisten tingkat tinggi yang menangani antarmuka API, build image, manajemen volume, dan jaringan container.
- **containerd**: Daemon runtime container standar industri (CNCF Graduated) yang mengelola siklus hidup container lengkap: transfer image, eksekusi container, dan pemantauan storage.
- **containerd-shim**: Proses perantara ringan antara containerd dan runc. Shim bertindak sebagai parent process dari container, menangani file descriptor I/O (stdin, stdout, stderr), dan mempertahankan container tetap hidup saat dockerd atau containerd di-restart.
- **runc**: Low-level runtime OCI resmi yang berinteraksi langsung dengan kernel Linux untuk mengonfigurasi cgroups dan namespaces sebelum menjalankan proses target.

---

## 6. How?
Rantai Peristiwa Saat Anda Menjalankan `docker run -d nginx`:
1. **CLI Request**: Pengguna mengetik `docker run -d nginx`. CLI mengemas perintah menjadi HTTP POST request ke Unix socket `/var/run/docker.sock`.
2. **Daemon Evaluation**: `dockerd` menerima request, memeriksa apakah image `nginx` tersedia di cache lokal. Jika tidak, daemon menginstruksikan `containerd` untuk menarik (*pull*) layer image dari Docker Hub.
3. **RootFS Preparation**: `containerd` membongkar layer image menggunakan storage driver (OverlayFS) untuk membuat read-write root filesystem bagi container.
4. **OCI Bundle Creation**: `containerd` membuat konfigurasi standar OCI (`config.json`) yang menentukan namespace, cgroup limits, environment variables, dan mount points.
5. **runc Execution**: `containerd` memanggil `runc` untuk membuat container.
6. **Shim Attachment**: `containerd-shim` mengambil alih kepemilikan I/O process. Setelah container aktif berjalan, binary `runc` langsung exit (*run-and-exit*), meninggalkan proses container di bawah pengawasan `containerd-shim`.

---

## 7. Analogy
Bayangkan **Virtual Machine** vs **Container** seperti **Membangun Rumah Tapak Pribadi** vs **Menyewa Kamar di Apartemen Modern**:
- **VM** seperti membangun rumah tapak lengkap dari nol: Anda harus membangun pondasi sendiri, instalasi pipa air sendiri, genset listrik sendiri, dan satpam sendiri (**Full Guest OS & Kernel**). Sangat aman dan terisolasi total, namun sangat mahal dan memakan lahan luas.
- **Container** seperti menyewa kamar apartemen: Setiap penyewa memiliki kunci pintu sendiri, privasi kamar mandi sendiri, dan dekorasi kamar sendiri (**Namespaces & RootFS**), namun semua penghuni berbagi satu pondasi gedung, pipa air utama, dan gardu listrik PLN gedung yang sama (**Shared Host Kernel**). Sangat efisien, hemat biaya, dan bisa menampung ribuan orang dalam satu gedung.

---

## 8. Diagram
```
+-----------------------------------------------------------------------------------+
|                        MODERN DOCKER ENGINE ARCHITECTURE                          |
+-----------------------------------------------------------------------------------+

 [ Developer ] 
      │
      ▼ (docker run -d -p 80:80 nginx)
 ┌──────────────────────────────────────┐
 │ Docker CLI                           │
 └──────────────────┬───────────────────┘
                    │ REST API via /var/run/docker.sock
                    ▼
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ Docker Daemon (dockerd)                                                     │
 │   - Image Building, Network Management, Volume Drivers, REST API Router     │
 └──────────────────┬──────────────────────────────────────────────────────────┘
                    │ gRPC API Call
                    ▼
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ containerd (CNCF Project)                                                   │
 │   - Image Distribution, Content Store, Snapshotter, Metadata Service        │
 └──────────┬──────────────────────────────────────────────────────┬───────────┘
            │                                                      │
            ▼ (Spawns shim)                                        ▼
 ┌──────────────────────┐                               ┌──────────────────────┐
 │ containerd-shim      │                               │ containerd-shim      │
 └──────────┬───────────┘                               └──────────┬───────────┘
            │ calls runc                                           │ calls runc
            ▼                                                      ▼
 ┌──────────────────────┐                               ┌──────────────────────┐
 │ runc (OCI Runtime)   │ ──(configures kernel)──>      │ runc (OCI Runtime)   │
 └──────────┬───────────┘                               └──────────┬───────────┘
            │ (runc exits after start)                             │
            ▼                                                      ▼
 ┌──────────────────────┐                               ┌──────────────────────┐
 │ Container Process:   │                               │ Container Process:   │
 │   Nginx Web Server   │                               │   Redis In-Memory    │
 └──────────────────────┘                               └──────────────────────┘
```

---

## 9. Simple Example: Memverifikasi Komponen Arsitektur via Terminal
Perintah untuk melihat proses `dockerd`, `containerd`, dan `containerd-shim` di Linux:

```bash
# 1. Menjalankan container di background
docker run -d --name web-test nginx:alpine

# 2. Melihat pohon proses (process tree) yang membuktikan hierarki arsitektur
pstree -p $(pgrep dockerd)
# Output:
# dockerd(1042)───containerd(1120)───containerd-shim(2401)───nginx(2425)───nginx(2440)

# 3. Mengetahui versi spesifik containerd dan runc bawaan Docker
docker info | grep -E "Server Version|Runtimes|containerd|runc"
```

---

## 10. Practical Example: Konfigurasi Kinerja Produksi `/etc/docker/daemon.json`
Konfigurasi optimal untuk server produksi Linux:

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "50m",
    "max-file": "3"
  },
  "storage-driver": "overlay2",
  "live-restore": true,
  "userland-proxy": false,
  "default-ulimits": {
    "nofile": {
      "Name": "nofile",
      "Hard": 65536,
      "Soft": 65536
    }
  },
  "metrics-addr": "127.0.0.1:9323",
  "experimental": false
}
```

> **Catatan Kritis**: Pengaturan `"live-restore": true` memastikan bahwa jika daemon `dockerd` di-restart atau di-upgrade, seluruh container yang sedang berjalan **TIDAK AKAN DIBUNUH / DOWNTIME**, berkat peran `containerd-shim`.

---

## 11. Real World Example: Migrasi 80 Microservices dari VM ke Container
Sebuah platform perbankan digital sebelumnya menjalankan setiap microservice di dalam 1 Virtual Machine AWS EC2 (`t3.medium` seharga $30/bulan per VM):
- **Total Biaya VM**: $80 \times \$30 = \$2.400 / \text{bulan}$. Rata-rata utilisasi CPU hanya $8\%$.
- **Migrasi ke Docker Container**:
  1. Seluruh 80 microservice dikemas ke dalam container OCI.
  2. Dijalankan di atas 4 server fisik bare-metal/EC2 berukuran besar (`c6i.4xlarge`) dengan Docker Engine & containerd.
- **Hasil**:
  - Biaya komputasi turun dari $2.400 menjadi $680/bulan (hemat 71%).
  - Waktu deployment rilis versi baru turun drastis dari 12 menit (reboot VM) menjadi 4 detik per container.

---

## 12. Trade-offs

| Aspek | Virtual Machine (VM) | Container (Docker) |
|---|---|---|
| **Isolasi Keamanan** | Sangat Kuat (Hardware level boundary via Hypervisor) | Sedang (OS level boundary, berbagi shared kernel) |
| **Startup Time** | Lambat (30-120 detik) | Instan (10-500 milidetik) |
| **Overhead Memori** | Besar (1-4 GB per guest OS) | Minimal (Hanya memori aplikasi itu sendiri) |
| **Dukungan Heterogen** | Bebas (Bisa jalankan Windows VM di atas Linux host) | Terikat (Linux container wajib jalan di Linux kernel) |
| **Performa I/O Disk & Network** | Mengalami degradasi emulasi hypervisor (~5-15%) | Hampir mendekati performa native bare-metal (~99%) |

---

## 13. When To Use
- Arsitektur microservices, aplikasi web modern, API, worker background, dan pipeline CI/CD.
- Lingkungan pengembangan tim yang membutuhkan replikasi dependensi identik di semua mesin developer.
- Menjalankan puluhan aplikasi terisolasi pada satu server tanpa pemborosan RAM.

---

## 14. When NOT To Use
- Menjalankan sistem operasi non-Linux (misal aplikasi legacy Windows Server 2003 yang butuh kernel berbeda) pada host Linux.
- Aplikasi dengan persyaratan regulasi keamanan militer/finansial tertentu yang secara tegas mewajibkan isolasi kernel perangkat keras mandiri (Gunakan VM atau MicroVM seperti AWS Firecracker / Kata Containers).

---

## 15. Common Mistakes
1. **Mengira Container adalah VM Mini**: Memperlakukan container seperti VM dengan memasang SSH server di dalam container (`sshd`), menginstal cron daemon, dan mengedit file langsung via nano di dalam container. Satu container idealnya hanya menjalankan **satu proses utama** (`one process per container`).
2. **Menyimpan Data Persisten di Root Filesystem Container**: Menyimpan database MySQL langsung di layer container tanpa Docker Volume. Begitu container di-destroy atau di-upgrade, seluruh data hilang seketika.
3. **Mematikan `live-restore` di Production**: Lupa mengaktifkan `"live-restore": true` di `daemon.json`, sehingga saat `apt upgrade docker-ce` dijalankan, seluruh container produksi mati serempak.

---

## 16. Best Practices
### Must Have
- Aktifkan `"live-restore": true` di `/etc/docker/daemon.json`.
- Pasang log rotation (`max-size`, `max-file`) pada daemon agar file log container tidak menghabiskan seluruh kapasitas harddisk server.
- Jangan pernah mengekspos Docker Unix socket `/var/run/docker.sock` ke internet publik tanpa autentikasi mTLS.

### Recommended
- Gunakan storage driver `overlay2` (default di Linux modern).
- Pantau metrik internal Docker daemon dengan mengaktifkan `"metrics-addr": "127.0.0.1:9323"`.

### Advanced
- Gabungkan containerd dengan runtime terisolasi berbasis gVisor (`runsc`) atau Kata Containers untuk workload multi-tenant yang membutuhkan perlindungan isolasi kernel ganda.

---

## 17. Troubleshooting
- **Masalah**: `Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?`
  - *Diagnostik*: Jalankan `systemctl status docker` dan periksa log `journalctl -u docker -e`.
  - *Solusi*: Nyalakan daemon dengan `sudo systemctl start docker`, dan tambahkan user Anda ke grup docker: `sudo usermod -aG docker $USER`.
- **Masalah**: Error `no space left on device` saat menjalankan container baru, padahal `df -h` menunjukkan disk masih 30% kosong.
  - *Penyebab*: Inodes habis atau storage driver layer menumpuk file dangling.
  - *Solusi*: Bersihkan resource terbengkalai dengan `docker system prune -a --volumes`.

---

## 18. Exercise
1. Jalankan container Nginx dengan port forwarding 8080:80. Telusuri PID container tersebut di host Linux menggunakan perintah `docker inspect --format '{{.State.Pid}}' <container-id>` dan buktikan bahwa proses tersebut terlihat di `ps aux` host!
2. Buat file `/etc/docker/daemon.json` dengan log driver `json-file` berukuran maksimal 20MB dan lakukan verifikasi menggunakan `docker info`.

---

## 19. Challenge
Simulasikan kegagalan daemon Docker:
- Jalankan container background yang melakukan streaming stempel waktu setiap detik ke file log.
- Lakukan restart mendadak pada layanan `dockerd` (`systemctl restart docker`).
- Buktikan bahwa container tetap hidup tanpa jeda downtime berkat peran `containerd-shim` dan pengaturan `live-restore`.

---

## 20. Summary
- Container adalah proses Linux terisolasi tingkat OS, sedangkan VM adalah virtualisasi hardware penuh.
- OCI menstandarisasi format image dan runtime untuk mencegah fragmentasi vendor.
- Arsitektur Docker modular memisahkan `dockerd` (API/management), `containerd` (lifecycle supervisor), `containerd-shim` (I/O & orphan protector), dan `runc` (kernel executor).
- Fitur `live-restore` menjamin ketersediaan tinggi container saat daemon Docker mengalami restart atau maintenance.
