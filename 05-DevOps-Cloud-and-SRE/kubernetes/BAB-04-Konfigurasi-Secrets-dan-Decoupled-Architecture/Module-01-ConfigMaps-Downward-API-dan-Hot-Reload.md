# Module 01: ConfigMaps, Downward API, Volume Mounts vs Env Vars, dan Hot-Reload

---
[⬅️ Evaluasi & Quiz BAB 03](../BAB-03-Workload-Controllers/BAB-03-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Secrets & External Secrets Operator ➡️](./Module-02-Secrets-External-Secrets-Operator-dan-Encryption.md)
---

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
1. Menerapkan prinsip *The Twelve-Factor App* (Faktor III: Config) dengan memisahkan konfigurasi aplikasi dari image kontainer menggunakan **ConfigMaps**.
2. Membedakan perilaku konsumsi konfigurasi: **Environment Variables** (`envFrom`) vs **Volume Mounts** (`volumes.configMap`).
3. Memahami mekanisme internal pembaruan otomatis Kubelet via symlink rotasi (`..data`) dan perbedaan update runtime antara Env Var (statis) vs Volume Mount (dinamis).
4. Mengekspos metadata internal Pod (nama pod, IP pod, namespace, alokasi CPU/RAM) ke dalam kontainer aplikasi menggunakan **Downward API**.
5. Mengimplementasikan strategi **Hot-Reload** konfigurasi: File Watcher internal, Hash Checksum Annotation trick, dan automated reloader pattern.
6. Mengoptimalkan kinerja Control Plane pada kluster berskala besar menggunakan **Immutable ConfigMaps** (`immutable: true`).

---

## 2. Prerequisite
- Memahami konsep Deployments dan Pod template ([BAB 03 Module 01](../BAB-03-Workload-Controllers/Module-01-Deployments-RollingUpdate-Strategies-dan-Rollbacks.md)).
- Pemahaman sistem file Linux, symlinks (symbolic links), dan inotify file watch events.

---

## 3. Concept
Dalam pengembangan software modern, membakar (*hardcoding*) konfigurasi seperti port database, feature flags, level logging, atau URL endpoint ke dalam image Docker adalah pelanggaran arsitektur fatal. Pendekatan tersebut memaksa Anda me-rebuild image baru hanya untuk mengubah setting dari environment `staging` ke `production`.

Kubernetes menyediakan resource **ConfigMap** sebagai objek level-kluster yang menyimpan data konfigurasi non-sensitif dalam bentuk pasangan *key-value* atau blok file teks utuh (seperti `nginx.conf` atau `application.properties`).

Aplikasi dapat mengonsumsi ConfigMap melalui dua cara utama:
1. **Environment Variables**: Variabel dibaca sekali saat proses kontainer di-spawn. Jika ConfigMap diubah di kluster, variabel lingkungan di dalam kontainer yang sedang berjalan **TIDAK AKAN BERUBAH** tanpa me-restart Pod.
2. **Volume Mounts**: ConfigMap di-mount sebagai direktori file di dalam kontainer. Kubelet secara berkala menyinkronkan perubahan isi ConfigMap ke filesystem kontainer tanpa perlu me-restart Pod.

---

## 4. Why?
1. **Pola Image Tunggal untuk Seluruh Environment (*Build Once, Deploy Anywhere*)**: Image biner yang sama persis (`mycompany/api:v1.0.0`) dapat di-deploy ke Dev, Staging, dan Prod hanya dengan menautkannya ke ConfigMap yang berbeda di masing-masing namespace.
2. **Zero-Restart Configuration Hot-Reload**: Mengubah log level dari `INFO` ke `DEBUG` saat insiden darurat dapat dilakukan secara instan tanpa perlu me-restart Pod yang sedang menangani jutaan transaksi.
3. **Penyadaran Konteks Topologi (Downward API)**: Aplikasi dapat mengetahui di node fisik mana ia sedang berjalan atau berapa jatah batas CPU yang ia miliki tanpa harus memanggil Kubernetes API secara langsung.

---

## 5. What?
### Komparasi Metode Konsumsi ConfigMap:

| Fitur | Environment Variables (`env` / `envFrom`) | ConfigMap Volume Mount (`volumeMounts`) |
|---|---|---|
| **Format Target di Pod** | Environment variable proses (`process.env.DB_HOST`) | File fisik di direktori (`/etc/config/db_host`) |
| **Pembaruan Otomatis (Live Sync)** | ❌ **TIDAK**. Membutuhkan restart Pod / rollout baru. | ✅ **YA**. Kubelet memperbarui isi file secara berkala via symlink. |
| **Kesesuaian Tipe Data** | Nilai string skalar pendek (port, flag, URL). | File konfigurasi besar terstruktur (JSON, YAML, INI, XML). |
| **SubPath Volume Behavior** | N/A | Jika menggunakan `subPath`, pembaruan otomatis symlink **TIDAK BEKERJA**! |

---

## 6. How? Mekanisme Atomic Symlink Kubelet pada Volume Mounts

Ketika ConfigMap di-mount sebagai volume ke `/etc/config`:
Kubelet tidak langsung menulis file di direktori tersebut. Sebaliknya, Kubelet membuat serangkaian *symbolic links*:

```text
/etc/config/
├── app.conf -> ..data/app.conf
├── ..data -> ..2026_09_11_14_05_12.849201948
└── ..2026_09_11_14_05_12.849201948/
    └── app.conf (Isi data konfigurasi aktual)
```

Saat Anda mengupdate ConfigMap via `kubectl edit cm`:
1. Kubelet mendeteksi perubahan versi resource (`metadata.resourceVersion`).
2. Kubelet membuat direktori baru dengan timestamp baru: `..2026_09_11_14_10_00.123456789`.
3. Kubelet mengubah pointer symlink `..data` ke direktori baru tersebut secara atomik menggunakan syscall `rename()`.
4. Aplikasi yang membaca `/etc/config/app.conf` langsung melihat konten terbaru secara aman tanpa pernah membaca file yang terpotong setengah (*corrupted half-written file*).

---

## 7. Analogy
Bayangkan aplikasi Anda adalah seorang koki di dapur restoran:
- **Environment Variables** adalah tato resep di lengan koki. Tato tersebut dibuat sebelum koki mulai bekerja. Jika pemilik restoran ingin mengubah takaran garam (update config), koki tidak bisa mengubahnya kecuali koki tersebut "diistirahatkan dan diganti koki baru" (restart Pod).
- **Volume Mounts** adalah papan tulis resep gantung di dinding dapur. Pemilik restoran bisa datang kapan saja dan menghapus angka garam lalu menuliskan angka baru. Koki cukup melirik papan tulis setiap kali memasak menu baru (Live Update).
- **Downward API** adalah kartu identitas pengenal yang dikalungkan di leher koki. Dari kartu itu, koki bisa membaca: "Saya adalah Koki Meja-3 di Cabang Surabaya" (`podName` dan `namespace`) tanpa perlu bertanya ke kantor pusat.

---

## 8. Diagram: Downward API Extraction Architecture

```text
[ Kubernetes Pod Metadata & Resource Quota ]
  - metadata.name: "payment-api-74b89f-8x2z"
  - metadata.namespace: "production"
  - status.podIP: "10.244.1.45"
  - spec.nodeName: "k8s-worker-node-02"
  - resources.limits.cpu: "2"
  - resources.limits.memory: "1024Mi"
                        |
                        v (Disuntikkan via Downward API)
+---------------------------------------------------------------+
|                      Pod Application Process                  |
|                                                               |
|  Env Vars:                                                    |
|  - MY_POD_NAME = "payment-api-74b89f-8x2z"                    |
|  - MY_NODE_NAME = "k8s-worker-node-02"                        |
|  - POD_IP = "10.244.1.45"                                     |
|                                                               |
|  Volume Files:                                                |
|  - /etc/podinfo/cpu_limit -> "2"                              |
|  - /etc/podinfo/memory_limit -> "1073741824"                  |
+---------------------------------------------------------------+
```

---

## 9. Simple Example: Membuat dan Mengonsumsi ConfigMap

### 1. Definisi ConfigMap (`app-config.yaml`):
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: payment-config
  namespace: default
data:
  # Pasangan key-value pendek
  LOG_LEVEL: "debug"
  MAX_RETRIES: "3"
  # File konfigurasi utuh multi-line
  application.yaml: |
    server:
      port: 8080
    database:
      poolSize: 20
      timeoutMs: 5000
    features:
      enableInstantRefund: true
```

### 2. Pod yang Mengonsumsi ConfigMap:
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: payment-app
spec:
  containers:
  - name: api
    image: myregistry/payment-api:v1.0.0
    # Cara A: Injeksi sebagai Environment Variable
    env:
    - name: APP_LOG_LEVEL
      valueFrom:
        configMapKeyRef:
          name: payment-config
          key: LOG_LEVEL

    # Cara B: Mount sebagai File Directory
    volumeMounts:
    - name: config-volume
      mountPath: /etc/payment/config
      readOnly: true
  volumes:
  - name: config-volume
    configMap:
      name: payment-config
```

---

## 10. Practical Example: Downward API & Hot-Reload Hash Annotation

### 1. Pod Mengonsumsi Downward API:
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: downward-api-demo
spec:
  containers:
  - name: app
    image: busybox:1.36
    command: ["sh", "-c", "echo Pod: $POD_NAME on Node: $NODE_NAME IP: $POD_IP; sleep 3600"]
    env:
    - name: POD_NAME
      valueFrom:
        fieldRef:
          fieldPath: metadata.name
    - name: POD_NAMESPACE
      valueFrom:
        fieldRef:
          fieldPath: metadata.namespace
    - name: POD_IP
      valueFrom:
        fieldRef:
          fieldPath: status.podIP
    - name: NODE_NAME
      valueFrom:
        fieldRef:
          fieldPath: spec.nodeName
```

### 2. Trik Industri: Otomatisasi Rolling Update saat ConfigMap Berubah (Config Hash Trick)
Jika aplikasi Anda menggunakan Environment Variables dan Anda ingin Deployment otomatis me-restart Pod setiap kali ConfigMap berubah, sematkan **SHA256 Hash** dari isi ConfigMap pada annotasi template Pod:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-deployment
spec:
  template:
    metadata:
      annotations:
        # Perubahan nilai hash ini akan memaksa Deployment memicu RollingUpdate baru!
        checksum/config: "4e9b89c3f104d49a37fa881b29a..."
    spec:
      containers:
      - name: api
        image: myapp:v1.0.0
        envFrom:
        - configMapRef:
            name: payment-config
```

---

## 11. Real World Example: Efek Samping `subPath` Menghancurkan Live Reload
Sebuah tim backend me-mount satu file `nginx.conf` dari ConfigMap ke `/etc/nginx/nginx.conf` menggunakan opsi `subPath`:
```yaml
volumeMounts:
- name: config-vol
  mountPath: /etc/nginx/nginx.conf
  subPath: nginx.conf # <--- PENYEBAB MASALAH!
```
- **Masalah**: Ketika sysadmin mengupdate `nginx.conf` di ConfigMap, file `/etc/nginx/nginx.conf` di dalam kontainer tidak pernah ter-update sama sekali meskipun ditunggu berjam-jam!
- **Penyebab Teknis**: Fitur `subPath` menggunakan mekanisme Linux *bind mount* langsung ke inode file tunggal, yang mem-bypass seluruh sistem symlink rotasi Kubelet (`..data`).
- **Solusi**: Jangan gunakan `subPath` jika menginginkan live reload. Mount seluruh direktori ke `/etc/nginx/conf.d/` atau gunakan sidecar container *Reloader*.

---

## 12. Trade-offs: Config Reload Strategies

| Pendekatan | Mekanisme | Downtime | Kelebihan | Kekurangan |
|---|---|---|---|---|
| **Volume Mount + App File Watcher** | Aplikasi memantau event `fsnotify` pada file volume | **0 Detik** (Instan) | Perubahan aktif dalam hitungan detik tanpa mematikan koneksi. | Aplikasi harus memiliki logika internal reload. |
| **Config Hash Annotation / Reloader** | Memperbarui annotation `checksum/config` pada Deployment | **0 Detik** (RollingUpdate) | Bekerja untuk aplikasi apa pun (bahkan yang tidak punya file watcher). | Memicu pembuatan Pod baru dan pembuangan Pod lama. |
| **Manual Rollout Restart** | Menjalankan `kubectl rollout restart deploy/<name>` | **0 Detik** (RollingUpdate) | Sangat mudah dan terkontrol manual. | Butuh intervensi manusia atau trigger CI/CD tambahan. |

---

## 13. When To Use
- Gunakan **ConfigMaps** untuk seluruh konfigurasi non-sensitif (feature flags, parameter koneksi non-password, file server config).
- Gunakan **Downward API** saat aplikasi atau logger membutuhkan identitas Pod/Node untuk penamaan thread audit (*Distributed Tracing span tags*).
- Aktifkan **`immutable: true`** pada ConfigMap yang tidak pernah diubah setelah rilis:
  ```yaml
  apiVersion: v1
  kind: ConfigMap
  metadata:
    name: static-config
  immutable: true # Mencegah watch polling Kubelet, menghemat 30% CPU apiserver pada kluster besar!
  ```

---

## 14. When NOT To Use
- **JANGAN PERNAH menyimpan password, token API, private keys, atau string koneksi rahasia di dalam ConfigMap** (Gunakan **Kubernetes Secret** di Module 02!).
- Jangan gunakan ConfigMap untuk menyimpan data biner berukuran besar (> 1MB). Kubernetes membatasi ukuran maksimal objek ConfigMap sebesar **1 MiB** di `etcd`.

---

## 15. Common Mistakes
1. **Mengira Environment Variable akan otomatis berubah saat ConfigMap diupdate**: Env vars di-snapshot saat proses kontainer dibuat. Nilai baru hanya akan terbaca jika Pod di-restart!
2. **Menyimpan data sensitif di ConfigMap**: Siapa pun yang memiliki akses baca namespace dapat melihat data ConfigMap secara transparan tanpa enkripsi.
3. **Menggunakan `subPath` lalu bingung mengapa file tidak pernah auto-update**.

---

## 16. Best Practices
### Must Have
- Batasi ukuran ConfigMap di bawah 1 MiB.
- Pisahkan ConfigMap berdasarkan frekuensi perubahannya (misal: `app-static-config` vs `app-dynamic-flags`).
- Gunakan `readOnly: true` pada `volumeMounts` ConfigMap agar kontainer aplikasi tidak bisa merusak file konfigurasi di filesystem.

### Recommended
- Gunakan tool open-source seperti **Stakater Reloader** untuk secara otomatis memicu rolling update Deployment setiap kali ConfigMap terkait diperbarui.
- Terapkan `immutable: true` pada ConfigMap rilis produksi berversi (misal: `config-v2.1.0`).

### Advanced
- Di bahasa Go/Node.js, gunakan library seperti `fsnotify` atau `chokidar` untuk mendengarkan perubahan symlink `..data` di folder volume mount dan me-reload cache in-memory secara mulus.

---

## 17. Troubleshooting Guide
### Problem 1: Pod gagal start dengan error `CreateContainerConfigError`
- **Penyebab**: PodSpec merujuk ke ConfigMap atau Key yang tidak ditemukan di namespace tersebut.
- **Diagnosa**:
  ```bash
  kubectl describe pod <nama-pod>
  # Cari pesan: configmap "payment-config" not found
  ```
- **Solusi**: Buat ConfigMap yang hilang atau perbaiki nama key di `configMapKeyRef`.

### Problem 2: File konfigurasi di Volume Mount kosong (0 bytes)
- **Penyebab**: Nama key pada `volumes.configMap.items` salah ketik, sehingga Kubelet memetakan key yang tidak ada.
- **Solusi**: Periksa kesesuaian antara key di ConfigMap data dengan blok `items` di PodSpec.

---

## 18. Exercises
### Level: Easy
1. Buat ConfigMap dari CLI menggunakan pasangan literal:
   `kubectl create configmap app-settings --from-literal=ENVIRONMENT=production --from-literal=MAX_WORKERS=5`
2. Tampilkan isi data ConfigMap tersebut dalam format YAML menggunakan `kubectl get cm app-settings -o yaml`.

### Level: Medium
1. Buat file `nginx.conf` kustom di mesin lokal Anda.
2. Buat ConfigMap dari file tersebut: `kubectl create configmap nginx-config --from-file=nginx.conf`.
3. Buat Pod Nginx yang me-mount ConfigMap tersebut ke `/etc/nginx/conf.d/` dan verifikasi konfigurasi aktif menggunakan `kubectl exec`.

### Level: Hard
1. Buat Pod yang mengonsumsi ConfigMap via Volume Mount dan catat isi file di dalamnya.
2. Lakukan `kubectl edit configmap` untuk mengubah nilai data.
3. Pantau direktori volume mount di dalam Pod selama 60 detik dan amati bagaimana rotasi symlink `..data` mengubah isi file secara otomatis tanpa restart Pod!

---

## 19. Challenge
Rancang arsitektur konfigurasi dinamis zero-downtime untuk microservice gateway:
- Gateway membaca routing rules dari file `/etc/gateway/routes.json` yang di-mount dari ConfigMap.
- Aplikasi memiliki background worker yang mendeteksi perubahan file via fsnotify dan me-reload routing table dalam memori (0ms connection drop).
- Buat manifest ConfigMap, Deployment dengan volume mount, dan script simulasi Node.js yang mendemonstrasikan live reload tanpa restart kontainer.

---

## 20. Summary
- **ConfigMap** memisahkan konfigurasi non-sensitif dari image kontainer (*Twelve-Factor App*).
- **Environment Variables** bersifat statis (butuh restart Pod untuk update), sedangkan **Volume Mounts** diperbarui secara otomatis oleh Kubelet via symlink rotasi.
- Hindari penggunaan **`subPath`** jika menginginkan auto-update volume.
- **Downward API** memberikan visibilitas metadata topologi Pod ke dalam aplikasi tanpa perlu akses Kubernetes API.
- Gunakan **`immutable: true`** untuk meningkatkan efisiensi dan keamanan kluster skala besar.

---
[⬅️ Evaluasi & Quiz BAB 03](../BAB-03-Workload-Controllers/BAB-03-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Secrets & External Secrets Operator ➡️](./Module-02-Secrets-External-Secrets-Operator-dan-Encryption.md)
---
