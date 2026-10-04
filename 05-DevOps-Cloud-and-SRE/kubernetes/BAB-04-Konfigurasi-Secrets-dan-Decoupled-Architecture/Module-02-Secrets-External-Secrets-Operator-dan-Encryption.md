# Module 02: Kubernetes Secrets, Secret Types, Encryption at Rest, dan External Secrets Operator (ESO)

---
[⬅️ Module 01: ConfigMaps & Downward API](./Module-01-ConfigMaps-Downward-API-dan-Hot-Reload.md) | [📋 Silabus Induk](../README.md) | [Evaluasi & Quiz BAB 04 ➡️](./BAB-04-Quiz-dan-Challenge.md)
---

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
1. Memahami arsitektur objek **Kubernetes Secrets** dan membongkar mitos keamanan seputar Base64 encoding (Base64 bukan enkripsi!).
2. Menguasai berbagai tipe rahasia standar: `Opaque`, `kubernetes.io/tls`, dan `kubernetes.io/dockerconfigjson`.
3. Mengonfigurasi **Encryption at Rest** pada Control Plane (`EncryptionConfiguration` menggunakan AES-CBC atau KMS Provider) untuk mengamankan data `etcd`.
4. Mengatasi tantangan GitOps pada manajemen secret (mencegah kredensial ter-commit ke repositori publik/privat).
5. Mengintegrasikan **External Secrets Operator (ESO)** dengan cloud secret vault (AWS Secrets Manager, HashiCorp Vault, GCP Secret Manager) via resource `SecretStore` dan `ExternalSecret`.
6. Membandingkan pendekatan ESO vs **Secrets Store CSI Driver** (in-memory volume mount tanpa membuat objek K8s Secret).

---

## 2. Prerequisite
- Memahami konsep ConfigMaps dan Volume Mounts ([Module 01 BAB 04](Module-01-ConfigMaps-Downward-API-dan-Hot-Reload.md)).
- Memahami konsep dasar kriptografi simetris (AES) vs asimetris (RSA/ECC) dan public/private key pairs.
- Pemahaman dasar arsitektur database `etcd` ([BAB 01 Module 01](../BAB-01-Arsitektur-Internal-dan-Control-Plane/Module-01-Arsitektur-Control-Plane-apiserver-etcd-controller-scheduler.md)).

---

## 3. Concept
Setiap sistem produksi membutuhkan data sensitif: password database, private key TLS/SSL, API token pembayaran, dan kredensial registry kontainer.

Kubernetes menyediakan objek primitif bernama **Secret**. Namun, terdapat kesalahpahaman umum yang sangat berbahaya di kalangan pemula:
> **"Data di dalam Secret berformat Base64, sehingga data saya sudah aman terenkripsi."**
> **FAKTA:** Base64 hanyalah algoritma encoding ASCII dua arah tanpa kunci (*obfuscation*), bukan enkripsi! Siapa pun yang memiliki akses baca dapat men-decode data tersebut dalam hitungan milidetik:
> `echo "cGFzc3dvcmQxMjM=" | base64 -d  # Output: password123`

Selain itu, secara default, database `etcd` menyimpan seluruh data Secret dalam format **Plaintext** pada disk host control plane! 

Oleh karena itu, arsitektur manajemen rahasia tingkat produksi enterprise menuntut dua perlindungan mutlak:
1. **Enkripsi di Tingkat Penyimpanan (Encryption at Rest)** di sisi Control Plane `etcd`.
2. **Sinkronisasi Eksternal Terisolasi (External Secrets Operator)** agar developer tidak pernah menyimpan file YAML secret di Git.

---

## 4. Why?
1. **Pencegahan Kebocoran Kredensial di GitOps**: Dengan maraknya adopsi GitOps (ArgoCD / Flux), seluruh manifest aplikasi disimpan di Git. Menaruh secret mentah di Git adalah penyebab nomor satu kebocoran data (*data breach*) di industri.
2. **Kepatuhan Regulasi (PCI-DSS, HIPAA, ISO 27001, SOC2)**: Lembaga audit keamanan mewajibkan seluruh kunci kriptografi dan password nasabah dienkripsi saat diam (*at-rest*) menggunakan Hardware Security Module (HSM) atau Cloud KMS.
3. **Rotasi Kredensial Terpusat (Centralized Secret Lifecycle)**: Mengubah password database di AWS Secrets Manager atau HashiCorp Vault secara otomatis menyinkronkan Secret baru ke ratusan Pod di kluster Kubernetes secara real-time tanpa campur tangan manusia.

---

## 5. What?
### Tipe-Tipe Standar Kubernetes Secret:

| Tipe Secret | Key yang Wajib Ada | Use Case Utama |
|---|---|---|
| **`Opaque`** (Default) | Bebas (*arbitrary user-defined keys*) | Password database, token API pihak ketiga, session secret. |
| **`kubernetes.io/tls`** | `tls.crt` dan `tls.key` | Sertifikat SSL/TLS untuk Ingress Controller HTTPS termination. |
| **`kubernetes.io/dockerconfigjson`** | `.dockerconfigjson` | Kredensial autentikasi penarikan image dari private registry (digunakan pada `imagePullSecrets`). |
| **`kubernetes.io/service-account-token`** | `token`, `ca.crt` | JWT token ServiceAccount internal Pod (K8s modern menggunakan TokenRequest API dinamis). |

---

## 6. How? Arsitektur External Secrets Operator (ESO)

```text
       [ Enterprise Cloud Vault: AWS Secrets Manager / Vault ]
       Secret: "prod/fintech/db-credentials" -> { "password": "SuperSecretKey999" }
                                  |
                                  v (Polling HTTPS via IAM Role / ServiceAccount)
+-----------------------------------------------------------------------------------+
|                        EXTERNAL SECRETS OPERATOR (ESO)                            |
|                                                                                   |
|  1. ClusterSecretStore / SecretStore                                              |
|     (Mendefinisikan koneksi aman & autentikasi ke AWS Secrets Manager)            |
|                                                                                   |
|  2. ExternalSecret CRD                                                            |
|     (Menentukan secret mana yang diambil & seberapa sering disinkronkan: 1m)      |
+-----------------------------------------------------------------------------------+
                                         |
                                         v (Reconciliation Loop: Auto-Generate)
+-----------------------------------------------------------------------------------+
|                     Native Kubernetes Secret (In-Memory / etcd)                   |
|  Nama: "payment-db-secret"                                                        |
|  data:                                                                            |
|    POSTGRES_PASSWORD: "U3VwZXJTZWNyZXRLZXk5OTk="                                  |
+-----------------------------------------------------------------------------------+
                                         |
                                         v (Injected via env / volume)
                            [ Pod Kontainer Aplikasi ]
```

---

## 7. Analogy
Bayangkan perbedaan antara brankas bank dan amplop surat:
- **Base64 Encoding** hanyalah menulis pesan rahasia di dalam amplop tertutup. Amplop itu tidak memiliki gembok. Siapa pun yang mengambil amplop bisa merobeknya dan langsung membaca isinya.
- **Encryption at Rest (`EncryptionConfiguration`)** adalah memasukkan seluruh kantor arsip bank ke dalam bunker lapis baja anti-bom. Meskipun pencuri berhasil menjebol dinding gedung (membaca raw disk disk host etcd), pencuri hanya menemukan tumpukan biner acak yang tidak bisa dibaca tanpa kunci master AWS KMS.
- **External Secrets Operator (ESO)** adalah kurir bersenjata khusus. Anda tidak menyimpan uang tunai di kantor cabang (Git). Uang tetap berada di brankas pusat (Vault). Saat kantor cabang butuh uang, kurir mengambilnya dari pusat dan menaruhnya di laci kasir kantor cabang secara otomatis.

---

## 8. Diagram: Plaintext etcd vs Enkripsi KMS Provider

```text
Tanpa Enkripsi (Default K8s):
Client ---> [ kube-apiserver ] ---> Simpan ke etcd: /registry/secrets/default/my-secret
                                    Isi data mentah di disk: {"password":"SuperSecretKey"}
                                    (Pencuri yang membobol backup etcd langsung dapat password!)

Dengan Enkripsi KMS (Production-Grade):
Client ---> [ kube-apiserver ]
                  |
                  v (Encrypt payload via gRPC socket)
         [ Cloud KMS Plugin: AWS KMS / Vault HSM ]
                  |
                  v (Menerima ciphertext terenkripsi: enc:kms:v1:8f9a2b...)
         Simpan ke disk etcd! (Data di storage 100% terenkripsi kuat AES-GCM)
```

---

## 9. Simple Example: Membuat Secret Tipe Opaque dan TLS

### 1. Secret Opaque (Password Database):
```bash
# Membuat secret langsung dari CLI (nilai otomatis di-base64)
kubectl create secret generic db-credentials \
  --from-literal=username=postgres_admin \
  --from-literal=password=SuperSafeP@ssw0rd2026

# Melihat data (akan muncul dalam bentuk base64)
kubectl get secret db-credentials -o jsonpath='{.data.password}' | base64 -d
# Output: SuperSafeP@ssw0rd2026
```

### 2. Secret TLS (Sertifikat SSL):
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: payment-tls-cert
  namespace: production
type: kubernetes.io/tls
data:
  # Base64 encoded cert dan key
  tls.crt: LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0t...
  tls.key: LS0tLS1CRUdJTiBSU0EgUFJJVkFURSBLRVkt...
```

---

## 10. Practical Example: Implementasi External Secrets Operator (ESO)

### 1. `SecretStore` (Menghubungkan ke AWS Secrets Manager):
```yaml
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: aws-secrets-manager
  namespace: production
spec:
  provider:
    aws:
      service: SecretsManager
      region: ap-southeast-1
      auth:
        jwt:
          serviceAccountRef:
            name: eso-irsa-serviceaccount # AWS IAM Roles for Service Accounts
```

### 2. `ExternalSecret` (Mendefinisikan Pemetaan Secret):
```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: payment-db-externalsecret
  namespace: production
spec:
  refreshInterval: "1h" # Cek update password setiap 1 jam
  secretStoreRef:
    name: aws-secrets-manager
    kind: SecretStore
  target:
    name: payment-db-native-secret # Nama native K8s Secret yang akan dibuat otomatis!
    creationPolicy: Owner
  data:
  - secretKey: DB_PASSWORD # Key di target K8s Secret
    remoteRef:
      key: prod/fintech/payment-db # Path remote di AWS Secrets Manager
      property: password
```

---

## 11. Real World Example: Konfigurasi Encryption at Rest pada `kube-apiserver`
Di server Linux control-plane, buat file konfigurasi `/etc/kubernetes/enc/encryption-config.yaml`:

```yaml
apiVersion: apiserver.config.k8s.io/v1
kind: EncryptionConfiguration
resources:
  - resources:
      - secrets
      - configmaps
    providers:
      - aescbc:
          keys:
            - name: key1
              secret: c2VjcmV0IGlzIGEgMzItYnl0ZSBmb28= # 32-byte base64 key
      - identity: {} # Fallback untuk data lawas yang belum terenkripsi
```

Pasang flag berikut pada pod static `kube-apiserver.yaml`:
```yaml
--encryption-provider-config=/etc/kubernetes/enc/encryption-config.yaml
```
Setelah apiserver di-restart, jalankan perintah migrasi paksa agar seluruh secret lama terenkripsi di etcd:
```bash
kubectl get secrets --all-namespaces -o json | kubectl replace -f -
```

---

## 12. Trade-offs: Pendekatan Manajemen Secret

| Pendekatan | Keamanan GitOps | Kompleksitas Setup | Otomasi Rotasi | Ketergantungan Eksternal |
|---|---|---|---|---|
| **Native K8s Secrets** | ❌ Terburuk (Bisa bocor di Git) | Sangat Rendah | Manual | Tidak Ada |
| **Bitnami Sealed Secrets** | ✅ Baik (Terenkripsi asimetris di Git) | Rendah | Butuh commit baru di Git | Membutuhkan SealedSecrets Controller |
| **External Secrets Operator** | ⭐ Terbaik (Zero secrets in Git) | Menengah | ✅ Otomatis (Polling) | Membutuhkan Cloud Vault (AWS/GCP/Vault) |
| **Secrets Store CSI Driver** | ⭐ Terbaik (Tidak pernah ada objek Secret di K8s) | Tinggi | ✅ Otomatis (Mount update) | Membutuhkan CSI driver daemonset |

---

## 13. When To Use
- Gunakan **External Secrets Operator (ESO)** sebagai standar de-facto untuk seluruh infrastruktur Kubernetes enterprise modern.
- Selalu aktifkan **Encryption at Rest** di level Control Plane pada seluruh kluster on-premise atau self-managed.
- Setel **`immutable: true`** pada Secret yang diproduksi oleh pipeline CI/CD untuk mencegah penimpaan yang tidak disengaja.

---

## 14. When NOT To Use
- Jangan pernah menyimpan file YAML secret yang berisi base64 di repositori GitHub/GitLab publik maupun privat tanpa enkripsi asimetris.
- Jangan gunakan Secret untuk data konfigurasi biasa yang tidak sensitif (gunakan **ConfigMap**).

---

## 15. Common Mistakes
1. **Mengira `base64` adalah enkripsi**: Developer men-commit file secret ke GitHub karena merasa string `dGVzdA==` sudah aman.
2. **Lupa memberikan izin IAM Role pada ESO**: Operator gagal menyinkronkan data dengan error `AccessDeniedException` dari AWS Secrets Manager.
3. **Mengabaikan permission file secret pada Volume Mount**: File secret di-mount dengan permission default `0644` sehingga proses non-root mana pun di kontainer bisa membaca file tersebut. Selalu setel `defaultMode: 0400`!

---

## 16. Best Practices
### Must Have
- Terapkan `defaultMode: 256` (izin oktal `0400` = Read-Only hanya untuk pemilik) saat me-mount Secret sebagai volume:
  ```yaml
  volumes:
  - name: secret-vol
    secret:
      secretName: db-secret
      defaultMode: 0400
  ```
- Amankan akses RBAC ke resource `secrets`: Hanya administrator dan ServiceAccount khusus yang diizinkan melakukan verb `get`, `list`, dan `watch` pada objek Secret.

### Recommended
- Gunakan cloud-managed Kubernetes (EKS, GKE, AKS) dengan integrasi KMS bawaan (*EKS Envelope Encryption with AWS KMS*).
- Pisahkan Secret ke namespace terisolasi per tim atau per domain aplikasi.

### Advanced
- Terapkan rotasi kredensial dinamis (*Dynamic Database Credentials*) menggunakan HashiCorp Vault, di mana setiap instance Pod menerima user/password PostgreSQL unik yang otomatis kedaluwarsa dalam 24 jam.

---

## 17. Troubleshooting Guide
### Problem 1: Pod gagal start dengan pesan `CreateContainerConfigError`
- **Penyebab**: Secret yang dideklarasikan di `secretKeyRef` tidak ada di namespace tersebut.
- **Diagnosa**:
  ```bash
  kubectl get secret <nama-secret> -n <namespace>
  kubectl describe pod <nama-pod>
  ```
- **Solusi**: Jika menggunakan ESO, periksa status ExternalSecret (`kubectl describe externalsecret <nama-es>`) untuk memastikan proses sinkronisasi dari cloud vault berhasil (`Status: SecretSynced`).

### Problem 2: ESO melempar error `SecretStore provider error`
- **Penyebab**: Kredensial IAM atau token akses ke HashiCorp Vault kedaluwarsa.
- **Solusi**: Periksa log pod ESO: `kubectl logs -n external-secrets -l app.kubernetes.io/name=external-secrets`.

---

## 18. Exercises
### Level: Easy
1. Buat Secret tipe Opaque yang memuat API token rahasia dari CLI:
   `kubectl create secret generic stripe-token --from-literal=STRIPE_KEY=sk_live_9482019482`
2. Ekstrak dan decode nilai token tersebut langsung dari terminal menggunakan `kubectl` dan `base64 -d`.

### Level: Medium
1. Buat Pod yang me-mount Secret tersebut sebagai file di `/var/secrets/stripe/key`.
2. Pastikan file tersebut hanya memiliki hak akses `0400` menggunakan parameter `defaultMode`.
3. Masuk ke dalam Pod menggunakan `kubectl exec` dan jalankan `ls -la /var/secrets/stripe/key` untuk memvalidasi izin file.

### Level: Hard
1. Buat Custom Resource `SecretStore` dan `ExternalSecret` simulasi.
2. Tuliskan manifest deployment aplikasi yang mengonsumsi native secret hasil sinkronisasi otomatis dari `ExternalSecret`.

---

## 19. Challenge
Rancang arsitektur Zero-Trust Secret Management untuk aplikasi perbankan di Kubernetes:
- Kredensial transaksi disimpan di HashiCorp Vault.
- Menggunakan External Secrets Operator dengan autentikasi Kubernetes ServiceAccount Token (JWT).
- Secret di-mount ke Pod dengan permission `0400` dan `read_only: true`.
- Seluruh data di etcd dienkripsi menggunakan provider KMS.
Tuliskan diagram alur, konfigurasi `EncryptionConfiguration`, dan manifest `SecretStore` serta `ExternalSecret` terpadu.

---

## 20. Summary
- **Base64 hanyalah encoding**, bukan enkripsi. Objek Secret Kubernetes membutuhkan proteksi tambahan.
- **Encryption at Rest** di Control Plane memastikan data yang disimpan di database `etcd` terenkripsi kuat menggunakan AES atau KMS HSM.
- **External Secrets Operator (ESO)** adalah standar industri untuk menjauhkan kredensial rahasia dari repositori GitOps.
- Selalu amankan izin file secret di dalam kontainer menggunakan `defaultMode: 0400`.

---
[⬅️ Module 01: ConfigMaps & Downward API](./Module-01-ConfigMaps-Downward-API-dan-Hot-Reload.md) | [📋 Silabus Induk](../README.md) | [Evaluasi & Quiz BAB 04 ➡️](./BAB-04-Quiz-dan-Challenge.md)
---
