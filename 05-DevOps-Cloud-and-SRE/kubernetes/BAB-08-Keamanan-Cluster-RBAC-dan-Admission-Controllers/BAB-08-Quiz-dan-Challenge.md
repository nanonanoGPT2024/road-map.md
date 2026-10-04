---
[⬅️ Module 02: Pod Security Standards & Webhooks](./Module-02-Pod-Security-Standards-dan-Admission-Webhooks.md) | [📋 Silabus Induk](../README.md) | [BAB 09 Module 01: Advanced Scheduling & Taints ➡️](../BAB-09-Scheduling-Lanjutan-dan-Autoscaling/Module-01-Taints-Tolerations-NodeAffinity-dan-TopologySpread.md)
---

# BAB 08: Keamanan Cluster: RBAC, ServiceAccounts, & Admission Controllers — Quiz & Chapter Challenge

Dokumen ini berisi pengujian pemahaman konseptual, analisis skenario eksploitasi dan pertahanan keamanan cluster, serta tantangan arsitektur zero-trust untuk BAB 08.

---

## Bagian 1: Quiz Konseptual Dasar (5 Soal)

### Soal 1
Apa perbedaan mendasar antara `RoleBinding` dan `ClusterRoleBinding` ketika keduanya merujuk ke sebuah objek `ClusterRole` yang sama?
- A. `RoleBinding` hanya mengikat izin ClusterRole di dalam satu namespace spesifik di mana RoleBinding tersebut berada, sedangkan `ClusterRoleBinding` memberikan izin di seluruh namespace dan resource tingkat cluster.
- B. `RoleBinding` hanya untuk User manusia, sedangkan `ClusterRoleBinding` hanya untuk ServiceAccount.
- C. `RoleBinding` menggunakan enkripsi RSA, sedangkan `ClusterRoleBinding` menggunakan ECDSA.
- D. `RoleBinding` membatasi CPU Pod, sedangkan `ClusterRoleBinding` membatasi Memory.

### Soal 2
Verb Kubernetes manakah yang harus didefinisikan dalam sebuah `Role` untuk mengizinkan developer membuka shell terminal interaktif ke dalam container menggunakan `kubectl exec`?
- A. `verbs: ["get"]` pada `resources: ["pods/terminal"]`
- B. `verbs: ["create"]` pada `resources: ["pods/exec"]`
- C. `verbs: ["update"]` pada `resources: ["pods/shell"]`
- D. `verbs: ["watch"]` pada `resources: ["containers/exec"]`

### Soal 3
Dalam fase pemrosesan request di `kube-apiserver`, di posisi manakah `Mutating Admission Webhook` dieksekusi?
- A. Setelah data berhasil disimpan di etcd.
- B. Sebelum proses Authentication selesai.
- C. Setelah request lolos Authentication & Authorization (RBAC), tetapi sebelum Schema Validation dan Validating Admission Webhook.
- D. Di dalam biner Kubelet pada worker node saat mendownload container image.

### Soal 4
Tiga level profil standar keamanan Pod dalam Pod Security Standards (PSS) adalah:
- A. `Development`, `Staging`, `Production`
- B. `Low`, `Medium`, `High`
- C. `Privileged`, `Baseline`, `Restricted`
- D. `Open`, `Strict`, `Isolated`

### Soal 5
Apa resiko operasional terbesar jika sebuah `ValidatingWebhookConfiguration` dikonfigurasi dengan `failurePolicy: Fail` tanpa mengecualikan namespace `kube-system`?
- A. CPU Kubelet akan langsung menyentuh 100%.
- B. Jika Pod server webhook tersebut down, cluster tidak akan bisa membuat atau me-restart Pod apapun (termasuk CoreDNS, CNI, atau Pod Webhook itu sendiri), menyebabkan kondisi cluster lumpuh total (*deadlock*).
- C. Sertifikat TLS cluster akan otomatis hangus.
- D. Semua PersistentVolume akan diformat ulang.

---

## Bagian 2: Quiz Skenario & Troubleshooting Tingkat Menengah (5 Soal)

### Soal 6
Seorang developer menjalankan `kubectl logs -f my-pod -n staging` dan mendapatkan pesan error:
`Error from server (Forbidden): pods "my-pod" is forbidden: User "alex" cannot get resource "pods/log" in API group "" in the namespace "staging"`.
Role RBAC milik Alex saat ini adalah:
```yaml
rules:
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["get", "list", "watch"]
```
Bagaimana cara memperbaiki Role tersebut agar Alex dapat membaca log tanpa memberikan hak akses berlebih?
- A. Ubah `verbs` menjadi `verbs: ["*"]`.
- B. Tambahkan subresource `"pods/log"` ke dalam array `resources`.
- C. Ubah `apiGroups` menjadi `["apps"]`.
- D. Pasang label `pod-security.kubernetes.io/enforce: privileged` di namespace staging.

### Soal 7
Sebuah namespace diberi label:
`pod-security.kubernetes.io/enforce: restricted`.
Developer mencoba men-deploy manifest Pod NGINX standar berikut:
```yaml
spec:
  containers:
    - name: nginx
      image: nginx:alpine
```
Deployment gagal dibuat oleh ReplicaSet controller. Mengapa?
- A. NGINX image tidak mendukung arsitektur ARM64.
- B. Standar `restricted` mewajibkan penegakan eksplisit: `securityContext.runAsNonRoot: true`, pembatasan Linux capabilities (drop `ALL`), pembatasan privilage escalation, dan seccomp profile `RuntimeDefault`.
- C. Namespace tidak memiliki ResourceQuota.
- D. Image nginx:alpine belum ditandatangani dengan Cosign.

### Soal 8
Sebuah Pod worker backend tidak pernah melakukan panggilan ke Kubernetes API Server, namun tim audit menemukan bahwa token ServiceAccount ter-mount secara otomatis di `/var/run/secrets/kubernetes.io/serviceaccount/token`.
Bagaimana cara terbaik menutup celah ini sesuai panduan hardening PCI-DSS?
- A. Menghapus biner `curl` di dalam image Docker.
- B. Menyetel `automountServiceAccountToken: false` pada ServiceAccount atau pada spesifikasi Pod.
- C. Menghapus namespace `default`.
- D. Mengubah izin chmod file token menjadi 000 via cronjob Linux.

### Soal 9
Platform Engineer ingin menyematkan label `injected-by: security-webhook` dan limit memory default `256Mi` secara transparan pada setiap Pod yang dibuat oleh developer tanpa mengubah file YAML asli mereka. Jenis admission controller apa yang harus digunakan?
- A. `ValidatingAdmissionWebhook`
- B. `MutatingAdmissionWebhook` yang menghasilkan JSON Patch RFC 6902
- C. RBAC ClusterRoleAggregator
- D. PodDisruptionBudget

### Soal 10
Ketika menjalankan `kubectl auth can-i create secrets --as system:serviceaccount:prod:web-sa -n prod`, terminal merespons `no`. Namun, ketika Pod `web-sa` berjalan, aplikasi berhasil membaca Secret `prod-db-creds` menggunakan panggilan HTTP REST GET.
Apakah hal ini mungkin terjadi dalam model RBAC Kubernetes?
- A. Tidak mungkin, output `can-i` selalu identik untuk semua aksi.
- B. Mungkin, karena pertanyaan audit menanyakan verb `create`, sedangkan Role RBAC Pod tersebut mungkin hanya memiliki izin verb `get` pada resource Secret.
- C. Kubelet memalsukan token ServiceAccount.
- D. Kubernetes API server mengalami split-brain.

---

## Bagian 3: Skenario Kasus Arsitektur Tingkat Lanjut (3 Soal)

### Skenario 1: Mitigasi Supply Chain Attack & Image Registry Whitelisting
Perusahaan Anda melarang keras penggunaan container image dari public Docker Hub tanpa audit tim security. Seluruh workload produksi WAJIB ditarik dari internal registry perusahaan (`registry.corp.internal/production/*`).
Rancang arsitektur `ValidatingAdmissionWebhook` (lengkap dengan penanganan TLS, failurePolicy, pengecualian namespace sistem, dan logika validasi) untuk memblokir setiap Pod yang mencoba menarik image di luar registry resmi tersebut!

### Skenario 2: Migrasi Pod Security Policy (PSP) ke PSS Tanpa Outage
Cluster perusahaan Anda sedang di-upgrade dari Kubernetes v1.24 ke v1.28. Objek `PodSecurityPolicy` (PSP) telah dihapus sepenuhnya di rilis baru ini. Terdapat 150 microservices yang berjalan di 20 namespace.
Jelaskan strategi bertahap (*phased rollout*) menggunakan mode PSA (`audit`, `warn`, `enforce`) untuk memastikan proses transisi berjalan mulus tanpa menyebabkan downtime microservice di produksi!

### Skenario 3: Zero-Trust RBAC untuk Multi-Tenant CI/CD Runner
Sebuah cluster digunakan bersama oleh tim Data Engineering (membutuhkan akses GPU dan Job/CronJob) dan tim Mobile Backend (membutuhkan Deployment dan HPA). Setiap tim memiliki runner GitLab CI/CD terpisah.
Rancang matriks otorisasi RBAC lengkap (menggunakan pola `ClusterRole` reusable + `RoleBinding` lokal) yang menjamin:
- CI/CD Runner tim Data tidak dapat melihat ConfigMap/Secret atau memodifikasi Deployment tim Mobile.
- Runner dilarang keras meng-exec ke Pod produksi.
- Runner dilarang melakukan eskalasi hak istimewa (privilege escalation).

---

## Bagian 4: Chapter Challenge — Hardened Multi-Tenant Namespace with Kyverno / Webhook Simulator

### Deskripsi Tantangan
Anda diminta membangun environment namespace produksi yang aman (*zero-trust sandbox*):
1. **Namespace**: Buat namespace `fintech-secure`.
2. **Pod Security Admission**: Terapkan label `restricted` pada namespace tersebut dengan mode `enforce`, `warn`, dan `audit`.
3. **RBAC Hardening**:
   - Buat ServiceAccount `fintech-app-sa` dengan `automountServiceAccountToken: false`.
   - Buat Role `app-operator` yang hanya boleh me-restart deployment (`patch deployments`) dan membaca log (`get pods/log`).
   - Ikat ServiceAccount ke Role tersebut.
4. **Validating Policy Manifest**:
   - Tulis spesifikasi webhook atau policy Kyverno yang menolak Pod jika tidak menyertakan label `data-classification` (hanya menerima nilai `confidential` atau `restricted`).
5. **Hardened Pod Manifest**: Tulis manifest Pod produksi yang 100% mematuhi seluruh aturan di atas dan berhasil berstatus `Running`.

---

## Bagian 5: Knowledge Check & Checklist

### Saya Harus Memahami:
- [ ] Tiga tahap validasi API Server: Authentication $\rightarrow$ Authorization $\rightarrow$ Admission Control.
- [ ] Perbedaan scope 4 objek RBAC: `Role`, `ClusterRole`, `RoleBinding`, `ClusterRoleBinding`.
- [ ] Konsep Subresource (`pods/log`, `pods/exec`, `pods/portforward`).
- [ ] Batasan granular berbasis `resourceNames`.
- [ ] Fitur keamanan Bound ServiceAccount Token Projection modern.
- [ ] Tiga level PSS: `Privileged`, `Baseline`, `Restricted`.
- [ ] Tiga mode aksi PSA: `enforce`, `audit`, `warn`.
- [ ] Cara kerja Mutating Webhook (JSON Patch) vs Validating Webhook.
- [ ] Dampak krusial `failurePolicy: Fail` vs `failurePolicy: Ignore`.

### Saya Tidak Perlu Menghafal:
- [ ] Daftar seluruh Linux capability kernel C header bitmask.
- [ ] Format biner internal dari token JWT x509 SAN certificate.

### Saya Harus Bisa Melakukan:
- [ ] Menulis Role dan RoleBinding granular sesuai prinsip Least Privilege.
- [ ] Menggunakan `kubectl auth can-i` untuk mengaudit wewenang pengguna dan ServiceAccount.
- [ ] Mengonfigurasi label PSS Restricted pada namespace produksi.
- [ ] Menulis manifest Pod yang lulus standar PSS Restricted.
- [ ] Mendiagnosa dan memulihkan cluster dari kegagalan admission webhook timeout.

---
[⬅️ Module 02: Pod Security Standards & Webhooks](./Module-02-Pod-Security-Standards-dan-Admission-Webhooks.md) | [📋 Silabus Induk](../README.md) | [BAB 09 Module 01: Advanced Scheduling & Taints ➡️](../BAB-09-Scheduling-Lanjutan-dan-Autoscaling/Module-01-Taints-Tolerations-NodeAffinity-dan-TopologySpread.md)
---
