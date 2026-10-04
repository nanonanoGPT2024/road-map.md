## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** Forward-Deployed Engineer (FDE)
*   **Kategori:** 06-Architecture-and-System-Design
*   **Kode Modul:** FDE-ARCH-10-01
*   **Nama Modul:** Enterprise Capstone Project: Mission-Critical Deployment: Perancangan, Integrasi, Validasi, dan Go-Live Arsitektur Skala Besar di Lingkungan Klien Enterprise
*   **Tingkat Kesulitan:** Advanced / Capstone
*   **Prasyarat:** FDE-ARCH-01 hingga FDE-ARCH-09 (Distributed Systems, Enterprise Integration Patterns, Hybrid-Cloud Networking, Security & Compliance, Data Pipelines, High Availability, Disaster Recovery, Observability)
*   **Durasi Pembelajaran:** 40 Jam (Hands-on Lab, Capstone Execution, & Architecture Review)
*   **Target Persona:** Senior Forward-Deployed Engineer, Enterprise Solutions Architect, Infrastructure Specialist

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik mampu:

1.  **Merancang Blueprint Arsitektur Enterprise Mission-Critical:** Menyusun arsitektur sistem hybrid/air-gapped berstandar Tier-4 enterprise yang memenuhi RPO = 0 dan RTO < 60 detik.
2.  **Mengimplementasikan Pola Integrasi Non-Invasif:** Membangun *data extraction* dan *traffic interception layer* menggunakan Change Data Capture (CDC) dan Service Mesh Traffic Mirroring tanpa mengganggu sistem warisan (*legacy*).
3.  **Mengembangkan Sistem Rekonsiliasi Otomatis:** Mengimplementasikan mesin verifikasi konsistensi data *dual-write* real-time yang memvalidasi integritas transaksi finansial lintas basis data heterogen.
4.  **Menjalankan Prosedur Cutover Tanpa Downtime:** Mengorkestrasikan *zero-downtime migration cutover* menggunakan pola Strangler Fig dan Canary Routing berbasis Automated Health Checks dan Circuit Breaking.
5.  **Membuat Automated Runbook & Disaster Recovery Rollback:** Mengotomatisasi protokol mitigasi kegagalan Day-0/Day-1 menggunakan *infrastructure-as-code* dan *declarative rollback pipelines*.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                    [ENTERPRISE CLIENT ECOSYSTEM]
                                  │
          ┌───────────────────────┴───────────────────────┐
          ▼                                               ▼
[LEGACY INFRASTRUCTURE]                     [SECURITY & COMPLIANCE]
  - Core Monolith (COBOL/Java)                - PCI-DSS / SOC2 / ISO27001
  - RDBMS (Oracle/DB2)                        - Air-Gapped / Isolated VPCs
  - ESB / Proprietary Message Bus             - Strict mTLS & HSM Integration
          │                                               │
          └───────────────────────┬───────────────────────┘
                                  ▼
                     [FDE MISSION-CRITICAL PLATFORM]
                                  │
      ┌───────────────────────────┼───────────────────────────┐
      ▼                           ▼                           ▼
[PHASE 1: INGESTION]      [PHASE 2: SHADOWING]      [PHASE 3: CUTOVER]
  - Non-invasive CDC        - Traffic Mirroring       - Canary Weighted Route
  - Event Sourcing Bridge   - Synthetic Dry-Run       - Automated Verification
  - Kafka / Schema Reg      - Latency & Drift Check   - Instant Rollback Gate
                                  │
                                  ▼
                   [PHASE 4: STEADY STATE DAY-2]
                     - Observability (eBPF/OTel)
                     - Continuous Reconciliation
                     - Chaos & Resiliency Drills
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Di dunia korporasi skala enterprise (perbankan tier-1, telekomunikasi nasional, sistem logistik global, pertahanan), kegagalan deployment bukan sekadar isu *bug fixing*; implikasinya adalah kerugian jutaan dolar per menit, sanksi regulasi, hingga tuntutan hukum. 

Sebagai Forward-Deployed Engineer (FDE), Anda bertindak di garis depan: menanamkan platform modern vendor ke dalam lingkungan klien yang terfragmentasi, terlindungi firewall ekstrem, memiliki birokrasi ketat, dan bergantung pada sistem warisan yang rapuh (*fragile monoliths*).

Klien enterprise tidak menerima downtime terencana (*maintenance windows*) yang panjang. FDE harus mampu menjamin bahwa proses transisi berjalan mulus bagai "mengganti mesin jet komersial saat pesawat sedang terbang di ketinggian 30.000 kaki", memastikan integritas data 100%, performa yang terukur, dan jalur kembali (*rollback*) tanpa residu jika terjadi anomali.

---

## SEKSI 05 — APA ITU (WHAT)

Enterprise Capstone Project adalah simulasi dan eksekusi deployment platform end-to-end berisiko tinggi. Ruang lingkupnya mencakup:

1.  **Architecture Decision Records (ADRs):** Dokumentasi formal setiap kompromi teknis yang disetujui bersama Chief Architect klien.
2.  **Traffic Interception & Shadowing:** Menggandakan lalu lintas produksi riil (*dark traffic*) ke platform baru tanpa menambah latensi pada jalur utama (*golden path*).
3.  **Data Synchronization & Active Dual-Run:** Menjaga keselarasan data antara RDBMS klien dan arsitektur target modern menggunakan CDC dan rekonsiliasi deterministik.
4.  **Runbook-as-Code:** Prosedur eksekusi go-live yang terotomatisasi secara terprogram (scripted/declarative), bukan instruksi manual berbasis spreadsheet yang rentan *human error*.

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

Implementasi mission-critical deployment dibagi menjadi 4 tahap eksekusi:

### 1. Inception & Security Boundary Piercing
*   Menetapkan konektivitas aman melalui Reverse Proxies, PrivateLink, atau IPsec VPN.
*   Pemberian izin dan implementasi agen CDC berbasis log (misal: Debezium membaca redo log Oracle/PostgreSQL) tanpa memasang ekstensi invasif di database klien.

### 2. Dark Launching & Traffic Shadowing
*   Menggunakan Service Mesh (Istio/Envoy) pada ingress layer untuk menduplikasi request baca (*read traffic*) dan kirimkan secara asinkron ke sistem baru.
*   Mengukur respon: mengecek *differential response* (apakah output sistem baru identik dengan sistem legacy) dan profil latensi.

### 3. Dual-Write & Continuous Reconciliation
*   Sistem baru mulai menerima transaksi tulis melalui antrean terdistribusi.
*   Reconciliation Engine berjalan di latar belakang untuk melakukan audit *hash-based* pada setiap record di source dan target. Jika terjadi *drift* (selisih), event dikirimkan ke Dead Letter Queue (DLQ) untuk auto-remedy.

### 4. Zero-Downtime Phased Cutover
*   **T-0:** Dry run simulasi rollback.
*   **T+1:** Pengalihan 1% traffic produksi ke sistem baru via dynamic DNS / weighted route Envoy.
*   **T+2:** Evaluasi Service Level Indicators (SLI) otomatis: Error rate < 0.01%, p99 latency < 200ms.
*   **T+3:** Eskalasi bertahap: 5% -> 25% -> 50% -> 100%.
*   **T+4:** Sistem legacy dialihkan fungsinya menjadi target replikasi pasif (*reverse replication*) sebagai jaminan jika rollback mendadak dibutuhkan setelah 24 jam go-live.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

```
                                      CLIENT EDGE / INGRESS
                                                │
                                    [BGP Anycast / L4 LB]
                                                │
                     ┌──────────────────────────┴──────────────────────────┐
                     ▼                                                     ▼
           [Legacy Gateway / F5]                                 [Modern Gateway / Envoy]
                     │                                                     │
         ┌───────────┴───────────┐                         ┌───────────────┴───────────────┐
         │ (Production Traffic)  │                         │                               │
         ▼                       ▼                         ▼ (1% to 100% Traffic)          ▼ (Shadow Copy)
   [Legacy Core Monolith]  [Traffic Mirror] ────────> [Modern Platform API]        [Differential Evaluator]
         │                       │                         │                               ▲
         │ (Transactions)        │ (Async Fire-and-Forget) │ (New Schema Writes)           │ (Compare Responses)
         ▼                       │                         ▼                               │
  [(Legacy RDBMS)]               │                   [(Distributed DB)]                    │
         │                       │                         │                               │
         │ (Transaction Logs)    │                         │                               │
         ▼                       │                         │                               │
   [Debezium CDC Engine]         │                         │                               │
         │                       │                         │                               │
         ▼ (Kafka Event Stream)  │                         │                               │
   [Streaming Ingestion Pipeline]│                         │                               │
         │                       │                         │                               │
         └───────────────────────┼─────────────────────────┤                               │
                                 ▼                         ▼                               │
                     [Continuous Reconciliation Engine] ───────────────────────────────────┘
                                 │
                     (Identifies & Heals Drift)
                                 │
                                 ▼
                     [Observability & SRE Alerting]
                     - Prometheus / Grafana
                     - OpenTelemetry Collector
                     - PagerDuty P1 Trigger
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah skrip Python murni sederhana untuk mensimulasikan mekanisme *Differential Traffic Shadowing Validator*. Skrip ini bertindak sebagai proxy perantara yang mengirimkan request ke Legacy Service dan menduplikasi (*shadowing*) request ke Modern Service, lalu membandingkan kesesuaian respon secara asinkron tanpa memblokir klien.

```python
import asyncio
import hashlib
import json
import time

async def call_legacy_system(payload: dict) -> dict:
    """Simulasi pemanggilan sistem monolitik warisan."""
    await asyncio.sleep(0.05)  # Simulasi latensi 50ms
    # Respon legacy
    return {
        "status": "SUCCESS",
        "account_id": payload["account_id"],
        "balance": payload["amount"] + 100.0,
        "engine": "v1-monolith"
    }

async def call_modern_system(payload: dict) -> dict:
    """Simulasi pemanggilan sistem cloud-native modern."""
    await asyncio.sleep(0.02)  # Simulasi latensi 20ms (lebih cepat)
    # Respon modern
    return {
        "status": "SUCCESS",
        "account_id": payload["account_id"],
        "balance": payload["amount"] + 100.0,
        "engine": "v2-distributed"
    }

def calculate_checksum(data: dict) -> str:
    """Normalisasi dan hitung checksum data bisnis krusial."""
    normalized = {
        "status": data.get("status"),
        "account_id": data.get("account_id"),
        "balance": round(float(data.get("balance", 0)), 2)
    }
    encoded = json.dumps(normalized, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

async def evaluate_shadow_traffic(payload: dict):
    """Mengeksekusi shadow validation secara asinkron."""
    try:
        modern_response = await call_modern_system(payload)
        
        # Validasi checksum
        legacy_ref = payload.get("__legacy_ref_checksum")
        modern_checksum = calculate_checksum(modern_response)
        
        if legacy_ref != modern_checksum:
            print(f"[ALERT-DRIFT] Ketidakcocokan Data! Payload: {payload['account_id']} | Legacy: {legacy_ref} vs Modern: {modern_checksum}")
        else:
            print(f"[VALID] SINKRON: Account {payload['account_id']} konsisten 100%.")
    except Exception as e:
        print(f"[SHADOW-ERROR] Gangguan pada target modern: {str(e)}")

async def proxy_gateway_entrypoint(payload: dict):
    """Pintu masuk traffic: Mengembalikan hasil Legacy langsung ke user."""
    # 1. Eksekusi Legacy (Golden Path)
    legacy_response = await call_legacy_system(payload)
    
    # 2. Hitung Checksum Legacy untuk komparasi
    legacy_checksum = calculate_checksum(legacy_response)
    
    # 3. Inject checksum ke shadow payload
    shadow_payload = payload.copy()
    shadow_payload["__legacy_ref_checksum"] = legacy_checksum
    
    # 4. Lepaskan shadow task ke background (Fire and Forget)
    asyncio.create_task(evaluate_shadow_traffic(shadow_payload))
    
    # 5. Kembalikan legacy response langsung ke klien enterprise
    return legacy_response

async def main():
    print("Memulai Injeksi Traffic Proxy Shadowing...")
    sample_requests = [
        {"account_id": f"ACC-00{i}", "amount": float(i * 50)} 
        for i in range(1, 4)
    ]
    for req in sample_requests:
        resp = await proxy_gateway_entrypoint(req)
        print(f"[CLIENT-RESP] Diterima dari Legacy: {resp['account_id']} -> Balance: {resp['balance']}")
    
    # Beri jeda agar background tasks selesai
    await asyncio.sleep(0.5)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Dalam skenario capstone riil, sistem rekonsiliasi data dan cutover controller harus dibangun dengan standar ketat. Di bawah ini disajikan implementasi **Reconciliation Engine & Circuit Breaker** berkinerja tinggi menggunakan **Go**. 

Engine ini bertugas memindai basis data legacy dan target secara berkelanjutan, menghitung hash dari partisi data, mengidentifikasi anomali transaksi (*data drift*), dan mengekspos metrik untuk mengendalikan proses cutover otomatis.

```go
package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"log"
	"sync"
	"sync/atomic"
	"time"
)

// TransactionRecord merepresentasikan data transaksi finansial inti.
type TransactionRecord struct {
	ID        string
	AccountID string
	Amount    float64
	Currency  string
	Status    string
	Timestamp int64
}

// ComputeHash menghitung hash deterministik dari data transaksi.
func (t *TransactionRecord) ComputeHash() string {
	payload := fmt.Sprintf("%s:%s:%.4f:%s:%s", t.ID, t.AccountID, t.Amount, t.Currency, t.Status)
	h := sha256.New()
	h.Write([]byte(payload))
	return hex.EncodeToString(h.Sum(nil))
}

// MockDatastore merepresentasikan abstraksi layer data klien dan platform modern.
type MockDatastore struct {
	name  string
	store map[string]TransactionRecord
	mu    sync.RWMutex
}

func (m *MockDatastore) Get(id string) (TransactionRecord, bool) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	rec, exists := m.store[id]
	return rec, exists
}

// CutoverState Controller
type CutoverController struct {
	driftCount        int64
	reconciledRecords int64
	circuitOpen       int32 // 0: Closed (Healthy), 1: Open (Drift Threshold Breached)
}

func (c *CutoverController) RecordDrift() {
	atomic.AddInt64(&c.driftCount, 1)
	if atomic.LoadInt64(&c.driftCount) > 2 { // Ambang batas maksimal toleransi error drift: 2
		atomic.StoreInt32(&c.circuitOpen, 1)
		log.Println("[CRITICAL] DRIFT THRESHOLD BREACHED! Auto-aborting cutover sequence...")
	}
}

func (c *CutoverController) IsSafeForCutover() bool {
	return atomic.LoadInt32(&c.circuitOpen) == 0
}

// ReconcilerEngine memvalidasi integritas data lintas platform heterogen
type ReconcilerEngine struct {
	legacyDS   *MockDatastore
	modernDS   *MockDatastore
	controller *CutoverController
}

func (r *ReconcilerEngine) VerifyStream(ctx context.Context, keys []string) {
	var wg sync.WaitGroup

	for _, key := range keys {
		wg.Add(1)
		go func(k string) {
			defer wg.Done()

			legRec, legOk := r.legacyDS.Get(k)
			modRec, modOk := r.modernDS.Get(k)

			if !legOk || !modOk {
				log.Printf("[RECON-DRIFT] Missing record across clusters for key: %s (Legacy: %v, Modern: %v)\n", k, legOk, modOk)
				r.controller.RecordDrift()
				return
			}

			legHash := legRec.ComputeHash()
			modHash := modRec.ComputeHash()

			if legHash != modHash {
				log.Printf("[RECON-MISMATCH] Data inconsistency on key %s! LegacyHash: %s | ModernHash: %s\n", k, legHash, modHash)
				r.controller.RecordDrift()
			} else {
				atomic.AddInt64(&r.controller.reconciledRecords, 1)
			}
		}(key)
	}

	wg.Wait()
}

func main() {
	log.Println("=== INITIALIZING MISSION-CRITICAL RECONCILIATION ENGINE ===")

	// Inisialisasi Database Legacy
	legacyDB := &MockDatastore{
		name: "Legacy-DB2",
		store: map[string]TransactionRecord{
			"TX-1001": {"TX-1001", "ACC-A", 1500.50, "USD", "SETTLED", 1700000000},
			"TX-1002": {"TX-1002", "ACC-B", 250.00, "USD", "SETTLED", 1700000001},
			"TX-1003": {"TX-1003", "ACC-C", 9999.99, "EUR", "PENDING", 1700000002},
			"TX-1004": {"TX-1004", "ACC-D", 12.00, "USD", "SETTLED", 1700000003}, // Sengaja disimulasikan drift
		},
	}

	// Inisialisasi Database Modern (CDC target)
	modernDB := &MockDatastore{
		name: "Modern-Distributed-ScyllaDB",
		store: map[string]TransactionRecord{
			"TX-1001": {"TX-1001", "ACC-A", 1500.50, "USD", "SETTLED", 1700000000},
			"TX-1002": {"TX-1002", "ACC-B", 250.00, "USD", "SETTLED", 1700000001},
			"TX-1003": {"TX-1003", "ACC-C", 9999.99, "EUR", "PENDING", 1700000002},
			"TX-1004": {"TX-1004", "ACC-D", 12.00, "USD", "FAILED", 1700000003}, // Status tidak sinkron!
		},
	}

	controller := &CutoverController{}
	engine := &ReconcilerEngine{
		legacyDS:   legacyDB,
		modernDS:   modernDB,
		controller: controller,
	}

	keysToCheck := []string{"TX-1001", "TX-1002", "TX-1003", "TX-1004"}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	log.Println("[GO-LIVE GATE] Memulai verifikasi integritas data transaksi...")
	engine.VerifyStream(ctx, keysToCheck)

	log.Printf("[AUDIT SUMMARY] Total Terverifikasi: %d | Total Drift: %d\n", 
		controller.reconciledRecords, controller.driftCount)

	if !controller.IsSafeForCutover() {
		log.Fatalf("[FATAL] Cutover GATE DITOLAK: Integritas sistem belum terjamin. Membatalkan perpindahan traffic!")
	} else {
		log.Println("[SUCCESS] Cutover GATE DITERIMA: Tingkat drift 0%. Siap melanjutkan migrasi traffic 100%.")
	}
}
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi Arsitektur | Opsi A: Dual-Write Application Layer | Opsi B: Change Data Capture (CDC Log-based) | Kompromi Teknis |
| :--- | :--- | :--- | :--- |
| **Konsistensi Data** | Memerlukan *Distributed Transaction (2PC/SAGA)*; risiko *split-brain* tinggi saat jaringan partisi. | *Eventually consistent*; log reader menjamin *strict ordering* tanpa membebani runtime monolitik klien. | Opsi B mengeliminasi latensi aplikasi tetapi membebankan dependensi pada storage engine logging (CDC). |
| **Invasivitas Kode** | Sangat invasif; merombak codebase legacy monolitik yang minim unit test. | Non-invasif; hanya butuh replikasi hak baca ke transaksi log level DB. | Opsi B lebih disukai di ranah enterprise untuk meminimalisasi risiko audit software vendor. |
| **Metode Cutover** | **Big-Bang Deployment** (Semua dialihkan sekaligus via DNS flip). | **Phased Strangler Fig** (Pemisahan domain bertahap via path-routing). | Big-Bang memiliki RTO tinggi jika gagal; Phased membutuhkan sinkronisasi dua arah yang rumit (*bi-directional sync*). |
| **Shadowing vs In-line** | **In-line Validation** (Menunggu respon modern sebelum return ke klien). | **Asynchronous Traffic Shadowing** (Fire-and-forget; copy traffic di level Envoy). | In-line mengorbankan performa pengguna; Async tidak mendeteksi bug write-side secara instan pada transaksi stateful. |

---

## SEKSI 11 — BEST PRACTICES

1.  **Immutability dan Idempotensi:** Pastikan seluruh API platform modern memiliki idempotency-key handling untuk mencegah duplikasi saldo/data akibat replikasi event yang terulang (*at-least-once delivery*).
2.  **Air-Gapped Deployment Bundles:** Selalu sediakan *bastion container registry mirror* dan *offline helm chart packages* yang telah ditandatangani secara kriptografis (Cosign) sebelum masuk ke on-premise klien.
3.  **Reverse CDC Loop (Backout Enabler):** Saat traffic cutover beralih 100% ke sistem modern, CDC harus dibalik arahnya: menulis kembali setiap mutasi baru dari sistem modern ke database legacy. Tujuannya adalah membuka opsi rollback instan di Day-3 tanpa kehilangan data transaksi terbaru.
4.  **Circuit Breaker pada Metrik Drift:** Jadikan rasio drift data sebagai metrik pemicu *Automated Rollback* pada pipeline Argo Rollouts atau Spinnaker. Jika drift > 0.001%, segera kembalikan traffic routing ke 0% secara otomatis.
5.  **Observability Sanitization:** Sensor eBPF dan OpenTelemetry Collector di lingkungan klien enterprise wajib mengaburkan data PII (*Personally Identifiable Information*) pada layer ingress sebelum disimpan ke log storage.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

*   **Asymmetric Network Routing:** Mengabaikan *stateful firewall* klien enterprise. Traffic request masuk lewat jalur Modern Gateway, namun balasan routing diarahkan langsung ke gateway lama, menyebabkan koneksi di-drop (*TCP RST*) oleh firewall.
*   **Ketergantungan Eksternal di Lingkungan Terisolasi (Air-Gap):** Lupa menyertakan schema validasi internal atau public key, menyebabkan pod crashloopbackoff karena cluster menolak menjalankan image tanpa verifikasi public cert authority eksternal.
*   **Mengabaikan Monolith Database Triggers:** Mengasumsikan replikasi data hanya melibatkan tabel target, melupakan bahwa database warisan memiliki *stored procedure* dan *triggers* tersembunyi yang melakukan auto-update ke puluhan tabel lain.
*   **Menggunakan DNS TTL Rendah Sebagai Satu-satunya Mekanisme Failover:** ISP korporat dan resolver internal klien kerap mengabaikan nilai TTL DNS (cache DNS terkunci hingga 24 jam). Cutover harus dikendalikan di level L4/L7 load balancer atau BGP, bukan bergantung pada propagasi DNS publik.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Skenario Lab
Anda ditugaskan mengeksekusi cutover sistem autentikasi dan transfer dana dari Core Monolith Banking ke Modern Platform.

### Tugas 1: Konfigurasi Envoy Shadow Routing
Tulis konfigurasi `EnvoyFilter` atau Envoy YAML VirtualService untuk menduplikasi seluruh traffic path `/api/v1/transfer` ke upstream cluster `modern-platform-svc` dengan persentase 100% shadowing tanpa menunggu responnya.

### Tugas 2: Membangun Drift Detection Pipeline
Jalankan skrip Go pada Seksi 09 di atas. Modifikasi kodenya agar mampu menerima file JSON berisi 10.000 log transaksi per detik dan mendeteksi anomali desimal pada floating-point currency. Ganti `float64` menjadi representasi *arbitrary-precision fixed-point* (misal: package `shopspring/decimal`) untuk mengeliminasi rounding error sistem.

### Tugas 3: Simulasi Automated Rollback
Simulasikan skenario kegagalan: Suntikkan 5% error HTTP 500 ke service modern. Tulis skrip shell yang memonitor endpoint `/metrics` Prometheus, lalu picu patch L7 Gateway via `curl` untuk mengembalikan upstream routing ke Legacy secara otomatis dalam waktu kurang dari 3 detik.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Mengapa *log-based CDC* lebih disukai daripada *trigger-based CDC* pada database enterprise yang menangani >10.000 TPS?**
   * A. Log-based CDC lebih mudah dikonfigurasi melalui query SQL standar.
   * B. Trigger-based CDC mengeksekusi overhead write lock tambahan pada transaksi produksi di thread yang sama, menurunkan throughput database legacy.
   * C. Log-based CDC tidak membutuhkan hak akses administratif di level instance database.
   * D. Trigger-based CDC tidak mendukung penangkapan skema tipe data JSON.
   * *Jawaban:* **B**. Trigger berjalan dalam konteks transaksi ACID utama. Pada traffic tinggi, overhead ini dapat memicu lock contention dan kehabisan connection pool database klien.

2. **Apa fungsi utama dari *Differential Response Evaluator* pada implementasi Dark Launching?**
   * A. Mengurangi latensi pemrosesan query modern.
   * B. Melakukan komparasi semantik dan integritas output antara implementasi legacy dan engine baru secara real-time tanpa berdampak pada end-user.
   * C. Mengompresi payload request yang masuk dari perimeter gateway.
   * D. Mengamankan enkripsi end-to-end melintasi batas mTLS.
   * *Jawaban:* **B**. Tujuannya adalah memastikan sistem baru memproduksi hasil yang identik secara fungsional sebelum traffic riil dialihkan.

3. **Kapan teknik *Reverse CDC Replication* harus diaktifkan selama proses migrasi core banking?**
   * A. Jauh sebelum tahapan dark launching dimulai.
   * B. Segera setelah cutover 100% traffic ke sistem baru berhasil dilakukan, agar sistem legacy tetap terisi mutasi terbaru jika sewaktu-waktu harus rollback.
   * C. Hanya saat sistem baru mengalami crash parah pada Day-0.
   * D. Saat database target dimatikan untuk proses audit regulasi.
   * *Jawaban:* **B**. Reverse CDC adalah jaring pengaman agar rollback di masa depan tidak mengakibatkan *data loss* atas transaksi yang telah terjadi di sistem baru.

4. **Metrik mana yang paling kritikal untuk dijadikan indikator *Automated Abort / Rollback* saat proses Canary Deployment?**
   * A. Peningkatan utilisasi memori cache node.
   * B. HTTP 5xx error budget burn rate dan peningkatan rasio Data Drift pada reconciler engine.
   * C. Jumlah log debug yang dihasilkan oleh application pod.
   * D. Waktu siklus continuous delivery pipeline.
   * *Jawaban:* **B**. Error budget burn rate dan integritas data langsung mengindikasikan degradasi fungsional dan korupsi data yang fatal.

5. **Di lingkungan *air-gapped enterprise*, mengapa pendekatan deployment berbasis `latest` tag container image merupakan pelanggaran kepatuhan operasional berat?**
   * A. Image dengan tag `latest` memakan memori swap lebih banyak.
   * B. Tag `latest` tidak deterministik, tidak dapat dilacak secara audit trail keamanan, dan melanggar prinsip imutabilitas software bill of materials (SBOM).
   * C. Tag `latest` secara otomatis mencoba mendownload patch dari public internet registry.
   * D. Tag `latest` tidak kompatibel dengan semua jenis container runtime modern (CRI-O/Containerd).
   * *Jawaban:* **B**. Setiap artifak di lingkungan enterprise harus dapat dilacak secara pasti melalui sha256 digest dan versioning semantik yang jelas untuk validasi keamanan dan audit.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

*   **Buku:**
    *   *Designing Data-Intensive Applications* oleh Martin Kleppmann (O'Reilly Media) - Khusus Bab Replikasi dan Konsistensi Terdistribusi.
    *   *Enterprise Integration Patterns* oleh Gregor Hohpe & Bobby Woolf.
    *   *Site Reliability Engineering: How Google Runs Production Systems* (O'Reilly Media).
*   **Whitepapers & Standards:**
    *   AWS Architecture Center: *Phased Migration: The Strangler Fig Pattern in Enterprise Modernization*.
    *   The Open Group: *TOGAF Standard Version 10 - Enterprise Deployment Models*.
    *   PCI Security Standards Council: *Cloud Computing Guidelines & Data Integrity Auditing*.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

Modul Capstone ini merangkum seluruh spektrum kapabilitas yang wajib dimiliki oleh seorang Senior Forward-Deployed Engineer:

1.  **Arsitektur Non-Invasif:** Memaksimalkan observasi dan replikasi data via CDC dan Proxy Mesh tanpa memodifikasi sistem legacy yang berisiko tinggi.
2.  **Mitigasi Risiko Data:** Menetapkan bahwa konsistensi data absolut adalah tolok ukur utama keberhasilan deployment. Penggunaan *hash verification* dan *reconciliation engines* mencegah kegagalan bisnis tersembunyi.
3.  **Transisi Dinamis:** Menggunakan pola Strangler Fig dan Canary Release yang dikendalikan oleh *circuit breakers* otomatis, mengeliminasi kebutuhan proses go-live manual yang rentan kesalahan manusia.
4.  **Kesiapsiagaan Rollback:** Mengharuskan FDE menyiapkan strategi mundur (*escape hatch*) sekuat strategi maju, termasuk mengimplementasikan *reverse replication* sesaat setelah cutover berhasil.

---

## SEKSI 17 — GLOSARIUM

*   **Air-Gapped Environment:** Lingkungan komputasi terisolasi secara fisik dan logis yang sama sekali tidak memiliki koneksi langsung ke jaringan internet publik.
*   **Change Data Capture (CDC):** Pola integrasi yang mendeteksi dan menangkap setiap mutasi data (INSERT, UPDATE, DELETE) pada level binary/redo log database untuk dialirkan sebagai event stream.
*   **Strangler Fig Pattern:** Strategi modernisasi sistem warisan secara bertahap dengan mengganti fungsionalitas monolith lapis demi lapis hingga sistem lama mati secara alami.
*   **Traffic Shadowing (Dark Traffic):** Menduplikasi traffic produksi riil ke sistem staging/modern baru tanpa membiarkan respon sistem baru tersebut memengaruhi klien atau data produksi.
*   **Data Drift:** Perbedaan atau ketidaksinkronan status representasi nilai data antara dua basis data yang berbeda dalam periode waktu tertentu.
*   **RPO (Recovery Point Objective):** Batas toleransi maksimal kehilangan data yang dapat diterima organisasi saat terjadi insiden (diukur dalam durasi waktu).
*   **RTO (Recovery Time Objective):** Durasi waktu maksimal yang dibutuhkan untuk memulihkan sistem kembali beroperasi normal setelah terjadi gangguan fatal.
*   **Idempotency:** Properti dari operasi/API di mana eksekusi berulang kali dengan parameter yang sama menghasilkan efek sistem yang persis sama tanpa duplikasi status.
*   **mTLS (Mutual TLS):** Metode autentikasi kriptografis dua arah di mana client dan server saling memverifikasi sertifikat digital masing-masing.
*   **Circuit Breaker:** Mekanisme pertahanan sistem terdistribusi yang otomatis menghentikan aliran trafik ke sistem downstream yang sedang mengalami anomali performa/error.

---

## SEKSI 18 — CATATAN INSTRUKTUR

*   **Fokus Evaluasi Proyek Capstone:** Jangan hanya menilai keberhasilan saat deployment berjalan mulus. Berikan ujian terberat pada skenario: *Apa yang terjadi jika jaringan partisi muncul saat cutover di posisi 50%? Seberapa cepat pipeline mahasiswa mengeksekusi self-healing atau auto-rollback?*
*   **Tip Fasilitasi:** Minta peserta memainkan peran ganda: Peserta A sebagai FDE yang melakukan deployment platform modern, Peserta B sebagai "Enterprise Security & Infrastructure Auditor" dari pihak klien yang bersikap skeptis, menolak akses root, dan memutus konektivitas sewaktu-waktu.
*   **Laboratorium:** Pastikan resource klaster Kubernetes lab disetup dengan network policy ketat yang memblokir egress internet secara default untuk mereplikasi realitas on-premise klien enterprise.

---

## SEKSI 19 — CHANGELOG & VERSI

*   **Versi:** 1.0.0
*   **Tanggal Terbit:** 2026-03-30
*   **Catatan Rilis:**
    *   Rilis kurikulum inisial Capstone Project FDE Track Architecture & System Design.
    *   Penambahan spesifikasi detil reconciler engine (Go), proxy shadowing architecture, dan standar kepatuhan enterprise mission-critical.

---

## SEKSI 20 — NAVIGASI KURIKULUM

*   **Modul Sebelumnya:** `06-Architecture-and-System-Design/Bab 09 - Observability, SRE, and Distributed Tracing in Client Ecosystems`
*   **Modul Berikutnya:** `07-Field-Operations-and-Crisis-Management/Bab 01 - Field Operations: Day-2 Support, Escalations, and Incident Command for FDEs`