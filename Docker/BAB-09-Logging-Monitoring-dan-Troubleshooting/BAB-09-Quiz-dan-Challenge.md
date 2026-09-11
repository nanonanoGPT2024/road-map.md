# BAB 09 — Quiz & Chapter Challenge: Logging, Monitoring, & Troubleshooting

Dokumen ini menguji pemahaman Anda terhadap arsitektur logging Docker, konfigurasi log rotation, integrasi centralized logging, monitoring metrik cgroups via cAdvisor/Prometheus, serta pemecahan masalah insiden kontainer (Exit Codes, OOM Killer).

---

## Bagian 1: Basic Quiz (5 Pertanyaan)

### Soal 1
Apa risiko terbesar jika sebuah host production menjalankan puluhan container dengan logging driver default `json-file` tanpa opsi `max-size`?
- A. Container akan otomatis menghapus image induknya.
- B. File JSON log di direktori `/var/lib/docker/containers/` akan terus bertambah besar tanpa batas hingga hard disk host 100% penuh, yang dapat melumpuhkan seluruh sistem operasi host.
- C. Port container akan otomatis tertutup.
- D. Docker daemon menolak koneksi SSH host.

### Soal 2
Bagaimana cara mengosongkan (truncate) file log container yang berukuran puluhan gigabyte secara aman di server tanpa harus mematikan atau me-restart container?
- A. Menjalankan `rm -rf /var/lib/docker/containers/<id>/<id>-json.log`.
- B. Menjalankan `truncate -s 0 /var/lib/docker/containers/<id>/<id>-json.log`.
- C. Mematikan listrik server secara mendadak.
- D. Menjalankan `docker system prune -a --force`.

### Soal 3
Apa arti dari **Exit Code 137** pada container Docker?
- A. Aplikasi berhasil menyelesaikan eksekusi dengan status sukses.
- B. Executable file tidak ditemukan di `$PATH` (Command not found).
- C. Container dihentikan secara paksa oleh sinyal `SIGKILL` (Sinyal 9, 128 + 9 = 137), yang umumnya dipicu oleh Linux Kernel OOM Killer atau `docker kill`.
- D. Script entrypoint tidak memiliki izin eksekusi (`chmod +x`).

### Soal 4
Perintah CLI manakah yang memberikan snapshot metrik real-time terkait penggunaan CPU%, Memory%, dan Network I/O dari container yang sedang berjalan?
- A. `docker ps -a`
- B. `docker top`
- C. `docker stats`
- D. `docker events`

### Soal 5
Apa perbedaan perilaku antara logging driver `mode: blocking` dan `mode: non-blocking`?
- A. Mode blocking menghapus log, mode non-blocking menggandakan log.
- B. Mode blocking menahan eksekusi aplikasi jika proses penulisan log ke disk/network lambat, sedangkan mode non-blocking menyimpan log dalam in-memory ring buffer sehingga aplikasi tidak pernah tertunda.
- C. Mode blocking hanya untuk container database.
- D. Tidak ada perbedaan performa sama sekali.

---

## Bagian 2: Intermediate Quiz (5 Pertanyaan)

### Soal 6
Perintah inspeksi `docker inspect` manakah yang paling akurat untuk memastikan secara definitif apakah container mati karena melampaui batas memori yang ditentukan cgroups?
- A. `docker inspect <id> --format '{{.State.Status}}'`
- B. `docker inspect <id> --format '{{.State.OOMKilled}}'`
- C. `docker inspect <id> --format '{{.Config.Image}}'`
- D. `docker inspect <id> --format '{{.NetworkSettings.IPAddress}}'`

### Soal 7
Jika container Node.js Anda dialokasikan memory limit `--memory=512m` pada Docker, berapa batas ideal untuk opsi `--max-old-space-size` pada runtime V8 Node.js?
- A. 1024 MB
- B. 512 MB (sama persis)
- C. Sekitar 384 MB - 400 MB (75-80% dari batas container) untuk menyisakan ruang bagi stack memory, buffer native, dan proses internal Node.js.
- D. 50 MB

### Soal 8
Mengapa container Anda langsung berhenti (exit) dengan **Exit Code 126** sesaat setelah dijalankan dengan `docker run`?
- A. Port host sudah digunakan oleh service lain.
- B. File script `entrypoint.sh` di dalam container tidak memiliki hak akses eksekusi (`executable bit / chmod +x`).
- C. Image belum di-download dari Docker Hub.
- D. RAM server sudah habis.

### Soal 9
Apa peran Google cAdvisor dalam arsitektur observability container modern?
- A. Menggantikan peran kernel Linux dalam scheduling thread.
- B. Mengumpulkan metrik historis resource usage (CPU, Memory, Network, Disk I/O) langsung dari Linux cgroups di host dan mengeksposnya dalam format metrik Prometheus.
- C. Mengenkripsi traffic SSL container.
- D. Menyimpan backup data database Postgres.

### Soal 10
Mengapa menjalankan `rm -f /var/lib/docker/containers/<id>/<id>-json.log` saat container masih aktif tidak langsung membebaskan kapasitas disk host?
- A. Karena file log terenkripsi oleh BIOS.
- B. Karena proses container runtime masih membuka open file descriptor (FD) ke file tersebut di memori kernel Linux, sehingga inode file belum dilepas sampai proses container dimatikan.
- C. Karena file log otomatis berpindah ke Recycle Bin Windows.
- D. Karena Docker daemon mengunci port 80.

---

## Bagian 3: Scenario-Based Questions (3 Skenario)

### Skenario 1: Misteri Crash Tengah Malam pada Worker Batch Job
Sebuah worker pemrosesan laporan keuangan (Python) dijalankan di dalam container dengan batasan `deploy.resources.limits.memory: 1G`.
Setiap tengah malam saat memproses data akhir bulan, worker ini tiba-tiba mati tanpa ada jejak pesan error atau traceback di log aplikasi (`docker logs` bersih).
Saat dicek di pagi hari, status container adalah `Exited (137)`.
- **Pertanyaan**: Jelaskan mengapa log aplikasi tidak sempat mencatat exception, bagaimana Anda membuktikan hipotesis OOM Killer menggunakan CLI, dan berikan 2 strategi perbaikan arsitektur untuk mencegah insiden ini terulang kembali!

### Skenario 2: Latensi API Melonjak Akibat Driver Logging Syslog
Sebuah tim backend mengonfigurasi logging driver `syslog` ke server remote syslog di data center lain.
Ketika koneksi VPN antar kantor mengalami gangguan dan packet loss mencapai 15%, latensi response endpoint HTTP API melonjak drastis dari 20ms menjadi 5000ms (timeout), meskipun beban CPU dan memori server API sangat rendah (dibawah 10%).
- **Pertanyaan**: Mengapa gangguan jaringan ke server log eksternal dapat memperlambat respon HTTP API aplikasi, dan bagaimana konfigurasi Docker logging yang harus diperbaiki?

### Skenario 3: Host Storage Exhaustion Emergency
Server production Docker Anda mengirimkan alert kritis PagerDuty: `Disk /dev/sda1 utilization 99.8%`.
Setelah dicek, partisi `/var/lib/docker/containers/` memakan 180GB dari 200GB storage.
- **Pertanyaan**: Tuliskan urutan komando terminal untuk:
  1. Menemukan container mana yang bertanggung jawab atas file log raksasa tersebut.
  2. Mengosongkan file log tersebut dengan aman dalam hitungan detik tanpa downtime.
  3. Konfigurasi file `/etc/docker/daemon.json` agar masalah ini tidak pernah terjadi lagi selamanya.

---

## Bagian 4: Chapter Challenge

### Tantangan Praktis: Production Observability & Self-Healing Watchdog
1. **Skenario**:
   Anda ditugaskan mendirikan stack monitoring standar untuk cluster microservices Docker mandiri di cloud instance:
   - Stack monitoring harus terdiri dari **cAdvisor** dan **Prometheus**.
   - Menjalankan satu microservice target yang memiliki endpoint beban CPU dan alokasi memori dinamis.
   - Mengonfigurasi Docker logging global dengan driver `json-file`, batas rotasi `max-size: 10m`, `max-file: 3`, dan `mode: non-blocking`.
2. **Deliverables**:
   - File `docker-compose.monitoring.yml` yang menghubungkan cAdvisor dan Prometheus di network terisolasi.
   - Konfigurasi `prometheus.yml` untuk scraping cAdvisor setiap 10 detik.
   - Rule alert Prometheus (`alerts.yml`) yang mendeteksi jika container menggunakan memory > 85% selama 1 menit berturut-turut.

---

## Bagian 5: Knowledge Check & Checklist

### Saya Harus Memahami:
- [ ] Arsitektur aliran log dari proses container (`stdout`/`stderr`) ke logging driver.
- [ ] Risiko fatal unrotated logs pada ketersediaan disk host.
- [ ] Perbedaan logging mode: `blocking` vs `non-blocking`.
- [ ] Makna teknis kode keluar container: Exit Codes 0, 1, 126, 127, 137, dan 143.
- [ ] Mekanisme Linux cgroups OOM Killer dan sinyal `SIGKILL`.
- [ ] Peran cAdvisor dalam mengekstrak metrik kernel cgroups untuk Prometheus.

### Saya Tidak Perlu Menghafal:
- Seluruh spesifikasi konfigurasi setiap driver log eksternal (cukup pahami prinsip konfigurasi di daemon.json).
- Rumus perhitungan TSDB Prometheus time series compression.

### Saya Harus Bisa Melakukan:
- [ ] Mengonfigurasi log rotation global di `/etc/docker/daemon.json`.
- [ ] Mengonfigurasi logging options di file `docker-compose.yml`.
- [ ] Mengosongkan file log besar secara darurat menggunakan perintah `truncate`.
- [ ] Menginspeksi OOM Killer menggunakan `docker inspect -f '{{.State.OOMKilled}}'`.
- [ ] Melakukan troubleshooting terstruktur untuk exit code 126, 127, dan 137.
- [ ] Mengonfigurasi limit memori heap aplikasi (Node.js/JVM) selaras dengan limit container.
