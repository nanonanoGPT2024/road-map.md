# Module 02: Linux Namespaces, Cgroups v2, & Storage Driver (OverlayFS)

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
- Menguasai 7 jenis **Linux Namespaces** yang mendasari isolasi container: PID, NET, MNT, UTS, IPC, USER, dan CGROUP.
- Memahami arsitektur pembatasan resource menggunakan **Control Groups (Cgroups v1 vs Cgroups v2)**.
- Mengonfigurasi batasan CPU, Memory, I/O, dan proses maksimal (`pids.max`) untuk mencegah serangan *fork bomb*.
- Menjelaskan cara kerja kernel **OOM (Out Of Memory) Killer** saat container melampaui batas memori.
- Membedah cara kerja storage driver **OverlayFS**: *LowerDir*, *UpperDir*, *WorkDir*, dan *MergedDir*.
- Memahami mekanisme **Copy-on-Write (CoW)** dan dampaknya terhadap performa I/O container.

---

## 2. Prerequisite
- Memahami konsep dasar proses Linux, PID 1, dan syscall sistem operasi (BAB 01 Module 01).
- Mengetahui struktur direktori Linux Filesystem Hierarchy Standard (FHS).
- Pemahaman dasar tentang memori komputer (RAM, Swap, Virtual Memory).

---

## 3. Concept
Container bukanlah fitur tunggal di kernel Linux. Istilah "container" hanyalah nama populer untuk gabungan 3 teknologi inti kernel Linux:
1. **Namespaces (*What you can see*)**: Memberikan ilusi kepada proses bahwa ia adalah satu-satunya entitas yang hidup di sistem, membatasi apa yang bisa *dilihat* oleh proses.
2. **Control Groups / Cgroups (*What you can use*)**: Mengukur, membatasi, dan mengisolasi penggunaan sumber daya fisik sistem (CPU, RAM, Disk I/O, jumlah thread), membatasi apa yang bisa *digunakan* oleh proses.
3. **OverlayFS (*What you can modify*)**: Sistem berkas berlapis (*Union Filesystem*) yang menggabungkan beberapa direktori read-only menjadi satu tampilan direktori terpadu dengan layer read-write tipis di atasnya.

```
       LINUX KERNEL ISOLATION PRIMITIVES
 ┌─────────────────────────────────────────────────────────────┐
 │                         CONTAINER                           │
 │                                                             │
 │  ┌─────────────────────────┐   ┌─────────────────────────┐  │
 │  │ NAMESPACES (ISOLATION)  │   │   CGROUPS (RESOURCE)    │  │
 │  │ - PID (Isolated PIDs)   │   │ - cpu.max (2 Cores)     │  │
 │  │ - NET (Virtual eth0)    │   │ - memory.max (512MB)    │  │
 │  │ - MNT (Chroot / RootFS) │   │ - pids.max (100 procs)  │  │
 │  │ - UTS (Hostname: web01) │   │ - io.max (Disk limits)  │  │
 │  └────────────┬────────────┘   └────────────┬────────────┘  │
 │               │                             │               │
 │               ▼                             ▼               │
 │  ┌───────────────────────────────────────────────────────┐  │
 │  │ STORAGE: OverlayFS (Merged View = LowerDir + UpperDir)│  │
 │  └───────────────────────────────────────────────────────┘  │
 └──────────────────────────────┬──────────────────────────────┘
                                │
                                ▼
                       [ SHARED LINUX KERNEL ]
```

---

## 4. Why?
1. **Keamanan & Pencegahan Gangguan Antar-Aplikasi (*Noisy Neighbors*)**: Tanpa Cgroups, satu aplikasi buggy yang mengalami memory leak atau infinite loop CPU akan menyedot 100% kapasitas server dan mematikan seluruh aplikasi lain di server yang sama.
2. **Pencegahan Fork Bomb**: Tanpa pembatasan `pids.max`, penyerang atau script loop sederhana (`:(){ :|:& };:`) dapat membuat jutaan proses dalam 2 detik dan melumpuhkan sistem operasi (*kernel panic*).
3. **Efisiensi Disk Storage Melalui Copy-on-Write**: Jika Anda menjalankan 50 container berbasis image `ubuntu:22.04` (ukuran 78MB), Anda tidak menghabiskan $50 \times 78\text{MB} = 3.9\text{GB}$ disk. Seluruh 50 container membaca layer image yang sama persis (**LowerDir**), dan hanya memakan beberapa Kilobyte untuk perubahan file baru (**UpperDir**).

---

## 5. What?
### 7 Linux Namespaces:
- **PID**: Mengisolasi pohon proses. Proses utama di dalam container melihat dirinya sebagai **PID 1**, meskipun di kernel host proses tersebut memiliki PID sebenarnya (misal PID 28419).
- **NET**: Mengisolasi antarmuka jaringan fisik/virtual, port routing, firewall iptables, dan socket table.
- **MNT (Mount)**: Mengisolasi mount points filesystem sehingga container memiliki direktori root (`/`) sendiri tanpa melihat direktori root host.
- **UTS**: Mengisolasi hostname dan domain name (`hostname web-prod-01`).
- **IPC**: Mengisolasi System V IPC dan antrean pesan memori POSIX.
- **USER**: Memetakan UID/GID container ke UID/GID host (misal user `root` UID 0 di dalam container dipetakan ke user biasa UID 10001 di host untuk keamanan).
- **CGROUP**: Mengisolasi visibilitas struktur direktori `/sys/fs/cgroup`.

### Struktur 4 Layer OverlayFS:
- **LowerDir (Read-Only)**: Layer-layer dasar dari container image (tidak pernah diubah).
- **UpperDir (Read-Write)**: Layer tipis tempat file baru ditulis atau file yang dimodifikasi disimpan.
- **WorkDir**: Direktori kerja internal kernel untuk mempersiapkan file secara atomik sebelum dipindahkan ke UpperDir.
- **MergedDir (Unified View)**: Titik mount gabungan tempat container melihat keseluruhan file sistem secara utuh.

---

## 6. How?
### Mekanisme Copy-on-Write (CoW) Saat File Dimodifikasi:
1. Container membaca file `/etc/nginx/nginx.conf`: Kernel membaca langsung dari **LowerDir** (kecepatan native).
2. Container mengubah isi file `/etc/nginx/nginx.conf`:
   - Kernel mendeteksi operasi penulisan (*write request*).
   - Kernel menyalin file asli dari **LowerDir** ke **UpperDir** (*Copy-up operation*).
   - Perubahan disimpan di **UpperDir**. File asli di **LowerDir** tetap perawan tak tersentuh.
3. Container menghapus file: Kernel tidak menghapus file di **LowerDir**, melainkan membuat file khusus bertanda *Whiteout* di **UpperDir** sehingga file tersebut tidak tampak di **MergedDir**.

---

## 7. Analogy
- **Namespaces** seperti **Kacamata Kuda Teater**: Setiap aktor di atas panggung hanya bisa melihat naskahnya sendiri dan tidak bisa melihat penonton atau aktor lain di balik panggung.
- **Cgroups** seperti **Meteran Listrik & Token Air Kamar Kos**: Pemilik gedung membatasi kamar kos Anda maksimal menyedot listrik 900 Watt dan air 100 liter per hari. Jika Anda menyalakan AC melebihi batas, sekring meteran Anda langsung anjlok (**OOM Killer**).
- **OverlayFS** seperti **Menulis di Atas Lembaran Mika Transparan**:
  - Buku cetak teks asli yang dijilid adalah **LowerDir** (Read-Only).
  - Anda meletakkan plastik mika bening di atas halaman buku tersebut (**UpperDir**).
  - Anda mencoret-coret mika tersebut menggunakan spidol. Buku asli di bawahnya tidak pernah rusak atau tercoret, namun siapapun yang melihat dari atas (**MergedDir**) melihat buku beserta coretan baru Anda.

---

## 8. Diagram
```
+-----------------------------------------------------------------------------------+
|                        OVERLAYFS UNION STORAGE ENGINE                             |
+-----------------------------------------------------------------------------------+

 [ Container Merged View ] ──> Melihat: /app/index.js (baru), /bin/bash, /etc/hosts
 ═══════════════════════════════════════════════════════════════════════════════════
 
 ┌───────────────────────────────────────────────────────────────┐
 │ UPPERDIR (Read-Write Layer):                                  │
 │   - /app/index.js (File baru ditambahkan atau dimodifikasi)   │
 │   - /etc/hosts (Whiteout marker jika ada file dihapus)        │
 └───────────────────────────────┬───────────────────────────────┘
                                 │
                     Copy-on-Write (CoW) Mechanism
                                 │
 ┌───────────────────────────────┴───────────────────────────────┐
 │ LOWERDIR 2 (Read-Only Image Layer):                           │
 │   - Node.js runtime libraries (/usr/local/bin/node)           │
 ├───────────────────────────────────────────────────────────────┤
 │ LOWERDIR 1 (Read-Only Base Image Layer):                      │
 │   - Alpine Linux RootFS (/bin, /lib, /etc)                    │
 └───────────────────────────────────────────────────────────────┘
```

---

## 9. Simple Example: Menjalankan Container dengan Cgroup Limits
Perintah membatasi CPU, Memory, dan PIDs:

```bash
# Menjalankan container dengan batas 1.5 CPU Core, 512MB RAM, dan maksimal 50 proses
docker run -d \
  --name app-constrained \
  --cpus="1.5" \
  --memory="512m" \
  --memory-swap="512m" \
  --pids-limit=50 \
  nginx:alpine

# Memeriksa konfigurasi Cgroups v2 langsung di virtual filesystem Linux host
cat /sys/fs/cgroup/system.slice/docker-<container-id>.scope/memory.max
# Output: 536870912 (512 MB dalam bytes)
```

---

## 10. Practical Example: Menginspeksi Layer OverlayFS Secara Nyata
Melihat lokasi direktori LowerDir dan UpperDir dari container aktif:

```bash
docker inspect app-constrained --format '{{json .GraphDriver.Data}}' | jq .
```
Output:
```json
{
  "LowerDir": "/var/lib/docker/overlay2/layer-sha-base/diff",
  "MergedDir": "/var/lib/docker/overlay2/layer-sha-active/merged",
  "UpperDir": "/var/lib/docker/overlay2/layer-sha-active/diff",
  "WorkDir": "/var/lib/docker/overlay2/layer-sha-active/work"
}
```

---

## 11. Real World Example: Mencegah Kernel Panic Akibat Fork Bomb Bug
Sebuah microservice pemroses gambar memiliki bug rekursi tak terhingga (*recursive worker spawn*):
- **Tanpa Cgroups (`--pids-limit`)**: Proses menciptakan 65.000 thread dalam 5 detik. Tabel proses kernel host (`PID table`) penuh. Administrator tidak bisa melakukan login SSH ke server (`fork: Cannot allocate memory`). Server fisik harus di-hard reboot secara manual, menyebabkan downtime 45 menit.
- **Dengan Cgroups**: DevOps menetapkan `--pids-limit=100`. Saat proses ke-101 mencoba dibuat, kernel menolak syscall `clone()`. Container melempar error internal namun **host Linux tetap 100% stabil**, dan container lain tidak terpengaruh sama sekali.

---

## 12. Trade-offs

| Aspek | Cgroups v1 | Cgroups v2 |
|---|---|---|
| **Hierarki Pengontrol** | Terpisah per controller (memory, cpu terpecah di folder berbeda) | Unified Hierarchy tunggal (`/sys/fs/cgroup`) |
| **Dukungan Rootless** | Sangat terbatas / rumit | Native dan aman untuk unprivileged users |
| **Kontrol Buffer I/O** | Buruk (Writeback memory tidak terhitung ke memory cgroup) | Sempurna (Penggabungan kalkulasi memory dan block I/O) |
| **Adopsi Sistem Modern** | Usang (Legacy di kernel lama) | Standar modern (Ubuntu 22.04+, Debian 11+, RHEL 9+) |

---

## 13. When To Use
- Selalu tentukan batas `--memory` dan `--cpus` pada seluruh container produksi.
- Gunakan `--pids-limit` pada aplikasi yang mengeksekusi kode dinamis atau parsing file eksternal (worker upload, compiler, runner).

---

## 14. When NOT To Use
- Jangan gunakan CoW filesystem (layer container biasa) untuk database dengan write throughput sangat tinggi (PostgreSQL / Cassandra / MongoDB). Gunakan **Docker Named Volumes** yang langsung menembus ke disk host tanpa overhead CoW.

---

## 15. Common Mistakes
1. **Tidak Menentukan `--memory-swap`**: Memberikan batas `--memory="512m"` namun membiarkan swap tidak terbatas. Saat container kehabisan RAM 512MB, kernel akan memindahkan data ke Swap disk yang sangat lambat, menyebabkan performa server melambat drastis (*disk thrashing*) alih-alih me-restart container. Setel `--memory-swap="512m"` untuk menonaktifkan swap bagi container tersebut.
2. **Menulis File Log Raksasa ke Layer Container**: Mengizinkan aplikasi mencetak log ke file lokal `/var/log/app.log` di dalam container. Hal ini menyebabkan **UpperDir** membengkak puluhan gigabyte dan menguras disk host `/var/lib/docker/`.

---

## 16. Best Practices
### Must Have
- Pastikan sistem host Linux Anda sudah menggunakan **Cgroups v2** (Periksa dengan `stat -fc %T /sys/fs/cgroup/` -> harus menghasilkan `cgroup2fs`).
- Selalu batasi `--memory` dan pasang restart policy agar saat terkena OOMKilled, container otomatis bangkit kembali.
- Pasang `--read-only` pada root filesystem container dan gunakan `tmpfs` untuk temporary direktori `/tmp`.

### Recommended
- Gunakan User Namespaces (`--userns-remap=default`) agar UID 0 di container tidak memiliki akses root ke host kernel.

### Advanced
- Gunakan utility `systemd-cgls` dan `systemd-cgtop` untuk memantau konsumsi sumber daya cgroup secara real-time di terminal host.

---

## 17. Troubleshooting
- **Masalah**: Container tiba-tiba mati dengan **Exit Code 137**.
  - *Diagnostik*: Jalankan `docker inspect <container-id> --format '{{.State.OOMKilled}}'`. Jika `true`, container dibunuh oleh kernel OOM Killer.
  - *Solusi*: Naikkan batas `--memory` atau cari memory leak di kode aplikasi menggunakan profiler.
- **Masalah**: I/O aplikasi database di container terasa sangat lambat dibanding native host.
  - *Penyebab*: Database menulis file `.db` ke layer OverlayFS (UpperDir) yang memiliki overhead Copy-on-Write.
  - *Solusi*: Pindahkan direktori data database ke Docker Volume terdedikasi (`-v pgdata:/var/lib/postgresql/data`).

---

## 18. Exercise
1. Tulis perintah `docker run` untuk menjalankan container Python yang dibatasi maksimal 256MB RAM, 0.5 CPU, dan 20 PIDs.
2. Buat skrip mount OverlayFS manual di Linux menggunakan perintah `mount -t overlay overlay -o lowerdir=...,upperdir=...,workdir=... target_dir` untuk memahami cara kerja union mount dari sudut pandang kernel!

---

## 19. Challenge
Simulasikan serangan OOM Killer dan Fork Bomb:
- Buat skrip simulasi alokasi array tak terhingga yang melampaui batas memori cgroup.
- Buktikan bahwa kernel mengirimkan sinyal `SIGKILL` (Exit Code 137).
- Buat skrip simulasi pembatasan `pids.max` dan buktikan bahwa proses baru ditolak secara elegan saat batas tercapai.

---

## 20. Summary
- Container diisolasi oleh **Namespaces** (*visibilitas*) dan dibatasi oleh **Cgroups v2** (*kapasitas*).
- **OverlayFS** menggabungkan layer image read-only (**LowerDir**) dengan layer container read-write (**UpperDir**) melalui mekanisme **Copy-on-Write**.
- Membatasi Memory, CPU, dan PIDs adalah kewajiban mutlak untuk menjaga stabilitas dan ketahanan sistem produksi.
