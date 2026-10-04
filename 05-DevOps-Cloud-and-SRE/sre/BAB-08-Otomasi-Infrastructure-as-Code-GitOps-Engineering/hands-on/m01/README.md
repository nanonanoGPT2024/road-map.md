# Panduan Hands-on Lab: GitOps Drift Reconciliation & Self-Healing Circuit Breaker

Lab ini mendemonstrasikan implementasi sistem kontrol tertutup (*closed-loop control system*) berbasis SRE yang mengintegrasikan deteksi penyimpangan (*drift detection*), rekonsiliasi otomatis (*idempotent patch reconciliation*), serta pengaman sistem berupa *circuit breaker*.

---

## 1. Arsitektur Komponen Hands-on

1. **Desired State Contract**: Representasi deklaratif sistem yang bersumber dari repository Git (Single Source of Truth).
2. **Infrastructure Platform Mock**: Abstraksi runtime environment yang menyimpan actual state dan menerima mutasi out-of-band (drift).
3. **Drift Detector Engine**: Mesin perbandingan struktural yang menghitung delta perbedaan antara Desired State dan Actual State.
4. **Circuit Breaker**: Mekanisme pembatas laju pemulihan berbasis waktu (*sliding window*) untuk mencegah kerusakan massal (*remediation cascading loop*).

---

## 2. Prasyarat Lingkungan Eksekusi

- **Python**: Versi 3.8 atau lebih baru.
- Tidak memerlukan third-party library tambahan (menggunakan pustaka standar Python: `dataclasses`, `json`, `logging`, `time`, `copy`).

---

## 3. Langkah Menjalankan Hands-on

1. Buka terminal Anda dan arahkan ke direktori hands-on:
   ```bash
   cd hands-on/m01/
   ```

2. Pastikan permission eksekusi skrip telah aktif:
   ```bash
   chmod +x self_healing_auto_remediation.py
   ```

3. Jalankan skrip engine otomatisasi:
   ```bash
   python3 self_healing_auto_remediation.py
   ```

---

## 4. Pengamatan Skenario Output

Saat Anda mengeksekusi skrip, perhatikan transisi status pada output log:

- **Siklus 1 (In-Sync State)**:
  Engine memverifikasi bahwa *actual state* identik dengan *desired state*. Tidak ada tindakan mutasi yang diambil.
  
- **Siklus 2 (Out-of-band Drift Correction)**:
  Sebuah manipulasi ilegal menurunkan kapasitas pod (`replicas: 1`). Engine mendeteksi anomali ini, mencatat log deviasi, dan secara idempoten mengembalikan spesifikasi ke `replicas: 5` sesuai spesifikasi Git.

- **Siklus 3 & 4 (Protection via Circuit Breaker)**:
  Terjadi inject error berulang dalam durasi singkat (< 5 detik). Setelah batas ambang (3 kali aksi) terlewati, **Circuit Breaker beralih ke status `OPEN`**. Tindakan otomatis keempat dibatalkan untuk melindungi infrastruktur dari kondisi ketidakstabilan beruntun (*flapping storm*).

---

## 5. Eksperimen Mandiri (Latihan Lanjutan)

1. Ubah parameter `failure_threshold` menjadi `5` dan `recovery_time_window_sec` menjadi `15.0`. Amati bagaimana perubahan ini mempengaruhi sensitivitas circuit breaker.
2. Tambahkan fungsi notifikasi webhook mockup (misal: mencetak log format JSON payload PagerDuty) ketika status Circuit Breaker berpindah dari `CLOSED` ke `OPEN`.
3. Modifikasi fungsi `calculate_drift` untuk mengabaikan field tertentu (misal: metadata annotation yang dinamis seperti timestamp) agar tidak memicu rekonsiliasi palsu (*intentional drift ignore*).