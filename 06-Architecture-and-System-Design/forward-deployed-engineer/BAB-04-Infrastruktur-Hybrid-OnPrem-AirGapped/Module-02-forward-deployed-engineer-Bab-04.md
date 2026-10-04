# BAB 04: Infrastruktur Hybrid, On-Premise & Air-Gapped
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Mendesain Arsitektur Bidirectional & Disconnected Sync**: Merancang topologi sinkronisasi data dan *state machine* antara *Control Plane* (Cloud/SaaS) dan *Data Plane* (On-Premise/Air-Gapped) yang tahan terhadap latensi tinggi, pemutusan jaringan total (*partitioning*), dan *unidirectional data diodes*.
- **Mengimplementasikan Offline Supply Chain Security**: Membangun mekanisme verifikasi integritas artefak (kontainer, Helm *charts*, biner, model bobot ML) menggunakan Cosign, TUF (*The Update Framework*), dan *air-gapped registry mirrors* tanpa ketergantungan pada *public keyserver* atau OCSP *responders*.
- **Mengonfigurasi Rootless & Hardened Kubernetes Runtimes**: Men-deploy kluster Kubernetes on-premise (*bare-metal*) dengan kernel Linux yang dikunci (*hardened*), SE-Linux enforcing, FIPS 140-2/3 compliance, dan jaringan overlay berbasis eBPF (Cilium) tanpa akses internet publik.
- **Mengelola Automated Remediation & Telemetry Egress**: Mengonfigurasi *asynchronous telemetry collection* yang mematuhi restriksi kerahasiaan data (anonimisasi/PII scrubbing di *edge*) dan mengekspornya keluar dari perimeter *air-gapped* menggunakan *staging bastions* atau *removable media staging workflows*.

---

### 2. Prerequisites
Sebelum mendalami modul ini, Anda wajib menguasai:
- **Sistem Operasi & Kernel Linux**: Konfigurasi `systemd`, manajemen *storage* (LVM, ZFS), *cgroups v2*, namespaces, dan mitigasi modul kernel (AppArmor/SELinux).
- **Networking Mendalam**: Arsitektur BGP, VLAN/VXLAN encapsulation, subnetting, mTLS handshake internals, x509 PKI, dan pengoperasian proxy layer-4/layer-7 (Envoy, HAProxy).
- **Container Internals**: OCI specification, *container runtime interface* (containerd/CRI-O), manipulasi image layer dengan `skopeo`, `umoci`, atau `crane`.
- **Dasar Modul 01**: Pemahaman fondasi mengenai karakteristik on-premise vs. cloud native dan definisi *air-gap level 1-4*.

---

### 3. Concept & Internal Architecture

Dalam lanskap operasional seorang *Forward Deployed Engineer* (FDE), instalasi perangkat lunak pada lingkungan *disconnected* (terputus dari internet) atau *hybrid-isolated* mengharuskan pemahaman struktural tentang bagaimana jaringan enterprise dibangun di luar ekosistem AWS/GCP/Azure.

```
+---------------------------------------------------------------------------------------+
|                                    LOW-SIDE (DMZ / Connected)                         |
|  +---------------------+        +--------------------+        +---------------------+  |
|  | Upstream Registries | -----> | CI/CD Packager     | -----> | Staging Bastion     |  |
|  | (Quay, DockerHub)   |        | Bundle & Sign (TUF)|        | (Transfer Staging)  |  |
|  +---------------------+        +--------------------+        +----------+----------+  |
+--------------------------------------------------------------------------|------------+
                                                                           |
                                                                           v
                                                [ PHYSICAL / PROTOCOL AIR-GAP ]
                                                [ Data Diode / Optical Isolator / Crypto ]
                                                                           |
+--------------------------------------------------------------------------|------------+
|                                    HIGH-SIDE (Enclave / Air-Gapped)       v            |
|  +-----------------------+      +--------------------+        +---------------------+  |
|  | On-Prem Node Pool     | <--- | Harvester / Local  | <---   | Ingestion Bastion   |  |
|  | (RKE2 / Cilium eBPF)  |      | Mirror (Harbor/OCI)|        | (Validation & Decrypt|  |
|  +-----------+-----------+      +--------------------+        +---------------------+  |
|              |                                                                        |
|              v                                                                        |
|  +-----------------------+                                                            |
|  | GitOps Engine (Offline|                                                            |
|  | ArgoCD / Local Gitea) |                                                            |
|  +-----------------------+                                                            |
+---------------------------------------------------------------------------------------+
```

#### 3.1. Topology Enclave: The High-Side vs. Low-Side Paradigm
Dalam infrastruktur pertahanan, perbankan inti (*core banking*), dan industri energi (*ICS/SCADA*), jaringan dibagi menjadi dua domain utama:
1. **Low-Side (Unclassified / Connected Zone)**: Memiliki akses langsung atau terbatas ke internet. Lingkungan ini digunakan untuk mengambil paket, memperbarui basis kode, dan membangun rilis kompilasi.
2. **High-Side (Classified / Secure Enclave)**: Dilarang keras memiliki jalur transmisi keluar (*egress*) ke internet terbuka. Semua komunikasi ingress dibatasi secara ketat atau menggunakan *Data Diode* (komunikasi optik satu arah berbasis UDP).

FDE bertugas menjembatani pengiriman perangkat lunak dari *Low-Side* ke *High-Side* tanpa merusak garansi keamanan *high-side*.

#### 3.2. Asynchronous State Reconciliation Architecture
Ketika komponen terdistribusi beroperasi pada High-Side, sistem tidak dapat menggunakan webhook eksternal, auth provider pihak ketiga (seperti Auth0 atau AWS Cognito), atau public NTP pools.
- **Identity Isolation**: High-Side harus menjalankan sistem Identity Provider (IdP) lokal (misalnya Keycloak, FreeIPA, atau Active Directory lokal) yang di-federasikan secara *air-gapped* atau mandiri.
- **Clock Drift Mitigation**: Latensi sistem dan divergensi waktu tanpa akses ke `pool.ntp.org` dapat merusak validitas token JWT, mTLS certificate validation, dan konsistensi Raft (pada etcd). High-Side menggunakan perangkat *hardware PTP (Precision Time Protocol)* atau antena GPS/GNSS khusus yang terpasang di atap data center lokal.
- **Offline Supply Chain Verification (Root of Trust)**: Karena OCSP (Online Certificate Status Protocol) responder tidak dapat dihubungi, sistem x509 PKI harus mengandalkan *static Certificate Revocation Lists (CRL)* lokal yang disuntikkan secara periodik, atau sertifikat berumur pendek (*short-lived certs*) yang diterbitkan oleh *in-enclave intermediate CA*.

---

### 4. Why & What

| Dimensi | Cloud-Native Standar | Hybrid / On-Premise Enterprise | Air-Gapped High-Side |
| :--- | :--- | :--- | :--- |
| **Dependency Resolution** | Dinamis saat build/runtime (`npm install`, `go mod download`, `docker pull`). | Cached proxy lokal (Nexus, Artifactory) dengan fall-through ke upstream. | Nol akses eksternal. Semua dependensi harus di-*vendoring*, di-*freeze*, dan diimpor secara fisik/batch. |
| **Identity & Access** | OAuth2 / OIDC cloud providers, IAM Roles (IRSA). | Active Directory on-premise, SAML 2.0, LDAP. | Isolated Kerberos, Local PKI mTLS, Air-gapped Keycloak. |
| **Patch Management** | Rolling upgrade otomatis via managed service (EKS/GKE). | Terjadwal, semi-manual via blue/green switch. | Manual, diverifikasi melalui sandbox terisolasi, diinjeksikan via staged release bundles. |
| **Observability** | SaaS APM (Datadog, New Relic) via outbound HTTPS. | Self-hosted monitoring stack (Prometheus/Thanos). | Isolated local storage (VictoriaMetrics/Loki) dengan offline batch audit dumps. |
| **Networking** | SDN tervirtualisasi penuh, Cloud VPC, Managed NAT. | VLAN statis, Physical switches, Hardware Load Balancer (F5/BIG-IP). | Calico/Cilium host-routing, BGP peering manual, zero egress NAT, unidirectional diodes. |

#### Mengapa Pola Cloud Native Gagal di Sini?
1. **Dynamic DNS Assumption**: Banyak container berasumsi DNS resolver publik (8.8.8.8, 1.1.1.1) dapat diakses jika resolver internal gagal. Pada High-Side, DNS leak langsung memicu alarm IDS/IPS perimeter.
2. **Hardcoded Upstream CDN Endpoints**: Library yang memanggil Google Fonts, CDN JS publik, atau telemetry tracking akan mengalami timeout tak berujung, memblokir rendering UI atau inisialisasi daemon backend.
3. **Container Image Manifest Layer Pulling**: Mesin runtime modern menarik manifest list multi-arsitektur. Jika registry mirror offline tidak dikonfigurasi dengan skema manifest V2-2 yang tepat, runtime akan crash dengan status `ImagePullBackOff` atau `manifest unknown`.

---

### 5. How (Workflow Detail)

Pengiriman software ke lingkungan air-gapped menuntut standardisasi pipeline berulang (*reproducible pipeline*). Berikut alur kerja end-to-end yang harus dieksekusi FDE:

```
[Tahap 1: Low-Side Packaging]
   │  1.1 Kompilasi kode statis (Go/Rust binary, CGO_ENABLED=0).
   │  1.2 Pull image dari public upstream & mirror dependencies.
   │  1.3 Generate Software Bill of Materials (SBOM) via Syft format CycloneDX.
   │  1.4 Tanda tangani image layers & manifests via Cosign menggunakan Private Key offline.
   │  1.5 Buat `airgap-bundle.tar.zst` (OCI Layout format).
   ▼
[Tahap 2: Transfer & Sanitasi (The "Air-Lock")]
   │  2.1 Ekspor bundle ke media terisolasi (WORM Drive / Sanitized Media).
   │  2.2 Pemindaian malware & deep packet inspection oleh security scanner High-Side.
   │  2.3 Transfer via Unidirectional Data Diode (UDP custom transport) atau fisik.
   ▼
[Tahap 3: High-Side Ingestion & Re-Anchoring]
   │  3.1 Unpack bundle pada Ingestion Bastion.
   │  3.2 Verifikasi signature via Public Key lokal (disimpan dalam hardware HSM/KMS lokal).
   │  3.3 Verifikasi integritas hash SHA256 terhadap manifest SBOM.
   │  3.4 Push OCI layers ke Local Enterprise Registry (Harbor High-Side).
   ▼
[Tahap 4: Declarative Deployment]
   │  4.1 GitOps Controller (ArgoCD High-Side) mendeteksi pembaruan Git internal (Gitea).
   │  4.2 Deployment controller menarik image dari Harbor internal via mTLS murni.
   │  4.3 Pod dijalankan dengan konfigurasi `imagePullPolicy: IfNotPresent`.
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Stasiun Luar Angkasa Internasional (ISS)
Bayangkan aplikasi Anda adalah kru yang hidup di dalam ISS (*High-Side*). 
- ISS tidak memiliki pipa air yang terhubung ke bumi (*Internet*). 
- Jika kru butuh air atau oksigen, mereka tidak bisa "memutar keran" ke bumi secara instan.
- Pasokan harus dikemas ke dalam modul kargo (Kapsul Dragon / *Transfer Bundle*), diuji sterilitasnya dari kontaminasi kuman (*Security Scanning & Malware Inspection*), ditembakkan melalui roket, melewati dok palka satu arah (*Air-lock / Data Diode*), dan didekompresi di dalam modul logistik stasiun (*Harbor Registry Internal*).
- Jika ada satu baut yang tertinggal di bumi, misi gagal karena astronot tidak bisa "membeli" baut pengganti secara online.

```
       LOW-SIDE (Bumi)                         HIGH-SIDE (Stasiun Luar Angkasa)
+-----------------------------+               +----------------------------------+
| - Docker Hub / GitHub       |               | - Bare-metal Nodes               |
| - Package Repos (APT, PyPI) |               | - No WAN / Default Gateway: DROP |
| - Security Scanning Engine  |               | - Internal DNS (.corp.local)     |
+--------------+--------------+               +-----------------+----------------+
               |                                                ^
               v                                                |
   [ OCI Tarball / Bundle ]                                     |
               |                                                |
               v                                                |
   +------------------------+      Transfer Fisik /      +------+-----------------+
   | Media Transfer WORM    | ------------------------>  | Offline Harbor         |
   | (Optical Disc / Dioda) |   Optical Isolation        | Registry Mirror        |
   +------------------------+                            +------------------------+
```

---

### 7. Simple & Practical Implementation Examples

Berikut adalah implementasi standar industri untuk sistem packaging air-gap, pipeline verifikasi, dan deployment runtime hardening.

#### 7.1. Packaging Script: OCI Artifact Bundler (Bash + Skopeo + Zstd)
Skrip ini mengunduh image, menyimpannya dalam format OCI Image Layout murni, menghasilkan manifest integritas, dan mengompresnya menggunakan algoritma `zstd`.

```bash
#!/usr/bin/env bash
# File: package-airgap-bundle.sh
set -euo pipefail

DEST_DIR="./bundle_output"
BUNDLE_NAME="enterprise-core-bundle"
IMAGE_LIST=("registry.k8s.io/coredns/coredns:v1.11.1" "quay.io/cilium/cilium:v1.15.5")

mkdir -p "${DEST_DIR}/oci-cache"
mkdir -p "${DEST_DIR}/metadata"

echo "[1/4] Preserving OCI manifests & pulling layers..."
for IMAGE in "${IMAGE_LIST[@]}"; do
    # Buat safe-name untuk folder lokal
    CLEAN_NAME=$(echo "${IMAGE}" | tr '/:' '_')
    echo "Processing image: ${IMAGE} -> ${CLEAN_NAME}"
    
    skopeo copy \
        --insecure-policy \
        --all \
        --format oci \
        "docker://${IMAGE}" \
        "oci:${DEST_DIR}/oci-cache/${CLEAN_NAME}"
done

echo "[2/4] Generating cryptographic checksums..."
find "${DEST_DIR}/oci-cache" -type f -exec sha256sum {} + > "${DEST_DIR}/metadata/checksums.sha256"

echo "[3/4] Exporting Software Bill of Materials (SBOM)..."
syft dir:"${DEST_DIR}/oci-cache" -o cyclonedx-json="${DEST_DIR}/metadata/sbom.json"

echo "[4/4] Compressing transport bundle with zstd level 19..."
tar -C "${DEST_DIR}" -cf - . | zstd -19 -T0 -o "${BUNDLE_NAME}.tar.zst"

rm -rf "${DEST_DIR}"
echo "SUCCESS: Bundle generated: ${BUNDLE_NAME}.tar.zst"
```

#### 7.2. Production Code: Dynamic High-Side Admission & Registry Rewriter (Go)
Di lingkungan High-Side, pod manifests yang dikirimkan developer sering kali masih mereferensikan registry internet publik (misal: `docker.io/library/nginx`). Mutating Webhook ini secara transparan memetakan ulang domain upstream ke mirror internal perusahaan tanpa memodifikasi source manifest pengembang secara manual.

```go
// File: webhook/main.go
package main

import (
	"context"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"

	admissionv1 "k8s.io/api/admission/v1"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/klog/v2"
)

const InternalRegistryHost = "harbor.enclave.internal/library/"

type WebhookServer struct {
	server *http.Server
}

type patchOperation struct {
	Op    string      `json:"op"`
	Path  string      `json:"path"`
	Value interface{} `json:"value,omitempty"`
}

func (ws *WebhookServer) mutate(w http.ResponseWriter, r *http.Request) {
	var admissionReview admissionv1.AdmissionReview
	if err := json.NewDecoder(r.Body).Decode(&admissionReview); err != nil {
		klog.Errorf("Could not decode request: %v", err)
		http.Error(w, "invalid request", http.StatusBadRequest)
		return
	}

	req := admissionReview.Request
	var pod corev1.Pod
	if err := json.Unmarshal(req.Object.Raw, &pod); err != nil {
		klog.Errorf("Could not unmarshal pod: %v", err)
		http.Error(w, "malformed pod object", http.StatusBadRequest)
		return
	}

	var patches []patchOperation
	for idx, container := range pod.Spec.Containers {
		newImage := rewriteToAirgapRegistry(container.Image)
		if newImage != container.Image {
			patches = append(patches, patchOperation{
				Op:    "replace",
				Path:  fmt.Sprintf("/spec/containers/%d/image", idx),
				Value: newImage,
			})
		}
	}

	patchBytes, err := json.Marshal(patches)
	if err != nil {
		klog.Errorf("Failed to marshal JSON patch: %v", err)
		http.Error(w, "internal server error", http.StatusInternalServerError)
		return
	}

	admissionResponse := admissionv1.AdmissionReview{
		TypeMeta: metav1.TypeMeta{
			APIVersion: "admission.k8s.io/v1",
			Kind:       "AdmissionReview",
		},
		Response: &admissionv1.AdmissionResponse{
			UID:     req.UID,
			Allowed: true,
			Patch:   patchBytes,
			PatchType: func() *admissionv1.PatchType {
				pt := admissionv1.PatchTypeJSONPatch
				return &pt
			}(),
		},
	}

	respBytes, err := json.Marshal(admissionResponse)
	if err != nil {
		klog.Errorf("Failed to encode response: %v", err)
		http.Error(w, "internal server error", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.Write(respBytes)
}

func rewriteToAirgapRegistry(image string) string {
	parts := strings.Split(image, "/")
	imageName := parts[len(parts)-1]
	// Menolak hardcoded DNS publik, mengarahkan ulang semua image ke Harbor internal
	return fmt.Sprintf("%s%s", InternalRegistryHost, imageName)
}

func main() {
	server := &WebhookServer{
		server: &http.Server{
			Addr: ":8443",
		},
	}
	http.HandleFunc("/mutate", server.mutate)
	klog.Info("Starting Airgap Admission Controller on port 8443...")
	if err := server.server.ListenAndServeTLS("/etc/certs/tls.crt", "/etc/certs/tls.key"); err != nil {
		klog.Fatalf("Fatal failed to serve TLS: %v", err)
	}
}
```

#### 7.3. Infrastructure as Code: RKE2 Hardened Air-Gapped Config
File konfigurasi `/etc/rancher/rke2/config.yaml` ini menjamin Kubernetes berjalan dalam status FIPS 140-2, SELinux enforcing, memblokir akses ingress selain port kontrol internal, dan memetakan registrasi kontainer offline.

```yaml
# /etc/rancher/rke2/config.yaml
write-kubeconfig-mode: "0600"
selinux: true
profile: "cis-1.23"

# Nonaktifkan komponen non-esensial dan rentan
disable:
  - rke2-ingress-nginx
  - metrics-server

# Dynamic offline registry routing mirror
system-default-registry: "harbor.enclave.internal"
tls-san:
  - "k8s-api.enclave.internal"
  - "10.240.10.10"

# Isolasi Jaringan: Pods and Services CIDR
cluster-cidr: "10.42.0.0/16"
service-cidr: "10.43.0.0/16"
cluster-dns: "10.43.0.10"

# Kubelet node hardening flags
kubelet-arg:
  - "protect-kernel-defaults=true"
  - "read-only-port=0"
  - "authorization-mode=Webhook"
  - "anonymous-auth=false"
  - "eviction-hard=memory.available<500Mi,nodefs.available<10%"
  - "event-qps=0"

# Audit Logging ke local persistent storage
kube-apiserver-arg:
  - "audit-log-path=/var/log/kube-audit/audit.log"
  - "audit-log-maxage=30"
  - "audit-log-maxbackup=10"
  - "audit-log-maxsize=100"
  - "anonymous-auth=false"
```

---

### 8. Real-World Case Study (Enterprise Scale)

**Klien**: Konsorsium Perbankan Sentral Transaksional  
**Masalah**: Klien mewajibkan implementasi platform *fraud detection engine* berbasis *deep learning inference* pada *High-Performance Cluster (HPC)* on-premise mereka. Regulasi perbankan melarang mesin pemroses transaksi memiliki koneksi Layer-3 ke jaringan mana pun di luar data center bawah tanah (Underground Vault Enclave). Cluster Cloud SaaS reguler tidak dapat digunakan.

**Kondisi Awal**:
- Server tanpa akses internet sama sekali.
- Bastion hanya menerima file via sistem optik unidirectional (Physical Data Diode) dengan MTU terbatas dan kehilangan paket UDP sesekali.
- Tidak tersedia *root access* ke DNS perusahaan; tim network internal butuh waktu 3 bulan untuk mengubah 1 record DNS.
- Pod engine gagal berjalan karena *hardcoded dynamic dependency loading* pada runtime Python (`pip` call terselubung saat startup container).

**Solusi yang Dijalankan Forward Deployed Engineer (FDE)**:
1. **Container Re-Architecting**:
   - Membongkar container image model inferensi. Mengganti PyTorch runtime standar dengan *pre-compiled statically linked binary* menggunakan C++ LibTorch.
   - Meng-embed semua weights tensor model ke dalam layer container lokal menggunakan format *SafeTensors*, mencegah inisialisasi jaringan runtime ke Hugging Face Hub.
2. **Reliable Unidirectional Streaming Protocol**:
   - Menulis *custom UDP Forwarder & Receiver* di atas data diode yang mengimplementasikan *Forward Error Correction (FEC - Reed-Solomon)*.
   - Dengan FEC 20%, tarball paket sistem sebesar 40GB berhasil ditransmisikan menembus *optical diode* satu arah tanpa perlu paket retransmisi (ACK tidak mungkin dikirim kembali karena batasan fisik diode).
3. **Core Cluster Zero-DNS Dependency**:
   - Menghindari DNS overhead dengan mengonfigurasi `CoreDNS` lokal di dalam cluster K8s menggunakan file `hosts` statis yang dibundle ke dalam ConfigMap terenkripsi.
   - Mengimplementasikan Cilium eBPF untuk menggantikan `kube-proxy`, sehingga perutean traffic *East-West* dipetakan secara direct socket routing tanpa NAT translations.

**Hasil**:
- Sistem live dalam 14 hari kalender (dari ekspektasi awal 6 bulan).
- Zero Security Finding pada audit perimeter high-side pihak ketiga.
- Latensi pemrosesan inferensi transaksi mencapai 1.2ms (7x lebih cepat daripada infrastruktur Cloud Hybrid sebelumnya).

---

### 9. Trade-offs & Engineering Decisions

| Matriks Keputusan | Opsi A: Full Air-Gap (Fully Isolated) | Opsi B: Hardware Data Diode (Unidirectional) | Opsi C: Layer-7 Bastion Proxy (Strict Hybrid) |
| :--- | :--- | :--- | :--- |
| **Keamanan Data Exfiltration** | **Mutlak (10/10)**: Nol jalur transmisi radio/fisik keluar. | **Sangat Tinggi (9.5/10)**: Secara fisik mustahil mengirim sinyal balik ke Low-Side. | **Moderat (6/10)**: Tergantung pada potensi zero-day di aplikasi proxy (Envoy, Squid). |
| **Kompleksitas Operasional** | **Sangat Tinggi**: Update butuh kurir fisik/media flash drive tersanitasi. | **Tinggi**: Membutuhkan algoritma *loss recovery* (FEC) pada transport layer. | **Rendah**: Pipeline CI/CD reguler masih bisa mengeksekusi push webhook via egress controller. |
| **Throughput & Latency** | Latensi batch: Hitungan jam atau hari (mengikuti interval update manual). | Throughput tinggi (10 Gbps line-rate optik), latensi transmisi < 1ms, tanpa ACK. | Throughput dibatasi *deep packet inspection* & SSL bumping CPU overhead. |
| **Infrastruktur & Cost** | Biaya operasional teknisi lokal tinggi; biaya lisensi hardware minimal. | Biaya pembelian hardware Data Diode (Owl Cyber Defense / Advenica) sangat mahal ($50k-$200k+). | Menggunakan server x86 standar; biaya lisensi software proxy komersial atau enterprise support. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Kegagalan x509 PKI Akibat "NTP Time Drift"
* **Gejala**: Pod di High-Side mendadak crash dengan error: `x509: certificate has expired or is not yet valid`. Log etcd menunjukkan `clock difference 4.12s is too higher than tolerance 500ms`.
* **Akar Masalah**: Bare-metal hypervisor internal kehilangan sinkronisasi waktu karena CMOS battery drop dan tidak adanya akses ke `pool.ntp.org`. Sistem operasi memajukan/memundurkan jam sistem secara mandiri.
* **Solusi FDE**:
  1. Pasang NTP server lokal berbasis GPS/PPS Hardware (misalnya Meinberg).
  2. Jika hardware terisolasi penuh, konfigurasikan `systemd-timesyncd` atau `chrony` lokal master:
     ```ini
     # /etc/chrony/chrony.conf
     local stratum 8
     manual
     allow 10.0.0.0/8
     ```
  3. Perpanjang validitas sertifikat internal CA darurat hingga 5 tahun untuk menghindari kegagalan instan saat investigasi audit berlangsung.

#### 10.2. MTU Mismatch Over VXLAN / On-Prem Switch
* **Gejala**: Curl ke service pod internal berjalan untuk payload kecil (`curl -I`), tetapi hang/timeout tanpa respon untuk payload besar (seperti transfer gRPC model atau file binary > 1500 bytes).
* **Akar Masalah**: Router fisik enterprise membatasi Interface MTU pada angka 1500 bytes murni. Overlay CNI (seperti Calico atau Flannel VXLAN) menambahkan enkapsulasi header sebesar 50 bytes. Ukuran paket menjadi 1550 bytes, dan bit `DF (Don't Fragment)` aktif, menyebabkan silent drop paket oleh hardware switch.
* **Solusi FDE**: Sesuaikan nilai CNI MTU menjadi `1450` atau aktifkan *Jumbo Frames* (MTU 9000) pada seluruh switchport fisik data center klien:
  ```yaml
  # kubectl edit configmap -n kube-system cilium-config
  bpf-mtu: "1450"
  ```

#### 10.3. DNS Lookup Loop & Fall-through Timeout
* **Gejala**: Startup pod memakan waktu 30-45 detik lebih lama dari seharusnya, menurunkan SLA cold-start.
* **Akar Masalah**: File `/etc/resolv.conf` di-generate secara otomatis oleh NetworkManager host dengan default `options ndots:5` dan domain search enterprise yang panjang (misal: `dept.zone.region.company.internal`). Kubelet mencoba me-resolve nama internal, gagal, lalu fall-through mencari recursive publik yang berujung timeout.
* **Solusi FDE**: Paksa DNS Config di pod level atau konfigurasi kubelet:
  ```yaml
  spec:
    dnsConfig:
      options:
        - name: ndots
          value: "2"
  ```

---

### 11. Best Practices (Production Checklist)

#### Pre-Deployment (Low-Side)
- [ ] Semua image layers dikemas dengan skema multi-arch minimal (`linux/amd64` explicit target).
- [ ] Base OS container menggunakan `distroless` atau `Alpine Hardened`, menghapus package manager (`apt`, `apk`, `yum`) dari container runtime final.
- [ ] SBOM dihasilkan secara otomatis di pipeline dan divalidasi tidak mengandung komponen berlisensi GPL v3 jika klien melarang strictly *copyleft*.
- [ ] Image ditandatangani menggunakan `cosign` dengan keypair lokal berbasis KMS / Hardware Security Key.

#### Ingestion & Perimeter (The Gate)
- [ ] Integritas hash SHA256 diverifikasi pada *Ingestion Bastion* sebelum artefak dipindahkan ke Registry High-Side.
- [ ] Deep File Scan dilakukan oleh engine ClamAV/Yara internal untuk memastikan bundle tarball tidak disusupi skrip trojan/polymorphic malware.
- [ ] Akses SSH ke Bastion hanya menggunakan *hardware-backed FIDO2/U2F keys* dengan audit session recording aktif (misal: Teleport offline cluster).

#### Core Runtime (High-Side Cluster)
- [ ] Kubernetes API Server diamankan dari komunikasi anonim (`--anonymous-auth=false`).
- [ ] Kontainer berjalan sebagai `non-root` user (`runAsNonRoot: true`, `readOnlyRootFilesystem: true`, `allowPrivilegeEscalation: false`).
- [ ] NetworkPolicies default memblokir semua trafik: Default Deny All Ingress & Egress di semua namespace, membuka secara granular berbasis label.
- [ ] Tidak ada referensi URL `http://` atau `https://` eksternal yang di-hardcode di kode aplikasi pengembang.

---

### 12. Hands-on Practice: Membangun Air-Gap Emulation Environment

Latihan ini akan memandu Anda membuat simulasi lingkungan air-gap lengkap menggunakan Docker networks terisolasi di workstation Anda.

#### Skenario Praktikum:
1. Membuat dua virtual network terisolasi: `low-side-net` (terkoneksi internet) dan `high-side-net` (terisolasi total via iptables `internal=true`).
2. Men-deploy Local Mirror Registry (Harbor alternatif ringan: Docker Registry V2) di High-Side.
3. Melakukan packaging image di Low-Side, memindahkannya, dan me-rehost di High-Side.
4. Menjalankan pod test pada k3s container yang hanya terhubung ke `high-side-net`.

#### Direktori Kerja: `hands-on/m02/`

```bash
# 1. Setup direktori kerja
mkdir -p hands-on/m02/{low-side,high-side,certs}
cd hands-on/m02

# 2. Setup isolated docker networks
docker network create --driver bridge low-side-net
# High-side network: internal=true memblokir default gateway eksternal secara fisik di bridge
docker network create --driver bridge --internal high-side-net

# 3. Deploy High-Side Registry (Internal Mirror)
# Hanya dipasangkan pada high-side-net!
docker run -d --name highside-registry \
  --network high-side-net \
  -e REGISTRY_HTTP_ADDR=0.0.0.0:5000 \
  -v $(pwd)/high-side/registry-data:/var/lib/registry \
  registry:2

# 4. LOW-SIDE OPERATION: Unduh dan simpan artifact
docker run --rm -it --network low-side-net \
  -v $(pwd)/low-side:/workdir \
  alpine:latest sh -c "
    apk add --no-cache curl bash skopeo
    # Tarik image dari internet publik
    skopeo copy --insecure-policy docker://docker.io/library/busybox:latest docker-archive:/workdir/busybox.tar:busybox:latest
  "

# 5. AIR-LOCK TRANSFER: Validasi & Pindahkan Bundle
# Simulasikan validasi hash integritas
sha256sum low-side/busybox.tar > high-side/busybox.tar.sha256
cp low-side/busybox.tar high-side/busybox.tar
cd high-side && sha256sum -c busybox.tar.sha256 && cd ..

# 6. HIGH-SIDE OPERATION: Push bundle ke mirror internal
# Jalankan helper container di high-side-net untuk mengisi mirror
docker run --rm -it --network high-side-net \
  -v $(pwd)/high-side:/workdir \
  alpine:latest sh -c "
    apk add --no-cache skopeo
    # Copy dari file tar ke registry internal High-Side
    skopeo copy --insecure-policy docker-archive:/workdir/busybox.tar docker://highside-registry:5000/core/busybox:latest
  "

# 7. VERIFIKASI HIGH-SIDE WORKLOAD EXECUTION
# Jalankan isolated container di high-side-net yang membuktikan image di-pull dari mirror, bukan internet
docker run --rm --network high-side-net \
  highside-registry:5000/core/busybox:latest \
  sh -c "echo 'SUCCESS: Air-gap container running seamlessly from local mirror!' && ping -c 1 -W 2 8.8.8.8 || echo 'NETWORK CONFIRMED AIR-GAPPED: Ping failed as expected.'"
```

---

### 13. Exercises

#### Level Easy
Tuliskan satu baris perintah `skopeo` yang dapat menduplikasi seluruh repository image (termasuk tag) dari upstream registry ke folder OCI layout offline lokal tanpa menjalankan docker daemon di mesin packaging.

#### Level Medium
Buat sebuah script Bash sanitasi yang mengurai manifest `k8s-manifest.yaml`, mendeteksi semua string URL `image: ...`, memvalidasi apakah domain image tersebut berasal dari registry internal perusahaan (`registry.corp.internal`), dan menggagalkan eksekusi (exit code 1) jika ditemukan manifest yang memanggil registry publik eksternal (misal: Docker Hub, GCR, Quay).

#### Level Hard
Buat script automasi Go (tanpa dependency eksternal, hanya stdlib) yang membaca folder berisikan ribuan file layer container (`.tar` atau blob), menghasilkan hash verification tree (mirip Merkle tree sederhana), dan mencocokkannya dengan `signatures.json`. Jika ada 1 byte saja layer yang termutasi/rusak saat transfer media fisik, script harus mengeluarkan pesan error yang menyebutkan digest blob yang korup dan mengembalikan status non-zero exit code.

---

### 14. Real-World Architectural Challenge

**Konteks**: Anda ditugaskan sebagai Lead FDE di pangkalan lepas pantai (*Offshore Drilling Platform*). Platform ini terhubung dengan kantor pusat di darat HANYA via satelit berkecepatan rendah (Bandwidth: 128 Kbps, Latency: 900ms, Packet Loss: 8%). 

**Kondisi Krisis**:
Terdapat deployment darurat untuk patch sistem kontrol turbin. Ukuran container patch adalah 1.8 GB. Upstream management meminta Anda menerapkan CI/CD standard, yang langsung gagal karena rsync/docker pull mengalami broken pipe dan timeout berulang kali. Anda TIDAK BISA menggunakan media fisik karena helikopter logistik baru akan datang 3 minggu lagi.

**Misi Anda**:
1. Rancang arsitektur sinkronisasi layer data yang sanggup mentransfer update 1.8 GB ini melewati link satelit 128 Kbps tersebut secara reliabel.
2. Identifikasi bagaimana Anda memanfaatkan teknik *Layer Deconstruction & Content Addressed Chunking* untuk meminimalkan data yang ditransfer (misal: hanya mentransfer delta binary via rolling hash algoritma bsdiff/zsync).
3. Buat skema *Resume-Capable Transfer Protocol* yang memecah file menjadi blok-blok kecil (misal: 1MB chunks) yang ditransmisikan secara independen dan diassemble ulang di edge cluster dengan validasi hash SHA-256 stateful.

---

### 15. Quiz Evaluasi Pemahaman

#### 5 Pertanyaan Konseptual (Basic)
1. Apa perbedaan utama antara isolasi jaringan Level-3 standar dan isolasi menggunakan *Hardware Optical Data Diode*?
2. Mengapa protokol NTP sangat penting dan sering menjadi *single point of failure* dalam enkripsi mTLS di jaringan *air-gapped*?
3. Mengapa parameter `imagePullPolicy: Always` berbahaya jika dikonfigurasi pada manifest pod di lingkungan disconnected?
4. Apa fungsi dari *Software Bill of Materials (SBOM)* dalam konteks audit kepatuhan rantai pasok software high-side?
5. Mengapa teknik dynamic compilation (misalnya mendownload dependency runtime saat pod bootstrap) dilarang keras di kluster on-premise high-side?

#### 5 Pertanyaan Desain & Implementasi (Intermediate)
6. Bagaimana cara kerja verifikasi tanda tangan container image menggunakan `Cosign` pada sistem yang tidak memiliki koneksi internet ke *Sigstore Public Rekor Transparency Log*?
7. Jika interface MTU di switch jaringan fisik adalah 1500 bytes, mengapa penggunaan overlay CNI berbasis VXLAN dapat menyebabkan freeze pada session HTTP payload besar, dan bagaimana cara memitigasinya?
8. Bagaimana Anda mendesain mekanisme log egress dari zona classified High-Side ke analitik Low-Side tanpa membuka celah ingress ke dalam High-Side?
9. Mengapa konfigurasi SELinux mode `Enforcing` sering kali mematahkan persistent volume mount pada Kubernetes on-premise bare-metal, dan flag apa yang harus disuntikkan pada konteks keamanan pod?
10. Pada saat melakukan transfer bundle via media fisik terenkripsi, teknik apa yang digunakan untuk memastikan bahwa media penyimpanan itu sendiri tidak mengeksekusi *BadUSB* atau *Autorun firmware attack* pada Ingestion Bastion?

#### 3 Skenario Kasus Produksi
11. **Skenario 1**: Anda men-deploy kluster high-side baru. Semua image kontainer telah di-push ke Harbor registry lokal internal. Namun, saat pod di-deploy, pod macet dalam siklus crash dengan pesan `x509: certificate signed by unknown authority`. Jelaskan tiga kemungkinan titik kegagalan pada trust chain dan bagaimana Anda memperbaikinya dari level Linux host hingga level containerd runtime!
12. **Skenario 2**: Sebuah aplikasi AI/ML membutuhkan token autentikasi model yang di-refresh setiap jam dari server lisensi pusat di cloud. Namun, cluster klien berada di air-gap level 4 (tanpa transmisi elektronik apa pun). Bagaimana Anda mendesain arsitektur *Licensing & Entitlement Validation* yang tetap menjaga integritas bisnis tanpa menuntut koneksi internet real-time?
13. **Skenario 3**: Terjadi insiden performa di mana etcd cluster on-premise mengalami *leader election flaps* setiap kali proses backup snapshot berjalan pada storage LVM internal. Analisis bottleneck hardware apa yang menjadi penyebab masalah ini dan rancang solusi arsitektur disk I/O isolations untuk etcd!

---

### 16. Summary

Mengoperasikan sistem kelas enterprise sebagai seorang *Forward Deployed Engineer* di infrastruktur hybrid, on-premise, dan *air-gapped* membutuhkan perubahan paradigma mendasar dari pola pikir pengembang cloud native.

```
       Kemandirian Penuh (Self-Sufficiency)
                        ▲
                        │
       [Reliabilitas] ──┼── [Integritas Kriptografis]
                        │
                        ▼
            Determinisme Deterministik
```

1. **Determinisme Mutlak**: Tidak boleh ada artefak, dependensi, konfigurasi, atau time synchronization yang diasumsikan "tersedia secara ajaib di internet". Semua aset harus dideklarasikan, diverifikasi, dan dibungkus secara deterministik.
2. **Kemandirian Penuh (Self-Sufficiency)**: Setiap enclave High-Side harus dirancang sebagai sistem yang mampu pulih sendiri (*self-healing*) dan terisolasi penuh dari kegagalan eksternal, termasuk hilangnya konektivitas permanen dengan control-plane cloud.
3. **Integritas Rantai Pasok**: Di lingkungan yang tidak memiliki koneksi real-time, integritas kriptografis (tanda tangan digital, verifikasi hash SHA256 layer, SBOM) adalah satu-satunya dinding pertahanan melawan injeksi supply chain attack sebelum artefak disuntikkan ke dalam sistem komputasi inti.