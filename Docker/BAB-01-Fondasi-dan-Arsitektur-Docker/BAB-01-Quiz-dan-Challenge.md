# BAB 01 — Quiz, Challenge, & Knowledge Check: Fondasi & Arsitektur Docker

## A. Quiz Evaluasi Pemahaman

### Bagian 1: Soal Tingkat Dasar (Basic)
1. Jelaskan perbedaan mendasar arsitektur antara Virtual Machine (VM) dan Docker Container dalam hal penggunaan kernel dan sistem operasi!
2. Mengapa proses utama di dalam container selalu memiliki PID bernilai 1 dari sudut pandang internal container?
3. Sebutkan peran masing-masing dari 3 komponen ini: `dockerd`, `containerd`, dan `runc`!
4. Apa fungsi dari `containerd-shim` dan mengapa ia sangat krusial agar container tidak mati saat daemon Docker di-restart?
5. Apa yang dimaksud dengan Open Container Initiative (OCI) dan spesifikasi apa saja yang diaturnya?

### Bagian 2: Soal Tingkat Menengah (Intermediate)
6. Jelaskan bagaimana mekanisme *Copy-on-Write (CoW)* pada storage driver OverlayFS bekerja ketika sebuah proses di dalam container memodifikasi file konfigurasi yang berasal dari base image!
7. Apa arti dari **Exit Code 137** pada container Docker dan sinyal kernel apa yang menyebabkannya?
8. Bagaimana fitur Cgroups v2 `pids.max` melindungi host Linux dari serangan denial-of-service berbasis script *fork bomb*?
9. Apa perbedaan antara Linux Network Namespace (`NET`) dan Mount Namespace (`MNT`) dalam menciptakan ilusi isolasi container?
10. Mengapa pengaturan `"live-restore": true` di file `/etc/docker/daemon.json` wajib diaktifkan pada server produksi?

### Bagian 3: Pertanyaan Skenario Nyata (Scenario-Based)
11. **Skenario 1**: Sebuah container database MySQL tiba-tiba mati setiap pukul 03:00 pagi saat proses batch report harian berjalan. Saat dicek, `docker inspect` menunjukkan field `OOMKilled: true`. Jelaskan analisis Anda terhadap konfigurasi cgroups container dan tindakan remedi yang harus diambil!
12. **Skenario 2**: Administrator sistem memperbarui paket Docker Engine di Ubuntu server produksi menggunakan `apt-get upgrade docker-ce`. Tiba-tiba seluruh 40 container website klien mati bersamaan selama 30 detik. Komponen arsitektur dan konfigurasi apa yang terlewatkan oleh administrator tersebut?
13. **Skenario 3**: Sebuah aplikasi e-commerce menyimpan upload file gambar produk pelanggan langsung ke dalam path `/var/www/uploads` di dalam layer container (tanpa volume). Setelah 3 bulan, performa penulisan file melambat drastis dan harddisk host penuh. Jelaskan secara teknis mengapa layer UpperDir OverlayFS menjadi bottleneck dan bagaimana solusi perbaikannya!

---

## B. Practical Chapter Challenge: Building a Hardened Container Sandbox

### Deskripsi Skenario
Anda diminta merancang konfigurasi eksekusi container yang aman dan kebal terhadap crash server untuk aplikasi untrusted code execution (mirip coding judge sandbox).

### Persyaratan Implementasi:
1. **Resource Constraint Configuration**:
   - Batasi penggunaan memori maksimal 256MB dan nonaktifkan swap berlebih (`--memory-swap=256m`).
   - Batasi kuota CPU maksimal 0.5 core (`--cpus=0.5`).
   - Pasang batas maksimal 30 proses anak (`--pids-limit=30`) untuk menahan fork bomb.
2. **Daemon Hardening**:
   - Tulis draf konfigurasi `/etc/docker/daemon.json` yang mengaktifkan `live-restore`, storage driver `overlay2`, dan log rotation maksimal 3 file berukuran masing-masing 10MB.
3. **Verifikasi Isolasi**:
   - Verifikasi bahwa container tidak dapat melihat proses aplikasi lain di host melalui pembuktian PID namespace.
   - Buktikan bahwa modifikasi file di dalam container tidak merusak file image asli menggunakan prinsip OverlayFS.

---

## C. Knowledge Check & Mastery Checklist

### Saya Harus Memahami:
- [ ] Perbedaan fundamental Container vs Virtual Machine.
- [ ] Rantai eksekusi OCI: Docker CLI -> dockerd -> containerd -> containerd-shim -> runc.
- [ ] 7 Jenis Linux Namespaces dan fungsinya.
- [ ] Mekanisme alokasi Cgroups v2 dan OOM Killer.
- [ ] 4 Layer OverlayFS (LowerDir, UpperDir, WorkDir, MergedDir) dan Copy-on-Write.

### Saya Tidak Perlu Menghafal:
- [ ] Seluruh tabel syscall kernel Linux (cukup pahami `clone()`, `unshare()`, dan `pivot_root()`).
- [ ] Struktur byte biner internal dari layer tarball image OCI.

### Saya Harus Bisa Melakukan:
- [ ] Menjalankan container dengan batasan Cgroups (`--memory`, `--cpus`, `--pids-limit`).
- [ ] Menginspeksi metadata runtime container menggunakan `docker inspect`.
- [ ] Mengonfigurasi `/etc/docker/daemon.json` dengan best practice produksi.
- [ ] Mendiagnosis penyebab container crash akibat OOMKilled (Exit code 137).

```text
Checklist Kesiapan BAB 01:
[ ] Memahami arsitektur Docker & OCI
[ ] Menjalankan hands-on runtime & live-restore m01
[ ] Menjalankan hands-on namespaces, cgroups, & overlayfs m02
[ ] Mampu menjawab seluruh pertanyaan Quiz dan Skenario
```
