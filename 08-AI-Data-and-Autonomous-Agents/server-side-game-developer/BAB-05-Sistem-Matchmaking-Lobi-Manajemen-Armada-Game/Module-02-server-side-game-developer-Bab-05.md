# Kurikulum Rekayasa Backend Game Enterprise
## Kategori: 08-AI-Data-and-Autonomous-Agents
## Topik: Server-Side Game Developer
## Bab 05: Sistem Matchmaking, Lobi, & Manajemen Armada Game (Fleet Management)
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Merancang dan mengimplementasikan mesin *matchmaking* berskala global menggunakan pola *Open Match* (Ticket, Director, Match Function, Evaluator) dengan latensi evaluasi sub-100 milidetik.
- Membangun sistem sinkronisasi state lobi real-time berbasis terdistribusi dengan toleransi kegagalan jaringan (split-brain mitigation, heartbeating, reconnect window).
- Mengorkestrasi Dedicated Game Server (DGS) di atas Kubernetes menggunakan Agones SDK dan Custom Controller, mencakup lifecycle management: *Scheduled*, *Ready*, *Allocated*, hingga *Reserved*.
- Menerapkan strategi *Zero-Downtime Fleet Draining* dan dynamic pod autoscaling terikat pada throughput sesi aktif game berlatensi rendah (UDP/WebSockets).
- Mengintegrasikan mekanisme mitigasi noisy neighbor, latensi routing multi-region, dan alokasi instance bare-metal/cloud hybrid.

---

### 2. Prerequisite

Sebelum memulai modul ini, peserta wajib memahami:
- **Jaringan Komputer Lanjutan**: UDP vs TCP, MTU fragmentation, NAT punch-through, model sinkronisasi state server-authoritative (Client-Side Prediction, Server Reconciliation).
- **Pemrograman Konkuren & Sistem Terdistribusi**: Goroutines, Channels, Mutexes, Atomic Operations, gRPC/Protobuf, Redis Data Structures (Sorted Sets, Pub/Sub, Hashes, Streams).
- **Dasar Orkestrasi Kontainer**: Arsitektur internal Kubernetes (Control Plane, Kubelet, CNI, CRD, Controllers/Operators).
- **Penguasaan Bahasa**: Go (v1.21+) sebagai bahasa utama backend orkestrator game engine.

---

### 3. Concept & Internal Architecture (Mendalam)

Arsitektur produksi sistem backend game multi-wilayah membutuhkan pemisahan tegas antara komponen *Stateless Orchestration* (Matchmaking, API Gateway) dan *Stateful Compute* (Dedicated Game Server/DGS).

```
                      GLOBAL TRAFFIC MANAGER (GeoDNS / Anycast)
                                       │
                ┌──────────────────────┴──────────────────────┐
                ▼                                             ▼
        REGION: ap-southeast-1                        REGION: us-east-1
 ┌─────────────────────────────┐               ┌─────────────────────────────┐
 │    Edge API / Gateway       │               │    Edge API / Gateway       │
 └──────────────┬──────────────┘               └──────────────┬──────────────┘
                │                                             │
                ▼                                             ▼
 ┌─────────────────────────────┐               ┌─────────────────────────────┐
 │     Lobby Microservices     │               │     Lobby Microservices     │
 └──────────────┬──────────────┘               └──────────────┬──────────────┘
                │                                             │
                ▼                                             ▼
 ┌───────────────────────────────────────────────────────────────────────────┐
 │               MATCHMAKING DISTRIBUTED CORE (Open-Match Engine)           │
 │  ┌─────────────────┐    ┌────────────────────┐    ┌──────────────────┐    │
 │  │ Match Function  │◄───┤   Match Director   ├───►│ Evaluator / FIFO │    │
 │  │ (MMR/Ping Sync) │    │  (Polls Proposals) │    │ Overlap Resolver │    │
 │  └────────┬────────┘    └─────────┬──────────┘    └──────────────────┘    │
 │           │                       │                                       │
 │           ▼                       ▼                                       │
 │     [Redis Cluster: Ticket State & Latency-indexed Sorted Sets]           │
 └───────────────────────────────────┬───────────────────────────────────────┘
                                     │ Allocation Request (gRPC)
                                     ▼
 ┌───────────────────────────────────────────────────────────────────────────┐
 │             AGONES GAME FLEET CONTROLLER (Custom Kubernetes Engine)        │
 │                                                                           │
 │  Node Pool (Bare Metal / C5.2xlarge Compute Optimized)                    │
 │  ┌─────────────────────────────────────────────────────────────────────┐  │
 │  │ Pod: DGS Instance 01 (Allocated)       Pod: DGS Instance 02 (Ready) │  │
 │  │ ┌────────────────┐ ┌──────────────┐    ┌──────────────┐ ┌─────────┐ │  │
 │  │ │ Unreal Engine/ │ │ Agones SDK   │    │ Unreal Engine│ │ Agones  │ │  │
 │  │ │ Unity Server   │ │ Sidecar      │    │ Server       │ │ SDK     │ │  │
 │  │ │ (Port: 7777/UDP) │ (Port: 9357) │    │ (Port: 7778) │ │ Sidecar │ │  │
 │  │ └───────▲────────┘ └──────▲───────┘    └──────────────┘ └─────────┘ │  │
 │  └─────────┼─────────────────┼─────────────────────────────────────────┘  │
 └────────────┼─────────────────┼────────────────────────────────────────────┘
              │ Direct UDP Flow │ Agones Control Flow (mTLS)
              ▼                 ▼
          Game Client (Players in Match)
```

#### Komponen Kunci Arsitektur:
1. **Match Ticket Ingestion**: Tiket pemain membawa metadata penting: identitas pemain, atribut MMR (Matchmaking Rating), data latensi regional (diperoleh dari probing ICMP/UDP ping ke edge reflector), dan timestamp antrean.
2. **Dynamic Range Expansion (Sliding Window)**: Mengurangi waktu antrean dengan melebarkan toleransi deviasi MMR secara asinkron berdasarkan waktu tunggu pemain di antrean.
3. **Agones Fleet Orchestration**: DGS tidak boleh dijalankan di balik Service Load Balancer standar (seperti Kubernetes `ClusterIP` atau AWS `ALB`) karena overhead enkapsulasi NAT dan hilangnya koneksi stateful UDP peer-to-peer. Setiap Pod DGS dipetakan langsung ke port Host fisik (`HostPort` networking atau Cilium BPF bypass) dan dikontrol melalui Agones GameServer CRD.

---

### 4. Why & What

| Dimensi | Pendekatan Monolitik / Tradisional | Pendekatan Produksi Modern (Cloud-Native Game Infra) |
| :--- | :--- | :--- |
| **Lifecycle DGS** | VM statis dengan script SSH/Bash pengangkat proses game | Lifecycle pod Kubernetes terkelola otomatis via CRD Agones (*Ready*, *Allocated*, *Shutdown*) |
| **Matchmaking** | Pengecekan *looping* terpusat pada basis data relasional tunggal | Mesin modular terdistribusi berbasis data kustom (Memory Graph / Redis Skiplists) |
| **Konektivitas Jaringan** | Melalui Ingress/Reverse Proxy layer 7 (meningkatkan latency & packet drop) | Host direct network mapping (HostPort / AWS ENI multi-IP) dengan UDP murni |
| **Skalabilitas Armada** | Berbasis utilitas CPU/Memori instans OS | Berbasis metric spesifik domain game (*Allocation Rate*, *Reserved Match Percentage*) |
| **Mitigasi Player Drop** | Sesi hilang jika server crash, tidak ada reconnect window terstruktur | Distributed lobby state session caching dengan token pemulihan ephemeral |

---

### 5. How (Workflow Detail)

Alur produksi dari inisiasi tombol "Find Match" hingga transmisi paket pertama ke Dedicated Game Server:

```
[Client]              [Lobby Service]         [Matchmaker]           [Director]             [Agones Fleet]
   │                         │                      │                     │                       │
   │ 1. Req Match (Pings)    │                      │                     │                       │
   ├────────────────────────►│                      │                     │                       │
   │                         │ 2. Create Ticket     │                     │                       │
   │                         ├─────────────────────►│                     │                       │
   │                         │                      │ 3. Group Players    │                       │
   │                         │                      │    (Match Function) │                       │
   │                         │                      │◄───────────────────►│                       │
   │                         │                      │                     │ 4. Poll Proposals     │
   │                         │                      │                     │◄──────────────────────┤
   │                         │                      │                     │                       │
   │                         │                      │                     │ 5. Allocate Server    │
   │                         │                      │                     ├──────────────────────►│
   │                         │                      │                     │    (gRPC Alloc Req)   │
   │                         │                      │                     │                       │
   │                         │                      │                     │ 6. Return IP:Port     │
   │                         │                      │                     │◄──────────────────────┤
   │                         │                      │ 7. Assign Ticket    │                       │
   │                         │                      │◄────────────────────┤                       │
   │                         │ 8. Notify MatchReady │                     │                       │
   │                         │◄─────────────────────┤                     │                       │
   │ 9. MatchFound(IP:Port)  │                      │                     │                       │
   │◄────────────────────────┤                      │                     │                       │
   │                                                                                              │
   │ 10. Handshake Direct UDP Game Protocol (Tick Rate 60Hz)                                      │
   ├─────────────────────────────────────────────────────────────────────────────────────────────►│
```

1. **Ping Probing**: Game client mengirim paket ping UDP ke edge endpoints di berbagai region (misal: `ap-southeast-1`, `us-west-2`) dan menyusun latensi map (`{"ap-southeast-1": 24, "us-west-2": 180}`).
2. **Ticket Creation**: Lobby Service memvalidasi token sesi dan memasukkan tiket ke Redis menggunakan representasi payload Protobuf terenkripsi.
3. **Match Formation Loop**: Match Function dieksekusi setiap interval tertentu (misal: 1000ms), mengambil batch tiket, mengelompokkannya berdasarkan kesamaan MMR dan ping rata-rata regional terendah.
4. **Assignment & Agones Allocation**: Match Director mendeteksi proposal match yang valid dan mengirimkan RPC `AllocateGameServer` ke Agones Kubernetes API via GameServerAllocation Client.
5. **Direct Connect**: Game client menerima IP eksternal DGS dan Port host unik, lalu memutuskan stream lobi dan memulai handshake UDP pada port yang dialokasikan.

---

### 6. Analogy & Diagram ASCII

#### Analogi Sistem
Bayangkan sebuah **Bandara Internasional**:
- **Pemain** adalah penumpang dengan tiket destinasi dan kelas penerbangan (MMR).
- **Matchmaker** adalah petugas *gate ticketing* yang mengelompokkan penumpang yang memiliki jadwal penerbangan sama secara presisi.
- **Director** adalah pengawas menara pengawas (*Air Traffic Controller*).
- **Agones Fleet** adalah armada pesawat di apron. Pesawat yang parkir dengan kru siap adalah status `Ready`. Ketika kelompok penumpang siap, Controller langsung menetapkan pesawat khusus tersebut menjadi `Allocated`. Begitu terbang dan selesai menurunkan penumpang, pesawat kembali dibersihkan (*Shutdown/Recycle*), bukan langsung dipakai ulang secara sembarangan, untuk mencegah akumulasi sampah memori (*memory leak* engine game).

#### Diagram Transisi Lifecycle Agones DGS:
```
                ┌──────────────┐
                │  Scheduled   │
                └──────┬───────┘
                       │ (Container Initialization)
                       ▼
                ┌──────────────┐
                │   Starting   │
                └──────┬───────┘
                       │ (Engine Initialization Complete: SDK.Ready())
                       ▼
         ┌────────► ┌──────────┐ ◄────────────────┐
         │          │  Ready   │                  │
         │          └────┬─────┘                  │
         │ (Vacated)     │                        │
         │               │ (Agones SDK.Allocate() │ (Fallback Timeout)
         │               │  or Director gRPC)     │
         │               ▼                        │
         │          ┌──────────┐                  │
         └──────────┤ Reserved │ ─────────────────┘
                    └────┬─────┘
                         │ (Match Starts)
                         ▼
                    ┌──────────┐
                    │Allocated │
                    └────┬─────┘
                         │ (Match Finished / Engine SDK.Shutdown())
                         ▼
                    ┌──────────┐
                    │ Shutdown │ ──► (Kubernetes Pod Terminated)
                    └──────────┘
```

---

### 7. Simple Example & Practical Example

#### Implementasi Produksi: Agones Allocation Client & Director Worker (Go)

Kode di bawah mendemonstrasikan implementasi level produksi dari Director Matchmaker yang berkomunikasi dengan Agones Allocation gRPC API untuk mengamankan Dedicated Game Server, lengkap dengan penanganan concurrency, retry with exponential backoff, dan context-aware lifecycle management.

```go
// Package main: Director & Fleet Allocation Handler
package main

import (
	"context"
	"crypto/tls"
	"crypto/x509"
	"errors"
	"fmt"
	"log"
	"net"
	"os"
	"sync"
	"time"

	allocationv1 "agones.dev/agones/pkg/allocation/go"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
)

// Config menyimpan konfigurasi komunikasi dengan Agones Allocation Service
type Config struct {
	AllocationEndpoint string
	ClientCertPath     string
	ClientKeyPath      string
	CACertPath         string
	FleetName          string
	Namespace          string
}

// FleetAllocator mendefinisikan interface alokasi server
type FleetAllocator interface {
	Allocate(ctx context.Context, matchID string, region string) (*allocationv1.AllocationResponse, error)
	Close() error
}

type agonesFleetAllocator struct {
	client allocationv1.AllocationServiceClient
	conn   *grpc.ClientConn
	cfg    Config
	mu     sync.RWMutex
}

// NewAgonesFleetAllocator menginisialisasi gRPC mTLS Client ke Agones Allocation Subsystem
func NewAgonesFleetAllocator(cfg Config) (FleetAllocator, error) {
	cert, err := tls.LoadX509KeyPair(cfg.ClientCertPath, cfg.ClientKeyPath)
	if err != nil {
		return nil, fmt.Errorf("failed to load client cert/key pair: %w", err)
	}

	caCert, err := os.ReadFile(cfg.CACertPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read CA certificate: %w", err)
	}

	caCertPool := x509.NewCertPool()
	if !caCertPool.AppendCertsFromPEM(caCert) {
		return nil, errors.New("failed to append root CA certificate to pool")
	}

	tlsConfig := &tls.Config{
		Certificates: []tls.Certificate{cert},
		RootCAs:      caCertPool,
		ServerName:   "agones-allocation.agones-system.svc.cluster.local",
	}

	dialOpts := []grpc.DialOption{
		grpc.WithTransportCredentials(credentials.NewTLS(tlsConfig)),
		grpc.WithBlock(),
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	conn, err := grpc.DialContext(ctx, cfg.AllocationEndpoint, dialOpts...)
	if err != nil {
		return nil, fmt.Errorf("could not connect to agones allocation gRPC server: %w", err)
	}

	client := allocationv1.NewAllocationServiceClient(conn)

	return &agonesFleetAllocator{
		client: client,
		conn:   conn,
		cfg:    cfg,
	}, nil
}

// Allocate meminta 1 buah GameServer dari pool Agones yang siap pakai
func (a *agonesFleetAllocator) Allocate(ctx context.Context, matchID string, region string) (*allocationv1.AllocationResponse, error) {
	req := &allocationv1.AllocationRequest{
		Namespace: a.cfg.Namespace,
		GameServerSelectors: []*allocationv1.GameServerSelector{
			{
				MatchLabels: map[string]string{
					"agones.dev/fleet": a.cfg.FleetName,
					"game.infra/region": region,
				},
				GameServerState: allocationv1.GameServerSelector_READY,
			},
		},
		Metadata: &allocationv1.MetaPatch{
			Labels: map[string]string{
				"game.infra/match-id": matchID,
				"game.infra/allocated-at": fmt.Sprintf("%d", time.Now().Unix()),
			},
		},
	}

	// Retry mechanism dengan context deadline
	var resp *allocationv1.AllocationResponse
	var err error

	backoff := 50 * time.Millisecond
	for attempt := 0; attempt < 3; attempt++ {
		resp, err = a.client.Allocate(ctx, req)
		if err == nil {
			return resp, nil
		}

		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		case <-time.After(backoff):
			backoff *= 2
		}
	}

	return nil, fmt.Errorf("allocation failed after 3 attempts: %w", err)
}

func (a *agonesFleetAllocator) Close() error {
	return a.conn.Close()
}

// Simulasi Alokasi oleh Director
func main() {
	cfg := Config{
		AllocationEndpoint: "10.0.4.15:443", // Agones Allocation Service ClusterIP
		ClientCertPath:     "/etc/certs/tls.crt",
		ClientKeyPath:      "/etc/certs/tls.key",
		CACertPath:         "/etc/certs/ca.crt",
		FleetName:          "fps-fleet-apac",
		Namespace:          "game-servers",
	}

	// Eksekusi jika file certificate tersedia, simulasi validasi argumen
	if _, err := os.Stat(cfg.ClientCertPath); os.IsNotExist(err) {
		log.Printf("[WARN] TLS Certs tidak ditemukan di %s, runtime mock aktif.", cfg.ClientCertPath)
		fmt.Println("Status Mocking: Director siap bekerja dalam testing harness.")
		return
	}

	allocator, err := NewAgonesFleetAllocator(cfg)
	if err != nil {
		log.Fatalf("Initialization failed: %v", err)
	}
	defer allocator.Close()

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	matchUUID := "m-80e2a22d-209a-4cba-9a81-cfd70f03ce39"
	targetRegion := "ap-southeast-1"

	allocResponse, err := allocator.Allocate(ctx, matchUUID, targetRegion)
	if err != nil {
		log.Fatalf("Failed to allocate server: %v", err)
	}

	// Parsing detail host port untuk dialokasikan ke game client
	var gamePort int32
	for _, port := range allocResponse.Ports {
		if port.Name == "default" {
			gamePort = port.Port
			break
		}
	}

	log.Printf("[SUCCESS] Server Dialokasikan! IP: %s, Port: %d, ServerID: %s\n",
		allocResponse.Address, gamePort, allocResponse.GameServerName)
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: 60-Player Battle Royale Matchmaking & Allocation Spike saat Global Launch
- **Skala Beban**: 1.500.000 Concurrent Connected Users (CCU), 25.000 match requests/detik, 9 region AWS & Bare-metal Equinix.
- **Bottleneck Ditemukan**:
  1. *Agones Allocation Latency Explosion*: API Server Kubernetes mengalami throttling etcd karena ribuan GameServerAllocation CRD dibuat bersamaan.
  2. *Redis Ticket Contention*: Penumpukan pembacaan lock tiket pertandingan pada Redis Sorted Sets menyebabkan CPU Redis mencapai 100%.
- **Solusi Arsitektural yang Diterapkan**:
  1. **Agones Native Allocation gRPC Service**: Memotong API Server Kubernetes secara langsung dengan mengaktifkan controller Agones Allocation mandiri yang menyimpan in-memory state etcd read-only cache. Latensi alokasi turun dari 1200ms ke 35ms.
  2. **Bucketized Ticketing Engine**: Alih-alih satu Redis queue tunggal, tiket dibagi menjadi sub-shard berbasis kombinasi MMR Hash & Latency Range:
     $$\text{BucketKey} = \text{Hash}(\text{MMR} / 100) \pmod{32}$$
  3. **Node Pre-Warming & Fleet Autoscale Over-provisioning**: Diterapkan buffer *Standby Reserve* sebesar 15% dari kapasitas armada yang aktif.

```
                    Traffic Ingestion Peak: 25k req/s
                                    │
                         Hash Sharded Redis Ring
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
                Shard 01        Shard 02        Shard 32
                    │               │               │
                    └───────┬───────┴───────────────┘
                            ▼
               16 Concurrent Match Function Workers
                            │
               Match Proposals Generated (Sub-100ms)
                            │
                            ▼
          Agones Allocation gRPC In-Memory Service (Bypasses APIServer)
                            │ (35ms Allocation Window)
                            ▼
            Pre-Warmed DGS Armada: Ready -> Allocated
```

---

### 9. Trade-offs (Analisis Keputusan Rekayasa)

| Parameter | Pendekatan A: In-Engine Server Reuse | Pendekatan B: Ephemeral Pod per Match (Agones Pattern) |
| :--- | :--- | :--- |
| **Performance (Boot Time)** | Cepat. Server langsung memuat map berikutnya tanpa reload process (~2 detik). | Membutuhkan spin-up container baru atau Agones SDK state reset (~8-15 detik). |
| **Memory Leak Immunity** | Sangat Rendah. Engine modern (misal C++ UE5) rentan menyimpan fragmentasi memori. | Maksimal (100%). Container langsung di-terminate dan di-recreate via Kubernetes. |
| **Cost Efficiency** | Lebih hemat komputasi (Node pool static). | Membutuhkan over-provisioning resource buffer (10-20% standby pods). |
| **Blast Radius Isolation** | Tinggi. Server crash saat runtime berisiko mematikan multi-match jika multiplexed. | Terisolasi total. 1 Crash hanya memengaruhi pemain pada match ID tersebut. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum:
1. **Menggunakan Kubernetes ClusterIP untuk Traffic Game**: Routing berbasis iptables/IPVS Kubernetes akan mendistribusikan paket UDP antar pod secara round-robin acak, merusak kontinuitas sesi UDP point-to-point.
   - *Fix*: Selalu deklarasikan `hostPort` atau gunakan CNI native VPC IP routing (AWS VPC CNI / Cilium Direct Routing) di Agones spec.
2. **Zombie Allocated Servers**: Game crash tanpa memicu `SDK.Shutdown()` menyebabkan GameServer tertahan selamanya pada status `Allocated`.
   - *Fix*: Konfigurasikan `HealthCheck` timeout di Agones SDK spec dan terapkan server-side dead-mans-switch di level loop engine:
   ```go
   // Jika game loop berhenti mengirim health tick selama 5 detik, Agones menandai server Unhealthy
   err := agonesSDK.Health(ctx)
   ```
3. **MMR Starvation**: Pemain di ujung distribusi MMR (sangat tinggi/rendah) terjebak dalam antrean tak terbatas.
   - *Fix*: Implementasikan monotonic linear MMR expansion berdasarkan nilai parameter `time_in_queue`.

#### Panduan Troubleshooting Agones CrashLoopBackOff:
```bash
# 1. Cek status CRD GameServer secara detail
kubectl get gameserver -n game-servers -o wide

# 2. Periksa apakah Agones SDK Sidecar gagal terhubung dengan Game Engine binary
kubectl describe pod <gameserver-pod-name> -n game-servers

# 3. Analisis log dari sisi Agones Sidecar
kubectl logs <gameserver-pod-name> -c agones-gameserver-sidecar -n game-servers

# 4. Analisis output crash dari Game Binary Engine
kubectl logs <gameserver-pod-name> -c <game-engine-container-name> -n game-servers --previous
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Resource Limits Strict Declaration**: Set explicit `limits` dan `requests` pod secara identik (Guaranteed QoS Class) guna mencegah Node OOM-Killer mematikan game yang sedang aktif.
- [ ] **Descheduler Protection**: Pasang anotasi `agones.dev/safe-to-evict: "false"` pada DGS yang sedang dalam status `Allocated`.
- [ ] **Graceful Fleet Draining**: Sebelum melakukan upgrade version image armada, tandai Fleet lama dengan status scaling down hanya ketika server mencapai fase `Ready` dan tolak alokasi baru pada versi yang deprecated.
- [ ] **UDP Buffer Tuning di Level Host Linux**:
  ```ini
  # Tambahkan pada /etc/sysctl.conf
  net.core.rmem_max = 16777216
  net.core.wmem_max = 16777216
  net.ipv4.udp_mem = 4096 87380 16777216
  ```
- [ ] **mTLS Certificate Rotation**: Pastikan sertifikat controller Agones Allocation di-rotate secara otomatis via HashiCorp Vault atau cert-manager sebelum masa berlaku 365 hari berakhir.

---

### 12. Hands-on Practice

Simpan seluruh file berikut ke dalam direktori: `hands-on/m02/`

#### File 1: Definisi Armada Agones (`hands-on/m02/fleet.yaml`)
```yaml
apiVersion: "agones.dev/v1"
kind: Fleet
metadata:
  name: dedicated-fps-fleet
  namespace: default
spec:
  replicas: 2
  scheduling: Packed
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 25%
      maxUnavailable: 0
  template:
    metadata:
      labels:
        game.infra/tier: battle-royale
    spec:
      ports:
      - name: default
        containerPort: 7654
        protocol: UDP
        portPolicy: Dynamic
      health:
        initialDelaySeconds: 15
        periodSeconds: 5
        failureThreshold: 3
      template:
        spec:
          containers:
          - name: dedicated-game-server
            image: gcr.io/agones-images/simple-game-server:0.32
            resources:
              requests:
                memory: "512Mi"
                cpu: "500m"
              limits:
                memory: "512Mi"
                cpu: "500m"
```

#### File 2: Skrip Uji Alokasi (`hands-on/m02/test_allocation.yaml`)
```yaml
apiVersion: "allocation.agones.dev/v1"
kind: GameServerAllocation
metadata:
  name: manual-test-allocation
  namespace: default
spec:
  selectors:
    - matchLabels:
        game.infra/tier: battle-royale
      gameServerState: Ready
```

#### Langkah Eksekusi Praktikum:
```bash
# 1. Pastikan Minikube atau KinD cluster telah terinstal Agones (v1.36+)
kubectl apply -f hands-on/m02/fleet.yaml

# 2. Verifikasi 2 Pod GameServer berjalan dan masuk status Ready
kubectl get gameservers -l agones.dev/fleet=dedicated-fps-fleet

# 3. Lakukan simulasi alokasi server
kubectl create -f hands-on/m02/test_allocation.yaml

# 4. Amati perubahan status: 1 server akan berubah menjadi Allocated
kubectl get gameservers -l agones.dev/fleet=dedicated-fps-fleet

# 5. Uji koneksi ping UDP ke IP dan HostPort yang dialokasikan
# (Gunakan nc -u <IP> <PORT> untuk mengirim payload uji string)
```

---

### 13. Exercise

#### Tingkat: Easy
- **Tugas**: Tambahkan filter `GameServerSelector` tambahan pada skrip YAML alokasi yang mengharuskan server berada di node dengan label `topology.kubernetes.io/zone=ap-southeast-1a`.
- **Kriteria Keberhasilan**: GameServerAllocation gagal jika tidak ada node yang memiliki label zona tersebut, dan berhasil jika node dilabeli dengan benar.

#### Tingkat: Medium
- **Tugas**: Tulis sebuah interceptor Go gRPC untuk `agonesFleetAllocator` yang mencatat metrik Prometheus: total durasi alokasi (latency histogram) dan status kode alokasi (berhasil vs kehabisan kapasitas armada).
- **Kriteria Keberhasilan**: Interceptor mengekspos endpoint `/metrics` dengan metrik `game_allocation_duration_seconds_bucket`.

#### Tingkat: Hard
- **Tugas**: Rancang algoritma dynamic rate windowing di dalam Match Function menggunakan Redis Lua Scripting. Algoritma harus memeriksa tiket pertandingan dan memperlebar parameter pencarian MMR sebesar $\pm 50$ poin setiap interval 5 detik sejak waktu pembuatan tiket (`created_at`), dengan batas ekspansi maksimal $\pm 500$ poin.
- **Kriteria Keberhasilan**: Script Lua bersifat atomik, tidak menyebabkan blocking pada thread Redis, dan mampu memproses 1.000 evaluasi antrean dalam waktu di bawah 10 milidetik.

---

### 14. Challenge

**Skenario**: Studio game Anda meluncurkan fitur turnamen cross-region real-time. 
Sebanyak 100 tim (masing-masing 5 pemain) terdistribusi di Tokyo, Singapura, dan Sydney. 

**Tantangan**:
1. Rancang arsitektur **Optimal Fleet Placement Engine** yang menerima matriks latensi seluruh tim dan menentukan secara deterministik di Region mana armada server harus dialokasikan agar deviasi latensi (Ping Imbalance) antar tim berada pada titik paling adil (fairness-weighted lowest variance).
2. Mekanisme harus menangani fallback otomatis: jika di region terpilih kapasitas armada penuh (Capacity Exhaustion), server harus dialokasikan ke region peringkat kedua tercepat dalam waktu kurang dari 500ms.
3. Berikan diagram state transition engine alokasi dan formula matematis yang digunakan untuk menghitung skor pemilihan region berdasarkan fairness penalty factor.

*Catatan: Tidak ada jawaban instan. Solusi harus mempertimbangkan Trade-off matematis antara Mean Ping vs Ping Variance (Fairness).*

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Mengapa Kubernetes default Service (`ClusterIP`) tidak kompatibel untuk Dedicated Game Server UDP bertempo cepat?
2. Apa tujuan Agones sidecar menginisialisasi loop ping SDK Health secara periodik ke container engine game?
3. Sebutkan 4 fase siklus hidup (*lifecycle state*) dari GameServer CRD di Agones!
4. Apa fungsi dari komponen *Evaluator* dalam arsitektur Open Match?
5. Mengapa strategi scheduling `Packed` lebih disukai daripada `Distributed` pada Game Server Node Autoscaling?

#### B. Pertanyaan Intermediate
6. Bagaimana cara mencegah terjadinya alokasi ganda (*double allocation*) pada sebuah GameServer yang berstatus `Ready` saat beberapa Match Director meminta alokasi secara simultan?
7. Apa dampak mengabaikan anotasi eviction Kubernetes pada pod GameServer yang sedang `Allocated` saat proses upgrade node-pool dilakukan?
8. Mengapa penyimpanan data tiket antrean matchmaking di memori berbasis Redis Streams atau Sorted Sets lebih dipilih dibandingkan basis data dokumen NoSQL seperti MongoDB?
9. Bagaimana strategi menangani pemain yang mengalami pemutusan koneksi sementara (*temporary disconnect*) agar posisinya di Dedicated Game Server tidak langsung digantikan oleh pemain lain?
10. Apa keuntungan menggunakan port policy `Dynamic` dibandingkan `Static` pada Agones Fleet spec?

#### C. Skenario Kasus Produksi
11. **Skenario 1**: Setelah melakukan deployment versi baru game engine, Agones controller mendadak menghapus seluruh pod yang sedang berstatus `Allocated` di mana pemain sedang bertanding. Kesalahan konfigurasi apa yang terjadi pada deployment fleet YAML?
12. **Skenario 2**: Sistem Matchmaking mengalami lonjakan antrean pemain (*queue backlog*) hingga 10x lipat, namun kapasitas DGS Agones di Kubernetes menunjukkan 80% armada menganggur di status `Ready`. Di layer manakah arsitektur tersebut mengalami bottleneck?
13. **Skenario 3**: Log Agones sidecar menunjukkan status `Allocated`, namun pemain melaporkan kegagalan koneksi (*connection timed out*) saat handshake UDP. Apa analisis urutan diagnosa networking yang harus Anda lakukan?

---

### Kunci Jawaban Quiz

#### Bagian A (Basic)
1. Karena `ClusterIP` berbasis NAT/iptables/IPVS yang membagi paket antar pod backend, memecah integritas stream UDP stateful direct-connection.
2. Untuk mendeteksi apakah proses game engine mengalami *deadlock*, *crash*, atau *freeze*, sehingga Agones dapat langsung menandai pod sebagai `Unhealthy` dan menggantinya.
3. `Starting`, `Ready`, `Allocated`, dan `Shutdown`.
4. Menyelesaikan konflik tumpang tindih (*overlap*) jika satu tiket pertandingan terpilih secara tidak sengaja oleh dua Match Function yang berjalan paralel.
5. Strategi `Packed` memadatkan pod DGS ke sesedikit mungkin node agar node kosong lainnya dapat di-scale down menjadi nol oleh Kubernetes Cluster Autoscaler untuk menekan biaya cloud.

#### Bagian B (Intermediate)
6. Melalui mekanisme *Atomic State Transition* etcd dengan compare-and-swap (optimistic concurrency control) yang dieksekusi secara native oleh controller Agones Allocation.
7. Kubernetes akan mengirim sinyal `SIGTERM` secara sepihak untuk mematikan pod game yang sedang berlangsung demi mengosongkan node, memutuskan pemain di tengah pertandingan.
8. Redis menjamin latensi baca/tulis sub-milidetik dalam memori dan menyediakan operasi atomik asli (seperti ZADD, ZREM, ZRANGEBYSCORE) tanpa overhead disk I/O.
9. Menggunakan token reconnect berbasis waktu (reconnect window misalnya 60-120 detik) yang dicatat pada Lobby State Store; GameServer menahan status slot pemain tersebut sebelum menendangnya secara permanen.
10. Menghindari tabrakan alokasi nomor port host di node yang sama, memungkinkan densitas pod game yang jauh lebih tinggi per mesin fisik.

#### Bagian C (Kasus Produksi)
11. Kesalahan pada `strategy.rollingUpdate`. Jika `maxUnavailable` diset lebih besar dari 0 atau tipe deployment tidak dikonfigurasi dengan proteksi safe rolling update, Agones dapat menghentikan pod lama secara paksa tanpa menunggu status pod kembali ke `Ready`/selesai bermain.
12. Bottleneck berada pada layer **Match Function** atau **Director Ingestion**. Match Function kemungkinan memakan waktu komputasi terlalu lama (CPU starvation) atau mengalami dead-lock koneksi database/Redis saat mengevaluasi tiket, sehingga lambat menghasilkan alokasi ke Agones.
13. 
    - Verifikasi apakah IP publik node diekspos dengan benar (bukan IP internal VPC).
    - Cek *Security Group* cloud provider / firewall apakah membuka rentang port UDP dinamis Agones (biasanya 7000-8000 UDP).
    - Cek apakah host OS memblokir UDP traffic melalui rules `ufw` atau `iptables`.
    - Pastikan Game Engine benar-benar me-listen pada interface `0.0.0.0`, bukan terbatas pada `127.0.0.1` (loopback).

---

### 16. Summary

- **Pemisahan Kendali**: Arsitektur server game modern memisahkan pemrosesan antrean *matchmaking* dari lifecycle Dedicated Game Server (DGS).
- **Orkestrasi Kubernetes Native**: Agones mentransformasikan orkestrator kontainer umum menjadi sistem manajemen armada game berlatensi rendah dengan mengeliminasi bottleneck layer proxy konvensional.
- **Efisiensi & Skala**: Pendekatan alokasi gRPC langsung, packing pod deterministik, pemetaan port dinamis UDP, dan sharding tiket antrean adalah pilar fundamental dalam melayani jutaan pemain konkuren secara global dengan keandalan enterprise.