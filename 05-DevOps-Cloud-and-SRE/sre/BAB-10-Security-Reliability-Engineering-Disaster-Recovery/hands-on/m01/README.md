# Hands-On Lab M01: DR Failover Health Checker & Safe Orchestrator

## Deskripsi Lab
Lab ini memberikan pengalaman langsung membangun dan memverifikasi komponen orkestrasi pemulihan bencana (Disaster Recovery Orchestrator). Peserta akan mempelajari bagaimana algoritma pemantauan modern mencegah bencana **Split-Brain** dan memvalidasi batas metrik **RPO (Recovery Point Objective)** sebelum mengeksekusi failover lintas region secara terprogram.

---

## Prasyarat Lingkungan
- Python 3.8 atau versi lebih tinggi terpasang di sistem lokal.
- Terminal berbasis Unix (macOS / Linux / WSL2 Windows).

---

## Struktur File
```
hands-on/m01/
├── README.md
└── dr_failover_health_checker.py
```

---

## Langkah Demi Langkah Menjalankan Hands-on

### Langkah 1: Navigasi dan Verifikasi Kode
Masuk ke direktori lab dan pastikan skrip dapat dieksekusi:
```bash
cd hands-on/m01
chmod +x dr_failover_health_checker.py
```

### Langkah 2: Menjalankan Simulasi Bencana
Eksekusi file skrip utama:
```bash
python3 dr_failover_health_checker.py
```

### Langkah 3: Menganalisis Output Konsol
Amati log eksekusi secara cermat:
1. **Skenario 1 (Operasi Normal)**: Perhatikan bagaimana sistem tetap berada dalam status `PRIMARY_ACTIVE`.
2. **Skenario 2 (Controlled Failover)**:
   - Primer mati secara konsisten selama 3 probe berurutan (*failure threshold* terpenuhi).
   - Logika memeriksa *replication lag* (1.5s $\le$ 4.0s). Ambang batas RPO aman.
   - Fase 1: *STONITH Fencing* dieksekusi untuk mematikan node primer lama.
   - Fase 2: Promosi Region Sekunder berhasil dipicu tanpa insiden split-brain.
3. **Skenario 3 (RPO Safety Guard Triggered)**:
   - Primer mati, tetapi *replication lag* bernilai 12.8 detik (melanggar ambang batas maksimal 4.0 detik).
   - Orkestrator menolak melakukan promosi otomatis, mengunci sistem dalam status `SPLIT_BRAIN_LOCKDOWN`, dan memicu peringatan eskalasi darurat.

---

## Eksperimen Mandiri (Challenge Extension)
1. Modifikasi objek `env_mock` pada file `dr_failover_health_checker.py` agar fungsi `fencing_success` bernilai `False`. Amati bagaimana sistem menolak mempromosikan node sekunder saat node primer gagal diisolasi.
2. Tambahkan variabel dinamis untuk menghitung rata-rata bergerak (*moving average*) dari replication lag selama 10 siklus terakhir sebelum membuat keputusan failover.
3. Integrasikan skrip ini dengan *mock webhook* Slack/Discord untuk mengirimkan payload alert otomatis saat status berpindah ke `SPLIT_BRAIN_LOCKDOWN`.