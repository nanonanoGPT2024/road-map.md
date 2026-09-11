# Module 02: Ingress Controller, ConfigMaps, Secrets, & Helm Package Management

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar akan mampu:
1. Memahami peran **Ingress Controller** (Nginx Ingress / Traefik) sebagai gerbang routing HTTP/S layer-7 terpusat.
2. Memisahkan kode program dari konfigurasi menggunakan **ConfigMaps** dan mengamankan kredensial sensitif menggunakan **Secrets** (Opaque, TLS, base64).
3. Mengotomatiskan manajemen rilis dan templating manifest Kubernetes menggunakan **Helm Charts** (`Chart.yaml`, `values.yaml`, templates Go).
4. Mengimplementasikan integrasi otomatisasi sertifikat SSL/TLS menggunakan **Cert-Manager** dan Let's Encrypt ACME.

---

## 2. Prerequisite
- Memahami konsep Service ClusterIP dan Deployments dari [BAB 04 Module 01](file:///d:/explore/roadmap.sh%20materi/DevOps/BAB-04-Kubernetes-Orchestration/Module-01-Arsitektur-Control-Plane-Pods-Deployments-Service-Networking.md).
- Mengetahui cara kerja Reverse Proxy dan Host header routing dari [BAB 02 Module 02](file:///d:/explore/roadmap.sh%20materi/DevOps/BAB-02-Jaringan-Protokol-dan-Web-Servers/Module-02-Reverse-Proxy-Load-Balancing-Nginx-Envoy.md).

---

## 3. Concept
Pada skala enterprise, menulis puluhan file YAML mentah secara manual untuk setiap microservice memicu masalah serius:
1. **Redundansi Konfigurasi**: 95% baris YAML antara environment dev, staging, dan prod identik. Copy-paste manual memicu kesalahan manusia (*human error*).
2. **Keterpaparan Password**: Menyimpan password database langsung di dalam file YAML Git repository sangat berbahaya.
3. **Biaya Load Balancer**: Menggunakan Service `type: LoadBalancer` untuk 50 microservices berarti menyewa 50 Public Load Balancer terpisah di AWS/GCP (biaya ribuan dolar per bulan).

Solusi arsitektur Kubernetes modern:
- **Ingress Controller**: 1 buah Load Balancer publik layer-7 yang merutekan ribuan domain dan sub-path URL (`api.domain.com`, `auth.domain.com/login`) ke Service internal yang sesuai.
- **ConfigMap & Secret**: Mengabstraksikan environment variable dan token rahasia secara terpisah dari Pod image.
- **Helm**: *The package manager for Kubernetes* (seperti `apt` atau `npm` untuk K8s) yang memungkinkan pembuatan template dinamis (*parameterized charts*) dengan file `values.yaml`.

---

## 4. Why?
Mengapa komponen ini adalah standar industri?
1. **Efisiensi Biaya Signifikan**: 1 Ingress Controller menggantikan puluhan Cloud Load Balancers, memangkas tagihan cloud hingga 80%.
2. **Prinsip 12-Factor App (Config Separation)**: Image container yang sama persis dapat dideploy ke dev, staging, dan production hanya dengan mengubah file `values-env.yaml`.
3. **Rollback Rilis Instan**: Helm mencatat riwayat rilis (`helm history`) dan memungkinkan rollback 1 baris perintah (`helm rollback myapp 2`) jika terjadi regresi.

---

## 5. What?
Komponen arsitektur:
- **Ingress Resource**: Aturan perutean HTTP/S (Host, Path, Backend Service).
- **Ingress Controller**: Daemon (seperti Nginx Ingress atau Envoy) yang terus membaca objek Ingress dan memperbarui konfigurasi routing proxy secara dinamis.
- **ConfigMap**: Objek penyimpan data non-sensitif (key-value plain text atau file konfigurasi penuh seperti `nginx.conf`).
- **Secret**: Objek penyimpan data sensitif (password, private key, token API) yang di-encode base64 dan disimpan terenkripsi di `etcd`.
- **Anatomi Helm Chart**:
  - `Chart.yaml`: Metadata nama chart dan versi.
  - `values.yaml`: Nilai default variabel parameter.
  - `templates/`: File YAML manifest dengan sintaks template engine Go (`{{ .Values.replicaCount }}`).

---

## 6. How?
Alur kerja Helm dan Ingress dalam siklus rilis:

```text
[ Developer: helm upgrade --install myapp ./chart -f values-prod.yaml ]
                                  │
                                  ▼
[ Helm Engine Melakukan Render Template Go dengan Nilai values-prod ]
                                  │
                                  ▼
[ Menghasilkan Manifest YAML Utuh & Mengirim ke kube-apiserver ]
  ├── Secret: DB Credentials (Terenkripsi)
  ├── ConfigMap: API Endpoints
  ├── Deployment: 5 Replicas (Image: v2.1.0)
  ├── Service: ClusterIP :80
  └── Ingress: Host: api.company.com -> Service:80
                                  │
                                  ▼
[ Ingress Controller Mendeteksi Aturan Baru & Reload Routing Tanpa Reload Pod ]
                                  │
                                  ▼
[ Traffic Publik https://api.company.com Diteruskan Mulus ke Pods Baru ]
```

---

## 7. Analogy
Bayangkan **Helm & Ingress Controller** seperti **Pabrik Percetakan & Kantor Pos Terpadu**:
- **Helm**: Seperti cetakan formulir stempel stensil. Anda tidak perlu menulis ulang 10 halaman dokumen dari nol; Anda hanya mengisi bagian kosong nama dan tanggal (`values.yaml`), lalu mesin stempel mencetak dokumen lengkap dalam sekejap.
- **Ingress Controller**: Seperti Kantor Pos Pusat. Surat dari seluruh dunia tiba di satu alamat gerbang utama, lalu petugas pos memilah berdasarkan nama jalan (`Host: api.com`) dan nomor rumah (`Path: /v1`) untuk diantarkan ke meja kamar yang tepat.

---

## 8. Diagram
```text
Public Traffic: https://shop.acme.com  &  https://api.acme.com
                            │
                            ▼
+-------------------------------------------------------------+
|               CLOUD LOAD BALANCER (Single Public IP)        |
+-------------------------------------------------------------+
                            │
                            ▼
+-------------------------------------------------------------+
|             KUBERNETES INGRESS CONTROLLER (Nginx)           |
|                                                             |
|  Rule 1: shop.acme.com  --> Service: frontend-svc:80        |
|  Rule 2: api.acme.com   --> Service: backend-svc:3000       |
|  TLS: Automatic renewal via Cert-Manager (Let's Encrypt)    |
+-------------------------------------------------------------+
           |                                  |
           v                                  v
+----------------------+          +----------------------+
| Service: frontend    |          | Service: backend     |
| (ClusterIP)          |          | (ClusterIP)          |
+----------------------+          +----------------------+
```

---

## 9. Simple Example
Manifest Ingress dengan TLS Certificate (`ingress.yaml`):

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: main-ingress
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - api.example.com
    secretName: api-tls-cert
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: api-service
            port:
              number: 80
```

---

## 10. Practical Example
Template Helm `templates/deployment.yaml` menggunakan parameter `values.yaml`:

```yaml
# values.yaml
replicaCount: 3
image:
  repository: acmecorp/order-service
  tag: "1.4.0"
resources:
  limits:
    memory: "256Mi"
  requests:
    memory: "128Mi"
```

```yaml
# templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Release.Name }}-deployment
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      app: {{ .Release.Name }}
  template:
    metadata:
      labels:
        app: {{ .Release.Name }}
    spec:
      containers:
      - name: app
        image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
        envFrom:
        - configMapRef:
            name: {{ .Release.Name }}-config
        - secretRef:
            name: {{ .Release.Name }}-secret
        resources:
          {{- toYaml .Values.resources | nindent 10 }}
```

---

## 11. Real World Example
### Kasus: Kebocoran Secret di Public GitHub & Solusi External Secrets Operator
1. Seorang junior engineer tidak sengaja meng-commit manifest K8s `secret.yaml` yang berisi password database base64 ke public repository.
2. Bot peretas mendeteksi kredensial tersebut dalam 3 menit dan mencuri data pelanggan.
3. Mengapa? Karena nilai pada Secret K8s bawaan hanyalah encode **Base64 (bukan enkripsi!)**; siapa pun bisa men-decode dengan `echo "cGFzc3dvcmQ=" | base64 -d`.
4. **Solusi DevSecOps Modern**:
   - Terapkan **External Secrets Operator (ESO)** atau **Sealed Secrets**.
   - Secret disimpan di AWS Secrets Manager / HashiCorp Vault.
   - Kubernetes secara dinamis menarik secret ke dalam cluster saat runtime tanpa pernah menyimpan password di file Git repository.

---

## 12. Trade-offs
| Pendekatan Manajemen Manifest | Raw YAML (`kubectl apply -f`) | Helm Charts |
|---|---|---|
| **Kompleksitas Awal** | Sangat mudah (cukup baca 1 file YAML) | Memerlukan pemahaman struktur chart & Go templating |
| **Pengelolaan Multi-Environment** | Buruk (harus copy-paste file berbeda tiap dev/prod) | Sangat baik (cukup ganti file `values-prod.yaml`) |
| **Kemampuan Rollback** | Terbatas (harus manual via commit git lama) | Sangat mudah (`helm rollback <release> <rev>`) |
| **Kesesuaian** | Uji coba cepat / lab lokal 1 service | Sistem microservices produksi skala menengah-besar |

---

## 13. When To Use
- Gunakan **Helm**: Untuk memaketkan aplikasi microservices perusahaan, mendistribusikan software ke cluster pelanggan, atau menginstal tool pihak ketiga (Prometheus, cert-manager, ArgoCD) via public artifact hub.
- Gunakan **Ingress Controller**: Untuk semua aplikasi web produksi yang menerima traffic publik dari internet.

---

## 14. When NOT To Use
- Jangan gunakan Ingress HTTP layer-7 untuk traffic non-HTTP (seperti koneksi database TCP mentah atau protokol VoIP UDP); gunakan Service `type: LoadBalancer` layer-4 atau Gateway API.

---

## 15. Common Mistakes
1. **Menganggap Secret K8s Sudah Terenkripsi Secara Default**: Nilai secret di manifest hanyalah string base64. Jika etcd tidak dikonfigurasi dengan *encryption at rest*, kredensial dapat dibaca oleh siapa pun yang memiliki akses read etcd.
2. **Tidak Menggunakan Helm Dependency Lock**: Tidak mengunci versi sub-chart di `Chart.lock`, menyebabkan build produksi gagal saat upstream dependency memperbarui versinya secara tak terduga.
3. **Typo pada Ingress `pathType`**: Menggunakan `pathType: ImplementationSpecific` tanpa memahami behavior Ingress controller, menyebabkan URL routing mengembalikan error 404.

---

## 16. Best Practices
### Must Have
- Selalu gunakan `pathType: Prefix` pada Ingress untuk rute standar.
- Jangan pernah menyimpan file Secret K8s plaintext di dalam version control Git (gunakan GitOps secrets vault).
- Definisikan `linter` Helm (`helm lint`) pada pipeline CI/CD sebelum deployment.

### Recommended
- Gunakan `cert-manager` untuk otomatisasi penerbitan dan pembaruan sertifikat TLS Let's Encrypt.
- Gunakan `helm diff` plugin untuk memvalidasi perubahan manifest sebelum mengeksekusi `helm upgrade`.

### Avoid / Overengineering
- Jangan membuat template Helm yang terlalu abstrak dengan ratusan parameter logika `if-else` bersarang yang sulit dibaca developer lain.

---

## 17. Troubleshooting
| Gejala | Kemungkinan Penyebab | Solusi |
|---|---|---|
| Domain Ingress mengembalikan `404 Not Found` | Service target salah port atau nama Service tidak cocok dengan Ingress spec | Periksa `kubectl describe ingress` dan pastikan nama Service & Port persis sama |
| Ingress controller tidak mengalokasikan ADDRESS IP | Ingress controller belum terinstal atau Service LoadBalancer-nya masih Pending | Periksa status pod ingress controller: `kubectl get pods -n ingress-nginx` |
| Helm upgrade gagal dengan pesan *release has no deployed releases* | Rilis Helm sebelumnya gagal di tengah jalan dan berstatus `pending-upgrade` | Hapus secret rilis atau jalankan rollback ke revisi sukses sebelumnya |

---

## 18. Exercise
1. Buat ConfigMap berisi konfigurasi key-value `ENVIRONMENT=production` dan `LOG_LEVEL=info`.
2. Pasang ConfigMap tersebut ke dalam Deployment Pod menggunakan direktif `envFrom`.

---

## 19. Challenge
Rancang arsitektur simulasi **Helm Templating & Ingress Routing Engine**:
- Buat template renderer yang menggabungkan file `values.yaml` dengan manifest template.
- Simulasikan Ingress controller yang menerima HTTP request, membaca header `Host`, dan meneruskan payload ke Service backend yang tepat.

---

## 20. Summary
- Ingress Controller memusatkan traffic masuk layer-7, menghemat biaya public IP dan load balancer.
- ConfigMaps dan Secrets memisahkan konfigurasi dari kode aplikasi sesuai prinsip *12-Factor App*.
- Helm menyediakan templating deklaratif, standardisasi rilis, dan kemudahan rollback di seluruh cluster.
- Modul praktikum lab dapat dijalankan langsung di [hands-on/m02/helm_ingress_template_sim.js](file:///d:/explore/roadmap.sh%20materi/DevOps/BAB-04-Kubernetes-Orchestration/hands-on/m02/helm_ingress_template_sim.js).
