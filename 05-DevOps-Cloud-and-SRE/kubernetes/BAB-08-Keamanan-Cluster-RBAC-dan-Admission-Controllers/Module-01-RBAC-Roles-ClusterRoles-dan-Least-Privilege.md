---
[⬅️ BAB 07 Quiz & Challenge](../BAB-07-Storage-Persistence-dan-CSI/BAB-07-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Pod Security Standards & Webhooks ➡️](./Module-02-Pod-Security-Standards-dan-Admission-Webhooks.md)
---

# Module 01: Role-Based Access Control (RBAC), ServiceAccounts, & Principle of Least Privilege

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Membedakan alur *Authentication* (Autentikasi: Siapa Anda?) vs *Authorization* (Otorisasi: Apa yang boleh Anda lakukan?) pada Kubernetes API Server.
- Menguasai model data 4 objek inti RBAC: `Role`, `ClusterRole`, `RoleBinding`, dan `ClusterRoleBinding`.
- Menulis aturan izin granular menggunakan kombinasi `apiGroups`, `resources`, `verbs`, `resourceNames`, dan subresources (`pods/log`, `pods/exec`, `pods/portforward`).
- Memahami strategi pengikatan `ClusterRole` ke `RoleBinding` lokal untuk standarisasi permission lintas puluhan namespace tanpa duplikasi kode.
- Mengelola identitas internal container via `ServiceAccount` dan memahami *Bound Service Account Token Volume Projection*.
- Menggunakan perintah audit otorisasi bawaan: `kubectl auth can-i`.

---

## 2. Prerequisite
- Memahami arsitektur Kubernetes API Server dan etcd (Bab 01).
- Memahami isolasi Namespace (Bab 01).
- Konsep dasar Public Key Infrastructure (X.509 client certificates) dan JSON Web Tokens (JWT).

---

## 3. Concept
Setiap panggilan API ke Kubernetes API Server (`kube-apiserver`) harus melewati tiga gerbang pengamanan berurutan sebelum data dibaca atau ditulis ke `etcd`:
1. **Authentication (AuthN)**: Memverifikasi identitas pemanggil (User manusia via X.509 cert/OIDC/OAuth2, atau robot/Pod via ServiceAccount JWT Token). Jika gagal $\rightarrow$ `401 Unauthorized`.
2. **Authorization (AuthZ)**: Mengevaluasi apakah subjek yang telah terotentikasi memiliki izin untuk melakukan aksi (*verb*) pada sumber daya (*resource*) di namespace target. Default mode Kubernetes: **RBAC (Role-Based Access Control)**. Jika ditolak $\rightarrow$ `403 Forbidden`.
3. **Admission Control**: Memvalidasi atau memodifikasi objek sebelum disimpan permanen ke database cluster.

```
Request ---> [ 1. Authentication ] ---> [ 2. Authorization (RBAC) ] ---> [ 3. Admission Control ] ---> [ etcd ]
                 (Who are you?)              (What can you do?)              (Is it secure/valid?)
                 - Client Certs              - Role / RoleBinding            - Mutating Webhooks
                 - OIDC / Dex                - ClusterRole / Binding         - Validating Webhooks
                 - ServiceAccounts                                           - Pod Security
```

---

## 4. Why?
Mengapa sistem otorisasi granular berbasis peran (RBAC) mutlak diperlukan?
1. **Multi-Tenancy & Zero Trust**: Dalam organisasi dengan puluhan tim developer, tim Frontend tidak boleh memiliki hak menghapus database milik tim Payment, dan developer magang tidak boleh memiliki akses `exec` ke Pod produksi yang memproses data kartu kredit.
2. **Mitigasi Kompromi Container**: Jika sebuah Pod web app terkena remote code execution (RCE), token default ServiceAccount yang terpasang di dalam container tidak boleh memiliki hak istimewa seperti membaca `Secrets` cluster atau memanipulasi node Linux.
3. **Kepatuhan Audit & Regulasi**: Standar keamanan seperti PCI-DSS, SOC 2, dan HIPAA mewajibkan pemisahan tugas (*separation of duties*) dan penerapan hak akses paling minim (*Principle of Least Privilege*).

---

## 5. What?

### A. Komponen Primitif RBAC
Kubernetes RBAC terdiri dari 4 objek deklaratif:

| Objek | Scope | Definisi |
|---|---|---|
| **Role** | Namespaced | Kumpulan aturan izin (*rules*) yang hanya berlaku di dalam satu namespace tertentu. |
| **ClusterRole** | Cluster-wide | Kumpulan aturan izin yang berlaku di seluruh cluster (termasuk resource non-namespaced seperti `Node`, `PersistentVolume`, `StorageClass`, `/healthz`). |
| **RoleBinding** | Namespaced | Menghubungkan Subjek (User, Group, ServiceAccount) ke Role (atau ClusterRole) **hanya di dalam satu namespace**. |
| **ClusterRoleBinding** | Cluster-wide | Menghubungkan Subjek ke ClusterRole **di seluruh namespace dan resource level cluster**. |

### B. Anatomi Rule RBAC
Sebuah rule terdiri dari:
- **`apiGroups`**: Grup API Kubernetes. String kosong `""` merepresentasikan core API group (seperti `pods`, `services`, `configmaps`, `secrets`). Contoh lain: `"apps"` (deployments, statefulsets), `"networking.k8s.io"` (ingresses, networkpolicies).
- **`resources`**: Jenis objek yang ditargetkan (selalu dalam bentuk jamak/plural, misal: `pods`, `deployments`, `persistentvolumeclaims`).
- **`verbs`**: Aksi yang diizinkan: `get`, `list`, `watch`, `create`, `update`, `patch`, `delete`, `deletecollection`.
- **`subresources`**: Mengontrol akses ke endpoint turunan, contoh: `pods/log` (membaca log), `pods/exec` (membuka shell interaktif), `pods/status` (hanya mengubah status).
- **`resourceNames`**: Membatasi izin hanya pada instance spesifik dari resource, misal hanya boleh mengedit ConfigMap bernama `app-config`.

### C. ServiceAccount & Bound Token Projection
Setiap Namespace memiliki `ServiceAccount` bernama `default`. Di era modern (Kubernetes v1.21+), ServiceAccount tidak lagi menggunakan token statis tanpa batas waktu yang disimpan sebagai Secret, melainkan menggunakan **Token Projection** (`serviceAccountToken` volume mount) yang:
- Memiliki masa kedaluwarsa otomatis (*time-bound*, misal 1 jam).
- Terikat pada identitas Pod spesifik (*bound to Pod UID*). Jika Pod dihapus, token otomatis hangus.
- Memiliki *audience restriction* (`aud`) yang spesifik guna mencegah pencurian token untuk menyerang layanan lain.

---

## 6. How?

### Pola Desain 1: Role & RoleBinding Lokal (Satu Namespace)
Hanya mengizinkan developer melihat dan me-restart Pod di namespace `dev-team`:

```yaml
# role-dev.yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: dev-team
  name: pod-operator-role
rules:
  - apiGroups: [""]
    resources: ["pods", "pods/log"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["pods/exec"]
    verbs: ["create"] # Akses exec direpresentasikan sebagai create di K8s
---
# binding-dev.yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: dev-users-binding
  namespace: dev-team
subjects:
  - kind: User
    name: "alex@company.com"
    apiGroup: rbac.authorization.k8s.io
  - kind: Group
    name: "frontend-developers"
    apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: Role
  name: pod-operator-role
  apiGroup: rbac.authorization.k8s.io
```

### Pola Desain 2: ClusterRole yang Di-bind via RoleBinding (Pola Best-Practice!)
Alih-alih mendefinisikan Role `view-only` berulang kali di 50 namespace yang berbeda, buat satu `ClusterRole` generik, lalu gunakan `RoleBinding` di masing-masing namespace:

```yaml
# clusterrole-readonly.yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: generic-namespace-reader
rules:
  - apiGroups: ["", "apps", "batch"]
    resources: ["pods", "services", "deployments", "jobs", "configmaps"]
    verbs: ["get", "list", "watch"]
---
# rolebinding-finance.yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: audit-reader-binding
  namespace: finance # Izin hanya berlaku di namespace finance!
subjects:
  - kind: User
    name: "auditor@external.com"
    apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: ClusterRole # Merujuk ke ClusterRole global
  name: generic-namespace-reader
  apiGroup: rbac.authorization.k8s.io
```

---

## 7. Analogy
Bayangkan sebuah **Gedung Perkantoran Multi-Perusahaan (Cluster)**:
- **`ClusterRole`**: SOP Sertifikasi Profesi Satpam atau Petugas Kebersihan yang berlaku standar secara universal.
- **`Role`**: Buku instruksi khusus untuk ruang kantor PT Finansial Maju di Lantai 3.
- **`ClusterRoleBinding`**: Memberikan Master Key Gedung kepada Direktur Properti, sehingga dia bisa masuk ke ruang manapun di seluruh lantai gedung.
- **`RoleBinding`**: Memberikan izin kepada Satpam Alex untuk berjaga **hanya** di pintu kantor PT Finansial Maju di Lantai 3. Meskipun Alex memegang sertifikasi Satpam standar gedung (`ClusterRole`), kuncinya hanya bisa membuka pintu di ruangan tersebut.

---

## 8. Diagram

```
+--------------------------------------------------------------------------------+
|                         KUBERNETES RBAC ARCHITECTURE                           |
|                                                                                |
|  [ Cluster Scope ]                                                             |
|  +---------------------------+       ClusterRoleBinding       +-------------+  |
|  | ClusterRole: cluster-admin | <============================ | User: Root  |  |
|  +---------------------------+                                +-------------+  |
|               ^                                                                |
|               | referenced by                                                  |
|               | RoleBinding                                                    |
|  =============|=============================================================== |
|  [ Namespace: payment-prod ]                                                   |
|               |                      RoleBinding              +-------------+  |
|               +---------------------------------------------  | Service-    |  |
|                                                               | Account: app|  |
|  +---------------------------+       RoleBinding              +-------------+  |
|  | Role: secret-reader       | <-------------------------------------+         |
|  +---------------------------+                                                 |
+--------------------------------------------------------------------------------+
```

---

## 9. Simple Example: Restricting Access to a Single Secret

Seringkali Pod aplikasi hanya boleh membaca satu Secret konfigurasi database miliknya sendiri tanpa bisa melihat Secret sertifikat TLS cluster:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: payment
  name: db-secret-reader-role
rules:
  - apiGroups: [""]
    resources: ["secrets"]
    resourceNames: ["payment-db-credentials"] # HANYA Secret ini yang boleh dibaca!
    verbs: ["get"]
```

---

## 10. Practical Example: Testing Permissions dengan `kubectl auth can-i`

Kubernetes menyediakan sub-perintah biner bawaan yang sangat kuat untuk mengaudit apakah suatu aksi diizinkan sebelum mengeksekusi script CI/CD:

```bash
# 1. Cek hak akses diri sendiri
kubectl auth can-i create deployments --namespace dev-team
# Output: yes

# 2. Cek hak akses impersonasi user lain (memerlukan hak cluster-admin)
kubectl auth can-i delete pods --as alex@company.com --namespace dev-team
# Output: no

# 3. Cek hak akses ServiceAccount aplikasi
kubectl auth can-i get secrets --as system:serviceaccount:payment:payment-backend-sa -n payment
# Output: no

# 4. Tampilkan matriks otorisasi lengkap seorang user di sebuah namespace
kubectl auth can-i --list --as alex@company.com -n dev-team
```

---

## 11. Real World Example: CI/CD Pipeline Deployment ServiceAccount
Sebuah pipeline GitLab CI/CD atau GitHub Actions Runner perlu men-deploy microservice ke namespace `production`.
**Anti-Pattern Fatal**: Menggunakan token `cluster-admin` di variabel CI/CD. Jika repo GitHub diretas, penyerang dapat menghapus seluruh cluster.

**Pola Arsitektur Produksi**:
1. Buat ServiceAccount terisolasi: `cicd-deployer-sa` di namespace `production`.
2. Buat Role khusus yang hanya mengizinkan `get, list, watch, create, update, patch` untuk `deployments`, `services`, `ingresses`, dan `configmaps`.
3. **Larangan Eksplisit**: Larang wewenang membuat atau mengubah `ClusterRole`, `ClusterRoleBinding`, atau meng-exec ke Pod produksi.
4. Gunakan OIDC Federation (GitHub OIDC Provider) agar GitHub Actions mendapatkan ephemeral token berumur 15 menit tanpa menyimpan file kubeconfig statis di repositori.

---

## 12. Trade-offs

| Pendekatan | Kelebihan | Kelemahan |
|---|---|---|
| **Role + RoleBinding per Namespace** | Isolasi total, tidak ada kebocoran antar namespace | Duplikasi manifest jika ada ratusan namespace |
| **ClusterRole + RoleBinding** | Reusability tinggi, satu definisi template dipaketkan ke banyak tenant | Perubahan pada ClusterRole akan berdampak ke seluruh tenant |
| **ClusterRoleBinding (Cluster-wide)** | Konfigurasi singkat untuk tim infra | Resiko keamanan masif jika akun developer diretas |
| **Wildcard Permission (`*`)** | Cepat untuk prototyping | Melanggar kepatuhan security & memudahkan privilege escalation |

---

## 13. When To Use
- Selalu gunakan kombinasi **ClusterRole + RoleBinding** untuk peran developer standar (`view`, `edit`, `operator`).
- Gunakan **`resourceNames`** ketika memberikan izin akses ke ConfigMap atau Secret spesifik bagi pipeline automation.
- Selalu pasang `automountServiceAccountToken: false` pada Pod yang tidak membutuhkan komunikasi ke Kubernetes API Server.

---

## 14. When NOT To Use
- **JANGAN PERNAH** memberikan `ClusterRoleBinding` dengan role `cluster-admin` ke developer aplikasi individual atau ServiceAccount workload umum.
- **JANGAN** menggunakan wildcard `verbs: ["*"]` dan `resources: ["*"]` kecuali untuk sistem cluster management primer.
- Hindari menyematkan izin `bind` atau `escalate` pada role kustom, karena memungkinkan pengguna menaikkan hak akses mereka sendiri menjadi root cluster (*Privilege Escalation*).

---

## 15. Common Mistakes
1. **Lupa bahwa `pods/exec` adalah Verb `create`**: Mengira bahwa membuka shell container membutuhkan verb `get` atau `update`. Di Kubernetes API, `exec` adalah subresource dan request-nya berupa subresource POST/create (`resources: ["pods/exec"]`, `verbs: ["create"]`).
2. **Membiarkan Token Default Terpasang di Setiap Pod**: Secara default, jika tidak dimatikan, setiap Pod akan me-mount ServiceAccount token di `/var/run/secrets/kubernetes.io/serviceaccount/token`. Jika web app memiliki celah Local File Inclusion (LFI), penyerang bisa mencuri token ini.
3. **Mengira Role Mengurangi Izin (Deny Rule)**: RBAC di Kubernetes adalah sistem **Pure Additive (Whitelist Only)**. Tidak ada konsep explicit "DENY" rule di RBAC. Jika ada satu Binding yang mengizinkan aksi, aksi tersebut lolos.

---

## 16. Best Practices
- **Must Have**: Nonaktifkan automount token jika tidak diperlukan:
  ```yaml
  apiVersion: v1
  kind: ServiceAccount
  metadata:
    name: worker-sa
  automountServiceAccountToken: false
  ```
- **Recommended**: Audit hak akses secara berkala menggunakan tool opensource seperti `rakkess` atau `kube-audit`.
- **Advanced**: Implementasikan **RBAC Aggregation** via label `rbac.authorization.k8s.io/aggregate-to-admin: "true"` untuk modularitas permission controller.
- **Avoid**: Memberikan wewenang verb `impersonate` ke user non-admin.

---

## 17. Troubleshooting Guide
```
Masalah: User mendapatkan error "403 Forbidden: User alex cannot get resource pods in API group '' in the namespace dev".
Penyebab 1: RoleBinding belum mengaitkan user 'alex' ke Role di namespace 'dev'.
Penyebab 2: User terhubung via sertifikat X.509 dengan Common Name (CN) atau Group (O) yang typo.
Diagnosa : kubectl auth can-i get pods --as alex -n dev
           kubectl get rolebindings -n dev -o yaml
Solusi   : Buat atau perbaiki RoleBinding yang mengarahkan subjek alex ke Role yang memiliki verb 'get' pada resource 'pods'.

Masalah: User memiliki hak get/list pods, tetapi tidak bisa melihat logs pod ("error: You must be logged in to the server (Unauthorized)").
Penyebab : Role hanya mendefinisikan resource 'pods', bukan subresource 'pods/log'.
Solusi   : Tambahkan 'pods/log' ke dalam daftar resources pada manifest Role.
```

---

## 18. Exercise
1. Buat ServiceAccount bernama `log-collector-sa` di namespace `monitoring`.
2. Buat Role bernama `log-reader-role` di namespace `monitoring` yang HANYA boleh membaca Pod dan logs Pod (`get`, `list`, `watch` pada `pods` dan `pods/log`).
3. Buat RoleBinding yang mengikat ServiceAccount tersebut ke Role.
4. Uji izin menggunakan perintah `kubectl auth can-i` untuk memastikan ServiceAccount tidak dapat melakukan `delete pods` atau `create pods`.

---

## 19. Challenge
Rancang arsitektur RBAC multi-tenant untuk 3 tim (`team-alpha`, `team-beta`, `team-shared`). Tim Alpha dan Beta hanya boleh mengelola Deployment dan Service di namespace masing-masing, tetapi kedua tim diizinkan membaca ConfigMap bersama di namespace `team-shared`. Tulis seluruh manifest deklaratifnya dan sertakan script validasi otomatis.

---

## 20. Summary
RBAC adalah pilar pertahanan utama API Server Kubernetes. Dengan memanfaatkan pemisahan tegas antara definisi peran (`Role`/`ClusterRole`) dan pengikatan peran ke subjek (`RoleBinding`/`ClusterRoleBinding`), serta menerapkan token proyeksi modern pada `ServiceAccount`, sistem dapat beroperasi dengan aman mematuhi *Principle of Least Privilege*.

---
[⬅️ BAB 07 Quiz & Challenge](../BAB-07-Storage-Persistence-dan-CSI/BAB-07-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Pod Security Standards & Webhooks ➡️](./Module-02-Pod-Security-Standards-dan-Admission-Webhooks.md)
---
