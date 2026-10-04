# Bab 04 Module 01: Infrastruktur Hybrid-Cloud, On-Premises & Air-Gapped Environments

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul:** `FDE-ARC-0401`
* **Nama Modul:** Arsitektur Deployment On-Premises, Air-Gapped Enclaves, Bastion Protocols, dan Offline Registries
* **Kategori:** 06-Architecture-and-System-Design
* **Tingkat Kesulitan:** Advanced / Senior
* **Prasyarat:** 
  * Pemahaman mendalam tentang arsitektur internal Kubernetes (Control Plane, Worker, etcd, CNI, CSI).
  * Kemahiran operasional Linux networking (`iptables`, `ip route`, CIDR, DNS resolution).
  * Pengalaman menggunakan Docker/OCI specifications, OpenSSL/PKI x509, dan Helm templating.
* **Estimasi Waktu Penyelesaian:** 120 Menit (Teori & Arsitektur) + 180 Menit (Hands-on Lab)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, seorang Forward Deployed Engineer (FDE) mampu:

1. **Mendiagnosis dan Menavigasi Hambatan Isolasi Jaringan Penuh (Air-Gap):** Memahami implikasi ketiadaan akses internet publik terhadap dependensi software runtime, bootstrapping TLS/x509, time synchronization (NTP), dan resolusi DNS internal.
2. **Merancang Pipeline Distribusi Artefak Mandiri (Self-Contained Artifact Pipeline):** Memaketkan ratusan container image dan Helm charts secara deterministik menggunakan toolset seperti `skopeo`, `crane`, dan OCI registries ke media transfer offline (sneakernet/optical media).
3. **Mengoperasikan & Mengonfigurasi Local OCI Registry Terisolasi:** Mengonfigurasi private container registry (Harbor) secara on-premises dengan integrasi High Availability, storage persistence (SAN/NAS/Ceph), sertifikat x509 internal kustom, serta mekanisme RBAC.
4. **Menerapkan Pola Zero-Trust Bastion Host:** Mengimplementasikan akses auditabel ke dalam secure enclave menggunakan jump host, cryptographic key management, dynamic port forwarding, dan audit trail logging tanpa membuka direct route ke worker nodes.
5. **Memodifikasi Deployment Charts untuk Lingkungan Offline:** Menggunakan teknik Helm post-rendering dan values overrides untuk mengarahkan seluruh dependensi image pull, chart dependencies, dan webhooks ke endpoint internal tanpa mengubah upstream source code.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
[INTERNET / CONNECTED ZONE]
         │
         ▼ (skopeo copy / crane export)
   [OCI Bundles (.tar)]
         │
         ▼ (Physical Transfer / Sneakernet / Data Diode)
┌─────────────────────────────────────────────────────────────┐
│ AIR-GAPPED SECURE ENCLAVE                                   │
│                                                             │
│  [Bastion Host / Jumpbox] ──(mTLS / SSH CA)──► [Audit Log]  │
│         │                                                   │
│         ▼ (crane import / skopeo sync)                      │
│  [Internal OCI Registry] (Harbor / Zot + Custom Root CA)     │
│         │                                                   │
│         ▼                                                   │
│  [Kubernetes Cluster (RKE2 / Kubeadm / Talos)]              │
│   ├── Control Plane (etcd sync via Internal NTP)            │
│   ├── CoreDNS (Upstream stubbed to Internal DNS Server)     │
│   ├── Containerd (Configured to mirror via local Harbor)    │
│   └── Pods / Workloads (Images redirected via Post-Renderer)│
└─────────────────────────────────────────────────────────────┘
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Sebagai Forward Deployed Engineer (FDE), Anda jarang bekerja pada infrastruktur cloud publik yang sepenuhnya terbuka. Klien bernilai tinggi—seperti lembaga perbankan tier-1, kementerian pertahanan, fasilitas manufaktur industri vital, dan perusahaan kesehatan—beroperasi di bawah regulasi ketat (misal: PCI-DSS Level 1, ISO 27001 Annex A.13, SOC 2 Type II, FedRAMP High, HIPAA). 

Lingkungan ini sering kali berstatus **Zero-Egress / Zero-Ingress (Strict Air-Gap)**:
* Server target tidak memiliki akses ke `docker.io`, `gcr.io`, `quay.io`, atau public package mirrors.
* Server DNS publik (seperti `8.8.8.8`) diblokir oleh perimeter hardware firewall.
* Setiap byte kode dan data yang masuk ke data center harus melalui audit statis, scanning kerentanan (CVE), dan transfer manual (sneakernet via USB terenkripsi atau data diode satu arah).

Jika software Anda mengasumsikan adanya konektivitas internet (seperti script install `curl | bash`, dependensi chart ke repo remote, atau dynamic base image download), deployment di client site dipastikan **gagal total pada hari pertama**. Memahami cara mendesain, memaketkan, dan mendistribusikan software secara terisolasi adalah pembeda utama antara engineer cloud konvensional dan Forward Deployed Engineer elite.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Air-Gapped Environment
Sistem komputasi yang terisolasi secara fisik dan logis dari jaringan luar, khususnya internet publik. Tidak ada kabel Ethernet yang terhubung ke switch publik, tidak ada antarmuka nirkabel, dan seluruh routing table dibatasi pada segmen subnet LAN privat lokal.

### 2. On-Premises Kubernetes Distros
Implementasi Kubernetes di atas bare-metal atau hypervisor lokal (VMware vSphere, Nutanix AHV, OpenStack). Distro seperti **RKE2 (Rancher Government Solutions)**, **Talos Linux**, atau vanilla **kubeadm** dirancang dengan keamanan default, kemampuan berjalan tanpa internet, serta kemudahan injeksi sertifikat PKI lokal.

### 3. Bastion Host / Jump Host
Server perantara yang diperkeras (hardened) yang ditempatkan di perimeter jaringan aman (DMZ). Bastion menjadi satu-satunya gerbang masuk bagi FDE untuk mengelola infrastruktur target. Tidak ada akses langsung via SSH/API server ke Kubernetes node tanpa melalui bastion.

### 4. Offline Container Registry
Registry OCI (seperti **Harbor**, **Zot**, atau **Quay**) yang di-bootstrap di dalam air-gap enclave. Bertindak sebagai single source of truth untuk seluruh container image, Helm charts, dan OCI artifacts yang dibutuhkan oleh cluster.

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

Alur kerja deployment pada lingkungan air-gapped dibagi menjadi 3 fase utama:

### Fase 1: Packaging & Serialization (Connected Zone)
1. **Dependency Analysis:** Ekstraksi seluruh image references dari Helm charts, manifests, dan operator custom resources.
2. **Container Image Mirroring:** Mengunduh image dari registry publik berdasarkan tag atau immutable digest (`@sha256:xxx`), kemudian memaketkannya ke dalam format OCI Image Layout (`tarball`) menggunakan utility modern seperti `crane` atau `skopeo`.
3. **Helm Packaging:** Mengunduh Helm dependencies (`helm dependency build`), memastikan tidak ada dependencies yang menunjuk ke URL eksternal, dan mengompresi chart ke dalam format `.tgz`.

### Fase 2: Ingestion & Verification (Transfer Zone)
1. **Transfer:** Pemindahan file arsip melalui media fisik yang disetujui (USB terenkripsi AES-256) atau transfer unidirectional data diode.
2. **Scanning:** Pemeriksaan malware dan verifikasi hash sha256 pada staging scanning station di sisi klien.
3. **Ingestion via Bastion:** Pengunggahan arsip ke Bastion Host atau deployment storage node.

### Fase 3: Local Re-Hydration & Execution (Air-Gapped Enclave)
1. **Registry Hydration:** Injeksi image dari OCI Image Layout ke local registry internal (Harbor) dengan mapping namespace yang terstruktur.
2. **Containerd Mirror Configuration:** Mengonfigurasi `/etc/containerd/certs.d/` atau mirror registries pada setiap worker node agar request ke registry publik dialihkan secara transparan ke registry lokal.
3. **Deployment via Helm Post-Renderer:** Jika containerd registry mirror tidak didukung atau dilarang oleh arsitektur client, manifest Helm diubah secara dinamis saat render time menggunakan kustom Kustomize/post-renderer script untuk mengganti prefix registry URL.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

```
+===================================================================================================+
|                                    CONNECTED ENVIRONMENT (OFF-SITE)                               |
|                                                                                                   |
|  +-------------------+       +--------------------+       +------------------------------------+  |
|  | Public Registries |       | Public Helm Repos  |       | CLI Machine (FDE Workstation)      |  |
|  | - DockerHub       |       | - Bitnami          |       | $ skopeo copy docker://... dir:... |  |
|  | - Quay.io         |       | - ArtifactHub      |       | $ helm pull ...                    |  |
|  +---------+---------+       +---------+----------+       +-----------------+------------------+  |
|            |                           |                                    |                     |
|            +---------------------------+------------------------------------+                     |
|                                        |                                                          |
|                                        v                                                          |
|                         [ Compressed Payload (.tar.gz) ]                                          |
|                         - OCI Image Layouts                                                       |
|                         - Helm Archive Charts                                                     |
|                         - Sha256 Checksums                                                        |
+========================================|==========================================================+
                                         |
                                         | PHYSICAL MEDIA / SECURE SNEAKERNET (DATA DIODE)
                                         v
+===================================================================================================+
|                                AIR-GAPPED SECURE ENCLAVE (ON-PREMISES)                            |
|                                                                                                   |
|  +---------------------------------------------------------------------------------------------+  |
|  | DMZ / EDGE PERIMETER                                                                        |  |
|  |                                                                                             |  |
|  |   +---------------------------------------+         +-----------------------------------+   |  |
|  |   | Hardened Bastion Host                 |         | Enterprise Staging Storage        |   |  |
|  |   | - SSH via Internal PKI Certificate    | <=====> | - Scanned Payload Depot           |   |  |
|  |   | - Session Auditing (teleport / tlog)  |         | - Verification & Hash Integrity   |   |  |
|  |   +-------------------+-------------------+         +-----------------------------------+   |  |
|  +-----------------------|---------------------------------------------------------------------+  |
|                          | Private Subnet Route (Port 443 Only, No Direct Node Access)            |
|                          v                                                                        |
|  +---------------------------------------------------------------------------------------------+  |
|  | INTERNAL SECURE CORE NETWORK (ISOLATED)                                                     |  |
|  |                                                                                             |  |
|  |   +-------------------------------------------------------------------------------------+   |  |
|  |   | Local OCI Registry (Harbor High-Availability)                                       |   |  |
|  |   | - URL: https://registry.corp.internal                                               |   |  |
|  |   | - Storage: Internal SAN/Ceph via S3 API                                             |   |  |
|  |   | - Identity: Signed by Corporate Root CA (x509)                                      |   |  |
|  |   +-------------------+-----------------------------------------------------------------+   |  |
|  |                       |                                                                     |  |
|  |                       | Internal Layer 2/3 LAN                                              |  |
|  |                       v                                                                     |  |
|  |   +-------------------------------------------------------------------------------------+   |  |
|  |   | Kubernetes Cluster (e.g., RKE2 / Kubeadm On-Premises)                               |   |  |
|  |   |                                                                                     |   |  |
|  |   |   +----------------------------------+       +----------------------------------+   |  |
|  |   |   | Control Plane (etcd, API-Server) |       | Worker Nodes (containerd runtime)|   |  |
|  |   |   | - NTP synced to Core Router      | <---> | - containerd mirror config       |   |  |
|  |   |   | - Internal CoreDNS pointing local|       | - Custom Root CA injected in OS  |   |  |
|  |   |   +----------------------------------+       +-----------------+----------------+   |  |
|  |                                                                    |                        |  |
|  |                                                                    v                        |  |
|  |                                                  +----------------------------------+   |  |
|  |                                                  | Workload Pods (Zero Internet)    |   |  |
|  |                                                  | - Pulled from registry.corp.int  |   |  |
|  |                                                  +----------------------------------+   |  |
|  +---------------------------------------------------------------------------------------------+  |
+===================================================================================================+
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah workflow minimal memaketkan sebuah image tunggal (misal: `redis:7.2-alpine`) dari mesin online dan mengekspornya untuk dipindahkan ke sistem air-gapped menggunakan tool standar industri `skopeo`.

### Di Mesin Online (Connected):
```bash
# 1. Simpan image dari registry publik ke direktori berformat OCI layout
mkdir -p ./bundle/images/redis-7.2
skopeo copy \
  --override-os linux \
  --override-arch amd64 \
  docker://docker.io/library/redis:7.2-alpine \
  oci:./bundle/images/redis-7.2:7.2-alpine

# 2. Kompres layout menjadi tarball
tar -czvf redis-bundle.tar.gz ./bundle/

# 3. Hitung SHA256 checksum untuk audit klien
sha256sum redis-bundle.tar.gz > redis-bundle.tar.gz.sha256
```

### Di Mesin Air-Gapped (Melalui Bastion):
```bash
# 1. Verifikasi integritas payload
sha256sum -c redis-bundle.tar.gz.sha256

# 2. Ekstrak payload
tar -xzvf redis-bundle.tar.gz

# 3. Push ke registry internal lokal tanpa validasi TLS publik (menggunakan internal corporate CA)
skopeo copy \
  --dest-cert-dir /etc/ssl/certs/corporate-ca.crt \
  oci:./bundle/images/redis-7.2:7.2-alpine \
  docker://registry.corp.internal/production/redis:7.2-alpine

# Verifikasi image sudah ter-push di registry lokal
curl -k -u "admin:HarborPassword123" https://registry.corp.internal/v2/production/redis/tags/list
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Kasus Produksi: Memaketkan aplikasi multi-container kompleks (PostgreSQL, Application API, Frontend) beserta Helm Chart, lalu menyiapkannya untuk deployment di lingkungan terisolasi dengan penulisan ulang registry secara transparan menggunakan Helm Post-Renderer.

### 1. Script Ekstraksi & Packaging Dependensi (Jalankan di Connected Zone)

Buat script bernama `airgap-packager.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

DEST_DIR="./airgap-payload"
REGISTRY_STAGING="staging-cache"
IMAGES_FILE="images-list.txt"

mkdir -p "${DEST_DIR}/charts"
mkdir -p "${DEST_DIR}/images"

# Daftar image yang dibutuhkan
cat <<EOF > "${IMAGES_FILE}"
docker.io/library/postgres:16.1-alpine
docker.io/library/nginx:1.25-alpine
quay.io/argoproj/argocd:v2.9.3
EOF

echo "[+] Mengunduh Helm Chart..."
helm repo add bitnami https://charts.bitnami.com/bitnami
helm pull bitnami/postgresql --version 13.2.24 --destination "${DEST_DIR}/charts"

echo "[+] Menyalin Image ke OCI Image Layout..."
while IFS= read -r img; do
    if [[ -z "$img" || "$img" =~ ^# ]]; then continue; fi
    # Ganti karakter '/' dan ':' untuk penamaan folder lokal
    safe_name=$(echo "$img" | tr '/:' '_')
    echo "Processing: $img -> $safe_name"
    
    skopeo copy \
      --all \
      --insecure-policy \
      "docker://${img}" \
      "oci:${DEST_DIR}/images/${safe_name}:latest"
done < "${IMAGES_FILE}"

echo "[+] Mengompres Seluruh Payload..."
tar -cvf airgap-package-v1.0.tar "${DEST_DIR}"
sha256sum airgap-package-v1.0.tar > airgap-package-v1.0.tar.sha256
echo "[✓] Payload selesai dibuat: airgap-package-v1.0.tar"
```

### 2. Script Injeksi ke Internal Registry (Jalankan di Bastion Host Air-Gapped)

Buat script `airgap-injector.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

LOCAL_REGISTRY="registry.internal.domain"
TARGET_PROJECT="enterprise-suite"
INTERNAL_CA="/etc/pki/ca-trust/source/anchors/InternalRootCA.crt"

echo "[+] Memvalidasi Checksum..."
sha256sum -c airgap-package-v1.0.tar.sha256

echo "[+] Mengekstrak Paket..."
tar -xvf airgap-package-v1.0.tar

cd airgap-payload/images
for dir in *; do
    if [ -d "$dir" ]; then
        # Parse nama asli image kembali
        # Asumsi: mapping image format sederhana
        image_tag=$(echo "$dir" | awk -F'_' '{print $(NF)}')
        image_name=$(echo "$dir" | awk -F'_' '{for(i=1;i<NF;i++) printf "%s-",$i}' | sed 's/-$//')

        dest="docker://${LOCAL_REGISTRY}/${TARGET_PROJECT}/${image_name}:${image_tag}"
        echo "[+] Mengunggah: $dir -> $dest"

        skopeo copy \
          --dest-cert-dir "$(dirname $INTERNAL_CA)" \
          --all \
          "oci:${dir}:latest" \
          "${dest}"
    fi
done
echo "[✓] Re-hydration Image Selesai."
```

### 3. Deploy dengan Helm Kustomize Post-Renderer
Bila Helm Chart memiliki nilai registry default yang terkunci atau terlalu rumit diubah via ribuan baris `values.yaml`, gunakan *Helm Post-Renderer* untuk meresolusi image secara otomatis.

Buat file kustomize generator `kustomization.yaml`:
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - all.yaml
images:
  - name: docker.io/library/postgres
    newName: registry.internal.domain/enterprise-suite/docker.io-library-postgres
  - name: docker.io/library/nginx
    newName: registry.internal.domain/enterprise-suite/docker.io-library-nginx
```

Buat post-renderer executable `kustomize-renderer.sh`:
```bash
#!/usr/bin/env bash
set -e
cat <&0 > all.yaml
kubectl kustomize .
rm -f all.yaml
```
Pastikan script executable: `chmod +x kustomize-renderer.sh`

Jalankan Helm upgrade/install dengan post-renderer:
```bash
helm template postgres-release ./charts/postgresql-13.2.24.tgz \
  --post-renderer ./kustomize-renderer.sh | kubectl apply -f -
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Pendekatan / Keputusan | Keuntungan (Pros) | Biaya / Risiko (Cons & Trade-offs) |
| :--- | :--- | :--- |
| **Containerd Mirroring via `certs.d`** | Transparan bagi developer; tidak perlu mengubah manifest/chart k8s asli. | Perlu konfigurasi manual di setiap worker node (OS file system); provisioning rumit saat ada worker node baru ditambahkan secara dinamis. |
| **Helm Values Override / Post-Renderer** | Independen dari konfigurasi worker node; sepenuhnya terkontrol pada level manifest CD/K8s. | Meningkatkan kompleksitas manifest parsing; rawan broken deployment jika nama registry upstream berubah tanpa terdeteksi kustomize. |
| **In-Cluster OCI Registry (e.g. Harbor on K8s)** | Biaya hardware lebih hemat; dikelola menggunakan lifecycle yang sama dengan workload K8s. | Masalah *Circular Dependency* (Chicken-and-Egg): Jika cluster down, registry tidak bisa diakses untuk me-reboot pod K8s itu sendiri. |
| **Standalone Appliance Registry (VM / Bare-metal)** | Sangat stabil, independen dari lifecycle K8s, tidak rentan failure cascade. | Butuh alokasi VM terpisah, setup storage dan snapshot disk manual, meningkatkan overhead maintainability. |
| **Data Diode Hardware Transfer** | Keamanan fisik matematis mutlak; tidak ada aliran byte data yang bisa bocor keluar (egress impossible). | Biaya hardware sangat tinggi; transfer bersifat simplex (tidak ada TCP ACK lintas diode, packet loss handling rumit). |

---

## SEKSI 11 — BEST PRACTICES

1. **Gunakan Immutable Digests (`@sha256:`), Bukan Floating Tags:** Di lingkungan air-gap, tag `:latest` atau `:v1.0` yang berubah diam-diam dapat memicu cache inconsistency di antara worker nodes. Gunakan digest untuk jaminan deterministik 100%.
2. **Kompilasi Root CA Lokal ke Golden Image Node:** Sertifikat CA privat yang menandatangani HTTPS local registry harus di-bake langsung ke dalam base operating system worker node (misal: `/etc/pki/ca-trust` di RHEL atau `/usr/local/share/ca-certificates` di Ubuntu) sebelum node di-boot.
3. **Konfigurasi Dedicated NTP Servers:** Cluster Kubernetes lokal akan segera collapse (terutama quorum etcd dan validasi sertifikat x509 API-server) jika waktu antar node bergeser (drift) lebih dari beberapa milidetik. Arahkan NTP daemon (`chrony` atau `systemd-timesyncd`) ke NTP server internal data center.
4. **Deploy Harbor dengan S3 Backend Terisolasi (MinIO / Ceph):** Jangan simpan image Harbor pada filesystem lokal node tunggal menggunakan `hostPath`. Gunakan backend storage terdistribusi on-premises berbasis Object Storage S3 protocol untuk menghindari hilangnya storage image saat node registry crash.
5. **Gunakan SSH Agent Forwarding dan Dynamic SOCKS Proxy pada Bastion:**
   ```bash
   # Buka dynamic proxy ke private network melalui Bastion Host tanpa memaparkan port langsung
   ssh -D 1080 -N -C -q -i ~/.ssh/bastion_rsa fde-user@bastion.client.internal
   # Akses internal cluster API lewat proxy:
   HTTPS_PROXY=socks5://127.0.0.1:1080 kubectl get nodes
   ```

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1. **Hardcoded Upstream Registries di Helper/Init Containers:** FDE sering kali sukses mengubah image workload utama, tetapi lupa mengubah image untuk `initContainers` (seperti wait-for-database), metrics-exporter, atau service mesh proxies (`linkerd-proxy` / `istio-proxy`), menyebabkan pod macet di status `ErrImagePull`.
2. **CoreDNS Mengalami Upstream Timeout:** CoreDNS secara default mencoba menghubungi upstream DNS host. Jika upstream tersebut tidak diisolasi atau masih mengarah ke DNS publik yang di-drop oleh firewall, query internal akan mengalami delay hingga 5 detik per lookup karena menunggu timeout koneksi UDP.
3. **Mengabaikan Storage Provisioning (No Dynamic Provisioner):** Di public cloud, `gp3` atau `standard-rwo` secara otomatis menyuplai block storage. Di on-premises air-gap, jika Anda tidak mengonfigurasi Local Path Provisioner, CSI Ceph-RBD, atau NFS Provisioner, stateful PVC akan selamanya berstatus `Pending`.
4. **Lupa Menarik Metadata Index Helm Chart:** Hanya menyalin container image tanpa menyertakan Helm repository index (`index.yaml`) atau dependencies library charts (`.tgz`), menyebabkan command `helm install` gagal mengevaluasi chart dependencies.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Skenario Lab
Anda diminta menyimulasikan lingkungan terisolasi (Air-Gapped) di laptop lokal Anda menggunakan Docker bridge networks tanpa rute egress internet.

```
              [Host Machine (Connected)]
                         |
      +------------------+------------------+
      | (simulated physical data boundary)  |
      v                                     v
[Isolated Registry: 5000]          [Isolated K3s Node]
      \                                    /
       +--- Network: "airgap-net" (Internal)
            --internal (NO EGRESS GATEWAY)
```

### Instruksi Langkah-demi-Langkah

#### Langkah 1: Buat Jaringan Terisolasi Penuh
```bash
# Buat internal network yang tidak memiliki default gateway ke WAN
docker network create --internal airgap-net
```

#### Langkah 2: Bootstrap Registry Offline di Jaringan Terisolasi
```bash
# Jalankan local registry v2 yang tersambung ke airgap-net
docker run -d \
  --name local-airgap-registry \
  --network airgap-net \
  --restart always \
  -e REGISTRY_HTTP_ADDR=0.0.0.0:5000 \
  registry:2
```

#### Langkah 3: Ekstraksi Image dari Publik dan Injeksi ke Jaringan Terisolasi
Jalankan container perantara (berfungsi sebagai transfer workstation) yang tersambung sementara ke host dan jaringan airgap:
```bash
# 1. Pull image di mesin host
docker pull alpine:3.19.1

# 2. Tag dan jalankan sementara jembatan transfer
docker tag alpine:3.19.1 localhost:5000/base/alpine:3.19.1

# 3. Masukkan container perantara ke jaringan airgap dan push
docker run --rm \
  --network airgap-net \
  -v /var/run/docker.sock:/var/run/docker.sock \
  quay.io/skopeo/stable:latest copy \
  --insecure-policy \
  --dest-tls-verify=false \
  docker-daemon:alpine:3.19.1 \
  docker://local-airgap-registry:5000/base/alpine:3.19.1
```

#### Langkah 4: Validasi bahwa Image Berhasil Ditarik Tanpa Internet
Jalankan container uji di dalam `airgap-net`:
```bash
docker run --rm \
  --network airgap-net \
  local-airgap-registry:5000/base/alpine:3.19.1 \
  sh -c "echo 'Airgap Execution Success' && ping -c 1 -W 2 8.8.8.8 || echo 'Verified: No WAN Egress'"
```

**Ekspektasi Output:**
Container sukses mencetak `Airgap Execution Success` diikuti failure konfirmasi bahwa jaringan publik `8.8.8.8` tidak terjangkau (Network unreachable).

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Mengapa penggunaan immutable digest (`@sha256:...`) sangat penting dalam skenario air-gapped dibandingkan floating tag (seperti `:v1.2`)?**
   * A. Floating tag tidak didukung oleh OCI registry v2.
   * B. Untuk mencegah worker node menjalankan layer image yang berbeda akibat adanya image caching lama di node tertentu saat payload di-update ulang di registry lokal.
   * C. Karena digest mengompresi ukuran image lebih kecil 50% dibanding tag.
   * D. Karena Kubernetes menolak eksekusi pod di on-premises jika tidak menyertakan hash SHA.
   * *Jawaban yang benar: B. Pembahasan: Tag dapat ditimpa (overwritten). Pada cluster air-gap, jika update image memakai tag yang sama, node yang sudah memiliki cache lama tidak akan melakukan pull ulang kecuali `imagePullPolicy: Always` aktif, dan itu pun rentan konflik cache mismatch.*

2. **Saat melakukan deployment Helm Chart di lingkungan air-gap, pod Anda gagal start dengan pesan `CrashLoopBackOff`, dan log CoreDNS menampilkan ribuan log connection timeout ke `10.96.0.10:53`. Apa kemungkinan akar penyebabnya?**
   * A. Node lokal kekurangan RAM untuk menjalankan CoreDNS.
   * B. CoreDNS mencoba me-resolve query eksternal ke forwarder DNS default host yang mencoba menghubungi internet publik yang di-drop oleh firewall hardware.
   * C. Helm Chart tidak terdaftar di internal certificate registry.
   * D. Bastion host mematikan port SSH routing.
   * *Jawaban yang benar: B. Pembahasan: CoreDNS mewarisi `/etc/resolv.conf` dari node host. Jika host memiliki DNS publik (misal IP ISP atau Google 8.8.8.8), CoreDNS akan menggantung hingga timeout saat service mencari host eksternal.*

3. **Apa kegunaan utama dari teknik "Helm Post-Renderer" dalam packaging air-gap?**
   * A. Menandatangani Helm chart menggunakan cryptographic key.
   * B. Memodifikasi manifest Kubernetes yang dirender Helm (misalnya mengganti domain image registry) secara otomatis menggunakan tool seperti Kustomize tanpa perlu mengubah source chart asli.
   * C. Menghubungkan cluster Kubernetes ke internet secara ilegal.
   * D. Mengurangi ukuran bundle OCI image layout sebelum ditransfer ke sneakernet.
   * *Jawaban yang benar: B. Pembahasan: Post-renderer memungkinkan FDE mengintercept stream YAML output dari Helm template dan mentransformasikannya (seperti image rewriting via Kustomize) tanpa memodifikasi chart upstream.*

4. **Bagaimana Anda memecahkan kendala etcd cluster down secara misterius beberapa minggu setelah deployment di data center isolated?**
   * A. Mematikan fitur TLS pada etcd.
   * B. Mengganti semua storage PVC ke ephemeral emptyDir.
   * C. Memeriksa time drift (desinkronisasi waktu) antar control plane node akibat ketiadaan koneksi NTP eksternal.
   * D. Menghapus folder containerd di setiap node.
   * *Jawaban yang benar: C. Pembahasan: Raft consensus pada etcd sangat sensitif terhadap clock drift. Tanpa NTP internal lokal, jam sistem antar node akan bergeser yang menyebabkan kegagalan election leader dan invalidasi sertifikat TLS.*

5. **Tool manakah di bawah ini yang paling direkomendasikan untuk menyalin OCI artifacts antar storage types (misal dari registry ke local folder archive) tanpa membutuhkan daemon Docker yang berjalan?**
   * A. Docker Compose
   * B. Skopeo
   * C. Minikube
   * D. Systemd
   * *Jawaban yang benar: B. Pembahasan: Skopeo dirancang khusus untuk menginspeksi, menyalin, dan memanipulasi container images dan OCI artifacts langsung lintas format storage (docker registry, local dir, oci layout) tanpa runtime Docker daemon.*

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **CNCF Air-Gapped Workgroup Documentation:** Panduan arsitektur referensi untuk implementasi Kubernetes pada lingkungan isolasi tinggi.
* **RKE2 (Rancher Government Solutions) Documentation:** Panduan resmi arsitektur Air-Gap install untuk distro Kubernetes FIPS-compliant: [https://docs.rke2.io/install/airgap](https://docs.rke2.io/install/airgap)
* **Containers/Skopeo Repository:** Dokumentasi manipulasi OCI image format dan protocol copy: [https://github.com/containers/skopeo](https://github.com/containers/skopeo)
* **Project Harbor Docs:** Konfigurasi enterprise offline registry, proxy cache, dan internal vulnerability scanning via Trivy: [https://goharbor.io/docs/](https://goharbor.io/docs/)
* **NIST Special Publication 800-125B:** Secure Virtual Network Configuration for Virtual Machine and Container Platforms.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. Lingkungan **Air-Gapped** menuntut kemandirian infrastruktur secara mutlak: tidak ada akses internet eksternal, validasi dependensi publik, maupun server waktu/DNS eksternal.
2. Siklus hidup distribusi software FDE pada site terisolasi bertumpu pada **Packaging Determiniftik**: semua aset (chart, binary, OCI image layout) dipaketkan bersama hash integritas cryptographic sebelum ditransfer via sneakernet/bastion.
3. **Local OCI Registry (Harbor)** adalah jantung operasional air-gap. Registry ini harus diintegrasikan dengan Certificate Authority (CA) lokal dan didukung persistent storage yang reliabel.
4. **Helm Post-Renderer** dan **Containerd Mirroring** adalah dua teknik esensial untuk mengatasi hardcoded image repository paths pada deployment package tanpa merusak struktur chart upstream.
5. Kegagalan operasional paling fatal di on-premises sering kali bukan berasal dari bug aplikasi, melainkan kegagalan primitif infrastruktur: **NTP time drift**, **DNS timeouts**, dan **ketiadaan dynamic storage provisioner (CSI)**.

---

## SEKSI 17 — GLOSARIUM

* **Air-Gap:** Isolasi fisik atau logis dari sebuah sistem komputasi dari jaringan publik atau internet.
* **Sneakernet:** Metode transfer data elektronik (khususnya transfer file deployment) secara fisik dengan membawa media penyimpanan portabel (USB, SSD, Optical Disc) dari satu sistem ke sistem lain.
* **OCI Layout:** Standar spesifikasi Open Container Initiative untuk menyimpan hierarki image layer dan metadata dalam sistem direktori file lokal.
* **Data Diode:** Perangkat keras jaringan searah yang hanya mengizinkan data mengalir dalam satu arah (misal: masuk ke secure enclave), menjamin secara fisik tidak ada data yang bisa keluar.
* **Helm Post-Renderer:** Fitur CLI Helm yang mengalirkan manifest YAML ter-render ke standard input binary eksternal untuk dimodifikasi sebelum manifest tersebut dieksekusi ke Kubernetes API server.
* **Bastion Host:** Komputer khusus yang didesain dan dikonfigurasi untuk menghadapi serangan (hardened) yang berfungsi sebagai satu-satunya proxy akses untuk mengelola resource di subnet terisolasi.
* **Chicken-and-Egg Registry Problem:** Kegagalan arsitektur di mana registry penyuplai image pod ditempatkan di dalam cluster Kubernetes yang membutuhkan registry tersebut untuk dapat melakukan restart pod-podnya.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Penyediaan Environment Mahasiswa:** Dalam mengajarkan modul ini, jangan pernah biarkan mahasiswa mengetes pipeline mereka pada mesin yang memiliki koneksi internet aktif. Mereka harus menggunakan flag `--internal` pada Docker network atau menggunakan VM dengan interface NIC eksternal di-disable secara eksplisit (`ip link set eth0 down`). Kebocoran akses internet sekecil apa pun akan menyembunyikan kegagalan isolasi DNS/registry.
* **Penekanan Sertifikat Internal (x509):** Banyak engineer junior panik ketika menghadapi error `x509: certificate signed by unknown authority`. Tekankan sesi troubleshooting bagaimana mendistribusikan custom self-signed CA cert ke OS truststore dan containerd directory (`/etc/containerd/certs.d/`).
* **Infrastruktur Bare-Metal:** Selalu ingatkan bahwa di cloud, komponen seperti Load Balancer dan Persistent Disk diurus oleh Cloud Controller Manager (CCM). Di on-premise, jelaskan bahwa mereka butuh **MetalLB** untuk Service `type: LoadBalancer` dan CSI Driver seperti **Rook-Ceph** atau **Longhorn** untuk dynamic PVCs.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 1.0.0 (Maret 2025):** 
  * Rilis perdana modul arsitektur Air-Gapped dan On-Premises Kubernetes.
  * Penambahan skrip automation bundle `skopeo` dan demonstrasi implementasi `Helm post-renderer`.
  * Integrasi studi kasus pencegahan kegagalan DNS dan time-sync drift (NTP).

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** `06-Architecture-and-System-Design/Bab 03 Module 02: Resilient Distributed Systems, Fault Tolerance, and Circuit Breakers`
* **Modul Saat Ini:** `06-Architecture-and-System-Design/Bab 04 Module 01: Infrastruktur Hybrid-Cloud, On-Premises & Air-Gapped Environments`
* **Modul Berikutnya:** `06-Architecture-and-System-Design/Bab 04 Module 02: High-Availability Storage Architectures, CSI Drivers, and Disaster Recovery in Edge Data Centers`