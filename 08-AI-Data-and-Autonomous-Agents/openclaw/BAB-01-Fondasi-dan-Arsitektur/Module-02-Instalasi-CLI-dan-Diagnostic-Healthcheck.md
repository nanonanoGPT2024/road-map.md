# Module 02: Instalasi CLI, Inisialisasi Workspace, & Diagnostic (`doctor --deep`)

## 1. Learning Objective
Setelah menyelesaikan modul ini, Anda akan mampu:
- Mempersiapkan environment sistem dan menginstal **OpenClaw CLI** secara benar di berbagai sistem operasi.
- Menjalankan inisialisasi workspace (`openclaw init` & `openclaw onboard`) dan memahami struktur direktori konfigurasi.
- Mengelola siklus hidup proses daemon (`openclaw start`, `status`, `logs`, `stop`).
- Menjalankan audit kesehatan dan pemecahan masalah mendalam menggunakan perintah diagnostik **`openclaw doctor`** dan **`openclaw doctor --deep`**.

## 2. Prerequisite
- Memahami konsep dasar OpenClaw Gateway Daemon dari Module 01.
- Terbiasa menggunakan Command Line Interface (CLI / PowerShell / Bash).
- Memiliki Node.js (versi >= 18.x) atau runtime Docker terinstal di mesin Anda.

## 3. Concept
Menyiapkan asisten AI pribadi yang selalu aktif (24/7) membutuhkan konfigurasi yang lebih komprehensif dibandingkan memasang aplikasi desktop biasa. Karena OpenClaw berinteraksi dengan:
- **Jaringan Luar**: Membuka koneksi socket ke server Telegram/Discord dan API provider AI.
- **Sistem Operasi Lokal**: Membaca file konfigurasi rahasia, mengakses database sesi lokal, dan mengeksekusi script.

Oleh karena itu, OpenClaw menyediakan perkakas onboarding interaktif dan subsistem diagnostik mandiri (**Self-Healing Diagnostic Engine**) melalui perintah `doctor` untuk memastikan seluruh permission, socket, API key, dan service dependency berada dalam kondisi prima sebelum agen diizinkan berjalan di background.

## 4. Why?
- **Mencegah Masalah "Silent Failure"**: Jika token Telegram salah atau koneksi API OpenAI terblokir firewall kantor, daemon yang berjalan di background tidak akan memunculkan popup error di layar. Tanpa alat diagnostik, Anda akan bingung mengapa bot tidak merespons di ponsel.
- **Validasi Keamanan Awal**: Memastikan izin berkas konfigurasi (`openclaw.json`) tidak dapat dibaca oleh user lain di server bersama (*Shared VPS*).
- **Automated Dependency Check**: Memverifikasi ketersediaan tools pendukung seperti `git`, `ffmpeg` (untuk transkripsi voice note), dan `curl`.

## 5. What?
### 1. Struktur Direktori Workspace OpenClaw (`~/.openclaw/`):
```text
~/.openclaw/
│
├── config.json              (Pengaturan utama: providers, channels, security)
├── .env                     (API Keys rahasia: OPENAI_API_KEY, TELEGRAM_BOT_TOKEN)
├── state/
│   ├── sessions.db          (SQLite database: riwayat obrolan & konteks)
│   └── daemon.pid           (Process ID daemon yang sedang aktif)
├── logs/
│   ├── gateway.log          (Log aktivitas operasional harian)
│   └── error.log            (Log tracing jika terjadi kegagalan)
└── skills/                  (Direktori custom skills lokal buatan Anda)
    ├── weather/
    └── server-monitor/
```

### 2. Peta Perintah Utama OpenClaw CLI:
- `openclaw init`: Membuat struktur folder workspace dan template konfigurasi default.
- `openclaw onboard`: Wizard interaktif untuk memandu input token bot Telegram, WhatsApp pairing, dan LLM API key.
- `openclaw start [--daemon]`: Menjalankan Gateway Daemon di latar belakang.
- `openclaw status`: Menampilkan status proses daemon, konsumsi memori, dan kanal aktif.
- `openclaw logs -f`: Mengalirkan (*stream*) log aktivitas agen secara real-time.
- `openclaw doctor`: Memeriksa kelayakan environment dasar.
- `openclaw doctor --deep`: Melakukan pengujian konektivitas mendalam (test ping ke API AI, uji handshake Telegram, cek integritas database SQLite).

## 6. How?
### Langkah Instalasi & Onboarding:
1. **Instalasi Paket CLI**:
   ```bash
   # Melalui NPM Global
   npm install -g openclaw-cli
   
   # Atau menggunakan installer script mandiri (Linux/macOS)
   curl -fsSL https://openclaw.ai/install.sh | bash
   ```
2. **Inisialisasi & Onboarding Wizard**:
   ```bash
   openclaw init
   openclaw onboard
   ```
   *Wizard akan menanyakan:*
   - Kanal komunikasi mana yang ingin diaktifkan? (Pilih: Telegram / Discord)
   - Masukkan Telegram Bot Token (didapat dari `@BotFather`).
   - Masukkan Telegram Chat ID Pemilik (untuk whitelist keamanan).
   - Masukkan API Key Provider utama (misal: Google Gemini API / Anthropic).
3. **Uji Kelayakan dengan Diagnostic Deep Check**:
   ```bash
   openclaw doctor --deep
   ```
4. **Jalankan Daemon 24/7**:
   ```bash
   openclaw start --daemon
   ```

## 7. Analogy
- **`openclaw onboard` = Wawancara Kerja & Orientasi Asisten Baru**: Anda membagikan kunci rumah (API key), nomor telepon Anda (Chat ID Whitelist), dan memberi tahu daftar tugas harian asisten Anda.
- **`openclaw doctor --deep` = Pemeriksaan Medis & Kelayakan Terbang Pilot (Pre-flight Checklist)**: Sebelum pesawat lepas landas (daemon aktif), teknisi mengecek seluruh sistem hidrolik, bahan bakar, dan radar. Jika ada satu indikator merah, pesawat tidak diizinkan terbang.

## 8. Diagram

```text
================ ALUR DIAGNOSTIK 'openclaw doctor --deep' ================

               [Jalankan: openclaw doctor --deep]
                               │
       ┌───────────────────────┼───────────────────────┐
       ▼                       ▼                       ▼
[1. System Checks]     [2. Security Checks]   [3. Provider Ping]
 ├── Node.js >= 18?     ├── Perms 600 config?  ├── OpenAI API Ping?
 ├── SQLite writable?   ├── Whitelist set?     ├── Gemini API Ping?
 └── Disk > 1 GB?       └── No plain secrets?  └── Ollama running?
       │                       │                       │
       └───────────────────────┼───────────────────────┘
                               │
                               ▼
                    [4. Channel Handshakes]
                     ├── Telegram getMe OK?
                     └── Discord WebSocket OK?
                               │
               ┌───────────────┴───────────────┐
               ▼                               ▼
       [Semua Hijau: PASS]             [Ada Masalah: FAIL]
     -> Siap Start Daemon!           -> Cetak Panduan Perbaikan!
```

## 9. Simple Example: Format Berkas Konfigurasi `config.json`
```json
{
  "version": "1.0",
  "gateway": {
    "port": 18800,
    "logLevel": "info"
  },
  "security": {
    "ownerChatId": "99881122",
    "allowAnonymous": false,
    "shellExecution": "prompt_confirmation"
  },
  "providers": {
    "default": "gemini-flash",
    "list": {
      "gemini-flash": { "type": "google", "model": "gemini-2.0-flash" },
      "claude-sonnet": { "type": "anthropic", "model": "claude-3-5-sonnet-20241022" }
    }
  },
  "channels": {
    "telegram": {
      "enabled": true,
      "mode": "polling"
    }
  }
}
```

## 10. Practical Example: Menangani File Permission Vulnerability
Jika file `config.json` memiliki permission `0644` di Linux, pengguna lain di VPS yang sama dapat membaca API token Anda.
Perintah `openclaw doctor` mendeteksi celah ini dan menyarankan:
```bash
chmod 600 ~/.openclaw/config.json
chmod 600 ~/.openclaw/.env
```
Setelah permission diubah menjadi `0600`, hanya akun user pemilik yang dapat membaca dan memodifikasi file tersebut.

## 11. Real World Example
- **Automated Health Monitoring di Serverless / Docker**: Tim platform engineer menjalankan perintah `openclaw doctor --deep --json` di dalam `HEALTHCHECK` container Docker. Jika koneksi ke Telegram terputus selama 3 menit, Kubernetes otomatis me-restart container pod untuk memulihkan koneksi socket.

## 12. Trade-offs

| Metode Eksekusi | Kelebihan | Kekurangan |
|---|---|---|
| **Foreground (`openclaw start`)** | Log langsung muncul di terminal, mudah debug | Berhenti berjalan jika terminal ditutup |
| **Background Daemon (`--daemon`)**| Terus berjalan di latar belakang (unattended) | Membutuhkan perintah `logs` untuk memantau error |
| **Systemd Service (Linux)** | Otomatis menyala saat server restart (*auto-boot*) | Memerlukan hak akses `sudo` saat setup awal |
| **Docker Container** | Terisolasi penuh dari OS host, zero dependency clash | Setup volume mapping untuk persistensi data SQLite |

## 13. When To Use
- Gunakan `openclaw doctor` setiap kali setelah melakukan instalasi baru, memperbarui versi CLI, atau mengganti API key provider.
- Gunakan `openclaw doctor --deep` saat agen tiba-tiba tidak merespons pesan teks dari aplikasi perpesanan Anda.

## 14. When NOT To Use
- Jangan jalankan `doctor --deep` secara terus-menerus dalam interval detik di cron loop, karena pengujian ping ke provider AI menghabiskan kuota request rate-limit Anda.

## 15. Common Mistakes
1. **Lupa Menutup Daemon Lama Sebelum Start Baru**: Menjalankan `openclaw start` saat instance daemon lama masih berjalan. Dua proses akan berebut membaca socket Telegram yang sama (*Socket Lock Conflict*).
2. **Menyimpan API Key di `config.json` yang Ter-commit ke Git**: Jangan pernah memasukkan API key langsung di `config.json` publik! Gunakan file `.env` yang masuk ke `.gitignore`.
3. **Mengabaikan Peringatan `doctor`**: Mengabaikan status peringatan kuning tentang sisa disk rendah, yang menyebabkan SQLite database corrupt saat disk 100% penuh.

## 16. Best Practices
- **Jalankan Self-Check Sebelum Start**: Selalu biasakan alur: `openclaw doctor && openclaw start --daemon`.
- **Gunakan Process Manager yang Andal**: Di server Linux production, pasang OpenClaw sebagai service `systemd` (`openclaw service install`) agar otomatis restart jika mesin mengalami reboot berkala.
- **Log Rotation**: Aktifkan rotasi berkas log di `gateway.log` agar tidak memakan kapasitas disk setelah beroperasi berbulan-bulan.

## 17. Troubleshooting
- **Masalah: Error `EADDRINUSE: Address already in use :::18800` saat menjalankan daemon**.
  - *Sebab*: Port gateway internal sedang dipakai oleh instance OpenClaw yang hang atau aplikasi lain.
  - *Solusi*: Jalankan `openclaw stop --force` atau cari PID yang mengunci port dengan `lsof -i :18800` lalu matikan dengan `kill -9 <PID>`.

## 18. Hands-on Practice
Mari kita buktikan implementasi nyata dari engine diagnostik sistem melalui script laboratorium mandiri di `hands-on/m02/doctor_diagnostic_tool.js`.

## 19. Exercises & Challenge
- **Exercise**: Buat daftar 5 komponen utama yang wajib diverifikasi oleh perintah `openclaw doctor --deep` sebelum menyatakan gateway sehat.
- **Challenge**: Rancang script automated watchdog sederhana yang menjalankan `openclaw doctor` setiap 6 jam dan mengirimkan peringatan jika salah satu status berlabel `FAIL`.

## 20. Summary
Kelancaran operasional asisten AI mandiri 24/7 bergantung pada fondasi instalasi yang kokoh. Dengan menguasai perkakas CLI OpenClaw, struktur konfigurasi workspace, dan instrumen diagnostik `openclaw doctor --deep`, Anda dapat mendeteksi dan menyelesaikan anomali infrastruktur sebelum mengganggu aktivitas Anda.
