## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul:** CR-ASD-08-01
* **Nama Modul:** Metrik, SLA, & Mengelola Review Fatigue: PR Turnaround Time, Review Load Balancing, Mengurangi Cognitive Load & Burnout pada Reviewer, SLA Tim
* **Kategori:** 06-Architecture-and-System-Design / Code Review Engineering
* **Level Kursus:** Advanced / Staff Engineer & Engineering Manager
* **Prasyarat (Prerequisites):** 
  * Pemahaman mendalam tentang Git internal, Trunk-based vs Feature Branch workflows.
  * Pengalaman mengelola pull request (PR) lifecycle pada platform modern (GitHub, GitLab, Bitbucket).
  * Pengalaman arsitektural dalam Continuous Integration (CI) dan automasi webhook.
* **Estimasi Waktu Belajar:** 150 Menit (Teori Arsitektural, Implementasi Skrip Automasi, & Studi Kasus)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. **Menganalisis (C4)** metrik siklus hidup Pull Request (PR Lead Time, Time to First Review/TTFR, Review Turnaround Time, Iteration Count) untuk mendeteksi bottleneck operasional pada tim rekayasa perangkat lunak.
2. **Merancang (C6)** Service Level Agreement (SLA) dan Service Level Objectives (SLO) code review yang seimbang, mencegah regresi kualitas kode sekaligus menjaga developer velocity.
3. **Mengimplementasikan (C3)** sistem *Review Load Balancing* berbasis beban kognitif riil (WIP limits, active review capacity, area of expertise) menggunakan otomasi API/webhook.
4. **Mengevaluasi (C5)** trade-off antara kebiasaan *rubber-stamping* akibat *review fatigue* vs proses peninjauan berlarut-larut (*PR starvation*).
5. **Menyusun (C6)** strategi mitigasi *cognitive load* pada reviewer melalui standarisasi ukuran PR, automasi validasi lint/test, dan arsitektur *stacked diffs*.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
[Engineering Velocity & Code Health]
         │
         ├──► [PR Lifecycle Metrics]
         │       ├── Pickup Time (TTFR: Time to First Review)
         │       ├── Review Turnaround Time (RTT)
         │       ├── Iteration Count & Comment Density
         │       └── Merge Lag
         │
         ├──► [Review SLA & SLO Governance]
         │       ├── Tiered PR SLA (Hotfix vs Core vs Chore)
         │       ├── Asynchronous vs Synchronous Window
         │       └── Goodhart's Law Safeguards (Preventing Rubber-Stamping)
         │
         ├──► [Human Factors & Fatigue Engineering]
         │       ├── Extraneous vs Intrinsic Cognitive Load
         │       ├── Review Fatigue & Decision Degradation
         │       └── Reviewer Burnout Patterns
         │
         └──► [Architectural Load Balancing]
                 ├── Round-Robin with WIP-aware Overrides
                 ├── Code Ownership (CODEOWNERS) Decentralization
                 └── Stacked Diffs & Micro-PR Enforcement
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Code review adalah garis pertahanan pertama kualitas kode, transfer pengetahuan, dan mitigasi risiko arsitektur. Namun, mayoritas organisasi engineering memperlakukannya sebagai aktivitas insidental tak berjadwal (*unplanned reactive work*).

Ketika volume PR meningkat tanpa tata kelola operasional yang terukur:
1. **Developer Velocity Tercekik (*PR Starvation*):** Insinyur menunggu berhari-hari hingga berminggu-minggu untuk mendapatkan umpan balik awal. Konsekuensinya adalah *context switching cost* yang masif, merge conflict yang eksponensial, dan penurunan frekuensi rilis.
2. **Review Fatigue & Rubber-Stamping:** Reviewer yang kewalahan menerima beban PR besar di luar kapasitas kerja normal (*cognitive overload*) akan berhenti melakukan evaluasi mendalam. Hasilnya adalah fenomena *"LGTM"* (Looks Good To Me) tanpa eksekusi pengujian kritis—menghilangkan total fungsi proteksi code review dan membiarkan bug fatal lolos ke produksi.
3. **Burnout pada Senior Engineers & Tech Leads:** Beban review hampir selalu jatuh ke segelintir insinyur senior atau Tech Lead (*bottlenecking*). Mereka mengalami fragmentasi fokus (*fragmented focus time*), kelelahan mental, hingga burnout kronis karena terus dipaksa memilih antara menyelesaikan deliverables arsitektural mereka sendiri atau mereview antrean PR tim.

Memperlakukan code review sebagai sebuah **sistem terdistribusi yang memiliki batasan throughput, antrean (queues), dan beban kognitif** adalah satu-satunya cara mempertahankan velocity tinggi tanpa mengorbankan stabilitas sistem dan kesehatan mental tim.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Dekonstruksi Metrik Siklus Hidup PR
Siklus hidup PR tidak boleh diukur sebagai satu kesatuan metrik tunggal (*PR Lead Time*), melainkan harus didekomposisi ke dalam fase-fase kritis:

$$\text{PR Lead Time} = T_{\text{pickup}} + T_{\text{review}} + T_{\text{rework}} + T_{\text{merge}}$$

* **Time to First Review (TTFR) / Pickup Time ($T_{\text{pickup}}$):** Waktu dari saat PR dinyatakan siap direview (`Ready for Review`) hingga review bermakna pertama kali diberikan (bukan komentar otomatis bot).
* **Review Turnaround Time ($T_{\text{review}}$):** Durasi yang dibutuhkan reviewer untuk merespons setiap revisi atau iterasi dari author.
* **Rework Time ($T_{\text{rework}}$):** Waktu yang dihabiskan author untuk menjawab feedback, memperbaiki kode, dan memperbarui commit.
* **Merge Lag ($T_{\text{merge}}$):** Waktu dari approval terakhir hingga kode benar-benar terintegrasi ke trunk branch (sering tertahan karena antrean CI yang lambat atau menunggu manual deployment).

### 2. Service Level Agreement (SLA) & Service Level Objective (SLO) Tim
* **SLI (Service Level Indicator):** Parameter yang diukur (misal: persentase PR berlabel `P1` yang mendapatkan review awal dalam $\le 4$ jam kerja).
* **SLO (Service Level Objective):** Target internal tim (misal: 90% PR mendapatkan review awal $\le 24$ jam kerja).
* **SLA (Service Level Agreement):** Komitmen formal lintas fungsi atau tim yang memiliki konsekuensi nyata jika dilanggar (misal: jika PR hotfix security tidak direview dalam 2 jam, PR tersebut otomatis dieskalasi via paging ke on-call architect).

### 3. Review Fatigue & Cognitive Load Theory
Beban kognitif (*Cognitive Load*) terbagi atas tiga kategori:
* **Intrinsic Load:** Kompleksitas inheren dari domain problem (misal: algoritma konsensus distributed ledger).
* **Extraneous Load:** Beban mental yang sia-sia akibat cara penyampaian kode (misal: format kode berantakan, perubahan 3000 baris dalam satu PR, ketiadaan deskripsi/konteks, coupling tinggi antara refactor dan business logic baru).
* **Germane Load:** Beban mental yang konstruktif untuk mengintegrasikan pola arsitektur baru ke dalam mental model tim.

**Review Fatigue** terjadi ketika *Extraneous Load* mendominasi secara konsisten, menghabiskan energi kognitif reviewer, dan memicu *Decision Fatigue* yang berujung pada menurunnya akurasi pendeteksian cacat kode secara drastis.

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

### 1. Segmentasi PR Menggunakan T-Shirt Sizing
Beban kognitif berbanding lurus dengan jumlah baris yang dimodifikasi (*Lines Changed*). Organisasi harus menegakkan batas ukuran PR berbasis data empiris SmartBear: tinjauan kode menurun drastis efektivitasnya setelah melampaui **200–400 baris kode dalam 60 menit**.

| Size | Lines of Code (LoC) Changed | Target TTFR SLO | Target Turnaround Time |
| :--- | :--- | :--- | :--- |
| **XS** | $1 - 20$ lines | $< 2$ jam kerja | $< 4$ jam kerja |
| **S** | $21 - 100$ lines | $< 4$ jam kerja | $< 8$ jam kerja |
| **M** | $101 - 300$ lines | $< 8$ jam kerja | $< 24$ jam kerja |
| **L** | $301 - 500$ lines | $< 24$ jam kerja | $< 48$ jam kerja |
| **XL** | $> 500$ lines | **Rejected / Must Split** | N/A |

### 2. Review Load Balancing Engine (WIP-Aware Routing)
Mekanisme default `CODEOWNERS` di GitHub sering kali menunjuk individu yang sama secara berulang (misal: `@tech-lead`), menciptakan antrean raksasa (*head-of-line blocking*).

Sistem arsitektur load balancing yang modern mengimplementasikan routing cerdas:
1. **Filter Kandidat:** Menemukan individu yang memiliki kompetensi teknis pada modul terkait (berdasarkan kepemilikan repositori/direktori).
2. **Filter Ketersediaan:** Menyingkirkan personel yang sedang cuti (*Out of Office*) atau sedang bertugas sebagai *incident on-call*.
3. **Perhitungan Dynamic Work-In-Progress (WIP):** Menghitung jumlah review aktif yang sedang ditugaskan kepada masing-masing kandidat. Review berbobot aktif adalah PR berstatus `Pending Review` dengan batas maksimal (misal: maksimal 3 PR aktif per reviewer).
4. **Weighted Assignment:** Mengalokasikan PR baru ke insinyur yang memiliki sisa kapasitas kognitif tertinggi.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. Timeline & Breakdown Metrik Siklus Hidup Pull Request

```
AUTHOR TIMELINE                                                 REVIEWER TIMELINE
[Create Branch]
       │
       ▼
[Push Commits]
       │
       ▼
[Open Pull Request] ─── (State: Ready)
       │
       ├────────────────────────────────────────┐
       │                                        ▼
       │                          [Pickup Time / TTFR]
       │                          (SLA Target: <= 4h)
       │                                        │
       │                                        ▼
       │                              [Reviewer Starts Review]
       │                                        │
       │                                        ▼
       │                              [Feedback Submitted] ──── Request Changes
       ▼                                        │
[Rework Time]                                   │
(Author fixes issues)                           │
       │                                        │
       ▼                                        │
[Push Fix Commits]                              ▼
       │                          [Turnaround Time Iteration 2]
       ├───────────────────────────────────────►│
       │                                        ▼
       │                              [Re-review & Approve] ─── Approved
       ▼                                        │
[Merge Lag Time] ◄──────────────────────────────┘
(CI/CD Pipeline Run & Auto-merge)
       │
       ▼
[Merged to Main]
```

### 2. Arsitektur Dynamic Review Load Balancer & SLA Watchdog

```
  +-------------------------+
  | GitHub / GitLab Webhook |
  +-------------------------+
               │ (PR Created / PR Updated / Review Submitted)
               ▼
  +───────────────────────────────────────────────────────────+
  |              Review Management Microservice               |
  |                                                           |
  |  +──────────────────────+       +──────────────────────+  |
  |  |    Payload Parser    |       |   Metrics Collector  |  |
  |  |  (Size, Tags, Author)|       | (TTFR, Iterations)   |  |
  |  +──────────┬───────────+       +──────────▲───────────+  |
  |             │                              │              |
  |             ▼                              │              |
  |  +─────────────────────────────────────────┴───────────+  |
  |  |               Routing & Decision Engine             |  |
  |  |                                                     |  |
  |  |  1. Exclude PR Author & OOO Personnel               |  |
  |  |  2. Query Reviewer Active WIP from Redis            |  |
  |  |  3. Filter Candidates by Area/Domain Codeowners     |  |
  |  |  4. Select Reviewer with MIN(Active_PR_Weight)       |  |
  |  +──────────────────────┬──────────────────────────────+  |
  +─────────────────────────┼─────────────────────────────────+
                            │ Assign Reviewer API Call
                            ▼
               +────────────────────────+
               | GitHub/GitLab Platform |
               +────────────────────────+
                            │
               +────────────┴───────────+
               │ Periodic SLA Watchdog  │ (Cron every 15m)
               +────────────┬───────────+
                            │ Checks TTFR > SLA_Threshold
                            ▼
               +────────────────────────+
               |  Slack / PagerDuty Alert|
               +────────────────────────+
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah skrip Python murni tanpa ketergantungan pihak ketiga eksternal untuk menghitung metrik durasi siklus hidup PR dan memverifikasi pelanggaran SLA dari raw JSON payload.

```python
#!/usr/bin/env python3
"""
Simple PR Lifecycle SLA Calculator
Menghitung TTFR dan validasi kepatuhan terhadap Target SLA.
"""
from datetime import datetime, timezone

def parse_iso8601(timestamp_str: str) -> datetime:
    return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

def evaluate_pr_sla(pr_payload: dict, sla_hours: float) -> dict:
    created_at = parse_iso8601(pr_payload["created_at"])
    first_review_at = None
    
    # Urutkan event review berdasarkan waktu untuk memastikan kronologi
    reviews = sorted(pr_payload.get("reviews", []), key=lambda r: parse_iso8601(r["submitted_at"]))
    
    for review in reviews:
        # Filter: Abaikan automated bot atau komentar author sendiri
        if review["user"] != pr_payload["author"] and not review.get("is_bot", False):
            first_review_at = parse_iso8601(review["submitted_at"])
            break

    now = datetime.now(timezone.utc)
    
    if first_review_at:
        ttfr_seconds = (first_review_at - created_at).total_seconds()
        ttfr_hours = ttfr_seconds / 3600.0
        sla_breached = ttfr_hours > sla_hours
        status = "REVIEWED"
    else:
        # PR belum pernah direview
        pending_seconds = (now - created_at).total_seconds()
        ttfr_hours = pending_seconds / 3600.0
        sla_breached = ttfr_hours > sla_hours
        status = "PENDING_FIRST_REVIEW"

    return {
        "pr_id": pr_payload["id"],
        "status": status,
        "ttfr_hours": round(ttfr_hours, 2),
        "sla_target_hours": sla_hours,
        "sla_breached": sla_breached
    }

if __name__ == "__main__":
    sample_pr = {
        "id": 1042,
        "author": "engineer_junior",
        "created_at": "2026-03-30T08:00:00Z",
        "reviews": [
            {
                "user": "github-actions[bot]",
                "is_bot": True,
                "submitted_at": "2026-03-30T08:02:00Z"
            },
            {
                "user": "senior_architect",
                "is_bot": False,
                "submitted_at": "2026-03-30T13:30:00Z" # 5.5 jam setelah PR dibuat
            }
        ]
    }
    
    SLA_LIMIT_HOURS = 4.0
    result = evaluate_pr_sla(sample_pr, SLA_LIMIT_HOURS)
    print(f"Hasil Evaluasi SLA PR #{result['pr_id']}:")
    print(f" - Status: {result['status']}")
    print(f" - TTFR: {result['ttfr_hours']} jam (Target: <= {result['sla_target_hours']} jam)")
    print(f" - Pelanggaran SLA: {'YA (BREACHED)' if result['sla_breached'] else 'TIDAK (PASSED)'}")
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Berikut adalah implementasi backend berbasis **Node.js/TypeScript** yang berfungsi sebagai webhook receiver dari GitHub. Service ini mengimplementasikan **WIP-Aware Reviewer Load Balancer** untuk mencegah *review fatigue* dan meratakan distribusi review ke anggota tim.

```typescript
// reviewer-balancer.ts
import http from 'node:http';

interface GitHubPullRequestEvent {
  action: string;
  pull_request: {
    number: number;
    title: number;
    user: { login: string };
    requested_reviewers: Array<{ login: string }>;
    draft: boolean;
  };
  repository: {
    name: string;
    owner: { login: string };
  };
}

interface ReviewerCapacity {
  username: string;
  activeReviewsCount: number;
  isAvailable: boolean; // false jika cuti / incident commander
}

// Simulasi Database Status Tim (Dalam sistem nyata: Redis / Postgres)
const TEAM_CAPACITY_STORE: Map<string, ReviewerCapacity> = new Map([
  ['alice_lead', { username: 'alice_lead', activeReviewsCount: 4, isAvailable: true }],
  ['bob_senior', { username: 'bob_senior', activeReviewsCount: 1, isAvailable: true }],
  ['charlie_mid', { username: 'charlie_mid', activeReviewsCount: 2, isAvailable: true }],
  ['david_mid', { username: 'david_mid', activeReviewsCount: 0, isAvailable: false }], // Sedang OOO
]);

const MAX_WIP_REVIEW_LIMIT = 3;

class ReviewLoadBalancerService {
  /**
   * Menemukan kandidat terbaik berdasarkan lowest active reviews 
   * dan menghormati batasan hard WIP limit.
   */
  public selectOptimalReviewer(prAuthor: string): string | null {
    let selectedCandidate: ReviewerCapacity | null = null;

    for (const member of TEAM_CAPACITY_STORE.values()) {
      // 1. Author tidak boleh mereview PR milik sendiri
      if (member.username === prAuthor) continue;

      // 2. Cek ketersediaan (Out-of-office / On-call)
      if (!member.isAvailable) continue;

      // 3. Batasi jika reviewer sudah mencapai batas cognitive overload
      if (member.activeReviewsCount >= MAX_WIP_REVIEW_LIMIT) continue;

      // 4. Pilih candidate dengan beban kognitif terendah (Min Active Reviews)
      if (!selectedCandidate || member.activeReviewsCount < selectedCandidate.activeReviewsCount) {
        selectedCandidate = member;
      }
    }

    return selectedCandidate ? selectedCandidate.username : null;
  }

  public registerAssignment(username: string): void {
    const member = TEAM_CAPACITY_STORE.get(username);
    if (member) {
      member.activeReviewsCount += 1;
      console.log(`[STATE] ${username} active PR count bumped to: ${member.activeReviewsCount}`);
    }
  }
}

const balancer = new ReviewLoadBalancerService();

const server = http.createServer((req, res) => {
  if (req.method === 'POST' && req.url === '/webhooks/github') {
    let body = '';

    req.on('data', chunk => {
      body += chunk.toString();
    });

    req.on('end', () => {
      try {
        const payload: GitHubPullRequestEvent = JSON.parse(body);

        // Hanya proses saat PR baru dibuka atau diubah dari Draft ke Ready
        if (payload.action === 'opened' || payload.action === 'ready_for_review') {
          if (payload.pull_request.draft) {
            res.writeHead(200, { 'Content-Type': 'application/json' });
            return res.end(JSON.stringify({ status: 'Ignored: PR is Draft' }));
          }

          const author = payload.pull_request.user.login;
          const assignedReviewer = balancer.selectOptimalReviewer(author);

          if (!assignedReviewer) {
            console.warn(`[WARN] Alert! Seluruh reviewer mencapai Max WIP limit atau tidak tersedia. PR #${payload.pull_request.number} tertahan.`);
            res.writeHead(503, { 'Content-Type': 'application/json' });
            return res.end(JSON.stringify({ error: 'All reviewers at capacity. Escalating to engineering manager.' }));
          }

          // Simulasi pemanggilan API GitHub untuk assign reviewer
          console.log(`[ASSIGNMENT] PR #${payload.pull_request.number} by ${author} dialokasikan ke: @${assignedReviewer}`);
          balancer.registerAssignment(assignedReviewer);

          res.writeHead(200, { 'Content-Type': 'application/json' });
          return res.end(JSON.stringify({ status: 'Assigned', reviewer: assignedReviewer }));
        }

        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'Ignored event action' }));
      } catch (err: any) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Malformed JSON payload' }));
      }
    });
  } else {
    res.writeHead(404);
    res.end();
  }
});

const PORT = 3000;
server.listen(PORT, () => {
  console.log(`PR Review Load Balancer listening on port ${PORT}`);
});
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Pendekatan | Keuntungan | Kerugian / Risiko | Strategi Mitigasi Arsitektural |
| :--- | :--- | :--- | :--- |
| **Strict SLA Enforcemet (e.g., TTFR < 2 Jam)** | Velocity pengiriman kode terpelihara, meminimalkan *idle time* engineer. | **Rubber-Stamping Risk:** Reviewer terburu-buru meng-approve tanpa membaca menyeluruh demi mematuhi metrik. | Gunakan metrik pendamping: *Review Depth* (jumlah inline comment, execution of test plans, ratio size vs review duration). |
| **Code Ownership Terpusat (`@tech-lead` approval)** | Konsistensi arsitektur terjamin, standar kualitas kode sistematis. | **Critical Path Bottleneck:** Terjadinya *head-of-line blocking*, Tech Lead mengalami burnout kronis, SLA runtuh. | Delegasi kepemilikan sub-modul (*decentralized CODEOWNERS*) dan pairing review antara Senior dan Mid-level engineer. |
| **Batas Ketat WIP Review Per Engineer** | Menghilangkan *Review Fatigue*, menjamin kualitas review yang mendalam dan tajam. | **PR Starvation Queue:** Jika throughput author melebihi kapasitas review tim, PR akan menumpuk di antrean *unassigned*. | Terapkan batas ukuran PR ketat ($\le 200$ LoC) dan terapkan teknik Stacked Diffs agar kapasitas review per PR menjadi ringan. |
| **Push Escalation via Slack/PagerDuty Alerts** | Mencegah PR terlupakan atau terbengkalai dalam antrean review. | **Alert Fatigue & Fragmented Focus Time:** Interupsi konstan merusak kondisi *flow state* reviewer saat coding. | Terapkan *Batching Windows* (misal: alert hanya dirangkum dan dikirim pukul 09.30 dan 14.00, bukan *real-time instant ping*). |

---

## SEKSI 11 — BEST PRACTICES

1. **Aturan "Review Sebelum Coding Baru":** Prioritaskan unblocking rekan kerja. Sebelum seorang engineer menarik tiket baru dari Kanban/Sprint backlog, wajib memeriksa antrean review PR tim yang berstatus aktif.
2. **Definisi *Reviewable Unit* ($\le 300$ Lines of Code):** Buat policy CI otomatis yang memberikan warning jika PR melampaui $400$ baris modifikasi logic (di luar kode autogenerated atau migrasi lockfile). PR besar harus dipecah menggunakan pola *Stacked PRs* atau *Feature Flag Branching*.
3. **Automasi Pra-Review (Zero-Tolerance Manual Linting):** Reviewer manusia tidak boleh menghabiskan waktu kognitif untuk mengomentari indentasi, formatting, penamaan variabel sederhana, atau ketiadaan unit test dasar. CI pipeline wajib memvalidasi Linter, Formatter (Prettier, ESLint, Black, Rustfmt), Security Static Analysis (SAST), dan Code Coverage secara otomatis sebelum PR dapat dibuka untuk review manusia.
4. **Alokasi Review Blocks Khusus (*Focus Time Preservation*):** Lindungi jadwal kerja insinyur. Terapkan blok waktu review yang terisolasi (misal: 45 menit di awal pagi dan 45 menit pasca-makan siang) untuk menghindari switch context terus-menerus sepanjang hari kerja.
5. **Gunakan Checklist Terstandarisasi untuk Memangkas *Intrinsic Load*:** Sediakan PR description template yang jelas:
   * *What problem does this PR solve?*
   * *How was this tested? (Unit, Integration, Manual steps)*
   * *Architectural side-effects & risk mitigation plan*.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1. **Jatuh ke dalam Jebakan Hukum Goodhart (*Goodhart's Law*):**
   * *Anti-pattern:* Menjadikan TTFR sebagai KPI performa personal engineer.
   * *Dampak:* Engineer akan membalas secara artifisial ("Looks interesting, will check later") atau langsung menekan tombol *Approve* dalam hitungan menit untuk mengamankan nilai KPI, tanpa memeriksa logika race condition atau celah keamanan.
2. **Membiarkan PR "Mega-Monolitik" Atas Dalih "Satu Fitur Selesai":**
   * *Anti-pattern:* Mengizinkan PR sebesar 2.500 baris dengan dalih fitur backend, database schema, dan integrasi frontend harus digabung sekaligus.
   * *Dampak:* Reviewer mengalami paralisis kognitif total. PR tertunda berminggu-minggu, memicu merge conflict masif, dan akhirnya di-approve secara buta karena kelelahan mental.
3. **Mengabaikan Author Responsiveness (*The Ghosting Author*):**
   * *Anti-pattern:* SLA hanya dibebankan kepada reviewer, sementara author menunda revisi feedback hingga berhari-hari.
   * *Dampak:* Saat author kembali mengunggah commit 5 hari kemudian, reviewer telah kehilangan konteks mental (*loss of mental cache*), sehingga harus mengulang proses analisa arsitektur dari awal.
4. **Distribusi Review Berbasis Senioritas Tunggal:**
   * *Anti-pattern:* Mengarahkan seluruh PR ke Senior Software Engineer paling berpengalaman di tim.
   * *Dampak:* Mengerdilkan kapabilitas evaluasi anggota tim Mid/Junior, menciptakan single point of failure (SPOF) organisasi, dan menyebabkan burnout pada senior engineer tersebut.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Skenario Latihan
Sebuah scale-up e-commerce menghadapi krisis produktivitas: PR rata-rata tertahan selama 7.2 hari kerja. Tim arsitektur menemukan bahwa 85% PR dialokasikan ke 2 orang Principal Engineer, sementara 10 engineer lainnya jarang mereview. Ketika insiden produksi terjadi, audit menunjukkan bahwa bug kritis tersebut berada di dalam PR sebesar 1.800 baris yang di-approve dalam tempo 3 menit oleh Principal Engineer yang kelelahan.

### Tugas:
1. **Latihan 1 (Algoritma Penyeimbang Beban):** Modifikasi kode TypeScript pada Seksi 09 untuk menyertakan faktor penimbang keahlian (*Domain Tagging*). Jika PR memiliki tag `domain:payments`, utamakan kandidat yang memiliki kapabilitas domain tersebut, namun bila seluruh expert payments melampaui `MAX_WIP_LIMIT`, sistem harus secara aman mengalokasikan PR ke secondary reviewer umum dengan auto-tag `requires-supervision`.
2. **Latihan 2 (SLA Breached Webhook Watchdog):** Tulis fungsi Node.js/Python yang berjalan secara terjadwal untuk memeriksa seluruh open PR. Jika suatu PR berlabel `P0-Critical` belum menerima review selama $\ge 60$ menit, buat notifikasi alert JSON yang siap dikirimkan ke webhook endpoint on-call pager.
3. **Latihan 3 (Sizing Validation Rules):** Rancang konfigurasi workflow GitHub Actions (`.github/workflows/pr-size-gate.yml`) yang mengevaluasi total diff PR (`additions + deletions`). Jika diff $\gt 400$ lines (mengabaikan generated file seperti `package-lock.json` atau `schema.prisma`), workflow harus otomatis mem-fail CI status check dan menambahkan komentar peringatan edukatif kepada PR author untuk memecah kodenya.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Apa bahaya terbesar dari penerapan SLA Time to First Review (TTFR) yang sangat agresif (misal: harus $\le 30$ menit) tanpa disertai guardrail kualitas review?**
   * A. PR author akan mogok kerja.
   * B. CI/CD pipeline akan mengalami memory exhaustion.
   * C. Reviewer terdorong melakukan *rubber-stamping* (approval dangkal) demi memenuhi metrik.
   * D. Repositori Git akan mengalami database corruption.
   * *Jawaban yang benar:* **C**. Metrik kecepatan yang dipaksakan tanpa metrik kualitas pendamping akan mengorbankan kedalaman review (Goodhart's Law).

2. **Berdasarkan Cognitive Load Theory dalam code review, manakah yang tergolong sebagai *Extraneous Cognitive Load*?**
   * A. Memahami dependensi algoritma perutean graf yang kompleks.
   * B. Membaca 800 baris perubahan kode yang tercampur antara refactoring nama variabel dan logika fitur baru.
   * C. Mengkaji validasi invariant domain bisnis perbankan.
   * D. Menganalisis potensi race condition pada shared memory multi-threading.
   * *Jawaban yang benar:* **B**. Percampuran refactor kosmetik dan logic baru adalah noise penyampaian yang memaksa otak memproses informasi non-esensial secara sia-sia.

3. **Kapan sebuah PR idealnya tidak diikutsertakan dalam penghitungan SLA Tim?**
   * A. Saat PR berstatus `Draft` atau berlabel `WIP` (Work in Progress).
   * B. Saat PR berukuran di atas 500 lines of code.
   * C. Saat PR dibuat oleh Junior Engineer.
   * D. Saat PR dibuat di hari Jumat.
   * *Jawaban yang benar:* **A**. PR draft belum siap untuk ditinjau secara formal, sehingga memasukkannya ke kalkulasi SLA akan mendistorsi metrik operational readiness tim.

4. **Dalam konteks Review Load Balancing, apa fungsi dari penerapan *WIP Limits* per reviewer?**
   * A. Membatasi jumlah PR yang dapat dimerge dalam satu sprint.
   * B. Mencegah seorang engineer menerima beban tinjauan baru jika antrean aktifnya sudah mencapai batas kognitif maksimal.
   * C. Menghentikan proses compile CI jika commit terlalu banyak.
   * D. Mengharuskan satu PR direview oleh minimal 5 orang.
   * *Jawaban yang benar:* **B**. WIP limits mengunci kapasitas kognitif aktif agar engineer fokus menuntaskan antrean yang ada sebelum mengemban beban baru.

5. **Apa dampak langsung dari *Merge Lag* yang tinggi dalam arsitektur software?**
   * A. Menurunnya memory footprint pada server produksi.
   * B. Meningkatnya risiko merge conflict dan ketidakcocokan kode dengan state branch utama (*drift*).
   * C. Menurunnya performa database SQL.
   * D. Hilangnya commit history secara permanen di remote origin.
   * *Jawaban yang benar:* **B**. Semakin lama kode yang telah di-approve tertahan sebelum dimerge ke trunk, semakin tinggi probabilitas divergensi terhadap branch `main`.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Buku:**
  * *Software Engineering at Google: Lessons Learned from Programming Over Time* — Titus Winters, Tom Manshreck, Hyrum Wright (Khususnya Bab: "Code Review").
  * *Accelerate: The Science of Lean Software and DevOps* — Nicole Forsgren, Jez Humble, Gene Kim (DORA Metrics & Batch Size Dynamics).
* **Riset & Publikasi Ilmiah:**
  * Rigby, P. C., & Bird, C. (2013). *Convergent contemporary software peer review practice*. Proceedings of the 2013 ESEC/FSE.
  * SmartBear Software. (2006). *Best Kept Secrets of Peer Code Review* (Studi Empiris 200-400 LoC threshold di Cisco).
* **Dokumentasi & Standar Industri:**
  * *Google Engineering Practices Documentation:* Code Review Developer Guide (`eng-practices`).
  * *Linux Kernel Patch Submission Guidelines:* Managing Reviewer Fatigue through Subsystems & Mailbox Queues.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. **Code Review adalah Proses Rekayasa Berantrean:** Mengelola code review menuntut penerapan prinsip throughput, antrean terkontrol, dan mitigasi bottleneck, sama halnya dengan mendesain arsitektur distributed backend.
2. **Dekomposisi Metrik:** Ukur siklus hidup PR secara granular menggunakan *Time to First Review (TTFR)*, *Turnaround Time*, *Rework Time*, dan *Merge Lag*, bukan metrik tunggal agregat yang bias.
3. **Kendalikan Cognitive Load:** Kelelahan review (*review fatigue*) merupakan akar dari kegagalan inspeksi kode. Batasi ukuran PR secara ketat ($\le 300$ LoC) dan bersihkan *extraneous noise* melalui validasi linter/CI otomatis.
4. **Dynamic Load Balancing:** Jangan biarkan penugasan reviewer bergantung pada mekanisme statis yang membebani Tech Lead. Terapkan load balancer cerdas dengan *WIP Limits* untuk meratakan distribusi review.
5. **Keseimbangan SLA:** SLA review harus dipadukan dengan metrik kualitas (*review depth*) untuk mencegah kompromi fatal berupa *rubber-stamping approval*.

---

## SEKSI 17 — GLOSARIUM

* **Time to First Review (TTFR):** Durasi waktu sejak PR dinyatakan terbuka untuk ditinjau hingga reviewer manusia memberikan umpan balik evaluatif pertama.
* **Review Fatigue:** Penurunan drastis energi mental dan ketajaman analisis reviewer akibat volume baris kode yang masif, PR yang tidak terstruktur, atau tumpukan antrean tanpa jeda.
* **Rubber-Stamping:** Tindakan menyetujui (*approving*) PR secara instan tanpa melakukan peninjauan logis, keamanan, atau pengujian arsitektur yang memadai.
* **PR Starvation:** Kondisi di mana PR milik developer tertahan dalam status menunggu review untuk jangka waktu yang sangat lama tanpa kepastian penyelesaian.
* **Stacked Diffs:** Praktik memecah fitur besar menjadi serangkaian PR kecil yang saling bergantung secara sekuensial untuk mempermudah proses peninjauan kode.
* **Merge Lag:** Jeda waktu antara sebuah PR dinyatakan lolos verifikasi (*approved*) hingga perubahan tersebut benar-benar dimerge ke branch utama.
* **WIP (Work In Progress) Limit:** Kebijakan pembatasan jumlah item pekerjaan atau tinjauan aktif yang boleh ditangani oleh satu engineer dalam satu satuan waktu.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Fasilitasi Diskusi Ruang Kelas:** Buka sesi dengan menanyakan kepada peserta: *"Berapa lama rata-rata PR Anda menunggu review di tim masing-masing, dan apa alasan utamanya?"* Gunakan respons mereka untuk mengidentifikasi apakah masalah utama tim berada pada *awareness* (tidak ada notifikasi terstruktur), *distribution* (hanya senior yang mereview), atau *sizing* (PR berukuran monster).
* **Peringatan Simulasi Metrik:** Tekankan secara tegas kepada calon Engineering Manager dan Tech Lead bahwa metrik peninjauan kode **tidak boleh** digunakan sebagai alat evaluasi kinerja individu (misal: "X mereview 50 PR minggu ini, jadi X berkinerja lebih baik dari Y"). Hal ini dijamin akan merusak kultur tim dan memicu sabotase metrik (*metric gaming*).
* **Fokus Hands-on:** Saat membimbing Latihan 3, pastikan peserta memahami cara mengecualikan file autogenerated dari kalkulasi diff PR agar tidak terjadi komplain *false-positive* dari para developer.

---

## SEKSI 19 — CHANGELOG & VERSI

| Versi | Tanggal | Penulis / Reviewer | Deskripsi Perubahan |
| :--- | :--- | :--- | :--- |
| **v1.0.0** | 30 Maret 2026 | Curriculum Lead Architect | Rilis awal materi arsitektur SLA, Review Fatigue, dan Load Balancing. |

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** `CR-ASD-07-02` — *Automated Review Guardrails: Linters, Static Analysis, & Security Gates*
* **Modul Saat Ini:** `CR-ASD-08-01` — *Metrik, SLA, & Mengelola Review Fatigue: PR Turnaround Time, Review Load Balancing, Mengurangi Cognitive Load & Burnout pada Reviewer, SLA Tim*
* **Modul Berikutnya:** `CR-ASD-08-02` — *Scaling Code Review Culture: Pair Reviewing, Cross-Team RFC Reviews, & Knowledge Sharing Patterns*