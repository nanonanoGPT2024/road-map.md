# Module 01: Deployments, RollingUpdate Strategies, ReplicaSets, dan Automated Rollbacks

---
[⬅️ Evaluasi & Quiz BAB 02](../BAB-02-Pod-Lifecycle-dan-Multi-Container-Patterns/BAB-02-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: StatefulSets & DaemonSets ➡️](./Module-02-StatefulSets-DaemonSets-Jobs-dan-CronJobs.md)
---

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
1. Memahami hierarki hubungan arsitektural antara **Deployment**, **ReplicaSet**, dan **Pod**.
2. Menguasai dua strategi utama deployment: **RollingUpdate** (inkremental tanpa downtime) dan **Recreate** (downtime terkontrol untuk database/singleton).
3. Mengonfigurasi dan menghitung parameter throttling rolling update: **`maxSurge`** dan **`maxUnavailable`** (dalam persentase maupun angka absolut).
4. Melakukan pelacakan revisi rilis (**Revision History**), pause/resume rollout, dan rollback instan (**`kubectl rollout undo`**).
5. Memahami fungsi label internal **`pod-template-hash`** dalam membedakan generasi ReplicaSet.

---

## 2. Prerequisite
- Memahami konsep dasar Pod dan Health Probes ([BAB 02 Module 01](../BAB-02-Pod-Lifecycle-dan-Multi-Container-Patterns/Module-01-Anatomi-Pod-Lifecycle-Probes-dan-Termination.md)).
- Memahami rekonsiliasi kontroler loop di Control Plane ([BAB 01 Module 01](../BAB-01-Arsitektur-Internal-dan-Control-Plane/Module-01-Arsitektur-Control-Plane-apiserver-etcd-controller-scheduler.md)).

---

## 3. Concept
Meskipun Pod adalah unit eksekusi terkecil di Kubernetes, mengelola Pod secara telanjang (*naked Pods*) di lingkungan produksi adalah sebuah anti-pattern. Jika sebuah Pod individu mati atau worker node tempat ia berjalan terbakar, Pod tersebut tidak akan pernah dibangkitkan kembali.

Kubernetes menyediakan **Workload Controllers**, dan yang paling dominan untuk aplikasi stateless adalah **Deployment**.

Secara arsitektural, Deployment tidak mengelola Pod secara langsung:
$$\text{Deployment} \longrightarrow \text{ReplicaSet} \longrightarrow \text{Pods}$$
- **ReplicaSet**: Bertanggung jawab menjaga jumlah replika Pod yang berjalan selalu sama dengan angka yang diinginkan (`spec.replicas`) menggunakan mekanisme *Label Selector*.
- **Deployment**: Bertindak sebagai manajer deklaratif tingkat tinggi di atas ReplicaSet. Deployment mengatur **bagaimana cara berpindah dari versi lama ke versi baru** (misal dari Image v1 ke Image v2) dengan cara membuat ReplicaSet baru secara bertahap sambil menurunkan replika pada ReplicaSet lama.

---

## 4. Why?
1. **Zero-Downtime Deployment**: Pengguna tidak akan pernah mengalami putus koneksi saat tim pengembang merilis versi software baru ke produksi.
2. **Kemampuan Rollback Seketika**: Jika versi baru mengandung bug kritis yang lolos ke produksi, Anda dapat mengembalikan sistem ke versi stabil sebelumnya dalam hitungan detik (`kubectl rollout undo`) tanpa perlu kompilasi ulang kode.
3. **Pemberhentian Sementara (Canary Pausing)**: Anda dapat mem-pause rollout di tengah jalan (`kubectl rollout pause`) untuk menginspeksi metrik sebelum melanjutkan ke seluruh armada server.

---

## 5. What?
### Dua Strategi Deployment Utama:

| Parameter | Strategi `RollingUpdate` (Default) | Strategi `Recreate` |
|---|---|---|
| **Perilaku** | Pod baru dinyalakan secara bertahap berdampingan dengan Pod lama sebelum Pod lama dimatikan. | Seluruh Pod lama dimatikan terlebih dahulu (0 Pod aktif), baru kemudian seluruh Pod baru dinyalakan. |
| **Downtime** | **0 Detik (Zero-Downtime)** jika probes dikonfigurasi benar. | **Ada Downtime** selama durasi penghapusan dan bootstrapping Pod baru. |
| **Konsumsi Resource** | Membutuhkan kapasitas CPU/RAM ekstra sementara di kluster (sesuai `maxSurge`). | Tidak membutuhkan resource tambahan (kapasitas lama dibebaskan dulu). |
| **Kesesuaian Workload** | Aplikasi stateless web HTTP, REST API, microservices. | Aplikasi yang tidak mendukung multi-versi (misal: single-writer database, aplikasi stateful legacy). |

---

## 6. How? Alur Kerja RollingUpdate dengan MaxSurge & MaxUnavailable

Misalkan kita memiliki Deployment dengan `replicas: 4`, `maxSurge: 1`, dan `maxUnavailable: 0`:
- **`maxSurge: 1`**: Kubernetes diizinkan membuat maksimal $4 + 1 = 5$ Pod secara total selama proses update berlangsung.
- **`maxUnavailable: 0`**: Kubernetes **TIDAK MENGIZINKAN** jumlah Pod yang sehat berkurang di bawah 4.

```text
Kondisi Awal (Versi v1.0.0 Aktif):
ReplicaSet Lama (v1) : [Pod 1] [Pod 2] [Pod 3] [Pod 4]  (Total: 4 Healthy)
ReplicaSet Baru (v2) : (Kosong)

Langkah 1: Kube-controller membuat 1 Pod baru (v2) karena maxSurge=1
RS Lama (v1) : [Pod 1] [Pod 2] [Pod 3] [Pod 4]
RS Baru (v2) : [Pod 5 (v2)] -> Menunggu readinessProbe lolos...

Langkah 2: Pod 5 (v2) dinyatakan "Ready=True", Kube-controller mematikan 1 Pod lama
RS Lama (v1) : [Pod 1] [Pod 2] [Pod 3]  (Pod 4 dimatikan via SIGTERM)
RS Baru (v2) : [Pod 5 (v2)]             (Total Healthy tetap: 4)

Langkah 3: Proses berulang secara bertahap hingga seluruh Pod berganti ke v2
RS Lama (v1) : (0 Replicas - Disimpan untuk riwayat rollback)
RS Baru (v2) : [Pod 5] [Pod 6] [Pod 7] [Pod 8]  (100% v2.0.0 Aktif!)
```

---

## 7. Analogy
Bayangkan proses rilis aplikasi seperti mengganti jembatan penyeberangan yang sedang ramai dilalui pejalan kaki:
- **Strategi Recreate**: Anda meledakkan jembatan lama hingga runtuh (semua pejalan kaki terjatuh/terhenti), lalu mulai membangun jembatan baru dari nol. Pejalan kaki harus menunggu hingga konstruksi selesai (Downtime).
- **Strategi RollingUpdate**: Anda membangun jalur setapak baru di samping jembatan lama (`maxSurge`). Ketika jalur baru sudah kokoh dan aman diinjak (`readinessProbe: PASS`), Anda mengarahkan sebagian pejalan kaki ke jalur baru sambil membongkar satu per satu papan jembatan lama, hingga akhirnya seluruh jembatan lama digantikan tanpa ada satupun pejalan kaki yang terhenti perjalanannya.

---

## 8. Diagram: Hierarki Deployment, ReplicaSet, dan Rollback

```text
                       [ Deployment: payment-api ]
                                    |
          +-------------------------+-------------------------+
          |                                                   |
          v (Revisi 1: Non-Aktif)                             v (Revisi 2: AKTIF)
[ ReplicaSet: payment-api-74b89f ]                  [ ReplicaSet: payment-api-59d4bc ]
  spec.replicas: 0                                    spec.replicas: 3
  (Disimpan sebagai riwayat rollback)                 (Menjalankan Pod produksi aktif)
                                                              |
                                           +------------------+------------------+
                                           |                  |                  |
                                           v                  v                  v
                                        [ Pod A ]          [ Pod B ]          [ Pod C ]
                                       (v2.0 Image)       (v2.0 Image)       (v2.0 Image)
```

---

## 9. Simple Example: Manifest Deployment Produksi

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: auth-service
  namespace: production
  labels:
    app: auth
spec:
  replicas: 4
  revisionHistoryLimit: 10 # Menyimpan hingga 10 riwayat revisi ReplicaSet
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 25%        # Maksimal 1 Pod ekstra di atas 4 (total 5)
      maxUnavailable: 0    # Jaminan 100% kapasitas selalu tersedia!
  selector:
    matchLabels:
      app: auth
  template:
    metadata:
      labels:
        app: auth
    spec:
      containers:
      - name: auth-api
        image: myregistry/auth-api:v2.1.0
        ports:
        - containerPort: 8080
        readinessProbe:
          httpGet:
            path: /healthz/ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 3
```

---

## 10. Practical Example: CLI Rollout & Rollback Operations

```bash
# 1. Terapkan deployment baru
kubectl apply -f auth-deployment.yaml

# 2. Pantau proses transisi rolling update secara real-time
kubectl rollout status deployment/auth-service -n production

# 3. Ubah versi image aplikasi (Memicu Rolling Update otomatis)
kubectl set image deployment/auth-service auth-api=myregistry/auth-api:v2.2.0 -n production --record

# 4. Periksa riwayat revisi rollout
kubectl rollout history deployment/auth-service -n production

# 5. Skenario Darurat: Versi baru v2.2.0 memiliki bug! Lakukan Rollback Instan ke revisi sebelumnya!
kubectl rollout undo deployment/auth-service -n production

# 6. Atau rollback ke nomor revisi spesifik (misal Revisi 1)
kubectl rollout undo deployment/auth-service -n production --to-revision=1
```

---

## 11. Real World Example: Deployment Menggantung (*Hung Rollout*) Akibat Readiness Probe Gagal
Sebuah tim DevOps merilis versi aplikasi baru `v3.0.0` dengan konfigurasi:
```yaml
maxSurge: 1
maxUnavailable: 0
```
- **Masalah**: Image baru `v3.0.0` memiliki salah ketik (typo) di nama database, sehingga kontainer Pod baru gagal melewati `readinessProbe`.
- **Perilaku Kubernetes**: 
  - Kube-controller membuat 1 Pod baru (v3.0.0).
  - Karena `readinessProbe` tidak pernah sukses (`Ready=False`), dan `maxUnavailable: 0` mewajibkan 4 Pod sehat tetap aktif, Kubernetes **TIDAK PERNAH MEMATIKAN** keempat Pod lama (v2.0.0).
  - Hasilnya: **Traffic pengguna 100% tetap aman dilayani oleh versi lama**, tidak ada downtime sama sekali!
  - Rollout otomatis berhenti (*stuck*) dan menunggu investigasi developer.

---

## 12. Trade-offs: RollingUpdate vs Recreate

| Aspek | RollingUpdate | Recreate |
|---|---|---|
| **Downtime Risiko** | 0% (Koneksi pengguna tidak terganggu) | 100% selama durasi pergantian Pod |
| **Kebutuhan Resource Kluster** | Butuh alokasi CPU/RAM cadangan (sesuai `maxSurge`) | Nol kebutuhan ekstra (Pod lama dimatikan dulu) |
| **Multi-Versi Database Compatibility** | Wajib mendukung backward compatibility (v1 dan v2 berjalan bersamaan) | Aman untuk perubahan database non-backward compatible |
| **Kecepatan Rollout** | Bertahap (bisa memakan 2-5 menit) | Seketika (secepat Pod baru bisa boot) |

---

## 13. When To Use
- Gunakan **`RollingUpdate`** dengan `maxUnavailable: 0` untuk seluruh API HTTP publik dan microservices mission-critical.
- Gunakan **`Recreate`** hanya jika aplikasi Anda membaca antrean eksklusif di mana dua versi kode berbeda dilarang berjalan bersamaan di waktu yang sama.
- Selalu setel **`revisionHistoryLimit`** (misal 5 atau 10) agar `etcd` tidak dipenuhi oleh ratusan ReplicaSet usang yang sudah berskala 0.

---

## 14. When NOT To Use
- Jangan gunakan `Deployment` untuk aplikasi stateful (database seperti PostgreSQL, Kafka, MongoDB) yang membutuhkan identitas network dan storage persisten yang stabil (gunakan **StatefulSet** di Module 02!).
- Jangan gunakan `maxUnavailable: 100%` di production kecuali Anda memang menghendaki downtime total.

---

## 15. Common Mistakes
1. **Mengubah selector `matchLabels` pada Deployment yang sudah ada**: Label selector bersifat *immutable* setelah dibuat. Mencoba mengubahnya akan memicu error validasi apiserver.
2. **Rolling update tanpa Readiness Probe**: Tanpa probe, Kubernetes menganggap kontainer sudah siap sesaat setelah proses PID 1 menyala, memicu rentetan error HTTP 502 ke client.
3. **Mengabaikan Backward Compatibility Database**: Mengubah kolom database di v2 saat v1 masih aktif melayani traffic, menyebabkan Pod v1 crash saat mencoba membaca database yang sudah berubah.

---

## 16. Best Practices
### Must Have
- Selalu pasang `readinessProbe` yang valid pada template Pod Deployment.
- Tentukan `maxSurge` dan `maxUnavailable` secara sadar (rekomendasi: `maxSurge: 25%`, `maxUnavailable: 0`).
- Simpan riwayat revisi dengan menyetel `revisionHistoryLimit: 10`.

### Recommended
- Gunakan flag `--record` (atau annotasi `kubernetes.io/change-cause`) pada metadata rilis agar perintah `kubectl rollout history` menampilkan pesan commit/alasan perubahan yang jelas.
- Konfigurasikan `progressDeadlineSeconds: 600` (10 menit) agar Deployment otomatis dilaporkan gagal (*Condition: Progressing=False*) jika proses rilis terhambat melebihi batas waktu.

### Advanced
- Gabungkan Deployment dengan **Argo Rollouts** atau **Flagger** untuk menerapkan strategi rilis **Canary Analysis** dan **Blue-Green** otomatis berbasis metrik error rate Prometheus.

---

## 17. Troubleshooting Guide
### Problem 1: Rollout terjebak di tengah jalan (*stuck*)
- **Penyebab**: Pod baru gagal lolos `readinessProbe` atau mengalami `CrashLoopBackOff`/`ImagePullBackOff`.
- **Diagnosa**:
  ```bash
  kubectl rollout status deployment/<nama-deploy>
  kubectl get pods -l app=<nama-app>
  kubectl describe pod <nama-pod-baru-yang-error>
  ```
- **Solusi Cepat**: Batalkan rollout dan kembalikan ke versi stabil segera:
  ```bash
  kubectl rollout undo deployment/<nama-deploy>
  ```

### Problem 2: Rollback gagal dengan error `no rollout history found`
- **Penyebab**: Nilai `revisionHistoryLimit` disetel ke 0, sehingga ReplicaSet lama langsung dihapus seketika.
- **Solusi**: Selalu pertahankan `revisionHistoryLimit` minimal bernilai 3 atau 5.

---

## 18. Exercises
### Level: Easy
1. Buat Deployment Nginx dengan 3 replika menggunakan CLI:
   `kubectl create deployment nginx-web --image=nginx:1.24 --replicas=3`
2. Periksa status rollout menggunakan `kubectl rollout status deployment/nginx-web`.

### Level: Medium
1. Update versi image deployment menjadi `nginx:1.25`:
   `kubectl set image deployment/nginx-web nginx=nginx:1.25`
2. Amati bagaimana ReplicaSet baru dibuat dan ReplicaSet lama diturunkan replikanya via `kubectl get rs`.
3. Lakukan rollback ke versi sebelumnya: `kubectl rollout undo deployment/nginx-web`.

### Level: Hard
1. Buat Deployment dengan `maxSurge: 1`, `maxUnavailable: 0`, dan `readinessProbe` ke port yang salah.
2. Lakukan update image dan amati bagaimana Kubernetes menghentikan proses rilis secara otomatis tanpa mematikan satu pun Pod lama.

---

## 19. Challenge
Rancang arsitektur zero-downtime deployment untuk sistem payment gateway:
- 12 replika Pod berjalan di cluster 3 worker node.
- Kebijakan perusahaan: Kapasitas throughput tidak boleh turun di bawah 100% setiap saat, namun resource CPU kluster terbatas hanya dapat menampung maksimal 3 Pod ekstra selama proses rilis.
- Tentukan nilai presisi `maxSurge` dan `maxUnavailable` (dalam persen atau integer).
- Buat skrip bash otomatisasi deployment yang mengevaluasi `kubectl rollout status`, dan otomatis memicu `kubectl rollout undo` jika proses rilis tidak selesai dalam waktu 3 menit.

---

## 20. Summary
- **Deployment** mengelola **ReplicaSet**, dan ReplicaSet mengelola replika **Pod**.
- **`RollingUpdate`** memungkinkan pergantian versi secara bertahap tanpa downtime dengan mengatur **`maxSurge`** (kelebihan Pod sementara) dan **`maxUnavailable`** (kekurangan Pod yang ditoleransi).
- **`readinessProbe`** adalah penjaga gawang mutlak agar traffic tidak dikirim ke Pod baru sebelum siap.
- **`kubectl rollout undo`** memberikan jaring pengaman instan untuk membatalkan rilis yang bermasalah dalam hitungan detik.

---
[⬅️ Evaluasi & Quiz BAB 02](../BAB-02-Pod-Lifecycle-dan-Multi-Container-Patterns/BAB-02-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: StatefulSets & DaemonSets ➡️](./Module-02-StatefulSets-DaemonSets-Jobs-dan-CronJobs.md)
---
