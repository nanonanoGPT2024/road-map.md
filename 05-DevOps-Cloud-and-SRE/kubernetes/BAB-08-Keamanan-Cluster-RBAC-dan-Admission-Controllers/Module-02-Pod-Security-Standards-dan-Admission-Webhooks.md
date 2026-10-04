---
[⬅️ Module 01: RBAC & Least Privilege](./Module-01-RBAC-Roles-ClusterRoles-dan-Least-Privilege.md) | [📋 Silabus Induk](../README.md) | [BAB 08 Quiz & Challenge ➡️](./BAB-08-Quiz-dan-Challenge.md)
---

# Module 02: Pod Security Standards (PSS/PSA) & Dynamic Admission Webhooks

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Memahami secara mendalam fase eksekusi request di `kube-apiserver`: *Authentication* $\rightarrow$ *Authorization* $\rightarrow$ *Mutating Webhooks* $\rightarrow$ *Object Validation* $\rightarrow$ *Validating Webhooks* $\rightarrow$ *etcd*.
- Menganalisis alasan depresiasi `PodSecurityPolicy` (PSP) dan adopsi standar pengganti resmi: **Pod Security Standards (PSS)** dan **Pod Security Admission (PSA)**.
- Mengonfigurasi 3 level profil PSS (`Privileged`, `Baseline`, `Restricted`) dan 3 mode aksi (`enforce`, `audit`, `warn`) via label namespace.
- Menguasai arsitektur dan daur hidup **Dynamic Admission Controllers**: `MutatingAdmissionWebhook` dan `ValidatingAdmissionWebhook`.
- Mengimplementasikan spesifikasi kontrak JSON `AdmissionReview` (Request & Response) dengan mekanisme TLS mutual dan `caBundle`.
- Memahami dampak operasional kritis dari `failurePolicy: Fail` vs `failurePolicy: Ignore` untuk ketersediaan cluster (*cluster availability*).

---

## 2. Prerequisite
- Memahami RBAC dan siklus otorisasi Kubernetes API (Modul 01).
- Memahami Linux security primitives: Capabilities (`CAP_SYS_ADMIN`, `CAP_NET_ADMIN`), UID/GID, Seccomp, AppArmor, dan cgroups.
- Pemahaman protokol HTTPS/TLS dan sertifikat X.509.

---

## 3. Concept
Meskipun sebuah akun developer memiliki izin RBAC untuk membuat Pod di suatu namespace, izin tersebut belum tentu aman. Developer yang ceroboh atau penyerang dapat men-deploy Pod dengan konfigurasi:
`securityContext.privileged: true` atau `hostNetwork: true` atau me-mount root filesystem host `/` via `hostPath`.
Konfigurasi ini memberikan akses setara root mesin fisik Linux kepada container, memicu pembobolan cluster (*cluster breakout / container escape*).

Untuk mencegah hal tersebut, Kubernetes menyediakan mekanisme pengamanan tingkat kedua: **Admission Control**.

```
                           KUBE-APISERVER PIPELINE
                                      |
                           [ Incoming HTTP Request ]
                                      |
                                      v
                           [ 1. Authentication ]
                                      |
                                      v
                           [ 2. Authorization (RBAC) ]
                                      |
                         =============v=============
                         |    ADMISSION PHASE      |
                         |                         |
                         |  [ 3. Mutating Webhooks ]   <---> Webhook Service (Modifies YAML)
                         |            |            |
                         |  [ 4. Schema Validation ]
                         |            |            |
                         |  [ 5. Validating Webhooks ] <---> Webhook Service (Allow / Deny)
                         |            |            |
                         |  [ 6. Built-in PSA ]    |
                         ===========================
                                      |
                                      v
                              [ Persist to etcd ]
```

---

## 4. Why?
Mengapa Pod Security Admission dan Admission Webhooks sangat vital?
1. **Pencegahan Container Breakout**: Mencegah container berjalan sebagai user root (UID 0), mematikan flag `allowPrivilegeEscalation`, dan memblokir mounting filesystem host yang sensitif (`/etc`, `/var/run/docker.sock`).
2. **Automated Policy Enforcement**: Platform engineering dapat memaksakan standard organisasi secara otomatis (misal: "Setiap Pod wajib mencantumkan label `cost-center`" atau "Image container dilarang menggunakan tag `:latest`").
3. **Transparent Sidecar Injection**: Mutating webhook memungkinkan injeksi otomatis sidecar proxy (seperti Envoy pada Istio/Linkerd) atau security monitoring agent tanpa mewajibkan developer menulis boilerplate sidecar di setiap manifest aplikasi.

---

## 5. What?

### A. Tiga Profil Pod Security Standards (PSS)
Kubernetes mendefinisikan 3 level profil keamanan resmi:

| Profil | Deskripsi | Aturan Utama | Use Case |
|---|---|---|---|
| **Privileged** | Tanpa batasan keamanan sama sekali. | Mengizinkan `privileged: true`, `hostNetwork`, `hostPID`, dan akses root host. | CNI daemon (Calico, Cilium), CSI node driver, kube-proxy. |
| **Baseline** | Mencegah eskalasi hak istimewa yang diketahui dengan batasan minimal. | Melarang `privileged: true`, melarang `hostNetwork`/`hostPID`, melarang `hostPath` berbahaya. | Aplikasi backend standar legacy yang masih butuh root container. |
| **Restricted** | Praktik terbaik pengerasan keamanan tingkat tinggi (*hardened*). | Wajib `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, drop ALL Linux capabilities, root filesystem read-only, seccomp profile `RuntimeDefault`. | Workload microservice modern, multi-tenant cluster perbankan. |

### B. Tiga Mode Pod Security Admission (PSA)
Label namespace mengontrol penegakan profil PSS:
- **`pod-security.kubernetes.io/enforce`**: Menolak (*reject*) Pod jika melanggar profil yang ditentukan. Pod tidak akan pernah dibuat.
- **`pod-security.kubernetes.io/warn`**: Mengizinkan Pod dibuat, tetapi menampilkan pesan peringatan (*warning alert*) di terminal `kubectl` developer.
- **`pod-security.kubernetes.io/audit`**: Mengizinkan Pod dibuat, tetapi mencatat pelanggaran ke dalam log audit Kubernetes untuk analisis tim Security Operations Center (SOC).

---

## 6. How?

### A. Mengaktifkan Pod Security Admission via Label Namespace
Cukup berikan label deklaratif pada namespace target:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: payment-production
  labels:
    # Tolak pembuatan pod yang melanggar standar Restricted
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/enforce-version: latest
    # Tampilkan warning di CLI jika melanggar standar Restricted
    pod-security.kubernetes.io/warn: restricted
    pod-security.kubernetes.io/warn-version: latest
    # Catat ke log audit
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/audit-version: latest
```

Jika developer mencoba membuat Pod berikut di namespace `payment-production`:
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: insecure-pod
  namespace: payment-production
spec:
  containers:
    - name: nginx
      image: nginx:latest
      securityContext:
        privileged: true # DITOLAK OLEH K8S API SERVER!
```
API Server akan langsung merespons dengan error:
```text
Error from server (Forbidden): pods "insecure-pod" is forbidden: 
violates PodSecurity "restricted:latest": privileged (container "nginx" must not set securityContext.privileged=true)
```

### B. Anatomi Validating Admission Webhook
Ketika aturan bisnis organisasi terlalu spesifik untuk PSS (misal: "Hanya izinkan image dari private registry `registry.perusahaan.com`"), kita menggunakan Dynamic Admission Webhook.

```yaml
# validating-webhook-config.yaml
apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingWebhookConfiguration
metadata:
  name: image-registry-policy-webhook
webhooks:
  - name: validate-registry.company.com
    rules:
      - apiGroups: [""]
        apiVersions: ["v1"]
        operations: ["CREATE", "UPDATE"]
        resources: ["pods"]
        scope: "Namespaced"
    clientConfig:
      service:
        name: policy-webhook-service
        namespace: security-system
        path: "/validate-pod"
        port: 443
      caBundle: LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCg==... # Base64 encoded CA cert
    admissionReviewVersions: ["v1"]
    sideEffects: None
    timeoutSeconds: 3
    failurePolicy: Fail # Atau 'Ignore'
    namespaceSelector:
      matchExpressions:
        - key: kubernetes.io/metadata.name
          operator: NotIn
          values: ["kube-system", "security-system"] # Hindari memblokir pod sistem!
```

---

## 7. Analogy
Bayangkan **Pemeriksaan Keamanan Bandara Internasional**:
1. **Tiket Masuk & Paspor (RBAC)**: Memeriksa apakah Anda memiliki tiket penerbangan yang sah ke kota tujuan.
2. **Mutating Webhook (Petugas Bea Cukai & Maskapai)**: Secara otomatis menempelkan stiker bagasi (*luggage tag*) dan menyematkan barcode penerbangan pada paspor Anda sebelum Anda berjalan ke gate.
3. **Validating Webhook (Mesin X-Ray & Metal Detector)**: Memeriksa seluruh isi koper Anda. Jika ada barang terlarang (misal: senjata tajam / `privileged: true`), Anda langsung dilarang masuk dan diusir dari bandara.
4. **`failurePolicy: Fail`**: Jika mesin X-Ray rusak mati lampu, seluruh penerbangan dihentikan demi keamanan nasional.
5. **`failurePolicy: Ignore`**: Jika mesin X-Ray rusak, penumpang dipersilakan lewat begitu saja (berisiko tinggi).

---

## 8. Diagram

```
+---------------------------------------------------------------------------------+
|                 DYNAMIC ADMISSION WEBHOOK LIFECYCLE (JSON RPC)                  |
+---------------------------------------------------------------------------------+

User (kubectl apply) ---> kube-apiserver
                               |
                               | 1. HTTP POST /validate-pod
                               |    (Payload: AdmissionReview Request)
                               v
               +-------------------------------+
               | Admission Webhook Server Pod  |
               | (Custom Go / Node.js Service) |
               +-------------------------------+
                               |
                               | 2. Evaluates Pod Spec:
                               |    - Is image from authorized registry?
                               |    - Are CPU/Memory limits configured?
                               |
                               | 3. HTTP 200 OK (AdmissionResponse)
                               |    {
                               |      "uid": "705ab7f5-...",
                               |      "allowed": false,
                               |      "status": {
                               |        "message": "Image must be from harbor.corp.internal"
                               |      }
                               |    }
                               v
                      kube-apiserver
                               |
             +-----------------+-----------------+
             |                                   |
      (If Allowed)                        (If Rejected)
             |                                   |
             v                                   v
      Write to etcd                       Return 403 Forbidden to User
```

---

## 9. Simple Example: Hardened Pod Spec (Restricted Standard Compliant)

Berikut adalah contoh manifest Pod yang memenuhi 100% persyaratan standar **PSS Restricted**:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: secure-web-app
  namespace: payment-production
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 10001
    runAsGroup: 10001
    fsGroup: 10001
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: web
      image: caddy:2.7-alpine
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities:
          drop:
            - ALL
      volumeMounts:
        - name: tmp-cache
          mountPath: /tmp
  volumes:
    - name: tmp-cache
      emptyDir: {}
```

---

## 10. Practical Example: Format Payload AdmissionReview v1

Webhook server berkomunikasi dengan API Server menggunakan format JSON standar:

### A. Payload Permintaan (Request dikirim oleh K8s API Server)
```json
{
  "apiVersion": "admission.k8s.io/v1",
  "kind": "AdmissionReview",
  "request": {
    "uid": "705ab7f5-6393-11e8-b7cc-42010a800002",
    "kind": { "group": "", "version": "v1", "kind": "Pod" },
    "resource": { "group": "", "version": "v1", "resource": "pods" },
    "namespace": "production",
    "operation": "CREATE",
    "userInfo": { "username": "alice@company.com" },
    "object": {
      "metadata": { "name": "backend-pod" },
      "spec": {
        "containers": [{ "name": "app", "image": "my-registry.io/app:v1.0" }]
      }
    }
  }
}
```

### B. Payload Respons (Dikirim kembali oleh Webhook Server)
```json
{
  "apiVersion": "admission.k8s.io/v1",
  "kind": "AdmissionReview",
  "response": {
    "uid": "705ab7f5-6393-11e8-b7cc-42010a800002",
    "allowed": true,
    "status": {
      "code": 200,
      "message": "Pod lulus seluruh pemeriksaan keamanan policy compliance."
    }
  }
}
```

---

## 11. Real World Example: OPA Gatekeeper vs Kyverno
Membangun dan me-maintain server webhook sendiri dengan Go/Node.js membutuhkan sertifikat TLS yang harus di-rotate setiap tahun dan penanganan HA yang rumit. Industri saat ini menggunakan Policy Engine siap pakai:

1. **Kyverno**: Kubernetes-native policy engine. Policy ditulis menggunakan deklarasi YAML standar Kubernetes tanpa perlu mempelajari bahasa pemrograman baru. Sangat populer karena kemudahan deklaratifnya.
2. **Open Policy Agent (OPA) Gatekeeper**: Policy ditulis menggunakan bahasa deklaratif **Rego**. Sangat powerful untuk evaluasi logika kompleks lintas-sumber daya (misal: "Cek apakah ada Ingress lain yang sudah memakai host domain yang sama di namespace lain").

---

## 12. Trade-offs

| Aspek | failurePolicy: Fail | failurePolicy: Ignore |
|---|---|---|
| **Postur Keamanan** | Sangat Tinggi (Jika webhook mati, tidak ada resource liar yang bisa masuk) | Rendah (Jika webhook mati, semua request lolos tanpa seleksi) |
| **Ketersediaan Cluster** | Berisiko (Jika Pod webhook crash, tidak ada Pod baru yang bisa dibuat di cluster) | Tinggi (Operasi cluster tetap berjalan meski webhook mengalami downtime) |
| **Penggunaan Ideal** | Production Namespace dengan data sensitif | Development / Sandbox Namespace |

---

## 13. When To Use
- Selalu aktifkan profil **PSS Baseline** atau **Restricted** pada seluruh namespace produksi non-infrastruktur.
- Gunakan **Mutating Webhook** untuk menyematkan label audit, proxy sidecar, atau batas resource request/limits default.
- Gunakan **Validating Webhook** untuk menegakkan aturan nama domain, registry image whitelisting, dan kepatuhan label kepemilikan tim.

---

## 14. When NOT To Use
- **JANGAN** memasang `failurePolicy: Fail` pada namespace `kube-system`, karena jika webhook crash, Kubelet tidak akan bisa membuat Pod CoreDNS, CNI, atau bahkan Pod Webhook itu sendiri (*Deadlock / Cluster bricked*).
- Jangan memvalidasi hal-hal yang memakan waktu lama (seperti memindai kerentanan image security scan di dalam alur synchronous admission webhook), karena timeout webhook default adalah 10 detik. Jika melebihi timeout, API request akan dibatalkan.

---

## 15. Common Mistakes
1. **Deadlock Webhook Pod**: Menjalankan Pod webhook di namespace yang sama dengan target validasi webhook ber-mode `failurePolicy: Fail`. Saat Pod webhook di-restart, API server tidak bisa me-restart pod tersebut karena webhook-nya sedang mati!
2. **Lupa CA Bundle TLS**: Kubernetes API Server mewajibkan endpoint webhook menggunakan HTTPS dengan sertifikat TLS yang valid. Mengisi `caBundle` yang salah atau kedaluwarsa akan menghasilkan error: `x509: certificate signed by unknown authority`.
3. **Mengabaikan Root Filesystem Writable**: Banyak pengembang men-deploy Pod tanpa `readOnlyRootFilesystem: true`, memungkinkan penyerang mengunduh biner malware cryptominer langsung ke dalam container saat terjadi eksploitasi RCE.

---

## 16. Best Practices
- **Must Have**: Pasang `namespaceSelector` untuk selalu mengecualikan `kube-system` dari pengawasan custom admission webhook:
  ```yaml
  namespaceSelector:
    matchExpressions:
      - key: kubernetes.io/metadata.name
        operator: NotIn
        values: ["kube-system"]
  ```
- **Recommended**: Jalankan minimal 3 replika untuk Admission Webhook Server dengan `PodDisruptionBudget` dan `topologySpreadConstraints`.
- **Advanced**: Implementasikan mode `warn` dan `audit` selama 30 hari sebelum menaikkan profil PSS menjadi `enforce` untuk mencegah breaking changes pada tim developer.
- **Avoid**: Mengatur `timeoutSeconds` lebih besar dari 5 detik.

---

## 17. Troubleshooting Guide
```
Masalah: Semua perintah 'kubectl create' atau 'helm install' gagal dengan error: "Internal error occurred: failed calling webhook 'xxx': dial tcp: i/o timeout".
Penyebab : Pod webhook sedang down, atau NetworkPolicy memblokir traffic dari Control Plane ke Service webhook, sementara failurePolicy diset ke 'Fail'.
Diagnosa : kubectl get pods -n <webhook-ns>
           Periksa apakah API Server dapat menjangkau port webhook.
Solusi   : Untuk recovery darurat, ubah sementara failurePolicy menjadi 'Ignore' atau hapus objek ValidatingWebhookConfiguration:
           kubectl delete validatingwebhookconfiguration <nama-webhook>

Masalah: Pod ditolak dengan pesan: "violates PodSecurity: restricted:latest: seccompProfile (container xxx must set securityContext.seccompProfile.type to 'RuntimeDefault' or 'Localhost')".
Penyebab : Pod belum mendefinisikan seccomp profile yang diwajibkan oleh standar Restricted.
Solusi   : Tambahkan spesifikasi securityContext berikut pada Pod:
           securityContext:
             seccompProfile:
               type: RuntimeDefault
```

---

## 18. Exercise
1. Buat namespace `stage-secure` dan sematkan label PSS mode `enforce: restricted`.
2. Tulis manifest Pod sederhana yang melanggar aturan Restricted (misal: menjalankan container dengan UID 0 / root). Jalankan `kubectl apply` dan amati pesan penolakan dari API Server.
3. Perbaiki konfigurasi Pod tersebut dengan menambahkan `securityContext` yang sesuai (`runAsNonRoot: true`, `seccompProfile`, drop capabilities) hingga Pod berhasil berjalan.

---

## 19. Challenge
Rancang arsitektur webhook validasi (bisa menggunakan Kyverno atau pseudocode webhook) yang menolak pembuatan Deployment jika:
1. Replica count bernilai kurang dari 2 di namespace `production`.
2. Image container menggunakan tag `:latest` atau tidak memiliki sha256 digest hash.
3. Container tidak memiliki `resources.limits.memory` yang terdefinisi.
Tuliskan manifest konfigurasi kebijakannya secara lengkap!

---

## 20. Summary
Pod Security Standards (PSS) dan Dynamic Admission Webhooks memberikan lapisan pertahanan terpadu yang menutup celah antara otorisasi pengguna (RBAC) dan keamanan runtime container Linux. Dengan menerapkan profiling PSS secara terukur dan memanfaatkan webhook validasi secara higienis, cluster enterprise dapat terlindungi dari risiko container breakout dan konfigurasi keliru yang fatal.

---
[⬅️ Module 01: RBAC & Least Privilege](./Module-01-RBAC-Roles-ClusterRoles-dan-Least-Privilege.md) | [📋 Silabus Induk](../README.md) | [BAB 08 Quiz & Challenge ➡️](./BAB-08-Quiz-dan-Challenge.md)
---
