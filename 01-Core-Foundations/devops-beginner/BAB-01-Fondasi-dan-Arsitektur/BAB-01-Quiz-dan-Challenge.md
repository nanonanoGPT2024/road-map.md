# BAB 01: Quiz, Challenge, & Knowledge Check
**Fondasi DevOps, Kultur, dan Siklus Hidup Perangkat Lunak**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Dinamika dan Trade-Off Empat Metrik Kunci DORA (DevOps Research and Assessment)**  
   Jelaskan secara analitis hubungan dependensi antara metrik kecepatan (*Deployment Frequency* dan *Lead Time for Changes*) dengan metrik stabilitas (*Change Failure Rate* dan *Time to Restore Service*). Mengapa organisasi yang mencoba mengoptimalkan *Deployment Frequency* tanpa menerapkan otomatisasi pengujian (*automated testing*) dan observabilitas justru akan mengalami degradasi eksponensial pada *Change Failure Rate* dan *Time to Restore Service*?

2. **The Three Ways (Gene Kim): Mekanisme Aliran dan Umpan Balik**  
   Uraikan korelasi mekanis antara *The First Way* (Prinsip Aliran Sistem / *Flow*) dan *The Second Way* (Amplifikasi Umpan Balik / *Feedback Loops*). Bagaimana pembatasan beban kerja yang sedang berjalan (*Work In Progress* / WIP limits) secara langsung mempercepat deteksi regresi kode pada siklus hidup pengembangan perangkat lunak (SDLC)?

3. **Dekonstruksi Kerangka Kerja CALMS: Paradoks Otomasi Tanpa Budaya**  
   Banyak organisasi mengadopsi instrumen CI/CD mutakhir namun tetap mempertahankan komite persetujuan manual bertingkat (*Change Advisory Board* / CAB). Analisis fenomena ini menggunakan lensa kerangka kerja CALMS (*Culture, Automation, Lean, Measurement, Sharing*). Di pilar mana titik kegagalan utama terjadi, dan apa dampak sistemik dari *bottleneck* tersebut terhadap waktu tunggu (*lead time*)?

4. **Prinsip Shift-Left dan Reduksi Blast Radius**  
   Definisikan paradigma *Shift-Left* secara teknis. Bandingkan efisiensi operasional dan dampak finansial (*cost of defect*) antara mendeteksi kerentanan konfigurasi keamanan (*misconfiguration*) pada fase *linting / pre-commit hook* versus mendeteksinya setelah artefak terdeploy di lingkungan *Staging* atau *Production*.

5. **Toil vs. Engineering Work dalam Konteks SRE dan DevOps**  
   Berdasarkan definisi Google Site Reliability Engineering (SRE), diferensiasikan karakteristik teknis antara *toil* dan *overhead / engineering work*. Berikan dua contoh konkret pekerjaan operasional yang memenuhi syarat mutlak sebagai *toil*, serta jelaskan bagaimana prinsip DevOps mentransformasi aktivitas tersebut menjadi *idempotent automated task*.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Latensi Pipeline CI dan Degradasi Pola Integrasi (Trunk-Based Development)**  
   Sebuah tim rekayasa perangkat lunak mengeluhkan bahwa waktu eksekusi pipeline integrasi berkelanjutan (*CI build & test*) meningkat dari 6 menit menjadi 52 menit. Analisis secara teknis bagaimana peningkatan latensi eksekusi ini memicu perilaku anti-pattern berupa *long-lived feature branches*, peningkatan risiko *merge conflict* berskala besar (*merge hell*), dan kegagalan penerapan *Trunk-Based Development*.

2. **Migrasi Skema Basis Data Non-Destruktif pada Deployment Berkelanjutan**  
   Dalam arsitektur *Continuous Deployment* dengan strategi rilis *Rolling Update* tanpa waktu henti (*zero-downtime*), aplikasi versi lama (v1) dan aplikasi versi baru (v2) akan berjalan berdampingan (*coexist*) selama rentang waktu transisi. Jelaskan mekanisme implementasi *Expand and Contract Pattern* (disebut juga *Parallel Run*) untuk skema database relasional guna mencegah *runtime crash* pada instans v1 saat v2 mengeksekusi migrasi skema yang memodifikasi tipe data kolom krusial.

3. **Investigasi Kegagalan Sistemik: Paradigma Blameless Post-Mortem**  
   Seorang *engineer* junior secara tidak sengaja memicu *script* *teardown* infrastruktur yang menghapus klaster basis data produksi karena variabel lingkungan `ENV=production` tereksekusi tanpa validasi. Rancang struktur penyelidikan insiden (*incident post-mortem*) menggunakan prinsip *Blameless Culture*. Tunjukkan bagaimana fokus analisis dialihkan dari kelalaian manusia (*human error*) ke kerentanan arsitektural sistem (*guardrails*, *least privilege IAM*, *execution drift*, dan *approval gates*).

4. **Mitigasi False-Positive Fatigue pada Integrasi DevSecOps**  
   Ketika mengintegrasikan perkakas SAST (*Static Application Security Testing*) dan SCA (*Software Composition Analysis*) ke dalam pipeline deployment otomatis, tim developer sering kali mematikan *security gate* karena tingginya angka *false-positive alerts* yang memblokir proses rilis. Bagaimana arsitektur pipeline harus dikonfigurasi untuk memfilter, melakukan triase, dan mengalokasikan ambang batas keparahan (*vulnerability threshold baseline*) tanpa mengorbankan kecepatan pengiriman kode?

5. **Telemetri Observabilitas sebagai Loop Umpan Balik SDLC**  
   Mengapa pemantauan berbasis *Three Pillars of Observability* (Metrics, Logs, Traces) harus diintegrasikan dan divalidasi sejak tahap pengembangan lokal (*local dev environment*) dan bukan sekadar ditambahkan sebagai *instrumentasi pasca-rilis* di level infrastruktur produksi? Jelaskan dampaknya terhadap waktu resolusi insiden (*Mean Time to Restore* / MTTR).

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Rilis dan "Wall of Confusion" pada PT Pembayaran Digital
PT Pembayaran Digital mengalami pertumbuhan transaksi 400% dalam 6 bulan. Tim Pengembang (Dev) dibagi menjadi 12 *squads* microservices yang merilis kode secara agresif, sementara Tim Operasional (Ops) bertanggung jawab penuh atas stabilitas infrastruktur klaster Kubernetes produksi. 

Setiap deployment ke produksi memerlukan pengajuan tiket Jira 7 hari sebelumnya dan verifikasi manual oleh tim Ops pada *maintenance window* hari Minggu malam. Rata-rata *Lead Time for Changes* membengkak menjadi 21 hari, dengan *Change Failure Rate* mencapai 38% akibat dependensi antar-layanan yang tidak teruji secara serentak. Setiap terjadi kegagalan, tim Dev menyalahkan konfigurasi lingkungan Ops, sementara tim Ops menuduh kualitas kode Dev buruk.
*   **Pertanyaan Diagnostik 1:** Identifikasi akar penyebab kegagalan kultural dan operasional dari skenario di atas dengan membedah rusaknya *feedback loop* dan keberadaan *Wall of Confusion*.
*   **Pertanyaan Diagnostik 2:** Rancang rencana transisi arsitektural proses (*process transformation*) untuk menghapus *maintenance window* mingguan dan menggantikannya dengan model kepemilikan penuh (*You Build It, You Run It*) menggunakan platform internal (*Internal Developer Platform* / IDP).

---

### Skenario B: Konflik Rilis State & Data Integrity pada Blue/Green Rollout
Platform e-commerce "BukaPasar" menerapkan strategi deployment *Blue/Green* pada klaster Kubernetes produksi untuk memperbarui `Order-Service` dari versi 2.4.0 (Blue) ke versi 2.5.0 (Green). Pembaruan ini mengubah mekanisme pembacaan status pesanan dari format *string* (`PENDING`, `PAID`) menjadi struktur objek JSON terenkapsulasi (`{"status": "PAID", "metadata": {...}}`). 

Operator mengarahkan 10% trafik ke *environment* Green menggunakan *Ingress Traffic Splitting*. Dua menit kemudian, tim *customer support* menerima laporan ribuan transaksi gagal. Analisis cepat menunjukkan bahwa kedua versi aplikasi membaca dan menulis ke basis data Redis dan PostgreSQL yang sama secara bersamaan. Aplikasi versi Blue mengalami *unhandled JSON parsing exception* saat membaca data pesanan baru yang ditulis oleh aplikasi versi Green, menyebabkan *crash loop* pada *pod* Blue yang masih melayani 90% trafik pelanggan.
*   **Pertanyaan Diagnostik 1:** Mengapa strategi deployment *Blue/Green* murni gagal mengisolasi risiko perubahan pada skenario data persisten (*stateful*) ini?
*   **Pertanyaan Diagnostik 2:** Formulasikan arsitektur deployment dan strategi kompatibilitas data (*backward & forward compatibility pattern*) yang seharusnya diimplementasikan untuk mencegah anomali korupsi pembacaan data antar-versi tersebut.

---

### Skenario C: Trade-off Arsitektur: Premature Microservices vs. Delivery Velocity
Startup logistik "KirimCepat" memiliki 15 orang *software engineer*. Tergiur oleh tren industri, tim memutuskan untuk langsung memecah aplikasi monolitik mereka menjadi 35 microservices yang terdistribusi di dalam klaster Kubernetes multi-region. 

Namun, tim belum memiliki standarisasi CI/CD, tidak memiliki sistem observabilitas terdistribusi (*distributed tracing* seperti Jaeger/OpenTelemetry), dan proses deployment masih mengandalkan *script bash* manual per repositori. Dampaknya, setiap rilis fitur baru membutuhkan sinkronisasi manual rilis pada 8-10 repositori berbeda. MTTR melonjak dari 15 menit menjadi 9 jam karena sulitnya mengidentifikasi sumber *error* dalam rantai dependensi HTTP internal, dan kapasitas tim habis untuk mengurus infrastruktur mikro (*operational overhead*).
*   **Pertanyaan Diagnostik 1:** Lakukan evaluasi trade-off arsitektural: Apakah dekomposisi monolitik ke microservices pada skala tim dan kapabilitas otomasi saat ini merupakan keputusan yang tepat? Justifikasi argumen Anda secara teknis.
*   **Pertanyaan Diagnostik 2:** Berikan rekomendasi langkah mitigasi konkret. Apakah tim harus melakukan rekomposisi kembali ke *Modular Monolith*, atau membangun fondasi *Core DevOps Enablers* terlebih dahulu? Uraikan urutan prioritas eksekusinya.

---

## 4. Chapter Challenge

### Tantangan Praktis: Rekayasa Value Stream Mapping (VSM) & Strategi Remediasi Siklus Hidup Rilis

#### Konteks Masalah
Anda ditunjuk sebagai Lead DevOps/Platform Engineer di sebuah institusi perbankan regional yang menangani aplikasi inti *Retail Internet Banking*. Proses rilis saat ini membutuhkan waktu rata-rata **42 hari** dari tahap commit kode hingga running di produksi. Metrik kinerja saat ini:
- **Deployment Frequency:** 1 kali per kuartal (3 bulan).
- **Lead Time for Changes:** 42 hari.
- **Change Failure Rate:** 45%.
- **Time to Restore Service (MTTR):** 18 jam.

Alur rilis eksisting:
1. Developer menulis kode di mesin lokal tanpa environment parity (menggunakan SQLite, sedangkan produksi PostgreSQL).
2. Kode di-merge ke branch `develop` via Pull Request tanpa automated test (bergantung pada tinjauan visual senior engineer).
3. Setiap akhir bulan, kode di-bundle manual dan di-deploy ke server QA oleh tim QA via SSH.
4. Tim QA mengeksekusi manual regression testing selama 14 hari kerja.
5. Hasil pengujian diserahkan ke Tim Keamanan Siber untuk vulnerability scanning manual (7 hari kerja).
6. Tim mengajukan dokumen setebal 50 halaman ke *Change Advisory Board* (CAB) yang mengadakan rapat 2 minggu sekali.
7. Tim Operasional mengeksekusi deployment manual di produksi pada pukul 01.00 dini hari hari Minggu dengan downtime 4 jam.

#### Persyaratan Rekayasa (*Requirements*)
1. **Analisis Current State Value Stream Map (VSM):**
   - Petakan langkah-langkah di atas ke dalam diagram alur teks atau tabel VSM.
   - Hitung rasio efisiensi siklus (*Process Velocity Ratio*): bedakan antara *Process Time* (waktu kerja aktif) dan *Wait/Lead Time* (waktu tunggu/antrean).
   - Identifikasi secara presisi 3 *bottleneck* struktural terbesar yang menyebabkan tingginya waktu tunggu dan *Change Failure Rate*.

2. **Perancangan Future State Pipeline Architecture:**
   - Rancang arsitektur pipeline CI/CD modern yang mengotomatisasi pengujian, validasi keamanan, dan rilis.
   - Definisikan gerbang kualitas otomatis (*Automated Quality Gates*) yang memvalidasi artefak di setiap tahap.
   - Rancang mekanisme *Shift-Left Testing* (termasuk penggunaan ephemeral environments / containerized dependencies).

3. **Strategi Transformasi Metrik DORA:**
   - Formulasikan target terukur 6 bulan ke depan untuk mentransformasi ke-4 metrik DORA organisasi dari kategori *Low Performer* menuju *High/Elite Performer*.

#### Batasan (*Constraints*)
- Arsitektur baru harus mematuhi kepatuhan audit perbankan: Harus ada pemisahan tugas (*Separation of Duties*) tanpa memerlukan persetujuan manual manusia via rapat CAB.
- Zero-Downtime Deployment wajib tercapai pada target akhir.

#### Format Output yang Diharapkan
Sajikan dokumen arsitektur teknis dalam format Markdown yang rapi, mencakup:
- **Tabel Value Stream Mapping Eksisting:** Mencakup Tahapan, Aktor, *Process Time*, *Lead/Wait Time*, dan *Identifikasi Pemborosan (Waste)*.
- **Diagram Alur Future State Delivery:** Representasi alur integrasi hingga deployment menggunakan diagram blok teks terstruktur atau Mermaid.js.
- **Tabel Target Metrik DORA:** Angka *baseline* vs target 6 bulan, disertai mekanisme teknis spesifik untuk mencapainya.
- **Rancangan Tata Kelola Kepatuhan (*Automated Governance*):** Mekanisme teknis kepatuhan audit berbasis kriptografi (misal: *signed commits*, *immutable artifact registries*, dan *automated audit logs*).

---

## 5. Knowledge Check & Checklist

Gunakan daftar periksa mandiri ini untuk mengukur kesiapan pemahaman konsep fondasi dan kultur DevOps sebelum melangkah ke modul otomasi infrastruktur.

### Saya harus memahami:
- [ ] Perbedaan filosofis dan praktis antara Continuous Integration (CI), Continuous Delivery (CD), dan Continuous Deployment.
- [ ] Empat metrik kunci DORA dan bagaimana metrik-metrik tersebut berkorelasi secara sistemik terhadap performa bisnis organisasi.
- [ ] Prinsip *The Three Ways* (Flow, Feedback, Continuous Learning) menurut Gene Kim dan implementasinya pada alur kerja rekayasa.
- [ ] Pilar kerangka kerja CALMS (*Culture, Automation, Lean, Measurement, Sharing*) dan bahaya mengadopsi otomasi tanpa transformasi kultur.
- [ ] Perbedaan antara *Toil* dan aktivitas rekayasa bernilai tambah (*Engineering Work*) berdasarkan prinsip Site Reliability Engineering (SRE).
- [ ] Konsep *Shift-Left* dalam konteks pengujian (*functional, performance*) dan keamanan (*security/compliance*).
- [ ] Implikasi arsitektural pemilihan strategi rilis (*Rolling, Blue/Green, Canary*) terhadap persistensi dan integritas data.
- [ ] Mengapa komite persetujuan manual (CAB eksternal) merupakan anti-pattern yang meningkatkan risiko kegagalan rilis alih-alih menurunkannya.

### Saya tidak perlu menghafal:
- [ ] Sintaks spesifik file konfigurasi pipeline (seperti sintaksis unik GitHub Actions YAML, GitLab CI YAML, atau Jenkinsfile Scripted Groovy).
- [ ] Perintah CLI (*command-line flags*) spesifik dari perkakas Git tingkat lanjut secara detail (misal parameter eksotis `git rebase -i` atau `git filter-branch`).
- [ ] Nama vendor komersial untuk perkakas SAST, DAST, atau VSM tertentu yang ada di pasar.
- [ ] Matriks komputasi matematis detail dari formula logaritmik korelasi metrik DORA.

### Saya harus bisa melakukan:
- [ ] Memetakan alur rilis perangkat lunak tradisional ke dalam *Value Stream Map* (VSM) untuk menghitung *lead time*, *process time*, dan mengidentifikasi pemborosan (*waste*).
- [ ] Menganalisis log insiden produksi dan menyusun dokumen *Blameless Post-Mortem* yang menitikberatkan pada perbaikan kelemahan sistemik.
- [ ] Merancang arsitektur pipeline CI/CD konseptual yang mengintegrasikan pengujian unit, analisis statis, pengujian integrasi, validasi keamanan, dan deployment tanpa waktu henti (*zero downtime*).
- [ ] Mengidentifikasi kondisi *race condition* dan inkompatibilitas skema basis data saat aplikasi menjalani pembaruan bertahap (*rolling update*).
- [ ] Mengukur dan mengkategorikan performa delivery perangkat lunak suatu tim berdasarkan metrik DORA serta menentukan intervensi teknis yang dibutuhkan.