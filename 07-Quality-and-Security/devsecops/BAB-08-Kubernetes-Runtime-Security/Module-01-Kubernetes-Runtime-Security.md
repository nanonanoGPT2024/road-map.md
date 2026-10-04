# Bab 08 Module 01: Kubernetes Runtime Security & Admission Control

---

### 1. Identitas Modul

*   **Track**: DevSecOps
*   **Kategori**: 07-Quality-and-Security
*   **Bab**: 08 – Kubernetes Security, Workload Hardening & Runtime Defense
*   **Modul**: 01 – Kubernetes Runtime Security & Admission Control
*   **Tingkat Kesulitan**: Advanced / Enterprise-Grade
*   **Prasyarat**: 
    *   Pemahaman mendalam mengenai arsitektur internal Kubernetes (Control Plane, Worker Node, Kubelet, etcd, Container Runtime Interface).
    *   Pengalaman praktis dalam administrasi Linux (Namespace, Cgroups, Seccomp, Capabilities, Syscalls).
    *   Konsep dasar networking TCP/IP, CNI (Container Network Interface), dan manipulasi firewall (iptables/eBPF).
    *   Familiaritas dengan format deklaratif YAML dan dasar-dasar pemrograman logika/deklaratif (Rego/JSONPath).
*   **Estimasi Waktu Penyelesaian**: 240 Menit (Teori Mendalam, Analisis Arsitektur, dan Hands-on Lab)

---

### 2. Learning Objectives (LO-01 s/d LO-08)

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1.  **LO-01 (Menganalisis Mekanika Admission Control)**: Menganalisis siklus hidup HTTP request di dalam `kube-apiserver`, membedakan fase Authentication, Authorization, Mutating Webhook, Schema Validation, dan Validating Webhook secara granular.
2.  **LO-02 (Mengimplementasikan Pod Security Standards)**: Merancang dan mengeksekusi strategi migrasi Pod Security Admission (PSA) pada namespace enterprise dengan level *Privileged*, *Baseline*, dan *Restricted* tanpa memicu outage operasional.
3.  **LO-03 (Mensintesis Kebijakan OPA Gatekeeper)**: Menulis ConstraintTemplates dan Constraints menggunakan bahasa deklaratif Rego untuk menegakkan isolasi workload, validasi registry image, dan drop privilege Linux.
4.  **LO-04 (Mengevaluasi Otomasi Mutasi & Validasi Kyverno)**: Mengonfigurasi engine Kyverno untuk validasi, mutasi konteks keamanan pod secara otomatis, dan verifikasi integritas supply chain berbasis Cosign image attestations.
5.  **LO-05 (Mendiagnosis Ancaman Runtime Berbasis eBPF)**: Menganalisis instrumentasi kernel Linux via eBPF untuk deteksi dan terminasi eksekusi biner mencurigakan, privilege escalation, dan syscall anomaly menggunakan Falco dan Tetragon.
6.  **LO-06 (Mengonfigurasi eBPF-based Inline Enforcement)**: Mengimplementasikan kebijakan keamanan aktif (LSM BPF hooks) pada Tetragon untuk memutus proses kompromi secara realtime pada level kernel.
7.  **LO-07 (Merancang Arsitektur Zero-Trust Network Fabric)**: Menyusun deklarasi `NetworkPolicy` ingress dan egress untuk memblokir eksfiltrasi data ke metadata endpoint cloud provider dan mengisolasi namespace secara hermetik.
8.  **LO-08 (Mengaudit Insiden Keamanan Workload)**: Melakukan triage forensik terhadap cluster breach menggunakan telemetri runtime eBPF, audit log apiserver, dan alert stream untuk merekonstruksi kill chain penyerang.

---

### 3. Concept Map & Architecture Diagram

Berikut adalah arsitektur pertahanan berlapis (Defense-in-Depth) yang mengintegrasikan Admission Control pada Control Plane dan eBPF-based Detection/Enforcement pada Kernel Worker Node:

```
[ Developer / CI/CD Pipeline / Attacker ]
                   |
                   v (HTTPS API Request: kubectl, Helm, REST)
+-----------------------------------------------------------------------------------+
| KUBE-APISERVER                                                                    |
|  1. Authentication (mTLS, OIDC, Webhook Tokens)                                   |
|  2. Authorization (RBAC, ABAC, Node Restriction)                                 |
|  3. Dynamic Admission Control (Phase 1):                                          |
|     +-----------------------------------------------------------------------+     |
|     | Mutating Webhook Controller                                            |     |
|     |  -> Calls Kyverno / Custom Webhooks (inject sidecars, securityContext)|     |
|     +-----------------------------------------------------------------------+     |
|  4. Object Schema Validation                                                      |
|  5. Built-in Admission & Dynamic Admission Control (Phase 2):                     |
|     +-----------------------------------------------------------------------+     |
|     | - Pod Security Admission (PSA: Privileged / Baseline / Restricted)    |     |
|     | - Validating Webhook Controller                                       |     |
|     |    -> OPA Gatekeeper (ConstraintTemplates / Rego Engine)             |     |
|     |    -> Kyverno Engine (ClusterPolicy Validation Rules)                 |     |
|     +-----------------------------------------------------------------------+     |
|  6. Persistence to etcd (Single Source of Truth)                                  |
+-----------------------------------------------------------------------------------+
                   |
         (Cluster Scheduler & Kubelet Sync)
                   v
+-----------------------------------------------------------------------------------+
| WORKER NODE (Linux Kernel & Container Runtime)                                    |
|                                                                                   |
|  [ Network Layer: CNI / iptables / eBPF Network Policies ]                        |
|  - Ingress/Egress Isolation | Block Cloud Metadata Service (169.254.169.254)     |
|                                                                                   |
|  [ Workload Pods (Cgroups, Namespaces, AppArmor, Seccomp) ]                       |
|  +-----------------------------+       +-----------------------------+            |
|  | Pod A (Restricted Context)  |       | Pod B (Compromised Vector)  |            |
|  | Non-root, Read-only RootFS  |       | RCE Attempt -> /bin/sh exec |            |
|  +-----------------------------+       +--------------+--------------+            |
|                 |                                     |                           |
|                 v (Syscalls: execve, clone, connect)  v (Syscalls: cap_set, bpf)  |
|  ===============================================================================  |
|  LINUX KERNEL SPACE                                                               |
|  [ Tracepoints / Kprobes / LSM (Linux Security Modules) Hooks ]                   |
|         |                                            |                            |
|         v                                            v                            |
|  +------------------------+                +-------------------------+            |
|  | Falco eBPF Driver      |                | Tetragon (Cilium eBPF)  |            |
|  | Kernel Event Stream    |                | In-Kernel Enforcement   |            |
|  +-----------+------------+                +------------+------------+            |
|              | (Ring Buffer)                            | (Ring Buffer & LSM Kill)|
+--------------|------------------------------------------|-------------------------+
               v                                          v
   +-----------------------+                 +--------------------------+
   | Falco Userspace Daemon|                 | Tetragon Daemon (SIGKILL)|
   | Threat Detection Engine                 | Realtime Process Kill    |
   | Logs / SIEM / PagerDuty                 | Direct Kernel Block      |
   +-----------------------+                 +--------------------------+
```

---

### 4. Mengapa Ini Penting (Why & Business / Security Impact)

1.  **Kegagalan Paradigma Perimeter-Only Security**:
    Perlindungan tradisional pada perimeter ingress (seperti Web Application Firewall atau API Gateway) tidak berdaya saat penyerang mengeksploitasi celah zero-day pada dependensi internal aplikasi (misalnya RCE melalui supply chain vulnerability). Setelah pod terkompromi, ketiadaan runtime security internal memungkinkan penyerang melakukan *lateral movement* di seluruh jaringan internal cluster via service discovery bawaan Kubernetes (CoreDNS).
2.  **Mereduksi Blast Radius & Dampak Finansial Breach**:
    Berdasarkan laporan industri (Cost of a Data Breach Report), waktu rata-rata penahanan breach yang melibatkan container mencapai lebih dari 200 hari jika telemetri runtime tidak tersedia. Dengan menerapkan eBPF runtime detection (Tetragon/Falco), *Mean Time to Detect* (MTTD) dan *Mean Time to Respond* (MTTR) ditekan dari hitungan bulan menjadi hitungan milidetik melalui terminasi proses inline otomatis di kernel space.
3.  **Kepatuhan Regulasi & Standar Keamanan Data**:
    Standar kepatuhan internasional (PCI-DSS 4.0 Sub-klausul 6.4.3 & 10.2, SOC 2 Type II Trust Principles, ISO 27001 Annex A.12, dan NIST SP 800-190) mewajibkan pemisahan hak akses terkecil (*least privilege*), audit immutability, dan isolasi jaringan workload. Admission Controller (PSA, Gatekeeper, Kyverno) adalah instrumen kepatuhan *shift-left* preventif yang menolak konfigurasi tidak patuh sebelum workload dideploy ke etcd.
4.  **Pencegahan Serangan Container Breakout**:
    Konfigurasi container insecure (seperti `privileged: true`, mounting `/var/run/docker.sock`, capabilities `CAP_SYS_ADMIN`, atau *hostPath* mounts tidak terkontrol) memungkinkan penyerang keluar dari isolasi cgroup/namespace dan mengambil alih Linux kernel host node secara penuh. Admission controller bertindak sebagai benteng terdepan untuk mencegah deploy manifest destruktif tersebut.

---

### 5. Apa Itu Konsep (What & Definisi Formal Mendalam)

#### Dynamic Admission Control
Admission Controller adalah ekstensi native pada `kube-apiserver` yang mencegat (*intercept*) request API Kubernetes setelah fase autentikasi dan otorisasi berhasil, tetapi sebelum state object dituliskan ke dalam database `etcd`. Dynamic Admission Controllers terbagi menjadi dua sub-mekanisme:
*   **MutatingAdmissionWebhook**: Webhook eksternal yang diizinkan untuk memodifikasi struktur payload objek request (misalnya, menginjeksi default `securityContext`, menambahkan sidecar proxy, atau memaksa penambahan label pelacakan finansial).
*   **ValidatingAdmissionWebhook**: Webhook eksternal yang mengevaluasi skema dan konfigurasi objek yang diusulkan terhadap sekumpulan aturan keamanan. Webhook ini hanya memiliki wewenang biner: menyetujui (*admit*) atau menolak (*reject*) request API beserta pemberian pesan kesalahan teknis terstruktur.

#### Pod Security Standards (PSS) & Pod Security Admission (PSA)
Pod Security Standards (PSS) adalah taksonomi keamanan formal yang dirancang oleh Kubernetes Special Interest Group (SIG) Security untuk memitigasi eskalasi privilese pod. PSS menggantikan mekanisme *PodSecurityPolicy* (PSP) yang telah dihentikan (*deprecated* di v1.21, *removed* di v1.25). PSS membagi postur keamanan pod menjadi 3 profil diskrit:
1.  **Privileged**: Profil tanpa batasan (*unrestricted*), memberikan akses kernel host secara bebas. Hanya ditujukan untuk system-level agent, CNI, storage plugin, dan daemonset monitoring internal.
2.  **Baseline**: Profil minimal yang mencegah eskalasi privilese struktural yang diketahui tanpa konfigurasi kompleks (misalnya melarang pod menambahkan capabilities Linux tambahan atau mengaktifkan `hostNetwork`).
3.  **Restricted**: Profil pengerasan maksimal (*hardened*) yang mengimplementasikan praktik keamanan terbaik container: mewajibkan workload berjalan sebagai user non-root (`runAsNonRoot: true`), menonaktifkan eskalasi privilese (`allowPrivilegeEscalation: false`), membatasi volume mounts, menghapus semua capabilities Linux (`drop: ["ALL"]`), dan memaksa root filesystem menjadi *read-only*.

Pod Security Admission (PSA) adalah implementation engine bawaan (*in-tree admission controller*) yang mengevaluasi profil PSS pada level namespace menggunakan mode audit: `enforce` (blokir request pelanggaran), `audit` (catat pelanggaran pada audit log), dan `warn` (tampilkan pesan peringatan kepada user pengirim request tanpa memblokir).

#### eBPF Runtime Threat Detection & Enforcement
Extended Berkeley Packet Filter (eBPF) adalah teknologi kernel Linux revolusioner yang memungkinkan eksekusi program bytecode terisolasi (*sandboxed*) langsung di dalam ruang kernel (*kernel space*) tanpa mengubah source code kernel atau memuat modul kernel eksternal (LKM). 
*   **Falco**: Mesin pendeteksi ancaman runtime yang membaca stream event syscall dari kernel (via eBPF probe atau kernel module), memparsing metadata container/Kubernetes, dan mengevaluasi event terhadap aturan deteksi berbasis DSL (*Domain Specific Language*) deklaratif.
*   **Tetragon**: Mesin keamanan runtime dan observability berbasis eBPF mendalam (dikembangkan oleh Cilium) yang terhubung langsung ke tracepoints, kprobes, dan terutama **LSM (Linux Security Module) BPF Hooks**. Berbeda dengan Falco yang mayoritas beroperasi secara asinkron di user space untuk alerting, Tetragon mampu mengeksekusi aksi penegakan (*enforcement*) inline sinkron langsung di dalam kernel (seperti memicu `SIGKILL` pada proses yang melanggar) sebelum syscall berbahaya selesai dieksekusi.

---

### 6. Bagaimana Cara Kerjanya (How & Mekanika Internal Arsitektur)

#### Siklus Hidup Request pada Dynamic Admission Controller
Saat request HTTP REST API (misal: `POST /api/v1/namespaces/prod/pods`) diterima oleh `kube-apiserver`:

```
Client (kubectl) 
   | 
   v
[Authentication & Authorization] 
   | 
   v
[Mutating Webhook Phase] 
   |---> Kirim JSON AdmissionReview (Mutating) ke OPA Gatekeeper / Kyverno
   |<--- Balasan AdmissionReview (JSONPatch: RFC 6902, e.g., inject securityContext)
   |
[Object Schema Validation] (Validasi OpenAPI Schema Pod)
   |
[Pod Security Admission (PSA)] (Evaluasi label namespace: enforce/audit/warn)
   |
[Validating Webhook Phase]
   |---> Kirim JSON AdmissionReview (Validating) ke OPA Gatekeeper / Kyverno
   |<--- Balasan AdmissionReview (Allowed: true/false, Status: Message)
   |
[etcd Persistence] (Objek ditulis secara atomik ke storage)
```

1.  **Serialization AdmissionReview**: `kube-apiserver` membungkus object definition ke dalam payload `admission.k8s.io/v1/AdmissionReview`.
2.  **Dispatch over TLS**: Payload dikirim via HTTP POST melalui secure TLS connection ke admission server service (contoh: port 8443 pada pod Kyverno/Gatekeeper).
3.  **Policy Parsing**:
    *   *Kyverno*: Mengevaluasi manifest terhadap AST (*Abstract Syntax Tree*) internal rule engine berbasis JSON/YAML.
    *   *Gatekeeper*: Mengirimkan data manifest dan state cluster ke runtime engine Rego (Open Policy Agent) via in-memory query evaluation.
4.  **AdmissionResponse Delivery**: Webhook mengembalikan objek `AdmissionReview` berisi parameter `uid`, `allowed: true/false`, dan opsi mutasi `patch` bertipe Base64 encoded JSONPatch.

#### Mekanika Sensor Kernel eBPF (Falco & Tetragon)
Operasi workload di container pada akhirnya diterjemahkan menjadi panggilan sistem (syscall) ke kernel Linux host yang digunakan bersama (*shared kernel*).

```
User Space (Container)             Kernel Space (Linux)                   User Space (Security Agents)
+-----------------------+          +---------------------------+          +-------------------------+
| Pod Execution:        |          | System Call Handler       |          |                         |
| execve("/bin/bash")  | -------->| sys_enter_execve          |          | Falco Daemon            |
+-----------------------+          +-------------+-------------+          | Reads Perf/Ring Buffer  |
                                                 |                        | Matches YAML Rules      |
                                                 v                        | Dispatches Alert        |
                                   +---------------------------+          +------------^------------+
                                   | eBPF Probe Hook Attached  |                       |
                                   | (kprobe/tracepoint/LSM)   |                       |
                                   +-------------+-------------+                       |
                                                 |                                     |
                                                 v (Event Generation)                  |
                                   +---------------------------+                       |
                                   | eBPF Perf / Ring Buffer   | ----------------------+
                                   +-------------+-------------+
                                                 |
                                  [ If LSM Hook & Tetragon Kill ]
                                                 v
                                   Send SIGKILL Immediately to Process!
```

1.  **Attachment**: Saat agent eBPF aktif, driver memuat program bytecode eBPF yang diverifikasi keselamatannya oleh *eBPF Verifier* (mencegah loop tak terhingga, dereferensi memori ilegal) dan mengaitkannya (*attach*) ke hook point kernel:
    *   Tracepoints: `sys_enter_execve`, `sys_enter_connect`, `sys_enter_mount`.
    *   LSM Hooks: `security_bprm_check`, `security_file_open`, `security_socket_connect`.
2.  **Context Extraction**: Ketika pod mengeksekusi binary atau membuka socket TCP, kernel memicu eBPF hook. Program eBPF mengekstrak metadata dari kernel task struct: `pid`, `ppid`, `uid`, `cgroup id`, dan namespaces (mount, network, pid).
3.  **Correlation with K8s Metadata**: Agent memetakan `cgroup id` ke container ID dan K8s Pod UID menggunakan cache metadata yang disinkronkan dari Kubelet API/Docker/containerd socket.
4.  **Synchronous Enforcement (LSM BPF)**: Pada Tetragon, jika trace LSM mendeteksi eksekusi biner terlarang (misalnya binary `/usr/bin/nc` dipanggil dalam pod produksi), program eBPF mengubah register return value atau memanggil helper `bpf_send_signal(SIGKILL)` sebelum eksekusi binary berlangsung, menghentikan penyerang pada tingkat microsecond.

---

### 7. Perbandingan Paradigma / Taksonomi Matriks

#### Dynamic Admission Control vs Built-in Pod Security Admission

| Parameter Evaluasi | Pod Security Admission (PSA) | OPA Gatekeeper | Kyverno |
| :--- | :--- | :--- | :--- |
| **Arsitektur Eksekusi** | In-Tree (`kube-apiserver` internal module) | Out-of-Tree (Dynamic Webhook Service) | Out-of-Tree (Dynamic Webhook Service) |
| **Kebutuhan Resource** | Sangat Rendah (Zero additional pods/memory) | Tinggi (Memerlukan pod controller + cache sync) | Menengah (Memerlukan pod controller dedicated) |
| **Bahasa Kebijakan** | Standar Kubernetes Label Namespace | Deklaratif Rego (Query-based DSL spesifik) | Native Kubernetes Manifests (YAML murni) |
| **Kemampuan Mutasi** | Tidak Ada (Hanya validasi Pod Security) | Terbatas (Via resource `Assign` / `AssignMetadata`) | Luas (Mutasi JSONPatch kompleks, conditional mutate) |
| **Generasi Resource** | Tidak Ada | Tidak Ada | Ada (Dapat men-generate `NetworkPolicy` via rule) |
| **External Data Lookup** | Tidak Mendukung | Mendukung via OPA external data cache / driver | Mendukung HTTP callout ke external API/Service |
| **Supply Chain Verification** | Tidak Tersedia | Memerlukan integrasi library custom/Gatekeeper external | Native Cosign, Notary v2 image/attestation verify |

#### Runtime Security: Falco vs Tetragon

| Fitur / Metrik | Falco (Sysdig / CNCF Graduated) | Tetragon (Isovalent / Cilium Project) |
| :--- | :--- | :--- |
| **Fokus Arsitektur Utama** | Deteksi Intrusi Runtime & Anomaly Alerting | Observability Mendalam & Inline Runtime Enforcement |
| **Mekanisme Sensor** | Kernel Module atau eBPF Probe (Legacy & Modern eBPF)| Pure Modern eBPF & LSM BPF (Kernel 5.3+) |
| **Enforcement Vector** | Reaktif (Asinkron via Falco Sidekick / Response Engine)| Preventif Inline (Sinkron langsung di Kernel via LSM SIGKILL)|
| **Format Kebijakan** | YAML-based rules syntax dengan kondisi ekspresi | Kubernetes CRD (`TracingPolicy`, `NamespacedTracingPolicy`)|
| **Overhead CPU Worker** | Rendah - Menengah (Bergantung volume ring buffer syscall)| Sangat Rendah (Penyaringan/filtering event terjadi di kernel)|
| **Kontekstualisasi Network** | Parsing paket socket network terbatas | Terintegrasi penuh dengan network identity Cilium CNI |
| **Namespace Awareness** | Context lookup di user space daemon | Dynamic context lookup langsung di probe kernel layer |

---

### 8. Analisis Mendalam Attack Surface & Vector Matrix

```
       [Attacker Initial Access: Vulnerable App]
                           |
       +-------------------+-------------------+
       |                                       |
       v                                       v
[Vector 1: Privilege Escalation]        [Vector 2: Lateral Movement]
- Missing root drop (`uid=0`)           - Flat Pod Network (Unrestricted CNI)
- Host IPC/PID Namespace Sharing        - Metadata Service Access (169.254.169.254)
- Sensitive Capabilities (CAP_SYS_ADMIN)- Insecure Internal Microservice API
       |                                       |
       v                                       v
[Vector 3: Container Escape]            [Vector 4: Supply Chain Pollution]
- HostPath Mount (`/var/run/docker.sock`)- Unsigned / Malicious Images from Docker Hub
- Exploitation of Container Runtime     - Package drifting at runtime (apt-get install)
```

| Vektor Serangan | Deskripsi Teknis Kerentanan | Dampak Eksploitasi | Mitigasi Admission Control | Mitigasi Runtime / Network |
| :--- | :--- | :--- | :--- | :--- |
| **Privileged Container & Capabilities Escape** | Pod dideklarasikan dengan `securityContext.privileged: true` atau mempertahankan capabilities `CAP_SYS_ADMIN`, `CAP_SYS_PTRACE`. | Penyerang mengakses host block devices (`/dev/sda`), melakukan remount root filesystem host, dan mengambil alih node sepenuhnya. | **PSA**: Mode `Restricted`.<br>**Gatekeeper/Kyverno**: Reject manifest jika capabilities tidak di-drop ke `ALL`. | **Tetragon**: Blokir syscall `mount` dan `setns` via `TracingPolicy`.<br>**Falco**: Alert rules `Privileged Container Spawned`. |
| **HostPath Arbitrary File Write** | Pod me-mount direktori sensitif host seperti `/etc/kubernetes/manifests`, `/etc/shadow`, atau socket CRI (`/run/containerd/containerd.sock`). | Penyerang membuat static pod backdoor langsung pada file system node worker atau memanipulasi Kubelet binary. | **Gatekeeper/Kyverno**: Larang penggunaan `hostPath` selain allowlist tertentu (misal logs read-only). | **Falco**: Deteksi pembacaan/penulisan file direktori sensitif (`Sensitive File Untrusted Access`). |
| **Network Metadata API Credential Theft** | Pod tidak dibatasi untuk memanggil link-local address AWS IMDSv1 (`169.254.169.254`) atau GCP Metadata API. | Pencurian temporary IAM Role credentials instance worker node, berujung pada kompromi infrastruktur Cloud Provider. | Tidak dapat dicegat oleh Admission Control (karena bersifat layer network). | **NetworkPolicy**: Terapkan default deny egress dan blokir CIDR `169.254.169.254/32` secara global. |
| **Runtime Binary Drifting & Reverse Shell** | Penyerang berhasil mengeksekusi payload RCE dan menjalankan perintah shell (`bash -i >& /dev/tcp/...`) atau mendownload cryptominer via `curl`. | Injeksi payload dinamis, resource hijacking (cryptomining), pemetaan port internal secara interaktif. | **Gatekeeper/Kyverno**: Paksa `readOnlyRootFilesystem: true` untuk membatasi penulisan binary berekstensi executable. | **Tetragon**: Inline drop dan SIGKILL otomatis saat binary di luar baseline container di-spawn.<br>**Falco**: Alert `Run shell in container`. |

---

### 9. Code Example Sederhana (Minimal & Clear)

#### A. Pod Security Standards via Namespace Label
Penerapan penegakan postur keamanan `Restricted` secara native pada namespace `workload-secure`.

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: workload-secure
  labels:
    # Blokir pembuatan pod yang melanggar standar Restricted (versi pod k8s v1.30)
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/enforce-version: v1.30
    # Berikan warning visual kepada developer jika melanggar standar Restricted
    pod-security.kubernetes.io/warn: restricted
    pod-security.kubernetes.io/warn-version: v1.30
    # Masukkan record log audit apiserver jika ada manifest melanggar
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/audit-version: v1.30
```

#### B. Skenario Uji: Pod Melanggar Baseline/Restricted (Harus Ditolak)
Manifest berikut akan langsung **ditolak** oleh Pod Security Admission controller karena menjalankan root user dan eskalasi privilese.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: insecure-test-pod
  namespace: workload-secure
spec:
  containers:
  - name: alpine-insecure
    image: alpine:3.19
    command: ["sleep", "3600"]
    securityContext:
      # Pelanggaran PSA Restricted: allowPrivilegeEscalation tidak diset ke false
      allowPrivilegeEscalation: true
      # Pelanggaran PSA Restricted: Container tidak membatasi diri dari non-root
      runAsNonRoot: false
```

Eksekusi CLI dan Output Penolakan dari apiserver:
```bash
$ kubectl apply -f insecure-test-pod.yaml
Error from server (Forbidden): error when creating "insecure-test-pod.yaml": 
pods "insecure-test-pod" is forbidden: violates PodSecurity "restricted:v1.30": 
allowPrivilegeEscalation != false (container "alpine-insecure" must set securityContext.allowPrivilegeEscalation=false), 
runAsNonRoot != true (pod or container "alpine-insecure" must set securityContext.runAsNonRoot=true), 
enforce-spec.containers[*].securityContext.capabilities.drop: require ["ALL"]
```

---

### 10. Code Example Lanjutan (Production-ready / Hardening / Exploit Analysis)

#### A. OPA Gatekeeper: ConstraintTemplate & Constraint (Enforce Read-Only Root Filesystem & Drop Capabilities)

Implementasi ConstraintTemplate berbasis Rego v1 yang memvalidasi bahwa setiap pod wajib memiliki `readOnlyRootFilesystem: true` dan wajib melakukan drop capability `ALL`.

```yaml
apiVersion: templates.gatekeeper.sh/v1
kind: ConstraintTemplate
metadata:
  name: k8scontaineroppsdefense
  annotations:
    description: "Memaksa implementasi isolasi runtime: immutable rootfs dan total capability drops."
spec:
  crd:
    spec:
      names:
        kind: K8sContainerOpsDefense
  targets:
    - target: admission.k8s.gatekeeper.sh
      rego: |
        package k8scontaineroppsdefense

        # Entry point validasi container
        violation[{"msg": msg}] {
          container := input.review.object.spec.containers[_]
          not has_readonly_root_fs(container)
          msg := sprintf("Container '%v' di-reject: Security Context wajib mendefinisikan 'readOnlyRootFilesystem: true' untuk mencegah runtime code alteration.", [container.name])
        }

        violation[{"msg": msg}] {
          container := input.review.object.spec.containers[_]
          not has_all_capabilities_dropped(container)
          msg := sprintf("Container '%v' di-reject: Linux capabilities wajib didrop secara absolut menggunakan drop: ['ALL'].", [container.name])
        }

        # Logika Helper: Validasi ReadOnly Root Filesystem
        has_readonly_root_fs(c) {
          c.securityContext.readOnlyRootFilesystem == true
        }

        # Logika Helper: Validasi Drop ALL Capabilities
        has_all_capabilities_dropped(c) {
          drops := c.securityContext.capabilities.drop
          drops[_] == "ALL"
        }
---
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sContainerOpsDefense
metadata:
  name: enforce-container-hardening
spec:
  enforcementAction: deny # Ubah ke 'dryrun' saat audit pra-produksi
  match:
    kinds:
      - apiGroups: [""]
        kinds: ["Pod"]
    namespaces:
      - "finance-api"
      - "payment-gateway"
    excludedNamespaces:
      - "kube-system"
      - "gatekeeper-system"
```

#### B. Tetragon TracingPolicy: Realtime Kernel SIGKILL untuk Pencegahan Dynamic Shell Execution

Konfigurasi eBPF Tetragon Custom Resource Definition (CRD) yang mencegat syscall `sys_enter_execve` pada LSM level. Jika proses memanggil binary interactive shell (`/bin/sh`, `/bin/bash`) di dalam namespace tertentu, Tetragon akan membunuh proses tersebut secara inline di kernel space.

```yaml
apiVersion: cilium.io/v1alpha1
kind: TracingPolicy
metadata:
  name: block-namespace-interactive-shells
  namespace: payment-gateway
spec:
  kprobes:
    - call: "sys_enter_execve"
      syscall: true
      args:
        - index: 0
          type: "string" # Path binary executable yang dipanggil
      selectors:
        - matchArgs:
            - index: 0
              operator: "In"
              values:
                - "/bin/sh"
                - "/bin/bash"
                - "/usr/bin/bash"
                - "/usr/bin/sh"
                - "/usr/bin/zsh"
          matchNamespaces:
            - payment-gateway
          matchActions:
            - action: Sigkill # Langsung tembak proses dengan sinyal 9 (Kernel Level SIGKILL)
            - action: Post # Emit structured telemetry data ke Tetragon ring buffer log
```

Log Forensik Tetragon saat serangan shell di-spawn di container:
```json
{
  "process_kprobe": {
    "process": {
      "exec_id": "cGF5bWVudC1nYXRld2F5LXBvZC1hcGk6MTAyOTM4NDc1",
      "pid": 28419,
      "uid": 10001,
      "binary": "/bin/bash",
      "arguments": "-i",
      "pod": {
        "namespace": "payment-gateway",
        "name": "payment-backend-674b94875b-w4j8k",
        "container": {"id": "containerd://b2f483c...", "name": "core-api"}
      }
    },
    "parent": {
      "pid": 28400,
      "binary": "/usr/local/bin/node"
    },
    "function_name": "sys_enter_execve",
    "action": "KPROBE_ACTION_SIGKILL",
    "policy_name": "block-namespace-interactive-shells"
  }
}
```

#### C. NetworkPolicy Hardening: Hermetic Namespace Isolation & Metadata Blocking

Deklarasi standar mitigasi lateral movement dan SSRF credential theft yang komprehensif.

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-and-isolate
  namespace: payment-gateway
spec:
  podSelector: {} # Berlaku untuk seluruh pod di namespace ini
  policyTypes:
  - Ingress
  - Egress
  ingress:
  # Izinkan traffic ingress HANYA dari ingress-controller namespace pada port 8080
  - from:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: ingress-nginx
      podSelector:
        matchLabels:
          app.kubernetes.io/name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8080
  egress:
  # 1. Izinkan resolusi DNS cluster internal (kube-dns)
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: kube-system
      podSelector:
        matchLabels:
          k8s-app: kube-dns
    ports:
    - protocol: UDP
      port: 53
    - protocol: TCP
      port: 53
  # 2. Izinkan egress database HANYA ke namespace db-tier, port Postgres 5432
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: db-tier
      podSelector:
        matchLabels:
          role: postgres-primary
    ports:
    - protocol: TCP
      port: 5432
  # 3. Blokir eksplisit terhadap Metadata Service Cloud (169.254.169.254/32)
  # Diimplementasikan dengan membuka semua IP eksternal tapi mengecualikan link-local
  - to:
    - ipBlock:
        cidr: 0.0.0.0/0
        except:
          - 169.254.169.254/32
          - 10.0.0.0/8 # Blokir akses lateral ke VPC internal nodes
```

---

### 11. Diagram Alur Serangan & Mitigasi

Alur ini mengilustrasikan anatomi serangan RCE yang berupaya melakukan download cryptominer dan container breakout, serta respons sistem pertahanan di setiap fase:

```
ATTACK LIFECYCLE                                    DEFENSE-IN-DEPTH LAYER INTERCEPTION
================                                    ====================================

[Phase 1: Ingestion Manifest Insecure]
Attacker mencoba apply Pod via GitOps/API
dengan hostPath mount & root user privilege.
        |
        v
[API Server: Admission Control] ------------------> [ADMISSION LAYER BLOCKS IT]
                                                    OPA Gatekeeper / Kyverno / PSA 
                                                    menemukan pelanggaran:
                                                    - runAsNonRoot != true
                                                    - hostPath != allowed
                                                    RESULT: 403 Forbidden. Pod ditolak!

[Phase 2: RCE on Legitimate Workload]
Workload valid lolos admission, tapi memiliki
kerentanan dependensi internal (Log4j/SSRF).
Attacker mentrigger RCE via HTTP request.
        |
        v
[Payload Execution inside Pod]
Attacker menjalankan shell:
execve("/bin/sh", ["sh", "-c", "curl..."])
        |
        +-----------------------------------------> [eBPF Tetragon (Kernel Space)]
        |                                           TracingPolicy LSM hook mendeteksi
        |                                           eksekusi shell pada restricted pod.
        |                                           ACTION: In-Kernel SIGKILL dikirim!
        |                                           Status code 137, proses dihentikan.
        v
[Phase 3: Fallback Payload (Spawn C Binary)]
Jika lolos SIGKILL, attacker menulis
file binary miner ke disk pod (/tmp/xmr).
        |
        +-----------------------------------------> [Container Hardening: Read-Only RootFS]
        |                                           Sistem operasi mengembalikan:
        |                                           "Read-only file system".
        |                                           Penulisan binary diblokir total.
        v
[Phase 4: Network SSRF Exfiltration]
Attacker mencoba mencuri kredensial host
via Cloud Metadata:
GET http://169.254.169.254/latest/meta-data/
        |
        +-----------------------------------------> [CNI NetworkPolicy Layer]
                                                    Egress drop policy mengecualikan
                                                    169.254.169.254/32. Paket didrop di veth!
                                                    RESULT: Connection Timeout. 
                                                    Kill Chain Terputus Total!
```

---

### 12. Trade-offs & Security vs Usability / Performance

#### 1. Admission Control Webhook Latency vs Cluster Availability
*   **Trade-off**: Validating dan Mutating Admission Webhook memperkenalkan HTTP network hop dari `kube-apiserver` ke webhook pods untuk setiap operasi API create/update/delete.
*   **Impact**: Jika webhook pod mengalami load tinggi atau node mengalami CPU throttling, API server dapat mengalami timeouts (`context deadline exceeded`).
*   **Engineering Resolution**: 
    *   Set parameter `failurePolicy: Fail` hanya untuk namespace misi-kritis dan `failurePolicy: Ignore` untuk operasi yang dapat ditoleransi saat bootstrap.
    *   Terapkan High Availability (minimal 3 replika) untuk pod Gatekeeper/Kyverno dengan `PodDisruptionBudget` dan `topologySpreadConstraints`.
    *   Gunakan PSA bawaan (*in-tree*) untuk baseline policy karena PSA tidak memiliki network overhead (evaluasi memory-speed di apiserver binary).

#### 2. eBPF Kernel Tracing vs Worker Node Resource Consumption
*   **Trade-off**: Instrumentasi kprobe pada kernel functions dengan frekuensi pemanggilan masif (misal: `tcp_sendmsg`, `vfs_read`, `vfs_write`) menghasilkan jutaan event per detik.
*   **Impact**: Ring buffer overflow dan konsumsi CPU tinggi pada user-space agent (Falco/Tetragon daemonset) untuk memproses event stream.
*   **Engineering Resolution**:
    *   Pindahkan logika filtering sedekat mungkin ke kernel space menggunakan selector native Tetragon atau Falco modern eBPF driver.
    *   Hindari hook pada system call I/O intensif (`read`, `write`); gunakan point-of-execution hooks (`sys_enter_execve`, `security_socket_connect`, `security_sb_mount`).

#### 3. Strict Pod Security Standards vs Developer Velocity
*   **Trade-off**: Menegakkan `Restricted` PSA secara langsung memblokir container off-the-shelf lama yang membutuhkan write access ke `/var/log` atau port `< 1024`.
*   **Impact**: Pipa CI/CD gagal deploy, resistensi dari tim engineering software, dan downtime aplikasi warisan.
*   **Engineering Resolution**:
    *   Gunakan siklus adopsi 3 fase: (1) `audit` mode selama 30 hari untuk mengumpulkan baseline log, (2) `warn` mode selama 14 hari agar developer menerima feedback CLI langsung, (3) `enforce` mode secara bertahap dimulai dari lingkungan non-produksi.

---

### 13. Edge Cases & Complex Failure Modes

#### Webhook Deadlock & Control Plane Blind Spot
*   **Skenario**: Webhook OPA Gatekeeper atau Kyverno dikonfigurasi dengan aturan yang mengevaluasi seluruh namespace termasuk namespace kontrol mereka sendiri atau `kube-system`, dengan `failurePolicy: Fail`. Jika cluster reboot atau master node di-restart:
    1.  `kube-apiserver` menyala, tetapi pod Kyverno/Gatekeeper belum berjalan.
    2.  Kubelet mencoba meluncurkan pod Kyverno.
    3.  `kube-apiserver` menerima request pembuatan pod Kyverno, namun menahannya untuk validasi webhook.
    4.  Webhook memanggil endpoint pod Kyverno yang belum siap. Request time out dan ditolak (`Fail`).
    5.  Cluster mengalami deadlock total di mana tidak ada pod baru yang dapat distart.
*   **Mitigasi Teknis**: Gunakan konfigurasi `namespaceSelector` pada `MutatingWebhookConfiguration` dan `ValidatingWebhookConfiguration` dengan pengecualian eksplisit:
    ```yaml
    namespaceSelector:
      matchExpressions:
      - key: kubernetes.io/metadata.name
        operator: NotIn
        values: ["kube-system", "gatekeeper-system", "kyverno"]
    ```

#### Bypassing Admission Control via Kubelet Static Pods
*   **Skenario**: Admission Controller hanya mencegat interaksi yang melewati REST API `kube-apiserver`. Jika seorang penyerang berhasil memperoleh akses file system pada worker node (misalnya via SSH key compromise atau file write exploit), penyerang dapat menaruh manifest pod di direktori static pod Kubelet (default: `/etc/kubernetes/manifests/`).
*   **Analisis**: Kubelet secara otonom membaca manifest tersebut dan meluncurkannya langsung ke container runtime lokal tanpa meminta verifikasi ke admission webhook apiserver. Pod ini akan berjalan sebagai "Mirror Pod" yang memiliki kendali tak terbatas.
*   **Mitigasi Teknis**: Admission Control tidak dapat memitigasi skenario ini. Dibutuhkan deteksi runtime eBPF (Falco/Tetragon) untuk memonitor integritas direktori host file system dan pembuatan container abnormal via socket containerd/CRI.

#### eBPF Verifier Rejection & Kernel Version Drift
*   **Skenario**: Fleet worker node menjalankan Linux kernel dengan patch security yang heterogen (misalnya campuran kernel 5.4 dan 6.2). Tetragon TracingPolicy yang memanfaatkan specific LSM hook gagal dimuat (*crashloop*) pada node dengan kernel lama karena eBPF Verifier menolak verifikasi bytecode keselamatan memori.
*   **Mitigasi Teknis**: Terapkan Node Feature Discovery (NFD) atau label node terstruktur (`kernel.core.feature/lsm: "true"`). Terapkan policy Daemonset eBPF menggunakan `nodeAffinity` yang ketat untuk memastikan fitur keamanan kernel cocok dengan kapabilitas underlying host.

---

### 14. Anti-Patterns & Common Vulnerabilities

#### 1. Anti-Pattern: Penggunaan `failurePolicy: Ignore` Berkelanjutan pada Production
Banyak tim konfigurasi dynamic webhook beralih ke `failurePolicy: Ignore` saat menghadapi outage pertama kali. 
*   **Kerentanan**: Jika penyerang melakukan serangan denial of service (DoS) terhadap pod webhook atau membanjiri memory worker node tempat webhook berada, apiserver akan melakukan *fail-open*. Penyerang dapat menyuntikkan workload berbahaya tanpa resistensi policy selama masa degradasi webhook tersebut.
*   **Rekomendasi**: Pertahankan `failurePolicy: Fail` untuk namespace sensitif, implementasikan HPA (Horizontal Pod Autoscaler) untuk admission webhook, dan pisahkan node webhook controller pada node pool dedicated.

#### 2. Anti-Pattern: Mengandalkan Admission Controller Tanpa Perlindungan Runtime
Mengasumsikan bahwa jika sebuah container lolos validasi admission control, maka beban kerja tersebut aman secara permanen.
*   **Kerentanan**: Validasi admission control adalah validasi statis berbasis deklarasi state. Admission controller tidak mampu mendeteksi *in-memory attacks*, eksploitasi deserialisasi Java, injection memory corruption, atau manipulasi logic aplikasi yang terjadi setelah container berjalan.
*   **Rekomendasi**: Terapkan postur komplementer: Admission control bertindak sebagai filter gerbang statis (*gatekeeper*), eBPF bertindak sebagai kamera pengawas dan algojo dinamis di dalam ruangan (*runtime defense*).

#### 3. Anti-Pattern: Single-Namespace Permissive NetworkPolicies
Tidak menerapkan isolated `NetworkPolicy` karena berasumsi namespace memberikan isolasi layer-3 secara otomatis.
*   **Fakta Teknis**: Namespace di Kubernetes adalah isolasi logikal Control Plane (API object scoping), **bukan** isolasi jaringan layer-3/layer-4. Secara default, Kubernetes mengadopsi model jaringan datar (*flat network*): setiap pod dapat berkomunikasi dengan setiap pod lain di seluruh cluster, lintas namespace, tanpa batasan.
*   **Rekomendasi**: Deklarasikan `default-deny-all` Ingress dan Egress pada setiap namespace baru sebagai baseline provisioning GitOps.

---

### 15. Best Practices & Enterprise Remediation Guide

#### Matriks Penerapan Defense-in-Depth Kubernetes

```
===================================================================================
FASE DEFENSI          TEKNOLOGI                      TARGET PENEGAKAN KEAMANAN
===================================================================================
1. Pre-Deployment     CI/CD, Cosign, Trivy           Signatur image, CVE vulnerability
                                                     scanning, static misconfig check.
-----------------------------------------------------------------------------------
2. Admission Phase    Pod Security Admission (PSA)   Enforce 'Restricted' profile pada
                                                     seluruh business namespace.
                      -------------------------------------------------------------
                      OPA Gatekeeper / Kyverno       Validasi supply chain (Cosign),
                                                     blokir default root, enforce label,
                                                     drop privileges, enforce storage class.
-----------------------------------------------------------------------------------
3. Network Layer      CNI NetworkPolicy              Default Deny Ingress & Egress,
                      (Calico / Cilium eBPF)         blokir Cloud Metadata Service IP,
                                                     mikrosegmentasi antar namespace.
-----------------------------------------------------------------------------------
4. Runtime Execution  Tetragon (eBPF + LSM BPF)      Inline SIGKILL pada unauthorized
                                                     binary execution, interactive shell,
                                                     dan privilege escalation attempt.
                      -------------------------------------------------------------
                      Falco                          Deep anomaly detection, audit log
                                                     correlation, SIEM integration alerting.
===================================================================================
```

#### Panduan Remediasi Bertahap (Enterprise Remediation Workflow)

1.  **Langkah 1: Terapkan PSA di Seluruh Cluster**:
    *   Beri label seluruh namespace target dengan `pod-security.kubernetes.io/enforce=restricted`.
    *   Jika terdapat pod legacy yang gagal, ubah namespace tersebut ke `pod-security.kubernetes.io/warn=restricted` dan `pod-security.kubernetes.io/enforce=baseline` untuk memberikan grace period perbaikan manifest.
2.  **Langkah 2: Enforce Baseline Dynamic Admission Rules via Kyverno/Gatekeeper**:
    *   Paksa semua container mendeklarasikan:
        ```yaml
        securityContext:
          runAsNonRoot: true
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          capabilities:
            drop: ["ALL"]
        ```
    *   Tolak deployment image yang menggunakan tag `:latest` atau image yang berasal dari registri publik yang tidak diizinkan (*untrusted registries*).
3.  **Langkah 3: Terapkan Isolasi Jaringan Default-Deny**:
    *   Pastikan CNI mendukung evaluasi NetworkPolicy (misal Cilium, Calico).
    *   Buat `NetworkPolicy` universal yang memblokir egress ke `169.254.169.254/32` dan `10.0.0.0/8` kecuali port microservice tujuan yang diotorisasi secara eksplisit.
4.  **Langkah 4: Deploy Sensor Runtime eBPF**:
    *   Deploy Tetragon DaemonSet dengan policy LSM untuk memblokir executable shell di namespace produksi.
    *   Deploy Falco dengan driver modern eBPF probe untuk mengirimkan alert runtime via webhook/gRPC ke SIEM korporat (Splunk, Elastic, Sentinel).

---

### 16. Hands-on Lab Step-by-Step

Lab ini menggunakan cluster `kind` (Kubernetes in Docker) untuk mengonfigurasi Admission Control dan runtime threat testing.

#### Prasyarat Sistem
*   Docker Engine v24+
*   Kind CLI v0.20+
*   kubectl v1.28+
*   Helm v3+

#### Step 1: Membuat Multi-Node Cluster Menggunakan Kind
Simpan konfigurasi berikut sebagai `kind-lab-config.yaml`:

```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  image: kindest/node:v1.30.0
- role: worker
  image: kindest/node:v1.30.0
- role: worker
  image: kindest/node:v1.30.0
```

Jalankan perintah pembuatan cluster:
```bash
kind create cluster --name sec-lab --config kind-lab-config.yaml
kubectl cluster-info --context kind-sec-lab
```

#### Step 2: Konfigurasi Pod Security Admission (Restricted Profile)
Buat namespace target dengan standar keamanan Restricted:

```bash
kubectl create namespace staging-secure

# Terapkan label Pod Security Standards
kubectl label namespace staging-secure \
  pod-security.kubernetes.io/enforce=restricted \
  pod-security.kubernetes.io/enforce-version=latest \
  pod-security.kubernetes.io/warn=restricted \
  pod-security.kubernetes.io/warn-version=latest
```

Verifikasi penegakan:
Coba deploy pod yang melanggar standar:
```bash
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: root-violation-pod
  namespace: staging-secure
spec:
  containers:
  - name: nginx
    image: nginx:alpine
EOF
```
*Hasil Verifikasi*: Perintah di atas **wajib ditolak** oleh API server dengan error detail mengenai `runAsNonRoot`, `allowPrivilegeEscalation`, dan capabilities.

Deploy pod compliant yang memenuhi seluruh kriteria:
```bash
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: compliant-secure-pod
  namespace: staging-secure
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 10001
    runAsGroup: 10001
    fsGroup: 10001
    seccompProfile:
      type: RuntimeDefault
  containers:
  - name: busybox
    image: busybox:1.36
    command: ["sleep", "3600"]
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities:
        drop:
        - ALL
EOF
```
*Hasil Verifikasi*: Pod `compliant-secure-pod` berhasil dibuat dengan status `Running`.

#### Step 3: Instalasi Kyverno Policy Engine via Helm
Deploy Kyverno ke cluster untuk validasi lanjutan:

```bash
helm repo add kyverno https://kyverno.github.io/kyverno/
helm repo update
helm install kyverno kyverno/kyverno -n kyverno --create-namespace \
  --set replicaCount=1

# Tunggu hingga pods kyverno running
kubectl wait --namespace kyverno \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/instance=kyverno \
  --timeout=90s
```

#### Step 4: Terapkan Kyverno ClusterPolicy (Disallow Latest Image Tag)
Terapkan kebijakan yang menolak container yang menggunakan image dengan tag `:latest` atau tanpa tag:

```bash
cat <<EOF | kubectl apply -f -
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: disallow-latest-tag
spec:
  validationFailureAction: Enforce
  background: false
  rules:
  - name: require-image-tag
    match:
      any:
      - resources:
          kinds:
          - Pod
    validate:
      message: "Image tag ':latest' dilarang keras. Gunakan explicit immutable versioning tag atau SHA256 digest!"
      pattern:
        spec:
          containers:
          - image: "!*:latest & !*:"
EOF
```

Verifikasi penegakan Kyverno:
```bash
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: test-latest-tag
  namespace: default
spec:
  containers:
  - name: web
    image: nginx:latest
EOF
```
*Hasil Output Verifikasi*:
```
Error from server: error when creating "STDIN": admission webhook "validate.kyverno.svc-fail" denied the request: 

resource Pod/default/test-latest-tag was blocked. rule require-image-tag failed: 
Image tag ':latest' dilarang keras. Gunakan explicit immutable versioning tag atau SHA256 digest!
```

#### Step 5: Instalasi Falco via Helm Menggunakan Modern eBPF Probe
Pasang Falco untuk mendeteksi ancaman runtime:

```bash
helm repo add falcosecurity https://falcosecurity.github.io/charts
helm repo update

# Deploy Falco dengan modern eBPF driver
helm install falco falcosecurity/falco \
  --namespace falco --create-namespace \
  --set driver.kind=modern_ebpf \
  --set tty=true

# Pastikan pod Falco running di node
kubectl wait --namespace falco \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/name=falco \
  --timeout=120s
```

#### Step 6: Simulasi Runtime Breach & Verifikasi Alerting Falco
Jalankan proses interactive terminal di dalam compliant pod untuk mensimulasikan aktivitas penyusup:

```bash
# Buka streaming log Falco di terminal terpisah
kubectl logs -n falco -l app.kubernetes.io/name=falco -c falco -f | grep -i "Notice" &

# Trigger runtime anomaly: Jalankan shell di pod staging-secure
kubectl exec -it compliant-secure-pod -n staging-secure -- sh -c "id; ls /"
```

*Verifikasi Output Log Falco*:
Falco mendeteksi spawn shell secara instan pada standard output log:
```
Notice A shell was spawned in a container with an attached terminal (evt_type=execve user=10001 user_loginuid=-1 process=sh pcmdline=sh -c id; ls / gparent=containerd-shim-runc-v2 container_id=3b92f7... container_name=busybox image=busybox:1.36)
```

---

### 17. Real-world Case Study & Incident Analysis Enterprise

#### Deskripsi Insiden: "The Crypto-Phantom Infiltration" (Retail Enterprise E-Commerce)
*   **Target Korban**: Platform E-Commerce berbasis microservices (200 Node Kubernetes Cluster di Cloud AWS).
*   **Vektor Akses Awal**: Kerentanan Apache Struts OGNL Injection yang belum ditambal pada deployment pod customer support legacy yang berada di namespace `support-tools`.
*   **Konfigurasi Kluster Eksisting**:
    *   Tidak ada Pod Security Standards yang diterapkan.
    *   Namespace `support-tools` tidak memiliki `NetworkPolicy` (unrestricted networking).
    *   Container berjalan sebagai default user (`root`).
    *   Root filesystem container bersifat writable (`readOnlyRootFilesystem: false`).
    *   Tidak ada runtime agent eBPF; audit logging apiserver hanya disimpan selama 3 hari tanpa alerting rule dinamis.

#### Rekonstruksi Kill Chain Penyerang
1.  **Exploitation**: Penyerang mengirim payload HTTP header `Content-Type` yang termanipulasi ke aplikasi Apache Struts, mengeksekusi arbitrary command di pod target dengan privilese UID 0 (`root`).
2.  **Payload Ingestion**: Karena root filesystem berstatus *writable*, penyerang menggunakan `curl` untuk mendownload script installer malware ke direktori `/tmp/setup.sh` dan mengeksekusi biner XMRig miner yang disamarkan sebagai `/usr/sbin/cron-update`.
3.  **Lateral Reconnaissance & SSRF**:
    *   Workload mengeksekusi query HTTP ke CoreDNS untuk memetakan service `auth-service.production.svc.cluster.local`.
    *   Workload memanggil AWS Metadata API (`http://169.254.169.254/latest/meta-data/iam/security-credentials/`) untuk mengambil token IAM Worker Node, karena tidak ada pemblokiran egress layer-3.
4.  **Dampak Kerugian**:
    *   Biaya komputasi cloud membengkak sebesar $45,000 akibat saturasi CPU worker node selama 12 hari penambangan cryptocurrency tanpa terdeteksi.
    *   Pencurian temporary session IAM Role memungkinkan penyerang membaca 2 bucket AWS S3 yang berisi data transaksi pelanggan.

```
ATTACK PATH TIMELINE:
[Apache Struts Pod (support-tools)]
   |
   +--> (Exploit RCE) ---> Runs as Root (UID 0)
   +--> (File Write)  ---> Downloads /tmp/setup.sh -> writes /usr/sbin/cron-update
   +--> (Unrestricted Egress) ---> Reaches 169.254.169.254 -> Steals IAM Instance Profile
   +--> (Flat Network)       ---> Reaches auth-service.production.svc.cluster.local
   +--> (Exfiltration)       ---> Drains data via outbound internet connection to C2
```

#### Remediasi Arsitektur Menyeluruh (Post-Incident Hardening)
1.  **Shift-Left & Admission**:
    *   Implementasi OPA Gatekeeper dengan kebijakan memblokir container yang tidak berjalan sebagai non-root (`runAsNonRoot: true`) dan memaksa `readOnlyRootFilesystem: true`. Payload file write pada `/tmp` atau `/usr/sbin` otomatis gagal di sistem file.
2.  **Network Microsegmentation**:
    *   Pemasangan default `NetworkPolicy` deny-all di seluruh namespace.
    *   Egress dibatasi secara ketat hanya ke DNS internal cluster, dan pemblokiran total ke IP Metadata AWS (`169.254.169.254/32`).
3.  **Runtime eBPF Active Defense**:
    *   Deploy Cilium dan Tetragon. Diterapkan `TracingPolicy` untuk mengirimkan `SIGKILL` secara instan ke setiap proses yang mengeksekusi binary dari direktori `/tmp`, `/dev/shm`, atau binary yang memiliki hash di luar baseline container image.
4.  **Least Privilege IAM**:
    *   Migrasi dari Node Instance Role ke AWS EKS Pod Identity / IRSA (IAM Roles for Service Accounts) dengan restriksi IMDSv2 Hop Count = 1 untuk memastikan pod tidak dapat membaca metadata worker node.

---

### 18. Quiz Pemahaman & Challenge

#### Soal Pilihan Ganda

##### Pertanyaan 1
Pada siklus request di dalam `kube-apiserver`, mengapa eksekusi `MutatingWebhookConfiguration` selalu dijalankan **sebelum** `ValidatingWebhookConfiguration`?
*   A. Karena Mutating Webhook membutuhkan privilege etcd storage yang lebih tinggi daripada Validating Webhook.
*   B. Agar setiap modifikasi struktur objek yang dilakukan oleh Mutating Webhook dapat dievaluasi dan divalidasi keabsahan akhirnya oleh Validating Webhook sebelum disimpan ke etcd.
*   C. Karena Validating Webhook hanya berfungsi memvalidasi otentikasi user via certificates, bukan objek manifest.
*   D. Merupakan bug legacy yang dipertahankan untuk kompatibilitas ke belakang (backward compatibility).

##### Pertanyaan 2
Sebuah tim platform menerapkan Pod Security Admission level `Restricted` pada namespace `production`. Manakah konfigurasi `securityContext` minimum yang **wajib** dipenuhi agar sebuah pod container dapat dijalankan?
*   A. `privileged: false`, `capabilities: {add: ["NET_ADMIN"]}`
*   B. `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `capabilities: {drop: ["ALL"]}`, seccomp profile yang valid.
*   C. `readOnlyRootFilesystem: false`, `hostNetwork: false`, `runAsUser: 0`
*   D. `allowPrivilegeEscalation: true`, `runAsGroup: 0`

##### Pertanyaan 3
Apa perbedaan mendasar antara mekanisme deteksi ancaman Falco konvensional dan runtime enforcement Tetragon menggunakan LSM BPF?
*   A. Falco tidak menggunakan eBPF sama sekali, sedangkan Tetragon murni user space.
*   B. Falco memproses event secara asinkron di user space (deteksi & alerting), sedangkan Tetragon mampu mengeksekusi terminasi inline sinkron (SIGKILL) langsung di kernel space sebelum syscall selesai.
*   C. Falco berjalan di Master Node, sedangkan Tetragon hanya berjalan di etcd database.
*   D. Falco hanya memonitor DNS request, sedangkan Tetragon memonitor HTTP payload API server.

##### Pertanyaan 4
Jika pod Anda berhasil dieksploitasi menggunakan Remote Code Execution, konfigurasi manakah yang paling efektif mencegah penyerang men-download dan menginstal persistence tooling (seperti biner `nmap`, script shell, atau tools mining) ke dalam container tersebut?
*   A. Menghapus konfigurasi readinessProbe dan livenessProbe.
*   B. Mengaktifkan `securityContext.readOnlyRootFilesystem: true`.
*   C. Menggunakan dynamic PVC storage class.
*   D. Mengatur replicaCount menjadi lebih dari 5 replika.

##### Pertanyaan 5
Bagaimana penyerang di dalam pod pada jaringan Kubernetes standar (flat network) dapat mencuri credential cloud infrastruktur jika CNI tidak memiliki `NetworkPolicy` egress yang memadai?
*   A. Dengan memodifikasi file `/etc/resolv.conf` di node worker secara lokal.
*   B. Dengan mengirim payload HTTP request langsung ke Cloud Instance Metadata Service di alamat `http://169.254.169.254`.
*   C. Dengan melakukan flooding DNS request ke port `53` apiserver.
*   D. Dengan menghapus etcd data directory secara remote.

---

#### Kunci Jawaban Quiz
*   **Q1**: **B** – Modifikasi mutasi objek harus diverifikasi oleh validator independen untuk mencegah mutator menyuntikkan konfigurasi tidak aman sebelum ditulis permanen ke etcd.
*   **Q2**: **B** – PSS level `Restricted` secara mutlak mewajibkan non-root, eliminasi eskalasi hak akses (`allowPrivilegeEscalation: false`), pembersihan seluruh capabilities (`drop: ["ALL"]`), dan runtime default seccomp profile.
*   **Q3**: **B** – Tetragon LSM BPF hooks mengevaluasi syscall di kernel context dan dapat menghentikan proses (`action: Sigkill`) sebelum execution context dikembalikan ke userspace, mencegah window of exposure dari deteksi asinkron.
*   **Q4**: **B** – `readOnlyRootFilesystem: true` me-mount layer penulisan overlayfs container sebagai read-only, sehingga eksekusi seperti `curl ... > /tmp/binary` atau `apt-get` akan langsung menghasilkan error `Read-only file system`.
*   **Q5**: **B** – Instance Metadata Service (IMDS) cloud provider berada di link-local IP statis `169.254.169.254`. Ketiadaan egress filter NetworkPolicy mengizinkan pod mengakses kredensial IAM role instance worker node tersebut.

---

#### Practical Challenge: The Broken Gatekeeper Hardening
*   **Skenario**: Anda ditugaskan memperbaiki pipeline deployment pada namespace `pci-compliance`. Developer mengeluh bahwa deployment aplikasi billing mereka ditolak oleh admission controller. Di saat yang sama, tim audit menemukan bahwa pod development dapat memanggil metadata IP AWS.
*   **Instruksi Tugas**:
    1.  Tulis satu file deklarasi `NetworkPolicy` (`pci-isolation.yaml`) yang:
        *   Membatasi pod pada namespace `pci-compliance` hanya menerima ingress dari namespace `api-gateway`.
        *   Memblokir total akses egress ke subnet metadata provider `169.254.169.254/32` tanpa memutus akses komunikasi DNS ke `kube-system`.
    2.  Tulis manifest Kyverno `ClusterPolicy` (`enforce-pci-seccontext.yaml`) yang memvalidasi bahwa seluruh pod yang dideploy di namespace `pci-compliance` wajib menyertakan blok:
        *   `runAsNonRoot: true`
        *   `readOnlyRootFilesystem: true`
        *   Setiap pelanggaran wajib di-`Enforce` (blokir) dengan pesan error spesifik.
    3.  Lakukan verifikasi menggunakan `kubectl dry-run` client side dan pastikan validasi syntax bebas dari error deklaratif.

---

### 19. Summary & Key Takeaways

1.  **Shift-Left & Run-Right Continuum**: Keamanan container Kubernetes tidak dapat dijamin hanya dengan scanning image statis pada tahap CI/CD pipeline. Diperlukan sinergi antara filter statis pada pintu masuk cluster (*Dynamic Admission Control & PSA*) dan monitoring/enforcement aktif di level kernel (*eBPF Runtime Defense*).
2.  **Pod Security Standards (PSA) adalah Fondasi Utama**: PSS/PSA