# Bab 07: Continuous Delivery & Automated Deployment
## Modul 01: Fondasi Continuous Delivery dan Pipeline Otomasi Deployment

---

## SEKSI 01 — IDENTITAS MODUL

* **Kurikulum:** devops-beginner
* **Kategori:** 01-Core-Foundations
* **Kode Modul:** DEV-01-07-01
* **Judul Modul:** Fondasi Continuous Delivery dan Pipeline Otomasi Deployment
* **Prasyarat Pengetahuan:** 
  * Pemahaman Git branching (Trunk-Based Development / GitHub Flow)
  * Pemahaman Linux shell scripting & process management (systemd/curl)
  * Pemahaman dasar CI (Bab 06: Automated Testing & Build Pipeline)
  * Pemahaman konsep containerization dasar (Docker engine & image registry)
* **Target Audiens:** Junior DevOps Engineer, Systems Administrator yang bertransisi ke DevOps, Backend Developer yang mengelola proses rilis aplikasi.
* **Estimasi Waktu Penyelesaian:** 4 - 6 Jam (Termasuk implementasi Hands-on Lab)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik mampu:

1. **Membedakan secara rigid batas arsitektural** antara Continuous Integration (CI), Continuous Delivery (CDel), dan Continuous Deployment (CDep).
2. **Merancang pipeline deployment multi-tahap (multi-stage promotion)** dengan prinsip *Immutable Artifacts* (Build Once, Deploy Anywhere).
3. **Mengonfigurasi dan mengotomasi deployment pipeline** menggunakan GitHub Actions dengan target staging dan production.
4. **Menganalisis dan mengimplementasikan health check otomatis** serta mekanisme fallback/rollback deterministik saat deployment gagal.
5. **Menerapkan metrik DORA (DevOps Research and Assessment)** untuk mengukur stabilitas dan efisiensi delivery cycle.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
[Source Code] 
      │
      ▼
[CI Engine] ──(Unit/Integration Test)──► [Immutable Artifact (Docker Image/Tarball)]
                                                          │
                    ┌─────────────────────────────────────┴─────────────────────────┐
                    ▼                                                               ▼
         [Continuous Delivery]                                           [Continuous Deployment]
                    │                                                               │
        [Deploy ke Staging]                                             [Deploy ke Staging]
                    │                                                               │
        [Automated Verification]                                        [Automated Verification]
                    │                                                               │
         [Manual Approval Gate]                                          [Automated Policy Gate]
                    │                                                               │
        [Deploy ke Production]                                          [Deploy ke Production]
                    │                                                               │
                    └───────────────────────┬───────────────────────────────────────┘
                                            ▼
                          [Deployment Strategy Execution]
                                 ├── Rolling Update
                                 ├── Blue/Green
                                 └── Canary
                                            │
                                            ▼
                          [Health Check & Smoke Test]
                                            │
                           ┌────────────────┴────────────────┐
                           ▼                                 ▼
                     [Status: 200 OK]               [Status: Degraded]
                           │                                 │
                   (Traffic Active)                 (Trigger Rollback)
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Secara historis, deployment perangkat lunak dilakukan secara manual melalui protokol SSH, FTP, atau salin berkas tarball di luar jam kerja (tengah malam atau akhir pekan) untuk meminimalkan dampak downtime kepada pengguna. Pendekatan ini memiliki sejumlah kelemahan fatal:

* **Human Error:** Eksekusi skrip manual rentan terhadap kelupaan konfigurasi environment, migrasi database yang terlewat, atau dependensi sistem operasi yang tidak sinkron.
* **Batch Size yang Terlalu Besar:** Rilis yang dilakukan mingguan atau bulanan menggabungkan puluhan hingga ratusan perubahan kode. Ketika terjadi insiden pasca-rilis, pelacakan akar masalah (*root cause analysis*) menjadi sangat sulit dan memakan waktu berjam-jam.
* **Organizational Friction:** Terciptanya silo antara tim Development yang terdorong merilis fitur secepatnya dan tim Operations yang berorientasi pada stabilitas sistem.

Menurut riset DORA (*DevOps Research and Assessment*), organisasi berkinerja tinggi (*elite performers*) mengotomasi jalur delivery untuk mencapai:
* **Deployment Frequency:** Berlipat ganda dari bulanan menjadi beberapa kali per hari.
* **Lead Time for Changes:** Dari hitungan minggu menjadi di bawah satu jam.
* **Change Failure Rate:** Turun hingga rentang 0-15%.
* **Mean Time to Restore (MTTR):** Pemulihan insiden di bawah satu jam menggunakan otomatisasi rollback.

Otomasi deployment bukan sekadar kemudahan teknis, melainkan fondasi bisnis modern untuk mengurangi risiko operasional, mempercepat validasi hipotesis produk di pasar, dan menjamin sistem dapat dipulihkan secara instan saat terjadi degradasi.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Definisi Formal: CI vs. CDel vs. CDep

* **Continuous Integration (CI):** Praktik penggabungan kode secara berkala ke trunk/mainline, diikuti dengan build otomatis dan eksekusi rangkaian tes (*unit/lint/integration*) untuk mendeteksi konflik sedini mungkin. Luaran (output) akhir CI yang valid adalah **Immutable Artifact** (misal: Docker Image tagged dengan Git SHA).
* **Continuous Delivery (CDel):** Kelanjutan dari CI di mana artefak yang telah teruji secara otomatis di-deploy ke lingkungan pengujian non-produksi (seperti Dev, Staging, QA). Kode selalu berada dalam status *releasable* (siap rilis ke production kapan saja). Namun, promosi artefak ke lingkungan Production membutuhkan **persetujuan manual (*manual approval gate*)** atau keputusan bisnis.
* **Continuous Deployment (CDep):** Evolusi penuh dari Continuous Delivery. Tidak ada intervensi manusia sama sekali. Setiap perubahan kode yang lolos dari seluruh tahapan validasi pipeline CI/CDel akan langsung di-deploy secara otomatis ke lingkungan Production dalam hitungan menit.

### 2. Prinsip Fondasi Deployment Otomatis

* **Immutable Infrastructure / Artifacts:** Artefak yang dibangun di tahap CI tidak boleh dibangun ulang (*rebuilt*) untuk target lingkungan yang berbeda. Satu artefak biner/container image yang sama persis dipromosikan dari Staging hingga ke Production. Perbedaan antar lingkungan hanya diinjeksikan melalui variabel konfigurasi (*Environment Variables* / Secret Stores).
* **Zero Downtime Deployment:** Mekanisme pembaruan aplikasi tanpa memutus koneksi pengguna aktif atau memunculkan status *HTTP 502/503 Service Unavailable*.
* **Idempotency:** Eksekusi skrip deployment yang dijalankan berulang kali dengan input yang sama harus menghasilkan status akhir sistem yang identik, tanpa efek samping yang merusak.
* **Fast Rollback Capability:** Kemampuan mengembalikan versi aplikasi ke status stabil sebelumnya secara otomatis atau satu kali klik dalam hitungan detik.

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

Pipeline Continuous Delivery bekerja sebagai sebuah *state machine* linier atau berorientasi grafik terarah (DAG - *Directed Acyclic Graph*).

### Tahap 1: Artifact Repository Check-in
Begitu CI pipeline berhasil, artefak biner (misal: container image) didorong ke Registry (GitHub Packages, AWS ECR, atau Docker Hub) dan diberi label unik menggunakan Git SHA spesifik:
`ghcr.io/org/service:a1b2c3d`

### Tahap 2: Deployment to Staging
1. CD runner mengambil kredensial staging melalui Secrets Management.
2. Menginstruksikan host target (via SSH, Kubernetes API, atau orchestration agent) untuk menarik image `ghcr.io/org/service:a1b2c3d`.
3. Menjalankan migrasi database yang kompatibel ke belakang (*backward-compatible migration*).
4. Menyalakan container baru dengan konfigurasi Staging.

### Tahap 3: Automated Staging Verification
Sistem mengeksekusi *Smoke Testing* dan *Synthetic End-to-End Testing*:
* Verifikasi endpoint `/healthz` merespons status `200 OK`.
* Verifikasi konektivitas database dan cache.
* Menjalankan request transaksi tiruan untuk memastikan fungsionalitas inti bekerja.

### Tahap 4: Production Approval Gate (Manual vs Automated)
* **CDel:** Pipeline berhenti (*pause*). Notifikasi dikirim ke Slack/Teams/Email. Lead Engineer atau Product Owner mengklik tombol "Approve" di dasbor CI/CD.
* **CDep:** Sistem memeriksa metrik staging (latency, error rate). Jika tidak ada anomali dalam rentang waktu yang ditentukan, pipeline langsung berlanjut ke tahap promosi.

### Tahap 5: Production Deployment & Health Monitoring
Aplikasi di-deploy ke kluster Production menggunakan strategi rilis (misal: Blue/Green atau Rolling Update). Begitu deployment selesai, health check dieksekusi. Jika health check gagal dalam batas waktu (*timeout*), instruksi rollback otomatis dipicu: memutar balik routing jaringan ke versi lama.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. Perbedaan Alur Kerja: CI, CDel, dan CDep

```
KODE SUMBER (Git Commit)
       │
       ▼
 [ CI STAGE ]
 ├── Static Analysis (Linter, SAST)
 ├── Automated Tests (Unit, Mock)
 └── Build Artifact ──► Output: service:v1.2.0 (SHA: 7f8a1c)
                                 │
       ┌─────────────────────────┴────────────────────────┐
       ▼                                                  ▼
 [ CONTINUOUS DELIVERY ]                        [ CONTINUOUS DEPLOYMENT ]
       │                                                  │
       ▼                                                  ▼
 [ Deploy Staging ]                             [ Deploy Staging ]
       │                                                  │
       ▼                                                  ▼
 [ Automated Verification ]                     [ Automated Verification ]
       │                                                  │
       ▼                                                  ▼
 [ Manual Gate / Button ]                       [ Automated Metrics Gate ]
  (Disetujui Manusia)                           (Error Rate < 0.01%?)
       │                                                  │
       ▼                                                  ▼
 [ Deploy Production ]                          [ Deploy Production ]
       │                                                  │
       ▼                                                  ▼
 [ Production Healthcheck ]                     [ Production Healthcheck ]
```

### 2. Strategi Deployment: Blue/Green vs Rolling Update

```
BLUE/GREEN DEPLOYMENT (Peralihan Trafik Seketika)

                    Router / Load Balancer
                             │
            ┌────────────────┴────────────────┐
            │ (Trafik 100%)                   │ (Trafik 0%)
            ▼                                 ▼
   [ Environment BLUE ]              [ Environment GREEN ]
     Versi Eksisting: v1               Versi Baru: v2
   ┌────────────────────┐            ┌────────────────────┐
   │ [Pod 1]    [Pod 2] │            │ [Pod 1]    [Pod 2] │
   └────────────────────┘            └────────────────────┘
                                               ▲
                                               │
                                     Lolos Smoke Test?
                                     Switch Router ke Green!


ROLLING UPDATE (Penggantian Node Bertahap)

Step 1:  [ v1 ]  [ v1 ]  [ v1 ]  (Semua node v1)
Step 2:  [ v2 ]  [ v1 ]  [ v1 ]  (Node 1 diperbarui ke v2, dialihkan trafik jika sehat)
Step 3:  [ v2 ]  [ v2 ]  [ v1 ]  (Node 2 diperbarui ke v2)
Step 4:  [ v2 ]  [ v2 ]  [ v2 ]  (Seluruh armada berhasil diperbarui ke v2)
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah implementasi skrip bash deployment level fundamental (`deploy-simple.sh`). Skrip ini mengilustrasikan mekanisme deployment atomik menggunakan *symlink* Linux, pengujian kesehatan, dan rollback otomatis.

```bash
#!/usr/bin/env bash
set -euo pipefail

# Variabel Konfigurasi
APP_DIR="/var/www/my-app"
RELEASES_DIR="${APP_DIR}/releases"
CURRENT_SYMLINK="${APP_DIR}/current"
TIMESTAMP=$(date +%Y%m%d%H%M%S)
NEW_RELEASE_DIR="${RELEASES_DIR}/${TIMESTAMP}"

echo "=== Memulai Deployment: ${TIMESTAMP} ==="

# 1. Siapkan direktori rilis baru
mkdir -p "${NEW_RELEASE_DIR}"

# 2. Unduh atau ekstrak artefak (Simulasi menggunakan payload sederhana)
echo "Ekstraksi artefak ke ${NEW_RELEASE_DIR}..."
echo "<h1>Aplikasi Versi: ${TIMESTAMP}</h1>" > "${NEW_RELEASE_DIR}/index.html"
echo "OK" > "${NEW_RELEASE_DIR}/healthz"

# 3. Simpan versi aktif sebelumnya untuk kebutuhan rollback
PREVIOUS_RELEASE=""
if [ -L "${CURRENT_SYMLINK}" ]; then
    PREVIOUS_RELEASE=$(readlink -f "${CURRENT_SYMLINK}")
fi

# 4. Atomically switch symlink ke rilis baru
echo "Mengalihkan symlink 'current' ke rilis baru..."
ln -sfn "${NEW_RELEASE_DIR}" "${CURRENT_SYMLINK}.tmp"
mv -Tf "${CURRENT_SYMLINK}.tmp" "${CURRENT_SYMLINK}"

# 5. Eksekusi Health Check / Smoke Test
echo "Menjalankan Health Check..."
HEALTH_CHECK_URL="http://localhost/healthz" # Disesuaikan dengan webserver lokal

# Simulasi verifikasi lokal via file reading
if grep -q "OK" "${CURRENT_SYMLINK}/healthz"; then
    echo "Health Check Sukses! Rilis ${TIMESTAMP} aktif."
    
    # Bersihkan rilis lama, pertahankan 3 rilis terakhir
    cd "${RELEASES_DIR}"
    ls -1dt */ | tail -n +4 | xargs rm -rf
    echo "Pembersihan rilis lama selesai."
else
    echo "ERROR: Health check gagal! Memulai Rollback otomatis..."
    if [ -n "${PREVIOUS_RELEASE}" ] && [ -d "${PREVIOUS_RELEASE}" ]; then
        ln -sfn "${PREVIOUS_RELEASE}" "${CURRENT_SYMLINK}.tmp"
        mv -Tf "${CURRENT_SYMLINK}.tmp" "${CURRENT_SYMLINK}"
        echo "Rollback berhasil dikembalikan ke: ${PREVIOUS_RELEASE}"
    else
        echo "FATAL: Tidak ada rilis sebelumnya yang valid untuk di-rollback!"
    fi
    exit 1
fi
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Skenario: Pipeline GitHub Actions produksi untuk Continuous Delivery aplikasi Node.js/Go berbasis container Docker. Pipeline mencakup tahap *Deploy to Staging*, *Smoke Test*, *Manual Approval Gate* via GitHub Environments, *Deploy to Production*, dan *Automated Verification*.

### File: `.github/workflows/delivery-pipeline.yml`

```yaml
name: Continuous Delivery Pipeline

on:
  push:
    branches:
      - main

permissions:
  contents: read
  packages: write

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  # ==========================================
  # TAHAP 1: BUILD & TEST (CI)
  # ==========================================
  ci-build:
    name: Build & Package Artifact
    runs-on: ubuntu-latest
    outputs:
      artifact_tag: ${{ steps.meta.outputs.version }}
    steps:
      - name: Checkout Source Code
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract Docker Metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=sha,format=long,prefix=

      - name: Build and Push Docker Image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  # ==========================================
  # TAHAP 2: DEPLOY TO STAGING (CDel)
  # ==========================================
  deploy-staging:
    name: Deploy to Staging
    needs: ci-build
    runs-on: ubuntu-latest
    environment:
      name: staging
      url: https://staging.example.com
    steps:
      - name: Deploy to Staging Server via SSH
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.STAGING_HOST }}
          username: ${{ secrets.STAGING_USER }}
          key: ${{ secrets.STAGING_SSH_KEY }}
          script: |
            set -e
            echo "Menarik image: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ needs.ci-build.outputs.artifact_tag }}"
            docker pull ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ needs.ci-build.outputs.artifact_tag }}
            
            # Hentikan container lama, jalankan container baru
            docker stop web-app-staging || true
            docker rm web-app-staging || true
            docker run -d \
              --name web-app-staging \
              -p 8080:8080 \
              -e APP_ENV=staging \
              --restart unless-stopped \
              ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ needs.ci-build.outputs.artifact_tag }}

      - name: Smoke Test Staging Health
        run: |
          echo "Menjalankan verifikasi staging..."
          sleep 5
          STATUS_CODE=$(curl -s -o /dev/null -w "%{http_code}" https://${{ secrets.STAGING_HOST }}:8080/healthz || echo "000")
          if [ "$STATUS_CODE" -ne 200 ]; then
            echo "ERROR: Health check staging gagal dengan status $STATUS_CODE"
            exit 1
          fi
          echo "Staging lolos smoke test."

  # ==========================================
  # TAHAP 3: DEPLOY TO PRODUCTION (Gate Required)
  # ==========================================
  deploy-production:
    name: Deploy to Production
    needs: [ci-build, deploy-staging]
    runs-on: ubuntu-latest
    # Lingkungan 'production' di GitHub Settings harus dikonfigurasi dengan:
    # "Required reviewers" agar menjadi Manual Gate (Continuous Delivery)
    environment:
      name: production
      url: https://app.example.com
    steps:
      - name: Deploy to Production Hosts
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.PRODUCTION_HOST }}
          username: ${{ secrets.PRODUCTION_USER }}
          key: ${{ secrets.PRODUCTION_SSH_KEY }}
          script: |
            set -e
            ARTIFACT="${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ needs.ci-build.outputs.artifact_tag }}"
            echo "Deploying ${ARTIFACT} to Production..."
            
            # Backup identifier container lama untuk potensi rollback
            OLD_CONTAINER_ID=$(docker ps -q -f name=web-app-production)
            
            docker pull ${ARTIFACT}
            
            # Jalankan container baru di port alternatif (Simulasi Blue/Green sederhana)
            docker run -d \
              --name web-app-production-next \
              -p 8081:8080 \
              -e APP_ENV=production \
              ${ARTIFACT}
            
            # Health check internal
            sleep 5
            HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8081/healthz || echo "000")
            
            if [ "$HEALTH" -eq 200 ]; then
              echo "Aplikasi baru sehat. Mengalihkan lalu lintas produksi..."
              docker stop web-app-production || true
              docker rm web-app-production || true
              docker rename web-app-production-next web-app-production
            else
              echo "CRITICAL: Health check gagal pada target rilis! Melakukan abort..."
              docker stop web-app-production-next || true
              docker rm web-app-production-next || true
              exit 1
            fi

      - name: Production Post-Deployment Verification
        run: |
          echo "Verifikasi eksternal domain publik..."
          PROD_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://app.example.com/healthz || echo "000")
          if [ "$PROD_STATUS" -ne 200 ]; then
            echo "WARNING: Domain publik tidak merespons 200 OK. Hubungi On-call Engineer!"
            exit 1
          fi
          echo "Deployment produksi sukses dan terverifikasi secara penuh."
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Aspek | Continuous Delivery (CDel) | Continuous Deployment (CDep) |
| :--- | :--- | :--- |
| **Keterlibatan Manusia** | Butuh persetujuan manual (klik tombol/tiket rilis). | Nol intervensi. Kode merge = Kode live di produksi. |
| **Kecepatan ke Pasar** | Tertunda oleh ketersediaan personil approver. | Sangat cepat (biasanya < 15 menit dari commit). |
| **Kematangan Testing** | Cukup dengan test automation standar; manusia memverifikasi visual/log. | Wajib memiliki test automation tingkat lanjut (Unit, Integration, Contract, Smoke, Canary analysis). |
| **Kesesuaian Regulasi** | Sangat cocok untuk industri finansial/medis (SOX, PCI-DSS, ISO 27001) yang mewajibkan *Separation of Duties*. | Sulit diterapkan tanpa dispensasi audit atau sistem kepatuhan berbasis software (*compliance-as-code*). |

### Perbandingan Strategi Deployment

| Strategi | Kelebihan | Kelemahan / Biaya |
| :--- | :--- | :--- |
| **Recreate (Downtime)** | Paling murah, tidak ada overhead server ganda, tidak ada konflik versi database. | Terjadi downtime (pengguna melihat halaman maintenance/error). |
| **Rolling Update** | Tidak ada downtime total, hemat sumber daya komputasi dibanding Blue/Green. | Versi aplikasi $N$ dan $N+1$ berjalan bersamaan dalam durasi tertentu. Skema database harus kompatibel dua arah. |
| **Blue/Green** | Rollback instan (hanya ubah pointer router/load balancer), isolasi pengujian environment penuh. | Biaya infrastruktur bertambah 2x lipat selama periode rilis; penanganan session state pengguna rumit. |
| **Canary** | Mengisolasi risiko rilis ke sebagian kecil pengguna riil (misal 1% trafik); mitigasi bug kritis sebelum menyebar. | Kompleksitas routing jaringan tinggi (butuh Service Mesh / Advanced API Gateway) dan monitoring metrik telemetri yang canggih. |

---

## SEKSI 11 — BEST PRACTICES

1. **Build Artefak Tepat Satu Kali:** Jangan pernah menjalankan `docker build` atau `npm run build` terpisah untuk Staging dan Production. Bangun satu image di tahap CI, simpan di registry dengan tag Git Commit SHA, lalu sebarkan image tersebut ke seluruh environment.
2. **Pisahkan Konfigurasi dari Artefak (12-Factor App):** Konfigurasi lingkungan (koneksi database, API keys, log level) harus disuplai saat *runtime* melalui variabel lingkungan atau *secrets vault*, bukan di-*hardcode* ke dalam build image.
3. **Endpoint `/healthz` yang Deterministik:** Bedakan antara *liveness probe* (apakah proses aplikasi hidup) dan *readiness probe* (apakah aplikasi siap menerima trafik/koneksi database sudah terbentuk). Deployment pipeline harus memeriksa status kesiapan (*readiness*).
4. **Idempotensi Skrip Deployment:** Pastikan jika pipeline dieksekusi 2 kali berturut-turut pada versi yang sama, hasilnya tidak menimbulkan kegagalan (*crash*) atau menduplikasi entitas infrastruktur.
5. **Database Migration Backward-Compatibility (Expand and Contract Phase):** 
   * **Fase Expand:** Tambahkan kolom baru tanpa menghapus kolom lama.
   * **Fase Deploy:** Rilis aplikasi baru yang menggunakan kolom baru.
   * **Fase Contract:** Hapus kolom lama setelah rilis baru stabil sepenuhnya.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Menjalankan `git pull` Langsung di Server Produksi
* **Anti-Pattern:** Skrip deployment melakukan SSH ke server target lalu mengeksekusi `git pull && npm run build && pm2 restart app`.
* **Dampak:** Proses *compilation* membebani CPU server produksi; jika dependensi *remote* gagal diunduh atau terjadi kompilasi error, aplikasi langsung lumpuh (*outage*).
* **Solusi Benar:** Gunakan *pre-built immutable artifact* (Docker Image atau Binary yang sudah dikompilasi di CI runner). Server produksi hanya bertugas mengunduh dan menjalankan artefak yang telah lolos uji.

### 2. Menggunakan Tag `:latest` pada Container Image
* **Anti-Pattern:** Pipeline CD mendeploy `docker run app:latest`.
* **Dampak:** Sifat non-deterministik. Mustahil mengetahui commit mana yang sedang aktif; mekanisme rollback menjadi tidak dapat diprediksi karena `:latest` menunjuk ke image yang berubah-ubah.
* **Solusi Benar:** Gunakan Git SHA atau versi semantik immutable (contoh: `app:sha-7f8a1c9` atau `app:v1.4.2`).

### 3. Mengabaikan Automated Rollback
* **Anti-Pattern:** Deployment script hanya berhenti dan mengirim notifikasi jika terjadi error tanpa mengembalikan kondisi sistem ke rilis sebelumnya.
* **Dampak:** Layanan berada dalam kondisi pincang (*dangling/broken state*) sampai teknisi merespons secara manual.
* **Solusi Benar:** Implementasikan penanganan kesalahan (trap/try-catch) pada skrip deployment yang secara otomatis mengembalikan konfigurasi load balancer atau symlink ke versi stabil jika status kesehatan tidak tercapai dalam kurun waktu tertentu.

### 4. Coupling Migrasi Database dengan Deployment Aplikasi
* **Anti-Pattern:** Aplikasi baru membutuhkan tabel baru; pipeline menjalankan migrasi destruktif (`DROP COLUMN`), yang langsung merusak aplikasi lama yang masih melayani trafik sebelum proses rollout selesai.
* **Solusi Benar:** Selalu pisahkan rilis skema database dari logika aplikasi, dan terapkan *Non-destructive Forward-compatible Schema Changes*.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Skenario Latihan
Anda diminta membangun mekanisme deployment lokal berbasis bash yang mengimplementasikan metode rilis zero-downtime Blue/Green sederhana menggunakan Docker dan Nginx reverse proxy.

### Langkah-Langkah:

#### Langkah 1: Persiapan Direktori Kerja
Buat direktori proyek lokal dan berpindahlah ke dalamnya:
```bash
mkdir -p ~/cd-lab/{deployments,nginx}
cd ~/cd-lab
```

#### Langkah 2: Konfigurasi Nginx Reverse Proxy
Buat file `nginx/nginx.conf`:
```nginx
events {}
http {
    upstream backend_app {
        # File ini akan dimanipulasi oleh deployment script
        server 127.0.0.1:8081;
    }

    server {
        listen 80;
        location / {
            proxy_pass http://backend_app;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }
}
```

#### Langkah 3: Menulis Script Blue/Green Orchestrator (`deploy-bg.sh`)
Buat script berikut dan berikan hak eksekusi (`chmod +x deploy-bg.sh`):

```bash
#!/usr/bin/env bash
set -e

# Argumen input: versi image yang akan di-deploy
TARGET_VERSION=${1:-"v1"}

echo "--- Memulai Deployment Strategi Blue/Green [Target: ${TARGET_VERSION}] ---"

# Cek container mana yang sedang aktif
if docker ps | grep -q "app-blue"; then
    ACTIVE="blue"
    TARGET="green"
    TARGET_PORT=8082
else
    ACTIVE="green"
    TARGET="blue"
    TARGET_PORT=8081
fi

echo "Environment aktif saat ini: ${ACTIVE}"
echo "Mendeploy versi baru ke environment target: ${TARGET} (Port: ${TARGET_PORT})..."

# 1. Jalankan target environment baru (Gunakan image simulasi hashicorp/http-echo)
docker stop "app-${TARGET}" 2>/dev/null || true
docker rm "app-${TARGET}" 2>/dev/null || true

docker run -d \
  --name "app-${TARGET}" \
  -p "${TARGET_PORT}:5678" \
  hashicorp/http-echo:latest \
  -text="Respon Aplikasi Versi: ${TARGET_VERSION} dari slot ${TARGET}"

# 2. Verifikasi Kesiapan (Health Check)
echo "Menunggu container siap..."
READY=0
for i in {1..5}; do
  if curl -s "http://127.0.0.1:${TARGET_PORT}" | grep -q "Versi: ${TARGET_VERSION}"; then
    READY=1
    break
  fi
  sleep 2
done

if [ $READY -ne 1 ]; then
  echo "CRITICAL: Health check gagal pada slot ${TARGET}. Membatalkan deployment."
  docker stop "app-${TARGET}"
  exit 1
fi

echo "Target ${TARGET} terverifikasi sehat!"

# 3. Alihkan Trafik (Update upstream Nginx)
echo "Mengalihkan lalu lintas Nginx ke slot ${TARGET}..."
cat <<EOF > nginx/upstream.conf
server 127.0.0.1:${TARGET_PORT};
EOF

# Perbarui konfigurasi Nginx dan reload tanpa downtime
sed -i.bak "s/server 127.0.0.1:.*/server host.docker.internal:${TARGET_PORT};/g" nginx/nginx.conf || true

# 4. Hentikan slot lama (Opsional: beri jeda grace period)
echo "Menghentikan environment lama (${ACTIVE})..."
docker stop "app-${ACTIVE}" 2>/dev/null || true

echo "=== Deployment Selesai! Versi ${TARGET_VERSION} sekarang melayani trafik ==="
```

### Tugas Peserta:
1. Jalankan skrip dengan perintah `./deploy-bg.sh v1.0.0`. Verifikasi via `curl http://localhost:8081`.
2. Jalankan pembaruan versi dengan `./deploy-bg.sh v2.0.0`. Amati bagaimana slot berganti dari blue ke green tanpa kegagalan koneksi.
3. Modifikasi script untuk mensimulasikan kegagalan health check (misal sengaja memasukkan port yang salah) dan buktikan bahwa environment lama tidak dimatikan jika environment baru bermasalah.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

Jawablah pertanyaan berikut untuk menguji pemahaman Anda:

1. **Apa perbedaan mendasar antara Continuous Delivery dan Continuous Deployment?**
   * A. Continuous Delivery tidak melibatkan pengujian otomatis, sedangkan Continuous Deployment melibatkan pengujian otomatis.
   * B. Continuous Delivery mewajibkan persetujuan manual (approval gate) untuk rilis ke produksi, sedangkan Continuous Deployment rilis ke produksi secara otomatis begitu lolos pipeline.
   * C. Continuous Delivery hanya berlaku untuk aplikasi monolitik, sedangkan Continuous Deployment khusus untuk microservices.
   * D. Continuous Delivery tidak memerlukan containerization, Continuous Deployment wajib Docker.

2. **Mengapa praktik pembangunan artefak (misal: Docker build) secara berulang di setiap environment (Dev, Staging, Prod) dianggap sebagai anti-pattern berbahaya?**
   * A. Memakan ruang penyimpanan registry.
   * B. Mengabaikan prinsip *Immutable Artifacts*; ada risiko dependensi eksternal terunduh pada versi berbeda sehingga artefak di produksi tidak identik dengan yang telah diuji di staging.
   * C. Menghambat proses debugging variabel lingkungan.
   * D. Memperlambat koneksi database production.

3. **Pada strategi Blue/Green Deployment, apa langkah mitigasi yang diambil jika rilis versi baru di lingkungan Green mengalami lonjakan error 500 sesaat setelah switch over trafik dilakukan?**
   * A. Langsung mengkompilasi kode perbaikan di server green.
   * B. Mematikan seluruh load balancer untuk perbaikan darurat.
   * C. Mengembalikan routing load balancer seketika ke lingkungan Blue yang masih aktif berjalan.
   * D. Menjalankan database restore dari snapshot kemarin malam.

4. **Metrik DORA yang mengukur durasi waktu yang dibutuhkan dari commit kode pertama kali hingga kode tersebut berjalan aktif menghasilkan nilai di server produksi disebut:**
   * A. Mean Time to Recovery (MTTR)
   * B. Lead Time for Changes
   * C. Change Failure Rate
   * D. Deployment Frequency

5. **Apa fungsi utama dari symlink switching yang bersifat atomik (seperti `mv -Tf link.tmp link`) dalam deployment berbasis file sistem?**
   * A. Mencegah request HTTP dari klien mengakses aplikasi dalam status berkas yang terpotong/setengah tersalin (*file corruption state*).
   * B. Mengurangi pemakaian ruang hard disk server.
   * C. Mengenkripsi berkas kode aplikasi secara otomatis.
   * D. Menghapus ketergantungan terhadap webserver Nginx atau Apache.

### Kunci Jawaban & Pembahasan:
* **1: B** — Batas formal Continuous Delivery vs Deployment berada pada keberadaan *approval gate* manual sebelum menyentuh produksi.
* **2: B** — Build sekali, deploy ke mana saja (*Build Once, Deploy Anywhere*) menjamin integritas perangkat lunak bahwa yang dirilis ke pengguna adalah artefak yang lolos seluruh tes sebelumnya.
* **3: C** — Keunggulan utama Blue/Green adalah rollback instan (berorde detik) hanya dengan memutar balik router trafik ke slot Blue.
* **4: B** — Lead Time for Changes mengukur efisiensi pipeline delivery dari tahap penulisan kode hingga operasional di tangan pengguna.
* **5: A** — Pengalihan pointer atomik memastikan tidak ada jeda di mana klien membaca aplikasi saat proses I/O penulisan direktori belum selesai.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Buku Referensi Industri:**
  * *Continuous Delivery: Reliable Software Releases through Build, Test, and Deployment Automation* oleh Jez Humble & David Farley (Addison-Wesley Professional).
  * *Accelerate: The Science of Lean Software and DevOps* oleh Nicole Forsgren, Jez Humble, & Gene Kim (IT Revolution Press).
* **Standar Arsitektur:**
  * The Twelve-Factor App: Konfigurasi dan Statelesness ([12factor.net](https://12factor.net/))
  * DORA Research: *DevOps Research and Assessment Program Metrics Guide* ([cloud.google.com/devops](https://cloud.google.com/devops)).
* **Dokumentasi Resmi Pipeline:**
  * GitHub Actions: Managing Environments and Deployment Protection Rules ([docs.github.com](https://docs.github.com/en/actions/deployment)).
  * GitLab CI/CD: Environments and Deployments Documentation.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

* **Continuous Delivery (CDel)** memastikan setiap perubahan kode valid selalu berada dalam kondisi siap rilis (*deployable state*), dengan keputusan akhir menuju produksi berada di tangan manusia (*manual gate*).
* **Continuous Deployment (CDep)** menghilangkan gate manual, mengandalkan kekuatan sistem pengujian otomatis dan telemetri observabilitas untuk merilis kode langsung ke produksi tanpa jeda.
* Prinsip **Immutable Artifacts** adalah hukum utama CD: kompilasi kode dan pemaketan dependensi dilakukan sekali saja di tahap awal pipeline; promosi antar-lingkungan hanya membedakan parameter konfigurasi runtime.
* Strategi deployment modern mencakup:
  * **Rolling Update:** Pembaruan instans bertahap (hemat biaya, kompleksitas migrasi database tinggi).
  * **Blue/Green:** Dua lingkungan identik, rollback instan via router (biaya infrastruktur tinggi).
  * **Canary:** Rilis bertahap berdasarkan persentase porsi trafik pengguna (paling aman, dependensi metrik tinggi).
* **Automated Rollback** dan health check `/healthz` terisolasi bukan fitur opsional, melainkan prasyarat mutlak untuk membangun sistem delivery modern yang tangguh.

---

## SEKSI 17 — GLOSARIUM

* **Continuous Delivery (CDel):** Rangkaian proses otomatisasi pembaruan perangkat lunak hingga lingkungan pra-produksi yang siap didorong ke produksi kapan saja via satu persetujuan manual.
* **Continuous Deployment (CDep):** Proses otomatisasi rilis perangkat lunak end-to-end langsung menuju lingkungan produksi tanpa intervensi manual.
* **Immutable Artifact:** Paket perangkat lunak (biner, arsip, container image) yang tidak dapat dimodifikasi setelah proses kompilasi selesai.
* **Manual Approval Gate:** Titik perhentian pada pipeline CI/CD yang membutuhkan tindakan otorisasi dari individu atau tim yang berwenang sebelum eksekusi dilanjutkan.
* **Smoke Testing:** Kumpulan tes fungsionalitas dasar dan krusial pasca-deployment untuk memastikan aplikasi mampu menyala dan tidak mengalami *crash* mendasar.
* **Health Check Probe:** Endpoint khusus sistem (umumnya `/healthz` atau `/ready`) yang mengembalikan kode status 200 OK jika proses internal dan ketergantungan dependensinya sehat.
* **Rollback:** Operasi memutar balik status sistem yang terdegradasi ke versi stabil sebelumnya yang telah teruji.
* **Blue/Green Deployment:** Pola deployment yang menyediakan dua arsitektur identik berdampingan, di mana satu melayani trafik live dan yang lain menerima pembaruan versi baru.
* **Canary Deployment:** Teknik rilis yang mengalirkan sebagian kecil trafik produksi ke versi aplikasi baru untuk memverifikasi performa sebelum dilakukan peluncuran global.
* **Idempotent Deployment:** Kemampuan skrip atau instruksi delivery untuk dieksekusi berulang kali tanpa mengubah hasil akhir status infrastruktur aplikasi di luar kondisi yang diharapkan.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Poin Penekanan:**
  * Mahasiswa sering kali bingung membedakan antara Continuous Delivery dan Continuous Deployment. Pastikan untuk mempertegas bahwa perbedaannya ada pada **otomasi pelepasan ke produksi (*human trigger vs pipeline trigger*)**, bukan pada kualitas testing atau jenis kodenya.
  * Tekankan bahaya melakukan kompilasi di server target (`git pull && npm run build`). Tunjukkan analogi bahwa pabrik mobil tidak merakit mesin langsung di jalan raya.
* **Potensi Hambatan Mahasiswa:**
  * Pemahaman konektivitas jaringan pada Hands-on Lab: Pastikan peserta memahami bagaimana Nginx me-reverse proxy ke port localhost yang berbeda (`8081` vs `8082`).
  * Hambatan izin akses (permission denied) pada skrip Bash: Ingatkan mahasiswa untuk mengeksekusi `chmod +x <nama-skrip>.sh`.
* **Saran Pengajaran:**
  * Lakukan demo langsung di mana instruktur sengaja memicu deployment gagal (misal: memberikan nilai exit 1 pada skrip health check) untuk memperlihatkan bagaimana skrip otomatis membatalkan alihan trafik dan mencegah sistem down.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi:** 1.0.0
* **Tanggal:** 2024-03-30
* **Penulis/Arsitek:** Senior Technical Curriculum Architect
* **Catatan Perubahan:**
  * Rilis inisial materi Fondasi Continuous Delivery dan Deployment Pipelines.
  * Penambahan skrip bash symlink deployment atomik.
  * Penyusunan contoh praktis GitHub Actions delivery pipeline terintegrasi.
  * Penyediaan latihan mandiri strategi Blue/Green menggunakan Nginx dan Docker.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** `06-02: Automated Testing, Static Analysis, and Build Pipeline`
* **Modul Saat Ini:** `07-01: Fondasi Continuous Delivery dan Pipeline Otomasi Deployment`
* **Modul Berikutnya:** `07-02: Deployment Strategies Deep Dive (Canary, Blue-Green, and Rolling Updates Architecture)`