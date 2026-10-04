# Module 01: Anatomi Image Layer, Caching Strategy, & Instruksi Fundamental

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
- Memahami struktur internal **OCI/Docker Image**: file manifest, konfigurasi JSON, dan layer tarball yang bersifat *read-only & immutable*.
- Menguasai logika **Docker Build Cache Engine** dan memahami faktor-faktor pemicu *cache hit* vs *cache invalidation*.
- Mengatur urutan instruksi Dockerfile secara strategis untuk memaksimalkan efisiensi re-build (*Least Frequently Changed First*).
- Membedakan perbedaan instruksi fundamental yang sering disalahpahami: **`COPY` vs `ADD`**, **`ENV` vs `ARG`**, dan **`ENTRYPOINT` vs `CMD`** (*Exec Form* vs *Shell Form*).
- Mengonfigurasi file **`.dockerignore`** untuk mempercepat proses pengiriman build context dan melindungi rahasia (*credentials*).

---

## 2. Prerequisite
- Memahami konsep dasar Linux Filesystem dan storage driver OverlayFS (BAB 01 Module 02).
- Mengetahui cara kerja terminal dan syntax dasar scripting shell.
- Memahami konsep git commit dan hash SHA-256.

---

## 3. Concept
Sebuah Docker image bukanlah satu file biner raksasa monolitik. Docker image adalah tumpukan **layer-layer read-only (*read-only tarball layers*)** yang disusun secara bertingkat. Setiap instruksi di dalam Dockerfile yang memodifikasi sistem berkas (seperti `RUN`, `COPY`, dan `ADD`) menciptakan satu layer baru yang diidentifikasi secara kriptografis menggunakan **Content Addressable Storage (SHA-256)**.

Saat Anda menjalankan perintah `docker build`, Docker Engine memeriksa apakah layer yang sama persis dengan hash input yang identik sudah pernah dibangun sebelumnya. Jika ya, Docker tidak akan menjalankan ulang perintah tersebut, melainkan menggunakan kembali cache yang ada (**`Using cache`**), memangkas waktu build dari 10 menit menjadi 2 detik.

```
       DOCKERFILE INSTRUCTIONS               IMAGE LAYERS (READ-ONLY)
 ┌──────────────────────────────────┐      ┌───────────────────────────┐
 │ FROM node:20-alpine              │ ───> │ Layer 1: Base Alpine OS   │ sha: e7b2...
 ├──────────────────────────────────┤      ├───────────────────────────┤
 │ WORKDIR /app                     │ ───> │ Metadata only (No layer)  │
 ├──────────────────────────────────┤      ├───────────────────────────┤
 │ COPY package*.json ./            │ ───> │ Layer 2: Manifest deps    │ sha: 4c91...
 ├──────────────────────────────────┤      ├───────────────────────────┤
 │ RUN npm ci                       │ ───> │ Layer 3: node_modules/    │ sha: a812...
 ├──────────────────────────────────┤      ├───────────────────────────┤
 │ COPY . .                         │ ───> │ Layer 4: Source Code      │ sha: 1f03... (Invalidated on edit)
 ├──────────────────────────────────┤      ├───────────────────────────┤
 │ CMD ["node", "server.js"]        │ ───> │ Metadata Config (Runtime) │
 └──────────────────────────────────┘      └───────────────────────────┘
```

---

## 4. Why?
1. **Kecepatan Feedback Loop Developer & CI/CD**: Di pipeline CI/CD modern yang berjalan puluhan kali sehari, menunggu proses `npm install` atau `apt-get install` berulang-ulang adalah pemborosan waktu developer dan biaya komputasi runner. Caching layer yang optimal membuat proses build berlangsung instan.
2. **Efisiensi Bandwidth Network & Registry**: Saat melakukan `docker push` atau `docker pull` image versi baru ke container registry, Docker hanya mentransfer layer yang berubah (Layer 4). Layer base OS (Layer 1) dan library (Layer 3) tidak pernah dikirim ulang jika tidak ada perubahan.
3. **Pencegahan Kebocoran Kredensial**: File sensitif (seperti `.env`, `.git`, file RSA key, riwayat bash) yang tidak dikecualikan di `.dockerignore` akan terkirim ke Docker daemon dan tersimpan permanen di riwayat layer image.

---

## 5. What?
### Pembedahan Instruksi Fundamental:

| Pasangan Instruksi | Perbedaan Utama & Rekomendasi |
|---|---|
| **`COPY` vs `ADD`** | `COPY` hanya menyalin file lokal ke container (Best practice). `ADD` memiliki fitur tambahan mengekstrak file `.tar.gz` otomatis dan mendownload URL remote (hindari `ADD` jika hanya untuk menyalin file biasa). |
| **`ARG` vs `ENV`** | `ARG` adalah variabel build-time (hanya ada saat `docker build` dan tidak tersimpan di container runtime). `ENV` adalah variabel environment persisten yang tetap ada saat container dijalankan via `docker run`. |
| **`CMD` vs `ENTRYPOINT`** | `ENTRYPOINT` mendefinisikan binary utama executable tetap. `CMD` mendefinisikan argumen default yang dapat dengan mudah ditimpa (*override*) oleh argumen CLI `docker run`. |
| **Exec Form vs Shell Form** | **Exec Form** (`CMD ["node", "app.js"]`) menjalankan binary langsung sebagai PID 1 (Mendukung SIGTERM graceful shutdown). **Shell Form** (`CMD node app.js`) membungkus proses di dalam `/bin/sh -c`, merusak penanganan sinyal SIGTERM. Selalu gunakan Exec Form! |

---

## 6. How?
### Prinsip Emas Caching Dockerfile:
1. **Urutan Dari yang Paling Jarang Berubah ke Paling Sering Berubah**:
   - Kode aplikasi (`.js`, `.go`, `.py`) berubah di setiap commit developer (Sangat Sering).
   - Daftar dependensi (`package.json`, `go.mod`, `requirements.txt`) hanya berubah seminggu sekali (Jarang).
   - Sistem Operasi (`alpine`, `debian`) hanya di-update sebulan sekali (Sangat Jarang).
2. **Pisahkan Copy Dependensi dari Copy Source Code**:
   ```dockerfile
   # ❌ PENDEKATAN BURUK: Cache selalu rusak setiap baris kode diedit
   COPY . .
   RUN npm ci

   # ✅ PENDEKATAN SEMPURNA: npm ci hanya dijalankan ulang jika package.json berubah!
   COPY package*.json ./
   RUN npm ci
   COPY . .
   ```
3. **Rangkai Perintah Shell dalam Satu Layer `RUN`**:
   Setiap instruksi `RUN` menciptakan satu layer terpisah. Gunakan operator `&&` untuk menggabungkan instalasi paket dan pembersihan cache package manager agar layer tidak membengkak:
   ```dockerfile
   RUN apt-get update && apt-get install -y --no-install-recommends \
       curl \
       ca-certificates \
       && rm -rf /var/lib/apt/lists/*
   ```

---

## 7. Analogy
Bayangkan **Docker Layer Caching** seperti **Menyiapkan Nasi Goreng di Restoran Cepat Saji**:
- **Layer 1 (Base Image)** adalah Panci Wajan dan Kompor Gas (Sudah siap selamanya di dapur).
- **Layer 2 (Dependensi)** adalah Menanak Nasi Putih Matang (Dimasak sekali di pagi hari untuk 100 porsi).
- **Layer 3 (Source Code)** adalah Bumbu Spesial Pilihan Pelanggan (Baru dimasukkan dan dioseng saat pesanan datang).
- Jika setiap kali ada pelanggan baru Anda harus menanam padi dari sawah lalu menanak nasi dari nol (**Pendekatan Buruk**), pelanggan akan menunggu 1 jam. Dengan caching, Anda cukup mengambil nasi yang sudah matang di wajan dan mengoseng bumbunya dalam 30 detik.

---

## 8. Diagram
```
+-----------------------------------------------------------------------------------+
|                     DOCKER BUILD CACHE INVALIDATION TREE                          |
+-----------------------------------------------------------------------------------+

 1. FROM node:20-alpine              ──> [CACHED: Layer A (Base OS)]
              │
              ▼
 2. WORKDIR /app                     ──> [CACHED: Metadata]
              │
              ▼
 3. COPY package*.json ./            ──> Has package.json changed?
              │                            ├── TIDAK ──> [CACHED: Layer B]
              │                            └── YA    ──> [INVALIDATED! Re-compute checksum]
              ▼
 4. RUN npm ci                       ──> Jika step 3 CACHED ──> [CACHED: Layer C (Instant!)]
              │                          Jika step 3 INVALID ─> [RE-RUN npm ci: Takes 45s]
              ▼
 5. COPY . .                         ──> Has any source file changed?
              │                            ├── TIDAK ──> [CACHED: Layer D]
              │                            └── YA    ──> [INVALIDATED! Copy new files]
              ▼
 6. CMD ["node", "server.js"]        ──> [Update Config Metadata]
```

---

## 9. Simple Example: Sintaks `.dockerignore` yang Benar
File `.dockerignore` di root repositori:

```text
# Mengabaikan folder dependensi lokal (akan di-install ulang di container)
node_modules
npm-debug.log

# Mengabaikan metadata Version Control
.git
.gitignore

# Mengabaikan file kredensial & rahasia
.env
.env.*
*.pem
*.key

# Mengabaikan folder build lokal & IDE
dist
coverage
.idea
.vscode
```

---

## 10. Practical Example: Dockerfile Node.js Berstandar Produksi
Contoh `Dockerfile` yang mengoptimalkan layer caching dan keamanan:

```dockerfile
# 1. Base Image Resmi dengan tag semver eksplisit
FROM node:20.11-alpine3.19

# 2. Set environment produksi
ENV NODE_ENV=production

# 3. Tentukan direktori kerja
WORKDIR /usr/src/app

# 4. Salin file manifest dependensi terlebih dahulu (MEMAKSIMALKAN CACHE)
COPY package*.json ./

# 5. Install hanya dependensi produksi secara bersih
RUN npm ci --only=production && npm cache clean --force

# 6. Salin kode aplikasi (Layer ini yang paling sering berubah)
COPY . .

# 7. Gunakan user non-root bawaan Alpine (UID 1000)
USER node

# 8. Dokumentasikan port aplikasi
EXPOSE 3000

# 9. Jalankan aplikasi menggunakan Exec Form (Mendukung SIGTERM)
CMD ["node", "src/index.js"]
```

---

## 11. Real World Example: Mengurangi Durasi Build CI dari 14 Menit ke 18 Detik
Sebuah tim SaaS memiliki 30 engineer yang melakukan push kode puluhan kali setiap hari:
- **Masalah Awal**: Dockerfile menyalin seluruh folder sebelum menginstal dependensi (`COPY . .` lalu `RUN pip install -r requirements.txt`). Setiap kali developer mengubah 1 baris komentar di file Python, pip mengunduh ulang 150 library dari PyPI, memakan waktu build 14 menit per PR.
- **Optimasi Caching**:
  1. Menambahkan `.dockerignore` untuk membuang folder virtualenv lokal dan `.git` (mengurangi build context dari 850MB menjadi 4MB).
  2. Memisahkan `COPY requirements.txt .` lalu `RUN pip install` sebelum `COPY . .`.
- **Hasil**: 95% build CI hanya memakan waktu 18 detik karena layer dependensi selalu berstatus `Using cache`. Produktivitas tim meningkat 300% dan tagihan komputasi CI runner terpangkas 80%.

---

## 12. Trade-offs

| Aspek | Dockerfile Tanpa Optimasi Cache | Dockerfile Caching Terstruktur |
|---|---|---|
| **Waktu Build Harian** | Sangat Lambat (Download dan kompilasi berulang) | Super Cepat (Hitungan detik berkat cache hit) |
| **Ukuran Build Context** | Raksasa (Seluruh node_modules & .git dikirim ke daemon) | Ringan (Hanya file kode esensial via .dockerignore) |
| **Ukuran Image Akhir** | Membengkak (File sampah apt/npm tersimpan di layer) | Ramping (Pembersihan cache dilakukan di layer yang sama) |
| **Disiplin Developer** | Rendah (Tulis sembarangan jalan) | Menuntut pemahaman urutan instruksi |

---

## 13. When To Use
- Wajib diterapkan pada seluruh proyek yang menggunakan pipeline CI/CD (GitHub Actions, GitLab CI).
- Wajib menggunakan `.dockerignore` untuk memastikan rahasia lokal tidak bocor ke container image.

---

## 14. When NOT To Use
- Jangan gunakan `ADD` untuk mengunduh paket dari URL internet di Dockerfile jika paket tersebut bisa diunduh via `curl` dalam satu instruksi `RUN` bersama pembersihannya (karena file hasil `ADD` akan tersimpan permanen di layer terpisah dan memperbesar ukuran image).

---

## 15. Common Mistakes
1. **Menggunakan Shell Form pada `CMD` atau `ENTRYPOINT`**: Menulis `CMD npm start` atau `CMD node app.js`. Shell form akan menjalankan `/bin/sh -c "node app.js"`. Shell Linux tidak meneruskan sinyal `SIGTERM` ke proses node anak, menyebabkan `docker stop` selalu timeout 10 detik dan mematikan aplikasi dengan `SIGKILL`. Selalu gunakan Exec Form: `CMD ["npm", "start"]`.
2. **Membersihkan Cache di Layer Terpisah**: Menjalankan `RUN apt-get update && apt-get install -y nginx` di satu baris, lalu menulis `RUN rm -rf /var/lib/apt/lists/*` di baris berikutnya. Dalam OverlayFS, file yang dibuat di layer sebelumnya tetap memakan ukuran disk di LowerDir! Pembersihan harus digabung dalam satu instruksi `RUN`.
3. **Lupa `.dockerignore`**: Mengirim folder `node_modules` lokal (yang dikompilasi untuk arsitektur macOS/Windows) ke dalam Linux container, menyebabkan error kompatibilitas binary native.

---

## 16. Best Practices
### Must Have
- Pisahkan penyalinan file manifes paket (`package.json`, `pom.xml`, `requirements.txt`) dari penyalinan kode sumber.
- Selalu sediakan file `.dockerignore`.
- Selalu gunakan format JSON Array (*Exec Form*) untuk instruksi `ENTRYPOINT` dan `CMD`.

### Recommended
- Gabungkan instruksi `RUN` pembaruan paket dengan instalasi dan pembersihan cache dalam satu layer menggunakan `&&`.
- Gunakan tag base image semver spesifik (misal `node:20.11-alpine` bukan `node:latest`).

### Advanced
- Manfaatkan Docker BuildKit Cache Mounts (`RUN --mount=type=cache,target=/root/.npm`) untuk mempertahankan cache package manager melintasi berbagai build.

---

## 17. Troubleshooting
- **Masalah**: Docker build selalu mengunduh ulang dependensi padahal tidak ada perubahan pada `package.json`.
  - *Penyebab*: File stempel waktu atau file dinamis di build context menyentuh hash layer sebelum `package.json`.
  - *Solusi*: Periksa file `.dockerignore` dan pastikan tidak ada file yang berubah di atas baris `COPY package*.json ./`.
- **Masalah**: `Sending build context to Docker daemon 1.8GB` memakan waktu 40 detik sebelum build dimulai.
  - *Solusi*: Anda lupa membuat file `.dockerignore`; folder `.git`, file video, atau virtual environment lokal sedang dikirim ke daemon.

---

## 18. Exercise
1. Tulis file `.dockerignore` komprehensif untuk aplikasi Python Flask yang mengabaikan `.git`, `__pycache__`, `.env`, dan folder virtualenv `.venv`.
2. Tulis Dockerfile untuk Go Web Server yang mendemonstrasikan Exec Form vs Shell Form dan buktikan perbedaan penanganan sinyal `SIGTERM` saat dijalankan!

---

## 19. Challenge
Rancang pipeline pengujian validasi layer caching:
- Buat Dockerfile simulasi aplikasi Node.js.
- Jalankan build pertama dan catat waktu kompilasi serta hash layer.
- Ubah 1 baris kode di `src/app.js` tanpa mengubah `package.json`.
- Buktikan bahwa langkah `RUN npm ci` menghasilkan pesan `Using cache` dan build kedua selesai dalam waktu kurang dari 1 detik.

---

## 20. Summary
- Docker image tersusun atas tumpukan layer read-only yang diidentifikasi dengan hash SHA-256.
- Docker build cache bekerja berdasarkan prinsip deterministik: jika input sebuah layer berubah, seluruh layer berikutnya akan di-invalidasi (*cache bust*).
- Menata urutan instruksi dari yang paling jarang berubah ke yang paling sering berubah adalah strategi fundamental mempercepat build.
- Penggunaan `.dockerignore` dan *Exec Form* adalah pilar kepatuhan keamanan dan operasional container modern.
