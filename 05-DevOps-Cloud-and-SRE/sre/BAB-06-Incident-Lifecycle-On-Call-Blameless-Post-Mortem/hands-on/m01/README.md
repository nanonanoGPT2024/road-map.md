# Hands-On Lab: Incident Commander Automation & Blameless Post-Mortem Engine

## Deskripsi Laboratorium
Laboratorium ini memberikan pengalaman langsung dalam mengeksekusi alur operasional Incident Lifecycle, simulasi eskalasi pager, pembagian peran Incident Command System (ICS), serta pembuatan laporan post-mortem otomatis sesuai standar ketat Site Reliability Engineering (SRE).

Anda akan menjalankan engine simulasi berbasis Python (`incident_commander_workflow.py`) yang mereproduksi insiden berskala SEV-1, menguji mekanisme failover rotasi on-call ketika engineer primer gagal merespons, dan mengompilasi artefak Markdown post-mortem tanpa menyalahkan individu (*blameless*).

---

## Prasyarat Lingkungan
- Python versi `3.8` atau yang lebih baru.
- Sistem operasi Linux, macOS, atau Windows Subsystem for Linux (WSL).
- Text editor atau terminal viewer untuk memeriksa artefak Markdown hasil generasi.

---

## Langkah-Langkah Hands-On

### Langkah 1: Persiapan Lingkungan & Navigasi Direktori
Buka terminal dan navigasikan ke direktori hands-on lab:
```bash
cd hands-on/m01
```

Pastikan skrip simulasi memiliki hak akses eksekusi:
```bash
chmod +x incident_commander_workflow.py
```

### Langkah 2: Inspeksi Logika Engine
Pelajari komponen logika pada `incident_commander_workflow.py`:
- Fungsi `evaluate_severity`: Bagaimana parameter `affected_users_percentage` dan `estimated_revenue_loss_per_min` memetakan status insiden ke SEV-1 hingga SEV-4.
- Fungsi `acknowledge_incident`: Perhatikan bagaimana ambang batas waktu (`ack_sla_seconds`) memicu perpindahan otomatis Incident Commander dari level Primary ke Secondary On-Call.
- Fungsi `generate_post_mortem`: Konstruksi struktur Markdown yang menjamin kelengkapan data kronologi waktu berstandar UTC.

### Langkah 3: Eksekusi Engine Simulasi Insiden
Jalankan skrip workflow secara langsung:
```bash
python3 incident_commander_workflow.py
```

Perhatikan output konsol yang menggambarkan kronologi sistemik:
1. Alert masuk dan dievaluasi sebagai **SEV-1 (Critical Outage)**.
2. Paging diluncurkan ke Primary On-Call.
3. Simulasi pelanggaran batas SLA MTTA (>300 detik) memicu eskalasi darurat ke Secondary On-Call.
4. Peran Incident Commander, Tech Lead, dan Comms Lead diaktifkan.
5. Strategi mitigasi dieksekusi dan dicatat ke dalam log berstempel waktu UTC.
6. Resolusi insiden diterapkan.
7. File post-mortem berformat Markdown diekspor secara otomatis.

### Langkah 4: Analisis dan Verifikasi Artefak Post-Mortem
Periksa file Markdown yang baru saja dibuat oleh engine (nama file mengikuti pola `post-mortem-inc-<timestamp>.md`):
```bash
# Ganti dengan nama file spesifik yang muncul pada output konsol
cat post-mortem-inc-*.md
```

Verifikasi bahwa dokumen tersebut mematuhi 4 pilar penting SRE:
- [x] **Metadata & Severity:** Klasifikasi SEV-1 tercatat jelas beserta pemegang komandonya.
- [x] **Blameless Executive Summary:** Fokus pada perbaikan sistem dan proteksi arsitektural.
- [x] **Detailed Timeline:** Seluruh histori kejadian tersusun rapi dengan format waktu UTC ISO-8601.
- [x] **Systemic 5-Whys & Action Items:** Berisi tiket remedi teknis preventif dengan PIC dan target penyelesaian yang terukur.

---

## Tugas Mandiri Tambahan (Challenge Lab)
1. Modifikasi parameter payload pada baris `mock_alert_payload` di dalam file `incident_commander_workflow.py` dengan skenario berikut:
   - `affected_users_percentage`: `2.5`
   - `estimated_revenue_loss_per_min`: `200.0`
   - `core_service_down`: `False`
2. Jalankan kembali script dan amati:
   - Apakah sistem secara tepat menurunkan klasifikasi severity ke **SEV-3 (Moderate Impact)**?
   - Apakah protokol high-severity dinonaktifkan?
3. Tambahkan 1 item aksi baru berkategori `PREVENT` pada array `engine.action_items` dan pastikan item tersebut muncul di tabel hasil ekspor Markdown.