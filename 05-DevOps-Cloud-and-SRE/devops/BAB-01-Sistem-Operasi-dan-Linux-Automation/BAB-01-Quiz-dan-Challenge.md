# BAB 01: Quiz, Challenge, & Knowledge Check
**Fondasi Sistem Operasi & Linux Shell Automation**

---

## 1. Basic Questions (5 Soal)
1. Apa perbedaan tanggung jawab antara *User Space* dan *Kernel Space* pada arsitektur sistem operasi Linux?
2. Sebutkan apa yang terjadi ketika sebuah program memanggil syscall `fork()` diikuti dengan `execve()`!
3. Apa perbedaan mendasar antara sinyal `SIGTERM (15)` dan `SIGKILL (9)`? Sinyal mana yang dapat ditangkap (*handled*) oleh aplikasi?
4. Mengapa kita disarankan selalu menyertakan flag `set -euo pipefail` di awal setiap script Bash produksi?
5. Apakah proses berstatus `ZOMBIE (Z)` mengonsumsi memori RAM di server? Mengapa zombie tetap berbahaya jika dibiarkan menumpuk?

---

## 2. Intermediate Questions (5 Soal)
6. Jelaskan apa yang dimaksud dengan proses dalam status `D (Uninterruptible Sleep)`. Mengapa perintah `kill -9` tidak dapat mematikan proses ini?
7. Pada metodologi diagnostik USE (*Utilization, Saturation, Errors*), utility Linux apa saja yang digunakan untuk menginspeksi CPU, Memory, Disk, dan Network?
8. Mengapa pada Docker container, aplikasi yang berjalan sebagai PID 1 membutuhkan init system kecil (seperti `tini` atau `dumb-init`) jika men-spawn child processes?
9. Apa fungsi dari direktif `Restart=on-failure` dan `RestartSec=5s` pada unit file Systemd?
10. Bagaimana cara menganalisis log spesifik dari satu service Systemd pada rentang waktu 30 menit terakhir menggunakan `journalctl`?

---

## 3. Scenario-Based Questions (3 Soal)

### Skenario A: The Mystery 502 on Deployment
Sebuah aplikasi Node.js dideploy ke cluster. Setiap kali deployment baru dirilis, beberapa pelanggan mengeluhkan error HTTP 502 Bad Gateway selama 10 detik. Setelah diperiksa, Kubernetes mengirimkan sinyal stop, dan container langsung mati seketika tanpa menyelesaikan request HTTP yang sedang berjalan di *in-flight queue*.
- *Pertanyaan:* Konfigurasi penanganan sinyal apa yang harus ditambahkan di kode aplikasi dan pengaturan termination grace period apa yang harus dikonfigurasi di level orchestrator?

### Skenario B: The Runaway Bash Script
Sebuah script maintenance harian ditulis dengan baris: `rm -rf $TEMP_DATA_DIR/`. Suatu hari, variabel `$TEMP_DATA_DIR` tidak terisi karena file `.env` gagal dimuat. Script mengeksekusi `rm -rf /` dan merusak seluruh filesystem server.
- *Pertanyaan:* Flag defensive dan teknik quoting/validasi variabel apa yang seharusnya mencegah terjadinya insiden fatal tersebut?

### Skenario C: Disk Full by Unvacuumed Logs
Sebuah VPS microservice berkapasitas 20GB tiba-tiba mengalami *No space left on device*. Saat dicek dengan `df -h`, disk root 100% penuh, tetapi folder `/var/www/` hanya berukuran 2GB.
- *Pertanyaan:* Perintah apa yang Anda gunakan untuk mengidentifikasi folder mana yang memakan disk, dan bagaimana konfigurasi rotasi log `systemd-journald` untuk mencegahnya?

---

## 4. Chapter Challenge
**Tantangan Praktis: The Automated Server Health Sentinel**
Buatlah sebuah script otomasi diagnostik server yang:
1. Membaca metrik CPU Load Average (1m, 5m, 15m), Free RAM, dan kapasitas Disk root (`/`).
2. Menampilkan 3 proses dengan konsumsi memori terbesar.
3. Memeriksa apakah service kritis (`nginx` dan `postgresql`) sedang berstatus `active (running)`.
4. Jika salah satu service mati atau disk > 85%, script mengembalikan exit code 1 dan mencetak pesan peringatan terformat ke stderr.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur User Space vs Kernel Space dan peran System Calls.
- [ ] Siklus hidup proses Linux: Fork, Exec, Zombie, dan Orphan Reaping.
- [ ] Mekanisme penanganan sinyal UNIX (`SIGTERM`, `SIGKILL`, `SIGHUP`).
- [ ] Standar *defensive programming* pada shell script (`set -euo pipefail`).
- [ ] Manajemen lifecycle service Linux menggunakan Systemd dan Journalctl.

### Saya tidak perlu menghafal:
- [ ] Seluruh nomor syscall POSIX tabel assembly (cukup pahami fungsi abstraksi umumnya).
- [ ] Puluhan opsi regex rumit utilitas sed/awk yang jarang dipakai di luar script builder.

### Saya harus bisa melakukan:
- [ ] Melakukan triage cepat saat server lambat menggunakan `top`/`htop`, `vmstat`, `iostat`, dan `ss`.
- [ ] Menulis file unit Systemd (`.service`) yang tahan banting dengan auto-restart.
- [ ] Mengidentifikasi dan membasmi proses zombie dengan menginspeksi parent PID-nya.

---
*Ketik **LANJUT** untuk berpindah ke BAB 02: Jaringan, Protokol Internet, & Web Servers.*
