# Kurikulum Enterprise: Security Reliability Engineering & Disaster Recovery
**Kategori:** 05-DevOps-Cloud-and-SRE  
**Bab 10:** BAB-10-Security-Reliability-Engineering-Disaster-Recovery  
**Modul 02:** Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis & Mengarsitekrur** topologi Multi-Region Disaster Recovery tingkat lanjut (*Active-Active*, *Active-Passive* dengan *Hot/Warm Standby*) yang tahan terhadap *partition network* dan kegagalan skala *Cloud Region*.
- **Mengimplementasikan** mekanisme mitigasi *Split-Brain* menggunakan *Consensus Protocol* (Raft/Paxos), *Distributed Locking*, dan *Fencing Tokens*.
- **Mengintegrasikan** arsitektur *Zero Trust Reliability* lintas region menggunakan federasi identitas berbasis SPIFFE/SPIRE dan mutual TLS (mTLS).
- **Membangun & Mengotomatisasi** *Continuous DR Validation Engine* menggunakan *Chaos Engineering* dan *Automated Failover Orchestration* (RTO < 60 detik, RPO $\approx$ 0).
- **Mengevaluasi & Mengoptimalkan** *trade-off* latensi replikasi sinkron vs. asinkron, konsistensi data (CAP/PACELC), serta struktur biaya transfer data antar-region (*cross-region egress cost*).

---

## 2. Prerequisite

Peserta wajib menguasai:
- **Konsep Inti SRE:** Pemahaman mendalam mengenai SLI/SLO/SLA, *Error Budget*, dan *Burn Rate Alerting*.
- **Distributed Systems:** Konsep dasar konsensus (Raft/Paxos), CAP/PACELC *Theorem*, *Vector Clocks*, dan replikasi basis data (CDC, *Wal Shipping*).
- **Networking & Security:** BGP Anycast, DNS routing (GeoDNS, Latency-based, ARC), TLS 1.3 handshake, PKI (*Public Key Infrastructure*), dan otentikasi berbasis token/identitas x509.
- **Tools & Platform:** Kubernetes Multi-Cluster, Terraform, HashiCorp Vault, Prometheus/OpenTelemetry, dan bahasa pemrograman Go/Python untuk otomatisasi kontrol sistem.

---

## 3. Concept & Internal Architecture (Mendalam)

Implementasi Disaster Recovery (DR) dan Security Reliability Engineering (SRE-Sec) pada skala enterprise bergerak melampaui sekadar *backup-and-restore* berkala. Arsitektur produksi modern menuntut *Resilience by Design* yang menyatukan integritas kriptografis, ketersediaan tinggi (*High Availability*), dan pemulihan otomatis dari bencana (*Automated Disaster Recovery*).

### A. Taksonomi Strategi Multi-Region DR

```
+-------------------------------------------------------------------------------+
|                      SPEKTRUM ARSITEKTUR DISASTER RECOVERY                    |
+-------------------------------------------------------------------------------+
|  Model              | RTO           | RPO           | Kompleksitas | Biaya    |
+---------------------+---------------+---------------+--------------+----------+
|  Backup & Restore   | 24+ Jam       | 12 - 24 Jam   | Rendah       | $        |
|  Pilot Light        | 1 - 4 Jam     | Menit - Jam   | Sedang       | $$       |
|  Warm Standby       | 5 - 15 Menit  | Detik - Menit | Tinggi       | $$$      |
|  Hot Standby        | < 1 Menit     | ~0 (Sub-detik)| Sangat Tinggi| $$$$     |
|  Active-Active      | ~0 (Otomatis) | ~0 (Sinkron)  | Ekstrem      | $$$$$    |
+-------------------------------------------------------------------------------+
```

### B. Anatomi Partition & Split-Brain Mitigation

Tantangan paling kritis pada *failover* multi-region adalah **Split-Brain**: kondisi di mana partisi jaringan memutus komunikasi antar-region, menyebabkan Region A dan Region B sama-sama menganggap dirinya sebagai *Primary Cluster* yang aktif menerima operasi *write*. Hal ini mengakibatkan divergensi data ireversibel (*data corruption*).

Mitigasi kelas enterprise mengandalkan kombinasi:
1. **Third-Party Quorum (Witness/Arbiter):** Node independen di Region 3 yang tidak melayani *traffic* data, melainkan hanya berpartisipasi dalam *voting* konsensus (misalnya Raft quorum $N/2 + 1$).
2. **Fencing Tokens:** Setiap kali *promotion* terjadi, sebuah token monotonik bertambah (*monotonically increasing epoch counter*) diterbitkan. Basis data dan *storage layer* menolak perintah dari node dengan token yang lebih rendah dari token terakhir yang divalidasi.
3. **STONITH / Automated Node Fencing:** Mekanisme pemutusan akses jaringan atau terminasi komputasi instance primer lama via *Cloud Provider API* sebelum *Secondary Cluster* dipromosikan menjadi *Primary*.

### C. Zero Trust Reliability: SPIFFE/SPIRE Cross-Region Federation

Keandalan sistem tidak boleh mengorbankan postur keamanan selama insiden bencana. Selama *cross-region failover*, kredensial statis (API keys, static passwords) berisiko bocor atau *stale*. Federasi SPIFFE/SPIRE memungkinkan *workload* di Region Secondary membuktikan identitas kriptografisnya (*SPIFFE ID*) kepada *Vault* atau *upstream services* di Region Primary tanpa perlu berbagi *root secret*, memanfaatkan pertukaran *trust bundle* berbasis JWKS/X.509.

---

## 4. Why & What

### Mengapa SRE Membutuhkan Dimensi Keamanan dalam DR?
Bencana modern tidak hanya berupa gempa bumi atau putusnya kabel serat optik bawah laut (*physical disaster*), melainkan sering kali dipicu oleh insiden keamanan siber:
- Serangan Ransomware yang mengenkripsi *storage volume* utama.
- Kompromi kredensial *Cloud IAM Root/Admin* yang menghapus infrastruktur (*malicious insider*).
- Eksploitasi rantai pasok (*supply chain compromise*) yang menyuntikkan *backdoor* ke seluruh image kontainer aktif.

DR konvensional yang menyinkronkan data secara instan (*blind replication*) justru menyalin data yang terenkripsi oleh ransomware atau terkorupsi ke region *standby*. SRE modern menerapkan **Security-First DR**, yang mencakup:
- *Cryptographically signed immutable backups* (WORM - *Write Once Read Many*).
- *Automated blast-radius containment* via eBPF/Network Policy *quarantine*.
- *Air-gapped key management* (HSM independen per region).

---

## 5. How (Workflow Detail)

Alur kerja mitigasi dan eksekusi *Failover Multi-Region* terotomatisasi secara end-to-end:

```
[Health Probers / Telemetry]
        │
        ▼ (Region A Degradation Detected: SLI Error Rate > 5% & Heartbeat Timeout)
[Failover Controller / Operator]
        │
        ├─► 1. Acquire Consensus Lock from Witness Node (Region C)
        │      (Abort if Quorum not achieved)
        │
        ├─► 2. Execute Fencing (Revoke Region A write-lease, issue Fencing Token #Epoch+1)
        │
        ├─► 3. Validate Replication Lag on Region B (RPO Gate Check: lag < threshold)
        │
        ├─► 4. Promote Region B Database to Read-Write
        │
        ├─► 5. Shift Global Ingress Traffic (BGP Anycast withdrawal / Route53 ARC routing controls)
        │
        └─► 6. Post-Failover Sanity Verification (E2E Synthetic Probe on Region B)
```

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem Kontrol Lalu Lintas Udara
Bayangkan sistem navigasi bandara utama (Region A) dan bandara cadangan (Region B). Region C adalah Menara Komunikasi Pusat (Quorum Witness). 
Jika lampu landasan Bandara A padam mendadak, Bandara B tidak boleh sembarangan membuka landasan pacu untuk pendaratan internasional tanpa izin dari Menara C. Jika Bandara B mendaratkan pesawat sementara Bandara A ternyata masih mendaratkan pesawat di tengah kegelapan, akan terjadi tabrakan fatal (*Split-Brain*). Bandara B harus memegang izin resmi terbaru (*Fencing Token*) yang secara resmi mencabut lisensi operasi Bandara A sebelum rute penerbangan dialihkan (*DNS/BGP Switch*).

### Diagram Arsitektur Multi-Region Active-Passive dengan Witness Quorum

```
                       +-------------------------------+
                       |   Anycast / Route53 ARC / CDN |
                       +---------------+---------------+
                                       │
                  ┌────────────────────┴────────────────────┐
                  │ Traffic Route (Weight: 100 -> 0)        │ Traffic Route (Weight: 0 -> 100)
                  ▼                                         ▼
+-----------------------------------+     +-----------------------------------+
|            REGION A               |     |            REGION B               |
|            (Primary)              |     |            (Standby)              |
|                                   |     |                                   |
|  +-----------------------------+  |     |  +-----------------------------+  |
|  |     Envoy Ingress Gateway   |  |     |  |     Envoy Ingress Gateway   |  |
|  +--------------+--------------+  |     |  +--------------+--------------+  |
|                 │                 |     |                 │                 |
|  +--------------▼--------------+  |     |  +--------------▼--------------+  |
|  |   Kubernetes Workload Cluster |  |     |  |   Kubernetes Workload Cluster |  |
|  +--------------+--------------+  |     |  +--------------+--------------+  |
|                 │                 |     |                 │                 |
|  +--------------▼--------------+  |     |  +--------------▼--------------+  |
|  | Database Primary (Read/Write)|  |     |  | Database Replica (Read-Only)|  |
|  | Lease Holder (Epoch: 42)    |  |     |  | Target Promotion            |  |
|  +--------------+--------------+  |     |  +--------------+--------------+  |
+-----------------│-----------------+     +-----------------│-----------------+
                  │                                         │
                  │   Async/Sync WAL Streaming Engine       │
                  │========================================>│
                  │                                         │
                  └───────────────┐         ┌───────────────┘
                                  │         │
                                  ▼         ▼
                       +-------------------------------+
                       |       REGION C (Witness)      |
                       |                               |
                       |  +-------------------------+  |
                       |  | Distributed Lock (etcd) |  |
                       |  | Quorum State Authority  |  |
                       |  | Current Epoch: 42       |  |
                       |  +-------------------------+  |
                       +-------------------------------+
```

---

## 7. Simple Example & Practical Example

### Simple Example: Pemeriksa Lag Replikasi Database & Evaluasi Ambang Batas RPO (Python)

Skrip ini bertindak sebagai *health monitor* independen yang menghitung keterlambatan replikasi (*replication lag*) dalam satuan byte/detik untuk menentukan kelayakan *failover*.

```python
#!/usr/bin/env python3
import sys
import psycopg2

def get_replication_lag(dsn_standby: str) -> float:
    try:
        conn = psycopg2.connect(dsn_standby)
        with conn.cursor() as cur:
            cur.execute("""
                SELECT CASE 
                    WHEN pg_last_wal_receive_lsn() = pg_last_wal_replay_lsn() THEN 0
                    ELSE EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp()))
                END AS lag_seconds;
            """)
            row = cur.fetchone()
            return float(row[0]) if row and row[0] is not None else 999999.0
    except Exception as e:
        print(f"[ERROR] Gagal memverifikasi status standby: {e}", file=sys.stderr)
        return float('inf')

if __name__ == "__main__":
    RPO_THRESHOLD_SECONDS = 5.0
    STANDBY_DSN = "postgresql://replicator:secret@10.200.0.15:5432/production?sslmode=verify-full"
    
    lag = get_replication_lag(STANDBY_DSN)
    print(f"[INFO] Current Standby Replication Lag: {lag:.2f} detik")
    
    if lag > RPO_THRESHOLD_SECONDS:
        print(f"[FATAL] RPO Terlanggar! Lag ({lag:.2f}s) > Threshold ({RPO_THRESHOLD_SECONDS}s). Failover Otomatis Dibatalkan!")
        sys.exit(1)
        
    print("[SUCCESS] Standby siap dipromosikan (RPO dalam toleransi aman).")
    sys.exit(0)
```

---

### Practical Example: Production-Grade Automated Failover Controller dengan Fencing Tokens (Go)

Kode berikut mengimplementasikan mesin *failover* berbasis konsensus distributed lock (etcd/Raft) dengan penerbitan *monotonically increasing fencing token*.

```go
package main

import (
	"context"
	"crypto/tls"
	"crypto/x509"
	"fmt"
	"log"
	"os"
	"time"

	clientv3 "go.etcd.io/etcd/client/v3"
	"go.etcd.io/etcd/client/v3/concurrency"
)

type FailoverOrchestrator struct {
	client     *clientv3.Client
	session    *concurrency.Session
	election   *concurrency.Election
	regionID   string
	lockKey    string
	promoted   bool
}

func NewFailoverOrchestrator(endpoints []string, regionID string) (*FailoverOrchestrator, error) {
	// Memuat mTLS Certificates untuk koneksi ke witness etcd
	tlsConfig, err := loadMTLSConfig("/etc/certs/ca.pem", "/etc/certs/cert.pem", "/etc/certs/key.pem")
	if err != nil {
		return nil, fmt.Errorf("gagal menginisialisasi TLS: %w", err)
	}

	cli, err := clientv3.New(clientv3.Config{
		Endpoints:   endpoints,
		DialTimeout: 5 * time.Second,
		TLS:         tlsConfig,
	})
	if err != nil {
		return nil, fmt.Errorf("gagal terhubung ke etcd witness: %w", err)
	}

	session, err := concurrency.NewSession(cli, concurrency.WithTTL(10))
	if err != nil {
		cli.Close()
		return nil, fmt.Errorf("gagal membuat session: %w", err)
	}

	election := concurrency.NewElection(session, "/dr/primary-election")

	return &FailoverOrchestrator{
		client:   cli,
		session:  session,
		election: election,
		regionID: regionID,
		lockKey:  "/dr/fencing-token",
		promoted: false,
	}, nil
}

func (fo *FailoverOrchestrator) RunFailoverLoop(ctx context.Context) {
	log.Printf("[INFO] Memulai Failover Monitor di region: %s", fo.regionID)
	
	// Mencoba memenangkan kepemimpinan (leader election) jika region primary gagal
	for {
		select {
		case <-ctx.Done():
			log.Println("[INFO] Menghentikan loop pemulihan...")
			return
		default:
			log.Println("[INFO] Mencoba mengakuisisi kepemimpinan failover...")
			if err := fo.election.Campaign(ctx, fo.regionID); err != nil {
				log.Printf("[WARN] Gagal berkampanye untuk kepemimpinan: %v. Mengulang dalam 2 detik...", err)
				time.Sleep(2 * time.Second)
				continue
			}

			// Pemimpin terpilih: Dapatkan fencing token baru secara atomik
			fencingToken, err := fo.acquireNewFencingToken(ctx)
			if err != nil {
				log.Printf("[ERROR] Gagal mendapatkan fencing token: %v", err)
				fo.election.Resign(ctx)
				time.Sleep(2 * time.Second)
				continue
			}

			log.Printf("[CRITICAL] Leader terpilih! Region: %s, Fencing Token Epoch: %d", fo.regionID, fencingToken)
			
			// Langkah 1: Isolasi cluster lama (Fencing via Cloud API/Network Route)
			if err := fo.fenceZombieCluster(ctx); err != nil {
				log.Printf("[FATAL] Gagal mengisolasi cluster lama: %v. Batalkan promosi!", err)
				fo.election.Resign(ctx)
				continue
			}

			// Langkah 2: Promosikan Standby Database lokal ke Primary
			if err := fo.promoteLocalStandby(ctx, fencingToken); err != nil {
				log.Printf("[FATAL] Promosi basis data gagal: %v", err)
				fo.election.Resign(ctx)
				continue
			}

			// Langkah 3: Update Global Routing Traffic
			if err := fo.shiftGlobalTraffic(ctx); err != nil {
				log.Printf("[ERROR] Gagal mengalihkan traffic global: %v", err)
			}

			fo.promoted = true
			log.Println("[SUCCESS] Failover berhasil diselesaikan dengan aman.")
			
			// Pantau session leader
			select {
			case <-fo.session.Done():
				log.Println("[WARN] Sesi kepemimpinan terputus. Mengembalikan status promosi.")
				fo.promoted = false
				return
			case <-ctx.Done():
				return
			}
		}
	}
}

func (fo *FailoverOrchestrator) acquireNewFencingToken(ctx context.Context) (int64, error) {
	// Transaksi atomik etcd untuk increment epoch token
	resp, err := fo.client.KV.Get(ctx, fo.lockKey)
	if err != nil {
		return 0, err
	}

	var currentEpoch int64 = 0
	var modRev int64 = 0
	if len(resp.Kvs) > 0 {
		fmt.Sscanf(string(resp.Kvs[0].Value), "%d", &currentEpoch)
		modRev = resp.Kvs[0].ModRevision
	}

	nextEpoch := currentEpoch + 1
	valStr := fmt.Sprintf("%d", nextEpoch)

	var txn clientv3.Txn
	if modRev == 0 {
		txn = fo.client.Txn(ctx).If(clientv3.Compare(clientv3.CreateRevision(fo.lockKey), "=", 0))
	} else {
		txn = fo.client.Txn(ctx).If(clientv3.Compare(clientv3.ModRevision(fo.lockKey), "=", modRev))
	}

	txnResp, err := txn.Then(clientv3.OpPut(fo.lockKey, valStr)).Commit()
	if err != nil {
		return 0, err
	}
	if !txnResp.Succeeded {
		return 0, fmt.Errorf("konflik konkuren saat memperbarui fencing token")
	}

	return nextEpoch, nil
}

func (fo *FailoverOrchestrator) fenceZombieCluster(ctx context.Context) error {
	log.Println("[STEP 1] Melakukan fencing ke cluster lama via Network Security Group...")
	// Simulasi panggilan Cloud API / SDN Controller untuk mencabut route
	time.Sleep(500 * time.Millisecond)
	return nil
}

func (fo *FailoverOrchestrator) promoteLocalStandby(ctx context.Context, token int64) error {
	log.Printf("[STEP 2] Mempromosikan basis data lokal dengan Fencing Token: %d...", token)
	// Simulasi eksekusi perintah SQL: pg_promote() atau modifikasi kontrol consensus
	time.Sleep(1 * time.Second)
	return nil
}

func (fo *FailoverOrchestrator) shiftGlobalTraffic(ctx context.Context) error {
	log.Println("[STEP 3] Mengalihkan Anycast/DNS Traffic ke region ini...")
	time.Sleep(500 * time.Millisecond)
	return nil
}

func loadMTLSConfig(caCertPath, clientCertPath, clientKeyPath string) (*tls.Config, error) {
	caCert, err := os.ReadFile(caCertPath)
	if err != nil {
		return nil, err
	}
	caCertPool := x509.NewCertPool()
	caCertPool.AppendCertsFromPEM(caCert)

	cert, err := tls.LoadX509KeyPair(clientCertPath, clientKeyPath)
	if err != nil {
		return nil, err
	}

	return &tls.Config{
		Certificates: []tls.Certificate{cert},
		RootCAs:      caCertPool,
		MinVersion:   tls.VersionTLS13,
	}, nil
}

func main() {
	ctx := context.Background()
	endpoints := []string{"10.250.0.10:2379", "10.250.0.11:2379", "10.250.0.12:2379"}
	regionID := "ap-southeast-3" // Region Jakarta sebagai Standby

	// Jalankan orchestrator (eksekusi terlindungi oleh simulasi runtime)
	fmt.Println("[BOOT] Orchestrator Failover Engine Terinisialisasi.")
	_ = ctx
	_ = endpoints
	_ = regionID
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Insiden Pemadaman Region Cloud Utama pada FinTech Payment Gateway Skala Nasional
- **Konteks:** Sebuah payment engine memproses >15.000 Transaksi Per Detik (TPS). Region primer berada di Singapore (`ap-southeast-1`), sedangkan *hot standby* berada di Jakarta (`ap-southeast-3`). Region witness berada di Tokyo (`ap-northeast-1`).
- **Insiden:** Terjadi *fiber cut* pada jaringan inter-region cloud provider, disertai degradasi sistem IAM internal cloud secara global di region Singapore. Ketersediaan API jatuh hingga 0% dalam waktu 3 menit.
- **Dampak Awal:** Transaksi *in-flight* mengalami kegagalan massal. Database asinkron di Jakarta tertinggal 420 ms di belakang primary.
- **Aksi Pemulihan (Execution of DR Plan):**
  1. *Consensus Engine* di Region Tokyo mendeteksi hilangnya detak jantung (*heartbeat*) Singapore selama 15 detik berturut-turut.
  2. Orchestrator Jakarta meminta akuisisi kepemimpinan. Tokyo memberikan Fencing Token Epoch `1089`.
  3. Sistem memicu isolasi API Singapore melalui Route53 Application Recovery Controller (ARC).
  4. Database Postgres Aurora Replica di Jakarta dipromosikan ke Primary. Data *in-flight* yang hilang diselamatkan dari *dead-letter queue* Kafka yang tersinkronisasi via MirrorMaker 2 (Active-Active Kafka).
- **Hasil Terukur:**
  - **RTO Aktual:** 48 detik (Target SLO: < 60 detik).
  - **RPO Aktual:** 0 transaksi finansial hilang (Data yang tertinggal direkonsiliasi otomatis dalam 4 menit melalui pencocokan Ledger Event Log).
  - Tidak terjadi *Split-Brain* karena transaksi lama yang tertahan di Singapura langsung ditolak oleh layer backend begitu koneksi pulih, akibat ketidakcocokan Fencing Token.

---

## 9. Trade-offs

Mengimplementasikan DR Multi-Region tingkat tinggi menuntut kompromi arsitektural yang ketat:

```
+-------------------+-----------------------------+-----------------------------+
| Parameter         | Synchronous Replication     | Asynchronous Replication    |
+-------------------+-----------------------------+-----------------------------+
| Latency Penalty   | Ekstrem (+20ms s/d +80ms     | Nyaris Nol (< 1ms lokal)   |
|                   | antar region round-trip)    |                             |
+-------------------+-----------------------------+-----------------------------+
| Data Loss (RPO)   | RPO = 0 (Jaminan Mutlak)    | RPO > 0 (Tergantung lag     |
|                   |                             | replikasi WAL, misal < 1s)  |
+-------------------+-----------------------------+-----------------------------+
| Network Cost      | Sangat Tinggi (SLA Jaringan | Standar (Egress data sync   |
|                   | khusus, eg. DirectConnect)  | batching via kompresi)      |
+-------------------+-----------------------------+-----------------------------+
| Availability Risk | Turun: Jika koneksi WAN     | Tinggi: Cluster primer tetap|
|                   | terganggu, write terblokir  | bisa write meski WAN putus  |
+-------------------+-----------------------------+-----------------------------+
```

### Analisis Finansial vs Keandalan (FinOps Dimension):
- **Active-Active:** Memerlukan infrastruktur ganda 100% kapasitas di kedua region + sinkronisasi state latensi rendah. Biaya komputasi & lisensi meningkat $2.1\times - 2.5\times$.
- **Pilot Light:** Memangkas biaya komputasi hingga $60\%$ di region sekunder, namun menaikkan RTO hingga 15-30 menit karena provisioning node Kubernetes membutuhkan waktu *spin-up*.

---

## 10. Common Mistakes & Troubleshooting

### Kesalahan Fatal Umum dalam DR:
1. **The Ghost Primary (Split-Brain):** Melakukan promosi database sekunder tanpa mematikan atau mengisolasi (*fencing*) database primer lama terlebih dahulu.
2. **Untested Secrets & Certificates:** Sijil mTLS atau API Key di Region B kadaluarsa tanpa disadari, menyebabkan seluruh *workload* gagal autentikasi saat trafik dialihkan.
3. **Capacity Blackhole:** Region B hanya dipersiapkan untuk menampung $20\%$ trafik dev/staging. Ketika failover $100\%$ trafik dialihkan ke Region B, terjadi kegagalan kaskade (*Cascading OOM Failure*).
4. **Circular Dependency on Cloud Control Plane:** Skrip failover Anda bergantung pada Cloud Provider IAM/API yang justru sedang padam di region yang terkena bencana.

### Troubleshooting Checklist & Debugging:

```bash
# 1. Periksa Latensi Jaringan Antar-Region & Jitter (Deteksi Degradasi Jaringan)
mtr -rw -c 50 --tcp -P 5432 <IP_TARGET_STANDBY_DB>

# 2. Validasi TLS Handshake & Sisa Masa Berlaku Sertifikat Lintas Region
openssl s_client -connect witness.etcd.internal:2379 -servername witness.etcd.internal \
  -CAfile /etc/certs/ca.pem -cert /etc/certs/cert.pem -key /etc/certs/key.pem </dev/null 2>/dev/null \
  | openssl x509 -noout -dates -subject

# 3. Analisis Replikasi Slot Postgres Standby
psql -h primary-db -U postgres -c "SELECT slot_name, active, active_pid, pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) AS replication_lag FROM pg_replication_slots;"

# 4. Verifikasi Health Check Status Route53 Application Recovery Controller (ARC)
aws route53-recovery-control-config get-routing-control-states \
  --routing-control-states-entries RoutingControlArn=arn:aws:route53-recovery-control::123456789:control/abc123
```

---

## 11. Best Practices (Production Checklist)

Berikut adalah daftar periksa wajib sebelum arsitektur DR dinyatakan *Production-Ready*:

- [ ] **Data Immutability:** *Snapshot backup* dikunci dengan kebijakan WORM (*Object Lock Compliance Mode*) untuk mencegah penghapusan akibat ransomware.
- [ ] **Independent Secret Engines:** HashiCorp Vault berjalan mandiri di tiap region; tidak bergantung pada enkripsi vault lintas region yang rentan terputus.
- [ ] **Cross-Region Capacity Reservations:** Kuota compute instance (*On-Demand Capacity Reservation*) telah dialokasikan di region cadangan guna menghindari `InsufficientInstanceCapacity`.
- [ ] **Automated Fencing Pipeline:** Sistem memiliki kemampuan STONITH berbasis API atau modifikasi security-group darurat tanpa intervensi manual.
- [ ] **GameDay Schedule:** Simulasi pemadaman total (*Chaos GameDay*) wajib dieksekusi terjadwal secara otomatis di *production* minimal setiap kuartal.
- [ ] **Fencing Tokens Implemented:** Seluruh RPC dan operasi modifikasi data memvalidasi token monotonik yang diterbitkan otoritas konsensus.

---

## 12. Hands-on Practice

Dalam latihan ini, Anda akan mensimulasikan lingkungan Multi-Region DR lokal dengan satu cluster etcd terdistribusi sebagai penentu konsensus (*Witness*), mendeteksi kegagalan primary, menerbitkan *fencing token*, dan mempromosikan node cadangan.

Simpan seluruh file di: `hands-on/m02/`

### File: `hands-on/m02/docker-compose.yaml`
```yaml
version: '3.8'

services:
  witness-etcd:
    image: quay.io/coreos/etcd:v3.5.9
    container_name: witness-etcd
    command:
      - /usr/local/bin/etcd
      - --name=witness
      - --data-dir=/etcd-data
      - --listen-client-urls=http://0.0.0.0:2379
      - --advertise-client-urls=http://witness-etcd:2379
      - --listen-peer-urls=http://0.0.0.0:2380
      - --initial-advertise-peer-urls=http://witness-etcd:2380
      - --initial-cluster=witness=http://witness-etcd:2380
    networks:
      - dr-network

  primary-db:
    image: postgres:15-alpine
    container_name: primary-db
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: supersecretpassword
      POSTGRES_DB: appdb
    volumes:
      - ./init-primary.sql:/docker-entrypoint-initdb.d/init.sql
    networks:
      - dr-network

  secondary-db:
    image: postgres:15-alpine
    container_name: secondary-db
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: supersecretpassword
      POSTGRES_DB: appdb
    networks:
      - dr-network
    depends_on:
      - primary-db

networks:
  dr-network:
    driver: bridge
```

### File: `hands-on/m02/init-primary.sql`
```sql
CREATE TABLE transaction_ledger (
    id SERIAL PRIMARY KEY,
    fencing_epoch BIGINT NOT NULL,
    amount NUMERIC(15, 2) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO transaction_ledger (fencing_epoch, amount) VALUES (1, 1000.00);
```

### Langkah Praktikum:
1. **Jalankan Lab Multi-Node:**
   ```bash
   cd hands-on/m02/
   docker compose up -d
   ```
2. **Inisialisasi Fencing State di Witness etcd:**
   ```bash
   docker exec -it witness-etcd etcdctl put /dr/fencing-token "1"
   docker exec -it witness-etcd etcdctl put /dr/active-region "region-primary"
   ```
3. **Simulasikan Bencana (Matikan Region Primary):**
   ```bash
   docker stop primary-db
   ```
4. **Eksekusi Promosi Failover Manual/Script:**
   - Dapatkan token baru:
     ```bash
     TOKEN=$(docker exec -it witness-etcd etcdctl get /dr/fencing-token --print-value-only)
     NEW_TOKEN=$((TOKEN + 1))
     docker exec -it witness-etcd etcdctl put /dr/fencing-token "$NEW_TOKEN"
     docker exec -it witness-etcd etcdctl put /dr/active-region "region-secondary"
     echo "Region B dipromosikan dengan Fencing Token: $NEW_TOKEN"
     ```
5. **Verifikasi Isolasi (Cegah Split-Brain):**
   - Hidupkan kembali `primary-db`:
     ```bash
     docker start primary-db
     ```
   - Validasi bahwa Primary lama sekarang berstatus *Zombie* dan tidak boleh menerima trafik karena epoch token-nya tertinggal.

---

## 13. Exercise

### Level Easy
Hitung ketersediaan tahunan (*availability SLA*) untuk arsitektur *Warm Standby* di mana region primer memiliki ketersediaan $99.9\%$, region sekunder $99.9\%$, dan mekanisme failover terotomatisasi memiliki tingkat keberhasilan $98\%$. Berapa menit total downtime maksimal dalam setahun?

### Level Medium
Tulis sebuah fungsi skrip Bash menggunakan `curl` dan `etcdctl` yang melakukan *pre-flight check* ke region standby sebelum eksekusi promosi. Skrip harus memverifikasi bahwa:
1. Standby database dapat dijangkau.
2. Witness quorum etcd berada dalam status *Healthy*.
3. Jika kondisi terpenuhi, cetak persetujuan promosi `PROCEED_FAILOVER=TRUE`.

### Level Hard
Rancang arsitektur terinci (*Design Document*) mitigasi *Split-Brain* untuk kluster Redis Cluster lintas benua (misal: AWS Frankurt ke AWS São Paulo). Karena latensi >180ms, replikasi sinkron tidak dimungkinkan. Tentukan algoritma rekonsiliasi data yang digunakan (*CRDTs vs Last-Write-Wins*), bagaimana skema *vector clock* diterapkan pada layer aplikasi, dan mekanisme *circuit breaker* saat terjadi pemutusan link WAN.

---

## 14. Challenge

**Skenario Kasus Kompleks:**
Anda adalah Principal SRE pada perusahaan Core Banking multi-nasional. Regulator mewajibkan sistem Anda mematuhi regulasi ketat: **RPO = 0 detik (Nol Data Loss mutlak)** dan **RTO < 30 detik**, bahkan jika seluruh region *data center* fisik meledak atau mengalami pemadaman total.

Tantangan Teknis:
1. Latensi jaringan antara Data Center 1 (Utama) dan Data Center 2 (Sekunder) adalah 18 ms (jarak ~1200 km).
2. Transaksi finansial membutuhkan konfirmasi *two-phase commit* (2PC) atau Paxos/Raft log sync sebelum mengembalikan status `HTTP 200 OK` ke nasabah.
3. Aplikasi tidak boleh mengalami penurunan performa transaksi (*TPS drops*) lebih dari $15\%$ dari batas normal ($10.000$ TPS).

**Tugas Anda:**
- Gambarkan topologi jaringan dan penyimpanan lengkap (termasuk penempatan *Consensus Quorum Witness Node* ketiga untuk menghindari *two-node split-brain*).
- Tentukan mekanisme konsensus basis data yang mampu memenuhi RPO = 0 pada latensi 18 ms.
- Berikan simulasi matematis mengapa RTO < 30 detik dapat dicapai tanpa intervensi manusia, lengkap dengan spesifikasi *fencing timeout* dan mitigasi resiko *false positive failover*.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Pertanyaan)
1. **Apa perbedaan mendasar antara RTO (*Recovery Time Objective*) dan RPO (*Recovery Point Objective*)?**
   - *Jawaban:* RTO adalah durasi maksimal pemulihan sistem hingga dapat beroperasi kembali setelah insiden. RPO adalah batas toleransi maksimal kehilangan data yang dihitung dalam rentang waktu sebelum bencana terjadi.
2. **Mengapa replikasi asinkron (*asynchronous replication*) selalu menghasilkan RPO > 0?**
   - *Jawaban:* Karena terdapat jeda waktu (*replication lag*) antara saat data di-commit di Primary dan saat data diterima/ditulis pada storage Replica di secondary region. Jika Primary padam seketika, data di dalam buffer transmisi hilang.
3. **Apa yang dimaksud dengan kondisi *Split-Brain* pada sistem terdistribusi?**
   - *Jawaban:* Kondisi anomali ketika dua atau lebih kluster/node secara terpisah menganggap dirinya sebagai *Primary/Leader* yang aktif secara bersamaan akibat putusnya komunikasi jaringan (*network partition*), mengakibatkan ketidaksinkronan data.
4. **Apa fungsi utama *Witness Node* dalam topologi Disaster Recovery multi-region?**
   - *Jawaban:* Bertindak sebagai pihak ketiga netral untuk menyediakan kuorum mayoritas (*consensus voting*) tanpa menyimpan beban kerja data penuh, sehingga memecahkan kondisi seri (*tie-break*) saat partisi jaringan terjadi.
5. **Mengapa *Active-Active Multi-Region* adalah strategi DR yang paling mahal?**
   - *Jawaban:* Karena memerlukan duplikasi penuh resource infrastruktur di seluruh region, sinkronisasi state latensi rendah yang kompleks, serta biaya transfer data egress antar-region yang tinggi secara terus-menerus.

### Bagian 2: Intermediate (5 Pertanyaan)
1. **Bagaimana mekanisme *Fencing Token* secara matematis dan logis mencegah korupsi data oleh zombie primary?**
   - *Jawaban:* Fencing Token adalah bilangan monotonik yang terus naik (*monotonically increasing counter*) yang dikeluarkan oleh konsensus. Penyimpanan/Database hanya memproses request dengan token tertinggi. Ketika zombie node mengirim write request dengan token lama, storage engine langsung menolaknya.
2. **Dalam kondisi degradasi jaringan parsial (*intermittent packet loss*), mengapa failover otomatis yang terlalu agresif dapat memperburuk ketersediaan sistem (*flapping failover*)?**
   - *Jawaban:* Kegagalan sementara dapat memicu failover prematur. Proses failover itu sendiri memiliki biaya overhead (koneksi terputus, *cache warm-up*, propagasi DNS). Jika traffic bolak-balik dialihkan (*flapping*), sistem akan mengalami *downtime* kaskade yang jauh lebih lama daripada degradasi awal.
3. **Bagaimana peran federasi identitas SPIFFE/SPIRE dalam menjaga postur keamanan selama insiden DR?**
   - *Jawaban:* Menyediakan identitas kriptografis jangka pendek (*ephemeral X.509 SVID*) yang terverifikasi otomatis lintas region melalui federasi trust bundle, mengeliminasi kebutuhan penggunaan API keys/secrets statis yang rawan bocor saat proses disaster recovery.
4. **Jelaskan batasan utama penggunaan DNS TTL rendah (misal 5 detik) untuk failover lintas region!**
   - *Jawaban:* Banyak DNS resolver publik, ISP, dan client caching mengabaikan nilai TTL yang sangat rendah (*TTL overriding/caching violations*), sehingga jutaan client tetap mengirim traffic ke region yang mati lama setelah DNS record diperbarui.
5. **Bagaimana Anycast BGP mengatasi kelemahan failover berbasis DNS?**
   - *Jawaban:* Anycast menggunakan alamat IP tunggal yang sama di seluruh dunia yang diumumkan melalui routing BGP. Failover dilakukan di level rute jaringan dengan mencabut (*withdrawing*) rute BGP dari region yang bermasalah, memungkinkan failover traffic dalam hitungan detik tanpa bergantung pada cache resolver DNS client.

### Bagian 3: Skenario Kasus Produksi (3 Kasus)

#### Kasus 1: Anomali "Split-State" pada Asynchronous Database Promotion
- **Skenario:** Kluster primer di Frankfurt mengalami crash listrik total. SRE mempromosikan replika di Dublin menjadi primary. Tiga puluh menit kemudian, teknisi data center menyalakan kembali server Frankfurt tanpa memutus kabel jaringan. Node Frankfurt langsung menerima request sisa dari worker internal yang belum memperbarui konfigurasi.
- **Analisis:** Mengapa insiden ini terjadi dan langkah teknis apa yang seharusnya diterapkan pada level arsitektur jaringan untuk mencegah node lama online sebagai primary liar?
- *Jawaban Analisis:* Terjadi akibat ketiadaan STONITH / Network Fencing otomatis. Solusinya: Implementasi *fencing hook* di mana node boot sequence mewajibkan verifikasi lease aktif ke konsensus eksternal (etcd/witness). Jika lease gagal didapat atau tokennya kadaluarsa, daemon database menolak menyala (*fail-safe halt*) atau firewall lokal memblokir port database (5432) secara otomatis.

#### Kasus 2: Degradasi Performa Akibat "Replication Stall" Sinkron
- **Skenario:** Perusahaan e-commerce mengaktifkan *synchronous replication* Postgres antara dua region demi mencapai RPO = 0. Tiba-tiba, p99 Latensi transaksi aplikasi melonjak dari 15ms menjadi 2.400ms, menyebabkan HTTP 504 Gateway Timeout masal, meskipun utilisasi CPU kedua database < 30%.
- **Analisis:** Apa akar masalah degradasi tersebut dan bagaimana mitigasi arsitekturnya tanpa langsung mengubah konfigurasi menjadi full-asynchronous?
- *Jawaban Analisis:* Akar masalah adalah latensi round-trip jaringan WAN yang melonjak (*network jitter/congestion*) atau IOPS disk replica macet, menahan *commit ACK* pada primary. Mitigasi: Terapkan *Semisynchronous Replication* dengan quorum fleksibel (misal commit dianggap valid jika diterima oleh 1 dari 2 replika lokal tercepat, sementara replika lintas region menerima streaming paralel dengan proteksi timeout `synchronous_commit = remote_write` atau *fallback to async with alert* jika lag melebihi SLA).

#### Kasus 3: Cascading Failure Akibat "Cold Cache" Pasca-DR Failover
- **Skenario:** Kluster aplikasi berhasil dialihkan ke region sekunder dalam waktu 40 detik (RTO tercapai). Namun, sesaat setelah trafik 100% masuk, database sekunder mengalami lonjakan CPU hingga 100% dan seluruh sistem mengalami *blackout* total selama 2 jam.
- **Analisis:** Mengapa kluster sekunder ambruk padahal kapasitas hardware identik dengan kluster primer, dan bagaimana desain arsitektur SRE untuk mencegahnya?
- *Jawaban Analisis:* Fenomena ini disebabkan oleh *Cold Cache* (Redis cache dan buffer pool DB di region cadangan masih kosong). Semua request langsung menghantam IOPS disk database (*cache stampede*). Solusi: Replikasi cache lintas region secara proaktif (*Cross-Region Redis replication*), implementasi *Canary/Progressive Traffic Shifting* (mengalirkan trafik bertahap: 10% -> 25% -> 50% -> 100%), dan *Cache Pre-warming script* sebelum membuka pintu ingress traffic secara penuh.

---

## 16. Summary

1. **DR Bukan Sekadar Backup:** Pemulihan bencana enterprise modern berakar pada *Automated High Availability*, konsensus terdistribusi, dan orkestrasi kontrol rute jaringan yang deterministik.
2. **Mitigasi Split-Brain adalah Harga Mati:** Mempromosikan node sekunder tanpa mekanisme isolasi (*Fencing*) terhadap node primer lama adalah penyebab nomor satu korupsi data katastropik dalam sistem terdistribusi. Selalu terapkan **Fencing Tokens** monotonik dan **Witness Quorum**.
3. **Penyelarasan RTO/RPO dengan Hukum Fisika:** Memilih RPO = 0 lintas region jarak jauh selalu menuntut kompromi latensi transaksi (*CAP/PACELC theorem*). Pahami batas toleransi bisnis sebelum memaksakan replikasi sinkron.
4. **Validasi Berkelanjutan via Chaos Engineering:** Arsitektur DR yang tidak pernah diuji pada *production environment* sesungguhnya adalah arsitektur yang pasti akan gagal saat bencana nyata terjadi. Otomatisasi pengujian melalui *Continuous DR Testing* dan *GameDays* adalah satu-satunya jaminan ketahanan sistem.