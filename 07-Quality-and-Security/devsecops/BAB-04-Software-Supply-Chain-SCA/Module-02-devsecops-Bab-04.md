# BAB 04: Software Supply Chain & Software Composition Analysis (SCA)
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Mendesain Arsitektur Supply Chain Security Berstandar SLSA Level 3/4**: Membangun pipeline build yang *hermetic*, *isolated*, dan menghasilkan *verifiable provenance* yang kebal terhadap manipulasi runner/infrastruktur CI/CD.
2. **Mengimplementasikan End-to-End Cryptographic Attestation**: Mengintegrasikan framework **Sigstore** (*Cosign, Fulcio, Rekor*) dan **in-toto** untuk menandatangani metadata build, Software Bill of Materials (SBOM), dan hasil scan kerentanan secara *keyless* via OIDC identity provider.
3. **Membangun Dynamic Admission Control di Kubernetes**: Menerapkan kebijakan deployment berbasis *cryptographic verification* menggunakan **Kyverno** atau **Cosign Admission Controller**, memblokir image tanpa tanda tangan valid, SBOM tidak lengkap, atau CVE kritis yang tidak memiliki justifikasi VEX.
4. **Mengelola Lifecycle Vulnerability Exploitability eXchange (VEX)**: Mereduksi false-positive fatigue pada tim platform dan security engineer dengan mengotomatisasi generasi dokumen OpenVEX/CSAF ke dalam OCI registry.
5. **Memitigasi Serangan Lanjutan Supply Chain**: Mengonfigurasi arsitektur pertahanan terhadap *Dependency Confusion*, *Typosquatting*, *Transitive Dependency Hijacking*, dan *Compromised Build Cache Poisoning*.

---

### 2. Prerequisite

Peserta harus memiliki pemahaman dan penguasaan teknis pada domain berikut:
- **Container Internals & OCI Spec**: Struktur OCI Image Manifests, Descriptor, Blob Layers, dan OCI Image Index.
- **Kriptografi Terapan & PKI**: Prinsip Public-Key Cryptography, format x509, hash SHA-256/SHA-512, Certificate Transparency logs (RFC 6962), dan OpenID Connect (OIDC) core flows.
- **Kubernetes Architecture**: Mekanisme kerja `kube-apiserver`, Dynamic Admission Control (`ValidatingWebhookConfiguration`), Resource Mutations, dan Custom Resource Definitions (CRDs).
- **CI/CD Platform Mechanics**: GitHub Actions / GitLab CI Runner runtime, ephemeral virtual environments, runner token isolation, dan environment secrets lifecycle.
- **Tools Minimal yang Terpasang di Workspace**:
  - `docker` (v24.0+) atau `podman` (v4.5+)
  - `cosign` (v2.2+)
  - `syft` (v0.90+) & `grype` (v0.65+)
  - `kubectl` (v1.27+)
  - `kind` (v0.20+)
  - `jq` (v1.6+)

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Anatomi Software Supply Chain Attack Vectors
Keamanan supply chain software tidak lagi berfokus hanya pada kode sumber (*first-party code*), melainkan mencakup integritas seluruh rantai transformasi: dari penulisan kode oleh developer, resolusi dependency (*third-party*), lingkungan eksekusi pipeline build, *intermediate artifacts*, registry penyimpanan, hingga admission controller di production runtime.

Serangan modern menyasar titik-titik transformasi tersebut:
1. **Source Compromise**: Pembajakan akun committer, manipulasi commit history (unsigned git commits), compromised pull requests.
2. **Build Integrity Compromise**: Runner caching poisoning, tampering binary compiler, peretasan dependensi transitif saat resolusi package dinamis.
3. **Distribution Integrity Compromise**: Man-in-the-Middle (MitM) saat push artifact, manipulasi image tag di registry (mutability exploitation), *registry credential exfiltration*.

```
+--------------------------------------------------------------------------------------------------+
|                                    SLSA THREAT MATRIX MAPPING                                    |
+--------------------------------------------------------------------------------------------------+
|   Source Code                 Build System                 Artifact Storage           Runtime    |
|                                                                                                  |
| [ Dev Machine ]               [ CI Runner ]                 [ OCI Registry ]         [ Cluster ] |
|       |                             |                              |                      |      |
|       |  (A) Threat:                |  (C) Threat:                 |  (E) Threat:         |      |
|       |  Compromised Commit         |  Compromised Runner          |  Registry Tampering  |      |
|       v                             v                              v                      v      |
|  [ Git Repo ]  ================> [ Build ]  =================> [ Container ]  =======> [ Deploy ]|
|       ^                             ^                              ^                      ^      |
|       |  (B) Threat:                |  (D) Threat:                 |  (F) Threat:         |      |
|       |  Bypassed PR / Review       |  Dependency Confusion        |  Unsigned Pull       |      |
|                                        (Remote Poisoning)                                        |
+--------------------------------------------------------------------------------------------------+
```

#### B. SLSA (Supply-chain Levels for Software Artifacts) Framework
SLSA (dibaca *salsa*) adalah framework keamanan terstandarisasi untuk menjamin integritas software artifacts. Kita berfokus pada SLSA v1.0 yang berpusat pada dua aspek utama: **Build Integrity** dan **Source Integrity**.

*   **SLSA Level 1**: Scripted build process + Provenance generation (identitas artifact, build platform, dan source commit terdokumentasi).
*   **SLSA Level 2**: Hosted build service (misal: GitHub Actions, GitLab CI managed runners) yang menandatangani provenance secara otomatis; mencegah tampering lokal developer.
*   **SLSA Level 3**: Hardened build platform. Pipeline build harus:
    *   **Isolated**: Runner berjalan di container/VM ephemeral yang dihancurkan setelah eksekusi.
    *   **Hermetic (Ideal)**: Tidak ada akses network dinamis saat proses kompilasi binary berlangsung (seluruh dependencies telah di-*lock* dan di-verifikasi hash kriptografisnya).
    *   **Non-falsifiable Provenance**: Kunci kriptografi penandatangan metadata berada di luar kontrol runner worker (dikelola oleh OIDC identity provider eksternal atau KMS berisolasi).

#### C. Arsitektur Kriptografi Sigstore: Keyless Signing Ecosystem
Model tradisional berbasis *Long-Lived Private Key* memiliki kelemahan struktural enterprise: risiko kebocoran private key, kompleksitas rotasi sertifikat, dan overhead manajemen secret. Ekosistem Sigstore menyelesaikan hal ini melalui integrasi tiga komponen utama:

1.  **Fulcio (Ephemeral CA)**: 
    *   Fulcio menerbitkan sertifikat x509 berumur sangat pendek (biasanya valid selama 10 menit).
    *   Sertifikat ini tidak diterbitkan berbasis private key persisten, melainkan berbasis **OIDC Identity Token** milik entitas yang mengeksekusi build (misal: `https://github.com/org/repo/.github/workflows/deploy.yml@refs/heads/main`).
    *   Sertifikat memetakan *identity string* ke ephemeral public key yang dibuat langsung oleh Cosign di memori CI runner.
2.  **Rekor (Transparency Log)**:
    *   Log terdistribusi yang append-only dan diamankan secara kriptografis menggunakan **Merkle Tree**.
    *   Setiap kali signature dan attestation dibuat, entry bukti penandatanganan (timestamp, public key/cert, payload hash) dikirim ke Rekor.
    *   Rekor mengembalikan **Signed Entry Timestamp (SET)**. Sekalipun ephemeral cert dari Fulcio kedaluwarsa setelah 10 menit, SET membuktikan secara kriptografis bahwa signature dibuat saat sertifikat masih valid dan diverifikasi oleh public transparency log.
3.  **Cosign (CLI & Verifier)**:
    *   Orchestrator client yang mengeksekusi pembentukan ephemeral keypair, request token OIDC, query sertifikat ke Fulcio, push signature/attestation ke OCI registry (menggunakan format OCI artifacts), dan menuliskan log entry ke Rekor.

```
+---------------------------------------------------------------------------------------------------+
|                                  SIGSTORE KEYLESS INTERNAL FLOW                                   |
+---------------------------------------------------------------------------------------------------+
|                                                                                                   |
|  [ CI Runner ]               [ OIDC Provider ]         [ Fulcio CA ]             [ Rekor Log ]    |
|   (Ephemeral)                 (GitHub / IdP)           (Short-lived)             (Merkle Tree)    |
|        |                             |                       |                         |          |
|   1. Generate Ephemeral              |                       |                         |          |
|      Keypair (In-Memory)             |                       |                         |          |
|        |                             |                       |                         |          |
|   2. Request OIDC Identity Token     |                       |                         |          |
|        |---------------------------->|                       |                         |          |
|        |<----------------------------|                       |                         |          |
|        |   (JWT containing Job ID)   |                       |                         |          |
|        |                                                     |                         |          |
|   3. Request Certificate (Send PubKey + OIDC Token)          |                         |          |
|        |---------------------------------------------------->|                         |          |
|        |                                                     |-- Validasi Signature    |          |
|        |                                                     |   dan Issuer OIDC Token |          |
|        |<----------------------------------------------------|                         |          |
|        |   (x509 Short-Lived Certificate, 10 min validity)   |                         |          |
|        |                                                                               |          |
|   4. Tandatangani OCI Artifact Hash (Local Sign)                                       |          |
|        |                                                                               |          |
|   5. Kirim Bukti Transaksi (Entry) ke Rekor Log                                        |          |
|        |------------------------------------------------------------------------------>|          |
|        |                                                     |--- Masukkan ke Merkle   |          |
|        |                                                     |    Tree, return Root    |          |
|        |<------------------------------------------------------------------------------|          |
|        |   (SET: Signed Entry Timestamp)                                               |          |
|        |                                                                                          |
|   6. Simpan Signature Payload, x509 Cert, & SET ke OCI Registry (Adjacent Image Tag/Artifact)    |
|                                                                                                   |
+---------------------------------------------------------------------------------------------------+
```

#### D. Transitive Dependency Graph Resolution & Attack Mechanics
Software Composition Analysis (SCA) tradisional sering gagal mendeteksi kerentanan yang bersarang di kedalaman pohon dependensi (*transitive dependencies*).

1.  **Dependency Confusion**:
    *   Sebuah aplikasi internal memanggil package `@company-internal/auth-lib` versi `1.2.0`.
    *   Jika package manager (npm, pip, maven) tidak dikonfigurasi dengan *strict namespace scoping* atau *registry fallback order* yang tepat, penyerang dapat mempublikasikan package dengan nama identik `@company-internal/auth-lib` versi `99.0.0` di public registry (seperti npmjs.org atau PyPI).
    *   Build runner akan secara default menarik package dari public registry karena version number yang lebih tinggi.
2.  **Typosquatting & Hijacking**:
    *   Registrasi package dengan nama mirip (misal: `cross-env` vs `crossenv`).
    *   Maintainer account takeover via credential stuffing atau pengabaian repository (*dormant package takeovers*).
3.  **Deep Transitive Injection**:
    *   Dependency Root -> Direct Dependency A -> Sub-Dependency B -> Compromised Dependency C.
    *   Solusi arsitektural: Wajibkan **Cryptographic Lockfiles** (`package-lock.json`, `poetry.lock`, `go.sum`) dan jalankan resolusi dependensi menggunakan mirror/proxy internal (seperti Harbor atau JFrog Artifactory) yang menerapkan quarantine engine sebelum dipromosikan ke main repository.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Legacy SCA) | Enterprise Supply Chain Security (Modern Architecture) |
| :--- | :--- | :--- |
| **Fokus Keamanan** | Pengecekan manifest statis (`pom.xml`, `package.json`) di repositori. | Menjamin integritas seluruh lifecycle: source, build engine, artifact, dan runtime admission. |
| **Validasi Integritas** | Validasi Image Tag sederhana (e.g. `:v1.0.0`) yang mutable dan rawan di-overwrite. | Validasi Cryptographic Digest (`sha256:...`) yang di-sign secara immutable dan terikat ke log transparansi. |
| **Trust Model** | "Percaya pada Developer & Network CI/CD internal". | **Zero Trust Pipeline**: "Asumsikan environment runner compromised; artifact harus membuktikan validitasnya sendiri via attestation". |
| **Visibilitas Komponen** | Scan report pasca build yang tersimpan terisolasi di console tool security. | Standarisasi SBOM OCI-native (CycloneDX/SPDX) yang menempel langsung pada OCI Image Manifest. |
| **Penanganan Kerentanan** | Alert storm tak terkurasi; developer mematikan scanner akibat false positive. | **VEX (Vulnerability Exploitability eXchange)**: Penegakan policy hanya memblokir CVE yang *actionable* dan *exploitable*. |
| **Production Gating** | Pemeriksaan manual atau gating berbasis branch Git. | Kube-apiserver Admission Controller memblokir image unsigned langsung di level kernel request via Webhooks. |

---

### 5. How (Workflow Detail)

Arsitektur produksi menerapkan rantai verifikasi tertutup yang terdiri dari 7 tahapan berurutan:

```
[ Developer Commit (Signed GPG) ]
                |
                v
[ CI Runner: Hermetic Build Environment ]
        |-- 1. Dependency Resolution via Internal Secure Proxy
        |-- 2. Build Artifact (Compile / Binary Packing)
        |-- 3. Produce OCI Image (Containerization)
                |
                v
[ Security Metadata Generation Pipeline ]
        |-- A. Generate SBOM (Syft -> CycloneDX JSON)
        |-- B. Scan Vulnerabilities (Grype/Trivy against SBOM)
        |-- C. Generate / Attach VEX Assessment (OpenVEX JSON)
        |-- D. Generate SLSA Provenance (in-toto Predicate)
                |
                v
[ Cryptographic Signing Engine (Cosign + Sigstore) ]
        |-- 1. Acquire OIDC Token from CI Identity Provider
        |-- 2. Request Ephemeral Cert from Fulcio
        |-- 3. Sign OCI Image Digest
        |-- 4. Attest SBOM, Provenance, & VEX to Image Digest
        |-- 5. Write SET to Rekor Transparency Log
                |
                v
[ Push OCI Artifacts to Enterprise Registry (Harbor) ]
                |
                v
[ Kubernetes Deployment Request (GitOps / ArgoCD) ]
                |
                v
[ Kubernetes Dynamic Admission Webhook (Kyverno) ]
        |-- 1. Intercept Pod Creation Request
        |-- 2. Extract Container Image Cryptographic Digest
        |-- 3. Query Sigstore Rekor & Fulcio Root of Trust
        |-- 4. Verify Cryptographic Attestation (Provenance + SBOM + VEX)
        |-- 5. Match SLSA Policy: Source repo match? Builder identity match?
        |-- 6. Evaluate VEX: Are there unmitigated CRITICAL CVEs?
                |
                v
     [ Decision Gate: ALLOW / REJECT ]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Dunia Nyata: Sistem Sertifikasi Logistik Farmasi Global
Bayangkan sebuah pabrik obat (*software developer*):
1. **Source Code**: Formula kimia obat.
2. **Third-party Dependencies**: Bahan kimia mentah yang dibeli dari supplier luar.
3. **Build Pipeline**: Reaktor kimia pabrik. Jika filter udara reaktor tercemar (*compromised runner*), obat terkontaminasi meski formula aslinya aman.
4. **SBOM**: Komposisi detail bahan aktif dan non-aktif pada label botol obat.
5. **Cosign & Sigstore**: Segel hologram anti-tamper berstandar interpol (*Rekor Log*) dengan sertifikat batch produksi resmi yang dikeluarkan oleh regulator farmasi (*Fulcio CA*).
6. **VEX**: Catatan dokter spesialis yang menyatakan bahwa bahan tertentu bereaksi negatif pada suhu 100°C, namun karena obat disimpan pada suhu 4°C, obat tersebut **Aman Digunakan**.
7. **Admission Controller**: Petugas farmasi rumah sakit yang memindai segel hologram dan menolak memasukkan obat ke ruang rawat inap jika segel rusak, formula tidak lengkap, atau berasal dari distributor ilegal.

#### Arsitektur Produksi Lengkap (ASCII Detail)

```
========================================================================================================================
                                      ENTERPRISE SOFTWARE SUPPLY CHAIN ARCHITECTURE
========================================================================================================================

 [ DEVELOPER DOMAIN ]
 +-------------------------------------+
 | Workstation (Strict Commits)        |
 | - Git Commit (SSH/GPG Signed)       |--------+
 +-------------------------------------+        |
                                                |
                                                v
 [ CONTINUOUS INTEGRATION CLUSTER (K8s/Tekton/GHA) ]
 +--------------------------------------------------------------------------------------------------------------------+
 | RUNNER POD (Isolated, Non-root, Ephemeral)                                                                         |
 |                                                                                                                    |
 |  +--------------------+        +------------------------+        +-----------------------------------------------+ |
 |  | 1. Source Checkout | -----> | 2. Hermetic Compilation| -----> | 3. Container Assembly (Buildx/Kaniko)         | |
 |  |    - Verify Commit |        |    - Cached Mirrors    |        |    - Distroless Base                          | |
 |  |    - Check Identity|        |    - Hash Checking     |        |    - Generate sha256 Digest                   | |
 |  +--------------------+        +------------------------+        +-----------------------------------------------+ |
 |                                                                                                  |                 |
 |                                +-----------------------------------------------------------------+                 |
 |                                v                                                                                   |
 |  +---------------------------------------------------------------------------------------------------------------+ |
 |  | 4. Security Metadata Factory                                                                                  | |
 |  |                                                                                                               | |
 |  |    [ Syft Analyzer ] ---------------> [ CycloneDX SBOM ] -----------------+                                   | |
 |  |                                                                           |                                   | |
 |  |    [ Grype/Trivy Scanner ] ---------> [ Vulnerability Scan Engine ]       |                                   | |
 |  |                                                    |                      v                                   | |
 |  |                                                    v             [ in-toto Envelope ]                         | |
 |  |    [ Pipeline Metadata ] -----------> [ SLSA Provenance v1.0 ]            |                                   | |
 |  |                                                    |                      |                                   | |
 |  |    [ Security Exception (Triage) ] -> [ OpenVEX Attestation ] ------------+                                   | |
 |  +---------------------------------------------------------------------------------------------------------------+ |
 |                                                                                                  |                 |
 |                                +-----------------------------------------------------------------+                 |
 |                                v                                                                                   |
 |  +---------------------------------------------------------------------------------------------------------------+ |
 |  | 5. Signing Engine (Cosign)                                                                                    | |
 |  |                                                                                                               | |
 |  |    a. Request Token ----> [ CI OIDC Provider ] (JWT Claim)                                                    | |
 |  |    b. Generate Ephemeral Keypair                                                                              | |
 |  |    c. Sign Digest & Attestations (SBOM + Provenance + VEX)                                                    | |
 |  |    d. Cert Request -----> [ Sigstore Fulcio ] (Receive Short-lived x509 Cert)                                 | |
 |  |    e. Publication ------> [ Sigstore Rekor ]  (Append Merkle Tree -> Receive SET)                             | |
 |  +---------------------------------------------------------------------------------------------------------------+ |
 +--------------------------------------------------------------------------------------------------------------------+
                                                |
                                                | Push Image, Attestations, & Signatures
                                                v
 [ ENTERPRISE ARTIFACT REPOSITORY (Harbor / OCI Registry) ]
 +--------------------------------------------------------------------------------------------------------------------+
 | Repository: production/core-banking-service                                                                        |
 |                                                                                                                    |
 |   - Image Manifest: core-banking-service@sha256:abcd1234...                                                        |
 |   - Signature Spec: sha256-abcd1234....sig (Signed by Fulcio Cert, SET attached)                                   |
 |   - SBOM Attest:    sha256-abcd1234....att (Predicate: CycloneDX)                                                  |
 |   - SLSA Attest:    sha256-abcd1234....att (Predicate: SLSA Provenance v1.0)                                        |
 |   - VEX Attest:     sha256-abcd1234....att (Predicate: OpenVEX)                                                    |
 +--------------------------------------------------------------------------------------------------------------------+
                                                |
                                                | Pull / Admission Webhook Intercept
                                                v
 [ PRODUCTION KUBERNETES CONTROL PLANE ]
 +--------------------------------------------------------------------------------------------------------------------+
 | API Server (kube-apiserver)                                                                                        |
 |       |                                                                                                            |
 |       | Dynamic Admission Webhook Call                                                                             |
 |       v                                                                                                            |
 | [ KYVERNO POLICY ENGINE / ADMISSION CONTROLLER ]                                                                   |
 |       |                                                                                                            |
 |       |-- Step A: Verify Cosign Signature (Rekor Public Key / Fulcio Identity Root)                                |
 |       |-- Step B: Verify Attestor Identity (Check Issuer == "https://token.actions.githubusercontent.com")         |
 |       |-- Step C: Extract and Validate SLSA Provenance (Verify Source Repository URL & Branch)                     |
 |       |-- Step D: Enforce Vulnerability Policy against SBOM + OpenVEX Attestations                                 |
 |       |                                                                                                            |
 |    [ PASSED? ]                                                                                                     |
 |       |                                                                                                            |
 |       |--- YES: [ Allow Pod Deployment to Node ]                                                                   |
 |       +--- NO : [ Reject Request (403 Forbidden) with Cryptographic Violation Log ]                               |
 +--------------------------------------------------------------------------------------------------------------------+
========================================================================================================================
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Manual Keypair Signing & Verification
Contoh dasar menandatangani image secara deterministik menggunakan asymmetric key lokal via `cosign`.

```bash
#!/usr/bin/env bash
set -euo pipefail

# 1. Generate keypair lokal terenkripsi password
export COSIGN_PASSWORD="SuperSecretPassword123!"
cosign generate-key-pair

# Output: cosign.key (Private Key) dan cosign.pub (Public Key)

# 2. Tag image lokal dan push ke registry lokal (Kind/Docker registry)
LOCAL_IMAGE="localhost:5001/payment-service:v1.0.0"
docker tag alpine:latest "${LOCAL_IMAGE}"
docker push "${LOCAL_IMAGE}"

# Dapatkan image digest spesifik (immutable)
IMAGE_DIGEST=$(docker inspect --format='{{index .RepoDigests 0}}' "${LOCAL_IMAGE}")

# 3. Tandatangani OCI image digest menggunakan private key
cosign sign --key cosign.key --yes "${IMAGE_DIGEST}"

# 4. Verifikasi signature image menggunakan public key
cosign verify --key cosign.pub "${IMAGE_DIGEST}" | jq .
```

---

#### B. Practical Enterprise Example: Automated CI/CD Pipeline
Berikut implementasi pipeline production menggunakan GitHub Actions: membangun image, mengekstrak SBOM CycloneDX, menginjeksi SLSA provenance, melakukan scanning, membuat dokumen OpenVEX untuk justifikasi CVE, dan menandatanganinya secara **Keyless via Sigstore**.

##### Pipeline Definition (`.github/workflows/secure-delivery.yml`)
```yaml
name: Production Secure Supply Chain Delivery

on:
  push:
    branches: [ "main" ]
    tags: [ 'v*.*.*' ]

permissions:
  id-token: write   # Wajib untuk Sigstore Fulcio OIDC Authentication
  contents: read    # Membaca source code
  packages: write  # Menulis ke GitHub Container Registry (GHCR)

jobs:
  build-secure-artifact:
    runs-on: ubuntu-latest
    env:
      REGISTRY: ghcr.io
      IMAGE_NAME: ${{ github.repository }}

    steps:
      - name: Checkout Source Code
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Install Security Tools (Cosign, Syft, Grype)
        uses: sigstore/cosign-installer@v3.3.0

      - name: Install Anchore Syft
        run: |
          curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh -s -- -b /usr/local/bin

      - name: Install Anchore Grype
        run: |
          curl -sSfL https://raw.githubusercontent.com/anchore/grype/main/install.sh | sh -s -- -b /usr/local/bin

      - name: Install OpenVEX CLI
        run: |
          curl -fsSL https://github.com/openvex/vexctl/releases/download/v0.3.0/vexctl_0.3.0_linux_amd64.tar.gz | tar -xz -C /usr/local/bin vexctl

      - name: Setup Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract Metadata (Labels, Tags)
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=sha,format=long
            type=semver,pattern={{version}}

      - name: Build and Push OCI Image
        id: build-and-push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}

      - name: Export Cryptographic Digest
        id: digest
        run: |
          # Ambil OCI Manifest Digest spesifik dari build step
          DIGEST="${{ steps.build-and-push.outputs.digest }}"
          IMAGE_URI="${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}@${DIGEST}"
          echo "IMAGE_URI=${IMAGE_URI}" >> $GITHUB_ENV
          echo "RAW_DIGEST=${DIGEST}" >> $GITHUB_ENV

      - name: Generate CycloneDX SBOM
        run: |
          syft "${IMAGE_URI}" -o cyclonedx-json=sbom.cyclonedx.json

      - name: Vulnerability Scan against SBOM
        id: scan
        run: |
          # Scan SBOM dan ekspor ke JSON format
          grype sbom:sbom.cyclonedx.json -o json > scan-report.json || true

      - name: Generate OpenVEX Document (Justifikasi Vulnerability)
        run: |
          # Contoh: Mereduksi False-Positive untuk CVE yang dependency-nya ada tapi code path tidak dipanggil
          vexctl create \
            --product="${IMAGE_URI}" \
            --vuln="CVE-2023-99999" \
            --status="not_affected" \
            --justification="vulnerable_code_not_in_execute_path" \
            --statement="Code execution path is disabled via immutable runtime configuration flags." \
            --file=patch-vex.json

      - name: Keyless Sign OCI Image (Sigstore Fulcio + Rekor)
        run: |
          # Melakukan signing image OCI menggunakan ephemeral certs via GitHub Actions OIDC ID Token
          cosign sign --yes "${IMAGE_URI}"

      - name: Attach and Sign SBOM Attestation
        run: |
          cosign attest --yes \
            --predicate sbom.cyclonedx.json \
            --type cyclonedx \
            "${IMAGE_URI}"

      - name: Attach and Sign OpenVEX Attestation
        run: |
          cosign attest --yes \
            --predicate patch-vex.json \
            --type https://openvex.dev/ns/v0.2.0 \
            "${IMAGE_URI}"
```

##### Policy Verification Rule di Kubernetes (`kyverno-policy.yaml`)
Kebijakan Kyverno berikut memblokir deployment pod apa pun jika image tidak ditandatangani oleh identity repository GitHub yang sah atau tidak menyertakan attestation SBOM yang terdaftar di Rekor Transparency Log.

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: enforce-supply-chain-integrity
  annotations:
    policies.kyverno.io/title: Verify Image Signature and Attestation via Keyless Sigstore
    policies.kyverno.io/category: Software Supply Chain Security
    policies.kyverno.io/severity: High
    policies.kyverno.io/subject: Pod
spec:
  validationFailureAction: Enforce
  webhookTimeoutSeconds: 30
  rules:
    - name: verify-sigstore-keyless-signature
      match:
        any:
          - resources:
              kinds:
                - Pod
      verifyImages:
        - imageReferences:
            - "ghcr.io/enterprise-org/*"
          # Wajibkan verifikasi keyless via Fulcio
          keyless:
            issuer: "https://token.actions.githubusercontent.com"
            subject: "https://github.com/enterprise-org/*/.github/workflows/*@refs/heads/main"
            rekor:
              url: "https://rekor.sigstore.dev"
          attestations:
            - predicateType: https://cyclonedx.org/schema/1.5
              conditions:
                - all:
                    - key: "{{ spec.components | length(@) > `0` }}"
                      operator: Equals
                      value: true
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
* **Sektor**: Tier-1 Digital Banking Platform (Asia Pasifik).
* **Skala**: 450+ Microservices, 12 Core Kubernetes Clusters (Multi-Region), ~4.000 Deployment/Bulan.
* **Standar Regulasi**: PCI-DSS v4.0 Requirement 6.3.2 (Software Inventories) & Bank Sentral Cybersecurity Framework.

#### Insiden Nyata & Akar Masalah
Pada Q2, sistem monitoring mendeteksi anomali pada salah satu service pemrosesan valuta asing. Investigasi forensik menemukan:
1. Sebuah pull request disetujui secara otomatis melalui *compromised developer credential*.
2. Dependency file `package.json` memuat package `@fintech-internal/crypto-utils` dengan versi `9.9.1`.
3. Dependency manager mengeksekusi serangan **Dependency Confusion**; runner menarik package dari public npmjs.org yang dibuat penyerang dengan nama identik, bukan dari private mirror internal.
4. Container image lolos dari pipeline security tradisional karena scanner SCA yang digunakan saat itu hanya memeriksa database CVE yang terdaftar, sementara dependency berbahaya ini berstatus *Zero-Day Exploit* yang baru dipublikasikan 4 jam sebelumnya.
5. Image unsigned tersebut langsung lolos deployment ke cluster staging dan production.

#### Arsitektur Remedi & Transformasi Menuju SLSA Level 3
Platform Security Engineering merombak total supply chain platform dalam 90 hari:

```
+--------------------------------------------------------------------------------------------------+
|                            ENTERPRISE REMEDIATION IMPLEMENTATION ARCHITECTURE                   |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
| [ Isolation Firewall ]                                                                           |
|   `---> Blokir direct egress dari seluruh CI Runner ke npmjs, PyPI, Maven Central.              |
|                                                                                                  |
| [ JFrog Artifactory / Harbor Smart Proxy ]                                                       |
|   `---> Terapkan Virtual Repositories dengan 'Internal-Only Overrides'.                          |
|   `---> Package ber-scope `@fintech-internal` diblokir total dari resolusi public upstream.      |
|                                                                                                  |
| [ Ephemeral Hermetic Build Engine ]                                                              |
|   `---> Migrasi CI Runner ke Kubernetes ephemeral pods tanpa internet access.                    |
|   `---> Caching dependencies menggunakan locked-down vendor bundles dengan SHA-512 checks.       |
|                                                                                                  |
| [ Dynamic Admission Enforcement (Kyverno + Cosign) ]                                             |
|   `---> Mengaktifkan Webhook Validating Controller pada seluruh cluster k8s.                     |
|   `---> Kebijakan strict:                                                                        |
|         1. Block semua image tanpa tanda tangan Fulcio dari identity GitHub Actions resmi.       |
|         2. Block semua image yang attestation SBOM-nya tidak memiliki hash verifikasi source.   |
|         3. Block image dengan CVE Critical/High KECUALI ada dokumen VEX "Not Affected".          |
|                                                                                                  |
+--------------------------------------------------------------------------------------------------+
```

#### Hasil Pasca-Implementasi (Metrics)
* **Waktu Triage Kerentanan**: Berkurang dari **48 jam menjadi 35 menit** per insiden CVE baru berkat adopsi automated VEX parsing.
* **Deployment Webhook Latency**: Optimasi Kyverno caching menurunkan webhook overhead dari **1.200ms menjadi 85ms** per request.
* **Temuan Zero-Trust**: Menahan 100% upaya deployment image modifikasi manual (*rogue pods*) yang dieksekusi langsung via `kubectl` oleh engineer yang memiliki privilege `cluster-admin`.

---

### 9. Trade-offs (Performance, Latency, Scalability, Cost)

| Parameter | Pendekatan Ringan (Permissive) | Pendekatan Hardened (Production Standard) | Analisis Trade-off Engineering |
| :--- | :--- | :--- | :--- |
| **Admission Control Latency** | Verifikasi signature Cosign secara asynchronous via controller audit mode. | Enforce Validating Admission Webhook secara synchronous di API Server (`FailurePolicy=Fail`). | Sinkronisasi webhooks menambah penundaan 50-300ms pada pembuatan Pod. Jika Sigstore Rekor/Fulcio public down dan tidak ada caching lokal, API server akan memblokir *seluruh* deployment pod darurat. |
| **Penyimpanan OCI Registry** | Hanya menyimpan container image base (`image:tag`). | Menyimpan Container Image + Signature + SBOM Attestation + VEX Metadata + Provenance. | Penggunaan storage OCI meningkat **2.5x hingga 4x**. Meningkatkan biaya storage cloud (S3/GCS backend) dan kebutuhan bandwidth transfer jaringan registry. |
| **Build Pipeline Duration** | Dynamic dependency resolution (`npm install`, `pip install` langsung dari internet). | Hermetic build (pre-fetching dependencies, vendoring, dependency checksum validation, SBOM extraction). | Waktu eksekusi build di CI bertambah **30% hingga 80%**, membutuhkan alokasi compute runner yang lebih tinggi untuk parsing dependency graph. |
| **Public vs Private Sigstore** | Memakai Public Sigstore Infrastructure (Fulcio, Rekor publik di sigstore.dev). | Self-hosted Private Sigstore Ecosystem (Fulcio, Rekor, Trillian, KMS internal). | Public Sigstore gratis namun metadata build dan OIDC Subject terekspos di public Merkle tree. Private Sigstore menjamin kerahasiaan namun menuntut overhead operasional maintenance Trillian DB, PKI KMS, dan high-availability cluster. |

---

### 10. Common Mistakes & Troubleshooting

#### A. Rekor Public Log Rate Limiting pada Admission Webhooks
*   **Gejala**: Pod gagal di-*schedule* secara tiba-tiba dengan log API Server: `Internal error occurred: failed calling webhook "validate.kyverno.svc": failed to verify signature: HTTP 429 Too Many Requests from rekor.sigstore.dev`.
*   **Penyebab**: Webhook Admission Controller memverifikasi signature dengan menghubungi Rekor log public Sigstore secara langsung pada setiap event replikasi pod (misal: saat HPA scale-up dari 10 menjadi 200 pod).
*   **Solusi**:
    1. Aktifkan fitur *signature caching* pada Admission Controller (Kyverno v1.10+ mendukung Redis cache untuk cryptographic verification results).
    2. Konfigurasi `cosign` untuk menyertakan **Rekor Bundle** (`--bundle`) langsung ke dalam OCI Image Manifest sehingga Admission Controller dapat melakukan *offline verification* tanpa query HTTP eksternal.

#### B. Mutated Multi-Stage Builds yang Merusak Provenance
*   **Gejala**: Attestation SLSA menyatakan hash binary valid, namun runtime Pod crash atau terdeteksi membawa binary yang tidak terlacak di SBOM.
*   **Penyebab**: Dockerfile menggunakan stage intermediate yang menarik artifact dari luar tanpa validasi hash:
    ```dockerfile
    # CRITICAL MISTAKE:
    FROM golang:1.21 AS builder
    WORKDIR /app
    COPY . .
    RUN go build -o main .

    FROM alpine:latest
    # Penarikan binary eksternal dinamis di stage akhir yang tidak tercatat di build awal
    RUN wget http://untrusted-server.com/helper-tool -O /usr/bin/helper-tool
    COPY --from=builder /app/main /main
    ENTRYPOINT ["/main"]
    ```
*   **Solusi**: Terapkan *Hermetic Multi-Stage Dockerfile*; seluruh runtime dependencies dan binary wajib di-resolve pada build step pertama dan dianalisis oleh generator SBOM sebelum image final dirakit.

#### C. False Positive Panic Akibat Scanning Tanpa Konteks
*   **Gejala**: Build CI gagal (*break the build*) karena scanner mendeteksi CVE-2023-XXXXX (Critical) di dalam image, padahal kerentanan tersebut berada di package testing internal yang tidak pernah dieksekusi di production container.
*   **Troubleshooting & Action Guide**:
    1. Lacak jalur ketergantungan menggunakan query Syft/Grype:
       ```bash
       grype sbom:sbom.cyclonedx.json -o json | jq '.matches[] | select(.vulnerability.id=="CVE-2023-XXXXX") | .artifact'
       ```
    2. Jika kerentanan terkonfirmasi *unreachable*: **Jangan matikan security scanner!**
    3. Buat file `openvex` resmi yang ditandatangani oleh Tech Lead/AppSec via `vexctl` dengan status `not_affected`.
    4. Inject attestation VEX ke OCI digest image agar policy gate meloloskan deployment secara terstruktur dan terdokumentasi.

---

### 11. Best Practices (Production Checklist)

#### Pipeline Hardening Checklist
- [ ] Runner CI dieksekusi secara **ephemeral** (pod/VM dihancurkan langsung setelah 1 pipeline run selesai).
- [ ] Network runner dikunci menggunakan egress filtering (hanya mengizinkan akses ke internal artifact repository dan secret manager).
- [ ] Akses Docker socket (`/var/run/docker.sock`) di CI runner dihilangkan total; gunakan unprivileged container builders seperti **Kaniko**, **Buildah**, atau **BuildKit rootless**.
- [ ] Konfigurasi package managers (`npm`, `pip`, `go`, `gradle`) diatur secara permanen ke internal repository mirror, bukan public registry.

#### Cryptography & Signing Checklist
- [ ] Image referensi di deployment YAML wajib menggunakan **Immutable Immutable Cryptographic Digest** (`image@sha256:...`), bukan mutable tag (`image:latest`).
- [ ] Signatures dan Attestations digenerasikan secara **Keyless via OIDC identity**, atau menggunakan private keys yang terisolasi di Hardware Security Module (HSM) / Cloud KMS (AWS KMS, GCP KMS, Vault).
- [ ] Public key atau Fulcio Root CA didistribusikan ke cluster via Kubernetes Secret atau ConfigMap yang diproteksi RBAC ketat.
- [ ] Setiap build menghasilkan minimal 3 attestation: **SLSA Provenance v1.0**, **CycloneDX SBOM**, dan **Security Evaluation (VEX)**.

#### Kubernetes Admission Checklist
- [ ] Admission Controller dijalankan minimal 3 replika dengan Anti-Affinity tinggi di kontrol plane/worker node.
- [ ] Konfigurasi `timeoutSeconds` pada `ValidatingWebhookConfiguration` diset maksimal pada `15s` agar tidak menyebabkan starvation pada worker pool `kube-apiserver`.
- [ ] Namespace infrastruktur esensial (`kube-system`, `kyverno`, `monitoring`) di-eksklusi secara ketat dari policy blocking untuk mencegah dead-lock cluster saat failure total.

---

### 12. Hands-on Practice

Simulasi menyeluruh: Setup Local Kind Cluster, Build Image, Generate SBOM, Sign Keyless via Cosign Lokal, Terapkan Kyverno Admission Controller, dan Lakukan Pengujian Blockade Image.

#### Directory Setup
Semua file praktikum ini disimpan dan dijalankan dari path:
`hands-on/m02/`

```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
```

#### Langkah 1: Inisialisasi Local Kind Cluster & Registry OCI
Buat cluster Kubernetes lokal terintegrasi dengan OCI registry internal tanpa autentikasi rumit:

```bash
cat << 'EOF' > setup-env.sh
#!/usr/bin/env bash
set -euo pipefail

# 1. Buat local OCI Registry
reg_name='local-registry'
reg_port='5001'
if [ "$(docker inspect -f '{{.State.Running}}' "${reg_name}" 2>/dev/null || true)" != 'true' ]; then
  docker run -d --restart=always -p "127.0.0.1:${reg_port}:5000" --name "${reg_name}" registry:2
fi

# 2. Buat Kind Cluster dengan akses ke OCI Registry
cat <<KIND_CONF | kind create cluster --name supply-chain-lab --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  extraPortMappings:
  - containerPort: 5000
    hostPort: 5001
KIND_CONF

# 3. Hubungkan Registry ke Network Kind
docker network connect "kind" "${reg_name}" || true

echo "Environment Ready: Kind Cluster (supply-chain-lab) connected to Registry (localhost:5001)"
EOF

chmod +x setup-env.sh
./setup-env.sh
```

#### Langkah 2: Install Kyverno Policy Engine
Deploy Kyverno ke cluster lokal:

```bash
kubectl create -f https://github.com/kyverno/kyverno/releases/download/v1.11.4/install.yaml
kubectl wait --namespace kyverno --for=condition=ready pod --selector=app.kubernetes.io/name=kyverno --timeout=180s
```

#### Langkah 3: Setup App, Build, dan Generate SBOM
Buat aplikasi microservice minimalis, bundle menjadi image OCI, dan ekstrak SBOM:

```bash
# 1. Buat aplikasi sederhana
cat << 'EOF' > app.py
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "SECURE_TRANSACTION_ACTIVE"}).encode())

server = HTTPServer(('0.0.0.0', 8080), SimpleHandler)
server.serve_forever()
EOF

# 2. Buat Dockerfile
cat << 'EOF' > Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY app.py .
EXPOSE 8080
USER 10001
ENTRYPOINT ["python", "app.py"]
EOF

# 3. Build dan Push ke Local Registry
IMAGE_TAG="localhost:5001/secure-api:v1.0.0"
docker build -t "${IMAGE_TAG}" .
docker push "${IMAGE_TAG}"

# Dapatkan Digest SHA-256 spesifik
DIGEST=$(docker inspect --format='{{index .RepoDigests 0}}' "${IMAGE_TAG}")
echo "Artifact Digest: ${DIGEST}"
echo "${DIGEST}" > image_digest.txt

# 4. Generate CycloneDX SBOM menggunakan Syft
syft "${DIGEST}" -o cyclonedx-json=sbom.json
```

#### Langkah 4: Sign Image dan Attach SBOM Menggunakan Cosign
Tandatangani image digest dan attach file SBOM sebagai attestation OCI:

```bash
# Generate keypair lokal (gunakan string kosong untuk password di lab ini)
export COSIGN_PASSWORD=""
cosign generate-key-pair

# Ambil digest yang telah diekspor
IMAGE_DIGEST=$(cat image_digest.txt)

# 1. Sign Image
cosign sign --key cosign.key --yes "${IMAGE_DIGEST}"

# 2. Attest SBOM ke OCI Image
cosign attest --key cosign.key --predicate sbom.json --type cyclonedx --yes "${IMAGE_DIGEST}"
```

#### Langkah 5: Buat Kebijakan Validasi di Kubernetes (Kyverno Policy)
Terapkan ClusterPolicy yang memblokir semua pod yang image-nya tidak diverifikasi oleh public key `cosign.pub`:

```bash
# Ambil public key satu baris
PUB_KEY=$(cat cosign.pub)

cat << EOF | kubectl apply -f -
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: verify-image-policy
spec:
  validationFailureAction: Enforce
  background: false
  rules:
    - name: verify-signature-rule
      match:
        any:
          - resources:
              kinds:
                - Pod
      verifyImages:
        - imageReferences:
            - "localhost:5001/*"
          key: |-
$(cat cosign.pub | sed 's/^/            /')
EOF
```

#### Langkah 6: Eksekusi Uji Penetrasi Admission Verification

##### Kasus A: Deploy Unsigned Image (Harus Ditolak)
```bash
# Push image unsigned ke registry
docker tag alpine:latest localhost:5001/untrusted-app:v1.0.0
docker push localhost:5001/untrusted-app:v1.0.0
UNTRUSTED_DIGEST=$(docker inspect --format='{{index .RepoDigests 0}}' localhost:5001/untrusted-app:v1.0.0)

# Coba deploy ke Kubernetes
cat << EOF | kubectl apply -f - || true
apiVersion: v1
kind: Pod
metadata:
  name: untrusted-pod
spec:
  containers:
    - name: app
      image: ${UNTRUSTED_DIGEST}
EOF
```
*Hasil yang diharapkan*: `kube-apiserver` menolak deployment dengan pesan error: `admission webhook "validate.kyverno.svc" denied the request: image verification failed for localhost:5001/untrusted-app...`.

##### Kasus B: Deploy Signed Image yang Sah (Harus Berhasil)
```bash
VALID_DIGEST=$(cat image_digest.txt)

cat << EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: trusted-pod
spec:
  containers:
    - name: secure-app
      image: ${VALID_DIGEST}
EOF

# Verifikasi Pod Berjalan
kubectl get pod trusted-pod -o wide
```
*Hasil yang diharapkan*: Pod `trusted-pod` berstatus `Running`.

---

### 13. Exercise

#### Level Easy
Ubah policy Kyverno di cluster lokal praktikum untuk memverifikasi bahwa attestation `cyclonedx` ada pada image, dan pastikan deployment gagal jika attestation SBOM dihapus dari registry OCI.
*Kriteria Sukses*: Deploy pod ditolak dengan log validasi `Attestation not found` saat attestation SBOM dihapus via `cosign clean` (atau diuji pada image yang di-sign tanpa parameter `--predicate`).

#### Level Medium
Buat sebuah bash automation script `generate-vex.sh` yang menerima input nama image dan nomor CVE, kemudian:
1. Menghasilkan dokumen OpenVEX (`status=not_affected`, `justification=inline_mitigations_exist`).
2. Menggunakan `cosign attest` untuk menginjeksi dokumen VEX tersebut ke dalam OCI Image Manifest.
3. Melakukan verifikasi parsing isi dokumen VEX langsung dari OCI registry menggunakan perintah `cosign verify-attestation`.
*Kriteria Sukses*: Script berjalan non-interaktif, menghasilkan output JSON status `success`, dan payload VEX dapat diekstraksi menggunakan `jq`.

#### Level Hard
Simulasikan serangan **Dependency Confusion** lokal menggunakan registry Python (`pypiserver` lokal) dan PyPI public:
1. Siapkan script build Python yang memanggil library buatan sendiri bernama `company-calc`.
2. Buat repository public tiruan yang memiliki library `company-calc` dengan versi lebih tinggi (`v99.0.0`) yang memuat payload berbahaya (misal: print alert `COMPROMISED`).
3. Konfigurasikan file build `pip` dan runner agar menerapkan *hash checking* (`--require-hashes`) dan *pinning direct indices*.
*Kriteria Sukses*: Build pipeline menggagalkan download package `v99.0.0` dari upstream public, dan memaksakan proses build menggunakan package otentik internal yang hash-nya cocok.

---

### 14. Challenge (Studi Kasus Kompleks)

**Konteks Permasalahan:**
Sebuah institusi pertahanan memiliki environment cluster Kubernetes yang beroperasi secara **Total Air-Gapped** (tidak ada koneksi internet keluar sama sekali, tidak ada akses ke `sigstore.dev`, `rekor.sigstore.dev`, atau public NTP pools). 

Mereka menerima rilis aplikasi dari 5 vendor external software developer yang berbeda. Setiap vendor memiliki infrastruktur CI/CD masing-masing di cloud publik. 

**Objektif:**
Rancang dan dokumentasikan arsitektur *Supply Chain Ingestion Gate* enterprise di perbatasan perimeter network air-gap tersebut yang memenuhi kriteria:
1. Vendor external **tidak diizinkan** mengetahui public key internal institusi.
2. Setiap artifact container yang dikirimkan vendor via transfer media fisik (USB/Hard Drive terenkripsi) harus memuat:
   * SLSA Provenance v1.0 yang membuktikan proses build di-trigger dari branch release vendor.
   * Full CycloneDX SBOM.
   * Tanda tangan digital vendor menggunakan x509 Enterprise PKI mereka sendiri.
3. Di dalam lingkungan Air-gap, institusi harus:
   * Melakukan validasi kriptografis offline tanpa memanggil OCSP server vendor publik.
   * Melakukan re-signing otomatis (*cross-attestation*) menggunakan HSM internal sebelum image dimasukkan ke registry produksi lokal.
   * Memastikan Admission Controller cluster lokal hanya percaya pada Root of Trust internal institusi, namun jejak audit vendor external tetap tersimpan permanen.

**Output Deliverables yang Diharapkan:**
1. Desain arsitektur detail (ASCII diagram alur ingest, verifikasi, re-signing, dan admit).
2. Konfigurasi offline validation script/daemon menggunakan Cosign/in-toto.
3. Spesifikasi struktur metadata attestasi yang disimpan di internal registry.
4. Analisis penanganan resiko pemalsuan timestamp (*timestamp replay attacks*) tanpa ketersediaan public Rekor transparency log.

---

### 15. Quiz Evaluasi Pemahaman

#### Soal Basic (Pilihan Ganda)
1. Apa peran utama dari komponen **Fulcio** dalam ekosistem Sigstore?
   - A. Menyediakan database penyimpanan SBOM dalam format OCI.
   - B. Bertindak sebagai Certificate Authority (CA) yang menerbitkan sertifikat x509 ephemeral berbasis verifikasi OIDC token.
   - C. Menyimpan Merkle Tree transparency log secara terdistribusi.
   - D. Berfungsi sebagai admission webhook controller di dalam cluster Kubernetes.
   *Jawaban & Penjelasan*: **B**. Fulcio adalah Ephemeral CA yang menerbitkan sertifikat x509 berumur pendek (10 menit) yang mengikat public key sementara dengan identitas OIDC pengguna atau CI/CD pipeline.

2. Mengapa penandatanganan image container menggunakan immutable digest (`sha256:...`) wajib dilakukan dibandingkan menandatangani mutable tag (seperti `:latest`)?
   - A. Karena mutable tag membutuhkan resource compute CPU lebih besar saat diverifikasi.
   - B. Karena tag `:latest` tidak didukung oleh OCI registry v2 specification.
   - C. Karena mutable tag dapat ditimpa (*overwrite*) oleh penyerang dengan image berbahaya tanpa mengubah nama tag, sedangkan cryptographic digest bersifat permanen dan matematis terikat pada layer image.
   - D. Karena Cosign tidak memiliki fungsi untuk membaca string format tag.
   *Jawaban & Penjelasan*: **C**. Tag bersifat pointer yang mutable. Penyerang dapat me-push image terinfeksi menggunakan tag yang sama (`:latest`). Mengunci dan menandatangani cryptographic digest memastikan immutability absolut.

3. Apa kepanjangan dan fungsi utama dari dokumen **VEX (Vulnerability Exploitability eXchange)**?
   - A. Virtual Execution X-factor; format eksekusi container tanpa menggunakan Linux kernel namespaces.
   - B. Vulnerability Exploitability eXchange; format machine-readable untuk menyatakan status apakah suatu kerentanan (CVE) benar-benar dapat dieksploitasi dalam konteks produk tertentu.
   - C. Validated Extension XML; format backup konfigurasi cluster Kubernetes.
   - D. Variable Encryption X.509; metode enkripsi payload layer image menggunakan asymmetric key.
   *Jawaban & Penjelasan*: **B**. VEX memungkinkan software producer memberi tahu consumer bahwa sebuah CVE yang terdeteksi di SBOM tidak berdampak (misal: *not_affected* karena code tidak terpanggil), sehingga deployment tidak terblokir secara keliru.

4. Pada framework SLSA v1.0, apa karakteristik utama yang membedakan **SLSA Level 3** dari level di bawahnya?
   - A. Kode sumber wajib ditulis menggunakan bahasa yang memori-safe (seperti Rust atau Go).
   - B. Adanya sistem automated testing dengan coverage unit test minimal 90%.
   - C. Lingkungan build platform harus terisolasi (*isolated*), non-falsifiable provenance, dan kebal dari tampering eksternal runner.
   - D. Database image wajib di-backup secara asinkronus ke multi-cloud providers.
   *Jawaban & Penjelasan*: **C**. SLSA Level 3 fokus pada pencegahan modifikasi build dari dalam dengan mewajibkan build platform terisolasi dan provenance yang tidak dapat dipalsukan oleh pengguna atau lingkungan runner itu sendiri.

5. Manakah format manifest SBOM berikut yang diakui sebagai standar industri global?
   - A. TOML dan INI format.
   - B. CycloneDX dan SPDX.
   - C. Sigstore Manifest Language (SML).
   - D. OCI Dockerfile Layer Specification.
   *Jawaban & Penjelasan*: **B**. Software Bill of Materials (SBOM) memiliki dua standar industri utama yang didukung oleh berbagai vendor dan regulasi global: **CycloneDX** (OWASP) dan **SPDX** (Linux Foundation).

---

#### Soal Intermediate (Pilihan Ganda & Analisis Kasus)
6. Di sebuah pipeline CI/CD yang menggunakan Sigstore Keyless signing, runner mengeksekusi perintah sign pada jam `10:00 UTC`. Sertifikat ephemeral dari Fulcio valid hingga jam `10:10 UTC`. Jika admission controller memverifikasi image tersebut pada jam `15:00 UTC` (5 jam kemudian), mengapa verifikasi tetap sah (*valid*)?
   - A. Karena Cosign secara otomatis memperpanjang umur sertifikat x509 di background.
   - B. Karena Kyverno mematikan pengecekan waktu sertifikat secara default.
   - C. Karena Rekor menyediakan Signed Entry Timestamp (SET) yang membuktikan secara kriptografis bahwa penandatanganan terjadi pada saat sertifikat masih sah.
   - D. Karena OIDC token GitHub Actions memiliki masa berlaku 24 jam.
   *Jawaban & Penjelasan*: **C**. Inilah fungsi utama Merkle Tree di Rekor Transparency Log. Rekor menerbitkan SET yang tidak dapat dipalsukan, membuktikan bahwa proses penandatanganan terjadi di dalam jendela masa aktif sertifikat (antara 10:00 - 10:10 UTC), sehingga validitasnya diakui selamanya.

7. Perhatikan konfigurasi package resolver berikut pada file pipeline sebuah project Python:
   ```bash
   pip install --extra-index-url https://internal-pypi.corp/simple/ internal-auth-lib
   ```
   Mengapa baris konfigurasi di atas membuka celah kerentanan **Dependency Confusion**?
   - A. Karena parameter `--extra-index-url` tidak mengenali protokol HTTPS.
   - B. Karena `pip` akan melakukan query paralel ke PyPI public dan internal-pypi; jika penyerang membuat package bernama `internal-auth-lib` di PyPI publik dengan versi lebih tinggi, pip akan mengunduh versi berbahaya dari publik.
   - C. Karena format path `/simple/` hanya dikhususkan untuk package manager Java (Maven).
   - D. Karena `internal-auth-lib` tidak ditandatangani menggunakan GPG key lokal.
   *Jawaban & Penjelasan*: **B**. Penggunaan `--extra-index-url` menyebabkan `pip` mencari di kedua index secara bersamaan dan memilih versi tertinggi secara heuristik. Penyerang mengeksploitasi ini dengan mempublikasikan versi tinggi di repository publik. Solusinya adalah menggunakan `--index-url` tunggal ke proxy internal yang terisolasi.

8. Dalam context Kyverno Admission Policy, apa akibat fatal jika konfigurasi `failurePolicy` diset ke `Fail` sementara infrastruktur Sigstore Rekor publik mengalami pemadaman (outage)?
   - A. Cluster Kubernetes otomatis restart ke node recovery mode.
   - B. Seluruh image unsigned dapat langsung masuk tanpa peringatan.
   - C. Semua request deployment baru atau scale-out Pod di cluster akan ditolak (terblokir total), mengakibatkan insiden operasional.
   - D. Kebijakan Kyverno akan di-downgrade otomatis menjadi `Audit` mode.
   *Jawaban & Penjelasan*: **C**. `failurePolicy: Fail` menginstruksikan API server untuk menolak request jika webhook validasi gagal berkomunikasi atau mengalami timeout. Jika kontroler bergantung pada Rekor publik yang sedang down dan tidak ada bundle lokal/caching, seluruh deploy baru akan gagal.

9. Apa fungsi dari predikat `in-toto` saat dibundel ke dalam attestation OCI menggunakan Cosign?
   - A. Mengompresi ukuran layer Docker image menjadi 50% lebih kecil.
   - B. Menghubungkan metadata spesifik (seperti build steps, input source commits, output artifact hash, material hashes) dalam format terstandarisasi yang dapat diaudit oleh verifier engine.
   - C. Menghilangkan kebutuhan akan admission controller di Kubernetes.
   - D. Menjalankan scanning kernel exploit pada worker node secara berkala.
   *Jawaban & Penjelasan*: **B**. in-toto menyediakan framework metadata terstruktur (*link*, *layout*, *predicate*) untuk mendokumentasikan setiap aksi yang terjadi di seluruh rantai supply chain: siapa yang mengeksekusi, apa inputnya, dan apa output hash yang dihasilkan.

10. Mengapa scanning SCA pada tahap runtime (di dalam running container) sering kali memberikan hasil yang tidak konsisten dibandingkan scanning SBOM pada tahap build time?
    - A. Karena container runtime memodifikasi source code aplikasi secara acak.
    - B. Karena package compiler, debugging tools, dan dependency manifest file (`package-lock.json`, dll.) sering kali telah dihapus (*stripped*) dari image produksi final untuk optimasi ukuran, menyembunyikan jejak transitive dependencies asli.
    - C. Karena kernel Linux membatasi akses scanning file system lebih dari 100MB.
    - D. Karena format JSON SBOM tidak kompatibel dengan arsitektur CPU ARM/x86.
    *Jawaban & Penjelasan*: **B**. Dockerfile multi-stage yang baik hanya menyalin compiled binary ke base image minimal (seperti distroless/scratch). Di runtime, file metadata dependency sudah tidak ada, sehingga scanner runtime hanya bisa menebak berdasarkan hash binary yang sering kali tidak akurat.

---

#### Skenario Kasus Produksi
11. **Skenario 1**: Sebuah security audit menemukan bahwa developer dapat me-push image container langsung dari laptop mereka ke production OCI registry dan me-deploy image tersebut menggunakan `kubectl apply` darurat, melewati seluruh kontrol pipeline CI/CD dan lolos dari verifikasi admission controller.
    *Tugas Evaluasi*: Jelaskan minimal 2 celah arsitektural yang memungkinkan ini terjadi dan bagaimana cara menutupnya secara absolut!
    *Kriteria Jawaban*:
    - Celah 1: IAM OCI Registry mengizinkan credential developer melakukan write/push ke production namespace.
    - Celah 2: Kebijakan Kyverno/Gatekeeper tidak membatasi identitas signer (hanya memvalidasi sembarang signature, atau verifikasi dimatikan pada namespace darurat).
    - Remedi: Kunci RBAC registry (hanya service account CI/CD yang bisa push ke production). Konfigurasi Kyverno untuk **wajib mencocokkan identity subject OIDC** (hanya ID token dari runner GitHub Actions branch `main` yang diterima; tolak private key lokal developer).

12. **Skenario 2**: Perusahaan Anda memiliki aplikasi monolitik warisan yang menggunakan 1.800 dependencies. Laporan scan Grype mendeteksi ada 42 CVE Kritis. Rilis produksi tertunda 3 minggu karena tim security menolak deploy, sementara tim developer menyatakan bahwa 40 dari 42 CVE tersebut berada pada modul reporting offline yang fiturnya telah dinonaktifkan sejak 2 tahun lalu.
    *Tugas Evaluasi*: Bagaimana Anda memecahkan kebuntuan (*deadlock*) ini secara teknis tanpa melanggar prinsip kepatuhan ISO 27001 / PCI-DSS?
    *Kriteria Jawaban*:
    - Jangan mendegradasi severity threshold scanner.
    - Implementasikan **OpenVEX Workflow**.
    - Tim Security dan Lead Developer melakukan audit bersama: untuk 40 CVE yang berada pada modul mati, buat dokumen VEX resmi dengan status `not_affected` dan justifikasi `vulnerable_code_cannot_be_controlled_by_adversary` atau `vulnerable_code_not_in_execute_path`.
    - Sign dan attach dokumen VEX ke OCI Image. Konfigurasikan Kyverno/Gatekeeper untuk mengevaluasi status VEX: loloskan 40 CVE yang telah memiliki justifikasi valid, dan paksa developer memperbaiki 2 CVE yang benar-benar actionable.

13. **Skenario 3**: Sebuah bank mengimplementasikan SLSA Level 3 pipeline. Namun, audit internal menemukan bahwa runner CI yang digunakan adalah self-hosted runner Kubernetes pod yang berjalan dengan mode `privileged: true` dan me-mount docker socket host (`/var/run/docker.sock`).
    *Tugas Evaluasi*: Mengapa konfigurasi ini secara fundamental membatalkan klaim kepatuhan SLSA Level 3, dan serangan apa yang dapat dieksekusi oleh attacker?
    *Kriteria Jawaban*:
    - Pelanggaran SLSA Level 3: SLSA Level 3 mewajibkan **Hermetic and Isolated Build Infrastructure** yang non-falsifiable. Runner tidak boleh memiliki kemampuan untuk memanipulasi host atau runner lain.
    - Skenario Serangan: Penyerang yang dapat menginjeksi perintah ke build step (misal via PR atau dependensi berbahaya) dapat menggunakan socket Docker host untuk melarikan diri dari container (*container breakout*), memodifikasi memori daemon Docker host, membajak proses kompilasi pod runner lain yang berjalan di node yang sama, atau memalsukan provenance hash sebelum dikirim ke Rekor.
    - Remedi: Hapus container runtime privileged. Gunakan isolated runner berbasis microVM (seperti AWS Firecracker / Kata Containers) dan tools build unprivileged (Kaniko/Buildah).

---

### 16. Summary

Implementasi lanjutan dari **Software Supply Chain Security (SCA)** menuntut pergeseran paradigma dari *Passive Vulnerability Scanning* menuju **Cryptographic Verification & Zero-Trust Pipelines**:

1. **Integritas Rantai Nilai (Supply Chain Integrity)**: Keamanan aplikasi bukan lagi sekadar ketiadaan bug pada kode first-party, melainkan jaminan matematis bahwa setiap dependensi, compiler, intermediate artifact, dan konfigurasi deployment