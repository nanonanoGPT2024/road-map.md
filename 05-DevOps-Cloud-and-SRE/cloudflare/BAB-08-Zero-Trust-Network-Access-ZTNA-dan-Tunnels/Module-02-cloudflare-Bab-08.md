# BAB 08: Zero Trust Network Access (ZTNA) dan Tunnels
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Merancang dan mengimplementasikan arsitektur **Cloudflare Zero Trust Network Access (ZTNA)** enterprise menggunakan **Cloudflare Tunnel (`cloudflared`)** dalam konfigurasi *High Availability (HA)* multi-replica.
- Mengonfigurasi **Private Network Routing (L4/CIDR)** melalui Tunnel untuk mengeliminasi ketergantungan pada VPN konsentrator warisan (legacy hub-and-spoke VPN).
- Mengintegrasikan **Identity Provider (IdP)** enterprise berbasis OIDC/SAML 2.0 (seperti Okta atau Azure AD/Entra ID) dengan penegakan kebijakan bersyarat (*conditional access policies*).
- Mengonfigurasi dan memvalidasi **Device Posture Checks** (mTLS, CrowdStrike Falcon integration, OS Version, dan Disk Encryption status) sebelum akses ke jaringan privat diberikan.
- Mengotomatisasi seluruh siklus hidup infrastruktur ZTNA (Tunnel, Access Applications, Policies, Posture Checks, dan Routing) menggunakan **Terraform / OpenTofu**.
- Mendiagnosis degradasi performa, kegagalan *handshake* QUIC, dan kendala *routing asymmetric* pada skala produksi.

---

### 2. Prerequisites

Sebelum mempelajari modul ini, Anda wajib memiliki pemahaman mendalam dan akses terhadap:
- **Konsep Jaringan Lanjutan**: Model OSI L4 (TCP/UDP) vs L7 (HTTP/S), IP Routing, CIDR, Split-Tunneling, DNS resolution internal vs publik, TLS 1.3 handshake, dan mTLS.
- **Protokol QUIC & HTTP/3**: Pemahaman alur UDP-based multiplexing, zero-RTT connection establishment, dan mitigasi Head-of-Line (HoL) blocking.
- **Identity & Access Management (IAM)**: Alur autentikasi OIDC (Authorization Code Flow with PKCE) dan SAML 2.0 assertion.
- **Tooling**:
  - `cloudflared` CLI versi `>= 2024.x` terinstal pada target server/bastion.
  - Terraform/OpenTofu versi `>= 1.6.x` dengan Cloudflare Provider versi `>= 4.x`.
  - Docker & Kubernetes (opsional, untuk deployment HA connector).
  - Akun Cloudflare berbayar/enterprise dengan langganan Zero Trust (Access & Gateway).

---

### 3. Concept & Internal Architecture

Implementasi enterprise Cloudflare ZTNA dibangun di atas dua fondasi utama: **Cloudflare Access** (L7 Identity-Aware Proxy) dan **Cloudflare Tunnels** (L4/L7 Bidirectional Edge Connectors).

```
+-----------------------------------------------------------------------------------+
|                            CLOUDFLARE EDGE (GLOBAL ANYCAST)                       |
|                                                                                   |
|   +---------------------------------------------------------------------------+   |
|   |                       WARP Ingress (WireGuard / UDP 2408)                 |   |
|   +---------------------------------------------------------------------------+   |
|                                         |                                         |
|                                         v                                         |
|   +---------------------------------------------------------------------------+   |
|   |                        ZTNA Policy & Posture Engine                       |   |
|   |  - Identity Assertion Check (Okta/Azure AD JWT Validation)                |   |
|   |  - Device Posture (CrowdStrike ZTA / Intune / OS / Disk Encryption)       |   |
|   +---------------------------------------------------------------------------+   |
|                                         |                                         |
|                     +-------------------+-------------------+                     |
|                     |                                       |                     |
|                     v                                       v                     |
|        [L7 Proxy: HTTP/gRPC/WS]                [L4 Router: Virtual IP Route]       |
|                     |                                       |                     |
|                     +-------------------+-------------------+                     |
|                                         |                                         |
|                                         v                                         |
|   +---------------------------------------------------------------------------+   |
|   |                   Tunnel Multiplexer (QUIC - UDP Port 7844)               |   |
|   +---------------------------------------------------------------------------+   |
+-----------------------------------------|-----------------------------------------+
                                          | Outbound UDP/QUIC (No Inbound Ports)
                                          v
+-----------------------------------------------------------------------------------+
|                        CUSTOMER PRIVATE ENVIRONMENT (ON-PREM / VPC)               |
|                                                                                   |
|   +------------------------------------+ +------------------------------------+   |
|   |     cloudflared Replica A (Active) | |     cloudflared Replica B (Active) |   |
|   +------------------------------------+ +------------------------------------+   |
|                     \                                     /                       |
|                      v                                   v                        |
|       +------------------------------------------------------------------+        |
|       |               Private Network (VPC / On-Prem Subnet)             |        |
|       |   - Internal K8s API (10.100.0.1:443)                            |        |
|       |   - Production RDS PostgreSQL (10.100.20.15:5432)                |        |
|       +------------------------------------------------------------------+        |
+-----------------------------------------------------------------------------------+
```

#### 3.1. Anatomi dan Lifecycle `cloudflared` Daemon
Daemon `cloudflared` beroperasi sepenuhnya sebagai klien *egress-only*. Daemon tidak pernah membuka *inbound port* pada firewall lokal Anda.
1. **Bootstrap & Autentikasi**: Saat startup, daemon mengautentikasi ke Cloudflare Control Plane menggunakan Tunnel Token (kredensial berbasis JWT/Secret yang di-generate via API/Terraform).
2. **Anycast Edge Discovery**: Daemon menyelesaikan DNS Anycast untuk mencari dua *Point of Presence* (PoP) Cloudflare terdekat secara geografis dan latensi jaringan.
3. **Multi-Tunnel Mesh Connection**: Daemon menginisiasi 4 koneksi paralel independen (2 koneksi per PoP). Secara default, koneksi ini menggunakan protokol **QUIC** (UDP port 7844). Jika UDP terblokir oleh firewall lokal, koneksi fallback ke **HTTP/2 over TLS** (TCP port 7844/443).
4. **Multiplexing**: Setiap request dari edge ke upstream diarahkan melalui koneksi QUIC yang sudah established menggunakan sistem multiplexed virtual streams (`quic-go` implementation).

#### 3.2. Penegakan Kebijakan (Edge Policy Enforcement)
Ketika pengguna mencoba mengakses resource privat:
1. **Device Posture Collection**: Cloudflare WARP client pada perangkat endpoint mengirimkan telemetri secara periodik (setiap 5 menit secara default, atau *event-driven*) ke Cloudflare Edge via protokol WireGuard. Telemetri memuat status enkripsi disk, running processes (e.g., EDR sensor), dan sertifikat mTLS.
2. **Context-Aware Evaluation**: Saat user mengirimkan paket SYN L4 atau HTTP GET L7, Edge menginterupsi request. Cloudflare Access memverifikasi validitas token sesi (IdP JWT), memeriksa apakah atribut user (e.g., grup AD) cocok, dan mencocokkan *posture rule* real-time.
3. **Data Path Execution**: Jika lolos validasi, traffic disalurkan ke tunnel yang terikat dengan rute jaringan privat tujuan.

---

### 4. Why & What

| Fitur / Parameter | Legacy Concentrator VPN (IPsec/OpenVPN) | Cloudflare ZTNA & Tunnels |
| :--- | :--- | :--- |
| **Attack Surface** | Terbuka ke internet publik (Inbound open ports: UDP 500/4500, TCP 1194). Rentan zero-day RCE pada gateway. | Zero inbound open ports. Perimeter firewall lokal menerapkan `DENY ALL` inbound. |
| **Model Keamanan** | Kastil & Parit (Perimeter-based). Sekali terhubung, user memiliki akses lateral ke seluruh subnet. | Least Privilege (Micro-segmentation). Akses diberikan per-aplikasi atau per-host/port spesifik via identity & device posture. |
| **Routing Architecture** | Sentralisasi traffic (Tromboning / Hairpinning) melalui satu data center terpusat, menimbulkan bottle-neck latensi. | Global Anycast Routing. Traffic dialihkan ke PoP Cloudflare terdekat dari user, lalu disalurkan via backbone privat Cloudflare. |
| **High Availability (HA)** | Membutuhkan setup active-passive yang kompleks (VRRP, CARP) dengan downtime saat failover. | Cloud-native multi-replica Active-Active. Traffic di-load balance di edge secara transparan tanpa sesi terputus. |
| **Device Trust Context** | Terbatas pada kredensial login atau sertifikat statis pada saat koneksi awal VPN dibuat. | Continuous verification. Jika agent EDR mati di endpoint di tengah sesi, akses langsung diputus di edge. |

---

### 5. Workflow Detail

Alur berikut menjelaskan siklus hidup end-to-end dari autentikasi pengguna hingga eksekusi kueri pada basis data PostgreSQL privat tanpa *public IP*:

```
+--------+           +-------------+      +-------------------+      +----------------+      +---------------+
|  WARP  |           |     IdP     |      |  Cloudflare Edge  |      |  cloudflared   |      | Internal App/ |
| Client |           | (Okta/Entra)|      |   (ZTNA Engine)   |      |   (Replica)    |      | Database (DB) |
+--------+           +-------------+      +-------------------+      +----------------+      +---------------+
    |                       |                       |                         |                       |
    |-- 1. Resolve DB DNS ->|                       |                         |                       |
    |   (db.internal.corp)  |                       |                         |                       |
    |---------------------------------------------->|                         |                       |
    |   2. Intercept: WireGuard Tunnel (UDP 2408)   |                         |                       |
    |                       |                       |                         |                       |
    |<- 3. Auth Redirect (If no active session) ----|                         |                       |
    |---------------------->|                       |                         |                       |
    |   4. User Login & MFA |                       |                         |                       |
    |                       |-- 5. Return SAML/OIDC |                         |                       |
    |                       |      Assertion ------>|                         |                       |
    |                                               |                         |                       |
    |-- 6. Collect & Push Device Posture Telemetry->|                         |                       |
    |   (OS, BitLocker, CrowdStrike Agent Status)   |                         |                       |
    |                                               |-- 7. Policy Engine ---- |                       |
    |                                               |      Evaluation Passed  |                       |
    |                                               |                         |                       |
    |-- 8. Forward DB Query (TCP Payload) --------->|                         |                       |
    |                                               |-- 9. Encapsulate into ->|                       |
    |                                               |   QUIC Stream (UDP 7844)|                       |
    |                                               |                         |-- 10. Forward TCP --->|
    |                                               |                         |       Raw Stream      |
    |                                               |                         |                       |
    |                                               |                         |<-- 11. Response Data -|
    |                                               |<- 12. Return Payload ---|                       |
    |<-- 13. Deliver Decapsulated Data to App ------|                         |                       |
    |                                               |                         |                       |
```

1. Klien mengakses `db.internal.corp:5432`.
2. WARP Client menangkap kueri DNS lokal dan mencocokkannya dengan *Split Tunnel Inclusive Route* (misal: `10.100.0.0/16`).
3. Sesi dialihkan ke Cloudflare Edge via tunnel WireGuard terenkripsi.
4. Jika session token JWT kedaluwarsa atau belum ada, Cloudflare Edge memicu flow OIDC/SAML ke IdP Enterprise.
5. IdP memvalidasi user, MFA, lalu mereturn signed assertions ke Cloudflare.
6. WARP Client mengirimkan data posture terkini. Edge memverifikasi integritas endpoint (CrowdStrike Zero Trust Assessment Score >= 80, Disk Encryption = Active).
7. Access Policy Engine memvalidasi kesesuaian: `User in Group 'Data-Engineers'` AND `Device Posture == Healthy`.
8. Edge mengarahkan trafik L4 ke Tunnel ID yang mengumumkan subnet `10.100.20.0/24`.
9. Edge mengeksekusi multiplexing payload TCP ke dalam stream QUIC aktif yang mengarah ke `cloudflared`.
10. `cloudflared` menerima stream, mengonversinya menjadi koneksi TCP standar lokal, dan menyambungkannya ke IP PostgreSQL `10.100.20.15:5432`.
11. Paket balasan dieksekusi secara simetris kembali ke pengguna.

---

### 6. Analogi & Diagram ASCII

#### Analogi: Bandara Internasional VVIP dan Koridor Diplomatik
Bayangkan jaringan korporat Anda adalah sebuah fasilitas riset rahasia di dalam sebuah negara:
- **Legacy VPN** ibarat memberikan kunci gerbang perimeter utama beserta kartu pas umum kepada tamu. Sekali tamu melewati pagar luar, mereka bebas berjalan di selasar, membuka pintu-pintu ruangan yang tidak terkunci, dan mengintip aktivitas di seluruh gedung.
- **Cloudflare ZTNA** ibarat mengeliminasi seluruh pintu gerbang luar. Fasilitas Anda tidak memiliki alamat publik di peta dan tidak memiliki pintu masuk fisik dari luar. Sebaliknya, fasilitas mengirimkan **kurir diplomatik internal (`cloudflared`)** untuk standby di Terminal Khusus Bandara Internasional (**Cloudflare Anycast Edge**). Tamu yang ingin berinteraksi harus mendatangi bandara tersebut, memperlihatkan paspor diplomatik (**IdP Authentication**), menjalani pemeriksaan kesehatan dan pemindai x-ray biometrik (**Device Posture Check**). Jika diizinkan, kurir diplomatik internal akan mengambil dokumen dari tamu di bandara, membawanya pulang melalui jalur bawah tanah tertutup, memprosesnya ke lab internal, dan mengantarkan jawabannya kembali ke bandara.

#### Diagram Topologi Produksi (Multi-Cloud Hybrid HA)

```
                 =========================================================
                                  INTERNET / REMOTE USERS
                 =========================================================
                        |                                       |
                 [WARP Client A]                         [WARP Client B]
                 (Device Healthy)                        (EDR Compromised)
                        |                                       |
                        v                                       v
                 =========================================================
                               CLOUDFLARE ANYCAST EDGE
                 =========================================================
                 |  [Policy Engine]                      [Policy Engine] |
                 |  Allowed -> Identity + Posture OK     Blocked: EDR NG |
                 =========================================================
                        |                                       |
           +------------+------------+                          X (Dropped)
           |                         |
           v (QUIC Multiplex)        v (QUIC Multiplex)
    +--------------------+    +--------------------+
    | AWS VPC (us-east-1)|    | GCP VPC (asia-se1) |
    | Subnet:            |    | Subnet:            |
    | 10.100.0.0/16      |    | 10.200.0.0/16      |
    |                    |    |                    |
    |  +---------------+ |    |  +---------------+ |
    |  | cloudflared   | |    |  | cloudflared   | |
    |  | Pod / Node 1  | |    |  | Pod / Node 1  | |
    |  +-------+-------+ |    |  +-------+-------+ |
    |          |         |    |          |         |
    |  +-------+-------+ |    |  +-------+-------+ |
    |  | cloudflared   | |    |  | cloudflared   | |
    |  | Pod / Node 2  | |    |  | Pod / Node 2  | |
    |  +-------+-------+ |    |  +-------+-------+ |
    |          |         |    |          |         |
    |          v         |    |          v         |
    |    [Internal K8s   |    |    [Internal Cloud |
    |     Control Plane] |    |     Spanner/SQL]   |
    +--------------------+    +--------------------+
```

---

### 7. Implementation: Simple & Practical Examples

Berikut adalah implementasi deklaratif menggunakan arsitektur **Infrastructure as Code (IaC)** dengan Terraform untuk penyediaan zero-trust production stack, serta manifes deployment Kubernetes untuk *high availability*.

#### 7.1. Terraform Production Configuration

```hcl
# main.tf
terraform {
  required_version = ">= 1.6.0"
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.35.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6.0"
    }
  }
}

variable "cloudflare_account_id" {
  type        = string
  description = "Account ID Cloudflare Enterprise"
}

variable "cloudflare_zone_id" {
  type        = string
  description = "Target DNS Zone ID"
}

variable "corporate_domain" {
  type        = string
  default     = "corp.internal-infra.net"
  description = "Domain FQDN untuk akses internal"
}

# Generate secure 32-byte secret untuk Tunnel Authentication
resource "random_id" "tunnel_secret" {
  byte_length = 32
}

# 1. Mendefinisikan Zero Trust Cloudflared Tunnel
resource "cloudflare_zero_trust_tunnel_cloudflared" "ha_k8s_tunnel" {
  account_id = var.cloudflare_account_id
  name       = "prod-core-k8s-tunnel"
  secret     = random_id.tunnel_secret.b64_std
}

# 2. Mendefinisikan Private Subnet Route (L4 CIDR)
resource "cloudflare_zero_trust_tunnel_cloudflared_route" "vpc_private_route" {
  account_id    = var.cloudflare_account_id
  tunnel_id     = cloudflare_zero_trust_tunnel_cloudflared.ha_k8s_tunnel.id
  network       = "10.100.0.0/16"
  comment       = "Production AWS VPC Core Network Route"
}

# 3. Tunnel Configuration (Ingress Rules L7 & Catch-All)
resource "cloudflare_zero_trust_tunnel_cloudflared_config" "ha_tunnel_config" {
  account_id = var.cloudflare_account_id
  tunnel_id  = cloudflare_zero_trust_tunnel_cloudflared.ha_k8s_tunnel.id

  config {
    warp_routing {
      enabled = true
    }

    # Aturan L7: Web UI Internal Admin
    ingress_rule {
      hostname = "admin.${var.corporate_domain}"
      service  = "https://internal-admin.core.svc.cluster.local:8443"
      origin_request {
        connect_timeout          = "15s"
        no_tls_verify            = false
        ca_pool                  = "/etc/cloudflared/certs/internal-ca.pem"
        http2_origin             = true
        keep_alive_connections   = 100
        keep_alive_timeout       = "90s"
      }
    }

    # Aturan Catch-All (Wajib di akhir ingress rules)
    ingress_rule {
      service = "http_status:404"
    }
  }
}

# 4. Device Posture Rule: Memastikan Enkripsi Disk & Min OS
resource "cloudflare_zero_trust_device_posture_rule" "disk_encryption_check" {
  account_id = var.cloudflare_account_id
  name       = "Corporate Disk Encryption Required"
  type       = "disk_encryption"
  schedule   = "5m"
  
  match {
    platform = "mac"
  }
  input {
    requireCheck = true
  }
}

# 5. Access Application Definition
resource "cloudflare_zero_trust_access_application" "admin_portal" {
  account_id                = var.cloudflare_account_id
  name                      = "Kubernetes Core Admin Portal"
  domain                    = "admin.${var.corporate_domain}"
  type                      = "self_hosted"
  session_duration          = "8h"
  auto_redirect_to_identity = true

  destinations {
    uri = "admin.${var.corporate_domain}"
  }
}

# 6. Access Policy: Strict Conditional Access
resource "cloudflare_zero_trust_access_policy" "strict_eng_policy" {
  account_id             = var.cloudflare_account_id
  application_id         = cloudflare_zero_trust_access_application.admin_portal.id
  name                   = "Engineering Core Access Policy"
  decision               = "allow"
  precedence             = 1

  include {
    email_domain = ["enterprise-corp.com"]
  }

  require {
    device_posture = [cloudflare_zero_trust_device_posture_rule.disk_encryption_check.id]
  }
}

# Output Tunnel Token untuk dideploy ke Kubernetes Secret
output "tunnel_token" {
  value     = cloudflare_zero_trust_tunnel_cloudflared.ha_k8s_tunnel.tunnel_token
  sensitive = true
}
```

#### 7.2. Production-Grade Kubernetes Daemon Manifest

Manifes ini menerapkan implementasi kontainer HA dengan proteksi non-root, liveness probe berbasis metrik HTTP, pod anti-affinity, dan alokasi resource limits yang ketat.

```yaml
# cloudflared-ha-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cloudflared-core-tunnel
  namespace: networking-infra
  labels:
    app.kubernetes.io/name: cloudflared
    app.kubernetes.io/component: ztna-connector
    app.kubernetes.io/part-of: edge-infrastructure
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app.kubernetes.io/name: cloudflared
  template:
    metadata:
      labels:
        app.kubernetes.io/name: cloudflared
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "2000"
        prometheus.io/path: "/ready"
    spec:
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              podAffinityTerm:
                labelSelector:
                  matchExpressions:
                    - key: app.kubernetes.io/name
                      operator: In
                      values:
                        - cloudflared
                topologyKey: "kubernetes.io/hostname"
      securityContext:
        runAsNonRoot: true
        runAsUser: 65532
        runAsGroup: 65532
        fsGroup: 65532
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: connector
          image: cloudflare/cloudflared:2024.4.1
          imagePullPolicy: IfNotPresent
          args:
            - tunnel
            - --no-autoupdate
            - --metrics
            - 0.0.0.0:2000
            - --protocol
            - quic
            - run
          env:
            - name: TUNNEL_TOKEN
              valueFrom:
                secretKeyRef:
                  name: cloudflare-tunnel-credentials
                  key: token
            - name: TUNNEL_TRANSPORT_LOGLEVEL
              value: "warn"
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "500m"
              memory: "512Mi"
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop:
                - ALL
          livenessProbe:
            httpGet:
              path: /ready
              port: 2000
            initialDelaySeconds: 10
            periodSeconds: 10
            timeoutSeconds: 3
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /ready
              port: 2000
            initialDelaySeconds: 5
            periodSeconds: 5
            timeoutSeconds: 2
            successThreshold: 1
            failureThreshold: 2
```

---

### 8. Real World Case Study: Skala Enterprise

#### Skenario Kasus
- **Perusahaan**: Multinasional Payment Gateway (Fintech) dengan 3.500 engineers, terdistribusi secara global di 4 benua.
- **Kondisi Awal (Legacy)**:
  - Menggunakan appliance VPN konsentrator terpusat (Palo Alto GlobalProtect) di 2 data center (Frankfurt dan Virginia).
  - Seluruh engineer harus melalui VPN untuk mengakses production database (Postgres, Redis) dan ratusan cluster Kubernetes privat di AWS VPC.
  - Masalah: Latensi tinggi bagi engineer APAC (+280ms round-trip ke Frankfurt), beban throughput VPN mencapai 8 Gbps saat jam sibuk, sering terjadi kegagalan koneksi (*split-tunnel leakage*), audit kepatuhan PCI-DSS menemukan bahwa izin lateral antar-subnet terlalu longgar.

#### Desain Solusi Implementasi
1. Mengganti appliance VPN dengan **Cloudflare ZTNA Private Network Routing** dan **Access L7 Apps**.
2. Di setiap cluster EKS dan subnet database VPC, di-deploy 4 replica pod `cloudflared` menggunakan Terraform.
3. Subnet VPC di-advertise sebagai rute privat ke Cloudflare Zero Trust Routing Table (`10.100.0.0/16`, `10.101.0.0/16`).
4. Autentikasi diintegrasikan ke **Okta IdP via OIDC** dengan MFA FIDO2 (WebAuthn).
5. Penegakan **Device Posture**:
   - Device wajib terdaftar di Microsoft Intune.
   - CrowdStrike Falcon Sensor wajib aktif dengan score Zero Trust Assessment (ZTA) minimal 85.
   - Sertifikat mTLS internal wajib valid pada sistem operasi endpoint.

#### Metrik Keberhasilan & Hasil

```
+------------------------------------+--------------------------+--------------------------+
| Metrik Kinerja & Operasional       | Sebelum (Legacy VPN)     | Sesudah (Cloudflare ZTNA)|
+------------------------------------+--------------------------+--------------------------+
| Rata-rata Latensi APAC ke EKS      | 285 ms (Hairpinning EU)  | 42 ms (Edge Anycast HKG) |
| Downtime Tahunan Akses Bastion     | 18.4 Jam                 | 0 Jam (No Single Point)  |
| Insiden Akses Lateral Terdeteksi   | 14 insiden / kuartal     | 0 (Micro-segmented L4/L7)|
| Biaya Bandwidth Egress VPN Gateway | $32,000 / bulan          | $0 (Egress via Tunnel)   |
| Waktu Onboarding Engineer Baru     | Rata-rata 2 hari         | < 15 Menit               |
+------------------------------------+--------------------------+--------------------------+
```

---

### 9. Trade-offs Architecture Matrix

| Komponen / Keputusan | Opsi A | Opsi B | Trade-off Implication |
| :--- | :--- | :--- | :--- |
| **Tunnel Protocol** | **QUIC (UDP Port 7844)** | **HTTP/2 (TCP Port 443/7844)** | QUIC mengeliminasi Head-of-Line blocking pada jaringan lossy dan memberikan performa throughput terbaik. Namun, beberapa firewall korporat memblokir UDP keluar secara default, sehingga memerlukan fallback manual atau otomatis ke HTTP/2. |
| **WARP Client Architecture** | **Split Tunnel (Exclude Mode)** | **Split Tunnel (Include Mode)** | **Exclude Mode** mengirimkan semua trafik internet publik melalui Cloudflare Gateway (bagus untuk deep packet inspection, tetapi mengonsumsi bandwidth besar). **Include Mode** hanya merutekan CIDR privat korporat (kinerja optimal untuk trafik internet pribadi developer, namun blind spot terhadap ancaman malware internet umum). |
| **Connector Deployment** | **Kubernetes StatefulSet / Deployment** | **Dedicated VM Appliance (EC2/GCE)** | Menjalankan `cloudflared` di Kubernetes menghemat biaya dan mempermudah auto-scaling horizontal. Namun, jika cluster Kubernetes mengalami *control-plane failure*, akses *troubleshooting* jaringan privat ke node underlying bisa terputus. |
| **Access Ingress Mode** | **L7 Proxy Ingress (CNAME hostname)** | **L4 Private Network (WARP CIDR routing)** | Mode L7 tidak memerlukan WARP client di perangkat pengguna (akses via browser biasa), namun terbatas pada HTTP/WebSockets/gRPC. Mode L4 mendukung semua protokol TCP/UDP murni (SSH, RDP, psql), namun mewajibkan instalasi dan enrollment WARP agent. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Split-Tunnel CIDR Overlapping
- **Gejala**: Pengguna WARP tidak dapat mengakses subnet lokal rumah/kantor fisik (misal: printer LAN di `192.168.1.x`) atau IP Docker container lokal (`172.17.0.x`).
- **Penyebab**: Konfigurasi *Split Tunnel Include* mencakup blok IP lokal tersebut secara agresif (`192.168.0.0/16` dimasukkan ke dalam rute tunnel Cloudflare).
- **Solusi**: Pastikan CIDR internal korporat yang dimasukkan ke route tabel benar-benar terisolasi (gunakan sub-alokasi RFC 1918 yang unik seperti `10.240.0.0/14` atau CGNAT IP space `100.64.0.0/10`).

#### 2. Egress UDP Silent Drop (QUIC Handshake Stalls)
- **Gejala**: Log `cloudflared` menampilkan error: `Failed to create new quic connection: timeout: no recent network activity`. Tunnel mengalami flapping atau crash berulang kali.
- **Penyebab**: Firewall penyedia upstream (seperti AWS Security Group atau Corporate On-Prem Firewall) mengizinkan outbound TCP 443, tetapi memblokir UDP 7844 tanpa mengirim respons ICMP Port Unreachable (*silent drop*).
- **Solusi**: Tambahkan flag explicit protocol fallback atau izinkan outbound UDP 7844 secara eksplisit:
  ```bash
  # Quick diagnostic test via netcat/socat
  nc -z -v -u 198.41.192.167 7844
  
  # Jalankan tunnel secara paksa via HTTP/2 untuk isolasi masalah
  cloudflared tunnel --protocol http2 run <TUNNEL_NAME>
  ```

#### 3. Asymmetric Routing & Deadlock pada Private Cloudflare Routing
- **Gejala**: Paket TCP SYN dari WARP client mencapai server internal, tetapi respons SYN-ACK tidak pernah sampai kembali ke client. Koneksi *timeout*.
- **Penyebab**: Server internal memiliki *default gateway* yang mengarahkan traffic keluar melalui Internet Gateway / NAT lokal, bukan mengarahkannya kembali ke node/host tempat `cloudflared` berada, sehingga state tracking TCP di Cloudflare Edge menganggap sesi mati.
- **Solusi**: Terapkan Source NAT (SNAT) menggunakan iptables pada node yang menjalankan `cloudflared` jika berada di luar subnet yang sama, atau pastikan routing table VPC secara statis mengarahkan balik paket client virtual IP (`100.64.0.0/10`) ke IP lokal connector instance `cloudflared`.

```bash
# Debugging Steps Cheat Sheet
# 1. Cek status konektivitas 4 koneksi edge
cloudflared tunnel info <TUNNEL_ID>

# 2. Trace route end-to-end WARP client dari sisi terminal developer
warp-cli debug trace
warp-cli status
warp-cli tunnel stats

# 3. Validasi aturan ingress local tanpa restart
cloudflared tunnel ingress validate
```

---

### 11. Best Practices (Production Checklist)

#### Architecture & Deployment
- [ ] Deploy minimal **2 replica connector** per availability zone (AZ) atau data center region untuk mengeliminasi Single Point of Failure (SPOF).
- [ ] Terapkan konfigurasi **Pod Anti-Affinity** pada Kubernetes agar replica tidak berjalan pada physical host/node yang sama.
- [ ] Jalankan container dengan atribut `readOnlyRootFilesystem: true`, non-root user (`UID 65532`), dan matikan seluruh privilege escalation capabilities (`drop: ALL`).

#### Security & Policy
- [ ] Wajibkan integrasi **Enterprise IdP** dengan SCIM provisioning agar hak akses terhubung dengan lifecycle karyawan secara instan saat *offboarding*.
- [ ] Aktifkan minimal 2 jenis **Device Posture Checks**: EDR Telemetry (CrowdStrike/SentinelOne) dan status Enkripsi Disk (BitLocker/FileVault).
- [ ] Atur durasi sesi token (`session_duration`) aplikasi berisiko tinggi (seperti Production DB) maksimal **1 jam**, sementara aplikasi operasional umum dapat berdurasi **8–12 jam**.

#### Observability & Operations
- [ ] Aktifkan scrap metric internal `cloudflared` melalui Prometheus endpoint (`:2000/metrics`) dan pantau metrik kunci:
  - `cloudflared_tunnel_total_transmissions`
  - `cloudflared_tunnel_active_streams`
  - `cloudflared_tunnel_user_errors`
- [ ] Integrasikan audit logs Cloudflare Access ke SIEM korporat (Splunk, Datadog, atau Elastic) via Cloudflare Logpush Job.

---

### 12. Hands-on Practice

Simpan seluruh file praktikum ini di dalam repositori Anda pada path: `hands-on/m02/`.

#### Struktur Direktori
```
hands-on/m02/
├── terraform/
│   ├── main.tf
│   ├── variables.tf
│   └── terraform.tfvars.example
├── docker/
│   ├── docker-compose.yml
│   └── certs/
│       └── .gitkeep
└── scripts/
    ├── validate_tunnel.sh
    └── warp_doctor.sh
```

#### Langkah 1: Siapkan Konfigurasi Terraform
Tulis file `hands-on/m02/terraform/main.tf` sesuai basis kode pada Bagian 7.1. Buat file `hands-on/m02/terraform/terraform.tfvars`:
```hcl
cloudflare_account_id = "your_actual_account_id"
cloudflare_zone_id    = "your_actual_zone_id"
corporate_domain      = "infra-lab.internal"
```
Jalankan inisialisasi dan provisioning:
```bash
cd hands-on/m02/terraform
terraform init
terraform apply -auto-approve
```

#### Langkah 2: Deployment HA Connector dengan Docker Compose
Simpan konfigurasi berikut pada `hands-on/m02/docker/docker-compose.yml` untuk memvalidasi failover lokal:

```yaml
version: '3.8'

services:
  cloudflared-node-1:
    image: cloudflare/cloudflared:2024.4.1
    container_name: ztna-connector-1
    restart: unless-stopped
    command: tunnel --no-autoupdate --metrics 0.0.0.0:2000 run
    environment:
      - TUNNEL_TOKEN=${TUNNEL_TOKEN}
    ports:
      - "2001:2000"
    networks:
      ztna-net:
        ipv4_address: 172.28.0.10

  cloudflared-node-2:
    image: cloudflare/cloudflared:2024.4.1
    container_name: ztna-connector-2
    restart: unless-stopped
    command: tunnel --no-autoupdate --metrics 0.0.0.0:2000 run
    environment:
      - TUNNEL_TOKEN=${TUNNEL_TOKEN}
    ports:
      - "2002:2000"
    networks:
      ztna-net:
        ipv4_address: 172.28.0.11

  # Target Mock Internal Application
  internal-secure-app:
    image: hashicorp/http-echo:latest
    container_name: internal-app
    restart: unless-stopped
    command: ["-text=ACCESS_GRANTED_SECURE_PAYMENT_CORE", "-listen=:8080"]
    networks:
      ztna-net:
        ipv4_address: 172.28.0.50

networks:
  ztna-net:
    ipam:
      driver: default
      config:
        - subnet: 172.28.0.0/16
```

Jalankan container:
```bash
export TUNNEL_TOKEN=$(terraform -chdir=../terraform output -raw tunnel_token)
docker compose up -d
```

#### Langkah 3: Eksekusi Validasi Otomatis
Buat script verifikasi pada `hands-on/m02/scripts/validate_tunnel.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "==========================================="
echo "  ZTNA CONNECTOR HEALTH CHECK VERIFICATION "
echo "==========================================="

check_health() {
  local port=$1
  local node=$2
  echo -n "[*] Pengecekan Node ${node} di Port ${port}... "
  local response
  response=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${port}/ready" || true)
  if [ "${response}" -eq 200 ]; then
    echo "STATUS: HEALTHY (200 OK)"
  else
    echo "STATUS: UNHEALTHY (Code: ${response})"
    exit 1
  fi
}

check_health 2001 "Node-1"
check_health 2002 "Node-2"

echo "[+] Menguji Active Stream Metric..."
curl -s http://localhost:2001/metrics | grep "cloudflared_tunnel_ha_connections" || true

echo "==========================================="
echo "  SEMUA VALIDASI SISTEM BERHASIL DIVERIFIKASI"
echo "==========================================="
```
Jalankan script:
```bash
chmod +x hands-on/m02/scripts/validate_tunnel.sh
./hands-on/m02/scripts/validate_tunnel.sh
```

---

### 13. Exercises

#### Level 1 - Easy
1. Lakukan konfigurasi sebuah Cloudflare Tunnel baru menggunakan Terraform yang mengekspos web server Nginx internal lokal secara L7 ke subdomain publik terotentikasi (misal: `test-app.domain-anda.com`).
2. Pasang kebijakan Access dasar: Hanya email berakhiran `@perusahaan.com` yang diizinkan login menggunakan One-Time PIN (OTP).

#### Level 2 - Medium
1. Perluas implementasi Easy dengan mengonfigurasi **Private Network Routing (L4)** pada subnet lokal Docker (`172.28.0.0/16`).
2. Instal client **Cloudflare WARP** pada workstation Anda, sambungkan ke organisasi Zero Trust Anda, lalu uji akses koneksi TCP mentah via CLI `nc` atau `curl` langsung ke IP privat internal `172.28.0.50:8080` tanpa mengekspos subdomain publik di DNS zone.

#### Level 3 - Hard
1. Buat arsitektur failover multi-cloud. Pasang 2 instance `cloudflared` di AWS VPC (Region A) dan 2 instance di GCP VPC (Region B).
2. Konfigurasikan overlapping-free private routing untuk menjangkau database yang berada di GCP dari workstation remote melalui Anycast Cloudflare.
3. Terapkan Cloudflare Access Policy yang mewajibkan **mTLS Certificate Rule** (unggah self-signed Root CA Anda ke Cloudflare Access Service Auth) dan evaluasi apakah akses ditolak saat private key mTLS dicabut dari WARP client profile.

---

### 14. Architecture Challenge

Anda ditunjuk sebagai Principal Infrastructure Architect di bank digital yang sedang melakukan audit ketat terhadap kepatuhan **PCI-DSS Level 1** dan **ISO 27001**:
1. **Kendala Infrastruktur**: Terdapat cluster database legacy Oracle di on-premise datacenter Jakarta yang tidak boleh terhubung langsung ke internet, tidak boleh memiliki inbound open port, dan tidak boleh dipasang agent asing apapun secara lokal pada host database OS.
2. **Kebutuhan Akses**: Sekitar 40 Data Engineers dan DBA membutuhkan akses L4 langsung (port 1521) menggunakan client native (DBeaver / Oracle SQL Developer).
3. **Kondisi Perangkat**: Seluruh laptop tim data adalah macOS dan Windows yang dikelola oleh Microsoft Intune.
4. **Tantangan Desain**:
   - Rancang arsitektur High-Availability connector terisolasi di DMZ on-premise.
   - Buat skema access policy berjenjang: DBA wajib memenuhi kriteria (1) Status BitLocker/FileVault aktif, (2) SentinelOne status running, (3) Lokasi negara hanya dari Indonesia, (4) Maksimal durasi sesi TCP 2 jam dengan *re-authentication prompt*.
   - Rancang rencana pemulihan bencana (*Disaster Recovery*) jika koneksi ISP primer on-premise terputus: Bagaimana routing `cloudflared` beralih secara instan ke ISP sekunder tanpa mengubah IP tujuan pada aplikasi klien pengguna.
   - Tuliskan dokumen arsitektur komprehensif disertai diagram arsitektur jaringan ASCII lengkap beserta spesifikasi Terraform module skeleton-nya.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)
1. Protokol transport default yang digunakan oleh daemon `cloudflared` modern untuk membangun koneksi egress tunnel ke Cloudflare Edge adalah:
   - A. TCP Port 80
   - B. UDP Port 7844 (QUIC)
   - C. TCP Port 1194 (OpenVPN)
   - D. UDP Port 500 (IPsec)
2. Apa yang terjadi jika firewall lokal memblokir paket UDP keluar ke port 7844?
   - A. Tunnel mati total dan tidak dapat mengirim traffic.
   - B. Tunnel beralih secara otomatis ke HTTP/2 berbasis TCP.
   - C. Tunnel membuka port inbound 443 pada firewall.
   - D. Tunnel mengalihkan traffic melalui DNS port 53.
3. Apakah Cloudflare Tunnel membutuhkan alokasi Public IPv4 Address statis pada server lokal/on-premise Anda?
   - A. Ya, wajib untuk handshake edge.
   - B. Ya, tetapi hanya satu IP untuk primary replica.
   - C. Tidak, tunnel sepenuhnya bekerja via outbound connection.
   - D. Hanya jika menggunakan protokol QUIC.
4. Komponen mana pada workstation pengguna yang bertanggung jawab menangkap traffic L4 (IP/CIDR) privat dan meneruskannya ke Cloudflare Edge?
   - A. Nginx Reverse Proxy
   - B. Cloudflare WARP Client
   - C. Google Authenticator
   - D. Systemd Resolver daemon
5. File atau resource apa yang wajib dijaga kerahasiaannya dan digunakan connector untuk mengautentikasi tunnel ke akun Cloudflare?
   - A. Origin CA Certificate
   - B. Tunnel Token / Credentials JSON
   - C. Zone ID
   - D. Global API Key

#### Bagian 2: Intermediate (Pilihan Ganda & Analisis)
6. Manakah konfigurasi Ingress Rule berikut yang valid dan wajib dicantumkan pada baris paling akhir file konfigurasi tunnel?
   - A. `- service: http_status:200`
   - B. `- service: http_status:404`
   - C. `- hostname: "*"`
   - D. `- service: drop`
7. Mengapa mode routing *Split Tunnel Include* sering direkomendasikan pada lingkungan enterprise dibanding *Split Tunnel Exclude*?
   - A. Karena Include mode mematikan enkripsi WireGuard sehingga lebih cepat.
   - B. Untuk mencegah kebocoran IP address pengguna ke server internet.
   - C. Hanya trafik ke CIDR privat internal yang dialihkan ke tunnel, menjaga privasi aktivitas personal dan menghemat bandwidth edge gateway.
   - D. Include mode mengizinkan bypass autentikasi IdP.
8. Dalam deployment HA (High Availability) dengan 3 replica `cloudflared`, bagaimana Cloudflare mendistribusikan beban trafik masuk dari edge?
   - A. Active-Passive menggunakan mekanisme Virtual Router Redundancy Protocol (VRRP).
   - B. Round-Robin murni berbasis waktu tanpa health-check.
   - C. Load balancing secara otomatis di Cloudflare Edge ke koneksi replica yang sehat (Active-Active).
   - D. Klien WARP memilih IP replica secara acak saat resolving DNS.
9. Atribut apa yang divalidasi oleh Cloudflare Access saat Device Posture Check memeriksa integritas disk encryption pada endpoint macOS?
   - A. APFS Container GUID
   - B. Status proteksi enkripsi FileVault (Active/Inactive)
   - C. Keberadaan file `/etc/crypttab`
   - D. Password hash milik superuser
10. Apa kegunaan utama dari fitur **WARP Routing** (`warp_routing: enabled: true`) pada konfigurasi Tunnel?
    - A. Mempercepat koneksi internet publik pengguna.
    - B. Mengizinkan tunneling L4 untuk private network CIDR yang diumumkan, bukan hanya L7 hostname proxy.
    - C. Mengonversi TCP traffic menjadi ICMP ping.
    - D. Menghubungkan Cloudflare Access ke Microsoft Active Directory via LDAP.

#### Bagian 3: Skenario Kasus Produksi
11. **Kasus 1**: Sebuah tim DevOps mengeluh bahwa setelah mengonfigurasi Cloudflare Tunnel untuk sebuah web application internal, mereka mendapatkan error `HTTP 502 Bad Gateway` di browser saat mengakses domain publik Access, padahal pod `cloudflared` berstatus `Running (Ready)`. Langkah root-cause analysis sistematis apa yang harus Anda lakukan untuk mendeteksi sumber masalah?
12. **Kasus 2**: Tim compliance mendeteksi bahwa seorang karyawan yang akun Google Workspace-nya (IdP) sudah di-suspend masih bisa mengakses database internal melalui sesi WARP yang aktif selama 3 jam berikutnya. Parameter arsitektur apa yang terlewatkan dan bagaimana mengatasinya secara instan?
13. **Kasus 3**: Anda memiliki dua kantor cabang (Cabang A dan Cabang B) yang keduanya secara historis menggunakan subnet private yang identik (`192.168.1.0/24`) karena salah perencanaan IP masa lalu (Overlapping IP Space). Bagaimana Anda mendesain Cloudflare Private Network Route agar pengguna WARP dari pusat dapat mengakses server spesifik di kedua cabang tersebut tanpa memicu konflik routing?

---

### Kunci Jawaban Quiz

#### Bagian 1: Basic
1. **B** — Protokol transport default `cloudflared` adalah QUIC (UDP Port 7844).
2. **B** — Daemon `cloudflared` memiliki mekanisme internal fallback ke HTTP/2 (TCP) jika paket UDP 7844 mengalami timeout atau diblokir.
3. **C** — Cloudflare Tunnel sepenuhnya bekerja melalui koneksi outbound (egress-only) ke edge Anycast, sehingga tidak membutuhkan IP publik statis inbound.
4. **B** — Cloudflare WARP Client bertindak sebagai proxy/adapter jaringan lokal yang menangkap rute IP privat dan mengenkapsulasinya via WireGuard ke Cloudflare.
5. **B** — Tunnel Token (atau file credentials JSON pada model manual) memuat rahasia kriptografi untuk otorisasi daemon ke edge.

#### Bagian 2: Intermediate
6. **B** — Aturan terakhir ingress rule wajib berupa catch-all rule, standar industri menggunakan `service: http_status:404`.
7. **C** — *Include Mode* memastikan hanya subnet bisnis internal yang disedot masuk ke tunnel, mencegah konsumsi bandwidth berlebih dari streaming video publik atau traffic non-kerjaan pengguna.
8. **C** — Edge Anycast Cloudflare mendistribusikan stream data secara otomatis ke replica tunnel yang aktif secara Active-Active tanpa memerlukan protokol failover L2/L3 lokal.
9. **B** — Pada macOS, posture disk encryption memvalidasi status enkripsi bawaan OS yaitu FileVault.
10. **B** — Parameter `warp_routing: enabled: true` mengaktifkan kemampuan tunnel untuk bertindak sebagai gateway paket L4 dari jaringan privat CIDR.

#### Bagian 3: Skenario Kasus Produksi (Pedoman Penilaian Solusi)
11. **Solusi Kasus 1**:
    - **Step 1**: Cek log internal `cloudflared` (`kubectl logs <pod_name>`).
    - **Step 2**: Status 502 Bad Gateway mengindikasikan koneksi dari edge ke `cloudflared` sukses, namun `cloudflared` gagal menghubungi origin backend service di dalam cluster.
    - **Step 3**: Periksa hostname/service pada block `ingress` di tunnel config. Apakah mengarah ke service DNS yang valid (e.g., `http://app-svc.default.svc.cluster.local:8080`)?
    - **Step 4**: Jika origin menggunakan HTTPS dengan sertifikat internal/self-signed, periksa apakah opsi `no_tls_verify: true` atau `ca_pool` sudah diset. Ketiadaan trust certificate authority lokal menyebabkan `cloudflared` memutus koneksi TLS ke backend secara otomatis (indikasi error: `x509: certificate signed by unknown authority`).
12. **Solusi Kasus 2**:
    - **Penyebab**: Konfigurasi `session_duration` pada Access Application diset terlalu lama (misal: 24 jam) dan Cloudflare Access hanya mengevaluasi status pengguna saat validasi token awal tanpa session revocation check.
    - **Mitigasi Seketika**: Revoke sesi aktif pengguna secara manual atau via API melalui endpoint `DELETE /accounts/{account_id}/access/users/{user_id}/active_sessions`.
    - **Pencegahan Jangka Panjang**: Konfigurasikan integrasi **SCIM (System for Cross-domain Identity Management)** antara Google Workspace / Okta dengan Cloudflare Zero Trust. Ketika user di-suspend di IdP, event webhook SCIM langsung menonaktifkan identity seat di Cloudflare secara real-time. Terapkan pula pemendekan masa aktif token sesi (e.g., 1 jam) untuk akses infrastruktur kritis.
13. **Solusi Kasus 3**:
    - **Pendekatan Cloudflare Virtual Networks (VNet)**: Fitur Cloudflare Zero Trust mendukung abstraksi *Virtual Networks*.
    - **Langkah 1**: Buat dua Virtual Network ID terpisah di Cloudflare: `vnet-cabang-a` dan `vnet-cabang-b`.
    - **Langkah 2**: Bind Tunnel Cabang A ke `vnet-cabang-a` saat mengumumkan CIDR `192.168.1.0/24`.
    - **Langkah 3**: Bind Tunnel Cabang B ke `vnet-cabang-b` untuk subnet `192.168.1.0/24`.
    - **Langkah 4**: Di sisi klien WARP atau Gateway Policy, tetapkan routing policy kontekstual berbasis DNS/Split-Tunnel profile atau routing selector, sehingga traffic ke target tertentu dipetakan secara terisolasi ke VNet target tanpa tabrakan routing table. Alternatif lain: Terapkan 1:1 NAT (Network Address Translation) pada salah satu router cabang sebelum masuk ke tunnel.

---

### 16. Summary

Implementasi lanjutan **Cloudflare Zero Trust Network Access (ZTNA) dan Tunnels** merevolusi postur keamanan jaringan enterprise modern:
1. **Perimeter-less Architecture**: Menghilangkan kebutuhan inbound firewall rules, IP publik pada server origin, dan konsentrator VPN legacy melalui tunnel koneksi outbound berbasis **QUIC/HTTP-2**.
2. **Micro-Segmentation & Least Privilege**: Akses jaringan kini tidak lagi berbasis segmen subnet fisik, melainkan secara dinamis divalidasi pada Layer 4 dan Layer 7 oleh Identity Provider (IdP) dan Continuous Device Posture Verification.
3. **Resilience & Scale**: Menggunakan konfigurasi multi-replica Active-Active yang disebar melintasi Availability Zone dan region menggaransi tidak adanya single point of failure dengan latensi minimal berkat jaringan global Anycast Cloudflare.
4. **Automated Infrastructure**: Seluruh konfigurasi perimeter enterprise—mulai dari tunnel, routing CIDR, hingga policy access—dapat dan wajib dikelola sebagai kode (**Infrastructure as Code**) menggunakan Terraform untuk menjaga auditabilitas dan kepatuhan standar industri.