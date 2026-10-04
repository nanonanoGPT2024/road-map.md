# BAB 08 — Quiz & Chapter Challenge: Advanced BuildKit & Multi-Architecture

Dokumen ini dirancang untuk menguji pemahaman konseptual, kapabilitas arsitektural, dan keterampilan praktis Anda terkait teknologi **Docker BuildKit engine**, optimasi performa build melalui cache mounts, keamanan injection secrets, serta orkestrasi image **Multi-Architecture** (AMD64 / ARM64) menggunakan **Docker Buildx**.

---

## Bagian 1: Basic Quiz (5 Pertanyaan)

### Soal 1
Mengapa instruksi `ARG GITHUB_TOKEN` dan `RUN git clone https://$GITHUB_TOKEN@github.com/...` sangat tidak direkomendasikan di lingkungan produksi?
- A. Karena ARG hanya bisa menerima string maksimal 32 karakter.
- B. Karena nilai ARG dan perintah git clone akan tersimpan permanen dalam metadata image config dan layer history (`docker history`), sehingga siapa pun yang menarik image dapat membocorkan token tersebut.
- C. Karena BuildKit otomatis menolak build jika mendeteksi kata "TOKEN".
- D. Karena Git clone tidak didukung di dalam container Docker.

### Soal 2
Apa peran dari sintaks `# syntax=docker/dockerfile:1.4` pada baris paling awal sebuah Dockerfile?
- A. Memberikan komentar dokumentasi kepada developer lain.
- B. Mengunci versi Linux kernel host yang boleh mengeksekusi container.
- C. Menginstruksikan BuildKit client untuk menarik image frontend parser Dockerfile versi 1.4 secara dinamis dari registry, mengaktifkan fitur-fitur modern seperti `--mount=type=cache` dan `--mount=type=secret`.
- D. Mengubah format biner container dari OCI menjadi VMDK.

### Soal 3
Apa perbedaan mendasar antara OCI Single Image Manifest dengan OCI Manifest List (Image Index)?
- A. Single Manifest hanya untuk Windows, Manifest List untuk Linux.
- B. Manifest List adalah dokumen JSON induk yang memetakan tuple platform (`os`/`architecture`) ke SHA256 digest dari manifest spesifik masing-masing arsitektur CPU di bawah satu nama image tag yang sama.
- C. Manifest List membatasi ukuran image maksimal 100MB.
- D. Single Manifest tidak mendukung kompresi gzip.

### Soal 4
Mengapa perintah `docker buildx build --platform linux/amd64,linux/arm64 -t myapp:1.0 --load .` akan menghasilkan error pada Docker Engine standar?
- A. Karena Docker CLI tidak memiliki lisensi ARM64.
- B. Karena storage daemon Docker lokal standar tidak mendukung penyimpanan multi-architecture manifest list dalam local image graph driver untuk satu tag tunggal.
- C. Karena QEMU hanya bisa berjalan di macOS.
- D. Karena flag `--load` wajib disertai password admin.

### Soal 5
Apa fungsi dari flag `--mount=type=cache,target=/root/.cache/pip` pada instruksi `RUN`?
- A. Menyimpan file cache instalasi package ke dalam image layer final agar ukuran image membesar.
- B. Mempertahankan direktori cache download dependencies di host daemon antar sesi build, mempercepat re-build secara drastis tanpa memasukkan data cache ke dalam image layer akhir.
- C. Menghapus folder cache secara otomatis setiap 5 menit.
- D. Mengubah koneksi network menjadi offline.

---

## Bagian 2: Intermediate Quiz (5 Pertanyaan)

### Soal 6
Dalam eksekusi graf BuildKit (LLB - Low-Level Builder), apa yang terjadi jika Anda memiliki dua stage Dockerfile independen yang tidak saling bergantung (`FROM node:20 AS fe-build` dan `FROM golang:1.22 AS be-build`)?
- A. BuildKit akan mengeksekusi stage Node.js terlebih dahulu, lalu mem-pause, lalu mengeksekusi stage Go secara berurutan (sekuensial).
- B. BuildKit menganalisis dependensi DAG dan secara otomatis mengeksekusi kedua stage tersebut secara konkuren (paralel), memangkas total waktu eksekusi build.
- C. BuildKit akan melempar peringatan sintaks ganda.
- D. Salah satu stage akan otomatis dibatalkan.

### Soal 7
Saat mengompilasi biner Go multi-arch dengan Buildx, manakah pendekatan yang memberikan throughput kompilasi tertinggi di mesin build x86_64?
- A. Menggunakan QEMU emulation `linux/arm64` untuk menjalankan compiler Go ARM64 di atas CPU x86.
- B. Menggunakan instruksi `FROM --platform=$BUILDPLATFORM golang:1.22-alpine` dan mengoper `TARGETOS` serta `TARGETARCH` ke compiler native Go (`GOOS=${TARGETOS} GOARCH=${TARGETARCH} go build`).
- C. Menghapus flag BuildKit dan menggunakan build manual container-by-container.
- D. Menginstal Rosetta 2 di dalam kontainer Linux.

### Soal 8
Bagaimana cara yang benar untuk menginjeksi SSH private key saat build container yang membutuhkan akses private Git submodule tanpa meninggalkan jejak key pada disk image?
- A. Meng-copy SSH key dengan instruksi `COPY id_rsa /root/.ssh/id_rsa` lalu menjalankan `RUN rm -f /root/.ssh/id_rsa`.
- B. Menggunakan flag `docker buildx build --ssh default ...` dan instruksi `RUN --mount=type=ssh git clone git@github.com:priv/repo.git`, di mana komunikasi dilakukan via forward SSH agent socket di memory.
- C. Memasukkan SSH key ke dalam variabel `ENV SSH_KEY=...`.
- D. Mengubah repository menjadi public sebelum build dimulai.

### Soal 9
Jika container yang baru saja di-deploy ke AWS Graviton (ARM64) menghasilkan error log:
`exec /entrypoint.sh: exec format error`
Langkah diagnosa teknis apa yang harus dilakukan?
- A. Memperbesar RAM server EC2 menjadi 64GB.
- B. Memeriksa arsitektur CPU binary di dalam image dengan `docker inspect` atau `file /entrypoint.sh` untuk membuktikan apakah biner tersebut tidak sengaja ter-compile untuk AMD64 (x86_64).
- C. Menghapus file `docker-compose.yml`.
- D. Mengganti sistem operasi host menjadi Windows Server.

### Soal 10
Apa perbedaan mendasar antara driver builder `docker` default dan driver `docker-container` pada Docker Buildx?
- A. Driver `docker` berjalan di Kubernetes, driver `docker-container` berjalan di laptop.
- B. Driver `docker` menggunakan daemon engine lokal yang memiliki limitasi fitur (tidak mendukung multi-platform export tanpa registry), sedangkan `docker-container` memunculkan container BuildKit dedicated yang mendukung multi-platform, cache mount tingkat lanjut, dan build matrix paralel.
- C. Driver `docker-container` berbayar, driver `docker` gratis.
- D. Driver `docker` hanya mendukung PHP, driver `docker-container` mendukung semua bahasa.

---

## Bagian 3: Scenario-Based Questions (3 Skenario)

### Skenario 1: Kebocoran Kredensial Private NPM Registry
Sebuah tim frontend e-commerce membangun Docker image aplikasi Next.js mereka. Di dalam Dockerfile mereka menuliskan:
```dockerfile
ARG NPM_TOKEN
RUN echo "//npm.pkg.github.com/:_authToken=${NPM_TOKEN}" > .npmrc && \
    npm install && \
    rm -f .npmrc
```
Tim keamanan (Security Pentester) berhasil mengekstraksi `${NPM_TOKEN}` hanya dengan mengunduh image dari Docker Hub dan menjalankan `docker history --no-trunc <image-name>`.
- **Pertanyaan**: Jelaskan mengapa token tersebut tetap bocor meskipun ada perintah `rm -f .npmrc`, dan tuliskan refactoring Dockerfile menggunakan fitur `--mount=type=secret` BuildKit untuk menyelesaikan masalah ini secara permanen.

### Skenario 2: Pipeline CI/CD 40 Menit Akibat Emulasi QEMU
Sebuah startup SaaS memiliki pipeline GitHub Actions runner berbasis Ubuntu AMD64 (`runs-on: ubuntu-latest`). Mereka mengompilasi backend microservice berbasis Rust untuk dua arsitektur (`linux/amd64,linux/arm64`).
Build pipeline memakan waktu **42 menit**, di mana proses kompilasi ARM64 via QEMU menelan 38 menit dan sering kali mengalami timeout runner.
- **Pertanyaan**: Jelaskan mengapa QEMU begitu lambat pada workload kompilasi Rust/C++, dan rancang arsitektur build yang dapat memangkas waktu build tersebut menjadi di bawah 5 menit!

### Skenario 3: Heterogeneous Microservices Deployment Validation
Anda bertindak sebagai Lead DevOps Engineer. Tim Anda baru saja merilis image `registry.internal.corp/fintech/payment-gateway:v3.2.0`.
Server staging menggunakan laptop macOS M3 (ARM64), sedangkan server production menggunakan Dell PowerEdge Intel Xeon (AMD64).
- **Pertanyaan**: Tuliskan perintah CLI `docker buildx imagetools` yang harus Anda jalankan untuk memvalidasi bahwa manifest list image tersebut benar-benar memiliki layer untuk kedua arsitektur sebelum tiket rilis production disetujui.

---

## Bagian 4: Chapter Challenge

### Tantangan Praktis: Multi-Arch BuildKit Pipeline Architect
1. **Skenario**:
   Anda diminta membangun container image untuk aplikasi API berkinerja tinggi yang ditulis dalam Go/Rust.
   Persyaratan teknis:
   - Image harus mendukung arsitektur `linux/amd64` dan `linux/arm64`.
   - Mengambil private dependencies dari repository privat tanpa mengekspos token auth ke layer image.
   - Menggunakan package manager cache mount (`go mod` / `cargo`) agar re-build di CI hanya membutuhkan waktu hitungan detik.
   - Menghasilkan final runtime image berbasis `scratch` atau `distroless` tanpa shell dengan ukuran di bawah 25MB.
2. **Deliverables**:
   - Tuliskan Dockerfile lengkap dengan deklarasi BuildKit syntax, multi-stage, target platforms, cache mount, dan secret mount.
   - Tuliskan urutan perintah Docker Buildx CLI untuk membuat custom builder instance, mem-bootstrap, dan mengeksekusi build multi-arch dengan injection secret dari file lokal.

---

## Bagian 5: Knowledge Check & Checklist

### Saya Harus Memahami:
- [ ] Konsep Directed Acyclic Graph (DAG) pada Low-Level Builder (LLB) BuildKit.
- [ ] Cara kerja `--mount=type=cache` dan perbedaannya dengan Docker layer caching konvensional.
- [ ] Cara kerja `--mount=type=secret` dan `--mount=type=ssh` serta mengapa secret aman dari `docker history`.
- [ ] Struktur OCI Image Index / Manifest List dan resolusi otomatis arsitektur CPU saat `docker pull`.
- [ ] Perbedaan antara QEMU user emulation vs Native Cross-Compilation.

### Saya Tidak Perlu Menghafal:
- Rincian format bytecode QEMU opcodes atau binary header ELF arsitektur CPU.
- Seluruh daftar platform variant unik (cukup tahu bahwa BuildKit menyediakannya melalui variabel environment otomatis).

### Saya Harus Bisa Melakukan:
- [ ] Mengonfigurasi Docker Buildx dengan driver `docker-container`.
- [ ] Menulis Dockerfile multi-stage yang mengoptimalkan cache mount package manager.
- [ ] Menulis Dockerfile yang mengonsumsi secret mount untuk autentikasi private dependencies.
- [ ] Mengompilasi dan memublikasikan image multi-arch (`linux/amd64,linux/arm64`) ke remote registry.
- [ ] Memeriksa integritas manifest list dengan `docker buildx imagetools inspect`.
- [ ] Mengatasi dan men-debug galat `exec format error`.
