# BAB 03: Quiz, Challenge, & Knowledge Check
**Containerization dengan Docker Modern**

---

## 1. Basic Questions (5 Soal)
1. Apa perbedaan mendasar antara isolasi menggunakan Virtual Machine (Hypervisor) dengan isolasi menggunakan Linux Container?
2. Sebutkan fungsi dari 3 Linux Namespaces berikut: `PID`, `NET`, dan `MNT`!
3. Apa peran dari subsistem kernel **Control Groups (cgroups)** dalam operasional container?
4. Mengapa kita disarankan menggunakan teknik **Multi-Stage Build** pada Dockerfile aplikasi produksi?
5. Apa perbedaan antara *Named Volume* dan *Bind Mount* pada penyimpanan data Docker?

---

## 2. Intermediate Questions (5 Soal)
6. Mengapa instruksi `COPY package*.json ./` dan `RUN npm ci` diletakkan **sebelum** instruksi `COPY . .` di Dockerfile?
7. Apa arti dari status container `OOMKilled` dengan `Exit Code 137`? Bagaimana kernel menentukan container mana yang harus dimatikan?
8. Mengapa menjalankan proses aplikasi di dalam container sebagai user `root (UID 0)` dianggap sebagai pelanggaran keamanan serius (*security vulnerability*)?
9. Apa fungsi dari parameter `depends_on` dengan kondisi `service_healthy` pada file `docker-compose.yml`?
10. Bagaimana file `.dockerignore` dapat mempercepat proses build Docker dan melindungi keamanan credential rahasia?

---

## 3. Scenario-Based Questions (3 Soal)

### Skenario A: The 1.8 GB Bloated Production Image
Sebuah tim frontend merilis image Docker React SPA ke production. Ukuran image mencapai 1.8 GB karena memuat seluruh `node_modules`, tool bundler Vite, dan file source TypeScript. Deployment ke cluster Kubernetes membutuhkan waktu 12 menit hanya untuk proses `docker pull`.
- *Pertanyaan:* Bagaimana rancangan Dockerfile Multi-Stage 2 tahap (Builder Node.js + Nginx Alpine Runner) untuk memangkas ukuran image tersebut menjadi di bawah 30 MB?

### Skenario B: The Disappearing Database Data
Seorang engineer menjalankan database MySQL di Docker menggunakan perintah: `docker run -d --name mydb -e MYSQL_ROOT_PASSWORD=rahasia mysql:8.0`. Seminggu kemudian, server di-restart dan container di-recreate. Seluruh data tabel transaksi pelanggan hilang tanpa jejak.
- *Pertanyaan:* Kesalahan apa yang dilakukan oleh engineer tersebut, dan bagaimana perintah yang benar dengan persistent named volume?

### Skenario C: The Host Port Conflict in Compose
Dua developer di tim Anda ingin menjalankan dua branch proyek yang berbeda secara bersamaan di satu mesin laptop menggunakan Docker Compose. Namun, saat menjalankan `docker compose up` pada proyek kedua, muncul error: `Bind for 0.0.0.0:3000 failed: port is already allocated`.
- *Pertanyaan:* Bagaimana cara menggunakan file `.env` untuk memetakan port host dinamis tanpa mengubah file `docker-compose.yml` utama?

---

## 4. Chapter Challenge
**Tantangan Praktis: The Production-Grade Multi-Service Stack**
Buatlah sebuah arsitektur stack terintegrasi yang terdiri dari:
1. **Dockerfile Multi-Stage**: Meng-compile aplikasi web, menerapkan user non-root (`USER 1001:1001`), dan menyertakan instruksi `HEALTHCHECK`.
2. **File `.dockerignore`**: Menyaring `.git`, `node_modules`, `*.md`, dan `.env`.
3. **File `docker-compose.yml`**:
   - Menghubungkan service API dengan database PostgreSQL.
   - Menggunakan persistent named volume untuk data database.
   - Menggunakan isolated bridge network.
   - Memastikan service API hanya menyala setelah healthcheck database berstatus *healthy*.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur internal container (Namespaces, Cgroups, dan OverlayFS).
- [ ] OCI Container Stack: Docker Engine, Containerd, dan Runc.
- [ ] Mekanisme Layer Caching Dockerfile dan cara mengoptimalkannya.
- [ ] Konsep Multi-Stage Build untuk memisahkan build tools dari runtime image.
- [ ] Strategi persistensi data (Named Volumes vs Bind Mounts vs tmpfs).

### Saya tidak perlu menghafal:
- [ ] Seluruh parameter flags cgroup v1 vs v2 secara manual (cukup gunakan konfigurasi Docker/Kubernetes).
- [ ] Struktur internal metadata tar image OCI.

### Saya harus bisa melakukan:
- [ ] Menulis Dockerfile multi-stage yang aman dengan user non-root dan footprint minimal.
- [ ] Mendiagnosis penyebab container exit 137 (OOMKilled) menggunakan `docker inspect` dan `docker stats`.
- [ ] Mengorkestrasikan stack multi-container yang andal menggunakan Docker Compose.

---
*Ketik **LANJUT** untuk berpindah ke BAB 04: Orkestrasi Container dengan Kubernetes (K8s).*
