# Bab 08: Cloud & Container Security
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
*   Menganalisis dan mengonfigurasi isolasi kernel tingkat rendah (*namespaces*, *cgroups v2*, *Seccomp-BPF*, dan *Linux Security Modules* seperti AppArmor/SELinux) untuk mencegah eskalasi *container breakout*.
*   Merancang dan mengimplementasikan *admission control pipeline* berbasis deklaratif (Kyverno / OPA Gatekeeper) dengan validasi kriptografis (*cosign keyless verification*) dan *Pod Security Standards* (PSS) profil *Restricted*.
*   Membangun arsitektur *runtime security monitoring* dan *automated remediation* menggunakan eBPF (*Extended Berkeley Packet Filter*) via Falco atau Cilium Tetragon.
*   Mengonfigurasi autentikasi identitas beban kerja (*workload identity federation*) berbasis SPIFFE/SPIRE dan integrasi *Secret Management* terdistribusi (Vault CSI Driver) tanpa mengekspos kredensial statis.
*   Menguji, mengaudit, dan memitigasi celah keamanan *software supply chain* menggunakan attestasi in-toto dan SLSA (*Supply-chain Levels for Software Artifacts*) Framework.

---

### 2. Prerequisite

Sebelum memulai modul ini, Anda harus memahami:
*   **Operating Systems Internals**: Memahami struktur Linux Kernel, *system calls* (`clone`, `unshare`, `pivot_root`, `setns`), serta hak akses POSIX.
*   **Container Engines & OCI**: Memahami arsitektur *low-level container runtime* (`runc`, `crun`), *high-level runtime* (`containerd`, `CRI-O`), dan format *OCI Image Specification*.
*   **Kubernetes Administration**: Penguasaan konsep Pod, ServiceAccount, Dynamic Admission Webhook, Mutating/Validating Webhooks, dan arsitektur Control Plane vs Worker Node.
*   **Kriptografi Terapan**: Pemahaman tentang Public Key Infrastructure (PKI), x509 certificates, OIDC (*OpenID Connect*), SHA256 digest, dan mekanisme tanda tangan digital (*asymmetric digital signatures*).

---

### 3. Concept & Internal Architecture (Mendalam)

Container bukanlah entitas virtual layaknya Virtual Machine; container adalah sekadar proses reguler Linux yang dibatasi oleh isolasi kernel. Memahami arsitektur keamanan container mewajibkan pembedahan terhadap lapisan abstraksi kernel berikut:

```
+-----------------------------------------------------------------------+
|                            USER SPACE                                 |
|                                                                       |
|  +--------------------------------+   +----------------------------+  |
|  | Containerized Process (PID 1)  |   | Security Agent (Falco/     |  |
|  | UID 10001 (Non-Root)           |   | Tetragon / DaemonSet)      |  |
|  +--------------------------------+   +----------------------------+  |
|                 | (Syscalls: execve, socket, etc.)   ^                |
+-----------------|------------------------------------|----------------+
|                 v                                    |                |
|  +---------------------------------------------------|-------------+  |
|  | KERNEL SPACE                                      | (Ring Buffer|  |
|  |                                                   |  / Perf Map)|  |
|  |  +-------------------+   +--------------------+   |             |  |
|  |  | Namespaces        |   | cgroups v2         |   |             |  |
|  |  | (PID, MNT, NET,   |   | (CPU, Memory, IO,  |   |             |  |
|  |  |  IPC, UTS, USER)  |   |  PIDs Limit)       |   |             |  |
|  |  +-------------------+   +--------------------+   |             |  |
|  |            |                       |              |             |  |
|  |            v                       v              |             |  |
|  |  +--------------------------------------------+   |             |  |
|  |  | Seccomp-BPF Filter Engine                  |   |             |  |
|  |  | (Intercepts & filters system calls)         |   |             |  |
|  |  +--------------------------------------------+   |             |  |
|  |            |                                      |             |  |
|  |            v                                      |             |  |
|  |  +--------------------------------------------+   |             |  |
|  |  | Linux Security Modules (AppArmor/SELinux)  |   |             |  |
|  |  | (MAC: Mandatory Access Control)            |   |             |  |
|  |  +--------------------------------------------+   |             |  |
|  |            |                                      |             |  |
|  |            v                                      |             |  |
|  |  +--------------------------------------------+   |             |  |
|  |  | eBPF Instrumentation Hooks                 |---+             |  |
|  |  | (Kprobes, Tracepoints, LSM BPF hooks)      |                 |  |
|  |  +--------------------------------------------+                 |  |
+--------------------------------------------------------------------+--+
```

#### A. Primitif Isolasi Kernel Linux
1.  **Linux Namespaces**: Menyediakan ilusi alokasi sumber daya independen kepada proses.
    *   `pid`: Mengisolasi penomoran proses (proses di dalam container melihat dirinya sebagai PID 1, padahal di host memiliki PID lain).
    *   `mnt`: Mengisolasi *mount points* berkas (bekerja sama dengan `pivot_root`).
    *   `net`: Mengisolasi *network stack* (antarmuka jaringan, rute, tabel iptables/nftables).
    *   `user`: Memetakan UID/GID dalam namespace ke UID/GID berbeda di host. Ini adalah basis *rootless containers* (misalnya: root `UID 0` di dalam container dipetakan ke unprivileged `UID 10001` di host).
    *   `ipc`, `uts`, `cgroup`: Mengisolasi System V IPC, nama host/domain, dan hierarki cgroup.
2.  **Control Groups (cgroups v2)**: Membatasi, mencatat, dan mengisolasi penggunaan sumber daya (CPU, RAM, Disk I/O, batas jumlah proses `pids.max`). Pembatasan `pids.max` krusial untuk mencegah serangan *fork bomb* yang dapat melumpuhkan seluruh node Kubernetes.
3.  **Seccomp-BPF (Secure Computing with BPF)**: Menggunakan instruksi BPF dalam kernel untuk menyaring *system call* (syscall) sebelum dieksekusi. Jika proses memanggil syscall terlarang (misalnya `reboot`, `sys_ptrace`, `kexec_load`), kernel langsung menghentikan proses (`SECCOMP_RET_KILL_PROCESS`) atau mengembalikan error (`SECCOMP_RET_ERRNO`).
4.  **Linux Security Modules (LSM)**: Lapisan otorisasi berbasis *Mandatory Access Control* (MAC). Berbeda dengan *Discretionary Access Control* (DAC: `chmod`/`chown`), LSM memeriksa hak akses berkas dan *inode* berdasarkan aturan sistemik global (AppArmor membatasi path direktori, SELinux menggunakan pelabelan konteks konteks tipe/domain).

#### B. Mekanisme eBPF untuk Runtime Security
Sistem keamanan lama memanfaatkan `ptrace` atau auditd, yang memiliki performa lambat (*context-switch penalty*) dan rentan manipulasi. eBPF memungkinkan pemuatan kode *bytecode* yang diverifikasi ke dalam kernel space secara dinamis.
*   **Hooks**: eBPF dapat menempel pada *kprobes* (kernel probes), *kretprobes*, *tracepoints*, dan *LSM hooks*.
*   **Keuntungan Arsitektural**: eBPF membaca argumen eksekusi langsung dari memori kernel, melewati manipulasi *Time-of-Check to Time-of-Use* (TOCTOU).
*   **Tetragon & Falco**: Mengekstraksi event kernel (misal: pemanggilan `execve`, modifikasi *namespace* via `setns`, pembukaan socket keluar) dan mengirimkannya ke user space via struktur data efisien (*ring buffer*).

#### C. Supply Chain Security Architecture (SLSA & Sigstore)
Dalam arsitektur modern, image container dilarang dideploy ke cluster tanpa bukti integritas kriptografis:
1.  **SLSA Framework**: Kerangka kerja yang memastikan artefak perangkat lunak tidak dapat dimanipulasi dari *source code* hingga deployment.
2.  **Sigstore Stack**:
    *   **Fulcio**: *Free Certificate Authority* yang menerbitkan sertifikat x509 berbasis token OIDC (GitHub Actions, GitLab CI, Google IAM).
    *   **Cosign**: Perkakas untuk menandatangani dan memverifikasi container images serta attestasi (SBOM/Vuln report).
    *   **Rekor**: *Transparency Log* berbasis *Merkle tree* publik/privat yang mencatat tanda tangan secara *tamper-evident*.
    *   **Kyverno/Gatekeeper**: Mengintersepsi permintaan pod di Kubernetes Admission Controller dan menolak eksekusi jika *digest* image tidak memiliki signature sah yang tercatat di Rekor.

---

### 4. Why & What

#### Mengapa Keamanan Host Konvensional Gagal pada Container?
*   **Shared Kernel Paradigm**: Container berbagi satu kernel yang sama dengan host. Sebuah *vulnerability* pada kernel host (misal: *Dirty COW*, *Dirty Pipe*) memungkinkan proses di dalam container lolos (*breakout*) dan mengambil alih kendali penuh atas node host.
*   **Ephemeral Lifecycle**: Umur container yang pendek (menit atau detik) membuat *endpoint agent* tradisional tidak mampu menangkap jejak forensik jika storage container dimusnahkan.
*   **Perimeter Defense Basi**: Di lingkungan microservices, konsep firewall perimeter jaringan runtuh. Serangan lateral di dalam cluster dapat terjadi jika tidak ada isolasi tingkat jaringan (*NetworkPolicy*) dan identitas (*mTLS/SPIFFE*).

#### Apa Komponen Utama Enterprise Container Security Architecture?
1.  **Shift-Left Immutability**: Analisis dependensi, pembuatan Software Bill of Materials (SBOM), *static binary analysis*, dan penandatanganan image saat CI.
2.  **Zero-Trust Admission Phase**: Kebijakan kluster ketat yang memastikan hanya image terverifikasi dengan profil keamanan minimal yang dapat dieksekusi.
3.  **Kernel-Level Containment**: Penegakan hak akses terendah (*Principle of Least Privilege*): non-root, *immutable root filesystem*, dropping seluruh *Linux capabilities*, serta isolasi profil Seccomp default.
4.  **Active Runtime Enforcement**: Kemampuan untuk mendeteksi anomali di level kernel dan secara otomatis membunuh (*SIGKILL*) pod yang terkompromi dalam hitungan milidetik.

---

### 5. How (Workflow detail)

Berikut adalah alur produksi komprehensif mulai dari kode hingga penegakan runtime di Kubernetes:

```
[ Developer ] 
      │ git push
      ▼
[ CI Engine: GitHub Actions / GitLab CI ]
      │ 1. Build Minimal Image (Distroless/Scratch)
      │ 2. Scan Vuln (Trivy/Grype) & Generate SBOM (SPDX/CycloneDX)
      │ 3. Keyless Sign Image via Cosign + Fulcio (OIDC)
      │ 4. Attest SBOM & Vuln Report to Rekor Transparency Log
      ▼
[ Container Registry (Harbor / ECR / OCI Registry) ]
      │ (Stores Image Digest + Signed Attestations)
      ▼
[ Kubernetes API Server ]
      │ Admission Request: Pod Creation
      ▼
[ Validating Webhook: Kyverno / OPA Gatekeeper ]
      │ 1. Verifikasi Signature via Rekor & Fulcio Root CA
      │ 2. Verifikasi Compliance PSS (Disallow Root, Drop Caps)
      │ 3. Verifikasi Attestation (Vuln scan: No Critical CVEs)
      ├── [ REJECTED ] ──> Tolak Pod (HTTP 403 Forbidden)
      └── [ ACCEPTED ]
            │
            ▼
[ Kubelet / CRI Runtime: containerd ]
      │ 1. Mount Image (Root filesystem: Read-Only)
      │ 2. Apply Seccomp Profile (RuntimeDefault)
      │ 3. Apply AppArmor Profile (runtime/default)
      │ 4. Drop Capabilities: CAP_ALL -> Add: none
      │ 5. Setup cgroups v2 (CPU/Mem/PIDs limits)
      ▼
[ Linux Kernel Execution ]
      │
      ├── [ Tetragon / Falco eBPF Probes Monitoring ]
      │         │
      │         ├── Anomaly Detected: execve("/bin/sh") inside distroless
      │         └── Kernel-space Action: Send SIGKILL to thread immediately!
      ▼
[ Pod Running Healthy ]
```

1.  **Pipeline CI Build & Sign**: Container di-build menggunakan *multi-stage Dockerfile* dengan base image minimal (*distroless*). Tool `syft` meng-generate SBOM, `trivy` memindai celah keamanan. Tool `cosign` mengautentikasi terhadap OIDC IdP, menandatangani image SHA256 digest, dan mempublikasikan attestasi ke OCI Registry serta Rekor.
2.  **Kubernetes Admission Interception**: Pod Manifest dikirim ke API Server. Validating Admission Webhook (Kyverno) memverifikasi:
    *   Apakah image memiliki tanda tangan valid dari identity issuer yang diizinkan?
    *   Apakah manifest melanggar aturan Pod Security Standard (misal: mencoba `privileged: true` atau `runAsUser: 0`)?
3.  **Kernel Sandboxing**: Runtime `containerd` mengonfigurasi isolasi Linux sebelum proses di-spawn: memberlakukan *immutable root filesystem*, mengaktifkan seccomp filter, dan membatasi namespace.
4.  **Runtime Observability**: Sensor eBPF memonitor antarmuka syscall kernel secara *real-time*. Jika ada proses yang melanggar aturan (misal: pod mencoba membaca direktori `/etc/shadow` atau men-spawn shell interaktif), eBPF agent mengeksekusi *in-kernel termination* atau mengirim peringatan ke SIEM.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Pengapalan Peti Kemas Ultra-Ketat
*   **Image Container = Peti Kemas Bersegel**: Sebelum masuk ke pelabuhan, peti kemas harus memiliki manifes kargo yang terdaftar (SBOM) dan segel lilin anti-rusak (*Cosign Signature*).
*   **Admission Controller = Gerbang Pabean/Bea Cukai**: Memeriksa segel peti kemas. Jika segel rusak atau manifes mencatat barang berbahaya tanpa izin, peti kemas ditolak masuk pelabuhan.
*   **Namespaces = Kompartemen Kedap Air**: Setiap peti diletakkan di ruang khusus tanpa akses fisik ke ruang lain.
*   **cgroups v2 = Skala Batas Muatan**: Memastikan peti tidak boleh melebihi berat atau kapasitas tertentu agar kapal tidak karam.
*   **Seccomp-BPF & LSM = Penjaga Bersenjata Internal**: Berada di lorong kapal; jika ada penumpang peti kemas mencoba membuka pintu mesin utama (syscall ilegal), penjaga langsung melumpuhkannya di tempat (*SIGKILL*).
*   **eBPF = Kamera Sensor X-Ray 24/7**: Memantau pergerakan molekuler di seluruh kapal secara real-time tanpa mengganggu kinerja awak kapal.

---

### 7. Simple Example & Practical Example (Standar Industri)

#### A. Simple Example: Seccomp Profile Minimal
Definisi profil Seccomp JSON yang memblokir semua syscall secara *default*, dan hanya mengizinkan syscall minimal untuk eksekusi standar:

```json
{
  "defaultAction": "SCMP_ACT_ERRNO",
  "architectures": [
    "SCMP_ARCH_X86_64",
    "SCMP_ARCH_AARCH64"
  ],
  "syscalls": [
    {
      "names": [
        "read",
        "write",
        "exit",
        "exit_group",
        "futex",
        "nanosleep"
      ],
      "action": "SCMP_ACT_ALLOW"
    }
  ]
}
```

#### B. Practical Example 1: Multi-Stage Secure Dockerfile (Distroless + Non-Root)

```dockerfile
# Stage 1: Build binary secara aman
FROM golang:1.22-alpine AS builder

# Pasang dependensi minimal yang diperlukan untuk build
RUN apk update && apk add --no-cache git ca-certificates tzdata

WORKDIR /workspace

# Optimasi cache dependensi
COPY go.mod go.sum ./
RUN go mod download && go mod verify

COPY . .

# Kompilasi binary statis (tanpa CGO) dan stripping debugging symbols (-ldflags="-s -w")
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build \
    -a -installsuffix cgo \
    -ldflags="-s -w -extldflags '-static'" \
    -o secure-api ./cmd/api

# Stage 2: Runtime Minimalis dengan Distroless
FROM gcr.io/distroless/static-debian12:nonroot

WORKDIR /app

# Salin CA certificates dan timezone data
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --from=builder /usr/share/zoneinfo /usr/share/zoneinfo

# Salin binary yang telah dikompilasi
COPY --from=builder /workspace/secure-api /app/secure-api

# nonroot user UID di distroless adalah 65532
USER 65532:65532

# Expose port (non-privileged > 1024)
EXPOSE 8080

ENTRYPOINT ["/app/secure-api"]
```

#### C. Practical Example 2: Hardened Pod Specification (Kubernetes)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-processor
  namespace: production
  labels:
    app.kubernetes.io/name: payment-processor
    sec.enterprise.io/tier: critical
spec:
  replicas: 3
  selector:
    matchLabels:
      app.kubernetes.io/name: payment-processor
  template:
    metadata:
      labels:
        app.kubernetes.io/name: payment-processor
    spec:
      # Hilangkan ketergantungan token k8s default jika tidak perlu berinteraksi dengan API Server
      automountServiceAccountToken: false
      securityContext:
        runAsNonRoot: true
        runAsUser: 65532
        runAsGroup: 65532
        fsGroup: 65532
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: payment-api
          image: ghcr.io/enterprise/payment-api:v2.4.1@sha256:7f83b1657ff1fc5351b70eb2447d25e8346b9a8cf61f4fa9b47e58319e7550f2
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 8080
          resources:
            limits:
              cpu: "1"
              memory: "512Mi"
            requests:
              cpu: "250m"
              memory: "128Mi"
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            privileged: false
            capabilities:
              drop:
                - ALL
          volumeMounts:
            # Mount direktori tulis sementara yang aman di memory, bukan di storage host
            - name: ephemeral-tmp
              mountPath: /tmp
      volumes:
        - name: ephemeral-tmp
          emptyDir:
            medium: Memory
            sizeLimit: 64Mi
```

#### D. Practical Example 3: Kyverno ClusterPolicy untuk Penegakan Verifikasi Cosign & PSS

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: enforce-supply-chain-and-hardening
  annotations:
    policies.kyverno.io/title: Verify Cosign Signatures and Container Hardening
    policies.kyverno.io/severity: critical
spec:
  validationFailureAction: Enforce
  background: false
  rules:
    - name: verify-image-signature
      match:
        any:
          - resources:
              kinds:
                - Pod
              namespaces:
                - production
      verifyImages:
        - imageReferences:
            - "ghcr.io/enterprise/*"
          attestors:
            - entries:
                - keyless:
                    issuer: "https://token.actions.githubusercontent.com"
                    subject: "https://github.com/enterprise/payment-backend/.github/workflows/deploy.yml@refs/heads/main"
                    rekor:
                      url: "https://rekor.sigstore.dev"
    - name: validate-immutable-rootfs-and-non-root
      match:
        any:
          - resources:
              kinds:
                - Pod
              namespaces:
                - production
      validate:
        message: "Container HARUS berjalan sebagai non-root dan menggunakan read-only root filesystem."
        pattern:
          spec:
            securityContext:
              runAsNonRoot: true
            containers:
              - securityContext:
                  readOnlyRootFilesystem: true
                  allowPrivilegeEscalation: false
                  capabilities:
                    drop:
                      - ALL
```

#### E. Practical Example 4: Tetragon TracingPolicy (eBPF Real-time Threat Kill)

```yaml
apiVersion: cilium.io/v1alpha1
kind: TracingPolicy
metadata:
  name: block-namespace-breakout-and-shell
  namespace: kube-system
spec:
  kprobes:
    - call: "sys_execve"
      syscall: true
      args:
        - index: 0
          type: "string" # Argumen eksekusi biner
      selectors:
        - matchArgs:
            - index: 0
              operator: "Prefix"
              values:
                - "/bin/"
                - "/usr/bin/"
                - "/sh"
                - "/bash"
          matchNamespaces:
            - production
          matchActions:
            - action: Sigkill # Langsung tembak proses di level kernel jika binary shell dieksekusi
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks & Insiden
Sebuah platform Neobank berskala besar di Asia Tenggara dengan throughput 15.000 TPS bermigrasi dari armada VM monolitik ke arsitektur multi-tenant Kubernetes (EKS). Tiga bulan pasca-migrasi, tim Security Operations Center (SOC) mendeteksi anomali pada salah satu worker node: trafik outbound mencurigakan menuju server C2 (*Command and Control*) eksternal melalui port 4444.

#### Analisis Forensik & Vektor Serangan
1.  **Vulnerability Entry**: Sebuah microservice analitik pihak ketiga yang rentan terhadap eksekusi kode jarak jauh (RCE berbasis deserialisasi objek) dieksploitasi oleh penyerang.
2.  **Container Weakness**: Microservice tersebut di-deploy menggunakan base image Ubuntu standar, berjalan sebagai `root` (`UID 0`), tanpa membatasi *Linux capabilities*.
3.  **Breakout Vector**: Penyerang mendownload *exploit payload* ke direktori `/tmp`, memanfaatkan kapabilitas `CAP_SYS_ADMIN` yang tertinggal untuk berinteraksi dengan cgroups release agent host, lolos (*container breakout*) dari isolated filesystem, dan menanam reverse-shell langsung di sistem operasi Worker Node.
4.  **Lateral Movement**: Penyerang mengakses metadata instance AWS via link local IP `169.254.169.254` (karena IMDSv1 masih aktif), mengekstrak kredensial IAM node host yang memiliki hak akses luas ke S3 bucket database backup.

#### Solusi Arsitektural & Mitigasi Menyeluruh
Organisasi melakukan overhaul arsitektur menyeluruh dalam 72 jam:
1.  **Membatasi Akses Kernel**: Menerapkan Pod Security Standard `Restricted` di seluruh cluster via Kyverno. Menghapus seluruh kapabilitas Linux (`drop: ["ALL"]`) dan mewajibkan `readOnlyRootFilesystem: true`. Pod tidak lagi dapat membuat file executable baru di disk lokal.
2.  **Non-Root Enforcement & Distroless**: Seluruh pipeline CI/CD diwajibkan menggunakan Google Container Tools *distroless* images. Proses dijalankan dengan UID acak `10001` ke atas.
3.  **eBPF Active Kill Engine**: Mengimplementasikan Cilium Tetragon pada seluruh cluster. Tetragon dikonfigurasi untuk memonitor syscall `sys_execve` dan modifikasi namespace. Jika ada eksekusi biner yang tidak lazim atau upaya perubahan UID via kernel, Tetragon mengirim sinyal `SIGKILL` secara instan.
4.  **Workload Identity & Metadata Protection**:
    *   Memigrasikan seluruh *node metadata service* ke AWS IMDSv2 dengan `http-put-response-hop-limit` diatur ke `1`, mencegah container menjangkau metadata IAM node host.
    *   Mengadopsi EKS Pod Identity (IRSA), memberikan peran IAM temporer dengan prinsip *least privilege* langsung ke ServiceAccount pod spesifik.
5.  **Dampak**: Ketika tim Red Team melakukan simulasi serangan serupa pada kuartal berikutnya, upaya eksekusi binary shell langsung dibatalkan di level kernel dalam rentang 1,2 milidetik oleh hook eBPF, tanpa dampak latensi pada transaksi perbankan.

---

### 9. Trade-offs (Analisis Kompromi Teknis)

| Aspek Arsitektur | Pilihan A (Paling Aman) | Pilihan B (Paling Praktis) | Dampak & Kompromi Teknis |
| :--- | :--- | :--- | :--- |
| **Base Images** | Distroless / Scratch (Zero Shell, Minimalist) | OS Lengkap (Ubuntu/Alpine dengan paket debugging) | **Security vs Troubleshootability**: Distroless mengeliminasi vektor serangan shell, tetapi menyulitkan *in-cluster debugging* (membutuhkan `kubectl debug` dengan ephemeral containers). |
| **Admission Control** | Validating Webhook dengan `failurePolicy: Fail` | Validating Webhook dengan `failurePolicy: Ignore` | **Availability vs Security**: Mode `Fail` menjamin cluster tidak menerima pod tidak sah jika admission pod crash, tetapi dapat melumpuhkan seluruh deployment operasional jika webhook timeout. |
| **Filesystem Security** | `readOnlyRootFilesystem: true` + Memory `emptyDir` | Writable Filesystem standar | **Performance & Memory Overhead**: Read-only mencegah malware menulis file biner baru, namun aplikasi yang rakus log atau file temporer dapat menyebabkan *Out of Memory* (OOM) jika `emptyDir` di-mount di RAM. |
| **Runtime Engine** | eBPF-based In-Kernel Blocking (Tetragon) | Log-based Detection (Auditd / Daemon log parsers) | **Resource vs Latency**: eBPF memberikan proteksi instan *zero-latency window*, namun membutuhkan kernel modern (>= 5.4/5.10) dan memakan resource CPU Worker Node untuk verifikasi instruksi BPF. |
| **Supply Chain Verification** | Rekor Online Verification di setiap Pod deployment | Verifikasi internal cache / offline keys | **External Dependency**: Verifikasi keyless Fulcio/Rekor bergantung pada stabilitas koneksi internet control-plane menuju Transparency Log publik jika tidak meng-host Rekor internal sendiri. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum (Anti-Patterns)
1.  **Mounting Docker Socket ke Container Pod (`/var/run/docker.sock`)**: Memberikan kontrol mutlak atas daemon Docker host kepada pod. Siapa pun yang menguasai container dapat membuat container lain dengan akses root ke host filesystem.
2.  **Menjalankan Pod dengan Flag `privileged: true`**: Menonaktifkan seluruh isolasi kernel (AppArmor, Seccomp, dan pembatasan device). Container memiliki hak setara root di node fisik.
3.  **Mengabaikan `automountServiceAccountToken`**: Secara default, Kubernetes me-mount token service account ke `/var/run/secrets/kubernetes.io/serviceaccount/token`. Jika pod terkompromi, penyerang menggunakan token ini untuk mengeksploitasi Kubernetes API Server.
4.  **Konfigurasi Mutable Image Tags (misal: `:latest`)**: Membuka celah terhadap *tag squatting* atau modifikasi isi image tanpa perubahan nama. Gunakan immutable image SHA256 digest (`image@sha256:...`).
5.  **Salah Menempatkan `tmp` Volume pada Read-Only RootFS**: Aplikasi modern kerap menulis file lock atau cache ke `/tmp`. Menonaktifkan write permission tanpa me-mount volume `emptyDir` ke `/tmp` akan memicu `CrashLoopBackOff`.

#### Panduan Troubleshooting

##### Skenario 1: Pod Mengalami `CrashLoopBackOff` setelah Mengaktifkan `readOnlyRootFilesystem: true`
*   **Gejala**: Aplikasi crash saat startup dengan error: `EROFS: read-only file system, open '/app/cache/app.log'`.
*   **Diagnosis**:
    ```bash
    # Periksa log container
    kubectl logs <pod-name> -n <namespace>
    ```
*   **Solusi**: Identifikasi seluruh path yang butuh izin tulis, mount volume `emptyDir` tipe memori ke direktori tersebut:
    ```yaml
    volumeMounts:
      - name: app-cache
        mountPath: /app/cache
    volumes:
      - name: app-cache
        emptyDir: {}
    ```

##### Skenario 2: Admission Webhook Timeout Melumpuhkan Deployment
*   **Gejala**: `Error from server (InternalError): Internal error occurred: failed calling webhook "validate.kyverno.svc": Post "...": context deadline exceeded`.
*   **Diagnosis**: Periksa apakah pod admission controller (Kyverno) kekurangan resource CPU/Memory atau terganggu oleh *NetworkPolicy*:
    ```bash
    kubectl get pods -n kyverno -o wide
    kubectl top pod -n kyverno
    ```
*   **Solusi**: Konfigurasi `failurePolicy: Ignore` sementara dalam kondisi darurat pemulihan kluster (DR), atau tingkatkan alokasi resource limits serta replicas webhook pod minimal menjadi 3 pod dengan *Anti-Affinity*.

##### Skenario 3: Syscall Terblokir oleh Profil Seccomp Default
*   **Gejala**: Aplikasi gagal menjalankan sub-operasi tertentu tanpa pesan error aplikasi yang jelas (biasanya error `Operation not permitted`).
*   **Diagnosis**: Cek dmesg pada worker node untuk melihat intersepsi audit seccomp:
    ```bash
    dmesg -T | grep -i seccomp
    # Output: audit: type=1326 audit(1620000.000:123): auid=4294967295 uid=10001 gid=10001 ses=4294967295 subj=snap.docker.dockerd pid=4123 comm="app" exe="/app/binary" sig=31 arch=c000003e syscall=165 compat=0 ip=0x7f...
    ```
    Identifikasi ID syscall (misal `syscall=165` adalah `mount`).
*   **Solusi**: Evaluasi apakah aplikasi benar-benar membutuhkan syscall tersebut. Jika iya, buat *custom seccomp profile* yang meloloskan syscall terkait secara terbatas, bukan mematikan Seccomp.

---

### 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum merilis beban kerja container ke lingkungan produksi:

- [ ] **Image Hardening**:
  - [ ] Image dibangun berbasis Distroless, Scratch, atau Alpine versi ter-patch.
  - [ ] Tidak ada package manager (`apt`, `apk`, `yum`) tertinggal di production runtime layer.
  - [ ] Tidak ada kredensial, sertifikat privat, atau API key yang tertulis di Dockerfile layer.
  - [ ] Menggunakan multi-stage build untuk memisahkan tool kompilasi dari runtime.
- [ ] **Cryptographic Verification**:
  - [ ] Seluruh image ditandatangani menggunakan Cosign (Keyless via OIDC).
  - [ ] SBOM (Software Bill of Materials) ter-generate dan tersimpan di OCI registry.
  - [ ] Admission Controller aktif menolak image tanpa signature valid.
- [ ] **Kubernetes Pod Security**:
  - [ ] Pod Security Standards (PSS) berstatus `enforce: restricted` pada namespace kerja.
  - [ ] `runAsNonRoot: true` dan `runAsUser` secara eksplisit diset ke UID >= 10000.
  - [ ] `allowPrivilegeEscalation: false` diaktifkan pada seluruh container.
  - [ ] `readOnlyRootFilesystem: true` diaktifkan di seluruh container.
  - [ ] `capabilities.drop: ["ALL"]` dikonfigurasi tanpa penambahan kapabilitas yang tidak ditinjau ketat.
  - [ ] `seccompProfile.type: RuntimeDefault` diterapkan di tingkat pod atau container.
  - [ ] `automountServiceAccountToken: false` jika pod tidak memerlukan koneksi ke Kubernetes API.
- [ ] **Resource Limits & Isolation**:
  - [ ] `resources.limits.cpu`, `resources.limits.memory` terdefinisi.
  - [ ] cgroups `pids.max` diterapkan di tingkat Kubelet konfigurasi node.
- [ ] **Network & Secret Security**:
  - [ ] *Default-deny* NetworkPolicy terpasang (Inbound & Outbound) di namespace.
  - [ ] Kredensial dinamis diinjeksi via HashiCorp Vault Agent / CSI Driver, bukan K8s Secret dasar plain base64.
  - [ ] Komunikasi antar-pod dienkripsi dengan mTLS melalui Service Mesh (Istio / Linkerd / Cilium).

---

### 12. Hands-on Practice: Membangun Zero-Trust Secure Pod & eBPF Defense

Simpan seluruh file praktikum ini di direktori: `hands-on/m02/`

#### Persiapan Lab
Pastikan Anda memiliki terminal Linux dengan perkakas berikut:
*   `kind` (Kubernetes in Docker)
*   `kubectl`
*   `cosign`
*   `helm`

#### Langkah 1: Inisialisasi Kluster Uji Coba Kind
Buat file `hands-on/m02/kind-config.yaml`:
```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  extraMounts:
    - hostPath: /sys/kernel/debug
      containerPath: /sys/kernel/debug
```
Jalankan perintah:
```bash
kind create cluster --name sec-ops-lab --config hands-on/m02/kind-config.yaml
```

#### Langkah 2: Instalasi Kyverno Policy Engine
```bash
helm repo add kyverno https://kyverno.github.io/kyverno/
helm repo update
helm install kyverno kyverno/kyverno --namespace kyverno --create-namespace \
  --set replicaCount=1
```
Tunggu hingga pod Kyverno running:
```bash
kubectl wait --namespace kyverno --for=condition=ready pod -l app.kubernetes.io/name=kyverno --timeout=90s
```

#### Langkah 3: Menerapkan Kebijakan Pembatasan Pod (Zero-Tolerance Policy)
Buat file `hands-on/m02/strict-policy.yaml`:
```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: enforce-pod-hardening
spec:
  validationFailureAction: Enforce
  rules:
    - name: check-security-context
      match:
        any:
          - resources:
              kinds:
                - Pod
      validate:
        message: "PELANGGARAN KEAMANAN: Pod harus non-root, read-only rootfs, drop all capabilities, dan melarang privilege escalation!"
        pattern:
          spec:
            securityContext:
              runAsNonRoot: true
            containers:
              - securityContext:
                  allowPrivilegeEscalation: false
                  readOnlyRootFilesystem: true
                  capabilities:
                    drop:
                      - ALL
```
Terapkan kebijakan:
```bash
kubectl apply -f hands-on/m02/strict-policy.yaml
```

#### Langkah 4: Uji Coba Serangan Penetrasi Admission Control (Negative Test)
Coba deploy pod yang tidak aman. Buat file `hands-on/m02/bad-pod.yaml`:
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: insecure-pod
spec:
  containers:
    - name: attacker
      image: alpine:latest
      command: ["/bin/sh", "-c", "sleep 3600"]
      # Tidak mendefinisikan nonRoot, readOnlyRootFilesystem, dan drop capabilities
```
Jalankan:
```bash
kubectl apply -f hands-on/m02/bad-pod.yaml
```
**Hasil yang Diharapkan:**
Kubernetes API akan langsung menolak deployment dengan pesan:
```
Error from server: error when creating "hands-on/m02/bad-pod.yaml": admission webhook "validate.kyverno.svc-fail" denied the request: 

resource Pod/default/insecure-pod was blocked. The following policies were violated:

enforce-pod-hardening:
  check-security-context: 'PELANGGARAN KEAMANAN: Pod harus non-root, read-only rootfs, drop all capabilities, dan melarang privilege escalation!'
```

#### Langkah 5: Penerapan Deployment Aman (Positive Test)
Buat file `hands-on/m02/good-pod.yaml`:
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: hardened-pod
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 10001
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: secure-app
      image: cgr.dev/chainguard/static:latest
      command: ["/bin/sleep", "3600"]
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities:
          drop:
            - ALL
```
Jalankan:
```bash
kubectl apply -f hands-on/m02/good-pod.yaml
```
Verifikasi status pod:
```bash
kubectl get pods
# Output: hardened-pod   1/1     Running   0          5s
```

#### Langkah 6: Pembersihan Lingkungan Lab
```bash
kind delete cluster --name sec-ops-lab
```

---

### 13. Exercise

#### Level Easy
Buat file manifest Kubernetes berupa `Pod` dengan base image `cgr.dev/chainguard/static`. Pod harus memiliki batasan resource memori maksimal `64Mi`, CPU `100m`, berjalan dengan UID/GID `5000`, me-mount direktori in-memory temporer `/tmp` sebesar `10Mi`, dan tidak me-mount token service account secara otomatis. Simpan manifest dengan nama `hands-on/m02/exercise-easy.yaml`.

#### Level Medium
Buat sebuah `ClusterPolicy` Kyverno yang memverifikasi bahwa:
1.  Hanya image dari domain `ghcr.io/enterprise-approved/*` yang diizinkan untuk dideploy.
2.  Setiap container di dalam pod harus secara eksplisit mendefinisikan batasan `resources.limits.memory` dan `resources.limits.cpu`.
3.  Uji kebijakan tersebut dengan membuat dua manifest: manifest valid dan manifest yang tidak mendefinisikan limits resource. Simpan di `hands-on/m02/exercise-medium.yaml`.

#### Level Hard
Rancang dan konfigurasikan deployment arsitektur sidecar logging menggunakan Fluentbit yang berjalan di samping container utama aplikasi (*distroless*). 
Tantangan:
*   Aplikasi utama menulis file log ke direktori bersama `/var/log/app`.
*   Aplikasi utama berjalan dalam mode `readOnlyRootFilesystem: true`, non-root (`UID 10001`), dan men-drop seluruh Linux capabilities.
*   Container logging Fluentbit berjalan dengan UID berbeda (`UID 20002`), juga memiliki `readOnlyRootFilesystem: true`, dan hanya memiliki izin baca (*read-only*) terhadap direktori share `/var/log/app`.
*   Simpan konfigurasi Pod lengkap beserta konfigurasi `emptyDir` permissions yang tepat di `hands-on/m02/exercise-hard.yaml`.

---

### 14. Challenge

#### Skenario Kasus Kompleks: Serangan Zero-Day Reverse Shell & Evasi eBPF
Anda adalah Lead DevSecOps Architect di sebuah platform pertukaran aset kripto. Tim red team internal berhasil melakukan simulasi serangan:
1.  Mereka menemukan zero-day RCE pada layanan API publik.
2.  Karena image API merupakan image distroless tanpa shell binary (`/bin/sh` atau `/bin/bash`), mereka mengunggah *statically linked binary backdoor* langsung ke dalam memori via syscall `memfd_create` (proses murni *in-memory fileless execution* tanpa menulis ke disk sama sekali).
3.  Binary tersebut membuka koneksi HTTPS terenkripsi keluar (*outbound reverse shell*) ke IP publik penyerang dan mulai membaca secret token database dari environment variable proses lain via akses `/proc`.

#### Instruksi Misi:
Rancang cetak biru pertahanan (*defense architecture document*) komprehensif tanpa merestart pod sehat atau menambah latency lebih dari 5ms:
1.  **Arsitektur Network Policy**: Bagaimana mengunci egress traffic pod sehingga hanya dapat berkomunikasi dengan database internal dan DNS cluster, menolak seluruh koneksi keluar internet tanpa izin?
2.  **Mitigasi Fileless Execution via eBPF**: Rancang aturan konseptual eBPF (Tetragon / Falco) yang dapat mengintersepsi syscall `memfd_create` dan melarang pemanggilan syscall `execveat` yang merujuk pada file descriptor memori (`MFD_CLOEXEC`).
3.  **ProcFS Hardening**: Konfigurasi parameter keamanan kernel Linux apa di level container runtime yang mencegah sebuah proses menelusuri memori atau file descriptor proses lain di host atau pod yang sama?
4.  Dokumentasikan solusi arsitektural lengkap Anda dalam file `hands-on/m02/CHALLENGE-SOLUTION.md`.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic (Pilihan Ganda)

1. **Linux namespace manakah yang bertanggung jawab memetakan UID `0` di dalam container menjadi UID non-privilege di sistem operasi host?**
   * A. PID Namespace
   * B. Mount Namespace
   * C. User Namespace
   * D. IPC Namespace

2. **Apa yang terjadi secara default pada kernel Linux jika sebuah proses container memanggil syscall yang dilarang oleh profil Seccomp dengan konfigurasi `"defaultAction": "SCMP_ACT_ERRNO"`?**
   * A. Kernel me-reboot mesin host seketika.
   * B. Syscall dibatalkan dan mengembalikan kode error sistemik ke aplikasi tanpa mematikan proses.
   * C. Proses langsung dibunuh dengan sinyal `SIGKILL`.
   * D. Kernel mengalihkan panggilan syscall ke antarmuka audit logging saja.

3. **Mengapa penyerang sangat mengincar direktori `/var/run/docker.sock` jika berhasil masuk ke dalam container?**
   * A. Karena direktori tersebut menyimpan source code aplikasi secara unencrypted.
   * B. Karena socket tersebut memungkinkan komunikasi langsung dengan daemon Docker host, memungkinkan pembuatan container baru dengan akses root penuh ke host.
   * C. Karena direktori tersebut menyimpan salinan database production.
   * D. Karena socket tersebut dapat digunakan untuk mengubah sertifikat SSL cluster.

4. **Apa fungsi utama dari parameter `readOnlyRootFilesystem: true` pada SecurityContext Kubernetes?**
   * A. Mencegah container membaca konfigurasi file sistem host.
   * B. Mengunci layer penulisan storage container, mencegah penyerang mengunduh dan menyimpan script atau binary berbahaya ke disk container.
   * C. Memaksa container menyimpan seluruh log langsung ke cloud storage.
   * D. Mematikan fungsi cgroups pada pod.

5. **Manakah dari tool berikut yang memanfaatkan eBPF untuk melakukan intersepsi keamanan dan penindakan ancaman (*real-time kill*) langsung di kernel space?**
   * A. SonarQube
   * B. Trivy
   * C. Cilium Tetragon
   * D. HashiCorp Vault

---

#### B. Pertanyaan Intermediate (Pilihan Ganda)

6. **Mengapa penandatanganan container image menggunakan Cosign Keyless Mode dengan Fulcio dan Rekor dianggap lebih aman untuk enterprise dibandingkan metode penandatanganan PGP tradisional?**
   * A. Karena PGP tidak kompatibel dengan registry OCI.
   * B. Karena Keyless Mode mengeliminasi risiko kebocoran private key statis jangka panjang dengan memanfaatkan token identitas OIDC jangka pendek (ephemeral certificates) dan transparansi log publik.
   * C. Karena Keyless Mode tidak memerlukan koneksi jaringan saat memvalidasi image.
   * D. Karena Fulcio secara otomatis menghapus kerentanan CVE pada image yang ditandatangani.

7. **Perhatikan cuplikan konfigurasi Kubernetes Pod berikut:**
   ```yaml
   securityContext:
     capabilities:
       drop: ["ALL"]
       add: ["NET_ADMIN"]
   ```
   **Apa implikasi keamanan dari konfigurasi di atas?**
   * A. Pod memiliki proteksi penuh dan tidak dapat melakukan perubahan apa pun.
   * B. Seluruh kapabilitas kernel dibuang kecuali hak untuk memanipulasi routing table, antarmuka jaringan, dan aturan iptables/nftables.
   * C. Pod otomatis berjalan sebagai root.
   * D. Pod tidak dapat melakukan panggilan syscall jaringan.

8. **Teknik eksploitasi Time-of-Check to Time-of-Use (TOCTOU) pada monitoring keamanan berbasis `ptrace` atau `auditd` terjadi karena:**
   * A. Registry container belum menerapkan verifikasi signature image.
   * B. Adanya jeda waktu antara saat syscall diperiksa di user space dan saat argumen dieksekusi di kernel space, memungkinkan penyerang menukar argumen memori secara konkuren.
   * C. eBPF memakan terlalu banyak bandwidth memory ring buffer.
   * D. Kubernetes Admission Webhook mengalami timeout.

9. **Jika sebuah Pod membutuhkan penyimpanan data sementara untuk file log lokal, namun SecurityContext mewajibkan `readOnlyRootFilesystem: true`, solusi arsitektural mana yang paling tepat dan aman?**
   * A. Mengubah `readOnlyRootFilesystem` menjadi `false`.
   * B. Menambahkan kapabilitas `CAP_SYS_ADMIN`.
   * C. Me-mount volume `emptyDir` dengan medium `Memory` dan batasan `sizeLimit` pada direktori log spesifik.
   * D. Me-mount direktori host `/var/log` langsung via `hostPath`.

10. **Bagaimana mekanisme eBPF memitigasi celah eksploitasi eskalasi hak akses dibandingkan agent keamanan berbasis userspace?**
    * A. eBPF mengompilasi ulang kernel Linux setiap kali ada pod baru berjalan.
    * B. eBPF membaca konteks eksekusi langsung dari struktur data kernel sebelum proses berpindah ke userspace dan dapat menghentikan thread eksekusi sebelum syscall berbahaya tuntas.
    * C. eBPF mengenkripsi seluruh memori container secara transparan.
    * D. eBPF memblokir semua koneksi HTTP yang tidak menggunakan sertifikat mutual TLS.

---

#### C. Skenario Kasus Produksi (Analisis Situasional)

11. **Skenario Kasus 1: Admission Webhook Failure saat Incident Spiketime**
    Sebuah aplikasi e-commerce mengalami lonjakan trafik transaksi mendadak (*Flash Sale*). Fitur Horizontal Pod Autoscaler (HPA) memicu pembuatan 200 pod baru secara serentak. Pada saat yang sama, node tempat Pod Kyverno Admission Controller berada mengalami degradasi jaringan, menyebabkan API server gagal menghubungi webhook validation dalam batas waktu 10 detik. Kebijakan Kyverno dikonfigurasi dengan `failurePolicy: Fail`.
    *Pertanyaan:* Apa dampak yang terjadi pada kluster, dan bagaimana langkah mitigasi arsitektur high-availability (HA) yang wajib diambil tanpa mengorbankan postur keamanan sistem?

12. **Skenario Kasus 2: Deteksi Kebocoran Metadata AWS IAM via Pod Compromise**
    Seorang engineer keamanan menemukan log AWS CloudTrail yang menunjukkan bahwa instance profile dari Worker Node EKS melakukan aksi `s3:GetObject` pada bucket rahasia perusahaan yang tidak terkait dengan fungsi worker node tersebut. Setelah ditelusuri, sebuah container microservice publik di node tersebut terindikasi disusupi melalui celah injeksi perintah. Container tersebut tidak menggunakan `hostNetwork: true`.
    *Pertanyaan:* Bagaimana penyerang di dalam container tersebut berhasil memperoleh kredensial AWS IAM milik node host, dan konfigurasi platform apa yang gagal diterapkan untuk mencegah hal ini?

13. **Skenario Kasus 3: Breakout Melalui Kerentanan RunC (CVE-2024-21626)**
    Pada awal 2024, ditemukan kerentanan fatal pada `runc` (CVE-2024-21626) di mana kebocoran *file descriptor* internal host (`/sys/fs/cgroup`) memungkinkan proses di dalam container untuk mengakses filesystem host dan melakukan breakout jika container mengarahkan *working directory* (`WORKDIR`) ke path file descriptor tersebut.
    *Pertanyaan:* Pertahanan berlapis (*defense-in-depth*) tingkat platform apa saja yang secara efektif menggagalkan eksploitasi CVE ini meskipun runtime `runc` pada node host belum sempat di-patch ke versi terbaru?

---

### Kunci Jawaban & Pembahasan Quiz

#### Kunci Pilihan Ganda (Basic & Intermediate)
1.  **C**: User Namespace memetakan UID/GID dalam namespace ke UID/GID non-root di host.
2.  **B**: `SCMP_ACT_ERRNO` memblokir syscall dan mengembalikan nilai errno (misal `EPERM` - Operation not permitted) tanpa mematikan proses, berbeda dengan `SCMP_ACT_KILL_PROCESS`.
3.  **B**: Mengakses docker socket sama dengan memberikan kontrol root host penuh karena client dapat memerintahkan daemon membuat container dengan privilege apa pun.
4.  **B**: Mencegah malware menulis file ke filesystem container, memastikan runtime container tetap immutabel.
5.  **C**: Cilium Tetragon beroperasi di tingkat eBPF kernel hooks dan mampu mengirimkan sinyal pembunuhan proses (`SIGKILL`) langsung dari kernel space.
6.  **B**: Menghilangkan masalah pengelolaan dan kebocoran *private key* jangka panjang dengan beralih ke sertifikat identitas berbasis OIDC yang berumur pendek serta tercatat di Rekor transparency log.
7.  **B**: `drop: ["ALL"]` membuang semua privilege, dan `add: ["NET_ADMIN"]` secara selektif hanya memberikan kapabilitas administrasi jaringan.
8.  **B**: TOCTOU terjadi akibat jeda waktu antara pengecekan di userspace dan eksekusi kernel; penyerang menukar pointer memori di antara dua peristiwa tersebut.
9.  **C**: Menggunakan `emptyDir` (di-mount ke memory) melokalisasi hak tulis ke path aman tanpa merusak kebijakan `readOnlyRootFilesystem`.
10. **B**: eBPF terintegrasi di kernel context hooks, membaca data mentah kernel sebelum manipulasi userspace dapat terjadi, dan mampu bertindak deterministik tanpa context switch overhead.

#### Pembahasan Skenario Kasus Produksi
11. **Pembahasan Skenario 1**:
    *   *Dampak*: HPA akan gagal men-scale pod baru. API Server menolak semua pembuatan pod karena webhook Kyverno unreachable dan kebijakan diset ke `failurePolicy: Fail`. Skalabilitas sistem lumpuh.
    *   *Mitigasi*:
        1.  Deploy Admission Controller dengan minimal 3 replika yang disebar di berbagai availability zone menggunakan `podAntiAffinity` dan alokasi resource terjamin (*Guaranteed QoS*).
        2.  Implementasikan `PriorityClass: system-cluster-critical` pada pod Kyverno agar tidak dapat di-evict saat resource node menipis.
        3.  Konfigurasi auto-scaler terpisah untuk komponen admission webhook.
12. **Pembahasan Skenario 2**:
    *   *Vektor Serangan*: Container melakukan query HTTP ke IP metadata link-local AWS (`http://169.254.169.254/latest/meta-data/iam/security-credentials/`) menggunakan IMDSv1 yang tidak memerlukan token autentikasi sesi, sehingga berhasil mencuri IAM role node host.
    *   *Mitigasi*:
        1.  Wajibkan penggunaan IMDSv2 dan atur batas hop jaringan instance metadata menjadi 1 (`http-put-response-hop-limit: 1`). Ini memastikan paket jaringan yang melewati veth interface container (hop > 1) langsung di-drop.
        2.  Gunakan EKS Pod Identity / IRSA sehingga pod hanya menggunakan perannya sendiri, bukan role host.
        3.  Pasang Calico/Cilium NetworkPolicy global yang memblokir akses egress pod menuju `169.254.169.254/32`.
13. **Pembahasan Skenario 3**:
    *   *Mitigasi Berlapis Tanpa Patch*:
        1.  *User Namespaces*: Jika user namespace aktif, proses lolos ke host tetap hanya memiliki hak unprivileged UID di host, bukan root host.
        2.  *Admission Controller*: Kebijakan Kyverno/Gatekeeper memvalidasi manifest dan menolak pod yang mendefinisikan `workingDir` yang mengarah ke `/proc/*` atau path symlink mencurigakan.
        3.  *AppArmor/SELinux*: Profil MAC standar (seperti `runtime/default`) membatasi kemampuan proses container untuk menulis ke direktori cgroup host di luar alokasi spesifiknya.
        4.  *eBPF Runtime Defense*: Tetragon mendeteksi upaya proses mengakses file descriptor di luar root direktori namespace dan langsung menghentikan proses tersebut.

---

### 16. Summary

Membangun arsitektur container kelas enterprise membutuhkan perubahan paradigma: **container bukanlah benteng isolasi mutlak, melainkan sekadar proses Linux biasa yang berbagi kernel.** Keamanan tingkat produksi tidak dapat bergantung pada satu lapisan saja, melainkan harus menerapkan pendekatan pertahanan mendalam (*defense-in-depth*):

1.  **Shift-Left & Cryptographic Supply Chain**: Integritas dimulai dari pembuatan image berbasis minimalis (*distroless*), pemindaian dependensi, pembuatan SBOM, dan penandatanganan keyless (Cosign, Fulcio, Rekor).
2.  **Strict Admission Control**: Menjaga integritas kluster di pintu gerbang Kubernetes API menggunakan Kyverno/Gatekeeper dengan penegakan Pod Security Standard `Restricted`.
3.  **Kernel Sandbox Hardening**: Mengeliminasi hak istimewa di tingkat Linux primitives: isolasi UID via User Namespaces, pemangkasan Linux capabilities (`drop: ALL`), read-only root filesystems, serta pembatasan syscall melalui Seccomp-BPF.
4.  **Active eBPF Runtime Observability**: Melindungi fase operasional secara deterministik dengan eBPF (Tetragon/Falco) yang mampu memonitor event kernel secara real-time dan mengeksekusi mitigasi instan (*in-kernel SIGKILL*) terhadap ancaman zero-day dan container breakout.