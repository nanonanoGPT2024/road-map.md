# Module 02: Otomasi Shell Scripting (Bash) & Diagnostik Sistem

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar akan mampu:
1. Menulis script otomasi Bash standar produksi dengan menerapkan prinsip *defensive programming* (`set -euo pipefail`).
2. Melakukan diagnostik performa sistem secara komprehensif menggunakan utility Linux esensial (`top`/`htop`, `vmstat`, `iostat`, `netstat`/`ss`).
3. Mengelola daemon background dan unit service menggunakan **Systemd** (`systemctl`, unit files, dan timer pengganti cron).
4. Melakukan troubleshooting log terpusat dengan filter query lanjut pada **Journalctl**.

---

## 2. Prerequisite
- Memahami konsep dasar User Space vs Kernel Space dan sinyal proses dari [BAB 01 Module 01](file:///d:/explore/roadmap.sh%20materi/DevOps/BAB-01-Sistem-Operasi-dan-Linux-Automation/Module-01-Arsitektur-Kernel-Linux-Manajemen-Proses-dan-Konkurensi.md).
- Mengetahui navigasi filesystem Linux (`cd`, `ls`, `cat`, `grep`, `awk`, `sed`).

---

## 3. Concept
Sebagai seorang DevOps Engineer, tugas utama Anda adalah mengeliminasi pekerjaan repetitif (*toil*) melalui otomatisasi dan memastikan server selalu dalam kondisi prima.

Dua pilar fundamental dalam administrasi server Linux modern:
1. **Defensive Shell Scripting (Bash)**: Bash sering digunakan untuk provisioning awal, healthcheck container, dan pipeline CI/CD runner. Script yang ditulis serampangan dapat menghapus data jika variabel kosong (contoh terkenal: `rm -rf $DIR/` jika `$DIR` tidak terdefinisi akan mengeksekusi `rm -rf /`!). Dengan `set -euo pipefail`, setiap error dan variabel tak terdefinisi langsung menghentikan script seketika (*fail-fast*).
2. **Systemd & Modern Diagnostics**: Linux modern tidak lagi menggunakan SysV init scripts lawas (`/etc/init.d/`). Systemd adalah init system standar (PID 1) yang mengelola dependency service, auto-restart saat crash, batasan cgroup cgroups, timer terjadwal, dan logging biner terindeks via `journald`.

---

## 4. Why?
Mengapa topik ini krusial?
1. **Keandalan Script CI/CD & Deployments**: Script deployment yang gagal di tengah jalan tetapi tetap mengembalikan exit code 0 dapat merilis kode cacat ke production. *Defensive flags* menjamin integritas alur build.
2. **Kecepatan Triage Insiden (MTTD/MTTR)**: Saat CPU server melonjak 100% atau memory leak terjadi pada jam 2 pagi, engineer yang menguasai kombinasi `htop`, `vmstat`, dan `journalctl -xeu` dapat menemukan akar masalah dalam 60 detik.
3. **Standarisasi Service Production**: Mengemas aplikasi ke dalam unit service Systemd memberikan jaminan restart otomatis dan log rotation tanpa perlu tool supervisor pihak ketiga tambahan.

---

## 5. What?
Komponen penting dalam otomatisasi dan diagnostik:
- **Bash Strict Mode**: `set -euo pipefail`
  - `-e`: Berhenti seketika jika ada command yang mengembalikan exit status non-zero.
  - `-u`: Berhenti jika ada variabel yang belum dideklarasikan (*unbound variable*).
  - `-o pipefail`: Memastikan error di dalam pipeline (misal: `cmd1 | cmd2 | cmd3`) tetap terdeteksi meski `cmd3` sukses.
- **The USE Method (Utilization, Saturation, Errors)**: Metodologi diagnostik oleh Brendan Gregg untuk menginspeksi:
  - *CPU*: `htop`, `mpstat 1`
  - *Memory & Swap*: `free -m`, `vmstat 1`
  - *Disk I/O*: `iostat -xz 1`, `df -h`
  - *Network Socket*: `ss -tulpn`
- **Systemd Service Units**: File konfigurasi deklaratif (`.service`) yang mendefinisikan cara menjalankan, me-restart, dan membatasi resource aplikasi.

---

## 6. How?
Alur kerja diagnostik sistem saat terjadi penurunan performa:

```text
               [ Gejala: API Server Mengalami Latency Tinggi ]
                                     │
                                     ▼
                      [ Step 1: System-Wide Overview ]
                      Jalankan: uptime && free -h && df -h
                                     │
           ┌─────────────────────────┼─────────────────────────┐
           ▼                         ▼                         ▼
   [ CPU Load Tinggi ]      [ Memori Hampir Habis ]   [ Disk I/O 100% ]
   Jalankan: top / htop     Jalankan: vmstat 1        Jalankan: iostat -xz 1
   Identifikasi PID rakus   Periksa swapped memory    Cek queue request disk
           │                         │                         │
           └─────────────────────────┼─────────────────────────┘
                                     │
                                     ▼
                      [ Step 2: Deep Dive ke Proses ]
                      Jalankan: ps -p <PID> -o %cpu,%mem,cmd
                      Periksa Sockets: ss -tulpn | grep <PID>
                                     │
                                     ▼
                      [ Step 3: Inspeksi Log Systemd ]
                      Jalankan: journalctl -u my-app.service -n 100 --no-pager
                                     │
                                     ▼
                      [ Step 4: Tindakan Perbaikan ]
                      Restart Service: systemctl restart my-app
```

---

## 7. Analogy
Bayangkan **Systemd & Diagnostic Tools** seperti **Dashboard Kokpit Pesawat Terbang**:
- Menjalankan script tanpa `set -euo pipefail`: Seperti pilot yang mematikan alarm peringatan kabin dan terus terbang meski salah satu mesin mati.
- Systemd: Seperti sistem autopilot cerdas yang jika mendeteksi turbulensi kecil langsung menyeimbangkan pesawat kembali (auto-restart saat crash).
- `htop`, `vmstat`, `ss`: Indikator altimeter, kecepatan angin, dan tekanan bahan bakar yang memberitahu kondisi fisik pesawat secara real-time.

---

## 8. Diagram
```text
+------------------------------------------------------------------------+
|                          SYSTEMD (PID 1)                               |
|                                                                        |
|  +-----------------------------+      +-----------------------------+  |
|  |   API Service Unit          |      |  Database Service Unit      |  |
|  |   ExecStart=/usr/bin/node   |      |  ExecStart=/usr/bin/postgres|  |
|  |   Restart=on-failure        |      |  Restart=always             |  |
|  |   MemoryLimit=1G            |      |  CPUQuota=200%              |  |
|  +-----------------------------+      +-----------------------------+  |
|                 │                                    │                 |
|                 v                                    v                 |
|  +------------------------------------------------------------------+  |
|  |                 SYSTEMD-JOURNALD LOG COLLECTOR                   |  |
|  |  (Menangkap stdout/stderr dari semua service, terindeks biner)   |  |
|  +------------------------------------------------------------------+  |
+------------------------------------------------------------------------+
                                     │
                                     ▼
                       [ Query: journalctl -u ... ]
```

---

## 9. Simple Example
Contoh template Bash Script standar industri (`deploy.sh`):

```bash
#!/usr/bin/env bash
set -euo pipefail

# Konfigurasi variabel
readonly APP_DIR="/var/www/myapp"
readonly LOG_FILE="/var/log/myapp/deploy.log"

echo "=== [INFO] Memulai deployment pada $(date) ===" | tee -a "$LOG_FILE"

# Validasi folder tujuan
if [[ ! -d "$APP_DIR" ]]; then
  echo "=== [ERROR] Direktori $APP_DIR tidak ditemukan! ===" >&2
  exit 1
fi

cd "$APP_DIR"
git fetch origin main
git reset --hard origin/main

npm ci --production
npm run build

sudo systemctl restart myapp.service
echo "=== [SUCCESS] Deployment berhasil! ==="
```

---

## 10. Practical Example
Unit file Systemd `/etc/systemd/system/payment-gateway.service`:

```ini
[Unit]
Description=Payment Gateway Microservice
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=appuser
Group=appuser
WorkingDirectory=/opt/payment-gateway
ExecStart=/usr/bin/node src/index.js
ExecReload=/bin/kill -HUP $MAINPID

# Resiliensi & Auto-Restart
Restart=on-failure
RestartSec=3s
TimeoutStopSec=30s

# Environment & Keamanan
Environment=NODE_ENV=production PORT=3000
ProtectSystem=full
NoNewPrivileges=true
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
```

---

## 11. Real World Example
### Kasus: Insiden OOM Killer Berulang pada Production Service
1. Layanan e-commerce mengalami down mendadak setiap flash sale jam 12:00.
2. SRE memeriksa log sistem:
   ```bash
   journalctl -k | grep -i "out of memory"
   ```
3. Terlihat kernel mencatat: `Out of memory: Killed process 8421 (node) total-vm:2048MB, anon-rss:1800MB`.
4. SRE memeriksa status soket dan memori saat load tinggi:
   ```bash
   ss -s
   vmstat 1 5
   ```
5. Ditemukan bahwa aplikasi tidak me-release buffer gambar struk belanja.
6. **Solusi**: SRE mengonfigurasi batas cgroups di Systemd service (`MemoryHigh=800M`, `MemoryMax=1G`), memasang Node.js `--max-old-space-size=768`, dan menerapkan alert Prometheus sebelum OOM terjadi.

---

## 12. Trade-offs
| Alat Otomasi / Service Manager | Bash Script + Cron | Systemd Services & Timers |
|---|---|---|
| **Kompleksitas Setup** | Sangat rendah (cukup 1 file script) | Sedikit konfigurasi file `.service` dan `.timer` |
| **Pengecekan Status** | Sulit (harus parsing PID manual) | Sangat mudah (`systemctl status <service>`) |
| **Crash Recovery** | Tidak ada (jika mati, tetap mati) | Otomatis (`Restart=always` / `Restart=on-failure`) |
| **Logging** | Harus append manual ke file log teks | Otomatis ditangani `systemd-journald` |
| **Resource Limits** | Manual via `ulimit` | Terintegrasi langsung dengan kernel cgroups |

---

## 13. When To Use
- Gunakan **Systemd Service** untuk semua long-running process di server (API, proxy, queue worker, database).
- Gunakan **Bash dengan `set -euo pipefail`** untuk script otomasi deployment, task backup harian, dan hook CI/CD.

---

## 14. When NOT To Use
- Jangan gunakan Bash script untuk logika bisnis yang rumit (manipulasi JSON bersarang atau API calling kompleks); gunakan **Python** atau **Go** untuk kejelasan dan type safety.

---

## 15. Common Mistakes
1. **Lupa Memberikan Permission Eksekusi**: Lupa menjalankan `chmod +x script.sh`, menyebabkan pipeline runner CI gagal.
2. **Tidak Mengutip Variabel (*Unquoted Variables*)**: Menulis `rm -rf $TARGET_DIR` alih-alih `rm -rf "$TARGET_DIR"`. Jika path mengandung spasi (misal: `My Documents`), script akan menghapus folder yang salah.
3. **Mengabaikan Log Journalctl yang Membengkak**: Tidak mengonfigurasi `/etc/systemd/journald.conf` (`SystemMaxUse=500M`), sehingga log sistem menghabiskan 20GB disk server.

---

## 16. Best Practices
### Must Have
- Selalu awali script Bash dengan `set -euo pipefail`.
- Berikan quote pada semua ekspansi variabel: `"$MY_VAR"`.
- Konfigurasi `Restart=always` atau `Restart=on-failure` pada unit file Systemd.

### Recommended
- Gunakan `trap` di Bash untuk membersihkan temporary files saat script exit atau menerima `SIGINT`/`SIGTERM`:
  ```bash
  trap 'rm -rf "$TMP_DIR"' EXIT INT TERM
  ```
- Batasi ukuran log journald dengan `journalctl --vacuum-size=200M`.

### Avoid / Overengineering
- Jangan membuat script bash raksasa 2.000 baris; pecah menjadi fungsi modular atau pindahkan ke Python/Ansible.

---

## 17. Troubleshooting
| Gejala | Kemungkinan Penyebab | Solusi |
|---|---|---|
| Script bash berhenti tanpa pesan error | Perintah di dalam pipeline gagal dan terpicu oleh `pipefail` | Gunakan `bash -x script.sh` untuk mencetak debug trace baris demi baris |
| Service systemd gagal start (*status=203/EXEC*) | File eksekutor tidak ditemukan atau izin execute (`+x`) hilang | Periksa path di `ExecStart` dan pastikan file binari memiliki permission `chmod +x` |
| Port server sudah terpakai (*address already in use*) | Proses lama masih hidup di background | Cari PID yang mendengarkan port: `ss -tulpn | grep :<PORT>`, lalu terminate |

---

## 18. Exercise
1. Buat script Bash yang memeriksa penggunaan disk root (`/`). Jika disk > 80%, cetak peringatan ke stderr dan exit code 1.
2. Tulis file unit Systemd untuk menjalankan aplikasi dummy di background dengan auto-restart setiap 5 detik.

---

## 19. Challenge
Bangun **System Health Diagnostik Script**:
- Kumpulkan metrik CPU Load Average, Free Memory, Disk Space, dan 3 proses dengan konsumsi memori tertinggi.
- Jika ada metrik yang melampaui ambang batas kritis (misal CPU load > 4.0 atau RAM free < 10%), cetak laporan ringkas dan berikan rekomendasi aksi.

---

## 20. Summary
- *Defensive programming* pada Bash (`set -euo pipefail`) mencegah bencana operasional dan rilis cacat.
- Systemd adalah orkestrator standar di Linux modern yang mengelola daemons, auto-restart, dan isolasi resource.
- Menguasai metrik USE Method (`top`, `vmstat`, `iostat`, `ss`) mempersingkat waktu diagnosa insiden produksi secara dramatis.
- Modul praktikum lab dapat dijalankan langsung di [hands-on/m02/system_diagnostic_bash_sim.js](file:///d:/explore/roadmap.sh%20materi/DevOps/BAB-01-Sistem-Operasi-dan-Linux-Automation/hands-on/m02/system_diagnostic_bash_sim.js).
