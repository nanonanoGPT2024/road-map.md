# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Merancang Arsitektur Zero-Trust Software Supply Chain** berbasis framework SLSA (*Supply-chain Levels for Software Artifacts*) Level 3+.
- **Mengimplementasikan Kriptografis Software Attestation** menggunakan ekosistem Sigstore (*Cosign, Fulcio, Rekor*) dan spesifikasi *in-toto* pada *pipeline* CI/CD.
- **Membangun Policy-as-Code (PaC) Engine** terdistribusi menggunakan Open Policy Agent (OPA/Rego) dan Kyverno untuk validasi statis (*pre-commit* / CI) serta dinamis (*Kubernetes Admission Control*).
- **Menerapkan Hermetic & Reproducible Builds** menggunakan *multi-stage distroless containers* dengan audit jejak *Software Bill of Materials* (SBOM) berstandar CycloneDX.
- **Mengintegrasikan Observabilitas Runtime Security** berbasis eBPF (*Extended Berkeley Packet Filter*) untuk mendeteksi anomali pada *kernel-level* secara deterministik.

---

## 2. Prerequisites
Peserta wajib memiliki pemahaman mendalam dan pengalaman praktis pada:
- **Container Internals**: Linux namespaces (`pid`, `net`, `mnt`, `user`), cgroups v2, copy-on-write (OverlayFS), dan OCI (*Open Container Initiative*) runtime specification.
- **Kubernetes Architecture**: Siklus hidup Pod, *API Server request processing*, Webhook Admission Controllers (*Mutating* dan *Validating*).
- **Kriptografi Terapan**: Public Key Infrastructure (PKI), asimetris *signing/verification*, X.509 certificates, OIDC (*OpenID Connect*) identity federation, dan hashing algorithms (SHA-256).
- **CI/CD Engineering**: Deklaratif *pipeline orchestration* (GitHub Actions, GitLab CI, atau Tekton Pipelines) dan sistem manajemen artefak (OCI registries).

---

## 3. Concept & Internal Architecture (Mendalam)

Implementasi DevSecOps tingkat lanjut bergeser dari sekadar *vulnerability scanning* reaktif menuju arsitektur pertahanan berlapis kriptografis dan deterministik.

```
       +-------------------------------------------------------------+
       |                  DEVELOPER WORKSTATION                      |
       |  [Git Commit] -> [GPG/SSH Sign] -> [Pre-commit Hook (Trivy)]|
       +------------------------------+------------------------------+
                                      | Git Push (TLS 1.3)
                                      v
       +-------------------------------------------------------------+
       |                   CI/CD PIPELINE ENGINE                     |
       |                                                             |
       |  1. Hermetic Build (Distroless / Minimal Surface)           |
       |  2. SAST (Semgrep) & SCA (Trivy) -> SARIF Export            |
       |  3. SBOM Generation (Syft) -> CycloneDX JSON                |
       |  4. OIDC Token Exchange (CI Runner Identity)                |
       |         |                                                   |
       |         v                                                   |
       |  +--------------+   +---------------+   +----------------+  |
       |  | Fulcio (CA)  |   | Cosign (Sign) |   | Rekor (T-Log)  |  |
       |  +--------------+   +---------------+   +----------------+  |
       |         |                   |                   |           |
       |         +-> Ephemeral Cert -+-> Attestation ----+           |
       +-----------------------------+-------------------------------+
                                     | OCI Push (Image + Sig + SBOM)
                                     v
       +-------------------------------------------------------------+
       |               CONTAINER REGISTRY (OCI-Compliant)            |
       |  - app:v1.0.0 (Image Blob)                                  |
       |  - app:v1.0.0.sig (Cosign Signature)                        |
       |  - app:v1.0.0.att (In-Toto Provenance / SBOM Predicate)     |
       +-----------------------------+-------------------------------+
                                     | Deploy Trigger
                                     v
       +-------------------------------------------------------------+
       |                 KUBERNETES CONTROL PLANE                    |
       |                                                             |
       |              API Request (e.g., Create Pod)                 |
       |                             |                               |
       |                             v                               |
       |             [Authentication & Authorization]                |
       |                             |                               |
       |                             v                               |
       |             [Mutating Admission Webhook]                    |
       |                             |                               |
       |                             v                               |
       |             [Validating Admission Webhook]                  |
       |                  (Kyverno / OPA Gatekeeper)                 |
       |                    - Verify Rekor Entry                     |
       |                    - Verify Fulcio Root Cert                |
       |                    - Verify Image Signature                 |
       |                    - Enforce Rootless & ReadOnlyRootFS      |
       +-----------------------------+-------------------------------+
                                     | Approved
                                     v
       +-------------------------------------------------------------+
       |                    WORKER NODE RUNTIME                      |
       |                                                             |
       |   +-------------------+             +-------------------+   |
       |   |   Kubelet / CRI   |             |   Kernel Space    |   |
       |   |  (containerd/CRI-O)             |   (Linux Kernel)  |   |
       |   +---------+---------+             +---------+---------+   |
       |             |                                 |             |
       |             v                                 |             |
       |     [Container Process]                       | Syscalls    |
       |   (Drop ALL Caps, Non-Root)                   v             |
       |             |                        +-----------------+    |
       |             +----------------------->|  eBPF Engine    |    |
       |                                      | (Tetragon/Falco)|    |
       |                                      +--------+--------+    |
       |                                               | Alert/Kill  |
       |                                               v             |
       |                                      [Security Data Lake]   |
       +-------------------------------------------------------------+
```

### 3.1 Software Supply Chain Security & SLSA Framework
Ancaman modern menyasar integritas rantai pasok (contoh: kompromi *build runner*, injeksi dependensi transitif, modifikasi artefak pasca-kompilasi). SLSA menyediakan panduan formal:
- **SLSA Level 1**: *Build process* terdokumentasi dan menghasilkan *provenance metadata*.
- **SLSA Level 2**: Penggunaan *hosted build platform* dan verifikasi *provenance* bertanda tangan digital.
- **SLSA Level 3**: *Build platform* terisolasi (*ephemeral runner*), *provenance non-falsifiable* (kunci kriptografi tidak terekspos ke proses *build* aplikasi).

### 3.2 Keyless Signature Lifecycle (Sigstore Architecture)
Pendekatan konvensional menggunakan *static private keys* berisiko tinggi terhadap kebocoran kredensial. Sigstore memfasilitasi model *keyless*:
1. **OIDC Federation**: Runner CI mengotentikasi ke Identity Provider (misal: GitHub/GitLab IdP) dan memperoleh token OIDC berumur pendek (*short-lived*).
2. **Fulcio CA**: Token OIDC ditukar ke Fulcio (Certificate Authority) yang memvalidasi identitas *issuer*, *repository*, dan *workflow ref*, lalu menerbitkan sertifikat X.509 ephemeral (berlaku ~10 menit) yang terikat dengan *ephemeral public key*.
3. **Cosign Signing**: Cosign menandatangani digest container image (bukan tag mutable) menggunakan *ephemeral private key*.
4. **Rekor Transparency Log**: Bukti penandatanganan dicatat ke *immutable, append-only, tamper-evident transparency log* berbasis Merkle Tree.
5. **Verifikasi**: Sistem validasi (Kyverno/Gatekeeper) memverifikasi jejak log di Rekor dan sertifikat Fulcio tanpa membutuhkan pertukaran kunci rahasia (*secretless*).

### 3.3 Dynamic vs Static Policy Engine
- **Statis (CI/CD)**: Validasi dilakukan pada fase perancangan/kompilasi menggunakan OPA Conftest atau Trivy config scanning untuk mencegah sintaks berbahaya lolos ke repositori.
- **Dinamis (Admission Controller)**: Mencegah *drift configuration* dan *bypassed commits* dengan memvalidasi request HTTP payload dari `kube-apiserver` secara *in-memory* sebelum etcd melakukan *persistence*.

---

## 4. Why & What

| Dimensi | Pendekatan Reaktif (Legacy DevSecOps) | Zero-Trust Supply Chain (Modern Enterprise) |
| :--- | :--- | :--- |
| **Identitas Artefak** | Image Tag (`app:latest`, `app:v1.0`) yang mutable | Kriptografis Digest (`app@sha256:4f3b...`) |
| **Trust Model** | Percaya pada jaringan internal / perimeter registry | *Never trust, always verify* via Public Key Infrastructure (Sigstore) |
| **Manajemen Kunci** | Static Long-lived Private Keys di CI/CD Secret | Keyless, berbasis Identity Provider OIDC token & short-lived certificates |
| **Pemeriksaan Kerentanan** | Scan terjadwal mingguan/bulanan (*ad-hoc*) | Continuous gate: SAST/SCA di CI, admission deny di K8s, runtime drift enforcement |
| **Runtime Protection** | Periodic Agent log analysis (Syslog parsing) | In-kernel eBPF real-time execution prevention (SIGKILL pada level syscall) |

---

## 5. How (Workflow Detail)

1. **Phase 1: Code Verification & Static Analysis**
   - Developer melakukan *commit* dengan SSH/GPG signing.
   - *Pre-push hooks* mengeksekusi *secret detection* berbasis entropy (Gitleaks).
   - Pipeline CI memvalidasi dependensi (*lockfiles*) menggunakan SCA dan kode via SAST, lalu mengekspor hasil ke format SARIF (*Static Analysis Results Interchange Format*).
2. **Phase 2: Hermetic Container Build & SBOM Generation**
   - Image dibangun menggunakan model *multi-stage* berbasis base image *distroless* (non-root, tanpa shell/coreutils).
   - *Syft* mengekstraksi dependensi internal untuk memproduksi dokumen SBOM (CycloneDX JSON).
3. **Phase 3: Attestation & Signing**
   - CI runner meminta token identitas OIDC.
   - Cosign berinteraksi dengan Fulcio dan menandatangani OCI digest.
   - SBOM di-*attach* ke OCI registry sebagai *in-toto attestation predicate*.
   - Payload transaksi dicatat ke Rekor Transparency Log.
4. **Phase 4: Admission Gating**
   - Kubernetes API Server menerima manifest `Deployment`.
   - Kyverno Validating Webhook memanggil OCI Registry dan Rekor.
   - Webhook memverifikasi:
     - Apakah image ditandatangani oleh identitas GitHub Actions workflow yang sah?
     - Apakah image bebas dari CVE berkategori *CRITICAL* tanpa *fix* yang disetujui?
     - Apakah manifest mematuhi *Pod Security Standards (Restricted)*?
5. **Phase 5: Runtime Enforce via eBPF**
   - Pod dijalankan di Node.
   - Tetragon mengaitkan (*hooking*) probe eBPF ke syscall kernel (`sys_execve`, `sys_socket`).
   - Upaya *privilege escalation* atau *reverse shell* dideteksi dan dihentikan langsung di level *kernel space*.

---

## 6. Analogy & Diagram ASCII

Bayangkan sistem pengiriman kargo berstandar keamanan internasional:

- **Legacy DevSecOps**: Sopir truk membawa surat jalan bertanda tangan manual di atas kertas. Penjaga gerbang hanya memeriksa sekilas stempel kertas tersebut.
- **Enterprise DevSecOps Modern**: Kontainer disegel menggunakan gembok kriptografis otomatis (*Cosign*). Surat muatan (*SBOM*) didaftarkan pada buku besar publik anti-pemalsuan (*Rekor Transparency Log*). Penjaga gerbang (*Kubernetes Admission Controller*) mencocokkan segel dengan kamera biometrik terpusat (*Fulcio OIDC*). Sensor biometrik internal di dalam kontainer (*eBPF Tetragon*) langsung melumpuhkan muatan jika terjadi aktivitas mencurigakan.

---

## 7. Practical Implementation Code

### 7.1 Hardened Multi-Stage Dockerfile (Distroless Target)

```dockerfile
# syntax=docker/dockerfile:1.4
# Stage 1: Build binary secara deterministik
FROM golang:1.22-alpine AS builder

WORKDIR /src

RUN apk --no-cache add ca-certificates tzdata

COPY go.mod go.sum ./
RUN go mod download && go mod verify

COPY . .

# Hermetic build: Disable CGO, strip symbol & debug info (-s -w)
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build \
    -ldflags="-s -w -extldflags '-static'" \
    -trimpath \
    -o /bin/enterprise-app .

# Stage 2: Minimalist Non-Root Distroless Image
FROM gcr.io/distroless/static-debian12:nonroot

WORKDIR /app

COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --from=builder /bin/enterprise-app /app/enterprise-app

# Non-root user ID 65532 standard distroless
USER 65532:65532

ENTRYPOINT ["/app/enterprise-app"]
```

### 7.2 Enterprise GitHub Actions Pipeline (.github/workflows/devsecops.yml)

Pipeline ini mengimplementasikan Trivy, generate SBOM, keyless sign via Cosign, dan pembuatan attestation in-toto.

```yaml
name: Production DevSecOps Supply Chain

on:
  push:
    branches: [ "main" ]
  pull_request:
    branches: [ "main" ]

permissions:
  contents: read
  packages: write
  id-token: write # Diperlukan untuk OIDC token exchange dengan Sigstore Fulcio
  security-events: write

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build-and-secure:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Source Code
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Setup Cosign
        uses: sigstore/cosign-installer@v3.5.0

      - name: Setup Syft
        uses: anchore/sbom-action/download-syft@v0.15.11

      - name: Log in to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and Push OCI Image
        id: build-image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}

      # SCA Scanning & Static Vulnerability Scan
      - name: Run Trivy Vulnerability Scanner
        uses: aquasecurity/trivy-action@0.18.0
        with:
          image-ref: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
          format: 'sarif'
          output: 'trivy-results.sarif'
          severity: 'CRITICAL,HIGH'
          exit-code: '1' # Gating: Gagal jika ditemukan Critical/High
          ignore-unfixed: true

      - name: Upload SARIF to GitHub Security Hub
        if: always()
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: 'trivy-results.sarif'

      # Generate SBOM (CycloneDX standard)
      - name: Generate CycloneDX SBOM
        run: |
          syft ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }} -o cyclonedx-json=sbom.cyclonedx.json

      # Cryptographic Signing & Attestation (SLSA Level 3 requirement)
      - name: Sign Image Digest (Keyless)
        run: |
          cosign sign --yes \
            ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}@${{ steps.build-image.outputs.digest }}

      - name: Attest SBOM Predicate
        run: |
          cosign attest --yes \
            --predicate sbom.cyclonedx.json \
            --type cyclonedx \
            ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}@${{ steps.build-image.outputs.digest }}
```

### 7.3 Kubernetes Admission Control: Kyverno Policy
Menjamin pod hanya dapat berjalan jika:
1. Menggunakan digest yang divalidasi oleh Sigstore/Rekor.
2. Identitas OIDC sesuai dengan repositori yang sah.
3. Menjalankan image dengan atribut keamanan terproteksi (*read-only root filesystem*, *run-as-non-root*).

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: verify-image-signature-and-security
  annotations:
    policies.kyverno.io/title: Verify Enterprise Signature & Security Context
    policies.kyverno.io/severity: high
spec:
  validationFailureAction: Enforce
  webhookTimeoutSeconds: 30
  rules:
    - name: verify-sigstore-signature
      match:
        any:
          - resources:
              kinds:
                - Pod
      verifyImages:
        - imageReferences:
            - "ghcr.io/enterprise/secure-app:*"
          attestors:
            - entries:
                - keyless:
                    issuer: "https://token.actions.githubusercontent.com"
                    subject: "https://github.com/enterprise/secure-app/.github/workflows/devsecops.yml@refs/heads/main"
                    rekor:
                      url: "https://rekor.sigstore.dev"
    - name: enforce-pod-hardening
      match:
        any:
          - resources:
              kinds:
                - Pod
      validate:
        message: "Pod wajib non-root dan menggunakan readOnlyRootFilesystem."
        pattern:
          spec:
            securityContext:
              runAsNonRoot: true
            containers:
              - (name): "*"
                securityContext:
                  readOnlyRootFilesystem: true
                  allowPrivilegeEscalation: false
                  capabilities:
                    drop:
                      - ALL
```

### 7.4 Runtime Security Profile: Tetragon (eBPF) Policy
Mencegah eksekusi *interactive shell* atau akses binary berbahaya di dalam container pada runtime secara deterministik.

```yaml
apiVersion: cilium.io/v1alpha1
kind: TracingPolicy
metadata:
  name: block-shell-execution
  namespace: kube-system
spec:
  kprobes:
    - call: "sys_execve"
      syscall: true
      args:
        - index: 0
          type: "string"
      selectors:
        - matchArgs:
            - index: 0
              operator: "Prefix"
              values:
                - "/bin/sh"
                - "/bin/bash"
                - "/usr/bin/bash"
          matchActions:
            - action: Sigkill
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Bank Digital Tier-1 (15 Juta Pengguna Aktif)
- **Kondisi Awal**: Migrasi dari VM ke Kubernetes. Rata-rata *deployment* tertunda 14 hari kerja akibat proses manual CAB (*Change Advisory Board*) yang meninjau laporan scan PDF dari Fortify dan BlackDuck.
- **Serangan Supply Chain**: Sebuah dependensi utilitas parsing internal disusupi kode berbahaya (*typosquatting*) yang mentransfer AWS temporary metadata tokens keluar jaringan cluster saat *pod startup*.
- **Solusi Arsitektur Modern**:
  1. **Automated Cryptographic Attestation**: Penghapusan *approval CAB* manual. Git commit ditandai *verified*, pipeline menghasilkan *signed in-toto attestation* via Cosign.
  2. **Zero-Trust Admission Webhook**: Kyverno deployed dalam mode *High Availability* di multi-region EKS. Container yang tidak memiliki signature dan sertifikat OIDC valid langsung di-*reject* pada level etcd transaction dengan kode status `HTTP 403 Forbidden`.
  3. **eBPF-Based Kernel Enforcement**: Pemasangan Tetragon pada cluster node. Syscall `sys_connect` ke IP eksternal yang berada di luar subnet yang diizinkan langsung menerima instruksi `SIGKILL` dari kernel eBPF program, bahkan sebelum paket keluar dari kartu jaringan virtual (*veth*).
- **Hasil**:
  - *Lead Time to Production* turun drastis dari 14 hari menjadi **35 menit**.
  - Waktu mitigasi kerentanan kritis (*Mean Time to Remediate*) turun dari 72 jam menjadi **2 jam**.
  - 100% *supply chain integrity* terjamin dan lolos audit kepatuhan PCI-DSS 4.0 Sub-requirement 6.4 & 6.5.

---

## 9. Trade-offs

| Opsi Arsitektur | Keuntungan | Kerugian & Konsekuensi | Mitigasi Solusi |
| :--- | :--- | :--- | :--- |
| **Keyless Sigstore (OIDC)** | Tanpa rotasi secret; menghilangkan risiko pencurian private key CI runner. | Sangat bergantung pada ketersediaan eksternal IdP (GitHub OIDC) dan Rekor. | Pasang instans *private Sigstore* di dalam VPC terisolasi untuk enterprise air-gap. |
| **Strict CI Vulnerability Gating** | Menghentikan kode dengan CVE tinggi sebelum masuk registry. | Risiko *false positives* memblokir deployment kritis saat insiden mendesak (*hotfix*). | Mekanisme *vulnerability exception* berbasis VEX (*Vulnerability Exploitability eXchange*). |
| **Read-Only Root Filesystem** | Mencegah penyerang mendownload dan mengeksekusi payload di direktori lokal (`/tmp`). | Aplikasi legacy seringkali gagal start karena butuh menulis data temporer atau log lokal. | Mount *emptyDir memory backed* khusus ke path `/tmp` dengan limit ukuran kecil. |
| **eBPF Kernel Probing** | Deteksi anomali pada tingkat sub-milidetik, tanpa overhead tracing log konvensional. | Penggunaan resource CPU kernel ekstra; risiko *kernel panic* jika konfigurasi BPF verifier tidak kompatibel. | Uji kompatibilitas pada *staging kernel version*; gunakan tool stabil (Tetragon/Falco modern). |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Issue: Kyverno Gagal Memverifikasi Signature Cosign
**Penyebab**: Format referensi image pada Kubernetes Deployment manifest menggunakan *mutable tag* (contoh: `myimage:latest`), sementara Cosign menandatangani OCI *immutable digest* (`myimage@sha256:...`). Webhook kehabisan waktu (*timed out*) mencoba memetakan tag ke digest saat registry sedang mengalami *rate-limiting*.

**Solusi & Perintah Troubleshooting**:
Paksa deployment menggunakan digest atau gunakan fitur *image mutation* pada Kyverno:
```bash
# Cek ketersediaan signature di OCI Registry
cosign verify --certificate-identity-regexp="https://github.com/enterprise/.*" \
              --certificate-oidc-issuer="https://token.actions.githubusercontent.com" \
              ghcr.io/enterprise/secure-app:v1.0.0

# Ambil digest pasti
crane digest ghcr.io/enterprise/secure-app:v1.0.0
```

### 10.2 Issue: Pod CrashLoopBackOff: "Read-only file system"
**Penyebab**: Konfigurasi `readOnlyRootFilesystem: true` diterapkan, namun runtime aplikasi Golang/Java/NodeJS berupaya menulis ke direktori `/tmp` atau `/var/run`.

**Solusi**:
```yaml
# Fix manifest Pod
spec:
  containers:
    - name: app
      image: ghcr.io/enterprise/secure-app@sha256:...
      securityContext:
        readOnlyRootFilesystem: true
      volumeMounts:
        - mountPath: /tmp
          name: tmp-volume
  volumes:
    - name: tmp-volume
      emptyDir:
        medium: Memory
        sizeLimit: 64Mi
```

---

## 11. Best Practices (Production Checklist)

- [ ] **Runner CI Bersih**: Selalu gunakan *ephemeral, single-use runner* untuk mengisolasi proses build SLSA Level 3.
- [ ] **Zero Long-Lived Credentials**: Gantikan static AWS/GCP API Keys dengan *OpenID Connect federation* pada runner CI.
- [ ] **Immutable Base Images**: Pastikan base image distroless di-pin menggunakan `sha256` hash, bukan tag semantic.
- [ ] **Enforce Admission Timeout**: Pastikan webhook Kubernetes timeout dikonfigurasi secara toleran (maksimal 15-30 detik) dan gunakan *high availability* (minimal 3 replika untuk Admission Controller pods).
- [ ] **VEX Documents**: Publikasikan dokumen OpenVEX untuk mendokumentasikan kerentanan dependensi yang *tidak dapat dieksploitasi* (*not-affected*) agar tidak memblokir pipeline secara keliru.
- [ ] **Drop Capabilities**: Hapus seluruh Linux capabilities pada container manifest (`capabilities: drop: ["ALL"]`).
- [ ] **Runtime Syscall Filtering**: Implementasikan profil seccomp `RuntimeDefault` atau custom seccomp profile pada seluruh pod workloads.

---

## 12. Hands-on Practice

Simpan seluruh file praktikum di direktori: `hands-on/m02/`

### File Setup Structure:
```
hands-on/m02/
├── app/
│   ├── main.go
│   ├── go.mod
│   └── Dockerfile
├── policies/
│   ├── kyverno-verify.yaml
│   └── tetragon-exec.yaml
└── test-pipeline.sh
```

### Langkah Praktikum:
1. **Langkah 1**: Buat file aplikasi `hands-on/m02/app/main.go`:
   ```go
   package main
   import (
       "fmt"
       "net/http"
   )
   func main() {
       http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
           fmt.Fprintf(w, "Hello, Authenticated & Secure World!")
       })
       http.ListenAndServe(":8080", nil)
   }
   ```
2. **Langkah 2**: Buat `hands-on/m02/app/Dockerfile` menggunakan contoh *Distroless Multi-stage* dari Bagian 7.1.
3. **Langkah 3**: Eksekusi penandatanganan lokal menggunakan Cosign (menggunakan keypair lokal untuk simulasi testing):
   ```bash
   cd hands-on/m02/
   # Generate testing keypair
   cosign generate-key-pair
   
   # Build local image
   docker build -t localhost:5000/secure-app:test app/
   docker push localhost:5000/secure-app:test

   # Sign image
   cosign sign --key cosign.key localhost:5000/secure-app:test
   ```
4. **Langkah 4**: Terapkan kebijakan Kyverno di cluster Kubernetes minikube/kind:
   ```bash
   kubectl apply -f policies/kyverno-verify.yaml
   ```
5. **Langkah 5**: Lakukan deployment terhadap image yang belum ditandatangani dan verifikasi penolakannya:
   ```bash
   kubectl create deployment reject-test --image=nginx:latest
   # Error expected: Admission webhook "check-image" denied the request
   ```

---

## 13. Exercises

### Level Easy
Konfigurasikan pipeline CI/CD yang menolak artefak jika pemindaian Trivy mendeteksi kerentanan dengan skor CVSS > 8.0, dan ekspor hasilnya ke file log `audit-cve.json`.

### Level Medium
Buat policy Open Policy Agent (OPA/Rego) untuk Conftest yang memvalidasi bahwa manifest Kubernetes tidak menggunakan environment variable yang berisi substring sensitif seperti `_KEY`, `_SECRET`, atau `_PASSWORD`, dan mewajibkan referensi ke `SecretKeyRef`.

### Level Hard
Rancang arsitektur implementasi Sigstore *Private Deployment* untuk infrastruktur perbankan *air-gapped* tanpa koneksi internet langsung. Jelaskan bagaimana Anda mereplikasi Fulcio CA, Rekor Transparency Log, dan NTP time-stamping server di dalam datacenter on-premise, serta sertakan skema OIDC federation menggunakan HashiCorp Vault.

---

## 14. Enterprise Challenge

**Konteks**: Sebuah konglomerat logistik multinasional mengalami insiden di mana penyerang berhasil membobol infrastruktur build runner mereka (CI machine compromise) dan menyuntikkan crypto-miner ke dalam ratusan image aplikasi mikro tanpa mengubah repositori source code Git.

**Tantangan**:
Rancang strategi pertahanan *End-to-End Supply Chain Cryptographic Verification* yang mencakup:
1. **Hermetic Builds**: Isolasi build runner secara total dari jaringan luar saat langkah kompilasi berlangsung.
2. **Dual-Actor Attestation**: Pod admission controller hanya boleh mengizinkan deployment jika image memiliki **dua tanda tangan independen**: satu dari CI automated pipeline, dan satu lagi dari *security gate reviewer* (manual/bot kriptografis).
3. **Reproducible Builds Enforcement**: Bukti bahwa binary dapat dikompilasi ulang secara deterministik dan menghasilkan SHA256 checksum yang identik dari commit Git yang sama.
4. **Automated Incident Response**: Jika runtime detection (eBPF) mendeteksi instruksi CPU berlebih khas mining di node mana pun, lakukan isolasi jaringan Pod secara real-time via CNI, kirim sinyal revocasi sertifikat ke cluster, dan buat tiket audit investigasi otomatis.

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Pertanyaan Basic
1. Apa fungsi utama dari rekaman *transparency log* pada Rekor dalam ekosistem Sigstore?
2. Mengapa base image bertipe *distroless* lebih dianjurkan dibandingkan base image Alpine atau Debian minimal untuk produksi?
3. Pada tahap siklus Kubernetes manakah Validating Admission Webhook dijalankan?
4. Apa kepanjangan dan format data standar dari SBOM yang diakui secara luas oleh industri keamanan sistem perangkat lunak?
5. Mengapa tag image container seperti `:latest` atau `:v1.2` tidak dapat dijadikan jaminan integritas artefak yang aman?

### 15.2 Pertanyaan Intermediate
6. Jelaskan bagaimana mekanisme pertukaran OIDC token pada Sigstore Fulcio dapat menghilangkan kebutuhan penyimpanan sertifikat jangka panjang (*long-lived private keys*)!
7. Apa perbedaan mendasar antara model kerja OPA Gatekeeper dengan Kyverno dalam pemrosesan mutasi dan validasi manifest Kubernetes?
8. Bagaimana program eBPF mendeteksi intrusi keamanan di dalam container secara lebih efisien dibandingkan daemon audit konvensional (seperti Linux `auditd`)?
9. Apa fungsi file deskripsi *in-toto attestation* dan apa signifikansinya terhadap kepatuhan standar SLSA Framework level 3?
10. Jika webhook Kyverno/Gatekeeper mengalami *outage* atau tidak dapat dihubungi oleh API Server, apa dampak dari parameter konfigurasi `failurePolicy: Fail` vs `failurePolicy: Ignore`?

### 15.3 Skenario Kasus Produksi
11. **Kasus 1**: Tim SRE Anda mendapati webhook Validating Admission Controller meningkatkan latensi pembuatan Pod dari rata-rata 300ms menjadi 18 detik, yang menyebabkan auto-scaler (HPA) gagal merespons lonjakan trafik. Di mana kemungkinan letak *bottleneck* arsitekturnya dan bagaimana cara memperbaikinya tanpa menonaktifkan keamanan?
12. **Kasus 2**: Scanner Trivy Anda di CI/CD mendeteksi kerentanan kritis CVE baru pada libssl dalam base image distroless yang digunakan 80 microservice. Vendor upstream belum merilis patch versi terbaru, namun fungsi yang rentan tersebut tidak pernah dipanggil oleh kode aplikasi Anda. Tindakan arsitektural apa yang harus diambil agar rilis fitur bisnis tidak terhenti tanpa melanggar kebijakan audit?
13. **Kasus 3**: Container runtime pada node mendeteksi ada upaya manipulasi file `/etc/shadow` di dalam container, namun Kyverno tidak mengeluarkan log peringatan apa pun dan status Pod tetap running. Mengapa hal ini bisa terjadi dan sistem proteksi layer mana yang seharusnya bertugas menangani insiden ini?

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Jawaban Basic:
1. **Rekor Transparency Log**: Menyediakan catatan bukti kriptografis penandatanganan yang *tamper-evident*, *immutable*, dan publik berbasis Merkle Tree sehingga pihak ketiga dapat memverifikasi kapan dan oleh siapa artefak ditandatangani tanpa bergantung pada kejujuran satu pihak.
2. **Distroless**: Tidak memiliki shell, package manager, atau utilitas sistem standar (seperti `curl`, `wget`, `cat`), sehingga mengurangi *attack surface* secara drastis dan mencegah penyerang memanfaatkan perkakas OS untuk *lateral movement*.
3. **Validating Admission Phase**: Dijalankan setelah request di-autentikasi (*Authentication*), di-otorisasi (*RBAC*), dan dimutasi (*Mutating Admission*), tepat sebelum metadata objek ditulis (*persisted*) ke database etcd.
4. **CycloneDX** dan **SPDX** dalam format JSON atau XML. SBOM merupakan manifes detail seluruh komponen, library open-source, dependensi langsung maupun transitif sebuah software.
5. **Tag Bersifat Mutable**: Tag dapat ditimpa (*overwritten*) di registry tanpa mengubah nama tag tersebut. Hanya cryptographic digest (SHA-256) yang bersifat immutable dan merepresentasikan kondisi fisik artefak yang sebenarnya.

#### Jawaban Intermediate:
6. **Keyless Signing Mekanisme**: Pipeline CI meminta token identitas OIDC berumur sangat pendek ke penyedia identitas (GitHub/GitLab). Token ini diserahkan ke Fulcio CA. Fulcio memvalidasi klaim OIDC lalu menerbitkan sertifikat X.509 sementara (~10 menit) yang memetakan identitas runner dengan ephemeral public key. Begitu penandatanganan selesai, private key lokal langsung dihapus. Bukti dicatat di Rekor, sehingga validasi masa depan hanya bergantung pada log Rekor dan sertifikat root Fulcio.
7. **OPA Gatekeeper vs Kyverno**: OPA Gatekeeper menggunakan bahasa deklaratif Rego yang berjalan di atas VM OPA terpisah dan memerlukan konversi CRD ConstraintTemplate. Kyverno dirancang native Kubernetes; seluruh aturan didefinisikan murni menggunakan sintaks deklaratif YAML tanpa bahasa pemrograman baru, serta memiliki kapabilitas mutasi dan generasi resource K8s yang lebih fleksibel.
8. **eBPF vs Auditd**: Auditd bergantung pada pengiriman log melalui netlink socket ke user space yang rentan terhadap *event dropping* saat workload tinggi dan memiliki overhead context-switching yang mahal. eBPF berjalan langsung di kernel space, memfilter event di tingkat function hook, dan dapat memicu aksi protektif (seperti mematikan proses via `SIGKILL`) secara real-time sebelum instruksi syscall berbahaya selesai dieksekusi.
9. **in-toto Attestation**: Metadata terstruktur yang ditandatangani yang membuktikan rantai integritas: commit hash mana yang dipakai, runner mana yang mengeksekusi, parameter apa yang dipassing, dan hash SBOM yang diproduksi. Ini membuktikan bahwa artefak diproduksi oleh pipeline yang sah tanpa adanya proses tampering di tengah jalan (SLSA non-falsifiable provenance).
10. **FailurePolicy**: `failurePolicy: Fail` akan memblokir seluruh operasi pembuatan pod jika webhook admission tidak merespons (mengutamakan *security* dibanding *availability*). Sebaliknya, `failurePolicy: Ignore` akan meloloskan request tanpa inspeksi jika webhook mati (mengutamakan *availability* namun mematikan *security gate*).

#### Jawaban Skenario Kasus Produksi:
11. **Analisis Kasus 1**:
    *   *Bottleneck*: Webhook melakukan *network call* eksternal secara sinkron ke OCI Registry atau Sigstore Rekor publik pada setiap siklus replikasi pod tanpa proses caching.
    *   *Solusi*: 
        1) Terapkan cache lokal/in-memory pada Kyverno untuk menyimpan status verifikasi digest yang sudah terverifikasi.
        2) Ubah kebijakan admission untuk memverifikasi digest yang sudah di-resolve oleh mutating webhook sebelumnya daripada meminta webhook menghubungi network luar setiap kali replika baru spawn.
        3) Naikkan kapasitas CPU/Memori dan pastikan replika pod admission controller terdistribusi merata dengan resource request yang memadai.
12. **Analisis Kasus 2**:
    *   *Solusi*: Gunakan standar **VEX (Vulnerability Exploitability eXchange)**.
    *   *Langkah*: Buat dokumen VEX (misal: via format CSAF atau CycloneDX VEX) dengan status `not_affected` dan justifikasi `code_not_reachable` atau `inline_mitigations_exist`.
    *   *Implementasi*: Sertakan dokumen VEX tersebut ke dalam pipeline verifikasi Trivy menggunakan flag `--vex`. Dengan demikian, scanner akan secara sah mengabaikan CVE tersebut dalam kalkulasi kegagalan gate tanpa perlu menurunkan standar severity threshold ke level rendah.
13. **Analisis Kasus 3**:
    *   *Penyebab*: Kyverno adalah *Admission Controller* yang hanya bekerja pada fase **Pre-Run (Deploy time)** untuk mengevaluasi spesifikasi deklaratif manifest API. Setelah Pod berjalan di node, Kyverno tidak memiliki kapabilitas memantau operasi file atau proses kernel container secara real-time.
    *   *Solusi*: Lapisan pertahanan yang bertanggung jawab adalah **Runtime Security berbasis eBPF/Kernel Monitoring (Tetragon atau Falco)**. Konfigurasikan *TracingPolicy* kernel probe untuk memonitor syscall seperti `sys_openat` atau `sys_write` pada path sensitif `/etc/*`, lalu atur aksi otomatis `SIGKILL` terhadap container PID yang melanggar.

---

## 16. Summary

Implementasi DevSecOps tingkat enterprise modern menuntut transisi total dari scanning reaktif menjadi sistem pertahanan yang deterministik dan terverifikasi secara kriptografis:
1. **Integritas Rantai Pasok**: Penggunaan standar SLSA, SBOM CycloneDX, dan penandatanganan keyless via Sigstore memastikan bahwa seluruh artefak yang dieksekusi di cluster produksi terbukti berasal dari repositori dan pipeline yang sah.
2. **Policy-as-Code Terintegrasi**: Kyverno dan OPA bertindak sebagai *gatekeeper* deterministik yang menolak konfigurasi tidak aman dan artefak yang tidak terotentikasi langsung pada fase admission sebelum resource masuk ke etcd.
3. **Observabilitas & Pencegahan Runtime**: Keamanan container tidak berakhir saat lulus deployment; instrumentasi tingkat kernel berbasis eBPF (Tetragon) memberikan proteksi real-time terhadap payload zero-day dan malicious syscall, melengkapi postur pertahanan Zero-Trust secara menyeluruh.