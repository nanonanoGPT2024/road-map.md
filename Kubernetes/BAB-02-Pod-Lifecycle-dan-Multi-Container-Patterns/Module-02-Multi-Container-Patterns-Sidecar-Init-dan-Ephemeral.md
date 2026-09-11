# Module 02: Multi-Container Patterns: Sidecar, Init Container, Ambassador, Adapter, dan Ephemeral Containers

---
[⬅️ Module 01: Anatomi Pod & Probes](./Module-01-Anatomi-Pod-Lifecycle-Probes-dan-Termination.md) | [📋 Silabus Induk](../README.md) | [Evaluasi & Quiz BAB 02 ➡️](./BAB-02-Quiz-dan-Challenge.md)
---

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
1. Mengidentifikasi kapan dan mengapa arsitektur multi-kontainer di dalam satu Pod dibutuhkan.
2. Menguasai siklus hidup **Init Containers**: eksekusi sekuensial, blocking behavior, dan penanganan kegagalan inisialisasi.
3. Menerapkan pola desain klasik Kubernetes: **Sidecar Pattern**, **Ambassador Pattern**, dan **Adapter Pattern**.
4. Memahami fitur modern **Native Sidecar Containers** (Kubernetes v1.28+ / GA v1.29) menggunakan `initContainers` dengan `restartPolicy: Always`.
5. Melakukan live debugging pada Pod produksi berbasis image minimal/distroless menggunakan **Ephemeral Containers** via `kubectl debug`.

---

## 2. Prerequisite
- Memahami konsep dasar Pod dan shared namespace ([Module 01 BAB 02](Module-01-Anatomi-Pod-Lifecycle-Probes-dan-Termination.md)).
- Memahami konsep Distroless dan container tanpa shell ([Docker BAB 03](../../Docker/BAB-03-Dockerfile-Engineering-dan-Image-Optimization/)).
- Pemahaman Linux IPC (Inter-Process Communication) dan loopback networking (`127.0.0.1`).

---

## 3. Concept
Dalam ekosistem Kubernetes, memaksakan seluruh tanggung jawab ke dalam satu kontainer monolitik melanggar prinsip *Single Responsibility*. 

Pola **Multi-Container Pod** menggabungkan dua atau lebih kontainer yang bekerja sama secara erat di dalam satu Pod. Karena seluruh kontainer di dalam Pod berbagi:
- Alamat IP yang sama (`localhost`).
- Linux IPC Namespace.
- Volume penyimpanan lokal (`emptyDir`).

Kita dapat memisahkan proses aplikasi inti dari proses penunjang operasional (seperti log forwarding, proxy lalu lintas, validasi dependensi, dan normalisasi metrik).

---

## 4. Why?
1. **Pemisahan Kepedulian (Separation of Concerns)**: Tim pengembang aplikasi fokus menulis logika bisnis (Node.js/Go/Python), sementara tim platform/DevOps menyediakan kontainer penunjang standar (Fluent Bit, Vault Agent, Envoy).
2. **Modularitas & Reusabilitas**: Kontainer sidecar yang sama (misal kontainer rotasi sertifikat TLS) dapat dipasangkan ke ratusan microservices berbeda tanpa perlu mengubah kode sumber aplikasi.
3. **Penyelamatan Pod Minimal (Zero-Footprint Debugging)**: Kontainer produksi yang dikeraskan (*hardened distroless*) tidak memiliki `bash`, `curl`, atau `sh`. **Ephemeral Containers** memungkinkan kita memasang shell interaktif sementara ke Pod yang sedang berjalan tanpa perlu mematikan atau men-deploy ulang Pod tersebut.

---

## 5. What?
### Spektrum Pola Multi-Container Kubernetes:

| Pola | Deskripsi | Perilaku Siklus Hidup | Use Case Utama |
|---|---|---|---|
| **Init Container** | Kontainer inisialisasi yang berjalan sekuensial sebelum kontainer aplikasi dinyalakan. Wajib exit 0. | Menghalangi (*blocking*) kontainer aplikasi hingga selesai sukses. | Migrasi skema database, setup izin file `chown`, menunggu service upstream siap. |
| **Sidecar Container** | Kontainer pendamping yang berjalan simultan bersama kontainer aplikasi utama sepanjang hidup Pod. | Hidup bersama dan mati bersama kontainer aplikasi. | Log forwarding (Promtail), auto-sync konfigurasi Git (git-sync), secret injection (Vault Agent). |
| **Native Sidecar** (K8s 1.28+) | Init container spesial dengan `restartPolicy: Always`. | Start sebelum kontainer app, tetap hidup, dan mati setelah kontainer app selesai. | Service Mesh Proxy (Istio/Linkerd) dan job batch batch processing. |
| **Ambassador** | Kontainer proxy lokal yang menyederhanakan akses ke dunia luar. | Hidup bersama kontainer aplikasi. | Kontainer aplikasi menghubungi `localhost:6379`, ambassador merutekan traffic ke Redis cluster terdistribusi di luar. |
| **Adapter** | Kontainer yang menstandarisasi output atau metrik aplikasi heterogen ke satu format seragam. | Hidup bersama kontainer aplikasi. | Mengubah format metrik non-standar aplikasi legacy menjadi format `/metrics` Prometheus. |
| **Ephemeral Container** | Kontainer sementara yang disuntikkan ke Pod aktif untuk investigasi runtime. | Dibuat dinamis via API `pods/ephemeralcontainers`, tidak ada restart. | Troubleshooting & troubleshooting container distroless produksi. |

---

## 6. How? Alur Eksekusi Init Containers & Native Sidecars

```text
[ Pod Dibuat di Node ]
          |
          v
  +-------------------------------------------------------------+
  |                   Fase 1: Init Containers                   |
  |  1. init-db-migrate  -> RUNNING -> SUCCESS (Exit Code 0)    |
  |  2. init-download-cfg -> RUNNING -> SUCCESS (Exit Code 0)   |
  +-------------------------------------------------------------+
          |
          v (Jika K8s 1.28+ Native Sidecar aktif)
  +-------------------------------------------------------------+
  |              Fase 2: Native Sidecar Initialization          |
  |  vault-agent (initContainer + restartPolicy: Always)        |
  |  -> Menyala & men-download token rahasia ke shared volume   |
  |  -> Tetap hidup di background                               |
  +-------------------------------------------------------------+
          |
          v
  +-------------------------------------------------------------+
  |             Fase 3: Application Containers Start            |
  |  +---------------------------+ +--------------------------+ |
  |  | Main App (Port 8080)      | | Classic Sidecar (Fluent) | |
  |  | Membaca config dari /data | | Membaca /var/log/app.log | |
  |  +---------------------------+ +--------------------------+ |
  +-------------------------------------------------------------+
```

---

## 7. Analogy
Bayangkan Pod seperti sebuah kru pesawat tempur:
- **Init Container** adalah teknisi darat sebelum lepas landas. Mereka mengisi bahan bakar, memeriksa roda pendaratan, dan memastikan radar siap. Pesawat tidak akan diizinkan lepas landas sebelum teknisi menyelesaikan checklist dengan sempurna.
- **Kontainer Aplikasi Utama** adalah pilot pesawat yang mengemudikan misi utama.
- **Sidecar (Ambassador / Adapter)** adalah navigator dan co-pilot yang duduk di kokpit yang sama. Mereka menangani radio komunikasi terenkripsi (Ambassador) dan mencatat kotak hitam penerbangan (Sidecar logging).
- **Ephemeral Container** adalah teknisi darurat yang diterjunkan dari helikopter ke atas pesawat yang sedang terbang untuk memeriksa kerusakan mesin tanpa membatalkan misi penerbangan!

---

## 8. Diagram: Pola Adapter vs Ambassador

```text
Pola Ambassador (Proxy Outbound):
[ App Container ] ---> kirim query ke: localhost:6379
                               |
                               v
                       [ Ambassador Proxy ] ---> Enkripsi mTLS & Routing
                                                       |
                                                       v
                                            [ Remote Redis Shards ]

Pola Adapter (Normalisasi Inbound/Monitoring):
[ Prometheus Server ] ---> Scrape: localhost:9100/metrics
                                       |
                                       v
                                [ Adapter Container ]
                                (JMX / Custom Exporter)
                                       |
                                       v (Parsing metrik internal)
                               [ Legacy Enterprise App ]
```

---

## 9. Simple Example: Init Container Menunggu Database Siap

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: web-with-init
spec:
  # Volume lokal bersama antar kontainer
  volumes:
  - name: shared-data
    emptyDir: {}

  initContainers:
  # Init Container 1: Tunggu sampai port PostgreSQL terbuka
  - name: wait-for-postgres
    image: busybox:1.36
    command: ['sh', '-c', 'until nc -z -v -w3 postgres-svc 5432; do echo "Menunggu DB..."; sleep 2; done;']

  # Init Container 2: Download file konfigurasi ke volume bersama
  - name: fetch-config
    image: busybox:1.36
    command: ['sh', '-c', 'echo "FEATURE_FLAG_ENABLED=true" > /config/app.conf']
    volumeMounts:
    - name: shared-data
      mountPath: /config

  containers:
  # Kontainer Aplikasi Utama
  - name: web-app
    image: nginx:alpine
    volumeMounts:
    - name: shared-data
      mountPath: /etc/app-config
```

---

## 10. Practical Example: Native Sidecar Container (Kubernetes 1.28+)
Di Kubernetes 1.28+, kita dapat mendeklarasikan Sidecar di dalam `initContainers` dengan menyematkan `restartPolicy: Always`. 
Hal ini memecahkan problem klasik: **"Sidecar harus siap sebelum kontainer utama start, dan mati otomatis saat Job selesai"**:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: batch-job-with-sidecar
spec:
  volumes:
  - name: shared-vault-token
    emptyDir: {}

  initContainers:
  # Native Sidecar: Berjalan seperti init container (start duluan),
  # tetapi tidak memblokir dan TETAP HIDUP di background!
  - name: vault-agent-sidecar
    image: hashicorp/vault:1.15.2
    restartPolicy: Always # <--- KUNCI NATIVE SIDECAR!
    args: ["agent", "-config=/etc/vault/vault-agent.hcl"]
    volumeMounts:
    - name: shared-vault-token
      mountPath: /vault/secrets

  containers:
  - name: worker
    image: python:3.11-slim
    command: ["python", "-c", "import time; print('Membaca secret dari vault...'); time.sleep(10); print('Job Selesai!')"]
    volumeMounts:
    - name: shared-vault-token
      mountPath: /vault/secrets
```

---

## 11. Real World Example: Live Debugging Distroless via Ephemeral Containers
Bayangkan Pod backend produksi Anda yang menggunakan base image `distroless` (tanpa shell dan utilitas debug) mengalami lonjakan latensi ke database eksternal:

```bash
# 1. Cek status pod produksi
kubectl get pods -n production
# Output: payment-api-68f49b954c-88xtr   1/1   Running

# 2. Mencoba kubectl exec GAGAL karena distroless tidak punya /bin/sh:
kubectl exec -it payment-api-68f49b954c-88xtr -c api -- /bin/sh
# Error: OCI runtime exec failed: exec: "/bin/sh": stat /bin/sh: no such file or directory

# 3. SOLUSI ELEGAN: Suntikkan Ephemeral Debug Container dengan network sharing ke Pod aktif!
kubectl debug -it payment-api-68f49b954c-88xtr \
  --image=nicolaka/netshoot \
  --target=api \
  --container=debug-toolbox

# 4. Sekarang Anda berada di shell netshoot di dalam network namespace yang sama persis dengan aplikasi!
# Anda bisa menjalankan tcpdump, curl, dig, netstat, dan strace:
dig postgres.internal.corp
tcpdump -i eth0 port 5432 -nn
```

---

## 12. Trade-offs: Multi-Container vs Single Container

| Aspek | Single Container Pod | Multi-Container Pod (Sidecar) |
|---|---|---|
| **Kompleksitas Desain** | Sangat Sederhana | Lebih Kompleks (Sinkronisasi restart, lifecycle) |
| **Resource Overhead** | Minimal (1 container footprint) | Tambahan RAM/CPU untuk masing-masing container |
| **Separation of Concerns** | Buruk (Logika app bercampur dengan log forwarding) | Sangat Baik (Tugas terisolasi jelas) |
| **Blast Radius Kegagalan** | Jika kontainer crash, Pod langsung restart | Jika sidecar crash, kontainer aplikasi bisa ikut terganggu |

---

## 13. When To Use
- Gunakan **Init Containers** saat Anda perlu:
  - Menjalankan migrasi database (`prisma migrate`, `alembic upgrade`) sebelum aplikasi menyala.
  - Mempersiapkan permission direktori storage (`chmod -R 777 /data` via busybox).
- Gunakan **Sidecar Pattern** untuk streaming log, dynamic config reloader, dan proxy service mesh.
- Gunakan **Ephemeral Containers** untuk investigasi forensik pada container minimal di production.

---

## 14. When NOT To Use
- Jangan satukan dua aplikasi bisnis yang independen (misal: Service Auth dan Service Checkout) di dalam satu Pod multi-kontainer hanya karena mereka sering berkomunikasi. Pisahkan mereka ke dalam Pod masing-masing agar bisa di-scale secara terpisah!
- Jangan menjalankan tugas yang memakan waktu berjam-jam di dalam Init Container karena akan menunda kesiapan Pod.

---

## 15. Common Mistakes
1. **Init Container Mengalami Error Berulang**: Jika init container exit dengan kode non-nol (`exit 1`), Pod akan terjebak di status `Init:CrashLoopBackOff` dan kontainer aplikasi utama TIDAK AKAN PERNAH dimulai.
2. **Kekurangan Resource Limit Total**: Total permintaan CPU/RAM Pod adalah nilai tertinggi dari init container DITAMBAH jumlah seluruh kontainer aplikasi. Mengabaikan ini bisa membuat Pod gagal di-schedule (*Insufficient memory*).
3. **Problem Job Tidak Pernah Selesai pada Sidecar Lawas**: Sebelum K8s 1.28, kontainer sidecar logging (seperti Fluent Bit) tidak tahu kapan kontainer utama selesai, sehingga Kubernetes Job tidak pernah masuk status `Completed`. Gunakan **Native Sidecar** (`restartPolicy: Always` di `initContainers`) untuk mengatasi ini!

---

## 16. Best Practices
### Must Have
- Pastikan Init Container bersifat **Idempoten** (aman dijalankan berulang kali jika Kubelet me-restart Pod).
- Gunakan shared volume `emptyDir` dengan batasan ukuran (`medium: Memory, sizeLimit: 64Mi`) untuk pertukaran data ephemeral berlatensi rendah antar kontainer di dalam Pod.

### Recommended
- Berikan resource `limits` dan `requests` secara eksplisit pada masing-masing kontainer penunjang (sidecar) agar tidak mencuri alokasi resource kontainer aplikasi utama.
- Adopsi fitur Native Sidecar (`restartPolicy: Always`) untuk seluruh implementasi sidecar di Kubernetes 1.29+.

### Advanced
- Konfigurasikan Process Namespace Sharing (`shareProcessNamespace: true`) di PodSpec jika sidecar perlu mengirim sinyal POSIX langsung ke PID kontainer aplikasi (misal `nginx -s reload`).

---

## 17. Troubleshooting Guide
### Problem 1: Pod stuck pada status `Init:0/2`
- **Penyebab**: Salah satu Init Container gagal atau masih menunggu dependensi.
- **Diagnosa**:
  ```bash
  kubectl describe pod <nama-pod>
  # Periksa Init Containers: State & Reason
  kubectl logs <nama-pod> -c <nama-init-container>
  ```
- **Solusi**: Perbaiki kesalahan pada script inisialisasi atau pastikan service yang ditunggu sudah aktif.

### Problem 2: Ephemeral container gagal di-attach
- **Penyebab**: Fitur `EphemeralContainers` dinonaktifkan di kluster lawas, atau izin RBAC akun Anda tidak memiliki akses ke sub-resource `pods/ephemeralcontainers`.
- **Solusi**: Verifikasi versi Kubernetes ($\ge 1.25$ fitur sudah GA) dan pastikan ClusterRole Anda memiliki verb `update` pada resource `pods/ephemeralcontainers`.

---

## 18. Exercises
### Level: Easy
1. Buat Pod dengan satu Init Container `busybox` yang membuat file `/work-dir/ready.txt` di shared volume `emptyDir`.
2. Pasang kontainer utama `nginx` yang me-mount volume tersebut dan verifikasi isi file via `kubectl exec`.

### Level: Medium
1. Buat Pod dengan pola Sidecar:
   - Kontainer Utama: Menghasilkan log setiap 2 detik ke `/var/log/app.log`.
   - Kontainer Sidecar: Menjalankan `tail -f /var/log/app.log` dan mencetak log ke standard output.
2. Verifikasi output log sidecar menggunakan `kubectl logs <pod-name> -c sidecar`.

### Level: Hard
1. Jalankan Pod berbasis image scratch atau distroless tanpa shell.
2. Gunakan perintah `kubectl debug` untuk menyuntikkan Ephemeral Container dengan target process sharing ke Pod tersebut.
3. Lakukan inspeksi proses kontainer utama dari dalam shell ephemeral container.

---

## 19. Challenge
Rancang arsitektur Pod untuk aplikasi monolitik migrasi enterprise:
- Aplikasi utama membutuhkan runtime konfigurasi yang didekripsi secara real-time dari HashiCorp Vault.
- Logging aplikasi format teks lokal harus diubah menjadi JSON terstruktur sebelum dikirim ke remote Kafka broker.
- Tuliskan manifest Pod lengkap yang menggabungkan Init Container (auth bootstrap), Native Sidecar (Vault token refresh), Main App, dan Sidecar Adapter (Log shipper) menggunakan shared in-memory volume.

---

## 20. Summary
- Pola **Multi-Container** memanfaatkan namespace bersama (Network, IPC, Storage) di dalam satu Pod untuk mencapai *Separation of Concerns*.
- **Init Containers** mengeksekusi tugas inisialisasi secara sekuensial dan blocking sebelum kontainer utama start.
- **Native Sidecars** (`restartPolicy: Always` di initContainers) menyelesaikan siklus hidup sidecar pada Job/Batch workloads.
- **Ambassador** bertindak sebagai proxy outbound, sedangkan **Adapter** bertindak sebagai normalizer inbound/metrik.
- **Ephemeral Containers** memungkinkan live debugging interaktif pada Pod produksi minimal tanpa downtime.

---
[⬅️ Module 01: Anatomi Pod & Probes](./Module-01-Anatomi-Pod-Lifecycle-Probes-dan-Termination.md) | [📋 Silabus Induk](../README.md) | [Evaluasi & Quiz BAB 02 ➡️](./BAB-02-Quiz-dan-Challenge.md)
---
