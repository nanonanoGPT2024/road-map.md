# BAB 08: Metrik, SLA & Review Fatigue
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Principal Engineer, Lead Architect, dan Engineering Manager diharapkan mampu:
1. **Merancang Telemetry Pipeline Skala Enterprise**: Membangun arsitektur penangkapan event Git (GitHub/GitLab) terdistribusi untuk melacak *code review lifecycle metrics* secara real-time dengan overhead minimal.
2. **Memformulasi dan Mengkuantifikasi Review Fatigue**: Menerapkan kalkulasi matematis terhadap *Cognitive Load* dan *Review Fatigue Index* (RFI) guna mendeteksi degradasi kualitas review sebelum insiden lolos ke produksi (*Defect Escape*).
3. **Menerapkan Dynamic SLA Engine**: Mengembangkan sistem evaluasi Service Level Agreement berbasis state-machine yang adaptif terhadap dependensi kode, tingkat risiko, dan kalender kerja tim (menghindari *false-positive alerts* di luar jam kerja).
4. **Membangun Automated Review Routing & Load Balancing**: Mengimplementasikan algoritma penugasan reviewer otomatis (*Weighted Fair Queuing*) guna mencegah ketimpangan beban kerja (*silo review*) di antara Senior/Staff Engineers.

---

### 2. Prerequisite
Untuk menyerap materi ini secara optimal, peserta wajib memahami:
*   **Git Internals & Lifecycle**: Pemahaman mendalam tentang reflog, object model, diff generation, commit graph, dan event webhook (GitHub REST/GraphQL API & Webhook Payload v3/v4).
*   **Event-Driven Architecture**: Pemahaman tentang message brokers (Apache Kafka, RabbitMQ, atau AWS SQS) dan asynchronous processing.
*   **Time-Series & Analytical Databases**: Pengetahuan dasar tentang skema data OLAP (ClickHouse, PostgreSQL, atau Prometheus/VictoriaMetrics) untuk time-series aggregation.
*   **Go (Golang) / Python**: Kemampuan membaca dan menulis sistem concurrency-safe tingkat lanjut (channels, context, sync primitives, goroutines).

---

### 3. Concept & Internal Architecture (Mendalam)

Implementasi metrik code review di level enterprise bukan sekadar menghitung rata-rata waktu pull request (PR) terbuka. Masalah mendasar pada rekayasa perangkat lunak skala besar berkisar pada **keseimbangan kecepatan (cycle time) versus ketelitian (defect detection capability)**.

#### Arsitektur Telemetry Pipeline untuk Code Review
Untuk memonitor PR lifecycle secara akurat tanpa membebani infrastruktur Git host, kita menerapkan arsitektur *event-driven telemetry engine*:

```
+-----------------------------------------------------------------------------------+
|                            GIT HOST (GitHub / GitLab)                             |
+-----------------------------------------------------------------------------------+
             | (HTTPS POST Webhook: pull_request, pull_request_review)
             v
+-----------------------------------------------------------------------------------+
|                            INGRESS & EDGE GATEWAY                                 |
| - HMAC-SHA256 Signature Verification                                              |
| - Rate Limiting & TLS Termination                                                 |
+-----------------------------------------------------------------------------------+
             |
             v
+-----------------------------------------------------------------------------------+
|                        BUFFERING LAYER (Apache Kafka / SQS)                       |
| Topic: `git.pr.events` (Partition key: repository.id / pr.number)                 |
+-----------------------------------------------------------------------------------+
             |
             v
+-----------------------------------------------------------------------------------+
|                      TELEMETRY PROCESSOR & STATE MACHINE                          |
| - Event deduplication (Idempotency Key: X-GitHub-Delivery)                        |
| - Out-of-order event reconciliation (Sliding Window Engine)                       |
| - Review State Reconstruction:                                                    |
|     * Time-to-First-Review (TTFR) Tracking                                        |
|     * Review Fatigue Index (RFI) Engine                                           |
|     * SLA Breach Detection Timer                                                  |
+-----------------------------------------------------------------------------------+
       |                                          |                           |
       v                                          v                           v
+-----------------------+      +-----------------------+    +-----------------------+
|  STORAGE LAYER (OLAP) |      |   CACHE LAYER (Redis) |    | NOTIFICATION / ACTION |
|  ClickHouse / Postgres|      |   Active Review States|    | Alertmanager, Slack,  |
|  Analytical Queries   |      |   Reviewer Queues     |    | Auto-reassign Engine  |
+-----------------------+      +-----------------------+    +-----------------------+
```

#### Taksonomi Metrik Utama
1. **Time to First Review (TTFR)**: Durasi dari status PR menjadi `ready_for_review` hingga event `pull_request_review` pertama kali masuk dari reviewer yang ditunjuk (bukan automated bot).
2. **Review Depth Ratio (RDR)**:
   $$\text{RDR} = \frac{\text{Total Review Comments (Non-LGTM)}}{\Delta \text{LOC Modified}}$$
   Jika RDR mendekati $0$ pada PR dengan $\Delta \text{LOC} > 400$, probabilitas terjadinya *Rubber-Stamping* (menyetujui tanpa membaca) mendekati $99\%$.
3. **Review Iteration Count (RIC)**: Jumlah siklus pertukaran status antara `changes_requested` dan push commit baru. RIC yang terlalu tinggi ($> 4$) menandakan spesifikasi yang tidak jelas atau *architectural misalignment*.
4. **Reviewer Workload Saturation (RWS)**: Rasio PR aktif yang sedang ditinjau oleh seorang engineer relatif terhadap kapasitas ambang batas kognitifnya ($C_{max}$).

#### Formulasi Matematis Review Fatigue Index (RFI)
Review fatigue terjadi ketika beban kognitif melebihi kapasitas pemrosesan informasi seorang reviewer. Kami merumuskan RFI untuk seorang reviewer $u$ pada interval waktu $t$ sebagai berikut:

$$\text{RFI}_u(t) = \sum_{i \in \text{PR}_{\text{active}}} \left( w_1 \cdot \ln(\Delta \text{LOC}_i) + w_2 \cdot \text{Complexity}_i + w_3 \cdot \text{ContextSwitch}_i \right) - \delta \cdot \Delta t_{\text{rest}}$$

Di mana:
*   $\Delta \text{LOC}_i$: Jumlah baris kode yang ditambahkan/dihapus pada PR $i$. Fungsi $\ln$ digunakan karena penambahan baris kode memiliki efek kognitif marginal yang melambat namun melelahkan.
*   $\text{Complexity}_i$: Skor kompleksitas file yang diubah (misalnya perubahan skema database/security module bernilai bobot lebih tinggi dibanding file konfigurasi JSON).
*   $\text{ContextSwitch}_i$: Bernilai $1$ jika PR berasal dari domain/repositori yang berbeda dengan spesialisasi harian reviewer, bernilai $0$ jika dalam domain yang sama.
*   $\delta \cdot \Delta t_{\text{rest}}$: Faktor pemulihan (*recovery decay*) berdasarkan jeda waktu dari review terakhir.

Ambang batas produksi:
*   $\text{RFI} < 15$: Zona Optimal (Review mendalam, high defect detection).
*   $15 \le \text{RFI} \le 30$: Zona Waspada (Latency review meningkat, kedalaman komentar menurun).
*   $\text{RFI} > 30$: Zona Fatigue Kritis (Potensi tinggi *LGTM rubber-stamping* atau pengabaian total).

---

### 4. Why & What

| Dimensi | Pendekatan Ad-Hoc / Tanpa Metrik | Pendekatan Enterprise Telemetry & SLA Engine |
| :--- | :--- | :--- |
| **Visibilitas Bottleneck** | Bersifat asumsi individual ("PR saya lama di-review"). | Analisis empiris berbasis persentil (P50, P90, P99 TTFR dan TTM). |
| **Penegakan Kualitas** | Bergantung pada *mood* dan beban kerja masing-masing engineer. | Sistematis; PR tidak dapat di-merge jika RDR terlalu rendah tanpa persetujuan eksplisit. |
| **Mitigasi Fatigue** | Senior Engineer menerima beban review paling berat hingga *burnout*. | Beban didistribusikan via *Weighted Fair Queuing* berbasis RFI harian. |
| **Manajemen SLA** | Deadline diabaikan atau diingatkan manual via Slack. | Eskalasi bertingkat otomatis dengan pengecualian *out-of-office* dan *working-hours*. |

---

### 5. How (Workflow Detail)

Berikut adalah siklus operasional sistem pemrosesan metrik dan penegakan SLA:

```
[PR Created / Marked Ready]
            |
            v
[Ingest Webhook Event] 
            |
            v
[Validate HMAC & De-duplicate Event]
            |
            +--> [Hitung Skor Kompleksitas PR: LOC, File Types, Risk Score]
            |
            +--> [Pilih Reviewer: Minimalkan RFI, Cocokkan CODEOWNERS]
            |
            v
[Inisialisasi SLA State Machine]
            |
            +--> Set Timer: SLA_TTFR_Threshold (e.g., 4 jam kerja)
            |
            +--- (Review Masuk Tepat Waktu) ----> [Batalkan SLA Timer] --> [Catat Metrik TTFR]
            |                                                                   |
            +--- (Timeout / SLA Terlanggar)                                      v
                        |                                           [Analisis Kedalaman Review (RDR)]
                        v                                                       |
            [Kirim Eskalasi ke Slack Tim]                                        +--> RDR Rendah & LOC Besar?
                        |                                                                   |
                        v                                                                   v
            [Re-assign Reviewer Otomatis]                                      [Tandai Flag: Rubber-Stamp Warning]
```

1. **Ingestion & Validation**: Gateway menerima payload, memverifikasi `X-Hub-Signature-256`, dan meneruskan event ke broker Kafka.
2. **State Evaluation**: Telemetry worker membaca event. Jika PR berstatus `opened` atau `ready_for_review`, sistem memfilter bot (Dependabot, Renovate) dan menghitung estimasi bobot kognitif PR.
3. **Dynamic Assignment**: Algoritma penugasan memeriksa kapasitas para maintainer. Reviewer dengan skor $\text{RFI} > 25$ dieksklusikan dari antrean otomatis.
4. **SLA Watchdog**: Scheduler melacak status PR. Jika tidak ada aktivitas non-author review dalam batas SLA, eskalasi dipicu via webhook internal.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Air Traffic Control (ATC) vs. Code Review Pipeline
Bayangkan sebuah bandara internasional yang sibuk.
* **Pull Request** adalah **Pesawat yang Hendak Mendarat**. LOC adalah jumlah penumpang dan kargo bahan bakar di dalamnya.
* **Reviewer** adalah **Petugas Air Traffic Control (ATC)**.
* Jika seorang petugas ATC dipaksa memandu 15 pesawat berbadan lebar secara simultan (*High RFI*), mereka akan kehilangan fokus. Akibatnya fatal: instruksi diberikan secara asal-asalan (*Rubber-stamping/LGTM*), yang berisiko memicu tabrakan (*Defect lolos ke produksi*).
* **Dynamic SLA & Routing Engine** berfungsi sebagai sistem alokasi radar otomatis yang mengalihkan pesawat ke bandara satelit atau menugaskannya ke petugas ATC yang sedang memiliki ruang fokus optimal.

#### Diagram Interaksi State Machine SLA Review

```
                +-------------------+
                |     PR OPENED     |
                +-------------------+
                          |
                          v
         +---------------------------------+
         |      SCHEDULE SLA WATCHDOG      |
         |  Target: P90 TTFR <= 4 Jam      |
         +---------------------------------+
               /                       \
  [Event: Review Comment]     [Timer Expired (Breach)]
             /                           \
            v                             v
+-----------------------+     +-----------------------+
|   CANCEL SLA TIMER    |     | EMIT SLA_BREACH EVENT |
+-----------------------+     +-----------------------+
            |                             |
            v                             v
+-----------------------+     +-----------------------+
|  EVALUATE REVIEW RDR  |     | ESCALATE TO ON-CALL   |
+-----------------------+     | RE-ROUTE CANDIDATE    |
            |                 +-----------------------+
            v
+-----------------------+
| UPDATE REVIEWER METRIC|
|      (RFI Index)      |
+-----------------------+
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Perhitungan Metrik Waktu & Review Depth Sederhana (Python)
Script mandiri untuk menghitung metrik TTFR dan RDR dari event Git dasar.

```python
from datetime import datetime
from typing import List, Dict, Any

def calculate_review_metrics(pr_data: Dict[str, Any], reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
    created_at = datetime.fromisoformat(pr_data["created_at"].replace("Z", "+00:00"))
    loc_changed = pr_data["additions"] + pr_data["deletions"]
    
    # Filter review non-author dan non-bot
    valid_reviews = [
        r for r in reviews 
        if r["user"]["login"] != pr_data["user"]["login"] and not r["user"]["login"].endswith("[bot]")
    ]
    
    if not valid_reviews:
        return {
            "ttfr_seconds": None,
            "rdr": 0.0,
            "is_rubber_stamped": False
        }
        
    # Sort berdasarkan waktu submit
    valid_reviews.sort(key=lambda x: datetime.fromisoformat(x["submitted_at"].replace("Z", "+00:00")))
    first_review = valid_reviews[0]
    first_review_time = datetime.fromisoformat(first_review["submitted_at"].replace("Z", "+00:00"))
    
    ttfr_seconds = (first_review_time - created_at).total_seconds()
    
    # Hitung komentar substantif (mengabaikan komentar trivial)
    substantive_comments = sum(
        1 for r in valid_reviews 
        if len(r.get("body", "").strip()) > 10 and "LGTM" not in r.get("body", "").upper()
    )
    
    # Hitung Review Depth Ratio
    rdr = (substantive_comments / loc_changed) * 100 if loc_changed > 0 else 0.0
    
    # Deteksi Rubber Stamping: LOC besar, waktu sangat cepat, review minim
    is_rubber_stamped = (loc_changed > 300) and (ttfr_seconds < 180) and (substantive_comments == 0)
    
    return {
        "ttfr_seconds": ttfr_seconds,
        "total_loc": loc_changed,
        "substantive_comments": substantive_comments,
        "rdr": round(rdr, 4),
        "is_rubber_stamped": is_rubber_stamped
    }

# Contoh Kasus
mock_pr = {
    "user": {"login": "developer-a"},
    "created_at": "2026-03-30T08:00:00Z",
    "additions": 450,
    "deletions": 50
}

mock_reviews = [
    {
        "user": {"login": "senior-b"},
        "submitted_at": "2026-03-30T08:02:15Z",
        "body": "LGTM! Approved."
    }
]

metrics = calculate_review_metrics(mock_pr, mock_reviews)
print(f"Metrics Output: {metrics}")
# Output mendeteksi: is_rubber_stamped = True karena 500 LOC ditinjau dalam 135 detik tanpa diskusi substantif.
```

#### Practical Example: Production-Grade Telemetry Consumer & Fatigue Engine (Go)
Implementasi Go production-ready yang menangani streaming webhook event, pemrosesan konkurensi aman, penghitungan RFI, dan SLA dispatching.

```go
package main

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"sync"
	"time"
)

// Definisi Struktur Payload Webhook GitHub
type GitHubUser struct {
	Login string `json:"login"`
	Type  string `json:"type"`
}

type PullRequestPayload struct {
	Action      string `json:"action"`
	PullRequest struct {
		Number    int        `json:"number"`
		User      GitHubUser `json:"user"`
		CreatedAt time.Time  `json:"created_at"`
		Additions int        `json:"additions"`
		Deletions int        `json:"deletions"`
	} `json:"pull_request"`
	Review struct {
		User        GitHubUser `json:"user"`
		SubmittedAt time.Time  `json:"submitted_at"`
		Body        string     `json:"body"`
		State       string     `json:"state"`
	} `json:"review"`
	Repository struct {
		FullName string `json:"full_name"`
	} `json:"repository"`
}

// Model Telemetri dan Metrik
type ReviewerProfile struct {
	Username          string
	ActivePRCount     int
	TotalLOCReviewing int
	LastReviewTime    time.Time
	CurrentRFI        float64
}

type FatigueEngine struct {
	mu        sync.RWMutex
	reviewers map[string]*ReviewerProfile
	slaTimers map[string]*time.Timer
}

func NewFatigueEngine() *FatigueEngine {
	return &FatigueEngine{
		reviewers: make(map[string]*ReviewerProfile),
		slaTimers: make(map[string]*time.Timer),
	}
}

// Verifikasi Signature HMAC-SHA256 untuk Ingress Security
func VerifyWebhookSignature(secret []byte, signatureHeader string, body []byte) bool {
	const signaturePrefix = "sha256="
	if len(signatureHeader) <= len(signaturePrefix) || signatureHeader[:len(signaturePrefix)] != signaturePrefix {
		return false
	}
	sig, err := hex.DecodeString(signatureHeader[len(signaturePrefix):])
	if err != nil {
		return false
	}
	mac := hmac.New(sha256.New, secret)
	mac.Write(body)
	expectedMAC := mac.Sum(nil)
	return hmac.Equal(sig, expectedMAC)
}

// Perhitungan RFI Menggunakan Logarithmic Weighting & Decay
func (fe *FatigueEngine) CalculateRFI(reviewer *ReviewerProfile, addedLOC int) float64 {
	w1 := 1.8 // Bobot LOC
	w2 := 4.5 // Bobot per PR aktif
	decayRate := 0.2

	loc := float64(reviewer.TotalLOCReviewing + addedLOC)
	locScore := 0.0
	if loc > 0 {
		locScore = math.Log(loc) * w1
	}

	workloadScore := float64(reviewer.ActivePRCount) * w2
	
	hoursSinceLastReview := time.Since(reviewer.LastReviewTime).Hours()
	if reviewer.LastReviewTime.IsZero() {
		hoursSinceLastReview = 24.0
	}
	decay := hoursSinceLastReview * decayRate

	rfi := locScore + workloadScore - decay
	if rfi < 0 {
		return 0.0
	}
	return rfi
}

// Proses Event Pull Request Masuk (Assign SLA Timer & Track Workload)
func (fe *FatigueEngine) HandlePROpened(ctx context.Context, payload PullRequestPayload, assignedReviewer string) error {
	fe.mu.Lock()
	defer fe.mu.Unlock()

	reviewer, exists := fe.reviewers[assignedReviewer]
	if !exists {
		reviewer = &ReviewerProfile{
			Username:       assignedReviewer,
			LastReviewTime: time.Now().Add(-24 * time.Hour),
		}
		fe.reviewers[assignedReviewer] = reviewer
	}

	locChanged := payload.PullRequest.Additions + payload.PullRequest.Deletions
	reviewer.ActivePRCount++
	reviewer.TotalLOCReviewing += locChanged
	reviewer.CurrentRFI = fe.CalculateRFI(reviewer, 0)

	// Validasi Ambang Batas Fatigue
	if reviewer.CurrentRFI > 28.0 {
		fmt.Printf("[ALERT] Reviewer %s mengalami High Fatigue (RFI: %.2f)! Pertimbangkan re-routing.\n", 
			reviewer.Username, reviewer.CurrentRFI)
	}

	// Buat SLA Watchdog: Batas 4 Jam Kerja (Diilustrasikan 5 detik untuk test harness)
	slaKey := fmt.Sprintf("%s#%d", payload.Repository.FullName, payload.PullRequest.Number)
	fe.slaTimers[slaKey] = time.AfterFunc(5*time.Second, func() {
		fe.handleSLABreach(slaKey, assignedReviewer)
	})

	fmt.Printf("[PROCESSED] PR #%d terdaftar. Reviewer: %s, RFI Baru: %.2f\n", 
		payload.PullRequest.Number, assignedReviewer, reviewer.CurrentRFI)
	return nil
}

// Tangani Review yang Disubmit (Cancel SLA, Kurangi Workload)
func (fe *FatigueEngine) HandleReviewSubmitted(payload PullRequestPayload) error {
	fe.mu.Lock()
	defer fe.mu.Unlock()

	reviewerName := payload.Review.User.Login
	reviewer, exists := fe.reviewers[reviewerName]
	if !exists {
		return errors.New("reviewer profile not tracked")
	}

	slaKey := fmt.Sprintf("%s#%d", payload.Repository.FullName, payload.PullRequest.Number)
	if timer, ok := fe.slaTimers[slaKey]; ok {
		timer.Stop()
		delete(fe.slaTimers, slaKey)
		fmt.Printf("[SLA MET] PR #%d direview tepat waktu oleh %s\n", payload.PullRequest.Number, reviewerName)
	}

	// Perbarui state reviewer
	if reviewer.ActivePRCount > 0 {
		reviewer.ActivePRCount--
	}
	locChanged := payload.PullRequest.Additions + payload.PullRequest.Deletions
	reviewer.TotalLOCReviewing -= locChanged
	if reviewer.TotalLOCReviewing < 0 {
		reviewer.TotalLOCReviewing = 0
	}
	reviewer.LastReviewTime = time.Now()
	reviewer.CurrentRFI = fe.CalculateRFI(reviewer, 0)

	return nil
}

func (fe *FatigueEngine) handleSLABreach(slaKey string, assignedReviewer string) {
	fe.mu.Lock()
	defer fe.mu.Unlock()

	delete(fe.slaTimers, slaKey)
	fmt.Printf("[SLA BREACH CRITICAL] SLA Terlanggar untuk %s! Reviewer %s tidak merespons.\n", 
		slaKey, assignedReviewer)
	// Logika eskalasi real-time: Emisi event ke Kafka/PagerDuty/Slack Webhook
}

func main() {
	engine := NewFatigueEngine()
	ctx := context.Background()

	// Simulasi Event Ingestion
	mockEventPR := PullRequestPayload{
		Action: "opened",
	}
	mockEventPR.PullRequest.Number = 1042
	mockEventPR.PullRequest.Additions = 650
	mockEventPR.PullRequest.Deletions = 120
	mockEventPR.PullRequest.User.Login = "junior-dev"
	mockEventPR.Repository.FullName = "enterprise/payment-gateway"

	// Event 1: Assign ke Senior Lead
	_ = engine.HandlePROpened(ctx, mockEventPR, "lead-architect")

	// Tunggu timer SLA simulasi
	time.Sleep(6 * time.Second)

	// Simulasi PR kedua untuk menguji eskalasi Fatigue
	mockEventPR2 := mockEventPR
	mockEventPR2.PullRequest.Number = 1043
	_ = engine.HandlePROpened(ctx, mockEventPR2, "lead-architect")
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: PayGlobal Inc. (Fintech SuperApp Unicorn)
*   **Kondisi Awal**: 
    * 1.200 Software Engineers, 450 Microservices.
    * Standar industri mewajibkan minimal 2 approver per PR (1 Code Owner + 1 Peer).
    * Metrik DORA menunjukkan *Lead Time to Changes* memburuk dari 2 hari menjadi 11 hari.
    * Tim manajemen berasumsi bahwa bottleneck disebabkan oleh lamanya pipeline CI/CD.

*   **Audit Telemetri & Temuan Akar Masalah**:
    * Setelah telemetry collector diimplementasikan, data menunjukkan bahwa waktu CI/CD rata-rata hanya 18 menit. Bottleneck utama berada pada **P90 Time to First Review (TTFR)** yang mencapai 84 jam (3,5 hari kerja).
    * **Reviewer Skewness**: Sebanyak 72% review bergantung pada 40 orang Principal/Staff Engineers (Fenomena *Silo Review*).
    * **Fatigue Impact**: Principal Engineers memiliki skor RFI rata-rata 38,2. Ditemukan bahwa 64% review yang mereka lakukan berkategori *Rubber-Stamping* (disetujui dalam durasi $< 90$ detik untuk PR $> 500$ LOC).
    * **Insiden Produksi**: Terjadi kebocoran data kartu pembayaran karena logic bypass di layer otorisasi disetujui melalui *rubber-stamped review* oleh Lead Architect yang sedang menangani 19 PR aktif.

*   **Intervensi Arsitektur**:
    1. **Dynamic Review Throttling**: Mengunci batas penugasan maksimal 3 PR aktif secara bersamaan per engineer. Jika RFI $> 25$, sistem routing otomatis mengalihkan PR ke maintainer berikutnya.
    2. **Algoritma Auto-Sizing**: PR dengan $\Delta \text{LOC} > 400$ secara otomatis ditolak oleh GitHub Action linter (*Pre-receive enforcement*) dan diwajibkan untuk dipecah (*stacked PRs*).
    3. **SLA Tiers**: 
       * P0/Hotfix: SLA TTFR 45 menit.
       * Standar: SLA TTFR 4 jam kerja.
       * Low/Refactoring: SLA TTFR 24 jam kerja.

*   **Hasil Evaluasi Pasca 6 Bulan**:
    * P90 TTFR terpangkas sebesar 71% (dari 84 jam menjadi 6,2 jam).
    * RFI rata-rata tim inti turun dari 38,2 ke 12,4.
    * *Defect Escape Rate* (bug yang lolos ke staging/production) menurun sebesar 44%.

---

### 9. Trade-offs

Mengelola sistem penegakan metrik dan SLA code review memiliki kompromi teknis dan organisasional yang signifikan:

| Parameter | Pendekatan Ketat (Strict SLA & Throttling) | Pendekatan Fleksibel (Relaxed SLA & Manual) | Kompromi Teknis & Solusi Menengah |
| :--- | :--- | :--- | :--- |
| **Throughput vs. Thoroughness** | PR diproses sangat cepat untuk memenuhi target metrik, namun meningkatkan risiko *superficial review*. | Reviewer meneliti kode secara mendalam tanpa tekanan timer, tetapi memicu *stale PR* dan merge conflict. | Terapkan validasi berbasis **Review Depth Ratio (RDR)**. PR tidak dapat di-merge jika SLA terpenuhi tetapi nilai RDR di bawah batas kritis. |
| **Load Balancing vs. Contextual Domain** | Sistem membagi beban kerja secara merata ke seluruh engineer, tetapi reviewer baru membutuhkan waktu memahami konteks modul. | PR selalu diberikan kepada domain expert, tetapi menimbulkan bottleneck parah pada personel kunci. | Implementasikan *Tiered Routing*: Prioritaskan domain maintainer dengan RFI rendah. Alihkan ke tier sekunder hanya jika RFI tier utama melampaui batas aman. |
| **Ingestion Latency vs. Operational Cost** | Pipeline real-time menggunakan Kafka + Flink/ClickHouse memberikan feedback seketika, namun menambah biaya operasional infrastruktur. | Batch cron-job pemrosesan data review setiap 6 jam murah dan mudah dirawat, namun terlambat mendeteksi pelanggaran SLA. | Gunakan hybrid approach: Event-driven Redis pub/sub untuk deteksi SLA timeout; batched ingestion harian ke ClickHouse untuk analitik tren. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Gamifikasi Metrik ("Goodhart's Law")
* **Kesalahan**: Menjadikan kuantitas PR yang di-review atau kecepatan TTFR sebagai KPI performa individual engineer.
* **Gejala**: Reviewer membalas PR secara instan dengan komentar template ("Nice work!", "LGTM") hanya untuk menghentikan timer SLA tanpa menganalisis vulnerability atau edge case.
* **Mitigasi**: Gunakan **Compound Metrics**. TTFR tidak boleh dinilai terpisah dari *Post-Merge Defect Rate* dan *Review Depth Ratio*.

#### 2. False Alert SLA Akibat Mengabaikan Timezone dan Hari Libur
* **Kesalahan**: Menjalankan timer SLA berbasis durasi absolut (wall-clock time). PR yang dibuat hari Jumat pukul 18:00 memicu alert breach kritis pada Sabtu dini hari.
* **Solusi**: Integrasikan engine SLA dengan kalender kerja (*business hours scheduler*). Waktu di luar jam operasional tim tidak dihitung ke dalam degradasi SLA.

#### 3. Out-of-Order Webhook Delivery
* **Masalah**: Event Git host (GitHub/GitLab) dikirim secara asinkron melalui HTTP. Sering kali event `pull_request_review: approved` sampai lebih dulu ke ingestion gateway sebelum event `pull_request: opened` selesai diproses.
* **Troubleshooting**: Terapkan event resequencing berbasis sliding window dan deduplikasi state di Redis:
  ```go
  // Pseudocode penanganan Out-of-Order State
  func ProcessEvent(event GitEvent) {
      if !IsParentEntityPresent(event.PRID) {
          Redis.ZAdd("orphaned_events:"+event.PRID, event.Timestamp, event.Payload)
          return
      }
      ExecuteTransition(event)
      DrainOrphanedEvents(event.PRID)
  }
  ```

---

### 11. Best Practices (Production Checklist)

Gunakan checklist arsitektur berikut sebelum mengaktifkan enforcement metrik review di level organisasi:

- [ ] **Webhook Idempotency Layer**: Simpan dan periksa header `X-GitHub-Delivery` unik selama minimal 7 hari untuk mencegah duplikasi kalkulasi metrik.
- [ ] **Bot & Automation Isolation**: Filter seluruh aktivitas automated user (Dependabot, Snyk, Release Drafter) dari metrik RFI dan TTFR.
- [ ] **Small Pull Request Enforcement**: Pasang batasan CI/linter yang memblokir pembuatan PR melebihi 400 LOC (di luar generated code/lockfiles).
- [ ] **Business-Hours Engine**: Konfigurasikan SLA watchdog untuk menghormati zona waktu repositori/tim (misalnya 09:00 - 17:00 waktu lokal, mengecualikan akhir pekan dan hari libur nasional).
- [ ] **Dynamic Load Throttling**: Batasi penugasan reviewer otomatis maksimal 3 PR aktif secara konkuren per individu.
- [ ] **Circuit Breaker on Escalation**: Batasi laju alert eskalasi agar tidak membanjiri channel Slack/PagerDuty saat tim sedang menghadapi insiden produksi global (P1 Incident Freeze).
- [ ] **OLAP Analytics Partitioning**: Partisi tabel database analitik (misalnya ClickHouse) berdasarkan `toYYYYMM(event_date)` dan `tenant_id` untuk memastikan performa query P99 tetap di bawah 200ms.

---

### 12. Hands-on Practice

Buat struktur direktori untuk mempraktikkan telemetry collector dan fatigue calculator:

```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
go mod init review-telemetry
```

#### Langkah 1: Buat Engine Telemetri Sederhana (`main.go`)
Simpan kode berikut di `hands-on/m02/main.go`. Program ini menyediakan endpoint HTTP untuk menerima webhook dan memproses metrik RFI serta SLA:

```go
package main

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"sync"
	"time"
)

type WebhookEvent struct {
	Action      string `json:"action"`
	PullRequest struct {
		Number    int       `json:"number"`
		CreatedAt time.Time `json:"created_at"`
		Additions int       `json:"additions"`
		Deletions int       `json:"deletions"`
	} `json:"pull_request"`
	Review struct {
		SubmittedAt time.Time `json:"submitted_at"`
		Body        string    `json:"body"`
	} `json:"review"`
	Sender struct {
		Login string `json:"login"`
	} `json:"sender"`
}

type MetricsStore struct {
	mu   sync.Mutex
	data map[int]string
}

var store = &MetricsStore{data: make(map[int]string)}

func webhookHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	body, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, "Failed to read body", http.StatusBadRequest)
		return
	}

	var event WebhookEvent
	if err := json.Unmarshal(body, &event); err != nil {
		http.Error(w, "Bad JSON", http.StatusBadRequest)
		return
	}

	store.mu.Lock()
	defer store.mu.Unlock()

	loc := event.PullRequest.Additions + event.PullRequest.Deletions
	status := fmt.Sprintf("Action: %s | PR #%d | LOC: %d | User: %s", 
		event.Action, event.PullRequest.Number, loc, event.Sender.Login)
	store.data[event.PullRequest.Number] = status
	log.Println("[TELEMETRY INGESTED]:", status)

	w.WriteHeader(http.StatusAccepted)
	w.Write([]byte(`{"status":"queued"}`))
}

func main() {
	http.HandleFunc("/webhook", webhookHandler)
	log.Println("Telemetry Receiver running on port 8080...")
	if err := http.ListenAndServe(":8080", nil); err != nil {
		log.Fatal(err)
	}
}
```

#### Langkah 2: Jalankan dan Uji Telemetry Receiver
Jalankan server telemetri di terminal pertama:
```bash
go run main.go
```

Buka terminal kedua dan kirimkan simulasi event webhook GitHub:
```bash
curl -X POST http://localhost:8080/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "action": "opened",
    "pull_request": {
      "number": 101,
      "created_at": "2026-03-30T10:00:00Z",
      "additions": 230,
      "deletions": 45
    },
    "sender": {
      "login": "octocat"
    }
  }'
```

Output log terminal pertama akan mengonfirmasi pencatatan event:
```text
[TELEMETRY INGESTED]: Action: opened | PR #101 | LOC: 275 | User: octocat
```

---

### 13. Exercise

#### Tingkat Easy
Modifikasi implementasi pada `hands-on/m02/main.go` untuk menghitung durasi waktu antara `created_at` pada PR dan `submitted_at` pada Review event untuk PR yang sama. Cetak nilai `TTFR (detik)` ke konsol.

#### Tingkat Medium
Buat struktur in-memory *Sliding Window Rate Limiter* dalam Go yang melacak jumlah penugasan review seorang engineer dalam kurun waktu 24 jam terakhir. Jika seorang reviewer telah ditugaskan lebih dari 5 PR dalam window tersebut, sistem harus mengembalikan error `ReviewerCapacityExceededException`.

#### Tingkat Hard
Bangun model kalkulasi SLA berbasis state-machine yang mencakup:
1. Pengecualian waktu di luar jam kerja (hanya operasional Senin–Jumat, 09:00 - 18:00).
2. Mekanisme jeda (*pause*) timer SLA jika PR diubah statusnya menjadi `draft` atau diberikan label `waiting-for-author`.
3. Timer otomatis melanjutkan perhitungan (*resume*) saat status dikembalikan ke `ready_for_review`.

---

### 14. Challenge

**Skenario Sistem Penugasan Anti-Fatigue Global Multi-Tenant**:

Anda adalah Principal Systems Architect di sebuah korporasi SaaS dengan 4.000 engineer yang tersebar di 3 zona waktu (APAC, EMEA, US).
*   Sistem Git enterprise menghasilkan sekitar 12.000 event PR dan Review setiap jamnya.
*   Terjadi krisis kualitas kode: bug lolos ke level *release branch* meningkat 60% dalam 2 kuartal terakhir. Investigasi awal menunjukkan Lead Engineer di EMEA mengalami kejenuhan luar biasa karena harus me-review kode dari tim APAC saat pagi hari dan tim US saat sore hari.

**Tugas Arsitektural**:
1. Rancang arsitektur pipeline terdistribusi toleran kesalahan (*fault-tolerant*) menggunakan diagram sequence dan spesifikasi komponen untuk memproses seluruh webhook event secara real-time.
2. Tuliskan algoritma alokasi tugas reviewer adaptif (*Adaptive Dynamic Router*) dengan batasan:
   * Menjamin kepatuhan SLA TTFR P95 $< 3$ jam kerja.
   * Menjaga Reviewer Fatigue Index (RFI) harian setiap engineer di bawah ambang batas kritis ($\text{RFI} \le 20$).
   * Menghindari alokasi lintas zona waktu kecuali jika seluruh reviewer di zona lokal telah melampaui batas saturasi beban kognitif.
3. Tentukan mekanisme failover jika message broker mengalami partisi jaringan (*split-brain*) atau lag konsumsi data lebih dari 15 menit.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda / Konseptual Singkat)
1. **Apa definisi presisi dari Time to First Review (TTFR)?**
   * A. Waktu dari commit pertama dibuat hingga PR disetujui (*approved*).
   * B. Waktu dari PR dibuka atau diset menjadi `ready_for_review` hingga review/komentar substantif pertama masuk dari non-author.
   * C. Total durasi siklus CI pipeline dieksekusi pertama kali.
   * D. Waktu yang dibutuhkan reviewer untuk menekan tombol *merge*.

2. **Mengapa penambahan baris kode ($\Delta \text{LOC}$) pada formula Fatigue kognitif menggunakan pemodelan fungsi logaritmik ($\ln$) dan bukan linier murni?**
   * A. Karena compiler membaca kode secara non-linier.
   * B. Karena dampak kognitif penambahan baris kode bertambah secara marginal; memeriksa 1.000 baris kode tidak membutuhkan energi kognitif 10 kali lipat dari 100 baris, melainkan memicu kejenuhan (*rubber-stamping threshold*).
   * C. Agar nilai metrik selalu berada pada rentang bilangan bulat kecil.
   * D. Karena Git diff hanya memproses data secara eksponensial.

3. **Apa indikasi utama dari fenomena *LGTM Rubber-Stamping* jika dilihat dari metrik kuantitatif?**
   * A. TTFR bernilai sangat tinggi dan PR memiliki komentar diskusi panjang.
   * B. Review Iteration Count (RIC) bernilai lebih dari 5 siklus.
   * C. Delta LOC bernilai besar, waktu submit review sangat cepat, dan Review Depth Ratio (RDR) mendekati nol.
   * D. PR ditolak secara berulang oleh security scanner.

4. **Metrik mana yang paling akurat dalam mendeteksi adanya miskomunikasi arsitektur antara pembuat PR dan reviewer?**
   * A. Review Iteration Count (RIC) yang tinggi.
   * B. Time to First Review (TTFR) yang rendah.
   * C. Rendahnya jumlah event webhook yang diterima.
   * D. Ukuran payload JSON pada webhook.

5. **Apa fungsi utama dari header signature `X-Hub-Signature-256` pada pipeline telemetri review?**
   * A. Melakukan kompresi data JSON payload.
   * B. Memvalidasi integritas dan keaslian payload webhook menggunakan shared secret HMAC-SHA256 agar sistem tidak menerima injeksi event palsu.
   * C. Menyimpan ID unik commit Git.
   * D. Mengukur latency jaringan antara Git host dan ingestion engine.

#### Bagian 2: Intermediate (Analisis Arsitektur & Penerapan Logika)
6. **Dalam kalkulasi SLA yang akurat, mengapa *Wall-Clock Time* murni tidak dapat digunakan untuk mengevaluasi metrik performa review tim? Jelaskan dampaknya terhadap kesejahteraan tim.**
7. **Bagaimana cara mengisolasi *noise* data metrik yang disebabkan oleh automated bot seperti Dependabot atau Renovate agar tidak mendistorsi P50 TTFR tim?**
8. **Jelaskan risiko arsitektur jika penugasan reviewer otomatis (*auto-assign*) hanya didasarkan pada git blame / commit authorship historis modul tanpa memasukkan variabel beban kerja saat ini.**
9. **Sebutkan minimal dua strategi rekonsiliasi data jika webhook event untuk event `review_submitted` tiba lebih dahulu daripada event `pr_created` akibat anomali routing jaringan.**
10. **Bagaimana formula Review Depth Ratio (RDR) mencegah praktik manipulasi metrik oleh reviewer yang berniat mengakali sistem SLA?**

#### Bagian 3: Production Case Scenarios (Studi Kasus Arsitektural Nyata)
11. **Skenario 1 (The Review Queue Bottleneck)**:
    Tim Core Backend beranggotakan 2 orang Principal Engineer dan 12 Junior/Mid Engineers. P95 Cycle Time tim mencapai 9 hari. Data telemetri menunjukkan bahwa 95% PR mengantre pada status "Awaiting Review" yang ditujukan kepada 2 orang Principal tersebut. Bagaimana Anda merancang sistem multi-tier routing review untuk memecahkan bottleneck ini tanpa menurunkan standar governance arsitektur sistem?
12. **Skenario 2 (The SLA Gaming Anomaly)**:
    Manajemen memberlakukan SLA wajib: "Seluruh PR harus mendapatkan first review dalam tempo $< 2$ jam". Setelah 1 bulan, dashboard menunjukkan TTFR P90 sebesar 45 menit (SLA tercapai 100%). Namun, insiden regresi sistem di staging meningkat tajam sebesar 80%. Tunjukkan bagaimana pipeline telemetri Anda membuktikan bahwa regresi ini adalah akibat langsung dari kebijakan SLA yang salah arah!
13. **Skenario 3 (Telemetry Pipeline Kafka Consumer Lag Spikes)**:
    Setiap hari Senin pukul 09:30, puluhan tim rekayasa melakukan sync mingguan dan membuka ribuan PR secara bersamaan. Telemetry engine berbasis consumer worker mengalami lag antrean hingga 4 jam, menyebabkan data dashboard SLA kadaluwarsa dan memicu ratusan false-positive escalation alert. Solusi arsitektural apa yang harus diimplementasikan pada layer buffering dan processing engine?

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Bagian 1: Basic
1. **B** — Waktu dari saat PR siap ditinjau hingga reviewer independen pertama memberikan umpan balik substantif.
2. **B** — Pertambahan baris kode memberikan beban kognitif marginal yang melambat, memicu penurunan fokus secara signifikan setelah ambang batas tertentu.
3. **C** — Kombinasi perubahan kode masif dengan waktu review instan dan nihilnya komentar analitis merupakan indikasi kuat rubber-stamping.
4. **A** — Review Iteration Count (RIC) yang tinggi menandakan revisi berulang-ulang akibat ketidaksepakatan atau ketidakjelasan requirement teknis.
5. **B** — HMAC-SHA256 memverifikasi bahwa webhook benar-benar dikirimkan oleh Git host yang terdaftar, melindungi API ingress dari data tampering.

#### Bagian 2: Intermediate
6. **Jawaban**: Menggunakan wall-clock time murni akan menghitung malam hari, akhir pekan, dan hari libur ke dalam SLA review. Hal ini menciptakan metrik palsu (false breach) dan memicu stres kerja berlebih (burnout) karena engineer merasa dipaksa memantau PR di luar jam kerja resmi. Solusinya adalah business-hours window engine.
7. **Jawaban**: Terapkan filter di layer ingress worker: abaikan payload jika user memiliki flag `type: "Bot"` atau nama akun cocok dengan regex pola bot (`.*\[bot\]`, `renovate`, `dependabot`). Pisahkan penyimpanan metrik automation PR ke dalam partisi database yang berbeda.
8. **Jawaban**: Hanya mengandalkan git blame akan membebani kontributor historis terbesar secara berulang (membentuk titik kegagalan tunggal / SPOF), mengabaikan fakta bahwa engineer tersebut mungkin sedang berada dalam kondisi overload (*High RFI*) atau sedang memimpin inisiatif kritis lainnya.
9. **Jawaban**: 
   * (a) Menyimpan event anak (`review_submitted`) dalam cache sementara (Redis sorted set / Dead Letter Queue berdurasi TTL pendek) hingga event induk terdaftar, lalu memicu proses ulang.
   * (b) Melakukan query balik (*active fetch fallback*) ke GraphQL API host Git untuk memverifikasi dan menginstansiasi state PR induk secara real-time.
10. **Jawaban**: RDR mengukur rasio jumlah karakter dan kedalaman komentar terhadap delta LOC yang diubah. Jika reviewer hanya menulis review template singkat seperti "LGTM", nilai RDR tetap nol, sehingga reviewer tidak dapat memanipulasi metrik kualitas review.

#### Bagian 3: Skenario Kasus Produksi
11. **Panduan Jawaban Skenario 1**:
    * Implementasi **Tiered Code Ownership**:
      * Tier 1 (Syntactic & Style): Diotomatisasi penuh menggunakan CI Linter dan AI Code Review Assistant.
      * Tier 2 (Domain Implementation): Didelegasikan secara acak ke sesama Mid/Junior Engineers (*Peer Review*) untuk transfer pengetahuan.
      * Tier 3 (Architectural/Security Impact): Principal Engineer hanya di-assign jika PR menyentuh core schema, contract interface, atau shared library.
    * Terapkan ambang batas konfirmasi otomatis (*Auto-approval bypass*) untuk refactor trivial di bawah 50 LOC.
12. **Panduan Jawaban Skenario 2**:
    * Buat korelasi multi-metrik analitik: Gabungkan grafik **TTFR vs. Review Depth Ratio (RDR)** dan **Time-Spent-Reviewing**.
    * Tunjukkan data bahwa pasca-kebijakan SLA 2 jam berlaku:
      * Durasi antara pembukaan PR hingga approve menurun drastis dari 40 menit menjadi 35 detik.
      * RDR anjlok dari 1,8% menjadi 0,05%.
      * Kata-kata dalam komentar didominasi oleh kata persetujuan tanpa diskusi kritis.
    * Kesimpulan empiris: Tim mengorbankan kualitas review demi mengejar metrik TTFR superfisial, yang menyebabkan defect lolos dan merusak stabilitas staging.
13. **Panduan Jawaban Skenario 3**:
    * Terapkan strategi partisi Kafka berbasis `hash(repository_id)` untuk memastikan paralelisasi worker.
    * Tingkatkan jumlah partisi topic dan scale-out Telemetry Consumer pods secara dinamis menggunakan KEDA (Kubernetes Event-driven Autoscaling) berbasis metric `kafka_consumergroup_lag`.
    * Pisahkan antrean: Buat antrean terpisah untuk event pembukaan PR (`pr_opened`) dan event pelengkap telemetry ringan (`review_comment_created`) agar event pembukaan PR tidak terhambat oleh event komentar massal.
    * Terapkan circuit breaker sementara pada alert SLA saat consumer lag terdeteksi berada di atas batas toleransi.

---

### 16. Summary

1. **Metrik Bukan Sekadar Angka Rata-Rata**: Pendekatan modern code review mengandalkan distribusi persentil (P50, P90, P99) dan kombinasi metrik (TTFR, RDR, RIC) untuk mendapatkan pemahaman holistik atas siklus review tanpa bias angka rata-rata (*mean skew*).
2. **Kognisi Adalah Sumber Daya Terbatas**: *Review Fatigue* dapat diukur secara empiris. Membebani Staff/Principal Engineers dengan volume review yang tinggi tanpa filter kompleksitas secara langsung memicu *LGTM rubber-stamping* dan meningkatkan tingkat kebocoran bug (*defect escape*).
3. **SLA Adaptif Mengalahkan SLA Kaku**: SLA review yang efektif harus memperhitungkan risiko PR, jam kerja riil, kalender libur tim, dan kompleksitas kode. SLA yang kaku hanya akan memicu manipulasi sistem dan mengorbankan kualitas demi kecepatan semu.
4. **Arsitektur Telemetri Terisolasi**: Sistem pemrosesan metrik code review skala enterprise harus dibangun menggunakan arsitektur event-driven terdistribusi yang aman (HMAC verification), toleran terhadap urutan pengiriman yang tidak teratur (*out-of-order reconciliation*), dan tidak membebani pipeline CI/CD utama.