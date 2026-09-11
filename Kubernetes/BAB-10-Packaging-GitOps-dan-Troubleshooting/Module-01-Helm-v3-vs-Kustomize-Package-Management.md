---
[⬅️ BAB 09 Quiz & Challenge](../BAB-09-Scheduling-Lanjutan-dan-Autoscaling/BAB-09-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: GitOps & Troubleshooting ➡️](./Module-02-GitOps-ArgoCD-dan-Production-Troubleshooting.md)
---

# Module 01: Modern Packaging: Helm v3 vs Kustomize

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Mengidentifikasi kelemahan mendasar dari pengelolaan manifest Kubernetes mentah (*raw YAML sprawl*) di lingkungan multi-lingkungan (*multi-environment*).
- Menguasai arsitektur **Helm v3** (*Tiller-less*), struktur Chart, bahasa templating Go, fungsi utilitas `_helpers.tpl`, dan manajemen state rilis di dalam Kubernetes Secrets.
- Menguasai arsitektur bebas template (**Kustomize**): konsep *Base* dan *Overlays*, `patchesStrategicMerge`, `patchesJson6902`, serta generator otomatis ConfigMap/Secret dengan penambahan hash postfix unik.
- Membandingkan secara mendalam pro-kontra Helm vs Kustomize menggunakan matriks perbandingan teknis.
- Mengimplementasikan pola arsitektur hibrida (*Helm Post-Renderer* dengan Kustomize) untuk fleksibilitas maksimal.

---

## 2. Prerequisite
- Memahami seluruh primitif inti Kubernetes: Pod, Deployment, Service, ConfigMap, Secret, Ingress.
- Konsep dasar variabel, kontrol alur (if/else, range), dan format serialisasi data YAML & JSON.
- Version control system (Git) dan struktur direktori.

---

## 3. Concept
Ketika sebuah organisasi mengelola puluhan microservices di lingkungan yang berbeda (*Development*, *Staging*, *Production*), menduplikasi file YAML mentah adalah resep bencana:
- Lingkungan Dev hanya butuh 1 replika dengan CPU 100m dan domain `dev.perusahaan.com`.
- Lingkungan Prod butuh 10 replika, autoscaling HPA, CPU 2000m, dan domain `perusahaan.com`.
Jika menggunakan YAML mentah, developer harus mengelola dua file YAML terpisah. Saat ada perubahan label atau port, perubahan tersebut harus di-copy-paste manual, memicu kesalahan manusia (*configuration drift*).

Komunitas Kubernetes menghadirkan dua paradigma solusi utama:
1. **Helm (The Package Manager for Kubernetes)**: Paradigma berbasis **Template Engine** (Go template) dan parameterisasi via `values.yaml`. Helm memperlakukan kumpulan manifest sebagai satu paket aplikasi tunggal (*Chart*) yang memiliki siklus hidup versi, instalasi, upgrade, dan rollback.
2. **Kustomize (Template-Free Declarative Customization)**: Paradigma berbasis **Patching & Layering**. Kustomize mempertahankan YAML Kubernetes murni tanpa sintaks template kurung kurawal `{{ }}`, melainkan menggunakan konsep pewarisan: file `base/` didefinisikan satu kali, lalu file `overlays/prod/` menambahkan atau menimpa field tertentu. (Kustomize kini terintegrasi langsung di dalam `kubectl -k`).

```
                              RAW MANIFEST CHALLENGE
                                         |
         +-------------------------------+-------------------------------+
         |                                                               |
         v                                                               v
  [ PARADIGMA HELM (Templating) ]                        [ PARADIGMA KUSTOMIZE (Patching) ]
  - Parameterisasi variabel: values.yaml                 - YAML murni (Pure Declarative)
  - Go Template Engine: {{ .Values.replicas }}           - Layering: Base + Overlays
  - Packaging, Semantic Versioning, & Rollback           - Patching: Strategic Merge / JSON 6902
  - Release State disimpan di k8s Secret                 - Bawaan kubectl (kubectl apply -k)
```

---

## 4. Why?
Mengapa pengelolaan manifest tingkat lanjut mutlak diperlukan?
1. **Eliminasi Human Error**: Mencegah insiden di mana konfigurasi database Staging tidak sengaja terbawa ke cluster Produksi karena salah copy-paste baris YAML.
2. **Standardisasi Organisasi**: Platform engineering dapat membuat satu cetak biru *Enterprise Standard Chart* yang sudah otomatis menyertakan security context, probes liveness/readiness, dan anotasi observability Prometheus.
3. **Atomic Rollback & Versioning**: Jika deployment versi v2.0 mengalami crash, Helm memungkinkan pemulihan ke versi sebelumnya hanya dengan satu perintah: `helm rollback <release> <revision>`.

---

## 5. What?

### A. Anatomi Helm v3 Chart
```text
my-chart/
├── Chart.yaml          # Metadata: nama chart, versi chart (semver), versi aplikasi
├── values.yaml         # Nilai default parameter variabel
├── values.schema.json  # (Opsional) Validasi skema JSON untuk values
├── charts/             # Sub-charts (dependencies)
└── templates/          # Direktori manifest dengan sintaks template Go
    ├── _helpers.tpl    # Template parsial / fungsi helper yang dapat digunakan ulang
    ├── deployment.yaml
    ├── service.yaml
    ├── ingress.yaml
    └── NOTES.txt       # Pesan panduan yang ditampilkan setelah helm install
```

Di Helm v3, arsitektur menjadi *Tiller-less* (komponen server Tiller di K8s v2 dihapus demi keamanan). Helm v3 langsung berkomunikasi dengan Kube-APIServer menggunakan kredensial `kubeconfig` lokal user, dan metadata status rilis disimpan secara aman sebagai objek `Secret` di namespace aplikasi dengan enkripsi bawaan.

### B. Anatomi Kustomize (Base & Overlays)
```text
my-app/
├── base/
│   ├── deployment.yaml   # Manifest dasar (tanpa parameter template)
│   ├── service.yaml
│   └── kustomization.yaml # Mendeklarasikan resources: ["deployment.yaml", "service.yaml"]
└── overlays/
    ├── dev/
    │   ├── kustomization.yaml # Menimpa replicas=1, namespace=dev
    │   └── patch-replicas.yaml
    └── prod/
        ├── kustomization.yaml # Menimpa replicas=10, namespace=prod, inject Secret
        └── patch-resources.yaml
```

Fitur Unggulan Kustomize: **ConfigMapGenerator**.
Kustomize membuat ConfigMap dengan menyematkan hash konten pada nama objek, contoh: `app-config-g78hb4f92d`.
Jika isi konfigurasi diubah, nama ConfigMap berubah secara otomatis. Ini memaksa Kubernetes Deployment melakukan **Rolling Restart** tanpa perlu trik manual!

---

## 6. How?

### A. Contoh Implementasi Helm v3

#### `templates/_helpers.tpl`
```yaml
{{/* Nama lengkap aplikasi */}}
{{- define "mychart.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
```

#### `templates/deployment.yaml`
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "mychart.fullname" . }}
  labels:
    app.kubernetes.io/managed-by: Helm
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      app: {{ include "mychart.fullname" . }}
  template:
    metadata:
      labels:
        app: {{ include "mychart.fullname" . }}
    spec:
      containers:
        - name: {{ .Chart.Name }}
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
          ports:
            - containerPort: {{ .Values.service.port }}
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
```

#### Perintah Operasional Helm
```bash
# Render dan cek output manifest tanpa menyentuh cluster
helm template my-release ./my-chart -f values-prod.yaml

# Install aplikasi
helm install my-release ./my-chart -f values-prod.yaml -n production --create-namespace

# Upgrade aplikasi ke revisi baru
helm upgrade my-release ./my-chart -f values-prod.yaml -n production

# Rollback ke revisi sebelumnya jika terjadi kegagalan
helm history my-release -n production
helm rollback my-release 1 -n production
```

### B. Contoh Implementasi Kustomize

#### `base/kustomization.yaml`
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - deployment.yaml
  - service.yaml
```

#### `overlays/prod/kustomization.yaml`
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: production
namePrefix: prod-
resources:
  - ../../base
patches:
  - target:
      kind: Deployment
      name: my-app
    patch: |-
      - op: replace
        path: /spec/replicas
        value: 10
configMapGenerator:
  - name: app-settings
    files:
      - config.json
```

#### Perintah Operasional Kustomize
```bash
# Render manifest gabungan ke terminal
kubectl kustomize overlays/prod/

# Deploy langsung ke cluster
kubectl apply -k overlays/prod/
```

---

## 7. Analogy
Bayangkan **Pembuatan Baju Seragam Perusahaan**:
- **Helm**: Seperti **Pabrik Garmen dengan Pola Cetakan Dinamis (Formulir Ukuran)**. Anda memiliki cetakan baju standar (`template`), lalu Anda mengisi formulir: Warna = Biru, Ukuran = XL, Logo = Tulisan Custom (`values.yaml`). Mesin garmen mencetak baju persis sesuai formulir yang dimasukkan.
- **Kustomize**: Seperti **Membeli Baju Polos Standar di Toko, Lalu Membawa ke Penjahit Permak (Tailor)**. Anda membeli 100 baju putih polos ukuran All-Size (`Base`). Untuk tim Staging, penjahit menempelkan emblem kuning (`Overlay Staging`). Untuk tim Produksi, penjahit memotong lengan dan menambahkan bordir emas (`Overlay Prod`). Tidak ada cetakan baru yang dibuat, hanya modifikasi layer di atas barang jadi.

---

## 8. Diagram

```
+---------------------------------------------------------------------------------+
|                       HELM VS KUSTOMIZE WORKFLOW ENGINE                         |
+---------------------------------------------------------------------------------+

                      [ HELM PIPELINE ]
  +------------------+      +--------------------+
  | templates/*.yaml |  +   | values.prod.yaml   |
  +------------------+      +--------------------+
            \                    /
             v                  v
    [ Go Template Engine (String Interpolation) ]
                        |
                        v
        Rendered YAML ---> Kube-APIServer
        (State tracked in Secret: sh.helm.release.v1.xxx)

-----------------------------------------------------------------------------------

                    [ KUSTOMIZE PIPELINE ]
  +---------------------+
  | base/deployment.yaml| (Pure, Valid Kubernetes YAML)
  +---------------------+
            |
            v
  [ overlays/prod/kustomization.yaml ]
  - Strategic Merge Patch (Replicas = 10)
  - ConfigMapGenerator (SHA Hash: config-7b2h8f)
  - Namespace & NamePrefix Injection
            |
            v
        Rendered YAML ---> Kube-APIServer (via kubectl apply -k)
```

---

## 9. Simple Example: Strategic Merge Patch pada Kustomize

Mengubah image tag dan resource limit di environment `prod` tanpa menyentuh file `base`:

```yaml
# overlays/prod/patch-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-service
spec:
  replicas: 5
  template:
    spec:
      containers:
        - name: api
          image: myregistry.io/api:v2.0.0
          resources:
            limits:
              cpu: "1000m"
              memory: "1Gi"
```

---

## 10. Practical Example: Helm Lifecycle Hooks
Seringkali sebelum aplikasi di-upgrade, database schema migration harus dijalankan terlebih dahulu, dan jika migrasi gagal, upgrade harus dibatalkan:

```yaml
# templates/migration-job.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: "{{ .Release.Name }}-db-migrate"
  annotations:
    "helm.sh/hook": pre-install,pre-upgrade
    "helm.sh/hook-weight": "-5"
    "helm.sh/hook-delete-policy": hook-succeeded
spec:
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: migrate
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          command: ["./migrate-database.sh"]
```

---

## 11. Real World Example: The Hybrid Best-Practice (Helm + Kustomize)
Banyak tim platform enterprise menggunakan aplikasi open-source pihak ketiga (seperti Redis, Cert-Manager, ArgoCD) yang disediakan oleh komunitas dalam bentuk Helm Chart resmi.
Namun, tim enterprise memiliki aturan ketat: harus menambahkan label governance organisasi dan sidecar keamanan kustom.

**Pola Hibrida Modern**:
1. Gunakan Helm hanya untuk me-render Chart komunitas menjadi manifes YAML (`helm template`).
2. Gunakan Kustomize untuk menimpa (*overlay patch*) hasil render Helm tersebut sesuai standar organisasi.
3. Pola ini didukung secara native oleh ArgoCD via fitur `kustomized-helm`!

---

## 12. Trade-offs

| Kriteria | Helm v3 | Kustomize |
|---|---|---|
| **Kompleksitas Sintaks** | Tinggi (Membutuhkan penguasaan Go Template & spasi YAML) | Rendah (Hanya deklarasi YAML standar) |
| **Penyimpanan State & Rollback** | Ya (Tersimpan otomatis di etcd Secrets) | Tidak (Tergantung pada riwayat Git commit) |
| **Dependency Management** | Sangat baik (Dukungan sub-charts & Helm OCI registry) | Kurang fleksibel (Hanya referensi path URL/Git) |
| **Integrasi Eksternal** | Butuh CLI `helm` terpisah | Bawaan native biner `kubectl` (`-k`) |
| **Validasi Manifest** | YAML tidak valid sebelum dirender oleh engine template | Setiap file YAML dasar selalu valid secara mandiri |

---

## 13. When To Use
- Gunakan **Helm v3** jika Anda mempublikasikan aplikasi/library untuk digunakan oleh pihak ketiga (*off-the-shelf software distribution*), membutuhkan manajemen dependency antar komponen, atau mengandalkan Helm lifecycle hooks.
- Gunakan **Kustomize** untuk aplikasi in-house internal perusahaan di mana Anda ingin mempertahankan kesederhanaan YAML murni dan mengandalkan GitOps (ArgoCD/Flux) sebagai mesin pemicu rollback.

---

## 14. When NOT To Use
- **JANGAN** membuat template Helm yang terlalu rumit (*over-templating*) di mana setiap baris YAML digantikan oleh `{{ .Values.xxx }}`. Ini membuat debugging menjadi mimpi buruk (*YAML template hell*).
- Jangan menggunakan Helm jika tim Anda belum memahami alur kerja state rilis Secret.

---

## 15. Common Mistakes
1. **Kesalahan Indentasi Spasi pada Helm (`nindent`)**: Fungsi `toYaml` yang tidak diberi indentasi yang tepat (`nindent 12`) akan merusak struktur hirarki spasi YAML dan menyebabkan error `mapping values are not allowed here`.
2. **Lupa Menghapus Release Secret Lama**: Menjalankan ratusan upgrade Helm tanpa pembersihan dapat menimbun ribuan objek Secret `sh.helm.release.v1...` di namespace, membebani ukuran database etcd. Gunakan flag `--history-max 10`.
3. **Konflik Nama pada Kustomize Base**: Menentukan nama resource yang sama di beberapa sub-file kustomize tanpa menggunakan `namePrefix` atau `nameSuffix`.

---

## 16. Best Practices
- **Must Have**: Jalankan `helm lint` dan `helm template` di dalam pipeline CI/CD untuk mendeteksi error sintaks sebelum deploy.
- **Recommended**: Manfaatkan fitur `configMapGenerator` Kustomize untuk memicu restart otomatis Pod saat ada perubahan konfigurasi tanpa script downtime.
- **Advanced**: Publikasikan Helm Charts organisasi ke **OCI-compliant Registry** (seperti AWS ECR, Harbor, atau GitHub Packages) menggunakan perintah `helm push`.
- **Avoid**: Menyimpan password plain-text di file `values.yaml` yang di-commit ke Git publik.

---

## 17. Troubleshooting Guide
```
Masalah: Helm upgrade gagal dengan pesan "UPGRADE FAILED: another operation (install/upgrade/rollback) is in progress".
Penyebab : Pipeline CI sebelumnya terputus di tengah jalan, meninggalkan status release dalam kondisi 'pending-upgrade'.
Diagnosa : helm status <release-name> -n <ns>
Solusi   : Hapus secret status pending terakhir secara manual atau gunakan plugin helm-rollback:
           kubectl get secrets -n <ns> -l owner=helm,status=pending-upgrade
           kubectl delete secret <secret-name-pending> -n <ns>

Masalah: Kustomize error "strategic merge patch target not found".
Penyebab : Nama resource (metadata.name) atau kind pada file patch tidak persis cocok dengan manifest di direktori base.
Solusi   : Pastikan 'kind', 'apiVersion', dan 'metadata.name' di file patch identik dengan file base.
```

---

## 18. Exercise
1. Buat Helm Chart sederhana bernama `microservice-app` menggunakan perintah `helm create microservice-app`.
2. Bersihkan template bawaan dan sisakan `deployment.yaml` dan `service.yaml`.
3. Tambahkan parameter `replicaCount` dan `image.tag` di `values.yaml`.
4. Render manifest untuk environment testing menggunakan command `helm template test-run ./microservice-app --set replicaCount=3`.

---

## 19. Challenge
Bangun struktur Kustomize multi-environment untuk aplikasi Web:
1. `base/`: Deployment NGINX 1 replika dan Service port 80.
2. `overlays/dev/`: Menambahkan prefix `dev-` dan mengubah Service menjadi NodePort.
3. `overlays/prod/`: Menambahkan prefix `prod-`, menaikkan replika menjadi 5, menginjeksi ConfigMap via `configMapGenerator`, dan menambahkan toleration node produksi.
Validasi hasil render keduanya menggunakan `kubectl kustomize`!

---

## 20. Summary
Helm dan Kustomize adalah dua pilar modern dalam manajemen konfigurasi Kubernetes. Helm unggul dalam standardisasi paket, manajemen dependensi, dan siklus rilis bervolume tinggi, sementara Kustomize memberikan keanggunan deklaratif bebas template yang sangat cocok untuk alur kerja GitOps modern.

---
[⬅️ BAB 09 Quiz & Challenge](../BAB-09-Scheduling-Lanjutan-dan-Autoscaling/BAB-09-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: GitOps & Troubleshooting ➡️](./Module-02-GitOps-ArgoCD-dan-Production-Troubleshooting.md)
---
