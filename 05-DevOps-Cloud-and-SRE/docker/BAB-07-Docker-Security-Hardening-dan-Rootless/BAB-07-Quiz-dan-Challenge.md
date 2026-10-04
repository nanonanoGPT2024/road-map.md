# BAB 07 — Quiz, Challenge, & Knowledge Check: Security Hardening & Rootless Docker

## A. Quiz Evaluasi Pemahaman

### Bagian 1: Soal Tingkat Dasar (Basic)
1. Mengapa memberikan akses ke file Unix socket `/var/run/docker.sock` kepada user biasa sama berbahayanya dengan memberikan hak akses `sudo root` penuh?
2. Apa fungsi dari opsi keamanan `--security-opt=no-new-privileges:true` di Docker?
3. Apa yang dimaksud dengan *Rootless Docker* dan bagaimana perbedaannya dengan sekadar menuliskan `USER node` di Dockerfile?
4. Apa fungsi dari flag `--read-only` pada perintah `docker run`?
5. Mengapa flag `--cap-drop=ALL` sangat disarankan untuk diterapkan pada seluruh container produksi?

### Bagian 2: Soal Tingkat Menengah (Intermediate)
6. Jelaskan bagaimana mekanisme Linux Seccomp mem-filter panggilan sistem (*syscalls*) dan apa aksi default kernel jika syscall yang dilarang dipanggil!
7. Bagaimana penyerang dapat mengeksploitasi direktori `/tmp` jika container dijalankan dengan `--read-only` tetapi me-mount `/tmp` tanpa flag `noexec`?
8. Apa perbedaan antara alat pemindai kerentanan seperti **Docker Scout / Trivy** dan alat penandatangan digital seperti **Cosign**?
9. Mengapa aplikasi web yang berjalan sebagai user non-root (UID 10001) tidak dapat mendengarkan port 80 secara default di Linux, dan capability apa yang dapat mengatasinya secara elegan?
10. Bagaimana environment variable `DOCKER_CONTENT_TRUST=1` melindungi server produksi dari serangan *man-in-the-middle* (MITM)?

### Bagian 3: Pertanyaan Skenario Nyata (Scenario-Based)
11. **Skenario 1**: Sebuah aplikasi web e-commerce terkena eksploitasi celah Remote Code Execution (RCE). Hacker mencoba mengunduh script penambang kripto biner ke dalam folder `/tmp` dan mengeksekusinya. Jika Anda telah menerapkan pengerasan keamanan berlapis di container tersebut, jelaskan 2 lapisan pertahanan yang akan membuat serangan hacker tersebut gagal total!
12. **Skenario 2**: Tim pengembang Anda mengeluhkan bahwa rilis ke produksi gagal di pipeline GitHub Actions karena Trivy scanner mendeteksi 1 CVE level `CRITICAL` pada package `openssl` bawaan image `ubuntu:22.04`. Langkah remedi arsitektural apa yang paling cepat dan bersih untuk mengatasinya?
13. **Skenario 3**: Sebuah container database PostgreSQL tiba-tiba crash saat dijalankan dengan custom profile Seccomp yang terlalu ketat. Bagaimana Anda sebagai Platform Engineer melacak syscall spesifik apa yang ditolak oleh kernel untuk memperbaiki profil Seccomp tersebut?

---

## B. Practical Chapter Challenge: Hardened CIS-Benchmark Container Pipeline

### Deskripsi Skenario
Rancang pipeline pengerasan keamanan container tingkat perbankan (*Banking Grade*) yang mematuhi rekomendasi CIS Docker Benchmark.

### Persyaratan Implementasi:
1. **Dockerfile Hardening**:
   - Gunakan base image minimalis non-root (Distroless atau Alpine Non-Root).
   - Buat user dan group eksplisit dengan UID/GID di atas 10000.
   - Setel kepemilikan file dengan `COPY --chown`.
2. **Supply Chain Gate**:
   - Jalankan pemindaian Trivy pada image hasil build. Gagalkan proses jika ada CVE level `CRITICAL` yang memiliki patch.
   - Tanda tangani image digest menggunakan Cosign.
3. **Runtime Command Hardening**:
   - Jalankan container dengan:
     - `--security-opt=no-new-privileges:true`.
     - `--cap-drop=ALL` (dan hanya tambahkan `--cap-add=NET_BIND_SERVICE` jika perlu).
     - `--read-only` root filesystem.
     - `--tmpfs /tmp:rw,noexec,nosuid,size=64m`.
4. **Validasi Pertahanan**:
   - Buktikan bahwa eksekusi biner di `/tmp` ditolak oleh kernel.
   - Buktikan bahwa syscall terlarang (seperti `ptrace`) diblokir oleh Seccomp.

---

## C. Knowledge Check & Mastery Checklist

### Saya Harus Memahami:
- [ ] Vektor serangan Container Breakout dan mitigasi Rootless Docker.
- [ ] Konsep Linux Capabilities dan eliminasi hak akses (`--cap-drop=ALL`).
- [ ] Proteksi Immutability via `--read-only` dan temporary `tmpfs` flags (`noexec`, `nosuid`).
- [ ] Alur Seccomp syscall filtering (Allow, Deny, Errno).
- [ ] Standar pengujian supply chain: CVE scanning (Trivy/Scout) dan Digital Signing (Cosign).

### Saya Tidak Perlu Menghafal:
- [ ] Seluruh 300+ nama syscall Linux di arsitektur x86_64.
- [ ] Seluruh daftar CVE historis di database NVD.

### Saya Harus Bisa Melakukan:
- [ ] Menjalankan container dengan opsi `--read-only` dan `--tmpfs`.
- [ ] Mencabut seluruh capabilities Linux yang tidak diperlukan.
- [ ] Mengintegrasikan pemindaian Trivy di pipeline CI dengan exit code gate.
- [ ] Menandatangani dan memverifikasi image OCI menggunakan Cosign.

```text
Checklist Kesiapan BAB 07:
[ ] Memahami konsep security hardening & rootless
[ ] Menjalankan hands-on container hardening simulator m01
[ ] Menjalankan hands-on seccomp & trivy simulator m02
[ ] Mampu menjawab seluruh pertanyaan Quiz dan Skenario
```
