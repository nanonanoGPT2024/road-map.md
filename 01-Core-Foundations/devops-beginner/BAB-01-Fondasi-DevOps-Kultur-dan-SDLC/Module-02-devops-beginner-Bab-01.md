# Kurikulum Enterprise DevOps: 01-Core-Foundations
## BAB-01: Fondasi dan Arsitektur
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik pada level enterprise engineering diharapkan mampu:
1. **Menganalisis & Mengisolasi Primitif Kernel Linux**: Menguraikan dan merekonstruksi mekanisme isolasi proses tingkat rendah (*Linux Namespaces*, *Control Groups v2*, dan *Capabilities*) yang mendasari runtime kontainer modern tanpa bergantung pada abstraksi tingkat tinggi seperti Docker daemon.
2. **Merancang Pipeline Continuous Delivery Skala Enterprise**: Mengarsitekturi sistem deployment otomatis zero-downtime berbasis *Progressive Delivery* (Canary dan Blue/Green) yang terintegrasi langsung dengan metrik verifikasi telemetri otomatis.
3. **Mengimplementasikan Guardrail Keamanan Supply Chain (DevSecOps)**: Mengintegrasikan proses penandatanganan artefak kriptografis (*Cosign*), verifikasi integritas paket (*SBOM*), dan validasi statis/dinamis ke dalam pipeline CI/CD sesuai standar SLSA (*Supply-chain Levels for Software Artifacts*) Framework Level 3.
4. **Mendiagnosis Kegagalan Sistem Terdistribusi Tingkat Lanjut**: Melacak kebocoran sumber daya, *OOM (Out-of-Memory) thrashing*, serta anomali jaringan overlay menggunakan perangkat inspeksi sistem operasi tingkat rendah (`strace`, `nsenter`, `bpftrace`, dan analisis subsistem `/proc` & `/sys`).

---

### 2. Prerequisite

Peserta wajib menguasai kompetensi dasar berikut sebelum mempelajari modul ini:
* **Sistem Operasi**: Pemahaman arsitektur kernel Linux POSIX, manajemen memori virtual (paging, swap, VMA), manajemen proses (fork/exec, PID lifecycle, signals), dan filesystem hierarchy standard (FHS).
* **Jaringan Komputer**: TCP/IP stack (handshake 3-arah, TCP states, socket programming basics), DNS resolution internals, routing table, iptables/nftables packet filtering, dan HTTP/1.1 vs HTTP/2 protocol frame structure.
* **Perangkat Lunak & CLI**: Kemahiran scripting Bash tingkat lanjut (POSIX compliant, trap handlers, subshells), penguasaan Git internals (blobs, trees, commit objects, DAG), dan pembacaan format serialisasi data (JSON, YAML).

---

### 3. Concept & Internal Architecture

Fondasi DevOps modern di tingkat enterprise bertumpu pada kemampuan mengoperasikan abstraksi infrastruktur perangkat lunak di atas sistem operasi tanpa kehilangan visibilitas terhadap kondisi komputasi fisik.

```
+-------------------------------------------------------------------------------+
|                           USER APPLICATION LAYER                              |
|   12-Factor App | Microservices | Distributed Tracing Context (W3C TraceParent)|
+-------------------------------------------------------------------------------+
                                    |
+-------------------------------------------------------------------------------+
|                       ORCHESTRATION & DELIVERY LAYER                          |
|   GitOps Engine (ArgoCD) | Progressive Rollout Controller | Ingress / Mesh     |
+-------------------------------------------------------------------------------+
                                    |
+-------------------------------------------------------------------------------+
|                    CONTAINER RUNTIME ENGINE (CRI / OCI)                       |
|   containerd / CRI-O  -->  runc  -->  libcontainer                             |
+-------------------------------------------------------------------------------+
                                    |
+-------------------------------------------------------------------------------+
|                           LINUX KERNEL PRIMITIVES                             |
|  Namespaces       | cgroups v2        | LSM / Capabilities | Netfilter/eBPF   |
|  - PID, MNT, NET  | - Memory (OOM)    | - CapDrop          | - Packet Routing |
|  - IPC, UTS, USER | - CPU (Bandwidth) | - Seccomp Profile  | - XDP Bypass     |
+-------------------------------------------------------------------------------+
```

#### A. Primitif Isolasi Kernel Linux: Namespaces dan cgroups v2
Kontainer bukanlah entitas fisik atau virtualisasi perangkat keras; kontainer adalah proses Linux biasa dengan atribut isolasi yang dikonfigurasi melalui syscall kernel.

* **Linux Namespaces**: Menyediakan ilusi lingkungan sistem operasi yang sepenuhnya terisolasi untuk proses tertentu.
  * `CLONE_NEWPID`: Mengisolasi penomoran Process ID. Di dalam namespace, proses utama melihat dirinya sebagai PID 1.
  * `CLONE_NEWNET`: Mengisolasi stack jaringan fisik (perangkat jaringan, tabel routing, firewall rules, port binding).
  * `CLONE_NEWNS` (Mount): Mengisolasi mount points filesystem. Operasi `mount` atau `umount` tidak berimbas pada host.
  * `CLONE_NEWUTS`: Mengisolasi hostname dan domain name NIS.
  * `CLONE_NEWIPC`: Mengisolasi antrean pesan System V, POSIX message queues, dan shared memory.
  * `CLONE_NEWUSER`: Memetakan UID/GID host ke UID/GID virtual di dalam namespace (memungkinkan eksekusi sebagai UID 0 root di dalam kontainer, namun non-root UID 10001 di host fisik).
  * `CLONE_NEWCGROUP`: Mengisolasi visibilitas cgroup hierarchy dari proses.

* **Control Groups (cgroups) v2**: Mekanisme hierarkis untuk membatasi, mencatat, dan mengisolasi alokasi sumber daya fisik (CPU, Memori, I/O, PIDs) dari sekumpulan proses. Berbeda dari cgroups v1 yang memiliki hierarki terpisah untuk setiap controller (sehingga memicu *race condition* dan inefisiensi pengalokasian), cgroups v2 menerapkan *unified hierarchy tree*.
  * **Memory Controller**: Mengendalikan batas alokasi memori halaman anonim (*anonymous memory*), *page cache*, dan swap. Bila alokasi melebihi batas `memory.max`, kernel akan memicu memory reclamation. Jika tidak mencukupi, kernel akan membunuh proses dengan `oom-killer` berdasarkan skor `oom_score_adj`.
  * **CPU Controller**: Menerapkan model *Completely Fair Scheduler (CFS) bandwidth control*. Ditentukan melalui `cpu.max` yang terdiri dari dua parameter: `quota` dan `period`. Contoh: kuota `50000` dengan periode `100000` mengindikasikan batas konsumsi maksimal sebesar $0.5$ CPU core per $100$ milidetik.

#### B. Continuous Delivery Internals: Progressive Delivery & GitOps Engine
Sistem pengiriman perangkat lunak modern menolak intervensi manusia dalam deployment produksi. Paradigma yang digunakan adalah:

* **Infrastruktur Deklaratif (GitOps)**: Seluruh status sistem (*desired state*) didefinisikan secara deklaratif di dalam Git. Komponen rekonsiliasi (*reconciliation loop*) secara periodik membandingkan status deklaratif di Git dengan status aktual di cluster produksi (*actual state*). Apabila terjadi *drift*, agen rekonsiliasi mengembalikan kondisi sistem ke status Git secara atomik.
* **Progressive Delivery (Canary Deployments)**: Mengalihkan fraksi kecil trafik pengguna riil (misal: 1%, 5%, 10%) ke versi aplikasi baru (*Canary*) sembari mempertahankan versi stabil (*Baseline*). Kontroler canary menganalisis metrik keberhasilan secara dinamis (*dynamic threshold validation*) seperti HTTP 5xx error rate dan latency persentil p99. Kegagalan mencapai SLA memicu rollback otomatis tanpa waktu henti.

#### C. Arsitektur Observabilitas Terdistribusi: Context Propagation
Untuk melacak transaksi yang melewati ratusan microservices, sistem memerlukan tracing terdistribusi dengan format standar W3C TraceContext:
* **TraceID**: Pengidentifikasi acak global unik berukuran 16-byte yang mengikat seluruh perjalanan request dari klien pertama hingga database backend terdalam.
* **SpanID**: Pengidentifikasi operasi tunggal berukuran 8-byte dalam sebuah service.
* **Context Propagation**: Header HTTP `traceparent` (contoh: `00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`) wajib di-parsing, dimutasi, dan diteruskan oleh setiap layanan downstream via layer proxy atau instrumentasi kode untuk mencegah hilangnya jejak eksekusi (*broken traces*).

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Legacy Ops) | Paradigma Rekayasa Produksi Modern (DevOps Enterprise) |
| :--- | :--- | :--- |
| **Batas Isolasi Runtime** | Virtual Machine berbasis hypervisor berat (Type-1/Type-2) atau eksekusi *bare-metal* kotor dengan dependency collision. | Kontainerisasi murni berbasis kernel primitives (cgroups v2 + user namespaces) dengan batas isolasi performa tinggi dan footprint memori minimal. |
| **Deployment Lifecyle** | Maintenance window tengah malam, manual stop/start service, konfigurasi SSH *ad-hoc* imperatif. | Immutable infrastructure, blue/green canary rollout otomatis dengan automated metric-driven gatekeeper. Zero downtime. |
| **Arsitektur Konfigurasi** | Konfigurasi disimpan lokal di server, *hardcoded* di source code, atau disebar via email/wiki internal. | Paradigma 12-Factor App: Strict separation of config from code, injeksi via environment variables/Secret Manager yang terenkripsi. |
| **Keamanan Perangkat Lunak** | Audit statis manual tahunan, scanning ad-hoc saat rilis besar (*late feedback loop*). | DevSecOps Shift-Left: Validasi SAST/DAST, SCA, SBOM generation, dan cryptographic image signing langsung di transient CI worker. |
| **Observabilitas** | Logging manual menggunakan file log `/var/log/*`, polling metrik via shell script imperatif. | Tracing context terdistribusi OpenTelemetry, metrik RED (Rate, Errors, Duration) / USE (Utilization, Saturation, Errors), and log aggregation. |

---

### 5. How (Workflow Detail)

Siklus hidup operasional aplikasi dimulai dari modifikasi kode hingga verifikasi otomatis di lingkungan produksi:

```
[Developer]
    | (1) git push (Trunk-Based / Short-lived Branch)
    v
[GitHub Actions / GitLab CI Engine]
    | (2) Linting & Security Gate (SAST / Trivy Vulnerability Scan)
    | (3) Multi-stage Ephemeral Build Container
    | (4) SBOM Generation (Syft) & Artifact Signing (Cosign)
    | (5) Push Signed OCI Image to Enterprise Container Registry
    v
[GitOps Repository / ArgoCD Engine]
    | (6) Automated PR: Update target image tag sha256
    | (7) ArgoCD Detects Desired State Drift
    | (8) Synchronize Manifest to Target Cluster
    v
[Production Cluster Network Ingress]
    | (9) Initialize Canary Service (e.g. 5% Initial Traffic via Ingress)
    | (10) Prometheus / Metric Engine: Poll p99 Latency & Error Rate
    +---> IF PASS: Increment traffic (25% -> 50% -> 100%)
    +---> IF FAIL: Automatic Traffic Severing & Revert to Baseline
```

1. **Commit Phase**: Pengembang mendorong perubahan kode kecil ke branch utama menggunakan metodologi *Trunk-Based Development*.
2. **Deterministic Build Phase**: CI worker menjalankan build terisolasi. Seluruh pustaka eksternal diverifikasi menggunakan cryptographic hash lockfile (`package-lock.json`, `go.sum`, `Cargo.lock`).
3. **Artifact Hardening & Attestation**:
   - Container image dibangun menggunakan base image minimalis (*Distroless* atau *Scratch*).
   - *Software Bill of Materials* (SBOM) diekstraksi ke format SPDX/CycloneDX.
   - Image ditandatangani menggunakan private key / ephemeral OIDC certificate via Cosign.
4. **GitOps Trigger Phase**: CI engine membuat deklarasi commit ke repository konfigurasi GitOps, memperbarui hash digest `sha256:....` secara spesifik, bukan menggunakan tag dinamis seperti `:latest`.
5. **Progressive Rollout Execution**: Ingress controller membagi trafik pada layer 7. Sistem analisis metrik melakukan query ke Prometheus setiap 30 detik untuk memvalidasi performa.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Arsitektur Partisi Gedung Perkantoran Modern vs Kontainer Linux
Bayangkan sebuah gedung perkantoran besar (Kernel Linux tunggal):
* **Virtual Machine (VM)**: Membangun gedung-gedung kecil mandiri di dalam lahan parkir. Setiap gedung memiliki genset sendiri, instalasi pipa air sendiri, dan petugas keamanan sendiri. Sangat aman dan terisolasi, namun memakan ruang besar, biaya mahal, dan lambat dibangun.
* **Linux Namespaces**: Pemasangan sekat dinding kedap suara dan pintu akses satu arah di dalam satu gedung besar yang sama. Ruang meeting A (Namespace A) tidak bisa melihat dokumen di Ruang meeting B (Namespace B), dan mereka memiliki papan penomoran meja sendiri (PID namespace) meskipun menggunakan lantai dan atap yang sama.
* **Linux cgroups**: Kartu akses pintar yang membatasi daya listrik maksimal yang bisa dikonsumsi oleh penyewa di Lantai 3 (maksimal 10 Ampere). Jika penyewa mencoba menggunakan 11 Ampere, sekering otomatis memutus daya peralatan berlebih (*OOM killer / CPU throttling*).

#### Diagram Arsitektur Isolasi Proses Linux Tingkat Rendah:
```
+-------------------------------------------------------------------------+
| HOST HARDWARE (CPU, RAM, PHYSICAL NIC: eth0)                            |
+-------------------------------------------------------------------------+
                                   |
+-------------------------------------------------------------------------+
| LINUX KERNEL (Syscall Interface: clone, unshare, setns, pivot_root)     |
|                                                                         |
|  +------------------------+             +----------------------------+  |
|  | cgroup: /sys/fs/cgroup |             | Network Engine (netfilter) |  |
|  | memory.max = 256MB     |             | veth-host <--> veth-guest  |  |
|  | cpu.max = 50000 100000 |             | NAT/Masquerading to eth0   |  |
|  +------------------------+             +----------------------------+  |
+-------------------------------------------------------------------------+
       |                                                |
       | (Enforced limits)                              | (Enforced Network)
       v                                                v
+-------------------------------------------------------------------------+
| ISOLATED PROCESS (Namespace Boundary)                                   |
|                                                                         |
|   UTS NS:    hostname: "workload-pod-prod"                              |
|   PID NS:    Process Binary (PID 1 inside, PID 38921 outside)          |
|   MNT NS:    rootfs: /sysroot (isolated via pivot_root)                 |
|   NET NS:    eth0 (IP: 10.244.1.15, isolated loopback 'lo')             |
|   USER NS:   uid 0 (container) mapped to uid 10001 (host)               |
+-------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Membuat Runtime Kontainer Mandiri dari Nol
Skrip Bash POSIX berikut mengimplementasikan isolasi sistem murni langsung di atas kernel Linux menggunakan utilitas sistem operasi (`unshare`, `cgcreate`, `chroot`), membuktikan bahwa runtime container hanyalah perakitan primitives Linux.

```bash
#!/usr/bin/env bash
# ==============================================================================
# mini-container.sh: Mengisolasi eksekusi proses tanpa Docker Engine
# Prasyarat: Linux dengan cgroups v2 aktif dan package iproute2 terpasang.
# Jalankan sebagai ROOT.
# ==============================================================================
set -euo pipefail

CONTAINER_DIR="/tmp/mini-container-root"
CGROUP_PATH="/sys/fs/cgroup/sandbox-group"

cleanup() {
    echo "[*] Cleaning up resources..."
    rm -rf "${CONTAINER_DIR}"
    if [ -d "${CGROUP_PATH}" ]; then
        # Mengembalikan proses ke root cgroup sebelum menghapus leaf group
        rmdir "${CGROUP_PATH}" 2>/dev/null || true
    fi
}
trap cleanup EXIT

echo "[1] Mempersiapkan Root Filesystem (RootFS) terisolasi..."
mkdir -p "${CONTAINER_DIR}"/{bin,lib,lib64,proc,sys,dev}
cp /bin/bash "${CONTAINER_DIR}/bin/bash"
cp /bin/ls "${CONTAINER_DIR}/bin/ls"
cp /bin/ps "${CONTAINER_DIR}/bin/ps"

# Menyalin dependency shared libraries dinamis untuk binary
copy_deps() {
    local bin="$1"
    ldd "$bin" | grep -o '/lib[^ ]*' | while read -r lib; do
        mkdir -p "${CONTAINER_DIR}$(dirname "$lib")"
        cp -L "$lib" "${CONTAINER_DIR}$lib" 2>/dev/null || true
    done
}
copy_deps "/bin/bash"
copy_deps "/bin/ls"
copy_deps "/bin/ps"

echo "[2] Mengonfigurasi cgroups v2 resource limits..."
mkdir -p "${CGROUP_PATH}"
# Batasi alokasi memory maksimal 64 Megabytes
echo "67108864" > "${CGROUP_PATH}/memory.max"
# Batasi CPU hingga 20% dari 1 core (20000 us dari 100000 us period)
echo "20000 100000" > "${CGROUP_PATH}/cpu.max"

echo "[3] Mengeksekusi proses dalam namespace terisolasi..."
# Flag unshare:
# -m: Mount Namespace
# -u: UTS Namespace (Hostname)
# -i: IPC Namespace
# -p -f: PID Namespace & Fork child process
# --mount-proc: Mount /proc virtual filesystem khusus namespace baru
unshare --mount --uts --ipc --pid --fork bash -c "
    # Pasang cgroup execution untuk shell baru ini
    echo \$\$ > '${CGROUP_PATH}/cgroup.procs'
    
    # Ubah hostname internal
    hostname 'isolated-runtime'
    
    # Mount isolated procfs
    mount -t proc proc '${CONTAINER_DIR}/proc'
    
    # Chroot ke direktori baru
    chroot '${CONTAINER_DIR}' /bin/bash -c '
        echo \"=== INFORMASI DI DALAM CONTAINER ===\"
        echo \"Hostname: \$(hostname)\"
        echo \"Daftar Proses (PID Isolation):\"
        /bin/ps aux
        echo \"====================================\"
    '
    
    # Unmount procfs sebelum keluar
    umount '${CONTAINER_DIR}/proc'
"
```

#### B. Practical Example: Production Progressive Canary Pipeline
Implementasi standar industri berbasis Kubernetes Custom Resource Definition (`Argo Rollout`) yang mendefinisikan *Canary Strategy* otomatis terintegrasi dengan validasi metrik latency p99 Prometheus.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: payment-processing-engine
  namespace: finance-prod
  labels:
    app.kubernetes.io/name: payment-engine
    app.kubernetes.io/part-of: core-banking
spec:
  replicas: 10
  revisionHistoryLimit: 5
  selector:
    matchLabels:
      app: payment-engine
  strategy:
    canary:
      canaryService: payment-engine-canary
      stableService: payment-engine-stable
      trafficRouting:
        nginx:
          stableIngress: payment-engine-ingress
      analysis:
        templates:
          - templateName: verify-payment-health
        args:
          - name: service-name
            value: payment-engine-canary
      steps:
        # Tahap 1: Alihkan 5% trafik, validasi metrik selama 5 menit
        - setWeight: 5
        - pause: { duration: 5m }
        # Tahap 2: Alihkan 20% trafik, pause verifikasi manual atau metrics
        - setWeight: 20
        - pause: { duration: 10m }
        # Tahap 3: Alihkan 50% trafik
        - setWeight: 50
        - pause: { duration: 10m }
  template:
    metadata:
      labels:
        app: payment-engine
    spec:
      containers:
        - name: payment-engine
          image: internal-registry.enterprise.io/finance/payment-api:sha256-4c28a9f6004b5003b1d3f9b2d8e4f1a238e8cb14b532997dbe2fe31e8c0e25ef
          imagePullPolicy: IfNotPresent
          resources:
            requests:
              cpu: "500m"
              memory: "512Mi"
            limits:
              cpu: "1000m"
              memory: "1024Mi"
          securityContext:
            readOnlyRootFilesystem: true
            runAsNonRoot: true
            runAsUser: 10001
            allowPrivilegeEscalation: false
            capabilities:
              drop:
                - ALL
          ports:
            - name: http-api
              containerPort: 8080
          livenessProbe:
            httpGet:
              path: /healthz/liveness
              port: http-api
            initialDelaySeconds: 15
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /healthz/readiness
              port: http-api
            initialDelaySeconds: 5
            periodSeconds: 5
---
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: verify-payment-health
  namespace: finance-prod
spec:
  metrics:
  - name: success-rate-threshold
    interval: 30s
    successCondition: result[0] >= 0.9995
    failureLimit: 3
    provider:
      prometheus:
        address: http://prometheus-k8s.monitoring.svc.cluster.local:9090
        query: |
          sum(rate(http_requests_total{service="payment-engine-canary",status!~"5.*"}[2m]))
          /
          sum(rate(http_requests_total{service="payment-engine-canary"}[2m]))
  - name: latency-p99-threshold
    interval: 30s
    successCondition: result[0] <= 0.250
    failureLimit: 2
    provider:
      prometheus:
        address: http://prometheus-k8s.monitoring.svc.cluster.local:9090
        query: |
          histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{service="payment-engine-canary"}[2m])) by (le))
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks & Skala Arsitektur
Sebuah platform sistem pembayaran nasional memproses volume transaksi harian dengan beban puncak mencapai 45.000 Request Per Second (RPS). Sistem berjalan di atas cluster Kubernetes multi-zona dengan 120 node bare-metal berkapasitas tinggi.

#### Masalah Sistemik (The Incident)
Saat peluncuran rilis v2.14.0 (berisi pembaruan pustaka enkripsi transaksi), tim infrastruktur menggunakan pola *Recreate Deployment* sederhana. Dampaknya:
1. **Thundering Herd Problem**: 100+ pod lama dimatikan serentak, menyebabkan ribuan koneksi TCP klien terputus mendadak (*connection reset by peer*).
2. **Database Connection Starvation**: 100+ pod baru menyala secara simultan dan membanjiri pool koneksi cluster PostgresQL primer dengan 15.000 transaksi negosiasi handshake SSL baru sekaligus.
3. **Cascading Failure**: Latensi database melonjak dari 4ms ke 12.000ms. CPU starvation memicu kegagalan liveness probe di seluruh node, berujung pada pemusnahan pod secara berantai (*crash loop cascading collapse*). Sistem mati total (*blackout*) selama 42 menit dengan estimasi kerugian transaksi mencapai jutaan dolar.

#### Solusi Rekayasa & Transformasi Arsitektur
Tim Principal Infrastructure merekonstruksi arsitektur deployment secara menyeluruh:

```
[Edge Load Balancer]
       |
       v (Ingress Controller with Dynamic Weighting)
       |
       +--- 95% Traffic ---> [Baseline ReplicaSet v2.13.0] (100 Pods)
       |                          |
       |                          +--> Stable DB Connection Pool
       |
       +---  5% Traffic ---> [Canary ReplicaSet v2.14.0] (5 Pods)
                                  |
                                  +--> Monitored via Prometheus Analysis
```

1. **Implementasi Progressive Delivery**:
   - Mengalihkan trafik awal sebesar $2\%$ menggunakan service mesh Envoy dengan algoritma routing layer 7.
   - Evaluasi kriteria *Golden Signals* secara periodik setiap 60 detik selama 30 menit. Jika error rate melebihi $0.05\%$ atau latensi p99 melampaui $200\text{ ms}$, algoritma iptables langsung memutus routing ke pod canary dan mengembalikan seluruh alokasi trafik ke pod baseline dalam $1.2$ detik.
2. **Graceful Connection Draining**:
   - Menambahkan lifecycle hook `preStop: sleep 15` untuk menjamin pencabutan IP pod dari endpoint iptables sebelum runtime mengirimkan sinyal `SIGTERM`.
   - Mengimplementasikan penanganan sinyal `SIGTERM` di level aplikasi dengan batas toleransi draining koneksi aktif selama 30 detik sebelum menerima sinyal `SIGKILL`.
3. **Database Guardrails**:
   - Memasang layer proxy koneksi (PgBouncer) yang menerapkan *transaction-level pooling*, mencegah kehabisan slot koneksi database saat fase penskalaan pod baru.

---

### 9. Trade-offs

Setiap keputusan arsitektur dalam ekosistem DevOps membawa konsekuensi teknis dan finansial yang harus diperhitungkan secara presisi:

```
+---------------------------------------------------------------------------------------+
| Pendekatan Rekayasa        | Keuntungan Utama       | Konsekuensi Teknis / Biaya      |
+---------------------------------------------------------------------------------------+
| Canary Deployments         | Risiko kegagalan sistem| Kompleksitas manajemen ingress  |
| vs                         | diminimalkan pada fraksi| layer 7; butuh infrastruktur   |
| In-Place / Rolling Update  | kecil pengguna.        | telemetri real-time presisi.    |
+---------------------------------------------------------------------------------------+
| Trunk-Based Development   | Menghindari merge hell;| Membutuhkan test suite otomatis  |
| vs                         | lead time commit-to-   | yang sangat cepat (<5 min) dan  |
| GitFlow (Feature Branches) | production ultra-rendah| maturitas Feature Flagging tinggi|
+---------------------------------------------------------------------------------------+
| Distroless / Scratch Base  | Attack surface minimal;| Tidak ada utilities debug dasar |
| vs                         | tidak ada CVE shell.   | (curl, sh, bash) saat insiden; |
| Full OS Base (Ubuntu/Debian| Ukuran image sangat    | diagnosa wajib via ephemeral    |
| Container Images)          | kecil (<20MB).         | debug containers (nsenter).     |
+---------------------------------------------------------------------------------------+
| Microservices per Process  | Skalabilitas horizontal| Latensi jaringan inter-service  |
| vs                         | independen, domain-    | bertambah (overhead serialization|
| Modular Monolith           | bounded context bersih.| & TLS handshakes); tracing rumit|
+---------------------------------------------------------------------------------------+
```

---

### 10. Common Mistakes & Troubleshooting

#### A. Kesalahan Fatal yang Sering Terjadi (Anti-Patterns)
1. **Penggunaan Tag Dinamis `:latest` di Lingkungan Produksi**:
   - *Penyebab*: Container runtime melakukan caching layer berdasarkan metadata tag. Node yang berbeda berpotensi menjalankan image digest yang berbeda secara bersamaan, menciptakan inkonsistensi status runtime (*non-deterministic execution*).
   - *Solusi*: Wajib menyematkan *immutable digest*: `image:tag@sha256:7f83b165...`
2. **Menjalankan Proses Utama sebagai Root (UID 0)**:
   - *Penyebab*: Mengabaikan konfigurasi `runAsNonRoot: true`. Jika terjadi eksploitasi kerentanan *container breakout* (contoh: CVE-2019-5736 pada runc), penyerang secara otomatis memperoleh privilege root penuh terhadap kernel host.
3. **Inappropriate cgroup Limits (Memory Throttling vs OOM Kills)**:
   - *Penyebab*: Menyetel `memory.limit` terlalu dekat dengan konsumsi baseline aplikasi. Fluktuasi kecil pada page cache akibat aktivitas I/O disk memicu Linux kernel OOM Killer secara instan (`exit code 137`).
4. **Broken Tracing Propagation**:
   - *Penyebab*: Menggunakan HTTP client yang tidak menginjeksi header W3C `traceparent` saat memanggil dependency service, menyebabkan tracing graph terpecah menjadi trace terisolasi yang tidak dapat dikorelasikan.

#### B. Panduan Diagnostik Masalah Tingkat Lanjut (Troubleshooting Runbook)
Ketika pod atau kontainer mengalami kegagalan di level kernel, gunakan prosedur debug berikut:

```bash
# 1. Mendeteksi apakah proses terbunuh akibat OOM-Killer kernel
dmesg -T | grep -E -i 'oom[-_]killer|killed process'
# Output tipikal:
# [Wed Oct 25 10:14:22 2023] Memory cgroup out of memory: Killed process 38921 (java) total-vm:4231844kB, anon-rss:1048128kB, file-rss:4120kB

# 2. Mendeteksi namespace dari target container ID di Kubernetes Node
CONTAINER_PID=$(crictl inspect --output go-template --template '{{.info.pid}}' <CONTAINER_ID>)
echo "Target Host PID: ${CONTAINER_PID}"

# 3. Menembus batas isolasi (Injecting Host Toolset ke dalam isolated namespace)
# Menjalankan shell host di dalam Network dan Mount namespace target:
nsenter -t ${CONTAINER_PID} -n -m /bin/bash

# 4. Melacak System Call penyebab performa lambat / blocking secara real-time
strace -f -p ${CONTAINER_PID} -e trace=network,file -s 256

# 5. Memeriksa pembatasan CFS CPU Throttling pada cgroups v2
cat /sys/fs/cgroup/system.slice/docker-<CONTAINER_ID>.scope/cpu.stat
# Perhatikan metrik:
# nr_throttled: Jumlah siklus periode di mana proses dipaksa berhenti
# throttled_usec: Total durasi proses mengalami starvation akibat batas limit
```

---

### 11. Best Practices (Production Checklist)

Gunakan checklist ini sebagai *gatekeeper* sebelum merilis sistem ke lingkungan multi-tenant skala enterprise:

#### Isolation & OS Security
- [ ] Proses berjalan menggunakan User ID non-privilege (`UID >= 10000`).
- [ ] Root filesystem diset ke status read-only (`readOnlyRootFilesystem: true`). Seluruh penulisan sementara wajib diarahkan ke `emptyDir` memory-backed tmpfs.
- [ ] Matikan seluruh Linux capabilities default, alokasikan kembali hanya yang esensial (contoh: hanya `NET_BIND_SERVICE` jika butuh bind port < 1024).
- [ ] Konfigurasikan profil Seccomp standar (`RuntimeDefault`) untuk memblokir syscall berbahaya seperti `ptrace` atau `sys_chroot`.

#### Resource & Schedulability Governance
- [ ] CPU limits dikonfigurasi dengan hati-hati atau dihilangkan jika menggunakan kernel dengan CFS quotas yang rentan latensi artifisial, namun **Memory limits wajib selalu ditetapkan**.
- [ ] Konfigurasi probe kesehatan: Probe `readiness` wajib memverifikasi kesiapan memproses beban kerja tanpa membebani downstream dependencies, dan probe `liveness` hanya mengecek deadlock internal.
- [ ] Pasang `PodDisruptionBudget` (PDB) untuk mencegah hilangnya ketersediaan pod di bawah batas toleransi minimum SLA selama maintenance node draining.

#### Supply Chain Integrity (SLSA Compliance)
- [ ] Image dipindai terhadap Common Vulnerabilities and Exposures (CVE) dengan toleransi 0 Critical vulnerabilities.
- [ ] Image ditandatangani menggunakan kunci kriptografi terverifikasi via Cosign.
- [ ] Metadata artefak mencakup Software Bill of Materials (SBOM) dalam format CycloneDX atau SPDX.

---

### 12. Hands-on Practice

Praktikum ini dirancang untuk dijalankan pada terminal Linux. Simpan seluruh artefak ke direktori `hands-on/m02/`.

#### Task: Mengonfigurasi Cgroups v2 Memory Hard-Limit dan Memicu OOM Handling
Kita akan menguji mekanisme penanganan alokasi memori Linux Kernel dan memverifikasi interaksi cgroup terhadap proses yang melanggar batas alokasi.

##### Langkah 1: Inisialisasi Direktori Kerja
```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
```

##### Langkah 2: Buat Program Pengalokasi Memori C (`allocator.c`)
Program ini akan mengalokasikan blok memori virtual dan menuliskan data secara agresif untuk memaksakan alokasi Physical Resident Set Size (RSS).

```c
// hands-on/m02/allocator.c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define CHUNK_SIZE_MB 10

int main() {
    size_t total_allocated = 0;
    printf("[PID %d] Starting aggressive memory allocation...\n", getpid());

    while (1) {
        char *buffer = (char *)malloc(CHUNK_SIZE_MB * 1024 * 1024);
        if (buffer == NULL) {
            perror("[-] Allocation failed via malloc");
            return 1;
        }

        // Tulis data ke memori agar kernel memetakan Virtual Memory ke Physical RAM
        memset(buffer, 'A', CHUNK_SIZE_MB * 1024 * 1024);
        total_allocated += CHUNK_SIZE_MB;
        printf("[+] Allocated and faulted: %zu MB\n", total_allocated);
        
        // Jeda 500ms agar kita dapat mengamati metrik cgroups
        usleep(500000);
    }

    return 0;
}
```

##### Langkah 3: Kompilasi Binary
```bash
gcc -O2 hands-on/m02/allocator.c -o hands-on/m02/allocator
```

##### Langkah 4: Buat Hierarki Pengujian cgroups v2
```bash
# Verifikasi cgroups v2 telah aktif pada host
if [ ! -f /sys/fs/cgroup/cgroup.controllers ]; then
    echo "ERROR: Sistem ini tidak menjalankan cgroups v2 secara murni!"
    exit 1
fi

# Buat grup isolasi baru
sudo mkdir -p /sys/fs/cgroup/enterprise-lab

# Tetapkan batas maksimal memori menjadi 50MB (52428800 bytes)
# Matikan swap memory agar kernel memicu OOM killer secara deterministik
sudo bash -c 'echo "52428800" > /sys/fs/cgroup/enterprise-lab/memory.max'
sudo bash -c 'echo "0" > /sys/fs/cgroup/enterprise-lab/memory.swap.max'
```

##### Langkah 5: Eksekusi Binary di dalam Cgroup
Jalankan binary dengan membatasi eksekusinya langsung di dalam cgroup target:
```bash
# Jalankan subshell, daftarkan PID-nya ke cgroups procs, lalu eksekusi binary
sudo bash -c '
    echo $$ > /sys/fs/cgroup/enterprise-lab/cgroup.procs
    exec ./hands-on/m02/allocator
'
```

##### Hasil yang Diharapkan:
```text
[PID 142105] Starting aggressive memory allocation...
[+] Allocated and faulted: 10 MB
[+] Allocated and faulted: 20 MB
[+] Allocated and faulted: 30 MB
[+] Allocated and faulted: 40 MB
[+] Allocated and faulted: 50 MB
Killed
```

##### Langkah 6: Verifikasi Forensik Kernel
Periksa alasan terminasi melalui subsistem logging kernel:
```bash
dmesg -T | tail -n 25 | grep -E -A 5 -i 'oom[-_]killer'
```
Anda akan melihat entitas kernel `oom-killer` mengeksekusi aksi terminasi dengan pesan:
`Memory cgroup out of memory: Killed process ... (allocator) score ...`

##### Langkah 7: Pembersihan Lingkungan
```bash
sudo rmdir /sys/fs/cgroup/enterprise-lab
rm hands-on/m02/allocator
```

---

### 13. Exercise

Kerjakan latihan berikut secara mandiri dengan mengimplementasikan artefak kode/konfigurasi yang valid.

#### Level Easy
Tuliskan satu unit script Bash `hands-on/m02/verify-traceparent.sh` yang menerima sebuah string input via argumen CLI berupa W3C TraceParent Header (contoh: `00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`). Script harus memvalidasi panjang bit, versi (wajib `00`), memisahkan TraceID, ParentSpanID, dan TraceFlags, serta mengembalikan exit code 0 jika valid, atau exit code 1 jika format rusak.

#### Level Medium
Buat sebuah file konfigurasi Nginx reverse proxy `hands-on/m02/canary-traffic-split.conf` yang mengimplementasikan pemisahan trafik upstream dinamis menggunakan modul `split_clients`:
- $90\%$ request dialihkan ke backend stable cluster (`backend-stable:8080`).
- $10\%$ request dialihkan ke backend canary cluster (`backend-canary:8080`).
- Request dengan HTTP Header kustom `X-Internal-Employee: true` harus selalu diarahkan $100\%$ ke `backend-canary:8080` tanpa terpengaruh probabilitas distribusi.

#### Level Hard
Rancang file GitHub Actions workflow declarative `.github/workflows/secure-ci-pipeline.yml` yang mengimplementasikan pipeline build supply-chain zero-trust:
1. Membangun sebuah aplikasi Go menggunakan Containerfile multi-stage.
2. Menggunakan `trivy` untuk memindai basis filesystem hasil kompilasi; gagalkan pipeline jika ditemukan celah keamanan level `CRITICAL`.
3. Menghasilkan artefak *Software Bill of Materials* (SBOM) berformat CycloneDX JSON menggunakan Syft.
4. Menandatangani (*sign*) container image yang dihasilkan menggunakan `Cosign` dengan mode *Keyless Signing* memanfaatkan GitHub Actions OIDC token provider.

---

### 14. Challenge

#### Kasus Arsitektur Lanjutan: Mitigasi Split-Brain Progressive Deployment pada Cluster Hybrid Multi-Region
Sebuah institusi perbankan global memiliki arsitektur transaksi yang direplikasi secara aktif (*Active-Active*) di dua region cloud terpisah (Region-A Singapore dan Region-B Tokyo). Kedua region terhubung via inter-region private backbone latency 65ms, dengan basis data terdistribusi terdistribusi berbasis Raft Consensus (contoh: CockroachDB).

**Skenario Masalah:**
Saat dilakukan implementasi canary deployment untuk microservice transfer valuta asing ke Region-A, skema serialisasi payload biner internal (gRPC Protobuf payload) diubah dari v1 ke v2 (terdapat *breaking change* pada penomoran field byte schema serialization). Akibat partisi jaringan parsial (*intermittent cross-region packet drops*), Region-B gagal menerima sinkronisasi deployment manifest GitOps dan tetap menjalankan versi kode v1.
1. Transaksi antar-wilayah yang dialihkan dari Region-A (v2) ke Region-B (v1) mengalami deserialization error koruptif yang menyebabkan silent state divergence: database mencatat transaksi berhasil pada Region-A, namun status transaksi di Region-B mengalami hang state dan memicu kebocoran balance ledger.
2. Ingress controller tidak mendeteksi 5xx error secara eksplisit karena aplikasi mengembalikan status code `200 OK` dengan payload internal error body.

**Tantangan Eksekusi:**
Rancang arsitektur deployment terkoordinasi (*Cross-Region Deployment Coordinator Framework*) yang memitigasi anomali ini secara komprehensif tanpa mematikan fitur Active-Active. Desain Anda harus mencakup:
1. Skema manajemen versi API berorientasi backward/forward compatibility.
2. Ingress layer 7 routing guardrail yang mampu memvalidasi kompatibilitas payload secara distributed.
3. Mekanisme Automated Cross-Region Synchronization Health Check yang secara otomatis membekukan pipeline rollout di Region-A jika Region-B belum memverifikasi kesiapan schema migration.

Dokumentasikan solusi Anda dalam sebuah whitepaper teknis berformat Markdown (`hands-on/m02/challenge-solution.md`) lengkap dengan diagram arsitektur ASCII dan skema pseudocode validasi layer 7.

---

### 15. Quiz Evaluasi Pemahaman

#### Pertanyaan Basic
1. Apa fungsi mendasar dari syscall `unshare` atau `clone` dalam siklus pembuatan kontainer di kernel Linux?
2. Mengapa direktori hierarki `/sys/fs/cgroup/` pada cgroups v2 menggunakan single unified tree, tidak seperti cgroups v1 yang memisahkan hierarki controller?
3. Sebutkan risiko teknis terbesar dari menjalankan kontainer dengan parameter konfigurasi `--privileged`!
4. Apa perbedaan mendasar antara sinyal kernel `SIGTERM` (sinyal 15) dan `SIGKILL` (sinyal 9) dalam penanganan graceful shutdown sebuah microservice?
5. Mengapa tag image docker berbasis penamaan teks mutable (seperti `:v1.0.0`) tidak memenuhi kualifikasi standar implementasi continuous delivery tingkat enterprise?

#### Pertanyaan Intermediate
6. Bagaimana cara Linux Kernel menangani sebuah proses kontainer yang mencoba menggunakan memori melebihi batas `memory.max` pada cgroup v2 ketika alokasi swap dinonaktifkan?
7. Dalam distributed tracing berbasis spesifikasi W3C TraceContext, data apa saja yang wajib ditransmisikan di dalam format string header `traceparent`?
8. Bagaimana Nginx atau Envoy ingress controller membagi persentase distribusi trafik jaringan secara teknis pada implementasi Canary deployment?
9. Mengapa konfigurasi `readinessProbe` yang bergantung pada pengecekan ketersediaan koneksi database pihak ketiga (*downstream database connection check*) dianggap sebagai arsitektur anti-pattern?
10. Apa yang dimaksud dengan penyerangan supply-chain perangkat lunak berbasis "Dependency Confusion", dan bagaimana cara mengamankan pipeline CI/CD dari risiko tersebut?

#### Skenario Kasus Produksi
11. **Kasus 1**: Sebuah microservice Java Spring Boot di lingkungan produksi tiba-tiba mengalami crash loop dengan status kode terminasi `137`. Namun, log internal file aplikasi tidak mencatat indikasi exception ataupun error stack trace (`OutOfMemoryError`). Sebagai Senior DevOps Engineer, bagaimana metodologi Anda membuktikan secara absolut kepada tim developer bahwa masalah tersebut bersumber dari pembatasan infrastruktur cgroup OOM killer, bukan kesalahan logic internal kode?
12. **Kasus 2**: Tim rilis meluncurkan versi baru sebuah layanan checkout e-commerce menggunakan metode Canary Deployment dengan alokasi trafik 10%. Rata-rata error rate HTTP global tetap berada di angka 0.02% (di bawah batas toleransi trigger rollback sebesar 1%). Namun, tim Business Operations melaporkan bahwa transaksi menggunakan metode pembayaran kartu kredit tertentu mengalami kegagalan 100%. Mengapa metrik global Golden Signals gagal mendeteksi anomali ini, dan bagaimana cara mendesain ulang arsitektur evaluasi metrik untuk mendeteksi anomali tersebut?
13. **Kasus 3**: Sebuah worker node Kubernetes bare-metal dengan spesifikasi tinggi mendadak mengalami penurunan performa secara drastis (*high system latency*). CPU load average mencapai 120, namun metrik utilisasi CPU riil yang ditarik oleh cAdvisor/Prometheus hanya menunjukkan angka pemakaian sebesar 25%. Di saat yang sama, pod-pod yang berada di node tersebut sering terlempar ke status throttling. Di manakah titik kegagalan yang terjadi pada kernel host?

#### Jawaban & Pembahasan Quiz

##### Kunci Jawaban Basic
1. Syscall `clone` (dengan flag isolasi) atau `unshare` berfungsi untuk melepaskan eksekusi thread/proses anak dari referensi konteks eksekusi global sistem operasi host, memprogram kernel untuk menciptakan entri tabel partisi baru untuk resource yang diisolasi (seperti tabel proses baru pada `CLONE_NEWPID` atau routing table baru pada `CLONE_NEWNET`).
2. cgroups v1 menimbulkan *resource racing* dan kompleksitas pelacakan proses karena satu proses dapat berada di hierarki controller memori yang berbeda jalurnya dengan controller CPU. Unified hierarchy pada cgroups v2 menjamin aturan single-writer (proses yang sama diatur oleh satu node cgroup terpadu), menghilangkan konflik alokasi dan mempermudah sinkronisasi I/O writeback cache dengan memori.
3. Parameter `--privileged` melumpuhkan seluruh lapisan pengamanan kernel: memberikan semua Linux Capabilities kepada kontainer, menonaktifkan seccomp filter dan AppArmor/SELinux profil, serta memetakan seluruh file node perangkat fisik (`/dev/`) host langsung ke dalam kontainer. Ini memungkinkan penyerang mengambil alih kontrol kernel host secara instan.
4. `SIGTERM` adalah sinyal software interrupt yang dapat ditangkap (*catchable*), ditangani (*handled*), atau diabaikan oleh aplikasi untuk mengeksekusi prosedur pembersihan sumber daya (menutup socket koneksi, flushing transaction buffer, menyelesaikan request aktif). Sebaliknya, `SIGKILL` langsung ditangani oleh kernel dan tidak dapat diinterupsi oleh proses: kernel akan segera mematikan proses tersebut tanpa membersihkan state aplikasi yang sedang berjalan.
5. Tag teks bersifat dinamis (*mutable pointer*). Jika seorang pengembang menimpa tag `:v1.0.0` dengan commit baru, node Kubernetes yang sudah meng-cache layer lama tidak akan mendownload perubahan tersebut, sementara node baru akan mendownload versi baru. Hal ini merusak determinisme dan auditability sistem (*inconsistent binary parity*).

##### Kunci Jawaban Intermediate
6. Kernel Linux akan memicu mekanisme *page reclamation* secara agresif. Kernel mencoba mengosongkan *page cache* yang bersih (*clean pages*). Jika batas `memory.max` tetap terlampaui dan tidak ada lagi ruang yang dapat direklamasi (karena swap disabled), kernel memanggil `mem_cgroup_out_of_memory()`. OOM-killer kemudian memilih proses dengan nilai `oom_score` tertinggi di cgroup tersebut dan mengirimkan sinyal `SIGKILL` (`kill -9`) secara paksa.
7. Format W3C `traceparent` terdiri dari 4 field dipisahkan tanda strip (`-`):
   * Version (2 hex characters, saat ini `00`).
   * Trace ID (32 hex characters / 16 bytes unique identity).
   * Parent ID / Span ID (16 hex characters / 8 bytes).
   * Trace Flags (8-bit field, contoh: `01` menandakan trace di-sample untuk disimpan).
8. Ingress Layer 7 menerapkan routing probabilistik pada tingkat proxy:
   * Menggunakan modul random weighted hash upstream (seperti Lua scripting atau Nginx `split_clients`), proxy mencocokkan hash request (berdasarkan IP klien, Cookie sesi, atau UUID internal) dengan rentang probabilitas yang ditentukan (misal hash modulo 100 < 10 dialihkan ke upstream Canary).
   * Alternatifnya, proxy membaca spesifikasi weighted dynamic routing yang mengalokasikan persentase koneksi pooling secara proporsional.
9. Karena memicu efek kegagalan berantai (*cascading failure*). Jika database mengalami penurunan performa temporal, seluruh pod aplikasi akan serentak mendeklarasikan status `Unready`. Akibatnya, ingress mencabut seluruh pod dari load balancer pool, mematikan seluruh jalur akses aplikasi dan membuat sistem sama sekali tidak dapat memulihkan diri (*self-healing dead-lock*).
10. *Dependency Confusion* terjadi ketika penyerang mendaftarkan nama paket yang sama dengan pustaka internal privat perusahaan di repositori publik (misal npmjs, PyPI) dengan nomor versi yang jauh lebih tinggi (misal `v99.0.0`). Jika pipeline CI/CD tidak mengonfigurasi scoped namespace atau repository priority routing secara ketat, worker CI akan mengunduh paket berbahaya dari repositori publik. Mitigasi: Daftarkan private enterprise scope internal dan validasi cryptographic integrity checksum menggunakan *lockfiles*.

##### Kunci Jawaban Skenario Kasus Produksi
11. **Metodologi Diagnostik Skenario 1**:
    * Kode terminasi `137` berasal dari rumus POSIX: $128 + \text{Signal Number}$. Sinyal 9 (`SIGKILL`) menghasilkan $128 + 9 = 137$. JVM mati seketika tanpa sempat menangkap exception handling.
    * Eksekusi perintah `dmesg -T` pada node host yang mengeksekusi pod bersangkutan. Cari pesan spesifik: `Memory cgroup out of memory: Killed process`.
    * Periksa metrik native cgroup v2 pada host: `cat /sys/fs/cgroup/.../memory.events`. Jika atribut `oom_kill` bernilai $> 0$, hal tersebut membuktikan secara mutlak bahwa kernel yang menghentikan proses Java tersebut karena alokasi memori fisik melampaui deklarasi limit konfigurasi cgroup, bukan bug internal logika JVM.
12. **Mitigasi Metrik Skenario 2**:
    * Kegagalan terjadi akibat penggunaan *global aggregates metrics masking*. Mengukur persentase error secara makro menyamarkan anomali pada segmen bisnis bervolume rendah (metode kartu kredit mungkin hanya menyumbang 0.05% dari total volume keseluruhan transaksi).
    * Evaluasi canary wajib dipecah menjadi *Dimensional Metric Thresholds*: Ingress dan aplikasi harus mengekspos metrik terdistribusi yang menyertakan label dimensi konteks (`payment_method="credit_card"`).
    * Konfigurasi Canary Analysis Engine (seperti Argo Rollouts Analysis) wajib memvalidasi metrik dengan tingkat granularitas multi-dimensi:
      `sum(rate(payment_failure{payment_method="credit_card"}[1m])) / sum(rate(payment_total{payment_method="credit_card"}[1m])) > 0.01`
13. **Analisis Akar Masalah Skenario 3**:
    * Kondisi di mana CPU load average tinggi namun utilisasi CPU rendah mengindikasikan adanya antrean besar proses dalam status **Uninterruptible Sleep (`D` state)** pada tabel proses kernel.
    * Status `D` biasanya disebabkan oleh proses yang terhambat (*blocked*) pada pemanggilan I/O hardware (disk I/O saturation, network NFS hang) atau kegagalan pertukaran mutex lock di kernel space.
    * CPU CFS Throttling dapat terpicu secara artifisial jika parameter `cpu.cfs_quota_us` disetel terlalu ketat pada aplikasi multi-threaded, di mana thread pool Java/Go menggunakan kuota time slice microsecond secara serentak dalam rentang periode kecil, menyebabkan aplikasi dipaksa tidur (*throttled*) hingga window berikutnya terbuka.
    * Untuk mendiagnosis, jalankan perintah:
      `cat /proc/loadavg` dan gunakan `vmstat 1` untuk memeriksa kolom `b` (blocked processes). Gunakan `bpftrace` untuk mengidentifikasi fungsi kernel yang memicu latency tinggi:
      `bpftrace -e 'profile:hz:99 { @[kstack] = count(); }'`

---

### 16. Summary

Fondasi arsitektur DevOps kelas enterprise tidak bertumpu semata pada otomasi script deployment, melainkan pada pemahaman mendalam atas batas sistem dan primitives yang mengeksekusinya:
1. **Container Abstraction**: Kontainer bukanlah hardware virtual, melainkan proses biasa yang diisolasi oleh kombinasi *Linux Namespaces* (pembatasan visibilitas) dan *cgroups v2* (pembatasan konsumsi sumber daya), dikunci menggunakan *Capabilities* dan *Seccomp profiles*.
2. **Deterministic Delivery**: Sistem Continuous Delivery modern mengadopsi model *Immutability* dan *Progressive Delivery*. Deployment dilakukan secara deklaratif (GitOps), diverifikasi bertahap (Canary Rollouts), dan dikendalikan otomatis menggunakan analisis telemetri kuantitatif.
3. **Shift-Left Security & Resiliency**: Integritas supply chain dibangun langsung pada pipeline melalui penandatanganan kriptografis, verifikasi SBOM, serta penghapusan celah privilese sistem operasi secara sistemik (non-root execution, read-only root filesystems). Pemahaman ini menjadi modal penting untuk mengelola sistem komputasi terdistribusi dalam skala enterprise.