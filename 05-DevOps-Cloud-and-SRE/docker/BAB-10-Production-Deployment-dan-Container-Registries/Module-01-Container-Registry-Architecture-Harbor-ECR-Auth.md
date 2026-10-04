# Module 01: Arsitektur Container Registry (Harbor, ECR, GHCR), Autentikasi, dan Tagging Strategy

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
1. Memahami arsitektur OCI Distribution Specification yang menjadi standar kerja Container Registry modern (Docker Hub, AWS ECR, GitHub Container Registry/GHCR, CNCF Harbor).
2. Menguasai alur kerja autentikasi `docker login`, pertukaran Bearer Token (OAuth2 / Token Authentication), dan mekanisme **Docker Credential Helpers** (`secretservice`, `pass`, `osxkeychain`, `wincred`).
3. Menerapkan strategi penamaan dan versioning image yang deterministik: **Semantic Versioning (SemVer)**, **Git Commit SHA**, dan bahaya anti-pattern tag `:latest`.
4. Memahami konsep **Image Immutability** pada private registry enterprise untuk mencegah supply-chain tampering.
5. Mengonfigurasi self-hosted enterprise registry (CNCF Harbor) dengan fitur role-based access control (RBAC) dan security scanning integration.

---

## 2. Prerequisite
- Memahami konsep Image Layer dan Manifest List ([BAB 03 Module 01](../BAB-03-Dockerfile-Engineering-dan-Image-Optimization/Module-01-Anatomi-Image-Layer-Caching-Strategy-dan-Instruksi-Fundamental.md) dan [BAB 08 Module 02](../BAB-08-Advanced-BuildKit-dan-Multi-Architecture/Module-02-Multi-Architecture-Cross-Compilation-AMD64-ARM64-Buildx.md)).
- Pemahaman dasar protokol HTTP REST API dan Bearer Token authentication.
- Pemahaman version control Git (commit SHA, Git tags).

---

## 3. Concept
Sebuah **Container Registry** adalah layanan penyimpanan dan distribusi stateless untuk image kontainer berbasis Open Container Initiative (OCI) Distribution Specification. Registry tidak menyimpan satu file `.tar` raksasa untuk setiap image; sebaliknya, registry menyimpan:
1. **Blob Store**: Kumpulan layer terkompresi (tar.gz/zstd) yang diidentifikasi secara unik oleh SHA256 digest-nya (Content-Addressable Storage). Jika 10 image berbeda menggunakan base image `alpine:3.19`, registry hanya menyimpan blob Alpine tersebut satu kali!
2. **Manifest Store**: Dokumen JSON yang memetakan tag human-readable (misal `v1.2.0`) ke digest layer blob yang membentuk image tersebut.

Ketika Anda menjalankan `docker push`, engine hanya mengunggah layer-layer baru yang belum ada di server (deduplikasi storage). Ketika Anda menjalankan `docker pull`, engine memeriksa layer lokal dan hanya mengunduh blob yang belum dimiliki.

---

## 4. Why?
Mengapa pemahaman registry dan tagging sangat penting di level production?
1. **Integritas Rilis (Release Reproducibility)**: Mengandalkan tag yang bisa ditimpa (seperti `:latest`) adalah resep bencana di mana server A dan server B menjalankan kode yang berbeda meskipun menarik tag yang sama.
2. **Keamanan Kredensial (Credential Theft Mitigation)**: Menyimpan password plaintext di `~/.docker/config.json` di mesin developer atau CI runner adalah kerentanan keamanan fatal. Penggunaan credential helper adalah keharusan.
3. **Kepatuhan Regulasi & Audit (Enterprise Compliance)**: Perusahaan perbankan dan fintech diwajibkan menggunakan registry privat (seperti Harbor atau AWS ECR) dengan audit log, retention policy, dan immutable tags.

---

## 5. What?
### Lanskap Container Registry:

| Registry | Model Hosting | Fitur Unggulan | Use Case Utama |
|---|---|---|---|
| **Docker Hub** | Cloud Managed | Terbesar di dunia, default engine, official library images. | Open-source public distribution, base images. |
| **AWS ECR** | Cloud Managed (AWS) | Terintegrasi IAM native, scanning AWS Inspector, cross-region replication. | Workload AWS (EKS, ECS, Fargate). |
| **GHCR (GitHub Packages)** | Cloud Managed | Integrasi mulus dengan GitHub Actions dan fine-grained Personal Access Tokens. | CI/CD internal GitHub, tim open-source. |
| **CNCF Harbor** | Self-Hosted / On-Premise | Open-source, image immutability, vulnerability gate (Trivy), Cosign signature enforcement, RBAC. | Enterprise on-premise data center, private cloud kedaulatan data. |

---

## 6. How? Alur Autentikasi dan Push OCI Registry

```text
  [ Docker Client CLI ]                                 [ OCI Container Registry ]
            |                                                       |
            | 1. POST /v2/myorg/api/blobs/uploads/                  |
            |------------------------------------------------------>|
            | 2. 401 Unauthorized (Www-Authenticate: Bearer...)    |
            |<------------------------------------------------------|
            |                                                       |
            | 3. GET /token?service=registry&scope=repository:push  |
            |    (Mengirim HTTP Basic Auth atau Credential Helper)  |
            |------------------------------------------------------>|
            | 4. 200 OK (Returns JWT Bearer Access Token)           |
            |<------------------------------------------------------|
            |                                                       |
            | 5. HEAD /v2/myorg/api/blobs/<layer-sha256>            |
            |    (Cek apakah layer sudah ada di registry?)          |
            |------------------------------------------------------>|
            | 6. 200 OK (Layer exists! Skip upload / Deduplication) |
            |<------------------------------------------------------|
            |                                                       |
            | 7. PUT /v2/myorg/api/manifests/v1.0.0                 |
            |    (Kirim OCI Manifest JSON bertanda tangan)          |
            |------------------------------------------------------>|
            | 8. 201 Created (Image Manifest Committed)             |
            |<------------------------------------------------------|
```

---

## 7. Analogy
Bayangkan registry kontainer seperti sistem repositori buku perpustakaan digital:
- Bab-bab buku (layers) disimpan di ruang arsip pusat. Jika sepuluh buku sains yang berbeda menggunakan pengantar matematika dasar yang sama (base layer), perpustakaan hanya mencetak bab pengantar matematika tersebut satu kali.
- Sampul buku dan daftar isi (Manifest) disimpan terpisah, mencatat bab-bab mana saja yang harus disatukan.
- Nomor ISBN yang tidak boleh diganti (Immutable Tag) menjamin bahwa buku versi cetakan tertentu tidak akan pernah diubah isinya secara diam-diam oleh orang lain.

---

## 8. Diagram: Credential Helper vs Plaintext Storage

```text
Insecure (Default Plaintext di ~/.docker/config.json):
+--------------------------------------------------------------------+
| {                                                                  |
|   "auths": {                                                       |
|     "https://index.docker.io/v1/": {                               |
|       "auth": "dXNlcm5hbWU6cGFzc3dvcmQ="  <-- BASE64 PLAINTEXT!  |
|     }                                                              |
|   }                                                                |
| }                                                                  |
| (Malware atau script apa pun di host bisa membaca password Anda!)   |
+--------------------------------------------------------------------+

Secure (Menggunakan Docker Credential Helper):
+--------------------------------------------------------------------+
| ~/.docker/config.json                                              |
| {                                                                  |
|   "credsStore": "secretservice"  (Linux Secret Service / Keyring)  |
|   // atau "osxkeychain" (macOS) / "wincred" (Windows Vault)        |
| }                                                                  |
|                                                                    |
| Token terenkripsi kuat menggunakan hardware/OS master key!        |
+--------------------------------------------------------------------+
```

---

## 9. Simple Example: Autentikasi CLI Docker yang Aman

```bash
# 1. Login menggunakan token/secret via standard input (mencegah terekam di riwayat shell bash)
echo "$GITHUB_TOKEN" | docker login ghcr.io -u octocat --password-stdin

# 2. Login ke AWS ECR menggunakan AWS CLI v2
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com

# 3. Logout dan bersihkan sesi
docker logout ghcr.io
```

---

## 10. Practical Example: Skema Tagging Produksi yang Ideal

Strategi tagging profesional mewajibkan kombinasi **Triple Tagging**:

```bash
# Tentukan variabel rilis dari Git
GIT_COMMIT_SHA=$(git rev-parse --short HEAD)   # cth: a1b2c3d
APP_VERSION="v2.4.1"                          # SemVer
REGISTRY_URL="ghcr.io/mycompany/fintech-api"

# 1. Tag Spesifik Rilis SemVer (Imutable - tidak boleh diganti)
docker tag fintech-api:local ${REGISTRY_URL}:${APP_VERSION}

# 2. Tag Git Commit SHA (Untuk penelusuran audit forensik kode sumber)
docker tag fintech-api:local ${REGISTRY_URL}:sha-${GIT_COMMIT_SHA}

# 3. Tag Jalur Rilis Mayor (Opsional untuk consumer floating track)
docker tag fintech-api:local ${REGISTRY_URL}:v2

# 4. Push seluruh tag ke registry
docker push ${REGISTRY_URL}:${APP_VERSION}
docker push ${REGISTRY_URL}:sha-${GIT_COMMIT_SHA}
docker push ${REGISTRY_URL}:v2
```

---

## 11. Real World Example: CNCF Harbor Enterprise Policy Enforcement
Di lingkungan perbankan atau healthcare, CNCF Harbor dikonfigurasi dengan aturan ketat:
1. **Tag Immutability Rule**: Tag dengan regex `v*.*.*` dikunci secara permanen. Jika ada developer atau pipeline CI yang mencoba menjalankan `docker push myapp:v1.0.0` untuk kedua kalinya, registry menolak dengan error `412 Precondition Failed: Tag is immutable`.
2. **Vulnerability Gate**: Harbor memblokir penarikan image (`docker pull`) jika pemindai Trivy menemukan kerentanan tingkat **Critical** dengan skor CVSS > 9.0.
3. **Cosign / Notary Signature**: Hanya image yang ditandatangani oleh private key DevOps Lead yang diizinkan untuk di-deploy ke cluster production.

---

## 12. Trade-offs: Self-Hosted Harbor vs Managed Cloud Registry

| Dimensi | CNCF Harbor (Self-Hosted) | Managed Registry (AWS ECR / GHCR) |
|---|---|---|
| **Data Governance** | 100% On-Premise / Local storage sovereignty | Disimpan di cloud publik provider |
| **Biaya Operasional (Ops)** | Butuh tim sysadmin untuk maintenance VM, backup Postgres & S3 | 0 maintenance, bayar sesuai penyimpanan GB |
| **Fitur Tata Kelola** | Sangat lengkap (Quota, Webhook, Robot Accounts, Policy Gate) | Bergantung fitur cloud provider |
| **Konektivitas Jaringan** | Sangat cepat di LAN lokal / on-premise | Bergantung bandwidth internet keluar |

---

## 13. When To Use
- Terapkan **Git SHA tagging** (`sha-a1b2c3d`) pada setiap commit di pipeline CI/CD branch staging.
- Terapkan **Semantic Versioning** (`v1.2.3`) saat rilis produksi dirilis secara resmi via Git Tag / GitHub Release.
- Terapkan **Credential Helpers** di semua workstation developer dan build server permanen.

---

## 14. When NOT To Use
- **JANGAN PERNAH gunakan tag `:latest` di production manifest** (Kubernetes deployment, Compose file, Helm charts). Tag `:latest` bersifat mutable, tidak mengindikasikan versi kode sumber, dan merusak mekanisme rollback.
- Jangan menyimpan file kredensial plain text di image atau git commit.

---

## 15. Common Mistakes
1. **Menjalankan `docker login -u user -p password` langsung di shell**: Perintah ini menyimpan password plaintext di riwayat history terminal (`~/.bash_history`) dan terlihat oleh proses lain via `ps aux`.
2. **Deploy menggunakan tag `latest`**:
   Node A menarik `myapp:latest` pada pukul 10:00 (versi baru), Node B me-restart container `myapp:latest` pada pukul 09:00 (versi lama dari cache). Hasilnya terjadi inkonsistensi perilaku aplikasi antar server.
3. **Tidak memanfaatkan Layer Deduplication**: Mengubah base image dari debian ke alpine bolak-balik antar microservice membuat registry menyimpan ratusan gigabyte layer terduplikasi.

---

## 16. Best Practices
### Must Have
- Selalu gunakan `--password-stdin` saat melakukan `docker login` di automation script atau pipeline CI.
- Aktifkan fitur **Tag Immutability** di container registry produksi untuk mencegah image rilis ditimpa secara sengaja maupun tidak sengaja.
- Pasang credential helper (`pass` di Linux, `osxkeychain` di macOS, `wincred` di Windows).

### Recommended
- Buat Robot Accounts khusus di Harbor / ECR dengan hak akses terbatas (`pull-only` untuk server staging/prod, `push-only` untuk CI runner).
- Terapkan **Lifecycle Policy / Retention Policy** untuk membersihkan image bertag non-rilis (seperti `pr-*` atau branch build yang lebih lama dari 14 hari).

### Advanced
- Terapkan penandatanganan image kriptografis (**Image Signing**) menggunakan Sigstore **Cosign** sebelum mendorong image ke registry, dan verifikasi tandatangan via admission controller.

---

## 17. Troubleshooting Guide
### Problem 1: `401 Unauthorized` atau `403 Forbidden` saat `docker push`
- **Penyebab**: Token login kedaluwarsa, atau kredensial akun tidak memiliki izin *Write/Push* ke repositori target.
- **Diagnosa**:
  ```bash
  docker login <registry-domain>
  # Uji koneksi manifest
  curl -v -H "Authorization: Bearer <TOKEN>" https://<registry-domain>/v2/
  ```
- **Solusi**: Periksa apakah user/robot account memiliki hak akses repository `push`, atau generate Personal Access Token (PAT) baru dengan scope `write:packages`.

### Problem 2: `412 Precondition Failed` saat push ke Harbor
- **Penyebab**: Tag yang Anda coba push sudah ada di registry dan repository tersebut mengaktifkan aturan **Tag Immutability**.
- **Solusi**: Naikkan patch version (misal dari `v1.2.0` ke `v1.2.1`) atau sertakan commit SHA unik.

---

## 18. Exercises
### Level: Easy
1. Periksa file konfigurasi Docker Anda di `~/.docker/config.json` (atau `%USERPROFILE%\.docker\config.json` di Windows). Apakah terdapat field `credsStore` atau `auths`?
2. Tag salah satu image lokal Anda dengan dua format: SemVer (`v1.0.0`) dan Git SHA (`sha-manual-test`).

### Level: Medium
1. Konfigurasikan Docker credential helper di sistem Anda (misal `wincred` atau `pass`).
2. Lakukan `docker login` dan periksa kembali isi `config.json` untuk memastikan password Anda tidak lagi tersimpan sebagai string plaintext base64.

### Level: Hard
1. Buat local private registry menggunakan image resmi `registry:2`:
   `docker run -d -p 5001:5000 --name local-registry registry:2`
2. Push image lokal ke `localhost:5001/myapp:v1.0.0`.
3. Gunakan `curl` untuk query catalog endpoint: `http://localhost:5001/v2/_catalog` dan manifest endpoint: `http://localhost:5001/v2/myapp/manifests/v1.0.0`.

---

## 19. Challenge
Rancang arsitektur supply chain security container untuk pipeline perbankan:
- CI/CD men-trigger build dan scan otomatis dengan Trivy.
- Hanya jika scan 0 Critical dan 0 High vulnerability, image diizinkan di-push ke Harbor.
- Image ditandatangani secara digital dengan `cosign`.
- Server Kubernetes hanya boleh me-running image yang digest-nya terverifikasi oleh signature publik devops.
Tuliskan diagram alur dan langkah-langkah implementasinya secara detail.

---

## 20. Summary
- **OCI Registry** memisahkan layer biner (content-addressable blob store) dengan dokumen JSON manifest rilis.
- Autentikasi registry menggunakan protokol berbasis OAuth2 / JWT Bearer Tokens.
- Selalu hindari penyimpanan kredensial plaintext dengan memanfaatkan **Docker Credential Helpers**.
- Jangan pernah menggunakan tag mutable `:latest` di production; terapkan **Semantic Versioning** dan **Git Commit SHA** dengan aturan **Tag Immutability**.
