# MODUL 08: CLOUD, CONTAINER & VIRTUALIZATION SECURITY
**Kode Modul:** SEC-CCV-08-01  
**Kategori:** 07-Quality-and-Security  

---

## 1. Identitas Modul

| Parameter | Nilai Spesifikasi |
| :--- | :--- |
| **Track Kurikulum** | Cyber Security & Cloud Infrastructure Engineering |
| **Kategori** | 07-Quality-and-Security |
| **Bab** | 08 - Cloud, Container & Virtualization Security |
| **Tingkat Kemahiran** | Advanced (Tingkat 4/4) |
| **Prasyarat Teknis** | Arsitektur Jaringan TCP/IP, Linux Internals (Namespaces, cgroups, Syscalls), Pemrograman Go/Python, Pengalaman Operasional AWS/Azure CLI, Dasar Administrasi Kubernetes |
| **Estimasi Waktu** | 240 Menit (120 Menit Teori Mendalam, 120 Menit Hands-on Lab) |

---

## 2. Learning Objectives (LO-01 s/d LO-08)

Setelah menyelesaikan modul ini, peserta didik mampu:
*   **LO-01:** Menganalisis dan merancang perimeter akses berbasis AWS IAM Policy Evaluation Logic, Permission Boundaries, dan Service Control Policies (SCP) pada multi-account enterprise architecture.
*   **LO-02:** Mengonfigurasi dan mengautomasi deteksi anomali pada audit stream AWS CloudTrail dan Azure Monitor/Activity Logs menggunakan SIEM dan query analitis.
*   **LO-03:** Membedah mekanisme isolasi container tingkat rendah pada Linux Kernel (User/PID/Mount/Net namespaces, cgroups v2, Seccomp profiles, dan Linux Capabilities).
*   **LO-04:** Menerapkan pengerasan (hardening) Docker daemon socket, rootless mode, serta eliminasi vektor container-to-host escape.
*   **LO-05:** Mengimplementasikan pengerasan klaster Kubernetes menyeluruh pada control plane dan worker node (CIS Benchmarks, mTLS etcd, API Server flag hardening, dan Admission Controllers).
*   **LO-06:** Mengonfigurasi Pod Security Standards (PSS) dan Policy-as-Code engines (Kyverno / OPA Gatekeeper) untuk memitigasi privilege escalation workload.
*   **LO-07:** Mengintegrasikan platform Cloud Security Posture Management (CSPM) dan Static Analysis IaC (Infrastructure as Code) ke dalam pipeline DevSecOps CI/CD.
*   **LO-08:** Melakukan investigasi forensik dan mitigasi insiden container escape, kompromi metadata service (IMDSv1/v2), dan eksfiltrasi kredensial cloud.

---

## 3. Concept Map & Architecture Diagram

```
+-------------------------------------------------------------------------------------------------------+
|                                    ENTERPRISE CLOUD ARCHITECTURE                                      |
|                                                                                                       |
|  +-------------------------------------+                +------------------------------------------+  |
|  |       AWS Organizations / Azure AD  |                |         Management / Audit Account       |  |
|  |  +-------------------------------+  |  Audit Stream  |  +------------------------------------+  |  |
|  |  | Service Control Policies (SCP)|=====================>| CloudTrail Lake / S3 WORM Bucket  |  |  |
|  |  +---------------+---------------+  | (KMS Encrypted)|  +------------------+-----------------+  |  |
|  +------------------|------------------+                +---------------------|--------------------+  |
|                     | Enforces Governance                                     | Athena/SIEM Analysis  |
|                     v                                                         v                       |
|  +-------------------------------------------------------------------------------------------------+  |
|  | Workload Account / VPC / Subnet Boundary                                                        |  |
|  |                                                                                                 |  |
|  |  +-------------------------------------------------------------------------------------------+  |  |
|  |  | Kubernetes Control Plane (EKS / Self-Hosted)                                              |  |  |
|  |  |   [API Server] <---(mTLS)---> [etcd Encrypted]                                            |  |  |
|  |  |        |                                                                                  |  |  |
|  |  |        +---> [Validating Admission Webhook: Kyverno / OPA Gatekeeper]                     |  |  |
|  |  +--------|----------------------------------------------------------------------------------+  |  |
|  |           | Scheduled Pod Deployment                                                            |  |
|  |           v                                                                                     |  |
|  |  +-------------------------------------------------------------------------------------------+  |  |
|  |  | Worker Node (Linux Kernel Hardened: CIS Benchmark)                                        |  |  |
|  |  |                                                                                           |  |  |
|  |  |   +-------------------------- KUBELET / CONTAINERD RUNTIME ----------------------------+  |  |
|  |  |   |                                                                                    |  |  |
|  |  |   |  +------------------------------ CONTAINER -------------------------------------+  |  |  |
|  |  |   |  | App Process (UID 10001, Non-Root)                                            |  |  |  |
|  |  |   |  |   - Namespaces: PID, NET, IPC, MNT, UTS, USER                                |  |  |  |
|  |  |   |  |   - cgroups v2: Memory/CPU Hard Caps                                         |  |  |  |
|  |  |   |  |   - Capabilities: CAP_DROP_ALL (no CAP_SYS_ADMIN)                             |  |  |  |
|  |  |   |  |   - Seccomp Profile: BPF Syscall Filtering Default Deny                      |  |  |  |
|  |  |   |  +------------------------------------------------------------------------------+  |  |  |
|  |  |   |         |                                                                           |  |  |
|  |  |   |         | Blocked Attack Vector: Subpath / Unix Socket / CAP_SYS_ADMIN              |  |  |
|  |  |   |         x                                                                           |  |  |
|  |  |   +---------|---------------------------------------------------------------------------+  |  |
|  |  |             |                                                                              |  |
|  |  |   +---------x---------------------+             +---------------------------------------+  |  |
|  |  |   | Host Root FS: /var/run/docker |             | Instance Metadata Service (IMDSv2)    |  |  |
|  |  |   | (Immutable / Protected)       |             | Hop Limit = 1, Session Token Required |  |  |
|  |  |   +-------------------------------+             +---------------------------------------+  |  |
|  |  +-------------------------------------------------------------------------------------------+  |  |
|  +-------------------------------------------------------------------------------------------------+  |
+-------------------------------------------------------------------------------------------------------+
```

---

## 4. Mengapa Ini Penting (Why & Business / Security Impact)

Transisi beban kerja ke lingkungan cloud dan microservices mengubah batasan perimeter keamanan tradisional (firewall berbasis IP) menjadi model perimeter terdistribusi berbasis **Identitas (Identity)** dan **Integritas Runtime Kernel**.

1.  **Dampak Finansial dan Kepatuhan:** Kesalahan konfigurasi akses IAM dan kelemahan perimeter cloud memicu kebocoran data skala masif. Kegagalan kepatuhan terhadap PCI-DSS 4.0, HIPAA, atau GDPR akibat miskonfigurasi storage (misal: S3 bucket publik) atau lateral movement memicu penalti regulasi bernilai puluhan juta dolar.
2.  **Runtuhnya Boundary Isolasi (Container Escape):** Menjalankan container dengan hak istimewa berlebih (`privileged: true`, `CAP_SYS_ADMIN`, atau mounting `/var/run/docker.sock`) mereduksi container menjadi proses Linux biasa tanpa isolasi. Satu kerentanan remote code execution (RCE) pada aplikasi web memungkinkan penyerang menembus host kernel, membaca memori proses tetangga, mengompromikan worker node, dan merebut kredensial IAM host instance profile.
3.  **Lateral Movement Multi-Akun:** Tanpa Service Control Policies (SCP) dan Permission Boundaries, kompromi pada workload non-produksi dapat merembet secara lateral ke infrastruktur produksi melalui assume-role privileges yang berlebihan.
4.  **Supply Chain Poisoning & Drift:** Ketiadaan proteksi IaC scanning dan CSPM memungkinkan developer men-deploy resource dengan celah keamanan kritis ke lingkungan live tanpa pengawasan, menghasilkan konfigurasi sistem yang tidak terdokumentasi (infrastructure drift).

---

## 5. Apa Itu Konsep (What & Definisi Formal Mendalam)

### Cloud Shared Responsibility Model & IAM Boundaries
Arsitektur keamanan cloud berlandaskan pembagian tanggung jawab antara penyedia layanan (CSP) dan pengguna:
*   *Security OF the Cloud:* CSP bertanggung jawab atas fasilitas fisik, hypervisor, dan redundansi infrastruktur dasar.
*   *Security IN the Cloud:* Pelanggan bertanggung jawab atas konfigurasi OS, enkripsi data, firewall jaringan, arsitektur container, dan otorisasi IAM.

**AWS IAM Policy Evaluation Logic:** Proses deterministik untuk mengevaluasi apakah suatu pemanggilan API cloud diizinkan. Mekanismenya mengeksekusi aturan hierarkis:
1.  **Explicit Deny:** Jika ada statement `Deny` yang cocok di tingkat manapun, evaluasi langsung berhenti dengan hasil **DENIED**.
2.  **Organizations Service Control Policy (SCP):** Kebijakan penjaga batas (guardrail) pada tingkat AWS Organizations. SCP tidak memberikan hak akses secara langsung, melainkan menetapkan batas maksimal izin yang dapat diberikan di akun target.
3.  **Resource-based Policy:** Kebijakan yang menempel langsung pada target (misal: S3 Bucket Policy, KMS Key Policy).
4.  **IAM Permissions Boundary:** Mekanisme pembatas hak maksimum yang dialokasikan ke identity (User/Role) untuk mencegah privilege escalation.
5.  **Identity-based Policy:** Kebijakan yang ditempelkan langsung pada IAM Role atau User.
6.  **Implicit Deny:** Jika tidak ditemukan statement `Allow` eksplisit setelah evaluasi, izin ditolak secara default.

### Container Primitives: Linux Isolation
Container bukan virtual machine; container adalah proses biasa pada sistem operasi Linux yang diisolasi oleh empat pilar kernel:
*   **Namespaces:** Mempartisi visibilitas sumber daya sistem (PID, NET, MNT, IPC, UTS, USER, CGROUP).
*   **Control Groups (cgroups v2):** Membatasi, memprioritaskan, dan mengalokasikan konsumsi sumber daya fisik (CPU, Memory, I/O, Network bandwidth, PID exhaustion limit).
*   **Linux Capabilities:** Memecah kekuasaan absolut superuser (`root` / UID 0) menjadi unit-unit hak istimewa terpisah (misal: `CAP_NET_BIND_SERVICE`, `CAP_SYS_PTRACE`, `CAP_SYS_ADMIN`). Default deployment container wajib membuang seluruh kapabilitas (`ALL`) dan hanya menambahkan yang esensial.
*   **Seccomp (Secure Computing Mode):** Filter sistem BPF (Berkeley Packet Filter) yang mencegat dan memblokir pemanggilan syscall yang berpotensi membahayakan kernel (seperti `reboot`, `ptrace`, `sys_chroot`).

### Kubernetes Security Model (The 4Cs)
Model pertahanan berlapis Kubernetes: Cloud, Cluster, Container, Code.
*   **Cluster Hardening:** Perlindungan etcd (datastore absolut K8s) dengan enkripsi data-at-rest dan autentikasi mutual TLS (mTLS); penonaktifan anonymous authentication pada kube-apiserver; audit logging komprehensif; pembaruan versi Kubelet berkala.
*   **Policy-as-Code & Admission Control:** Penggunaan admission controller webhook untuk mencegat manifest sebelum dikomit ke etcd, memvalidasi dan memaksakan aturan Pod Security Standards (Privileged, Baseline, Restricted).

---

## 6. Bagaimana Cara Kerjanya (How & Mekanika Internal Arsitektur)

### Evaluasi IAM Permissions Boundary & Cross-Account Role Assume
Ketika sebuah entitas (misal: Pod via IRSA - IAM Roles for Service Accounts) memanggil `sts:AssumeRole` untuk mengakses resource di akun target, alur evaluasi internal AWS bekerja sebagai berikut:

```
[ Request Context ] 
        |
        v
+-----------------------------+
| Is there an Explicit Deny?  | === YES ===> [ ACCESS DENIED ]
+-----------------------------+
        | NO
        v
+-----------------------------+
| Is Action allowed by SCP?   | === NO ====> [ ACCESS DENIED ]
+-----------------------------+
        | YES
        v
+-----------------------------+
| Within Permission Boundary? | === NO ====> [ ACCESS DENIED ]
+-----------------------------+
        | YES
        v
+-----------------------------+
| Identity / Resource Policy  | === NO ====> [ ACCESS DENIED ]
|       allows Action?        |
+-----------------------------+
        | YES
        v
[ ACCESS GRANTED ]
```

### Mekanisme Isolasi Syscall dengan Seccomp-BPF
Runtime container (misal: containerd/runc) memuat aturan seccomp melalui syscall `prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, ...)`. Program BPF dikompilasi ke dalam kernel space. Setiap kali thread aplikasi memicu `syscall`, filter BPF mengeksekusi pemeriksaan register secara langsung:
1. Syscall dibaca dari register CPU (misal: `rax` pada arsitektur x86_64).
2. Register dicocokkan dengan whitelist seccomp.
3. Jika instruksi terlarang (misal: `sys_clone` dengan flag namespace baru saat `CAP_SYS_ADMIN` dicabut), kernel langsung merespons dengan aksi terdefinisi: `SECCOMP_RET_ERRNO` (mengembalikan error `EPERM`) atau `SECCOMP_RET_KILL_PROCESS` (terminasi proses instan).

### Kubernetes Admission Pipeline Execution
API Server mengeksekusi pemrosesan request HTTP REST melalui tahapan serial yang ketat:

```
[ HTTP POST Manifest ]
         |
         v
+------------------+     +------------------+     +-------------------------------+
|  Authentication  | --> |  Authorization   | --> | Mutating Admission Webhook    |
| (TLS / Webhook)  |     |   (RBAC Checks)  |     | (Inject Sidecars / Defaults)  |
+------------------+     +------------------+     +---------------+---------------+
                                                                  |
                                                                  v
+------------------+     +------------------+     +-------------------------------+
|   etcd Storage   | <-- | Schema Validation| <-- | Validating Admission Webhook  |
|  (Persistence)   |     |    (OpenAPI)     |     | (Enforce Kyverno / Gatekeeper)|
+------------------+     +------------------+     +-------------------------------+
```
Jika satu saja Validating Webhook mengembalikan status `reject`, seluruh siklus pembuatan objek dibatalkan dan API Server mengembalikan HTTP code `403 Forbidden`.

---

## 7. Perbandingan Paradigma / Taksonomi Matriks

| Atribut / Metrik | Virtual Machines (KVM / Xen) | Standard Containers (Docker / containerd) | Sandboxed Containers (gVisor / runsc) | MicroVMs (AWS Firecracker) |
| :--- | :--- | :--- | :--- | :--- |
| **Batas Isolasi** | Hardware-level (Hypervisor, VT-x/AMD-V) | OS Kernel-level (Namespaces, cgroups) | User-space Application Kernel (Sentry) | Minimal Hypervisor (KVM-backed) |
| **Kernel Sharing** | Tidak (Guest OS memiliki kernel independen) | Ya (Berbagi kernel host langsung) | Tidak (Syscall ditranslasikan di user-space) | Tidak (Kernel guest terisolasi minimal) |
| **Startup Overhead** | Tinggi (~10 - 60 detik) | Sangat Rendah (~100 - 500 ms) | Rendah (~300 - 800 ms) | Sangat Rendah (~5 - 50 ms) |
| **Memory Footprint** | Gigabytes | Megabytes (~10 - 50 MB) | Megabytes (~30 - 70 MB) | Sangat Ringan (~5 MB) |
| **Syscall Attack Surface**| Terbatas ke interface hypervisor emulasi | Sangat Luas (>300 raw kernel syscalls) | Sangat Kecil (Intersepsi via Sentry) | Sangat Kecil (Driver virtual minimal virtio) |
| **Kasus Penggunaan Optimal** | Multi-tenant un-trusted enterprise workloads | Internal trusted workloads, monolithic apps | Multi-tenant SaaS, parsing file untrusted | Serverless compute, functions-as-a-service |

---

## 8. Analisis Mendalam Attack Surface & Vector Matrix

| Komponen | Vektor Serangan | Kerentanan / Konfigurasi Rentan | Teknik Eksploitasi | Dampak | Pemetaan MITRE ATT&CK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Cloud IAM** | Cross-Account Lateral Movement | Over-permissive `sts:AssumeRole` policy tanpa ExternalId / Conditions | Eksploitasi SSRF untuk mencuri instance credentials, lalu asumsi role tingkat target admin | Kompromi total resource akun target | T1078 (Valid Accounts), T1552 (Unsecured Credentials) |
| **Cloud IMDS** | Metadata Credential Harvesting | Penggunaan IMDSv1 (tidak membutuhkan token sesi HTTP PUT) | Injeksi SSRF pada aplikasi web untuk mengambil token dari `http://169.254.169.254/latest/meta-data/` | Pencurian temporary security token instance host | T1552.005 (Cloud Instance Metadata API) |
| **Docker Engine** | Host Takeover via Docker Socket | Host mounting `/var/run/docker.sock` ke dalam container workload | Mengirim instruksi ke socket lokal untuk spin-up container privileged dengan host root mount: `-v /:/host` | Arbitrary host code execution, root escalation | T1611 (Escape to Host) |
| **Linux Kernel** | Container Escape | Penggunaan flag `securityContext.privileged: true` | Pemanfaatan `cgroups release_agent` untuk mengeksekusi shell script arbitrary di root kernel host | Pengambilalihan node fisik/virtual seutuhnya | T1611 (Escape to Host), T1068 (Privilege Escalation) |
| **Kubernetes API**| Unauthenticated Control Plane Access | Flag `--anonymous-auth=true` aktif dengan binding `cluster-admin` ke `system:anonymous` | Pengiriman instruksi HTTP REST ke API Server port 6443 secara publik untuk deploy malicious pods | Klaster kompromi total, penyisipan cryptocurrency miner | T1190 (Exploit Public-Facing Application) |
| **IaC Pipeline** | Supply Chain Infrastructure Poisoning | Ketiadaan static linting pada Terraform/CloudFormation code di CI | Injeksi konfigurasi S3 `acl = "public-read"` atau Security Group `0.0.0.0/0` ingress port 22 | Perimeter network terekspos, kebocoran data sensitif | T1584.004 (Compromise Software Dependencies) |

---

## 9. Code Example Sederhana (Minimal & Clear)

### Dockerfile Hardening & Non-Root Execution
Membangun container image yang menerapkan prinsip least-privilege secara bawaan:

```dockerfile
# Multi-stage build untuk mengeliminasi build tools dari runtime image
FROM golang:1.22-alpine AS builder
WORKDIR /src
COPY app.go .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -o secure-app app.go

# Production Runtime Stage
FROM alpine:3.19

# Buat grup dan pengguna non-root dengan UID/GID deterministik
RUN addgroup -g 10001 -S appgroup && \
    adduser -u 10001 -S appuser -G appgroup

# Set atribut sistem file menjadi read-only, kecuali temporary path eksplisit
WORKDIR /home/appuser
COPY --from=builder --chown=10001:10001 /src/secure-app /usr/local/bin/secure-app

# Copot Linux Capabilities yang tidak esensial
USER 10001:10001

# Ekspos port non-privileged (>1024)
EXPOSE 8080

# Deklarasi immutable root filesystem
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD ["/usr/local/bin/secure-app", "--healthcheck"] || exit 1

ENTRYPOINT ["/usr/local/bin/secure-app"]
```

### Kubernetes Pod Security: Baseline Manifest Non-Root
Manifest Kubernetes Pod yang mematuhi standar Pod Security Standards (PSS) Restricted:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: secured-workload
  namespace: production
  labels:
    app.kubernetes.io/name: payment-processor
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 10001
    runAsGroup: 10001
    fsGroup: 10001
    seccompProfile:
      type: RuntimeDefault
  containers:
  - name: processor
    image: payment-registry.internal/processor:v1.4.0
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities:
        drop:
        - ALL
    volumeMounts:
    - mountPath: /tmp
      name: ephemeral-tmp
    resources:
      limits:
        cpu: "500m"
        memory: "256Mi"
      requests:
        cpu: "100m"
        memory: "128Mi"
  volumes:
  - name: ephemeral-tmp
    emptyDir: {}
```

---

## 10. Code Example Lanjutan (Production-Ready / Hardening / Exploit Analysis)

### 1. Terraform AWS IAM Permission Boundary Policy (Defense-in-Depth)
Implementasi Policy-as-Code Terraform yang membatasi eskalasi privilege developer:

```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Boundary Policy: Membatasi hak maksimum dari role apa pun yang dibuat
resource "aws_iam_policy" "developer_boundary" {
  name        = "DeveloperPermissionBoundary"
  description = "Mencegah eskalasi privilege dan manipulasi IAM di luar batas yang ditentukan"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DenyIAMPolicyAlteration"
        Effect = "Deny"
        Action = [
          "iam:CreatePolicyVersion",
          "iam:DeletePolicy",
          "iam:DeletePolicyVersion",
          "iam:SetDefaultPolicyVersion",
          "iam:DeleteRolePermissionsBoundary",
          "iam:PutRolePermissionsBoundary"
        ]
        Resource = "*"
      },
      {
        Sid    = "DenyCloudTrailTampering"
        Effect = "Deny"
        Action = [
          "cloudtrail:DeleteTrail",
          "cloudtrail:StopLogging",
          "cloudtrail:UpdateTrail"
        ]
        Resource = "*"
      },
      {
        Sid    = "AllowedActions"
        Effect = "Allow"
        Action = [
          "s3:*",
          "dynamodb:*",
          "ec2:*",
          "sqs:*",
          "sns:*"
        ]
        Resource = "*"
      }
    ]
  })
}

# IAM Role Developer yang diikat secara paksa dengan Boundary
resource "aws_iam_role" "application_developer" {
  name                 = "AppDevExecutionRole"
  permissions_boundary = aws_iam_policy.developer_boundary.arn

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}
```

### 2. Kyverno ClusterPolicy: Menggagalkan Privilege Escalation dan Host Mounting
Policy-as-Code enterprise pada Kubernetes engine untuk mencegah mutasi insecure workload:

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: disallow-privileged-and-host-mounts
  annotations:
    policies.kyverno.io/title: Disallow Privileged Containers and Host Sockets
    policies.kyverno.io/severity: critical
    policies.kyverno.io/description: >-
      Mencegah eksekusi container berkategori privileged, hostPID, hostNetwork,
      serta mencegah mounting docker/containerd unix socket ke dalam Pod.
spec:
  validationFailureAction: Enforce
  background: true
  rules:
  - name: validate-privileged-and-namespaces
    match:
      any:
      - resources:
          kinds:
          - Pod
    validate:
      message: >-
        Penggunaan privileged mode, hostPID, dan hostNetwork dilarang keras
        untuk memenuhi standar CIS Kubernetes Benchmark.
      pattern:
        spec:
          =(hostPID): false
          =(hostNetwork): false
          =(hostIPC): false
          containers:
          - securityContext:
              =(privileged): false
              =(allowPrivilegeEscalation): false
  - name: block-docker-socket-mount
    match:
      any:
      - resources:
          kinds:
          - Pod
    validate:
      message: "Dilarang me-mount /var/run/docker.sock atau soket runtime lainnya ke dalam pod."
      pattern:
        spec:
          =(volumes):
          - =(hostPath):
              path: "!/var/run/docker.sock & !/run/containerd/containerd.sock"
```

---

## 11. Diagram Alur Serangan & Mitigasi

Berikut adalah alur serangan *Container Breakout* melalui soket Docker yang diekspos, serta mekanisme mitigasi preventifnya:

```
ATTACK PATH (UNMITIGATED)                     MITIGATION ARCHITECTURE (HARDENED)
=========================                     ==================================

+-------------------------------+             +-------------------------------+
| Attacker exploits Web App RCE |             | Attacker exploits Web App RCE |
+---------------+---------------+             +---------------+---------------+
                |                                             |
                v                                             v
+-------------------------------+             +-------------------------------+
| Attacker discovers exposed    |             | Kyverno / Admission Control   |
| socket: /var/run/docker.sock  |             | DENIES mounting host sockets  |
+---------------+---------------+             +---------------+---------------+
                |                                             |
                v                                             v (Execution Blocked)
+-------------------------------+             +-------------------------------+
| Sends API Command to Engine:  |             | Container Runtime Profile:    |
| docker run -v /:/host-root    |             | - ReadOnlyRootFilesystem=true |
+---------------+---------------+             | - Seccomp: RuntimeDefault     |
                |                             | - AppArmor / SELinux Active   |
                v                             +-------------------------------+
+-------------------------------+                             |
| Writes root SSH key or        |                             v
| crontab on Host Node Filesystem             [ EXPLOIT CHAIN BROKEN ]
+---------------+---------------+
                |
                v
+-------------------------------+
| Node Compromised: Queries     |             +-------------------------------+
| IMDSv1 to harvest AWS Keys    |             | IMDSv2 Enforced: Requires PUT |
+---------------+---------------+             | HTTP Token; Hop-Limit = 1;   |
                |                             | Container blocked from IMDS   |
                v                             +-------------------------------+
[ LATERAL MOVEMENT: CLOUD ADMIN ]                             |
                                                              v
                                              [ AUDIT: CloudTrail Alerts Sent ]
```

---

## 12. Trade-offs & Security vs Usability / Performance

1.  **Seccomp Profile Strictness vs Kompatibilitas Aplikasi:**
    *   *Trade-off:* Menerapkan profil Seccomp `RuntimeDefault` atau whitelist custom berbasis BPF menurunkan risiko eksekusi syscall exploit secara drastis, tetapi dapat mematahkan eksekusi framework legacy (misal: JVM profiling, runtime Go lama yang memanggil syscall usang).
    *   *Resolusi:* Lakukan audit logging (`SECCOMP_RET_LOG`) di cluster pengujian (staging) minimal 14 hari kerja untuk memetakan syscall baseline sebelum mengubah aksi ke `SECCOMP_RET_ERRNO` atau `SECCOMP_RET_KILL`.
2.  **IMDSv2 Hop Limit Enforcement vs Arsitektur Overlay Network:**
    *   *Trade-off:* Mengatur nilai `http-put-response-hop-limit` menjadi `1` pada AWS EC2 memblokir eksfiltrasi credential dari container pods (karena paket melewati IP hop virtual veth). Namun hal ini mematikan fungsionalitas container yang memang secara sah memerlukan otentikasi via instance profile (jika tidak menggunakan IRSA).
    *   *Resolusi:* Migrasi penuh dari Node Instance Profile ke AWS IRSA (IAM Roles for Service Accounts) atau EKS Pod Identity.
3.  **Rootless Containers vs Pengikatan Low-Number Ports:**
    *   *Trade-off:* Container tanpa root tidak dapat mengikat port jaringan di bawah 1024 (misal: port 80, 443) secara langsung tanpa mengubah flag kernel `net.ipv4.ip_unprivileged_port_start`.
    *   *Resolusi:* Konfigurasi container untuk mendengarkan port non-root (misal: 8080/8443) lalu gunakan Ingress Controller atau Load Balancer untuk melakukan terminasi port standar internet.
4.  **Mutual TLS (mTLS) Service Mesh vs Latensi Jaringan:**
    *   *Trade-off:* Mengimplementasikan zero-trust encryption intra-cluster (misal: Istio mTLS strict) menjamin privasi traffic antarpod, namun menghasilkan penambahan CPU usage overhead (~10-15%) dan penambahan latensi (~2-5ms per request hop).

---

## 13. Edge Cases & Complex Failure Modes

1.  **IMDSv2 Hop-Limit Pitfall pada Nested Virtualization/CNI Pods:**
    Ketika EC2 dikonfigurasi dengan `http-put-response-hop-limit: 1`, paket HTTP PUT dari container yang berjalan di dalam Pod CNI (seperti Calico atau Cilium dalam mode tunneling VXLAN) akan mengalami pengurangan Time-To-Live (TTL). Akibatnya, paket di-drop oleh interface hypervisor AWS. Jika aplikasi bergantung pada SDK resmi yang tidak dikonfigurasi timeout secara benar, aplikasi akan mengalami dead-lock koneksi (hang) tanpa pesan error eksplisit.
2.  **SubPath Mount File Replacement Race Condition (CVE-2021-25741):**
    Penggunaan fitur `volumeMounts.subPath` di Kubernetes dapat dimanipulasi dengan eksploitasi symlink race condition. User lokal container dapat menukar direktori target mount dengan symlink yang mengarah ke host path host sebelum mount engine Linux merampungkan locking namespace, menghasilkan mount point arbitrary pada host node root.
3.  **etcd Split-Brain Akibat Key Rotation yang Gagal:**
    Saat merotasi Certificate Authority (CA) etcd cluster yang terdistribusi secara asinkron, salah satu node etcd yang kehilangan quorum TLS akan mengisolasi dirinya sendiri. Kondisi ini menyebabkan API Server gagal melakukan sinkronisasi state Pod, menghasilkan penghapusan pod massal secara keliru (false node eviction) oleh Kubelet Controller Manager.
4.  **Linux Kernel cgroup v1 OOM Inefficiency vs cgroup v2 Unified Hierarchy:**
    Pada cgroup v1, pelacak alokasi memori buffer IO page cache terpisah dari anonymous memory limits. Workload intensif IO dapat memicu Out-Of-Memory (OOM) Killer membunuh proses utama database/web, padahal host memiliki kapasitas memori swap yang cukup. Migrasi ke cgroup v2 wajib dilakukan untuk unified memory and writeback accounting.

---

## 14. Anti-Patterns & Common Vulnerabilities

Berikut adalah pola implementasi keliru yang sering dijumpai di lingkungan cloud-native beserta koreksi arsitekturalnya:

### Anti-Pattern 1: Penggunaan Wildcard pada IAM Actions dan Resources
```json
// SANGAT TIDAK AMAN: Memberikan akses root lateral tak terkendali
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "*",
      "Resource": "*"
    }
  ]
}
```
*Koreksi Arsitektural:*
Terapkan least-privilege matrix dengan aksi spesifik dan conditional tag binding:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::corporate-customer-data-prod/*",
      "Condition": {
        "Bool": { "aws:SecureTransport": "true" }
      }
    }
  ]
}
```

### Anti-Pattern 2: Menjalankan Container Menggunakan Default Root User
```dockerfile
# SANGAT TIDAK AMAN: Default UID adalah 0 (root)
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y nginx
CMD ["nginx", "-g", "daemon off;"]
```
*Koreksi Arsitektural:*
Inisialisasi dedicated low-privilege system account dan enforce directive `USER` di Dockerfile atau via `runAsNonRoot: true` pada Pod context.

### Anti-Pattern 3: Flat Network Topology pada Kubernetes
Deploy aplikasi tanpa `NetworkPolicy` memungkinkan pod front-end (yang terekspos ke internet) terhubung langsung ke port administratif pod backend database atau API internal.  
*Koreksi Arsitektural:*
Definisikan default-deny network policy di seluruh namespace secara wajib:
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: production
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
```

---

## 15. Best Practices & Enterprise Remediation Guide

1.  **Enforce AWS Service Control Policies (SCP) Multi-Account Baseline:**
    *   Wajibkan enkripsi pada seluruh volume EBS: larang `ec2:CreateVolume` tanpa KMS.
    *   Larang pematian CloudTrail dan VPC Flow Logs di seluruh akun anak (child accounts).
    *   Batasi wilayah geospasial deployment AWS (Region Restriction) untuk mereduksi footprint serangan.
2.  **Hardening Docker Engine (`/etc/docker/daemon.json`):**
    Terapkan konfigurasi defensif berikut di seluruh worker host virtual:
    ```json
    {
      "icc": false,
      "userns-remap": "default",
      "log-driver": "journald",
      "no-new-privileges": true,
      "live-restore": true,
      "userland-proxy": false,
      "seccomp-profile": "/etc/docker/seccomp-hardened.json"
    }
    ```
3.  **Enforce Immutable Infrastructure:**
    *   Tutup akses SSH/RDP port menuju Kubernetes worker node. Gunakan AWS SSM Session Manager atau ephemeral debug containers untuk troubleshooting terautentikasi.
    *   Gunakan distro minimalis berfokus container seperti Talos Linux, Flatcar, atau AWS Bottlerocket yang memiliki rootfs berstatus immutable (`read-only`) secara native.
4.  **Static IaC Security Pipeline Integration:**
    *   Jalankan scanner `tfsec`, `trivy`, atau `checkov` di pre-commit hooks dan GitHub Actions pipeline.
    *   Gagalkan *build* secara otomatis jika teridentifikasi rule berkategori level *High* atau *Critical* (misal: S3 Public Access, Open Security Groups).

---

## 16. Hands-on Lab Step-by-Step

### Skenario Lab
Anda bertugas mengaudit dan memperkuat keamanan worker node, melarang container privileged melalui Kyverno Admission Controller, serta menganalisis jejak kompromi IAM dari CloudTrail log telemetry.

#### Langkah 1: Verifikasi dan Hardening Docker Daemon Runtime
Masuk ke terminal server Linux dan modifikasi konfigurasi daemon untuk mematikan inter-container communication (ICC) dan membatasi eskalasi privilege.

```bash
# 1.1 Buat backup file konfigurasi lama jika ada
sudo cp /etc/docker/daemon.json /etc/docker/daemon.json.bak 2>/dev/null || true

# 1.2 Injeksi konfigurasi hardening ke /etc/docker/daemon.json
sudo tee /etc/docker/daemon.json << 'EOF'
{
  "icc": false,
  "no-new-privileges": true,
  "live-restore": true,
  "storage-driver": "overlay2"
}
EOF

# 1.3 Restart Docker daemon dan pastikan status service berjalan normal
sudo systemctl restart docker
sudo docker info --format '{{.SecurityOptions}}'
# Verifikasi output harus memuat: [name=seccomp,profile=builtin name=no-new-privileges]
```

#### Langkah 2: Simulasi Penolakan Workload Menggunakan Kyverno Policy
Uji efektivitas Policy-as-Code engine di cluster Kubernetes lokal (Minikube / KinD).

```bash
# 2.1 Pasang Kyverno ke dalam klaster via Helm atau Release Manifest resmi
kubectl create -f https://github.com/kyverno/kyverno/releases/download/v1.11.4/install.yaml

# Tunggu hingga pods kyverno masuk ke tahap Running
kubectl wait --namespace kyverno --for=condition=ready pod --selector=app.kubernetes.io/instance=kyverno --timeout=90s

# 2.2 Terapkan Policy yang menolak container berstatus privileged
kubectl apply -f - << 'EOF'
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: block-privileged-exec
spec:
  validationFailureAction: Enforce
  rules:
  - name: check-privileged
    match:
      any:
      - resources:
          kinds:
          - Pod
    validate:
      message: "Kebijakan Keamanan: Container dengan hak istimewa (privileged) dilarang!"
      pattern:
        spec:
          containers:
          - securityContext:
              privileged: false
EOF

# 2.3 Coba deploy manifest pod penyerang (Eksploitasi)
kubectl apply -f - << 'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: malicious-privileged-pod
spec:
  containers:
  - name: exploit
    image: alpine:latest
    command: ["sleep", "3600"]
    securityContext:
      privileged: true
EOF
```
*Hasil Verifikasi:* Deployment harus diblokir oleh Kubernetes API Server dengan pesan error:
```
Error from server: error when creating "STDIN": admission webhook "validate.kyverno.svc-fail" denied the request: 
Policy block-privileged-exec failed that contains check-privileged: Kebijakan Keamanan: Container dengan hak istimewa (privileged) dilarang!
```

#### Langkah 3: Forensik Telemetri AWS CloudTrail Menggunakan SQL (Athena Engine)
Analisis aktivitas anomali di mana kredensial sementara digunakan dari luar IP korporat:

```sql
-- Query investigasi: Identifikasi kompromi AssumeRole dan pemanggilan API sensitif
SELECT 
    eventTime,
    userIdentity.arn AS assumed_role_arn,
    sourceIPAddress,
    eventName,
    awsRegion,
    userAgent,
    errorCode,
    errorMessage
FROM 
    cloudtrail_logs_db.cloudtrail_events
WHERE 
    eventName IN ('GetSecretValue', 'AuthorizeSecurityGroupIngress', 'CreateUser')
    AND sourceIPAddress NOT LIKE '198.51.100.%' -- Representasi CIDR Block Corporate VPN
    AND eventTime >= '2024-03-01T00:00:00Z'
ORDER BY 
    eventTime DESC 
LIMIT 50;
```

---

## 17. Real-world Case Study & Incident Analysis Enterprise

### Insiden Eksfiltrasi Data Finansial Cloud Skala Besar (Analisis Kasus Model SSRF-to-IMDS)
*   **Vektor Akses Awal:** Penyerang menemukan endpoint open-source Web Application Firewall (WAF) berbasis cloud yang salah dikonfigurasi, memungkinkan request parsing HTTP proxy terbalik (SSRF - Server-Side Request Forgery).
*   **Teknik Eksploitasi:**
    1.  Penyerang mengirim HTTP request yang memanipulasi header upstream untuk menargetkan IP lokal link: `http://169.254.169.254/latest/meta-data/iam/security-credentials/`.
    2.  Karena sistem host masih menggunakan **IMDSv1**, tidak ada kewajiban token flow (PUT request dengan header autentikasi). Server mengembalikan temporary AccessKeyId, SecretAccessKey, dan SessionToken milik IAM Role host EC2.
    3.  IAM Role yang diekstrak ternyata memiliki konfigurasi policy over-permissive `AmazonS3FullAccess`.
    4.  Penyerang mengonfigurasi AWS CLI lokal mereka menggunakan kredensial hasil curian, menjalankan perintah `aws s3 sync`, dan mengunduh puluhan terabyte data riwayat pengajuan kartu kredit pelanggan.
*   **Akar Masalah (Root Cause):**
    1.  Aplikasi rentan terhadap SSRF.
    2.  EC2 instance tidak memaksakan implementasi IMDSv2 (`HttpTokens=required`).
    3.  Pelanggaran Least Privilege: Role komputasi front-end diberikan akses langsung level administrasi ke seluruh bucket S3 storage backend.
*   **Arsitektur Solusi (Remediation Plan):**
    1.  *Enforce IMDSv2:* Memperbarui atribut seluruh EC2 via Launch Template:
        ```bash
        aws ec2 modify-instance-metadata-options \
          --instance-id i-0123456789abcdef0 \
          --http-tokens required \
          --http-put-response-hop-limit 1
        ```
    2.  *Implementasi Permissions Boundary:* Seluruh role aplikasi dibatasi secara strictly melalui boundary policy dan SCP organisasi.
    3.  *Deteksi Aktif:* Memasang deteksi AWS GuardDuty untuk alert tipe `UnauthorizedAccess:IAMUser/InstanceCredentialExfiltration.OutsideAWS`.

---

## 18. Quiz Pemahaman & Challenge

### Soal Pilihan Ganda Multi-Jawaban / Kompleks

#### Pertanyaan 1
Dalam arsitektur AWS IAM, sebuah IAM Role memiliki policy identity-based yang mengizinkan (`Allow`) aksi `s3:GetObject` pada seluruh bucket. Namun, Service Control Policy (SCP) pada AWS Organizations account tersebut menetapkan `Deny` untuk aksi `s3:*` kecuali jika request berasal dari VPC endpoint korporat tertentu. Bagaimana hasil evaluasi jika request `s3:GetObject` datang dari internet publik tanpa melalui VPC endpoint yang disyaratkan?
- A. Permintaan diizinkan karena identity-based policy memprioritaskan hak akses pengguna lokal.
- B. Permintaan ditolak karena SCP Deny dievaluasi secara otoritatif di atas identity policy dan bertindak sebagai explicit guardrail.
- C. Permintaan akan diteruskan ke Resource Policy bucket untuk mengambil keputusan penentu.
- D. AWS STS akan meminta token MFA tambahan sebelum mengizinkan aksi.

#### Pertanyaan 2
Konfigurasi isolasi keamanan container manakah yang secara efektif memblokir upaya eksploitasi escape kernel Linux berbasis manipulasi manipulasi driver perangkat dan mounting raw block devices?
- A. `readOnlyRootFilesystem: false` dan `runAsUser: 0`.
- B. Membuang seluruh Linux Capabilities (`drop: ["ALL"]`) dan menyetel `allowPrivilegeEscalation: false`.
- C. Memasang volume mount `/dev:/dev` dengan atribut `readOnly: true`.
- D. Mengaktifkan flag `hostPID: true` di pod specification.

#### Pertanyaan 3
Mengapa mitigasi IMDSv2 dengan menyetel parameter `http-put-response-hop-limit = 1` efektif dalam melindungi worker node containerized dari ancaman eksfiltrasi SSRF kredensial host?
- A. Karena IMDSv2 menggunakan protokol enkripsi TLS yang memverifikasi sertifikat x509 pod.
- B. Karena paket IP routing layer 3 dari container pod menuju interface virtual metadata di node host akan melewati batasan satu hop (TTL = 1 kedaluwarsa saat transit dari bridge/veth interface), sehingga request dari Pod di-drop secara hardware/kernel level.
- C. Karena IMDSv2 menghapus seluruh endpoint penyimpanan security token.
- D. Karena IMDSv2 mewajibkan AWS IAM Authenticator diinstal di setiap pod client.

---

### Challenge Terapan (Hands-on Mini-Lab Scenario)

**Nama Challenge:** Operation Hardened Perimeter  
**Deskripsi Skenario:**  
Anda diberikan sebuah manifest Kubernetes deployment aplikasi Node.js legacy yang memiliki tingkat kerentanan tinggi:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: legacy-app
spec:
  replicas: 1
  selector:
    matchLabels:
      app: legacy
  template:
    metadata:
      labels:
        app: legacy
    spec:
      hostPID: true
      hostNetwork: true
      containers:
      - name: web
        image: nginx:latest
        securityContext:
          privileged: true
        volumeMounts:
        - mountPath: /var/run/docker.sock
          name: dockersock
      volumes:
      - name: dockersock
        hostPath:
          path: /var/run/docker.sock
```

**Tugas Eksekusi:**
1.  Tuliskan kembali manifest Kubernetes di atas menjadi manifest production-grade yang menerapkan **Pod Security Standards (PSS) Restricted** secara penuh.
2.  Tulis satu file OPA (Open Policy Agent) Rego Rule yang akan mengevaluasi manifest tersebut dan menolak validasi jika menemukan atribut `privileged: true` atau `hostPID: true`.

---

### Kunci Jawaban & Evaluasi Quiz

*   **Jawaban Pertanyaan 1:** **B**. Mekanisme evaluasi policy AWS menempatkan Organizations SCP sebagai batas terluar. Adanya eksplisit `Deny` pada SCP yang tidak memenuhi kriteria pengecualian akan menghentikan alur evaluasi secara instan, menghasilkan status **Denied**, mengabaikan statement `Allow` pada Identity-based policy.
*   **Jawaban Pertanyaan 2:** **B**. Dengan mencabut seluruh kapabilitas (`drop: ["ALL"]`) serta mengunci flag eskalasi (`allowPrivilegeEscalation: false`), proses di dalam container kehilangan `CAP_SYS_ADMIN`, `CAP_MKNOD`, dan `CAP_SYS_RAWIO` yang dibutuhkan untuk memanipulasi hardware node atau memicu kernel escape.
*   **Jawaban Pertanyaan 3:** **B**. Arsitektur networking container (misal: veth pairs atau overlay bridges) merepresentasikan setidaknya satu layer-3 network hop tambahan dari container namespace ke root namespace host. Jika EC2 menyetel IP TTL/hop limit IMDSv2 ke `1`, hypervisor network stack akan men-drop paket PUT response sebelum sempat kembali ke dalam container.

---

## 19. Summary & Key Takeaways

```
+--------------------------------------------------------------------------------------------------+
|                                    DEFENSE-IN-DEPTH MATRIX                                       |
+---------------------+----------------------------------------------------------------------------+
| Cloud Control Plane | Enforce SCP Multi-Account Boundaries + WORM Storage untuk CloudTrail Audit  |
+---------------------+----------------------------------------------------------------------------+
| Node & OS Layer     | Hardening via CIS Benchmarks, immutable rootfs, enforce IMDSv2 (Hop=1)      |
+---------------------+----------------------------------------------------------------------------+
| Container Runtime   | No-new-privileges, rootless execution, drop CAP_ALL, enforce RuntimeDefault|
+---------------------+----------------------------------------------------------------------------+
| Cluster Orchestrator| Kyverno / OPA Admission Controllers, Strict PSS, Default-Deny NetworkPolicy |
+---------------------+----------------------------------------------------------------------------+
| Pipeline (Shift-Left| Static IaC Scanning (Checkov/Trivy) blocking insecure code before apply    |
+---------------------+----------------------------------------------------------------------------+
```

*   **Boundary adalah Kunci:** Perimeter keamanan modern tidak ditentukan oleh subnet semata, melainkan oleh perpaduan antara **AWS SCP / Azure Management Groups**, **IAM Boundaries**, dan **Kubernetes Admission Control**.
*   **Container Bukan Sandbox Virtual:** Proses container berjalan di atas kernel Linux host yang sama. Mengizinkan container berjalan dalam mode `privileged` sama dengan memberikan akses superuser penuh ke seluruh mesin host fisik/virtual.
*   **IMDSv2 adalah Standar Mutlak:** Migrasi ke IMDSv2 dengan membatasi network hop limit ke 1 memitigasi sebagian besar dampak serangan berbasis SSRF pada lingkungan komputasi cloud.
*   **Shift-Left & Shield-Right:** Validasi keamanan statis pada IaC dan image registry wajib dikombinasikan dengan pengawasan runtime defensif (admission controller webhook, runtime threat detection seperti Falco).

---

## 20. Referensi Resmi & Standar Keamanan

1.  **CIS Security Benchmarks:**
    *   *CIS Amazon Web Services Foundations Benchmark v3.0.0*
    *   *CIS Kubernetes Benchmark v1.8.0*
    *   *CIS Docker Benchmark v1.6.0*
2.  **NIST Special Publications:**
    *   *NIST SP 800-190:* Application Container Security Guide (Isolation, Image Vulnerabilities, Hardware-based enforcement).
    *   *NIST SP 800-204:* Security Strategies for Microservices-based Application Systems.
3.  **MITRE ATT&CK Matrix for Cloud & Containers:**
    *   Enterprise Matrix: Cloud Matrix (AWS, Azure, GCP).
    *   Containers Matrix: Initial Access via Exposed APIs, Privilege Escalation via Escape to Host (T1611).
4.  **OWASP Cloud-Native Application Security Top 10:**
    *   *CNAS-01:* Insecure Cloud, Container, or Orchestration Configuration.
    *   *CNAS-03:* Over-privileged Identities and Permissions.
5.  **Dokumentasi Resmi Engine:**
    *   *AWS IAM Policy Evaluation Logic Documentation* (Official AWS Docs).
    *   *Kubernetes Pod Security Standards* (v1.28+, kubernetes.io).
    *   *The Linux Kernel Documentation:* Control Groups v2 & Seccomp BPF interfaces.