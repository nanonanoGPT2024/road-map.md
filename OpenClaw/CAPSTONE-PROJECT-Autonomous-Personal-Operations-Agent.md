# CAPSTONE PROJECT: Autonomous 24/7 Personal Operations Agent (Executive Butler)

---

## 1. Project Name
**The Executive Butler: An Autonomous, Multi-Channel, Proactive AI Operations Agent**

---

## 2. Objective
Membangun dan mendeploy agen personal AI otonom 24/7 yang berjalan di VPS pribadi terisolasi. Agen ini mampu:
1. Menghubungkan komunikasi lintas kanal (Telegram dan WhatsApp).
2. Menjalankan automasi proaktif terjadwal (Morning Briefing & Calendar Review) serta reaktif (*Inbound Webhook Incident Responder*).
3. Melakukan eksekusi tugas multi-domain menggunakan arsitektur *Multi-Agent Delegation* (Orchestrator, Researcher, dan DevOps Sentinel).
4. Menjalankan perintah sistem secara aman di dalam sandbox dengan pengawasan *Human-in-the-Loop* (HITL) dan perlindungan dari *Prompt Injection*.
5. Menjaga persistensi memori jangka panjang berbasis Vector RAG untuk mengingat preferensi pengguna, catatan proyek, dan konteks historis.

---

## 3. Requirements

### Functional Requirements
- **Multi-Channel Presence**: Bot dapat menerima pesan teks dan perintah suara dari Telegram dan WhatsApp.
- **Intelligent Routing & Fallback**: Menggunakan Claude 3.5 Sonnet sebagai model reasoning utama, dengan fallback otomatis ke GPT-4o dan model lokal Ollama (Qwen 2.5) jika terjadi gangguan API atau kuota habis.
- **Proactive Heartbeat & Scheduled Cron**:
  - Pukul 07:30 setiap hari: Mengirimkan *Executive Morning Briefing* (jadwal kalender, cuaca, ringkasan email belum dibaca, dan berita industri).
  - Setiap 15 menit: Heartbeat memeriksa uptime server VPS dan batas disk/RAM.
- **Inbound Event-Driven Webhooks**: Menerima webhook dari GitHub (PR review alert) dan Sentry/Datadog (crash report).
- **Human-in-the-Loop (HITL) Security**: Perintah shell yang berpotensi mengubah status server (seperti `docker restart`, `pm2`, `git push`, atau migrasi database) wajib meminta persetujuan via inline button di Telegram sebelum dieksekusi.
- **Persistent Memory & RAG**: Kemampuan mengingat preferensi pengguna (*"Saya alergi kacang"*, *"Gunakan pnpm bukan npm"*, *"Server prod IP 10.0.1.5"*) menggunakan vector search.

### Non-Functional Requirements
- **Availability**: Siaga 24/7 di VPS Linux dengan Systemd/Docker auto-restart watchdog.
- **Security & Privacy**: Port dashboard terisolasi 100% menggunakan Tailscale VPN mesh (zero public exposed ports). Secret API terenkripsi menggunakan AES-256-GCM.
- **Latency**: Respon chat interaktif di Telegram < 2 detik; delegasi tugas multi-agent paralel < 10 detik.
- **Resource Footprint**: Ringan, dapat beroperasi stabil pada VPS 1 vCPU / 1GB RAM dengan swap 2GB.

---

## 4. Features Matrix
| Modul Fitur | Deskripsi | Integrasi Komponen |
|---|---|---|
| **Executive Gateway** | Daemon utama penghubung pesan dan event loop | Node.js Gateway + Telegram Bot API + Baileys WhatsApp |
| **Model Router** | Dynamic routing berdasar kompleksitas & fallback | Anthropic Claude + OpenAI + Ollama Local |
| **Cognitive Memory** | Memori jangka pendek percakapan & RAG dokumen | SQLite Session Store + Vector Embedding Engine |
| **Proactive Engine** | Eksekusi otomatis tanpa menunggu input manusia | Cron Scheduler + Webhook Receiver (HMAC Auth) |
| **Security Guard** | Mitigasi prompt injection, DLP redactor, & HITL gate | Regex Interceptor + Telegram HITL Session Manager |
| **Multi-Agent Pod** | Delegasi tugas spesifik ke worker paralel | Orchestrator + TechAuditor + ResearchWorker |

---

## 5. Technology Stack
- **Runtime Core**: Node.js LTS (v20+), Vanilla Architecture tanpa framework berat.
- **AI Providers**: Anthropic Claude (3.5 Sonnet & Haiku), OpenAI (GPT-4o & mini), Ollama (Qwen 2.5-Coder / Llama 3.2).
- **Messaging Adapters**: `node-telegram-bot-api`, `@whiskeysockets/baileys` (WhatsApp Multi-Device).
- **Security & Sandboxing**: Docker Engine, Linux cgroups, Node.js `crypto` (HMAC-SHA256 & AES-256-GCM).
- **Networking & Hosting**: Ubuntu 24.04 LTS VPS, Tailscale VPN, Systemd Supervisor.

---

## 6. Architecture & System Flow

```text
                                  +---------------------------------------+
                                  |         MESSAGING CHANNELS            |
                                  |   [ Telegram App ]   [ WhatsApp App ] |
                                  +---------------------------------------+
                                                      │
                                                      │ Webhook / WebSocket
                                                      ▼
+---------------------------------------------------------------------------------------------------------+
|                                    OPENCLAW 24/7 EXECUTIVE BUTLER                                       |
|                                                                                                         |
|  +---------------------------+       +----------------------------+       +--------------------------+  |
|  |   Channel Gateway Core    | <===> |     Security Interceptor   | <===> |  Memory & RAG Retrieval  |  |
|  | (Telegram & WA Adapters)  |       | (Prompt Guard + DLP + HITL)|       | (Short-term + Vector DB) |  |
|  +---------------------------+       +----------------------------+       +--------------------------+  |
|               │                                    │                                    │               |
|               ▼                                    ▼                                    ▼               |
|  +---------------------------------------------------------------------------------------------------+  |
|  |                                PRIMARY ORCHESTRATOR DECISION ENGINE                               |  |
|  |                 (Claude 3.5 Sonnet / Routing Fallback to GPT-4o & Local Ollama)                   |  |
|  +---------------------------------------------------------------------------------------------------+  |
|               │                                                                         │               |
|        [Task Delegation]                                                        [Autonomous Triggers]   |
|               ▼                                                                         ▼               |
|  +-------------------------+       +-------------------------+            +---------------------------+ |
|  | Subagent: Researcher    |       | Subagent: DevOps SRE    |            | Proactive Engine          | |
|  | - Web Search & Scraping |       | - Shell Sandboxing      |            | - Cron Daily Brief (07:30)| |
|  | - Parallel Execution    |       | - HITL Approval Gate    |            | - Inbound Webhooks (Sentry)| |
|  +-------------------------+       +-------------------------+            +---------------------------+ |
+---------------------------------------------------------------------------------------------------------+
                                                      │
                                                      ▼
                                       +-----------------------------+
                                       |      HOST INFRASTRUCTURE    |
                                       | - Tailscale Mesh Network    |
                                       | - Systemd Watchdog 24/7     |
                                       | - Encrypted Credential Vault|
                                       +-----------------------------+
```

---

## 7. Implementation Milestones

### Milestone 1: Environment & Credential Vault Setup
1. Inisialisasi struktur workspace OpenClaw:
   ```bash
   openclaw init --workspace ~/openclaw-butler
   ```
2. Buat master password vault untuk menyimpan API keys Anthropic, OpenAI, dan token Telegram Bot:
   ```bash
   openclaw vault set TELEGRAM_BOT_TOKEN "xxxx"
   openclaw vault set ANTHROPIC_API_KEY "xxxx"
   ```
3. Verifikasi kesehatan dependensi:
   ```bash
   openclaw doctor --deep
   ```

### Milestone 2: Multi-Channel Gateway & Memory System
1. Konfigurasikan adapter Telegram polling dan WhatsApp session folder pada `openclaw.json`.
2. Pasang SQLite session store untuk memori riwayat chat percakapan.
3. Inisialisasi vector store embedding untuk dokumen referensi personal pengguna (`notes/`, `projects/`).

### Milestone 3: Security Hardening & HITL Policy
1. Aktifkan sandbox interceptor:
   - Allowlist: `git status`, `uptime`, `df -h`, `curl -I`.
   - HITL Required: `git push`, `docker *`, `systemctl *`, `rm *`.
   - Denylist: `rm -rf /`, `mkfs`, `dd`.
2. Konfigurasikan inline keyboard approval di Telegram bot: jika perintah berisiko terdeteksi, bot mengirim tombol *[ Approve ] / [ Reject ]* dengan timeout 3 menit.
3. Pasang regex DLP Redactor untuk memindai token dan password sebelum dikirim ke chat.

### Milestone 4: Multi-Agent Delegation & Tools
1. Daftarkan 2 subagent pekerja di bawah Orchestrator:
   - `ResearcherSubagent`: Menggunakan model cepat (Claude 3.5 Haiku) dengan tool pencarian web.
   - `DevOpsSubagent`: Menggunakan model coding dengan tool command execution sandbox.
2. Terapkan pola *Map-Reduce* agar Orchestrator dapat menjalankan kedua subagent secara paralel tanpa context bloat.

### Milestone 5: Proactive Automations (Cron & Webhooks)
1. Pasang cron job harian pada jam `07:30` untuk mengirimkan *Morning Briefing* ke Telegram dan WhatsApp:
   - Cuaca hari ini.
   - 3 agenda terpenting.
   - Status kesehatan server VPS.
2. Buka Inbound Webhook listener pada port `18789` yang diproteksi HMAC-SHA256 untuk menerima notifikasi commit/PR GitHub.

### Milestone 6: VPS Deployment 24/7 & Tailscale Integration
1. Buat Systemd service unit `/etc/systemd/system/openclaw.service` dengan parameter `Restart=always`.
2. Konfigurasikan Tailscale pada server:
   - Ikat IP dashboard ke `100.x.y.z` (hanya bisa diakses via private VPN).
   - Blokir semua port publik menggunakan `ufw`.
3. Pasang cron backup snapshot SQLite setiap jam 02:00 pagi.

---

## 8. Testing & Validation Plan

### Scenario 1: Interaktif Chat & Memory Recall
- **Aksi**: User mengetik di Telegram: *"Saya lebih menyukai formatting tabel Markdown untuk data perbandingan."*
- **Verifikasi**: Keesokan harinya, tanyakan: *"Bandingkan fitur A dan B"*. Agent harus otomatis menampilkan output dalam format tabel Markdown tanpa diminta ulang.

### Scenario 2: Human-in-the-Loop Incident Test
- **Aksi**: User meminta agent me-restart service Docker: *"Tolong restart container postgres."*
- **Verifikasi**: Bot tidak langsung mengeksekusi, melainkan mengirim tombol persetujuan di Telegram: *"Agent meminta izin restart container postgres. Izinkan? [Ya] / [Tidak]"*. Setelah ditekan [Ya], container di-restart dan output dilaporkan.

### Scenario 3: Proactive Morning Briefing Trigger
- **Aksi**: Jalankan trigger manual cron briefing via CLI: `openclaw cron run morning-briefing`.
- **Verifikasi**: Notifikasi kaya informasi terkirim secara serentak ke Telegram dan WhatsApp dalam format elegan.

### Scenario 4: Webhook Event-Driven Action
- **Aksi**: Kirim cURL simulasi webhook GitHub PR dengan header `X-Hub-Signature-256`.
- **Verifikasi**: Server mengembalikan HTTP 202 instan, Orchestrator membaca diff, dan ringkasan 3 poin terkirim ke Telegram dalam waktu < 4 detik.

### Scenario 5: Self-Healing Crash Recovery
- **Aksi**: Matikan paksa proses agent menggunakan `kill -9 <PID>`.
- **Verifikasi**: Systemd watchdog mendeteksi crash dan menyalakan kembali service dalam waktu < 5 detik. Tidak ada sesi yang hilang.

---

## 9. Expected Result
Setelah proyek ini selesai dibangun:
- Anda memiliki asisten AI pribadi sekelas *Jarvis / Executive Butler* yang beroperasi 24/7 di VPS Anda sendiri.
- Tidak ada data pribadi atau percakapan yang terpapar ke publik karena seluruh jaringan terisolasi di dalam Tailscale mesh.
- Biaya operasional sangat efisien (< $10/bulan gabungan VPS dan API model routing pintar).
- Sistem aman dari serangan prompt injection dan kesalahan fatal eksekusi shell berkat Human-in-the-Loop.

---

## 10. Possible Improvements
1. **Voice Input/Output Real-Time**: Menambahkan integrasi Whisper STT dan Kokoro/ElevenLabs TTS agar asisten dapat berbicara melalui voice notes WhatsApp/Telegram.
2. **Vision Multi-Modal**: Menambahkan integrasi kamera (Home Assistant / RTSP) agar asisten dapat mengenali paket yang ditaruh kurir di depan pintu rumah secara proaktif.
3. **Local LLM Hybrid Offloading**: Menggunakan hardware GPU lokal untuk menjalankan model Ollama 70B saat siang hari, dan otomatis beralih ke cloud LLM saat malam.

---

## 11. Final Capstone Challenge
**Master Challenge: The Autonomous DevOps Sentinel**
1. Simulasikan insiden server crash (simulasi error 500 di web app).
2. Sistem monitoring memicu Inbound Webhook ke OpenClaw.
3. OpenClaw membaca log error, men-spawn `DevOpsSubagent` untuk mencari penyebabnya.
4. Agent mendeteksi bahwa port database terputus.
5. Agent mengirim prompt persetujuan HITL ke Telegram pemilik dengan ringkasan root cause dan usulan perbaikan:
   > *"Terdeteksi database crash karena connection leak. Saya merekomendasikan restart service dan flush connections. Setujui tindakan ini?"*
6. Pemilik menekan **[ Approve ]** langsung dari smartphone di luar rumah.
7. Agent mengeksekusi perbaikan di sandbox, menguji ulang healthcheck URL, dan mengonfirmasi bahwa web app telah kembali online 100%.

---
*Selamat! Anda telah menyelesaikan seluruh kurikulum **OpenClaw Mastery** dari fondasi hingga arsitektur otonom tingkat lanjut.*
