# BAB 07: Container Hardening & Image Security
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Merancang dan mengimplementasikan rantai pasok kontainer (*container supply chain*) yang aman berbasis prinsip *Zero Trust* dan *Defense-in-Depth*.
- Mengonfigurasi dan mengoptimalkan *multi-stage builds* menggunakan *base image* minimalis (*distroless* dan *scratch*) untuk meminimalisasi *attack surface*.
- Mengotomatisasi pembuatan *Software Bill of Materials* (SBOM) berstandar SPDX/CycloneDX serta pemindaian kerentanan (CVE) pada pipeline CI/CD.
- Menerapkan penandatanganan citra kriptografis (*image signing*) dan *attestation* menggunakan Cosign/Sigstore secara *keyless* via OIDC.
- Mengonfigurasi *runtime hardening* pada level OCI container: pembatasan Linux Capabilities, *Read-Only Root Filesystem*, Seccomp, dan AppArmor profile.
- Menegakkan kebijakan keamanan kluster secara preventif menggunakan *Kubernetes Admission Controller* (Kyverno / OPA Gatekeeper) untuk memblokir kontainer yang tidak terverifikasi atau tidak patuh standar CIS Benchmark.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
- **Containerization Fundamentals:** Pemahaman mendalam tentang Docker/OCI image layer, storage drivers (OverlayFS), dan arsitektur runtime (containerd/CRI-O).
- **Linux Kernel Primitives:** Konsep namespaces (PID, Mount, Net, IPC, UTS, User), Control Groups (cgroups v2), dan Security Modules (LSM: AppArmor/SELinux).
- **CI/CD Pipeline Engine:** Pengalaman mengonfigurasi GitHub Actions, GitLab CI, atau Tekton Pipelines.
- **Kubernetes Architecture:** Memahami alur kerja kube-apiserver, Mutating/Validating Admission Webhooks, dan Custom Resource Definitions (CRD).
- **Public Key Cryptography & PKI:** Konsep dasar asymmetric encryption, X.509 certificates, OIDC tokens, dan hashing (SHA-256).

---

### 3. Concept & Internal Architecture (Mendalam)

Keamanan kontainer bukan sekadar "tidak menjalankan aplikasi sebagai root di Dockerfile". Kontainer pada level kernel Linux hanyalah proses terisolasi yang berbagi satu kernel host. Jika batas isolasi (*isolation boundary*) ini runtuh, sebuah insiden *container escape* dapat mengorbankan seluruh infrastruktur node host.

```
+-------------------------------------------------------------------------------+
| HOST OS KERNEL (Shared Kernel Architecture)                                   |
| +---------------------------------------------------------------------------+ |
| | cgroups v2 | Namespaces (PID, Mount, Net, User, IPC) | LSM (AppArmor, BPF)| |
| +---------------------------------------------------------------------------+ |
|        ^                                    ^                                 |
|        | (Syscalls mediated by Seccomp)     | (Restricted Capabilities)       |
| +--------------------+            +--------------------+                      |
| | Container A        |            | Container B        |                      |
| | (Hardened Runtime) |            | (Standard Default) |                      |
| | - Read-Only RootFS |            | - R/W Filesystem   |                      |
| | - Distroless Image |            | - Debian/Ubuntu OS |                      |
| | - Non-root (UID >0)|            | - Root (UID 0)     |                      |
| | - Drop ALL Caps    |            | - Default Caps     |                      |
| +--------------------+            +--------------------+                      |
+-------------------------------------------------------------------------------+
```

#### A. Linux Isolation Primitives & Attack Surface
1. **Namespaces:** Membatasi apa yang *dapat dilihat* oleh proses. Namun, User Namespace sering kali tidak diaktifkan secara default pada banyak managed Kubernetes nodes, yang berarti `UID 0` di dalam kontainer dipetakan langsung ke `UID 0` di kernel host.
2. **Cgroups (Control Groups):** Membatasi apa yang *dapat dikonsumsi* oleh proses (CPU, Memory, PIDs, I/O). Kegagalan membatasi `pids.max` membuka celah serangan *fork bomb* yang membekukan host kernel.
3. **Linux Capabilities:** Memecah kekuasaan absolut superuser `root` menjadi 41 kapabilitas diskrit (misalnya, `CAP_SYS_ADMIN`, `CAP_NET_RAW`, `CAP_CHOWN`). Sebagian besar kontainer mikroservis backend hanya memerlukan 0 hingga 2 kapabilitas. Membiarkan kapabilitas default (`CAP_NET_RAW`, `CAP_MKNOD`, dll.) mempermudah eskalasi hak akses jika eksploitasi kode terjadi.
4. **Syscall Filtering (Seccomp):** Membatasi *system calls* yang dapat diajukan proses ke host kernel. Kernel Linux memiliki lebih dari 400 syscalls; aplikasi web standar umumnya hanya menggunakan sekitar 40-70 syscalls. Seccomp default Docker/CRI memblokir sekitar 44 syscalls berbahaya, namun profil kustom *least-privilege* jauh lebih aman.

#### B. Anatomi OCI Image & Insecurity Immutability
OCI Image tersusun dari tarballs yang ditumpuk (*stacked layers*) secara read-only dengan hashing SHA-256. Masalah umum:
- **Tainted Layers:** Menghapus file sensitif (misal: private key atau API token) di *layer* berikutnya menggunakan `RUN rm -rf /secret` **tidak menghapus** file tersebut dari layer sebelumnya. Artifact tetap dapat diekstraksi dari layer bawah.
- **Base Image Bloat:** Image berbasis `ubuntu:latest` atau `golang:latest` menyertakan package manager (`apt`), shell (`/bin/sh`, `/bin/bash`), coreutils (`curl`, `nc`, `wget`), dan ratusan dependensi C (glibc) yang tidak dibutuhkan saat runtime, melipatgandakan metrik CVE (Common Vulnerabilities and Exposures).

#### C. Supply Chain Cryptographic Verification Lifecycle
Arsitektur keamanan modern tidak mempercayai nama tag (`myapp:v1.0.0`) karena tag bersifat *mutable* (dapat ditimpa). Keamanan rantai pasok berbasis digest *immutable* (`myapp@sha256:...`) yang digabungkan dengan **Cryptographic Attestations**:

```
+-----------+      +-------------------+      +--------------------+      +--------------------+
|  Build    | ---> | Generate SBOM     | ---> | Scan Vulnerability | ---> | Sign & Attest      |
|  (kaniko/ |      | (Syft / CycloneDX)|      | (Trivy / Grype)    |      | (Cosign / Keyless) |
|   buildx) |      +-------------------+      +--------------------+      +--------------------+
+-----------+                                                                        |
                                                                                     v
+------------------+         +----------------------+                     +--------------------+
| Pod Admitted to  | <------ | Admission Controller | <------------------ | Push to OCI Reg.   |
| K8s Runtime Node | (Allow) | (Kyverno Policy)     | (Verify Signature & | (Image, Sig, SBOM, |
+------------------+         +----------------------+  Verify Attestation)|  Attestation layer)|
                                        | (Reject if Invalid)             +--------------------+
                                        v
                             [ DROP / QUARANTINE ]
```

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional | Pendekatan Enterprise DevSecOps |
| :--- | :--- | :--- |
| **Base Image** | OS Lengkap (Ubuntu, Alpine, Debian) dengan package manager. | Minimalis / *Distroless* / *Scratch*, tanpa shell, tanpa package manager. |
| **User Context** | Dijalankan sebagai default (`root` / UID 0) untuk kemudahan port binding. | Strict non-root UID eksplisit (misal: UID 10001), `runAsNonRoot: true`. |
| **Filesystem** | Read-Write, aplikasi dapat menulis ke direktori mana pun. | Read-Only Root Filesystem. Tulis hanya ke `emptyDir` in-memory (`tmpfs`). |
| **Vulnerability Mgmt**| Scanning periodik manual atau mingguan di registry. | *Shift-left*: Scan otomatis pada PR, build break on Critical/High CVE, continuous runtime monitoring. |
| **Image Integrity** | Verifikasi nama tag (`:release-v2.1`). | Verifikasi hash digest kriptografis, verifikasi tanda tangan Cosign via Rekor/Fulcio PKI transparency log. |
| **Container Admission**| Mengizinkan image apa pun ditarik dari public registry (Docker Hub). | Zero Trust Admission Control: Hanya image bertanda tangan internal yang diverifikasi policy engine yang boleh berjalan di kluster. |

---

### 5. How (Workflow Detail)

Implementasi rantai pasok aman mengadopsi alur berikut:

1. **Phase 1: Code to Artifact Isolation (Build Pipeline)**
   - Gunakan *multi-stage builds*. Stage pertama bertindak sebagai *builder* (memuat compiler, SDK, tools).
   - Salin hanya *binary executable* hasil kompilasi dan dependensi runtime absolut ke stage produksi berbasis `gcr.io/distroless/*`.
   - Set konfigurasi user secara eksplisit (`USER 65532:65532`).

2. **Phase 2: Automated SBOM & Vulnerability Gate**
   - Hasilkan SBOM dalam format SPDX/CycloneDX menggunakan utility seperti `syft`.
   - Pindai base image dan layer aplikasi menggunakan `trivy`. Jika terdeteksi kerentanan dengan level `CRITICAL` atau `HIGH` dengan patch yang tersedia, hentikan pipeline (`exit 1`).

3. **Phase 3: Cryptographic Signing & Attestation (Sigstore Ecosystem)**
   - Gunakan Cosign dengan alur *keyless* memanfaatkan OIDC token dari CI/CD provider (misalnya GitHub/GitLab).
   - Rekor menerima metadata tanda tangan secara transparan (*Transparency Log*).
   - Lampirkan hasil scan vulnerabilitas dan SBOM sebagai *attestation* langsung ke registry OCI sebagai *in-toto statement*.

4. **Phase 4: Gatekeeping on Orchestrator (Deployment)**
   - Saat deployment dikirim ke Kubernetes, `Admission Controller` (Kyverno) mencegat request.
   - Kebijakan memverifikasi apakah digest image telah ditandatangani oleh sertifikat OIDC pipeline yang sah.
   - Kebijakan memverifikasi bahwa attestation vulnerability scan menyatakan 0 CVE berstatus Critical.
   - Jika validasi lolos, pods dijadwalkan; jika tidak, API server menolak deployment secara instan.

5. **Phase 5: Runtime Defense Enforcement**
   - Pod Security Standards (PSS) enforced pada level `restricted`.
   - Security context wajib mengimplementasikan: `readOnlyRootFilesystem: true`, `allowPrivilegeEscalation: false`, `capabilities: { drop: ["ALL"] }`.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Bandara Internasional Super-Maksimum
- **Standard Container:** Penumpang membawa koper besar tanpa diperiksa, membawa pisau lipat (shell/bash), toolkit pertukangan (package manager), dan bebas masuk ke ruang kokpit (root UID).
- **Distroless Container:** Penumpang hanya mengenakan pakaian seragam steril tanpa saku (tanpa shell, tanpa package manager, non-root).
- **Image Signature & Attestation:** Paspor biometrik dengan visa digital yang divalidasi oleh imigrasi pusat; tidak ada penumpang yang dapat naik ke pesawat jika tidak memiliki cap digital resmi dari instansi pemerintah (CI/CD Pipeline).
- **Read-Only Root Filesystem:** Penumpang duduk di kursi yang terkunci; tidak diizinkan mengubah struktur kabin pesawat. Jika butuh menulis, hanya disediakan papan tulis mini yang akan dihapus total begitu mendarat (`tmpfs`).

#### Diagram Arsitektur Interaksi:

```
[ DEVELOPER ]
      |
      | (1) git push
      v
[ CI/CD PIPELINE (GitHub Actions / GitLab CI) ]
      |
      +---> (2) Build Multistage (BuildKit) ---> [ Scratch/Distroless Binary ]
      |
      +---> (3) Syft Scan ---> [ SBOM.json (CycloneDX) ]
      |
      +---> (4) Trivy Scanner ---> Validasi Threshold CVE (Fail on Critical)
      |
      +---> (5) Cosign Sign (OIDC ID Token via Fulcio/Rekor)
      |
      +---> (6) Push OCI Artifacts (Image + Sig + SBOM Attestation)
                                 |
                                 v
                 [ ENTERPRISE OCI CONTAINER REGISTRY ]
                 - app@sha256:abcd... (Image)
                 - app:sha256-abcd.sig (Cosign Signature)
                 - app:sha256-abcd.att (In-Toto Attestation)
                                 |
                                 v (7) kubectl apply
                 [ KUBERNETES CONTROL PLANE ]
                                 |
        +------------------------+-------------------------+
        | Kube-API Server                                  |
        |   |                                              |
        |   v (Admission Webhook Request)                  |
        | [ KYVERNO / OPA GATEKEEPER ]                     |
        |   - Validasi Tanda Tangan Cosign                 |
        |   - Validasi Status CVE Scan                     |
        |   - Enforce SecurityContext: Restricted          |
        +------------------------+-------------------------+
                                 | (8) If Valid: Allow Pod Creation
                                 v
                 [ WORKER NODE RUNTIME ENGINE ]
                 - containerd -> runc
                 - Non-root UID, Capabilities DROP ALL
                 - ReadOnly Root Filesystem + AppArmor Profile
```

---

### 7. Simple Example & Practical Example

#### A. Multi-Stage Distroless Hardened Dockerfile (Golang Implementation)
File: `Dockerfile`

```dockerfile
# ==========================================
# STAGE 1: Build Environment
# ==========================================
FROM golang:1.22-bookworm AS builder

# Buat grup dan user unprivileged untuk ditransfer ke final stage
RUN echo "appuser:x:10001:10001:Application User:/:/sbin/nologin" > /etc/passwd_app && \
    echo "appuser:x:10001:" > /etc/group_app

WORKDIR /workspace

# Optimasi caching dependency
COPY go.mod go.sum ./
RUN go mod download && go mod verify

COPY . .

# Kompilasi binary statis:
# - CGO_ENABLED=0: Mencegah linking dinamis terhadap glibc host
# - -ldflags="-s -w": Menghapus symbol table dan DWARF debugging info (memperkecil binary)
# - -trimpath: Menghapus absolute path direktori lokal mesin build dari binary
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build \
    -ldflags="-s -w -extldflags '-static'" \
    -trimpath \
    -o /workspace/bin/secure-service ./cmd/api

# ==========================================
# STAGE 2: Distroless Minimal Runtime
# ==========================================
# Menggunakan Google Distroless Static (tanpa shell, tanpa package manager, tanpa C runtime)
FROM gcr.io/distroless/static-debian12:nonroot

WORKDIR /app

# Ambil metadata user dari Stage 1
COPY --from=builder /etc/passwd_app /etc/passwd
COPY --from=builder /etc/group_app /etc/group

# Salin binary yang sudah terkompilasi
COPY --from=builder --chown=10001:10001 /workspace/bin/secure-service /app/secure-service

# Gunakan non-root user eksplisit
USER 10001:10001

# Hindari EXPOSE port di bawah 1024 (memerlukan CAP_NET_BIND_SERVICE)
EXPOSE 8080

ENTRYPOINT ["/app/secure-service"]
```

#### B. Pipeline Integrasi CI: Generate SBOM, Scan, Sign, Attest
File: `.github/workflows/secure-pipeline.yml`

```yaml
name: Enterprise Secure Container Pipeline

on:
  push:
    branches: [ "main" ]

permissions:
  contents: read
  packages: write
  id-token: write # Diperlukan untuk Cosign OIDC Keyless signing

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}/secure-service

jobs:
  build-and-secure:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Source Code
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract Metadata (Tags, Labels)
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=sha,format=long

      # Build & Push Image menggunakan Immutable Digest
      - name: Build and Push Docker Image
        id: build-push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}

      - name: Install Cosign & Syft
        uses: sigstore/cosign-installer@v3.4.0

      - name: Install Syft
        run: |
          curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh -s -- -b /usr/local/bin

      - name: Generate CycloneDX SBOM
        run: |
          syft ${{ steps.build-push.outputs.imageid }} -o cyclonedx-json=sbom.json

      - name: Scan Vulnerabilities with Trivy
        uses: aquasecurity/trivy-action@0.18.0
        with:
          image-ref: ${{ steps.build-push.outputs.imageid }}
          format: 'sarif'
          output: 'trivy-results.sarif'
          severity: 'CRITICAL,HIGH'
          exit-code: '1' # Build gagal jika ada CVE Critical/High yang unpatched
          ignore-unfixed: true

      - name: Sign Image (Keyless with OIDC)
        run: |
          cosign sign --yes ${{ steps.build-push.outputs.imageid }}

      - name: Attest SBOM to Registry
        run: |
          cosign attest --yes \
            --predicate sbom.json \
            --type cyclonedx \
            ${{ steps.build-push.outputs.imageid }}
```

#### C. Runtime Hardening: Kubernetes Pod & Kyverno Policy

##### 1. Manifest Deployment Ter-Hardening
File: `k8s/deployment.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: secure-service-deployment
  namespace: production
  labels:
    app.kubernetes.io/name: secure-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: secure-service
  template:
    metadata:
      labels:
        app: secure-service
    spec:
      # Hindari automount token jika pods tidak memanggil Kube-API
      automountServiceAccountToken: false
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
        runAsGroup: 10001
        fsGroup: 10001
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: service
          image: ghcr.io/organization/secure-service@sha256:7b7f5c9e2b1f81cf...
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 8080
          resources:
            limits:
              cpu: "500m"
              memory: "256Mi"
            requests:
              cpu: "100m"
              memory: "64Mi"
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop:
                - ALL
          volumeMounts:
            # Mount in-memory ephemeral storage untuk file temporer
            - name: temp-storage
              mountPath: /tmp
      volumes:
        - name: temp-storage
          emptyDir:
            medium: Memory
            sizeLimit: 64Mi
```

##### 2. Kyverno Cluster Policy: Menolak Image Tanpa Validasi Tanda Tangan
File: `k8s/kyverno-verify-image.yaml`

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: verify-image-signature
spec:
  validationFailureAction: Enforce
  webhookTimeoutSeconds: 30
  rules:
    - name: verify-signature-and-issuer
      match:
        any:
          - resources:
              kinds:
                - Pod
              namespaces:
                - production
      verifyImages:
        - imageReferences:
            - "ghcr.io/organization/*"
          attestors:
            - entries:
                - keyless:
                    subject: "https://github.com/organization/*"
                    issuer: "https://token.actions.githubusercontent.com"
                    rekor:
                      url: https://rekor.sigstore.dev
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: Lembaga Finansial (Payment Gateway)
Sebuah perusahaan Unicorn Payment Gateway memproses rata-rata 4.500 transaksi per detik (TPS). Mereka mengoperasikan 12 kluster Kubernetes (EKS) yang tersebar di multi-region untuk memenuhi kepatuhan PCI-DSS 4.0 Sub-Requirement 6.4 (Public-facing web applications protection & software security supply chain).

#### Vektor Insiden (Pra-Implementasi)
Audit independen menemukan kerentanan pada container pipeline:
1. Pengembang menggunakan base image `golang:1.18` (berukuran ~1.2GB) yang berisi lebih dari 800 sistem paket Linux usang dengan 42 Critical CVE.
2. Kontainer berjalan sebagai `root` dengan hak akses read-write pada filesystem.
3. Node EKS dieksploitasi dalam simulasi Red Team: sebuah exploit *Arbitrary File Upload* pada aplikasi backend memungkinkan penyerang menulis executable ELF ke direktori `/app/uploads` dan mengeksekusinya via Reverse Shell. Karena shell (`/bin/sh`) tersedia di base image dan kontainer berjalan sebagai root tanpa mitigasi AppArmor/Capabilities, penyerang berhasil mengakses metadata instance AWS dan membocorkan IAM credentials.

#### Solusi Arsitektur DevSecOps Skala Enterprise
1. **Refactoring Base Image:**
   - Seluruh 140+ mikroservis dialihkan ke *distroless/static* atau *scratch*.
   - Ukuran citra rata-rata dipangkas dari 1.2 GB menjadi 18 MB.
   - Attack surface berkurang drastis: tidak ada shell (`sh`, `bash`), utility jaringan (`curl`, `nc`), ataupun compiler/interpreter pada container production.

2. **Supply Chain Gate:**
   - Memasukkan Syft dan Trivy ke GitHub Actions runners lokal terisolasi.
   - Implementasi Cosign OIDC Keyless signing yang terikat ke enterprise GitHub Org identity.
   - Pendaftaran image hanya diizinkan ke AWS ECR privat yang dienkripsi dengan KMS kustom.

3. **Admission Control & Runtime Immutability:**
   - Penerapan Kyverno di level Admission Controller; kluster otomatis menolak *manifest* yang mengarah ke tag `latest` atau digest yang tidak memiliki tanda tangan GitHub Actions tim Core Engineering.
   - Pengaturan `readOnlyRootFilesystem: true` secara global. Upaya eksploitasi Red Team untuk menulis file biner ke direktori mana pun langsung memicu error kernel `EROFS (Read-only file system)` dan menggagalkan serangan sebelum payload aktif.

#### Dampak Bisnis & Operasional
- **Metrik CVE:** Pengurangan total kerentanan CVE pada seluruh armada kontainer sebesar **98.4%**.
- **Performa Penarikan Image (MTTR):** Waktu *cold pull* image pada autoscaling (HPA) node berkurang dari rata-rata **48 detik** menjadi **3.2 detik**, meningkatkan elastisitas saat lonjakan transaksi mendadak.
- **Audit Compliance:** PCI-DSS 4.0 lolos audit tanpa temuan deviasi rantai pasok software.

---

### 9. Trade-offs

Mengadopsi postur hardening tingkat lanjut memunculkan trade-off struktural yang wajib diantisipasi:

| Aspek | Tanpa Hardening (Default) | Extreme Hardened (Distroless, RO RootFS, Sign) | Analisis Trade-off |
| :--- | :--- | :--- | :--- |
| **Kemudahan Debugging** | **Tinggi:** Sederhana, teknisi cukup melakukan `kubectl exec -it <pod> -- /bin/bash` dan menjalankan `curl`, `netstat`. | **Sangat Rendah:** Tidak ada shell, tidak ada utility sistem. `kubectl exec` akan gagal (`OCI runtime exec failed: exec: "sh": executable file not found in $PATH`). | Membutuhkan adopsi *Ephemeral Debug Containers* (`kubectl debug -it <pod> --image=busybox --target=<container>`) yang menuntut pelatihan baru bagi tim SRE/Operations. |
| **Pipeline Latency** | **Cepat:** Docker build sederhana selesai dalam hitungan detik/menit tanpa validasi lanjutan. | **Menengah-Lambat:** SBOM generation, vulnerability scanning, dan OIDC cryptographic signing menambah 2–5 menit per pipeline execution. | Memerlukan caching agresif untuk layer OCI dan basis data vulnerabilitas lokal/in-cluster untuk menjaga *developer velocity*. |
| **Kompatibilitas Aplikasi**| **Sangat Fleksibel:** Framework apa pun berjalan lancar (Spring, Node, Python) karena file-file temporer bebas dibuat di mana saja. | **Ketat:** Banyak library atau agent (misal: Datadog/NewRelic APM, Java JVM hsperfdata, temporary caches) gagal berjalan di *Read-Only RootFS*. | Tim developer harus memetakan semua jalur IO aplikasi dan me-mount `emptyDir` mount-points secara eksplisit ke `/tmp`, `/var/log`, atau direktori cache. |
| **Operational & Cost** | **Biaya Minimal:** Cukup satu private registry standar. | **Biaya Tambahan:** Biaya infrastruktur untuk admission webhook reliability (HA Kyverno), storage untuk attestation/SBOM layer di registry. | Jika Admission Controller down dan diset ke policy `fail-close`, deployment kluster terhenti total. Perlu redundansi controller yang memadai. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan: `readOnlyRootFilesystem: true` Menyebabkan Crash-Loop Aplikasi
- **Gejala:** Kontainer langsung berhenti sesaat setelah start dengan status `CrashLoopBackOff`. Log mencatat: `java.io.IOException: Read-only file system` atau `open /tmp/app.pid: read-only file system`.
- **Akar Masalah:** Runtime environment (JVM, Node.js, Python, atau NGINX) memerlukan direktori sementara untuk menulis PID file, buffering, atau lock files.
- **Troubleshooting:**
  Identifikasi lokasi penulisan aplikasi melalui container runtime logs, kemudian sediakan volume `tmpfs` non-persistent:
  ```yaml
  volumeMounts:
    - name: app-temp
      mountPath: /tmp
    - name: app-logs
      mountPath: /app/logs
  volumes:
    - name: app-temp
      emptyDir: {}
    - name: app-logs
      emptyDir: {}
  ```

#### 2. Kesalahan: Mengubah Non-Root UID Namun Port Bind Gagal (Permission Denied)
- **Gejala:** Aplikasi gagal mengikat port jaringan: `listen tcp :80: bind: permission denied`.
- **Akar Masalah:** Port di bawah 1024 dianggap sebagai *Privileged Ports* di Linux. Pengguna non-root (UID selain 0) tidak dapat melakukan *bind* pada port tersebut tanpa kapabilitas kernel `CAP_NET_BIND_SERVICE`.
- **Troubleshooting:**
  - *Cara Terbaik:* Ubah aplikasi untuk mendengarkan port unprivileged di atas 1024 (misal: 8080, 8443).
  - *Alternatif:* Jika wajib menggunakan port di bawah 1024, berikan kapabilitas eksplisit di manifest pods:
    ```yaml
    securityContext:
      capabilities:
        drop: ["ALL"]
        add: ["NET_BIND_SERVICE"]
    ```

#### 3. Kesalahan: Gagal Memverifikasi Tanda Tangan Cosign di Admission Controller (Timeout)
- **Gejala:** Deployment ditolak oleh admission controller dengan pesan error: `failed to verify signature: remote verification error: GET https://rekor.sigstore.dev/...: i/o timeout`.
- **Akar Masalah:** Node Kubernetes / namespace admission controller tidak memiliki akses egress internet menuju transparency log publik Sigstore (Rekor/Fulcio).
- **Troubleshooting:**
  - Buka firewall egress port 443 ke endpoint Sigstore.
  - Untuk jaringan *air-gapped* atau isolasi total (VPC internal), gunakan model tanda tangan Cosign berbasis *Private/Public Key Pair* statis via Kubernetes Secret, atau buat infrastruktur Sigstore privat (Private Rekor/Fulcio instances).

---

### 11. Best Practices (Production Checklist)

Gunakan checklist ini sebagai *Production Readiness Gate* untuk setiap kontainer yang akan dirilis:

- [ ] **Minimalis Base Image:** Menggunakan `scratch`, Google Distroless, atau Chainguard images. Dilarang keras menyertakan distro penuh seperti Ubuntu/Debian di production runtime pods.
- [ ] **Multi-stage Construction:** Build dependencies (SDK, headers, compilers) tidak tertinggal pada target image akhir.
- [ ] **Non-Root Execution:** Pengaturan `USER <UID>` non-root pada Dockerfile dan dipertegas via Pod `securityContext.runAsNonRoot: true` (Gunakan UID > 10000).
- [ ] **Privilege Escalation Blocked:** Konfigurasi `allowPrivilegeEscalation: false` diaktifkan secara eksplisit untuk mencegah child processes mendapatkan privilege lebih tinggi dari parent process.
- [ ] **Capabilities Dropped:** Semua Linux capabilities dilepas secara absolut via `drop: ["ALL"]`. Hanya sertakan kapabilitas yang secara objektif dibutuhkan sistem.
- [ ] **Immutable Filesystem:** Mengaktifkan `readOnlyRootFilesystem: true`. Direktori dinamis dipetakan ke ephemeral `emptyDir` memory.
- [ ] **Immutable Image Digest:** Deployment menggunakan referensi SHA-256 Digest (`image@sha256:...`) bukan mutable tag seperti `:latest` atau `:v1.2`.
- [ ] **Automated SBOM & CVE Gating:** SBOM di-generate setiap build; pipeline otomatis *halt* jika ada kerentanan `CRITICAL` atau `HIGH` dengan status *fix available*.
- [ ] **Cryptographic Attestation:** Image ditandatangani secara kriptografis (Cosign) dan diverifikasi oleh Admission Webhook (Kyverno/OPA) sebelum scheduling.
- [ ] **Resource Bound:** Setiap kontainer wajib memiliki `limits` dan `requests` (CPU dan Memory) serta PID limits untuk mencegah *Denial-of-Service* pada node kernel.

---

### 12. Hands-on Practice

Tujuan: Membangun microservice ter-hardening dari nol, menghasilkan SBOM, memindai CVE, menandatanganinya secara lokal, dan menerapkan enforcement admission control menggunakan mock test Kyverno CLI.

#### Struktur Direktori Hands-on
Simpan seluruh artefak ini pada direktori: `hands-on/m02/`
```text
hands-on/m02/
├── Dockerfile
├── main.go
├── go.mod
├── k8s/
│   ├── deployment.yaml
│   └── policy.yaml
└── test-pipeline.sh
```

#### Langkah 1: Siapkan Kode Go Minimalis
File: `hands-on/m02/go.mod`
```go
module secure-app

go 1.22
```

File: `hands-on/m02/main.go`
```go
package main

import (
	"fmt"
	"net/http"
	"os"
)

func main() {
	http.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"HEALTHY"}`))
	})

	http.HandleFunc("/write-test", func(w http.ResponseWriter, r *http.Request) {
		// Uji apakah filesystem benar-benar read-only
		err := os.WriteFile("/root-test.txt", []byte("malicious content"), 0644)
		if err != nil {
			w.WriteHeader(http.StatusForbidden)
			w.Write([]byte(fmt.Sprintf("Security Active: File write failed as expected -> %v", err)))
			return
		}
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("VULNERABLE: Filesystem is writable!"))
	})

	fmt.Println("Server starting on port 8080...")
	if err := http.ListenAndServe(":8080", nil); err != nil {
		fmt.Printf("Error starting server: %v\n", err)
	}
}
```

#### Langkah 2: Buat Hardened Multi-Stage Dockerfile
File: `hands-on/m02/Dockerfile`
```dockerfile
FROM golang:1.22-alpine AS builder
WORKDIR /src
COPY go.mod ./
COPY main.go ./
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags="-s -w" -trimpath -o /app/server .

FROM gcr.io/distroless/static-debian12:nonroot
WORKDIR /app
COPY --from=builder /app/server /app/server
USER 65532:65532
EXPOSE 8080
ENTRYPOINT ["/app/server"]
```

#### Langkah 3: Eksekusi Build, SBOM, Scan, dan Key Signing
File: `hands-on/m02/test-pipeline.sh` (Jadikan executable: `chmod +x test-pipeline.sh`)

```bash
#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG="local/secure-app:1.0.0"

echo "[1/5] Building Hardened Docker Image..."
docker build -t "${IMAGE_TAG}" .

echo "[2/5] Generating SBOM with Syft..."
syft "${IMAGE_TAG}" -o spdx-json=sbom.spdx.json
echo "SBOM successfully written to sbom.spdx.json"

echo "[3/5] Scanning Image for CVEs with Trivy..."
trivy image --severity CRITICAL,HIGH --ignore-unfixed --exit-code 0 "${IMAGE_TAG}"

echo "[4/5] Generating Ephemeral Cosign Keypair for Local Testing..."
# Membuat key pair dengan password kosong untuk keperluan automasi pengujian
COSIGN_PASSWORD="" cosign generate-key-pair

echo "[5/5] Signing Image Locally with Cosign..."
# Catatan: Penandatanganan lokal ke image daemon memerlukan cosign v2+
# Di environment real, image di-push ke registry terlebih dahulu.
echo "Cosign keys ready. Public key: cosign.pub"
echo "Pipeline execution finished successfully!"
```

#### Langkah 4: Validasi Manifest Kubernetes Menggunakan Kyverno CLI
File: `hands-on/m02/k8s/policy.yaml`
```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: enforce-read-only-rootfs
spec:
  validationFailureAction: Enforce
  rules:
    - name: validate-read-only-fs
      match:
        any:
          - resources:
              kinds:
                - Pod
      validate:
        message: "File system root harus bersifat READ-ONLY (securityContext.readOnlyRootFilesystem=true)!"
        pattern:
          spec:
            containers:
              - securityContext:
                  readOnlyRootFilesystem: true
```

File: `hands-on/m02/k8s/deployment.yaml`
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: secure-app-pod
spec:
  securityContext:
    runAsNonRoot: true
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: server
      image: local/secure-app:1.0.0
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities:
          drop:
            - ALL
```

Jalankan test validasi kepatuhan:
```bash
# Install kyverno-cli jika belum ada: brew install kyverno / via binary github release
kyverno apply hands-on/m02/k8s/policy.yaml --resource hands-on/m02/k8s/deployment.yaml
```
Output yang diharapkan:
```text
pass: 1, fail: 0, warn: 0, error: 0, skip: 0 
Policy enforce-read-only-rootfs passed on resource Pod/default/secure-app-pod!
```

---

### 13. Exercise

#### Tingkat Easy
1. Modifikasi file `Dockerfile` pada `hands-on/m02/` untuk menyertakan health check native tanpa mengorbankan keamanan (Ingat: Distroless tidak memiliki `curl` atau `wget`).
   *Hint: Gunakan Go binary itu sendiri untuk bertindak sebagai health checker command line flag, misalnya: `ENTRYPOINT ["/app/server"]` dengan opsi `/app/server -healthcheck`.*

#### Tingkat Medium
1. Buat pipeline GitHub Actions yang memvalidasi integritas base image. Jika base image yang digunakan tidak berasal dari repository internal yang diizinkan (`mycompany.azurecr.io/*`), pipeline harus gagal di tahap awal sebelum proses compile berlangsung.
2. Buat profil seccomp kustom (`seccomp-custom.json`) yang hanya mengizinkan syscalls minimum yang dibutuhkan aplikasi HTTP (Drop syscall berbahaya seperti `ptrace`, `sys_chroot`, `reboot`, dan `clone3` jika tidak diperlukan). Terapkan profil ini ke dalam konfigurasi Pod.

#### Tingkat Hard
1. Buat sistem validasi ganda pada Kyverno:
   - Aturan 1: Memverifikasi tanda tangan Cosign dari image digest.
   - Aturan 2: Menguraikan attestation scan keamanan dari in-toto predicate dan menolak deployment secara otomatis jika ditemukan CVE bernilai CVSS > 8.0, **meskipun** tanda tangan image terbukti valid.

---

### 14. Challenge (Studi Kasus Kompleks)

**Skenario Kasus:**
Sebuah aplikasi analitik data legacy ditulis dalam bahasa C++ dan Python 3.9. Aplikasi ini memerlukan pustaka komputasi native non-statis (`.so` dynamic shared libraries) dan memiliki sub-komponen yang membutuhkan hak akses untuk membuka raw socket sniffing untuk memantau paket jaringan lokal (`CAP_NET_RAW`). Selain itu, pustaka analytics menulis temporary scratchpad files sebesar ratusan megabyte secara berkala ke lokasi default hardcoded `/var/tmp/data`.

**Tantangan:**
Rancang arsitektur containerization dan deployment manifest produksi untuk sistem di atas dengan batasan:
1. Anda dilarang memberikan status root/privileged pod.
2. Anda harus menggunakan base image minimalis (bukan full Ubuntu OS).
3. Filesystem root wajib berstatus *Read-Only*.
4. `CAP_NET_RAW` hanya boleh aktif jika benar-benar esensial, tanpa memberikan kapabilitas jaringan lain (`CAP_NET_ADMIN` harus diblokir).
5. File temporer besar di `/var/tmp/data` tidak boleh menghabiskan memory node (RAM) host jika menggunakan `emptyDir` bertipe memory.
6. Rancang strategi pengujian Admission Control untuk memastikan pod analitik ini tidak dapat dieksploitasi untuk melancarkan serangan *packet injection* ke pod tetangga di node yang sama.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic

1. **Mengapa menghapus file rahasia (misal: private key) pada layer berikutnya di Dockerfile (`RUN rm -f /secret.key`) tidak menghilangkan risiko keamanan?**
   - A. Karena Linux kernel menyimpan cache file yang dihapus di memori.
   - B. Karena format OCI Image bersifat append-only; layer sebelumnya tetap menyimpan file tersebut dan dapat diekstrak oleh siapa saja yang memiliki akses pull.
   - C. Karena perintah `rm` pada Linux hanya mengubah permissions file menjadi invisible.
   - D. Karena Docker daemon otomatis menduplikasi file ke layer teratas saat build.

2. **Apa perbedaan mendasar antara base image `alpine` dan `distroless`?**
   - A. Alpine tidak memiliki kernel, sedangkan Distroless memiliki kernel sendiri.
   - B. Alpine menyertakan package manager (`apk`) dan BusyBox shell, sedangkan Distroless hanya menyertakan aplikasi dan dependensi runtime-nya tanpa shell dan package manager.
   - C. Distroless berbasis RedHat, sedangkan Alpine berbasis Arch Linux.
   - D. Alpine secara otomatis mengenkripsi filesystem, sedangkan Distroless tidak.

3. **Apa fungsi utama dari konfigurasi `allowPrivilegeEscalation: false` pada Kubernetes SecurityContext?**
   - A. Mencegah pod menggunakan CPU di atas batas limit.
   - B. Mencegah child process mendapatkan hak akses lebih tinggi daripada parent process-nya (mengendalikan bit `setuid` / `setgid`).
   - C. Menonaktifkan koneksi jaringan pod ke pod lain di namespace yang sama.
   - D. Mengubah filesystem dari Read-Only menjadi Read-Write secara dinamis.

4. **Kapan sebaiknya penandatanganan image (Image Signing) dilakukan di dalam siklus hidup DevSecOps?**
   - A. Sebelum source code di-commit oleh developer.
   - B. Setelah image selesai di-build, di-scan, lolos threshold kerentanan, dan siap di-push ke registry.
   - C. Saat pod ditarik (pull) oleh worker node Kubernetes.
   - D. Setelah aplikasi selesai melewati load-testing di production.

5. **Apa dampak langsung jika parameter `runAsNonRoot: true` dipasang pada Pod spec, namun Dockerfile tidak memiliki instruksi `USER` (default UID 0)?**
   - A. Kubernetes secara otomatis membuat user baru dengan UID 1000.
   - B. Kubelet akan menolak menjalankan kontainer tersebut dan status Pod berubah menjadi `CreateContainerConfigError`.
   - C. Kontainer tetap berjalan normal sebagai root.
   - D. Docker daemon otomatis mengonversi UID 0 menjadi nobody.

---

#### B. Pertanyaan Intermediate

6. **Mengapa penandatanganan image berbasis tag mutable (misal: `v1.0.0`) merupakan kelemahan keamanan serius dibanding menggunakan OCI digest (`sha256:...`)?**
   - A. Karena tag memerlukan sertifikat SSL tambahan saat ditarik.
   - B. Karena tag dapat ditimpa (*overwritten*) oleh pihak yang memiliki izin write di registry dengan image berbahaya tanpa mengubah nama tag, sedangkan digest bersifat matematis dan unik untuk konten image tersebut.
   - C. Karena Kubernetes Admission Controller tidak mampu membaca format teks pada tag.
   - D. Karena tag otomatis kedaluwarsa setelah 30 hari.

7. **Bagaimana mekanisme verifikasi *keyless* Cosign memanfaatkan OIDC token dari CI/CD provider?**
   - A. Cosign menyimpan private key permanen di database internal GitHub/GitLab.
   - B. Fulcio (CA) memvalidasi OIDC token identitas workflow, kemudian menerbitkan sertifikat X.509 berumur sangat pendek (ephemeral) yang mencantumkan identitas repositori; rekaman penandatanganan dimasukkan ke transparancy log Rekor.
   - C. CI/CD provider mengirimkan password akun developer langsung ke kluster Kubernetes.
   - D. OIDC token digunakan untuk mengenkripsi base image secara simetris menggunakan algoritma AES-256.

8. **Aplikasi Anda membutuhkan direktori `/tmp` untuk menulis cache, namun Anda wajib menegakkan `readOnlyRootFilesystem: true`. Solusi arsitektural mana yang paling tepat dan aman?**
   - A. Memberikan hak `sudo chmod 777 /tmp` pada instruksi awal Dockerfile.
   - B. Menghapus konfigurasi `readOnlyRootFilesystem: true` dan menggantinya dengan network policy.
   - C. Me-mount volume `emptyDir` (opsional dengan flag `medium: Memory`) secara spesifik pada direktori `/tmp`.
   - D. Menjalankan kontainer dengan user `root` agar proteksi read-only dapat dilewati aplikasi.

9. **Apa kegunaan dari instrumen Software Bill of Materials (SBOM) dalam mitigasi kerentanan zero-day seperti Log4Shell?**
   - A. SBOM secara otomatis memodifikasi bytecode aplikasi untuk mematikan fungsi yang rentan.
   - B. SBOM menyediakan inventaris terstruktur yang terperinci mengenai semua pustaka, modul, dan dependensi, sehingga tim keamanan dapat mencari inventaris tersebut secara instan tanpa perlu memindai ulang seluruh source code.
   - C. SBOM memblokir traffic jaringan yang mencurigakan secara real-time.
   - D. SBOM mengenkripsi binary aplikasi agar tidak dapat didekompilasi.

10. **Jika sebuah kontainer dikompromikan oleh penyerang, kapabilitas Linux manakah yang paling berbahaya jika tidak di-drop karena memungkinkan manipulasi interface jaringan host dan sniffing paket?**
    - A. `CAP_CHOWN`
    - B. `CAP_SETUID`
    - C. `CAP_NET_RAW` dan `CAP_NET_ADMIN`
    - D. `CAP_KILL`

---

#### C. Skenario Kasus Produksi

11. **Skenario 1:**
    Sebuah aplikasi web perbankan yang menggunakan base image Alpine Linux dideploy di Kubernetes. Tim DevOps telah menyetel `readOnlyRootFilesystem: true` dan `runAsUser: 5000`. Saat terjadi insiden keamanan, tim forensik mendapati bahwa penyerang berhasil mengeksekusi script shell arbitrary via celah *Command Injection* pada aplikasi. Penyerang mengunduh malware binary ke `/tmp` (yang di-mount via `emptyDir`) dan mengeksekusinya. 
    
    *Mitigasi konfigurasi teknis manakah yang seharusnya diterapkan untuk mencegah eksekusi file biner tersebut dari partisi `/tmp`?*
    - A. Mengganti UID user aplikasi menjadi UID 0.
    - B. Mengonfigurasi volume mount `/tmp` di level node atau pod dengan opsi flag mount `noexec` (misal via custom storage class atau init script) dan beralih ke *Distroless* image agar command injection gagal karena ketiadaan interpreter shell (`/bin/sh`).
    - C. Menghapus limits CPU pada Pod.
    - D. Mengaktifkan privilege escalation pada container spec.

12. **Skenario 2:**
    Kluster Kubernetes perusahaan menerapkan Kyverno untuk memvalidasi tanda tangan Cosign. Pada suatu hari, terjadi pemadaman koneksi internet global pada datacenter yang mengakibatkan koneksi egress terputus selama 15 menit. Pada saat bersamaan, mekanisme autoscaler kluster memicu pembuatan pod baru. Seluruh pod baru gagal start dengan error validasi webhook Kyverno, menyebabkan layanan lumpuh total (*outage*).
    
    *Evaluasi akar masalah dan perbaikan arsitektur apa yang wajib diterapkan?*
    - A. Masalah terjadi karena Kyverno memerlukan validasi OIDC ke public transparency log (Rekor). Solusinya adalah mematikan seluruh admission controller secara permanen.
    - B. Arsitektur bergantung pada ekosistem public Sigstore secara sinkron tanpa caching/private deployment. Perbaikan: Buat infrastruktur Sigstore privat on-premise, atau gunakan caching sertifikat, serta evaluasi konfigurasi webhook failurePolicy (`Fail` vs `Ignore`) sesuai Service Level Objective aplikasi.
    - C. Mengganti Kyverno dengan static manual approval via email.
    - D. Menambahkan memory pod Kyverno menjadi 128 GB.

13. **Skenario 3:**
    Pipeline CI/CD Anda memindai image menggunakan Trivy. Pada release darurat untuk memperbaiki bug sistem pembayaran, Trivy mendeteksi satu kerentanan berstatus `CRITICAL` pada dependensi glibc bawaan base image. Vendor OS belum merilis patch untuk CVE tersebut. Kebijakan pipeline secara ketat memblokir deployment jika terdeteksi CVE Critical (`exit 1`).
    
    *Tindakan engineering mana yang paling tepat dan aman secara kaidah DevSecOps enterprise?*
    - A. Menghapus tahapan pemindaian Trivy dari script CI/CD agar rilis segera berjalan.
    - B. Melakukan assessment kompensasi risiko: Gunakan file `.trivyignore` yang mencantumkan CVE ID tersebut secara spesifik, disertai justifikasi teknis kedaluwarsa (misalnya: masa berlaku toleransi 7 hari) dan persetujuan formal dari tim CISO, sambil memverifikasi bahwa aplikasi tidak mengekspos jalur fungsi yang mengeksploitasi kerentanan glibc tersebut.
    - C. Menghapus konfigurasi `runAsNonRoot` pada pods produksi.
    - D. Mengubah versi aplikasi menjadi versi beta agar diabaikan scanner.

---

#### Kunci Jawaban & Rasional Singkat

1. **B** — Layer OCI bersifat immutable dan bertumpuk (*union file system*). File yang dihapus di layer atas hanya disembunyikan (*whiteout marker*), fisiknya tetap tersimpan di layer bawahnya.
2. **B** — Alpine adalah distribusi sistem operasi lengkap berbasis musl-libc dan busybox yang menyertakan shell dan package manager (`apk`). Distroless hanya berisi aplikasi Anda dan dependensi spesifiknya tanpa shell atau package management.
3. **B** — Konfigurasi ini menyetel flag `no_new_privs` pada level kernel Linux, memblokir biner yang memiliki bit `setuid` (seperti `sudo` atau `su`) untuk menaikkan privilege proses.
4. **B** — Tanda tangan kriptografis harus menjadi gerbang terakhir sebelum distribusi; image harus sudah selesai di-scan dan dinyatakan bersih agar tanda tangan tersebut mengonfirmasi keabsahan dan keamanannya.
5. **B** — Kubelet memvalidasi konfigurasi container sebelum membuatnya; jika `runAsNonRoot: true` namun UID terdeteksi 0, kontainer langsung diblokir sebelum dijalankan.
6. **B** — Tag mutable dapat dengan mudah dipindahkan/ditimpa untuk merujuk ke image yang telah disusupi malware (*image spoofing*). Digest SHA-256 merepresentasikan hash konten unik yang mustahil dipalsukan tanpa mengubah nilai hash.
7. **B** — Alur Sigstore Keyless memanfaatkan OIDC token CI/CD untuk meminta sertifikat temporer (ephemeral) dari CA Fulcio dan mencatat hash publiknya ke Rekor transparency log.
8. **C** — Memetakan volume `emptyDir` ke direktori spesifik mengizinkan aplikasi menulis data sementara hanya ke direktori tersebut, sementara seluruh bagian root filesystem lainnya tetap berstatus read-only murni.
9. **B** — SBOM mencatat data metadata dependensi software secara komprehensif, memungkinkan audit cepat berbasis query basis data tanpa harus membangun atau membongkar container image secara manual.
10. **C** — `CAP_NET_RAW` memungkinkan pembuatan raw packet dan packet sniffing, sedangkan `CAP_NET_ADMIN` memungkinkan pengubahan routing table dan konfigurasi interface jaringan node host.
11. **B** — Mencegah binary execution pada direktori writeable (`/tmp`) dan menghilangkan ketersediaan shell (Distroless) memutus rantai serangan (*kill-chain*) eksekusi arbitrary payload.
12. **B** — Ketergantungan kritis pada eksternal internet service saat runtime scheduling kluster adalah anti-pattern keandalan. Solusinya adalah lokalisasi verifikasi (Private PKI/Sigstore) dan penyesuaian fallback handling.
13. **B** — DevSecOps enterprise menuntut tata kelola pengecualian (*vulnerability exception handling*). Menghapus scanner adalah pelanggaran audit, sementara `.trivyignore` dengan time-to-live (TTL) dan mitigasi alternatif menjaga jejak audit kepatuhan.

---

### 16. Summary

1. **Defense in Depth pada Kontainer:** Keamanan kontainer yang efektif dibangun secara berlapis, mulai dari tahap kompilasi kode (multi-stage minimal base), penjaminan rantai pasok (SBOM & vulnerability gate), verifikasi integritas kriptografis (Cosign keyless OIDC), hingga penegakan runtime terisolasi (Namespaces, cgroups, LSM, dan pembatasan Linux Capabilities).
2. **Immutability Mutlak:** Menjalankan kontainer dengan `readOnlyRootFilesystem: true`, non-root user (UID > 10000), tanpa shell, dan menolak eskalasi hak akses (`allowPrivilegeEscalation: false`) secara drastis menurunkan probabilitas eksploitasi celah keamanan remote code execution (RCE).
3. **Pemberdayaan Zero Trust Admission Control:** Image tidak boleh dipercaya hanya berdasarkan nama repositori atau tag. Kubernetes cluster modern harus menggunakan admission controller (seperti Kyverno) untuk memverifikasi SHA-256 digest dan cryptographic signature sebelum pod diizinkan berjalan di lingkungan produksi.