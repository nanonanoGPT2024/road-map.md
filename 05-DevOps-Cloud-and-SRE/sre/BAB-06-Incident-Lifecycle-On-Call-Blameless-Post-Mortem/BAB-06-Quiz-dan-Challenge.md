# Bab 06: Quiz dan Challenge - Incident Lifecycle, On-Call, & Blameless Post-Mortem

---

## Bagian 1: Basic Questions (5 Soal Pilihan Ganda)

### Soal 1
Apa tugas utama seorang Incident Commander (IC) selama fase aktif penanganan insiden berskala kritis (SEV-1)?
- [ ] A. Menulis patch perbaikan kode secara langsung di server production.
- [ ] B. Membaca stack trace di log management platform dan mengarahkan database query.
- [ ] C. Memegang kendali orkestrasi insiden, mendelegasikan tugas, memfasilitasi keputusan, dan menjaga fokus tim tanpa melakukan hands-on debugging.
- [ ] D. Memberikan presentasi klarifikasi kepada media massa dan regulator perbankan.

### Soal 2
Berdasarkan Severity Matrix standar SRE, kondisi manakah yang paling tepat diklasifikasikan sebagai **SEV-1**?
- [ ] A. Halaman admin pelaporan internal memuat data 3 detik lebih lambat dari biasanya.
- [ ] B. Kegagalan sistem pembayaran inti yang menyebabkan transaksi pelanggan gagal total di seluruh region, menghabiskan >10% SLO error budget dalam tempo singkat.
- [ ] C. Kesalahan penulisan teks (typo) pada landing page promosi produk.
- [ ] D. Memory usage pada satu worker pod mencapai 85%, namun pod lain menangani lalu lintas secara normal.

### Soal 3
Dalam metodologi *Blameless Post-Mortem*, frasa manakah yang **dilarang keras** dijadikan kesimpulan penyebab insiden?
- [ ] A. "Koneksi database terputus akibat saturasi I/O pada EBS volume."
- [ ] B. "Human error: Insinyur DevOps ceroboh dan lalai menjalankan prosedur deployment."
- [ ] C. "Mekanisme retry backoff eksponensial tidak diaktifkan pada client library gRPC."
- [ ] D. "Health check endpoint mengembalikan HTTP 200 palsu saat threadpool backend deadlock."

### Soal 4
Metrik operasional yang mengukur rentang waktu dari saat sebuah insiden pertama kali terdeteksi oleh sistem telemetri hingga teknisi jaga melakukan acknowledgement (ACK) terhadap pager adalah:
- [ ] A. MTTR (Mean Time to Resolve)
- [ ] B. MTTF (Mean Time to Failure)
- [ ] C. MTTA (Mean Time to Acknowledge)
- [ ] D. MTTD (Mean Time to Detect)

### Soal 5
Pada arsitektur integrasi PagerDuty atau Opsgenie, apa tujuan utama dari konfigurasi *Escalation Policy* bertingkat (Multi-tier)?
- [ ] A. Memastikan seluruh karyawan perusahaan menerima telepon darurat secara serentak.
- [ ] B. Menghindari eskalasi ke manajemen eksekutif dalam keadaan apa pun.
- [ ] C. Mengalihkan alert secara otomatis ke engineer sekunder atau manager jika on-call primer tidak merespons dalam durasi batas waktu tertentu (*timeout*).
- [ ] D. Mengurangi konsumsi memori pada server Alertmanager.

---

## Bagian 2: Intermediate Questions (5 Soal Pilihan Ganda Berbobot)

### Soal 6
Sebuah microservice mengalami kondisi *flapping* di mana metrik utilisasi CPU melompat bolak-balik antara 89% dan 91% setiap 10 detik. Jika threshold alert disetel pada 90%, apa konsekuensi operasional jika alerting system tidak memiliki konfigurasi hysteresis atau *hold-down timer* (`for: 5m`)?
- [ ] A. Alertmanager akan mengalami memory exhaustion dan crash.
- [ ] B. Terjadi fenomena *Alert Fatigue* akibat lusinan notifikasi alert firing dan alert resolved terkirim dalam waktu singkat ke ponsel teknisi jaga.
- [ ] C. PagerDuty akan memblokir API key organisasi secara permanen karena spamming.
- [ ] D. Latensi $P99$ aplikasi akan otomatis tereduksi secara gradual.

### Soal 7
Perhatikan potongan arsitektur komando: Tim menghadapi insiden kebocoran data di mana seorang VP Engineering masuk ke dalam voice call war room dan mulai menuntut penjelasan teknis mendalam kepada insinyur database yang sedang menganalisis log. Berdasarkan protokol Incident Command System (ICS), tindakan apa yang **harus** diambil?
- [ ] A. Insinyur database wajib menghentikan pekerjaannya untuk menjawab seluruh pertanyaan sang VP sebagai bentuk kepatuhan korporat.
- [ ] B. Incident Commander (IC) mengambil alih komunikasi dan meminta Communications Lead (CL) mengarahkan sang VP ke kanal komunikasi pemangku kepentingan terpisah di luar war room utama.
- [ ] C. IC segera memindahkan hak Incident Commander kepada VP Engineering tersebut.
- [ ] D. Tech Lead membungkam (mute) mikrofon semua orang dan menunda penanganan insiden hingga situasi tenang.

### Soal 8
Dalam analisis *5-Whys*, mengapa berhenti pada pertanyaan "Mengapa developer meloloskan bug ke production?" dengan jawaban "Karena developer lupa menjalankan unit test lokal" dianggap sebagai analisis yang cacat secara prinsip keandalan?
- [ ] A. Karena mengasumsikan bahwa reliabilitas sistem dapat dijamin oleh ingatan dan ketelitian individu tanpa mekanisme proteksi otomatis di pipeline CI/CD.
- [ ] B. Karena developer memiliki imunitas mutlak dari segala evaluasi performa teknis.
- [ ] C. Karena unit test tidak pernah mampu mendeteksi bug fungsional di lingkungan modern.
- [ ] D. Karena analisis 5-Whys hanya boleh diterapkan pada kegagalan hardware, bukan software.

### Soal 9
Manakah dari strategi mitigasi berikut yang paling efektif untuk meminimalkan MTTR pada insiden rilis perangkat lunak baru yang menyebabkan degradasi performa akut?
- [ ] A. Menghubungkan debugger interaktif (`gdb` atau remote JVM profiler) ke instance production untuk menelusuri memori heap baris demi baris.
- [ ] B. Melakukan kompilasi ulang kode sumber dengan flag tracing aktif dan mendeploy patch baru ke production.
- [ ] C. Melakukan eksekusi otomatis prosedur rollback ke container image versi stabil sebelumnya atau mengalihkan *traffic canary* kembali ke baseline 0%.
- [ ] D. Menghapus log lama untuk mengosongkan ruang disk pada host instance.

### Soal 10
Sebuah action item pasca-insiden ditulis sebagai berikut: *"Tingkatkan pemantauan database dan buat sistem lebih tangguh terhadap kegagalan jaringan."* Mengapa action item ini melanggar standar best-practice SRE post-mortem?
- [ ] A. Terlalu panjang dan memuat kata-kata teknis yang rumit dipahami.
- [ ] B. Tidak memenuhi kriteria S.M.A.R.T: tidak terukur (*unmeasurable*), tidak spesifik, tidak memiliki penanggung jawab eksplisit (*ownerless*), dan tidak ada deadline target implementasi.
- [ ] C. Action item dilarang membahas aspek jaringan jika insiden berakar dari sistem database.
- [ ] D. Menulis tiket action item pasca-insiden hanya diperbolehkan bagi level Staff Engineer ke atas.

---

## Bagian 3: Scenario-Based Questions (3 Studi Kasus Dunia Nyata)

### Kasus 1: "The Black Friday Midnight Cascading Failure"
Pada pukul 23:58 WIB saat promo kilat Black Friday dimulai, platform e-commerce Anda mengalami lonjakan traffic 10x lipat. Layanan *Inventory Service* mulai mengalami timeout saat memanggil database Redis Sentinel. 
- Alert `HighErrorRate5xx` menyala.
- Dalam 3 menit, layanan upstream (*Cart Service*, *Checkout Service*, dan *Payment Gateway Proxy*) kehabisan threadpool connection karena menunggu respons dari Inventory Service tanpa batasan timeout yang ketat (*cascading failure*).
- Status: Pembeli tidak dapat melakukan checkout; kerugian ditaksir mencapai $20,000 per menit.
- Anda ditunjuk sebagai **Incident Commander (IC)**.

**Pertanyaan:**
1. Rincikan langkah pembagian peran awal (IC, Tech Lead, Comms Lead) dalam 5 menit pertama pembentukan war room.
2. Tentukan klasifikasi severity level insiden ini beserta argumen justifikasinya.
3. Sebutkan tindakan teknis mitigasi prioritas pertama yang harus diinstruksikan kepada Tech Lead sebelum mencari akar bug pada Redis Sentinel.

---

### Kasus 2: "The Flawed Config Push & Blameless Facilitation"
Seorang Junior Cloud Engineer bernama Dika diperintahkan untuk memperbarui rute ingress traffic pada cluster Kubernetes multi-region melalui kubectl CLI langsung karena sistem pipeline CI/CD sedang mengalami antrean panjang. 
- Dika salah mengarahkan context cluster (`kubectl config use-context prod-us-east` alih-alih `staging`).
- Dika mengeksekusi script penghapusan konfigurasi namespace yang mengakibatkan seluruh gateway API di region US-East terhapus seketika.
- Layanan padam selama 42 menit hingga backup manifests berhasil di-apply ulang.
- Pasca insiden, seorang Engineering Manager senior menulis di saluran Slack publik: *"Kelalaian junior engineer Dika menyebabkan kita kehilangan customer enterprise. Harus ada sanksi tegas bagi yang tidak teliti."*

**Pertanyaan:**
1. Bagaimana Anda sebagai Principal SRE merespons pernyataan Engineering Manager tersebut sesuai kaidah *Blameless Culture*?
2. Susun analisis 5-Whys terstruktur yang menggeser fokus dari kesalahan individu Dika menuju kegagalan sistemik arsitektur dan kontrol akses (*RBAC/tooling*).
3. Usulkan 2 Action Items preventif berbasis rekayasa sistem (*engineering guardrails*) agar kejadian serupa secara fisik mustahil diulangi oleh engineer lain.

---

### Kasus 3: "The Chronic On-Call Attrition"
Tim SRE yang mengelola sistem microservices logging menerima rata-rata 65 pager alerts per minggu di luar jam kerja (pukul 22:00 - 06:00). Setelah dianalisis:
- 80% dari alert tersebut adalah `NodeDiskUsageExceededWarning` yang otomatis selesai (*auto-resolved*) dalam 15 menit karena log rotator cron job berjalan setiap jam.
- 15% adalah transient network timeout ke pihak ketiga yang pulih dalam hitungan detik.
- Hanya 5% yang membutuhkan intervensi teknisi secara nyata.
- Dua anggota tim telah mengajukan pengunduran diri karena insomnia parah dan kelelahan mental (*on-call burnout*).

**Pertanyaan:**
1. Metrik SRE apa saja yang dilanggar secara fatal pada skenario rotasi on-call di atas?
2. Bagaimana Anda merestrukturisasi konfigurasi alerting policy (Prometheus/PagerDuty) untuk menyaring alert non-actionable tersebut?
3. Langkah operasional apa yang harus diambil terhadap kapasitas sprint tim untuk memulihkan beban kerja kognitif mereka (*sustainable on-call*)?

---

## Bagian 4: Practical Chapter Challenge

### Judul Tantangan: "Full-Cycle Resilient Incident Management Automation Engine"

### Deskripsi Masalah:
Organisasi Anda membutuhkan sistem orkestrasi insiden otomatis terpusat tanpa bergantung pada layanan SaaS berbayar yang mahal. Anda ditugaskan untuk mengimplementasikan sebuah sistem automasi berbasis Python mandiri yang berfungsi sebagai **Incident Commander Engine (ICE)**.

### Persyaratan Fungsional:
1. **Payload Ingestion & Severity Classification:**
   - Script harus mampu memvalidasi dan memproses event JSON dari Alertmanager.
   - Evaluasi otomatis metrik SLI:
     - Jika `affected_percentage >= 20.0` OR `estimated_revenue_loss_per_min >= 5000` $\implies$ **SEV-1**
     - Jika `affected_percentage >= 5.0` OR `estimated_revenue_loss_per_min >= 1000` $\implies$ **SEV-2**
     - Selain itu $\implies$ **SEV-3 / SEV-4**
2. **Escalation & Role Assignment Engine:**
   - Memiliki konfigurasi rotasi shift on-call terintegrasi (Primary, Secondary, Tech Lead, Comms Lead).
   - Menyediakan mesin status (*state machine*) transisi insiden: `TRIGGERED` $\to$ `ACKNOWLEDGED` $\to$ `MITIGATED` $\to$ `RESOLVED`.
   - Mengimplementasikan mekanisme *Escalation Timeout*: Jika status tidak berubah menjadi `ACKNOWLEDGED` dalam interval waktu simulasi tertentu, sistem secara otomatis mengeksekusi eskalasi ke Secondary On-Call.
3. **Automated Post-Mortem Report Generator:**
   - Menyediakan fungsi ekspor yang menghasilkan dokumen Markdown formal `post-mortem-<incident_id>.md`.
   - Format wajib mencakup: Header Metadata, Severity, Incident Commander & Roles, Detailed Timeline (berurutan dengan timestamp UTC), Systemic Root Causes (Format 5-Whys), dan Action Items Table dengan status tracking.

### Kriteria Kelulusan:
- Kode Python berjalan secara independen menggunakan pustaka standar Python 3 (tanpa library pihak ketiga yang rumit).
- Terdapat penanganan error yang tangguh (*defensive programming*).
- Menghasilkan file artefak post-mortem yang valid dan rapi.