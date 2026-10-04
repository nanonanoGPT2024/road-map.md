# Module 02: Production Deployment: Systemd Units, Watchtower, dan Automated Pruning

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
1. Mengintegrasikan lifecycle Docker container dan Docker Compose dengan Linux init system menggunakan **Systemd Service Unit Files** untuk memastikan auto-start saat reboot server dan recovery otomatis saat host crash.
2. Mengonfigurasi **Watchtower** untuk continuous deployment otomatis berbasis pendeteksian update digest image di container registry.
3. Membandingkan alur CD otomatis (Watchtower) vs deklaratif terkontrol (**GitOps & CI/CD Push Trigger**).
4. Merancang strategi pembersihan disk berkala (**Garbage Collection / Automated Pruning**) menggunakan `systemd.timer` dan filter `docker system prune --filter "until=168h"`.
5. Menerapkan pola deployment zero-downtime sederhana (Blue-Green / Rolling reload) pada host Docker standalone dengan reverse proxy.

---

## 2. Prerequisite
- Memahami konsep restart policies dan container lifecycle ([BAB 02 Module 02](../BAB-02-Container-Lifecycle-dan-CLI-Mastery/Module-02-Healthchecks-Restart-Policies-dan-Resource-Constraints.md)).
- Memahami multi-container orchestration dengan Docker Compose V2 ([BAB 06](../BAB-06-Multi-Container-dengan-Docker-Compose/)).
- Pemahaman dasar Linux init system (`systemctl`, `journalctl`, systemd unit files).

---

## 3. Concept
Meskipun orkestrator seperti Kubernetes dan Docker Swarm mendominasi cluster berskala masif, ratusan ribu server produksi di dunia nyata (terutama arsitektur monolitik modern, micro-SaaS, edge nodes, dan internal tooling) berjalan di atas **Single Host Docker**.

Untuk menjadikan single-host Docker siap di level *production grade*, tiga pilar operasional wajib dipenuhi:
1. **Host-Level Supervision (Systemd)**: Container dan stack Compose harus diperlakukan sebagai first-class system service oleh kernel Linux, hidup otomatis saat server boot, dan dikelola via `systemctl`.
2. **Controlled Delivery (Continuous Deployment)**: Pembaruan versi container baru harus dapat dilakukan dengan downtime minimal tanpa campur tangan SSH manual developer.
3. **Automated Housekeeping (Disk Hygiene)**: Tanpa pembersihan berkala, tumpukan *dangling images*, layer cache lama, dan container logs akan membuat disk host penuh dalam beberapa minggu.

---

## 4. Why?
1. **Ketahanan Reboot (Survival Across Host Reboots)**: Ketika penyedia cloud (AWS/GCP) me-reboot VM Anda karena maintenance kernel, Systemd menjamin seluruh stack database dan backend langsung hidup kembali dengan urutan dependensi yang benar.
2. **Eliminasi Manual SSH Deployment**: Menghentikan kebiasaan buruk developer masuk via SSH ke server production lalu menjalankan `docker-compose down && docker-compose up -d`.
3. **Mencegah Keruntuhan Storage (Disk Exhaustion)**: Image lama dan build cache yang menumpuk dapat menghabiskan 50-100GB storage dalam waktu singkat jika CI/CD sering merilis update.

---

## 5. What?
### Komponen Kunci Operasional Docker Production:

| Komponen | Peran Operasional | Alternatif |
|---|---|---|
| **Systemd Service Unit** | Mengikat proses Docker Compose ke daemon Linux systemd; menangani auto-start, timeout, cgroup tracking. | Restart policy `restart: always` (namun tidak menangani urutan network readiness OS). |
| **Watchtower** | Kontainer pengawas yang melakukan polling ke registry dan otomatis me-restart kontainer jika mendeteksi image digest baru. | GitHub Actions SSH webhook / Portainer Edge Agent. |
| **Systemd Timer + Prune** | Penjadwal cron modern untuk membersihkan container `exited`, build cache usang, dan dangling layers. | Cron job konvensional `/etc/crontab`. |
| **Reverse Proxy Reload** | Nginx / Traefik yang mengarahkan traffic antara container versi lama dan versi baru tanpa memutus koneksi client. | Caddy / Envoy Proxy. |

---

## 6. How? Arsitektur Systemd Unit & Deployment Flow

```text
       [ Linux Kernel / Systemd PID 1 ]
                      |
                      v (Saat server boot: network-online.target tercapai)
       +-------------------------------------------------------------+
       | /etc/systemd/system/docker-compose-app.service              |
       | - Requires=docker.service                                   |
       | - After=docker.service network-online.target                |
       | - ExecStart=/usr/bin/docker compose -f ... up -d            |
       | - ExecStop=/usr/bin/docker compose -f ... stop              |
       +-------------------------------------------------------------+
                      |
                      v
       +-------------------------------------------------------------+
       |                  Docker Engine Daemon                       |
       |                                                             |
       |   +-----------------------+     +-----------------------+   |
       |   | Nginx / Traefik Proxy |     | Watchtower Daemon     |   |
       |   | (Zero-Downtime Router)|     | (Polling Image Tags)  |   |
       |   +-----------------------+     +-----------------------+   |
       |               |                             |               |
       |               v                             v               |
       |   +-----------------------+        Registry Polling         |
       |   | Backend Microservices |        (Pull new SHA digest)    |
       |   +-----------------------+                                 |
       +-------------------------------------------------------------+
                      ^
                      | (Pembersihan Mingguan Terjadwal)
       +-------------------------------------------------------------+
       | systemd-timer: docker-prune.timer                           |
       | -> docker system prune -af --filter "until=168h"            |
       +-------------------------------------------------------------+
```

---

## 7. Analogy
Bayangkan server Anda adalah sebuah gedung perkantoran:
- **Systemd** adalah General Manager gedung. Jika listrik gedung sempat padam lalu hidup kembali, General Manager bertugas memastikan genset, pendingin ruangan, dan sistem keamanan kantor aktif kembali dalam urutan yang tepat sebelum karyawan masuk.
- **Watchtower** adalah kurir ekspedisi otomatis yang selalu memeriksa kotak pos. Saat paket perabot kantor baru tiba, kurir langsung mengganti perabot lama dengan yang baru.
- **Docker Prune Timer** adalah petugas kebersihan (cleaning service) yang datang setiap Minggu malam untuk membuang kardus-kardus bekas dan barang rusak yang sudah tidak terpakai lebih dari 7 hari.

---

## 8. Diagram: Pola Zero-Downtime Blue-Green Single-Host

```text
Langkah 1: Versi Aktif (Blue) Melayani Traffic
User Traffic ----> [ Reverse Proxy: Nginx ]
                           |
                           v
              +---------------------------+      +---------------------------+
              | Container: API v1 (Blue)  |      | Container: API v2 (Green) |
              | Port Host: 8081 (ACTIVE)  |      | (Belum Aktif)             |
              +---------------------------+      +---------------------------+

Langkah 2: Deployment Versi Green & Healthcheck Lolos
              +---------------------------+      +---------------------------+
              | Container: API v1 (Blue)  |      | Container: API v2 (Green) |
              | Port Host: 8081           |      | Port Host: 8082 (HEALTHY!)|
              +---------------------------+      +---------------------------+

Langkah 3: Nginx Reload Konfigurasi (0ms Downtime) & Matikan Blue
User Traffic ----> [ Reverse Proxy: Nginx ]
                                   |
                                   +--------------------------+
                                                              v
              +---------------------------+      +---------------------------+
              | Container: API v1 (Blue)  |      | Container: API v2 (Green) |
              | (Diberhentikan / Standby) |      | Port Host: 8082 (ACTIVE)  |
              +---------------------------+      +---------------------------+
```

---

## 9. Simple Example: Systemd Unit File untuk Docker Compose

Buat file `/etc/systemd/system/production-stack.service`:

```ini
[Unit]
Description=Production Docker Compose Application Stack
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/production-app
ExecStart=/usr/bin/docker compose up -d --remove-orphans
ExecStop=/usr/bin/docker compose stop
ExecReload=/usr/bin/docker compose pull --quiet && /usr/bin/docker compose up -d --remove-orphans
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
```

### Mengaktifkan Service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable production-stack.service
sudo systemctl start production-stack.service
sudo systemctl status production-stack.service
```

---

## 10. Practical Example: Konfigurasi Watchtower untuk Auto-Update

Jalankan Watchtower di dalam `docker-compose.yml` untuk memantau image hanya pada container yang memiliki label tertentu (**Selective Auto-Update**):

```yaml
version: '3.8'

services:
  api-service:
    image: ghcr.io/myorg/api:latest
    restart: always
    labels:
      - "com.centurylinklabs.watchtower.enable=true"
    ports:
      - "8080:8080"

  watchtower:
    image: containrrr/watchtower:1.7.1
    container_name: production-watchtower
    restart: always
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - /root/.docker/config.json:/config.json:ro
    environment:
      - WATCHTOWER_CLEANUP=true              # Hapus image lama setelah update
      - WATCHTOWER_LABEL_ENABLE=true         # Hanya update container berlabel khusus
      - WATCHTOWER_POLL_INTERVAL=300         # Cek registry setiap 5 menit (300 detik)
      - WATCHTOWER_INCLUDE_RESTARTING=true
      - WATCHTOWER_NOTIFICATIONS=webhook     # Kirim alert Slack / Discord
      - WATCHTOWER_NOTIFICATION_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

---

## 11. Real World Example: Automated Garbage Collection dengan Systemd Timer

Mencegah disk penuh secara teratur tanpa mengganggu container yang sedang aktif.

### 1. Service Unit: `/etc/systemd/system/docker-prune.service`
```ini
[Unit]
Description=Automated Docker Prune Housekeeping Task
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
# Bersihkan container exited, build cache, dan image tak terpakai yang lebih tua dari 7 hari (168 jam)
ExecStart=/usr/bin/docker system prune -af --filter "until=168h"
# Bersihkan volume yatim piatu (dangling volumes)
ExecStartPost=/usr/bin/docker volume prune -f
```

### 2. Timer Unit: `/etc/systemd/system/docker-prune.timer`
```ini
[Unit]
Description=Weekly Docker Prune Execution Timer

[Timer]
# Jalankan setiap hari Minggu pukul 03:00 dini hari
OnCalendar=Sun *-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

### Aktivasi Timer:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now docker-prune.timer
# Cek jadwal eksekusi timer berikutnya
systemctl list-timers | grep docker-prune
```

---

## 12. Trade-offs: Watchtower vs GitOps Pull vs CI/CD Push Webhook

| Pendekatan | Kelebihan | Kekurangan | Rekomendasi Lingkungan |
|---|---|---|---|
| **Watchtower** (Polling Registry) | Sangat praktis, 0 konfigurasi pipeline CD, otomatis menghapus image usang. | Kurang terkontrol, berpotensi deploy saat jam sibuk jika developer me-release tag, risiko rate limit registry. | Staging, Edge Devices, Homelab, Internal Tooling. |
| **CI/CD Push via SSH/Webhook** | Terkontrol ketat oleh rilis GitHub Actions / GitLab CI, approval gate jelas. | Membutuhkan kredensial SSH server di GitHub Secrets (risiko keamanan). | Production Small-to-Medium Enterprise. |
| **GitOps Agent** (Portainer / ArgoCD) | Manifest tersimpan di Git (Single Source of Truth), automatic drift detection. | Membutuhkan arsitektur kontroler atau agent tambahan. | Production Enterprise / Kubernetes. |

---

## 13. When To Use
- Gunakan **Systemd Unit Files** untuk seluruh server Docker standalone yang menjalankan beban kerja kritis.
- Gunakan **Automated Prune Timer** dengan filter `until=168h` di seluruh host Docker CI/CD runner dan staging/production server.
- Gunakan **Watchtower** pada environment staging atau fleet IoT Raspberry Pi yang tersebar di lapangan.

---

## 14. When NOT To Use
- **JANGAN gunakan Watchtower di cluster produksi misi kritis finansial**: Pembaruan container otomatis tanpa audit rilis manusia atau jadwal maintenance window dapat memicu downtime tak terduga.
- **Jangan jalankan `docker system prune -af --volumes` tanpa filter `until` secara membabi buta**: Perintah ini dapat menghapus named volume yang tidak sengaja sedang dilepas dan menghapus image cache berharga.

---

## 15. Common Mistakes
1. **Hanya mengandalkan `restart: always` tanpa Systemd**: Jika docker daemon crash atau hang saat reboot OS, container tidak pernah di-supervisi oleh system manager OS.
2. **Menjalankan `docker system prune -af` di server database tanpa mengecualikan volume**: Bisa menghapus data persisten jika volume tidak diberi nama secara benar.
3. **Mengizinkan Watchtower memantau semua container secara global**: Dapat me-restart database PostgreSQL di tengah transaksi berjalan saat image database ter-update minor.

---

## 16. Best Practices
### Must Have
- Ikat setiap stack Docker Compose produksi ke dalam Systemd Unit File dengan `After=network-online.target`.
- Jadwalkan pembersihan storage menggunakan Systemd Timer dengan filter durasi (`until=168h`).
- Gunakan graceful shutdown handling di Compose (`stop_grace_period: 30s`) agar worker menyelesaikan job sebelum dimatikan.

### Recommended
- Batasi Watchtower hanya untuk kontainer yang memiliki label eksplisit (`WATCHTOWER_LABEL_ENABLE=true`).
- Pasang notifikasi Discord/Slack pada Watchtower agar tim mengetahui kapan pun terjadi rolling restart.

### Advanced
- Buat pipeline Blue-Green rolling script dengan healthcheck validasi HTTP (200 OK) sebelum traffic reverse proxy dialihkan dan container lama dihentikan.

---

## 17. Troubleshooting Guide
### Problem 1: `production-stack.service` gagal start saat boot OS
- **Penyebab**: Docker daemon belum sepenuhnya siap menerima koneksi socket UNIX saat systemd mengeksekusi `docker compose up`.
- **Solusi**: Tambahkan direktif `Requires=docker.service` dan `After=docker.service` pada unit file `[Unit]`.

### Problem 2: Watchtower gagal pull image dari private registry
- **Penyebab**: Watchtower tidak memiliki volume mount ke file kredensial Docker host `/root/.docker/config.json`.
- **Solusi**: Mount konfigurasi kredensial ke `/config.json:ro` di dalam service Watchtower.

---

## 18. Exercises
### Level: Easy
1. Tuliskan perintah untuk melihat estimasi kapasitas disk yang dapat dibebaskan oleh Docker tanpa melakukan penghapusan:
   `docker system df`
2. Jalankan pembersihan khusus untuk container yang sudah berstatus `exited`:
   `docker container prune`

### Level: Medium
1. Buat Systemd Service unit file lokal di mesin Linux/WSL untuk menjalankan service web Nginx.
2. Uji status unit tersebut menggunakan `systemctl status <nama-unit>`.
3. Simulasikan reboot service menggunakan `systemctl restart <nama-unit>`.

### Level: Hard
1. Buat stack Docker Compose yang menyertakan service web dan Watchtower dengan mode label restriction.
2. Simulasikan push image versi baru ke registry lokal dan amati bagaimana Watchtower mendeteksi digest baru, mematikan container lama, dan menyalakan container baru secara otomatis.

---

## 19. Challenge
Rancang arsitektur Zero-Downtime Blue-Green Deployment pada satu host Ubuntu VM:
- Terdapat dua file compose: `docker-compose.blue.yml` (Port 8081) dan `docker-compose.green.yml` (Port 8082).
- Reverse Proxy Nginx mengarahkan port 80/443 ke upstream aktif.
- Buat bash script `deploy.sh` yang:
  1. Mendeteksi warna mana yang sedang aktif.
  2. Menyalakan warna lawannya.
  3. Melakukan curl polling healthcheck ke `/healthz` sampai HTTP 200 OK.
  4. Mengganti upstream Nginx dan me-reload Nginx dengan `nginx -s reload`.
  5. Mematikan warna lama.

---

## 20. Summary
- **Systemd** adalah fondasi keandalan host Linux untuk memastikan Docker Compose hidup otomatis setelah server reboot atau crash.
- **Watchtower** menyediakan automasi continuous deployment otomatis berbasis perubahan image registry, sangat ideal untuk staging dan edge computing.
- **Automated Housekeeping** melalui Systemd Timer dan `docker system prune --filter "until=168h"` menjamin kapasitas disk host tetap terjaga dari bloat.
- Pola **Blue-Green** dengan reverse proxy memungkinkan rilis aplikasi tanpa downtime pada arsitektur single-host.
