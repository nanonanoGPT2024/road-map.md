# Modul 01: Incident Lifecycle, On-Call, & Blameless Post-Mortem

## 1. Learning Objective
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- Mengoperasikan Incident Command System (ICS) secara disiplin dalam situasi krisis sistem terdistribusi skala besar.
- Mengklasifikasikan insiden secara presisi menggunakan Severity Matrix (SEV-1 hingga SEV-4) berdasarkan dampak bisnis dan SLA/SLO.
- Membangun dan mengotomatisasi Escalation Policies serta Alert Routing menggunakan arsitektur modern (PagerDuty/Opsgenie) via Infrastructure as Code (Terraform).
- Memfasilitasi sesi Blameless Post-Mortem tanpa atribusi kesalahan individu (*counterfactual reasoning bias*) dan menerapkan teknik 5-Whys yang berorientasi sistemik.
- Mengidentifikasi, mengukur, dan mereduksi Mean Time to Detect (MTTD), Mean Time to Acknowledge (MTTA), dan Mean Time to Resolve (MTTR) melalui *actionable post-mortem engineering work*.

---

## 2. Prerequisite
- Pemahaman mendalam mengenai Observability (Metrik, Log, Trace, SLI, SLO, Error Budget).
- Kemampuan dasar Infrastructure as Code (Terraform/OpenTofu) untuk deklarasi alert router.
- Pengalaman dasar navigasi Linux CLI dan REST API integration (Webhooks, Alertmanager).
- Pemahaman fundamental tentang arsitektur microservices dan titik kegagalan (*single point of failure* / cascading failure).

---

## 3. Concept
Incident Management dalam Site Reliability Engineering (SRE) adalah metodologi terstruktur untuk merespons, memitigasi, menganalisis, dan mencegah kegagalan tak terduga pada sistem produksi. Fondasi utamanya bersumber dari adaptasi sipil terhadap Incident Command System (ICS) milik US National Incident Management System (NIMS). 

Sistem ini memisahkan kendali komando menjadi peran yang terspesialisasi:
1. **Incident Commander (IC):** Pemegang kendali absolut operasional insiden; bertugas memfasilitasi keputusan, mendelegasikan tugas, dan menghilangkan hambatan (*clearing roadblocks*). IC tidak melakukan debugging langsung.
2. **Tech Lead (TL) / Operations Lead:** Memimpin investigasi teknis, membaca metrik, mengeksekusi mitigasi (*rollback*, *traffic shift*, *rate limiting*), dan mengoordinasikan *subject matter experts* (SME).
3. **Communications Lead (CL):** Mengisolasi IC dan TL dari gangguan eksternal dengan mengelola komunikasi berkala kepada para pemangku kepentingan (*stakeholders*), divisi operasional bisnis, tim customer support, dan halaman status publik (*statuspage*).

Siklus hidup insiden beroperasi berdasarkan prinsip bahwa kegagalan sistem terdistribusi adalah keniscayaan (*failure is an inevitable emergent property of complex systems*). Oleh karena itu, budaya pasca-insiden didasarkan pada **Blameless Culture**: kegagalan dianalisis sebagai anomali desain sistem, limitasi tooling, atau kelemahan proses proteksi, bukan kelalaian manusia (*human error is a symptom, not the root cause*).

---

## 4. Why
Tanpa struktur manajemen insiden yang formal, organisasi menghadapi serangkaian patologi teknis dan psikologis:
- **Hero Culture & Burnout:** Respon bergantung pada segelintir insinyur senior yang dibangunkan di luar jam kerja secara tidak teratur, memicu degradasi performa kognitif dan *attrition*.
- **Bystander Effect & Chaos:** Tanpa IC tunggal, puluhan engineer masuk ke call konferensi tanpa arah, saling menimpa konfigurasi, dan memperparah *blast radius* (contoh: me-restart database secara serentak saat terjadi antrean lock).
- **Executive Heckling:** Manajemen eksekutif langsung menginterupsi teknisi yang sedang memulihkan sistem, merusak fokus dan memperpanjang durasi *downtime*.
- **Recurring Outages:** Tanpa post-mortem tanpa menyalahkan (*blameless*) dan pelacakan item aksi yang terukur, insiden serupa dengan pola kegagalan yang sama akan berulang, membakar habis *error budget*.

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 Incident Command System (ICS) Roles & Responsibilities

```
+-------------------------------------------------------------+
|                     Incident Commander                      |
|  - Mengendalikan tempo penanganan                           |
|  - Memberikan delegasi eksplisit ("Alice, telusuri DB lock")|
|  - Sinkronisasi status berkala (setiap 10-15 menit)        |
+--------------+------------------------------+---------------+
               |                              |
               v                              v
+-------------------------------+ +-------------------------------+
|      Technical Lead (TL)      | |    Communications Lead (CL)   |
| - Menganalisis telemetri      | | - Internal updates (Slack/Mail)|
| - Menentukan hipotesis teknis | | - External Statuspage updates |
| - Eksekusi mitigasi           | | - Mengisolasi interupsi exec  |
+---------------+---------------+ +-------------------------------+
                |
     +----------+----------+
     |                     |
     v                     v
+----------+          +----------+
|  SME #1  |          |  SME #2  |
| Database |          | Network  |
+----------+          +----------+
```

1. **Incident Commander (IC):**
   - Menetapkan mode krisis (*declaring an incident*).
   - Memastikan tidak ada dua orang mengerjakan hal yang sama tanpa koordinasi.
   - Melakukan transfer kepemimpinan (*handover*) secara eksplisit dan tertulis jika durasi insiden melebihi batas kelelahan kognitif (> 4 jam).
2. **Technical Lead (TL):**
   - Mengarahkan *debugging loop*: Hipotesis $\to$ Uji Telemetri $\to$ Mitigasi $\to$ Validasi.
   - Melarang perbaikan permanen (*root-cause fix*) jika tindakan tersebut memperpanjang MTTR; prioritas mutlak adalah **mitigasi dampak** (*service restoration*), bukan penyelesaian sempurna di tengah kepanikan.
3. **Communications Lead (CL):**
   - Menggunakan format komunikasi terstandarisasi: 
     - *Dampak:* Apa yang rusak dan siapa pengguna yang terpengaruh.
     - *Status:* Apa yang sedang dieksekusi tim saat ini.
     - *Next Update:* Waktu pasti pembaruan informasi berikutnya (misal: "Update berikutnya pukul 14:15 UTC").

### 5.2 Severity Matrix

Penetapan tingkat keparahan (*severity level*) harus deterministik, bukan berdasarkan intuisi emosional atau tekanan jabatan.

| Severity Level | Definisi Operasional | Kriteria Finansial & SLO | Escalation & Response SLA | Frekuensi Update Komunikasi |
|---|---|---|---|---|
| **SEV-1 (Critical)** | Kegagalan katastropik sistem produksi. Core value proposition lumpuh total. | Error budget terbakar $\ge 10\%$ dalam 1 jam; Data loss terancam; Transaksi utama 0%. | Paging instan untuk IC, TL, Core SME. Respon MTTA < 5 menit. War room dibuka 24/7. | Setiap 15 menit |
| **SEV-2 (Major)** | Kerusakan fungsionalitas utama dengan degradasi parah. Sebagian besar user terdampak tanpa *workaround*. | Error budget terbakar signifikan; Kegagalan payment provider redundan; Latensi $P99 > 5\times$ SLO. | Paging on-call primary & secondary. Respon MTTA < 15 menit. | Setiap 30 menit |
| **SEV-3 (Moderate)** | Masalah operasional terisolasi. Fungsionalitas non-kritis terganggu; terdapat *workaround* manual/parsial. | Error budget konsumsi normal; Admin panel lambat; Layanan reporting internal mati. | Alerting normal via on-call queue. Respon MTTA < 1 jam (Jam kerja/Next on-call shift). | Setiap 2-4 jam |
| **SEV-4 (Low/Minor)** | Isu minor, kosmetik UI, performa sub-optimal yang tidak melanggar SLO, bug non-esensial. | Dampak pendapatan 0%; Tidak ada pelanggaran SLO. | Tiket Jira backlog; tidak memicu alert pager mekanis. Respon: Next sprint cycle. | Berdasarkan permintaan |

### 5.3 Alert Routing, Schedules, & Escalation Policies

Sistem modern seperti PagerDuty dan Opsgenie memodelkan perutean alert menggunakan dependensi berjenjang:
- **Tiers of Escalation:**
  - *Level 1 (Primary On-Call):* Pager berbunyi (Push Notification $\to$ SMS $\to$ Voice Call dalam interval 5 menit).
  - *Level 2 (Secondary On-Call / Shadow):* Terpicu jika Level 1 tidak melakukan *Acknowledge* (ACK) dalam rentang 10 menit.
  - *Level 3 (Engineering Manager / Lead On-Call):* Terpicu jika Level 2 tidak melakukan ACK dalam rentang 15 menit berikutnya.
- **Alert De-duplication & Flapping Suppression:**
  - Alert manager mengelompokkan alert berdasarkan label identik (`alertname`, `cluster`, `namespace`) untuk mencegah badai alert (*alert fatigue*). Jika sebuah alert menyala (*firing*) dan padam (*resolved*) berulang kali dalam kurun waktu singkat, sistem menerapkan penalti eksponensial (*hold-down timer*).

### 5.4 Blameless Culture & Root Cause Fallacy
- **The Fallacy of "Root Cause":** Sistem sosio-teknis yang kompleks tidak pernah gagal karena satu penyebab tunggal (*root cause is a myth*). Kegagalan adalah hasil pertemuan berbagai kondisi batas, kegagalan tersembunyi (*latent failures*), dan keputusan teknis masa lalu.
- **Counterfactual Reasoning Avoidance:** Hindari frase bias seperti: "Seharusnya teknisi mengecek...", "Jika saja pengujian dijalankan...", atau "Operator salah mengetik perintah...". Ganti analisis dengan: "Faktor apa dalam antarmuka CLI yang mengizinkan eksekusi destruktif tanpa konfirmasi ganda?", atau "Kondisi sistemik apa yang membuat verifikasi otomatis terlewati?".
- **5-Whys Methodology:** Dilakukan secara relasional berantai untuk menelusuri arsitektur sistemik, kebijakan otomasi, dan batasan perlindungan perangkat lunak, bukan untuk mencari nama individu.

### 5.5 Action Items Tracking & MTTR Metrics
- **Kategori Item Aksi:**
  - *Mitigate:* Mempercepat deteksi dan pemulihan jika anomali serupa terjadi (Otomasi rollback, penambahan alert SLI).
  - *Prevent:* Memodifikasi arsitektur untuk memutus rantai propagasi kegagalan (*circuit breaking*, *bulkheading*).
  - *Process:* Dokumentasi runbook baru, pelatihan simulasi *chaos engineering*.
- **Metrik Kunci:**
  $$\text{MTTD} = \frac{\sum (T_{\text{detected}} - T_{\text{event\_start}})}{N}$$
  $$\text{MTTA} = \frac{\sum (T_{\text{acknowledged}} - T_{\text{alert\_fired}})}{N}$$
  $$\text{MTTR} = \frac{\sum (T_{\text{mitigated}} - T_{\text{event\_start}})}{N}$$

---

## 6. How
Implementasi siklus insiden end-to-end:

1. **Deklarasi:** Alert sistem menyala atau laporan eskalasi manual masuk. Teknisi jaga mengetik perintah `/incident declare` pada chat workspace (Slack/Teams).
2. **Inisialisasi Role:** Pagerduty/Opsgenie meng-assign IC. Saluran komunikasi instan khusus dibuat otomatis (`#inc-20231024-db-deadlock`) beserta link video war room.
3. **Triase & Mitigasi:** IC menetapkan severitas (misal SEV-1), menunjuk Tech Lead untuk eksekusi, dan menunjuk Communications Lead untuk mengupdate statuspage.
4. **Resolusi Sementara:** Fokus pada *service restoration*. Jika rilis versi `v2.4.1` menyebabkan memory leak, perintah mitigasi adalah *rollback* ke `v2.4.0` atau *drain traffic*, bukan mereview patch C++ di tengah krisis.
5. **Post-Mortem Gathering:** 24-48 jam setelah insiden selesai, draf post-mortem disusun dengan data telemetri yang valid. Tim mengadakan review sinkronus selama 45 menit.
6. **Eksekusi Remediasi:** Action items dimasukkan ke issue tracking board dengan prioritas setara dengan tiket fitur bisnis (P0/P1), bukan diarsipkan ke backlog abadi.

---

## 7. Analogy
Bayangkan sebuah kokpit pesawat komersial modern yang mengalami malfungsi mesin ganda di udara.
- **Pilot In Command (Incident Commander):** Tidak memegang buku manual teknis atau membetulkan kabel di panel mesin. Pilot fokus menjaga orientasi pesawat, mendistribusikan tugas, dan mempertahankan altitudo aman.
- **First Officer (Tech Lead):** Mengeksekusi checklist darurat, mengatur tuas hidrolik, dan mengisolasi instrumen mesin yang terbakar.
- **Radio Controller Liaison (Communications Lead):** Berkomunikasi stabil dengan Air Traffic Control (ATC) dan mengumumkan instruksi keselamatan kepada penumpang di kabin tanpa memicu kepanikan massal.
- **Blameless Black Box Analysis:** Pasca-pendaratan darurat, investigasi National Transportation Safety Board (NTSB) tidak memidanakan kru kokpit jika mereka menekan tombol yang salah karena tata letak tombol switch yang identik dalam kondisi turbulensi. Sebagai gantinya, regulator merevisi standar manufaktur kokpit agar kesalahan ergonomis tersebut mustahil terulang.

---

## 8. Diagram (ASCII)

### Siklus Insiden Lengkap (Incident Lifecycle State Machine)

```
 [Normal Operations]
         |
         v
 [ANOMALY DETECTED]  ---> (Alert Triggered / Synthetic Test Failed)
         |
         v
 [TRIAGE & PAGING]   ---> (MTTD Ends, MTTA Begins)
         |
         +--> [PagerDuty / Opsgenie Policy]
                   |
                   v
 [ACKNOWLEDGED]      ---> (MTTA Ends, IC Assumes Command)
         |
         v
 [WAR ROOM FORMED]   ---> Role Delegation: [IC] | [Tech Lead] | [Comms Lead]
         |
         +---> (Severity Matrix Check: SEV-1 to SEV-4)
         |
         v
 [INVESTIGATION & HYPOTHESIS TESTING]
         |
         +---> Mitigation Attempt (Rollback / Traffic Drain / Scaling)
         |
         v
 [IMPACT MITIGATED]  ---> (MTTR Ends, Production Restored, Monitoring Phase)
         |
         v
 [INCIDENT CLOSED]
         |
         +-----------------------------+
         | Post-Mortem Phase (T+48h)  |
         | - Timeline Reconstruction   |
         | - 5-Whys Analysis (Blameless|
         | - Action Items to Jira/Git  |
         +-----------------------------+
```

---

## 9. Simple Example
Penerapan 5-Whys yang menyalahkan individu versus analisis sistemik:

**Kasus:** *Seorang engineer menjalankan `DROP TABLE users;` di production cluster.*

*Pendekatan Cacat (Blame-Centric):*
1. Mengapa database down? Karena tabel user terhapus.
2. Mengapa terhapus? Karena insinyur Bob mengeksekusi script query yang salah.
3. Mengapa Bob mengeksekusi script itu? Karena Bob ceroboh dan tidak membaca instruksi.
4. Mengapa Bob ceroboh? Kurang fokus karena kerja larut malam.
5. Tindakan: Bob diberikan surat peringatan dan diwajibkan membaca ulang SOP. *(Hasil: Insiden terulang 3 bulan kemudian oleh Alice).*

*Pendekatan SRE (Blameless Systemic Analysis):*
1. Mengapa database down? Karena tabel user terhapus dari production cluster.
2. Mengapa terhapus? Karena script deployment database staging terkoneksi ke connection string endpoint production.
3. Mengapa terkoneksi ke production? Karena environment variable `DATABASE_URL` di staging server mewarisi nilai secret production via IAM role yang terlalu longgar (*over-privileged*).
4. Mengapa query destruktif bisa tereksekusi tanpa approval? Karena database CLI tidak mengaktifkan safe-mode (`--safe-updates`) dan kredensial aplikasi memiliki hak akses DDL (`DROP`) pada jam operasional bisnis.
5. Mengapa tidak ada mekanisme pemulihan instan? Karena point-in-time recovery (PITR) belum pernah diuji secara otomatis dalam pipeline CI/CD pemulihan bencana.
6. Tindakan Aksi: Cabut hak DDL runtime app, pisahkan VPC staging/prod secara kriptografis, aktifkan proteksi drop table pada cluster proxy, dan otomatisasi latihan disaster recovery periodik.

---

## 10. Practical Example (Konfigurasi CLI / Terraform / Hands-on)

### Konfigurasi Terraform: PagerDuty Escalation Policy & Service Integration

```hcl
terraform {
  required_providers {
    pagerduty = {
      source  = "pagerduty/pagerduty"
      version = "~> 3.0"
    }
  }
}

# Provider configuration via environment variable PAGERDUTY_TOKEN
provider "pagerduty" {}

# User definitions
resource "pagerduty_user" "sre_lead" {
  name  = "Alex Mercer (Principal SRE)"
  email = "alex.mercer@enterprise.internal"
  role  = "user"
}

resource "pagerduty_user" "sre_secondary" {
  name  = "Jordan Blake (Senior SRE)"
  email = "jordan.blake@enterprise.internal"
  role  = "user"
}

# On-Call Schedules
resource "pagerduty_schedule" "primary_rotation" {
  name      = "Core Payments Primary Rotation"
  time_zone = "Asia/Jakarta"

  layer {
    name                         = "Weekly Shift"
    start                        = "2023-11-01T09:00:00+07:00"
    rotation_virtual_start       = "2023-11-01T09:00:00+07:00"
    rotation_turn_of_hand_format = "change"
    rotation_turn_of_hand_length = 7
    rotation_turn_of_hand_unit   = "days"
    users                        = [pagerduty_user.sre_lead.id, pagerduty_user.sre_secondary.id]
  }
}

# Multi-Tier Escalation Policy
resource "pagerduty_escalation_policy" "payments_escalation" {
  name      = "Payments High-Urgency Escalation Policy"
  num_loops = 3

  # Tier 1: Primary On-Call Engineer (Ack window: 10 minutes)
  rule {
    escalation_delay_in_minutes = 10
    target {
      type = "schedule_reference"
      id   = pagerduty_schedule.primary_rotation.id
    }
  }

  # Tier 2: Secondary / Backup Lead (Ack window: 15 minutes)
  rule {
    escalation_delay_in_minutes = 15
    target {
      type = "user_reference"
      id   = pagerduty_user.sre_secondary.id
    }
  }
}

# Production Service Binding with Severity Filtering
resource "pagerduty_service" "payments_api" {
  name                    = "Payments API Gateway"
  auto_resolve_timeout    = 14400 # 4 hours
  acknowledgement_timeout = 600   # 10 minutes
  escalation_policy       = pagerduty_escalation_policy.payments_escalation.id
  alert_creation          = "create_alerts_and_incidents"

  incident_urgency_rule {
    type    = "use_support_hours"
    
    during_support_hours {
      type    = "constant"
      urgency = "high"
    }

    outside_support_hours {
      type    = "constant"
      urgency = "high"
    }
  }
}

# Integration via Events API v2 for Prometheus Alertmanager
resource "pagerduty_service_integration" "alertmanager_webhook" {
  name    = "Prometheus Alertmanager Integration"
  service = pagerduty_service.payments_api.id
  vendor  = "b80f12c3f8e44e2b8b939ab7d287ef28" # Alertmanager Vendor ID
}

output "integration_routing_key" {
  value     = pagerduty_service_integration.alertmanager_webhook.integration_key
  sensitive = true
}
```

---

## 11. Real World Example
Kasus nyata pada sebuah sistem Core Banking/Fintech Unicorn:

- **Insiden:** Pukul 00:03 WIB, batch settlement processing memicu lonjakan koneksi database hingga batas *max_connections* (5000 koneksi), menyebabkan connection pool starvation pada layanan transfer antar bank. Transaksi transfer gagal total dengan error HTTP 503.
- **Tindakan Komando:**
  - Pager berbunyi (SEV-1 diaktifkan otomatis oleh SLI Error Rate > 5% selama 3 menit).
  - IC mengambil alih room, melarang developer mengubah kode settlement.
  - Tech Lead mengidentifikasi starvation dan segera mengeksekusi mitigasi: mengalihkan lalu lintas baca ke failover read-replica, menurunkan kapasitas batch worker via kubernetes Horizontal Pod Autoscaler override (`replicas: 0`), dan menerapkan rate-limiting via Envoy API Gateway.
  - Comms Lead memperbarui statuspage eksternal setiap 15 menit, memberitahukan bahwa transaksi sedang mengalami antrean.
  - Pukul 00:38 WIB, tingkat keberhasilan transfer kembali ke 99.98% (Sistem Termitigasi, durasi 35 menit).
- **Post-Mortem & Resolusi:**
  - Analisis 5-Whys membuktikan bahwa parameter connection idle timeout pada pool driver JVM tidak dikonfigurasi (*default infinite*).
  - Diterbitkan tiket P0 untuk mengimplementasikan connection pooling berbasis proxy (PgBouncer/AWS RDS Proxy) dan membatasi worker thread pool. MTTR berkurang drastis pada pengujian beban berikutnya.

---

## 12. Trade-offs

| Pendekatan / Paradigma | Keuntungan | Kerugian / Biaya |
|---|---|---|
| **Ketat Mengikuti ICS (Strict ICS Roles)** | Mengeliminasi kebingungan hierarki; komunikasi fokus dan terstruktur; mencegah interupsi eksekutif. | Memerlukan overhead personel minimum 3 engineer berpengalaman untuk insiden besar; canggung untuk tim rintisan berskala kecil (< 5 orang). |
| **Agresif Auto-Paging (Threshold Rendah)** | Mendeteksi degradasi sebelum user menyadarinya; MTTD mendekati 0 menit. | Risiko tinggi *Alert Fatigue*; insinyur on-call mengalami disonansi kognitif dan mulai mengabaikan alert (*desensitization*). |
| **Mitigasi Cepat (Aggressive Blast Mitigation)** | MTTR sangat rendah; customer tidak merasakan dampak berlarut-larut. | Kemungkinan kehilangan *in-flight context/state* (misal: restart instan pod menghapus memori core-dump untuk investigasi pasca-insiden). |
| **Blameless Culture Tanpa Kompromi** | Kolaborasi transparan; insinyur tidak menyembunyikan kesalahan; akar masalah arsitektural terekspos. | Rentan disalahartikan sebagai "tidak ada akuntabilitas" jika kepemimpinan tidak membedakan antara kecelakaan kognitif vs kelalaian etika disengaja (*gross negligence*). |

---

## 13. When To Use
- Terapkan ICS dan eskalasi ketat ketika terjadi pelanggaran SLO yang berdampak langsung pada customer (*user-facing downtime*).
- Terapkan post-mortem wajib untuk seluruh insiden berkategori SEV-1 dan SEV-2, atau insiden SEV-3 yang terjadi berulang kali dalam kurun waktu 30 hari (*recurrent anomaly*).
- Gunakan multi-tier escalation policies pada semua sistem mission-critical yang terikat kontrak komersial Customer Service Level Agreement (SLA).

---

## 14. When NOT To Use
- Jangan memicu paging telepon di luar jam kerja untuk kegagalan komponen yang memiliki mekanisme toleransi kesalahan (*fault-tolerant/self-healing*), seperti pod crash tunggal yang otomatis digantikan Kubernetes tanpa pelanggaran error budget.
- Hindari menggelar proses full-ICS war room formal untuk insiden SEV-4 (bug visual minor yang dapat dijadwalkan pada jam kerja normal).
- Jangan gunakan template post-mortem formal yang memakan waktu berjam-jam untuk isu lingkungan development lokal/staging internal non-kritis.

---

## 15. Common Mistakes
1. **IC Terjun ke Kode (Hands-on Keyboard IC):** IC mulai membuka terminal, membaca log trace, dan lupa memantau alur waktu, sehingga tidak ada yang mengarahkan strategi keseluruhan.
2. **Tidak Melakukan ACK Karena Mengira Orang Lain Menangani:** *Bystander effect* di kanal Slack publik tanpa alokasi kepemilikan eksplisit.
3. **Pemberitahuan Status Tanpa Estimasi Waktu:** Memberikan pesan "Kami sedang memperbaikinya" tanpa komitmen "Update berikutnya akan diberikan dalam 20 menit".
4. **Action Items Tidak Berpemilik:** Dokumen post-mortem menghasilkan rekomendasi tanpa nama pemilik (*owner*) dan batas waktu (*due date*), yang berakhir menjadi catatan mati.
5. **Mengabaikan Health On-Call Engineer:** On-call yang terjaga sepanjang malam tetap dipaksa menghadiri meeting sprint perencanaan keesokan paginya tanpa kompensasi istirahat (*on-call compensatory sleep*).

---

## 16. Best Practices
- **Definisikan Runbook/Playbook di Setiap Alert:** Setiap alert PagerDuty wajib menyertakan URL link runbook mitigasi yang jelas dan valid.
- **Rotasi On-Call yang Adil:** Terapkan shift bergilir dengan beban merata (misal: rotasi mingguan dengan primary dan secondary). Batasi batas shift harian untuk menjaga konsentrasi.
- **Simulasi Wheel of Misfortune / GameDay:** Jalankan latihan simulasi bencana terencana secara berkala untuk melatih insinyur memerankan fungsi IC, Tech Lead, dan Comms Lead di bawah tekanan simulasi.
- **Gunakan Prinsip SRE Post-Mortem Standard:**
  - Rekonstruksi timeline berdasarkan event log UTC.
  - Fokus pada *Context of Decision*: "Mengapa keputusan tersebut tampak masuk akal bagi operator pada saat kejadian terjadi?".

---

## 17. Troubleshooting Guide: On-Call & Incidents

### Masalah 1: Alert Storm / Alert Fatigue Saat Terjadi Network Partition
- **Gejala:** 400 alert masuk bersamaan ke ponsel on-call engineer dalam 60 detik dari berbagai microservices.
- **Root-Cause:** Dependensi downstream mati, menyebabkan seluruh upstream service membunyikan alert dependensi individual tanpa *alert grouping* atau *inhibition rule*.
- **Resolusi Teknis:** 
  Konfigurasikan alertmanager `inhibit_rules` untuk membungkam alert downstream jika root service (misal node gateway atau database utama) sudah dalam kondisi *firing*:
  ```yaml
  inhibit_rules:
    - source_match:
        alertname: 'NodeNetworkDown'
      target_match_re:
        alertname: '(ServiceUnavailable|EndpointTimeout)'
      equal: ['node', 'instance']
  ```

### Masalah 2: IC Overwhelm / Paralisis Analisis
- **Gejala:** Rapat koordinasi insiden berjalan 45 menit tanpa ada keputusan mitigasi yang dieksekusi; puluhan orang berbicara bersamaan.
- **Resolusi Teknis:**
  1. IC mengambil alih kontrol audio: "Mute all except designated leads."
  2. Terapkan *Time-boxing*: Tetapkan eksperimen diagnostik maksimal 5 menit. Jika hipotesis tidak terbukti via log, beralih langsung ke *fallback safe-action* (Rollback deployment).
  3. Lakukan hand-off peran jika IC kelelahan mental.

---

## 18. Exercise
1. Ambil insiden downtime publik terbaru dari perusahaan teknologi global (misal: AWS Kinesis 2020 Outage atau Cloudflare DNS Outage).
2. Ekstrak urutan kronologisnya menjadi bentuk Timeline berbasis UTC.
3. Tuliskan analisis 5-Whys sistemik dari studi kasus tersebut dengan mematuhi kaidah blameless (tidak menyalahkan manusia, berorientasi arsitektur perangkat lunak).
4. Buat 3 action items yang memenuhi kriteria S.M.A.R.T (Specific, Measurable, Achievable, Relevant, Time-bound).

---

## 19. Challenge
Rancang arsitektur sistem otomatisasi incident response engine berskala production:
- Sistem harus mengonsumsi webhook alert JSON mentah dari Prometheus Alertmanager.
- Lakukan evaluasi *Severity Matrix* otomatis berbasis label payload (`impacted_users`, `sli_breach_percentage`).
- Jika severity adalah SEV-1:
  - Buat channel Slack privat darurat dengan prefix `inc-<id>`.
  - Trigger paging telepon via provider PagerDuty/Opsgenie API ke Primary On-Call.
  - Buat dokumen kerja Google Docs / Notion dari template standar post-mortem secara otomatis.
- Implementasikan logic ini ke dalam sebuah skrip Python modular tanpa framework eksternal berat yang siap dijalankan dalam pipeline AWS Lambda atau Kubernetes Job.

---

## 20. Summary
- Siklus hidup insiden adalah proses disipliner formal untuk mengubah kekacauan operasional menjadi mitigasi terkontrol.
- Incident Command System (ICS) membagi beban kognitif secara terarah: IC memimpin alur koordinasi, Tech Lead memimpin penyelesaian teknis, dan Comms Lead melindungi fokus tim dari interupsi luar.
- Penetapan severity (SEV-1 s/d SEV-4) harus objektif berdasarkan degradasi fungsi bisnis dan konsumsi error budget SLO.
- Budaya Blameless Post-Mortem tidak mencari "siapa yang menekan tombol salah", melainkan membedah "mengapa sistem mengizinkan tombol tersebut merusak kestabilan produksi".
- Pengurangan MTTR yang berkelanjutan dicapai bukan dengan menghukum operator, melainkan melalui otomasi rollback, perbaikan runbook, penajaman alerting, dan implementasi arsitektur anti-rapuh (*resilient architecture*).