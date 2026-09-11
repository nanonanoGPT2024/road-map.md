---
[⬅️ Module 01: Serverless & Edge Workers](./Module-01-Serverless-Cloudflare-Edge-Workers-Cold-Starts.md) | [📋 Silabus Induk](../README.md) | [BAB 10 Quiz & Challenge ➡️](./BAB-10-Quiz-dan-Challenge.md)
---

# Module 02: Full-Stack Monorepos (Turborepo), Dockerizing Next.js, & Multi-Stage Deployment GitOps

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Merancang dan menyusun arsitektur **Full-Stack Monorepo** menggunakan **Turborepo** dan pnpm/npm workspaces: memisahkan aplikasi (`apps/web`, `apps/mobile`) dan paket bersama (`packages/ui`, `packages/database`, `packages/auth`, `packages/config`).
- Menguasai **Turborepo Task Graph & Remote Caching**: memahami bagaimana hash artefak dihitung berdasarkan konten file (*content-aware hashing*) dan bagaimana remote caching menghemat hingga 90% waktu kompilasi CI/CD.
- Mengimplementasikan teknik **Multi-Stage Dockerfile** dengan fitur **Next.js Standalone Output (`output: 'standalone'`)** untuk memangkas ukuran image container dari 1.2 GB menjadi di bawah 100 MB.
- Menerapkan prinsip keamanan container: menjalankan container dengan *unprivileged non-root user*, membuang dependensi development, dan meminimalisasi layer attack surface.
- Membangun pipeline **GitOps Continuous Integration / Continuous Deployment (CI/CD)** menggunakan GitHub Actions dengan validasi linting otomatis, pengujian paralel, dan deployment bertahap (*Blue-Green / Canary Releases*).

---

## 2. Prerequisite
- Memahami dasar-dasar Docker (Images, Containers, Dockerfile, Layer Caching).
- Memahami konsep NPM / pnpm workspaces dan file `package.json`.
- Memahami alur kerja Git (Branches, Pull Requests, Commits).

---

## 3. Concept
Ketika sebuah organisasi teknologi berkembang, arsitektur *Multi-Repo* (satu repositori terpisah untuk frontend, satu untuk backend, satu untuk skema database) sering kali memicu mimpi buruk koordinasi:
- Mengubah skema database di Repo A mengharuskan update tipe di Repo B, lalu membuat pull request terpisah di Repo C.
- Sinkronisasi versi pustaka antarmuka (*Design System UI*) menjadi rapuh dan rawan *version drift*.

**Full-Stack Monorepo dengan Turborepo** menyatukan seluruh aplikasi dan dependensi bersama ke dalam **satu repositori Git tunggal** tanpa mengorbankan kecepatan:

```
my-enterprise-monorepo/
├── apps/
│   ├── web/               # Next.js 14 Web Application
│   └── admin/             # Vite / Remix Backoffice Portal
│
├── packages/
│   ├── ui/                # Shared Tailwind / Radix Component Library
│   ├── database/          # Drizzle ORM Schema & Migrations
│   ├── auth/              # Shared Auth.js Configuration
│   └── tsconfig/          # Shared TypeScript Configuration
│
└── turbo.json             # Turborepo Build Dependency Pipeline Graph
```

Turborepo menganalisis grafik dependensi (*Dependency Graph*) antar-paket: jika Anda hanya mengubah kode di `apps/web`, Turborepo **tidak akan membuang waktu mengompilasi ulang** paket lain yang tidak terpengaruh!

---

## 4. Why? (Mengapa Membutuhkan Turborepo & Standalone Docker?)
1. **Pemberantasan Waktu Build yang Terbuang (Remote Caching)**:
   - Jika rekan tim Anda atau server CI/CD sudah pernah mengompilasi paket `packages/ui` dengan hash commit yang sama, komputer Anda cukup mengunduh hasil kompilasi dari cache dalam **50 milidetik** alih-alih mengompilasi ulang dari nol selama 5 menit (*Turbo Cache Hit*).
2. **Kutukan Ukuran Node_Modules Docker**:
   - Jika Anda menyalin folder `node_modules` monorepo biasa ke dalam Docker image, ukurannya bisa mencapai **1.5 Gigabyte**. Mengunduh dan men-deploy image raksasa ini ke AWS ECS / Kubernetes memakan waktu belasan menit.
   - Dengan fitur **Next.js Standalone Output**, Next.js secara otomatis melacak (*dependency tracing*) hanya file `.js` dan pustaka yang benar-benar dieksekusi di runtime, memangkas ukuran image menjadi **hanya ~80 Megabyte**!

---

## 5. What? (Konfigurasi Pipeline Turborepo: turbo.json)

```json
{
  "$schema": "https://turbo.build/schema.json",
  "globalDependencies": [".env"],
  "tasks": {
    "build": {
      "dependsOn": ["^build"],
      "outputs": [".next/**", "!.next/cache/**", "dist/**"]
    },
    "lint": {
      "dependsOn": ["^build"]
    },
    "test": {
      "dependsOn": ["^build"],
      "inputs": ["src/**/*.tsx", "src/**/*.ts", "tests/**/*.ts"]
    },
    "dev": {
      "cache": false,
      "persistent": true
    }
  }
}
```
- `"dependsOn": ["^build"]`: Tanda sisipan `^` (topologis) memerintahkan Turborepo untuk membangun seluruh dependensi hulu (*upstream packages*) terlebih dahulu sebelum membangun aplikasi hilir.

---

## 6. How? (Implementasi Multi-Stage Dockerfile untuk Next.js Standalone)

### 1. Mengaktifkan Mode Standalone di Next.js (next.config.mjs)
```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  // Wajib aktif untuk deployment Docker berukuran mini!
  output: "standalone",
};

export default nextConfig;
```

### 2. Multi-Stage Dockerfile Tingkat Produksi (Dockerfile)
```dockerfile
# ==============================================================================
# TAHAP 1: BASE IMAGE
# ==============================================================================
FROM node:20-alpine AS base
WORKDIR /app
RUN apk add --no-cache libc6-compat

# ==============================================================================
# TAHAP 2: DEPENDENCIES INSTALLER
# ==============================================================================
FROM base AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --frozen-lockfile

# ==============================================================================
# TAHAP 3: SOURCE BUILDER
# ==============================================================================
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Matikan telemetri Next.js saat build untuk privasi & kecepatan
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production

RUN npm run build

# ==============================================================================
# TAHAP 4: PRODUCTION RUNNER (SUPER RINGAN & AMAN)
# ==============================================================================
FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Buat grup dan pengguna non-root demi keamanan (Prinsip Least Privilege)
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Salin aset publik statis
COPY --from=builder /app/public ./public

# Berikan hak kepemilikan folder cache ke user nextjs
RUN mkdir .next
RUN chown nextjs:nodejs .next

# Salin bundle standalone yang sudah di-trace secara otomatis oleh Next.js
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

# Gunakan pengguna non-root (Bukan root!)
USER nextjs

EXPOSE 3000

# Jalankan server mandiri tanpa perlu npm run start!
CMD ["node", "server.js"]
```

---

## 7. Analogy
Bayangkan sebuah pabrik perakitan mobil modern:
- **Pendekatan Multi-Repo Tradisional**: Divisi mesin berada di pulau A, divisi bodi di pulau B, divisi interior di pulau C. Setiap kali ada perubahan baut, manajer harus mengirim surat resmi melalui pos, menunggu rapat koordinasi berhari-hari, dan sering kali saat mobil dirakit di pabrik akhir, pintu mobil tidak muat karena beda ukuran 2 sentimeter (*Version Drift Nightmare*).
- **Turborepo Monorepo**: Seluruh divisi bekerja di dalam satu gedung mega-pabrik yang sama (*Single Monorepo*). Bagian terbaiknya: pabrik memiliki sistem ban berjalan pintar (*Remote Cache*). Jika desain mesin tidak berubah dari minggu lalu, robot perakitan langsung mengambil mesin yang sudah jadi dari gudang dalam 1 detik tanpa perlu mencetak ulang besi bajanya dari awal!

---

## 8. Diagram Turborepo Build Dependency Graph & Caching

```
+-----------------------------------------------------------------------------------+
| TURBOREPO PIPELINE DEPENDENCY GRAPH                                               |
|                                                                                   |
|           [ packages/config ]         [ packages/database ]                       |
|                   \                           /                                   |
|                    v                         v                                    |
|              [ packages/ui (Design System Library) ]                              |
|                            /         \                                            |
|                           v           v                                           |
|                  [ apps/web ]       [ apps/admin ]                                |
+-----------------------------------------------------------------------------------+
                                        |
                 (Eksekusi `turbo run build` di CI/CD)
                                        v
+-----------------------------------------------------------------------------------+
| REMOTE CACHE EVALUATION ENGINE                                                    |
|                                                                                   |
|  - `packages/config`   ---> Hash: `a9b1` ---> CACHE HIT [FULL TURBO] (40ms)       |
|  - `packages/database` ---> Hash: `c3d4` ---> CACHE HIT [FULL TURBO] (35ms)       |
|  - `packages/ui`       ---> Hash: `e5f6` ---> CACHE HIT [FULL TURBO] (50ms)       |
|  - `apps/web`          ---> Hash: `7g8h` ---> MODIFIED! Menjalankan build nyata... |
|                                                                                   |
|  ⏱️ Total Waktu Build Monorepo Terpangkas dari 8 Menit menjadi 45 Detik!          |
+-----------------------------------------------------------------------------------+
```

---

## 9. Simple Example: Workflow GitHub Actions CI/CD (.github/workflows/ci.yml)

```yaml
name: Full-Stack CI/CD Pipeline

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Repositori
        uses: actions/checkout@v4

      - name: Setup Node.js Runtime
        uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: "npm"

      - name: Install Dependencies
        run: npm ci

      - name: Run Turborepo Linter & Tests
        run: npx turbo run lint test --parallel

      - name: Build All Packages with Remote Cache
        run: npx turbo run build
        env:
          TURBO_TOKEN: ${{ secrets.TURBO_TOKEN }}
          TURBO_TEAM: ${{ secrets.TURBO_TEAM }}
```

---

## 10. Practical Example: Blue-Green Deployment Zero-Downtime di Kubernetes / Docker
Saat memperbarui versi aplikasi produksi dari `v1.0.0` (Blue) ke `v2.0.0` (Green):

```
                        [ NGINX REVERSE PROXY / INGRESS ]
                                        |
                 (Awal: Mengarahkan 100% Traffic ke BLUE)
                                   /         \
                                  v           v
                    [ PODS BLUE (v1.0.0) ]   [ PODS GREEN (v2.0.0) ]
                    (Melayani Pengguna)      (Deployment Baru Sedang Health-Check)
                                  |                     |
                                  |          (Health Check Green Lolos 100%!)
                                  |                     |
                                  +---------------------+
                                        |
                 (Beralih Seketika: 100% Traffic ke GREEN!)
                                        v
                            [ PODS GREEN (v2.0.0) ]
                            (Zero-Downtime Tercapai!)
```
Jika terjadi anomali pada Green, proxy cukup dibelokkan kembali ke Blue dalam 1 detik (*Instant Rollback*).

---

## 11. Real-World Example: Optimasi Image Docker Next.js Enterprise
Perbandingan ukuran image Docker nyata pada aplikasi Next.js komersial:

| Komponen di dalam Image | Dockerfile Standar Naif | Dockerfile Multi-Stage Standalone |
| :--- | :--- | :--- |
| `node_modules` utuh | ~950 MB | Dieliminasi (Hanya standalone tracing ~45MB) |
| Source code & Git history | ~180 MB | Dibuang (Hanya bundle `.next/standalone`) |
| Compiler & DevTools (TypeScript, Webpack) | ~200 MB | Dibuang di tahap builder |
| **Total Ukuran Image Akhir** | **~1.33 GB** | **~88 MB (Penyusutan > 93%!)** |
| **Waktu Tarik Image di Server K8s** | ~45 detik | **~2.1 detik (Deploy Cepat!)** |

---

## 12. Trade-offs: Monorepo vs Polyrepo

| Parameter | Monorepo (Turborepo) | Polyrepo (Repositori Terpisah) |
| :--- | :--- | :--- |
| **Refactoring Lintas Paket** | **Sangat Mudah (Atomic Single Commit)** | Sulit (Butuh koordinasi banyak repo) |
| **Konsistensi Dependensi** | **Terjamin (Single lockfile)** | Rawan konflik versi pustaka |
| **Kecepatan Git Clone Awal** | Cenderung lebih lambat (Ukuran repo besar) | **Cepat (Repo kecil terisolasi)** |
| **Manajemen Hak Akses Repositori**| Terpusat (Semua developer melihat monorepo)| Fleksibel per tim |
| **Kebutuhan Tooling Build** | Wajib Turborepo / Nx | Script npm sederhana cukup |

---

## 13. When To Use Turborepo & Standalone Docker
- Tim Anda membangun aplikasi web yang berbagi model data, skema database, atau komponen UI yang sama.
- Anda ingin men-deploy Next.js ke infrastruktur container kustom sendiri (AWS ECS, Google Cloud Run, Kubernetes, Coolify, Dokku).
- Anda ingin menghemat ratusan jam waktu kompilasi CI/CD setiap bulannya menggunakan remote caching.

---

## 14. When NOT To Use
- Proyek website sederhana satu halaman (*Single Landing Page*) yang tidak memiliki dependensi bersama.
- Organisasi besar dengan ratusan tim independen yang regulasinya melarang pengembang frontend melihat kode repositori backend (*strict code compartmentalization*).

---

## 15. Common Mistakes
1. **Menjalankan Container Docker sebagai `root`**:
   - Membiarkan default user Linux `root` (UID 0) berjalan di dalam container. Jika aplikasi memiliki celah Remote Code Execution (RCE), penyerang memperoleh hak akses superuser ke host kernel server!
   - *Solusi*: Selalu deklarasikan `USER nextjs` (UID 1001).
2. **Lupa Menyalin Folder `.next/static` ke Runner**:
   - Mengira bahwa `.next/standalone` sudah mencakup seluruh aset CSS dan JS statis. Akibatnya, saat container dijalankan, halaman web muncul tanpa styling (CSS 404 Not Found)!
   - *Solusi*: Wajib sertakan `COPY --from=builder /app/.next/static ./.next/static`.
3. **Mengabaikan `.dockerignore`**:
   - Membiarkan folder `node_modules` lokal berukuran gigabyte atau file rahasia `.env.local` ter-copy ke dalam build context Docker.

---

## 16. Best Practices

### Must Have
- Sertakan file `.dockerignore` lengkap (abaikan `node_modules`, `.git`, `.next`, `.env*`).
- Aktifkan `output: "standalone"` pada `next.config.js` untuk meminimalisasi ukuran container.
- Buat pengguna non-root unprivileged di Dockerfile.

### Recommended
- Konfigurasikan Turborepo Remote Caching di Vercel atau self-hosted cache server (seperti `ducktors/turborepo-remote-cache`).
- Gunakan lockfile deterministik (`package-lock.json` atau `pnpm-lock.yaml`) dengan perintah `npm ci` di Dockerfile untuk menghindari perubahan versi dependensi tak terduga.

### Advanced
- Implementasikan *Canary Deployment* otomatis: kirimkan 5% traffic ke versi Docker baru selama 10 menit. Jika error rate < 0.01%, naikkan traffic secara bertahap hingga 100%.

### Avoid
- Jangan menyimpan secret credentials (API Keys, Database Password) di dalam instruksi `ENV` atau `ARG` Dockerfile karena nilai tersebut akan tersimpan permanen di dalam riwayat layer image.

---

## 17. Troubleshooting Guide

| Gejala Masalah | Kemungkinan Akar Masalah | Solusi |
| :--- | :--- | :--- |
| CSS dan gambar statis menghasilkan HTTP 404 saat Next.js dijalankan di Docker. | Folder `.next/static` atau `public` lupa disalin ke container runner. | Pastikan kedua perintah `COPY` untuk `.next/static` dan `public` ada di Dockerfile runner stage. |
| Turborepo selalu menjalankan kompilasi ulang (*Cache Miss*) padahal kode tidak berubah. | File `.env` atau timestamp file berubah dan dimasukkan ke dalam hash calculation. | Periksa konfigurasi `inputs` dan `globalDependencies` pada `turbo.json`. |
| Error `EACCES: permission denied` saat server Next.js mencoba membuat cache. | User `nextjs` non-root tidak memiliki hak tulis ke folder `.next`. | Jalankan `RUN chown -R nextjs:nodejs .next` sebelum beralih ke `USER nextjs`. |

---

## 18. Exercise
- **Easy**: Buat file `.dockerignore` yang mengabaikan `node_modules`, `.next`, dan file environment lokal.
- **Medium**: Tulis file konfigurasi `turbo.json` yang mendefinisikan pipeline tugas `build`, `lint`, dan `test` dengan dependensi topologis.
- **Hard**: Rancang script simulasi build graph dependency resolver: terima daftar paket monorepo dan ketergantungannya, lalu buat urutan eksekusi tugas yang optimal secara paralel.

---

## 19. Challenge
Rancang arsitektur monorepo enterprise skala penuh di Turborepo yang memuat 3 aplikasi (`web`, `docs`, `admin`) dan 4 paket internal (`ui`, `db`, `auth`, `utils`). Buat skrip pipeline CI/CD GitHub Actions lengkap yang mampu membedakan paket mana saja yang mengalami perubahan kode (*Affected Packages*), menjalankan pengujian paralel hanya untuk paket yang berubah, dan membangun image Docker Next.js Standalone dengan bobot < 100MB secara otomatis.

---

## 20. Summary
- **Turborepo Monorepo** menghadirkan koordinasi kode tingkat tinggi dan menghilangkan friksi sinkronisasi dependensi di tim rekayasa full-stack.
- **Content-Aware Remote Caching** mengembalikan waktu produktif developer dengan memastikan tidak ada kode yang pernah dikompilasi dua kali.
- **Multi-Stage Docker & Next.js Standalone** menyempurnakan siklus deployment dengan memangkas bobot image hingga 90%, mempercepat proses deployment GitOps, dan memperkokoh postur keamanan sistem produksi.

---

## Hands-on Practice: Simulasi Turborepo Build Graph & Remote Cache Resolver
Jalankan simulator resolver dependensi monorepo, kalkulasi hash konten, dan deteksi cache hit mandiri:

```bash
node Full-Stack/BAB-10-Serverless-Edge-Infrastructure-dan-Monorepo/hands-on/m02/turborepo_monorepo_pipeline_sim.js
```

---
[⬅️ Module 01: Serverless & Edge Workers](./Module-01-Serverless-Cloudflare-Edge-Workers-Cold-Starts.md) | [📋 Silabus Induk](../README.md) | [BAB 10 Quiz & Challenge ➡️](./BAB-10-Quiz-dan-Challenge.md)
---
