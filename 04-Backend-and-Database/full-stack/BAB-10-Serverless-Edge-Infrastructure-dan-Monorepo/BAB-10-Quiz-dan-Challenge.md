---
[⬅️ Module 02: Turborepo & Docker GitOps](./Module-02-Turborepo-Docker-Containerization-dan-GitOps.md) | [📋 Silabus Induk](../README.md) | [🏆 CAPSTONE PROJECT: Enterprise Collaborative Workspace SaaS ➡️](../CAPSTONE-PROJECT-Enterprise-Collaborative-Workspace-SaaS.md)
---

# BAB 10: Evaluasi Pembelajaran — Quiz, Challenge, & Knowledge Check

## 1. Uji Pemahaman Mandiri (Quiz)

### A. Soal Tingkat Dasar (Basic Questions)
1. **Apa perbedaan mendasar antara model isolasi komputasi Micro-VM (AWS Firecracker) dengan Google V8 Isolates (Cloudflare Workers / Edge Runtime)?**
2. **Mengapa Edge Runtime memiliki latensi Cold Start yang jauh lebih singkat (< 5ms) dibandingkan runtime Node.js Serverless tradisional?**
3. **Bagaimana fitur `output: "standalone"` pada Next.js memangkas ukuran image Docker dari 1.2GB menjadi di bawah 100MB?**
4. **Apa fungsi dari atribut `dependsOn: ["^build"]` di file konfigurasi `turbo.json` dan apa arti dari tanda sisipan `^` (caret)?**
5. **Mengapa menjalankan container Docker aplikasi web menggunakan user `root` (UID 0) merupakan pelanggaran keamanan kritis di lingkungan produksi?**

---

### B. Soal Tingkat Menengah (Intermediate Questions)
6. **Jelaskan bagaimana Turborepo menghitung *Content-Aware Hash* untuk menentukan apakah suatu paket memenuhi kriteria *Cache Hit (FULL TURBO)* atau harus dikompilasi ulang!**
7. **Bagaimana teknik Remote Caching pada Turborepo menghemat waktu kompilasi tim pengembang dan memangkas biaya komputasi runner CI/CD?**
8. **Jelaskan batasan-batasan teknis (*Constraints*) apa saja yang dimiliki oleh Edge Runtime yang membuatnya tidak cocok untuk semua jenis beban kerja backend!**
9. **Bagaimana mekanisme *Blue-Green Deployment* menjamin ketersediaan sistem 100% (*Zero Downtime*) saat terjadi pembaruan versi container di cluster Kubernetes?**
10. **Jelaskan bagaimana Edge Middleware dapat melakukan A/B Testing tanpa menimbulkan efek visual berkedip (*flickering / layout shift*) pada browser pengguna!**

---

### C. Soal Berbasis Skenario Arsitektur (Scenario-Based Questions)
11. **Skenario Kasus — Monorepo Dependency Drift & Atomic Commits**:
    Sebuah tim memiliki dua aplikasi web (`apps/storefront` dan `apps/dashboard`) yang sama-sama bergantung pada skema database (`packages/database`). Tim backend menambahkan kolom baru pada skema produk. Jelaskan bagaimana arsitektur monorepo dengan pnpm workspaces dan Turborepo memungkinkan pembaruan skema database dan penyesuaian kedua aplikasi dilakukan dalam satu buah *Atomic Commit* tunggal tanpa risiko inkonsistensi versi!
12. **Skenario Kasus — Image Docker Rusak Pasca-Deploy Standalone**:
    Seorang engineer mengaktifkan `output: "standalone"` pada Next.js dan berhasil membuat image Docker berukuran 85MB. Namun, saat dideploy ke AWS ECS, halaman web tampil berantakan tanpa file CSS dan seluruh gambar menghasilkan HTTP 404. Analisis baris perintah apa yang terlewat di Dockerfile dan jelaskan mengapa Next.js standalone tidak menyertakan aset tersebut secara otomatis!
13. **Skenario Kasus — Multi-Region Edge Failover saat Cloud Outage**:
    Data center utama aplikasi Anda di Virginia (`us-east-1`) mengalami pemadaman listrik total. Rancang arsitektur routing di Cloudflare Edge Workers yang secara otomatis mendeteksi anomali (misalnya jika origin mengembalikan status 502/503/504) dalam waktu kurang dari 50 milidetik dan mengalihkan seluruh lalu lintas pengguna ke backend cadangan di Frankfurt (`eu-central-1`) tanpa satupun request pengguna yang terputus!

---

## 2. Chapter Challenge: High-Velocity Monorepo & Standalone Container Pipeline

### Deskripsi Tantangan
Anda diminta merancang arsitektur monorepo tingkat enterprise yang siap di-deploy secara otomatis ke cluster Docker/Kubernetes dengan efisiensi maksimal.

### Kebutuhan & Spesifikasi:
1. **Workspace Hierarchy**:
   - `apps/web`: Next.js 14 App Router.
   - `packages/ui`: Pustaka komponen UI bersama berbasis Tailwind CSS.
   - `packages/database`: Skema Drizzle ORM.
2. **Turborepo Pipeline Configuration**:
   - Susun `turbo.json` dengan task `build`, `lint`, dan `test`.
   - Pastikan task `build` pada `apps/web` hanya dijalankan setelah `packages/ui` dan `packages/database` selesai dikompilasi.
3. **Production Multi-Stage Dockerfile**:
   - Terapkan 4 tahap build: `base` -> `deps` -> `builder` -> `runner`.
   - Aktifkan `output: "standalone"`.
   - Salin `.next/standalone`, `.next/static`, dan `public` dengan kepemilikan user unprivileged `nextjs:nodejs` (UID 1001).
4. **GitOps CI Workflow**:
   - Buat workflow GitHub Actions yang memanfaatkan Turborepo Remote Caching untuk memvalidasi linting dan pengujian unit pada setiap Pull Request.

---

## 3. Knowledge Check & Mastery Checklist

### Yang Wajib Anda Pahami:
- [ ] Perbedaan fundamental antara komputasi serverless berbasis Micro-VM dan Edge V8 Isolates.
- [ ] Konsep monorepo modern, dependensi topologis, dan efisiensi Turborepo remote cache.
- [ ] Cara kerja Next.js Standalone tracing dalam mengeliminasi beban `node_modules` di container Docker.
- [ ] Prinsip keamanan container (non-root execution, minimal base image Alpine).

### Yang Tidak Perlu Anda Hafal di Luar Kepala:
- Perintah Docker CLI internal tingkat rendah (`docker system prune -a`, inspect layer hashes)—cukup pahami deklarasi Dockerfile multi-stage.
- Skema JSON schema Turborepo baris-per-baris—dapat divalidasi via `$schema` URL di IDE.

### Yang Harus Bisa Anda Lakukan:
- [ ] Mengonfigurasi monorepo menggunakan pnpm workspaces dan Turborepo.
- [ ] Menulis Dockerfile multi-stage untuk Next.js dengan mode standalone.
- [ ] Mengonfigurasi Edge Function untuk routing dan personalisasi Geo-IP.
- [ ] Mengintegrasikan pipeline CI/CD GitHub Actions dengan remote caching.

---

## 4. Ringkasan Bab (Chapter Summary)
Bab 10 menutup sepuluh pilar kurikulum Full-Stack Developer Mastery dengan pondasi infrastruktur modern:
1. **Serverless & Edge Computing (V8 Isolates)** mengeliminasi belenggu *Cold Start* dan membawa eksekusi komputasi ke ratusan Point of Presence (PoP) di seluruh dunia.
2. **Turborepo Monorepo Architecture** menyatukan kode frontend, backend, dan pustaka bersama ke dalam satu alur kerja terpadu yang super cepat berkat *Content-Aware Remote Caching*.
3. **Multi-Stage Docker & Standalone Output** menyusutkan ukuran artefak produksi hingga lebih dari 90%, mengamankan lingkungan container, dan memastikan proses rilis GitOps berjalan dalam hitungan detik.

Selamat! Anda telah menyelesaikan seluruh 10 Bab kurikulum Full-Stack Developer Mastery! Kini, saatnya membuktikan seluruh kompetensi teknis Anda dalam proyek puncak: **🏆 CAPSTONE PROJECT: Enterprise Collaborative Workspace & Marketplace (SaaS)**!

---
[⬅️ Module 02: Turborepo & Docker GitOps](./Module-02-Turborepo-Docker-Containerization-dan-GitOps.md) | [📋 Silabus Induk](../README.md) | [🏆 CAPSTONE PROJECT: Enterprise Collaborative Workspace SaaS ➡️](../CAPSTONE-PROJECT-Enterprise-Collaborative-Workspace-SaaS.md)
---
