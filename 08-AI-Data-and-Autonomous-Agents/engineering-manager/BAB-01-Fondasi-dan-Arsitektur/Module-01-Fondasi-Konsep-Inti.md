# Bab 01: Fondasi & Transisi Engineering Management
## Module 01: Transisi Arsitektural dari IC ke EM: Mengelola Sistem Sosioteknikal, Output Equations, dan Delegasi Teknis

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis Pergeseran Paradigma (Bloom's Level 4 - Analysis):** Mengidentifikasi perbedaan deterministik antara kurva produktivitas *Individual Contributor* (IC) berbasis eksekusi langsung versus kurva *Engineering Manager* (EM) berbasis *organizational leverage*.
- **Merancang Framework Delegasi Sosioteknikal (Bloom's Level 6 - Creation):** Mengembangkan matriks akuntabilitas teknis dan delegasi berbasis level kompetensi tim tanpa melepaskan kontrol terhadap *architectural guardrails*.
- **Mengukur Output Sistemik Tim (Bloom's Level 5 - Evaluation):** Mengkuantifikasi performa rekayasa perangkat lunak menggunakan metrik turunan DORA (*DevOps Research and Assessment*) dan *SPACE Framework*, serta mengisolasi bottleneck sosioteknikal.
- **Mengimplementasikan Operational Audit Engine (Bloom's Level 3 - Application):** Membangun skrip automasi untuk mengevaluasi *bus factor*, *PR cycle time*, dan fragmentasi *work-in-progress* (WIP) dalam repositori Git.

---

### 2. Introduction & Conceptual Foundation
Transisi dari seorang *Staff/Senior Software Engineer* menjadi *Engineering Manager* bukanlah promosi linear, melainkan pergantian disiplin ilmu (*horizontal career pivot*). Sebagai IC, determinisme sistem bersifat biner: kode dikompilasi, pengujian integrasi lulus, dan *throughput* ditentukan oleh kapasitas eksekusi individual. Sebagai EM, Anda tidak lagi memprogram CPU; Anda merekayasa sistem sosioteknikal (*sociotechnical system*).

Berdasarkan *Conway's Law* (1967):
> *"Organizations which design systems are constrained to produce designs which are copies of the communication structures of these organizations."*

Arsitektur perangkat lunak merefleksikan topologi komunikasi tim. Jika komunikasi tim Anda *siloed*, arsitektur terdistribusi Anda akan mengalami degradasi menjadi *distributed monolith* dengan *coupling* runtime yang tinggi. Fondasi utama Engineering Management bertumpu pada **Hukum Output High-Output Management** (Andy Grove):

$$\text{Manager's Output} = \text{Team's Output} + \sum (\text{Neighboring Teams Influenced Output})$$

Peran EM adalah memaksimalkan rasio $\frac{\text{Impact}}{\text{Hour}}$ melalui *Managerial Leverage*: aktivitas berbiaya waktu rendah yang menghasilkan dampak operasional terukur berskala besar bagi tim.

---

### 3. Why This Matters
Kegagalan memahami pergeseran peran ini menciptakan fenomena berbahaya:
1. **The Hero Programmer Bottleneck:** EM yang menolak melepaskan repositori kritis menjadi *single point of failure* (SPOF). *Pull Request* (PR) menumpuk karena harus menunggu *review* EM, memicu *latency delivery* yang tinggi.
2. **Technical Drift & Attrisi:** Kegagalan menyediakan ruang otonomi teknis bagi senior engineer berujung pada demotivasi dan *turnover* talenta krusial.
3. **Ghost Management:** EM yang sepenuhnya melepaskan konteks teknis tanpa mekanisme observabilitas internal akan kehilangan kendali atas akumulasi *technical debt*, sehingga mengorbankan stabilitas operasional jangka panjang demi kecepatan semu.

Secara teknis, hilangnya kontrol atas *team topology* meningkatkan *cognitive load* para engineer, yang berbanding lurus dengan peningkatan *Change Failure Rate* (CFR) dan *Mean Time to Recovery* (MTTR) pada lingkungan produksi.

---

### 4. What: Core Concepts & Architecture

#### A. The Sociotechnical Decoupling Model
Sebagai EM, fokus kontrol didelegasikan dari *direct implementation* ke *system constraint design*.

```
+-------------------------------------------------------------------+
|                        LEVEL OF ABSTRACTION                       |
+-------------------------------------------------------------------+
| [IC] Code -> Function -> Microservice -> Direct Infrastructure    |
|   |                                                               |
|   v (Shift of Responsibility)                                     |
| [EM] Process Constraints -> Feedback Loops -> Team Topology       |
+-------------------------------------------------------------------+
```

#### B. The Delegation Matrix (Situational Leadership II Adapted for Tech)
Tingkat delegasi ditentukan oleh *Task-Relevant Maturity* (TRM) engineer pada domain teknis tertentu:

| Tingkat TRM | Karakteristik Engineer | Gaya Manajemen EM | Tindakan Nyata |
| :--- | :--- | :--- | :--- |
| **Rendah** | Baru mengenal codebase/teknologi | *Directive* | Berikan SOP spesifik, *pair programming*, *review* kode harian. |
| **Menengah** | Memahami sintaks, lemah di arsitektur | *Coaching* | Definisikan *interfaces*, diskusikan trade-off, pantau implementasi. |
| **Tinggi** | Menguasai domain teknis dan arsitektur | *Supporting* | Evaluasi *high-level design doc* (RFC), beri otonomi eksekusi. |
| **Ahli** | Domain expert / Staff level | *Delegating* | Berikan problem statement bisnis; minta output berupa roadmap teknis. |

#### C. The Engineering Productivity Formula
Metrik produktivitas tidak boleh mengukur *output* mentah (misal: jumlah commit/baris kode). Metrik harus mengukur kombinasi stabilitas sistem dan efisiensi aliran nilai (*value stream efficiency*):

$$\text{Engineering Velocity} = \frac{\text{Throughput} \times \text{Quality}}{\text{Cognitive Load}}$$

Di mana:
- **Throughput:** *Deployment Frequency* dan *Lead Time for Changes*.
- **Quality:** $1 - \text{Change Failure Rate}$.
- **Cognitive Load:** Derajat fragmentasi konteks (jumlah domain terdistribusi yang harus dikelola oleh satu engineer).

---

### 5. How: Step-by-Step Implementation Guide

Berikut tahapan transisi 90 hari pertama dari IC ke EM untuk membangun ekosistem kerja yang terukur:

```
+-----------------------------------------------------------------------------------+
|                            90-DAY TRANSITION TIMELINE                             |
+-----------------------------------------------------------------------------------+
| [Hari 01-30: Observasi]   Audit codebase, observasi 1:1, petakan SPOF            |
| [Hari 31-60: Stabilisasi] Pasang guardrails, delegasikan PR kritis, atur DORA    |
| [Hari 61-90: Optimasi]    Lepas direct coding, fokus arsitektur sosioteknikal     |
+-----------------------------------------------------------------------------------+
```

#### Langkah 1: Memutus Ketergantungan Eksekusi Kritis (Decoupling)
1. Identifikasi modul yang kepemilikannya hanya ada pada Anda.
2. Buat dokumentasi arsitektur run-time dan dependensi sistem.
3. Alihkan penugasan tiket modul kritis kepada engineer level TRM menengah/tinggi menggunakan teknik *shadowing* (mereka mengerjakan, Anda mengamati).

#### Langkah 2: Membangun Mekanisme Engineering Observability
1. Hubungkan pipeline CI/CD dengan pengumpul metrik (misal: GitHub Actions webhook ke database metrik).
2. Lacak metrik DORA:
   - *Lead Time to Changes* (dari commit pertama hingga rilis produksi).
   - *Deployment Frequency*.
   - *Change Failure Rate* (% deployment yang memerlukan rollback atau hotfix).
   - *Mean Time to Restore* (MTTR).

#### Langkah 3: Menjalankan Cadence Manajemen
1. **1-on-1 Mingguan (30-45 Menit):** Bukan status report. Agenda: hambatan struktural, *career path*, *wellbeing*, dan evaluasi *cognitive load*.
2. **Weekly Engineering Sync (45 Menit):** Review *health metrics*, insiden produksi, dan penyelarasan dependensi lintas tim.
3. **Bi-weekly System Health Review:** Evaluasi rasio alokasi: $70\%$ fitur bisnis, $20\%$ *tech debt & infrastructure*, $10\%$ eksperimentasi/inovasi.

---

### 6. Architectural Diagrams

Diagram di bawah menggambarkan pergeseran struktural aliran kerja: dari model terpusat (Hero Programmer) ke model sosioteknikal terdesentralisasi (Engineering Manager Pattern).

```
Pola Anti-Pattern: The Hero Programmer (SPOF)
+---------------------------------------------------------------------+
|                                                                     |
|   Junior/Mid Dev 1 ----+                                            |
|                        |                                            |
|   Junior/Mid Dev 2 ----+---> [ IC-turned-EM ] ---> Production       |
|                        |       (Code Review,      Deployment        |
|   Junior/Mid Dev 3 ----+        Architecture,                       |
|                                 Direct Coding)                      |
|                                                                     |
+---------------------------------------------------------------------+
* Problem: EM menjadi bottleneck; lead time meningkat linear.

Pola Target: The Sociotechnical Leverage Architecture
+---------------------------------------------------------------------+
|                                                                     |
|  [ Developer Team ]                                                 |
|         |                                                           |
|         v                                                           |
|  +--------------+       CI/CD Guardrails                            |
|  | Automated PR |-----> [ Lint / Test / Sonar ] ---> Auto-Deploy    |
|  +--------------+              |                                    |
|         ^                      v (Telemetry Event)                  |
|         |               +---------------+                           |
|  [ RFC Process ]        | Metric Engine |                           |
|         ^               +---------------+                           |
|         |                      | (DORA Data)                        |
|         |                      v                                    |
|  +---------------------------------------------------------------+  |
|  |                   Engineering Manager                         |  |
|  |       (Optimizes Constraints, Topologies, and Strategy)       |  |
|  +---------------------------------------------------------------+  |
|                                                                     |
+---------------------------------------------------------------------+
* Benefit: Aliran terdistribusi, EM bertindak sebagai perancang feedback loop.
```

---

### 7. Minimal Simple Example

Contoh minimal perhitungan *Managerial Leverage* menggunakan Python. Skrip ini menghitung ROI waktu seorang EM yang memilih mengotomatisasi pipeline deployment daripada melakukan deployment manual berulang kali.

```python
def calculate_managerial_leverage(
    manual_hours_per_week: float,
    automation_setup_hours: float,
    team_size: int,
    weeks: int = 52
) -> dict:
    """
    Menghitung Return on Investment (ROI) waktu EM
    berdasarkan prinsip Andy Grove High-Output Management.
    """
    total_manual_hours_team = manual_hours_per_week * team_size * weeks
    total_cost_automation = automation_setup_hours
    
    saved_hours = total_manual_hours_team - total_cost_automation
    leverage_ratio = total_manual_hours_team / total_cost_automation if total_cost_automation > 0 else 0
    
    return {
        "total_manual_hours_lost": total_manual_hours_team,
        "hours_invested": total_cost_automation,
        "net_hours_saved": saved_hours,
        "leverage_multiplier": round(leverage_ratio, 2)
    }

if __name__ == "__main__":
    # Skenario: EM meluangkan 20 jam membangun script validasi PR & automated staging
    # Menghemat 1.5 jam/minggu untuk 6 orang engineer selama 1 tahun.
    result = calculate_managerial_leverage(
        manual_hours_per_week=1.5,
        automation_setup_hours=20.0,
        team_size=6,
        weeks=52
    )
    print(f"Net Operational Hours Saved: {result['net_hours_saved']} hrs")
    print(f"Leverage Multiplier: {result['leverage_multiplier']}x")
```

---

### 8. Practical Real-World Example

Berikut adalah audit engine sosioteknikal produksi. Skrip Python berikut membedah riwayat Git lokal untuk menganalisis risiko sistem: **Bus Factor Risk Analysis** dan **PR Lead Time Distribution**. Data ini digunakan EM untuk menentukan intervensi struktural tanpa berspekulasi.

```python
#!/usr/bin/env python3
import subprocess
import json
import re
from collections import defaultdict
from typing import Dict, List, Tuple

class SociotechnicalAuditor:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path

    def _run_git(self, args: List[str]) -> str:
        cmd = ["git", "-C", self.repo_path] + args
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return result.stdout.strip()

    def get_bus_factor_distribution(self, path_limit: str = "", commit_limit: int = 500) -> Dict[str, Dict[str, float]]:
        """
        Menghitung persentase kontribusi per direktori untuk mendeteksi SPOF.
        Jika satu engineer menguasai > 70% commit pada suatu modul, area tersebut rentan.
        """
        log_format = "%H|%an|%ad"
        args = ["log", f"-n {commit_limit}", f"--pretty=format:{log_format}", "--name-only"]
        if path_limit:
            args.extend(["--", path_limit])
            
        raw_output = self._run_git(args)
        commits = raw_output.split("\n\n")
        
        module_author_commits = defaultdict(lambda: defaultdict(int))
        module_total_commits = defaultdict(int)

        for block in commits:
            lines = block.strip().split("\n")
            if not lines or "|" not in lines[0]:
                continue
            
            meta = lines[0].split("|")
            author = meta[1]
            files = lines[1:] if len(lines) > 1 else []

            for f in files:
                # Normalisasi path untuk mendapatkan nama modul level-1/level-2
                parts = f.split("/")
                module = parts[0] if len(parts) == 1 else f"{parts[0]}/{parts[1]}"
                
                module_author_commits[module][author] += 1
                module_total_commits[module] += 1

        # Analisis rasio kepemilikan kode
        ownership_report = {}
        for module, authors in module_author_commits.items():
            total = module_total_commits[module]
            if total < 5:  # Abaikan modul yang jarang disentuh
                continue
            ownership_report[module] = {
                author: round((count / total) * 100, 2)
                for author, count in sorted(authors.items(), key=lambda item: item[1], reverse=True)
            }
            
        return ownership_report

    def evaluate_spof_risks(self, ownership_report: Dict[str, Dict[str, float]], threshold_percentage: float = 70.0) -> List[Tuple[str, str, float]]:
        """
        Mengidentifikasi modul dengan Bus Factor = 1.
        """
        risks = []
        for module, authors in ownership_report.items():
            primary_author, percentage = next(iter(authors.items()))
            if percentage >= threshold_percentage:
                risks.append((module, primary_author, percentage))
        return risks

if __name__ == "__main__":
    import sys
    import os

    target_repo = os.getcwd() if len(sys.argv) < 2 else sys.argv[1]
    print(f"[*] Menjalankan audit sosioteknikal pada: {target_repo}")
    
    auditor = SociotechnicalAuditor(target_repo)
    
    try:
        report = auditor.get_bus_factor_distribution(commit_limit=1000)
        spof_risks = auditor.evaluate_spof_risks(report, threshold_percentage=65.0)
        
        print("\n=== SPOF / BUS FACTOR WARNINGS ===")
        if not spof_risks:
            print("[+] Risiko terisolasi. Pengetahuan terdistribusi secara baik.")
        else:
            for module, engineer, pct in spof_risks:
                print(f"[CRITICAL RISK] Modul: '{module}' dikuasai {pct}% oleh '{engineer}'.")
                print(f"                 Rekomendasi EM: Pasangkan Co-Owner via RFC & Cross-review.")
                
        print("\n=== TOP 5 MODULE OWNERSHIP BREAKDOWN ===")
        for module in list(report.keys())[:5]:
            print(f"\nModul: {module}")
            for engineer, pct in list(report[module].items())[:3]:
                print(f"  - {engineer}: {pct}%")
                
    except subprocess.CalledProcessError as e:
        print(f"[-] Gagal menjalankan audit Git: {e.stderr}", file=sys.stderr)
        sys.exit(1)
```

---

### 9. Edge Cases & Failure Modes

Berikut tabel *failure modes* transisi dari IC ke EM beserta mitigasi teknisnya:

| Skenario Edge Case | Pola Kegagalan Internal (*Pathology*) | Dampak Sistemik (*Blast Radius*) | Mitigasi Arsitektural / Manajerial |
| :--- | :--- | :--- | :--- |
| **Produksi P1 saat EM sedang 1-on-1** | EM panik, memotong 1-on-1, mengambil alih terminal SSH/deploy. | Tim menjadi dependen (*learned helplessness*); kapasitas eskalasi mandiri hancur. | Terapkan sistem *On-Call Rotation* (PagerDuty/OpsGenie) dengan *Incident Commander* yang terpisah dari peran EM. |
| **Tech Lead menolak RFC Arsitektur Baru** | Terjadi *deadlock* ideologis antara Senior Engineer vs EM. | Polarisasi tim, pengiriman roadmap tertunda (*schedule slippage*). | Buat *Consensus-Driven RFC Process* dengan batas waktu evaluasi (*time-boxed decision*). Terapkan prinsip: *"Disagree and Commit"*. |
| **EM mengambil porsi Critical Path Jira** | EM menghadiri rapat lintas fungsi; waktu kompilasi kode tertunda. | Sprint gagal diselesaikan; PR tersangkut menunggu kode dari EM. | **Hard Rule:** EM hanya boleh mengambil tiket *non-critical-path*, seperti *internal tooling*, bug prioritas rendah, atau update dokumentasi. |
| **Metrik Manipulasi (Goodhart's Law)** | Tim memecah PR menjadi perubahan trivial demi mengejar *Deployment Frequency*. | Metrik DORA tampak hijau, namun *value delivery* bisnis mendekati nol. | Pasangkan metrik throughput dengan *Lead Time for Changes* dan *Customer Impact Metric*. Audit secara berkala via kuesioner kualitatif SPACE. |

---

### 10. Trade-offs & Analysis

```
+-------------------------------------------------------------------+
|               TRADE-OFF ANALISIS PERAN DAN KEPEMIMPINAN           |
+-------------------------------------------------------------------+
| Opsi Arsitektural Peran:                                          |
|                                                                   |
| [1] Hands-on EM (50% Code, 50% Management)                        |
|     + Konteks teknis tetap tajam.                                 |
|     - Kegagalan ganda: Manajemen terbengkalai, coding terhambat.  |
|                                                                   |
| [2] Hands-off EM (100% Management, 0% Production Code)            |
|     + Fokus leverage, pembinaan talenta, penghapusan blocker.     |
|     - Risiko 'Technical Blindness' jika tidak memvalidasi sistem. |
|                                                                   |
| [3] Architecture-Aware EM (System Governor - RECOMMENDED)         |
|     + Review RFC, pantau DORA, audit code health, no direct lock. |
|     - Memerlukan disiplin boundary & delegasi tingkat tinggi.     |
+-------------------------------------------------------------------+
```

Analisis komparatif pendekatan kepemimpinan:

| Dimensi Evaluasi | Hands-on EM (Coding Manager) | Architecture-Aware EM (System Governor) | Pure People Manager (Non-Technical) |
| :--- | :--- | :--- | :--- |
| **Max Capacity Tim** | $\le 4\text{ Engineer}$ | $6 - 9\text{ Engineer}$ | $10+\text{ Engineer}$ |
| **Depth of Architectural Context**| Tinggi (micro-level) | Tinggi (macro/systemic level) | Rendah (bergantung penuh pada TL) |
| **Throughput Bottleneck** | Sangat Tinggi (EM menjadi bottleneck) | Rendah (otomatisasi via CI/CD) | Nol (tidak menyentuh PR) |
| **Resilience terhadap Incident** | Buruk (EM sering over-commit) | Optimal (observabilitas terpasang) | Bergantung pada engineering lead |

---

### 11. Best Practices & Antipatterns

#### Best Practices
- **Implementasikan "Guardrails Over Gates":** Daripada Anda me-*review* setiap baris kode, konfigurasikan *linter*, *static analysis security testing* (SAST), dan *test coverage check* otomatis pada pipeline CI/CD.
- **Terapkan Asynchronous Decision Making:** Gunakan *Architecture Decision Records* (ADR) di dalam Git. Setiap keputusan struktural harus terdokumentasi dan dapat ditelusuri riwayatnya (*auditable*).
- **Audit "Calendar Fragmentation":** Lindungi fokus tim dengan memberlakukan blokade waktu khusus: *No-Meeting Days* (misal: Selasa & Kamis).

#### Antipatterns (Code/Management Smells)
- **The "Shadow Architect":** Mendikte detail implementasi tanpa mendengarkan saran dari engineer yang menggarap kode langsung.
- **Skip-Level Blindness:** Hanya berbicara dengan Tech Lead, mengabaikan kondisi kerja para Software Engineer di tingkat implementasi.
- **Metrics Gaming:** Mengukur jam kerja aktif di IDE atau jumlah baris kode (LOC) yang dibuat.

---

### 12. Testing, Verification & Validation

Bagaimana Anda memverifikasi bahwa efektivitas transisi Anda berjalan dengan baik secara sosioteknikal? Gunakan kerangka validasi berikut:

#### 1. Validasi Distribusi Beban (Cognitive Load Audit)
Jalankan evaluasi kuartalan menggunakan kuesioner dengan model Likert scale (1-5):
- *Domain Familiarity:* Seberapa sering Anda harus mengubah kode di repositori yang tidak Anda pahami konteksnya?
- *Deployment Confidence:* Seberapa yakin Anda bahwa perubahan kode Anda tidak akan memicu insiden di sistem lain?

#### 2. Verification Dashboard Script (DORA Health Check)
Berikut skrip verifikasi otomatis untuk memeriksa ambang batas kesehatan tim:

```python
def verify_team_operational_health(
    lead_time_hours: float,
    deployment_freq_per_day: float,
    cfr_percentage: float,
    mttr_minutes: float
) -> Dict[str, str]:
    """
    Memvalidasi performa operasional tim berdasarkan standar DORA Elite/High performer.
    """
    validations = {}
    
    # Lead Time < 24 Hours
    validations["lead_time"] = "PASS" if lead_time_hours <= 24.0 else "FAIL: High latency delivery"
    
    # Deployment Frequency >= 1 per day
    validations["deployment_frequency"] = "PASS" if deployment_freq_per_day >= 1.0 else "FAIL: Low deployment throughput"
    
    # Change Failure Rate <= 15%
    validations["change_failure_rate"] = "PASS" if cfr_percentage <= 15.0 else "FAIL: Quality degradation"
    
    # MTTR < 60 Minutes
    validations["mttr"] = "PASS" if mttr_minutes <= 60.0 else "FAIL: Ineffective incident triage"
    
    return validations

# Contoh eksekusi audit:
status = verify_team_operational_health(
    lead_time_hours=12.5,
    deployment_freq_per_day=3.0,
    cfr_percentage=8.5,
    mttr_minutes=35.0
)
for metric, result in status.items():
    print(f"[{result.split(':')[0]}] {metric}: {result}")
```

---

### 13. Performance & Optimization

Untuk mengoptimalkan efisiensi rekayasa perangkat lunak tanpa menambah beban kerja (*headcount*):

1. **Eliminasi Waste dalam Feedback Loops:**
   - **Triage Kompilasi Lambat:** Jika CI memakan waktu $> 15\text{ menit}$, tim akan kehilangan konteks (*context switching*). Investasikan waktu untuk memperbaiki skema caching build Docker dan menjalankan unit test secara paralel.
2. **Optimasi Pull Request Size:**
   - Batasi PR maksimal $\le 400$ baris perubahan. PR kecil ditinjau lebih cepat, memiliki risiko regresi lebih rendah, dan mempercepat siklus merge secara eksponensial.
3. **Penerapan Trunk-Based Development:**
   - Tinggalkan pola *GitFlow* yang kompleks dengan branch rilis yang berumur panjang. Beralihlah ke *Trunk-Based Development* yang didukung fitur *Feature Flags* untuk memisahkan logika rilis kode dari waktu aktivasi fitur.

---

### 14. Security & Compliance Implications

Sebagai EM, Anda adalah benteng pertama dalam tata kelola keamanan dan kepatuhan (*governance, risk, and compliance* / GRC):

- **Prinsip Least Privilege (PoLP):** Akses write ke branch `main` atau akses produksi AWS/GCP tidak boleh diberikan secara statis ke workstation lokal engineer. Akses rilis wajib melalui pipeline CI/CD yang terotentikasi dan tersimpan riwayatnya (*audit trail*).
- **SOC2 & ISO 27001 Access Review:** EM wajib melakukan audit akses pengguna secara berkala setiap kuartal. Pastikan akun engineer yang telah beralih proyek atau mengundurkan diri langsung dicabut hak aksesnya.
- **Dependency Vulnerabilities Management:** Terapkan pemindaian ketergantungan otomatis (misal: Snyk, Dependabot) yang otomatis memblokir merge PR jika ditemukan kerentanan dengan keparahan berstatus *Critical* / *High* (CVE score $\ge 7.0$).

---

### 15. Operational Runbook & Troubleshooting

#### Masalah: "Velocity Tim Turun Drastis Pasca Rilis Arsitektur Baru"
Gunakan alur panduan operasional di bawah untuk melakukan identifikasi dan perbaikan:

```
[Mulai Investigasi]
       |
       v
Apakah DORA CFR Meningkat?
    ├── Ya  --> Ada regresi kode/infrastruktur. Hentikan fitur baru.
    │           Jalankan alokasi 100% bug fix & stabilisasi pipeline.
    │
    └── Tidak --> Periksa Mean Pull Request Review Time (Lead Time sub-segment)
            ├── Review Time > 48 Jam
            │   └── Diagnosis: Review bottleneck.
            │       Solusi: Wajibkan pair-review & kurangi batas ukuran PR (<300 LOC).
            │
            └── Review Time < 24 Jam
                └── Periksa Rasio Rework (Churn Rate Kode)
                    ├── Churn Rate > 30%
                    │   └── Diagnosis: Spesifikasi produk tidak jelas.
                    │       Solusi: Perbaiki kolaborasi PM/EM pada tahap penulisan PRD.
                    └── Churn Rate Normal
                        └── Lakukan audit cognitive load internal tim.
```

---

### 16. Scalability & Evolution

Seiring pertumbuhan tim dari 5 menjadi 50 engineer, terapkan prinsip evolusi topologi berikut:

```
FASE 1: Stream-Aligned Monolith
+------------------------------------------------------------+
| Single Pod (1 EM, 6 Engineers) -> Full Stack Responsibilities|
+------------------------------------------------------------+
                           |
                           v  (Headcount bertambah > 15)
FASE 2: Functional Decoupling
+------------------------------------------------------------+
| EM 1: Payments Stream      | EM 2: Core Logistics Stream   |
+------------------------------------------------------------+
                           |
                           v  (Headcount bertambah > 30)
FASE 3: Team Topologies Model (Platform + Stream)
+------------------------------------------------------------+
| [Stream-Aligned Pod A]       [Stream-Aligned Pod B]         |
|             \                      /                       |
|              v                    v                        |
|       +------------------------------------+               |
|       | Platform Team (Internal Dev Tools) |               |
|       | Lead by Platform EM                |               |
|       +------------------------------------+               |
+------------------------------------------------------------+
```

Peralihan ini mencegah replikasi infrastruktur umum (misal: pipeline deployment, logging stack) di tiap tim produk, sehingga beban kognitif pada masing-masing *stream-aligned team* tetap terkontrol.

---

### 17. Integration with Other Systems / Modules

Modul ini memiliki keterkaitan langsung dengan bab-bab berikutnya dalam kurikulum Engineering Management:
- **Integrasi ke Bab 02 (People Management & Hiring):** Framework delegasi sosioteknikal pada modul ini menjadi tolok ukur penentuan *hiring rubric* serta evaluasi kesenjangan kompetensi (*skill gap analysis*) di dalam tim.
- **Integrasi ke Bab 04 (Technical Debt & Architecture Governance):** Evaluasi *bus factor* dan kepemilikan kode menjadi fondasi pembuatan *Architecture Review Board* (ARB) dan prioritisasi refactor.
- **Integrasi ke Bab 06 (Cross-Functional Alignment):** Model eliminasi waste dan stabilitas throughput DORA menjadi modal utama EM dalam proses negosiasi kapasitas sprint bersama Product Manager.

---

### 18. Self-Assessment Exercises

Selesaikan dua skenario studi kasus berikut secara mandiri:

#### Skenario 1: The Bottleneck Architect
Anda baru saja dipromosikan menjadi EM untuk tim yang beranggotakan 6 engineer. Sebelumnya, Anda adalah *Lead Architect*. Ada satu microservice inti (*Payment Orchestrator*) yang Anda rancang sendiri. Tim merasa takut mengubah modul tersebut karena kompleksitas *concurrency*-nya, sehingga Anda masih rutin meninjau dan menulis fitur di modul tersebut hingga 15 jam per minggu. Dampaknya, review PR tim lain tertunda rata-rata 3 hari.
- **Tugas:** Buat rencana aksi 30 hari untuk melepaskan diri dari *critical path* modul pembayaran tersebut tanpa meningkatkan risiko *runtime failure*!

#### Skenario 2: Analysis Failure (Git Audit Challenge)
Ambil salah satu repositori Git di organisasi Anda, lalu jalankan skrip `SociotechnicalAuditor` dari Seksi 8 di atas.
- **Tugas:**
  1. Identifikasi 2 modul dengan tingkat dependensi tertinggi pada satu orang engineer (*Bus Factor = 1*).
  2. Rancang 1 dokumen RFC singkat (maksimal 1 halaman) yang mendistribusikan konteks modul tersebut kepada minimal 2 engineer lainnya melalui skema *knowledge transfer* dan *ownership transfer*.

---

### 19. Further Reading & References

1. **Books:**
   - Grove, Andrew S. *High Output Management*. Random House, 1983 (Prinsip Managerial Leverage).
   - Skelton, Matthew, and Manuel Pais. *Team Topologies: Organizing Business and Technology for Fast Flow*. IT Revolution Press, 2019.
   - Forsgren, Nicole, Jez Humble, and Gene Kim. *Accelerate: The Science of Lean Software and DevOps*. IT Revolution Press, 2018.
2. **Papers & Standards:**
   - Conway, Melvin E. "How do Committees Invent?" *Datamation*, 1968.
   - Forsgren, et al. "The SPACE of Developer Productivity." *ACM Queue*, 2021.
3. **Engineering Blogs:**
   - Charity Majors (Honeycomb.io): *The Engineer/Manager Pendulum*.
   - Gergely Orosz: *The Pragmatic Engineer: Managing Software Engineers*.

---

### 20. Summary & Key Takeaways

1. **Perubahan Peran adalah Horizontal:** Beralih ke posisi EM bukanlah penambahan gelar senioritas semata, melainkan pergantian disiplin dari memprogram komputer ke merekayasa ekosistem sistem sosioteknikal tim.
2. **Managerial Leverage Menggantikan Direct Output:** Nilai seorang EM diukur dari performa keseluruhan tim dan tim-tim di sekitarnya, bukan dari baris kode yang ditulis sendiri di Jira.
3. **Optimalkan Conway's Law:** Bangun struktur komunikasi, kepemilikan modul, dan guardrails teknis yang sehat untuk menjaga arsitektur perangkat lunak tetap modular dan skalabel.
4. **Lepaskan Critical Path:** Jangan pernah menjadi penghambat di alur kerja utama tim Anda. Alihkan fokus Anda ke membangun otomatisasi pipeline, mendistribusikan kepemilikan kode, dan memitigasi *single point of failure* (SPOF) menggunakan pendekatan terukur (*data-driven*).