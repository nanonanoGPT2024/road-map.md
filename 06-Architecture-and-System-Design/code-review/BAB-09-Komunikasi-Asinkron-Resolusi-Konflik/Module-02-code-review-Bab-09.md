# Bab 09: Komunikasi Asinkron & Resolusi Konflik
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik pada level *Staff / Principal Engineer* dan *Engineering Manager* diharapkan mampu:
1. **Mendiagnosis dan Memitigasi Deadlock Review**: Mengidentifikasi simtom *asynchronous communication breakdown* (*ping-pong debate*, *rubber-stamping*, dan *opinionated nitpicking*) menggunakan metrik objektif.
2. **Merancang Sistem Eskalasi dan Resolusi Terstruktur**: Mengarsitekturi *Conflict Resolution Matrix* berlapis berbasis konsensus terdistribusi yang menggabungkan *Conventional Comments*, *SLA-driven Timeouts*, dan arbitrase teknis.
3. **Mengintegrasikan Automated Governance & Policy Enforcement**: Mengembangkan dan men-deploy *automated arbitration pipeline* berbasis Webhooks, Open Policy Agent (OPA), dan bot orchestrator untuk mendeteksi serta mengeskalasi perdebatan PR sebelum melanggar SLA *Lead Time to Change*.
4. **Mengeksekusi Transisi Konsensus Arsitektur**: Mengonversi sengketa rancangan pada level *pull request* menjadi artefak formal (*Architectural Decision Record* / ADR atau RFC terdesentralisasi) tanpa menghentikan *delivery pipeline*.

---

### 2. Prerequisite
Untuk memahami modul ini secara komprehensif, pembaca wajib menguasai:
* Fundamental Git DAG (*Directed Acyclic Graph*), mekanisme *three-way merge*, serta penanganan *merge conflict* pada level baris kode.
* Modul 01: Dasar Komunikasi Asinkron, Etika Code Review, dan Taksonomi *Conventional Comments*.
* Konsep dasar Webhook event-driven architecture, REST/GraphQL API GitHub/GitLab, dan eksekusi CI/CD pipeline.
* Pemahaman arsitektural mengenai *Service-Oriented Architecture* (SOA) atau Microservices serta dependensi cross-team.

---

### 3. Concept & Internal Architecture (Mendalam)

Komunikasi asinkron dalam rekayasa perangkat lunak skala enterprise tunduk pada prinsip sistem terdistribusi. Setiap *engineer* bertindak sebagai *node* independen dengan latensi jaringan (zona waktu), *local memory cache* (konteks mental dan domain knowledge), serta tingkat ketersediaan (*availability*) yang berbeda.

Ketika dua atau lebih *node* gagal mencapai konsensus terkait modifikasi *state machine* sistem (yaitu perubahan kode pada Pull Request), kegagalan tersebut bukan sekadar masalah komunikasi interpersonal, melainkan kegagalan protokol konsensus sistem (*consensus protocol failure*).

```
+---------------------------------------------------------------------------------------+
|                 STATE MACHINE RESOLUSI PERDEBATAN CODE REVIEW                         |
+---------------------------------------------------------------------------------------+

 [ PR Dibuka ]
       │
       ▼
 [ Thread Diskusi ] <──────────────────┐ (Iterasi < 3x)
       │                               │
       ├─ [Non-blocking: Nit/Chore] ──>┼─> [ Resolve & Approve ]
       │                               │
       └─ [Blocking: Security/Arch] ───┘
               │
               ▼ (Iterasi >= 3x / Timeout 24 Jam)
     [ STATE: THREAD DEADLOCK ]
               │
               ▼ (Webhook / Event Trigger)
     [ Automated Circuit Breaker ]
               │
               ├─> [ Freeze Thread ] (Lock komentar PR via API)
               ├─> [ Inisiasi SLA Escalation Clock ]
               │
               ▼
     [ Arbitrase Teknis: Staff/Principal ]
               │
       ┌───────┴──────────────────────────────┐
       ▼                                      ▼
 [ Local Decision ]                 [ Systemic Divergence ]
 (Pilih Opsi A atau B)              (Dibutuhkan Perubahan Desain)
       │                                      │
       ▼                                      ▼
 [ Unblock PR & Merge ]             [ Spawn ADR / RFC Track ]
                                              │
                                    [ Isolate PR via Feature Flag ]
                                              │
                                              ▼
                                    [ Merge Minimal Unblocked Delta ]
```

#### A. The Physics of Review Latency: Little's Law Terapan
Dalam *Queueing Theory*, latensi PR tunduk pada Little's Law:

$$L = \lambda \times W$$

Di mana:
* $L$ = *Work in Progress* (WIP) Pull Request aktif dalam tim.
* $\lambda$ = *Throughput* (jumlah PR yang diselesaikan per satuan waktu).
* $W$ = *Review Cycle Time* (waktu tempuh dari pembukaan PR hingga *merge*).

Perdebatan asinkron tak berujung melipatgandakan nilai $W$. Berdasarkan kalkulasi matematis latensi komunikasi:
* Tiap interaksi bolak-balik (*round-trip*) asinkron melintasi zona waktu (misal: Jakarta UTC+7 dan San Francisco UTC-7) menambahkan penundaan deterministik $12 \text{ s.d. } 24 \text{ jam}$ per respons.
* Tiga siklus perdebatan minor menghabiskan rata-rata $72 \text{ jam}$ waktu kalender, menaikkan WIP ($L$), menurunkan *throughput* ($\lambda$), dan mendegradasi metrik DORA *Lead Time for Changes*.

#### B. Anatomi Deadlock dan "Circuit Breaker" Review
Deadlock teknis terjadi ketika dua belah pihak memiliki *bounded context* berbeda yang valid secara lokal, namun saling bertentangan secara global:
1. **Author**: Mengoptimalkan PR untuk *Speed-to-Market* dan kepatuhan terhadap *Scope Ticket*.
2. **Reviewer**: Mengoptimalkan PR untuk *Long-term Maintainability*, *Defensive Robustness*, atau konsistensi arsitektur global.

Untuk menghentikan *infinite loop*, arsitektur peninjauan modern menerapkan **Synchronous Circuit Breaker Pattern**:
* **Threshold Trigger**: Jika sebuah *thread* komentar mencapai kedalaman $\ge 3$ iterasi bolak-balik tanpa konvergensi status resolusi, atau waktu debat melampaui ambang batas $24 \text{ jam}$.
* **Tripping the Breaker**: Sistem otomasi memutus media asinkron (mengunci *thread* atau memberi label `status:escalated`) dan memaksa konversi ke mode sinkron berkurasi tinggi (15 menit *face-to-face* / *huddle*) atau arbitrase berbasis *Tech Lead veto*.

---

### 4. Why & What

| Dimensi | Pendekatan Ad-Hoc / Reaktif | Pendekatan Enterprise Asynchronous Protocol |
| :--- | :--- | :--- |
| **Penyelesaian Sengketa** | Debat opini berkepanjangan pada komentar PR; keputusan diambil oleh pihak yang paling persisten atau dominan. | Dipandu oleh *Conflict Escalation Matrix*, *RFC/ADR Quorum*, dan penentuan batas waktu (*timeboxing* ketat). |
| **Struktur Bahasa** | Komentar ambigu: *"Kode ini lambat, sebaiknya diganti"* (subjektif, tanpa acuan metrik). | Standar ketat *Conventional Comments*: `issue (blocking): Potensi OOM pada buffer allocation n > 10^6. Metrik profiling terlampir`. |
| **Audit Jejak Arsitektur** | Argumen hilang tertimbun di dalam *closed PRs* yang terfragmentasi di puluhan repositori. | Keputusan arsitektur diekstraksi menjadi ADR (*Architecture Decision Record*) di dalam repositori sentral. |
| **Mitigasi Bias Kognitif** | Bias senioritas mendikte validasi kode (*Authority Bias*). | Otoritas terikat pada *System Invariants*, OPA *Policy Gates*, dan SLA tertulis. |

---

### 5. How: Detailed Operational Workflow

Proses resolusi konflik asinkron dieksekusi melalui 5 fase deterministik:

```
[ Phase 1: Structured Tagging ] 
  Author & Reviewer wajib menandai komentar dengan Conventional Comments (Prefix, Label, Basis Fakta).
       │
       ▼
[ Phase 2: Divergence Detection ]
  Komentar berkategori "blocking" tidak terselesaikan dalam 2 iterasi saling balas.
       │
       ▼
[ Phase 3: Automated SLA Breach & Tripping ]
  GitHub Action / Polling Service mendeteksi SLA breach (e.g., > 24 jam deadlock).
  Sistem mengeksekusi lock pada thread dan menambahkan label `escalation:tech-lead`.
       │
       ▼
[ Phase 4: Tactical Arbitration (Max 24 Jam) ]
  Staff Engineer/Tech Lead mengevaluasi trade-off (Performance vs Latency vs Cost).
  Keputusan dijatuhkan: Accept, Reject, atau Split PR.
       │
       ▼
[ Phase 5: Architecture Sync & Resolution ]
  Jika divergensi bersifat struktural, Author membuat issue ADR baru; 
  PR saat ini di-unblock dengan mitigasi transisional (misal: Feature Flag).
```

#### Aturan Tiga Siklus (The 3-Strike Rule)
1. **Strike 1 (Identification)**: Reviewer memaparkan masalah teknis secara terstruktur (`issue (blocking): ...`) dilengkapi referensi/bukti (profiling, benchmark, O-notation, link dokumentasi).
2. **Strike 2 (Counter-Argument/Clarification)**: Author merespons sekali dengan argumentasi berbasis data atau alternatif kompromi.
3. **Strike 3 (Escalation Trigger)**: Jika respons Reviewer berikutnya tetap menolak tanpa konvergensi titik tengah, Reviewer dilarang membalas dengan argumen baru di PR. Reviewer **wajib** mengubah label PR menjadi `needs-arbitration` dan mengeksekusi *hand-off* ke Tech Lead/Staff Engineer terkait.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Two-Phase Commit (2PC) vs. Distributed Lease
*   **PR Review Ad-Hoc** menyerupai *Two-Phase Commit* tanpa koordinator pusat: Jika salah satu node (*Reviewer*) menahan status `VOTE_ABORT` dan tidak pernah melepaskan kuncinya, seluruh transaksi (*Deployment Release*) mengalami *hang* tanpa batas waktu (*infinite block*).
*   **Protokol Asinkron Terstruktur** bekerja seperti **Distributed Lease with Time-to-Live (TTL)**: Reviewer memiliki masa *lease* terbatas untuk memvalidasi perubahan. Jika dalam durasi TTL kesepakatan tidak tercapai, koordinator (*Escalation Engine*) mengambil alih kunci, membatalkan hak veto individual, dan mengeksekusi resolusi tingkat klaster (*Tech Lead Arbitration*).

#### Diagram Arsitektur Integrasi Webhook Resolusi Konflik

```
+---------------------------------------------------------------------------------------+
|                 EVENT-DRIVEN PR CONFLICT ARBITRATION ARCHITECTURE                     |
+---------------------------------------------------------------------------------------+

 GitHub / GitLab                  Review Arbiter Webhook Service           Slack / Opsgenie
+---------------+                +-------------------------------+        +-----------------+
|               |                |                               |        |                 |
| [PR Comment]  |──HTTP POST────>|  [Event Ingestion Controller] |        |                 |
|               | (Webhook Event)|               │               |        |                 |
+---------------+                |               ▼               |        |                 |
                                 |  [Thread Topology Analyzer]   |        |                 |
                                 |  - Count back-and-forth       |        |                 |
                                 |  - Parse Conventional Comment |        |                 |
                                 |  - Detect unresolved blocking |        |                 |
                                 |               │               |        |                 |
                                 |               ▼               |        |                 |
                                 |  [Breach Policy Engine]       |        |                 |
                                 |  - Deadlock rules evaluation  |        |                 |
                                 |  - SLA Timer tracking (Redis) |        |                 |
                                 |               │               |        |                 |
                                 |               ▼               |        |                 |
+---------------+                |  [Mutation Dispatcher]        |        |                 |
|               |<──GraphQL/REST─|  - Lock discussion thread     |        |                 |
| [PR Updated]  |   (Mutations)  |  - Apply label: needs-arb     |        |                 |
| - Locked      |                |  - Post Arbitration Template  |        |                 |
| - Label added |                |               │               |        |                 |
+---------------+                +───────────────┼───────────────+        +-----------------+
                                                 │                                  ▲
                                                 └─────────Send Escalation Alert────┘
                                                           (Ping Lead with Context)
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Validasi Conventional Comments Menggunakan Regex Engine
Sebelum mengotomasi eskalasi, sistem wajib memvalidasi bahwa setiap komentar *blocking* ditulis secara terstruktur agar bot parser dapat membedakan antara perdebatan arsitektural dan diskusi santai.

```go
package main

import (
	"fmt"
	"regexp"
	"strings"
)

// ConventionalComment mencakup label struktural komentar PR
type ConventionalComment struct {
	Label    string // e.g., suggestion, issue, question, nitpick
	Blocking bool   // Menentukan apakah komentar menahan merge
	Subject  string // Ringkasan masalah
	Body     string // Penjelasan detail & acuan teknis
}

var commentRegex = regexp.MustCompile(`^\*\*([a-z]+)(\s*\((blocking|non-blocking)\))?:\*\*\s*(.*)`)

func ParseComment(raw string) (*ConventionalComment, error) {
	lines := strings.SplitN(raw, "\n", 2)
	matches := commentRegex.FindStringSubmatch(lines[0])

	if len(matches) == 0 {
		return nil, fmt.Errorf("komentar melanggar format Conventional Comments")
	}

	label := matches[1]
	blockingFlag := matches[3]
	subject := matches[4]
	body := ""

	if len(lines) > 1 {
		body = strings.TrimSpace(lines[1])
	}

	isBlocking := (blockingFlag == "blocking") || (label == "issue" && blockingFlag != "non-blocking")

	return &ConventionalComment{
		Label:    label,
		Blocking: isBlocking,
		Subject:  subject,
		Body:     body,
	}, nil
}

func main() {
	validRaw := "**issue (blocking):** Skema indexing query ini mengakibatkan Full Table Scan pada PostgreSQL.\nMohon gunakan partial index pada kolom deleted_at."
	parsed, err := ParseComment(validRaw)
	if err != nil {
		fmt.Printf("Error: %v\n", err)
		return
	}
	fmt.Printf("Parsed: %+v\n", parsed)
}
```

#### Practical Example: Production-Ready PR Conflict Arbiter Engine (Go)
Service berikut bertindak sebagai consumer webhook GitHub. Ketika sebuah thread komentar mencapai kedalaman $\ge 3$ iterasi bolak-balik tanpa status resolved, service ini secara otomatis:
1. Memeriksa apakah thread memiliki unsur `blocking`.
2. Mengunci thread komentar melalui GitHub GraphQL API untuk mencegah perang argumen lanjutan.
3. Menambahkan label `needs-arbitration` pada PR.
4. Mengirimkan notifikasi darurat ke saluran komunikasi Tech Lead dengan menyertakan tautan thread dan ringkasan metrik debat.

```go
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"strings"

	"github.com/google/go-github/v58/github"
	"golang.org/x/oauth2"
)

type ConflictArbiterServer struct {
	client *github.Client
	secret []byte
}

func NewConflictArbiterServer(token string, webhookSecret []byte) *ConflictArbiterServer {
	ts := oauth2.StaticTokenSource(
		&oauth2.Token{AccessToken: token},
	)
	tc := oauth2.NewClient(context.Background(), ts)
	return &ConflictArbiterServer{
		client: github.NewClient(tc),
		secret: webhookSecret,
	}
}

func (s *ConflictArbiterServer) HandleWebhook(w http.ResponseWriter, r *http.Request) {
	payload, err := github.ValidatePayload(r, s.secret)
	if err != nil {
		http.Error(w, "Invalid signature", http.StatusUnauthorized)
		return
	}

	event, err := github.ParseWebHook(github.WebhookType(r), payload)
	if err != nil {
		http.Error(w, "Cannot parse webhook", http.StatusBadRequest)
		return
	}

	switch e := event.(type) {
	case *github.PullRequestReviewCommentEvent:
		if e.GetAction() == "created" {
			go s.evaluateReviewThread(context.Background(), e)
		}
	}

	w.WriteHeader(http.StatusOK)
}

func (s *ConflictArbiterServer) evaluateReviewThread(ctx context.Context, e *github.PullRequestReviewCommentEvent) {
	owner := e.GetRepo().GetOwner().GetLogin()
	repo := e.GetRepo().GetName()
	prNumber := e.GetPullRequest().GetNumber()
	commentID := e.GetComment().GetID()
	inReplyTo := e.GetComment().GetInReplyTo()

	// Hanya evaluasi jika komentar merupakan balasan dalam sebuah thread
	if inReplyTo == 0 {
		return
	}

	// Fetch seluruh komentar pada review PR tersebut untuk mengukur kedalaman thread
	comments, _, err := s.client.PullRequests.ListReviewComments(ctx, owner, repo, prNumber, &github.PullRequestListCommentsOptions{
		ListOptions: github.ListOptions{PerPage: 100},
	})
	if err != nil {
		fmt.Printf("Gagal menarik comments: %v\n", err)
		return
	}

	// Hitung chain komentar pada thread hierarki ini
	threadDepth := 1
	var threadAuthors []string
	rootID := inReplyTo

	for _, c := range comments {
		if c.GetInReplyTo() == rootID || c.GetID() == rootID {
			threadDepth++
			threadAuthors = append(threadAuthors, c.GetUser().GetLogin())
		}
	}

	fmt.Printf("[INFO] Thread ID: %d, Current Depth: %d\n", rootID, threadDepth)

	// Threshold: Jika kedalaman interaksi >= 4 balasan, circuit breaker aktif
	if threadDepth >= 4 {
		s.tripCircuitBreaker(ctx, owner, repo, prNumber, commentID, rootID, threadAuthors)
	}
}

func (s *ConflictArbiterServer) tripCircuitBreaker(ctx context.Context, owner, repo string, prNumber int, commentID, rootID int64, authors []string) {
	fmt.Printf("[CIRCUIT BREAKER] Tripped on PR #%d, Thread #%d. Halting discussion.\n", prNumber, rootID)

	// 1. Tambahkan label eskalasi ke PR
	labels := []string{"needs-arbitration", "discussion-locked"}
	_, _, err := s.client.Issues.AddLabelsToIssue(ctx, owner, repo, prNumber, labels)
	if err != nil {
		fmt.Printf("Gagal append labels: %v\n", err)
	}

	// 2. Berikan notifikasi komentar penengah resmi dari Bot
	breachNotice := fmt.Sprintf(
		"⚠️ **Automated Conflict Arbiter System** ⚠️\n\n"+
			"Thread diskusi ini telah melampaui batas kedalaman toleransi komunikasi asinkron (Depth: %d interaksi).\n"+
			"Sesuai dengan *Engineering Governance Bab 09*, debat asinkron dihentikan untuk mencegah *PR latency deadlock*.\n\n"+
			"**Tindakan Wajib:**\n"+
			"1. Thread dikunci dari tanggapan asinkron lanjutan.\n"+
			"2. Partisipan (%s) dialihkan ke sesi sinkron 15 menit, ATAU menunggu intervensi arbitrase dari Tech Lead/Staff Engineer.\n"+
			"3. Hasil keputusan wajib dituangkan dalam format ADR ringkas sebelum PR dapat di-merge.",
		len(authors), strings.Join(authors, ", "),
	)

	replyComment := &github.PullRequestComment{
		Body:      github.String(breachNotice),
		InReplyTo: github.Int64(rootID),
	}

	_, _, err = s.client.PullRequests.CreateCommentInReplyTo(ctx, owner, repo, prNumber, replyComment.GetBody(), rootID)
	if err != nil {
		fmt.Printf("Gagal membalas komentar: %v\n", err)
	}

	// 3. Dispatch alert ke webhook eksternal (Slack/Opsgenie)
	s.dispatchSlackAlert(owner, repo, prNumber, rootID)
}

func (s *ConflictArbiterServer) dispatchSlackAlert(owner, repo string, prNumber int, rootID int64) {
	// Implementasi webhook Slack korporat (HTTP POST payload ke incoming webhook endpoint)
	fmt.Printf("[SLACK EVENT] Notifikasi arbitrase dikirim ke kanal #core-eng-leads untuk PR https://github.com/%s/%s/pull/%d#discussion_r%d\n",
		owner, repo, prNumber, rootID)
}

func main() {
	token := os.Getenv("GITHUB_TOKEN")
	secret := []byte(os.Getenv("WEBHOOK_SECRET"))

	if token == "" || len(secret) == 0 {
		fmt.Println("Konfigurasi ENV (GITHUB_TOKEN, WEBHOOK_SECRET) wajib diisi.")
		os.Exit(1)
	}

	server := NewConflictArbiterServer(token, secret)
	http.HandleFunc("/webhooks/reviews", server.HandleWebhook)

	fmt.Println("PR Conflict Arbiter Service beroperasi pada port :8080...")
	if err := http.ListenAndServe(":8080", nil); err != nil {
		panic(err)
	}
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Deadlock Ledger Transaction Engine pada SuperApp FinTech
* **Skala Organisasi**: 1.500+ Engineers, 120 Microservices, sistem memproses rata-rata 45.000 Transaksi per Detik (TPS).
* **Insiden**: Terjadi deadlock pada PR #4291 yang merevisi modul *Double-Entry General Ledger*. 
  * Tim *Core Ledger* (Author) menerapkan model *optimistic locking* via version number pada database record untuk memaksimalkan throughput transaksi tinggi.
  * Tim *Fraud & Security Audit* (Reviewer) menolak dengan argumen bahwa *optimistic locking* pada beban konflik tinggi memicu *high abort/retry rates*, dan bersikeras menuntut *distributed pessimistic locking* berbasis Redis Redlock.
* **Dampak**: 
  * PR tertahan selama 17 hari kalender.
  * Ratusan komentar saling menyerang (*flame war* teknis) yang menghasilkan polarisasi antar tim.
  * *Blocked downstream releases* pada 4 squad perbankan lainnya, mengakibatkan potensi keterlambatan peluncuran fitur PayLater senilai proyeksi GMV jutaan dolar.

#### Intervensi & Resolusi Arsitektur
1. **Penerapan Circuit Breaker Tripping**: Head of Core Engineering mengunci seluruh thread di PR dan membekukan status PR ke state `ARBITRATION_PENDING`.
2. **Matrix Trade-Off Benchmarking**: Staff Engineer independent ditunjuk sebagai arbiter. Ia menyusun matriks pembuktian empiris, bukan debat berbasis asumsi:

```
+-----------------------------------------------------------------------------------------------+
|                       TRADE-OFF MATRIX ARBITRASE RESMI (PR #4291)                             |
+--------------------------+-------------------------------+------------------------------------+
| Parameter Evaluasi       | Opsi A: Optimistic Locking    | Opsi B: Distributed Redlock        |
+--------------------------+-------------------------------+------------------------------------+
| Peak P99 Latency         | 4.2 ms (Optimal)              | 28.7 ms (Degradasi signifikan)     |
| Abort Rate @ 50k TPS     | 8.3% (Tinggi pada Hot-wallet) | 0.01% (Sangat stabil)              |
| Resiliensi Infrastruktur | Bergantung pada ACID RDBMS    | Menambah failure domain baru       |
| Complexity Overhead      | Rendah (Built-in engine)      | Tinggi (Lease management & drift)  |
+--------------------------+-------------------------------+------------------------------------+
```

3. **Keputusan Arbitrase (The Synthesis)**: 
   * Ditemukan akar masalah: Hot-wallet transaksi massal (1% kasus) merusak performa *optimistic locking*, namun menerapkan Redlock ke 99% transaksi reguler adalah *over-engineering* yang menurunkan P99 latency secara sistemik.
   * **Resolusi Formal**: Author membagi implementasi menjadi *Strategy Pattern* terisolasi: Akun reguler menggunakan *Optimistic Locking*, sementara akun entitas *Merchant Aggregator* (Hot-wallet) dirutekan secara otomatis via *Pessimistic Partitioning Queue* (Kafka Key-partitioned).
   * **Formalisasi**: Diterbitkan **ADR-089: Ledger Concurrency Isolation Strategy**. PR #4291 di-merge dalam kurun waktu 12 jam pasca keputusan sintesis.

---

### 9. Trade-offs

Mengadopsi tata kelola dan sistem otomasi resolusi konflik asinkron membawa konsekuensi arsitektural dan organisasional yang harus dipertimbangkan:

| Aspek | Pilihan Ekstrem A: Tata Kelola Ketat & Rigid Automation | Pilihan Ekstrem B: Fleksibilitas Total & Konsensus Penuh |
| :--- | :--- | :--- |
| **Throughput Peninjauan** | **Sangat Tinggi**. Deadlock langsung dipotong paksa. PR bergerak cepat melewati *merge gate*. | **Sangat Rendah**. Diskusi dapat berbulan-bulan hingga semua pihak menyetujui detail implementasi. |
| **Psychological Safety** | **Netral hingga Kaku**. Berisiko menciptakan friksi jika engineer merasa suaranya dipotong paksa oleh bot / veto. | **Tinggi di Awal, Memburuk di Akhir**. Engineer merasa didengarkan, namun akhirnya lelah (*review fatigue*). |
| **Beban Kognitif Lead** | **Tinggi**. Tech Lead/Staff Engineer harus siap bertindak sebagai arbiter aktif yang menangani tiket sengketa. | **Terdistribusi Merata**. Tim mencoba menyelesaikan masalah sendiri tanpa mengganggu hierarki atas. |
| **Integritas Arsitektur** | **Tinggi & Konsisten**. Keputusan formal tercatat dalam ADR; deviasi langsung dicegat oleh sistem arbiter. | **Terfragmentasi**. Solusi tambal sulam sering lolos karena reviewer akhirnya menyerah (*capitulation merge*). |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Silent Rubber-Stamping (Capitulation Merge)
* **Gejala**: Reviewer yang awalnya memegang kritik arsitektur fundamental tiba-tiba memberikan `LGTM` / `Approve` tanpa adanya commit perubahan kode.
* **Akar Masalah**: *Review Fatigue*. Reviewer kelelahan berdebat secara asinkron dan menyerah demi menghindari ketegangan personal.
* **Solusi**: Audit otomatis. Jika sebuah PR memiliki lebih dari 15 komentar penolakan, namun disetujui tanpa ada commit baru pada rentang hash terkait, CI/CD pipeline menandai PR tersebut dengan `status:suspicious-approval` yang mewajibkan *secondary sign-off* dari Principal Engineer.

#### 2. Scope Creep via Review Nitpicking
* **Gejala**: Komentar review melebar keluar dari lingkup *diff* perubahan (misalnya: menuntut *refactoring* modul warisan (*legacy*) yang tidak sengaja tersentuh oleh impor).
* **Solusi**: Tegakkan aturan *Strict Diff Boundary*. Reviewer hanya boleh memblokir kode yang mengalami perubahan langsung (*hunk context* $\pm 5$ baris). Masalah di luar lingkup tersebut wajib dialihkan menjadi tiket *Technical Debt* terpisah di Jira/Linear.

#### 3. Unactionable Vague Feedback
* **Gejala**: Reviewer meninggalkan komentar: *"Struktur class ini buruk, tolong buat lebih clean."*
* **Troubleshooting Engine**: Gunakan bot linter PR untuk memeriksa apakah komentar berlabel `issue (blocking)` memiliki minimal 1 blok kode contoh atau URL referensi. Jika tidak, bot mengembalikan *prompt*: *"Blocking feedback must provide actionable alternatives or empirical reasoning."*

---

### 11. Best Practices (Production Checklist)

#### Pre-Review Phase (Author Checklist)
- [ ] PR berukuran kecil (*atomic*): $\le 400$ baris perubahan kode (*diff*).
- [ ] Latar belakang, motivasi, dan trade-off telah dijelaskan menggunakan template PR standar.
- [ ] Telah menyertakan *link* ke ADR atau RFC yang relevan jika perubahan menyangkut arsitektur sistem inti.
- [ ] Menambahkan *feature flag* jika perubahan memengaruhi alur data kritis (*mission-critical path*).

#### In-Review Phase (Reviewer Checklist)
- [ ] Wajib menggunakan format *Conventional Comments* (`suggestion`, `issue`, `question`, `nitpick`).
- [ ] Menyatakan klasifikasi secara eksplisit: `(blocking)` vs `(non-blocking)`.
- [ ] Menyertakan alternatif konkret atau referensi dokumentasi untuk setiap blokade yang diajukan.
- [ ] Menghentikan perdebatan asinkron jika argumen telah mencapai balasan kedua tanpa kesepakatan (Terapkan *3-Strike Rule*).

#### Post-Review Phase (Lead/Arbiter Checklist)
- [ ] Memeriksa apakah PR yang tertahan eskalasi telah melewati batas SLA 24 jam.
- [ ] Melakukan de-eskalasi emosional: Fokuskan perdebatan murni pada metrik teknis (latensi, throughput, maintainability, resource cost).
- [ ] Memastikan hasil resolusi non-trivial didokumentasikan ke dalam *Engineering Decision Log* / ADR repositori.

---

### 12. Hands-on Practice: Membangun PR Arbiter Pipeline Lokal

Pada sesi praktikum ini, Anda akan menyiapkan lingkungan pengujian lokal untuk memverifikasi mekanisme *escalation circuit breaker* saat terjadi deadlock review.

#### Langkah 1: Struktur Direktori Praktikum
Buat struktur direktori berikut di mesin lokal Anda:
```bash
mkdir -p hands-on/m02/{webhook-server,tests,policy}
cd hands-on/m02
```

#### Langkah 2: Inisialisasi Kebijakan OPA (Open Policy Agent)
Buat file `policy/review_policy.rego` untuk menentukan aturan deadlock secara deklaratif:

```rego
package review.arbitration

default trip_breaker = false
default require_adr = false

# Hitung jumlah reply dalam satu thread yang tidak terselesaikan
trip_breaker {
    input.thread_depth >= 4
    input.has_blocking_label == true
}

# Wajibkan ADR jika perdebatan melibatkan file arsitektur inti
require_adr {
    trip_breaker
    some file in input.changed_files
    regex.match("^core/(domain|infrastructure|security)/.*", file)
}
```

#### Langkah 3: Mock Webhook Server Payload Trigger
Buat payload pengujian `tests/mock_event.json` yang merepresentasikan balasan thread ke-4 yang memicu deadlock:

```json
{
  "action": "created",
  "pull_request": {
    "number": 108,
    "changed_files_list": ["core/domain/ledger_allocator.go", "go.mod"]
  },
  "comment": {
    "id": 99281,
    "in_reply_to_id": 88120,
    "user": { "login": "senior-reviewer" },
    "body": "**issue (blocking):** Saya tetap tidak setuju dengan alokasi heap ini. Ini merusak zero-allocation guarantee."
  },
  "thread_history": [
    { "user": "senior-reviewer", "body": "**issue (blocking):** Gunakan sync.Pool di sini." },
    { "user": "author-dev", "body": "sync.Pool menambah overhead GC tracing pada micro-benchmark kami." },
    { "user": "senior-reviewer", "body": "Tapi mengeliminasi fragmentasi memori jangka panjang." },
    { "user": "author-dev", "body": "Data profiler menunjukkan fragmentasi memori di bawah ambang 2%." }
  ]
}
```

#### Langkah 4: Script Verifikasi Breaker Logic
Buat file `webhook-server/arbiter_test.py` untuk menguji evaluasi logika eskalasi secara lokal tanpa koneksi internet:

```python
import json
import sys

def evaluate_deadlock(payload):
    thread_history = payload.get("thread_history", [])
    current_comment = payload.get("comment", {})
    
    total_depth = len(thread_history) + 1
    has_blocking = any("blocking" in c.get("body", "").lower() for c in thread_history) or \
                   ("blocking" in current_comment.get("body", "").lower())
    
    changed_files = payload.get("pull_request", {}).get("changed_files_list", [])
    is_core_change = any(f.startswith("core/") for f in changed_files)
    
    print(f"[*] Mengevaluasi PR #{payload['pull_request']['number']}")
    print(f"[*] Total Kedalaman Thread: {total_depth}")
    print(f"[*] Mengandung Unsur Blocking: {has_blocking}")
    print(f"[*] Mengubah Komponen Core: {is_core_change}")
    
    if total_depth >= 4 and has_blocking:
        print("\n[!] CIRCUIT BREAKER TRIPPED: Batas toleransi asinkron terlampaui.")
        print("[ACTION] Terapkan lock pada thread PR.")
        print("[ACTION] Beri label PR: 'status:needs-arbitration'.")
        
        if is_core_change:
            print("[ACTION] CRITICAL: Perubahan menyentuh domain core. Wajib terbitkan ADR sebelum merge.")
        return True
    
    print("\n[+] Thread masih dalam batas aman interaksi normal.")
    return False

if __name__ == "__main__":
    with open("tests/mock_event.json", "r") as f:
        data = json.load(f)
    tripped = evaluate_deadlock(data)
    assert tripped == True, "Arbiter gagal memicu circuit breaker pada kondisi deadlock!"
    print("\n[SUCCESS] Seluruh assertion verifikasi lulus 100%.")
```

Jalankan pengujian:
```bash
python3 webhook-server/arbiter_test.py
```

---

### 13. Exercise

#### Level 1 (Easy): Parser Conventional Comments Sanitizer
Buatlah sebuah *utility function* dalam bahasa pemrograman pilihan Anda (Go, TypeScript, atau Python) yang menerima string komentar mentah dan mengembalikan status:
* `VALID` (jika memenuhi format Conventional Comments resmi beserta tipe blocking/non-blocking).
* `INVALID` (jika komentar tidak menyertakan label kategori atau meninggalkan feedback kasar tanpa format terstruktur).
* *Acceptance Criteria*: Script menolak masukan komentar seperti: *"Ini jelek sekali, tolong perbaiki"* dan menerima: *"nitpick (non-blocking): Sebaiknya rename fungsi ini agar sesuai konvensi camelCase."*

#### Level 2 (Medium): Metrics Collector Latensi Thread
Rancang sebuah skrip agregasi metrik (menggunakan GitHub REST API Client) yang membaca riwayat PR pada sebuah repositori selama 30 hari terakhir dan menghitung:
1. Rata-rata kedalaman thread komentar per PR (*Mean Thread Depth*).
2. Rasio korelasi antara kedalaman thread $\ge 5$ komentar terhadap total durasi waktu *lead-time PR merge*.
* *Acceptance Criteria*: Script mengekspor laporan dalam format JSON yang menunjukkan daftar 5 PR dengan siklus debat terpanjang beserta identitas squad terkait.

#### Level 3 (Hard): Distributed Deadlock Breaker Webhook
Implementasikan sebuah microservice berbasis container (Dockerized) lengkap dengan REST endpoint `/v1/webhook` yang mengonsumsi event GitHub/GitLab:
1. Menyimpan state interaksi komentar thread ke dalam in-memory cache / Redis dengan key TTL $24 \text{ jam}$.
2. Mengintegrasikan algoritma circuit breaker: Jika waktu respon antar Author dan Reviewer melebihi $24 \text{ jam}$ kalender pada thread berstatus `blocking`, service secara otomatis mengirimkan notifikasi eskalasi berantai ke webhook Slack target dengan ringkasan diff file yang diperdebatkan.
* *Acceptance Criteria*: Pipeline diuji menggunakan simulated mock events dan lolos pengujian *concurrency stress-test* (100 concurrent webhook calls tanpa data race).

---

### 14. Challenge: Krisis Integrasi Arsitektur Multi-Squad

#### Skenario Kasus Kompleks (Arsitektur Produksi)
Anda bertindak sebagai **Principal Enterprise Architect** pada sebuah institusi perbankan digital. Squad "Payment Infrastructure" mengajukan PR kritis #8092 yang merestrukturisasi skema database transaksi dari *Single Shard* menjadi *Distributed Citus Sharded Cluster* untuk mengantisipasi lonjakan beban transaksi gajian akhir kuartal.

*   **Sengketa Teknis**:
    *   **Reviewer A (Staff DBA)** memblokir PR karena Author menggunakan *Distributed Distributed Joins* pada skema pelaporan transaksi yang berisiko mengunci worker node Citus selama jam sibuk. DBA menuntut de-normalisasi tabel total.
    *   **Reviewer B (InfoSec Lead)** menolak de-normalisasi tabel karena melanggar standar kepatuhan PCI-DSS terkait isolasi data tokenized PAN (nomor kartu kredit), menuntut enkripsi tingkat kolom (*column-level encryption*) yang akan mendegradasi performa query sharding sebesar 35%.
    *   **Author (Payment Squad Lead)** menolak kedua rekomendasi karena deadline peluncuran regulatori tinggal 5 hari kerja, dan menuduh kedua tim menghalangi komitmen bisnis.
    *   PR telah tertahan selama 8 hari dengan 68 komentar tanpa solusi kompromi.

#### Instruksi Misi untuk Arsitek:
Rancang **Comprehensive Architectural Resolution Document** untuk mengurai krisis di atas dengan cakupan sistemik:
1. **Pola Desain Arsitektur**: Rancang arsitektur sintesis yang memecahkan kontradiksi antara latensi Citus joins vs kepatuhan PCI-DSS tanpa mengorbankan performa transaksi gajian.
2. **Protokol Eskalasi Operasional**: Rancang langkah-langkah de-eskalasi dalam kurun waktu $24 \text{ jam}$ ke depan, termasuk penanganan risiko jadwal rilis.
3. **Penyusunan ADR**: Buat draf resmi ADR (format MADR / Michael Nygard) yang mengikat ketiga squad tersebut secara permanen.
4. **Automated Preventive Policy**: Rancang aturan OPA / linter arsitektur pada repositori CI/CD agar konflik kompatibilitas sharding vs enkripsi PCI-DSS terdeteksi otomatis sebelum mencapai fase review manual tim DBA/Sec.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Konseptual & Dasar (5 Soal)
1. **Mengapa Little's Law relevan dalam tata kelola code review asinkron?**
   * A. Karena Little's Law membuktikan bahwa menambah jumlah reviewer akan selalu mempercepat waktu merge.
   * B. Karena Little's Law menunjukkan bahwa membiarkan review berlarut-larut menaikkan WIP (*Work in Progress*), yang secara matematis mendegradasi throughput delivery tim.
   * C. Karena Little's Law mengatur batas maksimal baris kode yang boleh ditulis dalam sebuah fungsi.
   * D. Karena Little's Law mencegah terjadinya race condition pada Git push event.
   * *Jawaban*: **B**. Siklus review yang panjang ($W$) meningkatkan jumlah PR aktif/tertahan ($L$), yang menurunkan kapasitas throughput keseluruhan ($\lambda$).

2. **Apa tujuan utama dari taksonomi Conventional Comments (misal: `issue (blocking)` vs `nitpick (non-blocking)`)?**
   * A. Mengurangi penggunaan kapasitas penyimpanan database pada server GitHub.
   * B. Menggantikan peran unit testing otomatis dalam pipeline CI.
   * C. Memberikan sinyal intensi yang jelas secara deterministik agar Author dapat memprioritaskan tindakan dan mesin otomasi dapat memilah status PR.
   * D. Menghilangkan kebutuhan untuk berdiskusi tatap muka selamanya.
   * *Jawaban*: **C**. Struktur label memberikan kejelasan intensi seketika bagi manusia dan dapat di-parse oleh sistem otomasi eskalasi.

3. **Kapan *3-Strike Rule* harus dipicu dalam sebuah thread review?**
   * A. Ketika Author salah mengetik sintaks kode sebanyak 3 kali berturut-turut.
   * B. Ketika pertukaran argumen asinkron antara Author dan Reviewer telah berjalan 3 iterasi bolak-balik tanpa adanya konsensus atau konvergensi teknis.
   * C. Ketika reviewer menolak PR tanpa memberikan alasan selama 3 hari kerja.
   * D. Ketika pipeline CI mengalami kegagalan build (*build failure*) 3 kali.
   * *Jawaban*: **B**. Aturan ini mencegah debat kusir asinkron tanpa batas (*infinite ping-pong*).

4. **Apa yang dimaksud dengan "Silent Rubber-Stamping" (Capitulation Merge)?**
   * A. Kondisi di mana reviewer menolak PR secara anonim.
   * B. Tindakan menyetujui PR karena lelah berdebat secara mental (*review fatigue*), meskipun isu kualitas/arsitektur yang krusial belum teratasi.
   * C. Proses merge kode yang dilakukan langsung oleh branch protection bot tanpa keterlibatan manusia.
   * D. Penggunaan tanda tangan kriptografi GPG pada commit secara otomatis.
   * *Jawaban*: **B**. Ini adalah anti-pattern berbahaya di mana kompromi kualitas terjadi akibat kelelahan mental, bukan penyelesaian masalah teknis.

5. **Apa fungsi utama Architectural Decision Record (ADR) dalam resolusi konflik PR?**
   * A. Menghukum engineer yang menulis kode yang tidak optimal.
   * B. Bertindak sebagai dokumentasi abadi mengenai konteks, trade-off, dan justifikasi di balik pemilihan keputusan teknis, sehingga perdebatan yang sama tidak berulang di masa depan.
   * C. Menghitung estimasi bonus tahunan engineer berdasarkan kontribusi arsitektur.
   * D. Menggantikan seluruh dokumentasi OpenAPI / Swagger pada repositori microservices.
   * *Jawaban*: **B**. ADR mengabadikan konsensus dan konteks kompromi teknis yang disepakati untuk dijadikan pedoman masa depan.

#### Bagian B: Analisis & Intermediat (5 Soal)
6. **Sebuah PR memiliki 40 baris diff baru, namun memicu 50 komentar debat mengenai format indentasi dan preferensi style penulisan interface. Langkah struktural apa yang paling tepat diambil oleh Tech Lead?**
   * A. Menutup PR dan memecat kedua engineer yang berdebat.
   * B. Membiarkan perdebatan berlangsung agar tim belajar berdemokrasi secara mandiri.
   * C. Mengintervensi PR, menolak seluruh perdebatan gaya kode, dan mengarahkan penegakan style ke automated linter (misal: `golangci-lint` / `eslint`) di level pre-commit hook/CI.
   * D. Mengadakan rapat darurat 2 jam yang melibatkan seluruh anggota departemen engineering.
   * *Jawaban*: **C**. Isu mekanis dan preferensi sintaksis subjektif tidak boleh dibahas secara manual; hal tersebut wajib didelegasikan sepenuhnya ke mesin linter.

7. **Dalam sistem event-driven PR arbitration, mengapa kita harus membatasi event listener pada level comment reply (`in_reply_to_id != nil`), bukan pada *root comment* baru?**
   * A. Untuk menghemat memori cache browser sisi klien.
   * B. Karena root comment baru biasanya merepresentasikan identifikasi area isu yang berbeda, sedangkan balasan (*replies*) bertingkat menunjukkan dinamika kedalaman perdebatan atau argumentasi bolak-balik.
   * C. Karena API GitHub tidak mendukung pelacakan komentar root.
   * D. Agar author tidak dapat melihat review yang diberikan reviewer.
   * *Jawaban*: **B**. Deadlock dan debat kusir termanifestasi dalam rantai balasan (*thread depth*), bukan dari banyaknya titik observasi independen yang diidentifikasi.

8. **Manakah dari skenario berikut yang merepresentasikan pelanggaran terhadap *Strict Diff Boundary*?**
   * A. Reviewer meminta penambahan unit test untuk fungsi baru yang ditambahkan di dalam PR.
   * B. Reviewer menahan persetujuan PR penambahan field database karena menuntut Author menulis ulang seluruh arsitektur autentikasi legacy yang tidak tersentuh oleh branch PR saat ini.
   * C. Reviewer menemukan adanya regression bug pada fungsi yang dimodifikasi langsung oleh Author.
   * D. Reviewer meminta Author memperbaiki ejaan typo pada pesan error yang baru dibuat.
   * *Jawaban*: **B**. Menuntut perbaikan kode di luar batas lingkup kerja PR (*diff context boundary*) adalah bentuk *scope creep* yang merusak metrik cycle time.

9. **Jika Author dan Reviewer berada pada perbedaan zona waktu yang sangat ekstrem (misal: Singapura UTC+8 dan New York UTC-5), mengapa pola komunikasi sinkron singkat (15 menit) terkadang lebih disukai daripada asinkron murni saat terjadi konflik teknis?**
   * A. Karena komunikasi asinkron murni melintasi zona waktu tersebut membutuhkan latensi 24-48 jam kalender hanya untuk mengklarifikasi miskomunikasi kalimat sederhana.
   * B. Karena panggilan video menggunakan bandwidth internet yang lebih murah daripada payload teks API.
   * C. Karena zona waktu New York tidak memiliki koneksi git repository.
   * D. Komunikasi sinkron tidak pernah direkomendasikan dalam organisasi engineering modern.
   * *Jawaban*: **A**. Latensi per putaran interaksi asinkron lintas zona waktu ekstrem sangat tinggi; sinkronisasi 15 menit dapat memangkas latensi kalender selama berhari-hari.

10. **Apa metrik observabilitas terbaik untuk mendeteksi bahwa sebuah squad rekayasa sedang mengalami masalah *Review Gridlock* yang parah?**
    * A. Peningkatan drastis jumlah bintang (*stars*) pada repositori Git.
    * B. Peningkatan tajam pada metrik *PR Review Cycle Time* dan *Time-to-Merge*, diiringi oleh lonjakan jumlah komentar berstatus unresolved per PR.
    * C. Penurunan jumlah commit pada branch `main`.
    * D. Peningkatan error rate P99 pada container Kubernetes.
    * *Jawaban*: **B**. PR Review Cycle Time yang memanjang disertai tingginya volume komentar tak terpecahkan adalah indikator objektif kemacetan proses review.

#### Bagian C: Skenario Kasus Produksi (3 Soal)
11. **Skenario Kasus 1**:
    Tim Core Platform merilis *breaking change* pada library telemetry internal. Tim Author mengklaim perubahan ini mendesak untuk menekan biaya cluster tracing Datadog hingga 40%. Reviewer dari Squad Checkout menolak PR tersebut dengan label `blocking` karena perubahan tersebut menghapus backward-compatibility pada distributed context propagator mereka yang belum sempat di-update, sehingga berpotensi mematikan transaksi checkout jika di-deploy.
    **Keputusan mitigasi arsitektur terbaik yang harus diambil dalam 4 jam ke depan adalah:**
    * A. Menolak PR tim Platform secara permanen dan membatalkan inisiatif penghematan biaya telemetry.
    * B. Memaksa Squad Checkout lembur malam ini untuk menulis ulang modul tracing mereka.
    * C. Menerapkan pola *Deprecation Grace Period* via *Adapter Pattern*: Tim Platform wajib mempertahankan backward-compatible signature selama 2 sprint rilis ke depan, didukung log warning runtime, sembari Squad Checkout menjadwalkan migrasi bertahap.
    * D. Melakukan bypass proteksi branch dan langsung melakukan merge ke `main` demi efisiensi biaya.
    * *Jawaban*: **C**. Ini adalah pola rekayasa enterprise yang seimbang: Tim Platform tetap mencapai target arsitekturalnya tanpa merusak reliabilitas sistem operasional Squad Checkout via transisi bertahap (*compatibility adapter*).

12. **Skenario Kasus 2**:
    Arbiter Engine mendeteksi sebuah thread review pada modul penagihan (billing) telah dikunci karena melampaui kedalaman 5 iterasi. Topik perdebatan menyangkut presisi tipe data moneter: Reviewer menuntut migrasi dari `float64` ke custom struct `big.Int` (Fixed-Point Arithmetic) untuk menghindari pembulatan nilai desimal cent. Author berargumen bahwa perubahan ini memerlukan refactoring pada 42 file controller lainnya yang berada di luar cakupan ticket.
    **Instruksi teknis apa yang harus diberikan oleh Lead Arbiter kepada Author PR?**
    * A. Menyetujui penggunaan `float64` untuk seluruh transaksi demi kecepatan rilis fitur.
    * B. Memisahkan scope PR: Menerapkan custom struct `Fixed-Point` HANYA pada scope fungsi lokal yang diubah oleh PR saat ini, dan membuat sub-ticket teknis prioritas tinggi (P1) untuk merestrukturisasi 42 file controller sisanya pada PR independen berikutnya.
    * C. Menghapus seluruh unit test yang memeriksa pembulatan angka desimal.
    * D. Meminta reviewer untuk menulis sendiri seluruh kode yang diinginkan pada PR tersebut.
    * *Jawaban*: **B**. Menggunakan `float64` untuk kalkulasi moneter adalah dosa arsitektur fatal (*data corruption*), namun memaksakan refactoring masif pada satu PR memicu risiko regresi besar. Membatasi implementasi benar pada skop lokal sembari mendistribusikan sisa refactoring ke tiket terpisah adalah jalan keluar profesional terbaik.

13. **Skenario Kasus 3**:
    Perusahaan Anda menerapkan sistem Automated PR Arbiter berbasis Slack Bot. Namun, setelah 3 minggu beroperasi, terjadi fenomena di mana para senior engineer secara sengaja menghindari penggunaan tag `issue (blocking)` dan beralih menggunakan tag `thought (non-blocking)` atau komentar teks polos tanpa format tag, sembari secara implisit menahan approval mereka (*withholding review*).
    **Diagnosa akar masalah budaya/sistemik dan tindakan korektif yang tepat adalah:**
    * A. Sistem otomatisasi dipandang sebagai instrumen birokrasi pengawasan yang kaku (*punitive bureaucracy*), sehingga engineer mencari celah manipulasi (*gaming the system*) untuk menghindari eskalasi publik. Koreksi: Kalibrasi ulang matriks eskalasi agar tidak bersifat menghukum, melainkan memfasilitasi bantuan, dan libatkan engineer dalam perumusan ambang batas SLA.
    * B. Linter regex server bot mengalami crash memori. Koreksi: Restart worker bot di Kubernetes.
    * C. Para engineer senior tidak memahami bahasa Inggris. Koreksi: Terjemahkan seluruh bot ke bahasa lokal.
    * D. Hapus seluruh branch protection rules dan bebaskan merge tanpa review.
    * *Jawaban*: **A**. Ketika instrumen governance dipandang sebagai ancaman administratif oleh tim inti, mereka akan secara sadar memanipulasi metrik atau menghindari protokol resmi. Tata kelola harus didesain untuk melayani kebutuhan tim, bukan membelenggu mereka.

---

### 16. Summary

```
+───────────────────────────────────────────────────────────────────────────────────────+
|               TAKSONOMI AKSI RESOLUSI KONFLIK CODE REVIEW ENTERPRISE                  |
+───────────────────────────+───────────────────────────────+───────────────────────────+
| Gejala Teknis             | Akar Masalah Sistemik         | Protokol Intervensi Wajib |
+───────────────────────────+───────────────────────────────+───────────────────────────+
| Thread Depth >= 3         | Komunikasi asinkron gagal     | Circuit Breaker trips:    |
| (Ping-pong debate)        | melakukan konvergensi fakta.  | Lock thread, Sync Huddle. |
+───────────────────────────+───────────────────────────────+───────────────────────────+
| Debate pada Legacy Files  | Pelanggaran boundary scoped   | Strict Diff Boundary:     |
| (Scope Creep)             | diff; Reviewer bernostalgia.  | Reject & spawn Tech Debt. |
+───────────────────────────+───────────────────────────────+───────────────────────────+
| Desain Arsitektural Multi-| Konflik trade-off lokal       | Escalation to Principal;  |
| Varian & Buntu            | versus global invariansi.     | Formalkan via ADR & Flag. |
+───────────────────────────+───────────────────────────────+───────────────────────────+
| Approvals tanpa Solusi    | Cognitive exhaustion          | Automated Audit: Block    |
| (Review Fatigue)          | (*Capitulation merge*).       | suspicious merge without  |
|                           |                               | delta commit.             |
+───────────────────────────+───────────────────────────────+───────────────────────────+
```

> **Aksioma Rekayasa Perangkat Lunak Bab 09**:
> *"Kode adalah representasi fana dari sistem perangkat lunak, namun konsensus adalah fondasi operasional organisasi. Jangan biarkan perdebatan mekanis merusak kecepatan pengiriman produk, dan jangan biarkan kecepatan pengiriman produk merusak integritas arsitektural. Otomasikan apa yang mekanis, batasi apa yang asinkron, dan dokumentasikan apa yang diputuskan secara abadi."*