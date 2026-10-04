# Kurikulum Rekayasa Perangkat Lunak Enterprise
## Kategori: 07-Quality-and-Security
### BAB 01: Fondasi dan Arsitektur Kualitas Perangkat Lunak
#### Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Mendesain dan Mengimplementasikan Arsitektur Hermetic Testing**: Membangun lingkungan pengujian deterministik dan terisolasi secara penuh menggunakan *ephemeral test environments* via Testcontainers tanpa ketergantungan pada dependensi eksternal statis (*shared resources*).
2. **Mengeksekusi Consumer-Driven Contract Testing (CDCT)**: Mengimplementasikan verifikasi kontrak antar-layanan terdistribusi secara asinkron dan sinkron untuk mencegah regresi *breaking changes* pada API mikroservis menggunakan framework Pact.
3. **Menganalisis Efektivitas Pengujian Menggunakan Mutation Testing**: Mengukur ketahanan rangkaian uji (*test suite resilience*) pada level *bytecode/AST manipulation* untuk mengidentifikasi *false positives* pada cakupan kode (*code coverage metrics*).
4. **Membangun Flaky Test Detection & Quarantine Engine**: Mengintegrasikan sistem mitigasi ketidakstabilan pengujian berbasis algoritma probabilitas statistik dan *quarantine circuit breaker* pada pipeline CI/CD skala enterprise.
5. **Mengorkestrasi Shift-Right & Synthetic Monitoring Pipeline**: Menyusun arsitektur pengujian pasca-rilis berbasis telemetri eBPF, OpenTelemetry, dan *synthetic probes* di klaster Kubernetes produksi.

---

### 2. Prerequisite
Peserta wajib memiliki pemahaman mendalam dan pengalaman praktis terhadap:
* **Arsitektur Sistem Terdistribusi**: Komunikasi REST, gRPC, Event-Driven Architecture (Kafka/RabbitMQ), dan State Machine mikroservis.
* **Teknologi Kontainerisasi & Orkesgtrasi**: Docker Engine internals (cgroups, namespaces, Docker socket runtime `/var/run/docker.sock`), serta arsitektur dasar Pod/Deployment Kubernetes.
* **Bahasa Pemrograman**: Kemahiran tingkat menengah-lanjut dalam **Go (Golang)** atau **TypeScript/Node.js** (pointer, konkurensi/channel/goroutines, async/await, reflection/AST dasar).
* **Automasi CI/CD**: Pengalaman mengonfigurasi pipeline deklaratif (GitHub Actions, GitLab CI, atau Argo Workflows).

---

### 3. Concept & Internal Architecture

Arsitektur penjaminan kualitas enterprise modern melampaui pendekatan klasik "Piramida Pengujian Statis". Pada sistem terdistribusi skala besar, ekosistem QA bertransformasi menjadi **Continuous Verification and Test Infrastructure as Code (TIaC)**.

```
+-------------------------------------------------------------------------+
|                  Enterprise Test Harness Architecture                   |
+-------------------------------------------------------------------------+
| [Shift-Left] Unit & Hermetic Integration Tests                          |
|   +-----------------------+     +-------------------------------------+ |
|   | Domain Logic / Ast Gen|     | Testcontainers Execution Daemon     | |
|   | Unit Test Engine      | <-> | (PostgreSQL, Kafka, Redis Ephemeral)| |
|   +-----------------------+     +-------------------------------------+ |
+-------------------------------------------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
| [Pre-Deploy] Boundary & Contract Verification Engine                    |
|   +-------------------------------------------------------------------+ |
|   | Pact Broker (Matrix Compatibility & Semantic Versioning Gate)      | |
|   +-------------------------------------------------------------------+ |
|   | Mutation Testing Runner (Stryker/Pitest Bytecode Mutant Injector) | |
|   +-------------------------------------------------------------------+ |
+-------------------------------------------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
| [CI/CD Orchestration] Execution Plane & Quarantine Gate                 |
|   +-------------------------------------------------------------------+ |
|   | Parallel Sharding Engine -> Quarantine Circuit Breaker (Bayesian) | |
|   +-------------------------------------------------------------------+ |
+-------------------------------------------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
| [Shift-Right] Synthetic Probing & Observability Verification            |
|   +-------------------------+     +-----------------------------------+ |
|   | Canary Traffic Splitter | --> | OpenTelemetry Trace Analyzer      | |
|   +-------------------------+     +-----------------------------------+ |
+-------------------------------------------------------------------------+
```

#### A. Hermetic Integration Engine (Testcontainers Architecture)
Pendekatan integrasi lama mengandalkan database bersama (*shared staging database*), yang memicu kondisi balapan data (*data race condition*) dan kegagalan uji non-deterministik. Arsitektur Hermetik mengisolasi *runtime* sepenuhnya:
* **Moby API Interaction**: Pengujian menginisiasi panggilan melalui socket Docker lokal untuk membuat kontainer *throwaway* khusus bagi thread/proses pengujian tersebut.
* **Reaper Pattern (Ryuk)**: Testcontainers menyuntikkan kontainer pengawas (*Ryuk*) via label khusus (`org.testcontainers=true`). Jika runner CI/CD mengalami terminasi paksa (OOMKilled atau SIGKILL), Ryuk membersihkan seluruh alokasi kontainer, volume, dan *bridge network* yang terikat, mengeliminasi masalah *resource leakage*.

#### B. Consumer-Driven Contract Testing (CDCT) Internals
Alih-alih melakukan pengujian *end-to-end* (E2E) terpusat yang lambat dan rapuh (*brittle*), CDCT membalik model verifikasi:
1. **Consumer** mengekspresikan ekspektasi payload JSON/Protobuf dan *status code* dalam bentuk berkas kontrak deklaratif (*Pact File*).
2. Kontrak diunggah ke **Pact Broker** bersama dengan nomor commit Git dan hash branch.
3. Pipeline **Provider** mengunduh kontrak, memutar server lokal sementara, memutar ulang (*replay*) interaksi consumer, dan memvalidasi respons aktual terhadap skema ekspektasi.
4. **`can-i-deploy` CLI Gate**: Memvalidasi matriks dependensi secara real-time sebelum artefak dirilis ke lingkungan produksi target.

#### C. Mutation Testing Engine Internals
Metrik *Code Coverage* tradisional (Line/Branch Coverage) sering kali menyembunyikan kerapuhan logika assertions. Mutation testing bekerja pada level **Abstract Syntax Tree (AST)** atau **Bytecode Injection**:
* **Mutant Operators**: Mengubah operator logika (`&&` menjadi `||`), memodifikasi pembanding numerik (`<` menjadi `<=`), atau meniadakan pemanggilan fungsi (`void` call stripping).
* **Killed vs Escaped Mutants**: Jika rangkaian uji gagal saat mutasi disuntikkan, mutant dikategorikan **Killed** (Valid). Jika seluruh tes tetap lolos (*Pass*) meskipun kode telah disabotase, mutant dinyatakan **Escaped/Survived** (Defek Assertion).
* **Mutation Score Formula**:
  $$\text{Mutation Score} = \left( \frac{\text{Killed Mutants}}{\text{Total Mutants}} \right) \times 100\%$$

---

### 4. Why & What

| Dimensi | Pendekatan QA Konvensional (Legacy) | Pendekatan Modern Enterprise Quality Engineering |
| :--- | :--- | :--- |
| **Integrasi Database** | Shared Staging DB, data statis, dibersihkan berkala via cron job. | Ephemeral Container per suite/test runner, isolasi memori absolut. |
| **Verifikasi Mikroservis** | E2E staging environment, bergantung pada puluhan upstream services aktif. | Consumer-Driven Contract Testing (Pact), hermetic mock stubs. |
| **Validasi Kualitas Tes** | Target 80% Line Coverage (rentan terhadap *assertion-free tests*). | Mutation Coverage Score (>75% killed mutants), Boundary Analysis. |
| **Mitigasi Flaky Test** | Retries acak (misal: 3x rerun), mengabaikan log error acak. | Dynamic Quarantine Matrix, isolasi otomatis berbasis Bayesian Score. |
| **Deteksi Defek Produksi**| Menunggu tiket insiden/bug report dari pengguna/ops. | Synthetic In-Production Probes, tracing assertion via OpenTelemetry. |

---

### 5. How (Workflow Detail)

Siklus hidup validasi kualitas modern berjalan melalui pipeline terotomatisasi ketat:

```
[Developer Machine / PR]
       |
       v
(1) Static Analysis & Security SAST (golangci-lint / SonarQube)
       |
       v
(2) Hermetic Unit & Integration Tests (Testcontainers + Ephemeral DB)
       |
       v
(3) Mutation Testing Analysis (Injeksi AST mutasi pada modul kritis)
       |
       v
(4) Consumer Contract Generation -> Publikasi ke Pact Broker
       |
[CI Pipeline Server]
       |
       v
(5) Provider Contract Verification (Pact Broker `can-i-deploy` check)
       |
       v
(6) Flaky Test Quarantine Filter (Pemisahan eksekusi deterministik vs flakiness)
       |
[Deployment to Staging / Canary]
       |
       v
(7) Shift-Right Automated Synthetic Probing & Telemetry Trace Verification
```

1. **Local Pre-Commit/PR Gate**: Kode dianalisis secara statis (AST parsing). Pengujian lokal mengeksekusi integrasi hermetik menggunakan Testcontainers.
2. **Contract Generation & Matrix Verification**: Layanan konsumen memublikasikan kontrak baru ke Pact Broker. Pipeline CI memanggil API `can-i-deploy` untuk mengecek kompatibilitas lintas-versi.
3. **Bytecode/AST Mutation Phase**: Engine mutasi menyuntikkan kesalahan sengaja ke dalam *hot-path business logic*. Jika skor mutasi jatuh di bawah batas SLA (misal: 70%), PR otomatis diblokir (*merge denied*).
4. **Dynamic CI Sharding & Quarantine Gate**: Runner memecah tes ke dalam node paralel. Hasil tes yang gagal diproses oleh algoritma flakiness; jika teridentifikasi sebagai *non-deterministic state*, tes dipindahkan ke bucket *Quarantine* tanpa menghentikan jalur kritis (*critical path*), namun menerbitkan *technical debt ticket*.
5. **Synthetic Observability Probe**: Pasca-canary deployment, probe mengeksekusi skenario transaksi sintetis nyata, sementara engine verifikasi menarik metrik *p99 latency* dan *error trace* langsung dari backend OpenTelemetry.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Inspeksi Otomotif Modern
* **Legacy QA**: Merakit mobil secara keseluruhan, membawanya ke sirkuit luar ruangan umum. Jika mobil mogok, sulit mendeteksi apakah penyebabnya adalah busi cacat, bensin berkualitas buruk di sirkuit, atau jalanan licin (E2E testing di shared staging).
* **Modern Quality Engineering**:
  * **Hermetic Testing**: Busi dan mesin diuji pada simulator ruang kedap udara dengan variabel kontrol mutlak (suhu, kompresi udara murni buatan) yang langsung dimusnahkan setelah pengujian selesai.
  * **Contract Testing**: Pabrik baut dan pabrik mur menguji dimensi cetakan mereka secara matematis menggunakan cetak biru (*blueprint*) presisi milimeter tanpa perlu menunggu perakitan sasis mobil.
  * **Mutation Testing**: Menyabotase mesin sengaja (misal: memutus satu kabel sensor) untuk memastikan panel instrumen dasbor benar-benar menyalakan lampu peringatan, bukan hanya speedometer yang berfungsi normal.

```
+--------------------------------------------------------------------------------+
|                Test Execution Topology (Ephemeral vs Shared)                   |
+--------------------------------------------------------------------------------+

[PENDEKATAN LEGACY: SHARED RESOURCE BOTTLENECK]
  Test Suite Alpha --\
  Test Suite Beta  ---> [ Shared Remote Database ] <--- Race Condition, State Bleed
  Test Suite Gamma --/

[PENDEKATAN MODERN: HERMETIC CONTAINER ENGINE]
  +----------------------------------------------------------------------------+
  | Test Runner Process (Node/Pod 1)                                           |
  |  +--------------------+                                                    |
  |  | Unit / Integration |                                                    |
  |  | Test Engine        |                                                    |
  |  +--------+-----------+                                                    |
  |           | (Moby Unix Socket: /var/run/docker.sock)                       |
  |           v                                                                |
  |  +---------------------------------------+  +----------------------------+ |
  |  | Container: Postgres (Port: Ephemeral) |  | Container: Ryuk (Reaper)   | |
  |  +---------------------------------------+  +----------------------------+ |
  +----------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Contoh Sederhana: Basic Testcontainer Implementation (Go)
Menjalankan pengujian repositori data langsung di atas *ephemeral Redis container*.

```go
package integration_test

import (
	"context"
	"fmt"
	"testing"

	"github.com/redis/go-redis/v9"
	"github.com/testcontainers/testcontainers-go"
	"github.com/testcontainers/testcontainers-go/wait"
)

func TestRedisRepository_SetGet(t *testing.T) {
	ctx := context.Background()

	// Inisialisasi Ephemeral Redis Container
	req := testcontainers.ContainerRequest{
		Image:        "redis:7.2-alpine",
		ExposedPorts: []string{"6379/tcp"},
		WaitingFor:   wait.ForLog("* Ready to accept connections"),
	}
	redisC, err := testcontainers.GenericContainer(ctx, testcontainers.GenericContainerRequest{
		ContainerRequest: req,
		Started:          true,
	})
	if err != nil {
		t.Fatalf("Gagal menyalakan kontainer: %s", err)
	}
	// Pastikan kontainer dimusnahkan secara deterministik
	defer func() {
		if err := redisC.Terminate(ctx); err != nil {
			t.Fatalf("Gagal mematikan kontainer: %s", err)
		}
	}()

	endpoint, err := redisC.Endpoint(ctx, "")
	if err != nil {
		t.Fatalf("Gagal mendapatkan endpoint kontainer: %s", err)
	}

	client := redis.NewClient(&redis.Options{
		Addr: endpoint,
	})

	// Operasi state
	err = client.Set(ctx, "qa_key", "hermetic_value", 0).Err()
	if err != nil {
		t.Fatalf("Redis SET error: %s", err)
	}

	val, err := client.Get(ctx, "qa_key").Result()
	if err != nil {
		t.Fatalf("Redis GET error: %s", err)
	}

	if val != "hermetic_value" {
		t.Errorf("Ekspektasi 'hermetic_value', hasil '%s'", val)
	}
}
```

#### B. Contoh Praktis Enterprise: Contract Testing dengan Pact (Go Provider Verification)
Berikut implementasi Provider Verification Engine yang memvalidasi kontrak dari Consumer secara deterministik menggunakan Go test runner dan *database state handlers*.

```go
package pact_test

import (
	"fmt"
	"net"
	"net/http"
	"testing"

	"github.com/pact-foundation/pact-go/v2/models"
	"github.com/pact-foundation/pact-go/v2/provider"
	"github.com/stretchr/testify/assert"
)

// PaymentHTTPHandler merepresentasikan API yang akan divalidasi kontraknya
func PaymentHTTPHandler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/v1/transactions/", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		if r.Header.Get("Authorization") == "" {
			w.WriteHeader(http.StatusUnauthorized)
			_, _ = w.Write([]byte(`{"error": "Unauthorized Access"}`))
			return
		}
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"transaction_id":"tx-999","amount":150000,"currency":"IDR","status":"SETTLED"}`))
	})
	return mux
}

func TestPaymentProvider_ContractVerification(t *testing.T) {
	// 1. Jalankan Provider HTTP Server secara lokal pada port dinamis
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	assert.NoError(t, err)
	
	server := &http.Server{Handler: PaymentHTTPHandler()}
	go func() {
		_ = server.Serve(listener)
	}()
	defer func() { _ = server.Close() }()

	providerPort := listener.Addr().(*net.TCPAddr).Port

	// 2. Setup Pact Provider Verifier
	verifier := provider.NewHTTPVerifier()

	// 3. Eksekusi Verifikasi Kontrak
	verifyRequest := provider.VerifyRequest{
		ProviderBaseURL: fmt.Sprintf("http://127.0.0.1:%d", providerPort),
		PactFiles: []string{
			"./pacts/CheckoutService-PaymentService.json", // Path ke file kontrak lokal atau URL Broker
		},
		StateHandlers: models.ConsumerHandlers{
			"Transaksi tx-999 tersedia pada sistem": func(setup bool, state models.ProviderState) (models.ProviderStateResponse, error) {
				// State Setup: Mengatur database fixtures/mocks deterministik
				if setup {
					// Injeksi state DB (e.g. INSERT ID tx-999)
					return models.ProviderStateResponse{"description": "State injected successfully"}, nil
				}
				// State Teardown: Pembersihan data
				return models.ProviderStateResponse{"description": "State teardown finished"}, nil
			},
		},
		RequestFilter: func(next http.Handler) http.Handler {
			return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				// Inject dynamic authentication token untuk melewati middleware auth lokal
				r.Header.Set("Authorization", "Bearer valid-enterprise-ci-token")
				next.ServeHTTP(w, r)
			})
		},
	}

	err = verifier.VerifyProvider(t, verifyRequest)
	assert.NoError(t, err, "Verifikasi kontrak Pact gagal!")
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks & Masalah
Sebuah platform perbankan digital skala Asia Tenggara memproses 40 juta transaksi harian dengan 120+ mikroservis. Mereka menghadapi krisis QA:
* Rangkaian E2E Test Suite di Staging membutuhkan waktu **3 jam 45 menit** untuk selesai.
* Tingkat kegagalan palsu (*false positive failure rate*) mencapai **38%** akibat flakiness (jaringan time-out, race condition penulisan data antar-tim, *staging state pollution*).
* Kegagalan regresi lolos ke produksi 2-3 kali per sprint karena insinyur terbiasa mengabaikan kegagalan tes dan menekan tombol *rerun*.

#### Solusi Arsitektur
Tim Arsitektur Rekayasa Kualitas merestrukturisasi total pipeline QA:
1. **Pemusnahan Staging E2E Suite**: Mengganti 90% E2E tests dengan **Consumer-Driven Contract Tests (Pact)** yang divalidasi langsung di tahap pipeline PR Provider.
2. **Hermetic Sharded Integration Pipeline**:
   * Setiap tes integrasi basis data dipindahkan ke **Testcontainers (Postgres, CockroachDB, Kafka)**.
   * Node eksekusi CI dipecah menjadi 16 shards paralel di Kubernetes cluster menggunakan Spot Instances.
3. **Flaky Quarantine Engine berbasis Bayesian Filtering**:
   * Tes yang mengalami kegagalan pertama kali tidak langsung membatalkan build, melainkan langsung dieksekusi 10 kali secara terisolasi.
   * Jika varians hasil `(Pass / Total)` berada di antara `0.1` hingga `0.9`, tes diklasifikasi otomatis sebagai **Flaky** dan dipindahkan ke `quarantined_test_suite.db` via GitHub API Labeling.

#### Hasil / Metrik Keberhasilan
* **Waktu Eksekusi Pipeline**: Turun dari **3 jam 45 menit** menjadi **7 menit 12 detik** (efisiensi ~96.8%).
* **False Positive Failure**: Turun drastis dari **38%** menjadi **0.02%**.
* **Keberhasilan Rilis**: Kejadian *API Contract Incompatibility Incident* di produksi turun hingga **0 insiden** sepanjang 4 kuartal berturut-turut.

---

### 9. Trade-offs

```
                  [Fidelity (Ketepatan Lingkungan)]
                                 /\
                                /  \
                               /    \
                              /      \
                             /  E2E   \
                            /  Staging \
                           /   Tests    \
                          /              \
                         +----------------+
                        /                  \
                       /   Testcontainers   \
                      /   (Hermetic Tests)   \
                     /                        \
                    +--------------------------+
                   /    Contract / Unit Tests   \
                  /      (Virtual / Mocks)       \
                 +--------------------------------+
[Latency Rendah & Biaya Murah] <----------------------> [Resource Overhead & Kompleksitas]
```

| Pendekatan | Keuntungan | Kerugian & Batasan | Mitigasi Trade-off |
| :--- | :--- | :--- | :--- |
| **Hermetic Containers (Testcontainers)** | Isolasi 100%, deterministik mutlak, tidak bergantung pada konektivitas eksternal. | Konsumsi CPU & Memori masif di agen CI; latency *cold start* saat *pulling images*. | Gunakan local container image caching registry & persistent host runner daemons. |
| **Contract Testing (Pact)** | Eksekusi sangat cepat (milidetik), mengeliminasi ketergantungan deployment downstream. | Tidak memverifikasi integrasi internal provider (misal: performa query SQL kompleks). | Kombinasikan dengan Hermetic Integration Tests pada lapisan repositori data internal provider. |
| **Mutation Testing** | Menyingkap celah *assertion logic* yang tersembunyi oleh metrik Line Coverage. | Sangat lambat (*compute-intensive*); mengalikan waktu pengujian dengan jumlah mutan AST. | Terapkan selektif hanya pada berkas yang dimodifikasi pada PR (*incremental mutation testing*). |
| **Flaky Test Quarantine** | Mencegah blokade pada pipeline tim pengembang akibat tes yang tidak deterministik. | Menunda perbaikan bug pengujian jika tim tidak disiplin menyelesaikan backlog karantina. | Terapkan SLA karantina: tes yang berada di karantina > 14 hari otomatis dihapus atau ditandai *P0 bug*. |

---

### 10. Common Mistakes & Troubleshooting

#### A. Kebocoran Sumber Daya Docker Socket (Zombie Containers & OOM)
* **Gejala**: Node runner CI tiba-tiba kehabisan ruang disk (*no space left on device*) atau crash akibat *Out of Memory* (OOM).
* **Akar Masalah**: Panggilan Testcontainers crash sebelum hook `defer container.Terminate(ctx)` dieksekusi, dan kontainer Ryuk dinonaktifkan secara sengaja (`TESTCONTAINERS_RYUK_DISABLED=true`).
* **Solusi**: Jangan pernah menonaktifkan Ryuk di CI runner bersama. Gunakan perintah pembersihan berkala pada level node agent:
  ```bash
  docker system prune --force --filter "label=org.testcontainers=true"
  ```

#### B. Polusi State pada Pengujian Konkuren (Database Dirty Reads)
* **Gejala**: Pengujian berhasil saat dijalankan sendirian (`go test -run TestA`), tetapi gagal secara acak saat dijalankan paralel (`go test -parallel 8 ./...`).
* **Akar Masalah**: Antar-goroutine mengeksekusi operasi penulisan (*mutation*) pada tabel basis data yang sama tanpa isolasi skema/transaksi.
* **Solusi**: Gunakan mekanisme skema dinamis per thread atau manfaatkan rollback transaksi database:
  ```go
  // Bungkus setiap assertion dalam DB Transaction yang di-rollback paksa
  tx, _ := db.BeginTx(ctx, nil)
  defer func() { _ = tx.Rollback() }()
  repo := NewRepository(tx)
  // Eksekusi logic assertion menggunakan instance repo bertransaksi
  ```

#### C. Divergensi State Kontrak Pact (Out-of-Sync Consumer Expectations)
* **Gejala**: Pipeline lolos verifikasi kontrak, tetapi layanan downstream melempar error `HTTP 400 Bad Request` di lingkungan staging/produksi.
* **Akar Masalah**: Consumer melakukan mocking data pact yang tidak sesuai dengan *business rules* validasi milik Provider (misal: memalsukan format UUID padahal provider mewajibkan NanoID).
* **Solusi**: Terapkan bidirectional contract testing atau tautkan validasi skema OpenAPI/Protobuf langsung ke dalam generator kontrak Pact.

---

### 11. Best Practices (Production Checklist)

#### Pre-Commit & Local Phase
- [ ] Pengujian unit murni (*pure business logic*) tidak menginisiasi I/O jaringan atau disk (waktu eksekusi < 1ms per test case).
- [ ] Linter AST dan SAST mendeteksi *unhandled errors* serta *empty assertions*.

#### CI/CD Pipeline Phase
- [ ] Gambar basis data Testcontainers dikunci menggunakan *immutable digest tag* (contoh: `postgres:16.2-alpine3.19@sha256:abc123...`), bukan tag `latest`.
- [ ] Variabel environment `TESTCONTAINERS_RYUK_DISABLED` diset ke `false`.
- [ ] Alokasi resource CPU dan Memori Docker container dibatasi secara eksplisit melalui `testcontainers.WithResourceLimits`.
- [ ] Pact CLI `can-i-deploy` dieksekusi sebelum langkah deployment ke lingkungan apa pun:
  ```bash
  pact-broker can-i-deploy \
    --pacticipant PaymentService \
    --version ${GIT_COMMIT_HASH} \
    --to-environment production
  ```
- [ ] Target Mutation Testing Score minimal **75%** pada paket/modul *financial ledger*, *auth*, dan *state engine*.
- [ ] Engine deteksi flaky test mengisolasi tes dengan varians non-deterministik ke berkas laporan *quarantine metrics*.

#### Production (Shift-Right) Phase
- [ ] Synthetic probes memverifikasi fungsionalitas kritis dengan akun pengujian berlabel `X-Synthetic-Test: true`.
- [ ] Metrik synthetic traces OpenTelemetry dipisahkan dari metrik SLA/SLO pengguna asli pada dashboard Grafana.

---

### 12. Hands-on Practice

Implementasikan lingkungan hermetik terdistribusi mini untuk pengujian integrasi database dengan Testcontainers dan skema isolasi. Simpan seluruh artefak praktikum di direktori: `hands-on/m02/`.

#### Langkah 1: Inisialisasi Proyek
```bash
mkdir -p hands-on/m02
cd hands-on/m02
go mod init enterprise-qa-m02
go get -u github.com/testcontainers/testcontainers-go
go get -u github.com/testcontainers/testcontainers-go/modules/postgres
go get -u github.com/jackc/pgx/v5/pgxpool
go get -u github.com/stretchr/testify/assert
```

#### Langkah 2: Buat Skema & Repositori Ledger Transaksi
Buat file `hands-on/m02/ledger.go`:
```go
package ledger

import (
	"context"
	"errors"
	"github.com/jackc/pgx/v5/pgxpool"
)

type Account struct {
	ID      string
	Balance int64
}

type Repository struct {
	pool *pgxpool.Pool
}

func NewRepository(pool *pgxpool.Pool) *Repository {
	return &Repository{pool: pool}
}

func (r *Repository) Transfer(ctx context.Context, fromID, toID string, amount int64) error {
	if amount <= 0 {
		return errors.New("jumlah transfer harus positif")
	}

	tx, err := r.pool.Begin(ctx)
	if err != nil {
		return err
	}
	defer func() { _ = tx.Rollback(ctx) }()

	var fromBalance int64
	err = tx.QueryRow(ctx, "SELECT balance FROM accounts WHERE id = $1 FOR UPDATE", fromID).Scan(&fromBalance)
	if err != nil {
		return err
	}

	if fromBalance < amount {
		return errors.New("saldo tidak mencukupi")
	}

	_, err = tx.Exec(ctx, "UPDATE accounts SET balance = balance - $1 WHERE id = $2", amount, fromID)
	if err != nil {
		return err
	}

	_, err = tx.Exec(ctx, "UPDATE accounts SET balance = balance + $1 WHERE id = $2", amount, toID)
	if err != nil {
		return err
	}

	return tx.Commit(ctx)
}
```

#### Langkah 3: Implementasi Hermetic Integration Test Harness
Buat file `hands-on/m02/ledger_test.go`:
```go
package ledger_test

import (
	"context"
	"path/filepath"
	"testing"
	"time"

	"enterprise-qa-m02/ledger"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/stretchr/testify/assert"
	"github.com/testcontainers/testcontainers-go"
	pgmodule "github.com/testcontainers/testcontainers-go/modules/postgres"
	"github.com/testcontainers/testcontainers-go/wait"
)

func TestEnterpriseLedger_Transfer_Hermetic(t *testing.T) {
	ctx := context.Background()

	// 1. Inisialisasi PostgreSQL Testcontainer secara dinamis
	pgContainer, err := pgmodule.RunContainer(ctx,
		testcontainers.WithImage("postgres:16-alpine"),
		pgmodule.WithDatabase("ledger_db"),
		pgmodule.WithUsername("postgres"),
		pgmodule.WithPassword("supersecret"),
		testcontainers.WithWaitStrategy(
			wait.ForLog("database system is ready to accept connections").
				WithOccurrence(2).
				WithStartupTimeout(30*time.Second),
		),
	)
	assert.NoError(t, err)

	// Pastikan cleanup kontainer otomatis
	defer func() {
		err := pgContainer.Terminate(ctx)
		assert.NoError(t, err)
	}()

	connStr, err := pgContainer.ConnectionString(ctx, "sslmode=disable")
	assert.NoError(t, err)

	// 2. Hubungkan Connection Pool
	pool, err := pgxpool.New(ctx, connStr)
	assert.NoError(t, err)
	defer pool.Close()

	// 3. Setup Skema Database (DDL) & Fixture
	ddl := `
	CREATE TABLE accounts (
		id VARCHAR(64) PRIMARY KEY,
		balance BIGINT NOT NULL
	);
	INSERT INTO accounts (id, balance) VALUES ('acc-source', 1000000), ('acc-target', 500000);
	`
	_, err = pool.Exec(ctx, ddl)
	assert.NoError(t, err)

	repo := ledger.NewRepository(pool)

	// 4. Test Case: Transfer Valid
	t.Run("Valid Transfer Execution", func(t *testing.T) {
		err := repo.Transfer(ctx, "acc-source", "acc-target", 250000)
		assert.NoError(t, err)

		var sourceBalance, targetBalance int64
		_ = pool.QueryRow(ctx, "SELECT balance FROM accounts WHERE id = 'acc-source'").Scan(&sourceBalance)
		_ = pool.QueryRow(ctx, "SELECT balance FROM accounts WHERE id = 'acc-target'").Scan(&targetBalance)

		assert.Equal(t, int64(750000), sourceBalance)
		assert.Equal(t, int64(750000), targetBalance)
	})

	// 5. Test Case: Insufficient Funds (Rollback Test)
	t.Run("Insufficient Funds Rollback", func(t *testing.T) {
		err := repo.Transfer(ctx, "acc-source", "acc-target", 99999999)
		assert.Error(t, err)
		assert.Contains(t, err.Error(), "saldo tidak mencukupi")

		// Pastikan saldo tidak berubah
		var sourceBalance int64
		_ = pool.QueryRow(ctx, "SELECT balance FROM accounts WHERE id = 'acc-source'").Scan(&sourceBalance)
		assert.Equal(t, int64(750000), sourceBalance)
	})
}
```

#### Langkah 4: Jalankan Test Suite
```bash
go test -v -race ./...
```

---

### 13. Exercise

#### Level Easy
Ubah implementasi `hands-on/m02/ledger_test.go` agar menggunakan skema dinamis acak (*random schema isolation*) per sub-test (`t.Run`), sehingga pengujian dapat dieksekusi secara konkuren (`t.Parallel()`) di dalam satu kontainer database yang sama tanpa saling mengganggu.

#### Level Medium
Buat sebuah utility wrapper Go bernama `EphemeralKafkaCluster` menggunakan Testcontainers yang:
1. Menjalankan Apache Kafka (KRaft mode).
2. Membuat topic `transactions.events` dengan 3 partisi secara terprogram.
3. Mengembalikan array broker addresses yang siap diinjeksikan ke dalam Kafka Consumer/Producer client.
4. Memastikan timeout terminasi maksimal 15 detik jika runtime gagal booting.

#### Level Hard
Rancang engine deteksi mutasi AST sederhana menggunakan pustaka bawaan Go `go/parser`, `go/ast`, dan `go/printer`:
1. Buat program yang mem-parsing file `ledger.go`.
2. Temukan setiap node perbandingan `amount <= 0` pada AST dan mutasikan operator tersebut menjadi `amount < 0`.
3. Tuliskan file termutasi ke temporary directory.
4. Jalankan rangkaian uji secara otomatis terhadap file termutasi tersebut untuk memverifikasi apakah *test suite* mendeteksi modifikasi kode (Killed) atau meloloskannya (Survived).

---

### 14. Challenge

#### Deskripsi Skenario Kompleks
Sebuah sistem agregator pembayaran enterprise memproses transaksi pembayaran QRIS antar-negara. Arsitektur terdiri dari 4 layer layanan:
1. `API Gateway`: Melakukan routing dan auth validation.
2. `Transaction Processor`: Menyimpan state mesin pembayaran ke Cassandra & menerbitkan event ke Apache Pulsar.
3. `Settlement Worker`: Mengonsumsi event dari Pulsar dan berkomunikasi secara sinkron via gRPC ke sistem Core Banking mitra.

#### Tantangan Arsitektural & Persyaratan
1. **Zero External Staging**: Rancang arsitektur QA CI/CD di mana pipeline PR dapat memvalidasi end-to-end integrasi seluruh alur pembayaran tanpa satupun dependensi fisik yang menyala di luar runner CI.
2. **Strict Time Budget**: Total durasi eksekusi pengujian dari `git push` hingga verifikasi kontrak selesai tidak boleh melebihi **8 menit**.
3. **Flakiness Target**: Rasio kegagalan akibat masalah non-deterministik (jaringan kontainer, racing DB, timeout) harus **0%**.
4. **Deliverables**:
   * Desain diagram arsitektur pipeline pengujian lengkap dari commit hingga canary.
   * Strategi isolasi data antar layanan (Cassandra state & Apache Pulsar ephemeral topics).
   * Spesifikasi Contract Verification Matrix (Consumer & Provider Pact) untuk interaksi gRPC dan Event-Driven Messaging.
   * Algoritma Bayesian Flaky Test Isolation lengkap dengan pseudocode penanganan metrik deviasi hasil pengujian.

---

### 15. Quiz Evaluasi Pemahaman

#### Pertanyaan Basic (5 Soal)
1. **Mengapa metrik Line Coverage 100% tidak menjamin perangkat lunak bebas dari bug kritis?**
   * *Jawaban*: Line coverage hanya mengukur baris kode yang dieksekusi oleh mesin penguji, bukan validitas logika dari pengujian itu sendiri. Baris kode bisa dieksekusi tanpa adanya pernyataan `assertion` (pengujian kosong), atau pengujian tidak memverifikasi seluruh kemungkinan *state*, nilai batas (*boundary values*), dan penanganan error.
2. **Apa fungsi utama dari kontainer pendamping Ryuk pada arsitektur Testcontainers?**
   * *Jawaban*: Ryuk berfungsi sebagai *garbage collector process* independen yang berkomunikasi langsung dengan Docker daemon. Ryuk memantau lifecycle runner dan memastikan seluruh kontainer, jaringan, dan volume yang dialokasikan oleh pengujian otomatis dimusnahkan jika proses runner mengalami crash mendadak atau dihentikan secara paksa oleh CI runner.
3. **Apa perbedaan mendasar antara Provider State pada Contract Testing dengan Database Fixture konvensional?**
   * *Jawaban*: Database fixture konvensional memasukkan sekumpulan data statis global ke database bersama, sedangkan Provider State pada contract testing adalah setup data lokal deterministik yang diinisiasi *on-demand* sesuai instruksi deklaratif spesifik yang diminta oleh Consumer untuk satu interaksi tertentu saja.
4. **Pada mutation testing, apa indikasi kualitas rangkaian uji jika skor mutasi (*mutation score*) rendah meskipun code coverage tinggi?**
   * *Jawaban*: Rangkaian pengujian memiliki kualitas assertion yang sangat buruk (*brittle/weak assertions*). Kode dijalankan oleh pengujian, namun ketika logika operasi kode disabotase (dimutasi), pengujian tetap melaporkan status lolos (*pass*), yang menandakan ketiadaan validasi state yang sebenarnya.
5. **Bagaimana pendekatan Shift-Right testing melengkapi keterbatasan dari Shift-Left testing?**
   * *Jawaban*: Shift-Left berfokus pada verifikasi logika sebelum deployment pada lingkungan terkontrol, namun tidak dapat memprediksi variabel dinamis produksi seperti perilaku jaringan nyata, latensi storage fisik, degradasi upstream pihak ketiga, dan konkurensi skala masif. Shift-Right menguji sistem secara langsung di lingkungan produksi (via synthetic monitoring, chaos injection, dan telemetry trace analysis) untuk memvalidasi performa aktual.

#### Pertanyaan Intermediate (5 Soal)
6. **Bagaimana cara mencegah kehabisan port TCP lokal (*TCP port exhaustion*) ketika menjalankan ratusan container pengujian integrasi secara paralel?**
   * *Jawaban*: Tidak memetakan port kontainer ke port host statis (seperti `5432:5432`). Sebaliknya, gunakan alokasi port dinamis/efemeral dari host (`0.0.0.0:0` yang otomatis dialokasikan kernel host ke port bebas) dan ambil port tersebut secara terprogram via API inspeksi container (`container.MappedPort(ctx, "5432")`).
7. **Dalam Consumer-Driven Contract Testing, mengapa Consumer yang bertugas mendefinisikan kontrak dan bukan Provider?**
   * *Jawaban*: Pendekatan ini memastikan API dirancang secara berorientasi pada kebutuhan riil pengguna (*client-centric*), bukan asumsi internal penyedia data. Selain itu, ini memungkinkan Provider mengetahui secara presisi bagian payload mana yang benar-benar digunakan oleh Consumer, sehingga Provider dapat mengubah atau membuang field yang tidak digunakan tanpa risiko menimbulkan *breaking changes*.
8. **Jelaskan cara kerja mutator tipe *Conditionals Boundary Mutator* (misal: merubah `<` menjadi `<=`) dalam mengungkap defek *Off-by-One*!**
   * *Jawaban*: Mutator ini menyabotase logika batas nilai. Jika rangkaian uji tidak memiliki test case yang menguji batas nilai presisi (misal: saat `nilai == batas`), mutasi ini akan *survived* (lolos). Pengujian yang kuat harus menyertakan skenario batas bawah, batas pas, dan batas atas agar mutan tersebut *killed*.
9. **Kapan teknik *Docker-out-of-Docker* (DooD) lebih disukai daripada *Docker-in-Docker* (DinD) dalam konfigurasi agent CI pipeline untuk Testcontainers?**
   * *Jawaban*: DooD lebih disukai untuk menghindari kebutuhan hak istimewa *privileged container mode* yang menimbulkan risiko keamanan tinggi, menghindari masalah performa pada lapisan sistem berkas ganda (*storage driver over storage driver*), serta memungkinkan pemanfaatan *layer caching* Docker host secara langsung di runner CI.
10. **Bagaimana cara mengisolasi transaksi pengujian pada Kafka tanpa memerlukan kontainer baru untuk setiap test case?**
    * *Jawaban*: Menggunakan strategi penamaan topik dinamis yang diisolasi per pengujian (misal: `uuid-prefix-events`), atau menggunakan *Consumer Group ID* yang acak dan unik untuk tiap eksekusi tes dengan parameter pembacaan offset `earliest`.

#### Skenario Kasus Produksi (3 Soal)
11. **Skenario Kasus 1**: Pipeline pengujian hermetik tim Anda di GitHub Actions mendadak mengalami error `toomanyrequests: You have reached your unauthenticated pull rate limit` dari Docker Hub di tengah rilis hotfix darurat. Bagaimana arsitektur caching lokal dan Testcontainers harus dikonfigurasi untuk mencegah masalah ini secara permanen?
    * *Jawaban Analitis*: 
      1. Terapkan private container registry mirror internal (misal: Harbor atau AWS ECR Public Mirror) di dalam jaringan runner CI.
      2. Konfigurasi Docker daemon pada agent CI dengan `registry-mirrors`: `["https://mirror.internal.enterprise.domain"]`.
      3. Konfigurasi file properti Testcontainers `~/.testcontainers.properties` dengan parameter:
         `hub.image.name.prefix=mirror.internal.enterprise.domain/dockerhub-cache/`
      4. Ini secara otomatis mengarahkan seluruh unduhan image Testcontainers ke mirror lokal berotentikasi tanpa menyentuh batasan rate limit Docker Hub eksternal.
12. **Skenario Kasus 2**: Rangkaian uji integrasi microservice pembayaran Anda memiliki satu pengujian: `TestProcessPayment_Success` yang gagal rata-rata 2 kali dari setiap 10 eksekusi di pipeline CI, tetapi selalu sukses 100% saat dieksekusi di laptop developer. Log menunjukkan database timeout sporadis. Bagaimana metodologi forensik untuk membuktikan akar masalahnya dan langkah mitigasinya?
    * *Jawaban Analitis*:
      1. *Forensik*: Kegagalan lokal vs CI biasanya disebabkan oleh disparitas performa I/O dan alokasi resource CPU core. Pada agent CI yang terbebani tinggi, thread kontainer PostgreSQL mengalami kelaparan sumber daya (*CPU throttling* oleh cgroups), menyebabkan waktu startup dan eksekusi query melewati default context timeout (biasanya 5 detik).
      2. *Pembuktian*: Eksekusi pengujian dengan pembatasan resource buatan di lokal: `docker run --cpus=0.5 --memory=512m` dan amati metrik starvation melalui `docker stats`.
      3. *Mitigasi*:
         - Pasang `wait.ForLog()` atau `wait.ForListeningPort()` dengan threshold startup timeout yang lebih adaptif (misal: 30-60 detik).
         - Atur alokasi cgroups resource eksplisit pada builder Testcontainers (`WithResourceLimits`).
         - Hindari eksekusi paralel database I/O yang melebihi jumlah vCPU node CI runner.
13. **Skenario Kasus 3**: Tim arsitektur melarang penggunaan End-to-End Environment di Staging karena biaya infrastruktur cloud yang membengkak ($50,000/bulan) dan reliabilitas lingkungan yang buruk. Manajemen menuntut jaminan bahwa ketika Service A (Consumer) merilis payload baru ke Service B (Provider), sistem tidak crash dengan error 500. Rancang arsitektur pipeline verifikasi yang memvalidasi hal ini sebelum artefak masuk ke registry container produksi!
    * *Jawaban Analitis*:
      1. Implementasikan Consumer-Driven Contract Testing menggunakan **Pact Broker Matrix**.
      2. Pada PR Consumer Service A: Eksekusi contract generation, terbitkan kontrak interaksi ke Pact Broker dengan tag branch commit.
      3. Pada PR Provider Service B: Webhook memicu eksekusi verifikasi Provider terhadap kontrak Service A versi terbaru secara hermetik menggunakan Testcontainers untuk memvalidasi interaksi.
      4. Tambahkan validasi skema statis: Eksekusi *OpenAPI / JSON-Schema Compatibility Check* (misal: menggunakan `openapi-diff` atau `buf breaking` untuk gRPC/Protobuf) pada pipeline CI untuk menjamin *backward compatibility*.
      5. Pasang deployment blocker: Gunakan script CLI `pact-broker can-i-deploy --pacticipant ServiceA --version $GIT_COMMIT --to-environment production` sebagai gerbang penentu (*pass/fail gate*) pada pipeline deployment CD. Jika kompatibilitas belum diverifikasi oleh Service B, rilis otomatis diblokir di tingkat pipeline tanpa perlu menyalakan staging environment fisik.

---

### 16. Summary

* **Arsitektur Hermetik** adalah standar de facto dalam pengujian sistem terdistribusi modern; mengeliminasi kondisi balapan data (*data race*) dan kegagalan palsu dengan menggunakan resource dinamis terisolasi (via Testcontainers) yang memiliki lifecycle independen dan pembersihan deterministik via daemon Ryuk.
* **Consumer-Driven Contract Testing (Pact)** menggeser pengujian integrasi lintas-layanan ke arah kiri (*shift-left*), menggantikan kebutuhan staging environment terpusat yang rapuh dengan verifikasi kompatibilitas skema asinkron berbasis matriks status.
* **Mutation Testing** mengubah paradigma pengukuran kualitas pengujian dari sekadar *Code Execution* (Line Coverage) menjadi *Semantic Logic Verification* (Mutation Score), secara sistematis menyingkap kerapuhan pada *test assertion logic*.
* **Mitigasi Flaky Test Skala Enterprise** membutuhkan pendekatan matematis dan terprogram melalui isolasi karantina dinamis (*dynamic quarantine circuit breaker*), mencegah perlambatan throughput rekayasa perangkat lunak tanpa mengabaikan utang teknis (*technical debt*).
* **Verifikasi Kualitas Berkelanjutan (Shift-Right)** menyatukan QA dan Observabilitas, memastikan bahwa jaminan kualitas tidak berhenti saat kode lolos deployment, melainkan terus diverifikasi di lingkungan produksi menggunakan instrumen sintetis dan telemetri OpenTelemetry.