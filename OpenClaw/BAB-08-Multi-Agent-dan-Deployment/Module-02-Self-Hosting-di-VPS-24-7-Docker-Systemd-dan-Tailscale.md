# Module 02: Self-Hosting di VPS 24/7 (Docker, Systemd, & Tailscale)

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar akan mampu:
1. Menyiapkan environment server Linux VPS (Ubuntu/Debian) yang aman untuk operasional OpenClaw 24/7.
2. Mengonfigurasi **Docker Compose** dan **Systemd Daemon Service** dengan auto-restart, log rotation, dan resource monitoring.
3. Mengamankan akses remote ke OpenClaw Dashboard dan Webhooks tanpa mengekspos port publik ke internet menggunakan **Tailscale VPN / Wireguard Mesh**.
4. Menerapkan strategi backup berkala (*Automated State & Memory Backup*) dan Disaster Recovery untuk sesi agent.

---

## 2. Prerequisite
- Memahami dasar administrasi Linux (SSH, user management, systemctl, journalctl).
- Menguasai dasar Docker dan Docker Compose.
- Telah memahami konfigurasi daemon OpenClaw dari [BAB 01](file:///d:/explore/roadmap.sh%20materi/OpenClaw/BAB-01-Fondasi-dan-Arsitektur/Module-02-Instalasi-CLI-dan-Diagnostic-Healthcheck.md).

---

## 3. Concept
Menjalankan OpenClaw di laptop pribadi membatasi kemampuannya: ketika laptop ditutup (sleep mode) atau kehilangan koneksi Wi-Fi, bot Telegram Anda mati dan semua jadwal cron/heartbeat terhenti.

Untuk menjadikannya asisten sejati yang hidup 24/7, OpenClaw harus di-host pada sebuah **Virtual Private Server (VPS)** murah (seperti Hetzner, DigitalOcean, Linode, atau AWS Lightsail).

Namun, meletakkan agent yang memiliki akses shell ke internet publik memerlukan pertahanan berlapis:
1. **Service Persistence**: Menggunakan `systemd` atau Docker daemon restart policy (`restart: unless-stopped`) agar agent bangkit otomatis jika VPS reboot.
2. **Zero Open Ports (Tailscale Mesh VPN)**: Jangan membuka port web UI atau port SSH secara telanjang ke IP publik. Hubungkan VPS ke private mesh network Tailscale sehingga dashboard agent hanya dapat dibuka dari HP dan laptop pribadi Anda.
3. **Log & Storage Quarantine**: Membatasi ukuran log journald agar tidak memenuhi harddisk server.

---

## 4. Why?
Mengapa self-hosting di VPS 24/7 dengan Tailscale adalah pola arsitektur terbaik?
1. **Always-On Reliability**: Heartbeat memeriksa server jam 3 pagi, webhook Stripe diproses detik itu juga, dan briefing pagi terkirim tepat waktu sebelum Anda bangun.
2. **Kekebalan dari Serangan Botnet Internet**: Dengan Tailscale, port OpenClaw tersembunyi dari pemindaian bot Shodan / Masscan di internet publik. Tidak ada risiko serangan brute-force.
3. **Kemandirian Penuh & Biaya Rendah**: VPS $4-$6/bulan sudah lebih dari cukup untuk menjalankan daemon Node.js OpenClaw dengan performa tinggi.

---

## 5. What?
Komponen arsitektur deployment VPS:
- **Systemd Unit (`openclaw.service`)**: Mengelola lifecycle proses Node.js, auto-restart saat crash, dan routing stdout ke `journald`.
- **Docker Compose Stack**: Opsi containerisasi alternatif yang membungkus OpenClaw gateway, ChromaDB/Qdrant vector store, dan sandbox container runner.
- **Tailscale Daemon (`tailscaled`)**: Membentuk encrypted WireGuard tunnel point-to-point antara HP/Laptop Anda dan server VPS.
- **Backup Cron Script**: Mengarsip folder `~/.openclaw/data` (database memori & konfigurasi) ke cloud storage terenkripsi secara harian.

---

## 6. How?
Alur arsitektur deployment 24/7 di VPS:

```text
[ Smartphone / Laptop User ] (Tailscale IP: 100.80.x.x)
              │
              │ Encrypted WireGuard P2P Tunnel (Zero Public Ports)
              ▼
   [ VPS Linux Terisolasi ] (Tailscale IP: 100.90.y.y)
   (Port Publik UFW Firewall: 22 SSH Key-Only, Port Webhook: Tunnel)
              │
              ├── [ Systemd / Docker Supervisor ]
              │   ├── openclaw-gateway (Process Watchdog & Auto-Restart)
              │   └── openclaw-vector-db (Chroma/Qdrant)
              │
              ├── [ Local Cron Job (Daily 02:00) ]
              │   └── Backup Memory Snapshot -> Encrypted S3/R2
              │
              └── [ Outbound Internet Only ]
                  ├── LLM API Providers (OpenAI, Anthropic, Gemini)
                  └── Messaging Channels (Telegram API, Discord WS)
```

---

## 7. Analogy
Bayangkan **Self-Hosting di VPS dengan Tailscale** seperti **Menyewa Kantor Pribadi di Gedung Berpengamanan Tinggi**:
- Menjalankan di laptop: Seperti membuka lapak di atas meja kafe. Saat Anda beres-beres pulang, semua urusan terhenti.
- Menaruh di VPS dengan IP publik terbuka: Seperti menyewa ruko tetapi pintunya kaca transparan tanpa gembok di pinggir jalan raya rawan maling.
- Menaruh di VPS dengan Tailscale: Seperti kantor di bunker tertutup tanpa plang nama di luar, di mana hanya karyawan bermobil khusus dengan kartu akses magnetik (kunci Tailscale) yang tahu alamat dan bisa masuk ke dalam ruangan.

---

## 8. Diagram
```text
Public Internet
       X (Blocked by UFW Firewall)
       v
+-------------------------------------------------------------+
|                      LINUX VPS (Ubuntu)                     |
|                                                             |
|  +---------------------+        +------------------------+  |
|  | Tailscale Interface | <====> | OpenClaw Web Dashboard |  |
|  | 100.90.12.34:18789  | (Safe) | localhost:18789        |  |
|  +---------------------+        +------------------------+  |
|                                             ^               |
|                                             |               |
|                                 +------------------------+  |
|                                 | Systemd: openclaw.service |
|                                 | Restart=always         |  |
|                                 +------------------------+  |
+-------------------------------------------------------------+
```

---

## 9. Simple Example
File konfigurasi Systemd Service `/etc/systemd/system/openclaw.service`:

```ini
[Unit]
Description=OpenClaw 24/7 Personal Autonomous AI Agent
After=network.target

[Service]
Type=simple
User=openclaw
WorkingDirectory=/home/openclaw/.openclaw
ExecStart=/usr/bin/node /usr/local/bin/openclaw gateway --start
Restart=always
RestartSec=5s
Environment=NODE_ENV=production
EnvironmentFile=/home/openclaw/.openclaw/.env.vault

# Keamanan Sandbox Systemd
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/home/openclaw/.openclaw

[Install]
WantedBy=multi-user.target
```

Aktivasi service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now openclaw
sudo systemctl status openclaw
```

---

## 10. Practical Example
File `docker-compose.yml` untuk deployment OpenClaw siap produksi:

```yaml
version: '3.8'

services:
  openclaw-gateway:
    image: openclaw/gateway:latest
    container_name: openclaw-daemon
    restart: unless-stopped
    user: "1000:1000"
    environment:
      - NODE_ENV=production
      - OPENCLAW_DATA_DIR=/app/data
    volumes:
      - ./data:/app/data
      - ./config:/app/config
    ports:
      # Bind hanya ke localhost atau interface Tailscale!
      - "127.0.0.1:18789:18789"
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1024M
        reservations:
          memory: 256M
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

---

## 11. Real World Example
### Kasus: Personal Operations Assistant 24/7 Berbiaya $5/Bulan
1. Pengguna menyewa VPS 1 vCPU / 1GB RAM di Frankfurt ($4.5/bln).
2. Install Tailscale: `curl -fsSL https://tailscale.com/install.sh | sh && tailscale up`.
3. Firewall VPS dikunci rapat (`ufw default deny incoming`, izinkan hanya SSH via Tailscale).
4. Daemon OpenClaw dijalankan via Docker Compose.
5. Bot terhubung ke Telegram & WhatsApp.
6. Hasil: Agent aktif tanpa pernah mati selama 6 bulan berturut-turut, memantau server, mengingatkan tugas harian, dan merespons pesan WhatsApp pemilik dari mana pun di seluruh dunia secara instan.

---

## 12. Trade-offs
| Aspek | Systemd Native | Docker Compose |
|---|---|---|
| **Resource Overhead** | Paling rendah (langsung di kernel host) | Sedikit overhead container engine |
| **Kemudahan Isolasi** | Membutuhkan config cgroup/systemd manual | Sangat mudah (cukup atur `limits` di YAML) |
| **Reproducibility** | Bergantung pada versi runtime host | Identik di server mana pun |
| **Rekomendasi** | VPS spek sangat kecil (512MB RAM) | VPS standar (1GB+ RAM) |

---

## 13. When To Use
- Saat Anda membutuhkan agen yang selalu siaga merespons webhook dan cron schedule di jam-jam tidur Anda.
- Untuk integrasi WhatsApp session yang tidak boleh terputus agar QR code tidak kedaluwarsa.
- Operasional tim kecil yang membutuhkan bot asisten internal bersama.

---

## 14. When NOT To Use
- Jika Anda hanya ingin bereksperimen dengan prompt dan mengetes fitur baru selama 15 menit (cukup gunakan CLI lokal di laptop).

---

## 15. Common Mistakes
1. **Mengekspos Port Web UI (18789) ke Public IP (0.0.0.0)**: Siapa pun di internet dapat mengakses bot Anda jika tidak ada reverse proxy dan autentikasi kuat. Selalu bind ke `127.0.0.1` atau gunakan Tailscale.
2. **Log File Membengkak Tanpa Batas**: Mengabaikan rotasi log Docker / Systemd sehingga harddisk VPS penuh (*No space left on device*), menyebabkan database korup. Selalu pasang `max-size: 10m`.
3. **Lupa Menyiapkan Swap Space**: Pada VPS 1GB RAM, saat agent memanggil subagent paralel, memori bisa mengalami OOM (*Out of Memory*). Siapkan swap file 2GB (`fallocate -l 2G /swapfile`).

---

## 16. Best Practices
### Must Have
- Pasang `restart: unless-stopped` di Docker atau `Restart=always` di Systemd.
- Konfigurasi log rotation maksimal 3 file x 10MB.
- Buat swap memory 2GB untuk mencegah OOM killer mematikan daemon.

### Recommended
- Gunakan Tailscale untuk menghubungkan laptop/HP Anda dengan VPS secara privat tanpa public IP port.
- Otomatiskan backup snapshot memori SQLite/ChromaDB harian ke storage offsite (misal Cloudflare R2 / AWS S3).

### Avoid / Overengineering
- Jangan memasang Kubernetes multi-node yang rumit hanya untuk menjalankan 1 personal agent bot.

---

## 17. Troubleshooting
| Gejala | Kemungkinan Penyebab | Solusi |
|---|---|---|
| Service tiba-tiba mati dengan exit code 137 | OOM (Out of Memory) Killer mematikan proses | Tambahkan swap memory atau naikkan RAM VPS |
| Bot tidak bisa mengakses internet outbound | DNS server VPS tidak terkonfigurasi atau firewall memblokir UDP 53 | Periksa `/etc/resolv.conf`, gunakan Google DNS `8.8.8.8` |
| Webhook dari internet gagal masuk ke VPS | Port diblokir oleh Tailscale-only policy | Gunakan Cloudflare Tunnel (`cloudflared`) khusus untuk domain publik webhook |

---

## 18. Exercise
1. Tulis file `docker-compose.yml` yang menyertakan limit CPU 50% dan Memory 512MB untuk OpenClaw container.
2. Tulis bash command untuk memeriksa status logs systemd daemon secara real-time (`journalctl -u openclaw -f`).

---

## 19. Challenge
Rancang script **Watchdog Self-Healing Daemon**:
- Script memeriksa endpoint healthcheck `http://localhost:18789/healthz` setiap 10 detik.
- Jika endpoint tidak merespons 3x berturut-turut, script mencatat insiden dan me-restart container secara otomatis.

---

## 20. Summary
- Self-hosting di VPS memberikan stabilitas operasional 24/7 bagi agen OpenClaw Anda.
- Kombinasi Docker Compose / Systemd menjaga daemon tetap hidup dari crash, sementara Tailscale menyediakan lapisan privasi total tanpa port publik terbuka.
- Modul praktikum lab dapat dijalankan langsung di [hands-on/m02/daemon_service_runner.js](file:///d:/explore/roadmap.sh%20materi/OpenClaw/BAB-08-Multi-Agent-dan-Deployment/hands-on/m02/daemon_service_runner.js).
