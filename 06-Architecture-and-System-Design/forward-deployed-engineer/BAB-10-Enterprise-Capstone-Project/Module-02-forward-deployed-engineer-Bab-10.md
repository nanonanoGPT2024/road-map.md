# BAB 10: Enterprise Capstone Project
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Mendesain & Mengimplementasikan Arsitektur Hybrid/Air-Gapped**: Mengonfigurasi pola integrasi *forward-deployed* yang menghubungkan *Core SaaS Control Plane* ke *Customer VPC / On-Premises Data Plane* dengan batas kepatuhan regulasi ketat (*Zero-Trust*, PCI-DSS, HIPAA, GDPR/UU PDP).
2. **Membangun Resilient Edge Gateway & Bi-directional Sync Adapter**: Menulis kode level produksi dalam bahasa Go untuk menangani sinkronisasi data asinkron, buffering berbasis disk (*write-ahead logging*), resolusi konflik (*conflict resolution*), dan proteksi *network partition*.
3. **Mengeksekusi Zero-Downtime Deployment & Observability Tunneling**: Mengonfigurasi Envoy proxy, dynamic mTLS dengan SPIFFE/SPIRE, eBPF tracing, dan reverse telemetry tunneling melalui firewall pelanggan tanpa membuka *inbound port*.
4. **Mengelola Trade-off Teknis Tingkat Enterprise**: Menganalisis secara kuantitatif dampak latensi, throughput, isolasi data, dan overhead operasional pada sistem yang didelegasikan langsung di infrastruktur klien.

---

### 2. Prerequisite
Sebelum mendalami modul ini, Anda wajib menguasai:
* Arsitektur sistem terdistribusi: Teorema CAP/PACELC, model konsistensi (*linearizability*, *eventual consistency*), dan protokol konsensus (Raft/Paxos).
* Jaringan tingkat lanjut: TCP/IP internals, TLS 1.3 handshake, ALPN, Envoy architecture, CIDR overlapping, NAT traversal, dan protokol tunneling (gRPC streaming over HTTP/2, WebSocket).
* Linux Systems Engineering & Kubernetes: Namespaces, cgroups, eBPF dasar, CNI (Cilium/Calico), CRD controller pattern, dan storage class CSI.
* Bahasa Pemrograman Go (Golang): Konkurensi tingkat lanjut (`sync`, `channels`, `errgroup`), garbage collection tuning, serta integrasi gRPC/Protobuf.

---

### 3. Concept & Internal Architecture (Mendalam)

Sebagai Forward Deployed Engineer (FDE), batas operasional Anda berada di persimpangan antara **Core Engineering Platform** dan **Enterprise Client Perimeter**. Tidak seperti Software Engineer (SWE) murni yang mengontrol 100% lingkungan cloud target (misal: AWS tunggal dengan akses root penuh), FDE harus mengoperasikan sistem di lingkungan di mana:
1. *Inbound connections* diblokir secara total oleh corporate firewall (*air-gapped* atau *restricted egress*).
2. Data sensitif (PII/Financial) tidak boleh meninggalkan perimeter pelanggan (*Data Gravity* dan *Data Residency*).
3. Infrastruktur target heterogen (OpenShift di Bare Metal, AWS GovCloud, atau Azure Stack) dengan kebijakan keamanan *Zero-Trust* yang agresif.

```
+-----------------------------------------------------------------------------------+
|                        CUSTOMER ENTERPRISE PERIMETER                              |
|                                                                                   |
|  +--------------------+         +-----------------------------------------------+ |
|  |  Customer Core DB  |         |        FDE Local Data Plane (Cluster)         | |
|  |  (Oracle / DB2)    |         |                                               | |
|  +---------+----------+         |  +----------------+     +------------------+  | |
|            |                    |  | Local Ingest   |     | Enterprise Engine|  | |
|            v                    |  | Adapter (Go)   |---->| Processing Pods  |  | |
|  +--------------------+         |  +-------+--------+     +--------+---------+  | |
|  | Sensitive Raw PII  |         |          |                       |            | |
|  +--------------------+         |          v                       v            | |
|                                 |  +----------------+     +------------------+  | |
|                                 |  | Local Persistent|    | Data Sanitizer & |  | |
|                                 |  | Buffer (WAL)   |     | Tokenizer (Rust) |  | |
|                                 |  +----------------+     +--------+---------+  | |
|                                 +----------------------------------|------------+ |
|                                                                    |              |
|                                           +------------------------+              |
|                                           v                                       |
|                                +----------------------+                           |
|                                | Edge Reverse Tunnel  |                           |
|                                | Envoy / gRPC Client  |                           |
|                                +----------+-----------+                           |
+-------------------------------------------|---------------------------------------+
                                            | Outbound Only (TLS 1.3 via 443)
                                            | Dynamic mTLS (SPIFFE/SPIRE)
                                            v
+-----------------------------------------------------------------------------------+
|                           CORE SAAS CONTROL PLANE                                 |
|                                                                                   |
|  +----------------------+      +----------------------+     +------------------+  |
|  | Reverse Tunnel Proxy |<---->| Fleet Manager & API  |<--->| SaaS Analytics   |  |
|  | (Envoy Aggregator)   |      | Gateway (Core Plane) |     | & Global DB      |  |
|  +----------------------+      +----------------------+     +------------------+  |
|                                                                                   |
+-----------------------------------------------------------------------------------+
```

#### Komponen Kunci Arsitektur FDE:
1. **Secure Reverse Tunneling**: Klien tidak pernah membuka port *inbound*. FDE mengompilasi dan mengonfigurasi *outbound-only* persistent bi-directional gRPC stream multiplexer. SaaS Control plane mengirimkan perintah RPC kembali ke edge cluster melalui stream ini.
2. **Local Data Plane & Zero-Egress Sanitization**: Pemrosesan komputasi berat, deteksi fraud, atau inferensi model AI dieksekusi secara lokal di kluster pelanggan. Hanya metadata terdesensitisasi (*pseudonymized telemetry* atau agregasi statistik) yang diizinkan keluar melalui egress filter.
3. **Local Write-Ahead Logging (WAL) & Disk Buffering**: Apabila jaringan customer WAN terputus (*network partition*), sistem lokal tidak boleh mengalami *backpressure failure* ataupun data drop. Ingest adapter menggunakan embedded log (*disk-backed FIFO ring*) untuk menjamin semantik *at-least-once*.
4. **Dynamic Identity Attestation via SPIFFE/SPIRE**: Menggantikan static API keys dengan cryptographic X.509 SVID yang di-issue berdasarkan validasi status node pelanggan (e.g., TPM chips, Kubernetes ServiceAccount tokens).

---

### 4. Why & What

| Dimensi | Pendekatan SaaS Standar | Pendekatan Forward Deployed Engineering (FDE) |
| :--- | :--- | :--- |
| **Lokasi Data** | Terpusat di Cloud Provider milik Vendor. | Data mentah tetap di VPC/Data Center Klien. |
| **Topologi Jaringan** | Mengasumsikan konektivitas internet dua arah yang stabil. | Mengasumsikan konektivitas intermiten, *air-gapped*, atau *outbound-only*. |
| **Identitas & Akses** | Vendor mengelola IAM secara independen. | Integrasi wajib dengan Active Directory, CyberArk, SAML/OIDC milik Klien. |
| **Upgrade Lifecycle**| Continuous Deployment terotomatisasi secara instan. | Canary validation dengan staging terisolasi dan *maintenance window* ketat. |
| **Toleransi Kegagalan**| Mengandalkan multi-AZ failover cloud publik. | Wajib mendukung *offline degraded-mode operation* secara otonom. |

#### Mengapa Pola Ini Mutlak Diperlukan?
Enterprise Tier-1 (Perbankan, Layanan Kesehatan, Pertahanan) menolak mengekspor data ke cloud eksternal karena risiko legalitas. Namun, mereka menuntut kapabilitas pemrosesan modern setara SaaS. Sebagai FDE, Anda tidak menulis kode satu kali untuk dijalankan di server Anda sendiri; Anda merekayasa sistem yang dapat didelegasikan, beradaptasi dengan keterbatasan lingkungan pihak ketiga, dan secara mandiri menjaga kedaulatan data klien.

---

### 5. How (Workflow Detail)

Alur kerja implementasi arsitektur produksi FDE mencakup 5 tahapan utama:

```
[Phase 1: Discovery & Attestation]
  │
  ├── 1.1 Evaluasi Egress, Proxy Korporat, & SSL Interception Klien.
  └── 1.2 Penerbitan Node Attestation via SPIRE Agent ke SPIRE Server.
  │
[Phase 2: Bootstrap & Hardening]
  │
  ├── 2.1 Provisioning Local Storage CSI (Fast NVMe local path).
  └── 2.2 Deployment Zero-Egress Envoy Gateway & Network Policies (Cilium/Calico).
  │
[Phase 3: Core Engine & Data Plane Tailoring]
  │
  ├── 3.1 Pemasangan Ingest Adapter dengan Direct Database Reader (CDC/Debezium).
  └── 3.2 Inisialisasi Ring Buffer WAL lokal untuk isolasi kegagalan transmisi.
  │
[Phase 4: Establishing Bi-directional Control Plane Tunnel]
  │
  ├── 4.1 Inisiasi HTTP/2 Outbound gRPC Stream ke SaaS Control Plane.
  └── 4.2 Handshake mTLS dengan pinning public key CA internal.
  │
[Phase 5: Continuous Delivery via Air-gapped / Local GitOps]
  │
  ├── 5.1 Mirroring artifact ke Local Harbor Registry klien.
  └── 5.2 ArgoCD mengeksekusi rekonsiliasi state lokal tanpa akses internet langsung.
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Sistem
Bayangkan **Core Platform** sebagai Kantor Pusat Kedutaan Besar di luar negeri, dan **Customer Perimeter** adalah Wilayah Berdaulat Militer dengan keamanan tinggi.
* Kantor Pusat tidak diizinkan masuk ke wilayah militer secara sembarangan (*No Inbound Traffic*).
* Kedutaan menempatkan agen diplomatik elit (**Forward Deployed Adapter**).
* Setiap komunikasi keluar harus diperiksa oleh staf intelijen militer (*Egress Proxy*).
* Agen diplomatik menggunakan kurir diplomatik berkoper terkunci anti-sadap (*mTLS over HTTP/2 Reverse Tunnel*) dan hanya membawa dokumen yang telah disensor hitam-hitam (*Sanitized Metadata*), sementara dokumen rahasia asli tetap disimpan di dalam brankas pangkalan militer (*Local Encrypted WAL Storage*).

#### Diagram Detail Alur Komunikasi Edge-to-Core
```
+-----------------------------------------------------------------------------+
| CUSTOMER ON-PREM INFRASTRUCTURE                                             |
|                                                                             |
| +-----------------+      Payload Raw       +------------------------------+ |
| | Core Core Bank  | ---------------------> | Ingest Service               | |
| | Database        |                        | (Validasi Schema & PII Mask) | |
| +-----------------+                        +--------------+---------------+ |
|                                                           |                 |
|                                                     Writes to Disk          |
|                                                           v                 |
|                                            +------------------------------+ |
|                                            | Local Embedded RocksDB / WAL | |
|                                            +--------------+---------------+ |
|                                                           |                 |
|                                                     Reads Batches           |
|                                                           v                 |
|                                            +------------------------------+ |
|                                            | Sync Daemon (Go Engine)      | |
|                                            +--------------+---------------+ |
|                                                           |                 |
|                                                    gRPC Frame (Egress)      |
|                                                           v                 |
|                                            +------------------------------+ |
|                                            | Envoy Sidecar Proxy          | |
|                                            | (Strict SPIFFE/SPIRE mTLS)   | |
|                                            +--------------+---------------+ |
+-----------------------------------------------------------|-----------------+
                                                            |
                                    Outbound Port 443 Only  |
                          (Corporate Forward Proxy Traversal)
                                                            v
+-----------------------------------------------------------------------------+
| VENDOR SAAS PRODUCTION (CONTROL PLANE)                                      |
|                                                                             |
|                       +------------------------------+                      |
|                       | SaaS Ingress Edge LoadBalanc |                      |
|                       +--------------+---------------+                      |
|                                      |                                      |
|                                      v                                      |
|                       +------------------------------+                      |
|                       | Reverse Tunnel Terminus      |                      |
|                       | (gRPC Multiplex Handler)     |                      |
|                       +--------------+---------------+                      |
|                                      |                                      |
|                         Routes Config Push & Telemetry                      |
|                                      v                                      |
|                       +------------------------------+                      |
|                       | Central Analytics & Fleet UI |                      |
|                       +------------------------------+                      |
+-----------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

Berikut adalah implementasi level produksi **Enterprise Ingestion and Sync Engine** yang dirancang untuk mengatasi network partition, masking data sensitif (PII), dan streaming asinkron ke core control plane dengan fallback protektif.

#### Struktur Direktori Modul Hands-On
```
hands-on/m02/
├── cmd/
│   └── agent/
│       └── main.go
├── internal/
│   ├── buffer/
│   │   └── wal.go
│   ├── sanitizer/
│   │   └── pii.go
│   └── transport/
│       └── client.go
├── configs/
│   └── agent-config.yaml
├── go.mod
└── go.sum
```

#### `hands-on/m02/internal/sanitizer/pii.go`
```go
package sanitizer

import (
	"crypto/sha256"
	"encoding/hex"
	"regexp"
)

var (
	// Regex mendeteksi format Kartu Kredit standar
	creditCardRegex = regexp.MustCompile(`\b(?:\d{4}[-\s]?){3}\d{4}\b`)
	// Regex mendeteksi NIK/ID Pelanggan (16 digit)
	nationalIDRegex = regexp.MustCompile(`\b\d{16}\b`)
)

type Sanitizer struct {
	salt []byte
}

func NewSanitizer(salt string) *Sanitizer {
	return &Sanitizer{salt: []byte(salt)}
}

// Pseudonymize melakukan hashing searah pada PII dengan HMAC/Salt
func (s *Sanitizer) Pseudonymize(input string) string {
	hasher := sha256.New()
	hasher.Write(s.salt)
	hasher.Write([]byte(input))
	return hex.EncodeToString(hasher.Sum(nil))[:16]
}

// SanitizePayload menggantikan data sensitif dengan pseudonim aman
func (s *Sanitizer) SanitizePayload(payload string) string {
	cleanCC := creditCardRegex.ReplaceAllStringFunc(payload, func(match string) string {
		return "CC-" + s.Pseudonymize(match)
	})
	cleanID := nationalIDRegex.ReplaceAllStringFunc(cleanCC, func(match string) string {
		return "ID-" + s.Pseudonymize(match)
	})
	return cleanID
}
```

#### `hands-on/m02/internal/buffer/wal.go`
```go
package buffer

import (
	"encoding/binary"
	"fmt"
	"io"
	"os"
	"sync"
)

// DiskWAL adalah ring-buffer sederhana berbasis append-only file
type DiskWAL struct {
	mu       sync.Mutex
	file     *os.File
	filepath string
}

func NewDiskWAL(filepath string) (*DiskWAL, error) {
	file, err := os.OpenFile(filepath, os.O_CREATE|os.O_RDWR|os.O_APPEND, 0600)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize WAL: %w", err)
	}
	return &DiskWAL{file: file, filepath: filepath}, nil
}

func (w *DiskWAL) Write(record []byte) error {
	w.mu.Lock()
	defer w.mu.Unlock()

	// Protocol: [4-byte length header] + [payload]
	length := uint32(len(record))
	header := make([]byte, 4)
	binary.BigEndian.PutUint32(header, length)

	if _, err := w.file.Write(header); err != nil {
		return err
	}
	if _, err := w.file.Write(record); err != nil {
		return err
	}
	// Flush ke disk untuk memastikan fsync durability
	return w.file.Sync()
}

func (w *DiskWAL) Drain() ([][]byte, error) {
	w.mu.Lock()
	defer w.mu.Unlock()

	var records [][]byte
	if _, err := w.file.Seek(0, io.SeekStart); err != nil {
		return nil, err
	}

	header := make([]byte, 4)
	for {
		_, err := io.ReadFull(w.file, header)
		if err == io.EOF || err == io.ErrUnexpectedEOF {
			break
		}
		if err != nil {
			return nil, err
		}

		length := binary.BigEndian.Uint32(header)
		buf := make([]byte, length)
		if _, err := io.ReadFull(w.file, buf); err != nil {
			return nil, err
		}
		records = append(records, buf)
	}

	// Reset dan truncate file setelah drain berhasil
	if err := w.file.Truncate(0); err != nil {
		return nil, err
	}
	if _, err := w.file.Seek(0, io.SeekStart); err != nil {
		return nil, err
	}

	return records, nil
}

func (w *DiskWAL) Close() error {
	w.mu.Lock()
	defer w.mu.Unlock()
	return w.file.Close()
}
```

#### `hands-on/m02/internal/transport/client.go`
```go
package transport

import (
	"context"
	"crypto/tls"
	"crypto/x509"
	"errors"
	"fmt"
	"net"
	"net/http"
	"os"
	"time"
)

type SecureStreamClient struct {
	httpClient *http.Client
	targetURL  string
}

func NewSecureStreamClient(targetURL, caCertPath, clientCertPath, clientKeyPath string) (*SecureStreamClient, error) {
	caCert, err := os.ReadFile(caCertPath)
	if err != nil {
		return nil, fmt.Errorf("failed reading CA cert: %w", err)
	}

	caCertPool := x509.NewCertPool()
	if !caCertPool.AppendCertsFromPEM(caCert) {
		return nil, errors.New("failed to parse root CA cert into pool")
	}

	cert, err := tls.LoadX509KeyPair(clientCertPath, clientKeyPath)
	if err != nil {
		return nil, fmt.Errorf("failed loading client key pair: %w", err)
	}

	tlsConfig := &tls.Config{
		Certificates: []tls.Certificate{cert},
		RootCAs:      caCertPool,
		MinVersion:   tls.VersionTLS13, // Standar keamanan perbankan
	}

	transport := &http.Transport{
		TLSClientConfig:       tlsConfig,
		DialContext:           (&net.Dialer{Timeout: 10 * time.Second, KeepAlive: 30 * time.Second}).DialContext,
		MaxIdleConns:          100,
		IdleConnTimeout:       90 * time.Second,
		TLSHandshakeTimeout:   10 * time.Second,
		ExpectContinueTimeout: 1 * time.Second,
	}

	return &SecureStreamClient{
		httpClient: &http.Client{Transport: transport, Timeout: 30 * time.Second},
		targetURL:  targetURL,
	}, nil
}

func (c *SecureStreamClient) SendTelemetry(ctx context.Context, data []byte) error {
	// Implementasi request via mTLS Outbound
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.targetURL+"/api/v1/telemetry", nil)
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/octet-stream")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("network dispatch failure: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusAccepted {
		return fmt.Errorf("upstream responded with non-2xx status: %d", resp.StatusCode)
	}
	return nil
}
```

#### `hands-on/m02/cmd/agent/main.go`
```go
package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"hands-on/m02/internal/buffer"
	"hands-on/m02/internal/sanitizer"
)

func main() {
	log.Println("[INFO] Starting Enterprise FDE Edge Sync Daemon...")

	walPath := "/tmp/edge_agent.wal"
	wal, err := buffer.NewDiskWAL(walPath)
	if err != nil {
		log.Fatalf("[FATAL] Init WAL failed: %v", err)
	}
	defer wal.Close()

	cleaner := sanitizer.NewSanitizer("bank-production-salt-secret")

	// Skenario: Menerima incoming event lokal dengan data rahasia
	rawTransactions := []string{
		`{"tx_id": "1001", "card": "4532-1234-5678-9012", "amount": 2500000}`,
		`{"tx_id": "1002", "card": "5412-9876-5432-1098", "amount": 125000}`,
	}

	log.Println("[INFO] Sanitizing and persisting locally to WAL...")
	for _, tx := range rawTransactions {
		sanitized := cleaner.SanitizePayload(tx)
		log.Printf("[LOCAL PROCESSING] Data sanitized: %s", sanitized)

		if err := wal.Write([]byte(sanitized)); err != nil {
			log.Fatalf("[ERROR] WAL write failed: %v", err)
		}
	}

	// Loop pengiriman asinkron (Mendukung recovery pasca network partition)
	ctx, cancel := context.WithCancel(context.Background())
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		ticker := time.NewTicker(5 * time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				records, err := wal.Drain()
				if err != nil {
					log.Printf("[ERROR] Drain failed: %v", err)
					continue
				}
				if len(records) == 0 {
					log.Println("[DEBUG] No pending transactions in WAL. Idle.")
					continue
				}

				log.Printf("[OUTBOUND] Flushing %d records to Core Platform via reverse tunnel...", len(records))
				for _, rec := range records {
					// Di produksi: kirim via transport.SecureStreamClient
					fmt.Printf(">> Flushed: %s\n", string(rec))
				}
			}
		}
	}()

	<-sigChan
	log.Println("[INFO] Graceful shutdown triggered...")
	cancel()
	time.Sleep(1 * time.Second)
	log.Println("[INFO] Agent shut down cleanly.")
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Standard National Bank of Asia (SNBA)
* **Konteks**: SNBA mengontrak platform pendeteksi penipuan anti-pencucian uang (*Anti-Money Laundering/AML*) berbasis machine learning.
* **Tantangan Lingkungan**:
  * Jaringan inti perbankan (Core Banking) diputus total dari internet (*air-gapped*). Tidak ada egress langsung ke internet; egress wajib melalui proxy korporat BlueCoat dengan inspeksi SSL paksa.
  * Otoritas Jasa Keuangan (OJK/Monetary Authority) melarang keras nomor rekening, NIK, dan nominal mutasi dikirim keluar dari infrastruktur internal bank.
  * Volume transaksi harian: 45.000 TPS pada jam puncak dengan SLA pemrosesan AML $< 35\text{ ms}$.

#### Solusi Forward Deployed Engineer:
1. **Model Deployment**: Alih-alih mengirim data transaksi ke cloud vendor, FDE men-deploy inference pod C++ teroptimasi TensorRT langsung ke OpenShift Bare-Metal cluster bank.
2. **Proxy Bypass & Certificate Whitelisting**: FDE menegosiasikan enkripsi TLS berstandar *Zero-Break-and-Inspect* menggunakan SPIFFE mTLS yang diizinkan secara eksplisit pada layer proxy gateway korporat, menghindari MITM internal bank yang merusak payload signature.
3. **Data Residency Shield**: Implementasi custom Envoy filter (Wasm) untuk mendeteksi *Accidental PII Leakage*. Jika data rekening lolos tanpa enkripsi hashing token, koneksi outbound otomatis diputus oleh sidecar (*Hard-Drop Policy*).
4. **Hasil**: SNBA lulus audit kepatuhan ISO 27001 dan OJK dalam waktu 4 bulan; throughput mencapai 52.000 TPS dengan latensi p99 sebesar $18\text{ ms}$, tanpa satu pun data mentah nasabah keluar dari batas fisik bank.

---

### 9. Trade-offs

| Pendekatan / Pilihan Desain | Keuntungan | Kerugian & Konsekuensi | Titik Keputusan Arsitektural |
| :--- | :--- | :--- | :--- |
| **Local In-Cluster WAL vs Remote gRPC Streaming** | Resisten terhadap WAN outage; tidak pernah drop data transaksi. | Membutuhkan persistent fast storage lokal (NVMe CSI); risiko *disk exhaustion*. | Gunakan disk WAL jika network reliability $< 99.9\%$ dan data loss tidak dapat ditoleransi sama sekali. |
| **Edge Compute vs Cloud Compute** | Nol risiko pelanggaran kedaulatan data; latensi inferensi sangat rendah. | Vendor sulit melakukan profiling resource; ketergantungan hardware klien. | Pilih Edge Compute bila data memiliki volume sangat masif (*Data Gravity*) atau ada batasan regulasi. |
| **Strict mTLS with SPIFFE vs API Token via HTTPS** | Identitas berbasis hardware; mitigasi total pencurian kredensial statis. | Kompleksitas operasional: harus mengelola SPIRE Server & agent lifecycle. | Mandatory untuk institusi finansial Tier-1 dan sertifikasi FedRAMP/PCI-DSS 4.0. |
| **CDC (Debezium/Kafka) vs Batch Ingestion Polling** | Real-time event streaming; minim beban pembacaan DB (`O(1)` per log). | Butuh hak akses administratif ke transaction log DB internal bank (CDC privilege). | Pilih CDC jika SLA $< 1\text{ detik}$; gunakan Batch Polling jika tim security klien menolak akses replication log. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum Produksi:
1. **MTU Mismatch pada Overlay Network**:
   * *Gejala*: Paket TCP kecil (handshake SYN/ACK) berhasil, tetapi request HTTP payload besar mengalami *hang/timeout*.
   * *Akar Masalah*: Jaringan klien menggunakan encapsulation tambahan (VXLAN/Geneve) dengan MTU 1450, namun Pod FDE diset ke standar MTU 1500, memicu paket *fragmentation drop*.
   * *Solusi*: Atur `mtu: 1400` secara eksplisit pada Custom Resource CNI atau set Path MTU Discovery (PMTUD) via sysctl:
     ```bash
     sysctl -w net.ipv4.ip_no_pmtu_disc=0
     ```

2. **Cert-Manager / SPIRE Deadlock pada Air-Gapped Environment**:
   * *Gejala*: Pod gagal bootstrap karena Certificate Authority (CA) lokal tidak dapat memvalidasi CRL (*Certificate Revocation List*) ke OCSP server publik.
   * *Solusi*: Nonaktifkan OCSP check eksternal pada runtime Envoy dan gunakan CRL lokal yang diinjeksi via Secret Kubernetes.

3. **Disk Exhaustion akibat Unbounded WAL Accumulation**:
   * *Gejala*: Cluster node *CrashLoopBackOff* dengan status `Evicted: The node was low on resource: ephemeral-storage`.
   * *Solusi*: Terapkan sistem *circuit breaker* dengan *drop-oldest* atau *backpressure-upstream* ketika alokasi disk WAL mencapai threshold 80%:
     ```bash
     df -h /var/log/edge-wal
     ```

4. **DNS Resolution Latency Spikes**:
   * *Gejala*: Latensi streaming melonjak hingga 5000ms tiap beberapa menit.
   * *Akar Masalah*: DNS resolver enterprise bank melakukan *throttling* pada CoreDNS loop queries.
   * *Solusi*: Terapkan NodeLocal DNSCache pada setiap Kubernetes node dan tambahkan TTL caching agresif di sisi klien.

---

### 11. Best Practices (Production Checklist)

#### Security & Compliance:
- [ ] Nonaktifkan akses privilege root: Set Pod security context ke `runAsNonRoot: true`, `readOnlyRootFilesystem: true`.
- [ ] Blokir akses metadata cloud instance: Blokir IP `169.254.169.254` via NetworkPolicy lokal agar pod edge tidak dapat membaca identitas infrastruktur klien.
- [ ] Zero-Cleartext: Seluruh data at rest wajib dienkripsi via dm-crypt/LUKS atau Kubernetes StorageClass dengan KMS lokal.

#### Reliability & Operasional:
- [ ] Konfigurasikan Liveness & Readiness probe berbasis deep health-check (validasi koneksi ke WAL disk dan outbound tunnel socket).
- [ ] Atur Pod Disruption Budgets (PDB) dengan `minAvailable: 1` untuk mencegah maintenance node sepihak oleh sysadmin klien merusak ketersediaan data plane.
- [ ] Alokasikan Dedicated CPU & Memory limits (Guaranteed QoS class) untuk daemon sync utama.

#### Observabilitas FDE:
- [ ] Ekspos metrik Prometheus via push/scrape terisolasi: `edge_buffer_backlog_bytes`, `tunnel_reconnect_attempts_total`, `pii_sanitization_dropped_count`.
- [ ] Terapkan log format structured JSON dengan `client_tenant_id` dan `deployment_region` konsisten tanpa memuat data mentah sensitif (*Zero-PII Logs*).

---

### 12. Hands-on Practice

Siapkan implementasi hands-on langsung pada repository project Anda. Jalankan seluruh tahapan berikut pada direktori kerja:

```bash
mkdir -p hands-on/m02/configs
mkdir -p hands-on/m02/cmd/agent
mkdir -p hands-on/m02/internal/buffer
mkdir -p hands-on/m02/internal/sanitizer
mkdir -p hands-on/m02/internal/transport
cd hands-on/m02
```

#### Langkah 1: Inisialisasi Go Module
```bash
go mod init hands-on/m02
```

#### Langkah 2: Buat Source Files
Salin kode dari **Seksi 7** ke dalam file masing-masing:
* `internal/sanitizer/pii.go`
* `internal/buffer/wal.go`
* `internal/transport/client.go`
* `cmd/agent/main.go`

#### Langkah 3: Eksekusi dan Verifikasi Persistence Disk WAL
Jalankan agent dan amati simulasi buffering disk saat payload masuk:
```bash
go run cmd/agent/main.go
```
*Output Verifikasi yang Diharapkan:*
```text
[INFO] Starting Enterprise FDE Edge Sync Daemon...
[INFO] Sanitizing and persisting locally to WAL...
[LOCAL PROCESSING] Data sanitized: {"tx_id": "1001", "card": "CC-9d2a02b1c85d7b51", "amount": 2500000}
[LOCAL PROCESSING] Data sanitized: {"tx_id": "1002", "card": "CC-e3b0c44298fc1c14", "amount": 125000}
[OUTBOUND] Flushing 2 records to Core Platform via reverse tunnel...
>> Flushed: {"tx_id": "1001", "card": "CC-9d2a02b1c85d7b51", "amount": 2500000}
>> Flushed: {"tx_id": "1002", "card": "CC-e3b0c44298fc1c14", "amount": 125000}
[DEBUG] No pending transactions in WAL. Idle.
```

#### Langkah 4: Uji Durability Saat Hard Interruption
1. Modifikasi interval ticker pengiriman menjadi `30 * time.Second`.
2. Jalankan `go run cmd/agent/main.go`.
3. Matikan paksa menggunakan sinyal kill: `kill -9 $(pgrep -f "cmd/agent/main")`.
4. Periksa integritas file biner WAL:
```bash
hexdump -C /tmp/edge_agent.wal
```
Perhatikan bahwa header 4-byte dan data transaksi yang telah di-sanitize tersimpan di disk dan tidak mengalami korupsi.

---

### 13. Exercise

#### Level 1 - Easy:
Modifikasi package `sanitizer` agar mampu menyamarkan alamat email enterprise (contoh: `john.doe@megabank.co.id` menjadi `j***e@megabank.co.id`) tanpa menghilangkan nama domain target.

#### Level 2 - Medium:
Tambahkan fitur *Rate Limiting Token Bucket* pada struct `DiskWAL` di package `buffer`. Jika laju ingest melebihi 1.000 records/detik, agent harus menolak record baru dengan mengembalikan error terdefinisi `ErrCapacityExceeded` untuk melindungi write wear-out pada media storage edge.

#### Level 3 - Hard:
Buat reverse gRPC tunnel lengkap menggunakan HTTP/2 stream multiplexing. Client di Edge harus melakukan koneksi `Dial` ke server mock SaaS. Server SaaS kemudian harus dapat mengirimkan payload konfigurasi (*Config Push*) secara remote melalui connection context yang telah diinisiasi oleh Edge tersebut, membuktikan bypassing firewall inbound 100% tanpa membuka port di sisi client.

---

### 14. Challenge

**Studi Kasus Konseptual: The Defense Contractor Air-Gapped Disaster**

Anda ditugaskan sebagai Lead FDE di fasilitas militer dengan klasifikasi kerahasiaan tinggi (*Defense Contractor*). 
* **Batasan**:
  * Jaringan terputus secara fisik (*physical air-gap*), koneksi internet outbound eksternal sama sekali dilarang ($0\text{ bytes egress}$).
  * Model Machine Learning harus diperbarui setiap 7 hari sekali.
  * Terdapat kluster Kubernetes multi-master di dalam bunker yang tidak dapat menarik image dari registry publik (Docker Hub/Quay/ECR).
  * Data operasional penugasan drone militer harus diproses dengan latensi $< 5\text{ ms}$ secara terdistribusi.

**Tantangan Arsitektur**:
Rancang dokumen arsitektur dan runbook teknis komprehensif yang mencakup:
1. Strategi peremajaan model AI dan patch binary software menggunakan *Cryptographically Signed Data Diodes* atau media fisik terisolasi (USB/KMS verification).
2. Desain infrastruktur registri lokal (Harbor air-gapped sync) lengkap dengan image signature validation menggunakan Cosign/Sigstore secara offline.
3. Strategi fail-safe data plane dan fallback konsensus jika salah satu node controller di bunker hancur secara fisik.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)
1. Apa alasan fundamental sebuah sistem Forward Deployed menggunakan *Reverse Tunneling* alih-alih mengekspos Ingress Endpoint standar?
   * A. Karena Ingress endpoint memerlukan CPU yang lebih besar.
   * B. Untuk mematuhi aturan firewall enterprise yang memblokir semua koneksi inbound.
   * C. Karena protokol gRPC tidak mendukung mode server-side di cloud.
   * D. Karena latency Ingress endpoint selalu lebih lambat dari egress.
   * *Jawaban*: **B**. Enterprise perimeter secara default melarang pembukaan port inbound publik demi keamanan.

2. Protokol manakah yang menjamin enkripsi level transport paling aman untuk edge-to-core streaming pada lingkungan perbankan modern?
   * A. Telnet over VPN.
   * B. Plain HTTP/2.
   * C. TLS 1.3 dengan Mutual Authentication (mTLS).
   * D. HTTP/1.1 dengan API Key di Header.
   * *Jawaban*: **C**. TLS 1.3 mTLS menyediakan cryptographic mutual attestation dan membatasi chiper suite yang rentan.

3. Komponen apakah yang bertugas memberikan identitas dinamis berbasis workload (tanpa shared secret statis) dalam arsitektur Zero-Trust modern?
   * A. SPIFFE/SPIRE.
   * B. Nginx Ingress.
   * C. OpenSSL CLI.
   * D. Memcached.
   * *Jawaban*: **A**. SPIFFE mendefinisikan standar identitas workload dan SPIRE adalah implementasi open-source-nya.

4. Apa dampak utama dari fenomena *Data Gravity* pada enterprise data?
   * A. Database akan otomatis membuat replika ke seluruh region cloud.
   * B. Data yang berukuran sangat besar dan diikat regulasi lebih efisien diproses secara lokal daripada dipindahkan ke cloud vendor.
   * C. Storage hard drive akan mengalami degradasi mekanikal lebih cepat.
   * D. Latensi jaringan menjadi $0\text{ ms}$.
   * *Jawaban*: **B**. Biaya egress, batasan bandwidth, dan regulasi kepatuhan membuat komputasi harus mendekati data, bukan sebaliknya.

5. Manakah fungsi utama dari Write-Ahead Log (WAL) pada disk lokal adapter edge?
   * A. Mengompresi file agar muat di memori RAM.
   * B. Menghilangkan kebutuhan enkripsi data.
   * C. Menjamin durability data lokal saat terjadi network partition antara Edge dan Core.
   * D. Menggantikan peran DNS server klien.
   * *Jawaban*: **C**. WAL menjamin data transaksi yang diterima tidak hilang saat transmisi WAN putus total.

#### Bagian 2: Intermediate (Analisis Pilihan Ganda & Konseptual)
6. Jika corporate proxy bank melakukan deep SSL inspection (MITM), konfigurasi mTLS antara Edge Agent dan SaaS Core akan:
   * A. Berjalan lebih cepat karena didekripsi oleh proxy.
   * B. Mengalami kegagalan handshake TLS karena proxy merusak signature cert client dan memutus validasi public key asli.
   * C. Mengubah protokol secara otomatis menjadi plaintext.
   * D. Mengabaikan validasi x509 cert secara native.
   * *Jawaban*: **B**. SSL interception memutus chain-of-trust mTLS karena perantara tidak memiliki private key client yang sah.

7. Parameter kernel Linux `net.ipv4.ip_no_pmtu_disc=0` diatur untuk:
   * A. Mengaktifkan Path MTU Discovery guna menghindari fragmentasi paket pada jaringan encapsulation bertingkat.
   * B. Mematikan firewall bawaan OS.
   * C. Memperbesar buffer memory TCP secara eksponensial.
   * D. Mengizinkan login root tanpa SSH keys.
   * *Jawaban*: **A**. PMTUD diperlukan untuk mendeteksi MTU efektif minimum sepanjang rute paket overlay network.

8. Dalam konteks mitigasi kegagalan, semantik pengiriman apa yang paling tepat dicapai oleh perpaduan Disk WAL lokal dan Upstream Idempotent Consumer?
   * A. At-most-once.
   * B. At-least-once dengan deduplikasi idempotent (efektif Exactly-Once processing).
   * C. Best-effort delivery.
   * D. Zero-guarantee delivery.
   * *Jawaban*: **B**. Data di-retry sampai ack diterima, dan konsumen mengabaikan duplikat via deduplication key.

9. Apa risiko terbesar membiarkan `readOnlyRootFilesystem: false` pada pod data plane yang berjalan di infrastruktur klien?
   * A. Kubernetes node crash seketika saat booting.
   * B. Potensi modifikasi binary software atau injeksi malware persisten pada filesystem container saat terjadi compromise.
   * C. Pod tidak dapat melakukan logging ke `stdout`.
   * D. Mengakibatkan CPU throttling sebesar 50%.
   * *Jawaban*: **B**. Container immutability adalah standar PCI-DSS untuk mencegah eksploitasi filesystem lokal secara dinamis.

10. Ketika mengimplementasikan masking PII dengan metode Hashing, mengapa penggunaan static salt yang sama secara global berbahaya?
    * A. Karena hashing akan memerlukan CPU 100x lipat lebih tinggi.
    * B. Membuka kerentanan terhadap *rainbow table attacks* dan *cross-client correlation*.
    * C. File JSON menjadi rusak dan tidak terbaca parser standard.
    * D. String output akan selalu melebihi 4096 karakter.
    * *Jawaban*: **B**. Static salt memungkinkan penyerang membuat tabel pra-komputasi untuk merekonstruksi data sensitif asli di lintas sistem.

#### Bagian 3: Skenario Kasus Produksi
11. **Skenario Kasus 1**:
    Sebuah Edge sync pod yang berjalan di kluster Kubernetes klien mendadak dibunuh secara berulang (`OOMKilled`) setiap 2 jam. Metrik menunjukkan memory heap Go terus bertambah linier tanpa pernah turun meskipun traffic transaksi flat di 500 TPS.
    * *Pertanyaan*: Analisis kemungkinan akar penyebab di level runtime/goroutine dan langkah debug yang harus Anda ambil sebagai FDE!
    * *Solusi/Analisis*: Kemungkinan besar terjadi kebocoran goroutine (*Goroutine Leak*) pada sync streaming loop (misal: HTTP/2 client transport membuat goroutine reader/writer baru setiap kali koneksi mengalami reconnect/timeout tanpa menutup channel atau response body pada koneksi lama). Tindakan: Ambil pprof heap dan goroutine profile melalui `go tool pprof http://localhost:<debug-port>/debug/pprof/goroutine`, periksa trace goroutine yang menggantung pada state `chan receive` atau `net.Conn.Read`, pastikan semua transport response ditutup via `resp.Body.Close()`, dan pastikan context cancellation dipropagasi dengan benar.

12. **Skenario Kasus 2**:
    Tim Security Klien mendeteksi bahwa sistem FDE Anda mengirimkan payload ke Core Platform melalui port 443. Mereka menuduh sistem Anda membocorkan data nasabah ke internet publik dan mematikan rute egress secara mendadak.
    * *Pertanyaan*: Langkah mitigasi dan pembuktian teknis apa yang harus Anda sajikan untuk membuktikan integritas kepatuhan data residency platform Anda kepada tim CISO klien?
    * *Solusi/Analisis*: 
      1. Tunjukkan implementasi filter desensitisasi lokal (Wasm filter / regex pipeline) sebelum egress buffer.
      2. Jalankan audit dump transparan menggunakan network capture lokal (`tcpdump -A -i eth0 port 443`) pada staging environment yang terisolasi dengan data dummy, atau tunjukkan log *Zero-PII Tokenizer*.
      3. Buka konfigurasi mTLS pinning dan buktikan via payload schema validation bahwa data yang dikirim hanyalah metadata agregasi numerik dan token hash non-reversibel.
      4. Sediakan source code komponen sanitizer dan sertifikat evaluasi kepatuhan pihak ketiga (*attestation audit report*).

13. **Skenario Kasus 3**:
    Koneksi leased line WAN milik bank terputus selama 14 jam. Agen Edge Anda menyimpan seluruh transaksi ke dalam Disk WAL. Ketika jaringan kembali pulih (*recovery*), agen mencoba melakukan sinkronisasi jutaan data sekaligus, yang mengakibatkan Core Platform SaaS Anda terkena efek *Thundering Herd* dan mengalami kelumpuhan total (HTTP 503).
    * *Pertanyaan*: Rekayasa arsitektural apa yang wajib ditambahkan pada Edge Sync Daemon untuk mencegah insiden ini di masa depan?
    * *Solusi/Analisis*: Terapkan arsitektur *Gradual Backoff with Jitter* dan *Client-Side Congestion Control*. Agen Edge tidak boleh langsung memuntahkan seluruh log isi disk WAL. Desain sync pipeline harus menggunakan:
      1. Dynamic Batch Sizing (memulai dari batch kecil misal 50 record, bertahap naik jika respons latency SaaS $< 100\text{ ms}$).
      2. Leaky Bucket / Token Bucket Rate-Limiting yang dibatasi maksimal sesuai kuota downstream yang disepakati.
      3. Upstream Backpressure Feedback: Jika SaaS mengembalikan respons HTTP 429 atau header `Retry-After`, Edge Daemon seketika memelankan drain loop secara eksponensial.

---

### 16. Summary
Peran Forward Deployed Engineer (FDE) pada Capstone Enterprise menuntut pergeseran paradigma dari *standard application engineering* menuju *defensive distributed systems design*. Menjalankan software di dalam benteng enterprise pihak ketiga mewajibkan sistem dirancang dengan asumsi bahwa jaringan tidak pernah andal, akses inbound selalu ditolak, dan integritas data berada di bawah pengawasan regulasi ketat.

Dengan menguasai pola **Reverse Telemetry Tunneling**, **Data Plane Decoupling**, **Zero-PII Hashing Sanitization**, dan **Local Resilient Buffering (WAL)**, Anda dapat membangun platform kelas enterprise yang menjamin kedaulatan data klien tanpa mengorbankan kapabilitas automasi, observabilitas, serta performa komputasi terdistribusi modern.