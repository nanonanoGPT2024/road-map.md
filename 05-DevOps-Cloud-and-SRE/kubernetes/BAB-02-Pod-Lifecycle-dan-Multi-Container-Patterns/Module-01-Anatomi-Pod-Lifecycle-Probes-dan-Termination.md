# Module 01: Anatomi Pod, Pod Phase, Probes (Startup, Liveness, Readiness), dan Graceful Termination

---
[⬅️ Evaluasi & Quiz BAB 01](../BAB-01-Arsitektur-Internal-dan-Control-Plane/BAB-01-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Multi-Container Patterns ➡️](./Module-02-Multi-Container-Patterns-Sidecar-Init-dan-Ephemeral.md)
---

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
1. Memahami mengapa Kubernetes menggunakan abstraksi **Pod** alih-alih mengeksekusi kontainer secara langsung.
2. Menganalisis transisi status Pod: **Pod Phases** (`Pending`, `Running`, `Succeeded`, `Failed`, `Unknown`) dan **Pod Conditions** (`PodScheduled`, `Initialized`, `ContainersReady`, `Ready`).
3. Menguasai tiga mekanisme pemeriksaan kesehatan kontainer (**Health Probes**): `startupProbe`, `livenessProbe`, dan `readinessProbe` beserta parameter tuning-nya (`initialDelaySeconds`, `periodSeconds`, `failureThreshold`).
4. Membedakan mekanisme probe: `httpGet`, `tcpSocket`, `exec`, dan `grpc`.
5. Menerapkan alur penghentian aplikasi yang aman (**Graceful Termination**) menggunakan sinyal `SIGTERM`, `preStop` lifecycle hooks, dan `terminationGracePeriodSeconds` untuk mencegah kehilangan koneksi transaksi (*zero connection drop*).

---

## 2. Prerequisite
- Memahami konsep dasar Linux process signals (`SIGTERM` 15, `SIGKILL` 9) dan Container Lifecycle ([Docker BAB 02](../../Docker/BAB-02-Container-Lifecycle-dan-CLI-Mastery/)).
- Memahami peran Kubelet dan PLEG di Worker Node ([Kubernetes BAB 01 Module 02](../BAB-01-Arsitektur-Internal-dan-Control-Plane/Module-02-Arsitektur-Worker-Node-kubelet-kube-proxy-CRI.md)).

---

## 3. Concept
Sebuah **Pod** adalah unit terkecil dan paling mendasar dari komputasi yang dapat dideploy di dalam Kubernetes. Sebuah Pod mewakili satu atau beberapa kontainer yang beroperasi secara kohesif (co-located, co-scheduled) di satu host worker node yang sama.

Mengapa Kubernetes tidak langsung mengelola kontainer individu?
Di dunia nyata, aplikasi sering kali membutuhkan proses pendukung yang terikat erat (tightly coupled), seperti:
- Kontainer utama (Node.js API).
- Kontainer log shipper (Fluent Bit membaca log lokal).
- Kontainer proxy enkripsi (Envoy sidecar untuk mTLS).

Di dalam sebuah Pod, semua kontainer berbagi:
1. **Satu Network Namespace**: Memiliki satu Pod IP yang sama. Kontainer di dalam Pod yang sama dapat saling menyapa via `localhost` dengan nomor port berbeda.
2. **IPC Namespace**: Dapat berbagi shared memory / UNIX domain sockets.
3. **Penyimpanan Bersama (Shared Volumes)**: Dapat me-mount volume direktori yang sama secara simultan.

---

## 4. Why?
1. **Eliminasi Downtime saat Rolling Update**: Tanpa `readinessProbe`, Kubernetes akan langsung mengirimkan traffic pengguna ke kontainer yang baru dibuat padahal aplikasi backend masih melakukan bootstrapping koneksi database, memicu error HTTP `502 Bad Gateway`.
2. **Self-Healing Otomatis**: Jika aplikasi mengalami deadlock di memori (thread hang tanpa crash), `livenessProbe` mendeteksinya dan secara otomatis me-restart kontainer.
3. **Mencegah Data Korupsi saat Scaling Down**: Memahami Graceful Termination memastikan worker menyelesaikan transaksi database yang sedang berlangsung sebelum proses dimatikan paksa.

---

## 5. What?
### Tiga Serangkai Health Probes:

| Tipe Probe | Kapan Dijalankan? | Apa Tindakan jika GAGAL? | Use Case Utama |
|---|---|---|---|
| **`startupProbe`** | Hanya saat inisialisasi awal kontainer. Menunda probe lain hingga sukses. | Kontainer dimatikan dan di-restart sesuai `restartPolicy`. | Aplikasi legacy yang lambat start (cth: Java/Spring Boot yang butuh 60-120 detik inisialisasi). |
| **`livenessProbe`** | Secara periodik sepanjang hidup kontainer (setelah startup lolos). | Kontainer dianggap mati (deadlock) dan di-**RESTART** paksa. | Memulihkan aplikasi yang macet/deadlock tanpa intervensi manusia. |
| **`readinessProbe`** | Secara periodik sepanjang hidup kontainer. | Pod IP **DICABUT** dari Service Endpoints (traffic berhenti dikirim). Kontainer **TIDAK** di-restart! | Melindungi aplikasi saat sedang kelebihan beban (overload) atau saat koneksi database sempat terputus. |

---

## 6. How? Alur Siklus Hidup dan Graceful Termination

```text
[ Perintah Hapus: kubectl delete pod my-pod ]
                      |
                      +---------------------------------------+
                      |                                       |
                      v                                       v
    [ 1. Update Service Endpoints ]         [ 2. Kubelet Execution di Node ]
    Pod IP segera dihapus dari Endpoints                 |
    Traffic baru berhenti diarahkan ke Pod               v
                                            [ Menjalankan 'preStop' Hook ]
                                            (cth: sleep 5 atau drain connections)
                                                         |
                                                         v
                                            [ Mengirim Sinyal SIGTERM (PID 1) ]
                                            Aplikasi berhenti menerima request baru,
                                            menyelesaikan request yang sedang berjalan
                                                         |
                                                         +--------+
                                                         |        |
                                       (Aplikasi selesai |        | (Aplikasi belum selesai
                                        dalam batas waktu)        |  setelah grace period)
                                                         v        v
                                        [ Exit Code 0 ]   [ Kubelet kirim SIGKILL ]
                                        (Shutdown Bersih) (Paksa mati - Code 137)
                                                         \        /
                                                          v      v
                                             [ Pod Namespace Dihapus ]
```

---

## 7. Analogy
Bayangkan Pod seperti sebuah mobil:
- **`startupProbe`** adalah memutar kunci kontak dan memanaskan mesin mobil di pagi hari. Anda tidak akan langsung menginjak gas sebelum jarum temperatur mesin siap.
- **`livenessProbe`** adalah detektor detak jantung pengemudi. Jika pengemudi pingsan/serangan jantung di tengah jalan (deadlock), sistem darurat mobil otomatis mematikan mesin dan menyalakan alarm restart.
- **`readinessProbe`** adalah lampu taksi di atap mobil. Jika taksi sudah penuh penumpang (overload), lampu indikator dimatikan sehingga calon penumpang baru di jalan tidak akan mencegat taksi ini, tetapi mesin mobil tetap hidup.
- **Graceful Termination** adalah menyalakan lampu sein, menepi ke bahu jalan secara perlahan, menurunkan penumpang dengan selamat, baru kemudian mematikan mesin. Bukan menabrakkan mobil ke pohon secara mendadak (`SIGKILL`).

---

## 8. Diagram: State Machine Pod Phase & Containers

```text
+-------------------------------------------------------------------------+
| Pod Phase: PENDING                                                      |
| -> Kube-apiserver menyimpan manifest, Scheduler mencari node.           |
| -> Kubelet mendownload image, alokasi CNI network.                      |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
| Pod Phase: RUNNING                                                      |
|   +------------------------------------------------------------------+  |
|   | Container State: WAITING -> RUNNING                              |  |
|   | 1. startupProbe: PASS                                            |  |
|   | 2. readinessProbe: PASS -> Pod Condition: "Ready=True"           |  |
|   |    (Traffic Service mulai masuk)                                 |  |
|   | 3. livenessProbe: Rutin memantau kesehatan internal              |  |
|   +------------------------------------------------------------------+  |
+-------------------------------------------------------------------------+
                    /                                    \
                   / (Job selesai normal)                 \ (Error fatal tak tertangani)
                  v                                        v
+-------------------------------+        +--------------------------------+
| Pod Phase: SUCCEEDED          |        | Pod Phase: FAILED              |
| Seluruh container exit code 0 |        | Container exit != 0            |
+-------------------------------+        +--------------------------------+
```

---

## 9. Simple Example: Konfigurasi Probes di PodSpec

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: payment-api
  labels:
    app: payment
spec:
  containers:
  - name: api
    image: myregistry/payment-api:v1.2.0
    ports:
    - containerPort: 8080

    # 1. Startup Probe: Mentoleransi aplikasi lambat hingga 60 detik (30 x 2s)
    startupProbe:
      httpGet:
        path: /healthz/startup
        port: 8080
      failureThreshold: 30
      periodSeconds: 2

    # 2. Liveness Probe: Cek apakah deadlock
    livenessProbe:
      httpGet:
        path: /healthz/liveness
        port: 8080
      periodSeconds: 10
      timeoutSeconds: 3
      failureThreshold: 3

    # 3. Readiness Probe: Cek apakah siap melayani traffic HTTP
    readinessProbe:
      httpGet:
        path: /healthz/ready
        port: 8080
      periodSeconds: 5
      timeoutSeconds: 2
      failureThreshold: 2
```

---

## 10. Practical Example: Implementasi Graceful Termination Tanpa Connection Drop

File `pod-graceful.yaml`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: zero-downtime-api
spec:
  # Beri waktu hingga 45 detik untuk membersihkan koneksi
  terminationGracePeriodSeconds: 45
  containers:
  - name: web
    image: myorg/web-service:v2.0.0
    ports:
    - containerPort: 3000
    lifecycle:
      preStop:
        exec:
          # Trik Industri: Beri jeda 5 detik agar kube-proxy dan Ingress
          # sempat mencabut IP Pod ini dari routing table sebelum proses utama dimatikan!
          command: ["/bin/sh", "-c", "sleep 5"]
```

### Handler Sinyal di Kode Aplikasi (Node.js / Express):
```javascript
const server = app.listen(3000);

process.on('SIGTERM', () => {
  console.log('[SHUTDOWN] Menerima sinyal SIGTERM. Menolak koneksi baru...');
  
  // Berhenti menerima request HTTP baru
  server.close(() => {
    console.log('[SHUTDOWN] Seluruh request aktif selesai diproses. Menutup koneksi database...');
    dbPool.end().then(() => {
      console.log('[SHUTDOWN] Database tertutup. Keluar secara bersih (Exit 0).');
      process.exit(0);
    });
  });

  // Fallback pengaman jika ada request yang hang
  setTimeout(() => {
    console.error('[SHUTDOWN] Timeout 30s terlampaui. Keluar paksa (Exit 1).');
    process.exit(1);
  }, 30000);
});
```

---

## 11. Real World Example: Flapping Pods Akibat Salah Konfigurasi Liveness Probe
Sebuah aplikasi e-commerce menargetkan endpoint `/health` untuk `livenessProbe`. 
Di dalam endpoint `/health`, developer mengecek ketersediaan database PostgreSQL eksternal:
```javascript
// ANTI-PATTERN FATAL DI LIVENESS PROBE:
app.get('/health', async (req, res) => {
  const dbOk = await checkDatabaseConnection();
  if (!dbOk) return res.status(500).send("DB Down"); // SALAH!
  res.send("OK");
});
```
- **Bencana yang Terjadi**: Ketika database PostgreSQL mengalami spike query dan lambat merespons selama 30 detik, 50 Pod API di Kubernetes serempak gagal liveness probe. Kubernetes langsung me-restart seluruh 50 Pod secara bersamaan!
- Saat ke-50 Pod hidup kembali, mereka serempak mencoba menginisialisasi 50 koneksi connection-pool baru ke PostgreSQL, membuat PostgreSQL yang sedang megap-megap langsung crash total!
- **Solusi**: 
  - `livenessProbe` HANYA boleh mengecek kesehatan internal proses aplikasi itu sendiri (apakah event-loop jalan?).
  - Pemeriksaan dependensi eksternal (Database/Redis) HANYA diletakkan di `readinessProbe` agar Pod hanya berhenti menerima traffic, bukan di-restart!

---

## 12. Trade-offs: Mekanisme Probes

| Mekanisme | Kelebihan | Kekurangan | Rekomendasi |
|---|---|---|---|
| `httpGet` | Sangat umum, mendukung status code (200-399 = OK), mudah diinspeksi. | Membutuhkan HTTP server aktif di dalam kontainer. | Sangat Disarankan untuk Web API / Microservices. |
| `tcpSocket` | Sangat cepat, bisa digunakan untuk service non-HTTP (DB, Cache, Queue). | Hanya mengecek apakah port terbuka, tidak menjamin aplikasi siap memproses query. | Cocok untuk Database & Message Brokers. |
| `exec` | Sangat fleksibel (menjalankan script shell/biner). | Membuka proses baru (`fork/exec`) setiap beberapa detik, memakan CPU tinggi jika periodenya rapat. | Gunakan hanya jika tidak ada port TCP/HTTP. |
| `grpc` | Native gRPC health checking protocol standard (RFC). | Membutuhkan implementasi gRPC Health service di aplikasi. | Sangat disarankan untuk internal gRPC microservices. |

---

## 13. When To Use
- Selalu kombinasikan **`startupProbe`** dan **`livenessProbe`** jika aplikasi Anda membutuhkan waktu bootstrap lebih dari 15 detik.
- Pasang **`readinessProbe`** pada semua Pod yang menerima traffic dari Kubernetes Service.
- Selalu pasang `lifecycle.preStop` dengan `sleep 5` pada service web produksi dengan traffic padat untuk menjamin *zero connection drop* saat deployment.

---

## 14. When NOT To Use
- Jangan gunakan `livenessProbe` untuk mengecek ketersediaan layanan pihak ketiga (Database, Redis, payment gateway eksternal).
- Jangan setel `periodSeconds` terlalu agresif (misal: 1 detik) pada `exec` probe karena akan membebani CPU node oleh proses fork shell berulang-ulang.

---

## 15. Common Mistakes
1. **Menggunakan Liveness Probe tanpa Startup Probe pada aplikasi lambat**: Liveness probe dengan `initialDelaySeconds: 30` akan membunuh aplikasi yang kebetulan butuh 35 detik untuk start di server yang sedang sibuk.
2. **Lupa menangani `SIGTERM` di aplikasi**: Aplikasi mengabaikan `SIGTERM`, sehingga Kubelet menunggu hingga 30 detik lalu membunuhnya dengan `SIGKILL`, memutus transaksi client di tengah jalan.
3. **Mengabaikan status `ContainersReady` vs `Ready`**: Mengira kontainer sudah berjalan berarti traffic otomatis masuk, padahal `readinessProbe` masih mengembalikan status 503.

---

## 16. Best Practices
### Must Have
- Selalu pisahkan endpoint:
  - Liveness: `/healthz/live` (Cek shallow internal app).
  - Readiness: `/healthz/ready` (Cek koneksi database & kesiapan melayani).
- Terapkan penanganan sinyal `SIGTERM` di kode aplikasi.

### Recommended
- Berikan margin waktu `terminationGracePeriodSeconds` yang cukup (misal 45-60 detik) untuk worker background yang memproses batch processing.
- Konfigurasikan `timeoutSeconds: 2` atau `3` agar probe yang lambat tidak menggantung antrean pemeriksaan Kubelet.

### Advanced
- Di arsitektur service mesh (Istio/Linkerd), manfaatkan lifecycle pre-stop synchronization agar container aplikasi utama tidak mati lebih awal sebelum Envoy proxy sidecar sempat menyelesaikan flushing buffer log.

---

## 17. Troubleshooting Guide
### Problem 1: Pod mengalami `CrashLoopBackOff`
- **Penyebab**: Kontainer aplikasi crash berulang kali segera setelah start.
- **Diagnosa**:
  ```bash
  kubectl describe pod <nama-pod>
  # Cek bagian Last State: Exit Code dan Reason
  kubectl logs <nama-pod> --previous
  ```
  Flag `--previous` memungkinkan Anda membaca log dari instance kontainer sebelum ia crash!

### Problem 2: Pod berstatus `Running` tetapi tidak menerima traffic dari Service
- **Penyebab**: `readinessProbe` gagal, sehingga Pod IP tidak didaftarkan ke Service Endpoints.
- **Diagnosa**:
  ```bash
  kubectl get endpoints <nama-service>
  kubectl describe pod <nama-pod> | grep -A 5 Conditions
  # Cek apakah Ready: False
  ```
- **Solusi**: Periksa endpoint readiness aplikasi Anda (`curl http://<pod-ip>:port/healthz/ready`).

---

## 18. Exercises
### Level: Easy
1. Tuliskan manifest Pod Nginx sederhana dan sertakan `readinessProbe` tipe `httpGet` pada port 80 path `/`.
2. Deploy pod tersebut dan periksa kondisinya menggunakan `kubectl describe pod <nama-pod>`.

### Level: Medium
1. Buat Pod dengan `livenessProbe` yang sengaja gagal (misal memeriksa file `/tmp/healthy` yang kemudian dihapus setelah 10 detik).
2. Amati bagaimana kolom `RESTARTS` bertambah saat Kubelet membunuh dan me-restart kontainer tersebut.

### Level: Hard
1. Buat aplikasi web sederhana yang mencatat setiap sinyal Linux yang diterima.
2. Pasang `lifecycle.preStop` dan `terminationGracePeriodSeconds: 30`.
3. Jalankan `kubectl delete pod` dan amati log terminal untuk membuktikan urutan: `preStop` dieksekusi -> `SIGTERM` diterima -> koneksi dibersihkan -> kontainer exit 0.

---

## 19. Challenge
Rancang arsitektur zero-downtime rolling update untuk sistem checkout perbankan:
- Aplikasi Java Spring Boot membutuhkan waktu booting 45 detik.
- Setiap transaksi pembayaran memakan waktu maksimal 8 detik.
- Tentukan konfigurasi lengkap `startupProbe`, `livenessProbe`, `readinessProbe`, `terminationGracePeriodSeconds`, dan `preStop` hook agar tidak ada 1 pun transaksi nasabah yang terputus (HTTP 502/504) saat proses deployment versi baru berjalan di jam sibuk.

---

## 20. Summary
- **Pod** adalah primitif terkecil di Kubernetes yang membungkus satu atau beberapa kontainer dengan shared network, IPC, dan storage.
- **`startupProbe`** melindungi aplikasi lambat saat proses bootstrapping.
- **`livenessProbe`** bertindak sebagai self-healing pengawas deadlock (tindakan: RESTART).
- **`readinessProbe`** mengontrol gerbang traffic jaringan Service (tindakan: ISOLASI DARI ENDPOINTS).
- **Graceful Termination** (`preStop` -> `SIGTERM` -> `terminationGracePeriodSeconds`) adalah kunci operasional rilis tanpa gangguan koneksi pengguna (*zero downtime*).

---
[⬅️ Evaluasi & Quiz BAB 01](../BAB-01-Arsitektur-Internal-dan-Control-Plane/BAB-01-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Multi-Container Patterns ➡️](./Module-02-Multi-Container-Patterns-Sidecar-Init-dan-Ephemeral.md)
---
