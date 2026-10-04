# BAB 10: Evaluasi Pengetahuan - SRE-Sec & Disaster Recovery

## 1. Basic Questions (5 Soal)
1. Jelaskan perbedaan mendasar antara Recovery Time Objective (RTO) dan Recovery Point Objective (RPO)!
2. Sebutkan urutan strategi Disaster Recovery dari yang memiliki biaya paling rendah hingga paling tinggi!
3. Mengapa replikasi data asinkron (*asynchronous replication*) selalu memiliki potensi RPO > 0?
4. Apa tujuan utama dari penerapan S3 Object Lock dengan mode `COMPLIANCE` dalam mitigasi serangan ransomware?
5. Dalam terminologi sistem terdistribusi, apa yang dimaksud dengan fenomena bencana *Split-Brain*?

---

## 2. Intermediate Questions (5 Soal)
1. Bagaimana cara kerja mekanisme *Fencing* (seperti STONITH) dalam mencegah kerusakan data saat transisi failover antar region?
2. Pada strategi *Pilot Light*, komponen arsitektur apa saja yang tetap dibiarkan aktif (*running*) di region pemulihan (DR), dan komponen apa yang dinonaktifkan?
3. Mengapa pengujian backup secara tradisional (hanya memverifikasi status log backup sukses) dianggap sebagai anti-pattern fatal dalam SRE-Sec?
4. Bagaimana prinsip *Security Chaos Engineering* dapat digunakan untuk memverifikasi ketahanan konfigurasi Cross-Region Replication?
5. Jelaskan konsep *Health Check Hysteresis* dan bagaimana penerapannya mencegah osilasi rute DNS (*DNS flapping*) saat terjadi degradasi jaringan intermiten!

---

## 3. Scenario-Based Questions (3 Soal Kasus)

### Kasus 1: Petaka Split-Brain pada Fintech Payment Gateway
Sebuah payment gateway berskala nasional mengonfigurasi skema failover DNS otomatis penuh dengan TTL Route 53 bernilai 10 detik. Suatu hari, terjadi lonjakan *packet loss* 60% selama 4 menit antara region primer dan internet publik. Health checker Route 53 gagal menghubungi cluster web primer dan secara otomatis mengarahkan trafik baru ke Region Sekunder. Namun, koneksi internal VPC Peering antar database primer dan aplikasi internal lainnya masih berjalan. 
- **Pertanyaan**: 
  1. Dampak apa yang akan terjadi pada integritas data saldo pengguna?
  2. Bagaimana modifikasi arsitektur failover dan health checking yang harus diterapkan SRE-Sec untuk mencegah kejadian ini terulang?

### Kasus 2: Serangan Ransomware dengan Pembajakan Akses Root
Seorang penyerang berhasil mendapatkan kredensial IAM Administrator melalui insiden phishing terhadap salah satu insinyur infrastruktur. Penyerang mengeksekusi skrip destruktif yang menghapus seluruh volume disk EBS produksi di region primer dan mencoba mengeksekusi *purge* pada bucket backup di region DR.
- **Pertanyaan**:
  1. Kontrol keamanan dan arsitektur penyimpanan DR apa yang dapat mencegah terhapusnya data cadangan tersebut secara absolut?
  2. Jelaskan runbook langkah darurat yang harus diambil tim SRE-Sec untuk memulihkan kluster ke region DR!

### Kasus 3: Kenaikan Replication Lag saat Flash Sale
Platform e-commerce mengadopsi pola Warm Standby. Pada saat kampanye flash sale 12.12, database primer mengalami *write-load* hingga 45.000 TPS. Hal ini menyebabkan *replication lag* database standby di region DR membengkak menjadi 480 detik (8 menit). Pada menit ke-5 flash sale, region primer mengalami kebakaran data center fisik. Batas RPO bisnis yang disepakati adalah $\le 30$ detik.
- **Pertanyaan**:
  1. Apa dilema teknis dan operasional yang dihadapi oleh SRE Incident Commander dalam skenario ini?
  2. Prosedur keputusan apa yang harus didefinisikan dalam Game Day Runbook untuk mengatasi ketidaksesuaian antara RPO riil dan RPO SLO bisnis?

---

## 4. Practical Chapter Challenge
### Rancang Bangun Failover Engine & Automated Backup Auditor

Anda ditugaskan sebagai Principal SRE-Sec Architect untuk membangun sistem otomatisasi pemulihan bencana mini yang andal.

**Target Tugas**:
1. Buat sebuah skrip Python mandiri (`hands-on/m01/dr_failover_health_checker.py`) yang berperan sebagai Health Checker & Failover Orchestrator cerdas.
2. Program harus mampu memonitor dua endpoint:
   - Primary Region Service (simulasi endpoint REST API).
   - Database Replication Lag metric.
3. Program harus mengimplementasikan:
   - **Hysteresis / Flapping Protection**: Membutuhkan minimal 3 kali kegagalan berturut-turut sebelum mengubah status, dan 5 kali keberhasilan berturut-turut untuk normalisasi.
   - **RPO Guard**: Menolak memicu failover otomatis jika *replication lag* terdeteksi di atas batas ambang batas (misal: > 5 detik), lalu memberikan peringatan eskalasi darurat manual.
   - **Safe Fencing Action**: Menstimulasikan pencabutan akses tulis region primer sebelum menginstruksikan region sekunder menjadi master baru.
4. Buat simulasi skenario pengujian dengan variasi input kegagalan jaringan dan verifikasi eksekusi failover yang dihasilkan.

---